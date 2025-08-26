"""
LightGBM Tabular Model with GPU Optimization and Memory Mapping.

This module implements a LightGBM-based tabular model with:
- GPU acceleration
- Memory mapping for large datasets
- Mixed precision support
- Automatic memory management
- Batch processing
"""

import logging
from typing import Dict, Any, Optional, Union
import warnings

import numpy as np
import pandas as pd

# GPU optimization imports
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    warnings.warn("lightgbm not available - GPU optimization disabled")

from quanttime.models.base import ModelBase
from quanttime.ml.gpu_optimized_training import GPUOptimizedLightGBMTrainer

logger = logging.getLogger(__name__)


class LightGBMTabularModel(ModelBase):
    """
    LightGBM-based tabular model with GPU optimization and memory mapping.
    
    Features:
    - GPU acceleration for training
    - Memory mapping for large datasets
    - Mixed precision support
    - Automatic memory management
    - Batch processing
    - Feature importance analysis
    """
    
    def __init__(self, 
                 max_gpu_memory_gb: float = 7.0,
                 max_ram_gb: float = 14.0,
                 use_mixed_precision: bool = True,
                 batch_size: int = 10000,
                 device: str = "cuda",
                 **model_params):
        """
        Initialize LightGBM tabular model.
        
        Args:
            max_gpu_memory_gb: Maximum GPU memory usage in GB
            max_ram_gb: Maximum RAM usage in GB
            use_mixed_precision: Use mixed precision
            batch_size: Batch size for data processing
            device: Device to use (cuda, cpu)
            **model_params: LightGBM model parameters
        """
        super().__init__()
        
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("lightgbm not installed. Please install with: pip install lightgbm")
        
        self.max_gpu_memory_gb = max_gpu_memory_gb
        self.max_ram_gb = max_ram_gb
        self.use_mixed_precision = use_mixed_precision
        self.batch_size = batch_size
        self.device = device
        self.model_params = model_params
        
        # GPU-optimized trainer
        self.trainer = GPUOptimizedLightGBMTrainer(
            max_gpu_memory_gb=max_gpu_memory_gb,
            max_ram_gb=max_ram_gb,
            use_mixed_precision=use_mixed_precision,
            batch_size=batch_size,
            device=device
        )
        
        # Model state
        self.model = None
        self.feature_names = None
        self.is_trained = False
        
        logger.info(f"LightGBM tabular model initialized:")
        logger.info(f"  Max GPU memory: {max_gpu_memory_gb} GB")
        logger.info(f"  Max RAM: {max_ram_gb} GB")
        logger.info(f"  Mixed precision: {use_mixed_precision}")
        logger.info(f"  Batch size: {batch_size}")
        logger.info(f"  Device: {device}")
    
    def fit(self, 
            X: Union[np.ndarray, pd.DataFrame],
            y: Union[np.ndarray, pd.Series],
            **fit_params) -> 'LightGBMTabularModel':
        """
        Fit the LightGBM model with GPU optimization.
        
        Args:
            X: Feature matrix
            y: Target values
            **fit_params: Additional fitting parameters
            
        Returns:
            Self for chaining
        """
        logger.info("Starting LightGBM training with GPU optimization")
        
        # Store feature names
        if isinstance(X, pd.DataFrame):
            self.feature_names = list(X.columns)
        else:
            self.feature_names = [f"feature_{i}" for i in range(X.shape[1])]
        
        # Set default LightGBM parameters for GPU optimization
        default_params = {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'num_threads': 4,
            'seed': 42
        }
        
        # Merge with user parameters
        lgb_params = {**default_params, **self.model_params, **fit_params}
        
        # Train model with GPU optimization
        self.model = self.trainer.train(X, y, **lgb_params)
        
        self.is_trained = True
        logger.info("LightGBM training completed")
        
        return self
    
    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Make predictions with GPU optimization.
        
        Args:
            X: Feature matrix
            
        Returns:
            Predictions
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model must be trained before making predictions")
        
        # Convert to numpy if needed
        if isinstance(X, pd.DataFrame):
            X = X.to_numpy()
        
        # Optimize dtypes for memory usage
        if self.use_mixed_precision and X.dtype == np.float64:
            X = X.astype(np.float32)
        
        # Make predictions
        predictions = self.model.predict(X)
        
        return predictions
    
    def get_feature_importance(self, importance_type: str = 'gain') -> Dict[str, float]:
        """
        Get feature importance scores.
        
        Args:
            importance_type: Type of importance ('gain', 'split', 'cover')
            
        Returns:
            Dictionary mapping feature names to importance scores
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model must be trained before getting feature importance")
        
        if self.feature_names is None:
            raise ValueError("Feature names not available")
        
        importance_scores = self.model.feature_importance(importance_type=importance_type)
        
        return dict(zip(self.feature_names, importance_scores))
    
    def get_feature_importance_df(self, importance_type: str = 'gain') -> pd.DataFrame:
        """
        Get feature importance as a DataFrame.
        
        Args:
            importance_type: Type of importance ('gain', 'split', 'cover')
            
        Returns:
            DataFrame with feature names and importance scores
        """
        importance_dict = self.get_feature_importance(importance_type)
        
        df = pd.DataFrame([
            {'feature': name, 'importance': score}
            for name, score in importance_dict.items()
        ])
        
        return df.sort_values('importance', ascending=False)
    
    def save_model(self, filepath: str):
        """Save the trained model."""
        if not self.is_trained or self.model is None:
            raise ValueError("Model must be trained before saving")
        
        self.model.save_model(filepath)
        logger.info(f"Model saved to: {filepath}")
    
    def load_model(self, filepath: str):
        """Load a trained model."""
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("lightgbm not installed")
        
        self.model = lgb.Booster(model_file=filepath)
        self.is_trained = True
        logger.info(f"Model loaded from: {filepath}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        if not self.is_trained or self.model is None:
            return {"status": "not_trained"}
        
        info = {
            "status": "trained",
            "model_type": "lightgbm",
            "feature_count": len(self.feature_names) if self.feature_names else 0,
            "feature_names": self.feature_names,
            "max_gpu_memory_gb": self.max_gpu_memory_gb,
            "max_ram_gb": self.max_ram_gb,
            "use_mixed_precision": self.use_mixed_precision,
            "batch_size": self.batch_size,
            "device": self.device
        }
        
        return info


# Alias for backward compatibility
LGBMModel = LightGBMTabularModel


