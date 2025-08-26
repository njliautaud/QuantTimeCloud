"""
Matplotlib Charting Component for QuantTime ML Trading Suite.

This module provides matplotlib-based charts that display under the TradingView chart,
using official Databento data format.

REFERENCE SOURCES:
- databento-python-main/examples/historical_timeseries_to_df.py: DataFrame structure and data format
- databento-python-main/examples/historical_timeseries_from_file.py: Data loading patterns
- databento-python-main/databento/__init__.py: Schema definitions and data types
- databento-python-main/databento/common/dbnstore.py: DBNStore data structure and properties
"""

import logging
from typing import Optional, Dict, Any
import streamlit as st

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.axes import Axes

logger = logging.getLogger(__name__)


def create_candlestick_chart(df: pd.DataFrame, figsize: tuple = (12, 6)) -> Figure:
    """
    Create a candlestick chart from Databento MBO data.
    
    Args:
        df: DataFrame with Databento MBO data
        figsize: Figure size (width, height)
        
    Returns:
        matplotlib Figure object
        
    Reference: databento-python-main/examples/historical_timeseries_to_df.py - DataFrame structure
    """
    if df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
        ax.set_title('Candlestick Chart (No Data)')
        return fig
    
    # Convert MBO data to OHLCV candles
    # Reference: databento-python-main/examples/historical_timeseries_to_df.py - Data processing patterns
    candles_df = convert_mbo_to_ohlcv(df)
    
    if candles_df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'No execution data for candles', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
        ax.set_title('Candlestick Chart (No Executions)')
        return fig
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot candlesticks
    for i, (timestamp, row) in enumerate(candles_df.iterrows()):
        # Determine candle color
        if row['close'] >= row['open']:
            color = 'green'
            alpha = 0.8
        else:
            color = 'red'
            alpha = 0.8
        
        # Plot candle body
        ax.bar(timestamp, row['close'] - row['open'], 
               bottom=min(row['open'], row['close']),
               width=pd.Timedelta(minutes=0.8), color=color, alpha=alpha)
        
        # Plot wicks
        ax.plot([timestamp, timestamp], [row['low'], row['high']], 
                color='black', linewidth=1)
    
    # Formatting
    ax.set_title('ES Futures - 1-Minute Candlesticks (Matplotlib)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Price ($)', fontsize=12)
    ax.grid(True, alpha=0.3)
    
    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # Add price range info
    price_range = f"Range: ${candles_df['low'].min():.2f} - ${candles_df['high'].max():.2f}"
    ax.text(0.02, 0.98, price_range, transform=ax.transAxes, 
            verticalalignment='top', fontsize=10, 
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    return fig


def create_volume_chart(df: pd.DataFrame, figsize: tuple = (12, 4)) -> Figure:
    """
    Create a volume chart from Databento MBO data.
    
    Args:
        df: DataFrame with Databento MBO data
        figsize: Figure size (width, height)
        
    Returns:
        matplotlib Figure object
        
    Reference: databento-python-main/examples/historical_timeseries_to_df.py - Volume data handling
    """
    if df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
        ax.set_title('Volume Chart (No Data)')
        return fig
    
    # Convert MBO data to OHLCV candles for volume
    # Reference: databento-python-main/examples/historical_timeseries_to_df.py - Data aggregation patterns
    candles_df = convert_mbo_to_ohlcv(df)
    
    if candles_df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'No execution data for volume', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
        ax.set_title('Volume Chart (No Executions)')
        return fig
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot volume bars
    colors = ['green' if close >= open else 'red' 
              for close, open in zip(candles_df['close'], candles_df['open'])]
    
    ax.bar(candles_df.index, candles_df['volume'], color=colors, alpha=0.7)
    
    # Formatting
    ax.set_title('Volume Profile (Matplotlib)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Volume', fontsize=12)
    ax.grid(True, alpha=0.3)
    
    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # Add total volume info
    total_volume = candles_df['volume'].sum()
    ax.text(0.02, 0.98, f"Total Volume: {total_volume:,}", transform=ax.transAxes, 
            verticalalignment='top', fontsize=10, 
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
    
    plt.tight_layout()
    return fig


def create_tick_chart(df: pd.DataFrame, figsize: tuple = (12, 6)) -> Figure:
    """
    Create a tick-by-tick price chart from Databento MBO data.
    
    Args:
        df: DataFrame with Databento MBO data
        figsize: Figure size (width, height)
        
    Returns:
        matplotlib Figure object
        
    Reference: databento-python-main/examples/historical_timeseries_to_df.py - Tick data processing
    """
    if df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
        ax.set_title('Tick Chart (No Data)')
        return fig
    
    # Filter for execution events only
    # Reference: databento-python-main/databento/__init__.py - Action enum and execution filtering
    executions = df[df['action'] == 'F'].copy()
    
    if executions.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'No execution events found', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
        ax.set_title('Tick Chart (No Executions)')
        return fig
    
    # Convert timestamps
    # Reference: databento-python-main/examples/historical_timeseries_to_df.py - Timestamp handling
    if 'ts_event' in executions.columns:
        executions['datetime'] = pd.to_datetime(executions['ts_event'], unit='ns')
    elif 'datetime' not in executions.columns:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'No timestamp column found', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
        ax.set_title('Tick Chart (No Timestamps)')
        return fig
    
    # Sort by time
    executions = executions.sort_values('datetime')
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot tick prices
    ax.plot(executions['datetime'], executions['price'], 
            linewidth=1, alpha=0.8, color='blue')
    
    # Add scatter points for each tick
    ax.scatter(executions['datetime'], executions['price'], 
              s=20, alpha=0.6, color='blue')
    
    # Formatting
    ax.set_title('ES Futures - Tick-by-Tick Prices (Matplotlib)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Price ($)', fontsize=12)
    ax.grid(True, alpha=0.3)
    
    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # Add tick count info
    tick_count = len(executions)
    ax.text(0.02, 0.98, f"Total Ticks: {tick_count:,}", transform=ax.transAxes, 
            verticalalignment='top', fontsize=10, 
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
    
    plt.tight_layout()
    return fig


def convert_mbo_to_ohlcv(df: pd.DataFrame, interval: str = '1min') -> pd.DataFrame:
    """
    Convert MBO data to OHLCV candles using official Databento format.
    
    Args:
        df: DataFrame with Databento MBO data
        interval: Candle interval ('1min', '5min', etc.)
        
    Returns:
        DataFrame with OHLCV candles
        
    Reference: databento-python-main/examples/historical_timeseries_to_df.py - Data transformation patterns
    """
    if df.empty:
        return pd.DataFrame()
    
    # Filter for execution events only
    # Reference: databento-python-main/databento/__init__.py - Action enum for execution filtering
    executions = df[df['action'] == 'F'].copy()
    
    if executions.empty:
        logger.warning("No execution events found in MBO data")
        return pd.DataFrame()
    
    # Convert timestamps
    # Reference: databento-python-main/examples/historical_timeseries_to_df.py - Timestamp conversion
    if 'ts_event' in executions.columns:
        executions['datetime'] = pd.to_datetime(executions['ts_event'], unit='ns')
    elif 'datetime' not in executions.columns:
        logger.warning("No timestamp column found")
        return pd.DataFrame()
    
    # Sort by time
    executions = executions.sort_values('datetime')
    
    # Resample to create OHLCV candles
    # Reference: databento-python-main/examples/historical_timeseries_to_df.py - Data aggregation
    if interval == '1min':
        resampled = executions.set_index('datetime').resample('1T').agg({
            'price': ['first', 'max', 'min', 'last'],
            'size': 'sum'
        })
    elif interval == '5min':
        resampled = executions.set_index('datetime').resample('5T').agg({
            'price': ['first', 'max', 'min', 'last'],
            'size': 'sum'
        })
    else:
        # Default to 1 minute
        resampled = executions.set_index('datetime').resample('1T').agg({
            'price': ['first', 'max', 'min', 'last'],
            'size': 'sum'
        })
    
    # Flatten column names
    resampled.columns = ['open', 'high', 'low', 'close', 'volume']
    
    # Remove empty periods
    resampled = resampled.dropna()
    
    return resampled


def display_matplotlib_charts(df: pd.DataFrame, chart_type: str = "candlestick"):
    """
    Display matplotlib charts in Streamlit.
    
    Args:
        df: DataFrame with Databento MBO data
        chart_type: Type of chart to display
        
    Reference: databento-python-main/examples/historical_timeseries_to_df.py - Data display patterns
    """
    try:
        if chart_type == "candlestick":
            fig = create_candlestick_chart(df)
            st.pyplot(fig)
            plt.close(fig)
            
        elif chart_type == "volume":
            fig = create_volume_chart(df)
            st.pyplot(fig)
            plt.close(fig)
            
        elif chart_type == "tick":
            fig = create_tick_chart(df)
            st.pyplot(fig)
            plt.close(fig)
            
        elif chart_type == "comprehensive":
            # Display multiple charts
            col1, col2 = st.columns(2)
            
            with col1:
                fig1 = create_candlestick_chart(df, figsize=(8, 4))
                st.pyplot(fig1)
                plt.close(fig1)
            
            with col2:
                fig2 = create_volume_chart(df, figsize=(8, 4))
                st.pyplot(fig2)
                plt.close(fig2)
            
            # Full-width tick chart below
            fig3 = create_tick_chart(df, figsize=(12, 4))
            st.pyplot(fig3)
            plt.close(fig3)
            
        else:
            st.error(f"Unknown chart type: {chart_type}")
            
    except Exception as e:
        logger.error(f"Error creating matplotlib chart: {e}")
        st.error(f"Error creating chart: {e}")


def display_data_summary(df: pd.DataFrame):
    """
    Display data summary statistics.
    
    Args:
        df: DataFrame with Databento MBO data
        
    Reference: databento-python-main/examples/historical_timeseries_to_df.py - Data analysis patterns
    """
    if df.empty:
        st.warning("No data available for summary")
        return
    
    st.subheader("📊 Data Summary (Matplotlib)")
    
    # Basic statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Records", f"{len(df):,}")
    
    with col2:
        if 'action' in df.columns:
            # Reference: databento-python-main/databento/__init__.py - Action enum usage
            executions = len(df[df['action'] == 'F'])
            st.metric("Executions", f"{executions:,}")
    
    with col3:
        if 'price' in df.columns:
            price_range = f"${df['price'].min():.2f} - ${df['price'].max():.2f}"
            st.metric("Price Range", price_range)
    
    with col4:
        if 'size' in df.columns:
            total_volume = df['size'].sum()
            st.metric("Total Volume", f"{total_volume:,}")
    
    # Action breakdown
    if 'action' in df.columns:
        st.subheader("📈 Action Breakdown")
        action_counts = df['action'].value_counts()
        
        fig, ax = plt.subplots(figsize=(8, 4))
        bars = ax.bar(action_counts.index, action_counts.values, 
                     color=['red', 'blue', 'green', 'orange'][:len(action_counts)])
        
        # Add value labels on bars
        for bar, value in zip(bars, action_counts.values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01*max(action_counts.values),
                   f'{value:,}', ha='center', va='bottom', fontweight='bold')
        
        ax.set_title('MBO Action Types')
        ax.set_ylabel('Count')
        ax.grid(True, alpha=0.3)
        
        st.pyplot(fig)
        plt.close(fig)
