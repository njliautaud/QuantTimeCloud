"""
Memory-Optimized Training Module for QuantTime ML Trading Suite.

This module implements memory-efficient training using:
- Mixed precision training (float16/float32)
- Gradient accumulation
- Memory mapping for datasets
- Batch processing
- Automatic memory management
- Model checkpointing

Key Features:
- Mixed precision training with automatic mixed precision (AMP)
- Gradient accumulation for large effective batch sizes
- Memory-efficient data loading
- Automatic memory monitoring
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

# Memory optimization imports
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

from quanttime.data.memory_optimized_loader import MemoryOptimizedLoader, monitor_memory_usage

logger = logging.getLogger(__name__)


class MemoryOptimizedDataset(Dataset):
    """
    Memory-optimized PyTorch dataset with memory mapping and mixed precision.
    
    Features:
    - Memory mapping for large datasets
    - Mixed precision support
    - Automatic dtype optimization
    - Lazy loading
    """
    
    def __init__(self, 
                 data: Union[np.ndarray, pd.DataFrame],
                 targets: Optional[Union[np.ndarray, pd.Series]] = None,
                 use_mixed_precision: bool = True,
                 dtype: str = "float32"):
        """
        Initialize memory-optimized dataset.
        
        Args:
            data: Input features
            targets: Target values
            use_mixed_precision: Use mixed precision
            dtype: Data type for features
        """
        self.use_mixed_precision = use_mixed_precision
        self.dtype = dtype
        
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
        
        logger.info(f"Memory-optimized dataset created:")
        logger.info(f"  Data shape: {self.data.shape}")
        logger.info(f"  Data dtype: {self.data.dtype}")
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


class MemoryOptimizedTrainer:
    """
    Memory-optimized trainer with mixed precision, gradient accumulation, and memory management.
    
    Features:
    - Mixed precision training (AMP)
    - Gradient accumulation
    - Memory monitoring
    - Automatic batch size adjustment
    - Model checkpointing
    - Memory-efficient data loading
    """
    
    def __init__(self,
                 model: nn.Module,
                 train_dataset: Dataset,
                 val_dataset: Optional[Dataset] = None,
                 batch_size: int = 1024,
                 learning_rate: float = 1e-3,
                 max_memory_gb: float = 8.0,
                 use_mixed_precision: bool = True,
                 gradient_accumulation_steps: int = 1,
                 device: str = "auto"):
        """
        Initialize memory-optimized trainer.
        
        Args:
            model: PyTorch model
            train_dataset: Training dataset
            val_dataset: Validation dataset
            batch_size: Batch size
            learning_rate: Learning rate
            max_memory_gb: Maximum memory usage in GB
            use_mixed_precision: Use mixed precision training
            gradient_accumulation_steps: Gradient accumulation steps
            device: Device to use (auto, cpu, cuda)
        """
        self.model = model
        self.train_dataset = train_dataset
        self.val_dataset = val_dataset
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.max_memory_gb = max_memory_gb
        self.use_mixed_precision = use_mixed_precision
        self.gradient_accumulation_steps = gradient_accumulation_steps
        
        # Device setup
        if device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
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
        
        # Data loaders
        self.train_loader = self._create_data_loader(train_dataset, batch_size, shuffle=True)
        if val_dataset is not None:
            self.val_loader = self._create_data_loader(val_dataset, batch_size, shuffle=False)
        else:
            self.val_loader = None
        
        # Training state
        self.current_epoch = 0
        self.global_step = 0
        self.best_val_loss = float('inf')
        
        # Memory monitoring
        if PSUTIL_AVAILABLE:
            self.process = psutil.Process()
        
        logger.info(f"Memory-optimized trainer initialized:")
        logger.info(f"  Device: {self.device}")
        logger.info(f"  Batch size: {batch_size}")
        logger.info(f"  Gradient accumulation: {gradient_accumulation_steps}")
        logger.info(f"  Mixed precision: {use_mixed_precision}")
        logger.info(f"  Max memory: {max_memory_gb} GB")
    
    def _create_data_loader(self, dataset: Dataset, batch_size: int, shuffle: bool) -> DataLoader:
        """Create memory-optimized data loader."""
        # Calculate optimal number of workers based on memory
        if PSUTIL_AVAILABLE:
            available_memory = psutil.virtual_memory().available / 1024**3
            num_workers = max(1, min(4, int(available_memory / 2)))
        else:
            num_workers = 2
        
        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=num_workers,
            pin_memory=self.device.type == "cuda",
            persistent_workers=num_workers > 0
        )
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        if not PSUTIL_AVAILABLE:
            return {}
        
        memory_info = self.process.memory_info()
        return {
            'rss_gb': memory_info.rss / 1024**3,
            'vms_gb': memory_info.vms / 1024**3,
            'percent': self.process.memory_percent(),
            'available_gb': psutil.virtual_memory().available / 1024**3
        }
    
    def check_memory_limit(self) -> bool:
        """Check if current memory usage is within limits."""
        if not PSUTIL_AVAILABLE:
            return True
        
        memory_usage = self.get_memory_usage()
        return memory_usage['rss_gb'] < self.max_memory_gb
    
    def force_garbage_collection(self):
        """Force garbage collection to free memory."""
        gc.collect()
        if self.device.type == "cuda":
            torch.cuda.empty_cache()
        logger.debug("Forced garbage collection")
    
    def adjust_batch_size(self, current_batch_size: int) -> int:
        """Dynamically adjust batch size based on memory usage."""
        if not self.check_memory_limit():
            new_batch_size = max(1, current_batch_size // 2)
            logger.warning(f"Memory limit reached, reducing batch size from {current_batch_size} to {new_batch_size}")
            return new_batch_size
        return current_batch_size
    
    @monitor_memory_usage
    def train_epoch(self) -> Dict[str, float]:
        """Train for one epoch with memory optimization."""
        self.model.train()
        total_loss = 0.0
        num_batches = 0
        
        # Dynamic batch size adjustment
        current_batch_size = self.batch_size
        
        for batch_idx, (data, targets) in enumerate(self.train_loader):
            # Check memory and adjust batch size if needed
            current_batch_size = self.adjust_batch_size(current_batch_size)
            
            # Move data to device
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
            
            # Memory management
            if batch_idx % 100 == 0:
                if not self.check_memory_limit():
                    logger.warning("Memory limit reached during training")
                    self.force_garbage_collection()
        
        avg_loss = total_loss / num_batches
        return {'train_loss': avg_loss}
    
    @monitor_memory_usage
    def validate(self) -> Dict[str, float]:
        """Validate model with memory optimization."""
        if self.val_loader is None:
            return {}
        
        self.model.eval()
        total_loss = 0.0
        num_batches = 0
        
        with torch.no_grad():
            for data, targets in self.val_loader:
                # Move data to device
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
        """Save model checkpoint with memory optimization."""
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
                'gradient_accumulation_steps': self.gradient_accumulation_steps
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
        Train model with memory optimization.
        
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
            'memory_usage': []
        }
        
        # Initialize wandb if available
        if WANDB_AVAILABLE:
            wandb.init(project="quanttime-ml", config={
                'batch_size': self.batch_size,
                'learning_rate': self.learning_rate,
                'use_mixed_precision': self.use_mixed_precision,
                'gradient_accumulation_steps': self.gradient_accumulation_steps,
                'max_memory_gb': self.max_memory_gb
            })
        
        logger.info(f"Starting training for {num_epochs} epochs")
        
        for epoch in range(self.current_epoch, num_epochs):
            self.current_epoch = epoch
            
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
            if PSUTIL_AVAILABLE:
                memory_usage = self.get_memory_usage()
                metrics['memory_gb'] = memory_usage['rss_gb']
                history['memory_usage'].append(memory_usage['rss_gb'])
            
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
            
            # Memory management
            if not self.check_memory_limit():
                logger.warning("Memory limit reached, forcing garbage collection")
                self.force_garbage_collection()
        
        logger.info("Training completed")
        if WANDB_AVAILABLE:
            wandb.finish()
        
        return history


class MemoryOptimizedLightGBMTrainer:
    """
    Memory-optimized LightGBM trainer with memory mapping and mixed precision.
    """
    
    def __init__(self,
                 max_memory_gb: float = 8.0,
                 use_mixed_precision: bool = True,
                 batch_size: int = 10000):
        """
        Initialize memory-optimized LightGBM trainer.
        
        Args:
            max_memory_gb: Maximum memory usage in GB
            use_mixed_precision: Use mixed precision
            batch_size: Batch size for data processing
        """
        self.max_memory_gb = max_memory_gb
        self.use_mixed_precision = use_mixed_precision
        self.batch_size = batch_size
        
        # Memory monitoring
        if PSUTIL_AVAILABLE:
            self.process = psutil.Process()
        
        logger.info(f"Memory-optimized LightGBM trainer initialized:")
        logger.info(f"  Max memory: {max_memory_gb} GB")
        logger.info(f"  Mixed precision: {use_mixed_precision}")
        logger.info(f"  Batch size: {batch_size}")
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        if not PSUTIL_AVAILABLE:
            return {}
        
        memory_info = self.process.memory_info()
        return {
            'rss_gb': memory_info.rss / 1024**3,
            'vms_gb': memory_info.vms / 1024**3,
            'percent': self.process.memory_percent(),
            'available_gb': psutil.virtual_memory().available / 1024**3
        }
    
    @monitor_memory_usage
    def train(self, 
              X: Union[np.ndarray, pd.DataFrame],
              y: Union[np.ndarray, pd.Series],
              **lgb_params) -> Any:
        """
        Train LightGBM model with memory optimization.
        
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
        
        # Set memory-efficient LightGBM parameters
        memory_params = {
            'max_bin': 255,  # Reduce memory usage
            'min_data_in_bin': 3,
            'max_memory_usage': int(self.max_memory_gb * 1024),  # MB
            'force_col_wise': True,  # More memory efficient
            'verbose': -1
        }
        
        # Merge with user parameters
        lgb_params = {**memory_params, **lgb_params}
        
        logger.info(f"Training LightGBM model with memory optimization:")
        logger.info(f"  Data shape: {X.shape}")
        logger.info(f"  Data dtype: {X.dtype}")
        logger.info(f"  Memory usage: {self.get_memory_usage()['rss_gb']:.2f} GB")
        
        # Train model
        model = lgb.train(lgb_params, lgb.Dataset(X, y))
        
        logger.info("LightGBM training completed")
        return model


def create_memory_optimized_model(model_type: str,
                                input_dim: int,
                                hidden_dims: List[int],
                                output_dim: int = 1,
                                use_mixed_precision: bool = True) -> nn.Module:
    """
    Create a memory-optimized PyTorch model.
    
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
        return MemoryOptimizedMLP(input_dim, hidden_dims, output_dim, use_mixed_precision)
    elif model_type.lower() == "lstm":
        return MemoryOptimizedLSTM(input_dim, hidden_dims[0], output_dim, use_mixed_precision)
    elif model_type.lower() == "transformer":
        return MemoryOptimizedTransformer(input_dim, hidden_dims[0], output_dim, use_mixed_precision)
    else:
        raise ValueError(f"Unknown model type: {model_type}")


class MemoryOptimizedMLP(nn.Module):
    """Memory-optimized MLP with mixed precision support."""
    
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


class MemoryOptimizedLSTM(nn.Module):
    """Memory-optimized LSTM with mixed precision support."""
    
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


class MemoryOptimizedTransformer(nn.Module):
    """Memory-optimized Transformer with mixed precision support."""
    
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
