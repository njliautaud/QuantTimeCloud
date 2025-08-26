"""
MBO Feature Engineering for Tick-by-Tick Model Training.

This module implements comprehensive feature engineering for Market By Order (MBO) data,
creating features suitable for machine learning models that simulate real-time trading.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
import logging
from datetime import datetime, timedelta
from collections import deque
import warnings

logger = logging.getLogger(__name__)


class MBOFeatureEngineer:
    """
    Feature engineer for MBO data with tick-by-tick processing.
    
    Features:
    - Order book reconstruction and features
    - Market microstructure features
    - Technical indicators
    - Volume profile features
    - Price action features
    - Time-based features
    """
    
    def __init__(self, 
                 orderbook_depth: int = 10,
                 sequence_length: int = 100,
                 feature_window: int = 50,
                 use_mixed_precision: bool = True):
        """
        Initialize MBO feature engineer.
        
        Args:
            orderbook_depth: Number of levels to maintain in order book
            sequence_length: Length of sequence for time series features
            feature_window: Window size for rolling features
            use_mixed_precision: Use float32 for memory optimization
        """
        self.orderbook_depth = orderbook_depth
        self.sequence_length = sequence_length
        self.feature_window = feature_window
        self.use_mixed_precision = use_mixed_precision
        
        # Initialize data structures for real-time processing
        self.orderbook = {'bids': deque(maxlen=orderbook_depth), 'asks': deque(maxlen=orderbook_depth)}
        self.price_history = deque(maxlen=sequence_length)
        self.volume_history = deque(maxlen=sequence_length)
        self.trade_history = deque(maxlen=sequence_length)
        
        # Feature cache for optimization
        self.feature_cache = {}
        
        logger.info(f"MBO Feature Engineer initialized:")
        logger.info(f"  Order book depth: {orderbook_depth}")
        logger.info(f"  Sequence length: {sequence_length}")
        logger.info(f"  Feature window: {feature_window}")
        logger.info(f"  Mixed precision: {use_mixed_precision}")
    
    def reset_state(self):
        """Reset all internal state for new data stream."""
        self.orderbook = {'bids': deque(maxlen=self.orderbook_depth), 'asks': deque(maxlen=self.orderbook_depth)}
        self.price_history = deque(maxlen=self.sequence_length)
        self.volume_history = deque(maxlen=self.sequence_length)
        self.trade_history = deque(maxlen=self.sequence_length)
        self.feature_cache = {}
        logger.debug("Feature engineer state reset")
    
    def update_orderbook(self, mbo_event: Dict) -> None:
        """
        Update order book with new MBO event.
        
        Args:
            mbo_event: MBO event dictionary with price, size, side, action
        """
        price = mbo_event['price']
        size = mbo_event['size']
        side = mbo_event['side']
        action = mbo_event['action']
        
        # Handle different action types
        if action == 'A':  # Add order
            self._add_order(price, size, side)
        elif action == 'M':  # Modify order
            self._modify_order(price, size, side)
        elif action == 'D':  # Delete order
            self._delete_order(price, side)
        elif action == 'F':  # Fill/Execution
            self._handle_execution(price, size, side)
    
    def _add_order(self, price: float, size: int, side: str):
        """Add new order to order book."""
        order = {'price': price, 'size': size}
        
        if side == 'B':
            # Insert bid in descending order
            self.orderbook['bids'].append(order)
            self.orderbook['bids'] = deque(sorted(self.orderbook['bids'], 
                                                 key=lambda x: x['price'], reverse=True), 
                                         maxlen=self.orderbook_depth)
        else:
            # Insert ask in ascending order
            self.orderbook['asks'].append(order)
            self.orderbook['asks'] = deque(sorted(self.orderbook['asks'], 
                                                 key=lambda x: x['price']), 
                                         maxlen=self.orderbook_depth)
    
    def _modify_order(self, price: float, size: int, side: str):
        """Modify existing order in order book."""
        orders = self.orderbook['bids'] if side == 'B' else self.orderbook['asks']
        
        for order in orders:
            if order['price'] == price:
                order['size'] = size
                break
    
    def _delete_order(self, price: float, side: str):
        """Delete order from order book."""
        orders = self.orderbook['bids'] if side == 'B' else self.orderbook['asks']
        
        for i, order in enumerate(orders):
            if order['price'] == price:
                del orders[i]
                break
    
    def _handle_execution(self, price: float, size: int, side: str):
        """Handle trade execution."""
        # Update trade history
        trade = {
            'price': price,
            'size': size,
            'side': side,
            'timestamp': datetime.now()
        }
        self.trade_history.append(trade)
        
        # Update price and volume history
        self.price_history.append(price)
        self.volume_history.append(size)
        
        # Update order book (reduce size of matching orders)
        orders = self.orderbook['bids'] if side == 'B' else self.orderbook['asks']
        remaining_size = size
        
        for order in orders:
            if order['price'] == price and remaining_size > 0:
                if order['size'] <= remaining_size:
                    remaining_size -= order['size']
                    order['size'] = 0
                else:
                    order['size'] -= remaining_size
                    remaining_size = 0
        
        # Remove zero-size orders
        if side == 'B':
            self.orderbook['bids'] = deque([o for o in self.orderbook['bids'] if o['size'] > 0], 
                                         maxlen=self.orderbook_depth)
        else:
            self.orderbook['asks'] = deque([o for o in self.orderbook['asks'] if o['size'] > 0], 
                                         maxlen=self.orderbook_depth)
    
    def get_orderbook_features(self) -> Dict[str, float]:
        """Extract order book features."""
        features = {}
        
        # Bid features
        if self.orderbook['bids']:
            bid_prices = [order['price'] for order in self.orderbook['bids']]
            bid_sizes = [order['size'] for order in self.orderbook['bids']]
            
            features.update({
                'best_bid': bid_prices[0] if bid_prices else 0.0,
                'bid_depth': len(bid_prices),
                'bid_size_total': sum(bid_sizes),
                'bid_size_imbalance': bid_sizes[0] / sum(bid_sizes) if sum(bid_sizes) > 0 else 0.0,
                'bid_price_spread': bid_prices[0] - bid_prices[-1] if len(bid_prices) > 1 else 0.0,
                'bid_size_weighted_price': np.average(bid_prices, weights=bid_sizes) if sum(bid_sizes) > 0 else 0.0
            })
        else:
            features.update({
                'best_bid': 0.0, 'bid_depth': 0, 'bid_size_total': 0.0,
                'bid_size_imbalance': 0.0, 'bid_price_spread': 0.0, 'bid_size_weighted_price': 0.0
            })
        
        # Ask features
        if self.orderbook['asks']:
            ask_prices = [order['price'] for order in self.orderbook['asks']]
            ask_sizes = [order['size'] for order in self.orderbook['asks']]
            
            features.update({
                'best_ask': ask_prices[0] if ask_prices else 0.0,
                'ask_depth': len(ask_prices),
                'ask_size_total': sum(ask_sizes),
                'ask_size_imbalance': ask_sizes[0] / sum(ask_sizes) if sum(ask_sizes) > 0 else 0.0,
                'ask_price_spread': ask_prices[-1] - ask_prices[0] if len(ask_prices) > 1 else 0.0,
                'ask_size_weighted_price': np.average(ask_prices, weights=ask_sizes) if sum(ask_sizes) > 0 else 0.0
            })
        else:
            features.update({
                'best_ask': 0.0, 'ask_depth': 0, 'ask_size_total': 0.0,
                'ask_size_imbalance': 0.0, 'ask_price_spread': 0.0, 'ask_size_weighted_price': 0.0
            })
        
        # Spread features
        if features['best_bid'] > 0 and features['best_ask'] > 0:
            features.update({
                'spread': features['best_ask'] - features['best_bid'],
                'spread_bps': (features['best_ask'] - features['best_bid']) / features['best_bid'] * 10000,
                'mid_price': (features['best_bid'] + features['best_ask']) / 2,
                'size_imbalance': (features['bid_size_total'] - features['ask_size_total']) / 
                                (features['bid_size_total'] + features['ask_size_total']) if 
                                (features['bid_size_total'] + features['ask_size_total']) > 0 else 0.0
            })
        else:
            features.update({
                'spread': 0.0, 'spread_bps': 0.0, 'mid_price': 0.0, 'size_imbalance': 0.0
            })
        
        return features
    
    def get_price_features(self) -> Dict[str, float]:
        """Extract price action features."""
        features = {}
        
        if len(self.price_history) < 2:
            return {k: 0.0 for k in ['price_change', 'price_change_pct', 'price_volatility', 
                                    'price_momentum', 'price_acceleration']}
        
        prices = list(self.price_history)
        
        # Basic price changes
        features['price_change'] = prices[-1] - prices[-2]
        features['price_change_pct'] = (prices[-1] - prices[-2]) / prices[-2] * 100 if prices[-2] > 0 else 0.0
        
        # Volatility (rolling standard deviation)
        if len(prices) >= self.feature_window:
            recent_prices = prices[-self.feature_window:]
            features['price_volatility'] = np.std(recent_prices)
        else:
            features['price_volatility'] = np.std(prices)
        
        # Momentum (price change over longer period)
        if len(prices) >= 10:
            features['price_momentum'] = prices[-1] - prices[-10]
        else:
            features['price_momentum'] = prices[-1] - prices[0] if len(prices) > 1 else 0.0
        
        # Acceleration (change in momentum)
        if len(prices) >= 20:
            momentum_1 = prices[-1] - prices[-10]
            momentum_2 = prices[-10] - prices[-20]
            features['price_acceleration'] = momentum_1 - momentum_2
        else:
            features['price_acceleration'] = 0.0
        
        return features
    
    def get_volume_features(self) -> Dict[str, float]:
        """Extract volume profile features."""
        features = {}
        
        if len(self.volume_history) < 2:
            return {k: 0.0 for k in ['volume_change', 'volume_ma', 'volume_std', 'volume_imbalance',
                                    'volume_momentum', 'volume_acceleration']}
        
        volumes = list(self.volume_history)
        
        # Basic volume changes
        features['volume_change'] = volumes[-1] - volumes[-2]
        features['volume_change_pct'] = (volumes[-1] - volumes[-2]) / volumes[-2] * 100 if volumes[-2] > 0 else 0.0
        
        # Volume moving average
        if len(volumes) >= self.feature_window:
            features['volume_ma'] = np.mean(volumes[-self.feature_window:])
            features['volume_std'] = np.std(volumes[-self.feature_window:])
        else:
            features['volume_ma'] = np.mean(volumes)
            features['volume_std'] = np.std(volumes)
        
        # Volume imbalance (buy vs ask)
        if len(self.trade_history) >= 10:
            recent_trades = list(self.trade_history)[-10:]
            buy_volume = sum(trade['size'] for trade in recent_trades if trade['side'] == 'B')
            ask_volume = sum(trade['size'] for trade in recent_trades if trade['side'] == 'A')
            total_volume = buy_volume + ask_volume
            features['volume_imbalance'] = (buy_volume - ask_volume) / total_volume if total_volume > 0 else 0.0
        else:
            features['volume_imbalance'] = 0.0
        
        # Volume momentum
        if len(volumes) >= 10:
            features['volume_momentum'] = np.mean(volumes[-5:]) - np.mean(volumes[-10:-5])
        else:
            features['volume_momentum'] = 0.0
        
        # Volume acceleration
        if len(volumes) >= 15:
            momentum_1 = np.mean(volumes[-5:]) - np.mean(volumes[-10:-5])
            momentum_2 = np.mean(volumes[-10:-5]) - np.mean(volumes[-15:-10])
            features['volume_acceleration'] = momentum_1 - momentum_2
        else:
            features['volume_acceleration'] = 0.0
        
        return features
    
    def get_time_features(self, timestamp: datetime) -> Dict[str, float]:
        """Extract time-based features."""
        features = {}
        
        # Time of day features
        hour = timestamp.hour
        minute = timestamp.minute
        second = timestamp.second
        
        # Market session features (assuming 9:30-16:00 ET)
        market_open = 9.5  # 9:30 AM
        market_close = 16.0  # 4:00 PM
        
        time_decimal = hour + minute / 60.0 + second / 3600.0
        
        features.update({
            'hour': hour,
            'minute': minute,
            'second': second,
            'time_decimal': time_decimal,
            'market_session': 1.0 if market_open <= time_decimal <= market_close else 0.0,
            'session_progress': (time_decimal - market_open) / (market_close - market_open) if market_open <= time_decimal <= market_close else 0.0,
            'is_market_open': 1.0 if market_open <= time_decimal <= market_close else 0.0
        })
        
        # Day of week features
        weekday = timestamp.weekday()
        features.update({
            'weekday': weekday,
            'is_monday': 1.0 if weekday == 0 else 0.0,
            'is_friday': 1.0 if weekday == 4 else 0.0,
            'is_weekend': 1.0 if weekday >= 5 else 0.0
        })
        
        return features
    
    def get_technical_features(self) -> Dict[str, float]:
        """Extract technical indicators."""
        features = {}
        
        if len(self.price_history) < 20:
            return {k: 0.0 for k in ['rsi', 'macd', 'bollinger_upper', 'bollinger_lower', 
                                    'bollinger_position', 'ema_short', 'ema_long']}
        
        prices = np.array(list(self.price_history))
        
        # RSI (Relative Strength Index)
        if len(prices) >= 14:
            delta = np.diff(prices)
            gain = np.where(delta > 0, delta, 0)
            loss = np.where(delta < 0, -delta, 0)
            
            avg_gain = np.mean(gain[-14:])
            avg_loss = np.mean(loss[-14:])
            
            if avg_loss != 0:
                rs = avg_gain / avg_loss
                features['rsi'] = 100 - (100 / (1 + rs))
            else:
                features['rsi'] = 100.0
        else:
            features['rsi'] = 50.0
        
        # MACD (Moving Average Convergence Divergence)
        if len(prices) >= 26:
            ema_12 = self._calculate_ema(prices, 12)
            ema_26 = self._calculate_ema(prices, 26)
            features['macd'] = ema_12 - ema_26
        else:
            features['macd'] = 0.0
        
        # Bollinger Bands
        if len(prices) >= 20:
            sma_20 = np.mean(prices[-20:])
            std_20 = np.std(prices[-20:])
            features['bollinger_upper'] = sma_20 + (2 * std_20)
            features['bollinger_lower'] = sma_20 - (2 * std_20)
            
            current_price = prices[-1]
            if features['bollinger_upper'] != features['bollinger_lower']:
                features['bollinger_position'] = (current_price - features['bollinger_lower']) / \
                                               (features['bollinger_upper'] - features['bollinger_lower'])
            else:
                features['bollinger_position'] = 0.5
        else:
            features.update({
                'bollinger_upper': prices[-1], 'bollinger_lower': prices[-1], 'bollinger_position': 0.5
            })
        
        # Exponential Moving Averages
        if len(prices) >= 20:
            features['ema_short'] = self._calculate_ema(prices, 10)
            features['ema_long'] = self._calculate_ema(prices, 20)
        else:
            features['ema_short'] = prices[-1]
            features['ema_long'] = prices[-1]
        
        return features
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return prices[-1]
        
        alpha = 2.0 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return ema
    
    def process_tick(self, mbo_event: Dict) -> Dict[str, float]:
        """
        Process a single MBO event and extract all features.
        
        Args:
            mbo_event: MBO event dictionary
            
        Returns:
            Dictionary of features
        """
        # Update order book
        self.update_orderbook(mbo_event)
        
        # Extract timestamp
        timestamp = mbo_event.get('timestamp', datetime.now())
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp / 1e9)  # Convert nanoseconds
        
        # Extract all feature categories
        features = {}
        features.update(self.get_orderbook_features())
        features.update(self.get_price_features())
        features.update(self.get_volume_features())
        features.update(self.get_time_features(timestamp))
        features.update(self.get_technical_features())
        
        # Optimize data types for memory efficiency
        if self.use_mixed_precision:
            for key, value in features.items():
                if isinstance(value, float):
                    features[key] = np.float32(value)
        
        return features
    
    def create_target_variable(self, future_ticks: List[Dict], horizon: int = 10) -> float:
        """
        Create target variable for prediction.
        
        Args:
            future_ticks: List of future MBO events
            horizon: Number of ticks to look ahead
            
        Returns:
            Target value (e.g., price change, direction)
        """
        if len(future_ticks) < horizon:
            return 0.0
        
        # Use price change as target
        current_price = self.price_history[-1] if self.price_history else 0.0
        future_price = future_ticks[horizon-1]['price']
        
        if current_price > 0:
            return (future_price - current_price) / current_price * 100  # Percentage change
        else:
            return 0.0
    
    def process_mbo_dataframe(self, mbo_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Process entire MBO DataFrame and create features with targets.
        
        Args:
            mbo_df: DataFrame with MBO events
            
        Returns:
            Tuple of (features_df, targets_series)
        """
        logger.info(f"Processing MBO DataFrame with {len(mbo_df)} events")
        
        # Reset state
        self.reset_state()
        
        # Sort by timestamp
        if 'ts_event' in mbo_df.columns:
            mbo_df = mbo_df.sort_values('ts_event').reset_index(drop=True)
        elif 'datetime' in mbo_df.columns:
            mbo_df = mbo_df.sort_values('datetime').reset_index(drop=True)
        
        features_list = []
        targets_list = []
        
        # Process each event
        for i, row in mbo_df.iterrows():
            # Convert row to event dictionary
            event = {
                'price': float(row['price']),
                'size': int(row['size']),
                'side': row['side'],
                'action': row['action'],
                'timestamp': row.get('ts_event', row.get('datetime'))
            }
            
            # Extract features
            features = self.process_tick(event)
            features_list.append(features)
            
            # Create target (look ahead)
            if i + 10 < len(mbo_df):
                future_events = []
                for j in range(i + 1, min(i + 11, len(mbo_df))):
                    future_row = mbo_df.iloc[j]
                    future_event = {
                        'price': float(future_row['price']),
                        'size': int(future_row['size']),
                        'side': future_row['side'],
                        'action': future_row['action']
                    }
                    future_events.append(future_event)
                
                target = self.create_target_variable(future_events, horizon=10)
            else:
                target = 0.0
            
            targets_list.append(target)
            
            # Progress logging
            if i % 10000 == 0:
                logger.info(f"Processed {i}/{len(mbo_df)} events")
        
        # Convert to DataFrame and Series
        features_df = pd.DataFrame(features_list)
        targets_series = pd.Series(targets_list, name='target')
        
        logger.info(f"Feature engineering completed:")
        logger.info(f"  Features shape: {features_df.shape}")
        logger.info(f"  Targets shape: {targets_series.shape}")
        logger.info(f"  Feature columns: {list(features_df.columns)}")
        
        return features_df, targets_series


def create_mbo_features_pipeline(orderbook_depth: int = 10,
                               sequence_length: int = 100,
                               feature_window: int = 50,
                               use_mixed_precision: bool = True) -> MBOFeatureEngineer:
    """
    Create a configured MBO feature engineering pipeline.
    
    Args:
        orderbook_depth: Number of order book levels
        sequence_length: Length of price/volume sequences
        feature_window: Window for rolling calculations
        use_mixed_precision: Use float32 for memory optimization
        
    Returns:
        Configured MBOFeatureEngineer instance
    """
    return MBOFeatureEngineer(
        orderbook_depth=orderbook_depth,
        sequence_length=sequence_length,
        feature_window=feature_window,
        use_mixed_precision=use_mixed_precision
    )
