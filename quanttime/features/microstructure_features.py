"""
Advanced Microstructure Features for Ultra-High-Frequency Trading

This module implements sophisticated microstructure analysis for tick-level trading,
accounting for latency, data transmission delays, and ultra-short-term patterns.

Key Focus Areas:
1. Ultra-short-term features (microsecond to millisecond scale)
2. Latency and transmission delay analysis
3. Queue position and order book dynamics
4. Liquidity void detection and book flipping
5. Enhanced spoofing and manipulation detection
6. Real-time decision timing optimization

The implementation accounts for the reality that MBO data is flow-based, not time-based,
with varying intensity periods and critical timing considerations for competitive alpha.
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional, Union, Set
from dataclasses import dataclass
from collections import deque, defaultdict
import warnings
from scipy import stats
from scipy.signal import find_peaks
import itertools

logger = logging.getLogger(__name__)

@dataclass
class LatencyMetrics:
    """Latency and timing metrics for real trading considerations"""
    exchange_to_databento_lag: float    # Exchange -> Databento latency
    databento_to_us_lag: float          # Databento -> Our server latency
    processing_lag: float               # Our processing time
    total_decision_lag: float           # Total time from event to decision
    competitive_window: float           # Remaining alpha window after delays
    alpha_decay_rate: float             # How fast alpha decays with time

@dataclass
class BookDynamics:
    """Order book dynamics and liquidity analysis"""
    liquidity_imbalance: float          # Current liquidity imbalance
    void_probability: float             # Probability of liquidity void
    flip_intensity: float               # Rate of bid/ask dominance flipping
    queue_position_advantage: float     # Our position advantage in queue
    reload_intensity: float             # Rate of iceberg reloads
    sweep_probability: float            # Probability of incoming sweep

class MicrostructureAnalyzer:
    """Advanced microstructure analysis for ultra-HF trading"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".MicrostructureAnalyzer")
        
        # Order book state tracking
        self.order_book = {
            'bids': defaultdict(list),  # price -> [(size, order_id, timestamp), ...]
            'asks': defaultdict(list)
        }
        self.order_history = deque(maxlen=10000)  # Recent order events
        self.price_levels = deque(maxlen=1000)    # Recent price level changes
        
        # Queue position tracking
        self.queue_positions = {}  # order_id -> position in queue
        
        # Pattern detection
        self.spoof_candidates = {}  # order_id -> spoof metrics
        self.sweep_patterns = deque(maxlen=100)
        
    def extract_microstructure_features(self, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract comprehensive microstructure features for price prediction
        
        Args:
            mbo_df: Market by order data with columns:
                   - ts_event: Event timestamp (when it happened)
                   - ts_recv: Receive timestamp (when databento got it)  
                   - price, size, side, action, order_id
                   
        Returns:
            Enhanced dataframe with microstructure features for price prediction
        """
        try:
            features = mbo_df.copy()
            
            # 1. ULTRA-SHORT-TERM FEATURES (microsecond to millisecond)
            features = self._add_ultra_short_term_features(features)
            
            # 2. QUEUE POSITION AND BOOK DYNAMICS
            features = self._add_queue_position_features(features)
            
            # 3. LIQUIDITY VOID AND BOOK FLIPPING DETECTION
            features = self._add_liquidity_void_features(features)
            
            # 4. ENHANCED SPOOFING DETECTION
            features = self._add_spoofing_detection_features(features)
            
            # 5. ORDER SWEEP ANALYSIS
            features = self._add_sweep_analysis_features(features)
            
            # 6. TRADE SEQUENCING PATTERNS
            features = self._add_trade_sequencing_features(features)
            
            # 7. FLOW INTENSITY ANALYSIS
            features = self._add_flow_intensity_features(features)
            
            self.logger.info(f"Extracted {len([c for c in features.columns if c.startswith('micro_')])} microstructure features")
            return features
            
        except Exception as e:
            self.logger.error(f"Failed to extract microstructure features: {e}")
            return mbo_df
    

    
    def _add_ultra_short_term_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add ultra-short-term features (microsecond to millisecond scale) for price prediction"""
        try:
            # Ultra-short rolling windows in event counts (since MBO is flow-based, not time-based)
            ultra_windows = [10, 25, 50, 100, 200, 500]  # event windows
            
            for window_events in ultra_windows:
                window_label = f'{window_events}e'  # 'e' for events
                
                # Aggression ratio over ultra-short windows
                df[f'micro_aggression_ratio_{window_label}'] = (
                    (df['action'] == 'F').rolling(window_events).mean()
                )
                
                # Buy/sell imbalance over ultra-short windows
                buy_mask = df['side'] == 'B'
                df[f'micro_buy_ratio_{window_label}'] = buy_mask.rolling(window_events).mean()
                
                # Volume intensity over ultra-short windows
                df[f'micro_volume_intensity_{window_label}'] = (
                    df['size'].rolling(window_events).sum()
                )
                
                # Price volatility over ultra-short windows
                df[f'micro_price_volatility_{window_label}'] = (
                    df['price'].rolling(window_events).std()
                )
                
                # Large order frequency
                large_order_threshold = df['size'].rolling(1000).quantile(0.9)
                df[f'micro_large_order_freq_{window_label}'] = (
                    (df['size'] > large_order_threshold).rolling(window_events).mean()
                )
            
            # Momentum features over ultra-short windows
            df['micro_price_momentum_10e'] = df['price'].rolling(10).apply(
                lambda x: (x.iloc[-1] - x.iloc[0]) / x.iloc[0] if len(x) > 1 and x.iloc[0] != 0 else 0,
                raw=False
            )
            
            # Tick direction momentum
            df['micro_tick_direction'] = np.sign(df['price'].diff())
            df['micro_tick_momentum_50e'] = df['micro_tick_direction'].rolling(50).sum()
            
            # Event rate (events per time unit for flow intensity)
            if 'ts_event' in df.columns:
                df['micro_time_since_last'] = df['ts_event'].diff()
                df['micro_event_rate'] = 1.0 / (df['micro_time_since_last'] / 1_000_000 + 1e-6)  # events per ms
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add ultra-short-term features: {e}")
            return df
    
    def _add_queue_position_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add queue position and order book dynamics features"""
        try:
            # Simulate queue position analysis
            df['micro_queue_position_advantage'] = 0.0
            df['micro_queue_depth_ratio'] = 0.0
            df['micro_ahead_in_queue'] = 0.0
            
            # Process events to track queue positions
            for idx, row in df.iterrows():
                price = row['price']
                side = row['side']
                action = row['action']
                size = row['size']
                order_id = row.get('order_id', f'synthetic_{idx}')
                
                # Update queue position based on action
                if action == 'A':  # Add order
                    queue_key = (price, side)
                    if queue_key not in self.queue_positions:
                        self.queue_positions[queue_key] = []
                    
                    # Add to back of queue
                    self.queue_positions[queue_key].append((order_id, size, idx))
                    
                    # Calculate position advantage (closer to front = higher advantage)
                    queue_length = len(self.queue_positions[queue_key])
                    position = queue_length
                    df.at[idx, 'micro_queue_position_advantage'] = 1.0 / position if position > 0 else 1.0
                    df.at[idx, 'micro_queue_depth_ratio'] = position / max(queue_length, 1)
                    df.at[idx, 'micro_ahead_in_queue'] = queue_length - position
                
                elif action == 'D':  # Delete order
                    # Remove from queue (simplified)
                    for queue_key in list(self.queue_positions.keys()):
                        self.queue_positions[queue_key] = [
                            item for item in self.queue_positions[queue_key] 
                            if item[0] != order_id
                        ]
                
                # Cleanup old entries periodically
                if idx % 1000 == 0:
                    self._cleanup_queue_positions(idx)
            
            # Order book dominance features
            df['micro_book_dominance_flip'] = self._detect_dominance_flips(df)
            df['micro_level_concentration'] = self._calculate_level_concentration(df)
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add queue position features: {e}")
            return df
    
    def _add_liquidity_void_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add liquidity void and book flipping detection"""
        try:
            # Liquidity void detection
            df['micro_liquidity_pulled_volume'] = 0.0
            df['micro_void_creation_speed'] = 0.0
            df['micro_void_probability'] = 0.0
            
            # Book flipping intensity
            df['micro_book_flip_intensity'] = 0.0
            df['micro_level_flip_rate'] = 0.0
            df['micro_dominance_reversal'] = 0.0
            
            # Track liquidity changes over time
            liquidity_tracker = {}
            
            for idx, row in df.iterrows():
                price = row['price']
                side = row['side']
                action = row['action']
                size = row['size']
                
                level_key = (price, side)
                
                # Track liquidity changes
                if action == 'D':  # Order cancellation
                    if level_key in liquidity_tracker:
                        # Calculate void creation
                        prev_liquidity = liquidity_tracker.get(level_key, 0)
                        liquidity_pulled = min(size, prev_liquidity)
                        df.at[idx, 'micro_liquidity_pulled_volume'] = liquidity_pulled
                        
                        # Update liquidity tracker
                        liquidity_tracker[level_key] = max(0, prev_liquidity - size)
                        
                        # Void creation speed (amount pulled per time unit)
                        time_diff = df.at[idx, 'ts_event'] - df.at[max(0, idx-1), 'ts_event']
                        if time_diff > 0:
                            df.at[idx, 'micro_void_creation_speed'] = liquidity_pulled / time_diff
                
                elif action == 'A':  # Order addition
                    liquidity_tracker[level_key] = liquidity_tracker.get(level_key, 0) + size
                
                # Calculate void probability based on recent cancellations
                if idx >= 100:
                    recent_cancellations = df.iloc[idx-100:idx]['action'].eq('D').sum()
                    recent_additions = df.iloc[idx-100:idx]['action'].eq('A').sum()
                    void_ratio = recent_cancellations / max(recent_additions, 1)
                    df.at[idx, 'micro_void_probability'] = min(1.0, void_ratio)
            
            # Book flipping analysis
            df['micro_book_flip_intensity'] = self._analyze_book_flipping(df)
            
            # Liquidity imbalance momentum
            df['micro_liquidity_momentum'] = df['micro_liquidity_pulled_volume'].rolling(100).sum()
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add liquidity void features: {e}")
            return df
    
    def _add_spoofing_detection_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add enhanced spoofing and manipulation detection"""
        try:
            # Initialize spoofing detection features
            df['micro_spoof_probability'] = 0.0
            df['micro_fake_liquidity_ratio'] = 0.0
            df['micro_manipulation_score'] = 0.0
            df['micro_order_lifecycle_suspicion'] = 0.0
            
            # Track order lifecycles for spoofing detection
            order_lifecycles = {}
            
            for idx, row in df.iterrows():
                order_id = row.get('order_id', f'synthetic_{idx}')
                action = row['action']
                size = row['size']
                price = row['price']
                side = row['side']
                timestamp = row['ts_event']
                
                # Track order lifecycle
                if action == 'A':  # Order placement
                    order_lifecycles[order_id] = {
                        'placed_time': timestamp,
                        'placed_price': price,
                        'placed_size': size,
                        'side': side,
                        'modifications': 0,
                        'filled_amount': 0,
                        'cancelled': False
                    }
                
                elif action == 'M' and order_id in order_lifecycles:  # Modification
                    order_lifecycles[order_id]['modifications'] += 1
                
                elif action == 'F' and order_id in order_lifecycles:  # Fill
                    order_lifecycles[order_id]['filled_amount'] += size
                
                elif action == 'D' and order_id in order_lifecycles:  # Cancellation
                    order_lifecycles[order_id]['cancelled'] = True
                    
                    # Analyze for spoofing patterns
                    order_info = order_lifecycles[order_id]
                    
                    # Spoof indicators:
                    # 1. Large order cancelled quickly without fills
                    # 2. Multiple modifications before cancellation
                    # 3. Cancelled when price moves toward the order
                    
                    time_alive = timestamp - order_info['placed_time']
                    fill_ratio = order_info['filled_amount'] / order_info['placed_size']
                    
                    spoof_score = 0.0
                    
                    # Large order, quick cancellation, no fills
                    if (order_info['placed_size'] > df['size'].rolling(1000).quantile(0.9).iloc[idx] and
                        time_alive < 1_000_000 and  # Less than 1ms alive
                        fill_ratio < 0.1):  # Less than 10% filled
                        spoof_score += 0.4
                    
                    # Multiple modifications
                    if order_info['modifications'] > 2:
                        spoof_score += 0.3
                    
                    # High modification rate
                    if time_alive > 0:
                        mod_rate = order_info['modifications'] / time_alive
                        if mod_rate > 0.001:  # More than 1 mod per ms
                            spoof_score += 0.3
                    
                    df.at[idx, 'micro_spoof_probability'] = min(1.0, spoof_score)
                    df.at[idx, 'micro_order_lifecycle_suspicion'] = spoof_score
                
                # Calculate fake liquidity ratio
                if idx >= 100:
                    recent_orders = df.iloc[idx-100:idx]
                    total_size = recent_orders['size'].sum()
                    cancelled_size = recent_orders[recent_orders['action'] == 'D']['size'].sum()
                    df.at[idx, 'micro_fake_liquidity_ratio'] = cancelled_size / max(total_size, 1)
            
            # Cleanup old order lifecycles periodically
            if len(order_lifecycles) > 5000:
                # Keep only recent orders
                recent_threshold = df['ts_event'].iloc[-1] - 10_000_000  # 10ms ago
                order_lifecycles = {
                    oid: info for oid, info in order_lifecycles.items()
                    if info['placed_time'] > recent_threshold
                }
            
            # Manipulation score (composite)
            df['micro_manipulation_score'] = (
                0.4 * df['micro_spoof_probability'] +
                0.3 * df['micro_fake_liquidity_ratio'] +
                0.3 * df['micro_order_lifecycle_suspicion']
            )
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add spoofing detection features: {e}")
            return df
    
    def _add_sweep_analysis_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add order sweep analysis and multi-level consumption detection"""
        try:
            # Initialize sweep detection features
            df['micro_sweep_probability'] = 0.0
            df['micro_sweep_depth_levels'] = 0.0
            df['micro_sweep_intensity'] = 0.0
            df['micro_multi_level_consumption'] = 0.0
            
            # Track order book depth for sweep detection
            book_levels = {'bids': {}, 'asks': {}}
            
            for idx, row in df.iterrows():
                price = row['price']
                side = row['side']
                action = row['action']
                size = row['size']
                
                # Update book levels
                if action == 'A':
                    book_side = 'bids' if side == 'B' else 'asks'
                    book_levels[book_side][price] = book_levels[book_side].get(price, 0) + size
                
                elif action == 'D':
                    book_side = 'bids' if side == 'B' else 'asks'
                    if price in book_levels[book_side]:
                        book_levels[book_side][price] = max(0, book_levels[book_side][price] - size)
                        if book_levels[book_side][price] == 0:
                            del book_levels[book_side][price]
                
                elif action == 'F':  # Fill - potential sweep
                    # Analyze if this is part of a sweep
                    opposite_side = 'asks' if side == 'B' else 'bids'
                    
                    # Check how many levels this order might be consuming
                    levels_consumed = 0
                    remaining_size = size
                    
                    if opposite_side in book_levels:
                        sorted_prices = sorted(book_levels[opposite_side].keys())
                        if side == 'B':  # Buying, consuming asks (ascending prices)
                            relevant_prices = [p for p in sorted_prices if p <= price]
                        else:  # Selling, consuming bids (descending prices)
                            relevant_prices = [p for p in sorted(sorted_prices, reverse=True) if p >= price]
                        
                        for level_price in relevant_prices:
                            if remaining_size <= 0:
                                break
                            
                            level_size = book_levels[opposite_side].get(level_price, 0)
                            if level_size > 0:
                                levels_consumed += 1
                                consumed = min(remaining_size, level_size)
                                remaining_size -= consumed
                                
                                # Update book
                                book_levels[opposite_side][level_price] -= consumed
                                if book_levels[opposite_side][level_price] <= 0:
                                    del book_levels[opposite_side][level_price]
                    
                    df.at[idx, 'micro_sweep_depth_levels'] = levels_consumed
                    
                    # Sweep probability based on levels consumed and size
                    if levels_consumed > 1:
                        df.at[idx, 'micro_sweep_probability'] = min(1.0, levels_consumed / 5.0)
                        df.at[idx, 'micro_multi_level_consumption'] = 1.0
                    
                    # Sweep intensity (size × levels)
                    df.at[idx, 'micro_sweep_intensity'] = size * levels_consumed
            
            # Rolling sweep metrics
            df['micro_recent_sweep_count'] = (df['micro_sweep_probability'] > 0.5).rolling(100).sum()
            df['micro_sweep_volume_rate'] = df['micro_sweep_intensity'].rolling(100).mean()
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add sweep analysis features: {e}")
            return df
    
    def _add_trade_sequencing_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add trade-to-trade sequencing and momentum patterns"""
        try:
            # Initialize sequencing features
            df['micro_sequence_momentum'] = 0.0
            df['micro_aggressive_sequence_length'] = 0.0
            df['micro_size_escalation'] = 0.0
            df['micro_sequence_urgency'] = 0.0
            
            # Track consecutive patterns
            sequence_tracker = {
                'current_side': None,
                'sequence_length': 0,
                'sequence_sizes': [],
                'sequence_times': [],
                'last_direction': None
            }
            
            for idx, row in df.iterrows():
                side = row['side']
                action = row['action']
                size = row['size']
                timestamp = row['ts_event']
                
                if action == 'F':  # Only analyze fills for trade sequences
                    # Check if continuing same-side sequence
                    if side == sequence_tracker['current_side']:
                        sequence_tracker['sequence_length'] += 1
                        sequence_tracker['sequence_sizes'].append(size)
                        sequence_tracker['sequence_times'].append(timestamp)
                    else:
                        # New sequence starting
                        sequence_tracker['current_side'] = side
                        sequence_tracker['sequence_length'] = 1
                        sequence_tracker['sequence_sizes'] = [size]
                        sequence_tracker['sequence_times'] = [timestamp]
                    
                    # Calculate sequence momentum
                    seq_len = sequence_tracker['sequence_length']
                    df.at[idx, 'micro_aggressive_sequence_length'] = seq_len
                    
                    # Momentum score (longer sequences = higher momentum)
                    momentum_score = min(1.0, seq_len / 10.0)  # Cap at 10 consecutive
                    df.at[idx, 'micro_sequence_momentum'] = momentum_score
                    
                    # Size escalation analysis
                    if len(sequence_tracker['sequence_sizes']) >= 2:
                        sizes = sequence_tracker['sequence_sizes']
                        
                        # Check for increasing sizes
                        increasing_count = sum(1 for i in range(1, len(sizes)) if sizes[i] > sizes[i-1])
                        escalation_ratio = increasing_count / (len(sizes) - 1)
                        df.at[idx, 'micro_size_escalation'] = escalation_ratio
                        
                        # Sequence urgency (based on time compression)
                        if len(sequence_tracker['sequence_times']) >= 2:
                            times = sequence_tracker['sequence_times']
                            intervals = [times[i] - times[i-1] for i in range(1, len(times))]
                            avg_interval = np.mean(intervals)
                            
                            # Urgency = inverse of average interval (faster = more urgent)
                            urgency = 1.0 / (avg_interval / 1_000_000 + 1)  # Normalize to ms
                            df.at[idx, 'micro_sequence_urgency'] = min(1.0, urgency)
                    
                    # Keep sequence history reasonable
                    if len(sequence_tracker['sequence_sizes']) > 20:
                        sequence_tracker['sequence_sizes'] = sequence_tracker['sequence_sizes'][-10:]
                        sequence_tracker['sequence_times'] = sequence_tracker['sequence_times'][-10:]
            
            # Pattern recognition features
            df['micro_momentum_acceleration'] = df['micro_sequence_momentum'].diff()
            df['micro_urgency_trend'] = df['micro_sequence_urgency'].rolling(10).apply(
                lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) > 5 else 0, raw=False
            )
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add trade sequencing features: {e}")
            return df
    
    def _add_flow_intensity_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add flow intensity analysis accounting for variable data density"""
        try:
            # Flow intensity over multiple timescales
            df['micro_flow_intensity_100us'] = 0.0
            df['micro_flow_intensity_1ms'] = 0.0
            df['micro_flow_intensity_10ms'] = 0.0
            df['micro_flow_burst_ratio'] = 0.0
            df['micro_flow_density_change'] = 0.0
            
            # Calculate flow intensity using event counting
            for idx in range(len(df)):
                current_time = df.at[idx, 'ts_event']
                
                # Count events in different time windows
                for window_us, window_ns in [(100, 100_000), (1000, 1_000_000), (10000, 10_000_000)]:
                    start_time = current_time - window_ns
                    
                    # Count events in window
                    event_count = 0
                    for j in range(max(0, idx-1000), idx+1):  # Look back reasonable amount
                        if j < len(df) and df.at[j, 'ts_event'] >= start_time:
                            event_count += 1
                        elif j < len(df) and df.at[j, 'ts_event'] < start_time:
                            break
                    
                    # Intensity = events per microsecond
                    intensity = event_count / window_us
                    df.at[idx, f'micro_flow_intensity_{window_us}us'] = intensity
            
            # Flow burst detection
            for idx in range(100, len(df)):
                recent_intensity = df.at[idx, 'micro_flow_intensity_1ms']
                avg_intensity = df.iloc[idx-100:idx]['micro_flow_intensity_1ms'].mean()
                
                if avg_intensity > 0:
                    burst_ratio = recent_intensity / avg_intensity
                    df.at[idx, 'micro_flow_burst_ratio'] = min(10.0, burst_ratio)  # Cap extreme values
            
            # Flow density change rate
            df['micro_flow_density_change'] = df['micro_flow_intensity_1ms'].diff()
            
            # Adaptive features based on flow intensity
            df['micro_adaptive_window'] = 1.0 / (df['micro_flow_intensity_1ms'] + 0.001)  # Longer windows for low intensity
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add flow intensity features: {e}")
            return df
    

    
    # Helper methods
    def _cleanup_queue_positions(self, current_idx: int):
        """Clean up old queue position data"""
        cutoff_idx = current_idx - 5000
        for queue_key in list(self.queue_positions.keys()):
            self.queue_positions[queue_key] = [
                item for item in self.queue_positions[queue_key]
                if item[2] > cutoff_idx  # Keep only recent entries
            ]
            if not self.queue_positions[queue_key]:
                del self.queue_positions[queue_key]
    
    def _detect_dominance_flips(self, df: pd.DataFrame) -> pd.Series:
        """Detect order book dominance flips"""
        try:
            flips = pd.Series(0.0, index=df.index)
            
            # Simple implementation - can be enhanced
            buy_volume = df[df['side'] == 'B']['size'].rolling(100).sum()
            sell_volume = df[df['side'] == 'S']['size'].rolling(100).sum()
            
            dominance = (buy_volume - sell_volume) / (buy_volume + sell_volume + 1e-8)
            flip_intensity = abs(dominance.diff())
            
            return flip_intensity.fillna(0.0)
        except:
            return pd.Series(0.0, index=df.index)
    
    def _calculate_level_concentration(self, df: pd.DataFrame) -> pd.Series:
        """Calculate price level concentration"""
        try:
            concentration = pd.Series(0.5, index=df.index)
            
            # Simple implementation based on price diversity
            for i in range(100, len(df)):
                recent_prices = df.iloc[i-100:i]['price'].nunique()
                total_events = 100
                concentration.iloc[i] = recent_prices / total_events
            
            return concentration
        except:
            return pd.Series(0.5, index=df.index)
    
    def _analyze_book_flipping(self, df: pd.DataFrame) -> pd.Series:
        """Analyze order book flipping patterns"""
        try:
            flipping = pd.Series(0.0, index=df.index)
            
            # Track bid/ask dominance changes
            for i in range(100, len(df)):
                recent_data = df.iloc[i-100:i]
                
                # Calculate dominance changes
                buy_events = (recent_data['side'] == 'B').sum()
                sell_events = (recent_data['side'] == 'S').sum()
                
                # Flip intensity based on dominance changes
                total_events = buy_events + sell_events
                if total_events > 0:
                    dominance_ratio = abs(buy_events - sell_events) / total_events
                    flipping.iloc[i] = 1.0 - dominance_ratio  # Higher when more balanced/flipping
            
            return flipping
        except:
            return pd.Series(0.0, index=df.index)

def add_microstructure_features(mbo_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add comprehensive microstructure features to MBO dataframe for price prediction
    
    Args:
        mbo_df: Market by order dataframe
        
    Returns:
        Enhanced dataframe with microstructure features for price prediction
    """
    try:
        analyzer = MicrostructureAnalyzer()
        
        enhanced_df = analyzer.extract_microstructure_features(mbo_df)
        
        micro_features = [c for c in enhanced_df.columns if c.startswith('micro_')]
        logger.info(f"Added {len(micro_features)} microstructure features for price prediction")
        
        return enhanced_df
        
    except Exception as e:
        logger.error(f"Failed to add microstructure features: {e}")
        return mbo_df

if __name__ == "__main__":
    # Example usage
    sample_data = pd.DataFrame({
        'ts_event': pd.date_range('2024-01-01', periods=1000, freq='100us'),
        'ts_recv': pd.date_range('2024-01-01', periods=1000, freq='100us') + pd.Timedelta(microseconds=500),
        'price': 5000 + np.random.randn(1000) * 0.25,
        'size': np.random.randint(1, 100, 1000),
        'side': np.random.choice(['B', 'S'], 1000),
        'action': np.random.choice(['A', 'M', 'D', 'F'], 1000, p=[0.4, 0.1, 0.2, 0.3]),
        'order_id': [f'order_{i}' for i in range(1000)]
    })
    
    # Add microstructure features
    enhanced_data = add_microstructure_features(sample_data)
    
    print(f"Added microstructure features:")
    micro_cols = [c for c in enhanced_data.columns if c.startswith('micro_')]
    print(f"Total features: {len(micro_cols)}")
    for col in sorted(micro_cols)[:10]:  # Show first 10
        print(f"  - {col}")
