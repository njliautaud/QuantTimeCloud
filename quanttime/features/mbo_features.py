"""
MBO (Market By Order) Level 3 Feature Engineering

Comprehensive feature engineering for MBO data, designed for 1-5 minute price predictions
and multi-second to multi-minute trading strategies. Optimized for memory efficiency.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Generator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from collections import deque
import warnings

logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """Configuration for MBO feature engineering."""
    # Time windows for feature calculation (in minutes)
    short_window: int = 1      # 1 minute - immediate market conditions
    medium_window: int = 5     # 5 minutes - short-term trends
    long_window: int = 15      # 15 minutes - medium-term trends
    
    # Order book configuration
    order_book_depth: int = 10  # Number of price levels to track
    volume_threshold: int = 100  # Minimum volume for large order detection
    
    # Price precision
    price_precision: int = 2   # Decimal places for price rounding
    
    # Memory management
    batch_size: int = 10000    # Process data in batches (reduced from 50000)
    max_order_history: int = 5000  # Maximum orders to keep in memory (reduced from 10000)
    sub_batch_size: int = 1000  # Sub-batch size for processing
    memory_efficient: bool = True  # Enable memory optimization
    
    # Feature selection
    include_order_flow: bool = True
    include_microstructure: bool = True
    include_rolling_features: bool = True
    include_cross_features: bool = True
    
    # Target horizons (in minutes)
    target_horizons: List[int] = field(default_factory=lambda: [1, 3, 5])


class MBOFeatureEngineer:
    """Feature engineering for MBO Level 3 data with memory optimization."""
    
    def __init__(self, config: FeatureConfig = None):
        self.config = config or FeatureConfig()
        
        # Order book state - use more efficient data structures
        self.order_book = {'bids': {}, 'asks': {}}
        
        # Order history for flow analysis - limit size
        self.order_history = deque(maxlen=min(self.config.max_order_history, 5000))
        
        # Rolling statistics - limit size for memory efficiency
        self.price_history = deque(maxlen=500)  # Reduced from 1000
        self.volume_history = deque(maxlen=500)  # Reduced from 1000
        
        # Session tracking
        self.current_session = None
        self.session_start_time = None
        
        # Memory management
        self._last_cleanup = 0
        self._cleanup_interval = 10000  # Cleanup every 10k events
    
    def reset_order_book(self):
        """Reset the order book state."""
        self.order_book = {'bids': {}, 'asks': {}}
        self.order_history.clear()
        self.price_history.clear()
        self.volume_history.clear()
        self.current_session = None
        self.session_start_time = None
        self._last_cleanup = 0
    
    def _cleanup_memory(self):
        """Periodic memory cleanup to prevent memory bloat."""
        # Clear old orders from history if too many
        if len(self.order_history) > self.config.max_order_history * 0.8:
            # Keep only recent orders
            recent_orders = list(self.order_history)[-self.config.max_order_history//2:]
            self.order_history.clear()
            self.order_history.extend(recent_orders)
        
        # Clear old price/volume data if too much
        if len(self.price_history) > 400:
            recent_prices = list(self.price_history)[-200:]
            self.price_history.clear()
            self.price_history.extend(recent_prices)
        
        if len(self.volume_history) > 400:
            recent_volumes = list(self.volume_history)[-200:]
            self.volume_history.clear()
            self.volume_history.extend(recent_volumes)
    
    def update_order_book(self, event: pd.Series):
        """Update order book with MBO event."""
        price = event['price']
        size = event['size']
        side = event['side']
        action = event['action']
        
        # Update price and volume history
        self.price_history.append(price)
        self.volume_history.append(size)
        
        # Handle different event types
        if action == 'add':
            if side == 'B':
                self.order_book['bids'][price] = self.order_book['bids'].get(price, 0) + size
            else:
                self.order_book['asks'][price] = self.order_book['asks'].get(price, 0) + size
                
        elif action == 'cancel':
            if side == 'B' and price in self.order_book['bids']:
                self.order_book['bids'][price] = max(0, self.order_book['bids'][price] - size)
                if self.order_book['bids'][price] == 0:
                    del self.order_book['bids'][price]
            elif side == 'A' and price in self.order_book['asks']:
                self.order_book['asks'][price] = max(0, self.order_book['asks'][price] - size)
                if self.order_book['asks'][price] == 0:
                    del self.order_book['asks'][price]
                    
        elif action == 'execute':
            if side == 'B':
                if price in self.order_book['asks']:
                    self.order_book['asks'][price] = max(0, self.order_book['asks'][price] - size)
                    if self.order_book['asks'][price] == 0:
                        del self.order_book['asks'][price]
            else:
                if price in self.order_book['bids']:
                    self.order_book['bids'][price] = max(0, self.order_book['bids'][price] - size)
                    if self.order_book['bids'][price] == 0:
                        del self.order_book['bids'][price]
        
        # Add to order history
        order_info = {
            'price': price,
            'size': size,
            'side': side,
            'action': action,
            'timestamp': event['ts_event']
        }
        self.order_history.append(order_info)
        
        # Periodic memory cleanup
        self._last_cleanup += 1
        if self._last_cleanup >= self._cleanup_interval:
            self._cleanup_memory()
            self._last_cleanup = 0
    
    def get_order_book_features(self) -> Dict:
        """Extract order book features."""
        if not self.order_book['bids'] or not self.order_book['asks']:
            return {}
        
        # Best bid/ask
        best_bid = max(self.order_book['bids'].keys())
        best_ask = min(self.order_book['asks'].keys())
        mid_price = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        
        # Order book depth
        bid_prices = sorted(self.order_book['bids'].keys(), reverse=True)[:self.config.order_book_depth]
        ask_prices = sorted(self.order_book['asks'].keys())[:self.config.order_book_depth]
        
        total_bid_size = sum(self.order_book['bids'][p] for p in bid_prices)
        total_ask_size = sum(self.order_book['asks'][p] for p in ask_prices)
        
        # Imbalance
        imbalance_ratio = (total_bid_size - total_ask_size) / (total_bid_size + total_ask_size) if (total_bid_size + total_ask_size) > 0 else 0
        
        # Large order detection
        large_bid_orders = sum(1 for size in self.order_book['bids'].values() if size >= self.config.volume_threshold)
        large_ask_orders = sum(1 for size in self.order_book['asks'].values() if size >= self.config.volume_threshold)
        
        # Depth at different levels
        depth_levels = [1, 3, 5, 10]
        depth_features = {}
        
        for level in depth_levels:
            if len(bid_prices) >= level and len(ask_prices) >= level:
                bid_depth = sum(self.order_book['bids'][p] for p in bid_prices[:level])
                ask_depth = sum(self.order_book['asks'][p] for p in ask_prices[:level])
                depth_features[f'depth_imbalance_{level}'] = (bid_depth - ask_depth) / (bid_depth + ask_depth) if (bid_depth + ask_depth) > 0 else 0
        
        return {
            'best_bid': best_bid,
            'best_ask': best_ask,
            'mid_price': mid_price,
            'spread': spread,
            'spread_bps': spread / mid_price * 10000 if mid_price > 0 else 0,
            'total_bid_size': total_bid_size,
            'total_ask_size': total_ask_size,
            'imbalance_ratio': imbalance_ratio,
            'large_bid_orders': large_bid_orders,
            'large_ask_orders': large_ask_orders,
            **depth_features
        }
    
    def get_order_flow_features(self, window_minutes: int = 5) -> Dict:
        """Calculate order flow features from recent history."""
        if not self.order_history:
            return {}
        
        # Convert window to nanoseconds
        window_ns = window_minutes * 60 * 1_000_000_000
        current_time = self.order_history[-1]['timestamp']
        
        # Filter recent orders
        recent_orders = [
            order for order in self.order_history
            if current_time - order['timestamp'] <= window_ns
        ]
        
        if not recent_orders:
            return {}
        
        # Volume analysis
        total_volume = sum(order['size'] for order in recent_orders)
        buy_volume = sum(order['size'] for order in recent_orders if order['side'] == 'B')
        ask_volume = sum(order['size'] for order in recent_orders if order['side'] == 'A')
        
        # Net flow
        net_flow = buy_volume - ask_volume
        net_flow_ratio = net_flow / total_volume if total_volume > 0 else 0
        
        # Action analysis
        add_volume = sum(order['size'] for order in recent_orders if order['action'] == 'add')
        cancel_volume = sum(order['size'] for order in recent_orders if order['action'] == 'cancel')
        execute_volume = sum(order['size'] for order in recent_orders if order['action'] == 'execute')
        
        # Price analysis
        prices = [order['price'] for order in recent_orders]
        price_range = max(prices) - min(prices) if prices else 0
        price_volatility = np.std(prices) if len(prices) > 1 else 0
        
        # Order count analysis
        total_orders = len(recent_orders)
        unique_orders = len(set((order['price'], order['side']) for order in recent_orders))
        avg_order_size = total_volume / total_orders if total_orders > 0 else 0
        
        return {
            f'volume_{window_minutes}m': total_volume,
            f'buy_volume_{window_minutes}m': buy_volume,
            f'ask_volume_{window_minutes}m': ask_volume,
            f'net_flow_{window_minutes}m': net_flow,
            f'net_flow_ratio_{window_minutes}m': net_flow_ratio,
            f'add_volume_{window_minutes}m': add_volume,
            f'cancel_volume_{window_minutes}m': cancel_volume,
            f'execute_volume_{window_minutes}m': execute_volume,
            f'price_range_{window_minutes}m': price_range,
            f'price_volatility_{window_minutes}m': price_volatility,
            f'order_count_{window_minutes}m': total_orders,
            f'unique_orders_{window_minutes}m': unique_orders,
            f'avg_order_size_{window_minutes}m': avg_order_size
        }
    
    def get_market_microstructure_features(self) -> Dict:
        """Calculate market microstructure features."""
        if len(self.price_history) < 10:
            return {}
        
        prices = list(self.price_history)
        volumes = list(self.volume_history)
        
        # Price momentum
        price_momentum_1m = (prices[-1] - prices[-60]) / prices[-60] if len(prices) >= 60 else 0
        price_momentum_5m = (prices[-1] - prices[-300]) / prices[-300] if len(prices) >= 300 else 0
        
        # Volume analysis
        recent_volume = sum(volumes[-60:]) if len(volumes) >= 60 else sum(volumes)
        avg_volume = np.mean(volumes[-100:]) if len(volumes) >= 100 else np.mean(volumes)
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
        
        # Price efficiency
        price_changes = np.diff(prices)
        price_efficiency = np.abs(np.sum(price_changes)) / np.sum(np.abs(price_changes)) if np.sum(np.abs(price_changes)) > 0 else 0
        
        # Large trade detection
        large_trades = sum(1 for v in volumes[-100:] if v >= self.config.volume_threshold)
        large_trade_ratio = large_trades / min(100, len(volumes)) if volumes else 0
        
        return {
            'price_momentum_1m': price_momentum_1m,
            'price_momentum_5m': price_momentum_5m,
            'volume_ratio': volume_ratio,
            'price_efficiency': price_efficiency,
            'large_trade_ratio': large_trade_ratio
        }
    
    def process_mbo_batch(self, mbo_batch: pd.DataFrame) -> pd.DataFrame:
        """Process a batch of MBO data and extract features with memory optimization."""
        features_list = []
        
        # Process in smaller sub-batches to avoid memory buildup
        sub_batch_size = 1000
        total_events = len(mbo_batch)
        
        for sub_start in range(0, total_events, sub_batch_size):
            sub_end = min(sub_start + sub_batch_size, total_events)
            sub_batch = mbo_batch.iloc[sub_start:sub_end]
            
            sub_features = []
            for _, event in sub_batch.iterrows():
                # Update order book
                self.update_order_book(event)
                
                # Extract features
                features = {
                    'ts_event': event['ts_event'],
                    'datetime': pd.to_datetime(event['ts_event'], unit='ns')
                }
                
                # Order book features
                ob_features = self.get_order_book_features()
                features.update(ob_features)
                
                # Order flow features
                if self.config.include_order_flow:
                    flow_features = self.get_order_flow_features(self.config.short_window)
                    features.update(flow_features)
                    
                    flow_features_5m = self.get_order_flow_features(5)
                    features.update(flow_features_5m)
                
                # Microstructure features
                if self.config.include_microstructure:
                    micro_features = self.get_market_microstructure_features()
                    features.update(micro_features)
                
                sub_features.append(features)
            
            # Convert sub-batch to DataFrame and add to main list
            sub_df = pd.DataFrame(sub_features)
            features_list.append(sub_df)
            
            # Clear sub-batch from memory
            del sub_features, sub_batch
        
        # Combine all sub-batches
        if features_list:
            result_df = pd.concat(features_list, ignore_index=True)
            del features_list
            return result_df
        else:
            return pd.DataFrame()
    
    def process_mbo_stream(self, mbo_generator: Generator[pd.DataFrame, None, None]) -> Generator[pd.DataFrame, None, None]:
        """Process MBO data from a generator and yield feature batches."""
        for batch in mbo_generator:
            features_df = self.process_mbo_batch(batch)
            if not features_df.empty:
                yield features_df
    
    def get_rolling_features(self, features_df: pd.DataFrame, windows: List[int] = None) -> pd.DataFrame:
        """Add rolling window features to the feature DataFrame."""
        if windows is None:
            windows = [self.config.short_window, self.config.medium_window, self.config.long_window]
        
        df = features_df.copy()
        
        # Ensure datetime column exists and is sorted
        if 'datetime' not in df.columns:
            df['datetime'] = pd.to_datetime(df['ts_event'], unit='ns')
        
        # Sort by datetime to ensure monotonic index
        df = df.sort_values('datetime').reset_index(drop=True)
        df.set_index('datetime', inplace=True)
        
        # Price-based rolling features
        if 'mid_price' in df.columns:
            for window in windows:
                window_minutes = window
                df[f'price_ma_{window_minutes}m'] = df['mid_price'].rolling(f'{window_minutes}T').mean()
                df[f'price_std_{window_minutes}m'] = df['mid_price'].rolling(f'{window_minutes}T').std()
                df[f'price_momentum_{window_minutes}m'] = df['mid_price'].pct_change(window_minutes)
        
        # Volume-based rolling features
        volume_cols = [col for col in df.columns if 'volume_' in col and 'ratio' not in col]
        for col in volume_cols:
            for window in windows:
                window_minutes = window
                df[f'{col}_ma_{window_minutes}m'] = df[col].rolling(f'{window_minutes}T').mean()
                df[f'{col}_std_{window_minutes}m'] = df[col].rolling(f'{window_minutes}T').std()
        
        # Spread-based rolling features
        if 'spread' in df.columns:
            for window in windows:
                window_minutes = window
                df[f'spread_ma_{window_minutes}m'] = df['spread'].rolling(f'{window_minutes}T').mean()
                df[f'spread_std_{window_minutes}m'] = df['spread'].rolling(f'{window_minutes}T').std()
        
        # Imbalance-based rolling features
        if 'imbalance_ratio' in df.columns:
            for window in windows:
                window_minutes = window
                df[f'imbalance_ma_{window_minutes}m'] = df['imbalance_ratio'].rolling(f'{window_minutes}T').mean()
                df[f'imbalance_std_{window_minutes}m'] = df['imbalance_ratio'].rolling(f'{window_minutes}T').std()
        
        return df.reset_index()
    
    def get_cross_features(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Create interaction terms between features."""
        df = features_df.copy()
        
        # Price-volume interactions
        if 'mid_price' in df.columns and 'volume_5m' in df.columns:
            df['price_volume_interaction'] = df['mid_price'] * df['volume_5m']
        
        # Spread-volume interactions
        if 'spread' in df.columns and 'volume_5m' in df.columns:
            df['spread_volume_interaction'] = df['spread'] * df['volume_5m']
        
        # Imbalance-spread interactions
        if 'imbalance_ratio' in df.columns and 'spread' in df.columns:
            df['imbalance_spread_interaction'] = df['imbalance_ratio'] * df['spread']
        
        # Order pressure (imbalance * volume)
        if 'imbalance_ratio' in df.columns and 'volume_5m' in df.columns:
            df['order_pressure'] = df['imbalance_ratio'] * df['volume_5m']
        
        # Volatility-volume interaction
        if 'price_volatility_5m' in df.columns and 'volume_5m' in df.columns:
            df['volatility_volume_interaction'] = df['price_volatility_5m'] * df['volume_5m']
        
        return df
    
    def create_target_variables(self, features_df: pd.DataFrame, target_horizons: List[int] = None) -> pd.DataFrame:
        """Create target variables for different prediction horizons."""
        if target_horizons is None:
            target_horizons = self.config.target_horizons
        
        df = features_df.copy()
        
        # Ensure datetime index
        if 'datetime' not in df.columns:
            df['datetime'] = pd.to_datetime(df['ts_event'], unit='ns')
        
        df = df.sort_values('datetime').reset_index(drop=True)
        df.set_index('datetime', inplace=True)
        
        if 'mid_price' not in df.columns:
            return df.reset_index()
        
        for horizon in target_horizons:
            horizon_minutes = horizon
            
            # Future price change
            df[f'price_change_{horizon_minutes}m'] = df['mid_price'].shift(-horizon_minutes) - df['mid_price']
            
            # Future return
            df[f'price_return_{horizon_minutes}m'] = df['mid_price'].pct_change(horizon_minutes).shift(-horizon_minutes)
            
            # Future direction (1 for up, 0 for down)
            df[f'price_direction_{horizon_minutes}m'] = (df[f'price_return_{horizon_minutes}m'] > 0).astype(int)
            
            # Future volatility
            future_prices = df['mid_price'].shift(-horizon_minutes)
            if horizon_minutes > 1:
                df[f'price_volatility_{horizon_minutes}m'] = future_prices.rolling(horizon_minutes).std()
            else:
                df[f'price_volatility_{horizon_minutes}m'] = 0
        
        return df.reset_index()


def engineer_mbo_features(mbo_df: pd.DataFrame, config: FeatureConfig = None) -> pd.DataFrame:
    """Main function to orchestrate feature engineering with memory optimization."""
    config = config or FeatureConfig()
    engineer = MBOFeatureEngineer(config)
    
    # Reduce batch size for memory efficiency
    config.batch_size = min(config.batch_size, 10000)  # Smaller batches
    
    total_rows = len(mbo_df)
    logger.info(f"Processing {total_rows} MBO events in batches of {config.batch_size}")
    
    # Process data in smaller chunks and write to disk if needed
    if total_rows > 100000:  # Large dataset - use disk-based processing
        return _process_large_dataset(mbo_df, engineer, config)
    else:
        return _process_small_dataset(mbo_df, engineer, config)


def _process_small_dataset(mbo_df: pd.DataFrame, engineer: MBOFeatureEngineer, config: FeatureConfig) -> pd.DataFrame:
    """Process smaller datasets in memory."""
    total_rows = len(mbo_df)
    feature_dfs = []
    
    for start_idx in range(0, total_rows, config.batch_size):
        end_idx = min(start_idx + config.batch_size, total_rows)
        batch = mbo_df.iloc[start_idx:end_idx].copy()
        
        logger.info(f"Processing batch {start_idx//config.batch_size + 1}/{(total_rows-1)//config.batch_size + 1}")
        
        features_df = engineer.process_mbo_batch(batch)
        feature_dfs.append(features_df)
        
        # Clear batch from memory
        del batch
    
    # Combine all batches
    if feature_dfs:
        logger.info("Combining feature batches...")
        combined_df = pd.concat(feature_dfs, ignore_index=True)
        
        # Clear individual batches from memory
        del feature_dfs
        
        # Add rolling features
        if config.include_rolling_features:
            logger.info("Adding rolling features...")
            combined_df = engineer.get_rolling_features(combined_df)
        
        # Add cross features
        if config.include_cross_features:
            logger.info("Adding cross features...")
            combined_df = engineer.get_cross_features(combined_df)
        
        # Create target variables
        logger.info("Creating target variables...")
        combined_df = engineer.create_target_variables(combined_df)
        
        return combined_df
    else:
        return pd.DataFrame()


def _process_large_dataset(mbo_df: pd.DataFrame, engineer: MBOFeatureEngineer, config: FeatureConfig) -> pd.DataFrame:
    """Process large datasets using disk-based processing."""
    import tempfile
    import os
    
    total_rows = len(mbo_df)
    temp_files = []
    
    try:
        # Process in chunks and save to temporary files
        for start_idx in range(0, total_rows, config.batch_size):
            end_idx = min(start_idx + config.batch_size, total_rows)
            batch = mbo_df.iloc[start_idx:end_idx].copy()
            
            logger.info(f"Processing large batch {start_idx//config.batch_size + 1}/{(total_rows-1)//config.batch_size + 1}")
            
            features_df = engineer.process_mbo_batch(batch)
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.parquet')
            features_df.to_parquet(temp_file.name, index=False)
            temp_files.append(temp_file.name)
            
            # Clear from memory
            del batch, features_df
        
        # Combine temporary files
        logger.info("Combining temporary files...")
        combined_dfs = []
        for temp_file in temp_files:
            df = pd.read_parquet(temp_file)
            combined_dfs.append(df)
        
        combined_df = pd.concat(combined_dfs, ignore_index=True)
        del combined_dfs
        
        # Add rolling features (in chunks)
        if config.include_rolling_features:
            logger.info("Adding rolling features to large dataset...")
            combined_df = _add_rolling_features_chunked(combined_df, engineer)
        
        # Add cross features (in chunks)
        if config.include_cross_features:
            logger.info("Adding cross features to large dataset...")
            combined_df = _add_cross_features_chunked(combined_df, engineer)
        
        # Create target variables
        logger.info("Creating target variables for large dataset...")
        combined_df = engineer.create_target_variables(combined_df)
        
        return combined_df
        
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass


def _add_rolling_features_chunked(df: pd.DataFrame, engineer: MBOFeatureEngineer) -> pd.DataFrame:
    """Add rolling features in chunks to avoid memory issues."""
    chunk_size = 50000
    total_rows = len(df)
    result_dfs = []
    
    for start_idx in range(0, total_rows, chunk_size):
        end_idx = min(start_idx + chunk_size, total_rows)
        chunk = df.iloc[start_idx:end_idx].copy()
        
        # Add some overlap for rolling calculations
        if start_idx > 0:
            overlap_start = max(0, start_idx - 1000)
            overlap_chunk = df.iloc[overlap_start:start_idx]
            chunk = pd.concat([overlap_chunk, chunk], ignore_index=True)
        
        chunk_with_features = engineer.get_rolling_features(chunk)
        
        # Remove overlap if it was added
        if start_idx > 0:
            chunk_with_features = chunk_with_features.iloc[1000:].reset_index(drop=True)
        
        result_dfs.append(chunk_with_features)
    
    return pd.concat(result_dfs, ignore_index=True)


def _add_cross_features_chunked(df: pd.DataFrame, engineer: MBOFeatureEngineer) -> pd.DataFrame:
    """Add cross features in chunks to avoid memory issues."""
    chunk_size = 50000
    total_rows = len(df)
    result_dfs = []
    
    for start_idx in range(0, total_rows, chunk_size):
        end_idx = min(start_idx + chunk_size, total_rows)
        chunk = df.iloc[start_idx:end_idx].copy()
        
        chunk_with_features = engineer.get_cross_features(chunk)
        result_dfs.append(chunk_with_features)
    
    return pd.concat(result_dfs, ignore_index=True)


def get_feature_importance_ranking(features_df: pd.DataFrame, target_col: str = 'price_direction_5m') -> pd.DataFrame:
    """Rank features by importance using correlation."""
    if target_col not in features_df.columns:
        return pd.DataFrame()
    
    # Select numeric features
    numeric_cols = features_df.select_dtypes(include=[np.number]).columns
    feature_cols = [col for col in numeric_cols if col != target_col and not col.startswith('price_')]
    
    if not feature_cols:
        return pd.DataFrame()
    
    # Calculate correlations
    correlations = []
    for col in feature_cols:
        corr = abs(features_df[col].corr(features_df[target_col]))
        if not pd.isna(corr):
            correlations.append({'feature': col, 'correlation': corr})
    
    # Sort by correlation
    importance_df = pd.DataFrame(correlations)
    importance_df = importance_df.sort_values('correlation', ascending=False)
    
    return importance_df


def validate_features(features_df: pd.DataFrame) -> Dict:
    """Validate feature quality."""
    validation_results = {}
    
    # Check for missing values
    missing_counts = features_df.isnull().sum()
    validation_results['missing_values'] = missing_counts[missing_counts > 0].to_dict()
    
    # Check for infinite values
    inf_counts = np.isinf(features_df.select_dtypes(include=[np.number])).sum()
    validation_results['infinite_values'] = inf_counts[inf_counts > 0].to_dict()
    
    # Check for constant features
    constant_features = []
    for col in features_df.columns:
        if features_df[col].nunique() <= 1:
            constant_features.append(col)
    validation_results['constant_features'] = constant_features
    
    # Check for highly correlated features
    numeric_df = features_df.select_dtypes(include=[np.number])
    if len(numeric_df.columns) > 1:
        corr_matrix = numeric_df.corr().abs()
        high_corr_pairs = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                if corr_matrix.iloc[i, j] > 0.95:
                    high_corr_pairs.append((corr_matrix.columns[i], corr_matrix.columns[j]))
        validation_results['highly_correlated_features'] = high_corr_pairs
    
    return validation_results
