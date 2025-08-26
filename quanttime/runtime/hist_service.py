"""
Historical data service for Databento MBO data.

REFERENCE SOURCES:
- databento-python-main/examples/historical_timeseries_from_file.py: File loading patterns
- databento-python-main/examples/historical_timeseries_to_df.py: DataFrame conversion and processing
- databento-python-main/databento/__init__.py: Schema definitions and data types
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging
from pathlib import Path

from ..utils.config import AppConfig
from ..adapter.databento_loader import get_databento_loader, OfficialDatabentoLoader

logger = logging.getLogger(__name__)


def load_databento_mbo_data(data_dir: str, start_date: str, end_date: str, symbol: str = "ES.FUT") -> pd.DataFrame:
    """
    Load Databento MBO data for a date range using official Databento library.
    
    Reference: databento-python-main/examples/historical_timeseries_from_file.py - File loading patterns
    """
    try:
        loader = get_databento_loader(data_dir=data_dir)
        
        # Load data for each date in range
        all_data = []
        available_dates = loader.get_available_dates()
        
        for date in available_dates:
            if start_date <= date <= end_date:
                try:
                    # Reference: databento-python-main/examples/historical_timeseries_to_df.py - DataFrame loading
                    df = loader.load_date_as_dataframe(date)
                    if df is not None and not df.empty:
                        all_data.append(df)
                        logger.info(f"Loaded {len(df)} events for {date}")
                except Exception as e:
                    logger.warning(f"Failed to load data for {date}: {e}")
        
        if not all_data:
            return pd.DataFrame()
        
        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)
        
        logger.info(f"Total MBO events loaded: {len(combined_df)}")
        return combined_df
        
    except Exception as e:
        logger.error(f"Failed to load Databento MBO data: {e}")
        return pd.DataFrame()


def process_mbo_to_ticks(mbo_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert MBO data to tick data format using official Databento format.
    
    Reference: databento-python-main/databento/__init__.py - Action enum and execution filtering
    """
    if mbo_df.empty or 'action' not in mbo_df.columns:
        return pd.DataFrame()
    
    try:
        # Filter for execution events only (F = fill/execution)
        # Reference: databento-python-main/databento/__init__.py - Action enum usage
        executions = mbo_df[mbo_df['action'] == 'F'].copy()
        
        if executions.empty:
            logger.warning("No execution events found in MBO data")
            return pd.DataFrame()
        
        # Convert to tick format
        # Reference: databento-python-main/examples/historical_timeseries_to_df.py - Data transformation patterns
        ticks = []
        for _, row in executions.iterrows():
            tick = {
                'ts': row.get('ts_event', row.get('datetime')), # Use 'datetime' if 'ts_event' not present
                'price': row['price'],
                'size': row['size'],
                'side': row.get('side', 'buy') # Default to 'buy' if 'side' not present
            }
            ticks.append(tick)
        
        ticks_df = pd.DataFrame(ticks)
        
        # Sort by timestamp
        if 'ts' in ticks_df.columns:
            ticks_df = ticks_df.sort_values('ts').reset_index(drop=True)
        
        logger.info(f"Generated {len(ticks_df)} ticks from MBO data")
        return ticks_df
        
    except Exception as e:
        logger.error(f"Failed to process MBO to ticks: {e}")
        return pd.DataFrame()


def load_ticks_from_file(filepath: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> Optional[pd.DataFrame]:
    """
    Load tick data from a file with optional time filtering.
    
    Args:
        filepath: Path to the tick data file
        start_time: Optional start time filter
        end_time: Optional end time filter
        
    Returns:
        DataFrame with tick data or None if loading fails
    """
    try:
        if not os.path.exists(filepath):
            logger.error(f"Tick file not found: {filepath}")
            return None
        
        # Load tick data
        df = pd.read_parquet(filepath)
        
        if df.empty:
            logger.warning(f"Empty tick file: {filepath}")
            return None
        
        # Convert timestamp column if needed
        if 'ts' in df.columns:
            if df['ts'].dtype == 'int64':
                # Convert nanoseconds to datetime
                df['datetime'] = pd.to_datetime(df['ts'], unit='ns')
            else:
                df['datetime'] = pd.to_datetime(df['ts'])
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
        else:
            logger.error("No timestamp column found in tick data")
            return None
        
        # Apply time filters
        if start_time:
            cutoff = pd.Timestamp(start_time)
            df = df[df['datetime'] >= cutoff]
        
        if end_time:
            cutoff = pd.Timestamp(end_time)
            df = df[df['datetime'] <= cutoff]
        
        return df
        
    except Exception as e:
        logger.error(f"Failed to load ticks from file: {e}")
        return None


def get_available_databento_dates() -> List[str]:
    """Get list of available dates in the Databento dataset."""
    try:
        loader = get_databento_loader(data_dir="data/es_futures/mbo")
        return loader.get_available_dates()
    except Exception as e:
        logger.error(f"Failed to get available dates: {e}")
        return []


def get_databento_symbols() -> Dict[str, int]:
    """Get available symbols and their IDs from Databento."""
    try:
        loader = get_databento_loader(data_dir="data/es_futures")
        # Get available dates and extract symbols from them
        available_dates = loader.get_available_dates()
        symbols = {}
        
        # Extract unique symbols from available dates
        for date in available_dates:
            # Assuming date format contains symbol info, extract it
            if "ES" in date or "es" in date:
                symbols["ES.FUT"] = 1  # Default mapping
            elif "NQ" in date or "nq" in date:
                symbols["NQ.FUT"] = 2
            elif "YM" in date or "ym" in date:
                symbols["YM.FUT"] = 3
        
        # If no symbols found, provide default
        if not symbols:
            symbols = {"ES.FUT": 1}
            
        return symbols
    except Exception as e:
        logger.error(f"Failed to get symbols: {e}")
        return {"ES.FUT": 1}  # Default fallback


def load_mbo_data_for_analysis(cfg: AppConfig, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Load MBO data for advanced analysis (order book reconstruction, footprints, etc.)."""
    try:
        logger.info(f"Loading MBO data for analysis: {symbol} {start_date} to {end_date}")
        
        mbo_df = load_databento_mbo_data(
            data_dir="data/es_futures/mbo",
            start_date=start_date,
            end_date=end_date,
            symbol=symbol
        )
        
        if mbo_df.empty:
            logger.warning(f"No MBO data found for analysis")
            return None
        
        # Add datetime column for easier processing
        mbo_df['datetime'] = pd.to_datetime(mbo_df['ts_event'], unit='ns')
        
        return mbo_df
        
    except Exception as e:
        logger.error(f"Failed to load MBO data for analysis: {e}")
        return None


def generate_orderbook_snapshot(mbo_df: pd.DataFrame, target_time: Optional[datetime] = None) -> Dict:
    """Generate order book snapshot from MBO data at a specific time."""
    try:
        loader = OfficialDatabentoLoader()
        
        if target_time is None:
            target_time = mbo_df['datetime'].max()
        
        # Convert to nanosecond timestamp
        target_ts = int(target_time.timestamp() * 1e9)
        
        return loader.reconstruct_orderbook(mbo_df, target_ts)
        
    except Exception as e:
        logger.error(f"Failed to generate order book snapshot: {e}")
        return {'bids': [], 'asks': [], 'timestamp': 0}


def generate_footprint_data(mbo_df: pd.DataFrame) -> pd.DataFrame:
    """Generate footprint data from MBO data."""
    try:
        loader = OfficialDatabentoLoader()
        return loader.generate_footprint(mbo_df)
    except Exception as e:
        logger.error(f"Failed to generate footprint data: {e}")
        return pd.DataFrame()


def get_mbo_statistics(mbo_df: pd.DataFrame) -> Dict:
    """Get statistics about MBO data."""
    if mbo_df.empty:
        return {}
    
    stats = {
        'total_events': len(mbo_df),
        'date_range': {
            'start': mbo_df['datetime'].min().isoformat(),
            'end': mbo_df['datetime'].max().isoformat()
        },
        'actions': mbo_df['action'].value_counts().to_dict(),
        'sides': mbo_df['side'].value_counts().to_dict(),
        'price_range': {
            'min': float(mbo_df['price'].min()),
            'max': float(mbo_df['price'].max())
        },
        'size_stats': {
            'mean': float(mbo_df['size'].mean()),
            'std': float(mbo_df['size'].std()),
            'min': int(mbo_df['size'].min()),
            'max': int(mbo_df['size'].max())
        }
    }
    
    return stats


# New functions using official Databento client
def get_historical_data_official(symbols: str, start: str, end: str, 
                               schema: str = "mbo", api_key: str = None) -> Optional[pd.DataFrame]:
    """Get historical data using official Databento client."""
    try:
        client = OfficialDatabentoLoader(api_key=api_key)
        return client.get_historical_data(symbols, start, end, schema)
    except Exception as e:
        logger.error(f"Failed to get historical data with official client: {e}")
        return None


def validate_mbo_data_quality(mbo_df: pd.DataFrame) -> Dict[str, Any]:
    """Validate MBO data quality using official validator."""
    return OfficialDatabentoLoader.validate_mbo_data(mbo_df)


def resolve_symbols_official(symbols: List[str], api_key: str = None) -> Dict[str, int]:
    """Resolve symbols using official Databento symbology service."""
    try:
        client = OfficialDatabentoLoader(api_key=api_key)
        return client.resolve_symbols(symbols)
    except Exception as e:
        logger.error(f"Failed to resolve symbols with official client: {e}")
        return {}


def get_available_symbols_official(api_key: str = None) -> List[str]:
    """Get available symbols using official Databento client."""
    try:
        client = OfficialDatabentoLoader(api_key=api_key)
        return client.get_available_symbols()
    except Exception as e:
        logger.error(f"Failed to get available symbols with official client: {e}")
        return []


def get_dataset_info_official(api_key: str = None) -> Dict[str, Any]:
    """Get dataset information using official Databento client."""
    try:
        client = OfficialDatabentoLoader(api_key=api_key)
        return client.get_dataset_info()
    except Exception as e:
        logger.error(f"Failed to get dataset info with official client: {e}")
        return {}


