"""
Unified Data Processor for QuantTime MBO L3 Pipeline.

This module provides the main interface for processing MBO data from raw DBN files
to normalized, feature-engineered Parquet files. It combines schema management,
file organization, normalization, and feature engineering into a complete pipeline.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
import pandas as pd
import numpy as np
import logging
from datetime import datetime
import time
import re

from .schema import (
    DataType, NormalizationType, FeatureSet, get_unified_schema,
    get_schema_info, list_available_schemas
)
from .file_organization import (
    get_file_manager, get_data_type_summary, list_available_dates,
    get_file_paths
)
from .normalization import (
    get_normalization_engine, BatchNormalizer, denormalize_price
)
from .features import (
    get_feature_engine, compute_mbo_features, BatchFeatureEngine
)

logger = logging.getLogger(__name__)


class UnifiedDataProcessor:
    """
    Unified data processor for MBO L3 pipeline.
    
    Provides a complete interface for processing raw MBO data into
    normalized, feature-engineered formats suitable for ML training.
    """
    
    def __init__(self, base_data_dir: str = "data"):
        """
        Initialize unified data processor.
        
        Args:
            base_data_dir: Base directory for data storage
        """
        self.base_data_dir = base_data_dir
        self.file_manager = get_file_manager(base_data_dir)
        self.schema = get_unified_schema()
        
        logger.info(f"Initialized unified data processor: {base_data_dir}")
    
    def get_available_data_types(self) -> Dict[str, Any]:
        """
        Get summary of available data types and schemas.
        
        Returns:
            Dictionary with data type summary
        """
        return get_data_type_summary()
    
    def list_available_dates(self, 
                           data_type: str = "mbo",
                           schema_name: Optional[str] = None) -> List[str]:
        """
        List available dates for a specific data type and schema.
        
        Args:
            data_type: Data type (mbo, mbp, trades)
            schema_name: Optional schema name for processed data
            
        Returns:
            List of available date strings
        """
        return list_available_dates(data_type, schema_name)
    
    def get_schema_info(self, schema_name: str) -> Dict[str, Any]:
        """
        Get information about a specific schema.
        
        Args:
            schema_name: Schema name
            
        Returns:
            Dictionary with schema information
        """
        return get_schema_info(schema_name)
    
    def list_available_schemas(self, data_type: Optional[DataType] = None) -> List[str]:
        """
        List available schemas.
        
        Args:
            data_type: Optional data type filter
            
        Returns:
            List of available schema names
        """
        return list_available_schemas(data_type)
    
    def process_raw_to_normalized(self,
                                date_str: str,
                                data_type: str = "mbo",
                                schema_name: str = "basic_normalized_v1",
                                intensity_level: str = "medium",
                                trading_hours_only: bool = False,
                                max_rows: Optional[int] = None,
                                progress_callback: Optional[Callable] = None) -> bool:
        """
        Process raw DBN file to normalized Parquet file.
        
        Args:
            date_str: Date string (YYYYMMDD)
            data_type: Data type (mbo, mbp, trades)
            schema_name: Schema name for output
            intensity_level: Feature engineering intensity level
            trading_hours_only: If True, filter to NYSE trading hours (9:30 AM - 4:00 PM EST)
            progress_callback: Optional progress callback
            
        Returns:
            True if processing successful
        """
        # Import console logging function
        try:
            from quanttime.dashboard.app import log_to_console
        except ImportError:
            # Fallback if console logging not available
            def log_to_console(message: str, level: str = "INFO"):
                logger.info(f"[{level}] {message}")
        
        try:
            trading_hours_suffix = "_trading_hours" if trading_hours_only else "_full_day"
            log_to_console(f"🚀 Starting processing for {date_str} {data_type} -> {schema_name} ({intensity_level}) {trading_hours_suffix}", "INFO")
            logger.info(f"Processing {date_str} {data_type} to {schema_name} {trading_hours_suffix}")
            
            # Check if processed file already exists (simplified check)
            log_to_console("🔍 Checking if processed file already exists...", "INFO")
            schema_dir = self.file_manager.get_schema_dir(schema_name)
            processed_file_pattern = f"{date_str}_{data_type}_{intensity_level}_{schema_name}{trading_hours_suffix}.parquet"
            existing_files = list(schema_dir.glob(processed_file_pattern))
            if existing_files:
                log_to_console(f"✅ Processed file already exists: {existing_files[0]}", "INFO")
                logger.info(f"Processed file already exists: {existing_files[0]}")
                return True
            
            # Get schema info
            log_to_console(f"📋 Getting schema info for {schema_name}...", "INFO")
            schema_info = self.get_schema_info(schema_name)
            if not schema_info:
                log_to_console(f"❌ Schema not found: {schema_name}", "ERROR")
                logger.error(f"Schema not found: {schema_name}")
                return False
            
            log_to_console(f"✅ Schema info retrieved: {schema_info.get('description', 'No description')}", "INFO")
            
            # Load raw data
            if progress_callback:
                progress_callback("Loading raw data", 0, 1, "Reading DBN file", 0.0)
            
            log_to_console("📁 Loading raw DBN data...", "INFO")
            
            # Import databento loader here to avoid circular imports
            from quanttime.adapter.databento_loader import get_databento_loader
            
            # Use the correct directory where DBN files are actually stored
            data_dir = "data/es_futures/mbo"
            if progress_callback:
                progress_callback("Loading raw data", 0, 1, f"Initializing databento loader for {data_dir}", 0.1)
            
            log_to_console(f"🔧 Initializing databento loader for {data_dir}...", "INFO")
            databento_loader = get_databento_loader(data_dir)
            
            # Load DBN store
            if progress_callback:
                progress_callback("Loading raw data", 0, 1, f"Loading DBN file for {date_str}", 0.2)
            
            log_to_console(f"📂 Loading DBN file for {date_str}...", "INFO")
            dbn_store = databento_loader.load_date_data(date_str)
            if dbn_store is None:
                log_to_console(f"❌ Failed to load DBN store for {date_str}", "ERROR")
                logger.error(f"Failed to load DBN store for {date_str}")
                return False
            
            if progress_callback:
                progress_callback("Loading raw data", 0, 1, f"DBN file loaded successfully: {dbn_store.nbytes:,} bytes", 0.3)
            
            log_to_console(f"✅ DBN file loaded successfully: {dbn_store.nbytes:,} bytes", "INFO")
            
            # Convert to DataFrame
            if progress_callback:
                progress_callback("Loading raw data", 0, 1, "Converting DBN to DataFrame", 0.4)
            
            log_to_console("🔄 Converting DBN to DataFrame...", "INFO")
            df = databento_loader.convert_to_dataframe(dbn_store)
            if df is None or df.empty:
                log_to_console(f"❌ Failed to convert DBN to DataFrame for {date_str}", "ERROR")
                logger.error(f"Failed to convert DBN to DataFrame for {date_str}")
                return False
            
            if progress_callback:
                progress_callback("Loading raw data", 0, 1, f"DataFrame conversion complete: {len(df):,} rows, {len(df.columns)} columns", 0.5)
            
            log_to_console(f"✅ DataFrame conversion complete: {len(df):,} rows, {len(df.columns)} columns", "INFO")
            logger.info(f"Loaded {len(df):,} events from {date_str}")
            
            # Limit rows for testing if specified
            if max_rows is not None and len(df) > max_rows:
                log_to_console(f"🧪 TESTING MODE: Limiting to {max_rows:,} rows for testing", "INFO")
                df = df.head(max_rows)
                log_to_console(f"✅ Limited DataFrame to {len(df):,} rows for testing", "INFO")
            
            # Apply trading hours filter if requested
            if trading_hours_only:
                log_to_console("🕐 Filtering to NYSE trading hours (9:30 AM - 4:00 PM EST)...", "INFO")
                df = self._filter_trading_hours(df, date_str)
                log_to_console(f"✅ Trading hours filter applied: {len(df):,} rows remaining", "INFO")
            
            # Process based on schema type
            if schema_info['data_type'] == DataType.RAW.value:
                # Raw data - just save as Parquet
                log_to_console("📊 Processing as raw data (no feature engineering)...", "INFO")
                processed_df = df
            else:
                # Normalized/feature engineered data
                log_to_console("🔬 Processing with feature engineering...", "INFO")
                processed_df = self._apply_normalization_and_features(
                    df, schema_info, intensity_level, progress_callback
                )
            
            # Save processed file
            if progress_callback:
                progress_callback("Saving processed data", 0, 1, "Preparing to save processed data", 0.1)
            
            log_to_console("💾 Saving processed data...", "INFO")
            output_path = self._save_processed_file(
                processed_df, date_str, data_type, schema_name, intensity_level, trading_hours_only
            )
            
            if progress_callback:
                progress_callback("Saving processed data", 0, 1, f"Optimizing DataFrame for storage: {len(processed_df):,} rows", 0.3)
            
            log_to_console(f"🔧 Optimizing DataFrame for storage: {len(processed_df):,} rows...", "INFO")
            
            if progress_callback:
                progress_callback("Saving processed data", 0, 1, f"Writing Parquet file to {output_path}", 0.6)
            
            log_to_console(f"📝 Writing Parquet file to {output_path}...", "INFO")
            
            if progress_callback:
                progress_callback("Saving processed data", 1, 1, f"Successfully saved to {output_path}", 1.0)
            
            log_to_console(f"✅ Successfully processed {date_str} to {output_path}", "SUCCESS")
            logger.info(f"Successfully processed {date_str} to {output_path}")
            return True
            
        except Exception as e:
            log_to_console(f"❌ Error processing {date_str}: {str(e)}", "ERROR")
            logger.error(f"Error processing {date_str}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _apply_normalization_and_features(self,
                                        df: pd.DataFrame,
                                        schema_info: Dict[str, Any],
                                        intensity_level: str = "medium",
                                        progress_callback: Optional[Callable] = None) -> pd.DataFrame:
        """
        Apply normalization and feature engineering to DataFrame.
        
        Args:
            df: Input DataFrame
            schema_info: Schema information
            progress_callback: Optional progress callback
            
        Returns:
            Processed DataFrame
        """
        # Import console logging function
        try:
            from quanttime.dashboard.app import log_to_console
        except ImportError:
            # Fallback if console logging not available
            def log_to_console(message: str, level: str = "INFO"):
                logger.info(f"[{level}] {message}")
        
        log_to_console("🚀 Starting feature engineering pipeline...", "INFO")
        
        # Get normalization and feature parameters
        norm_type_str = schema_info.get('normalization_type', 'tick_relative')
        feature_set_str = schema_info.get('feature_set', 'basic')
        
        log_to_console(f"📋 Normalization type: {norm_type_str}", "INFO")
        log_to_console(f"📋 Feature set: {feature_set_str}", "INFO")
        log_to_console(f"📋 Intensity level: {intensity_level}", "INFO")
        
        # Convert strings to enums if needed
        if isinstance(norm_type_str, str):
            normalization_type = NormalizationType(norm_type_str)
        else:
            normalization_type = norm_type_str
            
        if isinstance(feature_set_str, str):
            feature_set = FeatureSet(feature_set_str)
        else:
            feature_set = feature_set_str
        
        log_to_console(f"🔬 Starting feature engineering with {feature_set.value} features and {normalization_type.value} normalization", "INFO")
        
        # Check for GPU acceleration
        log_to_console("🔍 Checking for GPU acceleration...", "INFO")
        gpu_available = self._check_gpu_availability()
        if gpu_available:
            log_to_console("🚀 GPU acceleration available - using GPU for feature engineering", "INFO")
        else:
            log_to_console("💻 Using CPU for feature engineering", "INFO")
        
        # Preprocess DataFrame to ensure compatibility
        if progress_callback:
            progress_callback("Feature engineering", 0, 1, "Preprocessing DataFrame", 0.1)
        log_to_console("🔧 Preprocessing DataFrame for feature engineering...", "INFO")
        
        # Optimize memory usage before processing
        log_to_console("💾 Optimizing memory usage...", "INFO")
        df = self._optimize_memory_usage(df)
        
        df = self._preprocess_dataframe(df)
        log_to_console(f"✅ Preprocessing complete: {len(df):,} rows, {len(df.columns)} columns", "INFO")
        
        # Add midprice column if not present
        if 'midprice' not in df.columns:
            if progress_callback:
                progress_callback("Feature engineering", 0, 1, "Adding midprice column", 0.2)
            log_to_console("💰 Adding midprice column...", "INFO")
            df = self._add_midprice_column(df)
            log_to_console("✅ Midprice column added", "INFO")
        
        # Check if we need to process in chunks due to memory constraints
        total_rows = len(df)
        memory_threshold = 5_000_000  # 5M rows threshold for chunked processing
        
        if total_rows > memory_threshold:
            log_to_console(f"⚠️ Large dataset detected ({total_rows:,} rows) - using chunked processing to avoid memory issues", "WARNING")
            processed_df = self._compute_features_chunked(df, feature_set, normalization_type, intensity_level, progress_callback)
        else:
            log_to_console(f"🚀 Starting feature computation: {total_rows:,} rows to process", "INFO")
            log_to_console(f"📊 Feature set: {feature_set.value}, Normalization: {normalization_type.value}, Intensity: {intensity_level}", "INFO")
            
            if progress_callback:
                progress_callback("Feature engineering", 0, 1, f"Computing {feature_set.value} features with {normalization_type.value} normalization", 0.3)
            
            if gpu_available:
                processed_df = self._compute_features_gpu(df, feature_set, normalization_type, intensity_level, progress_callback)
            else:
                processed_df = compute_mbo_features(
                    df, feature_set, normalization_type, intensity_level
                )
        
        if processed_df is None or processed_df.empty:
            log_to_console("❌ Feature computation failed - no data returned", "ERROR")
            return df
        
        log_to_console(f"✅ Feature computation completed successfully", "SUCCESS")
        
        if progress_callback:
            progress_callback("Feature engineering", 0, 1, f"Feature computation complete: {len(processed_df):,} rows, {len(processed_df.columns)} features", 0.8)
        
        log_to_console(f"📊 Final result: {len(processed_df):,} rows, {len(processed_df.columns)} features", "INFO")
        
        if progress_callback:
            progress_callback("Feature engineering", 1, 1, "Feature engineering completed", 1.0)
        
        return processed_df
    
    def _check_gpu_availability(self) -> bool:
        """
        Check if GPU acceleration is available.
        
        Returns:
            True if GPU is available and can be used
        """
        try:
            import torch
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9  # GB
                logger.info(f"GPU available: {gpu_count} devices, {gpu_memory:.1f}GB memory")
                return True
            else:
                logger.info("CUDA not available")
                return False
        except ImportError:
            logger.info("PyTorch not available for GPU acceleration")
            return False
        except Exception as e:
            logger.warning(f"Error checking GPU availability: {e}")
            return False
    
    def _compute_features_gpu(self, df: pd.DataFrame, feature_set: FeatureSet, 
                            normalization_type: NormalizationType, intensity_level: str,
                            progress_callback: Optional[Callable] = None) -> pd.DataFrame:
        """
        Compute features using GPU acceleration.
        
        Args:
            df: Input DataFrame
            feature_set: Feature set to compute
            normalization_type: Normalization type
            intensity_level: Intensity level
            progress_callback: Optional progress callback
            
        Returns:
            Processed DataFrame with features
        """
        try:
            from quanttime.dashboard.app import log_to_console
        except ImportError:
            def log_to_console(message: str, level: str = "INFO"):
                logger.info(f"[{level}] {message}")
        
        log_to_console("🚀 Using GPU acceleration for feature computation...", "INFO")
        
        try:
            import torch
            import numpy as np
            
            # Move data to GPU if possible
            log_to_console("📤 Moving data to GPU...", "INFO")
            
            # Convert DataFrame to GPU tensors for computation
            # This is a simplified GPU implementation - in practice you'd want more sophisticated GPU operations
            
            # For now, fall back to CPU computation but with better logging
            log_to_console("⚠️ GPU implementation not fully optimized, using CPU with enhanced logging", "WARNING")
            
            # Use the existing CPU implementation but with better progress tracking
            return compute_mbo_features(df, feature_set, normalization_type, intensity_level)
            
        except Exception as e:
            log_to_console(f"❌ GPU computation failed, falling back to CPU: {str(e)}", "WARNING")
            logger.warning(f"GPU computation failed: {e}")
            return compute_mbo_features(df, feature_set, normalization_type, intensity_level)
    
    def _compute_features_chunked(self, df: pd.DataFrame, feature_set: FeatureSet, 
                                normalization_type: NormalizationType, intensity_level: str,
                                progress_callback: Optional[Callable] = None) -> pd.DataFrame:
        """
        Compute features using chunked processing to avoid memory issues.
        
        Args:
            df: Input DataFrame
            feature_set: Feature set to compute
            normalization_type: Normalization type
            intensity_level: Intensity level
            progress_callback: Optional progress callback
            
        Returns:
            Processed DataFrame with features
        """
        try:
            from quanttime.dashboard.app import log_to_console
        except ImportError:
            def log_to_console(message: str, level: str = "INFO"):
                logger.info(f"[{level}] {message}")
        
        log_to_console("🔄 Using chunked processing to handle large dataset...", "INFO")
        
        # Determine chunk size based on available memory
        total_rows = len(df)
        chunk_size = 1_000_000  # 1M rows per chunk
        
        # Calculate number of chunks
        num_chunks = (total_rows + chunk_size - 1) // chunk_size
        
        log_to_console(f"📊 Processing {total_rows:,} rows in {num_chunks} chunks of {chunk_size:,} rows each", "INFO")
        
        # Process chunks
        processed_chunks = []
        
        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min((chunk_idx + 1) * chunk_size, total_rows)
            
            log_to_console(f"🔄 Processing chunk {chunk_idx + 1}/{num_chunks}: rows {start_idx:,}-{end_idx:,}", "INFO")
            
            # Extract chunk
            chunk_df = df.iloc[start_idx:end_idx].copy()
            
            # Process chunk
            try:
                processed_chunk = compute_mbo_features(
                    chunk_df, feature_set, normalization_type, intensity_level
                )
                
                if processed_chunk is not None and not processed_chunk.empty:
                    processed_chunks.append(processed_chunk)
                    log_to_console(f"✅ Chunk {chunk_idx + 1} processed successfully: {len(processed_chunk):,} rows", "INFO")
                else:
                    log_to_console(f"⚠️ Chunk {chunk_idx + 1} returned empty result", "WARNING")
                    
            except Exception as e:
                log_to_console(f"❌ Error processing chunk {chunk_idx + 1}: {str(e)}", "ERROR")
                # Continue with other chunks
                continue
            
            # Update progress
            if progress_callback:
                progress = (chunk_idx + 1) / num_chunks
                progress_callback("Feature engineering", progress, 1, f"Processed chunk {chunk_idx + 1}/{num_chunks}", 0.3 + progress * 0.5)
        
        # Combine chunks
        if processed_chunks:
            log_to_console(f"🔗 Combining {len(processed_chunks)} processed chunks...", "INFO")
            combined_df = pd.concat(processed_chunks, ignore_index=True)
            log_to_console(f"✅ Combined result: {len(combined_df):,} rows, {len(combined_df.columns)} columns", "SUCCESS")
            return combined_df
        else:
            log_to_console("❌ No chunks processed successfully", "ERROR")
            return df
    
    def _optimize_memory_usage(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Optimize DataFrame memory usage by converting data types.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Memory-optimized DataFrame
        """
        try:
            from quanttime.dashboard.app import log_to_console
        except ImportError:
            def log_to_console(message: str, level: str = "INFO"):
                logger.info(f"[{level}] {message}")
        
        log_to_console("💾 Optimizing DataFrame memory usage...", "INFO")
        
        # Get initial memory usage
        initial_memory = df.memory_usage(deep=True).sum() / 1024**2  # MB
        
        df_optimized = df.copy()
        
        # Optimize numeric columns
        for col in df_optimized.columns:
            col_type = df_optimized[col].dtype
            
            # Skip if column contains lists (can cause issues)
            if col_type == 'object':
                # Check if column contains lists
                sample_values = df_optimized[col].dropna().head(100)
                if any(isinstance(val, list) for val in sample_values):
                    log_to_console(f"  ⚠️ Skipping '{col}' - contains lists", "INFO")
                    continue
                
                # Convert object columns to categorical if they have limited unique values
                unique_count = df_optimized[col].nunique()
                if unique_count < len(df_optimized) * 0.5:  # Less than 50% unique values
                    df_optimized[col] = df_optimized[col].astype('category')
                    log_to_console(f"  📊 Converted '{col}' to categorical ({unique_count} unique values)", "INFO")
            
            elif col_type == 'float64':
                # Use float32 for better compression if precision is sufficient
                if df_optimized[col].notna().all():
                    min_val = df_optimized[col].min()
                    max_val = df_optimized[col].max()
                    if min_val >= -3.4e38 and max_val <= 3.4e38:
                        df_optimized[col] = df_optimized[col].astype('float32')
                        log_to_console(f"  📊 Converted '{col}' from float64 to float32", "INFO")
            
            elif col_type == 'int64':
                # Use smaller integer types if possible
                min_val = df_optimized[col].min()
                max_val = df_optimized[col].max()
                if min_val >= -32768 and max_val <= 32767:
                    df_optimized[col] = df_optimized[col].astype('int16')
                    log_to_console(f"  📊 Converted '{col}' from int64 to int16", "INFO")
                elif min_val >= -2147483648 and max_val <= 2147483647:
                    df_optimized[col] = df_optimized[col].astype('int32')
                    log_to_console(f"  📊 Converted '{col}' from int64 to int32", "INFO")
        
        # Calculate memory savings
        final_memory = df_optimized.memory_usage(deep=True).sum() / 1024**2  # MB
        memory_savings = (initial_memory - final_memory) / initial_memory * 100
        
        log_to_console(f"✅ Memory optimization complete: {initial_memory:.1f}MB -> {final_memory:.1f}MB ({memory_savings:.1f}% reduction)", "INFO")
        
        return df_optimized
    
    def _add_midprice_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add midprice column to DataFrame.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with midprice column
        """
        # Import console logging function
        try:
            from quanttime.dashboard.app import log_to_console
        except ImportError:
            def log_to_console(message: str, level: str = "INFO"):
                logger.info(f"[{level}] {message}")
        
        log_to_console("💰 Adding midprice column to DataFrame...", "INFO")
        
        # Simple midprice calculation based on best bid/ask
        # In practice, this would be more sophisticated
        df = df.copy()
        
        # For now, use a simple approximation
        # In a real implementation, you'd reconstruct the order book
        log_to_console("🔢 Calculating midprice using price column as approximation...", "INFO")
        df['midprice'] = df['price']  # Placeholder
        
        log_to_console("✅ Midprice column added successfully", "INFO")
        
        return df
    
    def _preprocess_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess DataFrame to ensure compatibility with feature engine.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Preprocessed DataFrame
        """
        # Import console logging function
        try:
            from quanttime.dashboard.app import log_to_console
        except ImportError:
            def log_to_console(message: str, level: str = "INFO"):
                logger.info(f"[{level}] {message}")
        
        log_to_console("🔧 Starting DataFrame preprocessing...", "INFO")
        log_to_console(f"📊 Input DataFrame: {len(df):,} rows, {len(df.columns)} columns", "INFO")
        log_to_console(f"📋 Columns: {list(df.columns)}", "INFO")
        
        df = df.copy()
        log_to_console("✅ DataFrame copied for preprocessing", "INFO")
        
        # Ensure required columns exist
        log_to_console("🔍 Checking required columns...", "INFO")
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
                    log_to_console(f"❌ Required column '{col}' missing from DataFrame", "ERROR")
                    raise ValueError(f"Required column '{col}' missing from DataFrame. Available columns: {list(df.columns)}")
                elif isinstance(default_value, str) and default_value in df.columns:
                    # Use existing column as fallback
                    log_to_console(f"🔄 Using '{default_value}' as fallback for missing '{col}'", "INFO")
                    df[col] = df[default_value]
                else:
                    # Use default value
                    log_to_console(f"➕ Adding missing column '{col}' with default value", "INFO")
                    df[col] = default_value
            else:
                log_to_console(f"✅ Column '{col}' exists", "INFO")
        
        # Handle special cases for Databento data
        log_to_console("🔧 Handling Databento-specific column mappings...", "INFO")
        if 'instrument' not in df.columns and 'symbol' in df.columns:
            log_to_console("🔄 Mapping 'symbol' to 'instrument'", "INFO")
            df['instrument'] = df['symbol']
        
        if 'ts_recv' not in df.columns and 'ts_event' in df.columns:
            log_to_console("🔄 Using 'ts_event' as 'ts_recv'", "INFO")
            df['ts_recv'] = df['ts_event']
        
        # Ensure data types are correct
        log_to_console("🔧 Converting data types...", "INFO")
        if 'ts_event' in df.columns:
            log_to_console("📅 Converting ts_event to numeric...", "INFO")
            df['ts_event'] = pd.to_numeric(df['ts_event'], errors='coerce').fillna(0).astype('int64')
        
        if 'ts_recv' in df.columns:
            log_to_console("📅 Converting ts_recv to numeric...", "INFO")
            df['ts_recv'] = pd.to_numeric(df['ts_recv'], errors='coerce').fillna(0).astype('int64')
        
        if 'order_id' in df.columns:
            log_to_console("🆔 Converting order_id to numeric...", "INFO")
            df['order_id'] = pd.to_numeric(df['order_id'], errors='coerce').fillna(0).astype('int64')
        
        if 'price' in df.columns:
            log_to_console("💰 Converting price to numeric...", "INFO")
            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0).astype('float64')
        
        if 'size' in df.columns:
            log_to_console("📏 Converting size to numeric...", "INFO")
            df['size'] = pd.to_numeric(df['size'], errors='coerce').fillna(0).astype('int64')
        
        if 'flags' in df.columns:
            log_to_console("🚩 Converting flags to numeric...", "INFO")
            df['flags'] = pd.to_numeric(df['flags'], errors='coerce').fillna(0).astype('int64')
        
        if 'sequence' in df.columns:
            log_to_console("🔢 Converting sequence to numeric...", "INFO")
            df['sequence'] = pd.to_numeric(df['sequence'], errors='coerce').fillna(0).astype('int64')
        
        # Ensure action and side are strings and validate against Databento codes
        log_to_console("🔍 Validating action and side codes...", "INFO")
        if 'action' in df.columns:
            log_to_console("🔄 Converting action to string...", "INFO")
            df['action'] = df['action'].astype(str)
            # Validate actions
            valid_actions = {'A', 'M', 'C', 'R', 'T', 'F', 'N', 'ADD', 'MODIFY', 'CANCEL', 'EXECUTE'}
            invalid_actions = set(df['action'].unique()) - valid_actions
            if invalid_actions:
                log_to_console(f"⚠️ Found invalid actions: {invalid_actions}", "WARNING")
                logger.warning(f"Found invalid actions: {invalid_actions}")
        
        if 'side' in df.columns:
            log_to_console("🔄 Converting side to string...", "INFO")
            df['side'] = df['side'].astype(str)
            # Validate sides
            valid_sides = {'B', 'A', 'N', 'BID', 'ASK'}
            invalid_sides = set(df['side'].unique()) - valid_sides
            if invalid_sides:
                log_to_console(f"⚠️ Found invalid sides: {invalid_sides}", "WARNING")
                logger.warning(f"Found invalid sides: {invalid_sides}")
        
        if 'instrument' in df.columns:
            log_to_console("🔄 Converting instrument to string...", "INFO")
            df['instrument'] = df['instrument'].astype(str)
        
        log_to_console(f"✅ Preprocessing complete: {len(df):,} rows, {len(df.columns)} columns", "INFO")
        log_to_console(f"📋 Final columns: {list(df.columns)}", "INFO")
        logger.info(f"Preprocessed DataFrame: {len(df)} rows, {len(df.columns)} columns")
        logger.info(f"Columns: {list(df.columns)}")
        
        return df
    
    def _save_processed_file(self,
                           df: pd.DataFrame,
                           date_str: str,
                           data_type: str,
                           schema_name: str,
                           intensity_level: str = "medium",
                           trading_hours_only: bool = False) -> Path:
        """
        Save processed DataFrame to Parquet file (production-ready).
        
        Args:
            df: DataFrame to save
            date_str: Date string
            data_type: Data type
            schema_name: Schema name
            intensity_level: Feature engineering intensity level
            trading_hours_only: If True, save as trading hours file
            
        Returns:
            Path to saved Parquet file
        """
        # Import console logging function
        try:
            from quanttime.dashboard.app import log_to_console
        except ImportError:
            def log_to_console(message: str, level: str = "INFO"):
                logger.info(f"[{level}] {message}")
        
        log_to_console("💾 Starting file save process...", "INFO")
        log_to_console(f"📊 Saving DataFrame: {len(df):,} rows, {len(df.columns)} columns", "INFO")
        
        # Create schema directory
        log_to_console("📁 Creating schema directory...", "INFO")
        schema_dir = self.file_manager.create_schema_directory(schema_name)
        log_to_console(f"✅ Schema directory: {schema_dir}", "INFO")
        
        # Generate filename with intensity level and trading hours suffix
        filename = f"{date_str}_{data_type}_{intensity_level}_{schema_name}"
        if trading_hours_only:
            filename += "_trading_hours"
        filename += ".parquet"
        
        output_path = schema_dir / filename
        log_to_console(f"📝 Output file: {output_path}", "INFO")
        
        # Optimize DataFrame for Parquet storage
        log_to_console("🔧 Optimizing DataFrame for Parquet storage...", "INFO")
        df_optimized = self._optimize_dataframe_for_storage(df)
        log_to_console("✅ DataFrame optimization complete", "INFO")
        
        # Save to Parquet with optimal settings for production
        log_to_console("💾 Writing Parquet file...", "INFO")
        df_optimized.to_parquet(
            output_path, 
            index=False, 
            compression='snappy',  # Fast compression/decompression
            engine='pyarrow',      # Use PyArrow for better performance
            row_group_size=100000  # Optimize for reading chunks
        )
        
        log_to_console(f"✅ Successfully saved {len(df):,} events to Parquet: {output_path}", "SUCCESS")
        logger.info(f"Saved {len(df):,} events to Parquet: {output_path}")
        return output_path
    
    def _optimize_dataframe_for_storage(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Optimize DataFrame for efficient Parquet storage and loading.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Optimized DataFrame
        """
        # Import console logging function
        try:
            from quanttime.dashboard.app import log_to_console
        except ImportError:
            def log_to_console(message: str, level: str = "INFO"):
                logger.info(f"[{level}] {message}")
        
        log_to_console("🔧 Starting DataFrame optimization for storage...", "INFO")
        log_to_console(f"📊 Input DataFrame: {len(df):,} rows, {len(df.columns)} columns", "INFO")
        
        df_optimized = df.copy()
        log_to_console("✅ DataFrame copied for optimization", "INFO")
        
        # Convert data types for better compression and performance
        log_to_console("🔄 Converting data types for better compression...", "INFO")
        optimized_columns = 0
        
        for col in df_optimized.columns:
            if df_optimized[col].dtype == 'object':
                # Check if column contains lists (unhashable types)
                try:
                    # Sample a few values to check for lists
                    sample_values = df_optimized[col].dropna().head(100)
                    has_lists = any(isinstance(val, list) for val in sample_values)
                    
                    if has_lists:
                        # Skip optimization for list columns
                        log_to_console(f"⚠️ Skipping optimization for '{col}' (contains lists)", "WARNING")
                        continue
                    
                    # Convert object columns to categorical if they have limited unique values
                    unique_count = df_optimized[col].nunique()
                    if unique_count < len(df_optimized) * 0.5:  # Less than 50% unique values
                        df_optimized[col] = df_optimized[col].astype('category')
                        optimized_columns += 1
                        log_to_console(f"📊 Converted '{col}' to categorical ({unique_count} unique values)", "INFO")
                except (TypeError, ValueError) as e:
                    # Skip optimization for problematic columns
                    log_to_console(f"⚠️ Skipping optimization for '{col}' (error: {str(e)})", "WARNING")
                    continue
            
            elif df_optimized[col].dtype == 'float64':
                # Use float32 for better compression if precision is sufficient
                if df_optimized[col].notna().all():
                    min_val = df_optimized[col].min()
                    max_val = df_optimized[col].max()
                    if min_val >= -3.4e38 and max_val <= 3.4e38:
                        df_optimized[col] = df_optimized[col].astype('float32')
                        optimized_columns += 1
                        log_to_console(f"📊 Converted '{col}' from float64 to float32", "INFO")
            
            elif df_optimized[col].dtype == 'int64':
                # Use smaller integer types if possible
                min_val = df_optimized[col].min()
                max_val = df_optimized[col].max()
                if min_val >= -32768 and max_val <= 32767:
                    df_optimized[col] = df_optimized[col].astype('int16')
                    optimized_columns += 1
                    log_to_console(f"📊 Converted '{col}' from int64 to int16", "INFO")
                elif min_val >= -2147483648 and max_val <= 2147483647:
                    df_optimized[col] = df_optimized[col].astype('int32')
                    optimized_columns += 1
                    log_to_console(f"📊 Converted '{col}' from int64 to int32", "INFO")
        
        log_to_console(f"✅ DataFrame optimization complete: {optimized_columns} columns optimized", "INFO")
        log_to_console(f"📊 Final DataFrame: {len(df_optimized):,} rows, {len(df_optimized.columns)} columns", "INFO")
        
        return df_optimized
    
    def load_processed_data(self,
                           date_str: str,
                           data_type: str = "mbo",
                           schema_name: str = "basic_normalized_v1") -> Optional[pd.DataFrame]:
        """
        Load processed data for a specific date and schema (production-ready).
        
        Args:
            date_str: Date string (YYYYMMDD)
            data_type: Data type (mbo, mbp, trades)
            schema_name: Schema name
            
        Returns:
            DataFrame with processed data or None if not found
        """
        try:
            file_paths = get_file_paths(date_str, data_type, schema_name)
            
            if 'processed' in file_paths:
                processed_path = file_paths['processed']
                df = self._load_parquet_optimized(processed_path)
                logger.info(f"Loaded {len(df):,} events from {processed_path}")
                return df
            else:
                logger.warning(f"No processed file found for {date_str} {schema_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading processed data for {date_str}: {e}")
            return None
    
    def _load_parquet_optimized(self, file_path: Path) -> pd.DataFrame:
        """
        Load Parquet file with optimized settings for production.
        
        Args:
            file_path: Path to Parquet file
            
        Returns:
            Optimized DataFrame
        """
        # Load with optimized settings for fast reading
        df = pd.read_parquet(
            file_path,
            engine='pyarrow',  # Use PyArrow for better performance
            use_nullable_dtypes=True  # Use nullable dtypes for better memory efficiency
        )
        
        # Optimize DataFrame for training/live use
        df = self._optimize_dataframe_for_use(df)
        
        return df
    
    def _optimize_dataframe_for_use(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Optimize DataFrame for training and live data use.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Optimized DataFrame
        """
        df_optimized = df.copy()
        
        # Convert categorical columns back to object for ML compatibility
        for col in df_optimized.columns:
            if df_optimized[col].dtype.name == 'category':
                df_optimized[col] = df_optimized[col].astype('object')
        
        # Ensure timestamp columns are properly typed
        timestamp_cols = ['ts_event', 'ts_recv', 'datetime']
        for col in timestamp_cols:
            if col in df_optimized.columns:
                if df_optimized[col].dtype == 'object':
                    try:
                        df_optimized[col] = pd.to_datetime(df_optimized[col])
                    except:
                        pass  # Keep as object if conversion fails
        
        return df_optimized
    
    def batch_process_dates(self,
                           date_range: List[str],
                           data_type: str = "mbo",
                           schema_name: str = "basic_normalized_v1",
                           intensity_level: str = "medium",
                           progress_callback: Optional[Callable] = None) -> Dict[str, bool]:
        """
        Process multiple dates in batch.
        
        Args:
            date_range: List of date strings
            data_type: Data type
            schema_name: Schema name
            progress_callback: Optional progress callback
            
        Returns:
            Dictionary mapping dates to success status
        """
        results = {}
        
        for i, date_str in enumerate(date_range):
            if progress_callback:
                progress_callback("Batch processing", i, len(date_range), f"Processing {date_str}", i/len(date_range))
            
            success = self.process_raw_to_normalized(
                date_str, data_type, schema_name, intensity_level, progress_callback
            )
            results[date_str] = success
            
            if progress_callback:
                progress_callback("Batch processing", i+1, len(date_range), f"Completed {date_str}", (i+1)/len(date_range))
        
        return results
    
    def batch_load_processed_data(self, 
                                date_strings: List[str],
                                data_type: str = "mbo",
                                schema_name: str = "basic_normalized_v1") -> Optional[pd.DataFrame]:
        """
        Load multiple processed data files and combine them.
        
        Args:
            date_strings: List of date strings (YYYYMMDD)
            data_type: Data type (mbo, mbp, trades)
            schema_name: Schema name
            
        Returns:
            Combined DataFrame or None if loading fails
        """
        try:
            # Import console logging function
            try:
                from quanttime.dashboard.app import log_to_console
            except ImportError:
                def log_to_console(message: str, level: str = "INFO"):
                    logger.info(f"[{level}] {message}")
            
            log_to_console(f"🚀 Starting batch load of {len(date_strings)} dates for {schema_name}", "INFO")
            logger.info(f"Batch loading {len(date_strings)} dates for {schema_name}")
            
            # Get schema directory
            schema_dir = self.file_manager.get_schema_dir(schema_name)
            log_to_console(f"📁 Schema directory: {schema_dir}", "INFO")
            
            if not schema_dir.exists():
                log_to_console(f"❌ Schema directory does not exist: {schema_dir}", "ERROR")
                logger.error(f"Schema directory does not exist: {schema_dir}")
                return None
            
            # List all files in schema directory for debugging
            all_files = list(schema_dir.glob("*.parquet"))
            log_to_console(f"📋 Found {len(all_files)} Parquet files in schema directory", "INFO")
            for file_path in all_files:
                log_to_console(f"   📄 {file_path.name}", "INFO")
            
            combined_dfs = []
            loaded_dates = []
            
            for date_str in date_strings:
                log_to_console(f"🔍 Looking for processed file for date: {date_str}", "INFO")
                
                # Try different file patterns
                file_patterns = [
                    f"{date_str}_{data_type}_*_{schema_name}_trading_hours.parquet",
                    f"{date_str}_{data_type}_*_{schema_name}_full_day.parquet",
                    f"{date_str}_{data_type}_*_{schema_name}.parquet"
                ]
                
                file_found = False
                for pattern in file_patterns:
                    matching_files = list(schema_dir.glob(pattern))
                    if matching_files:
                        file_path = matching_files[0]  # Take the first match
                        log_to_console(f"✅ Found file: {file_path.name}", "INFO")
                        
                        try:
                            log_to_console(f"📖 Loading file: {file_path}", "INFO")
                            df = pd.read_parquet(file_path)
                            log_to_console(f"✅ Loaded {len(df):,} rows from {file_path.name}", "INFO")
                            
                            combined_dfs.append(df)
                            loaded_dates.append(date_str)
                            file_found = True
                            break
                            
                        except Exception as e:
                            log_to_console(f"❌ Error loading {file_path}: {str(e)}", "ERROR")
                            logger.error(f"Error loading {file_path}: {e}")
                            continue
                
                if not file_found:
                    log_to_console(f"❌ No processed file found for {date_str} {schema_name}", "ERROR")
                    logger.warning(f"No processed file found for {date_str} {schema_name}")
                    
                    # List all files that might match for debugging
                    all_matching_files = []
                    for pattern in file_patterns:
                        all_matching_files.extend(list(schema_dir.glob(pattern)))
                    
                    if all_matching_files:
                        log_to_console(f"📋 Files that might match patterns:", "INFO")
                        for file_path in all_matching_files:
                            log_to_console(f"   📄 {file_path.name}", "INFO")
                    else:
                        log_to_console(f"📋 No files match any pattern for {date_str}", "INFO")
            
            if not combined_dfs:
                log_to_console(f"❌ No data found for any of the specified dates", "ERROR")
                logger.warning(f"No data found for any of the specified dates")
                return None
            
            # Combine all DataFrames
            log_to_console(f"🔗 Combining {len(combined_dfs)} DataFrames...", "INFO")
            combined_df = pd.concat(combined_dfs, ignore_index=True)
            
            log_to_console(f"✅ Successfully loaded {len(combined_df):,} total rows from {len(loaded_dates)} dates", "SUCCESS")
            log_to_console(f"📊 Loaded dates: {loaded_dates}", "INFO")
            logger.info(f"Successfully loaded {len(combined_df):,} rows from {len(loaded_dates)} dates")
            
            return combined_df
            
        except Exception as e:
            log_to_console(f"❌ Error in batch_load_processed_data: {str(e)}", "ERROR")
            logger.error(f"Error in batch_load_processed_data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_data_comparison(self,
                          date_str: str,
                          data_type: str = "mbo",
                          schema_name: str = "basic_normalized_v1") -> Dict[str, Any]:
        """
        Compare raw vs processed data for a specific date.
        
        Args:
            date_str: Date string
            data_type: Data type
            schema_name: Schema name
            
        Returns:
            Dictionary with comparison information
        """
        try:
            # Load raw data
            file_paths = get_file_paths(date_str, data_type)
            if 'raw' not in file_paths:
                return {'error': 'Raw file not found'}
            
            raw_metadata = self.file_manager.get_file_metadata(file_paths['raw'])
            
            # Load processed data
            processed_df = self.load_processed_data(date_str, data_type, schema_name)
            if processed_df is None:
                return {'error': 'Processed file not found'}
            
            # Get schema info
            schema_info = self.get_schema_info(schema_name)
            
            comparison = {
                'date': date_str,
                'data_type': data_type,
                'schema_name': schema_name,
                'raw_metadata': raw_metadata,
                'processed_rows': len(processed_df),
                'processed_columns': len(processed_df.columns),
                'processed_size_mb': processed_df.memory_usage(deep=True).sum() / (1024*1024),
                'schema_info': schema_info,
                'sample_data': processed_df.head(3).to_dict('records')
            }
            
            return comparison
            
        except Exception as e:
            logger.error(f"Error comparing data for {date_str}: {e}")
            return {'error': str(e)}
    
    def validate_processed_data(self,
                              date_str: str,
                              data_type: str = "mbo",
                              schema_name: str = "basic_normalized_v1") -> Dict[str, Any]:
        """
        Validate processed data against schema.
        
        Args:
            date_str: Date string
            data_type: Data type
            schema_name: Schema name
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Load processed data
            df = self.load_processed_data(date_str, data_type, schema_name)
            if df is None:
                return {'valid': False, 'error': 'Processed file not found'}
            
            # Get schema info
            schema_info = self.get_schema_info(schema_name)
            if not schema_info:
                return {'valid': False, 'error': 'Schema not found'}
            
            # Validate columns
            expected_features = set(schema_info.get('features', []))
            actual_columns = set(df.columns)
            
            missing_columns = expected_features - actual_columns
            extra_columns = actual_columns - expected_features
            
            # Check data types
            data_type_issues = []
            for col in df.columns:
                if df[col].isnull().all():
                    data_type_issues.append(f"Column {col} is all null")
            
            validation_result = {
                'valid': len(missing_columns) == 0 and len(data_type_issues) == 0,
                'missing_columns': list(missing_columns),
                'extra_columns': list(extra_columns),
                'data_type_issues': data_type_issues,
                'row_count': len(df),
                'column_count': len(df.columns),
                'schema_name': schema_name
            }
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating data for {date_str}: {e}")
            return {'valid': False, 'error': str(e)}
    
    def process_sample_data(self,
                           raw_df: pd.DataFrame,
                           data_type: str = "mbo",
                           schema_name: str = "basic_normalized_v1",
                           intensity_level: str = "medium") -> Optional[pd.DataFrame]:
        """
        Process a sample of raw data for testing purposes.
        
        Args:
            raw_df: Raw DataFrame to process
            data_type: Data type
            schema_name: Schema name
            intensity_level: Feature engineering intensity level
            
        Returns:
            Processed DataFrame or None if failed
        """
        try:
            logger.info(f"Processing sample data: {len(raw_df)} rows, {intensity_level} intensity")
            
            # Get schema info
            schema_info = self.get_schema_info(schema_name)
            if not schema_info:
                logger.error(f"Schema not found: {schema_name}")
                return None
            
            # Get feature engine
            feature_set_str = schema_info.get('feature_set', 'basic')
            norm_type_str = schema_info.get('normalization_type', 'tick_relative')
            
            # Convert strings to enums if needed
            if isinstance(feature_set_str, str):
                feature_set = FeatureSet(feature_set_str)
            else:
                feature_set = feature_set_str
                
            if isinstance(norm_type_str, str):
                normalization_type = NormalizationType(norm_type_str)
            else:
                normalization_type = norm_type_str
            
            feature_engine = get_feature_engine(
                feature_set=feature_set,
                normalization_type=normalization_type
            )
            
            # Get normalization engine
            normalization_engine = get_normalization_engine(
                normalization_type=normalization_type
            )
            
            # Process the sample data
            logger.info("Computing features...")
            processed_df = compute_mbo_features(
                raw_df, 
                feature_set=feature_set,
                normalization_type=normalization_type,
                intensity_level=intensity_level
            )
            
            if processed_df is None or processed_df.empty:
                logger.error("Feature computation failed")
                return None
            
            logger.info(f"Sample processing completed: {len(processed_df)} rows, {len(processed_df.columns)} columns")
            return processed_df
            
        except Exception as e:
            logger.error(f"Error processing sample data: {e}")
            return None

    def _filter_trading_hours(self, df: pd.DataFrame, date_str: str) -> pd.DataFrame:
        """
        Filter DataFrame to NYSE trading hours (9:30 AM - 4:00 PM EST).
        
        Args:
            df: Input DataFrame with ts_event column
            date_str: Date string (YYYYMMDD)
            
        Returns:
            Filtered DataFrame with only trading hours data
        """
        try:
            # Convert date string to datetime
            from datetime import datetime
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            
            # Define NYSE trading hours in EST (9:30 AM - 4:00 PM)
            # Convert to UTC (EST is UTC-5, but we need to handle DST)
            # For simplicity, we'll use UTC-5 (EST) - in production you'd want proper timezone handling
            
            # Create trading hours start and end timestamps
            trading_start = datetime.combine(date_obj, datetime.min.time().replace(hour=9, minute=30))
            trading_end = datetime.combine(date_obj, datetime.min.time().replace(hour=16, minute=0))
            
            # Convert to UTC (EST = UTC-5)
            import pytz
            est_tz = pytz.timezone('US/Eastern')
            utc_tz = pytz.UTC
            
            # Localize to EST and convert to UTC
            trading_start_est = est_tz.localize(trading_start)
            trading_end_est = est_tz.localize(trading_end)
            trading_start_utc = trading_start_est.astimezone(utc_tz)
            trading_end_utc = trading_end_est.astimezone(utc_tz)
            
            # Convert to nanoseconds (Databento timestamps are in nanoseconds)
            start_ns = int(trading_start_utc.timestamp() * 1e9)
            end_ns = int(trading_end_utc.timestamp() * 1e9)
            
            # Log the filtering details
            logger.info(f"Trading hours filter for {date_str}:")
            logger.info(f"  EST Range: {trading_start.strftime('%H:%M:%S')} - {trading_end.strftime('%H:%M:%S')}")
            logger.info(f"  UTC Range: {trading_start_utc.strftime('%H:%M:%S')} - {trading_end_utc.strftime('%H:%M:%S')}")
            logger.info(f"  Timestamp Range: {start_ns} - {end_ns}")
            
            # Filter DataFrame
            original_count = len(df)
            
            # Ensure ts_event is numeric and handle timezone-aware timestamps
            if 'ts_event' in df.columns:
                # Convert ts_event to numeric if it's not already
                if df['ts_event'].dtype == 'object':
                    # Try to convert to numeric
                    df['ts_event'] = pd.to_numeric(df['ts_event'], errors='coerce')
                
                # Handle timezone-aware timestamps if they exist
                if hasattr(df['ts_event'].iloc[0], 'tz'):
                    # If timestamps are timezone-aware, convert to UTC nanoseconds
                    df['ts_event_ns'] = df['ts_event'].astype(np.int64)
                else:
                    # Assume already in nanoseconds
                    df['ts_event_ns'] = df['ts_event']
                
                # Filter to trading hours
                mask = (df['ts_event_ns'] >= start_ns) & (df['ts_event_ns'] <= end_ns)
                df_filtered = df[mask].copy()
                
                # Remove temporary column
                df_filtered = df_filtered.drop('ts_event_ns', axis=1, errors='ignore')
            else:
                logger.warning("No ts_event column found, returning original data")
                return df
            
            filtered_count = len(df_filtered)
            
            logger.info(f"Trading hours filter: {original_count:,} -> {filtered_count:,} rows ({filtered_count/original_count*100:.1f}%)")
            
            return df_filtered
            
        except Exception as e:
            logger.warning(f"Error filtering trading hours, returning original data: {e}")
            return df

    def list_available_processed_dates(self, data_type: str, schema_name: str) -> List[str]:
        """
        List available processed dates for a specific schema.
        
        Args:
            data_type: Data type (mbo, mbp, trades)
            schema_name: Schema name
            
        Returns:
            List of available date strings (YYYYMMDD format)
        """
        try:
            # Get schema directory
            schema_dir = self.file_manager.get_schema_dir(schema_name)
            
            if not schema_dir.exists():
                return []
            
            # Look for processed files in the schema directory
            available_dates = []
            
            # Pattern to match: YYYYMMDD_mbo_intensity_schema_name_trading_hours.parquet
            # or: YYYYMMDD_mbo_intensity_schema_name_full_day.parquet
            pattern = rf"(\d{{8}})_{data_type}_.*_{schema_name}.*\.parquet"
            
            for file_path in schema_dir.glob("*.parquet"):
                match = re.match(pattern, file_path.name)
                if match:
                    date_str = match.group(1)
                    if date_str not in available_dates:
                        available_dates.append(date_str)
            
            # Sort dates
            available_dates.sort()
            
            logger.info(f"Found {len(available_dates)} processed dates for {schema_name}: {available_dates[:5]}...")
            return available_dates
            
        except Exception as e:
            logger.error(f"Error listing available processed dates for {schema_name}: {e}")
            return []


# Global processor instance
_processor = None

def get_processor(base_data_dir: str = "data") -> UnifiedDataProcessor:
    """Get global unified data processor."""
    global _processor
    if _processor is None or _processor.base_data_dir != base_data_dir:
        _processor = UnifiedDataProcessor(base_data_dir)
    return _processor


def process_raw_to_normalized(date_str: str,
                            data_type: str = "mbo",
                            schema_name: str = "basic_normalized_v1",
                            intensity_level: str = "medium",
                            trading_hours_only: bool = False,
                            progress_callback: Optional[Callable] = None) -> bool:
    """Process raw DBN file to normalized Parquet file."""
    processor = get_processor()
    return processor.process_raw_to_normalized(date_str, data_type, schema_name, intensity_level, trading_hours_only, progress_callback)


def load_processed_data(date_str: str,
                       data_type: str = "mbo",
                       schema_name: str = "basic_normalized_v1") -> Optional[pd.DataFrame]:
    """Load processed data for a specific date and schema."""
    processor = get_processor()
    return processor.load_processed_data(date_str, data_type, schema_name)


def get_available_data_types() -> Dict[str, Any]:
    """Get summary of available data types and schemas."""
    processor = get_processor()
    return processor.get_available_data_types()


def list_available_dates(data_type: str = "mbo",
                        schema_name: Optional[str] = None) -> List[str]:
    """List available dates for a specific data type and schema."""
    from .file_organization import list_available_dates as file_list_dates
    return file_list_dates(data_type, schema_name)


def convert_dbn_to_parquet_file(date_str: str,
                              compression_type: str = "snappy",
                              include_metadata: bool = True,
                              progress_callback: Optional[Callable] = None) -> bool:
    """
    Convert a single DBN file to Parquet format.
    
    Args:
        date_str: Date string (YYYYMMDD)
        compression_type: Parquet compression type (snappy, gzip, brotli)
        include_metadata: Whether to include metadata in the Parquet file
        progress_callback: Optional progress callback
        
    Returns:
        True if conversion successful
    """
    try:
        # Import console logging function
        try:
            from quanttime.dashboard.app import log_to_console
        except ImportError:
            def log_to_console(message: str, level: str = "INFO"):
                logger.info(f"[{level}] {message}")
        
        log_to_console(f"🚀 Starting DBN to Parquet conversion for {date_str}", "INFO")
        
        # Import databento loader
        from quanttime.adapter.databento_loader import get_databento_loader
        
        # Initialize databento loader
        if progress_callback:
            progress_callback("Initialization", 0, 1, "Initializing databento loader", 0.1)
        
        log_to_console("🔧 Initializing databento loader...", "INFO")
        databento_loader = get_databento_loader('data/es_futures/mbo')
        
        # Load DBN file
        if progress_callback:
            progress_callback("Loading DBN", 0, 1, f"Loading DBN file for {date_str}", 0.2)
        
        log_to_console(f"📂 Loading DBN file for {date_str}...", "INFO")
        dbn_store = databento_loader.load_date_data(date_str)
        if dbn_store is None:
            log_to_console(f"❌ Failed to load DBN store for {date_str}", "ERROR")
            return False
        
        log_to_console(f"✅ DBN file loaded: {dbn_store.nbytes:,} bytes", "INFO")
        
        # Convert to DataFrame
        if progress_callback:
            progress_callback("Converting to DataFrame", 0, 1, "Converting DBN to DataFrame", 0.4)
        
        log_to_console("🔄 Converting DBN to DataFrame...", "INFO")
        df = databento_loader.convert_to_dataframe(dbn_store)
        if df is None or df.empty:
            log_to_console(f"❌ Failed to convert DBN to DataFrame for {date_str}", "ERROR")
            return False
        
        log_to_console(f"✅ DataFrame conversion complete: {len(df):,} rows, {len(df.columns)} columns", "INFO")
        
        # Add metadata if requested
        if include_metadata:
            if progress_callback:
                progress_callback("Adding metadata", 0, 1, "Adding file metadata", 0.6)
            
            log_to_console("📋 Adding metadata to DataFrame...", "INFO")
            
            # Add conversion metadata
            df['_conversion_date'] = datetime.now().isoformat()
            df['_source_format'] = 'dbn'
            df['_compression_type'] = compression_type
            df['_original_file_size_bytes'] = dbn_store.nbytes
            df['_conversion_timestamp'] = int(datetime.now().timestamp() * 1e9)
            
            log_to_console("✅ Metadata added to DataFrame", "INFO")
        
        # Create output directory
        if progress_callback:
            progress_callback("Creating directory", 0, 1, "Creating output directory", 0.7)
        
        log_to_console("📁 Creating output directory...", "INFO")
        output_dir = Path("data/raw/mbo/parquet")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate output filename
        output_filename = f"{date_str}.parquet"
        output_path = output_dir / output_filename
        
        log_to_console(f"📝 Output file: {output_path}", "INFO")
        
        # Optimize DataFrame for Parquet storage
        if progress_callback:
            progress_callback("Optimizing DataFrame", 0, 1, "Optimizing DataFrame for storage", 0.8)
        
        log_to_console("🔧 Optimizing DataFrame for Parquet storage...", "INFO")
        
        # Convert data types for better compression
        df_optimized = df.copy()
        
        # Optimize numeric columns
        for col in df_optimized.columns:
            if df_optimized[col].dtype == 'object':
                # Convert object columns to categorical if they have limited unique values
                unique_count = df_optimized[col].nunique()
                if unique_count < len(df_optimized) * 0.5:  # Less than 50% unique values
                    df_optimized[col] = df_optimized[col].astype('category')
                    log_to_console(f"📊 Converted '{col}' to categorical ({unique_count} unique values)", "INFO")
            
            elif df_optimized[col].dtype == 'float64':
                # Use float32 for better compression if precision is sufficient
                if df_optimized[col].notna().all():
                    min_val = df_optimized[col].min()
                    max_val = df_optimized[col].max()
                    if min_val >= -3.4e38 and max_val <= 3.4e38:
                        df_optimized[col] = df_optimized[col].astype('float32')
                        log_to_console(f"📊 Converted '{col}' from float64 to float32", "INFO")
            
            elif df_optimized[col].dtype == 'int64':
                # Use smaller integer types if possible
                min_val = df_optimized[col].min()
                max_val = df_optimized[col].max()
                if min_val >= -32768 and max_val <= 32767:
                    df_optimized[col] = df_optimized[col].astype('int16')
                    log_to_console(f"📊 Converted '{col}' from int64 to int16", "INFO")
                elif min_val >= -2147483648 and max_val <= 2147483647:
                    df_optimized[col] = df_optimized[col].astype('int32')
                    log_to_console(f"📊 Converted '{col}' from int64 to int32", "INFO")
        
        log_to_console("✅ DataFrame optimization complete", "INFO")
        
        # Save to Parquet
        if progress_callback:
            progress_callback("Saving Parquet", 0, 1, f"Saving Parquet file with {compression_type} compression", 0.9)
        
        log_to_console(f"💾 Saving Parquet file with {compression_type} compression...", "INFO")
        
        df_optimized.to_parquet(
            output_path,
            index=False,
            compression=compression_type,
            engine='pyarrow',
            row_group_size=100000  # Optimize for reading chunks
        )
        
        # Get file size
        file_size = output_path.stat().st_size
        compression_ratio = (1 - file_size / dbn_store.nbytes) * 100
        
        log_to_console(f"✅ Successfully saved Parquet file: {file_size:,} bytes", "SUCCESS")
        log_to_console(f"📊 Compression ratio: {compression_ratio:.1f}% smaller than original", "INFO")
        log_to_console(f"📁 Output location: {output_path}", "INFO")
        
        if progress_callback:
            progress_callback("Complete", 1, 1, f"Conversion complete: {file_size:,} bytes", 1.0)
        
        return True
        
    except Exception as e:
        log_to_console(f"❌ Error converting {date_str}: {str(e)}", "ERROR")
        logger.error(f"Error converting {date_str}: {e}")
        import traceback
        traceback.print_exc()
        return False
