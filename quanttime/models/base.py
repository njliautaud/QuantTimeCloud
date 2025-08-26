"""
Base Model Interface for QuantTime ML Trading Suite.

This module defines the base classes and interfaces for all trading models.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for model training and prediction."""
    model_type: str  # 'lightgbm', 'lstm', 'transformer'
    prediction_horizons: List[int]  # Minutes ahead [1, 2, 3, 5]
    orderbook_depth: int = 20
    sequence_length: int = 200
    feature_window: int = 100
    use_gpu: bool = True
    use_mixed_precision: bool = True
    max_gpu_memory_gb: float = 7.0
    max_ram_gb: float = 14.0
    batch_size: int = 15000
    min_trade_duration_seconds: int = 10  # Minimum trade duration
    risk_management: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.risk_management is None:
            self.risk_management = {
                'max_position_size': 0.1,  # 10% of portfolio
                'stop_loss_pct': 0.02,     # 2% stop loss
                'take_profit_pct': 0.04,   # 4% take profit
                'max_drawdown': 0.05       # 5% max drawdown
            }


@dataclass
class TrainingMetrics:
    """Comprehensive training metrics for financial models."""
    # Basic metrics
    train_rmse: float
    val_rmse: float
    test_rmse: float
    train_mae: float
    val_mae: float
    test_mae: float
    train_r2: float
    val_r2: float
    test_r2: float
    
    # Financial metrics
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    total_return: float
    volatility: float
    
    # Risk metrics
    var_95: float  # Value at Risk 95%
    cvar_95: float  # Conditional Value at Risk 95%
    calmar_ratio: float
    sortino_ratio: float
    
    # Trading metrics
    total_trades: int
    profitable_trades: int
    avg_trade_duration: float
    avg_trade_return: float


class ModelBase(ABC):
    """
    Abstract base class for all trading models.
    
    All models must implement:
    - train(): Train the model
    - predict(): Make predictions
    - evaluate(): Evaluate model performance
    - save_model(): Save model to disk
    - load_model(): Load model from disk
    """
    
    def __init__(self, config: ModelConfig):
        """
        Initialize model with configuration.
        
        Args:
            config: Model configuration
        """
        self.config = config
        self.is_trained = False
        self.training_history = {}
        self.feature_importance = {}
        self.model_metadata = {
            'created_at': datetime.now().isoformat(),
            'model_type': config.model_type,
            'config': config
        }
        
        logger.info(f"Initialized {config.model_type} model")
    
    @abstractmethod
    def train(self, 
              mbo_df: pd.DataFrame,
              validation_split: float = 0.2,
              test_split: float = 0.1,
              random_state: int = 42) -> Dict[str, Any]:
        """
        Train the model on MBO data.
        
        Args:
            mbo_df: MBO dataframe
            validation_split: Validation split ratio
            test_split: Test split ratio
            random_state: Random seed
            
        Returns:
            Training results dictionary
        """
        pass
    
    @abstractmethod
    def predict(self, 
                mbo_df: pd.DataFrame,
                horizon: int = 1) -> np.ndarray:
        """
        Make predictions for given horizon.
        
        Args:
            mbo_df: MBO dataframe
            horizon: Prediction horizon in minutes
            
        Returns:
            Predictions array
        """
        pass
    
    @abstractmethod
    def evaluate(self, 
                 mbo_df: pd.DataFrame,
                 horizon: int = 1) -> TrainingMetrics:
        """
        Evaluate model performance.
        
        Args:
            mbo_df: MBO dataframe
            horizon: Prediction horizon in minutes
            
        Returns:
            Training metrics
        """
        pass
    
    @abstractmethod
    def save_model(self, filepath: str):
        """Save model to disk."""
        pass
    
    @abstractmethod
    def load_model(self, filepath: str):
        """Load model from disk."""
        pass
    
    def get_model_summary(self) -> Dict[str, Any]:
        """Get comprehensive model summary."""
        return {
            'model_type': self.config.model_type,
            'is_trained': self.is_trained,
            'prediction_horizons': self.config.prediction_horizons,
            'training_history': self.training_history,
            'feature_importance': self.feature_importance,
            'model_metadata': self.model_metadata
        }
    
    def _calculate_financial_metrics(self, 
                                   predictions: np.ndarray,
                                   actuals: np.ndarray,
                                   prices: np.ndarray) -> Dict[str, float]:
        """
        Calculate comprehensive financial metrics.
        
        Args:
            predictions: Model predictions
            actuals: Actual values
            prices: Price series
            
        Returns:
            Dictionary of financial metrics
        """
        # Calculate returns
        predicted_returns = predictions
        actual_returns = actuals
        
        # Basic metrics
        rmse = np.sqrt(np.mean((predictions - actuals) ** 2))
        mae = np.mean(np.abs(predictions - actuals))
        r2 = 1 - np.sum((actuals - predictions) ** 2) / np.sum((actuals - np.mean(actuals)) ** 2)
        
        # Trading simulation
        position = np.zeros(len(predictions))
        returns = np.zeros(len(predictions))
        
        # Simple trading strategy: long when prediction > threshold
        threshold = np.std(predictions) * 0.5
        position[predictions > threshold] = 1
        position[predictions < -threshold] = -1
        
        # Calculate returns
        for i in range(1, len(predictions)):
            if position[i-1] != 0:
                returns[i] = position[i-1] * actual_returns[i]
        
        # Financial metrics
        total_return = np.sum(returns)
        volatility = np.std(returns)
        sharpe_ratio = total_return / volatility if volatility > 0 else 0
        
        # Drawdown calculation
        cumulative_returns = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = cumulative_returns - running_max
        max_drawdown = np.min(drawdown)
        
        # Win rate
        profitable_trades = np.sum(returns > 0)
        total_trades = np.sum(returns != 0)
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0
        
        # Profit factor
        gross_profit = np.sum(returns[returns > 0])
        gross_loss = abs(np.sum(returns[returns < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Average win/loss
        avg_win = np.mean(returns[returns > 0]) if np.sum(returns > 0) > 0 else 0
        avg_loss = np.mean(returns[returns < 0]) if np.sum(returns < 0) > 0 else 0
        
        # Risk metrics
        var_95 = np.percentile(returns, 5)  # 95% VaR
        cvar_95 = np.mean(returns[returns <= var_95])  # 95% CVaR
        
        # Ratios
        calmar_ratio = total_return / abs(max_drawdown) if max_drawdown != 0 else 0
        sortino_ratio = total_return / np.std(returns[returns < 0]) if np.sum(returns < 0) > 0 else 0
        
        return {
            'rmse': rmse,
            'mae': mae,
            'r2': r2,
            'total_return': total_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'var_95': var_95,
            'cvar_95': cvar_95,
            'calmar_ratio': calmar_ratio,
            'sortino_ratio': sortino_ratio,
            'total_trades': total_trades,
            'profitable_trades': profitable_trades
        }


