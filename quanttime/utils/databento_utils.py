"""
Databento Utilities - Comprehensive data format handling

This module provides utilities for properly handling Databento data formats,
including price conversion, flag processing, timestamp handling, and schema validation.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# Databento Constants
UNDEF_PRICE = 9223372036854775807  # INT64_MAX
UNDEF_TIMESTAMP = 18446744073709551615  # UINT64_MAX


class DatabentoFlags:
    """Databento flag field constants and processing."""
    
    F_LAST = 1 << 7  # 128 - Last record in single event for instrument_id
    F_TOB = 1 << 6   # 64 - Top-of-book message, not individual order
    F_SNAPSHOT = 1 << 5  # 32 - Message sourced from replay/snapshot server
    F_MBP = 1 << 4   # 16 - Aggregated price level message, not individual order
    F_BAD_TS_RECV = 1 << 3  # 8 - ts_recv value inaccurate due to clock issues
    F_MAYBE_BAD_BOOK = 1 << 2  # 4 - Unrecoverable gap detected in channel
    F_PUBLISHER_SPECIFIC = 1 << 1  # 2 - Semantics depend on publisher_id
    RESERVED = 1 << 0  # 1 - Reserved for internal use
    
    @classmethod
    def process_flags(cls, flags: int) -> Dict[str, bool]:
        """Process Databento flags and return dictionary of flag states."""
        return {
            'is_last': bool(flags & cls.F_LAST),
            'is_tob': bool(flags & cls.F_TOB),
            'is_snapshot': bool(flags & cls.F_SNAPSHOT),
            'is_mbp': bool(flags & cls.F_MBP),
            'bad_ts_recv': bool(flags & cls.F_BAD_TS_RECV),
            'maybe_bad_book': bool(flags & cls.F_MAYBE_BAD_BOOK),
            'publisher_specific': bool(flags & cls.F_PUBLISHER_SPECIFIC),
            'reserved': bool(flags & cls.RESERVED)
        }
    
    @classmethod
    def get_flag_description(cls, flags: int) -> str:
        """Get human-readable description of flags."""
        flag_states = cls.process_flags(flags)
        descriptions = []
        
        if flag_states['is_last']:
            descriptions.append("Last record in event")
        if flag_states['is_tob']:
            descriptions.append("Top-of-book message")
        if flag_states['is_snapshot']:
            descriptions.append("Snapshot/replay data")
        if flag_states['is_mbp']:
            descriptions.append("Aggregated price level")
        if flag_states['bad_ts_recv']:
            descriptions.append("Bad receive timestamp")
        if flag_states['maybe_bad_book']:
            descriptions.append("Possible book gap")
        if flag_states['publisher_specific']:
            descriptions.append("Publisher-specific")
        
        return "; ".join(descriptions) if descriptions else "No special flags"


class DatabentoActions:
    """Databento action field constants and validation."""
    
    ADD = 'A'      # Insert new order into book
    MODIFY = 'M'   # Change order's price and/or size
    CANCEL = 'C'   # Fully or partially cancel order from book
    CLEAR = 'R'    # Remove all resting orders for instrument
    TRADE = 'T'    # Aggressing order traded (doesn't affect book)
    FILL = 'F'     # Resting order was filled (doesn't affect book)
    NONE = 'N'     # No action (may carry flags or other information)
    
    VALID_ACTIONS = {ADD, MODIFY, CANCEL, CLEAR, TRADE, FILL, NONE}
    
    @classmethod
    def is_valid_action(cls, action: str) -> bool:
        """Check if action is valid."""
        return action in cls.VALID_ACTIONS
    
    @classmethod
    def get_action_description(cls, action: str) -> str:
        """Get human-readable description of action."""
        descriptions = {
            cls.ADD: "Add order to book",
            cls.MODIFY: "Modify existing order",
            cls.CANCEL: "Cancel order from book",
            cls.CLEAR: "Clear all orders for instrument",
            cls.TRADE: "Trade executed (aggressor)",
            cls.FILL: "Order filled (resting)",
            cls.NONE: "No action (flags/info only)"
        }
        return descriptions.get(action, f"Unknown action: {action}")


class DatabentoSides:
    """Databento side field constants and validation."""
    
    BID = 'B'      # Buy side (bid)
    ASK = 'A'      # Ask side (sell)
    NONE = 'N'     # No side specified
    
    VALID_SIDES = {BID, ASK, NONE}
    
    @classmethod
    def is_valid_side(cls, side: str) -> bool:
        """Check if side is valid."""
        return side in cls.VALID_SIDES
    
    @classmethod
    def get_side_description(cls, side: str) -> str:
        """Get human-readable description of side."""
        descriptions = {
            cls.BID: "Buy/Bid",
            cls.ASK: "Ask/Sell",
            cls.NONE: "No side specified"
        }
        return descriptions.get(side, f"Unknown side: {side}")


def convert_databento_price(price_int: int) -> float:
    """
    Convert Databento fixed-precision price to decimal.
    
    Args:
        price_int: Price in Databento format (1e-9 precision)
        
    Returns:
        Price as float
    """
    if price_int == UNDEF_PRICE:
        return np.nan
    return price_int * 1e-9


def convert_to_databento_price(price_float: float) -> int:
    """
    Convert decimal price to Databento fixed-precision.
    
    Args:
        price_float: Price as float
        
    Returns:
        Price in Databento format (1e-9 precision)
    """
    if pd.isna(price_float):
        return UNDEF_PRICE
    return int(price_float * 1e9)


def convert_databento_timestamp(timestamp_ns: int) -> pd.Timestamp:
    """
    Convert Databento timestamp to pandas Timestamp.
    
    Args:
        timestamp_ns: Timestamp in nanoseconds since UNIX epoch
        
    Returns:
        pandas Timestamp
    """
    if timestamp_ns == UNDEF_TIMESTAMP:
        return pd.NaT
    return pd.to_datetime(timestamp_ns, unit='ns')


def convert_to_databento_timestamp(timestamp: Union[pd.Timestamp, str, int]) -> int:
    """
    Convert timestamp to Databento format.
    
    Args:
        timestamp: Timestamp in various formats
        
    Returns:
        Timestamp in nanoseconds since UNIX epoch
    """
    if pd.isna(timestamp):
        return UNDEF_TIMESTAMP
    
    if isinstance(timestamp, (int, np.integer)):
        return int(timestamp)
    
    if isinstance(timestamp, str):
        timestamp = pd.to_datetime(timestamp)
    
    if isinstance(timestamp, pd.Timestamp):
        return int(timestamp.timestamp() * 1e9)
    
    raise ValueError(f"Unsupported timestamp type: {type(timestamp)}")


def handle_databento_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Handle all Databento timestamp types and create datetime column.
    
    Args:
        df: DataFrame with Databento timestamp columns
        
    Returns:
        DataFrame with datetime column added
    """
    df = df.copy()
    
    # Databento timestamp columns in order of preference
    timestamp_columns = ['ts_event', 'ts_recv', 'ts_in_delta', 'ts_out']
    found_timestamp = None
    
    # Find the first available timestamp column
    for col in timestamp_columns:
        if col in df.columns:
            found_timestamp = col
            break
    
    if found_timestamp:
        if found_timestamp == 'ts_in_delta':
            # Calculate actual timestamp: ts_recv - ts_in_delta
            if 'ts_recv' in df.columns:
                df['datetime'] = pd.to_datetime(df['ts_recv'] - df['ts_in_delta'], unit='ns')
            else:
                logger.warning("ts_in_delta found but ts_recv missing")
                return df
        else:
            df['datetime'] = pd.to_datetime(df[found_timestamp], unit='ns')
        
        logger.info(f"Created datetime column from {found_timestamp}")
    else:
        logger.warning("No Databento timestamp columns found")
        return df
    
    return df


def sort_mbo_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sort MBO data by timestamp and sequence number.
    
    Args:
        df: MBO DataFrame
        
    Returns:
        Sorted DataFrame
    """
    if 'sequence' in df.columns and 'ts_event' in df.columns:
        return df.sort_values(['ts_event', 'sequence']).reset_index(drop=True)
    elif 'ts_event' in df.columns:
        return df.sort_values('ts_event').reset_index(drop=True)
    elif 'datetime' in df.columns:
        return df.sort_values('datetime').reset_index(drop=True)
    else:
        logger.warning("No timestamp columns found for sorting")
        return df


def detect_sequence_gaps(df: pd.DataFrame) -> List[Tuple[int, int]]:
    """
    Detect gaps in sequence numbers.
    
    Args:
        df: MBO DataFrame with sequence column
        
    Returns:
        List of (gap_start, gap_end) tuples
    """
    if 'sequence' not in df.columns:
        return []
    
    gaps = []
    sequences = df['sequence'].values
    
    for i in range(1, len(sequences)):
        if sequences[i] != sequences[i-1] + 1:
            gaps.append((sequences[i-1], sequences[i]))
    
    return gaps


def validate_mbo_schema(df: pd.DataFrame) -> bool:
    """
    Validate DataFrame against MBO schema.
    
    Args:
        df: DataFrame to validate
        
    Returns:
        True if valid, False otherwise
    """
    required_columns = [
        'ts_recv', 'ts_event', 'rtype', 'publisher_id', 'instrument_id',
        'action', 'side', 'price', 'size', 'channel_id', 'order_id',
        'flags', 'ts_in_delta', 'sequence'
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        logger.error(f"Missing required MBO columns: {missing_columns}")
        return False
    
    # Validate rtype (MBO = 160)
    if 'rtype' in df.columns and not df['rtype'].eq(160).all():
        logger.error("Invalid rtype values for MBO schema")
        return False
    
    # Validate actions
    if 'action' in df.columns:
        invalid_actions = df[~df['action'].isin(DatabentoActions.VALID_ACTIONS)]['action'].unique()
        if len(invalid_actions) > 0:
            logger.error(f"Invalid action values: {invalid_actions}")
            return False
    
    # Validate sides
    if 'side' in df.columns:
        invalid_sides = df[~df['side'].isin(DatabentoSides.VALID_SIDES)]['side'].unique()
        if len(invalid_sides) > 0:
            logger.error(f"Invalid side values: {invalid_sides}")
            return False
    
    logger.info("MBO schema validation passed")
    return True


@dataclass
class DatabentoMetadata:
    """Metadata for Databento data validation."""
    
    publisher_id: Optional[int] = None
    instrument_id: Optional[int] = None
    dataset: Optional[str] = None
    schema: Optional[str] = None
    symbols: List[str] = None
    start_ts: Optional[int] = None
    end_ts: Optional[int] = None
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = []


def validate_databento_data(df: pd.DataFrame, metadata: DatabentoMetadata) -> bool:
    """
    Validate that DataFrame contains expected Databento data.
    
    Args:
        df: DataFrame to validate
        metadata: Expected metadata
        
    Returns:
        True if valid, False otherwise
    """
    # Check required columns
    if 'publisher_id' not in df.columns:
        logger.error("Missing publisher_id column")
        return False
    
    if 'instrument_id' not in df.columns:
        logger.error("Missing instrument_id column")
        return False
    
    # Check for expected publisher_id
    if metadata.publisher_id and not df['publisher_id'].eq(metadata.publisher_id).all():
        unexpected_publishers = df[~df['publisher_id'].eq(metadata.publisher_id)]['publisher_id'].unique()
        logger.warning(f"Unexpected publisher_id values found: {unexpected_publishers}")
    
    # Check for expected instrument_id
    if metadata.instrument_id and not df['instrument_id'].eq(metadata.instrument_id).all():
        unexpected_instruments = df[~df['instrument_id'].eq(metadata.instrument_id)]['instrument_id'].unique()
        logger.warning(f"Unexpected instrument_id values found: {unexpected_instruments}")
    
    # Check timestamp range
    if metadata.start_ts and 'ts_event' in df.columns:
        if df['ts_event'].min() < metadata.start_ts:
            logger.warning("Data contains timestamps before expected start time")
    
    if metadata.end_ts and 'ts_event' in df.columns:
        if df['ts_event'].max() > metadata.end_ts:
            logger.warning("Data contains timestamps after expected end time")
    
    logger.info("Databento data validation passed")
    return True


def process_databento_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Process Databento flags and add flag columns to DataFrame.
    
    Args:
        df: DataFrame with flags column
        
    Returns:
        DataFrame with flag columns added
    """
    if 'flags' not in df.columns:
        logger.warning("No flags column found")
        return df
    
    df = df.copy()
    
    # Process flags for each row
    flag_data = []
    for flags in df['flags']:
        flag_data.append(DatabentoFlags.process_flags(flags))
    
    # Convert to DataFrame and join
    flag_df = pd.DataFrame(flag_data)
    flag_df.columns = [f'flag_{col}' for col in flag_df.columns]
    
    # Join with original DataFrame
    df = pd.concat([df, flag_df], axis=1)
    
    logger.info(f"Added {len(flag_df.columns)} flag columns")
    return df


def convert_prices_to_decimal(df: pd.DataFrame, price_columns: List[str] = None) -> pd.DataFrame:
    """
    Convert Databento fixed-precision prices to decimal format.
    
    Args:
        df: DataFrame with price columns
        price_columns: List of price columns to convert (default: ['price'])
        
    Returns:
        DataFrame with converted prices
    """
    if price_columns is None:
        price_columns = ['price']
    
    df = df.copy()
    
    for col in price_columns:
        if col in df.columns:
            df[f'{col}_decimal'] = df[col].apply(convert_databento_price)
            logger.info(f"Converted {col} to decimal format")
    
    return df


def get_databento_data_summary(df: pd.DataFrame) -> Dict[str, any]:
    """
    Get comprehensive summary of Databento data.
    
    Args:
        df: Databento DataFrame
        
    Returns:
        Dictionary with data summary
    """
    summary = {
        'total_records': len(df),
        'columns': list(df.columns),
        'schema': None,
        'publishers': [],
        'instruments': [],
        'actions': [],
        'sides': [],
        'timestamp_range': None,
        'price_range': None,
        'flag_summary': {},
        'sequence_gaps': []
    }
    
    # Schema detection
    if 'rtype' in df.columns:
        rtypes = df['rtype'].unique()
        summary['schema'] = f"rtype={rtypes[0]}" if len(rtypes) == 1 else f"mixed_rtypes={rtypes}"
    
    # Publisher and instrument info
    if 'publisher_id' in df.columns:
        summary['publishers'] = df['publisher_id'].unique().tolist()
    
    if 'instrument_id' in df.columns:
        summary['instruments'] = df['instrument_id'].unique().tolist()
    
    # Action and side distribution
    if 'action' in df.columns:
        summary['actions'] = df['action'].value_counts().to_dict()
    
    if 'side' in df.columns:
        summary['sides'] = df['side'].value_counts().to_dict()
    
    # Timestamp range
    timestamp_cols = ['ts_event', 'ts_recv', 'datetime']
    for col in timestamp_cols:
        if col in df.columns:
            summary['timestamp_range'] = {
                'start': df[col].min(),
                'end': df[col].max(),
                'column': col
            }
            break
    
    # Price range
    if 'price' in df.columns:
        summary['price_range'] = {
            'min': df['price'].min(),
            'max': df['price'].max(),
            'mean': df['price'].mean()
        }
    
    # Flag summary
    if 'flags' in df.columns:
        flag_counts = {}
        for flags in df['flags'].unique():
            flag_desc = DatabentoFlags.get_flag_description(flags)
            flag_counts[flags] = {
                'count': (df['flags'] == flags).sum(),
                'description': flag_desc
            }
        summary['flag_summary'] = flag_counts
    
    # Sequence gaps
    if 'sequence' in df.columns:
        summary['sequence_gaps'] = detect_sequence_gaps(df)
    
    return summary
