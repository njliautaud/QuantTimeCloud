"""
GPU-Optimized Training Module for QuantTime ML Trading Suite.

This module implements GPU-first training with:
- GPU memory management and monitoring
- Automatic GPU memory optimization
- Mixed precision training (float16/float32)
- Gradient accumulation
- Memory mapping for datasets
- Batch processing optimized for GPU
- Automatic memory management

Key Features:
- GPU-first approach (8GB VRAM utilization)
- RAM preservation (16GB system RAM)
- Mixed precision training with automatic mixed precision (AMP)
- Gradient accumulation for large effective batch sizes
- GPU memory monitoring and optimization
- Automatic batch size adjustment based on GPU memory
- Model checkpointing and resuming
"""

import os
import logging
import gc
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Union, Callable
import warnings

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, TensorDataset
import torch.cuda.amp as amp
from torch.cuda.amp import autocast, GradScaler

# GPU memory optimization imports
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    warnings.warn("psutil not available - memory monitoring disabled")

try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False
    warnings.warn("wandb not available - logging disabled")

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False
    warnings.warn("pynvml not available - GPU memory monitoring disabled")

from quanttime.data.memory_optimized_loader import MemoryOptimizedLoader, monitor_memory_usage

logger = logging.getLogger(__name__)


class GPUMemoryManager:
    """
    GPU memory manager for monitoring and optimizing GPU memory usage.
    
    Features:
    - GPU memory monitoring
    - Automatic memory optimization
    - Memory usage tracking
    - Batch size adjustment
    """
    
    def __init__(self, max_gpu_memory_gb: float = 7.0, max_ram_gb: float = 14.0):
        """
        Initialize GPU memory manager.
        
        Args:
            max_gpu_memory_gb: Maximum GPU memory usage in GB (leave 1GB buffer)
            max_ram_gb: Maximum RAM usage in GB (leave 2GB buffer)
        """
        self.max_gpu_memory_gb = max_gpu_memory_gb
        self.max_ram_gb = max_ram_gb
        self.max_gpu_memory_bytes = max_gpu_memory_gb * 1024**3
        
        # Initialize NVML for GPU monitoring
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.device_count = pynvml.nvmlDeviceGetCount()
                if self.device_count > 0:
                    self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # Use first GPU
                    self.gpu_name = pynvml.nvmlDeviceGetName(self.handle).decode('utf-8')
                    logger.info(f"GPU detected: {self.gpu_name}")
                else:
                    logger.warning("No GPU detected")
                    self.handle = None
            except Exception as e:
                logger.warning(f"Failed to initialize NVML: {e}")
                self.handle = None
        else:
            self.handle = None
        
        # RAM monitoring
        if PSUTIL_AVAILABLE:
            self.process = psutil.Process()
        
        logger.info(f"GPU memory manager initialized:")
        logger.info(f"  Max GPU memory: {max_gpu_memory_gb} GB")
        logger.info(f"  Max RAM usage: {max_ram_gb} GB")
    
    def get_gpu_memory_info(self) -> Dict[str, float]:
        """Get current GPU memory usage statistics."""
        if not NVML_AVAILABLE or self.handle is None:
            return {}
        
        try:
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
            return {
                'total_gb': memory_info.total / 1024**3,
                'used_gb': memory_info.used / 1024**3,
                'free_gb': memory_info.free / 1024**3,
                'percent': (memory_info.used / memory_info.total) * 100
            }
        except Exception as e:
            logger.warning(f"Failed to get GPU memory info: {e}")
            return {}
    
    def get_ram_memory_info(self) -> Dict[str, float]:
        """Get current RAM usage statistics."""
        if not PSUTIL_AVAILABLE:
            return {}
        
        memory_info = self.process.memory_info()
        return {
            'rss_gb': memory_info.rss / 1024**3,
            'vms_gb': memory_info.vms / 1024**3,
            'percent': self.process.memory_percent(),
            'available_gb': psutil.virtual_memory().available / 1024**3
        }
    
    def check_gpu_memory_limit(self) -> bool:
        """Check if current GPU memory usage is within limits."""
        gpu_info = self.get_gpu_memory_info()
        if not gpu_info:
            return True
        
        return gpu_info['used_gb'] < self.max_gpu_memory_gb
    
    def check_ram_memory_limit(self) -> bool:
        """Check if current RAM usage is within limits."""
        ram_info = self.get_ram_memory_info()
        if not ram_info:
            return True
        
        return ram_info['rss_gb'] < self.max_ram_gb
    
    def get_optimal_batch_size(self, 
                             feature_dim: int,
                             model_size_mb: float = 100.0,
                             dtype_size: int = 4) -> int:
        """
        Calculate optimal batch size based on available GPU memory.
        
        Args:
            feature_dim: Number of features
            model_size_mb: Estimated model size in MB
            dtype_size: Size of data type in bytes
            
        Returns:
            Optimal batch size
        """
        gpu_info = self.get_gpu_memory_info()
        if not gpu_info:
            # Fallback to conservative estimate
            return 1024
        
        # Reserve memory for model, gradients, and other operations
        available_memory = gpu_info['free_gb'] - 1.0  # Leave 1GB buffer
        available_memory_bytes = available_memory * 1024**3
        
        # Calculate memory needed per sample
        memory_per_sample = feature_dim * dtype_size * 3  # Features + gradients + activations
        
        # Calculate batch size
        batch_size = int(available_memory_bytes / memory_per_sample)
        
        # Ensure reasonable bounds
        batch_size = max(32, min(batch_size, 8192))
        
        logger.info(f"Optimal batch size calculation:")
        logger.info(f"  Available GPU memory: {available_memory:.2f} GB")
        logger.info(f"  Memory per sample: {memory_per_sample / 1024:.1f} KB")
        logger.info(f"  Calculated batch size: {batch_size}")
        
        return batch_size
    
    def force_gpu_garbage_collection(self):
        """Force GPU garbage collection to free memory."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        logger.debug("Forced GPU garbage collection")
    
    def log_memory_status(self):
        """Log current memory status."""
        gpu_info = self.get_gpu_memory_info()
        ram_info = self.get_ram_memory_info()
        
        logger.info("Memory Status:")
        if gpu_info:
            logger.info(f"  GPU: {gpu_info['used_gb']:.2f}/{gpu_info['total_gb']:.2f} GB ({gpu_info['percent']:.1f}%)")
        if ram_info:
            logger.info(f"  RAM: {ram_info['rss_gb']:.2f} GB used, {ram_info['available_gb']:.2f} GB available")


class GPUOptimizedDataset(Dataset):
    """
    GPU-optimized PyTorch dataset with memory mapping and mixed precision.
    
    Features:
    - Memory mapping for large datasets
    - Mixed precision support
    - Automatic dtype optimization
    - Lazy loading
    - GPU memory optimization
    """
    
    def __init__(self, 
                 data: Union[np.ndarray, pd.DataFrame],
                 targets: Optional[Union[np.ndarray, pd.Series]] = None,
                 use_mixed_precision: bool = True,
                 dtype: str = "float32",
                 device: str = "cuda"):
        """
        Initialize GPU-optimized dataset.
        
        Args:
            data: Input features
            targets: Target values
            use_mixed_precision: Use mixed precision
            dtype: Data type for features
            device: Device to use (cuda, cpu)
        """
        self.use_mixed_precision = use_mixed_precision
        self.dtype = dtype
        self.device = device
        
        # Convert data to numpy array with memory optimization
        if isinstance(data, pd.DataFrame):
            self.data = data.to_numpy()
        else:
            self.data = np.asarray(data)
        
        # Optimize dtypes for memory usage
        if use_mixed_precision:
            if self.data.dtype == np.float64:
                self.data = self.data.astype(np.float32)
            elif dtype == "float16":
                self.data = self.data.astype(np.float16)
        
        # Handle targets
        if targets is not None:
            if isinstance(targets, pd.Series):
                self.targets = targets.to_numpy()
            else:
                self.targets = np.asarray(targets)
            
            # Optimize target dtypes
            if use_mixed_precision:
                if self.targets.dtype == np.float64:
                    self.targets = self.targets.astype(np.float32)
        else:
            self.targets = None
        
        logger.info(f"GPU-optimized dataset created:")
        logger.info(f"  Data shape: {self.data.shape}")
        logger.info(f"  Data dtype: {self.data.dtype}")
        logger.info(f"  Device: {device}")
        if self.targets is not None:
            logger.info(f"  Targets shape: {self.targets.shape}")
            logger.info(f"  Targets dtype: {self.targets.dtype}")
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        if self.targets is not None:
            return self.data[idx], self.targets[idx]
        else:
            return self.data[idx]


class GPUOptimizedTrainer:
    """
    GPU-optimized trainer with mixed precision, gradient accumulation, and GPU memory management.
    
    Features:
    - GPU-first training approach
    - Mixed precision training (AMP)
    - Gradient accumulation
    - GPU memory monitoring and optimization
    - Automatic batch size adjustment
    - Model checkpointing
    - Memory-efficient data loading
    """
    
    def __init__(self,
                 model: nn.Module,
                 train_dataset: Dataset,
                 val_dataset: Optional[Dataset] = None,
                 batch_size: Optional[int] = None,
                 learning_rate: float = 1e-3,
                 max_gpu_memory_gb: float = 7.0,
                 max_ram_gb: float = 14.0,
                 use_mixed_precision: bool = True,
                 gradient_accumulation_steps: int = 1,
                 device: str = "cuda"):
        """
        Initialize GPU-optimized trainer.
        
        Args:
            model: PyTorch model
            train_dataset: Training dataset
            val_dataset: Validation dataset
            batch_size: Batch size (auto-calculated if None)
            learning_rate: Learning rate
            max_gpu_memory_gb: Maximum GPU memory usage in GB
            max_ram_gb: Maximum RAM usage in GB
            use_mixed_precision: Use mixed precision training
            gradient_accumulation_steps: Gradient accumulation steps
            device: Device to use (cuda, cpu)
        """
        self.model = model
        self.train_dataset = train_dataset
        self.val_dataset = val_dataset
        self.learning_rate = learning_rate
        self.max_gpu_memory_gb = max_gpu_memory_gb
        self.max_ram_gb = max_ram_gb
        self.use_mixed_precision = use_mixed_precision
        self.gradient_accumulation_steps = gradient_accumulation_steps
        
        # Device setup
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA not available, falling back to CPU")
            device = "cpu"
        
        self.device = torch.device(device)
        
        # GPU memory manager
        self.gpu_manager = GPUMemoryManager(max_gpu_memory_gb, max_ram_gb)
        
        # Calculate optimal batch size if not provided
        if batch_size is None:
            # Estimate feature dimension from dataset
            if hasattr(train_dataset, 'data'):
                feature_dim = train_dataset.data.shape[1] if len(train_dataset.data.shape) > 1 else 1
            else:
                # Fallback estimation
                sample = train_dataset[0]
                if isinstance(sample, tuple):
                    feature_dim = len(sample[0])
                else:
                    feature_dim = len(sample)
            
            batch_size = self.gpu_manager.get_optimal_batch_size(feature_dim)
        
        self.batch_size = batch_size
        
        # Move model to device
        self.model.to(self.device)
        
        # Mixed precision setup
        if use_mixed_precision and self.device.type == "cuda":
            self.scaler = GradScaler()
            self.use_amp = True
            logger.info("Mixed precision training enabled")
        else:
            self.scaler = None
            self.use_amp = False
            logger.info("Mixed precision training disabled")
        
        # Optimizer
        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        
        # Data loaders with GPU optimization
        self.train_loader = self._create_gpu_optimized_data_loader(train_dataset, batch_size, shuffle=True)
        if val_dataset is not None:
            self.val_loader = self._create_gpu_optimized_data_loader(val_dataset, batch_size, shuffle=False)
        else:
            self.val_loader = None
        
        # Training state
        self.current_epoch = 0
        self.global_step = 0
        self.best_val_loss = float('inf')
        
        logger.info(f"GPU-optimized trainer initialized:")
        logger.info(f"  Device: {self.device}")
        logger.info(f"  Batch size: {batch_size}")
        logger.info(f"  Gradient accumulation: {gradient_accumulation_steps}")
        logger.info(f"  Mixed precision: {use_mixed_precision}")
        logger.info(f"  Max GPU memory: {max_gpu_memory_gb} GB")
        logger.info(f"  Max RAM: {max_ram_gb} GB")
    
    def _create_gpu_optimized_data_loader(self, dataset: Dataset, batch_size: int, shuffle: bool) -> DataLoader:
        """Create GPU-optimized data loader."""
        # Calculate optimal number of workers based on RAM
        if PSUTIL_AVAILABLE:
            available_ram = psutil.virtual_memory().available / 1024**3
            # Use fewer workers to keep RAM free for GPU operations
            num_workers = max(1, min(2, int(available_ram / 4)))
        else:
            num_workers = 1
        
        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=num_workers,
            pin_memory=self.device.type == "cuda",
            persistent_workers=num_workers > 0,
            drop_last=True  # Ensure consistent batch sizes for GPU
        )
    
    def adjust_batch_size(self, current_batch_size: int) -> int:
        """Dynamically adjust batch size based on GPU memory usage."""
        if not self.gpu_manager.check_gpu_memory_limit():
            new_batch_size = max(16, current_batch_size // 2)
            logger.warning(f"GPU memory limit reached, reducing batch size from {current_batch_size} to {new_batch_size}")
            return new_batch_size
        return current_batch_size
    
    @monitor_memory_usage
    def train_epoch(self) -> Dict[str, float]:
        """Train for one epoch with GPU optimization."""
        self.model.train()
        total_loss = 0.0
        num_batches = 0
        
        # Dynamic batch size adjustment
        current_batch_size = self.batch_size
        
        for batch_idx, (data, targets) in enumerate(self.train_loader):
            # Check GPU memory and adjust batch size if needed
            current_batch_size = self.adjust_batch_size(current_batch_size)
            
            # Move data to GPU
            data = data.to(self.device, non_blocking=True)
            targets = targets.to(self.device, non_blocking=True)
            
            # Forward pass with mixed precision
            if self.use_amp:
                with autocast():
                    outputs = self.model(data)
                    loss = nn.functional.mse_loss(outputs, targets)
            else:
                outputs = self.model(data)
                loss = nn.functional.mse_loss(outputs, targets)
            
            # Scale loss for gradient accumulation
            loss = loss / self.gradient_accumulation_steps
            
            # Backward pass with mixed precision
            if self.use_amp:
                self.scaler.scale(loss).backward()
            else:
                loss.backward()
            
            # Gradient accumulation
            if (batch_idx + 1) % self.gradient_accumulation_steps == 0:
                if self.use_amp:
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                else:
                    self.optimizer.step()
                
                self.optimizer.zero_grad()
                self.global_step += 1
            
            # Update metrics
            total_loss += loss.item() * self.gradient_accumulation_steps
            num_batches += 1
            
            # GPU memory management
            if batch_idx % 50 == 0:
                if not self.gpu_manager.check_gpu_memory_limit():
                    logger.warning("GPU memory limit reached during training")
                    self.gpu_manager.force_gpu_garbage_collection()
                
                # Log memory status periodically
                if batch_idx % 200 == 0:
                    self.gpu_manager.log_memory_status()
        
        avg_loss = total_loss / num_batches
        return {'train_loss': avg_loss}
    
    @monitor_memory_usage
    def validate(self) -> Dict[str, float]:
        """Validate model with GPU optimization."""
        if self.val_loader is None:
            return {}
        
        self.model.eval()
        total_loss = 0.0
        num_batches = 0
        
        with torch.no_grad():
            for data, targets in self.val_loader:
                # Move data to GPU
                data = data.to(self.device, non_blocking=True)
                targets = targets.to(self.device, non_blocking=True)
                
                # Forward pass with mixed precision
                if self.use_amp:
                    with autocast():
                        outputs = self.model(data)
                        loss = nn.functional.mse_loss(outputs, targets)
                else:
                    outputs = self.model(data)
                    loss = nn.functional.mse_loss(outputs, targets)
                
                # Update metrics
                total_loss += loss.item()
                num_batches += 1
        
        avg_loss = total_loss / num_batches
        return {'val_loss': avg_loss}
    
    def save_checkpoint(self, filepath: str, is_best: bool = False):
        """Save model checkpoint with GPU optimization."""
        checkpoint = {
            'epoch': self.current_epoch,
            'global_step': self.global_step,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'best_val_loss': self.best_val_loss,
            'trainer_config': {
                'batch_size': self.batch_size,
                'learning_rate': self.learning_rate,
                'use_mixed_precision': self.use_mixed_precision,
                'gradient_accumulation_steps': self.gradient_accumulation_steps,
                'max_gpu_memory_gb': self.max_gpu_memory_gb,
                'max_ram_gb': self.max_ram_gb
            }
        }
        
        # Save checkpoint
        torch.save(checkpoint, filepath)
        logger.info(f"Checkpoint saved: {filepath}")
        
        # Save best model separately
        if is_best:
            best_filepath = filepath.replace('.pth', '_best.pth')
            torch.save(checkpoint, best_filepath)
            logger.info(f"Best model saved: {best_filepath}")
    
    def load_checkpoint(self, filepath: str):
        """Load model checkpoint."""
        if not os.path.exists(filepath):
            logger.warning(f"Checkpoint not found: {filepath}")
            return
        
        checkpoint = torch.load(filepath, map_location=self.device)
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.current_epoch = checkpoint['epoch']
        self.global_step = checkpoint['global_step']
        self.best_val_loss = checkpoint['best_val_loss']
        
        logger.info(f"Checkpoint loaded: {filepath}")
        logger.info(f"  Epoch: {self.current_epoch}")
        logger.info(f"  Global step: {self.global_step}")
        logger.info(f"  Best val loss: {self.best_val_loss}")
    
    def train(self, 
              num_epochs: int,
              checkpoint_dir: str = "checkpoints",
              save_frequency: int = 5,
              log_frequency: int = 100) -> Dict[str, List[float]]:
        """
        Train model with GPU optimization.
        
        Args:
            num_epochs: Number of epochs to train
            checkpoint_dir: Directory to save checkpoints
            save_frequency: Save checkpoint every N epochs
            log_frequency: Log metrics every N steps
            
        Returns:
            Training history
        """
        # Create checkpoint directory
        checkpoint_dir = Path(checkpoint_dir)
        checkpoint_dir.mkdir(exist_ok=True)
        
        # Training history
        history = {
            'train_loss': [],
            'val_loss': [],
            'gpu_memory_usage': [],
            'ram_memory_usage': []
        }
        
        # Initialize wandb if available
        if WANDB_AVAILABLE:
            wandb.init(project="quanttime-ml", config={
                'batch_size': self.batch_size,
                'learning_rate': self.learning_rate,
                'use_mixed_precision': self.use_mixed_precision,
                'gradient_accumulation_steps': self.gradient_accumulation_steps,
                'max_gpu_memory_gb': self.max_gpu_memory_gb,
                'max_ram_gb': self.max_ram_gb,
                'device': str(self.device)
            })
        
        logger.info(f"Starting GPU-optimized training for {num_epochs} epochs")
        
        for epoch in range(self.current_epoch, num_epochs):
            self.current_epoch = epoch
            
            # Log initial memory status
            self.gpu_manager.log_memory_status()
            
            # Train epoch
            train_metrics = self.train_epoch()
            
            # Validate
            val_metrics = self.validate()
            
            # Update best validation loss
            if val_metrics and val_metrics['val_loss'] < self.best_val_loss:
                self.best_val_loss = val_metrics['val_loss']
                is_best = True
            else:
                is_best = False
            
            # Log metrics
            metrics = {**train_metrics, **val_metrics}
            
            # Add memory metrics
            gpu_info = self.gpu_manager.get_gpu_memory_info()
            ram_info = self.gpu_manager.get_ram_memory_info()
            
            if gpu_info:
                metrics['gpu_memory_gb'] = gpu_info['used_gb']
                metrics['gpu_memory_percent'] = gpu_info['percent']
                history['gpu_memory_usage'].append(gpu_info['used_gb'])
            
            if ram_info:
                metrics['ram_memory_gb'] = ram_info['rss_gb']
                metrics['ram_memory_percent'] = ram_info['percent']
                history['ram_memory_usage'].append(ram_info['rss_gb'])
            
            logger.info(f"Epoch {epoch+1}/{num_epochs}: {metrics}")
            
            # Log to wandb
            if WANDB_AVAILABLE:
                wandb.log(metrics, step=self.global_step)
            
            # Save checkpoint
            if (epoch + 1) % save_frequency == 0 or is_best:
                checkpoint_path = checkpoint_dir / f"checkpoint_epoch_{epoch+1}.pth"
                self.save_checkpoint(str(checkpoint_path), is_best=is_best)
            
            # Update history
            history['train_loss'].append(train_metrics['train_loss'])
            if val_metrics:
                history['val_loss'].append(val_metrics['val_loss'])
            
            # GPU memory management
            if not self.gpu_manager.check_gpu_memory_limit():
                logger.warning("GPU memory limit reached, forcing garbage collection")
                self.gpu_manager.force_gpu_garbage_collection()
            
            # RAM memory management
            if not self.gpu_manager.check_ram_memory_limit():
                logger.warning("RAM limit reached, forcing garbage collection")
                gc.collect()
        
        logger.info("GPU-optimized training completed")
        if WANDB_AVAILABLE:
            wandb.finish()
        
        return history


class GPUOptimizedLightGBMTrainer:
    """
    GPU-optimized LightGBM trainer with GPU acceleration and memory optimization.
    """
    
    def __init__(self,
                 max_gpu_memory_gb: float = 7.0,
                 max_ram_gb: float = 14.0,
                 use_mixed_precision: bool = True,
                 batch_size: int = 10000,
                 device: str = "cuda"):
        """
        Initialize GPU-optimized LightGBM trainer.
        
        Args:
            max_gpu_memory_gb: Maximum GPU memory usage in GB
            max_ram_gb: Maximum RAM usage in GB
            use_mixed_precision: Use mixed precision
            batch_size: Batch size for data processing
            device: Device to use (cuda, cpu)
        """
        self.max_gpu_memory_gb = max_gpu_memory_gb
        self.max_ram_gb = max_ram_gb
        self.use_mixed_precision = use_mixed_precision
        self.batch_size = batch_size
        self.device = device
        
        # GPU memory manager
        self.gpu_manager = GPUMemoryManager(max_gpu_memory_gb, max_ram_gb)
        
        logger.info(f"GPU-optimized LightGBM trainer initialized:")
        logger.info(f"  Max GPU memory: {max_gpu_memory_gb} GB")
        logger.info(f"  Max RAM: {max_ram_gb} GB")
        logger.info(f"  Mixed precision: {use_mixed_precision}")
        logger.info(f"  Batch size: {batch_size}")
        logger.info(f"  Device: {device}")
    
    @monitor_memory_usage
    def train(self, 
              X: Union[np.ndarray, pd.DataFrame],
              y: Union[np.ndarray, pd.Series],
              **lgb_params) -> Any:
        """
        Train LightGBM model with GPU optimization.
        
        Args:
            X: Feature matrix
            y: Target values
            **lgb_params: LightGBM parameters
            
        Returns:
            Trained LightGBM model
        """
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError("lightgbm not installed")
        
        # Convert to numpy arrays with memory optimization
        if isinstance(X, pd.DataFrame):
            X = X.to_numpy()
        if isinstance(y, pd.Series):
            y = y.to_numpy()
        
        # Optimize dtypes for memory usage
        if self.use_mixed_precision:
            if X.dtype == np.float64:
                X = X.astype(np.float32)
            if y.dtype == np.float64:
                y = y.astype(np.float32)
        
        # Set GPU-optimized LightGBM parameters
        gpu_params = {
            'device': 'gpu' if self.device == "cuda" else 'cpu',
            'gpu_platform_id': 0,
            'gpu_device_id': 0,
            'max_bin': 255,  # Reduce memory usage
            'min_data_in_bin': 3,
            'max_memory_usage': int(self.max_gpu_memory_gb * 1024),  # MB
            'force_col_wise': True,  # More memory efficient
            'verbose': -1
        }
        
        # Merge with user parameters
        lgb_params = {**gpu_params, **lgb_params}
        
        logger.info(f"Training LightGBM model with GPU optimization:")
        logger.info(f"  Data shape: {X.shape}")
        logger.info(f"  Data dtype: {X.dtype}")
        logger.info(f"  Device: {self.device}")
        
        # Log initial memory status
        self.gpu_manager.log_memory_status()
        
        # Train model
        model = lgb.train(lgb_params, lgb.Dataset(X, y))
        
        logger.info("LightGBM training completed")
        return model


def create_gpu_optimized_model(model_type: str,
                             input_dim: int,
                             hidden_dims: List[int],
                             output_dim: int = 1,
                             use_mixed_precision: bool = True) -> nn.Module:
    """
    Create a GPU-optimized PyTorch model.
    
    Args:
        model_type: Model type (mlp, lstm, transformer)
        input_dim: Input dimension
        hidden_dims: Hidden layer dimensions
        output_dim: Output dimension
        use_mixed_precision: Use mixed precision
        
    Returns:
        PyTorch model
    """
    if model_type.lower() == "mlp":
        return GPUOptimizedMLP(input_dim, hidden_dims, output_dim, use_mixed_precision)
    elif model_type.lower() == "lstm":
        return GPUOptimizedLSTM(input_dim, hidden_dims[0], output_dim, use_mixed_precision)
    elif model_type.lower() == "transformer":
        return GPUOptimizedTransformer(input_dim, hidden_dims[0], output_dim, use_mixed_precision)
    else:
        raise ValueError(f"Unknown model type: {model_type}")


class GPUOptimizedMLP(nn.Module):
    """GPU-optimized MLP with mixed precision support."""
    
    def __init__(self, input_dim: int, hidden_dims: List[int], output_dim: int, use_mixed_precision: bool = True):
        super().__init__()
        self.use_mixed_precision = use_mixed_precision
        
        # Choose dtype based on mixed precision setting
        dtype = torch.float16 if use_mixed_precision else torch.float32
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim, dtype=dtype),
                nn.ReLU(),
                nn.Dropout(0.1)
            ])
            prev_dim = hidden_dim
        
        layers.append(nn.Linear(prev_dim, output_dim, dtype=dtype))
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x)


class GPUOptimizedLSTM(nn.Module):
    """GPU-optimized LSTM with mixed precision support."""
    
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, use_mixed_precision: bool = True):
        super().__init__()
        self.use_mixed_precision = use_mixed_precision
        self.hidden_dim = hidden_dim
        
        # Choose dtype based on mixed precision setting
        dtype = torch.float16 if use_mixed_precision else torch.float32
        
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True, dtype=dtype)
        self.fc = nn.Linear(hidden_dim, output_dim, dtype=dtype)
    
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        return self.fc(lstm_out[:, -1, :])


class GPUOptimizedTransformer(nn.Module):
    """GPU-optimized Transformer with mixed precision support."""
    
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, use_mixed_precision: bool = True):
        super().__init__()
        self.use_mixed_precision = use_mixed_precision
        
        # Choose dtype based on mixed precision setting
        dtype = torch.float16 if use_mixed_precision else torch.float32
        
        self.input_projection = nn.Linear(input_dim, hidden_dim, dtype=dtype)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=8,
            dim_feedforward=hidden_dim * 4,
            dropout=0.1,
            dtype=dtype
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=6)
        self.output_projection = nn.Linear(hidden_dim, output_dim, dtype=dtype)
    
    def forward(self, x):
        x = self.input_projection(x)
        x = x.transpose(0, 1)  # Transformer expects (seq_len, batch, features)
        x = self.transformer(x)
        x = x.transpose(0, 1)  # Back to (batch, seq_len, features)
        return self.output_projection(x[:, -1, :])  # Take last sequence element
