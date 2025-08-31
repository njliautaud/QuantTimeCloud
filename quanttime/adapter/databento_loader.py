"""
Official Databento Data Loader for QuantTime ML Trading Suite.

This module uses exclusively the official databento-python-main library
for all data handling, following the official examples and patterns.

REFERENCE SOURCES:
- databento-python-main/examples/historical_timeseries_from_file.py: DBNStore.from_file() usage
- databento-python-main/examples/historical_timeseries_to_df.py: DBNStore.to_df() conversion patterns
- databento-python-main/examples/historical_timeseries_disk_io.py: File path handling and data loading
- databento-python-main/databento/__init__.py: Available components and imports
- databento-python-main/databento/common/dbnstore.py: DBNStore class methods and properties
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

# Set up logging first
logger = logging.getLogger(__name__)

# Official Databento imports
# Reference: databento-python-main/databento/__init__.py - available components
from databento import DBNStore
from databento import Historical
from databento_dbn import Schema

# Handle PriceType import - it may not be available in all versions
try:
    from databento.common.enums import PriceType
    PRICE_TYPE_AVAILABLE = True
except ImportError:
    # Create a fallback enum if PriceType is not available
    from enum import Enum
    class PriceType(Enum):
        BID = "bid"
        ASK = "ask"
        TRADE = "trade"
        OPEN = "open"
        HIGH = "high"
        LOW = "low"
        CLOSE = "close"
    PRICE_TYPE_AVAILABLE = False
    logger.warning("PriceType not available in databento version, using fallback enum")

# Import MBO processor for training optimization
try:
    from quanttime.adapter.mbo_processor import process_mbo_for_training
    MBO_PROCESSOR_AVAILABLE = True
except ImportError as e:
    MBO_PROCESSOR_AVAILABLE = False
    logger.warning(f"MBO processor not available: {e}")


class OfficialDatabentoLoader:
    """
    Official Databento data loader using databento-python-main library.
    
    This class follows the official Databento patterns and examples:
    - Uses DBNStore.from_file() for local DBN files (Reference: databento-python-main/examples/historical_timeseries_from_file.py)
    - Uses Historical client for live data (Reference: databento-python-main/examples/historical_timeseries_to_df.py)
    - Follows official data conversion patterns (Reference: databento-python-main/examples/historical_timeseries_to_df.py)
    - Uses official schema definitions (Reference: databento-python-main/databento/__init__.py)
    """
    
    def __init__(self, data_dir: str = "data", api_key: Optional[str] = None):
        """
        Initialize the official Databento loader.
        
        Args:
            data_dir: Directory containing DBN files
            api_key: Optional Databento API key for live data
            
        Reference: databento-python-main/examples/historical_timeseries_to_df.py - Historical client initialization
        """
        self.data_dir = Path(data_dir)
        self.api_key = api_key
        self.historical_client = None
        
        if api_key:
            try:
                # Reference: databento-python-main/examples/historical_timeseries_to_df.py - Historical client setup
                self.historical_client = Historical(key=api_key)
                logger.info("Historical client initialized with API key")
            except Exception as e:
                logger.warning(f"Failed to initialize Historical client: {e}")
        
        # Scan for available DBN files
        self.available_files = self._scan_dbn_files()
        logger.info(f"Found {len(self.available_files)} DBN files in {self.data_dir}")
    
    def _scan_dbn_files(self) -> List[Path]:
        """
        Scan for DBN files in the data directory.
        
        Reference: databento-python-main/examples/historical_timeseries_disk_io.py - File path handling
        """
        dbn_files = []
        
        if not self.data_dir.exists():
            logger.warning(f"Data directory does not exist: {self.data_dir}")
            return dbn_files
        
        # Look for .dbn files (with or without compression)
        # Reference: databento-python-main/examples/historical_timeseries_from_file.py - File pattern matching
        for pattern in ["*.dbn", "*.dbn.zst", "*.dbn.gz"]:
            dbn_files.extend(self.data_dir.glob(pattern))
        
        # Also look for .dbn files inside date directories
        for date_dir in self.data_dir.glob("glbx-mdp3-*.mbo.dbn"):
            if date_dir.is_dir():
                for dbn_file in date_dir.glob("*.dbn"):
                    dbn_files.append(dbn_file)
        
        # Sort by modification time (newest first)
        dbn_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        logger.info(f"Found {len(dbn_files)} DBN files in {self.data_dir}")
        return dbn_files
    
    def get_available_dates(self) -> List[str]:
        """
        Get list of available dates from DBN files.
        
        Returns:
            List of date strings in YYYYMMDD format
            
        Reference: databento-python-main/examples/historical_timeseries_disk_io.py - File naming patterns
        """
        dates = []
        
        for file_path in self.available_files:
            try:
                # Extract date from filename (e.g., glbx-mdp3-20250813.mbo.dbn.zst)
                # Reference: databento-python-main/examples/historical_timeseries_disk_io.py - Dataset naming convention
                filename = file_path.name
                if "glbx-mdp3-" in filename:
                    # Extract date from glbx-mdp3-YYYYMMDD pattern
                    parts = filename.split("-")
                    if len(parts) >= 3:
                        date_part = parts[2].split(".")[0]  # Get YYYYMMDD part
                        if len(date_part) == 8 and date_part.isdigit():
                            dates.append(date_part)
            except Exception as e:
                logger.warning(f"Could not extract date from {file_path}: {e}")
        
        # Remove duplicates and sort
        dates = sorted(list(set(dates)), reverse=True)
        return dates
    
    def load_dbn_file(self, file_path: Path) -> Optional[DBNStore]:
        """
        Load a DBN file using official DBNStore.from_file().
        Reference: databento-python-main/examples/historical_timeseries_from_file.py - DBNStore.from_file() usage
        
        Args:
            file_path: Path to DBN file
            
        Returns:
            DBNStore object or None if failed
        """
        try:
            logger.info(f"Loading DBN file: {file_path}")
            
            # Check if file exists
            if not file_path.exists():
                logger.error(f"DBN file does not exist: {file_path}")
                return None
            
            # Check file size
            file_size = file_path.stat().st_size
            logger.info(f"File size: {file_size:,} bytes")
            
            # Reference: databento-python-main/examples/historical_timeseries_from_file.py - DBNStore.from_file() method
            dbn_store = DBNStore.from_file(str(file_path))
            
            logger.info(f"Loaded DBN file: {file_path}")
            logger.info(f"   Schema: {dbn_store.schema}")
            logger.info(f"   Dataset: {dbn_store.dataset}")
            logger.info(f"   Symbols: {dbn_store.symbols}")
            logger.info(f"   Size: {dbn_store.nbytes:,} bytes")
            
            return dbn_store
            
        except Exception as e:
            logger.error(f"Failed to load DBN file {file_path}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            return None
    
    def load_date_data(self, date_str: str) -> Optional[DBNStore]:
        """
        Load data for a specific date.
        
        Args:
            date_str: Date string in YYYYMMDD format
            
        Returns:
            DBNStore object or None if failed
            
        Reference: databento-python-main/examples/historical_timeseries_from_file.py - File loading pattern
        """
        # Find DBN file for this date
        target_file = None
        for file_path in self.available_files:
            if date_str in file_path.name:
                target_file = file_path
                break
        
        if not target_file:
            logger.warning(f"No DBN file found for date {date_str}")
            return None
        
        return self.load_dbn_file(target_file)
    
    def convert_to_dataframe(self, dbn_store: DBNStore, 
                           price_type: str = "float",
                           pretty_ts: bool = True,
                           map_symbols: bool = True) -> Optional[pd.DataFrame]:
        """
        Convert DBNStore to DataFrame using official to_df() method.
        Reference: databento-python-main/examples/historical_timeseries_to_df.py - DBNStore.to_df() conversion
        
        Args:
            dbn_store: DBNStore object
            price_type: Price type ("float" or "fixed")
            pretty_ts: Convert timestamps to readable format
            map_symbols: Map instrument IDs to symbols
            
        Returns:
            DataFrame or None if failed
        """
        try:
            logger.info(f"Converting DBNStore to DataFrame...")
            
            # Reference: databento-python-main/examples/historical_timeseries_to_df.py - to_df() method usage
            df = dbn_store.to_df(
                price_type=PriceType.FLOAT if price_type == "float" else PriceType.FIXED,
                pretty_ts=pretty_ts,
                map_symbols=map_symbols
            )
            
            logger.info(f"Converted to DataFrame: {len(df):,} rows, {len(df.columns)} columns")
            logger.info(f"   Columns: {list(df.columns)}")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to convert DBNStore to DataFrame: {e}")
            return None
    
    def load_date_as_dataframe(self, date_str: str) -> Optional[pd.DataFrame]:
        """
        Load data for a date and convert to DataFrame.
        
        Args:
            date_str: Date string in YYYYMMDD format
            
        Returns:
            DataFrame or None if failed
            
        Reference: databento-python-main/examples/historical_timeseries_from_file.py + historical_timeseries_to_df.py
        """
        dbn_store = self.load_date_data(date_str)
        if dbn_store is None:
            return None
        
        return self.convert_to_dataframe(dbn_store)
    
    def load_minute_chunk(self, date_str: str, start_minute: int = 0, 
                         duration_minutes: int = 1) -> Optional[pd.DataFrame]:
        """
        Load a specific minute chunk of data.
        
        Args:
            date_str: Date string in YYYYMMDD format
            start_minute: Starting minute from market open (0 = 9:30 AM)
            duration_minutes: Number of minutes to load
            
        Returns:
            DataFrame with minute chunk or None if failed
            
        Reference: databento-python-main/examples/historical_timeseries_to_df.py - Time range filtering
        """
        try:
            logger.info(f"Loading minute chunk: {date_str}, minute {start_minute} ({duration_minutes} min)")
            
            # Load full date data
            df = self.load_date_as_dataframe(date_str)
            if df is None or df.empty:
                return None
            
            # Filter to specific time window
            # Convert date string to datetime
            date_dt = datetime.strptime(date_str, "%Y%m%d")
            market_open = date_dt.replace(hour=9, minute=30, second=0, microsecond=0)
            
            # Calculate time window
            chunk_start = market_open + timedelta(minutes=start_minute)
            chunk_end = chunk_start + timedelta(minutes=duration_minutes)
            
            logger.info(f"Filtering to time window: {chunk_start.strftime('%H:%M')} - {chunk_end.strftime('%H:%M')}")
            
            # Handle Databento timestamp columns properly
            from quanttime.utils.databento_utils import handle_databento_timestamps
            df = handle_databento_timestamps(df)
            
            if 'datetime' not in df.columns:
                logger.warning("No Databento timestamp columns found for filtering")
                return df
            
            # Filter to time window
            mask = (df['datetime'] >= chunk_start) & (df['datetime'] < chunk_end)
            chunk_df = df[mask].copy()
            
            logger.info(f"Minute chunk loaded: {len(chunk_df):,} records")
            logger.info(f"   Time range: {chunk_df['datetime'].min().strftime('%H:%M:%S')} - {chunk_df['datetime'].max().strftime('%H:%M:%S')}")
            
            return chunk_df
            
        except Exception as e:
            logger.error(f"Failed to load minute chunk: {e}")
            return None
    
    def process_mbo_for_training(self, date: str, max_price_distance: int = 100) -> Optional[pd.DataFrame]:
        """
        Process MBO data for training with order book context and cumulative delta.
        
        Args:
            date: Date string in YYYYMMDD format
            max_price_distance: Maximum price points to track in order book
            
        Returns:
            DataFrame with training features or None if failed
            
        Reference: databento-python-main/examples/historical_timeseries_to_df.py - DataFrame processing
        """
        if not MBO_PROCESSOR_AVAILABLE:
            logger.error("MBO processor not available for training data preparation")
            return None
        
        try:
            # Load raw MBO data
            mbo_df = self.load_date_as_dataframe(date)
            
            if mbo_df is None or mbo_df.empty:
                logger.error(f"No MBO data available for date {date}")
                return None
            
            logger.info(f"Processing MBO data for training: {len(mbo_df)} records")
            
            # Process through MBO processor
            training_features = process_mbo_for_training(mbo_df, max_price_distance)
            
            if training_features is None or training_features.empty:
                logger.error("Failed to generate training features from MBO data")
                return None
            
            logger.info(f"Generated {len(training_features)} training samples with {len(training_features.columns)} features")
            
            return training_features
            
        except Exception as e:
            logger.error(f"Error processing MBO data for training: {e}")
            return None
    
    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get summary of available data.
        
        Returns:
            Dictionary with data summary
            
        Reference: databento-python-main/databento/common/dbnstore.py - DBNStore properties
        """
        available_dates = self.get_available_dates()
        
        summary = {
            'total_files': len(self.available_files),
            'available_dates': len(available_dates),
            'date_range': None,
            'file_details': []
        }
        
        if available_dates:
            summary['date_range'] = f"{available_dates[-1]} to {available_dates[0]}"
        
        # Get details for first few files
        for file_path in self.available_files[:5]:
            try:
                stat = file_path.stat()
                summary['file_details'].append({
                    'name': file_path.name,
                    'size_mb': stat.st_size / (1024 * 1024),
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                })
            except Exception as e:
                logger.warning(f"Could not get file details for {file_path}: {e}")
        
        return summary

    def load_dbn_files_memory_optimized(self, date_range: List[str], 
                                      max_memory_gb: float = 12.0,
                                      progress_callback: Optional[callable] = None) -> pd.DataFrame:
        """
        Load multiple DBN files with memory optimization and progress tracking.
        
        Args:
            date_range: List of date strings in YYYYMMDD format
            max_memory_gb: Maximum memory usage in GB
            progress_callback: Optional callback for progress tracking
            
        Returns:
            Combined DataFrame with all data
            
        Reference: databento-python-main/examples/historical_timeseries_from_file.py - Batch loading
        """
        try:
            logger.info(f"Loading {len(date_range)} DBN files with memory optimization")
            
            # Initialize progress tracking
            total_files = len(date_range)
            if progress_callback:
                progress_callback("Loading DBN Files", 0, total_files, "Initializing...", 0.0)
            
            combined_dataframes = []
            total_records = 0
            
            for i, date_str in enumerate(date_range):
                try:
                    # Update progress
                    if progress_callback:
                        progress_callback("Loading DBN Files", i + 1, total_files, f"Loading {date_str}...", 0.0)
                    
                    # Load DBN file for this date
                    dbn_store = self.load_date_data(date_str)
                    if dbn_store is None:
                        logger.warning(f"No data found for date {date_str}")
                        if progress_callback:
                            progress_callback("Loading DBN Files", i + 1, total_files, f"No data for {date_str}", 1.0)
                        continue
                    
                    # Convert to DataFrame
                    if progress_callback:
                        progress_callback("Loading DBN Files", i + 1, total_files, f"Converting {date_str} to DataFrame...", 0.5)
                    
                    df = self.convert_to_dataframe(dbn_store)
                    if df is None or df.empty:
                        logger.warning(f"Empty DataFrame for date {date_str}")
                        if progress_callback:
                            progress_callback("Loading DBN Files", i + 1, total_files, f"Empty data for {date_str}", 1.0)
                        continue
                    
                    # Add source date for tracking
                    df['source_date'] = date_str
                    
                    # Check memory usage
                    df_memory_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
                    logger.info(f"Date {date_str}: {len(df):,} records, {df_memory_mb:.1f} MB")
                    
                    # Memory optimization: if we're approaching the limit, process in chunks
                    if df_memory_mb > max_memory_gb * 1024 * 0.8:  # 80% of limit
                        logger.warning(f"Large file detected for {date_str}, processing in chunks")
                        
                        # Process in smaller chunks
                        chunk_size = len(df) // 4  # Split into 4 chunks
                        for chunk_idx in range(0, len(df), chunk_size):
                            chunk_df = df.iloc[chunk_idx:chunk_idx + chunk_size].copy()
                            combined_dataframes.append(chunk_df)
                            total_records += len(chunk_df)
                            
                            # Update progress for chunks
                            if progress_callback:
                                chunk_progress = (chunk_idx + chunk_size) / len(df)
                                progress_callback("Loading DBN Files", i + 1, total_files, 
                                                f"Processing {date_str} chunk {chunk_idx//chunk_size + 1}/4...", 
                                                min(chunk_progress, 1.0))
                    else:
                        combined_dataframes.append(df)
                        total_records += len(df)
                    
                    # Check total memory usage
                    total_memory_mb = sum(df.memory_usage(deep=True).sum() for df in combined_dataframes) / (1024 * 1024)
                    if total_memory_mb > max_memory_gb * 1024:
                        logger.warning(f"Memory usage approaching limit: {total_memory_mb:.1f} MB")
                    
                    # Update progress to show completion
                    if progress_callback:
                        progress_callback("Loading DBN Files", i + 1, total_files, f"Completed {date_str}", 1.0)
                        
                except Exception as e:
                    logger.error(f"Error loading date {date_str}: {e}")
                    if progress_callback:
                        progress_callback("Loading DBN Files", i + 1, total_files, f"Error loading {date_str}: {str(e)}", 1.0)
                    continue
            
            # Combine all DataFrames
            if progress_callback:
                progress_callback("Loading DBN Files", total_files, total_files, "Combining DataFrames...", 0.0)
            
            if not combined_dataframes:
                logger.error("No data loaded from any date")
                if progress_callback:
                    progress_callback("Loading DBN Files", total_files, total_files, "No data loaded", 1.0)
                return pd.DataFrame()
            
            # Concatenate all DataFrames
            combined_df = pd.concat(combined_dataframes, ignore_index=True)
            
            # Sort by timestamp if available
            if 'ts_event' in combined_df.columns:
                combined_df = combined_df.sort_values('ts_event').reset_index(drop=True)
            elif 'datetime' in combined_df.columns:
                combined_df = combined_df.sort_values('datetime').reset_index(drop=True)
            
            logger.info(f"Successfully loaded {len(combined_df):,} total records from {len(date_range)} dates")
            logger.info(f"Final memory usage: {combined_df.memory_usage(deep=True).sum() / (1024 * 1024):.1f} MB")
            
            if progress_callback:
                progress_callback("Loading DBN Files", total_files, total_files, "Data loading complete!", 1.0)
            
            return combined_df
            
        except Exception as e:
            logger.error(f"Error in load_dbn_files_memory_optimized: {e}")
            if progress_callback:
                progress_callback("Loading DBN Files", total_files, total_files, f"Error: {str(e)}", 1.0)
            return pd.DataFrame()
    
    def load_sample_data(self, date_str: str, max_events: int = 500) -> Optional[pd.DataFrame]:
        """
        Load a small sample of data for testing purposes.
        
        Args:
            date_str: Date string in YYYYMMDD format
            max_events: Maximum number of events to load
            
        Returns:
            DataFrame with sample data or None if failed
        """
        try:
            logger.info(f"Loading sample data: {date_str}, max {max_events} events")
            
            # Load full date data
            df = self.load_date_as_dataframe(date_str)
            if df is None or df.empty:
                logger.error(f"No data found for date {date_str}")
                return None
            
            # Take a sample of the data
            if len(df) > max_events:
                # Take first max_events rows for consistent testing
                sample_df = df.head(max_events).copy()
                logger.info(f"Sampled {len(sample_df)} events from {len(df)} total events")
            else:
                sample_df = df.copy()
                logger.info(f"Using all {len(sample_df)} events (less than max)")
            
            # Add source date for tracking
            sample_df['source_date'] = date_str
            
            logger.info(f"Sample data loaded: {len(sample_df)} rows, {len(sample_df.columns)} columns")
            return sample_df
            
        except Exception as e:
            logger.error(f"Failed to load sample data for {date_str}: {e}")
            return None


# Global loader instance
_loader_instance = None

def get_databento_loader(data_dir: str = "data", api_key: Optional[str] = None) -> OfficialDatabentoLoader:
    """
    Get or create global Databento loader instance.
    
    Args:
        data_dir: Data directory path
        api_key: Optional API key
        
    Returns:
        OfficialDatabentoLoader instance
        
    Reference: databento-python-main/examples/historical_timeseries_to_df.py - Client singleton pattern
    """
    global _loader_instance
    
    if _loader_instance is None:
        _loader_instance = OfficialDatabentoLoader(data_dir=data_dir, api_key=api_key)
    
    return _loader_instance
