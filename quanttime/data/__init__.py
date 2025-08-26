"""
QuantTime MBO L3 Unified Data Pipeline.

This module provides a complete data processing pipeline for Market-By-Order (MBO) Level 3 data,
including schema management, file organization, normalization, and feature engineering.

The pipeline ensures:
- Raw → Processed separation (no modification of raw data)
- Identical preprocessing for backtest and live trading
- Multi-scale feature engineering leveraging L3 alpha
- Optimized normalization for AI/ML training stability
- Modular design with clear extension points
"""

from .schema import (
    DataType, NormalizationType, FeatureSet, ActionType, SideType,
    get_unified_schema, get_schema_info, list_available_schemas,
    get_arrow_schema
)

from .file_organization import (
    get_file_manager, get_data_type_summary, list_available_dates,
    get_file_paths
)

from .normalization import (
    get_normalization_engine, BatchNormalizer, denormalize_price,
    normalize_mbo_event
)

from .features import (
    get_feature_engine, compute_mbo_features, BatchFeatureEngine
)

from .processor import (
    get_processor, process_raw_to_normalized, load_processed_data,
    get_available_data_types, list_available_dates
)

__all__ = [
    # Schema management
    'DataType', 'NormalizationType', 'FeatureSet', 'ActionType', 'SideType',
    'get_unified_schema', 'get_schema_info', 'list_available_schemas',
    'get_arrow_schema',
    
    # File organization
    'get_file_manager', 'get_data_type_summary', 'list_available_dates',
    'get_file_paths',
    
    # Normalization
    'get_normalization_engine', 'BatchNormalizer', 'denormalize_price',
    'normalize_mbo_event',
    
    # Feature engineering
    'get_feature_engine', 'compute_mbo_features', 'BatchFeatureEngine',
    
    # Unified processor
    'get_processor', 'process_raw_to_normalized', 'load_processed_data',
    'get_available_data_types', 'list_available_dates'
]


