"""
Memory Configuration for QuantTime ML Trading Suite.

This module provides optimal memory settings for different hardware configurations,
ensuring efficient use of GPU memory and system RAM.
"""

import os
import logging
from typing import Dict, Any, Optional
import psutil

logger = logging.getLogger(__name__)


class MemoryConfig:
    """
    Memory configuration manager for optimal resource utilization.
    
    Provides optimal settings for:
    - GPU memory usage
    - System RAM usage
    - Batch sizes
    - Mixed precision settings
    - Data loading strategies
    """
    
    def __init__(self, 
                 gpu_memory_gb: Optional[float] = None,
                 system_ram_gb: Optional[float] = None,
                 auto_detect: bool = True):
        """
        Initialize memory configuration.
        
        Args:
            gpu_memory_gb: GPU memory in GB (auto-detected if None)
            system_ram_gb: System RAM in GB (auto-detected if None)
            auto_detect: Auto-detect hardware specifications
        """
        self.auto_detect = auto_detect
        
        # Auto-detect hardware if requested
        if auto_detect:
            self.gpu_memory_gb = self._detect_gpu_memory() if gpu_memory_gb is None else gpu_memory_gb
            self.system_ram_gb = self._detect_system_ram() if system_ram_gb is None else system_ram_gb
        else:
            self.gpu_memory_gb = gpu_memory_gb or 8.0
            self.system_ram_gb = system_ram_gb or 16.0
        
        # Calculate optimal settings
        self.optimal_settings = self._calculate_optimal_settings()
        
        logger.info(f"Memory configuration initialized:")
        logger.info(f"  GPU Memory: {self.gpu_memory_gb} GB")
        logger.info(f"  System RAM: {self.system_ram_gb} GB")
        logger.info(f"  Optimal settings: {self.optimal_settings}")
    
    def _detect_gpu_memory(self) -> float:
        """Auto-detect GPU memory."""
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_memory_gb = memory_info.total / (1024**3)
                logger.info(f"Auto-detected GPU memory: {gpu_memory_gb:.1f} GB")
                return gpu_memory_gb
        except Exception as e:
            logger.warning(f"Failed to auto-detect GPU memory: {e}")
        
        # Fallback to environment variable or default
        gpu_memory_gb = float(os.getenv('GPU_MEMORY_GB', '8.0'))
        logger.info(f"Using GPU memory from environment/default: {gpu_memory_gb} GB")
        return gpu_memory_gb
    
    def _detect_system_ram(self) -> float:
        """Auto-detect system RAM."""
        try:
            system_ram_gb = psutil.virtual_memory().total / (1024**3)
            logger.info(f"Auto-detected system RAM: {system_ram_gb:.1f} GB")
            return system_ram_gb
        except Exception as e:
            logger.warning(f"Failed to auto-detect system RAM: {e}")
        
        # Fallback to environment variable or default
        system_ram_gb = float(os.getenv('SYSTEM_RAM_GB', '16.0'))
        logger.info(f"Using system RAM from environment/default: {system_ram_gb} GB")
        return system_ram_gb
    
    def _calculate_optimal_settings(self) -> Dict[str, Any]:
        """Calculate optimal memory settings based on hardware."""
        # GPU memory settings (leave 1GB buffer)
        max_gpu_memory_gb = max(1.0, self.gpu_memory_gb - 1.0)
        
        # System RAM settings (leave 2GB buffer for OS and other processes)
        max_ram_gb = max(4.0, self.system_ram_gb - 2.0)
        
        # Batch size calculation based on available memory
        if self.gpu_memory_gb >= 8.0:
            # High-end GPU (8GB+)
            default_batch_size = 2048
            gradient_accumulation_steps = 2
            use_mixed_precision = True
            dtype_float = "float16"
        elif self.gpu_memory_gb >= 4.0:
            # Mid-range GPU (4-8GB)
            default_batch_size = 1024
            gradient_accumulation_steps = 4
            use_mixed_precision = True
            dtype_float = "float32"
        else:
            # Low-end GPU or CPU-only
            default_batch_size = 512
            gradient_accumulation_steps = 8
            use_mixed_precision = False
            dtype_float = "float32"
        
        # Data loading settings
        if self.system_ram_gb >= 32.0:
            # High RAM system
            data_loader_workers = 4
            use_memory_mapping = False
            chunk_size = 50000
        elif self.system_ram_gb >= 16.0:
            # Mid-range RAM system
            data_loader_workers = 2
            use_memory_mapping = True
            chunk_size = 25000
        else:
            # Low RAM system
            data_loader_workers = 1
            use_memory_mapping = True
            chunk_size = 10000
        
        settings = {
            # GPU settings
            'max_gpu_memory_gb': max_gpu_memory_gb,
            'use_mixed_precision': use_mixed_precision,
            'dtype_float': dtype_float,
            'default_batch_size': default_batch_size,
            'gradient_accumulation_steps': gradient_accumulation_steps,
            
            # RAM settings
            'max_ram_gb': max_ram_gb,
            'data_loader_workers': data_loader_workers,
            'use_memory_mapping': use_memory_mapping,
            'chunk_size': chunk_size,
            
            # Hardware info
            'gpu_memory_gb': self.gpu_memory_gb,
            'system_ram_gb': self.system_ram_gb,
            
            # Optimization flags
            'use_gpu_optimization': self.gpu_memory_gb > 2.0,
            'use_memory_optimization': True,
            'use_batch_processing': True,
        }
        
        return settings
    
    def get_training_config(self, model_type: str = "auto") -> Dict[str, Any]:
        """
        Get training configuration for specific model type.
        
        Args:
            model_type: Model type (auto, lightgbm, pytorch, transformer)
            
        Returns:
            Training configuration dictionary
        """
        base_config = self.optimal_settings.copy()
        
        if model_type == "lightgbm":
            # LightGBM specific settings
            config = {
                **base_config,
                'device': 'gpu' if base_config['use_gpu_optimization'] else 'cpu',
                'max_bin': 255,
                'min_data_in_bin': 3,
                'force_col_wise': True,
                'verbose': -1,
                'num_threads': min(4, os.cpu_count() or 1)
            }
        elif model_type in ["pytorch", "transformer", "lstm"]:
            # PyTorch specific settings
            config = {
                **base_config,
                'device': 'cuda' if base_config['use_gpu_optimization'] else 'cpu',
                'learning_rate': 1e-3,
                'weight_decay': 1e-4,
                'scheduler_patience': 5,
                'early_stopping_patience': 10,
                'checkpoint_frequency': 5
            }
        else:
            # Auto-detect based on available libraries
            try:
                import torch
                if torch.cuda.is_available() and base_config['use_gpu_optimization']:
                    config = self.get_training_config("pytorch")
                else:
                    config = self.get_training_config("lightgbm")
            except ImportError:
                config = self.get_training_config("lightgbm")
        
        return config
    
    def get_data_loading_config(self) -> Dict[str, Any]:
        """Get data loading configuration."""
        return {
            'max_memory_gb': self.optimal_settings['max_ram_gb'],
            'batch_size': self.optimal_settings['chunk_size'],
            'use_mixed_precision': self.optimal_settings['use_mixed_precision'],
            'dtype_float': self.optimal_settings['dtype_float'],
            'use_memory_mapping': self.optimal_settings['use_memory_mapping'],
            'num_workers': self.optimal_settings['data_loader_workers']
        }
    
    def get_memory_monitoring_config(self) -> Dict[str, Any]:
        """Get memory monitoring configuration."""
        return {
            'monitor_gpu': self.optimal_settings['use_gpu_optimization'],
            'monitor_ram': True,
            'warning_threshold': 0.8,  # 80% usage warning
            'critical_threshold': 0.95,  # 95% usage critical
            'check_interval': 10  # Check every 10 seconds
        }
    
    def validate_environment(self) -> Dict[str, bool]:
        """Validate that the environment supports the configured settings."""
        validation = {
            'gpu_available': False,
            'cuda_available': False,
            'lightgbm_available': False,
            'torch_available': False,
            'psutil_available': True,
            'pynvml_available': False
        }
        
        # Check GPU/CUDA
        try:
            import pynvml
            pynvml.nvmlInit()
            validation['pynvml_available'] = True
            validation['gpu_available'] = pynvml.nvmlDeviceGetCount() > 0
        except ImportError:
            pass
        
        try:
            import torch
            validation['torch_available'] = True
            validation['cuda_available'] = torch.cuda.is_available()
        except ImportError:
            pass
        
        try:
            import lightgbm
            validation['lightgbm_available'] = True
        except ImportError:
            pass
        
        return validation
    
    def get_recommendations(self) -> Dict[str, str]:
        """Get recommendations for optimal performance."""
        recommendations = {}
        
        validation = self.validate_environment()
        
        if not validation['gpu_available']:
            recommendations['gpu'] = "No GPU detected. Consider using CPU-optimized settings."
        
        if not validation['cuda_available'] and self.optimal_settings['use_gpu_optimization']:
            recommendations['cuda'] = "CUDA not available. Install PyTorch with CUDA support for GPU acceleration."
        
        if not validation['lightgbm_available']:
            recommendations['lightgbm'] = "LightGBM not installed. Install with: pip install lightgbm"
        
        if not validation['torch_available']:
            recommendations['torch'] = "PyTorch not installed. Install with: pip install torch"
        
        if self.system_ram_gb < 8.0:
            recommendations['ram'] = f"Low system RAM ({self.system_ram_gb:.1f} GB). Consider using memory mapping and smaller batch sizes."
        
        if self.gpu_memory_gb < 4.0:
            recommendations['gpu_memory'] = f"Low GPU memory ({self.gpu_memory_gb:.1f} GB). Consider using gradient accumulation and mixed precision."
        
        return recommendations


# Global memory configuration instance
_memory_config = None


def get_memory_config() -> MemoryConfig:
    """Get global memory configuration instance."""
    global _memory_config
    if _memory_config is None:
        _memory_config = MemoryConfig()
    return _memory_config


def get_optimal_training_config(model_type: str = "auto") -> Dict[str, Any]:
    """Get optimal training configuration for the current hardware."""
    config = get_memory_config()
    return config.get_training_config(model_type)


def get_optimal_data_loading_config() -> Dict[str, Any]:
    """Get optimal data loading configuration for the current hardware."""
    config = get_memory_config()
    return config.get_data_loading_config()


def get_memory_recommendations() -> Dict[str, str]:
    """Get memory optimization recommendations."""
    config = get_memory_config()
    return config.get_recommendations()
