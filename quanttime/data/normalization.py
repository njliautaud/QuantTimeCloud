"""
Normalization System for QuantTime MBO L3 Pipeline.

This module implements various normalization strategies for MBO data,
ensuring stable training for AI/ML models while preserving the ability
to reconstruct raw prices for backtesting.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
import logging
from collections import deque
import warnings

from .schema import NormalizationType

logger = logging.getLogger(__name__)


@dataclass
class NormalizationState:
    """State for maintaining normalization parameters."""
    midprice: float = 0.0
    tick_size: float = 0.25  # Default tick size for ES futures
    rolling_mean_size: float = 0.0
    rolling_std_size: float = 1.0
    rolling_mean_time_delta: float = 0.0
    rolling_std_time_delta: float = 1.0
    session_open_midprice: float = 0.0
    session_open_time: int = 0
    
    # Multi-scale EMAs for normalization
    ema_fast: float = 0.0
    ema_medium: float = 0.0
    ema_slow: float = 0.0
    
    # Rolling statistics
    size_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    time_delta_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    price_history: deque = field(default_factory=lambda: deque(maxlen=1000))


class NormalizationEngine:
    """
    Normalization engine for MBO L3 data.
    
    Implements various normalization strategies while maintaining
    the ability to reconstruct raw values for backtesting.
    """
    
    def __init__(self, 
                 normalization_type: NormalizationType = NormalizationType.TICK_RELATIVE,
                 tick_size: float = 0.25,
                 ema_fast_alpha: float = 0.1,
                 ema_medium_alpha: float = 0.01,
                 ema_slow_alpha: float = 0.001):
        """
        Initialize normalization engine.
        
        Args:
            normalization_type: Type of normalization to apply
            tick_size: Tick size for price normalization
            ema_fast_alpha: Fast EMA alpha (100ms equivalent)
            ema_medium_alpha: Medium EMA alpha (1s equivalent)
            ema_slow_alpha: Slow EMA alpha (10s equivalent)
        """
        self.normalization_type = normalization_type
        self.tick_size = tick_size
        self.ema_fast_alpha = ema_fast_alpha
        self.ema_medium_alpha = ema_medium_alpha
        self.ema_slow_alpha = ema_slow_alpha
        
        # Initialize state
        self.state = NormalizationState(tick_size=tick_size)
        
        logger.info(f"Initialized normalization engine: {normalization_type.value}")
    
    def reset_session(self, session_open_time: int, initial_midprice: float):
        """
        Reset normalization state for new trading session.
        
        Args:
            session_open_time: Session open timestamp
            initial_midprice: Initial midprice for the session
        """
        self.state.session_open_time = session_open_time
        self.state.session_open_midprice = initial_midprice
        self.state.midprice = initial_midprice
        
        # Reset rolling statistics
        self.state.size_history.clear()
        self.state.time_delta_history.clear()
        self.state.price_history.clear()
        
        logger.info(f"Reset normalization state for session: midprice={initial_midprice}")
    
    def update_midprice(self, midprice: float, timestamp: int):
        """
        Update midprice and related normalization parameters.
        
        Args:
            midprice: Current midprice
            timestamp: Current timestamp
        """
        self.state.midprice = midprice
        self.state.price_history.append(midprice)
        
        # Update EMAs
        if self.state.ema_fast == 0.0:
            self.state.ema_fast = midprice
            self.state.ema_medium = midprice
            self.state.ema_slow = midprice
        else:
            self.state.ema_fast = (self.ema_fast_alpha * midprice + 
                                 (1 - self.ema_fast_alpha) * self.state.ema_fast)
            self.state.ema_medium = (self.ema_medium_alpha * midprice + 
                                   (1 - self.ema_medium_alpha) * self.state.ema_medium)
            self.state.ema_slow = (self.ema_slow_alpha * midprice + 
                                 (1 - self.ema_slow_alpha) * self.state.ema_slow)
    
    def normalize_price(self, price: float) -> float:
        """
        Normalize price based on current normalization type.
        
        Args:
            price: Raw price
            
        Returns:
            Normalized price
        """
        if self.normalization_type == NormalizationType.TICK_RELATIVE:
            # Express as tick offset relative to midprice
            return (price - self.state.midprice) / self.tick_size
        
        elif self.normalization_type == NormalizationType.LOG_NORMALIZED:
            # Log-normalized relative to midprice
            if price > 0 and self.state.midprice > 0:
                return np.log(price / self.state.midprice)
            else:
                return 0.0
        
        elif self.normalization_type == NormalizationType.Z_SCORE:
            # Z-score normalization using rolling statistics
            if len(self.state.price_history) > 1:
                price_mean = np.mean(self.state.price_history)
                price_std = np.std(self.state.price_history)
                if price_std > 0:
                    return (price - price_mean) / price_std
            return 0.0
        
        elif self.normalization_type == NormalizationType.MIN_MAX:
            # Min-max normalization
            if len(self.state.price_history) > 1:
                price_min = np.min(self.state.price_history)
                price_max = np.max(self.state.price_history)
                if price_max > price_min:
                    return (price - price_min) / (price_max - price_min)
            return 0.5
        
        else:
            # Default: no normalization
            return price
    
    def denormalize_price(self, normalized_price: float) -> float:
        """
        Denormalize price back to raw value.
        
        Args:
            normalized_price: Normalized price
            
        Returns:
            Raw price
        """
        if self.normalization_type == NormalizationType.TICK_RELATIVE:
            return normalized_price * self.tick_size + self.state.midprice
        
        elif self.normalization_type == NormalizationType.LOG_NORMALIZED:
            return self.state.midprice * np.exp(normalized_price)
        
        elif self.normalization_type == NormalizationType.Z_SCORE:
            if len(self.state.price_history) > 1:
                price_mean = np.mean(self.state.price_history)
                price_std = np.std(self.state.price_history)
                return normalized_price * price_std + price_mean
            return self.state.midprice
        
        elif self.normalization_type == NormalizationType.MIN_MAX:
            if len(self.state.price_history) > 1:
                price_min = np.min(self.state.price_history)
                price_max = np.max(self.state.price_history)
                return normalized_price * (price_max - price_min) + price_min
            return self.state.midprice
        
        else:
            return normalized_price
    
    def normalize_size(self, size: int) -> float:
        """
        Normalize size using log normalization with rolling baseline.
        
        Args:
            size: Raw size
            
        Returns:
            Normalized size
        """
        # Add to rolling history
        self.state.size_history.append(size)
        
        # Update rolling statistics
        if len(self.state.size_history) > 1:
            self.state.rolling_mean_size = np.mean(self.state.size_history)
            self.state.rolling_std_size = np.std(self.state.size_history)
        
        # Log normalization with rolling baseline
        log_size = np.log(1 + size)
        log_baseline = np.log(1 + max(self.state.rolling_mean_size, 1))
        
        return log_size / log_baseline
    
    def normalize_time_delta(self, time_delta: int) -> float:
        """
        Normalize time delta using rolling statistics.
        
        Args:
            time_delta: Time delta in nanoseconds
            
        Returns:
            Normalized time delta
        """
        # Add to rolling history
        self.state.time_delta_history.append(time_delta)
        
        # Update rolling statistics
        if len(self.state.time_delta_history) > 1:
            self.state.rolling_mean_time_delta = np.mean(self.state.time_delta_history)
            self.state.rolling_std_time_delta = np.std(self.state.time_delta_history)
        
        # Z-score normalization
        if self.state.rolling_std_time_delta > 0:
            return (time_delta - self.state.rolling_mean_time_delta) / self.state.rolling_std_time_delta
        else:
            return 0.0
    
    def normalize_depth(self, depth_values: List[float]) -> List[float]:
        """
        Normalize depth values using log normalization.
        
        Args:
            depth_values: List of depth values
            
        Returns:
            List of normalized depth values
        """
        normalized = []
        for depth in depth_values:
            if depth > 0:
                normalized.append(np.log(1 + depth))
            else:
                normalized.append(0.0)
        return normalized
    
    def normalize_imbalance(self, bid_volume: float, ask_volume: float) -> float:
        """
        Normalize order flow imbalance.
        
        Args:
            bid_volume: Bid volume
            ask_volume: Ask volume
            
        Returns:
            Normalized imbalance in [-1, 1]
        """
        total_volume = bid_volume + ask_volume
        if total_volume > 0:
            return (bid_volume - ask_volume) / total_volume
        else:
            return 0.0
    
    def squash_outliers(self, value: float, alpha: float = 1.0) -> float:
        """
        Apply tanh squash to handle outliers.
        
        Args:
            value: Input value
            alpha: Squash parameter
            
        Returns:
            Squashed value in [-1, 1]
        """
        return np.tanh(alpha * value)
    
    def normalize_event(self, 
                       price: float,
                       size: int,
                       time_delta: int,
                       midprice: float,
                       timestamp: int) -> Dict[str, float]:
        """
        Normalize a complete MBO event.
        
        Args:
            price: Raw price
            size: Raw size
            time_delta: Time delta in nanoseconds
            midprice: Current midprice
            timestamp: Current timestamp
            
        Returns:
            Dictionary of normalized values
        """
        # Update midprice
        self.update_midprice(midprice, timestamp)
        
        # Normalize components
        normalized = {
            'price_norm': self.normalize_price(price),
            'size_norm': self.normalize_size(size),
            'time_delta_norm': self.normalize_time_delta(time_delta)
        }
        
        # Apply outlier squashing if needed
        if self.normalization_type in [NormalizationType.Z_SCORE, NormalizationType.MIN_MAX]:
            normalized['price_norm'] = self.squash_outliers(normalized['price_norm'])
            normalized['size_norm'] = self.squash_outliers(normalized['size_norm'])
            normalized['time_delta_norm'] = self.squash_outliers(normalized['time_delta_norm'])
        
        return normalized
    
    def get_normalization_info(self) -> Dict[str, Any]:
        """
        Get current normalization state information.
        
        Returns:
            Dictionary with normalization state
        """
        return {
            'normalization_type': self.normalization_type.value,
            'tick_size': self.tick_size,
            'current_midprice': self.state.midprice,
            'session_open_midprice': self.state.session_open_midprice,
            'ema_fast': self.state.ema_fast,
            'ema_medium': self.state.ema_medium,
            'ema_slow': self.state.ema_slow,
            'rolling_mean_size': self.state.rolling_mean_size,
            'rolling_std_size': self.state.rolling_std_size,
            'rolling_mean_time_delta': self.state.rolling_mean_time_delta,
            'rolling_std_time_delta': self.state.rolling_std_time_delta,
            'price_history_length': len(self.state.price_history),
            'size_history_length': len(self.state.size_history),
            'time_delta_history_length': len(self.state.time_delta_history)
        }


class BatchNormalizer:
    """
    Batch normalizer for processing large datasets.
    
    Provides efficient batch normalization while maintaining
    consistency with streaming normalization.
    """
    
    def __init__(self, normalization_type: NormalizationType = NormalizationType.TICK_RELATIVE):
        """
        Initialize batch normalizer.
        
        Args:
            normalization_type: Type of normalization to apply
        """
        self.normalization_type = normalization_type
        self.engine = NormalizationEngine(normalization_type)
    
    def normalize_batch(self, 
                       df: pd.DataFrame,
                       price_col: str = 'price',
                       size_col: str = 'size',
                       time_col: str = 'ts_event',
                       midprice_col: str = 'midprice') -> pd.DataFrame:
        """
        Normalize a batch of MBO events.
        
        Args:
            df: DataFrame with MBO events
            price_col: Price column name
            size_col: Size column name
            time_col: Timestamp column name
            midprice_col: Midprice column name
            
        Returns:
            DataFrame with normalized columns added
        """
        if df.empty:
            return df
        
        # Sort by timestamp
        df = df.sort_values(time_col).reset_index(drop=True)
        
        # Initialize result DataFrame
        result_df = df.copy()
        
        # Process events sequentially to maintain state consistency
        normalized_prices = []
        normalized_sizes = []
        normalized_time_deltas = []
        
        prev_timestamp = None
        
        for idx, row in df.iterrows():
            # Calculate time delta
            if prev_timestamp is not None:
                time_delta = row[time_col] - prev_timestamp
            else:
                time_delta = 0
            
            # Normalize event
            normalized = self.engine.normalize_event(
                price=row[price_col],
                size=row[size_col],
                time_delta=time_delta,
                midprice=row[midprice_col],
                timestamp=row[time_col]
            )
            
            normalized_prices.append(normalized['price_norm'])
            normalized_sizes.append(normalized['size_norm'])
            normalized_time_deltas.append(normalized['time_delta_norm'])
            
            prev_timestamp = row[time_col]
        
        # Add normalized columns
        result_df['price_norm'] = normalized_prices
        result_df['size_norm'] = normalized_sizes
        result_df['time_delta_norm'] = normalized_time_deltas
        
        return result_df


# Global normalization engine
_normalization_engine = None

def get_normalization_engine(normalization_type: NormalizationType = NormalizationType.TICK_RELATIVE) -> NormalizationEngine:
    """Get global normalization engine."""
    global _normalization_engine
    if _normalization_engine is None or _normalization_engine.normalization_type != normalization_type:
        _normalization_engine = NormalizationEngine(normalization_type)
    return _normalization_engine


def normalize_mbo_event(price: float,
                       size: int,
                       time_delta: int,
                       midprice: float,
                       timestamp: int,
                       normalization_type: NormalizationType = NormalizationType.TICK_RELATIVE) -> Dict[str, float]:
    """Normalize a single MBO event."""
    engine = get_normalization_engine(normalization_type)
    return engine.normalize_event(price, size, time_delta, midprice, timestamp)


def denormalize_price(normalized_price: float,
                     normalization_type: NormalizationType = NormalizationType.TICK_RELATIVE) -> float:
    """Denormalize a price back to raw value."""
    engine = get_normalization_engine(normalization_type)
    return engine.denormalize_price(normalized_price)
