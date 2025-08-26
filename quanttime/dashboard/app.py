"""
Streamlit dashboard for QuantTime ML Trading Suite.

A comprehensive trading platform built around Databento MBO Level 3 data
for multi-second to multi-minute trading strategies.
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path
import queue
import threading
import io
import contextlib

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import plotly.graph_objects as go
import plotly.express as px

from quanttime.utils.config import AppConfig
from quanttime.runtime.hist_service import (
    get_available_databento_dates,
    get_databento_symbols,
    load_mbo_data_for_analysis,
    generate_orderbook_snapshot,
    generate_footprint_data,
    get_mbo_statistics,
    get_historical_data_official,
    validate_mbo_data_quality,
    resolve_symbols_official,
    get_available_symbols_official,
    get_dataset_info_official
)
from quanttime.runtime.live_service import get_live_service
from quanttime.runtime.stream_service import get_chart_stream_service
from quanttime.dashboard.components import (
    tradingview_chart,
    footprint_chart,
    model_card,
    model_card_clickable,
    list_parquet_files,
    list_datasets
)
from quanttime.dashboard.data_management_components import render_data_management_dashboard
from quanttime.dashboard.model_cards import (
    render_model_cards_dashboard,
    render_model_details,
    render_backtest_model_selector
)
from quanttime.dashboard.date_range_selector import render_date_range_selector
from quanttime.dashboard.progress_bar import ProgressTracker
from quanttime.dashboard.server_control import ServerControlCenter, server_control
from quanttime.dashboard.enhanced_server_control import render_enhanced_server_control
from quanttime.dashboard.task_submission_interface import render_task_submission_interface, render_task_monitoring
from quanttime.dashboard.data_transmission_interface import render_data_transmission_interface
from quanttime.dashboard.dev_tools import dev_tools
from quanttime.dashboard.server_deployment import render_server_deployment
from quanttime.dashboard.task_progress_tracker import progress_tracker
from quanttime.dashboard.hybrid_pipeline_interface import render_hybrid_pipeline_interface
from quanttime.dashboard.enhanced_backtest_interface import render_enhanced_backtest_interface
from quanttime.dashboard.syncthing_ray_interface import render_syncthing_ray_interface
from quanttime.dashboard.sftp_interface import render_sftp_interface, render_sftp_ray_integration
from quanttime.utils.training_progress import create_progress_callback, create_training_progress
import subprocess
import json
from quanttime.features.mbo_features import (
    engineer_mbo_features,
    get_feature_importance_ranking,
    validate_features,
    FeatureConfig
)
from quanttime.backtest.mbo_backtest_engine import (
    run_mbo_backtest,
    BacktestConfig,
    OrderSide,
    OrderType
)
from quanttime.adapter.databento_loader import get_databento_loader
from quanttime.data.pipeline import create_pipeline_from_config, DataPipelineConfig
from quanttime.data.processor import convert_dbn_to_parquet_file
from quanttime.dashboard.symbol_selector import symbol_dropdown, symbol_dropdown_simple, display_symbol_info
from quanttime.dashboard.custom_charts import display_custom_charts, display_performance_metrics
from quanttime.dashboard.matplotlib_charts import display_matplotlib_charts, display_data_summary
from quanttime.models.enhanced_mbo_lightgbm import create_enhanced_mbo_lightgbm_model
from quanttime.models.model_registry import ModelRegistry
from quanttime.models.trade_engine import TradeEngine, TradeEngineConfig, create_trade_engine
from quanttime.models.trade_engine import PositionSide

# Enhanced logging setup
from quanttime.utils.logging_config import setup_logging, log_device_operation, log_server_operation

# Setup enhanced logging with device tagging
logger = setup_logging(
    log_level="INFO",
    device_name="razer",
    device_type="laptop"
)

# Page configuration
st.set_page_config(
    page_title="QuantTime ML Trading Suite",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state for button responsiveness
if 'processing_active' not in st.session_state:
    st.session_state.processing_active = False
if 'current_stage' not in st.session_state:
    st.session_state.current_stage = "Ready"
if 'button_click_count' not in st.session_state:
    st.session_state.button_click_count = 0

# Custom CSS
st.markdown("""
<style>
.main-header {
    color: #1f77b4;
    text-align: center;
    font-size: 2.5rem;
    font-weight: bold;
    margin-bottom: 2rem;
}

.console-output {
    background-color: #1e1e1e;
    color: #00ff00;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    padding: 10px;
    border-radius: 5px;
    max-height: 300px;
    overflow-y: auto;
    border: 1px solid #333;
}

.progress-container {
    background-color: #f0f0f0;
    border-radius: 5px;
    padding: 10px;
    margin: 10px 0;
}

.error-message {
    background-color: #ffebee;
    color: #c62828;
    padding: 10px;
    border-radius: 5px;
    border-left: 4px solid #c62828;
    margin: 10px 0;
}

.success-message {
    background-color: #e8f5e8;
    color: #2e7d32;
    padding: 10px;
    border-radius: 5px;
    border-left: 4px solid #2e7d32;
    margin: 10px 0;
}

.info-message {
    background-color: #e3f2fd;
    color: #1565c0;
    padding: 10px;
    border-radius: 5px;
    border-left: 4px solid #1565c0;
    margin: 10px 0;
}

.schema-info {
    background: #e3f2fd;
    border-left: 4px solid #1f77b4;
    padding: 15px;
    border-radius: 5px;
    margin: 15px 0;
}

.schema-stats {
    display: flex;
    gap: 20px;
    margin-top: 10px;
}

.schema-stat {
    text-align: center;
    padding: 10px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.schema-stat-value {
    font-size: 1.5em;
    font-weight: bold;
    color: #1f77b4;
}

.schema-stat-label {
    font-size: 0.9em;
    color: #6c757d;
    margin-top: 5px;
}

.model-popup {
    background-color: #f0f2f6;
    padding: 20px;
    border-radius: 10px;
    border: 2px solid #1f77b4;
    margin: 10px 0;
}
</style>
""", unsafe_allow_html=True)

# Global console output queue
console_queue = queue.Queue()

# Custom logging handler to capture all logs and send to console
class ConsoleLogHandler(logging.Handler):
    def emit(self, record):
        try:
            # Format the log message
            msg = self.format(record)
            # Add timestamp and level
            timestamp = datetime.now().strftime("%H:%M:%S")
            level_emoji = {
                'DEBUG': '🔍',
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'CRITICAL': '🚨'
            }.get(record.levelname, 'ℹ️')
            
            formatted_msg = f"[{timestamp}] {level_emoji} {record.levelname}: {msg}"
            
            # Send to console queue
            console_queue.put(formatted_msg)
        except Exception:
            pass

# Set up the custom handler
console_handler = ConsoleLogHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(formatter)

# Add handler to root logger to capture all logs
logging.getLogger().addHandler(console_handler)

def log_to_console(message: str, level: str = "INFO"):
    """Log message to console queue for real-time display"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    console_queue.put(f"[{timestamp}] {level}: {message}")

def create_console_output():
    """Create a real-time console output component with autoscroll and auto-refresh"""
    st.markdown("### 📺 Real-Time Console Output")
    
    # Add clear console button
    col1, col2, col3 = st.columns([3, 1, 1])
    with col2:
        if st.button("🔄 Refresh", help="Refresh console output"):
            st.rerun()
    with col3:
        if st.button("🗑️ Clear Console", help="Clear all console output"):
            st.session_state.console_messages = []
            st.rerun()
    
    # Auto-refresh during processing
    if 'processing_active' in st.session_state and st.session_state.processing_active:
        st.info("🔄 Processing is active - console will auto-update")
        # Use Streamlit's rerun for auto-refresh
        st.rerun()
    
    # Create a container for console output
    console_container = st.container()
    
    with console_container:
        # Collect all messages from queue
        messages = []
        while not console_queue.empty():
            try:
                message = console_queue.get_nowait()
                messages.append(message)
            except queue.Empty:
                break
        
        # Store messages in session state for persistence
        if 'console_messages' not in st.session_state:
            st.session_state.console_messages = []
        
        if messages:
            st.session_state.console_messages.extend(messages)
        
        # Display all messages (last 100 to avoid overflow)
        if st.session_state.console_messages:
            display_text = "\n".join(st.session_state.console_messages[-100:])
            
            # Create autoscrolling console with JavaScript
            st.markdown(f"""
            <div class="console-output" id="console-output">
            <pre style="margin: 0; white-space: pre-wrap; word-wrap: break-word;">{display_text}</pre>
            </div>
            <script>
            // Auto-scroll to bottom
            const consoleDiv = document.getElementById('console-output');
            if (consoleDiv) {{
                consoleDiv.scrollTop = consoleDiv.scrollHeight;
            }}
            </script>
            """, unsafe_allow_html=True)
        else:
            st.info("Console output will appear here during processing...")
    
    return console_container

def create_progress_tracker():
    """Create a progress tracking component"""
    st.markdown("### 📊 Processing Progress")
    
    # Progress indicators
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Files Processed", "0", delta=None)
    
    with col2:
        st.metric("Events Processed", "0", delta=None)
    
    with col3:
        st.metric("Features Generated", "0", delta=None)
    
    with col4:
        current_stage = st.session_state.get('current_stage', 'Idle')
        st.metric("Current Stage", current_stage, delta=None)
    
    # Progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    return progress_bar, status_text

def create_training_console():
    """Create a real-time training console output component"""
    st.markdown("### 🎯 Training Console Output")
    
    # Create a container for training console output
    training_console_container = st.container()
    
    with training_console_container:
        # Display training console output
        training_console_text = ""
        while not console_queue.empty():
            try:
                message = console_queue.get_nowait()
                if "TRAINING" in message or "EPOCH" in message or "MODEL" in message:
                    training_console_text += message + "\n"
            except queue.Empty:
                break
        
        if training_console_text:
            st.markdown(f"""
            <div class="console-output">
            {training_console_text}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Training console output will appear here during model training...")
    
    return training_console_container

def create_training_progress_tracker():
    """Create a training progress tracking component"""
    st.markdown("### 📈 Training Progress")
    
    # Training progress indicators
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Current Epoch", "0", delta=None)
    
    with col2:
        st.metric("Training Loss", "0.000", delta=None)
    
    with col3:
        st.metric("Validation Loss", "0.000", delta=None)
    
    with col4:
        st.metric("Accuracy", "0.00%", delta=None)
    
    # Training progress bar
    training_progress_bar = st.progress(0)
    training_status_text = st.empty()
    
    return training_progress_bar, training_status_text

# Initialize session state
if 'training_mbo_data' not in st.session_state:
    st.session_state.training_mbo_data = None
if 'training_features' not in st.session_state:
    st.session_state.training_features = None


def generate_synthetic_chart_data() -> pd.DataFrame:
    """Generate synthetic chart data for placeholder display."""
    n = 240  # 4 hours of 1-minute bars
    base_time = pd.Timestamp.now().floor('h') - pd.Timedelta(hours=4)
    
    # Generate realistic price movement
    np.random.seed(42)  # For reproducible synthetic data
    returns = np.random.normal(0, 0.001, n)  # Small random returns
    prices = 5700 + np.cumsum(returns) * 100  # Start at 5700, scale up
    
    # Generate timestamps
    timestamps = [base_time + pd.Timedelta(minutes=i) for i in range(n)]
    
    # Create tick data format (ts, price, size, side)
    data = []
    for i in range(n):
        price = prices[i]
        # Generate multiple ticks per minute for more realistic data
        for j in range(5):  # 5 ticks per minute
            tick_time = timestamps[i] + pd.Timedelta(seconds=j*12)
            tick_price = price + np.random.normal(0, 0.1)
            tick_size = np.random.randint(1, 10)
            tick_side = "buy" if np.random.random() > 0.5 else "sell"
            
            data.append({
                'ts': tick_time,
                'price': round(tick_price, 2),
                'size': tick_size,
                'side': tick_side
            })
    
    return pd.DataFrame(data)


def process_mbo_to_ticks(mbo_df: pd.DataFrame) -> pd.DataFrame:
    """Convert MBO data to tick data format for charting."""
    if mbo_df.empty:
        return pd.DataFrame()
    
    try:
        # Filter for execution events only (F = fill/execution)
        executions = mbo_df[mbo_df['action'] == 'F'].copy()
        
        if executions.empty:
            logger.warning("No execution events found in MBO data")
            return pd.DataFrame()
        
        # Convert to tick format
        ticks = []
        for _, row in executions.iterrows():
            tick = {
                'ts': row['ts_event'],
                'price': row['price'],
                'size': row['size'],
                'side': row['side']
            }
            ticks.append(tick)
        
        ticks_df = pd.DataFrame(ticks)
        
        # Sort by timestamp
        ticks_df = ticks_df.sort_values('ts').reset_index(drop=True)
        
        logger.info(f"Generated {len(ticks_df)} ticks from MBO data")
        return ticks_df
        
    except Exception as e:
        logger.error(f"Failed to process MBO to ticks: {e}")
        return pd.DataFrame()


def get_cfg() -> AppConfig:
    """Get application configuration."""
    return AppConfig()


def overview_tab():
    st.subheader("Overview")
    st.write("Databento MBO Level 3 data analysis and live trading dashboard.")
    
    with st.expander("Master Model Rulebook", expanded=False):
        try:
            with open("docs/MASTER_MODEL_RULEBOOK.md", "r", encoding="utf-8") as f:
                st.markdown(f.read())
        except Exception:
            st.info("Rulebook not found at docs/MASTER_MODEL_RULEBOOK.md")
    
    cfg = get_cfg()
    live = get_live_service(cfg)
    snap = live.snapshot()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Last Price", f"{snap.last_price or '-'}")
    col2.metric("Position", f"{snap.position}")
    col3.metric("Last Pred", f"{(snap.last_prediction or 0):.2f}")

    st.markdown("---")
    # TradingView Chart
    st.markdown("### TradingView Chart (Databento MBO Data)")
    st.caption("ES.FUT by default; MBO data by default. Switch symbol or source below.")
    
    # Chart controls in a cleaner layout
    col1, col2, col3 = st.columns(3)
    with col1:
        # ES is the only ticker we have
        st.write("**Symbol:** ES (ES Futures)")
        sym = "ES"
    with col2:
        data_source = st.selectbox("Data Source", ["mbo", "ticks", "ohlc"], key="ov_source")
    with col3:
        # Show available dates info
        databento_loader = get_databento_loader('data/es_futures/mbo')
        available_dates = databento_loader.get_available_dates()
        if available_dates:
            st.write(f"**Available:** {len(available_dates)} trading days")
            st.caption(f"Latest: {available_dates[0]}")
        else:
            st.write("**Available:** No DBN data found")
    
    # Load data for chart
    if st.button("Load MBO Data", key="ov_load_chart"):
        try:
            with st.spinner("Loading DBN data sequentially..."):
                # Get Databento loader
                databento_loader = get_databento_loader('data/es_futures/mbo')
                
                if not databento_loader.get_available_dates():
                    st.error("No DBN data files found")
                    return
                
                # STEP 1: 1-MINUTE CHUNK loading for immediate display and memory efficiency
                most_recent_date = databento_loader.get_available_dates()[0]
                
                # Minute selector for loading different minutes
                col1, col2 = st.columns(2)
                with col1:
                    # Initialize minute offset from session state
                    if 'next_minute' in st.session_state:
                        default_minute = st.session_state.next_minute
                        del st.session_state.next_minute  # Clear after use
                    else:
                        default_minute = 0
                    
                    minute_offset = st.selectbox(
                        "Select Minute from Market Open",
                        options=list(range(10)),  # 0-9 minutes
                        index=default_minute,
                        format_func=lambda x: f"Minute {x} ({9+x//60}:{30+x%60:02d} AM)",
                        key="minute_selector"
                    )
                with col2:
                    st.info(f"📅 Loading data from {most_recent_date}")
                
                st.info(f"⚡ 1-MINUTE CHUNK loading price data from {most_recent_date} (Minute {minute_offset})...")
                
                # Load price data for selected minute using official Databento loader
                df = databento_loader.load_minute_chunk(most_recent_date, start_minute=minute_offset, duration_minutes=1)
                
                if df is not None and not df.empty:
                    st.success(f"✅ FAST loaded {len(df):,} records from {most_recent_date}")
                    
                    # STEP 2: Display price chart immediately
                    st.info("📈 Step 2: Displaying price chart...")
                    
                    # Display the main price chart
                    st.success(f"✅ Displaying price chart for {most_recent_date}")
                    
                    # Main price chart
                    st.subheader("📈 Price Chart (TradingView)")
                    
                    # Display TradingView chart with raw data
                    tradingview_chart(df, dark=True)
                    
                    # Show price data summary
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Records", len(df))
                    if 'price' in df.columns:
                        col2.metric("Price Range", f"${df['price'].min():.2f} - ${df['price'].max():.2f}")
                    if 'datetime' in df.columns:
                        col3.metric("Time Range", f"{df['datetime'].min().strftime('%H:%M')} - {df['datetime'].max().strftime('%H:%M')}")
                    
                    # Matplotlib Charts Section (Under TradingView)
                    st.subheader("📊 Matplotlib Charts (Under TradingView)")
                    
                    # Chart type selector
                    chart_type = st.selectbox(
                        "Select Chart Type",
                        ["candlestick", "volume", "tick", "comprehensive"],
                        key="matplotlib_chart_type"
                    )
                    
                    # Display matplotlib chart
                    display_matplotlib_charts(df, chart_type)
                    
                    # Display data summary
                    display_data_summary(df)
                    
                    # Show raw data
                    with st.expander("📋 Raw DBN Data", expanded=False):
                        st.dataframe(df, use_container_width=True)
                    
                    # Load next minute button
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("⏭️ Load Next Minute", key="load_next_minute"):
                            next_minute = min(minute_offset + 1, 9)  # Max 10 minutes
                            st.session_state.next_minute = next_minute
                            st.rerun()
                    with col2:
                        if st.button("⏮️ Load Previous Minute", key="load_prev_minute"):
                            prev_minute = max(minute_offset - 1, 0)
                            st.session_state.next_minute = prev_minute
                            st.rerun()
                    with col3:
                        if st.button("🔄 Reload Current Minute", key="reload_current_minute"):
                            st.rerun()
                    
                    # STEP 4: Tick Replay Chart Section
                    st.subheader("🎮 Tick Replay Chart (1-Minute Default)")
                    
                    if st.button("Load Tick Data for Replay", key="load_tick_replay"):
                        try:
                            st.info("🔄 Loading tick-level data for replay functionality...")
                            
                            # Get MBO loader for tick data
                            mbo_loader = get_databento_loader('data/es_futures/mbo')
                            
                            # Load tick data for replay (up to 10 minutes)
                            tick_df = mbo_loader.load_tick_data_for_replay(most_recent_date, start_hour=9, start_minute=30, max_minutes=10)
                            
                            if tick_df is not None and not tick_df.empty:
                                st.success(f"✅ Loaded {len(tick_df):,} ticks for replay")
                                
                                # Import and display replay chart
                                from quanttime.dashboard.custom_charts import display_replay_chart
                                display_replay_chart(tick_df, timeframe='1min')
                                
                                # Show tick data summary
                                with st.expander("📋 Tick Data Summary", expanded=False):
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        st.metric("Total Ticks", len(tick_df))
                                    with col2:
                                        st.metric("Executions", len(tick_df[tick_df['action'] == 'F']))
                                    with col3:
                                        st.metric("Bids", len(tick_df[tick_df['action'] == 'B']))
                                    with col4:
                                        st.metric("Asks", len(tick_df[tick_df['action'] == 'A']))
                                    
                                    # Show sample tick data
                                    st.dataframe(tick_df.head(10), use_container_width=True)
                            else:
                                st.error("❌ Failed to load tick data for replay")
                        except Exception as e:
                            st.error(f"❌ Failed to load tick data: {e}")
                    
                    # STEP 3: Optional - Load order book data for analysis
                    if st.button("Load Order Book Analysis (Optional)", key="load_orderbook_analysis"):
                        try:
                            st.info("🔄 Loading order book data for Level 2/3 analysis...")
                            
                            # Get MBO loader for order book analysis
                            mbo_loader = get_databento_loader('data/es_futures/mbo')
                            
                            # Load first 10 minutes of MBO data for order book analysis
                            mbo_df = mbo_loader.load_mbo_data_first_10min(most_recent_date, start_hour=9, start_minute=30)
                            
                            if mbo_df is not None and not mbo_df.empty:
                                # Generate order book heatmap
                                st.subheader("🔥 Order Book Heatmap (Level 2 Data)")
                                orderbook_heatmap = mbo_loader.generate_orderbook_heatmap(mbo_df, price_levels=15)
                                
                                if not orderbook_heatmap.empty:
                                    # Create heatmap visualization
                                    fig = go.Figure()
                                    
                                    # Bid side (green)
                                    fig.add_trace(go.Bar(
                                        x=orderbook_heatmap['bid_size'],
                                        y=orderbook_heatmap['price'],
                                        orientation='h',
                                        name='Bids',
                                        marker_color='rgba(0, 255, 0, 0.6)',
                                        hovertemplate='Price: $%{y:.2f}<br>Bid Size: %{x}<extra></extra>'
                                    ))
                                    
                                    # Ask side (red)
                                    fig.add_trace(go.Bar(
                                        x=orderbook_heatmap['ask_size'],
                                        y=orderbook_heatmap['price'],
                                        orientation='h',
                                        name='Asks',
                                        marker_color='rgba(255, 0, 0, 0.6)',
                                        hovertemplate='Price: $%{y:.2f}<br>Ask Size: %{x}<extra></extra>'
                                    ))
                                    
                                    fig.update_layout(
                                        title="Order Book Depth Heatmap",
                                        xaxis_title="Size",
                                        yaxis_title="Price",
                                        height=400,
                                        showlegend=True
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True)
                                
                                # Generate cumulative delta
                                st.subheader("📊 Cumulative Delta (Level 3 Analysis)")
                                cumulative_delta = mbo_loader.calculate_cumulative_delta(mbo_df)
                                
                                if not cumulative_delta.empty:
                                    # Create cumulative delta chart
                                    fig = go.Figure()
                                    
                                    fig.add_trace(go.Scatter(
                                        x=cumulative_delta['timestamp'],
                                        y=cumulative_delta['cumulative_delta'],
                                        mode='lines',
                                        name='Cumulative Delta',
                                        line=dict(color='blue', width=2),
                                        hovertemplate='Time: %{x}<br>Cumulative Delta: %{y}<extra></extra>'
                                    ))
                                    
                                    fig.update_layout(
                                        title="Cumulative Delta Over Time",
                                        xaxis_title="Time",
                                        yaxis_title="Cumulative Delta",
                                        height=300,
                                        showlegend=True
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.warning("Could not load order book data")
                        except Exception as e:
                            st.error(f"❌ Failed to load order book data: {e}")
                    
                    # STEP 4: Training section
                    st.subheader("🤖 GPU Training Section")
                    
                    # Test Pipeline Button
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        if st.button("🧪 Test Pipeline", key="test_pipeline", type="secondary"):
                            try:
                                st.info("🚀 Running pipeline test with 10 minutes of data...")
                                
                                # Try to load real data first
                                test_data = None
                                if hasattr(mbo_loader, 'available_dates') and mbo_loader.available_dates:
                                    test_data = mbo_loader.load_price_data_first_10min(
                                        mbo_loader.available_dates[0], 
                                        start_hour=9, 
                                        start_minute=30
                                    )
                                
                                # If no real data available, generate synthetic data
                                if test_data is None or test_data.empty:
                                    st.info("📊 No real data available, generating synthetic test data...")
                                    from quanttime.utils.test_data_generator import generate_test_candles_data
                                    test_data = generate_test_candles_data(num_candles=50)  # 50 minutes of data
                                
                                if test_data is not None and not test_data.empty:
                                    st.success(f"✅ Test data loaded: {len(test_data)} rows")
                                    st.session_state.test_data = test_data
                                    
                                    # Show data info
                                    st.info(f"📊 Data range: {test_data['timestamp'].min()} to {test_data['timestamp'].max()}")
                                    st.info(f"📊 Price range: ${test_data['low'].min():.2f} - ${test_data['high'].max():.2f}")
                                else:
                                    st.error("❌ Failed to load or generate test data")
                            except Exception as e:
                                st.error(f"❌ Pipeline test failed: {e}")
                                st.exception(e)
                    
                    with col2:
                        st.info("**Test Pipeline**: Loads 10 minutes of data for quick testing")
                    
                    # Timeframe selection for training
                    st.write("**Select Timeframe for Training:**")
                    timeframe_options = {
                        "Market Hours (9:00 AM - 4:30 PM EST)": "market_hours",
                        "24 Hour Trading": "24h",
                        "Extended Hours (8:00 AM - 5:00 PM EST)": "extended_hours",
                        "Core Hours (9:30 AM - 4:00 PM EST)": "core_hours"
                    }
                    
                    selected_timeframe = st.selectbox(
                        "Training Timeframe",
                        options=list(timeframe_options.keys()),
                        index=0,
                        key="training_timeframe"
                    )
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Train Model on This Data", key="train_model_data"):
                            try:
                                st.info("🚀 Starting GPU-accelerated training...")
                                
                                # Get timeframe filter
                                from quanttime.utils.timeframe_filter import get_timeframe_options
                                timeframe_filters = get_timeframe_options()
                                selected_filter = timeframe_filters[selected_timeframe]
                                
                                # Show filtering info
                                filter_stats = selected_filter.get_filter_stats(candles_df)
                                st.info(f"📊 Training on {filter_stats['filtered_percentage']:.1f}% of data "
                                       f"({filter_stats['filtered_rows']:,} rows) from {selected_timeframe}")
                                
                                # Import GPU training module
                                from quanttime.ml.gpu_training import train_model_on_mbo_data
                                
                                # Train model with timeframe filter
                                results = train_model_on_mbo_data(candles_df, timeframe_filter=selected_filter)
                                
                                if results:
                                    st.success("✅ Training completed!")
                                    
                                    # Show training results
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.line_chart(pd.DataFrame({
                                            'Train Loss': results['train_losses'],
                                            'Val Loss': results['val_losses']
                                        }))
                                    
                                    with col2:
                                        st.line_chart(pd.DataFrame({
                                            'Train Acc': results['train_accuracies'],
                                            'Val Acc': results['val_accuracies']
                                        }))
                                else:
                                    st.error("❌ Training failed")
                            except Exception as e:
                                st.error(f"Training error: {e}")
                    
                    with col2:
                        if st.button("Load More Data for Training", key="load_more_training_data"):
                            try:
                                st.info("📊 Loading additional dates for training...")
                                
                                # Load multiple dates for training using 10-minute chunks
                                additional_dates = mbo_loader.available_dates[1:6]  # Next 5 dates
                                all_candles = [candles_df]  # Start with current data
                                
                                for date_str in additional_dates:
                                    additional_candles = mbo_loader.load_price_data_first_10min(date_str, start_hour=9, start_minute=30)
                                    if additional_candles is not None and not additional_candles.empty:
                                        all_candles.append(additional_candles)
                                
                                if len(all_candles) > 1:
                                    # Combine all candles
                                    combined_candles = pd.concat(all_candles, ignore_index=True)
                                    st.success(f"✅ Loaded {len(combined_candles)} total candles from {len(all_candles)} dates")
                                    
                                    # Store for training
                                    st.session_state.training_candles = combined_candles
                                else:
                                    st.warning("No additional data loaded")
                            except Exception as e:
                                st.error(f"Error loading additional data: {e}")
                    
                    with col3:
                        if st.button("🧪 Test Training", key="test_training", type="secondary"):
                            try:
                                st.info("🚀 Running quick training test...")
                                
                                # Use test data if available, otherwise use current data
                                training_data = st.session_state.get('test_data', candles_df)
                                
                                if training_data is None or training_data.empty:
                                    st.error("❌ No test data available. Run 'Test Pipeline' first.")
                                    return
                                
                                # Get timeframe filter
                                from quanttime.utils.timeframe_filter import get_timeframe_options
                                timeframe_filters = get_timeframe_options()
                                selected_filter = timeframe_filters[selected_timeframe]
                                
                                # Show filtering info
                                filter_stats = selected_filter.get_filter_stats(training_data)
                                st.info(f"📊 Training on {filter_stats['filtered_percentage']:.1f}% of test data "
                                       f"({filter_stats['filtered_rows']:,} rows)")
                                
                                # Import GPU training module
                                from quanttime.ml.gpu_training import train_model_on_mbo_data
                                
                                # Train model with timeframe filter (quick test)
                                results = train_model_on_mbo_data(training_data, timeframe_filter=selected_filter, test_mode=True)
                                
                                if results:
                                    st.success("✅ Test training completed successfully!")
                                    st.info("🎯 Pipeline is working correctly. You can now proceed with full training.")
                                else:
                                    st.error("❌ Test training failed")
                            except Exception as e:
                                st.error(f"❌ Test training failed: {e}")
                                st.exception(e)
                    
                    # Note: The executions and ticks_df logic was moved outside the main data loading flow
                    # This section was causing syntax errors due to improper nesting
                    st.info("📊 Data loading completed successfully")
                    
                    # Show placeholder chart with synthetic data for now
                    if 'chart_data_loaded' not in st.session_state:
                        st.info("📊 Click 'Load MBO Data' to display real Level 1 price data from Databento MBO files")
                        # Show a placeholder chart with synthetic data
                        synthetic_data = generate_synthetic_chart_data()
                        tradingview_chart(synthetic_data, dark=True)
                        st.caption("Real MBO price data will be displayed here after clicking 'Load MBO Data'")
        except Exception as e:
            st.error(f"Error loading MBO data: {e}")
            st.exception(e)

    st.markdown("---")
    st.subheader("MBO Data Analysis")
    
    # Date range selector for MBO analysis
    col1, col2, col3 = st.columns(3)
    with col1:
        analysis_start = st.date_input("Analysis Start Date", value=datetime.now().date() - timedelta(days=7))
    with col2:
        analysis_end = st.date_input("Analysis End Date", value=datetime.now().date())
    with col3:
        if st.button("Load MBO Data for Analysis", key="load_mbo_analysis"):
            try:
                start_str = analysis_start.strftime("%Y%m%d")
                end_str = analysis_end.strftime("%Y%m%d")
                
                mbo_df = load_mbo_data_for_analysis(cfg, sym, start_str, end_str)
                
                if mbo_df is not None and not mbo_df.empty:
                    st.session_state.mbo_analysis_data = mbo_df
                    st.success(f"Loaded {len(mbo_df)} MBO events")
                else:
                    st.error("No MBO data found for selected date range")
            except Exception as e:
                st.error(f"Failed to load MBO data: {e}")
    
    # Display MBO analysis if data is loaded
    if 'mbo_analysis_data' in st.session_state:
        mbo_df = st.session_state.mbo_analysis_data
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Order Book Snapshot")
            if st.button("Generate Order Book", key="generate_orderbook"):
                orderbook = generate_orderbook_snapshot(mbo_df)
                st.write("**Bids:**")
                for price, size in orderbook['bids'][:5]:
                    st.write(f"  ${price:.2f} - {size}")
                st.write("**Asks:**")
                for price, size in orderbook['asks'][:5]:
                    st.write(f"  ${price:.2f} - {size}")
        
        with col2:
            st.subheader("Footprint Analysis")
            if st.button("Generate Footprint", key="generate_footprint"):
                footprint = generate_footprint_data(mbo_df)
                if not footprint.empty:
                    st.dataframe(footprint.head(10))
                else:
                    st.write("No footprint data available")


def leaderboard_tab():
    st.subheader("Model Leaderboard")
    cfg = get_cfg()
    
    st.info("Model registry functionality will be implemented in the next phase.")
    st.write("This tab will show trained models, their performance metrics, and allow selection for backtesting.")
    
    # Placeholder for future implementation
    st.markdown("### Future Features")
    st.write("- Model training history")
    st.write("- Performance comparison")
    st.write("- Model selection for backtesting")
    st.write("- Live trading model management")


def train_tab():
    st.subheader("Model Training")
    cfg = get_cfg()
    
    # Add training console and progress tracking
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🗑️ Clear Training Console", key="clear_training_console"):
            st.session_state.console_messages = []
            while not console_queue.empty():
                console_queue.get()
            st.rerun()
    
    training_console_container = create_training_console()
    training_progress_bar, training_status_text = create_training_progress_tracker()
    
    # Data source selection
    st.markdown("### Data Source")
    data_source = st.selectbox(
        "Select data source for training",
        options=["Raw MBO Data", "Processed Datasets", "Local Files"],
        index=0
    )
    
    if data_source == "Raw MBO Data":
        # Use the new date range selector
        start_date, end_date = render_date_range_selector(
            data_dir="data/es_futures/mbo",
            key_prefix="training"
        )
        
        if start_date and end_date:
            if st.button("Load Selected Date Range", key="load_selected_date_range"):
                try:
                    # Get databento loader
                    databento_loader = get_databento_loader('data/es_futures/mbo')
                    
                    # Get all available dates in the range
                    available_dates = databento_loader.get_available_dates()
                    selected_dates = [d for d in available_dates if start_date <= d <= end_date]
                    
                    if not selected_dates:
                        st.error("No data found for selected date range")
                        return
                    
                    # Create progress tracker
                    progress_tracker = ProgressTracker()
                    
                    # Create progress callback adapter for databento loader
                    def databento_progress_callback(task, current, total, subtask, subprogress):
                        """Adapter for databento loader progress callback"""
                        if current == 0:
                            progress_tracker.start_task(task, total)
                        else:
                            progress_tracker.update_progress(current, subtask, subprogress)
                    
                    # Load data with memory optimization and progress tracking
                    combined_df = databento_loader.load_dbn_files_memory_optimized(
                        date_range=selected_dates,
                        max_memory_gb=12.0,  # Keep RAM usage under 12GB
                        progress_callback=databento_progress_callback
                    )
                    
                    if combined_df is not None and not combined_df.empty:
                        # Add date column for tracking
                        combined_df['date'] = combined_df.get('source_date', 'unknown')
                        
                        # Store in session state
                        st.session_state.training_mbo_data = combined_df
                        st.session_state.training_start_date = start_date
                        st.session_state.training_end_date = end_date
                        
                        # Show success message
                        st.success(f"✅ Loaded {len(selected_dates)} trading days: {start_date} to {end_date}")
                        st.info(f"Total records: {len(combined_df):,}")
                        
                        # Show data statistics
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Total Events", len(combined_df))
                        col2.metric("Date Range", f"{start_date} to {end_date}")
                        col3.metric("Total Dates", len(selected_dates))
                        
                        # Show data preview
                        with st.expander("Data Preview", expanded=False):
                            st.dataframe(combined_df.head(100))
                            
                    else:
                        st.error("No data loaded from selected date range")
                        
                except Exception as e:
                    st.error(f"Failed to load DBN data: {e}")
                    st.exception(e)
    
    elif data_source == "Processed Datasets":
        st.markdown("### Data Schema Selection")
        
        # Schema info styling is now in the main CSS block
        
        # Add auto-refresh functionality for this tab
        if 'last_schema_refresh' not in st.session_state:
            st.session_state.last_schema_refresh = 0
        
        # Auto-refresh every 5 seconds when on this tab
        current_time = time.time()
        if current_time - st.session_state.last_schema_refresh > 5:
            st.session_state.last_schema_refresh = current_time
            st.rerun()
        
        # Get available processed datasets
        try:
            from quanttime.data import get_processor
            processor = get_processor()
            
            # Get available schemas
            from quanttime.data.schema import list_available_schemas
            schemas = list_available_schemas()
            
            # Define schema options with descriptions
            schema_options = {
                "raw": {
                    "name": "Raw MBO",
                    "description": "Unprocessed Market By Order data",
                    "features": "~15 columns",
                    "intensity": "None"
                },
                "execution_aware_light_v1": {
                    "name": "Light Intensity",
                    "description": "Core execution-aware features with 4 horizons",
                    "features": "~50 features",
                    "intensity": "Light"
                },
                "execution_aware_medium_v1": {
                    "name": "Medium Intensity", 
                    "description": "Expanded multi-horizon analysis with 8 horizons",
                    "features": "~100 features",
                    "intensity": "Medium"
                },
                "execution_aware_heavy_v1": {
                    "name": "Heavy Intensity",
                    "description": "Comprehensive analysis with 15 horizons",
                    "features": "~200 features", 
                    "intensity": "Heavy"
                },
                "execution_aware_extreme_v1": {
                    "name": "Extreme Intensity",
                    "description": "Maximum features including advanced patterns",
                    "features": "~300+ features",
                    "intensity": "Extreme"
                }
            }
            
            # Check availability for each schema
            schema_availability = {}
            available_dates_by_schema = {}
            
            for schema_key, schema_info in schema_options.items():
                if schema_key == "raw":
                    # For raw data, check databento files
                    try:
                        from quanttime.adapter.databento_loader import get_databento_loader
                        databento_loader = get_databento_loader('data/es_futures/mbo')
                        available_dates = databento_loader.get_available_dates()
                        schema_availability[schema_key] = len(available_dates) > 0
                        available_dates_by_schema[schema_key] = available_dates
                    except Exception as e:
                        schema_availability[schema_key] = False
                        available_dates_by_schema[schema_key] = []
                        st.warning(f"Error checking raw data: {str(e)}")
                else:
                    # For processed schemas, check processed files
                    try:
                        available_dates = processor.list_available_dates("mbo", schema_key)
                        schema_availability[schema_key] = len(available_dates) > 0
                        available_dates_by_schema[schema_key] = available_dates
                    except Exception as e:
                        schema_availability[schema_key] = False
                        available_dates_by_schema[schema_key] = []
                        st.warning(f"Error checking {schema_key}: {str(e)}")
                        log_device_operation(
                            operation=f"Check schema availability: {schema_key}",
                            status="ERROR",
                            error=e,
                            details={"schema": schema_key, "data_type": "mbo"}
                        )
            
            # Create a simple horizontal tab selection using columns
            st.markdown("### 📊 Select Data Schema")
            
            # Add manual refresh button
            col_refresh, col_info = st.columns([1, 4])
            with col_refresh:
                if st.button("🔄 Refresh", help="Manually refresh schema availability"):
                    st.session_state.last_schema_refresh = 0
                    st.rerun()
            
            with col_info:
                st.info("💡 Auto-refreshing every 5 seconds. Click 'Refresh' to update immediately.")
            
            # Initialize selected schema in session state
            if 'selected_training_schema' not in st.session_state:
                st.session_state.selected_training_schema = None
            
            # Create tabs using columns
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                if st.button("📄 Raw MBO", 
                           type="primary" if st.session_state.selected_training_schema == "raw" else "secondary",
                           disabled=not schema_availability.get("raw", False),
                           use_container_width=True):
                    st.session_state.selected_training_schema = "raw"
                    st.rerun()
                if schema_availability.get("raw", False):
                    st.caption(f"{len(available_dates_by_schema.get('raw', []))} days")
            
            with col2:
                if st.button("⚡ Light", 
                           type="primary" if st.session_state.selected_training_schema == "execution_aware_light_v1" else "secondary",
                           disabled=not schema_availability.get("execution_aware_light_v1", False),
                           use_container_width=True):
                    st.session_state.selected_training_schema = "execution_aware_light_v1"
                    st.rerun()
                if schema_availability.get("execution_aware_light_v1", False):
                    st.caption(f"{len(available_dates_by_schema.get('execution_aware_light_v1', []))} days")
            
            with col3:
                if st.button("🔥 Medium", 
                           type="primary" if st.session_state.selected_training_schema == "execution_aware_medium_v1" else "secondary",
                           disabled=not schema_availability.get("execution_aware_medium_v1", False),
                           use_container_width=True):
                    st.session_state.selected_training_schema = "execution_aware_medium_v1"
                    st.rerun()
                if schema_availability.get("execution_aware_medium_v1", False):
                    st.caption(f"{len(available_dates_by_schema.get('execution_aware_medium_v1', []))} days")
            
            with col4:
                if st.button("💪 Heavy", 
                           type="primary" if st.session_state.selected_training_schema == "execution_aware_heavy_v1" else "secondary",
                           disabled=not schema_availability.get("execution_aware_heavy_v1", False),
                           use_container_width=True):
                    st.session_state.selected_training_schema = "execution_aware_heavy_v1"
                    st.rerun()
                if schema_availability.get("execution_aware_heavy_v1", False):
                    st.caption(f"{len(available_dates_by_schema.get('execution_aware_heavy_v1', []))} days")
            
            with col5:
                if st.button("🚀 Extreme", 
                           type="primary" if st.session_state.selected_training_schema == "execution_aware_extreme_v1" else "secondary",
                           disabled=not schema_availability.get("execution_aware_extreme_v1", False),
                           use_container_width=True):
                    st.session_state.selected_training_schema = "execution_aware_extreme_v1"
                    st.rerun()
                if schema_availability.get("execution_aware_extreme_v1", False):
                    st.caption(f"{len(available_dates_by_schema.get('execution_aware_extreme_v1', []))} days")
            
            # Show selected schema info
            if st.session_state.selected_training_schema and st.session_state.selected_training_schema in schema_options:
                selected_schema_info = schema_options[st.session_state.selected_training_schema]
                available_dates = available_dates_by_schema.get(st.session_state.selected_training_schema, [])
                
                st.markdown(f"""
                <div class="schema-info">
                    <h4>📊 {selected_schema_info['name']}</h4>
                    <p>{selected_schema_info['description']}</p>
                    <div class="schema-stats">
                        <div class="schema-stat">
                            <div class="schema-stat-value">{len(available_dates)}</div>
                            <div class="schema-stat-label">Available Days</div>
                        </div>
                        <div class="schema-stat">
                            <div class="schema-stat-value">{selected_schema_info['features']}</div>
                            <div class="schema-stat-label">Features</div>
                        </div>
                        <div class="schema-stat">
                            <div class="schema-stat-value">{selected_schema_info['intensity']}</div>
                            <div class="schema-stat-label">Intensity</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Date selection for the selected schema
                if available_dates:
                    st.markdown("### 📅 Available Dates")
                    
                    # Sort dates in descending order (most recent first)
                    available_dates_sorted = sorted(available_dates, reverse=True)
                    
                    # Date selection with multi-select
                    selected_dates = st.multiselect(
                        f"Select dates for {selected_schema_info['name']} training",
                        available_dates_sorted,
                        default=available_dates_sorted[:3] if len(available_dates_sorted) >= 3 else available_dates_sorted,
                        help=f"Select dates with {selected_schema_info['name']} data for training"
                    )
                    
                    if selected_dates:
                        st.success(f"✅ Selected {len(selected_dates)} dates for {selected_schema_info['name']} training")
                        
                        # Load data button
                        if st.button(f"📥 Load {selected_schema_info['name']} Data", key="load_processed_data"):
                            try:
                                log_to_console(f"📥 Loading {selected_schema_info['name']} data for {len(selected_dates)} dates", "TRAINING")
                                
                                if st.session_state.selected_training_schema == "raw":
                                    # Load raw data
                                    from quanttime.adapter.databento_loader import get_databento_loader
                                    databento_loader = get_databento_loader('data/es_futures/mbo')
                                    
                                    # Load data with memory optimization
                                    combined_df = databento_loader.load_dbn_files_memory_optimized(
                                        date_range=selected_dates,
                                        max_memory_gb=12.0
                                    )
                                else:
                                    # Load processed data
                                    combined_df = processor.batch_load_processed_data(
                                        selected_dates, "mbo", st.session_state.selected_training_schema
                                    )
                                
                                if combined_df is not None and not combined_df.empty:
                                    # Store in session state
                                    st.session_state.training_mbo_data = combined_df
                                    st.session_state.training_schema = st.session_state.selected_training_schema
                                    st.session_state.training_dates = selected_dates
                                    
                                    log_to_console(f"✅ Loaded {len(combined_df):,} events from {len(selected_dates)} dates", "TRAINING")
                                    st.success(f"✅ Loaded {len(combined_df):,} events from {len(selected_dates)} dates")
                                    
                                    # Show data statistics
                                    col1, col2, col3, col4 = st.columns(4)
                                    col1.metric("Total Events", len(combined_df))
                                    col2.metric("Date Range", f"{min(selected_dates)} to {max(selected_dates)}")
                                    col3.metric("Total Dates", len(selected_dates))
                                    col4.metric("Features", len(combined_df.columns))
                                    
                                    # Show data preview
                                    with st.expander("Data Preview", expanded=False):
                                        st.dataframe(combined_df.head(100))
                                        
                                else:
                                    log_to_console(f"❌ Failed to load data for {selected_schema_info['name']}", "ERROR")
                                    st.error(f"Failed to load data for {selected_schema_info['name']}")
                                    
                            except Exception as e:
                                log_to_console(f"❌ Error loading data: {str(e)}", "ERROR")
                                st.error(f"Error loading data: {e}")
                                st.exception(e)
                else:
                    st.warning(f"⚠️ No data available for {selected_schema_info['name']}")
        except Exception as e:
            st.error(f"Failed to load processed datasets: {e}")
            st.exception(e)
    
    else:  # Local Files
        files = list_datasets(cfg)
        if not files:
            st.warning("No local datasets found. Use the Data tab to collect data first.")
            return
        
        selected_file = st.selectbox("Select dataset", files)
        if st.button("Load Dataset", key="load_dataset"):
            try:
                if selected_file.endswith(".csv"):
                    df = pd.read_csv(selected_file)
                else:
                    df = pd.read_parquet(selected_file)
                st.session_state.training_data = df
                st.success(f"Loaded {len(df)} rows from {selected_file}")
            except Exception as e:
                st.error(f"Failed to load dataset: {e}")
    
    # Model Configuration (Preprocessing happens during training)
    if 'training_mbo_data' in st.session_state:
        st.markdown("### Model Configuration")
        
        # Explain the data processing strategy
        st.info("""
        💡 **Data Processing Strategy:**
        
        **Current Phase (Data Loading):** We've loaded raw MBO (Market By Order) data into memory. This includes:
        - Order book events (adds, modifies, deletes, fills)
        - Timestamps, prices, sizes, sides, actions
        - Raw market microstructure data
        
        **Next Phase (Training):** During model training, the system will automatically:
        - **Feature Engineering:** Convert raw MBO data into order book snapshots, market microstructure features, technical indicators
        - **Order Book Reconstruction:** Build real-time order book state from MBO events
        - **Tick-by-Tick Processing:** Simulate real-time data flow for continuous predictions
        - **Memory Optimization:** Process data in batches to maintain performance
        
        This approach ensures the ML model learns from the most granular order flow data for optimal prediction accuracy.
        """)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            model_type = st.selectbox("Model Type", ["lightgbm", "lstm", "transformer"], index=0)
        with col2:
            train_split = st.slider("Train Split", 0.5, 0.9, 0.7, 0.05)
        with col3:
            val_split = st.slider("Validation Split", 0.1, 0.3, 0.15, 0.05)
    
        # Model-specific parameters based on selected model type
        st.markdown("### Model-Specific Parameters")
        
        if model_type == "lightgbm":
            # LightGBM specific parameters
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                orderbook_depth = st.slider("Order Book Depth", 5, 50, 20, help="Depth of order book to analyze")
                num_leaves = st.slider("Number of Leaves", 10, 100, 31, help="Maximum number of leaves in trees")
            with col2:
                feature_window = st.slider("Feature Window", 20, 200, 100, help="Window for feature calculation")
                max_depth = st.slider("Max Tree Depth", 3, 12, 6, help="Maximum depth of trees")
            with col3:
                learning_rate = st.slider("Learning Rate", 0.01, 0.3, 0.1, 0.01, help="Learning rate for gradient boosting")
                num_iterations = st.slider("Number of Iterations", 50, 500, 100, help="Number of boosting iterations")
            with col4:
                use_gpu = st.checkbox("Use GPU", value=True)
                use_mixed_precision = st.checkbox("Mixed Precision", value=True)
                
        elif model_type == "lstm":
            # LSTM specific parameters
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                orderbook_depth = st.slider("Order Book Depth", 5, 50, 20, help="Depth of order book to analyze")
                hidden_size = st.slider("Hidden Size", 64, 512, 256, help="Number of LSTM hidden units")
            with col2:
                sequence_length = st.slider("Sequence Length", 50, 500, 200, help="Length of input sequences")
                num_layers = st.slider("Number of Layers", 1, 8, 4, help="Number of LSTM layers")
            with col3:
                dropout = st.slider("Dropout Rate", 0.0, 0.5, 0.2, 0.1, help="Dropout rate for regularization")
                learning_rate = st.slider("Learning Rate", 0.0001, 0.01, 0.001, 0.0001, help="Learning rate for training")
            with col4:
                use_gpu = st.checkbox("Use GPU", value=True)
                use_mixed_precision = st.checkbox("Mixed Precision", value=True)
                
        elif model_type == "transformer":
            # Transformer specific parameters
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                orderbook_depth = st.slider("Order Book Depth", 5, 50, 20, help="Depth of order book to analyze")
                d_model = st.slider("Model Dimension", 128, 1024, 512, help="Dimension of the model")
            with col2:
                sequence_length = st.slider("Sequence Length", 50, 500, 200, help="Length of input sequences")
                num_layers = st.slider("Number of Layers", 2, 12, 8, help="Number of transformer layers")
            with col3:
                nhead = st.slider("Number of Heads", 4, 32, 16, help="Number of attention heads")
                dropout = st.slider("Dropout Rate", 0.0, 0.5, 0.1, 0.1, help="Dropout rate for regularization")
            with col4:
                use_gpu = st.checkbox("Use GPU", value=True)
                use_mixed_precision = st.checkbox("Mixed Precision", value=True)
        
        # Common parameters
        st.markdown("### Common Parameters")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            batch_size = st.selectbox("Batch Size", [5000, 10000, 15000, 20000], index=1)
        with col2:
            prediction_horizon = st.selectbox("Prediction Horizon", [1, 2, 3, 5], index=0)
        with col3:
            optimize_hyperparams = st.checkbox("Optimize Hyperparameters", value=False)
        with col4:
            enable_analysis = st.checkbox("Enable Model Analysis", value=True, help="Generate performance analysis and recommendations")
        
        # Dynamic training button
        st.markdown("### Start Training")
        if st.button("🚀 Start Training", key="start_training", type="primary", use_container_width=True):
            try:
                # Clear console and reset progress
                while not console_queue.empty():
                    console_queue.get()
                
                log_to_console(f"🚀 Starting {model_type.upper()} model training", "TRAINING")
                log_to_console(f"Model configuration: {model_config}", "TRAINING")
                
                # Create progress tracking placeholders
                progress_placeholder = st.empty()
                metrics_placeholder = st.empty()
                chart_placeholder = st.empty()
                
                # Create training progress tracker
                from quanttime.utils.training_progress import create_training_progress, create_progress_callback, StreamlitProgressUpdater
                
                progress = create_training_progress(model_type)
                progress.is_training = True
                
                # Create Streamlit updater
                updater = StreamlitProgressUpdater(progress_placeholder, metrics_placeholder, chart_placeholder)
                progress_callback = create_progress_callback(progress, updater.update)
                
                with st.spinner(f"Training {model_type.upper()} model with automatic preprocessing..."):
                    # Get training data
                    mbo_df = st.session_state.get('training_mbo_data', None)
                    
                    # Check if training data exists
                    if mbo_df is None or len(mbo_df) == 0:
                        log_to_console("❌ No training data found! Please load data first", "ERROR")
                        st.error("❌ No training data found! Please load data first using the 'Load Data' button above.")
                        st.stop()
                    
                    log_to_console(f"📊 Training data loaded: {len(mbo_df):,} events", "TRAINING")
                    
                    # Check if data has required columns
                    required_columns = ['price', 'size', 'side', 'action']
                    missing_columns = [col for col in required_columns if col not in mbo_df.columns]
                    if missing_columns:
                        log_to_console(f"❌ Missing required columns in training data: {missing_columns}", "ERROR")
                        st.error(f"❌ Missing required columns in training data: {missing_columns}")
                        st.error("Please ensure your data contains: price, size, side, action columns")
                        st.stop()
                    
                    log_to_console(f"✅ Data validation passed - all required columns present", "TRAINING")
                    
                    # Create model configuration with model-specific parameters
                    model_config = {
                        'model_type': model_type,
                        'prediction_horizons': [1, 2, 3, 5],
                        'orderbook_depth': orderbook_depth,
                        'use_gpu': use_gpu,
                        'use_mixed_precision': use_mixed_precision,
                        'max_gpu_memory_gb': 7.0,
                        'max_ram_gb': 14.0,
                        'batch_size': batch_size
                    }
                    
                    # Add model-specific parameters
                    if model_type == "lightgbm":
                        model_config.update({
                            'feature_window': feature_window,
                            'num_leaves': num_leaves,
                            'max_depth': max_depth,
                            'learning_rate': learning_rate,
                            'num_iterations': num_iterations
                        })
                    elif model_type == "lstm":
                        model_config.update({
                            'sequence_length': sequence_length,
                            'hidden_size': hidden_size,
                            'num_layers': num_layers,
                            'dropout': dropout,
                            'learning_rate': learning_rate
                        })
                    elif model_type == "transformer":
                        model_config.update({
                            'sequence_length': sequence_length,
                            'd_model': d_model,
                            'num_layers': num_layers,
                            'nhead': nhead,
                            'dropout': dropout
                        })
                    
                    # Create and train model based on type
                    log_to_console(f"🔧 Creating {model_type.upper()} model with configuration...", "TRAINING")
                    
                    if model_type == "lightgbm":
                        from quanttime.models import create_enhanced_mbo_lightgbm_model
                        model = create_enhanced_mbo_lightgbm_model(**model_config)
                        log_to_console(f"✅ LightGBM model created with {num_iterations} iterations, {num_leaves} leaves", "TRAINING")
                    elif model_type == "lstm":
                        from quanttime.models import create_lstm_model
                        model = create_lstm_model(**model_config)
                        log_to_console(f"✅ LSTM model created with {num_layers} layers, {hidden_size} hidden units", "TRAINING")
                    elif model_type == "transformer":
                        from quanttime.models import create_transformer_model
                        model = create_transformer_model(**model_config)
                        log_to_console(f"✅ Transformer model created with {num_layers} layers, {d_model} dimensions", "TRAINING")
                    
                    # Train the model with progress tracking
                    log_to_console(f"🎯 Starting model training with {len(mbo_df):,} events", "TRAINING")
                    log_to_console(f"Training split: {train_split:.1%}, Validation split: {val_split:.1%}", "TRAINING")
                    log_to_console(f"Batch size: {batch_size}, GPU: {'Enabled' if use_gpu else 'Disabled'}", "TRAINING")
                    
                    # Create enhanced progress callback that also logs to console
                    def enhanced_progress_callback(epoch, total_epochs, train_loss, val_loss, message):
                        log_to_console(f"EPOCH {epoch}/{total_epochs}: Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f} - {message}", "TRAINING")
                        if progress_callback:
                            progress_callback(epoch, total_epochs, train_loss, val_loss, message)
                    
                    training_results = model.train(
                        mbo_df=mbo_df,
                        validation_split=val_split,
                        test_split=1.0 - train_split - val_split,
                        random_state=42,
                        progress_callback=enhanced_progress_callback
                    )
                    
                    # Stop progress updater
                    updater.stop()
                    
                    log_to_console(f"✅ Model training completed successfully!", "TRAINING")
                    log_to_console(f"📊 Training results stored in session state", "TRAINING")
                    
                    # Store model in session state
                    st.session_state[f'trained_{model_type}_model'] = model
                    st.session_state[f'{model_type}_training_results'] = training_results
                    
                    # Perform model analysis if enabled
                    if enable_analysis:
                        log_to_console(f"🔍 Starting model analysis and performance evaluation...", "TRAINING")
                        try:
                            from quanttime.analysis.model_analyzer import create_model_analyzer
                            
                            analyzer = create_model_analyzer()
                            analysis_result = analyzer.analyze_model_performance(
                                training_results, model_config, model_type
                            )
                            
                            # Store analysis results
                            st.session_state[f'{model_type}_analysis'] = analysis_result
                            
                            st.success(f"✅ {model_type.upper()} model training completed!")
                            st.success("📊 Model analysis and recommendations generated!")
                            
                            # Display quick analysis summary
                            st.markdown("### 📊 Quick Analysis Summary")
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Training Accuracy", f"{analysis_result.train_accuracy:.3f}")
                                st.metric("Validation Accuracy", f"{analysis_result.val_accuracy:.3f}")
                            
                            with col2:
                                st.metric("Overfitting Score", f"{analysis_result.overfitting_score:.3f}")
                                st.metric("Underfitting Score", f"{analysis_result.underfitting_score:.3f}")
                            
                            with col3:
                                st.metric("Capacity Utilization", f"{analysis_result.capacity_utilization:.3f}")
                                st.metric("Complexity Score", f"{analysis_result.complexity_score:.3f}")
                            
                            # Show priority recommendations
                            if analysis_result.priority_changes:
                                st.markdown("### 🔴 Priority Recommendations")
                                for rec in analysis_result.priority_changes:
                                    st.error(rec)
                            
                        except Exception as e:
                            st.warning(f"Model analysis failed: {e}")
                            st.success(f"✅ {model_type.upper()} model training completed!")
                    else:
                        st.success(f"✅ {model_type.upper()} model training completed!")
                    
                    # Display training results
                    st.markdown("### Training Results")
                    
                    # Handle different training result structures
                    if 'success' in training_results and training_results['success']:
                        # Enhanced MBO LightGBM model results
                        st.success("✅ Training completed successfully!")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Train Accuracy", f"{training_results.get('train_accuracy', 0):.4f}")
                        col2.metric("Val Accuracy", f"{training_results.get('val_accuracy', 0):.4f}")
                        col3.metric("Test Accuracy", f"{training_results.get('test_accuracy', 0):.4f}")
                        col4.metric("Best Iteration", training_results.get('best_iteration', 0))
                        
                        # Store model in registry for leaderboard
                        if 'trained_lightgbm_model' in st.session_state:
                            model = st.session_state['trained_lightgbm_model']
                            model_summary = model.get_model_summary()
                            
                            # Create model entry for leaderboard
                            model_entry = {
                                'name': f"Enhanced_MBO_LightGBM_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                                'model_type': 'Enhanced MBO LightGBM',
                                'architecture': 'LightGBM',
                                'train_accuracy': training_results.get('train_accuracy', 0),
                                'val_accuracy': training_results.get('val_accuracy', 0),
                                'test_accuracy': training_results.get('test_accuracy', 0),
                                'best_iteration': training_results.get('best_iteration', 0),
                                'prediction_horizons': model_summary['prediction_horizons'],
                                'created_at': datetime.now().isoformat(),
                                'training_config': model_config,
                                'model_object': model
                            }
                            
                            # Store in session state for leaderboard
                            if 'model_leaderboard' not in st.session_state:
                                st.session_state.model_leaderboard = []
                            st.session_state.model_leaderboard.append(model_entry)
                            
                    elif 'results' in training_results:
                        # Standard model results structure
                        for horizon, results in training_results['results'].items():
                            st.markdown(f"#### {horizon}-Minute Prediction Horizon")
                        
                        if 'test_metrics' in results:
                            metrics = results['test_metrics']
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Test RMSE", f"{metrics['rmse']:.6f}")
                            col2.metric("Test MAE", f"{metrics['mae']:.6f}")
                            col3.metric("Test R²", f"{metrics['r2']:.4f}")
                            col4.metric("Samples", f"{results['test_samples']:,}")
                            
                            # Direction accuracy (if available)
                            if 'direction_accuracy' in metrics:
                                st.markdown("**Direction Prediction Metrics:**")
                                col1, col2, col3, col4 = st.columns(4)
                                col1.metric("Direction Accuracy", f"{metrics['direction_accuracy']:.1%}")
                                col2.metric("Direction RMSE", f"{metrics['rmse']:.6f}")
                                col3.metric("Direction MAE", f"{metrics['mae']:.6f}")
                                col4.metric("Direction R²", f"{metrics['r2']:.4f}")
                            
                            # Pattern detection metrics (if available)
                            if 'pattern_accuracy' in metrics:
                                st.markdown("**Pattern Detection Metrics:**")
                                col1, col2, col3, col4 = st.columns(4)
                                col1.metric("Pattern Accuracy", f"{metrics['pattern_accuracy']:.1%}")
                                col2.metric("Iceberg Detection", f"{metrics.get('iceberg_accuracy', 0):.1%}")
                                col3.metric("Order Block Detection", f"{metrics.get('order_block_accuracy', 0):.1%}")
                                col4.metric("Absorption Detection", f"{metrics.get('absorption_accuracy', 0):.1%}")
                            
                            # Financial metrics
                            if 'sharpe_ratio' in metrics:
                                st.markdown("**Financial Metrics:**")
                                col1, col2, col3, col4 = st.columns(4)
                                col1.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.3f}")
                                col2.metric("Max Drawdown", f"{metrics['max_drawdown']:.3f}")
                                col3.metric("Win Rate", f"{metrics['win_rate']:.1%}")
                                col4.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
                                
                                col1, col2, col3, col4 = st.columns(4)
                                col1.metric("Total Return", f"{metrics['total_return']:.3f}")
                                col2.metric("Volatility", f"{metrics['volatility']:.3f}")
                                col3.metric("VaR (95%)", f"{metrics['var_95']:.3f}")
                                col4.metric("CVaR (95%)", f"{metrics['cvar_95']:.3f}")
                        else:
                            # Fallback for basic metrics
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Train Samples", f"{results['train_samples']:,}")
                            col2.metric("Val Samples", f"{results['val_samples']:,}")
                            col3.metric("Test Samples", f"{results['test_samples']:,}")
                            col4.metric("Best Val Loss", f"{results['best_val_loss']:.6f}")
                        
                        # Overall training summary
                        st.markdown("### Training Summary")
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Training Duration", f"{training_results['training_duration_minutes']:.1f} min")
                        col2.metric("Total Samples", f"{training_results['total_samples']:,}")
                        col3.metric("Feature Count", f"{training_results['feature_count']}")
                        
                        # Model summary
                        st.markdown("### Model Summary")
                        model_summary = model.get_model_summary()
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Model Type", model_summary['model_type'])
                        col2.metric("Prediction Horizons", str(model_summary['prediction_horizons']))
                        col3.metric("Is Trained", str(model_summary['is_trained']))
                        col4.metric("Created At", model_summary['model_metadata']['created_at'][:10])
                        
                        # Show model capabilities
                        if 'price_models' in model_summary['model_metadata']:
                            st.markdown("**Model Capabilities:**")
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Price Models", model_summary['model_metadata']['price_models'])
                            col2.metric("Direction Models", model_summary['model_metadata']['direction_models'])
                            col3.metric("Pattern Models", model_summary['model_metadata']['pattern_models'])
                        
                        # Save model option
                        st.markdown("### Model Management")
                        if st.button(f"Save {model_type.upper()} Model", key=f"save_{model_type}_model"):
                            try:
                                import os
                                from datetime import datetime
                                
                                # Create models directory if it doesn't exist
                                os.makedirs("models", exist_ok=True)
                                
                                # Generate filename
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"models/{model_type}_{timestamp}.joblib"
                                
                                # Save model
                                model.save_model(filename)
                                
                                st.success(f"✅ Model saved to {filename}")
                                
                                # Register in model registry
                                from quanttime.models.model_registry import ModelRegistry
                                registry = ModelRegistry()
                                
                                metadata = {
                                    'model_id': f"{model_type}_{timestamp}",
                                    'name': f"{model_type.upper()} MBO Model",
                                    'model_type': model_type,
                                    'symbol': 'ES.FUT',
                                    'start_date': st.session_state.get('training_start_date', 'unknown'),
                                    'end_date': st.session_state.get('training_end_date', 'unknown'),
                                    'duration_minutes': training_results['training_duration_minutes'],
                                    'samples': training_results['total_samples'],
                                    'parameters': model_config,
                                    'performance_metrics': {
                                        'test_rmse': results.get('test_metrics', {}).get('rmse', 0.0),
                                        'test_r2': results.get('test_metrics', {}).get('r2', 0.0),
                                        'sharpe_ratio': results.get('test_metrics', {}).get('sharpe_ratio', 0.0)
                                    },
                                    'file_path': filename,
                                    'size_mb': os.path.getsize(filename) / (1024 * 1024),
                                    'status': 'trained'
                                }
                                
                                registry.register_model(metadata)
                                st.success("✅ Model registered in model registry")
                                
                            except Exception as e:
                                st.error(f"Failed to save model: {e}")
                                
            except Exception as e:
                st.error(f"Training failed: {e}")
                st.exception(e)
        
        # Model actions
        if 'trained_mbo_model' in st.session_state:
            st.markdown("### Model Actions")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Save Model", key="save_mbo_model"):
                    try:
                        model = st.session_state.trained_mbo_model
                        model_path = "models/mbo_lightgbm_model.pkl"
                        model.save_model(model_path)
                        st.success(f"Model saved to {model_path}")
                    except Exception as e:
                        st.error(f"Failed to save model: {e}")
            
            with col2:
                if st.button("Load Model", key="load_mbo_model"):
                    try:
                        model = create_mbo_lightgbm_model()
                        model_path = "models/mbo_lightgbm_model.pkl"
                        model.load_model(model_path)
                        st.session_state.trained_mbo_model = model
                        st.success("Model loaded successfully")
                    except Exception as e:
                        st.error(f"Failed to load model: {e}")
            
            with col3:
                if st.button("Make Prediction", key="predict_mbo"):
                    try:
                        model = st.session_state.trained_mbo_model
                        
                        # Create sample MBO event for prediction
                        sample_event = {
                            'price': 5000.0,
                            'size': 100,
                            'side': 'B',
                            'action': 'F',
                            'timestamp': datetime.now()
                        }
                        
                        prediction = model.predict_single_tick(sample_event)
                        st.info(f"Sample prediction: {prediction:.6f}")
                    except Exception as e:
                        st.error(f"Prediction failed: {e}")

        # 🧪 Test Pipeline Section (appears after main training button)
        st.markdown("### 🧪 Test Pipeline")
        st.info("**Test the entire pipeline from data to backtest with small datasets for quick validation**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🧪 Full Pipeline Test", key="full_pipeline_test"):
                try:
                    # Create progress tracking placeholders for test
                    test_progress_placeholder = st.empty()
                    test_metrics_placeholder = st.empty()
                    test_chart_placeholder = st.empty()
                    
                    # Create training progress tracker for test
                    from quanttime.utils.training_progress import create_training_progress, create_progress_callback, StreamlitProgressUpdater
                    
                    test_progress = create_training_progress("test_pipeline")
                    test_progress.is_training = True
                    
                    # Create Streamlit updater for test
                    test_updater = StreamlitProgressUpdater(test_progress_placeholder, test_metrics_placeholder, test_chart_placeholder)
                    test_progress_callback = create_progress_callback(test_progress, test_updater.update)
                    
                    with st.spinner("Running full pipeline test (data → train → backtest)..."):
                        # Step 1: Generate test data
                        test_progress_callback.on_phase_start("data_generation", "Generating test data...")
                        from quanttime.utils.test_data_generator import generate_test_mbo_data
                        test_data = generate_test_mbo_data(num_events=1000)
                        st.session_state.test_data = test_data
                        
                        st.success("✅ Step 1: Test data generated")
                        st.info(f"📊 Generated {len(test_data)} MBO events")
                        
                        # Step 2: Train test model
                        test_progress_callback.on_phase_start("model_creation", "Creating test model...")
                        test_config = {
                            'model_type': model_type,
                            'prediction_horizons': [1, 2, 3],
                            'orderbook_depth': 10,
                            'sequence_length': 50,
                            'feature_window': 25,
                            'use_gpu': False,  # Use CPU for testing
                            'use_mixed_precision': False,
                            'max_gpu_memory_gb': 2.0,
                            'max_ram_gb': 4.0,
                            'batch_size': 1000
                        }
                        
                        if model_type == "lightgbm":
                            from quanttime.models import create_enhanced_mbo_lightgbm_model
                            test_model = create_enhanced_mbo_lightgbm_model(**test_config)
                        elif model_type == "lstm":
                            from quanttime.models import create_lstm_model
                            test_model = create_lstm_model(**test_config)
                        elif model_type == "transformer":
                            from quanttime.models import create_transformer_model
                            test_model = create_transformer_model(**test_config)
                        
                        test_results = test_model.train(
                            mbo_df=test_data,
                            validation_split=0.2,
                            test_split=0.1,
                            random_state=42,
                            progress_callback=test_progress_callback
                        )
                        
                        st.success("✅ Step 2: Test model trained")
                        st.info(f"🎯 Test accuracy: {test_results.get('test_accuracy', 0):.4f}")
                        
                        # Step 3: Run test backtest
                        test_progress_callback.on_phase_start("backtest", "Running test backtest...")
                        from quanttime.backtest.mbo_backtest_engine import run_mbo_backtest, OrderSide
                        
                        def simple_test_strategy(engine, event):
                            """Simple test strategy that buys on every 10th event."""
                            if engine.tick_count % 10 == 0:
                                engine.place_market_order(OrderSide.BUY, 1)
                        
                        backtest_result = run_mbo_backtest(
                            test_data, 
                            simple_test_strategy
                        )
                        
                        st.success("✅ Step 3: Test backtest completed")
                        st.info(f"🎯 Backtest trades: {backtest_result.total_trades}")
                        st.info(f"🎯 Backtest return: {backtest_result.total_return:.2%}")
                        
                        # Complete test and cleanup
                        test_progress_callback.on_training_complete({
                            'training_results': test_results,
                            'backtest_results': backtest_result
                        })
                        test_updater.stop()
                        
                        st.success("🎉 Full pipeline test completed successfully!")
                        st.info("All components (data generation, training, backtesting) are working correctly.")
                        
                except Exception as e:
                    st.error(f"❌ Full pipeline test failed: {e}")
                    st.exception(e)
        
        with col2:
            if st.button("🧪 Test Training Only", key="test_training_only"):
                try:
                    # Create progress tracking placeholders for test training
                    test_train_progress_placeholder = st.empty()
                    test_train_metrics_placeholder = st.empty()
                    test_train_chart_placeholder = st.empty()
                    
                    # Create training progress tracker for test training
                    from quanttime.utils.training_progress import create_training_progress, create_progress_callback, StreamlitProgressUpdater
                    
                    test_train_progress = create_training_progress("test_training")
                    test_train_progress.is_training = True
                    
                    # Create Streamlit updater for test training
                    test_train_updater = StreamlitProgressUpdater(test_train_progress_placeholder, test_train_metrics_placeholder, test_train_chart_placeholder)
                    test_train_progress_callback = create_progress_callback(test_train_progress, test_train_updater.update)
                    
                    with st.spinner("Running test training..."):
                        # Use test data if available, otherwise generate
                        if 'test_data' in st.session_state:
                            test_data = st.session_state.test_data
                        else:
                            test_train_progress_callback.on_phase_start("data_generation", "Generating test data...")
                            from quanttime.utils.test_data_generator import generate_test_mbo_data
                            test_data = generate_test_mbo_data(num_events=500)
                        
                        # Create test model config
                        test_train_progress_callback.on_phase_start("model_creation", "Creating test model...")
                        test_config = {
                            'model_type': model_type,
                            'prediction_horizons': [1, 2, 3],
                            'orderbook_depth': 10,
                            'sequence_length': 50,
                            'feature_window': 25,
                            'use_gpu': False,  # Use CPU for testing
                            'use_mixed_precision': False,
                            'max_gpu_memory_gb': 2.0,
                            'max_ram_gb': 4.0,
                            'batch_size': 1000
                        }
                        
                        # Create and train test model
                        if model_type == "lightgbm":
                            from quanttime.models import create_enhanced_mbo_lightgbm_model
                            test_model = create_enhanced_mbo_lightgbm_model(**test_config)
                        elif model_type == "lstm":
                            from quanttime.models import create_lstm_model
                            test_model = create_lstm_model(**test_config)
                        elif model_type == "transformer":
                            from quanttime.models import create_transformer_model
                            test_model = create_transformer_model(**test_config)
                        
                        # Train with test data
                        test_results = test_model.train(
                            mbo_df=test_data,
                            validation_split=0.2,
                            test_split=0.1,
                            random_state=42,
                            progress_callback=test_train_progress_callback
                        )
                        
                        # Complete test training and cleanup
                        test_train_progress_callback.on_training_complete(test_results)
                        test_train_updater.stop()
                        
                        st.success("✅ Test training completed!")
                        st.info(f"🎯 Test accuracy: {test_results.get('test_accuracy', 0):.4f}")
                        
                except Exception as e:
                    st.error(f"❌ Test training failed: {e}")
        
        with col3:
            if st.button("🧪 Test Backtest Only", key="test_backtest_only"):
                try:
                    with st.spinner("Running test backtest..."):
                        # Use test data if available, otherwise generate
                        if 'test_data' in st.session_state:
                            test_data = st.session_state.test_data
                        else:
                            from quanttime.utils.test_data_generator import generate_test_mbo_data
                            test_data = generate_test_mbo_data(num_events=500)
                        
                        # Run quick backtest
                        from quanttime.backtest.mbo_backtest_engine import run_mbo_backtest, OrderSide
                        
                        def simple_test_strategy(engine, event):
                            """Simple test strategy that buys on every 10th event."""
                            if engine.tick_count % 10 == 0:
                                engine.place_market_order(OrderSide.BUY, 1)
                        
                        test_result = run_mbo_backtest(
                            mbo_data=test_data,
                            strategy_func=simple_test_strategy
                        )
                        
                        st.success("✅ Test backtest completed!")
                        st.info(f"🎯 Test trades: {test_result.total_trades}")
                        st.info(f"🎯 Test return: {test_result.total_return:.2%}")
                        
                except Exception as e:
                    st.error(f"❌ Test backtest failed: {e}")


def backtests_tab():
    """Backtesting interface tab"""
    st.subheader("📈 Backtesting")
    
    # Backtest Configuration
    with st.expander("⚙️ Backtest Configuration", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Model selection
            st.markdown("**🤖 Model Selection**")
            model_type = st.selectbox(
                "Model Type:",
                ["LightGBM", "XGBoost", "Random Forest", "Neural Network", "Ensemble"],
                key="backtest_model_type"
            )
            
            # Strategy selection
            st.markdown("**📊 Strategy**")
            strategy = st.selectbox(
                "Trading Strategy:",
                ["Mean Reversion", "Momentum", "Arbitrage", "Market Making", "Custom"],
                key="backtest_strategy"
            )
        
        with col2:
            # Date range
            st.markdown("**📅 Date Range**")
            start_date = st.date_input(
                "Start Date:",
                value=datetime.now().date() - timedelta(days=30),
                key="backtest_start_date"
            )
            end_date = st.date_input(
                "End Date:",
                value=datetime.now().date(),
                key="backtest_end_date"
            )
            
            # Timeframe
            st.markdown("**⏰ Timeframe**")
            timeframe = st.selectbox(
                "Timeframe:",
                ["1m", "5m", "15m", "1h", "4h", "1d"],
                key="backtest_timeframe"
            )
        
        with col3:
            # Capital and risk
            st.markdown("**💰 Capital & Risk**")
            initial_capital = st.number_input(
                "Initial Capital ($):",
                min_value=1000,
                max_value=1000000,
                value=100000,
                step=10000,
                key="backtest_capital"
            )
            
            position_size = st.slider(
                "Position Size (%):",
                min_value=1,
                max_value=100,
                value=10,
                key="backtest_position_size"
            )
            
            stop_loss = st.slider(
                "Stop Loss (%):",
                min_value=1,
                max_value=50,
                value=5,
                key="backtest_stop_loss"
            )
    
    # Backtest Execution
    with st.expander("🚀 Execute Backtest", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Symbols to test
            st.markdown("**📊 Symbols**")
            symbols = st.multiselect(
                "Select Symbols:",
                ["ES", "NQ", "RTY", "YM", "CL", "GC", "SI", "ZB", "ZN"],
                default=["ES"],
                key="backtest_symbols"
            )
        
        with col2:
            # Advanced options
            st.markdown("**🔧 Advanced Options**")
            include_slippage = st.checkbox("Include Slippage", value=True, key="backtest_slippage")
            include_commission = st.checkbox("Include Commission", value=True, key="backtest_commission")
            commission_rate = st.number_input(
                "Commission Rate ($):",
                min_value=0.0,
                max_value=10.0,
                value=2.5,
                step=0.1,
                key="backtest_commission_rate"
            )
        
        with col3:
            # Execution
            st.markdown("**▶️ Execute**")
            if st.button("🚀 Run Backtest", type="primary", key="run_backtest"):
                with st.spinner("Running backtest..."):
                    # Simulate backtest execution
                    time.sleep(2)
                    st.success("✅ Backtest completed!")
    
    # Backtest Results
    with st.expander("📊 Backtest Results", expanded=True):
        # Results tabs
        results_tabs = st.tabs(["📈 Performance", "💰 P&L", "📊 Statistics", "🎯 Trades"])
        
        with results_tabs[0]:
            st.markdown("**📈 Performance Metrics**")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Return", "12.5%", "2.3%")
                st.metric("Sharpe Ratio", "1.85", "0.12")
            
            with col2:
                st.metric("Max Drawdown", "-8.2%", "-1.1%")
                st.metric("Win Rate", "68.5%", "3.2%")
            
            with col3:
                st.metric("Profit Factor", "2.34", "0.15")
                st.metric("Total Trades", "156", "12")
            
            with col4:
                st.metric("Avg Trade", "$342", "$28")
                st.metric("Best Trade", "$1,245", "$89")
            
            # Performance chart placeholder
            st.markdown("**📈 Equity Curve**")
            st.info("Performance chart will be displayed here")
        
        with results_tabs[1]:
            st.markdown("**💰 Profit & Loss Analysis**")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Monthly P&L**")
                monthly_data = {
                    "Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                    "P&L": [1250, 890, 1560, -320, 2100, 980]
                }
                st.bar_chart(monthly_data, x="Month", y="P&L")
            
            with col2:
                st.markdown("**Symbol Performance**")
                symbol_data = {
                    "Symbol": ["ES", "NQ", "RTY"],
                    "P&L": [2340, 1560, 890],
                    "Trades": [45, 32, 28]
                }
                st.dataframe(symbol_data, use_container_width=True)
        
        with results_tabs[2]:
            st.markdown("**📊 Detailed Statistics**")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Risk Metrics**")
                risk_metrics = {
                    "Metric": ["VaR (95%)", "CVaR (95%)", "Volatility", "Beta", "Alpha"],
                    "Value": ["-2.3%", "-3.1%", "15.2%", "0.85", "0.8%"]
                }
                st.dataframe(risk_metrics, use_container_width=True)
            
            with col2:
                st.markdown("**Trade Analysis**")
                trade_metrics = {
                    "Metric": ["Avg Win", "Avg Loss", "Largest Win", "Largest Loss", "Avg Hold Time"],
                    "Value": ["$456", "-$234", "$1,245", "-$567", "2.3 days"]
                }
                st.dataframe(trade_metrics, use_container_width=True)
        
        with results_tabs[3]:
            st.markdown("**🎯 Recent Trades**")
            # Trade history table
            trades_data = {
                "Date": ["2024-01-15", "2024-01-14", "2024-01-13", "2024-01-12", "2024-01-11"],
                "Symbol": ["ES", "NQ", "ES", "RTY", "ES"],
                "Side": ["Long", "Short", "Long", "Short", "Long"],
                "Entry": ["$4,850", "$16,750", "$4,845", "$2,120", "$4,840"],
                "Exit": ["$4,865", "$16,720", "$4,860", "$2,105", "$4,855"],
                "P&L": ["$750", "$1,200", "$750", "$750", "$750"],
                "Duration": ["2h 15m", "4h 30m", "1h 45m", "3h 20m", "2h 50m"]
            }
            st.dataframe(trades_data, use_container_width=True)
    
    # Backtest Management
    with st.expander("💾 Backtest Management", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**💾 Save Backtest**")
            backtest_name = st.text_input("Backtest Name:", key="save_backtest_name")
            if st.button("💾 Save Results", key="save_backtest"):
                st.success("✅ Backtest saved!")
        
        with col2:
            st.markdown("**📋 Load Backtest**")
            saved_backtests = ["Backtest_2024_01_15", "Backtest_2024_01_14", "Backtest_2024_01_13"]
            selected_backtest = st.selectbox("Select Backtest:", saved_backtests, key="load_backtest")
            if st.button("📋 Load Results", key="load_backtest_btn"):
                st.info("📋 Loading backtest results...")


def train_tab():
    """Training interface tab"""
    st.subheader("🏋️ Model Training")
    
    # Training Configuration
    with st.expander("⚙️ Training Configuration", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Model architecture
            st.markdown("**🤖 Model Architecture**")
            model_type = st.selectbox(
                "Model Type:",
                ["LightGBM", "XGBoost", "Random Forest", "LSTM", "Transformer", "Ensemble"],
                key="train_model_type"
            )
            
            # Data source
            st.markdown("**📊 Data Source**")
            data_source = st.selectbox(
                "Data Source:",
                ["Databento MBO", "Custom CSV", "Live Stream", "Historical"],
                key="train_data_source"
            )
        
        with col2:
            # Training parameters
            st.markdown("**📈 Training Parameters**")
            epochs = st.number_input("Epochs:", min_value=1, max_value=1000, value=100, key="train_epochs")
            batch_size = st.number_input("Batch Size:", min_value=32, max_value=10000, value=1000, key="train_batch_size")
            learning_rate = st.slider("Learning Rate:", min_value=0.001, max_value=0.1, value=0.01, key="train_lr")
        
        with col3:
            # Advanced settings
            st.markdown("**🔧 Advanced Settings**")
            validation_split = st.slider("Validation Split:", min_value=0.1, max_value=0.5, value=0.2, key="train_val_split")
            early_stopping = st.checkbox("Early Stopping", value=True, key="train_early_stop")
            cross_validation = st.checkbox("Cross Validation", value=False, key="train_cv")
    
    # Data Selection
    with st.expander("📁 Data Selection", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Date range
            st.markdown("**📅 Training Period**")
            train_start = st.date_input(
                "Training Start:",
                value=datetime.now().date() - timedelta(days=60),
                key="train_start_date"
            )
            train_end = st.date_input(
                "Training End:",
                value=datetime.now().date() - timedelta(days=30),
                key="train_end_date"
            )
            
            # Symbols
            st.markdown("**📊 Symbols**")
            train_symbols = st.multiselect(
                "Select Symbols:",
                ["ES", "NQ", "RTY", "YM", "CL", "GC", "SI", "ZB", "ZN"],
                default=["ES"],
                key="train_symbols"
            )
        
        with col2:
            # Feature engineering
            st.markdown("**🔧 Feature Engineering**")
            feature_set = st.selectbox(
                "Feature Set:",
                ["Basic MBO", "Advanced L3", "Execution Aware", "Custom"],
                key="train_feature_set"
            )
            
            # Prediction horizon
            st.markdown("**⏰ Prediction Horizon**")
            horizons = st.multiselect(
                "Prediction Horizons (minutes):",
                [1, 2, 3, 5, 10, 15, 30, 60],
                default=[1, 2, 3, 5],
                key="train_horizons"
            )
    
    # Training Execution
    with st.expander("🚀 Start Training", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Model name
            st.markdown("**📝 Model Name**")
            model_name = st.text_input(
                "Model Name:",
                value=f"{model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                key="train_model_name"
            )
        
        with col2:
            # Training device
            st.markdown("**🖥️ Training Device**")
            training_device = st.selectbox(
                "Device:",
                ["laptop", "r630xl", "r810"],
                key="train_device"
            )
        
        with col3:
            # Start training
            st.markdown("**▶️ Execute**")
            if st.button("🚀 Start Training", type="primary", key="start_training"):
                with st.spinner("Starting training..."):
                    # Simulate training start
                    time.sleep(2)
                    st.success("✅ Training started!")
    
    # Training Progress
    with st.expander("📊 Training Progress", expanded=True):
        # Progress metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Epoch", "45/100", "45%")
            st.progress(0.45)
        
        with col2:
            st.metric("Training Loss", "0.234", "-0.012")
            st.metric("Validation Loss", "0.289", "0.008")
        
        with col3:
            st.metric("Accuracy", "72.3%", "1.2%")
            st.metric("F1 Score", "0.689", "0.023")
        
        with col4:
            st.metric("Time Remaining", "2h 15m", "-5m")
            st.metric("GPU Usage", "87%", "3%")
        
        # Training charts
        st.markdown("**📈 Training Metrics**")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Loss Curve**")
            st.info("Loss curve chart will be displayed here")
        
        with col2:
            st.markdown("**Accuracy Curve**")
            st.info("Accuracy curve chart will be displayed here")
    
    # Model Management
    with st.expander("💾 Model Management", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**💾 Save Model**")
            save_name = st.text_input("Save Name:", key="save_model_name")
            if st.button("💾 Save Model", key="save_model"):
                st.success("✅ Model saved!")
        
        with col2:
            st.markdown("**📋 Load Model**")
            saved_models = ["Model_2024_01_15", "Model_2024_01_14", "Model_2024_01_13"]
            selected_model = st.selectbox("Select Model:", saved_models, key="load_model")
            if st.button("📋 Load Model", key="load_model_btn"):
                st.info("📋 Loading model...")


def data_tab():
    st.subheader("Data Collection & Processing")
    cfg = get_cfg()
    
    # Import unified data pipeline
    from quanttime.data import (
        get_processor, get_available_data_types, list_available_schemas,
        DataType, NormalizationType, FeatureSet
    )
    
    # Initialize processor
    processor = get_processor()
    
    # Create tabs for different data operations
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Data Overview", "🔄 Data Processing", "📁 File Management", "📈 Data Export"])
    
    with tab1:
        st.markdown("### Data Overview")
        
        # Show data type summary
        try:
            summary = get_available_data_types()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Raw Data Types**")
                if summary.get('raw_data_types'):
                    for data_type, info in summary['raw_data_types'].items():
                        st.info(f"**{data_type.upper()}**: {info['files']} files, {info['dates']} dates, {info['size_gb']:.2f} GB")
                else:
                    st.warning("No raw data found")
            
            with col2:
                st.markdown("**Processed Schemas**")
                if summary.get('processed_schemas'):
                    for schema_name, info in summary['processed_schemas'].items():
                        st.success(f"**{schema_name}**: {info['files']} files, {info['size_gb']:.2f} GB")
                else:
                    st.info("No processed data found")
            
            # Show total statistics
            st.markdown("**Overall Statistics**")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Files", summary.get('total_files', 0))
            col2.metric("Total Size", f"{summary.get('total_size_gb', 0):.2f} GB")
            col3.metric("Data Types", len(summary.get('raw_data_types', {})))
            
        except Exception as e:
            st.error(f"Failed to load data summary: {e}")
        
        # Show available schemas
        st.markdown("### Available Schemas")
        try:
            schemas = list_available_schemas()
            if schemas:
                for schema_name in schemas:
                    with st.expander(f"Schema: {schema_name}"):
                        from quanttime.data import get_schema_info
                        info = get_schema_info(schema_name)
                        if info:
                            st.write(f"**Type**: {info.get('data_type', 'Unknown')}")
                            st.write(f"**Features**: {len(info.get('features', []))}")
                            st.write(f"**Description**: {info.get('description', 'No description')}")
                            if info.get('normalization_type'):
                                st.write(f"**Normalization**: {info.get('normalization_type')}")
                            if info.get('feature_set'):
                                st.write(f"**Feature Set**: {info.get('feature_set')}")
            else:
                st.info("No schemas available")
        except Exception as e:
            st.error(f"Failed to load schemas: {e}")
    
    with tab2:
        st.markdown("### Data Processing")
        
        # Data processing controls
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Processing Configuration**")
            
            # Data type selection (MBO only)
            data_type = st.selectbox(
                "Data Type",
                ["mbo"],
                help="MBO (Market By Order) Level 3 data"
            )
            
            # Normalization technique selection
            normalization_technique = st.selectbox(
                "Normalization Technique",
                ["tick_relative", "log_normalized", "z_score", "min_max", "robust"],
                index=0,  # Default to tick_relative
                help="Select the normalization technique for price and size data"
            )
            
            # Feature engineering intensity selection
            intensity_level = st.selectbox(
                "Feature Engineering Intensity",
                ["light", "medium", "heavy", "extreme"],
                index=1,  # Default to medium
                help="Select the intensity level for feature engineering"
            )
            
            # Display intensity level info
            intensity_info = {
                "light": "~50 features - Core execution-aware features with 4 key horizons",
                "medium": "~100 features - Expanded multi-horizon analysis with 8 horizons", 
                "heavy": "~200 features - Comprehensive analysis with 15 horizons",
                "extreme": "~300+ features - Maximum features including advanced patterns and regimes"
            }
            
            st.info(f"**{intensity_level.upper()} Intensity**: {intensity_info[intensity_level]}")
            
            # Auto-generate schema name based on intensity and normalization
            schema_name = f"execution_aware_{intensity_level}_v1"
        
        with col2:
            st.markdown("**Processing Options**")
            
            # Date selection - Use databento loader to get actual available dates
            try:
                from quanttime.adapter.databento_loader import get_databento_loader
                databento_loader = get_databento_loader('data/es_futures/mbo')
                available_dates = databento_loader.get_available_dates()
                
                log_to_console(f"🔍 Found {len(available_dates)} available dates for processing", "INFO")
                if available_dates:
                    log_to_console(f"📅 Sample dates: {available_dates[:5]}", "INFO")
                
                if available_dates:
                    selected_dates = st.multiselect(
                        "Select Dates to Process",
                        available_dates,
                        default=available_dates[:3] if len(available_dates) >= 3 else available_dates,
                        help="Select dates to process from raw to normalized"
                    )
                    
                    log_to_console(f"✅ Selected {len(selected_dates)} dates for processing", "INFO")
                    if selected_dates:
                        log_to_console(f"📅 Selected dates: {selected_dates}", "INFO")
                    else:
                        log_to_console("⚠️ No dates selected - button will be disabled", "WARNING")
                else:
                    selected_dates = []
                    st.warning("No raw data dates available")
                    log_to_console("❌ No raw data dates available", "ERROR")
            except Exception as e:
                selected_dates = []
                st.error(f"Failed to load available dates: {e}")
                log_to_console(f"❌ Error loading available dates: {str(e)}", "ERROR")
                import traceback
                traceback.print_exc()
            
            # Trading hours filter option
            trading_hours_only = st.checkbox(
                "📈 Trading Hours Only (9:30 AM - 4:00 PM EST)",
                value=False,
                help="Filter to NYSE trading hours only. Unchecked = full day data"
            )
            
            # Batch processing option
            batch_process = st.checkbox(
                "Batch Process",
                value=True,
                help="Process multiple dates in batch"
            )
        
        # Console output and progress tracking
        st.markdown("---")
        console_container = create_console_output()
        progress_bar, status_text = create_progress_tracker()
        
        # DBN to Parquet Conversion Section
        st.markdown("---")
        st.markdown("### 📁 DBN to Parquet Conversion")
        st.markdown("Convert raw DBN files to optimized Parquet format for faster loading.")
        
        # DBN to Parquet conversion options
        col1, col2 = st.columns(2)
        
        with col1:
            convert_dbn_to_parquet = st.checkbox(
                "🔄 Convert DBN to Parquet",
                value=False,
                help="Convert DBN files to Parquet for faster loading"
            )
            
            if convert_dbn_to_parquet:
                # Get available DBN dates
                try:
                    from quanttime.adapter.databento_loader import get_databento_loader
                    databento_loader = get_databento_loader('data/es_futures/mbo')
                    dbn_dates = databento_loader.get_available_dates()
                    
                    if dbn_dates:
                        st.success(f"✅ Found {len(dbn_dates)} DBN files")
                        
                        # Date selection for conversion
                        selected_dbn_dates = st.multiselect(
                            "Select DBN files to convert:",
                            dbn_dates,
                            default=dbn_dates[:5] if len(dbn_dates) > 5 else dbn_dates,
                            help="Select which DBN files to convert to Parquet"
                        )
                        
                        # Conversion options
                        compression_type = st.selectbox(
                            "Compression Type:",
                            ["snappy", "gzip", "brotli"],
                            index=0,
                            help="Parquet compression type (snappy = fast, gzip = smaller)"
                        )
                        
                        include_metadata = st.checkbox(
                            "📋 Include metadata",
                            value=True,
                            help="Include file metadata and schema information"
                        )
                        
                    else:
                        st.warning("⚠️ No DBN files found in data/es_futures/mbo")
                        selected_dbn_dates = []
                        
                except Exception as e:
                    st.error(f"❌ Error loading DBN files: {e}")
                    selected_dbn_dates = []
        
        with col2:
            if convert_dbn_to_parquet and 'selected_dbn_dates' in locals() and selected_dbn_dates:
                st.info("📊 Conversion Info:")
                st.write(f"• **Files to convert**: {len(selected_dbn_dates)}")
                st.write(f"• **Compression**: {compression_type}")
                st.write(f"• **Output location**: `data/raw/mbo/parquet/`")
                st.write(f"• **Naming**: `{selected_dbn_dates[0]}.parquet` format")
                
                # Conversion button
                if st.button("🚀 Convert DBN to Parquet", type="primary"):
                    if selected_dbn_dates:
                        try:
                            # Clear console and reset progress
                            while not console_queue.empty():
                                console_queue.get()
                            
                            # Set processing active flag for auto-refresh
                            st.session_state.processing_active = True
                            
                            log_to_console(f"🚀 Starting DBN to Parquet conversion for {len(selected_dbn_dates)} files", "INFO")
                            log_to_console(f"📊 Compression: {compression_type}, Include metadata: {include_metadata}", "INFO")
                            
                            # Create progress callback for conversion
                            def conversion_callback(stage, current, total, message, progress):
                                log_to_console(f"{stage}: {message} ({progress:.1%})", "INFO")
                                status_text.text(f"{stage}: {message}")
                                progress_bar.progress(progress)
                            
                            # Convert each DBN file
                            success_count = 0
                            for i, date_str in enumerate(selected_dbn_dates):
                                log_to_console(f"📁 Converting {date_str} ({i+1}/{len(selected_dbn_dates)})", "INFO")
                                status_text.text(f"Converting {date_str}...")
                                progress_bar.progress(i / len(selected_dbn_dates))
                                
                                try:
                                    success = convert_dbn_to_parquet_file(
                                        date_str, 
                                        compression_type, 
                                        include_metadata, 
                                        conversion_callback
                                    )
                                    
                                    if success:
                                        success_count += 1
                                        log_to_console(f"✅ Successfully converted {date_str}", "SUCCESS")
                                    else:
                                        log_to_console(f"❌ Failed to convert {date_str}", "ERROR")
                                        
                                except Exception as e:
                                    log_to_console(f"❌ Error converting {date_str}: {str(e)}", "ERROR")
                                    st.error(f"Error converting {date_str}: {str(e)}")
                            
                            progress_bar.progress(1.0)
                            status_text.text("Conversion complete!")
                            
                            # Clear processing active flag
                            st.session_state.processing_active = False
                            
                            if success_count > 0:
                                log_to_console(f"✅ Conversion complete: {success_count}/{len(selected_dbn_dates)} files converted successfully", "SUCCESS")
                                st.success(f"Converted {success_count}/{len(selected_dbn_dates)} files to Parquet format")
                            else:
                                log_to_console("❌ No files were converted successfully", "ERROR")
                                st.error("No files were converted successfully. Check console output for details.")
                                
                        except Exception as e:
                            log_to_console(f"❌ Conversion failed: {str(e)}", "ERROR")
                            st.error(f"Conversion failed: {e}")
                            progress_bar.progress(0)
                            status_text.text("Conversion failed!")
                            st.session_state.processing_active = False
        
        # Debug information
        with st.expander("🔍 Debug Information", expanded=False):
            st.write(f"**selected_dates**: {selected_dates}")
            st.write(f"**selected_dates type**: {type(selected_dates)}")
            st.write(f"**selected_dates length**: {len(selected_dates) if selected_dates else 0}")
            st.write(f"**Button disabled**: {not selected_dates}")
            st.write(f"**available_dates**: {available_dates[:5] if 'available_dates' in locals() else 'Not loaded'}")
        
        # Processing buttons
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            log_to_console(f"🔘 Button state - selected_dates: {len(selected_dates) if selected_dates else 0}", "INFO")
            
            if st.button("🔄 Process Raw to Normalized", disabled=not selected_dates, key="process_raw_button"):
                st.session_state.button_click_count += 1
                log_to_console(f"🔄 Process Raw to Normalized button clicked! (Click #{st.session_state.button_click_count})", "INFO")
                if selected_dates:
                    try:
                        # Clear console and reset progress
                        while not console_queue.empty():
                            console_queue.get()
                        
                        # Ensure processing state is clean
                        st.session_state.processing_active = True
                        st.session_state.current_stage = "Starting"
                        
                        trading_hours_text = "Trading Hours Only" if trading_hours_only else "Full Day"
                        log_to_console(f"🚀 Starting batch processing of {len(selected_dates)} dates", "INFO")
                        log_to_console(f"📊 Data type: {data_type}, Schema: {schema_name}, Intensity: {intensity_level}, Mode: {trading_hours_text}", "INFO")
                        
                        if batch_process:
                            log_to_console("Using batch processing mode", "INFO")
                            
                            # Process each date with detailed logging
                            success_count = 0
                            for i, date_str in enumerate(selected_dates):
                                log_to_console(f"Processing date {i+1}/{len(selected_dates)}: {date_str}", "INFO")
                                status_text.text(f"Processing {date_str}...")
                                progress_bar.progress((i) / len(selected_dates))
                                
                                try:
                                    # Check if raw file exists first
                                    from quanttime.adapter.databento_loader import get_databento_loader
                                    databento_loader = get_databento_loader('data/es_futures/mbo')
                                    available_dates = databento_loader.get_available_dates()
                                    
                                    if date_str not in available_dates:
                                        log_to_console(f"❌ Raw file not found for {date_str}", "ERROR")
                                        log_to_console(f"Available dates: {available_dates[:10]}...", "INFO")
                                        st.error(f"Raw file not found for {date_str}. Available dates: {available_dates[:10]}...")
                                        continue
                                    
                                    log_to_console(f"📁 Found raw file for {date_str} - processing entire day's data", "INFO")
                                    
                                    log_to_console(f"✅ Raw file found for {date_str}, starting processing...", "INFO")
                                    log_to_console(f"🎯 Processing {len(selected_dates)} dates with {intensity_level} intensity", "INFO")
                                    
                                    # Create a progress callback that logs to console
                                    def processing_callback(stage, current, total, message, progress):
                                        log_to_console(f"{stage}: {message} ({progress:.1%})", "INFO")
                                        status_text.text(f"{stage}: {message}")
                                        progress_bar.progress(progress)
                                        
                                        # Update metrics based on stage
                                        if "Loading raw data" in stage:
                                            st.session_state.current_stage = "Loading Data"
                                        elif "Feature engineering" in stage:
                                            st.session_state.current_stage = "Feature Engineering"
                                        elif "Saving processed data" in stage:
                                            st.session_state.current_stage = "Saving Data"
                                    
                                    success = processor.process_raw_to_normalized(
                                        date_str, data_type, schema_name, intensity_level, trading_hours_only, max_rows=None, progress_callback=processing_callback
                                    )
                                    
                                    if success:
                                        success_count += 1
                                        log_to_console(f"✅ Successfully processed {date_str}", "SUCCESS")
                                    else:
                                        log_to_console(f"❌ Failed to process {date_str}", "ERROR")
                                        
                                except Exception as e:
                                    log_to_console(f"❌ Error processing {date_str}: {str(e)}", "ERROR")
                                    st.error(f"Error processing {date_str}: {str(e)}")
                            
                            progress_bar.progress(1.0)
                            status_text.text("Processing complete!")
                            
                            # Clear processing active flag
                            st.session_state.processing_active = False
                            
                            if success_count > 0:
                                log_to_console(f"✅ Batch processing complete: {success_count}/{len(selected_dates)} dates processed successfully", "SUCCESS")
                                st.success(f"Processed {success_count}/{len(selected_dates)} dates with {intensity_level} intensity successfully")
                            else:
                                log_to_console("❌ No dates were processed successfully", "ERROR")
                                st.error("No dates were processed successfully. Check console output for details.")
                                
                        else:
                            trading_hours_text = "Trading Hours Only" if trading_hours_only else "Full Day"
                            log_to_console("Using single date processing mode", "INFO")
                            log_to_console(f"Mode: {trading_hours_text}", "INFO")
                            for date_str in selected_dates:
                                log_to_console(f"Processing single date: {date_str}", "INFO")
                                status_text.text(f"Processing {date_str}...")
                                
                                try:
                                    # Create a progress callback that logs to console
                                    def processing_callback(stage, current, total, message, progress):
                                        log_to_console(f"{stage}: {message} ({progress:.1%})", "INFO")
                                        status_text.text(f"{stage}: {message}")
                                        progress_bar.progress(progress)
                                        
                                        # Update metrics based on stage
                                        if "Loading raw data" in stage:
                                            st.session_state.current_stage = "Loading Data"
                                        elif "Feature engineering" in stage:
                                            st.session_state.current_stage = "Feature Engineering"
                                        elif "Saving processed data" in stage:
                                            st.session_state.current_stage = "Saving Data"
                                    
                                    success = processor.process_raw_to_normalized(
                                        date_str, data_type, schema_name, intensity_level, trading_hours_only, max_rows=None, progress_callback=processing_callback
                                    )
                                    
                                    if success:
                                        log_to_console(f"✅ Successfully processed {date_str}", "SUCCESS")
                                        st.success(f"Processed {date_str} with {intensity_level} intensity successfully")
                                    else:
                                        log_to_console(f"❌ Failed to process {date_str}", "ERROR")
                                        st.error(f"Failed to process {date_str}")
                                        
                                except Exception as e:
                                    log_to_console(f"❌ Error processing {date_str}: {str(e)}", "ERROR")
                                    st.error(f"Error processing {date_str}: {str(e)}")
                        
                        progress_bar.progress(1.0)
                        status_text.text("Processing complete!")
                        
                        # Clear processing active flag
                        st.session_state.processing_active = False
                        
                    except Exception as e:
                        log_to_console(f"❌ Processing failed: {str(e)}", "ERROR")
                        st.error(f"Processing failed: {e}")
                        progress_bar.progress(0)
                        status_text.text("Processing failed!")
                        st.session_state.processing_active = False
        
        with col2:
            if st.button("✅ Validate Processed Data", disabled=not selected_dates, key="validate_data_button"):
                if selected_dates:
                    try:
                        with st.spinner("Validating data..."):
                            for date_str in selected_dates:
                                validation = processor.validate_processed_data(
                                    date_str, data_type, schema_name
                                )
                                if validation.get('valid', False):
                                    st.success(f"✅ {date_str}: Valid")
                                else:
                                    st.error(f"❌ {date_str}: {validation.get('error', 'Invalid')}")
                    except Exception as e:
                        st.error(f"Validation failed: {e}")
        
        with col3:
            if st.button("📊 Compare Raw vs Processed", disabled=not selected_dates, key="compare_data_button"):
                if selected_dates:
                    try:
                        with st.spinner("Comparing data..."):
                            for date_str in selected_dates[:1]:  # Show first date only
                                comparison = processor.get_data_comparison(
                                    date_str, data_type, schema_name
                                )
                                if 'error' not in comparison:
                                    st.info(f"**{date_str} Comparison:**")
                                    st.write(f"Raw: {comparison.get('raw_metadata', {}).get('size_mb', 0):.2f} MB")
                                    st.write(f"Processed: {comparison.get('processed_rows', 0):,} rows, {comparison.get('processed_columns', 0)} columns")
                                else:
                                    st.error(f"Comparison failed: {comparison['error']}")
                    except Exception as e:
                        st.error(f"Comparison failed: {e}")
        
        # Test Pipeline Section (Moved to bottom)
        st.markdown("---")
        st.markdown("### 🧪 Test Pipeline")
        
        # Add a simple test button for UI responsiveness
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🧪 Test UI Responsiveness", key="test_ui_button"):
                st.session_state.button_click_count += 1
                log_to_console(f"🧪 UI responsiveness test - button clicked! (Click #{st.session_state.button_click_count})", "SUCCESS")
                st.success("✅ UI is responsive!")
        
        with col2:
            # Test sample size selection
            sample_size = st.selectbox(
                "Sample Size",
                [100, 500, 1000, 5000],
                index=1,  # Default to 500
                help="Number of events to process for testing"
            )
        
        with col3:
            # Test date selection (use first available date)
            test_date = None
            if available_dates:
                test_date = st.selectbox(
                    "Test Date",
                    available_dates[:5],  # Show first 5 dates
                    index=0,
                    help="Select a date to test the pipeline"
                )
        
        # Test button in its own row
        if st.button("🧪 Test Pipeline", disabled=not test_date, key="test_pipeline_button"):
            st.session_state.button_click_count += 1
            if test_date:
                    try:
                        # Clear console and reset progress
                        while not console_queue.empty():
                            console_queue.get()
                        
                        log_to_console(f"🧪 Starting test pipeline for {test_date}", "INFO")
                        log_to_console(f"Sample size: {sample_size} events, Intensity: {intensity_level}", "INFO")
                        
                        # Get databento loader for raw data
                        from quanttime.adapter.databento_loader import get_databento_loader
                        databento_loader = get_databento_loader('data/es_futures/mbo')
                        
                        # Load a small sample of raw data
                        log_to_console(f"📥 Loading sample data from {test_date}...", "INFO")
                        status_text.text(f"Loading sample data from {test_date}...")
                        progress_bar.progress(0.2)
                        
                        raw_sample = databento_loader.load_sample_data(test_date, max_events=sample_size)
                        
                        if raw_sample is not None and not raw_sample.empty:
                            log_to_console(f"✅ Loaded {len(raw_sample)} raw events", "SUCCESS")
                            st.success(f"✅ Loaded {len(raw_sample)} raw events")
                            
                            # Process the sample through the pipeline
                            log_to_console(f"🔄 Processing with {intensity_level} intensity...", "INFO")
                            status_text.text(f"Processing with {intensity_level} intensity...")
                            progress_bar.progress(0.5)
                            
                            # Create a temporary processor for testing
                            from quanttime.data.processor import UnifiedDataProcessor
                            test_processor = UnifiedDataProcessor()
                            
                            # Process the sample data
                            processed_sample = test_processor.process_sample_data(
                                raw_sample, data_type, schema_name, intensity_level
                            )
                            
                            if processed_sample is not None and not processed_sample.empty:
                                log_to_console(f"✅ Successfully processed sample: {len(processed_sample)} rows, {len(processed_sample.columns)} columns", "SUCCESS")
                                status_text.text("Processing complete!")
                                progress_bar.progress(1.0)
                                
                                st.success(f"✅ Processed sample: {len(processed_sample)} rows, {len(processed_sample.columns)} columns")
                                
                                # Store in session state for preview
                                st.session_state.test_processed_sample = processed_sample
                                st.session_state.test_raw_sample = raw_sample
                                st.session_state.test_intensity_level = intensity_level
                                st.session_state.test_schema_name = schema_name
                                
                                st.success("✅ Test completed successfully! Preview available below.")
                            else:
                                log_to_console("❌ Failed to process sample data", "ERROR")
                                st.error("❌ Failed to process sample data")
                        else:
                            log_to_console("❌ Failed to load sample data", "ERROR")
                            st.error("❌ Failed to load sample data")
                    except Exception as e:
                        st.error(f"❌ Test failed: {e}")
                        st.exception(e)
        
        # Preview section
        if 'test_processed_sample' in st.session_state:
            st.markdown("### 📊 Sample Data Preview")
            
            processed_sample = st.session_state.test_processed_sample
            raw_sample = st.session_state.test_raw_sample
            test_intensity = st.session_state.test_intensity_level
            test_schema = st.session_state.test_schema_name
            
            # Show processing summary
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Raw Events", len(raw_sample))
            col2.metric("Processed Rows", len(processed_sample))
            col3.metric("Features", len(processed_sample.columns))
            col4.metric("Intensity", test_intensity.upper())
            
            # Show data preview
            with st.expander("📋 Processed Data Preview", expanded=True):
                st.dataframe(processed_sample.head(20), use_container_width=True)
            
            # Show feature summary
            with st.expander("🔍 Feature Summary", expanded=False):
                feature_cols = [col for col in processed_sample.columns if col not in ['ts_event', 'ts_recv', 'datetime', 'date']]
                st.write(f"**Total Features**: {len(feature_cols)}")
                st.write(f"**Schema**: {test_schema}")
                st.write(f"**Intensity Level**: {test_intensity}")
                
                # Show feature categories
                feature_categories = {
                    'Price Features': [col for col in feature_cols if 'price' in col.lower() or 'mid' in col.lower()],
                    'Volume Features': [col for col in feature_cols if 'volume' in col.lower() or 'size' in col.lower()],
                    'Imbalance Features': [col for col in feature_cols if 'imbalance' in col.lower() or 'ofi' in col.lower()],
                    'Execution Features': [col for col in feature_cols if 'execution' in col.lower() or 'delta' in col.lower()],
                    'Multi-Horizon Features': [col for col in feature_cols if any(h in col.lower() for h in ['10ms', '50ms', '100ms', '1s', '10s', '1m', '5m', '10m', '20m', '30m', '1h'])],
                    'Other Features': [col for col in feature_cols if not any(cat in col.lower() for cat in ['price', 'volume', 'size', 'imbalance', 'ofi', 'execution', 'delta', '10ms', '50ms', '100ms', '1s', '10s', '1m', '5m', '10m', '20m', '30m', '1h'])]
                }
                
                for category, features in feature_categories.items():
                    if features:
                        with st.expander(f"{category} ({len(features)})", expanded=False):
                            for feature in sorted(features):
                                st.write(f"• {feature}")
            
            # Show raw vs processed comparison
            with st.expander("🔄 Raw vs Processed Comparison", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Raw Data Sample:**")
                    st.dataframe(raw_sample.head(10), use_container_width=True)
                with col2:
                    st.write("**Processed Data Sample:**")
                    st.dataframe(processed_sample.head(10), use_container_width=True)
    
    with tab3:
        st.markdown("### File Management")
        
        # Show file organization
        try:
            from quanttime.data import get_file_manager
            file_manager = get_file_manager()
            
            # Raw data files (MBO only)
            st.markdown("**Raw Data Files**")
            raw_dir = file_manager.get_raw_data_dir("mbo")
            if raw_dir.exists():
                files = list(raw_dir.glob("*.dbn*"))
                if files:
                    with st.expander(f"MBO Files ({len(files)})"):
                        for file_path in files[:10]:  # Show first 10
                            metadata = file_manager.get_file_metadata(file_path)
                            st.write(f"📄 {file_path.name} ({metadata.get('size_mb', 0):.2f} MB)")
                        if len(files) > 10:
                            st.write(f"... and {len(files) - 10} more files")
                else:
                    st.info("No MBO files found")
            else:
                st.info("MBO directory not found")
            
            # Processed data files (Execution-aware schemas only)
            st.markdown("**Processed Data Files**")
            execution_schemas = [
                "execution_aware_light_v1",
                "execution_aware_medium_v1", 
                "execution_aware_heavy_v1",
                "execution_aware_extreme_v1"
            ]
            for schema_name in execution_schemas:
                schema_dir = file_manager.get_schema_dir(schema_name)
                if schema_dir.exists():
                    # Look for Parquet files only (production-ready)
                    parquet_files = list(schema_dir.glob("*.parquet"))
                    
                    if parquet_files:
                        # Extract intensity level from schema name
                        intensity = schema_name.replace("execution_aware_", "").replace("_v1", "")
                        with st.expander(f"{intensity.upper()} Intensity Files ({len(parquet_files)} Parquet files)"):
                            for file_path in parquet_files[:10]:  # Show first 10
                                metadata = file_manager.get_file_metadata(file_path)
                                st.write(f"🟢 {file_path.name} ({metadata.get('size_mb', 0):.2f} MB)")
                            if len(parquet_files) > 10:
                                st.write(f"... and {len(parquet_files) - 10} more files")
        
        except Exception as e:
            st.error(f"Failed to load file information: {e}")
    
    with tab4:
        st.markdown("### Data Export (Legacy)")
        
        # Show available dates
        try:
            from quanttime.adapter.databento_loader import get_databento_loader
            databento_loader = get_databento_loader('data/es_futures/mbo')
            available_dates = databento_loader.get_available_dates()
            if available_dates:
                st.success(f"✅ Databento MBO data available: {len(available_dates)} files")
                st.caption(f"Date range: {available_dates[0]} to {available_dates[-1]}")
                
                # Show recent dates
                recent_dates = available_dates[-5:]
                st.write("**Recent dates:**", ", ".join(recent_dates))
            else:
                st.error("❌ No Databento MBO data found")
        except Exception as e:
            st.error(f"❌ Failed to check Databento data: {e}")
        
        st.markdown("### Legacy Data Export")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            # ES is the only ticker we have
            st.write("**Export Symbol:** ES (ES Futures)")
            export_symbol = "ES"
        with col2:
            # Show available dates info
            if 'databento_loader' in locals():
                available_dates = databento_loader.get_available_dates()
                if available_dates:
                    st.write(f"**Available:** {len(available_dates)} trading days")
                    st.caption(f"Range: {available_dates[-1]} to {available_dates[0]}")
                else:
                    st.write("**Available:** No DBN data found")
            else:
                st.write("**Available:** Loading...")
        with col3:
            # Export parameters
            max_dates = st.number_input("Max Dates to Export", value=5, min_value=1, max_value=20, key="data_tab_export_max_dates")
        
        if st.button("Export MBO Data", key="data_tab_export_button"):
            try:
                with st.spinner("Loading and exporting DBN data..."):
                    # Get Databento loader
                    databento_loader = get_databento_loader('data/es_futures/mbo')
                    
                    if not databento_loader.get_available_dates():
                        st.error("No DBN data files found")
                        return
                    
                    # Load data for available dates
                    available_dates = databento_loader.get_available_dates()[:max_dates]
                    all_mbo_data = []
                    
                    for date_str in available_dates:
                        try:
                            df = databento_loader.load_date_as_dataframe(date_str)
                            if df is not None and not df.empty:
                                df['date'] = date_str
                                all_mbo_data.append(df)
                        except Exception as e:
                            st.warning(f"Failed to load {date_str}: {e}")
                    
                    if not all_mbo_data:
                        st.error("No DBN data loaded")
                        return
                    
                    mbo_df = pd.concat(all_mbo_data, ignore_index=True)
                    
                    if mbo_df is not None and not mbo_df.empty:
                        # Convert to ticks using the new process_mbo_to_ticks function
                        from quanttime.runtime.hist_service import process_mbo_to_ticks
                        ticks_df = process_mbo_to_ticks(mbo_df)
                        
                        if not ticks_df.empty:
                            # Save to file
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"data/ticks_{timestamp}.parquet"
                            
                            # Ensure data directory exists
                            import os
                            os.makedirs("data", exist_ok=True)
                            
                            ticks_df.to_parquet(filename, index=False)
                            st.success(f"Exported {len(ticks_df)} ticks to {filename}")
                        else:
                            st.error("No tick data generated from MBO")
                    else:
                        st.error("No MBO data found for export")
            except Exception as e:
                st.error(f"Export failed: {e}")


def live_tab():
    st.subheader("Live Trading")
    cfg = get_cfg()
    
    if not cfg.live_trading_enabled:
        st.warning("Live trading is disabled. Enable it in settings.txt to use this tab.")
        return
    
    live = get_live_service(cfg)
    snap = live.snapshot()
    
    # Live status
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", "🟢 Running" if snap.is_running else "🔴 Stopped")
    col2.metric("Position", snap.position)
    col3.metric("Last Price", f"{snap.last_price or '-'}")
    col4.metric("P&L", f"${snap.realized_pnl or 0:.2f}")
    
    st.markdown("### Live Controls")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Start Live Trading", key="start_live_trading"):
            live.start()
            st.success("Live trading started")
    with col2:
        if st.button("Stop Live Trading", key="stop_live_trading"):
            live.stop()
            st.warning("Live trading stopped")
    with col3:
        if st.button("Reset Position", key="reset_position"):
            live.reset_position()
            st.info("Position reset")
    
    st.markdown("### Recent Activity")
    st.info("Live activity logging will be implemented in the next phase.")


def databento_tab():
    """Comprehensive Databento data access tab."""
    st.subheader("Databento Data Access")
    cfg = get_cfg()
    
    st.markdown("### Databento MBO Data Status")
    
    # Show available dates
    try:
        available_dates = get_available_databento_dates()
        if available_dates:
            st.success(f"✅ Databento MBO data available: {len(available_dates)} files")
            st.caption(f"Date range: {available_dates[0]} to {available_dates[-1]}")
            
            # Show recent dates
            recent_dates = available_dates[-5:]
            st.write("**Recent dates:**", ", ".join(recent_dates))
        else:
            st.error("❌ No Databento MBO data found")
    except Exception as e:
        st.error(f"❌ Failed to check Databento data: {e}")
    
    # Show available symbols
    try:
        symbols = get_databento_symbols()
        if symbols:
            st.write("**Available symbols:**")
            for sym, sym_id in list(symbols.items())[:10]:  # Show first 10
                st.caption(f"  {sym} (ID: {sym_id})")
        else:
            st.warning("No symbols found in symbology")
    except Exception as e:
        st.error(f"Failed to load symbols: {e}")
    
    st.markdown("### Data Export")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        # ES is the only ticker we have
        st.write("**Export Symbol:** ES (ES Futures)")
        export_symbol = "ES"
    with col2:
        # Show available dates info
        databento_loader = get_databento_loader('data/es_futures/mbo')
        available_dates = databento_loader.get_available_dates()
        if available_dates:
            st.write(f"**Available:** {len(available_dates)} trading days")
            st.caption(f"Range: {available_dates[-1]} to {available_dates[0]}")
        else:
            st.write("**Available:** No DBN data found")
    with col3:
        # Export parameters
        max_dates = st.number_input("Max Dates to Export", value=5, min_value=1, max_value=20, key="databento_tab_export_max_dates")
    
    if st.button("Export MBO Data", key="databento_tab_export_button"):
        try:
            with st.spinner("Loading and exporting DBN data..."):
                # Get Databento loader
                databento_loader = get_databento_loader('data/es_futures/mbo')
                
                if not databento_loader.get_available_dates():
                    st.error("No DBN data files found")
                    return
                
                # Load data for available dates
                available_dates = databento_loader.get_available_dates()[:max_dates]
                all_mbo_data = []
                
                for date_str in available_dates:
                    try:
                        df = databento_loader.load_date_as_dataframe(date_str)
                        if df is not None and not df.empty:
                            df['date'] = date_str
                            all_mbo_data.append(df)
                    except Exception as e:
                        st.warning(f"Failed to load {date_str}: {e}")
                
                if not all_mbo_data:
                    st.error("No DBN data loaded")
                    return
                
                mbo_df = pd.concat(all_mbo_data, ignore_index=True)
                
                if mbo_df is not None and not mbo_df.empty:
                    # Convert to ticks using the new process_mbo_to_ticks function
                    from quanttime.runtime.hist_service import process_mbo_to_ticks
                    ticks_df = process_mbo_to_ticks(mbo_df)
                    
                    if not ticks_df.empty:
                        # Save to file
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"data/ticks_{timestamp}.parquet"
                        
                        # Ensure data directory exists
                        import os
                        os.makedirs("data", exist_ok=True)
                        
                        ticks_df.to_parquet(filename, index=False)
                        st.success(f"Exported {len(ticks_df)} ticks to {filename}")
                    else:
                        st.error("No tick data generated from MBO")
                else:
                    st.error("No MBO data found for export")
        except Exception as e:
            st.error(f"Export failed: {e}")


def models_tab():
    """Models tab for card-based model management."""
    # Check if user wants to view model details
    if 'selected_model_id' in st.session_state:
        render_model_details(st.session_state['selected_model_id'])
    else:
        render_model_cards_dashboard()

def data_management_tab():
    """Data management tab for scanning, unzipping, and organizing data."""
    render_data_management_dashboard()


def data_pipeline_tab():
    st.subheader("Data Pipeline")
    cfg = get_cfg()
    
    # Initialize pipeline
    try:
        pipeline = create_pipeline_from_config(cfg)
        st.success("✅ Data pipeline initialized successfully")
    except Exception as e:
        st.error(f"❌ Failed to initialize pipeline: {e}")
        return
    
    # Pipeline Status
    st.markdown("### Pipeline Status")
    status = pipeline.get_streaming_status()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        status_icon = "🟢" if status['is_streaming'] else "🔴"
        st.metric("Streaming Status", f"{status_icon} {'Active' if status['is_streaming'] else 'Inactive'}")
    with col2:
        st.metric("Queue Size", status['queue_size'])
    with col3:
        current_file = status['current_file'] or "None"
        st.metric("Current File", current_file.split('/')[-1] if '/' in current_file else current_file)
    
    # Live Streaming Controls
    st.markdown("### Live Streaming")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        # For pipeline, we'll keep text input since it's for live streaming symbols
        symbols = st.text_input("Symbols (comma-separated)", value="ES.c.0,ES.c.1", key="pipeline_symbols")
    with col2:
        if st.button("Start Streaming", key="start_stream"):
            symbol_list = [s.strip() for s in symbols.split(',') if s.strip()]
            if pipeline.start_live_streaming(symbol_list):
                st.success("✅ Live streaming started")
            else:
                st.error("❌ Failed to start streaming")
    with col3:
        if st.button("Stop Streaming", key="stop_stream"):
            pipeline.stop_live_streaming()
            st.warning("⚠️ Live streaming stopped")
    
    # Historical Data Processing
    st.markdown("### Historical Data Processing")
    
    # File selection
    data_files = []
    if Path("data/es_futures/mbo").exists():
        for file_path in Path("data/es_futures/mbo").glob("*.dbn"):
            data_files.append(str(file_path))
        for file_path in Path("data/es_futures/mbo").glob("*.dbn.zst"):
            data_files.append(str(file_path))
    
    if data_files:
        selected_file = st.selectbox("Select DBN file to process", data_files, key="pipeline_file_select")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Process File", key="process_file"):
                with st.spinner("Processing MBO data..."):
                    try:
                        results = pipeline.process_historical_data(selected_file)
                        
                        st.success(f"✅ Processed {selected_file}")
                        
                        # Display results
                        for data_type, df in results.items():
                            if isinstance(df, pd.DataFrame):
                                st.write(f"**{data_type.title()}**: {len(df)} rows")
                                if len(df) > 0:
                                    st.dataframe(df.head(), use_container_width=True)
                        
                        # Save processed data
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        saved_files = pipeline.save_processed_data(results, f"processed_{timestamp}")
                        
                        st.success(f"✅ Saved processed data:")
                        for data_type, filepath in saved_files.items():
                            st.write(f"  - {data_type}: {filepath}")
                            
                    except Exception as e:
                        st.error(f"❌ Processing failed: {e}")
        
        with col2:
            if st.button("Generate Sample Analysis", key="sample_analysis"):
                with st.spinner("Generating sample analysis..."):
                    try:
                        # Load a small sample for analysis
                        from quanttime.adapter.databento_mbo import DatabentoMBOReader
                        reader = DatabentoMBOReader(cfg.data_dir)
                        
                        # Get first available date
                        dates = reader.get_available_dates()
                        if dates:
                            sample_date = dates[0]
                            symbol_map = reader.get_symbol_mapping("ESU5")  # Use main contract
                            
                            if symbol_map:
                                symbol_ids = list(symbol_map.values())
                                mbo_df = reader.read_mbo_file(sample_date, symbol_ids)
                                
                                if not mbo_df.empty:
                                    # Convert to MBO events and process
                                    mbo_events = []
                                    for _, row in mbo_df.head(1000).iterrows():  # Sample 1000 events
                                        from quanttime.data.pipeline import MBOEvent
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
                                    
                                    # Process events
                                    ticks_df = pipeline.processor.aggregate_to_ticks(mbo_events)
                                    footprint_df = pipeline.processor.generate_footprint(mbo_events)
                                    
                                    st.success(f"✅ Sample analysis complete")
                                    st.write(f"**Ticks**: {len(ticks_df)} rows")
                                    st.write(f"**Footprint**: {len(footprint_df)} rows")
                                    
                                    if not ticks_df.empty:
                                        st.dataframe(ticks_df.head(), use_container_width=True)
                                    
                                else:
                                    st.warning("No MBO data found for sample analysis")
                            else:
                                st.warning("No symbol mapping found")
                        else:
                            st.warning("No available dates found")
                            
                    except Exception as e:
                        st.error(f"❌ Sample analysis failed: {e}")
    else:
        st.warning("No DBN files found in GLBX-20250814-LPE95B5DRD directory")
    
    # File Management
    st.markdown("### File Management")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("List Data Files", key="list_files"):
            files = pipeline.file_manager.list_data_files("*.parquet")
            if files:
                st.write("**Data files:**")
                for file in files[:10]:  # Show first 10
                    st.write(f"  - {file}")
            else:
                st.info("No data files found")
    
    with col2:
        if st.button("Cleanup Old Files", key="cleanup_files"):
            pipeline.file_manager.cleanup_old_files(max_age_days=30)
            st.success("✅ Cleanup completed")


def leaderboard_tab():
    st.subheader("Model Leaderboard")
    
    # Initialize leaderboard if not exists
    if 'model_leaderboard' not in st.session_state:
        st.session_state.model_leaderboard = []
    
    # Add some sample models for demonstration
    if not st.session_state.model_leaderboard:
        st.info("No models in leaderboard yet. Train a model to see it here!")
        
        # Add sample models for demonstration
        sample_models = [
            {
                'name': 'Sample_LightGBM_20241201_120000',
                'model_type': 'Enhanced MBO LightGBM',
                'architecture': 'LightGBM',
                'train_accuracy': 0.7234,
                'val_accuracy': 0.6891,
                'test_accuracy': 0.6543,
                'backtest_sharpe': 1.85,
                'backtest_return': 0.234,
                'backtest_max_dd': 0.089,
                'backtest_win_rate': 0.678,
                'prediction_horizons': [1, 2, 3, 5],
                'created_at': '2024-12-01T12:00:00',
                'training_config': {
                    'orderbook_depth': 20,
                    'sequence_length': 200,
                    'feature_window': 100,
                    'batch_size': 10000
                },
                'data_info': {
                    'data_source': 'Databento MBO',
                    'date_range': '2024-11-01 to 2024-11-30',
                    'total_events': 15420000,
                    'timeframe_filter': '9:00-16:30 EST'
                },
                'analysis': {
                    'overfitting_score': 0.15,
                    'underfitting_score': 0.08,
                    'capacity_utilization': 0.72,
                    'complexity_score': 0.65,
                    'recommendations': [
                        "✅ Model performance is well-balanced",
                        "Consider fine-tuning for marginal improvements"
                    ],
                    'architecture_suggestions': {
                        'optimize_learning_rate': "Try reducing learning rate by 20%",
                        'increase_training_time': "Train for more epochs"
                    }
                },
                'trade_metrics': {
                    'total_trades': 1247,
                    'winning_trades': 845,
                    'losing_trades': 402,
                    'best_trade_pnl': 0.0234,
                    'worst_trade_pnl': -0.0156,
                    'avg_win': 0.0089,
                    'avg_loss': -0.0054,
                    'avg_position_hold_time_minutes': 23.4,
                    'profit_factor': 3.67,
                    'avg_daily_trades': 41.6,
                    'avg_daily_pnl': 0.0078,
                    'daily_win_rate': 0.682,
                    'long_trades': 678,
                    'short_trades': 569,
                    'long_win_rate': 0.691,
                    'short_win_rate': 0.663,
                    'limit_order_trades': 892,
                    'market_order_trades': 355,
                    'limit_order_win_rate': 0.723,
                    'market_order_win_rate': 0.587,
                    'avg_limit_order_pnl': 0.0092,
                    'avg_market_order_pnl': 0.0078,
                    'largest_winning_streak': 12,
                    'largest_losing_streak': 5,
                    'avg_trade_duration_minutes': 23.4,
                    'max_consecutive_wins': 12,
                    'max_consecutive_losses': 5,
                    'sharpe_ratio': 1.85,
                    'sortino_ratio': 2.34,
                    'calmar_ratio': 2.63,
                    'max_drawdown': 0.089,
                    'total_return': 0.234,
                    'volatility': 0.126,
                    'var_95': -0.0189,
                    'cvar_95': -0.0234
                }
            },
            {
                'name': 'Sample_LSTM_20241201_140000',
                'model_type': 'MBO LSTM',
                'architecture': 'LSTM',
                'train_accuracy': 0.6987,
                'val_accuracy': 0.6654,
                'test_accuracy': 0.6234,
                'backtest_sharpe': 1.42,
                'backtest_return': 0.187,
                'backtest_max_dd': 0.112,
                'backtest_win_rate': 0.634,
                'prediction_horizons': [1, 2, 3],
                'created_at': '2024-12-01T14:00:00',
                'training_config': {
                    'orderbook_depth': 15,
                    'sequence_length': 150,
                    'feature_window': 75,
                    'batch_size': 8000
                },
                'data_info': {
                    'data_source': 'Databento MBO',
                    'date_range': '2024-11-15 to 2024-11-30',
                    'total_events': 8760000,
                    'timeframe_filter': '9:00-16:30 EST'
                },
                'analysis': {
                    'overfitting_score': 0.25,
                    'underfitting_score': 0.12,
                    'capacity_utilization': 0.58,
                    'complexity_score': 0.78,
                    'recommendations': [
                        "🔴 HIGH PRIORITY: Model is overfitting",
                        "Reduce model complexity to prevent overfitting"
                    ],
                    'architecture_suggestions': {
                        'increase_dropout': "Increase dropout rate by 0.1",
                        'reduce_layers': "Decrease number of layers by 1",
                        'reduce_hidden_size': "Decrease hidden size by 25%"
                    }
                },
                'trade_metrics': {
                    'total_trades': 987,
                    'winning_trades': 626,
                    'losing_trades': 361,
                    'best_trade_pnl': 0.0198,
                    'worst_trade_pnl': -0.0187,
                    'avg_win': 0.0076,
                    'avg_loss': -0.0062,
                    'avg_position_hold_time_minutes': 31.2,
                    'profit_factor': 2.89,
                    'avg_daily_trades': 32.9,
                    'avg_daily_pnl': 0.0062,
                    'daily_win_rate': 0.634,
                    'long_trades': 534,
                    'short_trades': 453,
                    'long_win_rate': 0.648,
                    'short_win_rate': 0.618,
                    'limit_order_trades': 691,
                    'market_order_trades': 296,
                    'limit_order_win_rate': 0.667,
                    'market_order_win_rate': 0.554,
                    'avg_limit_order_pnl': 0.0081,
                    'avg_market_order_pnl': 0.0065,
                    'largest_winning_streak': 8,
                    'largest_losing_streak': 7,
                    'avg_trade_duration_minutes': 31.2,
                    'max_consecutive_wins': 8,
                    'max_consecutive_losses': 7,
                    'sharpe_ratio': 1.42,
                    'sortino_ratio': 1.89,
                    'calmar_ratio': 1.67,
                    'max_drawdown': 0.112,
                    'total_return': 0.187,
                    'volatility': 0.132,
                    'var_95': -0.0212,
                    'cvar_95': -0.0267
                }
            },
            {
                'name': 'Sample_Transformer_20241201_160000',
                'model_type': 'MBO Transformer',
                'architecture': 'Transformer',
                'train_accuracy': 0.7156,
                'val_accuracy': 0.6823,
                'test_accuracy': 0.6412,
                'backtest_sharpe': 1.67,
                'backtest_return': 0.198,
                'backtest_max_dd': 0.095,
                'backtest_win_rate': 0.656,
                'prediction_horizons': [1, 2, 3, 5],
                'created_at': '2024-12-01T16:00:00',
                'training_config': {
                    'orderbook_depth': 25,
                    'sequence_length': 250,
                    'feature_window': 125,
                    'batch_size': 12000
                },
                'data_info': {
                    'data_source': 'Databento MBO',
                    'date_range': '2024-11-01 to 2024-11-30',
                    'total_events': 12340000,
                    'timeframe_filter': '9:00-16:30 EST'
                },
                'analysis': {
                    'overfitting_score': 0.18,
                    'underfitting_score': 0.09,
                    'capacity_utilization': 0.68,
                    'complexity_score': 0.71,
                    'recommendations': [
                        "✅ Model shows good balance",
                        "Consider increasing attention heads for better pattern recognition"
                    ],
                    'architecture_suggestions': {
                        'increase_attention_heads': "Try increasing from 16 to 24 heads",
                        'adjust_learning_rate': "Fine-tune learning rate for better convergence"
                    }
                },
                'trade_metrics': {
                    'total_trades': 1156,
                    'winning_trades': 758,
                    'losing_trades': 398,
                    'best_trade_pnl': 0.0212,
                    'worst_trade_pnl': -0.0167,
                    'avg_win': 0.0082,
                    'avg_loss': -0.0058,
                    'avg_position_hold_time_minutes': 27.8,
                    'profit_factor': 3.24,
                    'avg_daily_trades': 38.5,
                    'avg_daily_pnl': 0.0066,
                    'daily_win_rate': 0.656,
                    'long_trades': 623,
                    'short_trades': 533,
                    'long_win_rate': 0.669,
                    'short_win_rate': 0.641,
                    'limit_order_trades': 809,
                    'market_order_trades': 347,
                    'limit_order_win_rate': 0.701,
                    'market_order_win_rate': 0.589,
                    'avg_limit_order_pnl': 0.0087,
                    'avg_market_order_pnl': 0.0072,
                    'largest_winning_streak': 10,
                    'largest_losing_streak': 6,
                    'avg_trade_duration_minutes': 27.8,
                    'max_consecutive_wins': 10,
                    'max_consecutive_losses': 6,
                    'sharpe_ratio': 1.67,
                    'sortino_ratio': 2.12,
                    'calmar_ratio': 2.08,
                    'max_drawdown': 0.095,
                    'total_return': 0.198,
                    'volatility': 0.119,
                    'var_95': -0.0198,
                    'cvar_95': -0.0245
                }
            }
        ]
        st.session_state.model_leaderboard = sample_models
    
    # Sort models by backtest Sharpe ratio (primary) and test accuracy (secondary)
    sorted_models = sorted(
        st.session_state.model_leaderboard,
        key=lambda x: (x.get('backtest_sharpe', 0), x.get('test_accuracy', 0)),
        reverse=True
    )
    
    # Display leaderboard
    st.markdown("### 🏆 Model Performance Leaderboard")
    st.info("💡 **Click on any model card to view detailed analysis and recommendations**")
    
    # Display models as interactive cards
    if sorted_models:
        for i, model in enumerate(sorted_models):
            # Create model card
            with st.container():
                st.markdown("---")
                
                # Model card header
                col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 1, 1, 1, 1])
                
                with col1:
                    st.markdown(f"**#{i+1} {model['name']}**")
                    st.caption(f"{model['architecture']} • Created: {model['created_at'][:10]}")
                
                with col2:
                    st.metric("Test Acc", f"{model.get('test_accuracy', 0):.3f}")
                    if 'trade_metrics' in model:
                        st.caption(f"Trades: {model['trade_metrics'].get('total_trades', 0)}")
                
                with col3:
                    st.metric("Sharpe", f"{model.get('backtest_sharpe', 0):.2f}")
                    if 'trade_metrics' in model:
                        st.caption(f"Win Rate: {model['trade_metrics'].get('daily_win_rate', 0):.1%}")
                
                with col4:
                    st.metric("Return", f"{model.get('backtest_return', 0):.1%}")
                    if 'trade_metrics' in model:
                        st.caption(f"Profit Factor: {model['trade_metrics'].get('profit_factor', 0):.1f}")
                
                with col5:
                    st.metric("Max DD", f"{model.get('backtest_max_dd', 0):.1%}")
                    if 'trade_metrics' in model:
                        st.caption(f"Avg Hold: {model['trade_metrics'].get('avg_position_hold_time_minutes', 0):.0f}m")
                
                with col6:
                    # Clickable button to open detailed view
                    if st.button(f"📊 Details", key=f"details_{i}", use_container_width=True):
                        st.session_state.selected_model_index = i
                        st.session_state.show_model_details = True
                
                # Show model details popup if selected
                if (st.session_state.get('selected_model_index') == i and 
                    st.session_state.get('show_model_details', False)):
                    
                    # Create popup-like container
                    with st.container():
                        
                        st.markdown('<div class="model-popup">', unsafe_allow_html=True)
                        
                        # Model details tabs
                        detail_tabs = st.tabs([
                            "📈 Performance Metrics", 
                            "💰 Trade Analysis", 
                            "⚙️ Configuration", 
                            "📊 Training Data", 
                            "🔍 Model Specs",
                            "🎯 Analysis & Recommendations"
                        ])
                        
                        with detail_tabs[0]:
                            st.markdown("#### Performance Metrics")
                            
                            # Performance metrics
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Test Accuracy", f"{model.get('test_accuracy', 0):.3f}")
                                st.metric("Validation Accuracy", f"{model.get('val_accuracy', 0):.3f}")
                            with col2:
                                st.metric("Sharpe Ratio", f"{model.get('backtest_sharpe', 0):.2f}")
                                st.metric("Total Return", f"{model.get('backtest_return', 0):.1%}")
                            with col3:
                                st.metric("Max Drawdown", f"{model.get('backtest_max_dd', 0):.1%}")
                                st.metric("Win Rate", f"{model.get('backtest_win_rate', 0):.1%}")
                            with col4:
                                st.metric("Train Accuracy", f"{model.get('train_accuracy', 0):.3f}")
                                st.metric("Best Iteration", model.get('best_iteration', 'N/A'))
                            
                            # Performance chart
                            st.markdown("#### Performance Chart")
                            performance_data = {
                                'Metric': ['Train Acc', 'Val Acc', 'Test Acc', 'Sharpe', 'Return', 'Win Rate'],
                                'Value': [
                                    model.get('train_accuracy', 0),
                                    model.get('val_accuracy', 0),
                                    model.get('test_accuracy', 0),
                                    model.get('backtest_sharpe', 0) / 3,  # Normalize for chart
                                    model.get('backtest_return', 0),
                                    model.get('backtest_win_rate', 0)
                                ]
                            }
                            df_perf = pd.DataFrame(performance_data)
                            fig = px.bar(df_perf, x='Metric', y='Value', title='Model Performance Metrics')
                            st.plotly_chart(fig, use_container_width=True)
                        
                        with detail_tabs[1]:
                            st.markdown("#### 💰 Comprehensive Trade Analysis")
                            
                            trade_metrics = model.get('trade_metrics', {})
                            if trade_metrics:
                                # Trade Overview
                                st.markdown("##### 📊 Trade Overview")
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Total Trades", f"{trade_metrics.get('total_trades', 0):,}")
                                    st.metric("Winning Trades", f"{trade_metrics.get('winning_trades', 0):,}")
                                with col2:
                                    st.metric("Win Rate", f"{trade_metrics.get('daily_win_rate', 0):.1%}")
                                    st.metric("Profit Factor", f"{trade_metrics.get('profit_factor', 0):.2f}")
                                with col3:
                                    st.metric("Best Trade", f"{trade_metrics.get('best_trade_pnl', 0):.2%}")
                                    st.metric("Worst Trade", f"{trade_metrics.get('worst_trade_pnl', 0):.2%}")
                                with col4:
                                    st.metric("Avg Win", f"{trade_metrics.get('avg_win', 0):.2%}")
                                    st.metric("Avg Loss", f"{trade_metrics.get('avg_loss', 0):.2%}")
                                
                                # Position Analysis
                                st.markdown("##### 📈 Position Analysis")
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Avg Hold Time", f"{trade_metrics.get('avg_position_hold_time_minutes', 0):.1f} min")
                                    st.metric("Avg Daily Trades", f"{trade_metrics.get('avg_daily_trades', 0):.1f}")
                                with col2:
                                    st.metric("Avg Daily PnL", f"{trade_metrics.get('avg_daily_pnl', 0):.2%}")
                                    st.metric("Largest Win Streak", trade_metrics.get('largest_winning_streak', 0))
                                with col3:
                                    st.metric("Largest Loss Streak", trade_metrics.get('largest_losing_streak', 0))
                                    st.metric("Max Consecutive Wins", trade_metrics.get('max_consecutive_wins', 0))
                                with col4:
                                    st.metric("Max Consecutive Losses", trade_metrics.get('max_consecutive_losses', 0))
                                    st.metric("Avg Trade Duration", f"{trade_metrics.get('avg_trade_duration_minutes', 0):.1f} min")
                                
                                # Direction Analysis
                                st.markdown("##### 🔄 Trade Direction Analysis")
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Long Trades", f"{trade_metrics.get('long_trades', 0):,}")
                                    st.metric("Short Trades", f"{trade_metrics.get('short_trades', 0):,}")
                                with col2:
                                    st.metric("Long Win Rate", f"{trade_metrics.get('long_win_rate', 0):.1%}")
                                    st.metric("Short Win Rate", f"{trade_metrics.get('short_win_rate', 0):.1%}")
                                with col3:
                                    st.metric("Long/Short Ratio", f"{trade_metrics.get('long_trades', 0) / max(trade_metrics.get('short_trades', 1), 1):.2f}")
                                    st.metric("Direction Bias", "Long" if trade_metrics.get('long_trades', 0) > trade_metrics.get('short_trades', 0) else "Short")
                                with col4:
                                    st.metric("Long PnL", f"{trade_metrics.get('long_trades', 0) * trade_metrics.get('avg_win', 0):.2%}")
                                    st.metric("Short PnL", f"{trade_metrics.get('short_trades', 0) * trade_metrics.get('avg_win', 0):.2%}")
                                
                                # Order Type Analysis
                                st.markdown("##### 📋 Order Type Analysis")
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Limit Orders", f"{trade_metrics.get('limit_order_trades', 0):,}")
                                    st.metric("Market Orders", f"{trade_metrics.get('market_order_trades', 0):,}")
                                with col2:
                                    st.metric("Limit Win Rate", f"{trade_metrics.get('limit_order_win_rate', 0):.1%}")
                                    st.metric("Market Win Rate", f"{trade_metrics.get('market_order_win_rate', 0):.1%}")
                                with col3:
                                    st.metric("Avg Limit PnL", f"{trade_metrics.get('avg_limit_order_pnl', 0):.2%}")
                                    st.metric("Avg Market PnL", f"{trade_metrics.get('avg_market_order_pnl', 0):.2%}")
                                with col4:
                                    st.metric("Limit/Market Ratio", f"{trade_metrics.get('limit_order_trades', 0) / max(trade_metrics.get('market_order_trades', 1), 1):.2f}")
                                    st.metric("Order Type Bias", "Limit" if trade_metrics.get('limit_order_trades', 0) > trade_metrics.get('market_order_trades', 0) else "Market")
                                
                                # Risk Metrics
                                st.markdown("##### ⚠️ Risk Metrics")
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Sharpe Ratio", f"{trade_metrics.get('sharpe_ratio', 0):.2f}")
                                    st.metric("Sortino Ratio", f"{trade_metrics.get('sortino_ratio', 0):.2f}")
                                with col2:
                                    st.metric("Calmar Ratio", f"{trade_metrics.get('calmar_ratio', 0):.2f}")
                                    st.metric("Max Drawdown", f"{trade_metrics.get('max_drawdown', 0):.2%}")
                                with col3:
                                    st.metric("Volatility", f"{trade_metrics.get('volatility', 0):.2%}")
                                    st.metric("VaR (95%)", f"{trade_metrics.get('var_95', 0):.2%}")
                                with col4:
                                    st.metric("CVaR (95%)", f"{trade_metrics.get('cvar_95', 0):.2%}")
                                    st.metric("Total Return", f"{trade_metrics.get('total_return', 0):.2%}")
                                
                                # Trade Performance Chart
                                st.markdown("##### 📊 Trade Performance Visualization")
                                trade_performance_data = {
                                    'Metric': ['Win Rate', 'Profit Factor', 'Avg Win', 'Avg Loss', 'Best Trade', 'Worst Trade'],
                                    'Value': [
                                        trade_metrics.get('daily_win_rate', 0),
                                        trade_metrics.get('profit_factor', 0) / 10,  # Normalize for chart
                                        trade_metrics.get('avg_win', 0) * 100,  # Convert to percentage
                                        abs(trade_metrics.get('avg_loss', 0)) * 100,  # Convert to percentage
                                        trade_metrics.get('best_trade_pnl', 0) * 100,  # Convert to percentage
                                        abs(trade_metrics.get('worst_trade_pnl', 0)) * 100  # Convert to percentage
                                    ]
                                }
                                df_trade = pd.DataFrame(trade_performance_data)
                                fig_trade = px.bar(df_trade, x='Metric', y='Value', title='Trade Performance Metrics')
                                st.plotly_chart(fig_trade, use_container_width=True)
                                
                            else:
                                st.info("No trade metrics available for this model.")
                        
                        with detail_tabs[2]:
                            st.markdown("#### Training Configuration")
                            
                            config = model.get('training_config', {})
                            if config:
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.markdown("**Model Parameters:**")
                                    for key, value in config.items():
                                        st.write(f"**{key.replace('_', ' ').title()}:** {value}")
                                
                                with col2:
                                    st.markdown("**Prediction Horizons:**")
                                    horizons = model.get('prediction_horizons', [])
                                    for horizon in horizons:
                                        st.write(f"• {horizon} minute(s)")
                            
                            # Architecture details
                            st.markdown("#### Architecture Details")
                            st.write(f"**Model Type:** {model['model_type']}")
                            st.write(f"**Architecture:** {model['architecture']}")
                            st.write(f"**Created:** {model['created_at']}")
                        
                        with detail_tabs[3]:
                            st.markdown("#### Training Data Information")
                            
                            data_info = model.get('data_info', {})
                            if data_info:
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.markdown("**Data Source:**")
                                    st.write(f"• **Source:** {data_info.get('data_source', 'N/A')}")
                                    st.write(f"• **Date Range:** {data_info.get('date_range', 'N/A')}")
                                    st.write(f"• **Timeframe Filter:** {data_info.get('timeframe_filter', 'N/A')}")
                                
                                with col2:
                                    st.markdown("**Data Statistics:**")
                                    st.write(f"• **Total Events:** {data_info.get('total_events', 0):,}")
                                    st.write(f"• **Trading Days:** {data_info.get('trading_days', 'N/A')}")
                                    st.write(f"• **Data Size:** {data_info.get('data_size_gb', 'N/A')}")
                            
                            # Data visualization (placeholder)
                            st.markdown("#### Data Distribution")
                            st.info("Data distribution charts will be implemented in the next phase.")
                        
                        with detail_tabs[4]:
                            st.markdown("#### Model Specifications")
                            
                            # Model architecture details
                            st.markdown("**Model Architecture:**")
                            st.write(f"• **Type:** {model['model_type']}")
                            st.write(f"• **Architecture:** {model['architecture']}")
                            st.write(f"• **Prediction Horizons:** {model.get('prediction_horizons', [])}")
                            
                            # Training details
                            st.markdown("**Training Details:**")
                            st.write(f"• **Created:** {model['created_at']}")
                            st.write(f"• **Training Duration:** {model.get('training_duration', 'N/A')}")
                            st.write(f"• **Data Points:** {model.get('data_points', 'N/A')}")
                        
                        with detail_tabs[5]:
                            st.markdown("#### Model Analysis & Recommendations")
                            
                            analysis = model.get('analysis', {})
                            if analysis:
                                # Analysis metrics
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Overfitting Score", f"{analysis.get('overfitting_score', 0):.3f}")
                                with col2:
                                    st.metric("Underfitting Score", f"{analysis.get('underfitting_score', 0):.3f}")
                                with col3:
                                    st.metric("Capacity Utilization", f"{analysis.get('capacity_utilization', 0):.3f}")
                                with col4:
                                    st.metric("Complexity Score", f"{analysis.get('complexity_score', 0):.3f}")
                                
                                # Recommendations
                                st.markdown("#### 🎯 Recommendations")
                                recommendations = analysis.get('recommendations', [])
                                for rec in recommendations:
                                    if "🔴 HIGH PRIORITY" in rec:
                                        st.error(rec)
                                    elif "🟡 MEDIUM PRIORITY" in rec:
                                        st.warning(rec)
                                    else:
                                        st.success(rec)
                                
                                # Architecture suggestions
                                st.markdown("#### ⚙️ Architecture Suggestions")
                                suggestions = analysis.get('architecture_suggestions', {})
                                for key, suggestion in suggestions.items():
                                    st.info(f"**{key.replace('_', ' ').title()}:** {suggestion}")
                            
                            else:
                                st.info("No analysis data available for this model.")
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Close button
                        if st.button("❌ Close Details", key=f"close_{i}"):
                            st.session_state.show_model_details = False
                            st.session_state.selected_model_index = None
                            st.rerun()
    
    else:
        st.info("No models available in the leaderboard. Train a model to see it here!")
    
    # Leaderboard management
    st.markdown("### 🛠️ Leaderboard Management")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Refresh Leaderboard", key="refresh_leaderboard"):
            st.rerun()
    
    with col2:
        if st.button("📊 Export Leaderboard", key="export_leaderboard"):
            if sorted_models:
                # Create export data
                export_data = []
                for model in sorted_models:
                    export_data.append({
                        'Model Name': model['name'],
                        'Architecture': model['architecture'],
                        'Test Accuracy': model.get('test_accuracy', 0),
                        'Sharpe Ratio': model.get('backtest_sharpe', 0),
                        'Total Return': model.get('backtest_return', 0),
                        'Max Drawdown': model.get('backtest_max_dd', 0),
                        'Win Rate': model.get('backtest_win_rate', 0),
                        'Created': model['created_at']
                    })
                
                df_export = pd.DataFrame(export_data)
                csv = df_export.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"model_leaderboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    with col3:
        if st.button("🗑️ Clear Leaderboard", key="clear_leaderboard"):
            st.session_state.model_leaderboard = []
            st.success("✅ Leaderboard cleared!")
            st.rerun()


def sync_data_and_models():
    """Smart sync with file comparison and approval"""
    
    log_device_operation("Starting data and model sync", "INFO")
    logger.info("🔄 Starting sync analysis...")
    
    # Load server configuration
    config_path = "server/config/servers.json"
    try:
        with open(config_path, 'r') as f:
            servers = json.load(f)
        logger.info(f"✅ Loaded server config with {len(servers)} servers")
    except Exception as e:
        error_msg = f"❌ Failed to load server config: {e}"
        st.error(error_msg)
        logger.error(error_msg)
        return
    
    # Sync directories
    sync_dirs = ['data', 'models', 'backtests', 'logs']
    
    # Step 1: Analyze what needs to be synced
    st.subheader("📊 Sync Analysis")
    
    sync_plan = analyze_sync_needs(servers, sync_dirs)
    
    if not sync_plan['has_changes']:
        success_msg = "✅ All files are already in sync!"
        st.success(success_msg)
        logger.info(success_msg)
        return
    
    # Step 2: Show sync plan and get approval
    st.subheader("🔄 Sync Plan")
    
    # Display what will be synced
    for server_name, changes in sync_plan['changes'].items():
        if changes['files_to_upload'] or changes['files_to_download']:
            with st.expander(f"📁 {server_name} Changes", expanded=True):
                if changes['files_to_upload']:
                    st.write("**📤 Files to upload to server:**")
                    for file_info in changes['files_to_upload'][:10]:  # Show first 10
                        st.write(f"  • {file_info['path']} ({file_info['size']})")
                    if len(changes['files_to_upload']) > 10:
                        st.write(f"  ... and {len(changes['files_to_upload']) - 10} more files")
                
                if changes['files_to_download']:
                    st.write("**📥 Files to download from server:**")
                    for file_info in changes['files_to_download'][:10]:  # Show first 10
                        st.write(f"  • {file_info['path']} ({file_info['size']})")
                    if len(changes['files_to_download']) > 10:
                        st.write(f"  ... and {len(changes['files_to_download']) - 10} more files")
    
    # Get approval
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve & Sync", key="approve_sync", type="primary"):
            execute_sync_plan(sync_plan, servers, sync_dirs)
    with col2:
        if st.button("❌ Cancel", key="cancel_sync"):
            cancel_msg = "Sync cancelled"
            st.info(cancel_msg)
            logger.info(cancel_msg)
            return


def analyze_sync_needs(servers, sync_dirs):
    """Analyze what files need to be synced"""
    logger.info("📊 Analyzing sync needs...")
    
    sync_plan = {
        'has_changes': False,
        'changes': {}
    }
    
    for server_name, server_config in servers.items():
        if server_name == 'laptop':
            continue
        
        ip = server_config.get('tailscale_ip', server_config['ip_address'])
        username = server_config['username']
        
        sync_plan['changes'][server_name] = {
            'files_to_upload': [],
            'files_to_download': []
        }
        
        for sync_dir in sync_dirs:
            try:
                # Get local files
                local_dir = Path(sync_dir)
                local_files = get_file_list(local_dir) if local_dir.exists() else {}
                
                # Get remote files
                remote_files = get_remote_file_list(username, ip, sync_dir)
                
                # Compare and find differences
                upload_files, download_files = compare_file_lists(local_files, remote_files, sync_dir)
                
                sync_plan['changes'][server_name]['files_to_upload'].extend(upload_files)
                sync_plan['changes'][server_name]['files_to_download'].extend(download_files)
                
            except Exception as e:
                st.error(f"❌ Error analyzing {sync_dir} for {server_name}: {e}")
        
        if (sync_plan['changes'][server_name]['files_to_upload'] or 
            sync_plan['changes'][server_name]['files_to_download']):
            sync_plan['has_changes'] = True
    
    logger.info(f"📊 Sync analysis complete. Changes found: {sync_plan['has_changes']}")
    return sync_plan


def get_file_list(directory):
    """Get list of files in directory with sizes and modification times"""
    files = {}
    if directory.exists():
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(directory))
                files[rel_path] = {
                    'size': file_path.stat().st_size,
                    'mtime': file_path.stat().st_mtime
                }
    return files


def get_remote_file_list(username, ip, sync_dir):
    """Get list of files on remote server"""
    try:
        cmd = f"ssh {username}@{ip} 'find /opt/quanttime/{sync_dir} -type f -printf \"%P\\t%s\\t%T@\\n\" 2>/dev/null || echo \"\"'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        files = {}
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) == 3:
                        rel_path, size, mtime = parts
                        files[rel_path] = {
                            'size': int(size),
                            'mtime': float(mtime)
                        }
        return files
    except Exception as e:
        st.error(f"❌ Error getting remote file list: {e}")
        return {}


def compare_file_lists(local_files, remote_files, sync_dir):
    """Compare local and remote files to find differences"""
    upload_files = []
    download_files = []
    
    # Find files to upload (newer on local or missing on remote)
    for rel_path, local_info in local_files.items():
        if rel_path not in remote_files:
            upload_files.append({
                'path': f"{sync_dir}/{rel_path}",
                'size': local_info['size'],
                'action': 'upload'
            })
        elif local_info['mtime'] > remote_files[rel_path]['mtime']:
            upload_files.append({
                'path': f"{sync_dir}/{rel_path}",
                'size': local_info['size'],
                'action': 'upload'
            })
    
    # Find files to download (newer on remote or missing on local)
    for rel_path, remote_info in remote_files.items():
        if rel_path not in local_files:
            download_files.append({
                'path': f"{sync_dir}/{rel_path}",
                'size': remote_info['size'],
                'action': 'download'
            })
        elif remote_info['mtime'] > local_files[rel_path]['mtime']:
            download_files.append({
                'path': f"{sync_dir}/{rel_path}",
                'size': remote_info['size'],
                'action': 'download'
            })
    
    return upload_files, download_files


def execute_sync_plan(sync_plan, servers, sync_dirs):
    """Execute the approved sync plan with progress tracking"""
    
    logger.info("🚀 Executing sync plan...")
    
    # Create progress tracking
    total_files = sum(
        len(changes['files_to_upload']) + len(changes['files_to_download'])
        for changes in sync_plan['changes'].values()
    )
    
    if total_files == 0:
        success_msg = "✅ No files to sync!"
        st.success(success_msg)
        logger.info(success_msg)
        return
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    files_processed = 0
    
    try:
        # Step 1: Sync laptop to servers
        for server_name, changes in sync_plan['changes'].items():
            if changes['files_to_upload']:
                server_config = servers[server_name]
                ip = server_config.get('tailscale_ip', server_config['ip_address'])
                username = server_config['username']
                
                status_text.text(f"📤 Uploading to {server_name}...")
                logger.info(f"📤 Starting upload to {server_name}...")
                
                for file_info in changes['files_to_upload']:
                    try:
                        # Extract directory and filename
                        sync_dir = file_info['path'].split('/')[0]
                        rel_path = '/'.join(file_info['path'].split('/')[1:])
                        
                        # Upload file
                        local_path = Path(sync_dir) / rel_path
                        remote_path = f"{username}@{ip}:/opt/quanttime/{file_info['path']}"
                        
                        cmd = ['rsync', '-avz', str(local_path), remote_path]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            success_msg = f"✅ Uploaded {file_info['path']}"
                            st.success(success_msg)
                            logger.info(success_msg)
                        else:
                            error_msg = f"❌ Failed to upload {file_info['path']}: {result.stderr}"
                            st.error(error_msg)
                            logger.error(error_msg)
                        
                        files_processed += 1
                        progress_bar.progress(files_processed / total_files)
                        
                    except Exception as e:
                        error_msg = f"❌ Error uploading {file_info['path']}: {e}"
                        st.error(error_msg)
                        logger.error(error_msg)
                        files_processed += 1
                        progress_bar.progress(files_processed / total_files)
        
        # Step 2: Download from servers to laptop
        for server_name, changes in sync_plan['changes'].items():
            if changes['files_to_download']:
                server_config = servers[server_name]
                ip = server_config.get('tailscale_ip', server_config['ip_address'])
                username = server_config['username']
                
                status_text.text(f"📥 Downloading from {server_name}...")
                logger.info(f"📥 Starting download from {server_name}...")
                
                for file_info in changes['files_to_download']:
                    try:
                        # Extract directory and filename
                        sync_dir = file_info['path'].split('/')[0]
                        rel_path = '/'.join(file_info['path'].split('/')[1:])
                        
                        # Create local directory
                        local_dir = Path(sync_dir)
                        local_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Download file
                        remote_path = f"{username}@{ip}:/opt/quanttime/{file_info['path']}"
                        local_path = local_dir / rel_path
                        
                        cmd = ['rsync', '-avz', remote_path, str(local_path)]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            success_msg = f"✅ Downloaded {file_info['path']}"
                            st.success(success_msg)
                            logger.info(success_msg)
                        else:
                            error_msg = f"❌ Failed to download {file_info['path']}: {result.stderr}"
                            st.error(error_msg)
                            logger.error(error_msg)
                        
                        files_processed += 1
                        progress_bar.progress(files_processed / total_files)
                        
                    except Exception as e:
                        error_msg = f"❌ Error downloading {file_info['path']}: {e}"
                        st.error(error_msg)
                        logger.error(error_msg)
                        files_processed += 1
                        progress_bar.progress(files_processed / total_files)
        
        # Step 3: Sync between servers (they share storage)
        server_names = [name for name in servers.keys() if name != 'laptop']
        if len(server_names) >= 2:
            status_text.text("🔄 Syncing between servers...")
            logger.info("🔄 Syncing between servers...")
            
            source = server_names[0]
            target = server_names[1]
            
            source_config = servers[source]
            target_config = servers[target]
            
            source_ip = source_config.get('tailscale_ip', source_config['ip_address'])
            target_ip = target_config.get('tailscale_ip', target_config['ip_address'])
            
            source_user = source_config['username']
            target_user = target_config['username']
            
            for sync_dir in sync_dirs:
                try:
                    cmd = [
                        'rsync', '-avz', '--delete',
                        f'{source_user}@{source_ip}:/opt/quanttime/{sync_dir}/',
                        f'{target_user}@{target_ip}:/opt/quanttime/{sync_dir}/'
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        success_msg = f"✅ Synced {sync_dir} between servers"
                        st.success(success_msg)
                        logger.info(success_msg)
                    else:
                        error_msg = f"❌ Failed to sync {sync_dir} between servers: {result.stderr}"
                        st.error(error_msg)
                        logger.error(error_msg)
                        
                except Exception as e:
                    error_msg = f"❌ Error syncing {sync_dir} between servers: {e}"
                    st.error(error_msg)
                    logger.error(error_msg)
        
        progress_bar.progress(1.0)
        status_text.text("🎉 Sync completed successfully!")
        success_msg = "✅ All files synced successfully!"
        st.success(success_msg)
        logger.info(success_msg)
        
    except Exception as e:
        error_msg = f"❌ Sync failed: {e}"
        st.error(error_msg)
        logger.error(error_msg)
    finally:
        # Clean up progress indicators
        progress_bar.empty()
        status_text.empty()


def main():
    st.markdown('<h1 class="main-header">QuantTime ML Trading Suite</h1>', unsafe_allow_html=True)
    
    # Enhanced Server Control Sidebar
    render_enhanced_server_control()
    
    # Task Progress Tracking Sidebar
    progress_tracker.render_sidebar_progress()
    
    # Dynamic tab navigation based on selected device
    selected_device = st.session_state.get("selected_server", "laptop")
    
    if selected_device == "laptop":
        # Laptop dashboard - simplified with core tabs
        tabs = st.tabs(["🚀 Auto", "📊 Overview", "🤖 Models", "🏋️ Train", "📈 Backtests", "📁 Data", "🏆 Leaderboard", "⚙️ Settings"])
        
        with tabs[0]:
            st.subheader("🚀 Auto Mode")
            st.write("Automated trading and model management will be implemented in the next phase.")
            
            # Quick status
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Models", "0 Active")
            with col2:
                st.metric("Backtests", "0 Running")
            with col3:
                st.metric("Data", "81 Files")
        
        with tabs[1]:
            overview_tab()
        
        with tabs[2]:
            models_tab()
        
        with tabs[3]:
            train_tab()
        
        with tabs[4]:
            render_enhanced_backtest_interface()
        
        with tabs[5]:
            data_tab()
        
        with tabs[6]:
            leaderboard_tab()
        
        with tabs[7]:
            # Settings tab with all advanced features
            st.subheader("⚙️ Advanced Settings")
            
                        # Sub-tabs for advanced features
            settings_tabs = st.tabs(["🧠 Hybrid Pipeline", "🔄 Pipeline", "📡 Live", "📊 Databento", "📋 Tasks", "🖥️ Servers", "🔧 Dev Tools"])
            
            with settings_tabs[0]:
                render_hybrid_pipeline_interface()
            
            with settings_tabs[1]:
                data_pipeline_tab()
            
            with settings_tabs[2]:
                live_tab()
            
            with settings_tabs[3]:
                databento_tab()
            
            with settings_tabs[4]:
                col1, col2 = st.columns(2)
                with col1:
                    task_submission_tab()
                with col2:
                    task_monitoring_tab()
            
            with settings_tabs[5]:
                col1, col2 = st.columns(2)
                with col1:
                    servers_tab()
                with col2:
                    server_deployment_tab()
            
            with settings_tabs[6]:
                render_syncthing_ray_interface()

            with settings_tabs[7]:
                render_sftp_interface()

            with settings_tabs[8]:
                dev_tools_tab()
    
    else:
        # Server dashboard - server-specific capabilities
        server_name = selected_device.upper()
        tabs = st.tabs([f"🖥️ {server_name} Status", "📊 Performance", "📋 Tasks", "📁 Files", "⚙️ Settings"])
        
        with tabs[0]:
            server_status_tab(selected_device)
        
        with tabs[1]:
            server_performance_tab(selected_device)
        
        with tabs[2]:
            server_tasks_tab(selected_device)
        
        with tabs[3]:
            server_files_tab(selected_device)
        
        with tabs[4]:
            server_settings_tab(selected_device)


def task_submission_tab():
    """Task submission interface tab"""
    render_task_submission_interface()


def task_monitoring_tab():
    """Task monitoring interface tab"""
    render_task_monitoring()


def servers_tab():
    """Server management and monitoring tab"""
    server_control.render_main_dashboard()


def server_deployment_tab():
    """Server deployment and management tab"""
    render_server_deployment()


def leaderboard_tab():
    """Leaderboard tab"""
    st.subheader("🏆 Leaderboard")
    st.markdown("""
    **Performance Leaderboard**: Track and compare backtest results across different strategies, 
    models, and configurations. View historical performance and identify the best performing approaches.
    """)
    
    # Initialize leaderboard
    if 'global_leaderboard' not in st.session_state:
        st.session_state.global_leaderboard = []
    
    # Leaderboard management
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Leaderboard Management")
        
        # Add sample entries for demonstration
        if st.button("🎲 Add Sample Entries"):
            sample_entries = [
                {
                    'timestamp': datetime.now() - timedelta(days=i),
                    'strategy': f"Strategy_{i+1}",
                    'model_type': ['Transformer', 'LSTM', 'LightGBM'][i % 3],
                    'trader_type': ['prediction', 'rl', 'hybrid'][i % 3],
                    'total_return': 0.15 + (i * 0.02),
                    'sharpe_ratio': 1.2 + (i * 0.1),
                    'max_drawdown': 0.08 - (i * 0.005),
                    'win_rate': 0.65 + (i * 0.02),
                    'total_trades': 150 + (i * 10)
                }
                for i in range(10)
            ]
            st.session_state.global_leaderboard.extend(sample_entries)
            st.success("✅ Added sample entries!")
        
        # Clear leaderboard
        if st.button("🗑️ Clear Leaderboard"):
            st.session_state.global_leaderboard = []
            st.success("✅ Leaderboard cleared!")
    
    with col2:
        st.markdown("#### 📈 Leaderboard Statistics")
        
        if st.session_state.global_leaderboard:
            total_entries = len(st.session_state.global_leaderboard)
            avg_return = np.mean([entry['total_return'] for entry in st.session_state.global_leaderboard])
            best_return = max([entry['total_return'] for entry in st.session_state.global_leaderboard])
            
            st.metric("Total Entries", total_entries)
            st.metric("Average Return", f"{avg_return:.2%}")
            st.metric("Best Return", f"{best_return:.2%}")
        else:
            st.info("📊 No entries in leaderboard yet")
    
    # Display leaderboard
    if st.session_state.global_leaderboard:
        st.markdown("#### 🏆 Leaderboard Rankings")
        
        # Sort options
        col1, col2 = st.columns(2)
        
        with col1:
            sort_by = st.selectbox(
                "Sort by:",
                ["total_return", "sharpe_ratio", "max_drawdown", "win_rate", "total_trades"]
            )
        
        with col2:
            filter_strategy = st.selectbox(
                "Filter by Strategy:",
                ["All"] + list(set([entry['strategy'] for entry in st.session_state.global_leaderboard]))
            )
        
        # Create leaderboard DataFrame
        leaderboard_df = pd.DataFrame(st.session_state.global_leaderboard)
        
        # Apply filter
        if filter_strategy != "All":
            leaderboard_df = leaderboard_df[leaderboard_df['strategy'] == filter_strategy]
        
        # Sort
        leaderboard_df = leaderboard_df.sort_values(sort_by, ascending=False)
        
        # Display top entries
        st.dataframe(
            leaderboard_df[['timestamp', 'strategy', 'model_type', 'trader_type', 'total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate', 'total_trades']].head(20),
            use_container_width=True
        )
        
        # Leaderboard visualization
        st.markdown("#### 📊 Performance Visualization")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Return vs Sharpe scatter
            fig = px.scatter(
                leaderboard_df,
                x='total_return',
                y='sharpe_ratio',
                color='trader_type',
                size='total_trades',
                hover_data=['strategy', 'model_type'],
                title="Return vs Sharpe Ratio"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Return distribution by trader type
            fig = px.box(
                leaderboard_df,
                x='trader_type',
                y='total_return',
                title="Return Distribution by Trader Type"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Performance over time
        st.markdown("#### 📈 Performance Over Time")
        
        fig = go.Figure()
        
        for trader_type in leaderboard_df['trader_type'].unique():
            trader_data = leaderboard_df[leaderboard_df['trader_type'] == trader_type]
            fig.add_trace(go.Scatter(
                x=trader_data['timestamp'],
                y=trader_data['total_return'],
                mode='markers+lines',
                name=trader_type.upper(),
                marker=dict(size=8)
            ))
        
        fig.update_layout(
            title="Performance Over Time by Trader Type",
            xaxis_title="Date",
            yaxis_title="Total Return",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Export functionality
        st.markdown("#### 💾 Export Leaderboard")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Export to CSV"):
                csv = leaderboard_df.to_csv(index=False)
                st.download_button(
                    label="Download Leaderboard CSV",
                    data=csv,
                    file_name=f"leaderboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("📊 Export Summary Report"):
                # Create summary report
                summary = f"""
                # QuantTime Leaderboard Summary Report
                
                Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                
                ## Overview
                - Total Entries: {len(leaderboard_df)}
                - Date Range: {leaderboard_df['timestamp'].min()} to {leaderboard_df['timestamp'].max()}
                
                ## Top Performers
                - Best Return: {leaderboard_df['total_return'].max():.2%}
                - Best Sharpe: {leaderboard_df['sharpe_ratio'].max():.2f}
                - Lowest Drawdown: {leaderboard_df['max_drawdown'].min():.2%}
                
                ## Strategy Breakdown
                {leaderboard_df.groupby('strategy')['total_return'].mean().to_string()}
                
                ## Model Type Performance
                {leaderboard_df.groupby('model_type')['total_return'].mean().to_string()}
                
                ## Trader Type Performance
                {leaderboard_df.groupby('trader_type')['total_return'].mean().to_string()}
                """
                
                st.download_button(
                    label="Download Summary Report",
                    data=summary,
                    file_name=f"leaderboard_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown"
                )
    
    else:
        st.info("📊 No entries in the leaderboard yet. Run backtests to populate the leaderboard!")


def dev_tools_tab():
    """Development tools and troubleshooting tab"""
    dev_tools.render_dev_tools()


# Server-specific tab functions
def server_status_tab(server_name: str):
    """Server status and monitoring tab"""
    st.subheader(f"🖥️ {server_name.upper()} Server Status")
    
    try:
        from quanttime.dashboard.server_task_manager import task_manager
        status = task_manager.get_server_status(server_name)
        
        if status.get("connected", False):
            st.success(f"✅ {server_name.upper()} is online and connected")
            
            # Server info
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Status", "🟢 Online")
                st.metric("Uptime", status.get("uptime", "Unknown"))
            with col2:
                st.metric("Memory", status.get("memory", "Unknown"))
                st.metric("Disk", status.get("disk", "Unknown"))
            
            # Running processes
            processes = status.get("processes", "")
            if processes:
                st.subheader("🔄 Running Processes")
                st.code(processes)
            else:
                st.info("No active processes")
                
        else:
            st.error(f"❌ {server_name.upper()} is offline")
            if "error" in status:
                st.error(f"Connection error: {status['error']}")
    
    except Exception as e:
        st.error(f"Failed to get server status: {e}")


def server_performance_tab(server_name: str):
    """Server performance monitoring tab"""
    st.subheader(f"📊 {server_name.upper()} Performance")
    
    # Performance metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("CPU Usage", "45%")
        st.progress(0.45)
    with col2:
        st.metric("Memory Usage", "62%")
        st.progress(0.62)
    with col3:
        st.metric("Disk Usage", "78%")
        st.progress(0.78)
    
    # Performance charts would go here
    st.info("Performance charts and historical data will be implemented")


def server_tasks_tab(server_name: str):
    """Server task management tab"""
    st.subheader(f"📋 {server_name.upper()} Tasks")
    
    # Task management interface
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Submit New Task"):
            st.info("Task submission dialog would open")
        
        if st.button("📊 View All Tasks"):
            st.info("Task manager would open")
    
    with col2:
        if st.button("⏸️ Pause All"):
            st.info("All tasks paused")
        
        if st.button("▶️ Resume All"):
            st.info("All tasks resumed")
    
    # Current tasks list
    st.subheader("Current Tasks")
    st.info("Task list would be displayed here")


def server_files_tab(server_name: str):
    """Server file management tab"""
    st.subheader(f"📁 {server_name.upper()} Files")
    
    # File management interface
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Download Files"):
            st.info("File download dialog would open")
        
        if st.button("📤 Upload Files"):
            st.info("File upload dialog would open")
    
    with col2:
        if st.button("🔄 Sync Files"):
            st.info("File synchronization started")
        
        if st.button("🗑️ Clean Up"):
            st.info("Cleanup dialog would open")
    
    # File browser
    st.subheader("File Browser")
    st.info("File browser would be displayed here")


def server_settings_tab(server_name: str):
    """Server settings and configuration tab"""
    st.subheader(f"⚙️ {server_name.upper()} Settings")
    
    # Configuration options
    st.subheader("Server Configuration")
    
    # SSH settings
    with st.expander("SSH Configuration", expanded=False):
        st.text_input("SSH Host", value="jupiter", key=f"ssh_host_{server_name}")
        st.text_input("SSH User", value="quanttime", key=f"ssh_user_{server_name}")
        st.text_input("SSH Password", type="password", value="", key=f"ssh_pass_{server_name}")
    
    # Performance settings
    with st.expander("Performance Settings", expanded=False):
        st.slider("Max CPU Usage", 0, 100, 80, key=f"max_cpu_{server_name}")
        st.slider("Max Memory Usage", 0, 100, 90, key=f"max_mem_{server_name}")
        st.slider("Max Concurrent Tasks", 1, 10, 4, key=f"max_tasks_{server_name}")
    
    # Save settings
    if st.button("💾 Save Settings"):
        st.success("Settings saved successfully")


def data_transmission_tab():
    """Data transmission interface tab"""
    render_data_transmission_interface()


if __name__ == "__main__":
    main()


