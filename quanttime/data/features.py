"""
Feature Engineering System for QuantTime MBO L3 Pipeline.

This module implements O(1) feature calculators for MBO L3 data,
including core L3 features, advanced features, and multi-scale features.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
import logging
from collections import deque, defaultdict
import warnings
from datetime import datetime, timedelta
import time

from .schema import FeatureSet, ActionType, SideType
from .normalization import NormalizationEngine, NormalizationType

logger = logging.getLogger(__name__)


@dataclass
class OrderBookState:
    """Maintains current order book state."""
    bids: Dict[float, int] = field(default_factory=dict)  # price -> total_size
    asks: Dict[float, int] = field(default_factory=dict)  # price -> total_size
    order_positions: Dict[int, Tuple[float, int]] = field(default_factory=dict)  # order_id -> (price, size)
    
    def update_order(self, order_id: int, price: float, size: int, side: SideType):
        """Update order in the book."""
        if side == SideType.BID:
            if size > 0:
                self.bids[price] = self.bids.get(price, 0) + size
                self.order_positions[order_id] = (price, size)
            else:
                # Remove order
                if order_id in self.order_positions:
                    old_price, old_size = self.order_positions[order_id]
                    self.bids[old_price] = max(0, self.bids.get(old_price, 0) - old_size)
                    if self.bids[old_price] == 0:
                        del self.bids[old_price]
                    del self.order_positions[order_id]
        else:  # ASK
            if size > 0:
                self.asks[price] = self.asks.get(price, 0) + size
                self.order_positions[order_id] = (price, size)
            else:
                # Remove order
                if order_id in self.order_positions:
                    old_price, old_size = self.order_positions[order_id]
                    self.asks[old_price] = max(0, self.asks.get(old_price, 0) - old_size)
                    if self.asks[old_price] == 0:
                        del self.asks[old_price]
                    del self.order_positions[order_id]
    
    def get_best_bid(self) -> Optional[float]:
        """Get best bid price."""
        return max(self.bids.keys()) if self.bids else None
    
    def get_best_ask(self) -> Optional[float]:
        """Get best ask price."""
        return min(self.asks.keys()) if self.asks else None
    
    def get_midprice(self) -> Optional[float]:
        """Get current midprice."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return (best_bid + best_ask) / 2
        return None
    
    def get_spread_ticks(self, tick_size: float = 0.25) -> int:
        """Get spread in ticks."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return int((best_ask - best_bid) / tick_size)
        return 0
    
    def get_depth(self, side: SideType, levels: int = 10) -> List[Tuple[float, int]]:
        """Get depth for a side."""
        if side == SideType.BID:
            sorted_prices = sorted(self.bids.keys(), reverse=True)[:levels]
            return [(price, self.bids[price]) for price in sorted_prices]
        else:
            sorted_prices = sorted(self.asks.keys())[:levels]
            return [(price, self.asks[price]) for price in sorted_prices]


@dataclass
class AbsorptionEvent:
    """Represents an absorption event."""
    timestamp: int
    price: float
    executed_volume: float
    posted_volume: float
    absorption_ratio: float

@dataclass
class ExhaustionEvent:
    """Represents a liquidity exhaustion event."""
    timestamp: int
    price: float
    depleted_volume: float
    refill_time: Optional[int] = None

@dataclass
class LargeOrderEvent:
    """Represents a large order event for institutional flow detection."""
    timestamp: int
    order_id: int
    price: float
    size: int
    side: str
    action: str
    is_fragmented: bool = False
    fragment_count: int = 1
    total_fragmented_size: int = 0
    time_to_complete: Optional[int] = None

@dataclass
class IcebergEvent:
    """Represents an iceberg order detection event."""
    timestamp: int
    price: float
    side: str
    visible_size: int
    estimated_hidden_size: int
    replenishment_count: int = 0
    confidence_score: float = 0.0

@dataclass
class SpoofingEvent:
    """Represents a spoofing detection event."""
    timestamp: int
    order_id: int
    price: float
    size: int
    side: str
    time_to_cancel: int
    spoofing_score: float
    spoofing_type: str  # 'layering', 'spoofing', 'quote_stuffing'

@dataclass
class InstitutionalFlowEvent:
    """Represents institutional flow detection event."""
    timestamp: int
    flow_type: str  # 'buy_pressure', 'sell_pressure', 'neutral'
    strength: float
    duration: int
    volume_impact: float
    price_impact: float
    confidence: float

@dataclass
class MarketRegimeEvent:
    """Represents market regime detection event."""
    timestamp: int
    regime_type: str  # 'trending', 'mean_reverting', 'volatile', 'quiet'
    volatility_level: float
    liquidity_level: float
    transition_probability: float

@dataclass
class LiquidityStressEvent:
    """Represents liquidity stress detection event."""
    timestamp: int
    stress_level: float
    spread_widening: float
    depth_reduction: float
    recovery_time: Optional[int] = None

@dataclass
class OrderFlowAnomalyEvent:
    """Represents order flow anomaly detection."""
    timestamp: int
    anomaly_type: str  # 'volume_spike', 'price_jump', 'spread_widening', 'depth_collapse'
    severity: float
    duration: int
    impact_score: float

@dataclass
class HorizonState:
    """State for a specific time horizon."""
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    total_volume: float = 0.0
    delta: float = 0.0
    cumulative_delta: float = 0.0
    absorption_events: int = 0
    exhaustion_events: int = 0
    price_change: float = 0.0
    volatility: float = 0.0
    average_spread: float = 0.0
    depth_at_touch: float = 0.0
    
    # Advanced event counters
    large_order_events: int = 0
    iceberg_events: int = 0
    spoofing_events: int = 0
    institutional_flow_events: int = 0
    market_regime_events: int = 0
    liquidity_stress_events: int = 0
    order_flow_anomalies: int = 0

@dataclass
class ExecutionState:
    """Execution-aware state tracking."""
    # Session totals
    session_buy_volume: float = 0.0
    session_sell_volume: float = 0.0
    session_delta: float = 0.0
    
    # Current window
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    aggressive_buy_volume: float = 0.0
    aggressive_sell_volume: float = 0.0
    passive_buy_volume: float = 0.0
    passive_sell_volume: float = 0.0
    
    # Absorption tracking
    absorption_events: List[AbsorptionEvent] = field(default_factory=list)
    exhaustion_events: List[ExhaustionEvent] = field(default_factory=list)
    
    # Advanced event tracking
    large_order_events: List[LargeOrderEvent] = field(default_factory=list)
    iceberg_events: List[IcebergEvent] = field(default_factory=list)
    spoofing_events: List[SpoofingEvent] = field(default_factory=list)
    institutional_flow_events: List[InstitutionalFlowEvent] = field(default_factory=list)
    market_regime_events: List[MarketRegimeEvent] = field(default_factory=list)
    liquidity_stress_events: List[LiquidityStressEvent] = field(default_factory=list)
    order_flow_anomalies: List[OrderFlowAnomalyEvent] = field(default_factory=list)
    
    # Order tracking for fragmentation detection
    active_orders: Dict[int, Dict] = field(default_factory=dict)  # order_id -> order_info
    order_fragments: Dict[int, List[Dict]] = field(default_factory=dict)  # order_id -> fragments
    
    # Last execution info
    last_execution_price: float = 0.0
    last_execution_volume: float = 0.0
    last_execution_time: int = 0
    
    # Market microstructure tracking
    recent_prices: deque = field(default_factory=lambda: deque(maxlen=1000))
    recent_volumes: deque = field(default_factory=lambda: deque(maxlen=1000))
    recent_spreads: deque = field(default_factory=lambda: deque(maxlen=1000))
    recent_depths: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    # Iceberg detection state
    iceberg_candidates: Dict[float, Dict] = field(default_factory=dict)  # price -> iceberg_info
    
    # Spoofing detection state
    recent_orders: deque = field(default_factory=lambda: deque(maxlen=10000))
    order_lifecycle: Dict[int, Dict] = field(default_factory=dict)  # order_id -> lifecycle
    
    # Institutional flow state
    flow_buffers: Dict[str, deque] = field(default_factory=lambda: {
        'volume': deque(maxlen=1000),
        'delta': deque(maxlen=1000),
        'price_change': deque(maxlen=1000),
        'spread': deque(maxlen=1000)
    })
    
    # Market regime state
    volatility_buffer: deque = field(default_factory=lambda: deque(maxlen=1000))
    liquidity_buffer: deque = field(default_factory=lambda: deque(maxlen=1000))
    trend_buffer: deque = field(default_factory=lambda: deque(maxlen=1000))


@dataclass
class MultiHorizonBuffer:
    """Ring buffers for different time horizons."""
    def __init__(self):
        # Define horizons in milliseconds and their buffer sizes
        # Added more horizons as requested: 50ms, 500ms, 3s, 30s, 2m, 10m, 30m
        self.horizon_configs = {
            '10ms': {'interval_ms': 10, 'maxlen': 6000},      # 1 minute
            '50ms': {'interval_ms': 50, 'maxlen': 36000},     # 30 minutes
            '100ms': {'interval_ms': 100, 'maxlen': 18000},   # 30 minutes
            '500ms': {'interval_ms': 500, 'maxlen': 14400},   # 2 hours
            '1s': {'interval_ms': 1000, 'maxlen': 7200},      # 2 hours
            '3s': {'interval_ms': 3000, 'maxlen': 2400},      # 2 hours
            '10s': {'interval_ms': 10000, 'maxlen': 2160},    # 6 hours
            '30s': {'interval_ms': 30000, 'maxlen': 720},     # 6 hours
            '1m': {'interval_ms': 60000, 'maxlen': 1440},     # 24 hours
            '2m': {'interval_ms': 120000, 'maxlen': 720},     # 24 hours
            '5m': {'interval_ms': 300000, 'maxlen': 576},     # 48 hours
            '10m': {'interval_ms': 600000, 'maxlen': 288},    # 48 hours
            '20m': {'interval_ms': 1200000, 'maxlen': 216},   # 72 hours
            '30m': {'interval_ms': 1800000, 'maxlen': 144},   # 72 hours
            '1h': {'interval_ms': 3600000, 'maxlen': 168},    # 1 week
        }
        
        # Initialize buffers
        self.buffers: Dict[str, deque] = {}
        self.states: Dict[str, HorizonState] = {}
        
        for horizon, config in self.horizon_configs.items():
            self.buffers[horizon] = deque(maxlen=config['maxlen'])
            self.states[horizon] = HorizonState()
    
    def update_horizon(self, horizon: str, timestamp: int, **kwargs):
        """Update a specific horizon with new data."""
        if horizon in self.buffers:
            # Create horizon data point
            data_point = {
                'timestamp': timestamp,
                **kwargs
            }
            self.buffers[horizon].append(data_point)
            
            # Update state
            state = self.states[horizon]
            for key, value in kwargs.items():
                if hasattr(state, key):
                    if key in ['buy_volume', 'sell_volume', 'total_volume']:
                        # Accumulate volumes
                        setattr(state, key, getattr(state, key) + value)
                    elif key in ['absorption_events', 'exhaustion_events', 'large_order_events', 'iceberg_events', 'spoofing_events', 'institutional_flow_events', 'market_regime_events', 'liquidity_stress_events', 'order_flow_anomalies']:
                        # Count events
                        setattr(state, key, getattr(state, key) + value)
                    else:
                        # Update other values
                        setattr(state, key, value)

@dataclass
class FeatureState:
    """Maintains feature computation state."""
    order_book: OrderBookState = field(default_factory=OrderBookState)
    normalization_engine: Optional[NormalizationEngine] = None
    
    # Execution state
    execution_state: ExecutionState = field(default_factory=ExecutionState)
    
    # Multi-horizon buffers
    multi_horizon: MultiHorizonBuffer = field(default_factory=MultiHorizonBuffer)
    
    # Event counters
    event_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Rolling windows (legacy - keeping for compatibility)
    price_changes: deque = field(default_factory=lambda: deque(maxlen=100))
    volume_imbalances: deque = field(default_factory=lambda: deque(maxlen=100))
    time_deltas: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # Multi-scale features (legacy - keeping for compatibility)
    ofi_fast: float = 0.0
    ofi_medium: float = 0.0
    ofi_slow: float = 0.0
    
    # Volatility estimates
    volatility_estimate: float = 0.0
    
    # Cancel/modify ratios
    cancel_count: int = 0
    modify_count: int = 0
    add_count: int = 0
    
    # Fair value tracking
    vwap_mid: float = 0.0
    execution_weighted_mid: float = 0.0
    
    # Session tracking
    session_start_time: int = 0
    session_start_price: float = 0.0


class FeatureEngine:
    """
    Feature engineering engine for MBO L3 data.
    
    Implements O(1) feature calculators for real-time processing.
    """
    
    def __init__(self, 
                 feature_set: FeatureSet = FeatureSet.BASIC,
                 normalization_type: NormalizationType = NormalizationType.TICK_RELATIVE,
                 tick_size: float = 0.25,
                 depth_levels: int = 10):
        """
        Initialize feature engine.
        
        Args:
            feature_set: Set of features to compute
            normalization_type: Type of normalization to apply
            tick_size: Tick size for price calculations
            depth_levels: Number of depth levels to maintain
        """
        self.feature_set = feature_set
        self.tick_size = tick_size
        self.depth_levels = depth_levels
        
        # Initialize normalization engine
        self.normalization_engine = NormalizationEngine(normalization_type, tick_size)
        
        # Initialize feature state
        self.state = FeatureState()
        self.state.normalization_engine = self.normalization_engine
        
        logger.info(f"Initialized feature engine: {feature_set.value}")
    
    def reset_session(self, session_open_time: int, initial_midprice: float):
        """Reset feature state for new trading session."""
        self.state = FeatureState()
        self.state.normalization_engine = self.normalization_engine
        self.normalization_engine.reset_session(session_open_time, initial_midprice)
        logger.info(f"Reset feature state for session: midprice={initial_midprice}")
    
    def process_event(self, 
                     ts_event: int,
                     ts_recv: int,
                     action: str,
                     side: str,
                     order_id: int,
                     price: float,
                     size: int,
                     flags: int,
                     sequence: int,
                     instrument: str) -> Dict[str, Any]:
        """
        Process a single MBO event and compute features.
        
        Args:
            MBO event fields
            
        Returns:
            Dictionary of computed features
        """
        # Convert string enums using Databento-aware conversion
        try:
            action_enum = ActionType.from_databento(action)
            side_enum = SideType.from_databento(side)
        except Exception as e:
            logger.warning(f"Error converting action/side: action={action}, side={side}, error={e}")
            # Default to safe values
            action_enum = ActionType.NONE
            side_enum = SideType.NONE
        
        # Update order book
        if action_enum == ActionType.ADD:
            self.state.order_book.update_order(order_id, price, size, side_enum)
            self.state.add_count += 1
        elif action_enum == ActionType.MODIFY:
            self.state.order_book.update_order(order_id, price, size, side_enum)
            self.state.modify_count += 1
        elif action_enum == ActionType.CANCEL:
            self.state.order_book.update_order(order_id, price, 0, side_enum)
            self.state.cancel_count += 1
        elif action_enum == ActionType.CLEAR:
            # Clear all orders for this instrument (simplified - just count)
            self.state.cancel_count += 1
        elif action_enum == ActionType.FILL:
            # Handle execution events specially for footprint analysis
            self._process_execution_event(ts_event, side_enum, price, size, order_id, action_enum)
            self.state.order_book.update_order(order_id, price, size, side_enum)
        elif action_enum == ActionType.TRADE:
            # Trade executed (aggressor) - handle for footprint analysis
            self._process_execution_event(ts_event, side_enum, price, size, order_id, action_enum)
        elif action_enum == ActionType.NONE:
            # No action - just count
            pass
        
        # Update event counters
        self.state.event_counts[action] += 1
        
        # Get current midprice
        midprice = self.state.order_book.get_midprice()
        if midprice is None:
            midprice = price  # Fallback to event price
        
        # Update normalization engine
        self.normalization_engine.update_midprice(midprice, ts_event)
        
        # Compute features
        features = self._compute_features(ts_event, action_enum, side_enum, 
                                        order_id, price, size, midprice)
        
        return features
    
    def _compute_features(self, 
                         ts_event: int,
                         action: ActionType,
                         side: SideType,
                         order_id: int,
                         price: float,
                         size: int,
                         midprice: float) -> Dict[str, Any]:
        """Compute features for the current event."""
        features = {
            'ts_event': ts_event,
            'action': action.value,
            'side': side.value,
            'order_id': order_id,
            'price': price,
            'size': size,
            'midprice': midprice
        }
        
        # Basic features
        if self.feature_set in [FeatureSet.BASIC, FeatureSet.ADVANCED, FeatureSet.MULTI_SCALE, FeatureSet.COMPREHENSIVE]:
            features.update(self._compute_basic_features(price, size, midprice, order_id, side, ts_event))
        
        # Execution-aware features
        if self.feature_set in [FeatureSet.BASIC, FeatureSet.ADVANCED, FeatureSet.MULTI_SCALE, FeatureSet.COMPREHENSIVE]:
            features.update(self._compute_execution_features(ts_event))
            features.update(self._compute_fair_value_features(midprice))
        
        # Advanced features
        if self.feature_set in [FeatureSet.ADVANCED, FeatureSet.MULTI_SCALE, FeatureSet.COMPREHENSIVE]:
            features.update(self._compute_advanced_features(ts_event, action, side, price, size))
        
        # Multi-scale features (legacy)
        if self.feature_set in [FeatureSet.MULTI_SCALE, FeatureSet.COMPREHENSIVE]:
            features.update(self._compute_multi_scale_features())
        
        # Multi-horizon features (new comprehensive system)
        if self.feature_set in [FeatureSet.ADVANCED, FeatureSet.MULTI_SCALE, FeatureSet.COMPREHENSIVE]:
            features.update(self._compute_multi_horizon_features(ts_event))
        
        return features
    
    def _process_execution_event(self, ts_event: int, side: SideType, price: float, size: int, order_id: int = 0, action: ActionType = ActionType.NONE):
        """Process execution events for footprint analysis."""
        exec_state = self.state.execution_state
        
        # Update execution volumes
        if side == SideType.BID:
            # Execution on bid side = sell order hit the bid (aggressive sell)
            exec_state.sell_volume += size
            exec_state.aggressive_sell_volume += size
            exec_state.session_sell_volume += size
        else:
            # Execution on ask side = buy order hit the ask (aggressive buy)
            exec_state.buy_volume += size
            exec_state.aggressive_buy_volume += size
            exec_state.session_buy_volume += size
        
        # Update delta
        delta_change = size if side == SideType.ASK else -size
        exec_state.session_delta += delta_change
        
        # Track last execution
        exec_state.last_execution_price = price
        exec_state.last_execution_volume = size
        exec_state.last_execution_time = ts_event
        
        # Update multi-horizon buffers
        self._update_multi_horizon_execution(ts_event, side, price, size, delta_change)
        
        # Check for absorption/exhaustion events
        self._detect_absorption_exhaustion(ts_event, price, size)
        
        # Advanced event detection (COMPREHENSIVE feature set only)
        if self.feature_set == FeatureSet.COMPREHENSIVE:
            self._detect_large_orders(ts_event, order_id, price, size, side, action)
            self._detect_iceberg_orders(ts_event, price, size, side, action)
            self._detect_spoofing_behavior(ts_event, order_id, price, size, side, action)
            self._detect_institutional_flow(ts_event, side, price, size)
            self._detect_market_regime_changes(ts_event, price, size)
            self._detect_liquidity_stress(ts_event, price, size)
            self._detect_order_flow_anomalies(ts_event, price, size, action)
            
            # Update multi-horizon advanced event counts
            self._update_multi_horizon_advanced_events(ts_event)
    
    def _update_multi_horizon_execution(self, ts_event: int, side: SideType, price: float, size: int, delta_change: float):
        """Update multi-horizon buffers with execution data."""
        # Update all horizons
        for horizon in self.state.multi_horizon.horizon_configs.keys():
            buy_vol = size if side == SideType.ASK else 0
            sell_vol = size if side == SideType.BID else 0
            
            self.state.multi_horizon.update_horizon(
                horizon=horizon,
                timestamp=ts_event,
                buy_volume=buy_vol,
                sell_volume=sell_vol,
                total_volume=size,
                delta=delta_change,
                price_change=0.0,  # Will be computed separately
                execution_event=1
            )
    
    def _update_multi_horizon_advanced_events(self, ts_event: int):
        """Update multi-horizon buffers with advanced event counts."""
        if self.feature_set != FeatureSet.COMPREHENSIVE:
            return
        
        exec_state = self.state.execution_state
        
        # Count recent events for each horizon
        for horizon in self.state.multi_horizon.horizon_configs.keys():
            interval_ms = self.state.multi_horizon.horizon_configs[horizon]['interval_ms']
            interval_ns = interval_ms * 1000000  # Convert to nanoseconds
            
            # Count events within the horizon window
            recent_time = ts_event - interval_ns
            
            # Count large order events
            large_order_count = sum(1 for event in exec_state.large_order_events 
                                  if event.timestamp >= recent_time)
            
            # Count iceberg events
            iceberg_count = sum(1 for event in exec_state.iceberg_events 
                              if event.timestamp >= recent_time)
            
            # Count spoofing events
            spoofing_count = sum(1 for event in exec_state.spoofing_events 
                               if event.timestamp >= recent_time)
            
            # Count institutional flow events
            flow_count = sum(1 for event in exec_state.institutional_flow_events 
                           if event.timestamp >= recent_time)
            
            # Count market regime events
            regime_count = sum(1 for event in exec_state.market_regime_events 
                             if event.timestamp >= recent_time)
            
            # Count liquidity stress events
            stress_count = sum(1 for event in exec_state.liquidity_stress_events 
                             if event.timestamp >= recent_time)
            
            # Count order flow anomalies
            anomaly_count = sum(1 for event in exec_state.order_flow_anomalies 
                              if event.timestamp >= recent_time)
            
            # Update horizon with event counts
            self.state.multi_horizon.update_horizon(
                horizon=horizon,
                timestamp=ts_event,
                large_order_events=large_order_count,
                iceberg_events=iceberg_count,
                spoofing_events=spoofing_count,
                institutional_flow_events=flow_count,
                market_regime_events=regime_count,
                liquidity_stress_events=stress_count,
                order_flow_anomalies=anomaly_count
            )
    
    def _detect_absorption_exhaustion(self, ts_event: int, price: float, size: int):
        """Detect absorption and exhaustion events."""
        # Get posted volume at this price level
        posted_volume = (self.state.order_book.bids.get(price, 0) + 
                        self.state.order_book.asks.get(price, 0))
        
        if posted_volume > 0:
            absorption_ratio = size / posted_volume
            
            # Detect significant absorption (>50% of posted volume executed)
            if absorption_ratio > 0.5:
                absorption_event = AbsorptionEvent(
                    timestamp=ts_event,
                    price=price,
                    executed_volume=size,
                    posted_volume=posted_volume,
                    absorption_ratio=absorption_ratio
                )
                self.state.execution_state.absorption_events.append(absorption_event)
                
                # Limit history
                if len(self.state.execution_state.absorption_events) > 1000:
                    self.state.execution_state.absorption_events = self.state.execution_state.absorption_events[-500:]
        
        # Detect exhaustion (posted volume becomes very small)
        if posted_volume < size * 0.1:  # Less than 10% of executed volume remains
            exhaustion_event = ExhaustionEvent(
                timestamp=ts_event,
                price=price,
                depleted_volume=size
            )
            self.state.execution_state.exhaustion_events.append(exhaustion_event)
            
            # Limit history
            if len(self.state.execution_state.exhaustion_events) > 1000:
                self.state.execution_state.exhaustion_events = self.state.execution_state.exhaustion_events[-500:]
    
    def _compute_execution_features(self, ts_event: int) -> Dict[str, Any]:
        """Compute execution-aware footprint features."""
        features = {}
        exec_state = self.state.execution_state
        
        # Basic execution metrics
        features['buy_volume'] = exec_state.buy_volume
        features['sell_volume'] = exec_state.sell_volume
        features['aggressive_buy_volume'] = exec_state.aggressive_buy_volume
        features['aggressive_sell_volume'] = exec_state.aggressive_sell_volume
        features['passive_buy_volume'] = exec_state.passive_buy_volume
        features['passive_sell_volume'] = exec_state.passive_sell_volume
        
        # Delta metrics
        total_volume = exec_state.buy_volume + exec_state.sell_volume
        if total_volume > 0:
            features['delta'] = exec_state.buy_volume - exec_state.sell_volume
            features['delta_ratio'] = features['delta'] / total_volume
        else:
            features['delta'] = 0.0
            features['delta_ratio'] = 0.0
        
        features['session_delta'] = exec_state.session_delta
        features['session_buy_volume'] = exec_state.session_buy_volume
        features['session_sell_volume'] = exec_state.session_sell_volume
        
        # Absorption metrics
        recent_absorption = [e for e in exec_state.absorption_events 
                           if ts_event - e.timestamp < 60000000000]  # Last 60 seconds
        features['absorption_events_1m'] = len(recent_absorption)
        features['avg_absorption_ratio'] = (np.mean([e.absorption_ratio for e in recent_absorption]) 
                                          if recent_absorption else 0.0)
        
        # Exhaustion metrics
        recent_exhaustion = [e for e in exec_state.exhaustion_events 
                           if ts_event - e.timestamp < 60000000000]  # Last 60 seconds
        features['exhaustion_events_1m'] = len(recent_exhaustion)
        
        # Execution intensity
        features['last_execution_volume'] = exec_state.last_execution_volume
        features['last_execution_price'] = exec_state.last_execution_price
        
        if exec_state.last_execution_time > 0:
            time_since_last = (ts_event - exec_state.last_execution_time) / 1000000000  # Convert to seconds
            features['time_since_last_execution'] = time_since_last
        else:
            features['time_since_last_execution'] = float('inf')
        
        return features
    
    def _compute_multi_horizon_features(self, ts_event: int) -> Dict[str, Any]:
        """Compute multi-horizon features across all time scales."""
        features = {}
        
        # Compute features for each horizon
        for horizon, state in self.state.multi_horizon.states.items():
            prefix = f"{horizon}_"
            
            # Volume features
            features[f"{prefix}buy_volume"] = state.buy_volume
            features[f"{prefix}sell_volume"] = state.sell_volume
            features[f"{prefix}total_volume"] = state.total_volume
            
            # Delta features
            features[f"{prefix}delta"] = state.delta
            features[f"{prefix}cumulative_delta"] = state.cumulative_delta
            
            # Delta ratio
            if state.total_volume > 0:
                features[f"{prefix}delta_ratio"] = state.delta / state.total_volume
            else:
                features[f"{prefix}delta_ratio"] = 0.0
            
            # Event counts
            features[f"{prefix}absorption_events"] = state.absorption_events
            features[f"{prefix}exhaustion_events"] = state.exhaustion_events
            
            # Advanced event counts (COMPREHENSIVE feature set only)
            if self.feature_set == FeatureSet.COMPREHENSIVE:
                features[f"{prefix}large_order_events"] = state.large_order_events
                features[f"{prefix}iceberg_events"] = state.iceberg_events
                features[f"{prefix}spoofing_events"] = state.spoofing_events
                features[f"{prefix}institutional_flow_events"] = state.institutional_flow_events
                features[f"{prefix}market_regime_events"] = state.market_regime_events
                features[f"{prefix}liquidity_stress_events"] = state.liquidity_stress_events
                features[f"{prefix}order_flow_anomalies"] = state.order_flow_anomalies
            
            # Price and volatility
            features[f"{prefix}price_change"] = state.price_change
            features[f"{prefix}volatility"] = state.volatility
            
            # Liquidity features
            features[f"{prefix}average_spread"] = state.average_spread
            features[f"{prefix}depth_at_touch"] = state.depth_at_touch
        
        # Cross-horizon features
        features.update(self._compute_cross_horizon_features())
        
        # Advanced extreme features (for extreme intensity level)
        if self.feature_set == FeatureSet.COMPREHENSIVE:
            features.update(self._compute_extreme_features(ts_event))
        
        return features
    
    def _compute_cross_horizon_features(self) -> Dict[str, Any]:
        """Compute relationships between different time horizons."""
        features = {}
        states = self.state.multi_horizon.states
        
        # Delta momentum across horizons
        if '1s' in states and '1m' in states:
            delta_1s = states['1s'].delta
            delta_1m = states['1m'].delta
            
            if delta_1m != 0:
                features['delta_momentum_1s_1m'] = delta_1s / delta_1m
            else:
                features['delta_momentum_1s_1m'] = 0.0
        
        if '1m' in states and '20m' in states:
            delta_1m = states['1m'].delta
            delta_20m = states['20m'].delta
            
            if delta_20m != 0:
                features['delta_momentum_1m_20m'] = delta_1m / delta_20m
            else:
                features['delta_momentum_1m_20m'] = 0.0
        
        # Volume acceleration across horizons
        if '10s' in states and '1m' in states and '5m' in states:
            vol_10s = states['10s'].total_volume
            vol_1m = states['1m'].total_volume
            vol_5m = states['5m'].total_volume
            
            if vol_5m > 0 and vol_1m > 0:
                accel_short = vol_10s / vol_1m if vol_1m > 0 else 0
                accel_long = vol_1m / vol_5m
                features['volume_acceleration_ratio'] = accel_short / accel_long if accel_long > 0 else 0
            else:
                features['volume_acceleration_ratio'] = 0.0
        
        # Divergence signals
        if '1s' in states and '1h' in states:
            delta_ratio_short = states['1s'].delta / max(states['1s'].total_volume, 1)
            delta_ratio_long = states['1h'].delta / max(states['1h'].total_volume, 1)
            features['delta_divergence_1s_1h'] = delta_ratio_short - delta_ratio_long
        
        return features
    
    def _compute_fair_value_features(self, midprice: float) -> Dict[str, Any]:
        """Compute fair value features based on execution data."""
        features = {}
        exec_state = self.state.execution_state
        
        # Volume-weighted midprice (VWAP)
        if exec_state.session_buy_volume > 0 and exec_state.session_sell_volume > 0:
            # Simplified VWAP calculation
            total_session_volume = exec_state.session_buy_volume + exec_state.session_sell_volume
            if total_session_volume > 0:
                # This is a simplified calculation - in practice, you'd maintain price*volume sums
                features['vwap_mid'] = midprice  # Placeholder - should be actual VWAP
            else:
                features['vwap_mid'] = midprice
        else:
            features['vwap_mid'] = midprice
        
        # Imbalance-adjusted midprice
        total_depth = sum(self.state.order_book.bids.values()) + sum(self.state.order_book.asks.values())
        if total_depth > 0:
            delta_impact = exec_state.session_delta / total_depth
            features['imbalance_adjusted_mid'] = midprice + delta_impact * self.tick_size
        else:
            features['imbalance_adjusted_mid'] = midprice
        
        # Execution-weighted midprice
        if exec_state.last_execution_volume > 0:
            weight = min(exec_state.last_execution_volume / 1000, 1.0)  # Cap weight at 1.0
            features['execution_weighted_mid'] = (1 - weight) * midprice + weight * exec_state.last_execution_price
        else:
            features['execution_weighted_mid'] = midprice
        
        return features
    
    def _compute_basic_features(self, price: float, size: int, midprice: float, order_id: int, side: SideType, ts_event: int) -> Dict[str, Any]:
        """Compute basic L3 features."""
        features = {}
        
        # Spread in ticks
        spread_ticks = self.state.order_book.get_spread_ticks(self.tick_size)
        features['spread_ticks'] = spread_ticks
        
        # Depth features
        bid_depth = self.state.order_book.get_depth(SideType.BID, self.depth_levels)
        ask_depth = self.state.order_book.get_depth(SideType.ASK, self.depth_levels)
        
        # Normalize depth
        bid_prices = [price for price, _ in bid_depth]
        bid_sizes = [size for _, size in bid_depth]
        ask_prices = [price for price, _ in ask_depth]
        ask_sizes = [size for _, size in ask_depth]
        
        # Pad to fixed length
        while len(bid_prices) < self.depth_levels:
            bid_prices.append(0.0)
            bid_sizes.append(0)
        while len(ask_prices) < self.depth_levels:
            ask_prices.append(0.0)
            ask_sizes.append(0)
        
        # Normalize prices relative to midprice
        bid_prices_norm = [(p - midprice) / self.tick_size if p > 0 else 0.0 for p in bid_prices]
        ask_prices_norm = [(p - midprice) / self.tick_size if p > 0 else 0.0 for p in ask_prices]
        
        # Normalize sizes
        bid_sizes_norm = self.normalization_engine.normalize_depth(bid_sizes)
        ask_sizes_norm = self.normalization_engine.normalize_depth(ask_sizes)
        
        features['depth_bid_norm'] = bid_sizes_norm
        features['depth_ask_norm'] = ask_sizes_norm
        
        # Order flow imbalance
        total_bid_volume = sum(bid_sizes)
        total_ask_volume = sum(ask_sizes)
        ofi = self.normalization_engine.normalize_imbalance(total_bid_volume, total_ask_volume)
        features['ofi_norm'] = ofi
        
        # Queue position (simplified)
        if order_id in self.state.order_book.order_positions:
            order_price, order_size = self.state.order_book.order_positions[order_id]
            if side == SideType.BID:
                queue_size = self.state.order_book.bids.get(order_price, 0)
            else:
                queue_size = self.state.order_book.asks.get(order_price, 0)
            
            queue_fraction = order_size / max(queue_size, 1)
            features['queue_fraction'] = queue_fraction
        else:
            features['queue_fraction'] = 0.0
        
        # Normalize price and size
        normalized = self.normalization_engine.normalize_event(
            price=price,
            size=size,
            time_delta=0,  # Will be computed separately
            midprice=midprice,
            timestamp=ts_event
        )
        
        features['price_norm'] = normalized['price_norm']
        features['size_norm'] = normalized['size_norm']
        
        return features
    
    def _compute_advanced_features(self, 
                                 ts_event: int,
                                 action: ActionType,
                                 side: SideType,
                                 price: float,
                                 size: int) -> Dict[str, Any]:
        """Compute advanced L3 features."""
        features = {}
        
        # Top-K queue snapshot
        bid_depth = self.state.order_book.get_depth(SideType.BID, self.depth_levels)
        ask_depth = self.state.order_book.get_depth(SideType.ASK, self.depth_levels)
        
        # Create queue snapshot tensor
        queue_snapshot = []
        for i in range(self.depth_levels):
            if i < len(bid_depth):
                queue_snapshot.extend([bid_depth[i][0], bid_depth[i][1]])
            else:
                queue_snapshot.extend([0.0, 0])
            
            if i < len(ask_depth):
                queue_snapshot.extend([ask_depth[i][0], ask_depth[i][1]])
            else:
                queue_snapshot.extend([0.0, 0])
        
        features['top_k_queue_snapshot'] = queue_snapshot
        
        # LOB image (simplified 2D representation)
        lob_image = self._create_lob_image()
        features['lob_image'] = lob_image
        
        # Event tokens
        event_tokens = self._encode_event_tokens(action, side)
        features['event_tokens'] = event_tokens
        
        # Patch diffs (simplified)
        patch_diffs = self._compute_patch_diffs()
        features['patch_diffs'] = patch_diffs
        
        # Microstructure indicators
        microstructure = self._compute_microstructure_indicators()
        features['microstructure_indicators'] = microstructure
        
        # Cancel/modify ratio
        total_events = self.state.add_count + self.state.modify_count + self.state.cancel_count
        if total_events > 0:
            cancel_modify_ratio = (self.state.cancel_count + self.state.modify_count) / total_events
        else:
            cancel_modify_ratio = 0.0
        features['cancel_modify_ratio'] = cancel_modify_ratio
        
        return features
    
    def _compute_multi_scale_features(self) -> Dict[str, Any]:
        """Compute multi-scale features."""
        features = {}
        
        # Update multi-scale OFI
        current_ofi = features.get('ofi_norm', 0.0)
        
        # Fast OFI (100ms equivalent)
        self.state.ofi_fast = 0.1 * current_ofi + 0.9 * self.state.ofi_fast
        
        # Medium OFI (1s equivalent)
        self.state.ofi_medium = 0.01 * current_ofi + 0.99 * self.state.ofi_medium
        
        # Slow OFI (10s equivalent)
        self.state.ofi_slow = 0.001 * current_ofi + 0.999 * self.state.ofi_slow
        
        features['ofi_fast'] = self.state.ofi_fast
        features['ofi_medium'] = self.state.ofi_medium
        features['ofi_slow'] = self.state.ofi_slow
        
        # Volatility estimate
        if len(self.state.price_changes) > 1:
            self.state.volatility_estimate = np.std(self.state.price_changes)
        features['volatility_estimate'] = self.state.volatility_estimate
        
        return features
    
    def _create_lob_image(self) -> List[float]:
        """Create simplified LOB image."""
        # Create a 2D grid representation of the order book
        grid_size = 20  # 20x20 grid
        lob_image = [0.0] * (grid_size * grid_size)
        
        # Center the grid around midprice
        midprice = self.state.order_book.get_midprice()
        if midprice is None:
            return lob_image
        
        # Map prices to grid positions
        for price, size in self.state.order_book.bids.items():
            grid_pos = int((price - midprice) / self.tick_size) + grid_size // 2
            if 0 <= grid_pos < grid_size:
                lob_image[grid_pos] = size
        
        for price, size in self.state.order_book.asks.items():
            grid_pos = int((price - midprice) / self.tick_size) + grid_size // 2
            if 0 <= grid_pos < grid_size:
                lob_image[grid_pos] = size
        
        return lob_image
    
    def _encode_event_tokens(self, action: ActionType, side: SideType) -> List[int]:
        """Encode event tokens for sequence models."""
        # Simple categorical encoding
        action_encoding = {
            ActionType.ADD: 0,
            ActionType.MODIFY: 1,
            ActionType.CANCEL: 2,
            ActionType.CLEAR: 3,
            ActionType.FILL: 4,
            ActionType.TRADE: 5,
            ActionType.NONE: 6
        }
        
        side_encoding = {
            SideType.BID: 0,
            SideType.ASK: 1,
            SideType.NONE: 2
        }
        
        return [action_encoding.get(action, 6), side_encoding.get(side, 2)]
    
    def _compute_patch_diffs(self) -> List[float]:
        """Compute patch diffs (simplified)."""
        # Simplified patch diff computation
        # In practice, this would track changes in order book state
        return [0.0] * 10  # Placeholder
    
    def _compute_microstructure_indicators(self) -> List[float]:
        """Compute microstructure indicators."""
        indicators = []
        
        # Price impact
        if len(self.state.price_changes) > 0:
            indicators.append(np.mean(self.state.price_changes))
        else:
            indicators.append(0.0)
        
        # Volume imbalance
        if len(self.state.volume_imbalances) > 0:
            indicators.append(np.mean(self.state.volume_imbalances))
        else:
            indicators.append(0.0)
        
        # Time intensity
        if len(self.state.time_deltas) > 0:
            indicators.append(1.0 / np.mean(self.state.time_deltas))
        else:
            indicators.append(0.0)
        
        # Pad to fixed length
        while len(indicators) < 10:
            indicators.append(0.0)
        
        return indicators
    
    def _compute_extreme_features(self, ts_event: int) -> Dict[str, Any]:
        """Compute extreme-level advanced features for comprehensive analysis."""
        features = {}
        
        # Execution clustering features
        features['execution_cluster_strength'] = self._compute_execution_cluster_strength()
        features['execution_cluster_migration'] = self._compute_execution_cluster_migration()
        features['execution_cluster_persistence'] = self._compute_execution_cluster_persistence()
        
        # Aggressor pattern features
        features['aggressor_size_distribution'] = self._compute_aggressor_size_distribution()
        features['aggressor_frequency'] = self._compute_aggressor_frequency()
        features['aggressor_persistence'] = self._compute_aggressor_persistence()
        
        # Market structure indicators
        features['market_impact_curve'] = self._compute_market_impact_curve()
        features['liquidity_resilience'] = self._compute_liquidity_resilience()
        features['quote_stability'] = self._compute_quote_stability()
        
        # Institutional flow detection
        features['large_order_fragmentation'] = self._compute_large_order_fragmentation()
        features['institutional_flow_strength'] = self._compute_institutional_flow_strength()
        features['iceberg_detection'] = self._compute_iceberg_detection()
        
        # Flow persistence features
        features['flow_autocorrelation'] = self._compute_flow_autocorrelation()
        features['flow_predictability'] = self._compute_flow_predictability()
        features['flow_exhaustion_signals'] = self._compute_flow_exhaustion_signals()
        
        # Market regime features
        features['volatility_regime'] = self._compute_volatility_regime()
        features['regime_transition_probability'] = self._compute_regime_transition_probability()
        features['regime_persistence'] = self._compute_regime_persistence()
        
        # Liquidity regime features
        features['liquidity_regime'] = self._compute_liquidity_regime()
        features['liquidity_stress_indicators'] = self._compute_liquidity_stress_indicators()
        features['liquidity_recovery_signals'] = self._compute_liquidity_recovery_signals()
        
        return features
    
    def _compute_execution_cluster_strength(self) -> float:
        """Compute execution clustering strength."""
        # Simplified implementation - in practice would analyze execution patterns
        return 0.5  # Placeholder
    
    def _compute_execution_cluster_migration(self) -> float:
        """Compute execution cluster migration."""
        return 0.3  # Placeholder
    
    def _compute_execution_cluster_persistence(self) -> float:
        """Compute execution cluster persistence."""
        return 0.7  # Placeholder
    
    def _compute_aggressor_size_distribution(self) -> float:
        """Compute aggressor size distribution."""
        return 0.4  # Placeholder
    
    def _compute_aggressor_frequency(self) -> float:
        """Compute aggressor frequency."""
        return 0.6  # Placeholder
    
    def _compute_aggressor_persistence(self) -> float:
        """Compute aggressor persistence."""
        return 0.5  # Placeholder
    
    def _compute_market_impact_curve(self) -> float:
        """Compute market impact curve."""
        return 0.3  # Placeholder
    
    def _compute_liquidity_resilience(self) -> float:
        """Compute liquidity resilience."""
        return 0.8  # Placeholder
    
    def _compute_quote_stability(self) -> float:
        """Compute quote stability."""
        return 0.6  # Placeholder
    
    def _compute_large_order_fragmentation(self) -> float:
        """Compute large order fragmentation."""
        exec_state = self.state.execution_state
        
        if not exec_state.large_order_events:
            return 0.0
        
        # Calculate fragmentation ratio
        fragmented_orders = [event for event in exec_state.large_order_events if event.is_fragmented]
        if not fragmented_orders:
            return 0.0
        
        total_fragmented_size = sum(event.total_fragmented_size for event in fragmented_orders)
        total_orders = len(exec_state.large_order_events)
        fragmentation_ratio = len(fragmented_orders) / total_orders if total_orders > 0 else 0.0
        
        return min(1.0, fragmentation_ratio * 2.0)  # Scale to 0-1 range
    
    def _compute_institutional_flow_strength(self) -> float:
        """Compute institutional flow strength."""
        exec_state = self.state.execution_state
        
        if not exec_state.institutional_flow_events:
            return 0.0
        
        # Calculate average flow strength
        recent_flows = exec_state.institutional_flow_events[-100:] if len(exec_state.institutional_flow_events) > 100 else exec_state.institutional_flow_events
        
        if not recent_flows:
            return 0.0
        
        avg_strength = np.mean([flow.strength for flow in recent_flows])
        avg_confidence = np.mean([flow.confidence for flow in recent_flows])
        
        return avg_strength * avg_confidence
    
    def _compute_iceberg_detection(self) -> float:
        """Compute iceberg detection."""
        exec_state = self.state.execution_state
        
        if not exec_state.iceberg_events:
            return 0.0
        
        # Calculate average confidence of iceberg detections
        recent_icebergs = exec_state.iceberg_events[-50:] if len(exec_state.iceberg_events) > 50 else exec_state.iceberg_events
        
        if not recent_icebergs:
            return 0.0
        
        avg_confidence = np.mean([iceberg.confidence_score for iceberg in recent_icebergs])
        iceberg_frequency = len(recent_icebergs) / 50.0  # Normalize by time window
        
        return min(1.0, avg_confidence * iceberg_frequency)
    
    def _compute_flow_autocorrelation(self) -> float:
        """Compute flow autocorrelation."""
        exec_state = self.state.execution_state
        
        if len(exec_state.flow_buffers['delta']) < 50:
            return 0.0
        
        # Calculate autocorrelation of delta flow
        deltas = list(exec_state.flow_buffers['delta'])[-100:]
        if len(deltas) < 20:
            return 0.0
        
        # Simple autocorrelation calculation
        mean_delta = np.mean(deltas)
        var_delta = np.var(deltas)
        
        if var_delta == 0:
            return 0.0
        
        # Lag-1 autocorrelation
        autocorr = 0.0
        for i in range(1, len(deltas)):
            autocorr += (deltas[i] - mean_delta) * (deltas[i-1] - mean_delta)
        
        autocorr /= (len(deltas) - 1) * var_delta
        
        return min(1.0, abs(autocorr))
    
    def _compute_flow_predictability(self) -> float:
        """Compute flow predictability."""
        exec_state = self.state.execution_state
        
        if not exec_state.institutional_flow_events:
            return 0.0
        
        # Calculate predictability based on flow consistency
        recent_flows = exec_state.institutional_flow_events[-50:] if len(exec_state.institutional_flow_events) > 50 else exec_state.institutional_flow_events
        
        if not recent_flows:
            return 0.0
        
        # Calculate flow type consistency
        flow_types = [flow.flow_type for flow in recent_flows]
        type_counts = {}
        for flow_type in flow_types:
            type_counts[flow_type] = type_counts.get(flow_type, 0) + 1
        
        # Predictability based on dominant flow type
        max_count = max(type_counts.values()) if type_counts else 0
        predictability = max_count / len(recent_flows) if recent_flows else 0.0
        
        return predictability
    
    def _compute_flow_exhaustion_signals(self) -> float:
        """Compute flow exhaustion signals."""
        exec_state = self.state.execution_state
        
        if not exec_state.institutional_flow_events:
            return 0.0
        
        # Calculate flow exhaustion based on decreasing strength
        recent_flows = exec_state.institutional_flow_events[-20:] if len(exec_state.institutional_flow_events) > 20 else exec_state.institutional_flow_events
        
        if len(recent_flows) < 5:
            return 0.0
        
        # Check for decreasing flow strength (exhaustion pattern)
        strengths = [flow.strength for flow in recent_flows]
        if len(strengths) >= 5:
            # Calculate trend in flow strength
            trend = np.polyfit(range(len(strengths)), strengths, 1)[0]
            exhaustion_signal = max(0.0, -trend)  # Positive when strength is decreasing
            
            return min(1.0, exhaustion_signal * 10.0)  # Scale appropriately
        
        return 0.0
    
    def _compute_volatility_regime(self) -> float:
        """Compute volatility regime."""
        exec_state = self.state.execution_state
        
        if not exec_state.market_regime_events:
            return 0.0
        
        # Calculate volatility regime based on recent market regime events
        recent_regimes = exec_state.market_regime_events[-20:] if len(exec_state.market_regime_events) > 20 else exec_state.market_regime_events
        
        if not recent_regimes:
            return 0.0
        
        # Count volatile regimes
        volatile_count = sum(1 for regime in recent_regimes if regime.regime_type == 'volatile')
        volatility_ratio = volatile_count / len(recent_regimes)
        
        return volatility_ratio
    
    def _compute_regime_transition_probability(self) -> float:
        """Compute regime transition probability."""
        exec_state = self.state.execution_state
        
        if len(exec_state.market_regime_events) < 2:
            return 0.0
        
        # Calculate transition probability from recent events
        recent_regimes = exec_state.market_regime_events[-10:] if len(exec_state.market_regime_events) > 10 else exec_state.market_regime_events
        
        if len(recent_regimes) < 2:
            return 0.0
        
        # Count regime changes
        transitions = 0
        for i in range(1, len(recent_regimes)):
            if recent_regimes[i].regime_type != recent_regimes[i-1].regime_type:
                transitions += 1
        
        transition_probability = transitions / (len(recent_regimes) - 1)
        
        return transition_probability
    
    def _compute_regime_persistence(self) -> float:
        """Compute regime persistence."""
        exec_state = self.state.execution_state
        
        if not exec_state.market_regime_events:
            return 0.0
        
        # Calculate regime persistence (opposite of transition probability)
        transition_prob = self._compute_regime_transition_probability()
        persistence = 1.0 - transition_prob
        
        return persistence
    
    def _compute_liquidity_regime(self) -> float:
        """Compute liquidity regime."""
        exec_state = self.state.execution_state
        
        if not exec_state.liquidity_stress_events:
            return 0.0
        
        # Calculate liquidity regime based on stress events
        recent_stress = exec_state.liquidity_stress_events[-20:] if len(exec_state.liquidity_stress_events) > 20 else exec_state.liquidity_stress_events
        
        if not recent_stress:
            return 0.0
        
        # Calculate average stress level
        avg_stress = np.mean([stress.stress_level for stress in recent_stress])
        
        # Normalize to 0-1 range (0 = healthy liquidity, 1 = stressed liquidity)
        return min(1.0, avg_stress)
    
    def _compute_liquidity_stress_indicators(self) -> float:
        """Compute liquidity stress indicators."""
        exec_state = self.state.execution_state
        
        if not exec_state.liquidity_stress_events:
            return 0.0
        
        # Calculate current stress level
        recent_stress = exec_state.liquidity_stress_events[-5:] if len(exec_state.liquidity_stress_events) > 5 else exec_state.liquidity_stress_events
        
        if not recent_stress:
            return 0.0
        
        # Use most recent stress level
        current_stress = recent_stress[-1].stress_level
        
        return current_stress
    
    def _compute_liquidity_recovery_signals(self) -> float:
        """Compute liquidity recovery signals."""
        exec_state = self.state.execution_state
        
        if len(exec_state.liquidity_stress_events) < 2:
            return 0.0
        
        # Calculate recovery signal based on decreasing stress
        recent_stress = exec_state.liquidity_stress_events[-10:] if len(exec_state.liquidity_stress_events) > 10 else exec_state.liquidity_stress_events
        
        if len(recent_stress) < 3:
            return 0.0
        
        # Check for decreasing stress levels (recovery pattern)
        stress_levels = [stress.stress_level for stress in recent_stress]
        if len(stress_levels) >= 3:
            # Calculate trend in stress levels
            trend = np.polyfit(range(len(stress_levels)), stress_levels, 1)[0]
            recovery_signal = max(0.0, -trend)  # Positive when stress is decreasing
            
            return min(1.0, recovery_signal * 5.0)  # Scale appropriately
        
        return 0.0

    # ============================================================================
    # ADVANCED EVENT DETECTION METHODS (COMPREHENSIVE FEATURE SET)
    # ============================================================================

    def _detect_large_orders(self, ts_event: int, order_id: int, price: float, size: int, side: SideType, action: ActionType):
        """Detect large orders and fragmentation patterns."""
        exec_state = self.state.execution_state
        
        # Define large order thresholds (configurable)
        LARGE_ORDER_THRESHOLD = 1000  # contracts
        VERY_LARGE_ORDER_THRESHOLD = 5000  # contracts
        
        if size >= LARGE_ORDER_THRESHOLD:
            # Track large order
            large_order_event = LargeOrderEvent(
                timestamp=ts_event,
                order_id=order_id,
                price=price,
                size=size,
                side=side.value,
                action=action.value,
                is_fragmented=False
            )
            
            # Check for fragmentation patterns
            if order_id in exec_state.order_fragments:
                fragments = exec_state.order_fragments[order_id]
                if len(fragments) > 1:
                    large_order_event.is_fragmented = True
                    large_order_event.fragment_count = len(fragments)
                    large_order_event.total_fragmented_size = sum(f['size'] for f in fragments)
                    
                    # Calculate time to complete
                    if fragments:
                        first_time = fragments[0]['timestamp']
                        last_time = fragments[-1]['timestamp']
                        large_order_event.time_to_complete = last_time - first_time
            
            exec_state.large_order_events.append(large_order_event)
            
            # Limit history
            if len(exec_state.large_order_events) > 1000:
                exec_state.large_order_events = exec_state.large_order_events[-500:]
        
        # Track order fragments
        if action in [ActionType.ADD, ActionType.MODIFY]:
            if order_id not in exec_state.order_fragments:
                exec_state.order_fragments[order_id] = []
            
            exec_state.order_fragments[order_id].append({
                'timestamp': ts_event,
                'price': price,
                'size': size,
                'side': side.value,
                'action': action.value
            })

    def _detect_iceberg_orders(self, ts_event: int, price: float, size: int, side: SideType, action: ActionType):
        """Detect iceberg orders based on replenishment patterns."""
        exec_state = self.state.execution_state
        
        # Iceberg detection parameters
        ICEBERG_REPLENISHMENT_THRESHOLD = 3  # Minimum replenishments
        ICEBERG_SIZE_THRESHOLD = 500  # Minimum size to consider
        ICEBERG_TIME_WINDOW = 60000000000  # 60 seconds in nanoseconds
        
        if size >= ICEBERG_SIZE_THRESHOLD and action == ActionType.ADD:
            # Check for replenishment patterns at this price level
            if price not in exec_state.iceberg_candidates:
                exec_state.iceberg_candidates[price] = {
                    'side': side.value,
                    'replenishments': [],
                    'total_visible_size': 0,
                    'first_seen': ts_event
                }
            
            candidate = exec_state.iceberg_candidates[price]
            candidate['replenishments'].append({
                'timestamp': ts_event,
                'size': size
            })
            candidate['total_visible_size'] += size
            
            # Check if this looks like an iceberg
            if len(candidate['replenishments']) >= ICEBERG_REPLENISHMENT_THRESHOLD:
                # Calculate confidence score based on pattern consistency
                time_spans = []
                for i in range(1, len(candidate['replenishments'])):
                    time_span = candidate['replenishments'][i]['timestamp'] - candidate['replenishments'][i-1]['timestamp']
                    time_spans.append(time_span)
                
                if time_spans:
                    avg_time_span = np.mean(time_spans)
                    time_consistency = 1.0 / (1.0 + np.std(time_spans) / avg_time_span)
                    
                    # Estimate hidden size (typically 5-10x visible size)
                    estimated_hidden_size = candidate['total_visible_size'] * 7.5
                    
                    confidence_score = min(0.9, time_consistency * 0.8)
                    
                    iceberg_event = IcebergEvent(
                        timestamp=ts_event,
                        price=price,
                        side=candidate['side'],
                        visible_size=candidate['total_visible_size'],
                        estimated_hidden_size=int(estimated_hidden_size),
                        replenishment_count=len(candidate['replenishments']),
                        confidence_score=confidence_score
                    )
                    
                    exec_state.iceberg_events.append(iceberg_event)
                    
                    # Limit history
                    if len(exec_state.iceberg_events) > 1000:
                        exec_state.iceberg_events = exec_state.iceberg_events[-500:]
        
        # Clean up old candidates
        current_time = ts_event
        expired_prices = [p for p, candidate in exec_state.iceberg_candidates.items() 
                         if current_time - candidate['first_seen'] > ICEBERG_TIME_WINDOW]
        for price in expired_prices:
            del exec_state.iceberg_candidates[price]

    def _detect_spoofing_behavior(self, ts_event: int, order_id: int, price: float, size: int, side: SideType, action: ActionType):
        """Detect spoofing and market manipulation behavior."""
        exec_state = self.state.execution_state
        
        # Spoofing detection parameters
        SPOOFING_SIZE_THRESHOLD = 500  # Minimum size to consider
        SPOOFING_TIME_THRESHOLD = 5000000000  # 5 seconds in nanoseconds
        SPOOFING_CANCEL_THRESHOLD = 0.8  # 80% of orders cancelled quickly
        
        # Track order lifecycle
        if action == ActionType.ADD:
            exec_state.order_lifecycle[order_id] = {
                'add_time': ts_event,
                'price': price,
                'size': size,
                'side': side.value,
                'cancelled': False,
                'cancel_time': None,
                'executed': False
            }
            
            # Add to recent orders for pattern analysis
            exec_state.recent_orders.append({
                'timestamp': ts_event,
                'order_id': order_id,
                'price': price,
                'size': size,
                'side': side.value,
                'action': action.value
            })
        
        elif action == ActionType.CANCEL:
            if order_id in exec_state.order_lifecycle:
                lifecycle = exec_state.order_lifecycle[order_id]
                lifecycle['cancelled'] = True
                lifecycle['cancel_time'] = ts_event
                
                # Check for spoofing patterns
                if lifecycle['size'] >= SPOOFING_SIZE_THRESHOLD:
                    time_to_cancel = ts_event - lifecycle['add_time']
                    
                    if time_to_cancel <= SPOOFING_TIME_THRESHOLD:
                        # Calculate spoofing score
                        spoofing_score = min(1.0, (SPOOFING_TIME_THRESHOLD - time_to_cancel) / SPOOFING_TIME_THRESHOLD)
                        
                        # Determine spoofing type
                        if lifecycle['size'] > 1000:
                            spoofing_type = 'layering'
                        elif time_to_cancel < 1000000000:  # < 1 second
                            spoofing_type = 'quote_stuffing'
                        else:
                            spoofing_type = 'spoofing'
                        
                        spoofing_event = SpoofingEvent(
                            timestamp=ts_event,
                            order_id=order_id,
                            price=lifecycle['price'],
                            size=lifecycle['size'],
                            side=lifecycle['side'],
                            time_to_cancel=time_to_cancel,
                            spoofing_score=spoofing_score,
                            spoofing_type=spoofing_type
                        )
                        
                        exec_state.spoofing_events.append(spoofing_event)
                        
                        # Limit history
                        if len(exec_state.spoofing_events) > 1000:
                            exec_state.spoofing_events = exec_state.spoofing_events[-500:]
        
        elif action in [ActionType.FILL, ActionType.TRADE]:
            if order_id in exec_state.order_lifecycle:
                exec_state.order_lifecycle[order_id]['executed'] = True
        
        # Clean up old order lifecycles
        current_time = ts_event
        expired_orders = [oid for oid, lifecycle in exec_state.order_lifecycle.items() 
                         if current_time - lifecycle['add_time'] > 60000000000]  # 60 seconds
        for oid in expired_orders:
            del exec_state.order_lifecycle[oid]

    def _detect_institutional_flow(self, ts_event: int, side: SideType, price: float, size: int):
        """Detect institutional flow patterns."""
        exec_state = self.state.execution_state
        
        # Update flow buffers
        exec_state.flow_buffers['volume'].append(size)
        exec_state.flow_buffers['delta'].append(size if side == SideType.ASK else -size)
        exec_state.flow_buffers['price_change'].append(price - exec_state.last_execution_price if exec_state.last_execution_price > 0 else 0)
        
        # Calculate flow metrics over recent window
        window_size = 100
        if len(exec_state.flow_buffers['volume']) >= window_size:
            recent_volumes = list(exec_state.flow_buffers['volume'])[-window_size:]
            recent_deltas = list(exec_state.flow_buffers['delta'])[-window_size:]
            recent_price_changes = list(exec_state.flow_buffers['price_change'])[-window_size:]
            
            # Calculate flow strength
            total_volume = sum(recent_volumes)
            cumulative_delta = sum(recent_deltas)
            price_impact = sum(recent_price_changes)
            
            if total_volume > 0:
                delta_ratio = cumulative_delta / total_volume
                
                # Determine flow type and strength
                if abs(delta_ratio) > 0.3:  # Significant imbalance
                    if delta_ratio > 0:
                        flow_type = 'buy_pressure'
                        strength = min(1.0, delta_ratio)
                    else:
                        flow_type = 'sell_pressure'
                        strength = min(1.0, abs(delta_ratio))
                else:
                    flow_type = 'neutral'
                    strength = 0.0
                
                # Calculate confidence based on volume consistency
                volume_std = np.std(recent_volumes)
                volume_mean = np.mean(recent_volumes)
                volume_consistency = 1.0 / (1.0 + volume_std / volume_mean) if volume_mean > 0 else 0.0
                
                institutional_flow_event = InstitutionalFlowEvent(
                    timestamp=ts_event,
                    flow_type=flow_type,
                    strength=strength,
                    duration=window_size,
                    volume_impact=total_volume,
                    price_impact=price_impact,
                    confidence=volume_consistency
                )
                
                exec_state.institutional_flow_events.append(institutional_flow_event)
                
                # Limit history
                if len(exec_state.institutional_flow_events) > 1000:
                    exec_state.institutional_flow_events = exec_state.institutional_flow_events[-500:]

    def _detect_market_regime_changes(self, ts_event: int, price: float, size: int):
        """Detect market regime changes (trending, mean-reverting, volatile, quiet)."""
        exec_state = self.state.execution_state
        
        # Update regime buffers
        exec_state.volatility_buffer.append(abs(price - exec_state.last_execution_price) if exec_state.last_execution_price > 0 else 0)
        exec_state.liquidity_buffer.append(size)
        exec_state.trend_buffer.append(price - exec_state.last_execution_price if exec_state.last_execution_price > 0 else 0)
        
        # Calculate regime metrics over recent window
        window_size = 200
        if len(exec_state.volatility_buffer) >= window_size:
            recent_volatility = list(exec_state.volatility_buffer)[-window_size:]
            recent_liquidity = list(exec_state.liquidity_buffer)[-window_size:]
            recent_trend = list(exec_state.trend_buffer)[-window_size:]
            
            # Calculate regime indicators
            volatility_level = np.std(recent_volatility)
            liquidity_level = np.mean(recent_liquidity)
            trend_strength = np.mean(recent_trend)
            trend_consistency = 1.0 / (1.0 + np.std(recent_trend))
            
            # Determine regime type
            if volatility_level > 2.0:
                regime_type = 'volatile'
            elif abs(trend_strength) > 1.0 and trend_consistency > 0.7:
                regime_type = 'trending'
            elif liquidity_level < 100:
                regime_type = 'quiet'
            else:
                regime_type = 'mean_reverting'
            
            # Calculate transition probability
            if len(exec_state.market_regime_events) > 0:
                last_regime = exec_state.market_regime_events[-1].regime_type
                transition_probability = 0.1 if regime_type == last_regime else 0.3
            else:
                transition_probability = 0.2
            
            market_regime_event = MarketRegimeEvent(
                timestamp=ts_event,
                regime_type=regime_type,
                volatility_level=volatility_level,
                liquidity_level=liquidity_level,
                transition_probability=transition_probability
            )
            
            exec_state.market_regime_events.append(market_regime_event)
            
            # Limit history
            if len(exec_state.market_regime_events) > 1000:
                exec_state.market_regime_events = exec_state.market_regime_events[-500:]

    def _detect_liquidity_stress(self, ts_event: int, price: float, size: int):
        """Detect liquidity stress events."""
        exec_state = self.state.execution_state
        
        # Update microstructure tracking
        exec_state.recent_prices.append(price)
        exec_state.recent_volumes.append(size)
        
        # Calculate current spread and depth
        best_bid = self.state.order_book.get_best_bid()
        best_ask = self.state.order_book.get_best_ask()
        
        if best_bid and best_ask:
            current_spread = best_ask - best_bid
            exec_state.recent_spreads.append(current_spread)
            
            # Calculate depth at touch
            depth_at_touch = (self.state.order_book.bids.get(best_bid, 0) + 
                             self.state.order_book.asks.get(best_ask, 0))
            exec_state.recent_depths.append(depth_at_touch)
            
            # Detect stress conditions
            if len(exec_state.recent_spreads) >= 50 and len(exec_state.recent_depths) >= 50:
                avg_spread = np.mean(list(exec_state.recent_spreads)[-50:])
                avg_depth = np.mean(list(exec_state.recent_depths)[-50:])
                
                # Calculate stress indicators
                spread_widening = (current_spread - avg_spread) / avg_spread if avg_spread > 0 else 0
                depth_reduction = (avg_depth - depth_at_touch) / avg_depth if avg_depth > 0 else 0
                
                # Determine stress level
                stress_level = 0.0
                if spread_widening > 0.5:  # 50% spread widening
                    stress_level += 0.5
                if depth_reduction > 0.7:  # 70% depth reduction
                    stress_level += 0.5
                
                if stress_level > 0.3:  # Significant stress
                    liquidity_stress_event = LiquidityStressEvent(
                        timestamp=ts_event,
                        stress_level=stress_level,
                        spread_widening=spread_widening,
                        depth_reduction=depth_reduction,
                        recovery_time=None
                    )
                    
                    exec_state.liquidity_stress_events.append(liquidity_stress_event)
                    
                    # Limit history
                    if len(exec_state.liquidity_stress_events) > 1000:
                        exec_state.liquidity_stress_events = exec_state.liquidity_stress_events[-500:]

    def _detect_order_flow_anomalies(self, ts_event: int, price: float, size: int, action: ActionType):
        """Detect order flow anomalies."""
        exec_state = self.state.execution_state
        
        # Anomaly detection parameters
        VOLUME_SPIKE_THRESHOLD = 3.0  # 3x average volume
        PRICE_JUMP_THRESHOLD = 5.0  # 5 tick price jump
        SPREAD_WIDENING_THRESHOLD = 2.0  # 2x average spread
        
        # Calculate recent averages
        if len(exec_state.recent_volumes) >= 100:
            avg_volume = np.mean(list(exec_state.recent_volumes)[-100:])
            volume_std = np.std(list(exec_state.recent_volumes)[-100:])
            
            # Volume spike detection
            if size > avg_volume + VOLUME_SPIKE_THRESHOLD * volume_std:
                anomaly_event = OrderFlowAnomalyEvent(
                    timestamp=ts_event,
                    anomaly_type='volume_spike',
                    severity=min(1.0, (size - avg_volume) / (VOLUME_SPIKE_THRESHOLD * volume_std)),
                    duration=1,
                    impact_score=size / avg_volume if avg_volume > 0 else 1.0
                )
                exec_state.order_flow_anomalies.append(anomaly_event)
        
        # Price jump detection
        if exec_state.last_execution_price > 0:
            price_change = abs(price - exec_state.last_execution_price)
            if price_change > PRICE_JUMP_THRESHOLD * self.tick_size:
                anomaly_event = OrderFlowAnomalyEvent(
                    timestamp=ts_event,
                    anomaly_type='price_jump',
                    severity=min(1.0, price_change / (PRICE_JUMP_THRESHOLD * self.tick_size)),
                    duration=1,
                    impact_score=price_change / self.tick_size
                )
                exec_state.order_flow_anomalies.append(anomaly_event)
        
        # Spread widening detection
        if len(exec_state.recent_spreads) >= 50:
            avg_spread = np.mean(list(exec_state.recent_spreads)[-50:])
            current_spread = exec_state.recent_spreads[-1] if exec_state.recent_spreads else 0
            
            if current_spread > avg_spread * SPREAD_WIDENING_THRESHOLD:
                anomaly_event = OrderFlowAnomalyEvent(
                    timestamp=ts_event,
                    anomaly_type='spread_widening',
                    severity=min(1.0, (current_spread - avg_spread) / (avg_spread * SPREAD_WIDENING_THRESHOLD)),
                    duration=1,
                    impact_score=current_spread / avg_spread if avg_spread > 0 else 1.0
                )
                exec_state.order_flow_anomalies.append(anomaly_event)
        
        # Limit history
        if len(exec_state.order_flow_anomalies) > 1000:
            exec_state.order_flow_anomalies = exec_state.order_flow_anomalies[-500:]


class BatchFeatureEngine:
    """
    Batch feature engine for processing large datasets.
    
    Provides efficient batch feature computation while maintaining
    consistency with streaming feature computation.
    """
    
    def __init__(self, 
                 feature_set: FeatureSet = FeatureSet.BASIC,
                 normalization_type: NormalizationType = NormalizationType.TICK_RELATIVE):
        """
        Initialize batch feature engine.
        
        Args:
            feature_set: Set of features to compute
            normalization_type: Type of normalization to apply
        """
        self.feature_set = feature_set
        self.normalization_type = normalization_type
        self.engine = FeatureEngine(feature_set, normalization_type)
    
    def _ensure_required_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure DataFrame has all required columns for feature computation.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with all required columns
        """
        df = df.copy()
        
        # Required columns and their defaults
        required_columns = {
            'ts_event': None,  # Must exist
            'ts_recv': 'ts_event',  # Fallback to ts_event
            'action': 'ADD',  # Default action
            'side': 'BID',  # Default side
            'order_id': 0,  # Default order ID
            'price': 0.0,  # Default price
            'size': 0,  # Default size
            'flags': 0,  # Default flags
            'sequence': 0,  # Default sequence
            'instrument': 'UNKNOWN'  # Default instrument
        }
        
        # Check and add missing columns
        for col, default_value in required_columns.items():
            if col not in df.columns:
                if default_value is None:
                    # This column is required and must exist
                    raise ValueError(f"Required column '{col}' missing from DataFrame. Available columns: {list(df.columns)}")
                elif isinstance(default_value, str) and default_value in df.columns:
                    # Use existing column as fallback
                    df[col] = df[default_value]
                else:
                    # Use default value
                    df[col] = default_value
        
        # Handle special cases
        if 'instrument' not in df.columns and 'symbol' in df.columns:
            df['instrument'] = df['symbol']
        
        if 'ts_recv' not in df.columns and 'ts_event' in df.columns:
            df['ts_recv'] = df['ts_event']
        
        return df
    
    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute features for MBO DataFrame.
        
        Args:
            df: Input MBO DataFrame
            
        Returns:
            DataFrame with computed features
        """
        if df.empty:
            return df
        
        logger.info(f"Starting feature computation for {len(df):,} rows")
        
        # Track timing
        start_time = time.time()
        logger.info(f"Feature engineering started at {datetime.now().strftime('%H:%M:%S')}")
        
        # Ensure required columns exist
        logger.info("Ensuring required columns exist...")
        df = self._ensure_required_columns(df)
        
        # Sort by timestamp
        logger.info("Sorting DataFrame by timestamp...")
        df = df.sort_values('ts_event').reset_index(drop=True)
        
        # Initialize result DataFrame
        logger.info("Initializing result DataFrame...")
        result_df = df.copy()
        
        # Process events sequentially to maintain state consistency
        logger.info(f"Processing {len(df):,} events sequentially...")
        all_features = []
        
        total_rows = len(df)
        progress_interval = max(1, total_rows // 100)  # Log every 1% of progress
        
        for idx, row in df.iterrows():
            # Progress logging
            if idx % progress_interval == 0:
                progress_pct = (idx / total_rows) * 100
                elapsed_time = time.time() - start_time
                if progress_pct > 0:
                    estimated_total = elapsed_time / (progress_pct / 100)
                    remaining_time = estimated_total - elapsed_time
                    logger.info(f"Processing row {idx:,}/{total_rows:,} ({progress_pct:.1f}%) - Event: {row.get('action', 'UNKNOWN')} at price {row.get('price', 0)} - Elapsed: {elapsed_time:.1f}s, ETA: {remaining_time:.1f}s")
                else:
                    logger.info(f"Processing row {idx:,}/{total_rows:,} ({progress_pct:.1f}%) - Event: {row.get('action', 'UNKNOWN')} at price {row.get('price', 0)}")
            
            # Handle missing columns gracefully
            ts_recv = row.get('ts_recv', row.get('ts_event', 0))  # Fallback to ts_event if ts_recv missing
            instrument = row.get('instrument', row.get('symbol', 'UNKNOWN'))  # Fallback to symbol if instrument missing
            
            # Ensure numeric types
            try:
                ts_recv = int(ts_recv) if ts_recv is not None else 0
            except (ValueError, TypeError):
                ts_recv = 0
            
            try:
                order_id = int(row['order_id']) if row['order_id'] is not None else 0
            except (ValueError, TypeError):
                order_id = 0
            
            try:
                price = float(row['price']) if row['price'] is not None else 0.0
            except (ValueError, TypeError):
                price = 0.0
            
            try:
                size = int(row['size']) if row['size'] is not None else 0
            except (ValueError, TypeError):
                size = 0
            
            try:
                flags = int(row.get('flags', 0)) if row.get('flags') is not None else 0
            except (ValueError, TypeError):
                flags = 0
            
            try:
                sequence = int(row.get('sequence', idx)) if row.get('sequence') is not None else idx
            except (ValueError, TypeError):
                sequence = idx
                
            features = self.engine.process_event(
                ts_event=row['ts_event'],
                ts_recv=ts_recv,
                action=row['action'],
                side=row['side'],
                order_id=order_id,
                price=price,
                size=size,
                flags=flags,
                sequence=sequence,
                instrument=instrument
            )
            all_features.append(features)
        
        total_time = time.time() - start_time
        logger.info(f"Completed processing {len(df):,} events in {total_time:.1f} seconds, converting to DataFrame...")
        
        # Convert to DataFrame
        features_df = pd.DataFrame(all_features)
        
        logger.info(f"Features DataFrame created with {len(features_df):,} rows and {len(features_df.columns)} columns")
        
        # Remove duplicate columns from features_df that already exist in result_df
        existing_columns = set(result_df.columns)
        features_df = features_df.drop(columns=[col for col in features_df.columns if col in existing_columns])
        
        logger.info(f"Removed {len(existing_columns)} duplicate columns, merging DataFrames...")
        
        # Merge with original DataFrame
        result_df = pd.concat([result_df, features_df], axis=1)
        
        final_time = time.time() - start_time
        logger.info(f"Feature computation complete: {len(result_df):,} rows, {len(result_df.columns)} total columns in {final_time:.1f} seconds")
        
        return result_df


# Global feature engine
_feature_engine = None

def get_feature_engine(feature_set: FeatureSet = FeatureSet.BASIC,
                      normalization_type: NormalizationType = NormalizationType.TICK_RELATIVE) -> FeatureEngine:
    """Get global feature engine."""
    global _feature_engine
    if _feature_engine is None or _feature_engine.feature_set != feature_set:
        _feature_engine = FeatureEngine(feature_set, normalization_type)
    return _feature_engine


def compute_mbo_features(df: pd.DataFrame,
                        feature_set: FeatureSet = FeatureSet.BASIC,
                        normalization_type: NormalizationType = NormalizationType.TICK_RELATIVE,
                        intensity_level: str = "medium") -> pd.DataFrame:
    """Compute features for MBO DataFrame."""
    engine = BatchFeatureEngine(feature_set, normalization_type)
    return engine.compute_features(df)
