"""
Test Data Generator for Pipeline Testing

This module provides functions to generate synthetic test data for validating
the training and backtesting pipelines when real data is not available.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def generate_test_mbo_data(num_events: int = 1000, 
                          start_time: Optional[datetime] = None,
                          symbol: str = "ES.FUT") -> pd.DataFrame:
    """
    Generate synthetic MBO (Market By Order) test data.
    
    Args:
        num_events: Number of MBO events to generate
        start_time: Start time for the data (default: current time)
        symbol: Trading symbol
        
    Returns:
        DataFrame with synthetic MBO data
    """
    if start_time is None:
        start_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    
    # Generate timestamps
    timestamps = []
    current_time = start_time
    for i in range(num_events):
        timestamps.append(current_time)
        # Add random time increment (0.1 to 1 second)
        current_time += timedelta(seconds=np.random.uniform(0.1, 1.0))
    
    # Generate price data (random walk around 5000)
    base_price = 5000.0
    prices = []
    current_price = base_price
    
    for i in range(num_events):
        # Random price movement
        price_change = np.random.normal(0, 0.5)  # Small random changes
        current_price += price_change
        prices.append(current_price)
    
    # Generate MBO events
    events = []
    for i in range(num_events):
        # Random event type
        event_type = np.random.choice(['A', 'C', 'F', 'M', 'R', 'T'], p=[0.3, 0.1, 0.2, 0.1, 0.1, 0.2])
        
        # Generate event data based on type
        if event_type == 'A':  # Add
            side = np.random.choice(['B', 'A'])  # Use uppercase B/A for consistency (B=buy, A=ask)
            size = np.random.randint(1, 100)
            price = prices[i] + np.random.normal(0, 1.0)
            events.append({
                'ts_event': timestamps[i].timestamp() * 1e9,  # Nanoseconds
                'action': 'A',  # Databento Add action
                'side': side,
                'price': price,
                'size': size,
                'order_id': f"order_{i}",
                'symbol': symbol
            })
        elif event_type == 'C':  # Cancel
            events.append({
                'ts_event': timestamps[i].timestamp() * 1e9,
                'action': 'C',  # Databento Cancel action
                'side': np.random.choice(['B', 'A']),  # Add side for consistency
                'price': prices[i] + np.random.normal(0, 1.0),  # Add price for consistency
                'size': np.random.randint(1, 50),  # Add size for consistency
                'order_id': f"order_{np.random.randint(0, max(1, i))}",
                'symbol': symbol
            })
        elif event_type == 'F':  # Fill
            side = np.random.choice(['B', 'A'])  # Use uppercase B/A for consistency (B=buy, A=ask)
            size = np.random.randint(1, 50)
            price = prices[i] + np.random.normal(0, 0.5)
            events.append({
                'ts_event': timestamps[i].timestamp() * 1e9,
                'action': 'F',  # Databento Fill action
                'side': side,
                'price': price,
                'size': size,
                'order_id': f"order_{np.random.randint(0, max(1, i))}",
                'symbol': symbol
            })
        elif event_type == 'M':  # Modify
            events.append({
                'ts_event': timestamps[i].timestamp() * 1e9,
                'action': 'M',  # Databento Modify action
                'side': np.random.choice(['B', 'A']),  # Add side for consistency
                'price': prices[i] + np.random.normal(0, 1.0),  # Add price for consistency
                'size': np.random.randint(1, 100),  # Add size for consistency
                'order_id': f"order_{np.random.randint(0, max(1, i))}",
                'new_price': prices[i] + np.random.normal(0, 1.0),
                'new_size': np.random.randint(1, 100),
                'symbol': symbol
            })
        elif event_type == 'R':  # Replace
            events.append({
                'ts_event': timestamps[i].timestamp() * 1e9,
                'action': 'R',  # Databento Clear action
                'side': np.random.choice(['B', 'A']),  # Add side for consistency
                'price': prices[i] + np.random.normal(0, 1.0),  # Add price for consistency
                'size': np.random.randint(1, 100),  # Add size for consistency
                'order_id': f"order_{np.random.randint(0, max(1, i))}",
                'new_order_id': f"order_{i}",
                'new_price': prices[i] + np.random.normal(0, 1.0),
                'new_size': np.random.randint(1, 100),
                'symbol': symbol
            })
        elif event_type == 'T':  # Trade
            side = np.random.choice(['B', 'A'])  # Use uppercase B/A for consistency (B=buy, A=ask)
            size = np.random.randint(1, 100)
            price = prices[i] + np.random.normal(0, 0.5)
            events.append({
                'ts_event': timestamps[i].timestamp() * 1e9,
                'action': 'T',  # Databento Trade action
                'side': side,
                'price': price,
                'size': size,
                'symbol': symbol
            })
    
    # Create DataFrame
    df = pd.DataFrame(events)
    
    # Add missing required Databento MBO columns for full schema compatibility
    df['ts_recv'] = df['ts_event'] + np.random.randint(1000, 10000, len(df))  # Receive timestamp
    df['rtype'] = 160  # MBO record type
    df['publisher_id'] = 1  # Default publisher
    df['instrument_id'] = 1  # Default instrument
    df['channel_id'] = 1  # Default channel
    df['flags'] = 0  # Default flags
    df['ts_in_delta'] = np.random.randint(0, 1000, len(df))  # In delta timestamp
    df['sequence'] = range(len(df))  # Sequential order
    
    # Add timestamp column for compatibility
    df['ts'] = df['ts_event'] / 1e9  # Convert to seconds
    
    logger.info(f"Generated {len(df)} synthetic MBO events with full schema")
    return df


def generate_test_candles_data(num_candles: int = 100,
                              start_time: Optional[datetime] = None,
                              symbol: str = "ES.FUT") -> pd.DataFrame:
    """
    Generate synthetic OHLCV candle data for testing.
    
    Args:
        num_candles: Number of candles to generate
        start_time: Start time for the data (default: current time)
        symbol: Trading symbol
        
    Returns:
        DataFrame with synthetic OHLCV data
    """
    if start_time is None:
        start_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    
    # Generate timestamps (1-minute candles)
    timestamps = []
    current_time = start_time
    for i in range(num_candles):
        timestamps.append(current_time)
        current_time += timedelta(minutes=1)
    
    # Generate OHLCV data (random walk)
    base_price = 5000.0
    current_price = base_price
    
    data = []
    for i in range(num_candles):
        # Generate OHLC from current price
        price_change = np.random.normal(0, 2.0)  # Larger changes for OHLC
        current_price += price_change
        
        # Create OHLC from current price
        high = current_price + abs(np.random.normal(0, 1.0))
        low = current_price - abs(np.random.normal(0, 1.0))
        open_price = current_price + np.random.normal(0, 0.5)
        close_price = current_price + np.random.normal(0, 0.5)
        
        # Ensure OHLC relationships
        high = max(high, open_price, close_price)
        low = min(low, open_price, close_price)
        
        # Generate volume
        volume = np.random.randint(100, 1000)
        
        data.append({
            'timestamp': timestamps[i],
            'ts': timestamps[i].timestamp(),
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price,
            'volume': volume,
            'symbol': symbol
        })
    
    df = pd.DataFrame(data)
    logger.info(f"Generated {len(df)} synthetic OHLCV candles")
    return df


def generate_test_tick_data(num_ticks: int = 1000,
                           start_time: Optional[datetime] = None,
                           symbol: str = "ES.FUT") -> pd.DataFrame:
    """
    Generate synthetic tick data for testing.
    
    Args:
        num_ticks: Number of ticks to generate
        start_time: Start time for the data (default: current time)
        symbol: Trading symbol
        
    Returns:
        DataFrame with synthetic tick data
    """
    if start_time is None:
        start_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    
    # Generate timestamps
    timestamps = []
    current_time = start_time
    for i in range(num_ticks):
        timestamps.append(current_time)
        current_time += timedelta(seconds=np.random.uniform(0.1, 2.0))
    
    # Generate price data (random walk)
    base_price = 5000.0
    current_price = base_price
    
    data = []
    for i in range(num_ticks):
        # Random price movement
        price_change = np.random.normal(0, 0.25)
        current_price += price_change
        
        # Generate side and size
        side = np.random.choice(['buy', 'sell'])
        size = np.random.randint(1, 100)
        
        data.append({
            'ts': timestamps[i].timestamp(),
            'price': current_price,
            'side': side,
            'size': size,
            'symbol': symbol
        })
    
    df = pd.DataFrame(data)
    logger.info(f"Generated {len(df)} synthetic tick events")
    return df


def get_test_data_for_pipeline(data_type: str = "mbo", 
                              size: str = "small") -> pd.DataFrame:
    """
    Get test data for pipeline testing.
    
    Args:
        data_type: Type of data ('mbo', 'candles', 'ticks')
        size: Size of dataset ('small', 'medium', 'large')
        
    Returns:
        DataFrame with test data
    """
    size_map = {
        'small': {'mbo': 500, 'candles': 50, 'ticks': 500},
        'medium': {'mbo': 2000, 'candles': 200, 'ticks': 2000},
        'large': {'mbo': 5000, 'candles': 500, 'ticks': 5000}
    }
    
    num_items = size_map[size][data_type]
    
    if data_type == 'mbo':
        return generate_test_mbo_data(num_items)
    elif data_type == 'candles':
        return generate_test_candles_data(num_items)
    elif data_type == 'ticks':
        return generate_test_tick_data(num_items)
    else:
        raise ValueError(f"Unknown data type: {data_type}")


def validate_test_data(df: pd.DataFrame, data_type: str) -> Dict[str, Any]:
    """
    Validate test data for pipeline testing.
    
    Args:
        df: DataFrame to validate
        data_type: Type of data ('mbo', 'candles', 'ticks')
        
    Returns:
        Dictionary with validation results
    """
    results = {
        'valid': True,
        'rows': len(df),
        'columns': list(df.columns),
        'missing_values': df.isnull().sum().to_dict(),
        'data_types': df.dtypes.to_dict(),
        'time_range': None,
        'errors': []
    }
    
    try:
        # Check for required columns
        required_columns = {
            'mbo': ['ts_event', 'action', 'symbol'],
            'candles': ['timestamp', 'open', 'high', 'low', 'close', 'volume'],
            'ticks': ['ts', 'price', 'side', 'size']
        }
        
        if data_type in required_columns:
            missing_cols = set(required_columns[data_type]) - set(df.columns)
            if missing_cols:
                results['errors'].append(f"Missing required columns: {missing_cols}")
                results['valid'] = False
        
        # Check for timestamp column
        if 'ts' in df.columns:
            results['time_range'] = {
                'start': datetime.fromtimestamp(df['ts'].min()),
                'end': datetime.fromtimestamp(df['ts'].max())
            }
        elif 'timestamp' in df.columns:
            results['time_range'] = {
                'start': df['timestamp'].min(),
                'end': df['timestamp'].max()
            }
        
        # Check for missing values
        if df.isnull().any().any():
            results['errors'].append("Data contains missing values")
            results['valid'] = False
        
        # Check data types
        if data_type == 'ticks' and 'price' in df.columns:
            if not pd.api.types.is_numeric_dtype(df['price']):
                results['errors'].append("Price column is not numeric")
                results['valid'] = False
        
    except Exception as e:
        results['errors'].append(f"Validation error: {str(e)}")
        results['valid'] = False
    
    return results
