"""
MBO Data Processor - Tick-by-tick order book assembly and volume tracking

This module processes MBO (Market By Order) data to construct real-time order books,
calculate volume at price levels, and track cumulative delta for training models.

Reference: databento-python-main/examples/historical_timeseries_to_df.py - DataFrame processing
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class OrderBookLevel:
    """Represents a single price level in the order book."""
    price: float
    bid_size: int = 0
    ask_size: int = 0
    bid_orders: Dict[int, int] = None  # order_id -> size
    ask_orders: Dict[int, int] = None  # order_id -> size
    
    def __post_init__(self):
        if self.bid_orders is None:
            self.bid_orders = {}
        if self.ask_orders is None:
            self.ask_orders = {}


@dataclass
class TickSnapshot:
    """Snapshot of market state at a specific tick."""
    timestamp: pd.Timestamp
    price: float
    volume: int
    side: str  # 'B' for buy, 'A' for ask
    order_book: Dict[float, OrderBookLevel]
    cumulative_delta: float
    bid_volume: int
    ask_volume: int
    spread: float
    mid_price: float


class MBOProcessor:
    """
    Processes MBO data to construct order books and calculate market metrics.
    
    Features:
    - Tick-by-tick order book assembly
    - Volume tracking at price levels
    - Cumulative delta calculation
    - Localized order book (±100 points)
    - Level 2 aggregation for distant orders
    """
    
    def __init__(self, max_price_distance: int = 100, level2_threshold: int = 100):
        """
        Initialize MBO processor.
        
        Args:
            max_price_distance: Maximum price points to track in detail
            level2_threshold: Distance beyond which to use Level 2 aggregation
        """
        self.max_price_distance = max_price_distance
        self.level2_threshold = level2_threshold
        
        # Order book state
        self.order_book: Dict[float, OrderBookLevel] = {}
        self.order_id_map: Dict[int, Tuple[float, str]] = {}  # order_id -> (price, side)
        
        # Market metrics
        self.cumulative_delta = 0.0
        self.current_price = None
        self.tick_snapshots: List[TickSnapshot] = []
        
        # Level 2 aggregation
        self.level2_bid_volume = 0
        self.level2_ask_volume = 0
        
        logger.info(f"MBO Processor initialized with max_distance={max_price_distance}, level2_threshold={level2_threshold}")
    
    def process_mbo_data(self, df: pd.DataFrame) -> List[TickSnapshot]:
        """
        Process MBO DataFrame and return tick snapshots.
        
        Reference: databento-python-main/examples/historical_timeseries_to_df.py - DataFrame processing
        """
        logger.info(f"Processing {len(df)} MBO records")
        
        # Sort by timestamp and sequence for proper order
        df = df.sort_values(['ts_event', 'sequence']).reset_index(drop=True)
        
        snapshots = []
        
        for idx, row in df.iterrows():
            if idx % 10000 == 0:
                logger.info(f"Processed {idx}/{len(df)} records")
            
            snapshot = self._process_tick(row)
            if snapshot:
                snapshots.append(snapshot)
        
        logger.info(f"Generated {len(snapshots)} tick snapshots")
        return snapshots
    
    def _process_tick(self, row: pd.Series) -> Optional[TickSnapshot]:
        """Process a single MBO tick and update order book."""
        timestamp = row['ts_event']
        action = row['action']
        side = row['side']
        price = row['price']
        size = row['size']
        order_id = row['order_id']
        
        # Handle different action types according to Databento specification
        if action == 'A':  # Add - Insert new order into book
            self._add_order(price, side, size, order_id)
        elif action == 'M':  # Modify - Change order's price and/or size
            self._modify_order(order_id, price, size)
        elif action == 'C':  # Cancel - Fully or partially cancel order
            self._cancel_order(order_id, size)
        elif action == 'R':  # Clear - Remove all resting orders for instrument
            self._clear_book()
        elif action == 'T':  # Trade - Aggressing order traded (doesn't affect book)
            self._process_trade(price, side, size, order_id)
            # Update cumulative delta for trades
            if side == 'B':
                self.cumulative_delta += size
            elif side == 'A':
                self.cumulative_delta -= size
        elif action == 'F':  # Fill - Resting order was filled (doesn't affect book)
            self._process_fill(order_id, size)
            # Update cumulative delta for fills
            if side == 'B':
                self.cumulative_delta += size
            elif side == 'A':
                self.cumulative_delta -= size
        elif action == 'N':  # None - No action (may carry flags or other information)
            self._process_none_action(row)
        
        # Update current price if we have a valid price
        if pd.notna(price) and price > 0:
            self.current_price = price
        
        # Create snapshot if we have a current price
        if self.current_price is not None:
            return self._create_snapshot(timestamp, price, size, side)
        
        return None
    
    def _add_order(self, price: float, side: str, size: int, order_id: int):
        """Add a new order to the order book."""
        if pd.isna(price) or price <= 0:
            return
        
        # Create price level if it doesn't exist
        if price not in self.order_book:
            self.order_book[price] = OrderBookLevel(price)
        
        level = self.order_book[price]
        
        # Add order to appropriate side
        if side == 'B':
            level.bid_orders[order_id] = size
            level.bid_size += size
        elif side == 'A':
            level.ask_orders[order_id] = size
            level.ask_size += size
        
        # Track order location
        self.order_id_map[order_id] = (price, side)
        
        # Update Level 2 aggregation if order is distant
        if self.current_price is not None:
            distance = abs(price - self.current_price)
            if distance > self.level2_threshold:
                if side == 'B':
                    self.level2_bid_volume += size
                else:
                    self.level2_ask_volume += size
    
    def _clear_book(self):
        """Clear all resting orders for the instrument."""
        self.order_book.clear()
        self.order_id_map.clear()
        self.level2_bid_volume = 0
        self.level2_ask_volume = 0
        logger.info("Order book cleared")
    
    def _process_trade(self, price: float, side: str, size: int, order_id: int):
        """Process a trade event (aggressing order traded)."""
        # Trades don't affect the order book, just track for analysis
        logger.debug(f"Trade processed: {side} {size} @ {price}")
    
    def _process_fill(self, order_id: int, size: int):
        """Process a fill event (resting order was filled)."""
        # Fills don't affect the order book, just track for analysis
        logger.debug(f"Fill processed: order_id={order_id}, size={size}")
    
    def _process_none_action(self, row: pd.Series):
        """Process a None action (may carry flags or other information)."""
        # None actions don't affect the order book
        logger.debug(f"None action processed: {row.to_dict()}")
    
    def _cancel_order(self, order_id: int, size: int):
        """Cancel an order from the order book."""
        if order_id not in self.order_id_map:
            return
        
        price, side = self.order_id_map[order_id]
        if price not in self.order_book:
            return
        
        level = self.order_book[price]
        current_size = level.bid_orders.get(order_id, 0) if side == 'B' else level.ask_orders.get(order_id, 0)
        
        # Calculate new size after cancellation
        new_size = max(0, current_size - size)
        
        # Update or remove order
        if side == 'B':
            if order_id in level.bid_orders:
                del level.bid_orders[order_id]
                level.bid_size -= size
        else:
            if order_id in level.ask_orders:
                del level.ask_orders[order_id]
                level.ask_size -= size
        
        # Remove price level if empty
        if level.bid_size == 0 and level.ask_size == 0:
            del self.order_book[price]
        
        # Remove from tracking
        del self.order_id_map[order_id]
    
    def _modify_order(self, order_id: int, new_price: float, new_size: int):
        """Modify an existing order."""
        if order_id not in self.order_id_map:
            return
        
        old_price, side = self.order_id_map[order_id]
        
        # Remove from old price level
        self._remove_order(order_id)
        
        # Add to new price level
        self._add_order(new_price, side, new_size, order_id)
    
    def _fill_order(self, order_id: int, fill_size: int):
        """Handle order fill/execution."""
        if order_id not in self.order_id_map:
            return
        
        price, side = self.order_id_map[order_id]
        if price not in self.order_book:
            return
        
        level = self.order_book[price]
        
        # Update order size
        if side == 'B':
            if order_id in level.bid_orders:
                current_size = level.bid_orders[order_id]
                new_size = max(0, current_size - fill_size)
                level.bid_orders[order_id] = new_size
                level.bid_size -= (current_size - new_size)
                
                if new_size == 0:
                    del level.bid_orders[order_id]
        else:
            if order_id in level.ask_orders:
                current_size = level.ask_orders[order_id]
                new_size = max(0, current_size - fill_size)
                level.ask_orders[order_id] = new_size
                level.ask_size -= (current_size - new_size)
                
                if new_size == 0:
                    del level.ask_orders[order_id]
        
        # Remove price level if empty
        if level.bid_size == 0 and level.ask_size == 0:
            del self.order_book[price]
    
    def _change_order(self, order_id: int, new_price: float, new_size: int):
        """Change order price and size."""
        self._modify_order(order_id, new_price, new_size)
    
    def _create_snapshot(self, timestamp: pd.Timestamp, price: float, volume: int, side: str) -> TickSnapshot:
        """Create a snapshot of current market state."""
        # Get localized order book (±max_price_distance)
        localized_book = self._get_localized_order_book()
        
        # Calculate market metrics
        bid_volume, ask_volume = self._calculate_volumes(localized_book)
        spread, mid_price = self._calculate_spread_and_mid(localized_book)
        
        return TickSnapshot(
            timestamp=timestamp,
            price=price,
            volume=volume,
            side=side,
            order_book=localized_book,
            cumulative_delta=self.cumulative_delta,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            spread=spread,
            mid_price=mid_price
        )
    
    def _get_localized_order_book(self) -> Dict[float, OrderBookLevel]:
        """Get order book within max_price_distance of current price."""
        if self.current_price is None:
            return {}
        
        localized = {}
        min_price = self.current_price - self.max_price_distance
        max_price = self.current_price + self.max_price_distance
        
        for price, level in self.order_book.items():
            if min_price <= price <= max_price:
                localized[price] = level
        
        return localized
    
    def _calculate_volumes(self, order_book: Dict[float, OrderBookLevel]) -> Tuple[int, int]:
        """Calculate total bid and ask volumes."""
        bid_volume = sum(level.bid_size for level in order_book.values())
        ask_volume = sum(level.ask_size for level in order_book.values())
        
        # Add Level 2 volumes
        bid_volume += self.level2_bid_volume
        ask_volume += self.level2_ask_volume
        
        return bid_volume, ask_volume
    
    def _calculate_spread_and_mid(self, order_book: Dict[float, OrderBookLevel]) -> Tuple[float, float]:
        """Calculate bid-ask spread and mid price."""
        if not order_book:
            return 0.0, self.current_price or 0.0
        
        # Find best bid and ask
        bid_prices = [price for price, level in order_book.items() if level.bid_size > 0]
        ask_prices = [price for price, level in order_book.items() if level.ask_size > 0]
        
        if not bid_prices or not ask_prices:
            return 0.0, self.current_price or 0.0
        
        best_bid = max(bid_prices)
        best_ask = min(ask_prices)
        
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2
        
        return spread, mid_price
    
    def get_training_features(self, snapshots: List[TickSnapshot]) -> pd.DataFrame:
        """Convert snapshots to training features DataFrame."""
        features = []
        
        for i, snapshot in enumerate(snapshots):
            # Basic price features
            feature_dict = {
                'timestamp': snapshot.timestamp,
                'price': snapshot.price,
                'volume': snapshot.volume,
                'side': snapshot.side,
                'cumulative_delta': snapshot.cumulative_delta,
                'bid_volume': snapshot.bid_volume,
                'ask_volume': snapshot.ask_volume,
                'spread': snapshot.spread,
                'mid_price': snapshot.mid_price,
                'volume_imbalance': snapshot.bid_volume - snapshot.ask_volume,
                'total_volume': snapshot.bid_volume + snapshot.ask_volume,
            }
            
            # Order book features (top 10 levels)
            order_book_features = self._extract_order_book_features(snapshot.order_book)
            feature_dict.update(order_book_features)
            
            # Historical features (if available)
            if i > 0:
                prev_snapshot = snapshots[i-1]
                feature_dict.update({
                    'price_change': snapshot.price - prev_snapshot.price,
                    'volume_change': snapshot.volume - prev_snapshot.volume,
                    'delta_change': snapshot.cumulative_delta - prev_snapshot.cumulative_delta,
                    'spread_change': snapshot.spread - prev_snapshot.spread,
                })
            
            features.append(feature_dict)
        
        return pd.DataFrame(features)
    
    def _extract_order_book_features(self, order_book: Dict[float, OrderBookLevel]) -> Dict[str, float]:
        """Extract features from order book structure."""
        features = {}
        
        if not order_book:
            # Fill with zeros if no order book
            for i in range(10):
                features.update({
                    f'bid_price_{i}': 0.0,
                    f'bid_size_{i}': 0.0,
                    f'ask_price_{i}': 0.0,
                    f'ask_size_{i}': 0.0,
                })
            return features
        
        # Sort by price
        sorted_prices = sorted(order_book.keys())
        
        # Extract top 10 bid levels
        bid_levels = [(price, level) for price, level in order_book.items() if level.bid_size > 0]
        bid_levels.sort(key=lambda x: x[0], reverse=True)  # Highest bid first
        
        # Extract top 10 ask levels
        ask_levels = [(price, level) for price, level in order_book.items() if level.ask_size > 0]
        ask_levels.sort(key=lambda x: x[0])  # Lowest ask first
        
        # Fill bid features
        for i in range(10):
            if i < len(bid_levels):
                price, level = bid_levels[i]
                features[f'bid_price_{i}'] = price
                features[f'bid_size_{i}'] = level.bid_size
            else:
                features[f'bid_price_{i}'] = 0.0
                features[f'bid_size_{i}'] = 0.0
        
        # Fill ask features
        for i in range(10):
            if i < len(ask_levels):
                price, level = ask_levels[i]
                features[f'ask_price_{i}'] = price
                features[f'ask_size_{i}'] = level.ask_size
            else:
                features[f'ask_price_{i}'] = 0.0
                features[f'ask_size_{i}'] = 0.0
        
        return features


def process_mbo_for_training(df: pd.DataFrame, max_price_distance: int = 100) -> pd.DataFrame:
    """
    Process MBO data for training with optimized order book assembly.
    
    Args:
        df: MBO DataFrame from Databento
        max_price_distance: Maximum price points to track in detail
    
    Returns:
        DataFrame with training features including order book and cumulative delta
    """
    processor = MBOProcessor(max_price_distance=max_price_distance)
    snapshots = processor.process_mbo_data(df)
    features_df = processor.get_training_features(snapshots)
    
    logger.info(f"Generated {len(features_df)} training samples with {len(features_df.columns)} features")
    return features_df
