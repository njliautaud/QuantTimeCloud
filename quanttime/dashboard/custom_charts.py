"""
Custom Chart Components for QuantTime Dashboard

Provides matplotlib-based charts as alternatives to TradingView charts.
Uses official Databento Python library for all data processing.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pandas as pd
import numpy as np
import streamlit as st
from typing import Optional, Dict, Any
import seaborn as sns

# Import official Databento library
try:
    from databento import DBNStore, Historical, SType
    DATABENTO_AVAILABLE = True
except ImportError:
    DATABENTO_AVAILABLE = False
    import logging
    logging.warning("Databento library not available. Install with: pip install databento")

# Set style for better-looking charts
plt.style.use('dark_background')
sns.set_palette("husl")


def create_candlestick_chart(df: pd.DataFrame, title: str = "Price Chart", figsize: tuple = (12, 8)) -> plt.Figure:
    """
    Create a professional candlestick chart using matplotlib.
    Uses Databento timestamp fields for accurate time representation.
    
    Args:
        df: DataFrame with OHLCV data (timestamp, open, high, low, close, volume)
        title: Chart title
        figsize: Figure size (width, height)
        
    Returns:
        matplotlib Figure object
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, gridspec_kw={'height_ratios': [3, 1]})
    
    # Ensure timestamp is datetime (Databento format)
    if 'timestamp' in df.columns:
        df = df.copy()
        df['datetime'] = pd.to_datetime(df['timestamp'])
    else:
        df['datetime'] = pd.to_datetime(df.index)
    
    # Color scheme
    colors = {
        'up': '#00ff88',      # Green for up candles
        'down': '#ff4444',    # Red for down candles
        'volume_up': '#00ff88',
        'volume_down': '#ff4444',
        'background': '#1a1a1a',
        'grid': '#333333',
        'text': '#ffffff'
    }
    
    # Set background
    fig.patch.set_facecolor(colors['background'])
    ax1.set_facecolor(colors['background'])
    ax2.set_facecolor(colors['background'])
    
    # Plot candlesticks
    for i, row in df.iterrows():
        datetime = row['datetime']
        open_price = row['open']
        high = row['high']
        low = row['low']
        close = row['close']
        
        # Determine if candle is up or down
        is_up = close >= open_price
        color = colors['up'] if is_up else colors['down']
        
        # Calculate candle dimensions
        body_height = abs(close - open_price)
        body_bottom = min(open_price, close)
        
        # Draw wick (high-low line)
        ax1.plot([datetime, datetime], [low, high], color=color, linewidth=1)
        
        # Draw body
        if body_height > 0:
            rect = Rectangle((datetime - pd.Timedelta(minutes=0.4), body_bottom), 
                           pd.Timedelta(minutes=0.8), body_height,
                           facecolor=color, edgecolor=color, linewidth=1)
            ax1.add_patch(rect)
        else:
            # Doji - just a line
            ax1.plot([datetime - pd.Timedelta(minutes=0.4), datetime + pd.Timedelta(minutes=0.4)], 
                    [open_price, open_price], color=color, linewidth=2)
    
    # Plot volume bars
    for i, row in df.iterrows():
        datetime = row['datetime']
        volume = row['volume']
        close = row['close']
        open_price = row['open']
        
        # Color volume based on price direction
        vol_color = colors['volume_up'] if close >= open_price else colors['volume_down']
        
        ax2.bar(datetime, volume, color=vol_color, alpha=0.7, width=pd.Timedelta(minutes=0.8))
    
    # Customize price chart
    ax1.set_title(title, color=colors['text'], fontsize=16, fontweight='bold', pad=20)
    ax1.set_ylabel('Price ($)', color=colors['text'], fontsize=12)
    ax1.grid(True, alpha=0.3, color=colors['grid'])
    ax1.tick_params(colors=colors['text'])
    
    # Format x-axis
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=15))
    
    # Customize volume chart
    ax2.set_ylabel('Volume', color=colors['text'], fontsize=12)
    ax2.set_xlabel('Time', color=colors['text'], fontsize=12)
    ax2.grid(True, alpha=0.3, color=colors['grid'])
    ax2.tick_params(colors=colors['text'])
    
    # Format x-axis for volume chart
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.MinuteLocator(interval=15))
    
    # Rotate x-axis labels
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
    
    # Add price statistics
    price_range = f"${df['low'].min():.2f} - ${df['high'].max():.2f}"
    total_volume = f"{df['volume'].sum():,}"
    
    stats_text = f"Price Range: {price_range} | Total Volume: {total_volume} | Candles: {len(df)}"
    fig.text(0.5, 0.02, stats_text, ha='center', va='bottom', color=colors['text'], fontsize=10)
    
    plt.tight_layout()
    return fig


def create_technical_indicators_chart(df: pd.DataFrame, figsize: tuple = (12, 10)) -> plt.Figure:
    """
    Create a chart with technical indicators.
    Uses Databento price data for accurate calculations.
    
    Args:
        df: DataFrame with OHLCV data
        figsize: Figure size
        
    Returns:
        matplotlib Figure object
    """
    fig, axes = plt.subplots(4, 1, figsize=figsize, gridspec_kw={'height_ratios': [2, 1, 1, 1]})
    
    # Ensure timestamp is datetime (Databento format)
    if 'timestamp' in df.columns:
        df = df.copy()
        df['datetime'] = pd.to_datetime(df['timestamp'])
    else:
        df['datetime'] = pd.to_datetime(df.index)
    
    # Color scheme
    colors = {
        'price': '#00ff88',
        'sma': '#ffaa00',
        'ema': '#ff00ff',
        'rsi': '#00ffff',
        'macd': '#ff8800',
        'volume': '#888888',
        'background': '#1a1a1a',
        'grid': '#333333',
        'text': '#ffffff'
    }
    
    # Set background
    fig.patch.set_facecolor(colors['background'])
    for ax in axes:
        ax.set_facecolor(colors['background'])
    
    # Calculate technical indicators
    df_tech = df.copy()
    
    # Moving averages
    df_tech['SMA_20'] = df_tech['close'].rolling(20).mean()
    df_tech['EMA_12'] = df_tech['close'].ewm(span=12).mean()
    
    # RSI
    delta = df_tech['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df_tech['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    df_tech['EMA_26'] = df_tech['close'].ewm(span=26).mean()
    df_tech['MACD'] = df_tech['EMA_12'] - df_tech['EMA_26']
    df_tech['MACD_Signal'] = df_tech['MACD'].ewm(span=9).mean()
    df_tech['MACD_Histogram'] = df_tech['MACD'] - df_tech['MACD_Signal']
    
    # Plot 1: Price with moving averages
    axes[0].plot(df_tech['datetime'], df_tech['close'], color=colors['price'], linewidth=2, label='Close Price')
    axes[0].plot(df_tech['datetime'], df_tech['SMA_20'], color=colors['sma'], linewidth=1, label='SMA 20')
    axes[0].plot(df_tech['datetime'], df_tech['EMA_12'], color=colors['ema'], linewidth=1, label='EMA 12')
    axes[0].set_title('Price with Moving Averages', color=colors['text'], fontsize=14)
    axes[0].set_ylabel('Price ($)', color=colors['text'])
    axes[0].grid(True, alpha=0.3, color=colors['grid'])
    axes[0].legend(loc='upper left')
    axes[0].tick_params(colors=colors['text'])
    
    # Plot 2: RSI
    axes[1].plot(df_tech['datetime'], df_tech['RSI'], color=colors['rsi'], linewidth=2)
    axes[1].axhline(y=70, color='red', linestyle='--', alpha=0.7)
    axes[1].axhline(y=30, color='green', linestyle='--', alpha=0.7)
    axes[1].set_title('RSI (14)', color=colors['text'], fontsize=14)
    axes[1].set_ylabel('RSI', color=colors['text'])
    axes[1].set_ylim(0, 100)
    axes[1].grid(True, alpha=0.3, color=colors['grid'])
    axes[1].tick_params(colors=colors['text'])
    
    # Plot 3: MACD
    axes[2].plot(df_tech['datetime'], df_tech['MACD'], color=colors['macd'], linewidth=2, label='MACD')
    axes[2].plot(df_tech['datetime'], df_tech['MACD_Signal'], color='yellow', linewidth=1, label='Signal')
    axes[2].bar(df_tech['datetime'], df_tech['MACD_Histogram'], color='gray', alpha=0.5, label='Histogram')
    axes[2].set_title('MACD', color=colors['text'], fontsize=14)
    axes[2].set_ylabel('MACD', color=colors['text'])
    axes[2].grid(True, alpha=0.3, color=colors['grid'])
    axes[2].legend(loc='upper left')
    axes[2].tick_params(colors=colors['text'])
    
    # Plot 4: Volume
    axes[3].bar(df_tech['datetime'], df_tech['volume'], color=colors['volume'], alpha=0.7)
    axes[3].set_title('Volume', color=colors['text'], fontsize=14)
    axes[3].set_ylabel('Volume', color=colors['text'])
    axes[3].set_xlabel('Time', color=colors['text'])
    axes[3].grid(True, alpha=0.3, color=colors['grid'])
    axes[3].tick_params(colors=colors['text'])
    
    # Format x-axis for all subplots
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=15))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    return fig


def create_order_flow_chart(df: pd.DataFrame, figsize: tuple = (12, 8)) -> plt.Figure:
    """
    Create an order flow chart showing price and volume distribution.
    Uses Databento volume data for accurate representation.
    
    Args:
        df: DataFrame with OHLCV data
        figsize: Figure size
        
    Returns:
        matplotlib Figure object
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, gridspec_kw={'height_ratios': [2, 1]})
    
    # Ensure timestamp is datetime (Databento format)
    if 'timestamp' in df.columns:
        df = df.copy()
        df['datetime'] = pd.to_datetime(df['timestamp'])
    else:
        df['datetime'] = pd.to_datetime(df.index)
    
    # Color scheme
    colors = {
        'price': '#00ff88',
        'volume': '#ff4444',
        'background': '#1a1a1a',
        'grid': '#333333',
        'text': '#ffffff'
    }
    
    # Set background
    fig.patch.set_facecolor(colors['background'])
    ax1.set_facecolor(colors['background'])
    ax2.set_facecolor(colors['background'])
    
    # Plot 1: Price with volume overlay
    ax1_twin = ax1.twinx()
    
    # Price line
    ax1.plot(df['datetime'], df['close'], color=colors['price'], linewidth=2, label='Close Price')
    ax1.set_ylabel('Price ($)', color=colors['price'], fontsize=12)
    ax1.tick_params(axis='y', colors=colors['price'])
    
    # Volume bars
    ax1_twin.bar(df['datetime'], df['volume'], color=colors['volume'], alpha=0.3, label='Volume')
    ax1_twin.set_ylabel('Volume', color=colors['volume'], fontsize=12)
    ax1_twin.tick_params(axis='y', colors=colors['volume'])
    
    ax1.set_title('Price with Volume Overlay', color=colors['text'], fontsize=16, fontweight='bold')
    ax1.grid(True, alpha=0.3, color=colors['grid'])
    ax1.tick_params(axis='x', colors=colors['text'])
    
    # Plot 2: Volume distribution
    ax2.hist(df['volume'], bins=20, color=colors['volume'], alpha=0.7, edgecolor='white')
    ax2.set_title('Volume Distribution', color=colors['text'], fontsize=14)
    ax2.set_xlabel('Volume', color=colors['text'])
    ax2.set_ylabel('Frequency', color=colors['text'])
    ax2.grid(True, alpha=0.3, color=colors['grid'])
    ax2.tick_params(colors=colors['text'])
    
    # Format x-axis
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=15))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    return fig


def create_comprehensive_chart(df: pd.DataFrame, mbo_df: pd.DataFrame = None, figsize: tuple = (16, 12)) -> plt.Figure:
    """
    Create a comprehensive chart showing 10-minute candles, orderbook, and cumulative delta.
    Uses Databento library for all MBO data processing.
    
    Args:
        df: DataFrame with OHLCV data
        mbo_df: DataFrame with full MBO data from Databento for orderbook analysis
        figsize: Figure size
        
    Returns:
        matplotlib Figure object
    """
    # Create figure with subplots: main chart, orderbook, cumulative delta
    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(3, 3, height_ratios=[3, 1, 1], width_ratios=[2, 1, 0.1])
    
    # Ensure timestamp is datetime (Databento format)
    if 'timestamp' in df.columns:
        df = df.copy()
        df['datetime'] = pd.to_datetime(df['timestamp'])
    else:
        df['datetime'] = pd.to_datetime(df.index)
    
    # Color scheme
    colors = {
        'up': '#00ff88',      # Green for up candles
        'down': '#ff4444',    # Red for down candles
        'volume_up': '#00ff88',
        'volume_down': '#ff4444',
        'background': '#1a1a1a',
        'grid': '#333333',
        'text': '#ffffff',
        'bid': '#00ff88',
        'ask': '#ff4444',
        'delta': '#0088ff'
    }
    
    # Set background
    fig.patch.set_facecolor(colors['background'])
    
    # Main price chart (top left)
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor(colors['background'])
    
    # Plot candlesticks
    for i, row in df.iterrows():
        datetime = row['datetime']
        open_price = row['open']
        high = row['high']
        low = row['low']
        close = row['close']
        
        # Determine if candle is up or down
        is_up = close >= open_price
        color = colors['up'] if is_up else colors['down']
        
        # Calculate candle dimensions
        body_height = abs(close - open_price)
        body_bottom = min(open_price, close)
        
        # Draw wick (high-low line)
        ax1.plot([datetime, datetime], [low, high], color=color, linewidth=1)
        
        # Draw body
        if body_height > 0:
            rect = Rectangle((datetime - pd.Timedelta(minutes=4), body_bottom), 
                           pd.Timedelta(minutes=8), body_height,
                           facecolor=color, edgecolor=color, linewidth=1)
            ax1.add_patch(rect)
        else:
            # Doji - just a line
            ax1.plot([datetime - pd.Timedelta(minutes=4), datetime + pd.Timedelta(minutes=4)], 
                    [open_price, open_price], color=color, linewidth=2)
    
    # Customize main chart
    ax1.set_title('ES Futures - 10-Minute Candles', color=colors['text'], fontsize=16, fontweight='bold', pad=20)
    ax1.set_ylabel('Price ($)', color=colors['text'], fontsize=12)
    ax1.grid(True, alpha=0.3, color=colors['grid'])
    ax1.tick_params(colors=colors['text'])
    
    # Format x-axis
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
    
    # Volume chart (middle left)
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_facecolor(colors['background'])
    
    # Plot volume bars
    for i, row in df.iterrows():
        datetime = row['datetime']
        volume = row['volume']
        close = row['close']
        open_price = row['open']
        
        # Color volume based on price direction
        vol_color = colors['volume_up'] if close >= open_price else colors['volume_down']
        
        ax2.bar(datetime, volume, color=vol_color, alpha=0.7, width=pd.Timedelta(minutes=8))
    
    ax2.set_ylabel('Volume', color=colors['text'], fontsize=12)
    ax2.grid(True, alpha=0.3, color=colors['grid'])
    ax2.tick_params(colors=colors['text'])
    
    # Format x-axis for volume chart
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
    
    # Orderbook chart (top right)
    ax3 = fig.add_subplot(gs[0, 1])
    ax3.set_facecolor(colors['background'])
    
    if mbo_df is not None and not mbo_df.empty:
        # Generate orderbook data using Databento fields
        orderbook_data = _generate_orderbook_from_mbo(mbo_df, price_levels=10)
        
        if not orderbook_data.empty:
            # Plot orderbook
            ax3.barh(orderbook_data['price'], orderbook_data['bid_size'], 
                    color=colors['bid'], alpha=0.7, label='Bids')
            ax3.barh(orderbook_data['price'], orderbook_data['ask_size'], 
                    color=colors['ask'], alpha=0.7, label='Asks')
            
            ax3.set_title('Order Book', color=colors['text'], fontsize=14)
            ax3.set_xlabel('Size', color=colors['text'], fontsize=10)
            ax3.grid(True, alpha=0.3, color=colors['grid'])
            ax3.tick_params(colors=colors['text'])
            ax3.legend(loc='upper right')
    
    # Cumulative delta chart (bottom)
    ax4 = fig.add_subplot(gs[2, :])
    ax4.set_facecolor(colors['background'])
    
    if mbo_df is not None and not mbo_df.empty:
        # Calculate cumulative delta using Databento fields
        cumulative_delta = _calculate_cumulative_delta_from_mbo(mbo_df)
        
        if not cumulative_delta.empty:
            ax4.plot(cumulative_delta['timestamp'], cumulative_delta['cumulative_delta'], 
                    color=colors['delta'], linewidth=2)
            ax4.axhline(y=0, color=colors['text'], linestyle='--', alpha=0.5)
            
            ax4.set_title('Cumulative Delta', color=colors['text'], fontsize=14)
            ax4.set_ylabel('Cumulative Delta', color=colors['text'], fontsize=10)
            ax4.set_xlabel('Time', color=colors['text'], fontsize=10)
            ax4.grid(True, alpha=0.3, color=colors['grid'])
            ax4.tick_params(colors=colors['text'])
            
            # Format x-axis
            ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax4.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
    
    # Rotate x-axis labels
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
    plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)
    
    # Add price statistics
    price_range = f"${df['low'].min():.2f} - ${df['high'].max():.2f}"
    total_volume = f"{df['volume'].sum():,}"
    
    stats_text = f"Price Range: {price_range} | Total Volume: {total_volume} | Candles: {len(df)}"
    fig.text(0.5, 0.02, stats_text, ha='center', va='bottom', color=colors['text'], fontsize=10)
    
    plt.tight_layout()
    return fig


def _generate_orderbook_from_mbo(mbo_df: pd.DataFrame, price_levels: int = 10) -> pd.DataFrame:
    """
    Generate orderbook data from MBO DataFrame using Databento fields.
    
    Args:
        mbo_df: DataFrame with MBO data from Databento
        price_levels: Number of price levels to show
        
    Returns:
        DataFrame with orderbook data
    """
    try:
        # Filter for order book updates (not executions) using Databento action field
        orderbook_updates = mbo_df[mbo_df['action'] != 'F'].copy()
        
        if orderbook_updates.empty:
            return pd.DataFrame()
        
        # Get unique prices from Databento price field
        unique_prices = sorted(orderbook_updates['price'].unique())
        
        if len(unique_prices) == 0:
            return pd.DataFrame()
        
        # Take the middle price levels
        mid_idx = len(unique_prices) // 2
        start_idx = max(0, mid_idx - price_levels // 2)
        end_idx = min(len(unique_prices), start_idx + price_levels)
        selected_prices = unique_prices[start_idx:end_idx]
        
        # Create orderbook DataFrame
        orderbook_data = []
        for price in selected_prices:
            # Get latest bid and ask sizes for this price
            price_data = orderbook_updates[orderbook_updates['price'] == price]
            
            # Separate bids and asks using Databento side field
            bids = price_data[price_data['side'] == 'B']
            asks = price_data[price_data['side'] == 'A']
            
            bid_size = bids['size'].sum() if not bids.empty else 0
            ask_size = asks['size'].sum() if not asks.empty else 0
            
            orderbook_data.append({
                'price': price,
                'bid_size': bid_size,
                'ask_size': ask_size
            })
        
        return pd.DataFrame(orderbook_data)
        
    except Exception as e:
        print(f"Error generating orderbook: {e}")
        return pd.DataFrame()


def _calculate_cumulative_delta_from_mbo(mbo_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate cumulative delta from MBO DataFrame using Databento fields.
    
    Args:
        mbo_df: DataFrame with MBO data from Databento
        
    Returns:
        DataFrame with cumulative delta
    """
    try:
        # Filter for execution events only using Databento action field
        executions = mbo_df[mbo_df['action'] == 'F'].copy()
        
        if executions.empty:
            return pd.DataFrame()
        
        # Calculate delta for each execution using Databento side and size fields
        executions['delta'] = executions.apply(
            lambda row: row['size'] if row['side'] == 'B' else -row['size'], axis=1
        )
        
        # Calculate cumulative delta
        executions['cumulative_delta'] = executions['delta'].cumsum()
        
        # Select relevant columns
        result = executions[['datetime', 'cumulative_delta']].copy()
        result['timestamp'] = result['datetime']
        
        return result
        
    except Exception as e:
        print(f"Error calculating cumulative delta: {e}")
        return pd.DataFrame()


def create_replay_chart(tick_df: pd.DataFrame, current_tick_index: int = 0, timeframe: str = '1min', figsize: tuple = (14, 10)) -> plt.Figure:
    """
    Create a tick-level replay chart with navigation controls.
    Displays tick data with current position indicator and replay functionality.
    Uses Databento timestamp fields for accurate time representation.
    
    Args:
        tick_df: DataFrame with tick-level data from Databento
        current_tick_index: Current tick position for replay
        timeframe: Timeframe for candle conversion ('1min', '5min', etc.)
        figsize: Figure size (width, height)
        
    Returns:
        matplotlib Figure object
    """
    if tick_df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'No tick data available', ha='center', va='center', transform=ax.transAxes, color='white')
        return fig
    
    # Create figure with subplots
    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(4, 1, height_ratios=[3, 1, 1, 1], hspace=0.3)
    
    # Color scheme
    colors = {
        'background': '#1a1a1a',
        'grid': '#333333',
        'text': '#ffffff',
        'tick_line': '#00ff88',
        'current_tick': '#ffff00',
        'execution': '#00ff88',
        'bid': '#00aa00',
        'ask': '#ff4444',
        'cancel': '#ff8800'
    }
    
    # Set background
    fig.patch.set_facecolor(colors['background'])
    
    # Main price chart (subplot 1)
    ax1 = fig.add_subplot(gs[0])
    ax1.set_facecolor(colors['background'])
    
    # Volume chart (subplot 2)
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax2.set_facecolor(colors['background'])
    
    # Order flow chart (subplot 3)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax3.set_facecolor(colors['background'])
    
    # Tick details (subplot 4)
    ax4 = fig.add_subplot(gs[3])
    ax4.set_facecolor(colors['background'])
    
    # Convert tick data to candles for the specified timeframe
    if timeframe != 'tick':
        candles_df = _convert_ticks_to_candles(tick_df, timeframe)
        if not candles_df.empty:
            # Plot candles
            _plot_candles_on_axis(candles_df, ax1, colors)
    
    # Plot individual ticks up to current position
    visible_ticks = tick_df.iloc[:current_tick_index + 1]
    if not visible_ticks.empty:
        # Plot tick line
        ax1.plot(visible_ticks['datetime'], visible_ticks['price'], 
                color=colors['tick_line'], linewidth=1, alpha=0.7, label='Tick Price')
        
        # Highlight current tick
        if current_tick_index < len(tick_df):
            current_tick = tick_df.iloc[current_tick_index]
            ax1.scatter(current_tick['datetime'], current_tick['price'], 
                       color=colors['current_tick'], s=100, zorder=5, label='Current Tick')
    
    # Plot volume
    if not visible_ticks.empty:
        executions = visible_ticks[visible_ticks['action'] == 'F']
        if not executions.empty:
            ax2.bar(executions['datetime'], executions['size'], 
                   color=colors['execution'], alpha=0.7, width=0.0001)
    
    # Plot order flow (bid/ask/cancel)
    if not visible_ticks.empty:
        bids = visible_ticks[visible_ticks['action'] == 'B']
        asks = visible_ticks[visible_ticks['action'] == 'A']
        cancels = visible_ticks[visible_ticks['action'] == 'C']
        
        if not bids.empty:
            ax3.scatter(bids['datetime'], bids['price'], color=colors['bid'], s=20, alpha=0.7, label='Bids')
        if not asks.empty:
            ax3.scatter(asks['datetime'], asks['price'], color=colors['ask'], s=20, alpha=0.7, label='Asks')
        if not cancels.empty:
            ax3.scatter(cancels['datetime'], cancels['price'], color=colors['cancel'], s=20, alpha=0.7, label='Cancels')
    
    # Display current tick details
    if current_tick_index < len(tick_df):
        current_tick = tick_df.iloc[current_tick_index]
        tick_info = f"Tick {current_tick_index + 1}/{len(tick_df)} | "
        tick_info += f"Time: {current_tick['datetime'].strftime('%H:%M:%S.%f')[:-3]} | "
        tick_info += f"Price: ${current_tick['price']:.2f} | "
        tick_info += f"Size: {current_tick['size']} | "
        tick_info += f"Action: {current_tick['action']} | "
        tick_info += f"Side: {current_tick['side']}"
        
        ax4.text(0.02, 0.5, tick_info, transform=ax4.transAxes, 
                color=colors['text'], fontsize=10, verticalalignment='center')
    
    # Configure axes
    for ax in [ax1, ax2, ax3]:
        ax.grid(True, color=colors['grid'], alpha=0.3)
        ax.tick_params(colors=colors['text'])
        for spine in ax.spines.values():
            spine.set_color(colors['grid'])
    
    # Set labels and titles
    ax1.set_title(f'Tick Replay Chart - {timeframe} Timeframe | Tick {current_tick_index + 1}/{len(tick_df)}', 
                  color=colors['text'], fontsize=12)
    ax1.set_ylabel('Price ($)', color=colors['text'])
    ax2.set_ylabel('Volume', color=colors['text'])
    ax3.set_ylabel('Order Flow', color=colors['text'])
    ax4.set_ylabel('Current Tick', color=colors['text'])
    
    # Format x-axis
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # Add legends
    ax1.legend(loc='upper left', framealpha=0.8)
    ax3.legend(loc='upper left', framealpha=0.8)
    
    return fig


def _convert_ticks_to_candles(tick_df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Convert tick data to OHLCV candles for specified timeframe.
    Uses Databento execution events (action == 'F').
    
    Args:
        tick_df: DataFrame with tick-level data
        timeframe: Time interval ('1min', '5min', etc.)
        
    Returns:
        DataFrame with OHLCV candles
    """
    try:
        # Filter for execution events only
        executions = tick_df[tick_df['action'] == 'F'].copy()
        if executions.empty:
            return pd.DataFrame()
        
        # Set datetime as index for resampling
        executions = executions.set_index('datetime')
        
        # Resample to OHLCV
        ohlcv = executions['price'].resample(timeframe).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        })
        
        # Add volume
        ohlcv['volume'] = executions['size'].resample(timeframe).sum()
        
        # Reset index
        ohlcv = ohlcv.reset_index()
        ohlcv['timestamp'] = ohlcv['datetime']
        
        return ohlcv.dropna()
        
    except Exception as e:
        print(f"Error converting ticks to candles: {e}")
        return pd.DataFrame()


def _plot_candles_on_axis(candles_df: pd.DataFrame, ax: plt.Axes, colors: dict) -> None:
    """
    Plot candlesticks on the given axis.
    
    Args:
        candles_df: DataFrame with OHLCV data
        ax: Matplotlib axis
        colors: Color scheme dictionary
    """
    for i, row in candles_df.iterrows():
        datetime = row['datetime']
        open_price = row['open']
        high = row['high']
        low = row['low']
        close = row['close']
        
        # Determine if candle is up or down
        is_up = close >= open_price
        color = colors['execution'] if is_up else colors['ask']
        
        # Calculate candle dimensions
        body_height = abs(close - open_price)
        body_bottom = min(open_price, close)
        
        # Draw wick (high-low line)
        ax.plot([datetime, datetime], [low, high], color=color, linewidth=1)
        
        # Draw body
        if body_height > 0:
            from matplotlib.patches import Rectangle
            rect = Rectangle((datetime - pd.Timedelta(minutes=0.4), body_bottom), 
                           pd.Timedelta(minutes=0.8), body_height,
                           facecolor=color, edgecolor=color, linewidth=1)
            ax.add_patch(rect)
        else:
            # Doji - just a line
            ax.plot([datetime - pd.Timedelta(minutes=0.4), datetime + pd.Timedelta(minutes=0.4)], 
                    [open_price, open_price], color=color, linewidth=2)


def display_replay_chart(tick_df: pd.DataFrame, timeframe: str = '1min') -> None:
    """
    Display tick replay chart with Streamlit controls.
    Uses Databento data for accurate tick representation.
    
    Args:
        tick_df: DataFrame with tick-level data
        timeframe: Default timeframe for display
    """
    if tick_df.empty:
        st.error("No tick data available for replay")
        return
    
    st.subheader("🎮 Tick Replay Chart")
    
    # Timeframe selection
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        selected_timeframe = st.selectbox(
            "Select Timeframe",
            ["tick", "1min", "5min", "10min"],
            index=1,  # Default to 1min
            key="replay_timeframe"
        )
    
    with col2:
        st.metric("Total Ticks", len(tick_df))
    
    with col3:
        st.metric("Time Range", f"{tick_df['datetime'].min().strftime('%H:%M')} - {tick_df['datetime'].max().strftime('%H:%M')}")
    
    # Replay controls
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if st.button("⏮️ First Tick", key="first_tick"):
            st.session_state.current_tick_index = 0
    
    with col2:
        if st.button("⏪ Previous Tick", key="prev_tick"):
            if 'current_tick_index' not in st.session_state:
                st.session_state.current_tick_index = 0
            else:
                st.session_state.current_tick_index = max(0, st.session_state.current_tick_index - 1)
    
    with col3:
        if st.button("⏯️ Play/Pause", key="play_pause"):
            if 'replay_playing' not in st.session_state:
                st.session_state.replay_playing = False
            st.session_state.replay_playing = not st.session_state.replay_playing
    
    with col4:
        if st.button("⏩ Next Tick", key="next_tick"):
            if 'current_tick_index' not in st.session_state:
                st.session_state.current_tick_index = 0
            else:
                st.session_state.current_tick_index = min(len(tick_df) - 1, st.session_state.current_tick_index + 1)
    
    with col5:
        if st.button("⏭️ Last Tick", key="last_tick"):
            st.session_state.current_tick_index = len(tick_df) - 1
    
    # Initialize current tick index if not set
    if 'current_tick_index' not in st.session_state:
        st.session_state.current_tick_index = 0
    
    # Tick position slider
    current_tick_index = st.slider(
        "Tick Position",
        0, len(tick_df) - 1,
        st.session_state.current_tick_index,
        key="tick_slider"
    )
    
    # Update session state
    st.session_state.current_tick_index = current_tick_index
    
    # Auto-play functionality
    if st.session_state.get('replay_playing', False):
        if current_tick_index < len(tick_df) - 1:
            st.session_state.current_tick_index += 1
            st.rerun()
        else:
            st.session_state.replay_playing = False
    
    # Create and display the replay chart
    try:
        fig = create_replay_chart(tick_df, current_tick_index, selected_timeframe)
        st.pyplot(fig)
        
        # Display current tick details
        if current_tick_index < len(tick_df):
            current_tick = tick_df.iloc[current_tick_index]
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Current Time", current_tick['datetime'].strftime('%H:%M:%S.%f')[:-3])
            with col2:
                st.metric("Price", f"${current_tick['price']:.2f}")
            with col3:
                st.metric("Size", current_tick['size'])
            with col4:
                st.metric("Action", current_tick['action'])
        
    except Exception as e:
        st.error(f"Error creating replay chart: {e}")
        st.exception(e)


def display_custom_charts(df: pd.DataFrame, chart_type: str = "candlestick", mbo_df: pd.DataFrame = None) -> None:
    """
    Display custom charts in Streamlit.
    Uses Databento library for all data processing.
    
    Args:
        df: DataFrame with OHLCV data
        chart_type: Type of chart to display ("candlestick", "technical", "orderflow", "comprehensive")
        mbo_df: DataFrame with MBO data from Databento for orderbook analysis (required for comprehensive chart)
    """
    if df.empty:
        st.warning("No data available for charting")
        return
    
    try:
        if chart_type == "candlestick":
            fig = create_candlestick_chart(df, title="ES Futures - Custom Candlestick Chart")
            st.pyplot(fig)
            
        elif chart_type == "technical":
            fig = create_technical_indicators_chart(df)
            st.pyplot(fig)
            
        elif chart_type == "orderflow":
            fig = create_order_flow_chart(df)
            st.pyplot(fig)
            
        elif chart_type == "comprehensive":
            if mbo_df is None or mbo_df.empty:
                st.warning("MBO data required for comprehensive chart. Loading orderbook data...")
                # Try to load MBO data if not provided using Databento library
                from quanttime.adapter.mbo_data_loader import MBODataLoader
                mbo_loader = MBODataLoader()
                if hasattr(mbo_loader, 'available_dates') and mbo_loader.available_dates:
                    most_recent_date = mbo_loader.available_dates[0]
                    mbo_df = mbo_loader.load_mbo_data_first_10min(most_recent_date)
            
            fig = create_comprehensive_chart(df, mbo_df)
            st.pyplot(fig)
            
        else:
            st.error(f"Unknown chart type: {chart_type}")
            
    except Exception as e:
        st.error(f"Error creating chart: {e}")
        st.exception(e)


def create_performance_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Create a performance summary from OHLCV data.
    Uses Databento timestamp fields for accurate calculations.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        Dictionary with performance metrics
    """
    if df.empty:
        return {}
    
    try:
        # Basic metrics
        total_return = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100
        price_range = df['high'].max() - df['low'].min()
        avg_volume = df['volume'].mean()
        total_volume = df['volume'].sum()
        
        # Volatility
        returns = df['close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100  # Annualized
        
        # Price movement analysis
        up_candles = len(df[df['close'] > df['open']])
        down_candles = len(df[df['close'] < df['open']])
        doji_candles = len(df[df['close'] == df['open']])
        
        # Volume analysis
        volume_std = df['volume'].std()
        max_volume = df['volume'].max()
        min_volume = df['volume'].min()
        
        return {
            'total_return_pct': total_return,
            'price_range': price_range,
            'avg_volume': avg_volume,
            'total_volume': total_volume,
            'volatility_pct': volatility,
            'up_candles': up_candles,
            'down_candles': down_candles,
            'doji_candles': doji_candles,
            'volume_std': volume_std,
            'max_volume': max_volume,
            'min_volume': min_volume,
            'total_candles': len(df)
        }
        
    except Exception as e:
        st.error(f"Error calculating performance summary: {e}")
        return {}


def display_performance_metrics(df: pd.DataFrame) -> None:
    """
    Display performance metrics in Streamlit.
    Uses Databento data for accurate calculations.
    
    Args:
        df: DataFrame with OHLCV data
    """
    metrics = create_performance_summary(df)
    
    if not metrics:
        return
    
    st.subheader("📊 Performance Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Return", f"{metrics['total_return_pct']:.2f}%")
        st.metric("Price Range", f"${metrics['price_range']:.2f}")
    
    with col2:
        st.metric("Volatility", f"{metrics['volatility_pct']:.2f}%")
        st.metric("Avg Volume", f"{metrics['avg_volume']:,.0f}")
    
    with col3:
        st.metric("Up Candles", metrics['up_candles'])
        st.metric("Down Candles", metrics['down_candles'])
    
    with col4:
        st.metric("Total Volume", f"{metrics['total_volume']:,.0f}")
        st.metric("Total Candles", metrics['total_candles'])


def create_footprint_chart(df: pd.DataFrame, figsize: tuple = (12, 8)) -> plt.Figure:
    """
    Create a footprint chart showing volume at price levels.
    Uses Databento data for accurate price and volume representation.
    
    Args:
        df: DataFrame with OHLCV data
        figsize: Figure size (width, height)
        
    Returns:
        matplotlib Figure object
    """
    if df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'No data available for footprint', ha='center', va='center', transform=ax.transAxes, color='white')
        return fig
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Color scheme
    colors = {
        'background': '#1a1a1a',
        'grid': '#333333',
        'text': '#ffffff',
        'up_volume': '#00ff88',
        'down_volume': '#ff4444',
        'neutral_volume': '#888888'
    }
    
    # Set background
    fig.patch.set_facecolor(colors['background'])
    ax.set_facecolor(colors['background'])
    
    # Calculate price levels
    price_range = df['high'].max() - df['low'].min()
    if price_range == 0:
        price_range = 1
    
    # Create price bins
    num_bins = min(20, len(df))  # Max 20 bins
    price_bins = np.linspace(df['low'].min(), df['high'].max(), num_bins + 1)
    
    # Calculate volume at each price level
    volume_data = []
    for i in range(len(price_bins) - 1):
        price_low = price_bins[i]
        price_high = price_bins[i + 1]
        price_mid = (price_low + price_high) / 2
        
        # Find candles that overlap with this price range
        mask = (df['low'] <= price_high) & (df['high'] >= price_low)
        candles_in_range = df[mask]
        
        if not candles_in_range.empty:
            # Calculate volume weighted by overlap
            total_volume = candles_in_range['volume'].sum()
            
            # Determine if this price level is mostly up or down
            up_volume = candles_in_range[candles_in_range['close'] >= candles_in_range['open']]['volume'].sum()
            down_volume = candles_in_range[candles_in_range['close'] < candles_in_range['open']]['volume'].sum()
            
            volume_data.append({
                'price': price_mid,
                'total_volume': total_volume,
                'up_volume': up_volume,
                'down_volume': down_volume
            })
    
    if not volume_data:
        ax.text(0.5, 0.5, 'No volume data available', ha='center', va='center', transform=ax.transAxes, color='white')
        return fig
    
    # Convert to DataFrame
    footprint_df = pd.DataFrame(volume_data)
    
    # Create horizontal bar chart
    y_pos = np.arange(len(footprint_df))
    
    # Plot up volume (green)
    ax.barh(y_pos, footprint_df['up_volume'], color=colors['up_volume'], alpha=0.7, label='Up Volume')
    
    # Plot down volume (red) - negative to show on left side
    ax.barh(y_pos, -footprint_df['down_volume'], color=colors['down_volume'], alpha=0.7, label='Down Volume')
    
    # Set y-axis labels to prices
    ax.set_yticks(y_pos)
    ax.set_yticklabels([f'${p:.2f}' for p in footprint_df['price']])
    
    # Configure axes
    ax.set_xlabel('Volume', color=colors['text'])
    ax.set_ylabel('Price Level', color=colors['text'])
    ax.set_title('Volume Footprint Chart', color=colors['text'], fontsize=14)
    
    # Add grid
    ax.grid(True, color=colors['grid'], alpha=0.3)
    
    # Add legend
    ax.legend(loc='upper right', framealpha=0.8)
    
    # Add volume statistics
    total_vol = footprint_df['total_volume'].sum()
    up_vol = footprint_df['up_volume'].sum()
    down_vol = footprint_df['down_volume'].sum()
    
    stats_text = f'Total Volume: {total_vol:,.0f}\nUp Volume: {up_vol:,.0f}\nDown Volume: {down_vol:,.0f}'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, verticalalignment='top', 
            bbox=dict(boxstyle='round', facecolor='black', alpha=0.7), color=colors['text'])
    
    # Configure spines
    for spine in ax.spines.values():
        spine.set_color(colors['grid'])
    
    return fig


def display_footprint_chart(df: pd.DataFrame) -> None:
    """
    Display footprint chart in Streamlit.
    Uses Databento data for accurate visualization.
    
    Args:
        df: DataFrame with OHLCV data
    """
    if df.empty:
        st.error("No data available for footprint chart")
        return
    
    st.subheader("👣 Volume Footprint Chart")
    
    try:
        fig = create_footprint_chart(df)
        st.pyplot(fig)
        
        # Show footprint statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Volume", f"{df['volume'].sum():,.0f}")
        with col2:
            up_volume = df[df['close'] >= df['open']]['volume'].sum()
            st.metric("Up Volume", f"{up_volume:,.0f}")
        with col3:
            down_volume = df[df['close'] < df['open']]['volume'].sum()
            st.metric("Down Volume", f"{down_volume:,.0f}")
            
    except Exception as e:
        st.error(f"Error creating footprint chart: {e}")
        st.exception(e)
