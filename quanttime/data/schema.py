"""
Unified Data Schema System for QuantTime MBO L3 Pipeline.

This module defines the canonical schemas for raw MBO data, normalized data,
and different feature engineering types. It provides a unified interface
for data type management across the entire pipeline.
"""

import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ActionType(enum.Enum):
    """MBO action types."""
    # Databento single-character codes
    ADD = "A"          # Insert new order into book
    MODIFY = "M"       # Change order's price and/or size
    CANCEL = "C"       # Fully or partially cancel order from book
    CLEAR = "R"        # Remove all resting orders for instrument
    TRADE = "T"        # Aggressing order traded (doesn't affect book)
    FILL = "F"         # Resting order was filled (doesn't affect book)
    NONE = "N"         # No action (may carry flags or other information)
    
    # Legacy full-word mappings for backward compatibility
    ADD_FULL = "ADD"
    MODIFY_FULL = "MODIFY"
    CANCEL_FULL = "CANCEL"
    EXECUTE_FULL = "EXECUTE"
    
    @classmethod
    def from_databento(cls, action: str) -> 'ActionType':
        """Convert Databento action code to ActionType enum."""
        # Direct mapping for single-character codes
        if action == 'A':
            return cls.ADD
        elif action == 'M':
            return cls.MODIFY
        elif action == 'C':
            return cls.CANCEL
        elif action == 'R':
            return cls.CLEAR
        elif action == 'T':
            return cls.TRADE
        elif action == 'F':
            return cls.FILL
        elif action == 'N':
            return cls.NONE
        # Legacy full-word mappings
        elif action == 'ADD':
            return cls.ADD
        elif action == 'MODIFY':
            return cls.MODIFY
        elif action == 'CANCEL':
            return cls.CANCEL
        elif action == 'EXECUTE':
            return cls.FILL  # Map EXECUTE to FILL
        else:
            # Default to NONE for unknown actions
            logger.warning(f"Unknown action type: {action}, defaulting to NONE")
            return cls.NONE
    
    @classmethod
    def validate_databento_data(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate Databento MBO DataFrame for action/side consistency."""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'action_counts': {},
            'side_counts': {},
            'invalid_actions': [],
            'invalid_sides': []
        }
        
        if 'action' in df.columns:
            action_counts = df['action'].value_counts().to_dict()
            validation_result['action_counts'] = action_counts
            
            # Check for invalid actions
            valid_actions = {'A', 'M', 'C', 'R', 'T', 'F', 'N'}
            invalid_actions = set(df['action'].unique()) - valid_actions
            if invalid_actions:
                validation_result['invalid_actions'] = list(invalid_actions)
                validation_result['warnings'].append(f"Found invalid actions: {invalid_actions}")
        
        if 'side' in df.columns:
            side_counts = df['side'].value_counts().to_dict()
            validation_result['side_counts'] = side_counts
            
            # Check for invalid sides
            valid_sides = {'B', 'A', 'N'}
            invalid_sides = set(df['side'].unique()) - valid_sides
            if invalid_sides:
                validation_result['invalid_sides'] = list(invalid_sides)
                validation_result['warnings'].append(f"Found invalid sides: {invalid_sides}")
        
        # Check for required columns
        required_columns = ['ts_event', 'action', 'side', 'order_id', 'price', 'size']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            validation_result['errors'].append(f"Missing required columns: {missing_columns}")
            validation_result['valid'] = False
        
        return validation_result


class SideType(enum.Enum):
    """Order side types."""
    # Databento single-character codes
    BID = "B"      # Buy side (bid)
    ASK = "A"      # Ask side (sell)
    NONE = "N"     # No side specified
    
    # Legacy full-word mappings for backward compatibility
    BID_FULL = "BID"
    ASK_FULL = "ASK"
    
    @classmethod
    def from_databento(cls, side: str) -> 'SideType':
        """Convert Databento side code to SideType enum."""
        # Direct mapping for single-character codes
        if side == 'B':
            return cls.BID
        elif side == 'A':
            return cls.ASK
        elif side == 'N':
            return cls.NONE
        # Legacy full-word mappings
        elif side == 'BID':
            return cls.BID
        elif side == 'ASK':
            return cls.ASK
        else:
            # Default to NONE for unknown sides
            logger.warning(f"Unknown side type: {side}, defaulting to NONE")
            return cls.NONE
    
    @classmethod
    def validate_databento_data(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate Databento MBO DataFrame for side consistency."""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'side_counts': {},
            'invalid_sides': []
        }
        
        if 'side' in df.columns:
            side_counts = df['side'].value_counts().to_dict()
            validation_result['side_counts'] = side_counts
            
            # Check for invalid sides
            valid_sides = {'B', 'A', 'N'}
            invalid_sides = set(df['side'].unique()) - valid_sides
            if invalid_sides:
                validation_result['invalid_sides'] = list(invalid_sides)
                validation_result['warnings'].append(f"Found invalid sides: {invalid_sides}")
        
        return validation_result


class DataType(enum.Enum):
    """Data type categories."""
    RAW = "raw"
    NORMALIZED = "normalized"
    FEATURE_ENGINEERED = "feature_engineered"
    HYBRID = "hybrid"


class NormalizationType(enum.Enum):
    """Normalization types."""
    TICK_RELATIVE = "tick_relative"
    LOG_NORMALIZED = "log_normalized"
    Z_SCORE = "z_score"
    MIN_MAX = "min_max"
    ROBUST = "robust"


class FeatureSet(enum.Enum):
    """Feature engineering sets."""
    BASIC = "basic"  # Core L3 features
    ADVANCED = "advanced"  # Advanced L3 features
    MULTI_SCALE = "multi_scale"  # Multi-scale features
    COMPREHENSIVE = "comprehensive"  # All features


class FeatureIntensity(enum.Enum):
    """Feature engineering intensity levels."""
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"
    EXTREME = "extreme"


@dataclass
class SchemaVersion:
    """Schema version information."""
    version: str
    description: str
    created_date: datetime
    data_type: DataType
    normalization_type: Optional[NormalizationType] = None
    feature_set: Optional[FeatureSet] = None
    features: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CanonicalMBOEvent:
    """Canonical MBO event structure."""
    ts_event: int  # Exchange event timestamp (nanoseconds)
    ts_recv: int  # Receiver timestamp (nanoseconds)
    action: ActionType
    side: SideType
    order_id: int
    price: float  # Raw exchange units
    size: int  # Remaining size
    flags: int  # Bitfield (hidden, iceberg, priority, etc.)
    sequence: int  # Exchange sequence number
    instrument: str  # Symbol identifier
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'ts_event': self.ts_event,
            'ts_recv': self.ts_recv,
            'action': self.action.value,
            'side': self.side.value,
            'order_id': self.order_id,
            'price': self.price,
            'size': self.size,
            'flags': self.flags,
            'sequence': self.sequence,
            'instrument': self.instrument
        }


class UnifiedDataSchema:
    """
    Unified data schema system for MBO L3 pipeline.
    
    Manages schemas for different data types, normalization methods,
    and feature engineering sets.
    """
    
    def __init__(self):
        """Initialize schema system."""
        self.schemas: Dict[str, SchemaVersion] = {}
        self._initialize_default_schemas()
    
    def _initialize_default_schemas(self):
        """Initialize default schemas."""
        # Raw MBO Schema
        raw_schema = SchemaVersion(
            version="1.0.0",
            description="Raw MBO events from Databento DBN files",
            created_date=datetime.now(),
            data_type=DataType.RAW,
            features=[
                'ts_event', 'ts_recv', 'action', 'side', 'order_id',
                'price', 'size', 'flags', 'sequence', 'instrument'
            ]
        )
        self.register_schema("raw_mbo_v1", raw_schema)
        
        # Basic Normalized Schema
        basic_normalized = SchemaVersion(
            version="1.0.0",
            description="Basic normalized MBO features",
            created_date=datetime.now(),
            data_type=DataType.NORMALIZED,
            normalization_type=NormalizationType.TICK_RELATIVE,
            feature_set=FeatureSet.BASIC,
            features=[
                'ts_event', 'ts_recv', 'action', 'side', 'order_id',
                'price_norm', 'size_norm', 'flags', 'sequence', 'instrument',
                'midprice', 'spread_ticks', 'depth_bid_norm', 'depth_ask_norm',
                'ofi_norm', 'queue_fraction', 'time_delta_norm'
            ]
        )
        self.register_schema("basic_normalized_v1", basic_normalized)
        
        # Advanced Feature Engineered Schema
        advanced_features = SchemaVersion(
            version="1.0.0",
            description="Advanced L3 features with multi-scale normalization",
            created_date=datetime.now(),
            data_type=DataType.FEATURE_ENGINEERED,
            normalization_type=NormalizationType.LOG_NORMALIZED,
            feature_set=FeatureSet.ADVANCED,
            features=[
                'ts_event', 'ts_recv', 'action', 'side', 'order_id',
                'price_norm', 'size_norm', 'flags', 'sequence', 'instrument',
                'midprice', 'spread_ticks', 'depth_bid_norm', 'depth_ask_norm',
                'ofi_norm', 'queue_fraction', 'time_delta_norm',
                'top_k_queue_snapshot', 'lob_image', 'event_tokens',
                'patch_diffs', 'microstructure_indicators',
                'ofi_fast', 'ofi_medium', 'ofi_slow',
                'volatility_estimate', 'cancel_modify_ratio'
            ]
        )
        self.register_schema("advanced_features_v1", advanced_features)
        
        # Execution-Aware Multi-Horizon Schema (Light)
        execution_aware_light = SchemaVersion(
            version="1.0.0",
            description="Light execution-aware features - CORE ESSENTIAL features only",
            created_date=datetime.now(),
            data_type=DataType.FEATURE_ENGINEERED,
            normalization_type=NormalizationType.TICK_RELATIVE,
            feature_set=FeatureSet.BASIC,
            features=[
                # Base MBO data (10 features)
                'ts_event', 'ts_recv', 'action', 'side', 'order_id',
                'price', 'size', 'flags', 'sequence', 'instrument',
                
                # Core processing (3 features)
                'midprice', 'price_norm', 'size_norm',
                
                # Essential L3 features (6 features)
                'spread_ticks', 'depth_bid_norm', 'depth_ask_norm',
                'ofi_norm', 'queue_fraction', 'time_delta_norm',
                
                # Core execution features (6 features)
                'buy_volume', 'sell_volume', 'delta', 'delta_ratio',
                'session_delta', 'vwap_mid',
                
                # Essential multi-horizon (3 horizons × 3 features = 9 features)
                '1s_delta', '1s_volume', '1s_price_change',
                '1m_delta', '1m_volume', '1m_price_change', 
                '5m_delta', '5m_volume', '5m_price_change',
                
                # Core time features (6 features)
                'hour', 'minute', 'market_session', 'is_market_open', 'weekday', 'session_progress',
                
                # Essential momentum (4 features)
                'delta_momentum_1s_1m', 'ofi_fast', 'volatility_estimate', 'price_momentum'
            ]
        )
        self.register_schema("execution_aware_light_v1", execution_aware_light)

        # Execution-Aware Multi-Horizon Schema (Medium)
        execution_aware_medium = SchemaVersion(
            version="1.0.0",
            description="Medium execution-aware features - BALANCED analysis with expanded orderflow",
            created_date=datetime.now(),
            data_type=DataType.FEATURE_ENGINEERED,
            normalization_type=NormalizationType.TICK_RELATIVE,
            feature_set=FeatureSet.ADVANCED,
            features=[
                # ALL LIGHT FEATURES (47 features) +
                'ts_event', 'ts_recv', 'action', 'side', 'order_id',
                'price', 'size', 'flags', 'sequence', 'instrument',
                'midprice', 'price_norm', 'size_norm',
                'spread_ticks', 'depth_bid_norm', 'depth_ask_norm',
                'ofi_norm', 'queue_fraction', 'time_delta_norm',
                'buy_volume', 'sell_volume', 'delta', 'delta_ratio',
                'session_delta', 'vwap_mid',
                '1s_delta', '1s_volume', '1s_price_change',
                '1m_delta', '1m_volume', '1m_price_change', 
                '5m_delta', '5m_volume', '5m_price_change',
                'hour', 'minute', 'market_session', 'is_market_open', 'weekday', 'session_progress',
                'delta_momentum_1s_1m', 'ofi_fast', 'volatility_estimate', 'price_momentum',
                
                # EXPANDED execution features (12 features)
                'aggressive_buy_volume', 'aggressive_sell_volume',
                'passive_buy_volume', 'passive_sell_volume',
                'absorption_events_1m', 'exhaustion_events_1m',
                'imbalance_adjusted_mid', 'execution_weighted_mid',
                'buy_velocity', 'sell_velocity', 'net_flow_1m', 'avg_order_size_1m',
                
                # EXPANDED multi-horizon (6 horizons × 4 features = 24 features)
                '100ms_delta', '100ms_volume', '100ms_price_change', '100ms_volatility',
                '10s_delta', '10s_volume', '10s_price_change', '10s_volatility',
                '20m_delta', '20m_volume', '20m_price_change', '20m_volatility',
                '1h_delta', '1h_volume', '1h_price_change', '1h_volatility',
                '1s_cumulative_delta', '1m_cumulative_delta', '5m_cumulative_delta', '20m_cumulative_delta',
                '1s_spread', '1m_spread', '5m_spread', '20m_spread',
                
                # BASIC microstructure (8 features)
                'price_momentum_1m', 'volume_ratio', 'price_efficiency',
                'large_trade_ratio', 'bid_ask_imbalance_ratio',
                'order_flow_imbalance', 'depth_weighted_imbalance', 'liquidity_replenishment_rate',
                
                # BASIC technical indicators (7 features)
                'rsi', 'macd', 'ema_short', 'ema_long', 'bollinger_position',
                'price_volatility', 'volume_momentum',
                
                # CROSS-horizon momentum (4 features)
                'delta_momentum_1m_20m', 'volume_acceleration_ratio',
                'ofi_medium', 'ofi_slow'
            ]
        )
        self.register_schema("execution_aware_medium_v1", execution_aware_medium)

        # Execution-Aware Multi-Horizon Schema (Heavy)
        execution_aware_heavy = SchemaVersion(
            version="1.0.0",
            description="Heavy execution-aware features - COMPREHENSIVE analysis with advanced engineering",
            created_date=datetime.now(),
            data_type=DataType.FEATURE_ENGINEERED,
            normalization_type=NormalizationType.TICK_RELATIVE,
            feature_set=FeatureSet.MULTI_SCALE,
            features=[
                # ALL MEDIUM FEATURES (102 features) +
                'ts_event', 'ts_recv', 'action', 'side', 'order_id',
                'price', 'size', 'flags', 'sequence', 'instrument',
                'midprice', 'price_norm', 'size_norm',
                'spread_ticks', 'depth_bid_norm', 'depth_ask_norm',
                'ofi_norm', 'queue_fraction', 'time_delta_norm',
                'buy_volume', 'sell_volume', 'delta', 'delta_ratio',
                'session_delta', 'vwap_mid',
                '1s_delta', '1s_volume', '1s_price_change',
                '1m_delta', '1m_volume', '1m_price_change', 
                '5m_delta', '5m_volume', '5m_price_change',
                'hour', 'minute', 'market_session', 'is_market_open', 'weekday', 'session_progress',
                'delta_momentum_1s_1m', 'ofi_fast', 'volatility_estimate', 'price_momentum',
                'aggressive_buy_volume', 'aggressive_sell_volume',
                'passive_buy_volume', 'passive_sell_volume',
                'absorption_events_1m', 'exhaustion_events_1m',
                'imbalance_adjusted_mid', 'execution_weighted_mid',
                'buy_velocity', 'sell_velocity', 'net_flow_1m', 'avg_order_size_1m',
                '100ms_delta', '100ms_volume', '100ms_price_change', '100ms_volatility',
                '10s_delta', '10s_volume', '10s_price_change', '10s_volatility',
                '20m_delta', '20m_volume', '20m_price_change', '20m_volatility',
                '1h_delta', '1h_volume', '1h_price_change', '1h_volatility',
                '1s_cumulative_delta', '1m_cumulative_delta', '5m_cumulative_delta', '20m_cumulative_delta',
                '1s_spread', '1m_spread', '5m_spread', '20m_spread',
                'price_momentum_1m', 'volume_ratio', 'price_efficiency',
                'large_trade_ratio', 'bid_ask_imbalance_ratio',
                'order_flow_imbalance', 'depth_weighted_imbalance', 'liquidity_replenishment_rate',
                'rsi', 'macd', 'ema_short', 'ema_long', 'bollinger_position',
                'price_volatility', 'volume_momentum',
                'delta_momentum_1m_20m', 'volume_acceleration_ratio',
                'ofi_medium', 'ofi_slow',
                
                # ADVANCED multi-horizon (10 horizons × 5 features = 50 features)
                '10ms_delta', '10ms_volume', '10ms_price_change', '10ms_volatility', '10ms_cumulative_delta',
                '50ms_delta', '50ms_volume', '50ms_price_change', '50ms_volatility', '50ms_cumulative_delta',
                '500ms_delta', '500ms_volume', '500ms_price_change', '500ms_volatility', '500ms_cumulative_delta',
                '3s_delta', '3s_volume', '3s_price_change', '3s_volatility', '3s_cumulative_delta',
                '30s_delta', '30s_volume', '30s_price_change', '30s_volatility', '30s_cumulative_delta',
                '2m_delta', '2m_volume', '2m_price_change', '2m_volatility', '2m_cumulative_delta',
                '10m_delta', '10m_volume', '10m_price_change', '10m_volatility', '10m_cumulative_delta',
                '30m_delta', '30m_volume', '30m_price_change', '30m_volatility', '30m_cumulative_delta',
                '2h_delta', '2h_volume', '2h_price_change', '2h_volatility', '2h_cumulative_delta',
                '4h_delta', '4h_volume', '4h_price_change', '4h_volatility', '4h_cumulative_delta',
                
                # ADVANCED microstructure & orderbook features (16 features)
                'depth_imbalance_1', 'depth_imbalance_3', 'depth_imbalance_5', 'depth_imbalance_10',
                'market_impact_curve', 'quote_stability', 'cancel_modify_ratio',
                'absorption_strength', 'liquidity_void_zones', 'aggression_surges',
                'momentum_exhaustion', 'delta_pressure_gradient', 'vwap_dev',
                'mom_divergence', 'cumulative_delta', 'flow_persistence',
                
                # ADVANCED technical indicators (11 features)
                'bollinger_upper', 'bollinger_lower', 'atr', 'stoch_k', 'stoch_d',
                'williams_r', 'cci', 'mfi', 'adx', 'aroon_up', 'aroon_down',
                
                # ADVANCED time features (5 features)
                'second', 'time_decimal', 'is_monday', 'is_friday', 'is_weekend',
                
                # CROSS-horizon momentum & divergence (8 features)
                'delta_momentum_10s_5m', 'delta_momentum_5m_1h', 'delta_momentum_50ms_1s',
                'delta_divergence_1s_1h', 'delta_divergence_10s_30m', 'volume_acceleration_short',
                'volume_acceleration_medium', 'volume_acceleration_long'
            ]
        )
        self.register_schema("execution_aware_heavy_v1", execution_aware_heavy)

        # Execution-Aware Multi-Horizon Schema (Extreme)
        execution_aware_extreme = SchemaVersion(
            version="1.0.0",
            description="EXTREME execution-aware features - ALL FEATURES from ALL modules including ultra-microstructure",
            created_date=datetime.now(),
            data_type=DataType.FEATURE_ENGINEERED,
            normalization_type=NormalizationType.TICK_RELATIVE,
            feature_set=FeatureSet.COMPREHENSIVE,
            features=[
                # ALL HEAVY FEATURES (192 features) +
                'ts_event', 'ts_recv', 'action', 'side', 'order_id',
                'price', 'size', 'flags', 'sequence', 'instrument',
                'midprice', 'price_norm', 'size_norm',
                'spread_ticks', 'depth_bid_norm', 'depth_ask_norm',
                'ofi_norm', 'queue_fraction', 'time_delta_norm',
                'buy_volume', 'sell_volume', 'delta', 'delta_ratio',
                'session_delta', 'vwap_mid',
                '1s_delta', '1s_volume', '1s_price_change',
                '1m_delta', '1m_volume', '1m_price_change', 
                '5m_delta', '5m_volume', '5m_price_change',
                'hour', 'minute', 'market_session', 'is_market_open', 'weekday', 'session_progress',
                'delta_momentum_1s_1m', 'ofi_fast', 'volatility_estimate', 'price_momentum',
                'aggressive_buy_volume', 'aggressive_sell_volume',
                'passive_buy_volume', 'passive_sell_volume',
                'absorption_events_1m', 'exhaustion_events_1m',
                'imbalance_adjusted_mid', 'execution_weighted_mid',
                'buy_velocity', 'sell_velocity', 'net_flow_1m', 'avg_order_size_1m',
                '100ms_delta', '100ms_volume', '100ms_price_change', '100ms_volatility',
                '10s_delta', '10s_volume', '10s_price_change', '10s_volatility',
                '20m_delta', '20m_volume', '20m_price_change', '20m_volatility',
                '1h_delta', '1h_volume', '1h_price_change', '1h_volatility',
                '1s_cumulative_delta', '1m_cumulative_delta', '5m_cumulative_delta', '20m_cumulative_delta',
                '1s_spread', '1m_spread', '5m_spread', '20m_spread',
                'price_momentum_1m', 'volume_ratio', 'price_efficiency',
                'large_trade_ratio', 'bid_ask_imbalance_ratio',
                'order_flow_imbalance', 'depth_weighted_imbalance', 'liquidity_replenishment_rate',
                'rsi', 'macd', 'ema_short', 'ema_long', 'bollinger_position',
                'price_volatility', 'volume_momentum',
                'delta_momentum_1m_20m', 'volume_acceleration_ratio',
                'ofi_medium', 'ofi_slow',
                '10ms_delta', '10ms_volume', '10ms_price_change', '10ms_volatility', '10ms_cumulative_delta',
                '50ms_delta', '50ms_volume', '50ms_price_change', '50ms_volatility', '50ms_cumulative_delta',
                '500ms_delta', '500ms_volume', '500ms_price_change', '500ms_volatility', '500ms_cumulative_delta',
                '3s_delta', '3s_volume', '3s_price_change', '3s_volatility', '3s_cumulative_delta',
                '30s_delta', '30s_volume', '30s_price_change', '30s_volatility', '30s_cumulative_delta',
                '2m_delta', '2m_volume', '2m_price_change', '2m_volatility', '2m_cumulative_delta',
                '10m_delta', '10m_volume', '10m_price_change', '10m_volatility', '10m_cumulative_delta',
                '30m_delta', '30m_volume', '30m_price_change', '30m_volatility', '30m_cumulative_delta',
                '2h_delta', '2h_volume', '2h_price_change', '2h_volatility', '2h_cumulative_delta',
                '4h_delta', '4h_volume', '4h_price_change', '4h_volatility', '4h_cumulative_delta',
                'depth_imbalance_1', 'depth_imbalance_3', 'depth_imbalance_5', 'depth_imbalance_10',
                'market_impact_curve', 'quote_stability', 'cancel_modify_ratio',
                'absorption_strength', 'liquidity_void_zones', 'aggression_surges',
                'momentum_exhaustion', 'delta_pressure_gradient', 'vwap_dev',
                'mom_divergence', 'cumulative_delta', 'flow_persistence',
                'bollinger_upper', 'bollinger_lower', 'atr', 'stoch_k', 'stoch_d',
                'williams_r', 'cci', 'mfi', 'adx', 'aroon_up', 'aroon_down',
                'second', 'time_decimal', 'is_monday', 'is_friday', 'is_weekend',
                'delta_momentum_10s_5m', 'delta_momentum_5m_1h', 'delta_momentum_50ms_1s',
                'delta_divergence_1s_1h', 'delta_divergence_10s_30m', 'volume_acceleration_short',
                'volume_acceleration_medium', 'volume_acceleration_long',
                
                # ULTRA-MICROSTRUCTURE FEATURES (69 features from microstructure_features.py)
                'micro_aggression_ratio_10e', 'micro_aggression_ratio_25e', 'micro_aggression_ratio_50e',
                'micro_aggression_ratio_100e', 'micro_aggression_ratio_200e', 'micro_aggression_ratio_500e',
                'micro_buy_ratio_10e', 'micro_buy_ratio_25e', 'micro_buy_ratio_50e',
                'micro_buy_ratio_100e', 'micro_buy_ratio_200e', 'micro_buy_ratio_500e',
                'micro_volume_intensity_10e', 'micro_volume_intensity_25e', 'micro_volume_intensity_50e',
                'micro_volume_intensity_100e', 'micro_volume_intensity_200e', 'micro_volume_intensity_500e',
                'micro_price_volatility_10e', 'micro_price_volatility_25e', 'micro_price_volatility_50e',
                'micro_price_volatility_100e', 'micro_price_volatility_200e', 'micro_price_volatility_500e',
                'micro_large_order_freq_10e', 'micro_large_order_freq_25e', 'micro_large_order_freq_50e',
                'micro_large_order_freq_100e', 'micro_large_order_freq_200e', 'micro_large_order_freq_500e',
                'micro_price_momentum_10e', 'micro_tick_direction', 'micro_tick_momentum_50e',
                'micro_time_since_last', 'micro_event_rate',
                'micro_queue_position_advantage', 'micro_queue_depth_ratio', 'micro_ahead_in_queue',
                'micro_book_dominance_flip', 'micro_level_concentration',
                'micro_liquidity_pulled_volume', 'micro_void_creation_speed', 'micro_void_probability',
                'micro_book_flip_intensity', 'micro_level_flip_rate', 'micro_dominance_reversal',
                'micro_liquidity_momentum',
                'micro_spoof_probability', 'micro_fake_liquidity_ratio', 'micro_manipulation_score',
                'micro_order_lifecycle_suspicion',
                'micro_sweep_probability', 'micro_sweep_depth_levels', 'micro_sweep_intensity',
                'micro_multi_level_consumption', 'micro_recent_sweep_count', 'micro_sweep_volume_rate',
                'micro_sequence_momentum', 'micro_aggressive_sequence_length', 'micro_size_escalation',
                'micro_sequence_urgency', 'micro_momentum_acceleration', 'micro_urgency_trend',
                'micro_flow_intensity_100us', 'micro_flow_intensity_1ms', 'micro_flow_intensity_10ms',
                'micro_flow_burst_ratio', 'micro_flow_density_change', 'micro_adaptive_window',
                
                # ORDERFLOW CLASSIFICATION FEATURES (11 features from orderflow_classification.py)
                'flow_toxicity_score', 'toxic_flow_ratio', 'benign_flow_ratio',
                'information_content', 'adverse_selection_risk', 'flow_persistence',
                'timing_sophistication', 'venue_coordination', 'size_aggressiveness',
                'institutional_flow_score', 'market_maker_flow_score',
                
                # COMPREHENSIVE ORDER FLOW FEATURES (additional advanced features)
                'execution_cluster_strength', 'execution_cluster_migration', 'execution_cluster_persistence',
                'aggressor_size_distribution', 'aggressor_frequency', 'aggressor_persistence',
                'liquidity_resilience', 'large_order_fragmentation', 'institutional_flow_strength',
                'iceberg_detection', 'flow_autocorrelation', 'flow_predictability', 'flow_exhaustion_signals',
                
                # REGIME & ADVANCED PATTERN FEATURES
                'volatility_regime', 'regime_transition_probability', 'regime_persistence',
                'liquidity_regime', 'liquidity_stress_indicators', 'liquidity_recovery_signals',
                'pattern_momentum_convergence', 'pattern_volume_surge', 'pattern_liquidity_trap',
                'pattern_breakout_strength', 'pattern_reversal_probability',
                
                # LATENCY & TIMING FEATURES (critical for extreme performance)
                'latency_adjusted_alpha', 'competitive_window_remaining', 'alpha_decay_rate',
                'processing_lag_impact', 'timing_advantage_score', 'decision_urgency_index'
            ]
        )
        self.register_schema("execution_aware_extreme_v1", execution_aware_extreme)
    
    def register_schema(self, name: str, schema: SchemaVersion):
        """Register a new schema version."""
        self.schemas[name] = schema
        logger.info(f"Registered schema: {name} - {schema.description}")
    
    def get_schema(self, name: str) -> Optional[SchemaVersion]:
        """Get schema by name."""
        return self.schemas.get(name)
    
    def list_schemas(self, data_type: Optional[DataType] = None) -> List[str]:
        """List available schemas, optionally filtered by data type."""
        schemas = []
        for name, schema in self.schemas.items():
            if data_type is None or schema.data_type == data_type:
                schemas.append(name)
        return sorted(schemas)
    
    def get_arrow_schema(self, schema_name: str) -> Optional[pa.Schema]:
        """Get PyArrow schema for a given schema version."""
        schema = self.get_schema(schema_name)
        if schema is None:
            return None
        
        # Define field types based on schema
        fields = []
        
        # Common fields
        fields.extend([
            pa.field('ts_event', pa.int64()),
            pa.field('ts_recv', pa.int64()),
            pa.field('action', pa.string()),
            pa.field('side', pa.string()),
            pa.field('order_id', pa.int64()),
            pa.field('flags', pa.int32()),
            pa.field('sequence', pa.int64()),
            pa.field('instrument', pa.string())
        ])
        
        # Add schema-specific fields
        for feature in schema.features:
            if feature == 'price_norm':
                fields.append(pa.field('price_norm', pa.float64()))
            elif feature == 'size_norm':
                fields.append(pa.field('size_norm', pa.float64()))
            elif feature == 'price':
                fields.append(pa.field('price', pa.float64()))
            elif feature == 'size':
                fields.append(pa.field('size', pa.int32()))
            elif feature == 'midprice':
                fields.append(pa.field('midprice', pa.float64()))
            elif feature == 'spread_ticks':
                fields.append(pa.field('spread_ticks', pa.int32()))
            elif feature == 'depth_bid_norm':
                fields.append(pa.field('depth_bid_norm', pa.list_(pa.float64())))
            elif feature == 'depth_ask_norm':
                fields.append(pa.field('depth_ask_norm', pa.list_(pa.float64())))
            elif feature == 'ofi_norm':
                fields.append(pa.field('ofi_norm', pa.float64()))
            elif feature == 'queue_fraction':
                fields.append(pa.field('queue_fraction', pa.float64()))
            elif feature == 'time_delta_norm':
                fields.append(pa.field('time_delta_norm', pa.float64()))
            elif feature == 'top_k_queue_snapshot':
                fields.append(pa.field('top_k_queue_snapshot', pa.list_(pa.float64())))
            elif feature == 'lob_image':
                fields.append(pa.field('lob_image', pa.list_(pa.float64())))
            elif feature == 'event_tokens':
                fields.append(pa.field('event_tokens', pa.list_(pa.int32())))
            elif feature == 'patch_diffs':
                fields.append(pa.field('patch_diffs', pa.list_(pa.float64())))
            elif feature == 'microstructure_indicators':
                fields.append(pa.field('microstructure_indicators', pa.list_(pa.float64())))
            elif feature == 'ofi_fast':
                fields.append(pa.field('ofi_fast', pa.float64()))
            elif feature == 'ofi_medium':
                fields.append(pa.field('ofi_medium', pa.float64()))
            elif feature == 'ofi_slow':
                fields.append(pa.field('ofi_slow', pa.float64()))
            elif feature == 'volatility_estimate':
                fields.append(pa.field('volatility_estimate', pa.float64()))
            elif feature == 'cancel_modify_ratio':
                fields.append(pa.field('cancel_modify_ratio', pa.float64()))
        
        return pa.schema(fields)
    
    def get_data_type_info(self, schema_name: str) -> Dict[str, Any]:
        """Get comprehensive data type information."""
        schema = self.get_schema(schema_name)
        if schema is None:
            return {}
        
        return {
            'name': schema_name,
            'version': schema.version,
            'description': schema.description,
            'data_type': schema.data_type.value,
            'normalization_type': schema.normalization_type.value if schema.normalization_type else None,
            'feature_set': schema.feature_set.value if schema.feature_set else None,
            'features': schema.features,
            'created_date': schema.created_date.isoformat(),
            'metadata': schema.metadata
        }


# Global schema instance
_unified_schema = None

def get_unified_schema() -> UnifiedDataSchema:
    """Get global unified schema instance."""
    global _unified_schema
    if _unified_schema is None:
        _unified_schema = UnifiedDataSchema()
    return _unified_schema


def get_schema_info(schema_name: str) -> Dict[str, Any]:
    """Get schema information for a given schema name."""
    schema = get_unified_schema()
    return schema.get_data_type_info(schema_name)


def list_available_schemas(data_type: Optional[DataType] = None) -> List[str]:
    """List available schemas."""
    schema = get_unified_schema()
    return schema.list_schemas(data_type)


def get_arrow_schema(schema_name: str) -> Optional[pa.Schema]:
    """Get PyArrow schema for a given schema name."""
    schema = get_unified_schema()
    return schema.get_arrow_schema(schema_name)
