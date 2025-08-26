"""
Timeframe filtering utilities for market hours data processing.

This module provides functions to filter trading data to focus on high-volume
market hours (9:00 AM - 4:30 PM EST) and exclude low-volume overnight sessions.
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
from typing import Optional, Union, Dict, Any
import pytz
import logging

logger = logging.getLogger(__name__)


class TimeframeFilter:
    """Filter for market hours data processing."""
    
    def __init__(self, 
                 start_time: time = time(9, 0),  # 9:00 AM EST
                 end_time: time = time(16, 30),  # 4:30 PM EST
                 timezone: str = "US/Eastern"):
        """
        Initialize timeframe filter.
        
        Args:
            start_time: Start time for market hours (default: 9:00 AM EST)
            end_time: End time for market hours (default: 4:30 PM EST)
            timezone: Timezone for market hours (default: US/Eastern)
        """
        self.start_time = start_time
        self.end_time = end_time
        self.timezone = pytz.timezone(timezone)
        self.tag = f"market_hours_{start_time.hour:02d}{start_time.minute:02d}-{end_time.hour:02d}{end_time.minute:02d}_EST"
    
    def filter_dataframe(self, df: pd.DataFrame, timestamp_col: str = "ts") -> pd.DataFrame:
        """
        Filter dataframe to include only market hours data.
        
        Args:
            df: Input dataframe with timestamp column
            timestamp_col: Name of the timestamp column
            
        Returns:
            Filtered dataframe containing only market hours data
        """
        if df.empty:
            return df
        
        # Ensure timestamp column exists
        if timestamp_col not in df.columns:
            logger.warning(f"Timestamp column '{timestamp_col}' not found in dataframe")
            return df
        
        # Convert timestamp to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
            df = df.copy()
            df[timestamp_col] = pd.to_datetime(df[timestamp_col], unit='s')
        
        # Convert to EST timezone
        df_est = df.copy()
        df_est[timestamp_col] = df_est[timestamp_col].dt.tz_localize('UTC').dt.tz_convert(self.timezone)
        
        # Extract time component
        df_est['_time_only'] = df_est[timestamp_col].dt.time
        
        # Filter for market hours
        mask = (df_est['_time_only'] >= self.start_time) & (df_est['_time_only'] <= self.end_time)
        filtered_df = df[mask].copy()
        
        # Clean up temporary column
        filtered_df = filtered_df.drop(columns=['_time_only'], errors='ignore')
        
        logger.info(f"Filtered {len(df)} rows to {len(filtered_df)} market hours rows "
                   f"({len(filtered_df)/len(df)*100:.1f}% of original data)")
        
        return filtered_df
    
    def get_filter_stats(self, df: pd.DataFrame, timestamp_col: str = "ts") -> Dict[str, Any]:
        """
        Get statistics about the timeframe filtering.
        
        Args:
            df: Input dataframe with timestamp column
            timestamp_col: Name of the timestamp column
            
        Returns:
            Dictionary with filtering statistics
        """
        if df.empty:
            return {
                'total_rows': 0,
                'filtered_rows': 0,
                'filtered_percentage': 0.0,
                'start_time': self.start_time,
                'end_time': self.end_time,
                'timezone': self.timezone.zone
            }
        
        filtered_df = self.filter_dataframe(df, timestamp_col)
        
        return {
            'total_rows': len(df),
            'filtered_rows': len(filtered_df),
            'filtered_percentage': len(filtered_df) / len(df) * 100 if len(df) > 0 else 0.0,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'timezone': self.timezone.zone,
            'filter_tag': self.tag
        }


def create_market_hours_filter() -> TimeframeFilter:
    """
    Create a default market hours filter (9:00 AM - 4:30 PM EST).
    
    Returns:
        TimeframeFilter configured for market hours
    """
    return TimeframeFilter(
        start_time=time(9, 0),   # 9:00 AM EST
        end_time=time(16, 30),   # 4:30 PM EST
        timezone="US/Eastern"
    )


def create_24h_filter() -> TimeframeFilter:
    """
    Create a 24-hour filter (no time restrictions).
    
    Returns:
        TimeframeFilter configured for 24-hour trading
    """
    return TimeframeFilter(
        start_time=time(0, 0),   # 12:00 AM
        end_time=time(23, 59),   # 11:59 PM
        timezone="US/Eastern"
    )


def filter_mbo_data_by_timeframe(df: pd.DataFrame, 
                                timeframe_filter: Optional[TimeframeFilter] = None,
                                timestamp_col: str = "ts") -> pd.DataFrame:
    """
    Filter MBO data by timeframe.
    
    Args:
        df: MBO dataframe
        timeframe_filter: TimeframeFilter instance (default: market hours)
        timestamp_col: Name of the timestamp column
        
    Returns:
        Filtered MBO dataframe
    """
    if timeframe_filter is None:
        timeframe_filter = create_market_hours_filter()
    
    return timeframe_filter.filter_dataframe(df, timestamp_col)


def get_timeframe_options() -> Dict[str, TimeframeFilter]:
    """
    Get available timeframe filter options.
    
    Returns:
        Dictionary mapping option names to TimeframeFilter instances
    """
    return {
        "Market Hours (9:00 AM - 4:30 PM EST)": create_market_hours_filter(),
        "24 Hour Trading": create_24h_filter(),
        "Extended Hours (8:00 AM - 5:00 PM EST)": TimeframeFilter(
            start_time=time(8, 0),
            end_time=time(17, 0),
            timezone="US/Eastern"
        ),
        "Core Hours (9:30 AM - 4:00 PM EST)": TimeframeFilter(
            start_time=time(9, 30),
            end_time=time(16, 0),
            timezone="US/Eastern"
        )
    }
