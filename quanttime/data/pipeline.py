"""
QuantTime Data Pipeline

Comprehensive data pipeline for Databento MBO (Market By Order) Level 3 data.
Handles historical data loading, live streaming, file management, and data processing.
"""

import os
import time
import logging
import threading
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
import queue
import json

import pandas as pd
import numpy as np
import databento as db
from databento import Live

from ..utils.config import AppConfig
from ..utils.logging import get_logger

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('quanttime_pipeline.log')  # File output
    ]
)

logger = get_logger(__name__)


@dataclass
class MBOEvent:
    """Represents a single MBO event with proper field mapping."""
    ts_recv: int  # Capture-server-received timestamp (nanoseconds)
    ts_event: int  # Matching-engine-received timestamp (nanoseconds)
    rtype: int  # Record type (always 160 for MBO)
    publisher_id: int  # Publisher ID
    instrument_id: int  # Numeric instrument ID
    action: str  # Event action (A/C/M/R/T/F/N)
    side: str  # Side (A=Ask, B=Bid, N=None)
    price: int  # Order price (1 unit = 1e-9)
    size: int  # Order quantity
    channel_id: int  # Channel ID
    order_id: int  # Order ID assigned by venue
    flags: int  # Bit field for event characteristics
    ts_in_delta: int  # Matching-engine-sending timestamp delta
    sequence: int  # Message sequence number
    symbol: str  # Symbol name
    
    @property
    def price_float(self) -> float:
        """Convert price from integer to float."""
        try:
            # Handle different price formats
            if isinstance(self.price, (int, float)):
                # If price is already a reasonable float, return as is
                if 0 < self.price < 100000:  # Reasonable price range
                    return float(self.price)
                else:
                    # Convert from nanosecond precision
                    return self.price / 1e9
            else:
                logger.error(f"Invalid price type: {type(self.price)}, price={self.price}")
                return 0.0
        except (TypeError, ValueError) as e:
            logger.error(f"Price conversion error: {e}, price={self.price}")
            return 0.0
    
    @property
    def ts_event_dt(self) -> datetime:
        """Convert ts_event to datetime."""
        try:
            return pd.to_datetime(self.ts_event, unit='ns')
        except (TypeError, ValueError) as e:
            logger.error(f"Timestamp conversion error: {e}, ts_event={self.ts_event}")
            return pd.Timestamp.now()
    
    @property
    def ts_recv_dt(self) -> datetime:
        """Convert ts_recv to datetime."""
        try:
            return pd.to_datetime(self.ts_recv, unit='ns')
        except (TypeError, ValueError) as e:
            logger.error(f"Timestamp conversion error: {e}, ts_recv={self.ts_recv}")
            return pd.Timestamp.now()


@dataclass
class DataPipelineConfig:
    """Configuration for the data pipeline."""
    # Databento configuration
    databento_key: str = ""
    dataset: str = "GLBX.MDP3"
    schema: str = "mbo"
    
    # File management
    data_dir: str = "./data/es_futures/mbo"
    archive_dir: str = "./data/archive"
    live_stream_dir: str = "./data/live_streams"  # Added missing attribute
    
    # Streaming configuration
    stream_buffer_size: int = 10000
    flush_interval_seconds: int = 60
    max_file_size_mb: int = 100
    
    # Symbol configuration
    default_symbols: List[str] = field(default_factory=lambda: ["ES.c.0", "ES.c.1"])
    
    # Processing configuration
    enable_order_book_reconstruction: bool = True
    enable_footprint_generation: bool = True
    enable_tick_aggregation: bool = True
    
    # Data validation
    validate_data: bool = True
    log_data_quality: bool = True


class DataValidator:
    """Validates MBO data quality and alignment."""
    
    @staticmethod
    def validate_mbo_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
        """Validate MBO DataFrame and return quality metrics."""
        validation_results = {
            'total_rows': len(df),
            'missing_values': {},
            'data_types': {},
            'timestamp_range': {},
            'price_range': {},
            'action_distribution': {},
            'symbol_distribution': {},
            'warnings': [],
            'errors': []
        }
        
        try:
            # Check for missing values
            missing_counts = df.isnull().sum()
            validation_results['missing_values'] = missing_counts[missing_counts > 0].to_dict()
            
            # Check data types
            validation_results['data_types'] = df.dtypes.to_dict()
            
            # Validate timestamps
            if 'ts_event' in df.columns:
                ts_events = pd.to_datetime(df['ts_event'], errors='coerce')
                valid_ts = ts_events.dropna()
                if len(valid_ts) > 0:
                    validation_results['timestamp_range'] = {
                        'min': valid_ts.min().isoformat(),
                        'max': valid_ts.max().isoformat(),
                        'valid_count': len(valid_ts),
                        'invalid_count': len(ts_events) - len(valid_ts)
                    }
                else:
                    validation_results['errors'].append("No valid timestamps found")
            
            # Validate prices
            if 'price' in df.columns:
                prices = pd.to_numeric(df['price'], errors='coerce')
                valid_prices = prices.dropna()
                if len(valid_prices) > 0:
                    validation_results['price_range'] = {
                        'min': float(valid_prices.min()),
                        'max': float(valid_prices.max()),
                        'valid_count': len(valid_prices),
                        'invalid_count': len(prices) - len(valid_prices)
                    }
                else:
                    validation_results['warnings'].append("No valid prices found")
            
            # Check action distribution
            if 'action' in df.columns:
                action_counts = df['action'].value_counts()
                validation_results['action_distribution'] = action_counts.to_dict()
                
                # Validate action codes
                valid_actions = {'A', 'C', 'M', 'F', 'T', 'R'}
                invalid_actions = set(action_counts.index) - valid_actions
                if invalid_actions:
                    validation_results['warnings'].append(f"Invalid action codes found: {invalid_actions}")
            
            # Check symbol distribution
            if 'symbol' in df.columns:
                symbol_counts = df['symbol'].value_counts()
                validation_results['symbol_distribution'] = symbol_counts.head(10).to_dict()
            
            # Log validation results
            if validation_results['warnings']:
                logger.warning(f"Data validation warnings: {validation_results['warnings']}")
            if validation_results['errors']:
                logger.error(f"Data validation errors: {validation_results['errors']}")
            
            logger.info(f"Data validation completed: {validation_results['total_rows']} rows processed")
            
        except Exception as e:
            logger.error(f"Data validation failed: {e}")
            validation_results['errors'].append(str(e))
        
        return validation_results
    
    @staticmethod
    def fix_data_alignment(df: pd.DataFrame) -> pd.DataFrame:
        """Fix common data alignment issues."""
        logger.info("Starting data alignment fixes...")
        
        try:
            # Create a copy to avoid modifying original
            fixed_df = df.copy()
            
            # Fix timestamp alignment
            if 'ts_event' in fixed_df.columns:
                # Ensure timestamps are datetime objects
                fixed_df['ts_event'] = pd.to_datetime(fixed_df['ts_event'], errors='coerce')
                
                # Remove rows with invalid timestamps
                invalid_ts = fixed_df['ts_event'].isna()
                if invalid_ts.sum() > 0:
                    logger.warning(f"Removing {invalid_ts.sum()} rows with invalid timestamps")
                    fixed_df = fixed_df[~invalid_ts]
            
            # Fix price alignment
            if 'price' in fixed_df.columns:
                # Convert prices to numeric, handling NaN values
                fixed_df['price'] = pd.to_numeric(fixed_df['price'], errors='coerce')
                
                # For execution events (F), ensure prices are valid
                execution_mask = fixed_df['action'] == 'F'
                invalid_execution_prices = execution_mask & fixed_df['price'].isna()
                if invalid_execution_prices.sum() > 0:
                    logger.warning(f"Found {invalid_execution_prices.sum()} execution events with invalid prices")
            
            # Fix side alignment
            if 'side' in fixed_df.columns:
                # Ensure side values are valid
                valid_sides = {'A', 'B', 'N'}
                invalid_sides = ~fixed_df['side'].isin(valid_sides)
                if invalid_sides.sum() > 0:
                    logger.warning(f"Found {invalid_sides.sum()} rows with invalid side values")
                    # Replace invalid sides with 'N' (neutral)
                    fixed_df.loc[invalid_sides, 'side'] = 'N'
            
            # Sort by timestamp to ensure chronological order
            if 'ts_event' in fixed_df.columns:
                fixed_df = fixed_df.sort_values('ts_event').reset_index(drop=True)
                logger.info(f"Data sorted by timestamp: {fixed_df['ts_event'].min()} to {fixed_df['ts_event'].max()}")
            
            logger.info(f"Data alignment completed: {len(fixed_df)} rows remaining")
            return fixed_df
            
        except Exception as e:
            logger.error(f"Data alignment failed: {e}")
            return df


class MBODataProcessor:
    """Processes MBO data and converts to various formats."""
    
    def __init__(self, config: DataPipelineConfig):
        self.config = config
        self.order_book = {'bids': {}, 'asks': {}}
        self.order_book_lock = threading.Lock()
        self.validator = DataValidator()
        
    def process_mbo_event(self, event: MBOEvent) -> Dict[str, Any]:
        """Process a single MBO event and return processed data."""
        try:
            processed = {
                'ts_event': event.ts_event_dt,
                'ts_recv': event.ts_recv_dt,
                'symbol': event.symbol,
                'action': event.action,
                'side': event.side,
                'price': event.price_float,
                'size': event.size,
                'order_id': event.order_id,
                'instrument_id': event.instrument_id,
                'sequence': event.sequence
            }
            
            # Update order book if enabled
            if self.config.enable_order_book_reconstruction:
                self._update_order_book(event)
                processed['order_book'] = self._get_order_book_snapshot()
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing MBO event: {e}")
            logger.error(f"Event data: {event}")
            return {}
    
    def _update_order_book(self, event: MBOEvent):
        """Update the order book with an MBO event."""
        try:
            with self.order_book_lock:
                price_key = event.price
                
                if event.action == 'A':  # Add order
                    if event.side == 'B':  # Bid
                        self.order_book['bids'][price_key] = self.order_book['bids'].get(price_key, 0) + event.size
                    elif event.side == 'A':  # Ask
                        self.order_book['asks'][price_key] = self.order_book['asks'].get(price_key, 0) + event.size
                        
                elif event.action == 'C':  # Cancel order
                    if event.side == 'B':  # Bid
                        if price_key in self.order_book['bids']:
                            self.order_book['bids'][price_key] = max(0, self.order_book['bids'][price_key] - event.size)
                            if self.order_book['bids'][price_key] == 0:
                                del self.order_book['bids'][price_key]
                    elif event.side == 'A':  # Ask
                        if price_key in self.order_book['asks']:
                            self.order_book['asks'][price_key] = max(0, self.order_book['asks'][price_key] - event.size)
                            if self.order_book['asks'][price_key] == 0:
                                del self.order_book['asks'][price_key]
                                
                elif event.action == 'F':  # Fill/Execute
                    if event.side == 'B':  # Bid
                        if price_key in self.order_book['bids']:
                            self.order_book['bids'][price_key] = max(0, self.order_book['bids'][price_key] - event.size)
                            if self.order_book['bids'][price_key] == 0:
                                del self.order_book['bids'][price_key]
                    elif event.side == 'A':  # Ask
                        if price_key in self.order_book['asks']:
                            self.order_book['asks'][price_key] = max(0, self.order_book['asks'][price_key] - event.size)
                            if self.order_book['asks'][price_key] == 0:
                                del self.order_book['asks'][price_key]
                                
        except Exception as e:
            logger.error(f"Error updating order book: {e}")
    
    def _get_order_book_snapshot(self) -> Dict[str, List]:
        """Get current order book snapshot."""
        try:
            with self.order_book_lock:
                bids = sorted([(price/1e9, size) for price, size in self.order_book['bids'].items()], reverse=True)
                asks = sorted([(price/1e9, size) for price, size in self.order_book['asks'].items()])
                return {
                    'bids': bids[:10],  # Top 10 bids
                    'asks': asks[:10],  # Top 10 asks
                    'timestamp': datetime.now()
                }
        except Exception as e:
            logger.error(f"Error getting order book snapshot: {e}")
            return {'bids': [], 'asks': [], 'timestamp': datetime.now()}
    
    def aggregate_to_ticks(self, mbo_events: List[MBOEvent]) -> pd.DataFrame:
        """Aggregate MBO events to tick data."""
        try:
            if not mbo_events:
                logger.warning("No MBO events provided for tick aggregation")
                return pd.DataFrame()
            
            # Filter for execution events only
            executions = [event for event in mbo_events if event.action == 'F']
            
            if not executions:
                logger.warning("No execution events found in MBO data")
                return pd.DataFrame()
            
            logger.info(f"Processing {len(executions)} execution events for tick data")
            
            ticks = []
            for event in executions:
                try:
                    tick = {
                        'ts': event.ts_event_dt,
                        'price': event.price_float,
                        'size': event.size,
                        'side': event.side,
                        'symbol': event.symbol,
                        'order_id': event.order_id
                    }
                    ticks.append(tick)
                except Exception as e:
                    logger.error(f"Error processing execution event: {e}")
                    continue
            
            if not ticks:
                logger.warning("No valid ticks generated from execution events")
                return pd.DataFrame()
            
            ticks_df = pd.DataFrame(ticks)
            
            # Sort by timestamp and ensure proper data types
            ticks_df = ticks_df.sort_values('ts').reset_index(drop=True)
            
            # Validate tick data
            if self.config.validate_data:
                self._validate_tick_data(ticks_df)
            
            logger.info(f"Generated {len(ticks_df)} ticks from MBO data")
            return ticks_df
            
        except Exception as e:
            logger.error(f"Error aggregating to ticks: {e}")
            logger.error(traceback.format_exc())
            return pd.DataFrame()
    
    def _validate_tick_data(self, ticks_df: pd.DataFrame):
        """Validate tick data quality."""
        try:
            # Check for missing values
            missing = ticks_df.isnull().sum()
            if missing.sum() > 0:
                logger.warning(f"Missing values in tick data: {missing[missing > 0].to_dict()}")
            
            # Check price range
            if 'price' in ticks_df.columns:
                price_range = ticks_df['price'].describe()
                logger.info(f"Price range: {price_range['min']:.2f} to {price_range['max']:.2f}")
                
                # Check for suspicious prices
                zero_prices = (ticks_df['price'] == 0).sum()
                if zero_prices > 0:
                    logger.warning(f"Found {zero_prices} ticks with zero price")
            
            # Check timestamp consistency
            if 'ts' in ticks_df.columns:
                time_diff = ticks_df['ts'].diff().dropna()
                if len(time_diff) > 0:
                    logger.info(f"Average time between ticks: {time_diff.mean()}")
                    
                    # Check for duplicate timestamps
                    duplicates = ticks_df['ts'].duplicated().sum()
                    if duplicates > 0:
                        logger.warning(f"Found {duplicates} duplicate timestamps")
            
        except Exception as e:
            logger.error(f"Error validating tick data: {e}")
    
    def generate_footprint(self, mbo_events: List[MBOEvent], 
                          time_window_minutes: int = 1) -> pd.DataFrame:
        """Generate footprint data from MBO events."""
        try:
            if not mbo_events:
                logger.warning("No MBO events provided for footprint generation")
                return pd.DataFrame()
            
            logger.info(f"Generating footprint from {len(mbo_events)} MBO events")
            
            # Convert to DataFrame for easier processing
            df_data = []
            for event in mbo_events:
                try:
                    df_data.append({
                        'ts': event.ts_event_dt,
                        'price': event.price_float,
                        'size': event.size,
                        'side': event.side,
                        'action': event.action,
                        'symbol': event.symbol
                    })
                except Exception as e:
                    logger.error(f"Error processing event for footprint: {e}")
                    continue
            
            if not df_data:
                logger.warning("No valid data for footprint generation")
                return pd.DataFrame()
            
            df = pd.DataFrame(df_data)
            
            # Calculate delta (buy volume - sell volume)
            df['delta'] = df['size'].where(df['side'] == 'B', -df['size'])
            
            # Aggregate by time window
            df.set_index('ts', inplace=True)
            footprint = df.resample(f'{time_window_minutes}min').agg({
                'price': ['first', 'last', 'max', 'min'],
                'size': 'sum',
                'delta': 'sum'
            }).round(2)
            
            footprint.columns = ['open', 'close', 'high', 'low', 'volume', 'delta']
            footprint['delta_ratio'] = (footprint['delta'] / footprint['volume']).fillna(0)
            
            logger.info(f"Generated footprint with {len(footprint)} time windows")
            return footprint.reset_index()
            
        except Exception as e:
            logger.error(f"Error generating footprint: {e}")
            logger.error(traceback.format_exc())
            return pd.DataFrame()


class LiveDataStreamer:
    """Handles live data streaming from Databento."""
    
    def __init__(self, config: DataPipelineConfig, processor: MBODataProcessor):
        self.config = config
        self.processor = processor
        self.live_client: Optional[Live] = None
        self.is_streaming = False
        self.current_file: Optional[str] = None
        self.event_queue = queue.Queue(maxsize=config.stream_buffer_size)
        self.stream_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Ensure directories exist
        if hasattr(self.config, 'live_stream_dir') and self.config.live_stream_dir:
            Path(self.config.live_stream_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.data_dir).mkdir(parents=True, exist_ok=True)
    
    def start_streaming(self, symbols: Optional[List[str]] = None) -> bool:
        """Start live data streaming."""
        if self.is_streaming:
            logger.warning("Already streaming data")
            return False
        
        try:
            logger.info(f"Starting live streaming with symbols: {symbols}")
            
            # Initialize live client
            self.live_client = Live(key=self.config.databento_key)
            
            # Subscribe to symbols
            symbols = symbols or self.config.default_symbols
            self.live_client.subscribe(
                dataset=self.config.databento_dataset,
                schema=self.config.schema,
                stype_in="continuous",
                symbols=symbols
            )
            
            # Create output file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if hasattr(self.config, 'live_stream_dir') and self.config.live_stream_dir:
                self.current_file = f"{self.config.live_stream_dir}/live_mbo_{timestamp}.dbn"
            else:
                # Fallback to data_dir if live_stream_dir is not set
                self.current_file = f"{self.config.data_dir}/live_mbo_{timestamp}.dbn"
            self.live_client.add_stream(self.current_file)
            
            # Start streaming
            self.live_client.start()
            self.is_streaming = True
            
            # Start processing thread
            self.stream_thread = threading.Thread(target=self._process_stream, daemon=True)
            self.stream_thread.start()
            
            logger.info(f"Started live streaming to {self.current_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def stop_streaming(self):
        """Stop live data streaming."""
        if not self.is_streaming:
            return
        
        logger.info("Stopping live streaming...")
        self.stop_event.set()
        self.is_streaming = False
        
        if self.live_client:
            try:
                self.live_client.close()
            except Exception as e:
                logger.error(f"Error closing live client: {e}")
        
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=5)
        
        logger.info("Stopped live streaming")
    
    def _process_stream(self):
        """Process the live data stream."""
        try:
            logger.info("Starting stream processing thread")
            while self.is_streaming and not self.stop_event.is_set():
                # Process events from queue
                try:
                    while not self.event_queue.empty():
                        event = self.event_queue.get_nowait()
                        processed = self.processor.process_mbo_event(event)
                        
                        # Here you can add real-time processing logic
                        # For example, sending to ZeroMQ, updating dashboards, etc.
                        
                except queue.Empty:
                    pass
                
                time.sleep(0.001)  # Small delay to prevent busy waiting
                
        except Exception as e:
            logger.error(f"Error in stream processing: {e}")
            logger.error(traceback.format_exc())
    
    def get_current_file(self) -> Optional[str]:
        """Get the current streaming file path."""
        return self.current_file


class DataFileManager:
    """Manages data files and archiving."""
    
    def __init__(self, config: DataPipelineConfig):
        self.config = config
        self.ensure_directories()
    
    def ensure_directories(self):
        """Ensure all required directories exist."""
        directories = [self.config.data_dir, self.config.archive_dir]
        if hasattr(self.config, 'live_stream_dir') and self.config.live_stream_dir:
            directories.append(self.config.live_stream_dir)
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured directory exists: {directory}")
    
    def save_mbo_data(self, df: pd.DataFrame, filename: str, 
                     format: str = "parquet") -> str:
        """Save MBO data to file."""
        try:
            filepath = Path(self.config.data_dir) / filename
            
            if format == "parquet":
                filepath = filepath.with_suffix(".parquet")
                df.to_parquet(filepath, index=False)
            elif format == "csv":
                filepath = filepath.with_suffix(".csv")
                df.to_csv(filepath, index=False)
            elif format == "dbn":
                # Save as DBN format using Databento
                filepath = filepath.with_suffix(".dbn")
                # Note: This would require implementing DBN writing
                # For now, save as parquet
                df.to_parquet(filepath.with_suffix(".parquet"), index=False)
            
            logger.info(f"Saved MBO data to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving MBO data: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def load_mbo_data(self, filepath: str) -> pd.DataFrame:
        """Load MBO data from file."""
        try:
            filepath = Path(filepath)
            logger.info(f"Loading MBO data from: {filepath}")
            
            if filepath.suffix == ".parquet":
                df = pd.read_parquet(filepath)
            elif filepath.suffix == ".csv":
                df = pd.read_csv(filepath)
            elif filepath.suffix == ".dbn":
                # Load DBN file using Databento
                dbn_store = db.read_dbn(str(filepath))
                df = dbn_store.to_df()
            else:
                raise ValueError(f"Unsupported file format: {filepath.suffix}")
            
            logger.info(f"Loaded {len(df)} rows from {filepath}")
            return df
            
        except Exception as e:
            logger.error(f"Error loading MBO data from {filepath}: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def archive_file(self, filepath: str, archive_name: Optional[str] = None) -> str:
        """Archive a file to the archive directory."""
        try:
            source_path = Path(filepath)
            
            if not source_path.exists():
                raise FileNotFoundError(f"File not found: {filepath}")
            
            if archive_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_name = f"{source_path.stem}_{timestamp}{source_path.suffix}"
            
            archive_path = Path(self.config.archive_dir) / archive_name
            
            # Move file to archive
            source_path.rename(archive_path)
            
            logger.info(f"Archived {filepath} to {archive_path}")
            return str(archive_path)
            
        except Exception as e:
            logger.error(f"Error archiving file {filepath}: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def list_data_files(self, pattern: str = "*.parquet") -> List[str]:
        """List all data files matching pattern."""
        try:
            data_dir = Path(self.config.data_dir)
            files = list(data_dir.glob(pattern))
            file_list = [str(f) for f in sorted(files)]
            logger.info(f"Found {len(file_list)} files matching pattern: {pattern}")
            return file_list
        except Exception as e:
            logger.error(f"Error listing data files: {e}")
            return []
    
    def cleanup_old_files(self, max_age_days: int = 30):
        """Clean up old files."""
        try:
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            cleaned_count = 0
            
            directories = [self.config.data_dir]
            if hasattr(self.config, 'live_stream_dir') and self.config.live_stream_dir:
                directories.append(self.config.live_stream_dir)
            
            for directory in directories:
                dir_path = Path(directory)
                for file_path in dir_path.iterdir():
                    if file_path.is_file():
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_time < cutoff_time:
                            file_path.unlink()
                            cleaned_count += 1
                            logger.info(f"Cleaned up old file: {file_path}")
            
            logger.info(f"Cleanup completed: {cleaned_count} files removed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            logger.error(traceback.format_exc())


class DataPipeline:
    """Main data pipeline orchestrator."""
    
    def __init__(self, config: DataPipelineConfig):
        self.config = config
        self.processor = MBODataProcessor(config)
        self.streamer = LiveDataStreamer(config, self.processor)
        self.file_manager = DataFileManager(config)
        self.validator = DataValidator()
        
        logger.info("Data pipeline initialized successfully")
    
    def start_live_streaming(self, symbols: Optional[List[str]] = None) -> bool:
        """Start live data streaming."""
        return self.streamer.start_streaming(symbols)
    
    def stop_live_streaming(self):
        """Stop live data streaming."""
        self.streamer.stop_streaming()
    
    def process_historical_data(self, filepath: str) -> Dict[str, pd.DataFrame]:
        """Process historical MBO data file."""
        try:
            logger.info(f"Processing historical data: {filepath}")
            
            # Load data
            df = self.file_manager.load_mbo_data(filepath)
            
            # Validate and fix data alignment
            if self.config.validate_data:
                validation_results = self.validator.validate_mbo_dataframe(df)
                logger.info(f"Data validation results: {validation_results}")
                
                if validation_results['errors']:
                    logger.error(f"Critical data errors found: {validation_results['errors']}")
                
                # Fix data alignment issues
                df = self.validator.fix_data_alignment(df)
            
            # Convert to MBO events
            mbo_events = []
            conversion_errors = 0
            
            for idx, row in df.iterrows():
                try:
                    event = MBOEvent(
                        ts_recv=row.get('ts_recv', 0),
                        ts_event=row.get('ts_event', 0),
                        rtype=row.get('rtype', 160),
                        publisher_id=row.get('publisher_id', 0),
                        instrument_id=row.get('instrument_id', 0),
                        action=row.get('action', ''),
                        side=row.get('side', ''),
                        price=row.get('price', 0),
                        size=row.get('size', 0),
                        channel_id=row.get('channel_id', 0),
                        order_id=row.get('order_id', 0),
                        flags=row.get('flags', 0),
                        ts_in_delta=row.get('ts_in_delta', 0),
                        sequence=row.get('sequence', 0),
                        symbol=row.get('symbol', '')
                    )
                    mbo_events.append(event)
                except Exception as e:
                    conversion_errors += 1
                    if conversion_errors <= 10:  # Log first 10 errors
                        logger.error(f"Error converting row {idx} to MBO event: {e}")
                    continue
            
            if conversion_errors > 0:
                logger.warning(f"Failed to convert {conversion_errors} rows to MBO events")
            
            logger.info(f"Converted {len(mbo_events)} rows to MBO events")
            
            # Process data
            results = {}
            
            # Generate ticks
            if self.config.enable_tick_aggregation:
                results['ticks'] = self.processor.aggregate_to_ticks(mbo_events)
            
            # Generate footprint
            if self.config.enable_footprint_generation:
                results['footprint'] = self.processor.generate_footprint(mbo_events)
            
            # Order book snapshot
            if self.config.enable_order_book_reconstruction:
                # Process all events to build order book
                for event in mbo_events:
                    self.processor._update_order_book(event)
                results['order_book'] = self.processor._get_order_book_snapshot()
            
            logger.info(f"Successfully processed {len(mbo_events)} MBO events")
            return results
            
        except Exception as e:
            logger.error(f"Error processing historical data: {e}")
            logger.error(traceback.format_exc())
            return {}
    
    def save_processed_data(self, data: Dict[str, pd.DataFrame], 
                          base_filename: str) -> Dict[str, str]:
        """Save processed data to files."""
        try:
            saved_files = {}
            
            for data_type, df in data.items():
                if isinstance(df, pd.DataFrame) and not df.empty:
                    filename = f"{base_filename}_{data_type}"
                    filepath = self.file_manager.save_mbo_data(df, filename)
                    saved_files[data_type] = filepath
            
            logger.info(f"Saved {len(saved_files)} processed data files")
            return saved_files
            
        except Exception as e:
            logger.error(f"Error saving processed data: {e}")
            logger.error(traceback.format_exc())
            return {}
    
    def get_streaming_status(self) -> Dict[str, Any]:
        """Get current streaming status."""
        try:
            return {
                'is_streaming': self.streamer.is_streaming,
                'current_file': self.streamer.get_current_file(),
                'queue_size': self.streamer.event_queue.qsize()
            }
        except Exception as e:
            logger.error(f"Error getting streaming status: {e}")
            return {
                'is_streaming': False,
                'current_file': None,
                'queue_size': 0
            }


# Convenience functions
def create_pipeline_from_config(app_config: AppConfig) -> DataPipeline:
    """Create a data pipeline from application config."""
    try:
        pipeline_config = DataPipelineConfig(
            databento_key=app_config.databento_key,
            dataset=app_config.databento_dataset,
            schema=app_config.databento_schema,
            data_dir=app_config.data_dir,
            archive_dir=f"{app_config.data_dir}/archive",
            live_stream_dir=app_config.live_stream_dir # Added missing attribute
        )
        
        return DataPipeline(pipeline_config)
        
    except Exception as e:
        logger.error(f"Error creating pipeline from config: {e}")
        logger.error(traceback.format_exc())
        raise


def process_databento_file(filepath: str, config: DataPipelineConfig) -> Dict[str, pd.DataFrame]:
    """Process a Databento DBN file and return processed data."""
    try:
        pipeline = DataPipeline(config)
        return pipeline.process_historical_data(filepath)
    except Exception as e:
        logger.error(f"Error processing Databento file: {e}")
        logger.error(traceback.format_exc())
        return {}
