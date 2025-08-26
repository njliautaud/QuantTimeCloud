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
            description="Light execution-aware features with core multi-horizon analysis",
            created_date=datetime.now(),
            data_type=DataType.FEATURE_ENGINEERED,
            normalization_type=NormalizationType.TICK_RELATIVE,
            feature_set=FeatureSet.ADVANCED,
            features=[
                # Base MBO data
                'ts_event', 'ts_recv', 'action', 'side', 'order_id',
                'price', 'size', 'flags', 'sequence', 'instrument',
                'midprice', 'price_norm', 'size_norm',
                
                # Basic L3 features
                'spread_ticks', 'depth_bid_norm', 'depth_ask_norm',
                'ofi_norm', 'queue_fraction', 'time_delta_norm',
                
                # Core execution-aware features
                'buy_volume', 'sell_volume', 'delta', 'delta_ratio',
                'session_delta', 'absorption_events_1m', 'exhaustion_events_1m',
                
                # Fair value features
                'vwap_mid', 'imbalance_adjusted_mid',
                
                # Key multi-horizon features (4 main horizons)
                '1s_buy_volume', '1s_sell_volume', '1s_total_volume', '1s_delta', '1s_delta_ratio',
                '1m_buy_volume', '1m_sell_volume', '1m_total_volume', '1m_delta', '1m_delta_ratio',
                '5m_buy_volume', '5m_sell_volume', '5m_total_volume', '5m_delta', '5m_delta_ratio',
                '20m_buy_volume', '20m_sell_volume', '20m_total_volume', '20m_delta', '20m_delta_ratio',
                
                # Key cumulative delta
                '1s_cumulative_delta', '1m_cumulative_delta', '5m_cumulative_delta', '20m_cumulative_delta',
                
                # Key price and volatility
                '1s_price_change', '1m_price_change', '5m_price_change', '20m_price_change',
                '1s_volatility', '1m_volatility', '5m_volatility', '20m_volatility',
                
                # Key liquidity features
                '1s_average_spread', '1m_average_spread', '5m_average_spread', '20m_average_spread',
                '1s_depth_at_touch', '1m_depth_at_touch', '5m_depth_at_touch', '20m_depth_at_touch',
                
                # Core cross-horizon features
                'delta_momentum_1s_1m', 'delta_momentum_1m_20m',
                
                # Legacy features
                'ofi_fast', 'ofi_medium', 'ofi_slow', 'volatility_estimate', 'cancel_modify_ratio'
            ]
        )
        self.register_schema("execution_aware_light_v1", execution_aware_light)

        # Execution-Aware Multi-Horizon Schema (Medium)
        execution_aware_medium = SchemaVersion(
            version="1.0.0",
            description="Medium execution-aware features with expanded multi-horizon analysis",
            created_date=datetime.now(),
            data_type=DataType.FEATURE_ENGINEERED,
            normalization_type=NormalizationType.TICK_RELATIVE,
            feature_set=FeatureSet.ADVANCED,
            features=[
                # Base MBO data
                'ts_event', 'ts_recv', 'action', 'side', 'order_id',
                'price', 'size', 'flags', 'sequence', 'instrument',
                'midprice', 'price_norm', 'size_norm',
                
                # Basic L3 features
                'spread_ticks', 'depth_bid_norm', 'depth_ask_norm',
                'ofi_norm', 'queue_fraction', 'time_delta_norm',
                
                # Execution-aware features
                'buy_volume', 'sell_volume', 'aggressive_buy_volume', 'aggressive_sell_volume',
                'passive_buy_volume', 'passive_sell_volume', 'delta', 'delta_ratio',
                'session_delta', 'session_buy_volume', 'session_sell_volume',
                'absorption_events_1m', 'avg_absorption_ratio', 'exhaustion_events_1m',
                'last_execution_volume', 'last_execution_price', 'time_since_last_execution',
                
                # Fair value features
                'vwap_mid', 'imbalance_adjusted_mid', 'execution_weighted_mid',
                
                # Multi-horizon volume features (8 horizons)
                '10ms_buy_volume', '10ms_sell_volume', '10ms_total_volume', '10ms_delta', '10ms_delta_ratio',
                '100ms_buy_volume', '100ms_sell_volume', '100ms_total_volume', '100ms_delta', '100ms_delta_ratio',
                '1s_buy_volume', '1s_sell_volume', '1s_total_volume', '1s_delta', '1s_delta_ratio',
                '10s_buy_volume', '10s_sell_volume', '10s_total_volume', '10s_delta', '10s_delta_ratio',
                '1m_buy_volume', '1m_sell_volume', '1m_total_volume', '1m_delta', '1m_delta_ratio',
                '5m_buy_volume', '5m_sell_volume', '5m_total_volume', '5m_delta', '5m_delta_ratio',
                '20m_buy_volume', '20m_sell_volume', '20m_total_volume', '20m_delta', '20m_delta_ratio',
                '1h_buy_volume', '1h_sell_volume', '1h_total_volume', '1h_delta', '1h_delta_ratio',
                
                # Multi-horizon cumulative delta
                '10ms_cumulative_delta', '100ms_cumulative_delta', '1s_cumulative_delta', '10s_cumulative_delta',
                '1m_cumulative_delta', '5m_cumulative_delta', '20m_cumulative_delta', '1h_cumulative_delta',
                
                # Multi-horizon absorption/exhaustion events
                '10ms_absorption_events', '100ms_absorption_events', '1s_absorption_events', '10s_absorption_events',
                '1m_absorption_events', '5m_absorption_events', '20m_absorption_events', '1h_absorption_events',
                '10ms_exhaustion_events', '100ms_exhaustion_events', '1s_exhaustion_events', '10s_exhaustion_events',
                '1m_exhaustion_events', '5m_exhaustion_events', '20m_exhaustion_events', '1h_exhaustion_events',
                
                # Multi-horizon price and volatility
                '10ms_price_change', '100ms_price_change', '1s_price_change', '10s_price_change',
                '1m_price_change', '5m_price_change', '20m_price_change', '1h_price_change',
                '10ms_volatility', '100ms_volatility', '1s_volatility', '10s_volatility',
                '1m_volatility', '5m_volatility', '20m_volatility', '1h_volatility',
                
                # Multi-horizon liquidity features
                '10ms_average_spread', '100ms_average_spread', '1s_average_spread', '10s_average_spread',
                '1m_average_spread', '5m_average_spread', '20m_average_spread', '1h_average_spread',
                '10ms_depth_at_touch', '100ms_depth_at_touch', '1s_depth_at_touch', '10s_depth_at_touch',
                '1m_depth_at_touch', '5m_depth_at_touch', '20m_depth_at_touch', '1h_depth_at_touch',
                
                # Cross-horizon momentum and divergence features
                'delta_momentum_1s_1m', 'delta_momentum_1m_20m', 'volume_acceleration_ratio', 'delta_divergence_1s_1h',
                
                # Advanced features
                'top_k_queue_snapshot', 'lob_image', 'event_tokens', 'patch_diffs', 'microstructure_indicators',
                'ofi_fast', 'ofi_medium', 'ofi_slow', 'volatility_estimate', 'cancel_modify_ratio'
            ]
        )
        self.register_schema("execution_aware_medium_v1", execution_aware_medium)

        # Execution-Aware Multi-Horizon Schema (Heavy)
        execution_aware_heavy = SchemaVersion(
            version="1.0.0",
            description="Heavy execution-aware features with comprehensive multi-horizon analysis",
            created_date=datetime.now(),
            data_type=DataType.FEATURE_ENGINEERED,
            normalization_type=NormalizationType.TICK_RELATIVE,
            feature_set=FeatureSet.MULTI_SCALE,
            features=[
                # Base MBO data
                'ts_event', 'ts_recv', 'action', 'side', 'order_id',
                'price', 'size', 'flags', 'sequence', 'instrument',
                'midprice', 'price_norm', 'size_norm',
                
                # Basic L3 features
                'spread_ticks', 'depth_bid_norm', 'depth_ask_norm',
                'ofi_norm', 'queue_fraction', 'time_delta_norm',
                
                # Execution-aware features
                'buy_volume', 'sell_volume', 'aggressive_buy_volume', 'aggressive_sell_volume',
                'passive_buy_volume', 'passive_sell_volume', 'delta', 'delta_ratio',
                'session_delta', 'session_buy_volume', 'session_sell_volume',
                'absorption_events_1m', 'avg_absorption_ratio', 'exhaustion_events_1m',
                'last_execution_volume', 'last_execution_price', 'time_since_last_execution',
                
                # Fair value features
                'vwap_mid', 'imbalance_adjusted_mid', 'execution_weighted_mid',
                
                # Multi-horizon volume features (15 horizons)
                '10ms_buy_volume', '10ms_sell_volume', '10ms_total_volume', '10ms_delta', '10ms_delta_ratio',
                '50ms_buy_volume', '50ms_sell_volume', '50ms_total_volume', '50ms_delta', '50ms_delta_ratio',
                '100ms_buy_volume', '100ms_sell_volume', '100ms_total_volume', '100ms_delta', '100ms_delta_ratio',
                '500ms_buy_volume', '500ms_sell_volume', '500ms_total_volume', '500ms_delta', '500ms_delta_ratio',
                '1s_buy_volume', '1s_sell_volume', '1s_total_volume', '1s_delta', '1s_delta_ratio',
                '3s_buy_volume', '3s_sell_volume', '3s_total_volume', '3s_delta', '3s_delta_ratio',
                '10s_buy_volume', '10s_sell_volume', '10s_total_volume', '10s_delta', '10s_delta_ratio',
                '30s_buy_volume', '30s_sell_volume', '30s_total_volume', '30s_delta', '30s_delta_ratio',
                '1m_buy_volume', '1m_sell_volume', '1m_total_volume', '1m_delta', '1m_delta_ratio',
                '2m_buy_volume', '2m_sell_volume', '2m_total_volume', '2m_delta', '2m_delta_ratio',
                '5m_buy_volume', '5m_sell_volume', '5m_total_volume', '5m_delta', '5m_delta_ratio',
                '10m_buy_volume', '10m_sell_volume', '10m_total_volume', '10m_delta', '10m_delta_ratio',
                '20m_buy_volume', '20m_sell_volume', '20m_total_volume', '20m_delta', '20m_delta_ratio',
                '30m_buy_volume', '30m_sell_volume', '30m_total_volume', '30m_delta', '30m_delta_ratio',
                '1h_buy_volume', '1h_sell_volume', '1h_total_volume', '1h_delta', '1h_delta_ratio',
                
                # Multi-horizon cumulative delta
                '10ms_cumulative_delta', '50ms_cumulative_delta', '100ms_cumulative_delta', '500ms_cumulative_delta',
                '1s_cumulative_delta', '3s_cumulative_delta', '10s_cumulative_delta', '30s_cumulative_delta',
                '1m_cumulative_delta', '2m_cumulative_delta', '5m_cumulative_delta', '10m_cumulative_delta',
                '20m_cumulative_delta', '30m_cumulative_delta', '1h_cumulative_delta',
                
                # Multi-horizon absorption/exhaustion events
                '10ms_absorption_events', '50ms_absorption_events', '100ms_absorption_events', '500ms_absorption_events',
                '1s_absorption_events', '3s_absorption_events', '10s_absorption_events', '30s_absorption_events',
                '1m_absorption_events', '2m_absorption_events', '5m_absorption_events', '10m_absorption_events',
                '20m_absorption_events', '30m_absorption_events', '1h_absorption_events',
                '10ms_exhaustion_events', '50ms_exhaustion_events', '100ms_exhaustion_events', '500ms_exhaustion_events',
                '1s_exhaustion_events', '3s_exhaustion_events', '10s_exhaustion_events', '30s_exhaustion_events',
                '1m_exhaustion_events', '2m_exhaustion_events', '5m_exhaustion_events', '10m_exhaustion_events',
                '20m_exhaustion_events', '30m_exhaustion_events', '1h_exhaustion_events',
                
                # Multi-horizon price and volatility
                '10ms_price_change', '50ms_price_change', '100ms_price_change', '500ms_price_change',
                '1s_price_change', '3s_price_change', '10s_price_change', '30s_price_change',
                '1m_price_change', '2m_price_change', '5m_price_change', '10m_price_change',
                '20m_price_change', '30m_price_change', '1h_price_change',
                '10ms_volatility', '50ms_volatility', '100ms_volatility', '500ms_volatility',
                '1s_volatility', '3s_volatility', '10s_volatility', '30s_volatility',
                '1m_volatility', '2m_volatility', '5m_volatility', '10m_volatility',
                '20m_volatility', '30m_volatility', '1h_volatility',
                
                # Multi-horizon liquidity features
                '10ms_average_spread', '50ms_average_spread', '100ms_average_spread', '500ms_average_spread',
                '1s_average_spread', '3s_average_spread', '10s_average_spread', '30s_average_spread',
                '1m_average_spread', '2m_average_spread', '5m_average_spread', '10m_average_spread',
                '20m_average_spread', '30m_average_spread', '1h_average_spread',
                '10ms_depth_at_touch', '50ms_depth_at_touch', '100ms_depth_at_touch', '500ms_depth_at_touch',
                '1s_depth_at_touch', '3s_depth_at_touch', '10s_depth_at_touch', '30s_depth_at_touch',
                '1m_depth_at_touch', '2m_depth_at_touch', '5m_depth_at_touch', '10m_depth_at_touch',
                '20m_depth_at_touch', '30m_depth_at_touch', '1h_depth_at_touch',
                
                # Cross-horizon momentum and divergence features
                'delta_momentum_1s_1m', 'delta_momentum_1m_20m', 'delta_momentum_10s_5m', 'delta_momentum_5m_1h',
                'volume_acceleration_ratio', 'delta_divergence_1s_1h', 'delta_divergence_10s_30m',
                
                # Advanced features
                'top_k_queue_snapshot', 'lob_image', 'event_tokens', 'patch_diffs', 'microstructure_indicators',
                'ofi_fast', 'ofi_medium', 'ofi_slow', 'volatility_estimate', 'cancel_modify_ratio'
            ]
        )
        self.register_schema("execution_aware_heavy_v1", execution_aware_heavy)

        # Execution-Aware Multi-Horizon Schema (Extreme)
        execution_aware_extreme = SchemaVersion(
            version="1.0.0",
            description="Extreme execution-aware features with maximum multi-horizon analysis",
            created_date=datetime.now(),
            data_type=DataType.FEATURE_ENGINEERED,
            normalization_type=NormalizationType.TICK_RELATIVE,
            feature_set=FeatureSet.COMPREHENSIVE,
            features=[
                # Base MBO data
                'ts_event', 'ts_recv', 'action', 'side', 'order_id',
                'price', 'size', 'flags', 'sequence', 'instrument',
                'midprice', 'price_norm', 'size_norm',
                
                # Basic L3 features
                'spread_ticks', 'depth_bid_norm', 'depth_ask_norm',
                'ofi_norm', 'queue_fraction', 'time_delta_norm',
                
                # Execution-aware features
                'buy_volume', 'sell_volume', 'aggressive_buy_volume', 'aggressive_sell_volume',
                'passive_buy_volume', 'passive_sell_volume', 'delta', 'delta_ratio',
                'session_delta', 'session_buy_volume', 'session_sell_volume',
                'absorption_events_1m', 'avg_absorption_ratio', 'exhaustion_events_1m',
                'last_execution_volume', 'last_execution_price', 'time_since_last_execution',
                
                # Fair value features
                'vwap_mid', 'imbalance_adjusted_mid', 'execution_weighted_mid',
                
                # Multi-horizon volume features (15 horizons)
                '10ms_buy_volume', '10ms_sell_volume', '10ms_total_volume', '10ms_delta', '10ms_delta_ratio',
                '50ms_buy_volume', '50ms_sell_volume', '50ms_total_volume', '50ms_delta', '50ms_delta_ratio',
                '100ms_buy_volume', '100ms_sell_volume', '100ms_total_volume', '100ms_delta', '100ms_delta_ratio',
                '500ms_buy_volume', '500ms_sell_volume', '500ms_total_volume', '500ms_delta', '500ms_delta_ratio',
                '1s_buy_volume', '1s_sell_volume', '1s_total_volume', '1s_delta', '1s_delta_ratio',
                '3s_buy_volume', '3s_sell_volume', '3s_total_volume', '3s_delta', '3s_delta_ratio',
                '10s_buy_volume', '10s_sell_volume', '10s_total_volume', '10s_delta', '10s_delta_ratio',
                '30s_buy_volume', '30s_sell_volume', '30s_total_volume', '30s_delta', '30s_delta_ratio',
                '1m_buy_volume', '1m_sell_volume', '1m_total_volume', '1m_delta', '1m_delta_ratio',
                '2m_buy_volume', '2m_sell_volume', '2m_total_volume', '2m_delta', '2m_delta_ratio',
                '5m_buy_volume', '5m_sell_volume', '5m_total_volume', '5m_delta', '5m_delta_ratio',
                '10m_buy_volume', '10m_sell_volume', '10m_total_volume', '10m_delta', '10m_delta_ratio',
                '20m_buy_volume', '20m_sell_volume', '20m_total_volume', '20m_delta', '20m_delta_ratio',
                '30m_buy_volume', '30m_sell_volume', '30m_total_volume', '30m_delta', '30m_delta_ratio',
                '1h_buy_volume', '1h_sell_volume', '1h_total_volume', '1h_delta', '1h_delta_ratio',
                
                # Multi-horizon cumulative delta
                '10ms_cumulative_delta', '50ms_cumulative_delta', '100ms_cumulative_delta', '500ms_cumulative_delta',
                '1s_cumulative_delta', '3s_cumulative_delta', '10s_cumulative_delta', '30s_cumulative_delta',
                '1m_cumulative_delta', '2m_cumulative_delta', '5m_cumulative_delta', '10m_cumulative_delta',
                '20m_cumulative_delta', '30m_cumulative_delta', '1h_cumulative_delta',
                
                # Multi-horizon absorption/exhaustion events
                '10ms_absorption_events', '50ms_absorption_events', '100ms_absorption_events', '500ms_absorption_events',
                '1s_absorption_events', '3s_absorption_events', '10s_absorption_events', '30s_absorption_events',
                '1m_absorption_events', '2m_absorption_events', '5m_absorption_events', '10m_absorption_events',
                '20m_absorption_events', '30m_absorption_events', '1h_absorption_events',
                '10ms_exhaustion_events', '50ms_exhaustion_events', '100ms_exhaustion_events', '500ms_exhaustion_events',
                '1s_exhaustion_events', '3s_exhaustion_events', '10s_exhaustion_events', '30s_exhaustion_events',
                '1m_exhaustion_events', '2m_exhaustion_events', '5m_exhaustion_events', '10m_exhaustion_events',
                '20m_exhaustion_events', '30m_exhaustion_events', '1h_exhaustion_events',
                
                # Multi-horizon price and volatility
                '10ms_price_change', '50ms_price_change', '100ms_price_change', '500ms_price_change',
                '1s_price_change', '3s_price_change', '10s_price_change', '30s_price_change',
                '1m_price_change', '2m_price_change', '5m_price_change', '10m_price_change',
                '20m_price_change', '30m_price_change', '1h_price_change',
                '10ms_volatility', '50ms_volatility', '100ms_volatility', '500ms_volatility',
                '1s_volatility', '3s_volatility', '10s_volatility', '30s_volatility',
                '1m_volatility', '2m_volatility', '5m_volatility', '10m_volatility',
                '20m_volatility', '30m_volatility', '1h_volatility',
                
                # Multi-horizon liquidity features
                '10ms_average_spread', '50ms_average_spread', '100ms_average_spread', '500ms_average_spread',
                '1s_average_spread', '3s_average_spread', '10s_average_spread', '30s_average_spread',
                '1m_average_spread', '2m_average_spread', '5m_average_spread', '10m_average_spread',
                '20m_average_spread', '30m_average_spread', '1h_average_spread',
                '10ms_depth_at_touch', '50ms_depth_at_touch', '100ms_depth_at_touch', '500ms_depth_at_touch',
                '1s_depth_at_touch', '3s_depth_at_touch', '10s_depth_at_touch', '30s_depth_at_touch',
                '1m_depth_at_touch', '2m_depth_at_touch', '5m_depth_at_touch', '10m_depth_at_touch',
                '20m_depth_at_touch', '30m_depth_at_touch', '1h_depth_at_touch',
                
                # Cross-horizon momentum and divergence features
                'delta_momentum_1s_1m', 'delta_momentum_1m_20m', 'delta_momentum_10s_5m', 'delta_momentum_5m_1h',
                'volume_acceleration_ratio', 'delta_divergence_1s_1h', 'delta_divergence_10s_30m',
                'delta_momentum_50ms_1s', 'delta_momentum_100ms_10s', 'delta_momentum_500ms_30s',
                'volume_acceleration_short', 'volume_acceleration_medium', 'volume_acceleration_long',
                'delta_divergence_50ms_5m', 'delta_divergence_100ms_10m', 'delta_divergence_500ms_20m',
                
                # Advanced features
                'top_k_queue_snapshot', 'lob_image', 'event_tokens', 'patch_diffs', 'microstructure_indicators',
                'ofi_fast', 'ofi_medium', 'ofi_slow', 'volatility_estimate', 'cancel_modify_ratio',
                
                # Additional extreme features
                'execution_cluster_strength', 'execution_cluster_migration', 'execution_cluster_persistence',
                'aggressor_size_distribution', 'aggressor_frequency', 'aggressor_persistence',
                'market_impact_curve', 'liquidity_resilience', 'quote_stability',
                'large_order_fragmentation', 'institutional_flow_strength', 'iceberg_detection',
                'flow_autocorrelation', 'flow_predictability', 'flow_exhaustion_signals',
                'volatility_regime', 'regime_transition_probability', 'regime_persistence',
                'liquidity_regime', 'liquidity_stress_indicators', 'liquidity_recovery_signals'
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
