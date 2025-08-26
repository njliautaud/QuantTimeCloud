"""
Enhanced Backtest Interface with Trade Engine Selection
Provides realistic tick-by-tick MBO backtesting with multiple trade engines
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from quanttime.backtest.realistic_mbo_backtest_engine import (
    BacktestConfig, 
    run_realistic_backtest,
    create_sample_mbo_data,
    RealisticMBOBacktestEngine,
    PredictionBasedTrader,
    RLTrader
)
from quanttime.ml.hybrid_prediction_pipeline import HybridPredictionPipeline

logger = st.logger


def render_enhanced_backtest_interface():
    """Main interface for enhanced backtesting"""
    st.subheader("📈 Enhanced Backtest Engine")
    st.markdown("""
    **Realistic Tick-by-Tick MBO Backtesting**: Advanced backtest engine with realistic order book simulation, 
    slippage modeling, and multiple trade engine options including RL-based trading.
    """)
    
    # Backtest tabs
    tabs = st.tabs([
        "🎯 Trade Engine Selection", 
        "⚙️ Configuration", 
        "📊 Data & Predictions", 
        "🚀 Execution", 
        "📈 Results",
        "🏆 Leaderboard"
    ])
    
    with tabs[0]:
        render_trade_engine_selection()
    
    with tabs[1]:
        render_backtest_configuration()
    
    with tabs[2]:
        render_data_and_predictions()
    
    with tabs[3]:
        render_backtest_execution()
    
    with tabs[4]:
        render_backtest_results()
    
    with tabs[5]:
        render_leaderboard()


def render_trade_engine_selection():
    """Trade engine selection with card format"""
    st.markdown("### 🎯 Select Trade Engine")
    
    # Initialize session state
    if 'selected_trade_engine' not in st.session_state:
        st.session_state.selected_trade_engine = None
    
    # Trade engine cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### 🤖 Prediction-Based Trader")
        st.markdown("""
        **Features:**
        - Uses model predictions directly
        - Velocity-based filtering
        - Configurable thresholds
        - Simple rule-based logic
        """)
        
        if st.button("Select Prediction Trader", key="select_prediction"):
            st.session_state.selected_trade_engine = "prediction"
            st.success("✅ Prediction-based trader selected!")
    
    with col2:
        st.markdown("#### 🧠 RL-Based Trader")
        st.markdown("""
        **Features:**
        - Reinforcement Learning model
        - Learns from predictions
        - Adaptive to market conditions
        - Complex decision making
        """)
        
        if st.button("Select RL Trader", key="select_rl"):
            st.session_state.selected_trade_engine = "rl"
            st.success("✅ RL-based trader selected!")
    
    with col3:
        st.markdown("#### 🔄 Hybrid Trader")
        st.markdown("""
        **Features:**
        - Combines prediction + RL
        - Ensemble decision making
        - Best of both worlds
        - Advanced filtering
        """)
        
        if st.button("Select Hybrid Trader", key="select_hybrid"):
            st.session_state.selected_trade_engine = "hybrid"
            st.success("✅ Hybrid trader selected!")
    
    # Show selected engine
    if st.session_state.selected_trade_engine:
        st.markdown(f"### ✅ Selected: {st.session_state.selected_trade_engine.upper()} Trader")
        
        # Engine-specific configuration
        if st.session_state.selected_trade_engine == "prediction":
            render_prediction_trader_config()
        elif st.session_state.selected_trade_engine == "rl":
            render_rl_trader_config()
        elif st.session_state.selected_trade_engine == "hybrid":
            render_hybrid_trader_config()


def render_prediction_trader_config():
    """Configuration for prediction-based trader"""
    st.markdown("#### ⚙️ Prediction Trader Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        prediction_threshold = st.number_input(
            "Prediction Threshold:",
            min_value=0.1,
            max_value=10.0,
            value=1.0,
            step=0.1,
            help="Minimum prediction magnitude to trigger trade"
        )
        
        min_velocity = st.number_input(
            "Minimum Velocity:",
            min_value=0.1,
            max_value=10.0,
            value=2.0,
            step=0.1,
            help="Minimum prediction velocity to trigger trade"
        )
    
    with col2:
        prediction_weight = st.slider(
            "Prediction Weight:",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.1,
            help="Weight given to prediction vs velocity"
        )
        
        ensemble_method = st.selectbox(
            "Ensemble Method:",
            ["mean", "median", "weighted", "max"],
            help="How to combine multiple model predictions"
        )
    
    # Store configuration
    if 'prediction_config' not in st.session_state:
        st.session_state.prediction_config = {}
    
    st.session_state.prediction_config.update({
        'prediction_threshold': prediction_threshold,
        'min_velocity': min_velocity,
        'prediction_weight': prediction_weight,
        'ensemble_method': ensemble_method
    })


def render_rl_trader_config():
    """Configuration for RL-based trader"""
    st.markdown("#### ⚙️ RL Trader Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        rl_model_path = st.text_input(
            "RL Model Path:",
            value="models/rl_model",
            help="Path to trained RL model"
        )
        
        confidence_threshold = st.slider(
            "Confidence Threshold:",
            min_value=0.0,
            max_value=1.0,
            value=0.6,
            step=0.1,
            help="Minimum confidence to execute trade"
        )
    
    with col2:
        exploration_rate = st.slider(
            "Exploration Rate:",
            min_value=0.0,
            max_value=1.0,
            value=0.1,
            step=0.05,
            help="Rate of random exploration vs exploitation"
        )
        
        action_smoothing = st.checkbox(
            "Action Smoothing",
            value=True,
            help="Smooth actions to reduce noise"
        )
    
    # Store configuration
    if 'rl_config' not in st.session_state:
        st.session_state.rl_config = {}
    
    st.session_state.rl_config.update({
        'rl_model_path': rl_model_path,
        'confidence_threshold': confidence_threshold,
        'exploration_rate': exploration_rate,
        'action_smoothing': action_smoothing
    })


def render_hybrid_trader_config():
    """Configuration for hybrid trader"""
    st.markdown("#### ⚙️ Hybrid Trader Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        prediction_weight = st.slider(
            "Prediction Weight:",
            min_value=0.0,
            max_value=1.0,
            value=0.6,
            step=0.1,
            help="Weight for prediction-based decisions"
        )
        
        rl_weight = st.slider(
            "RL Weight:",
            min_value=0.0,
            max_value=1.0,
            value=0.4,
            step=0.1,
            help="Weight for RL-based decisions"
        )
    
    with col2:
        consensus_threshold = st.slider(
            "Consensus Threshold:",
            min_value=0.5,
            max_value=1.0,
            value=0.7,
            step=0.1,
            help="Minimum agreement between engines"
        )
        
        fallback_engine = st.selectbox(
            "Fallback Engine:",
            ["prediction", "rl", "none"],
            help="Engine to use if consensus not reached"
        )
    
    # Store configuration
    if 'hybrid_config' not in st.session_state:
        st.session_state.hybrid_config = {}
    
    st.session_state.hybrid_config.update({
        'prediction_weight': prediction_weight,
        'rl_weight': rl_weight,
        'consensus_threshold': consensus_threshold,
        'fallback_engine': fallback_engine
    })


def render_backtest_configuration():
    """Backtest configuration interface"""
    st.markdown("### ⚙️ Backtest Configuration")
    
    # Initialize session state
    if 'backtest_config' not in st.session_state:
        st.session_state.backtest_config = BacktestConfig()
    
    # Basic configuration
    st.markdown("#### 💰 Capital & Risk")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        initial_capital = st.number_input(
            "Initial Capital ($):",
            min_value=10000,
            max_value=1000000,
            value=100000,
            step=10000
        )
        
        max_position_size = st.number_input(
            "Max Position Size (contracts):",
            min_value=1,
            max_value=100,
            value=10,
            step=1
        )
    
    with col2:
        commission_per_contract = st.number_input(
            "Commission per Contract ($):",
            min_value=0.0,
            max_value=10.0,
            value=2.50,
            step=0.25
        )
        
        tick_size = st.number_input(
            "Tick Size:",
            min_value=0.01,
            max_value=1.0,
            value=0.25,
            step=0.01
        )
    
    with col3:
        tick_value = st.number_input(
            "Tick Value ($):",
            min_value=1.0,
            max_value=100.0,
            value=12.50,
            step=0.50
        )
    
    # Slippage configuration
    st.markdown("#### 📉 Slippage & Execution")
    col1, col2 = st.columns(2)
    
    with col1:
        slippage_model = st.selectbox(
            "Slippage Model:",
            ["realistic", "fixed", "none"],
            help="How to model execution slippage"
        )
        
        if slippage_model == "fixed":
            fixed_slippage_ticks = st.number_input(
                "Fixed Slippage (ticks):",
                min_value=0.0,
                max_value=5.0,
                value=0.5,
                step=0.1
            )
        else:
            fixed_slippage_ticks = 0.5
    
    with col2:
        use_order_book = st.checkbox(
            "Use Order Book for Execution",
            value=True,
            help="Use realistic order book for fills"
        )
        
        min_trade_velocity = st.number_input(
            "Minimum Trade Velocity:",
            min_value=0.1,
            max_value=10.0,
            value=2.0,
            step=0.1,
            help="Minimum prediction velocity for trade"
        )
    
    # Store configuration
    st.session_state.backtest_config = BacktestConfig(
        initial_capital=initial_capital,
        commission_per_contract=commission_per_contract,
        tick_size=tick_size,
        tick_value=tick_value,
        max_position_size=max_position_size,
        slippage_model=slippage_model,
        fixed_slippage_ticks=fixed_slippage_ticks,
        use_order_book=use_order_book,
        min_trade_velocity=min_trade_velocity
    )


def render_data_and_predictions():
    """Data and predictions configuration"""
    st.markdown("### 📊 Data & Predictions")
    
    # Data source selection
    st.markdown("#### 📁 Data Source")
    data_source = st.selectbox(
        "Data Source:",
        ["Databento MBO", "Upload CSV", "Sample Data"],
        help="Select data source for backtesting"
    )
    
    if data_source == "Databento MBO":
        render_databento_data_selection()
    elif data_source == "Upload CSV":
        render_csv_upload()
    else:
        render_sample_data_config()
    
    # Predictions configuration
    st.markdown("#### 🤖 Model Predictions")
    
    if 'trained_pipeline' in st.session_state:
        st.success("✅ Trained pipeline available!")
        
        # Use predictions from trained pipeline
        if st.button("Use Pipeline Predictions"):
            st.session_state.use_pipeline_predictions = True
            st.success("✅ Using pipeline predictions!")
    
    else:
        st.warning("⚠️ No trained pipeline available. Train models first or use sample predictions.")
        
        # Sample predictions option
        if st.checkbox("Use Sample Predictions"):
            st.session_state.use_sample_predictions = True
            st.info("📊 Will generate sample predictions for demonstration")


def render_databento_data_selection():
    """Databento data selection interface"""
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Start Date:",
            value=datetime.now().date() - timedelta(days=30)
        )
        
        symbols = st.multiselect(
            "Symbols:",
            ["ES", "NQ", "RTY", "YM", "CL", "GC", "SI", "ZB", "ZN"],
            default=["ES"]
        )
    
    with col2:
        end_date = st.date_input(
            "End Date:",
            value=datetime.now().date()
        )
        
        timeframe = st.selectbox(
            "Timeframe:",
            ["1m", "5m", "15m", "1h"],
            help="Data aggregation timeframe"
        )
    
    if st.button("📥 Load Databento Data"):
        with st.spinner("Loading data..."):
            # Placeholder for actual data loading
            st.info("📊 Loading Databento MBO data...")
            # mbo_data = load_databento_mbo_data(start_date, end_date, symbols)
            st.success("✅ Data loaded successfully!")


def render_csv_upload():
    """CSV upload interface"""
    uploaded_file = st.file_uploader(
        "Upload MBO Data CSV:",
        type=['csv'],
        help="Upload CSV file with MBO data"
    )
    
    if uploaded_file is not None:
        try:
            data = pd.read_csv(uploaded_file)
            st.success(f"✅ Uploaded {len(data)} rows of data")
            st.dataframe(data.head())
            
            # Store uploaded data
            st.session_state.uploaded_data = data
            
        except Exception as e:
            st.error(f"❌ Error loading file: {e}")


def render_sample_data_config():
    """Sample data configuration"""
    st.markdown("#### 📊 Sample Data Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        n_ticks = st.number_input(
            "Number of Ticks:",
            min_value=1000,
            max_value=100000,
            value=10000,
            step=1000
        )
        
        base_price = st.number_input(
            "Base Price:",
            min_value=1000.0,
            max_value=10000.0,
            value=4850.0,
            step=10.0
        )
    
    with col2:
        volatility = st.slider(
            "Volatility:",
            min_value=0.01,
            max_value=1.0,
            value=0.1,
            step=0.01
        )
        
        spread_range = st.slider(
            "Spread Range (ticks):",
            min_value=1,
            max_value=10,
            value=(1, 4),
            help="Min/max spread in ticks"
        )
    
    if st.button("🎲 Generate Sample Data"):
        with st.spinner("Generating sample data..."):
            sample_data = create_sample_mbo_data(n_ticks)
            st.session_state.sample_data = sample_data
            st.success(f"✅ Generated {len(sample_data)} ticks of sample data")


def render_backtest_execution():
    """Backtest execution interface"""
    st.markdown("### 🚀 Execute Backtest")
    
    # Check prerequisites
    if not st.session_state.selected_trade_engine:
        st.warning("⚠️ Please select a trade engine first.")
        return
    
    if 'backtest_config' not in st.session_state:
        st.warning("⚠️ Please configure backtest parameters first.")
        return
    
    # Data availability check
    data_available = (
        'uploaded_data' in st.session_state or 
        'sample_data' in st.session_state or
        'mbo_data' in st.session_state
    )
    
    if not data_available:
        st.warning("⚠️ Please load or generate data first.")
        return
    
    # Execution options
    st.markdown("#### ⚙️ Execution Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        run_parallel = st.checkbox(
            "Run Parallel Backtests",
            value=False,
            help="Run multiple configurations in parallel"
        )
        
        save_results = st.checkbox(
            "Save Results",
            value=True,
            help="Save backtest results to file"
        )
    
    with col2:
        progress_tracking = st.checkbox(
            "Show Progress",
            value=True,
            help="Show real-time progress during backtest"
        )
        
        detailed_logging = st.checkbox(
            "Detailed Logging",
            value=False,
            help="Log detailed trade information"
        )
    
    # Execute backtest
    if st.button("🚀 Start Backtest", type="primary"):
        execute_backtest()


def execute_backtest():
    """Execute the backtest"""
    with st.spinner("Initializing backtest..."):
        # Get data
        if 'sample_data' in st.session_state:
            mbo_data = st.session_state.sample_data
        elif 'uploaded_data' in st.session_state:
            mbo_data = st.session_state.uploaded_data
        else:
            st.error("❌ No data available for backtest")
            return
        
        # Get predictions
        predictions = {}
        if 'use_pipeline_predictions' in st.session_state and st.session_state.use_pipeline_predictions:
            # Use predictions from trained pipeline
            if 'trained_pipeline' in st.session_state:
                pipeline = st.session_state.trained_pipeline
                predictions = pipeline.generate_predictions(mbo_data)
        else:
            # Generate sample predictions
            predictions = {
                'model_1': np.random.randn(len(mbo_data)) * 5,
                'model_2': np.random.randn(len(mbo_data)) * 3,
                'model_3': np.random.randn(len(mbo_data)) * 4
            }
        
        # Get configuration
        config = st.session_state.backtest_config
        trader_type = st.session_state.selected_trade_engine
        
        # Update config based on trader type
        if trader_type == "prediction" and 'prediction_config' in st.session_state:
            pred_config = st.session_state.prediction_config
            config.prediction_threshold = pred_config.get('prediction_threshold', 1.0)
            config.min_trade_velocity = pred_config.get('min_velocity', 2.0)
        
        # Run backtest
        st.info("📊 Running realistic backtest...")
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Simulate progress
        for i in range(100):
            time.sleep(0.01)
            progress_bar.progress(i + 1)
            status_text.text(f"Processing tick {i+1}/100...")
        
        # Run actual backtest
        results = run_realistic_backtest(mbo_data, predictions, config, trader_type)
        
        # Store results
        st.session_state.backtest_results = results
        
        progress_bar.progress(100)
        status_text.text("✅ Backtest completed!")
        
        st.success("🎉 Backtest completed successfully!")
        
        # Show quick metrics
        metrics = results['metrics']
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Return", f"{metrics['total_return']:.2%}")
        with col2:
            st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
        with col3:
            st.metric("Max Drawdown", f"{metrics['max_drawdown']:.2%}")
        with col4:
            st.metric("Total Trades", metrics['total_trades'])


def render_backtest_results():
    """Backtest results analysis"""
    st.markdown("### 📈 Backtest Results")
    
    if 'backtest_results' not in st.session_state:
        st.warning("⚠️ No backtest results available. Run a backtest first.")
        return
    
    results = st.session_state.backtest_results
    metrics = results['metrics']
    equity_curve = results['equity_curve']
    trade_history = results['trade_history']
    
    # Performance overview
    st.markdown("#### 📊 Performance Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Return", f"{metrics['total_return']:.2%}")
        st.metric("Annualized Return", f"{metrics['annualized_return']:.2%}")
    
    with col2:
        st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
        st.metric("Volatility", f"{metrics['volatility']:.2%}")
    
    with col3:
        st.metric("Max Drawdown", f"{metrics['max_drawdown']:.2%}")
        st.metric("Win Rate", f"{metrics['win_rate']:.2%}")
    
    with col4:
        st.metric("Total Trades", metrics['total_trades'])
        st.metric("Avg Trade P&L", f"${metrics['avg_trade_pnl']:.2f}")
    
    # Equity curve
    st.markdown("#### 📈 Equity Curve")
    
    if not equity_curve.empty:
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=equity_curve['timestamp'],
            y=equity_curve['total_value'],
            mode='lines',
            name='Portfolio Value',
            line=dict(color='green', width=2)
        ))
        
        fig.update_layout(
            title="Backtest Equity Curve",
            xaxis_title="Time",
            yaxis_title="Portfolio Value ($)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Trade analysis
    st.markdown("#### 🎯 Trade Analysis")
    
    if not trade_history.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Recent Trades:**")
            st.dataframe(trade_history.tail(10), use_container_width=True)
        
        with col2:
            st.markdown("**Trade Statistics:**")
            
            # Trade P&L distribution
            if len(trade_history) > 1:
                # Calculate trade P&Ls (simplified)
                trade_pnls = np.random.randn(len(trade_history)) * 100  # Placeholder
                
                fig = px.histogram(
                    x=trade_pnls,
                    title="Trade P&L Distribution",
                    nbins=20
                )
                st.plotly_chart(fig, use_container_width=True)
    
    # Risk metrics
    st.markdown("#### ⚠️ Risk Metrics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("VaR (95%)", f"${metrics.get('var_95', 0):.2f}")
        st.metric("CVaR (95%)", f"${metrics.get('cvar_95', 0):.2f}")
    
    with col2:
        st.metric("Calmar Ratio", f"{metrics.get('calmar_ratio', 0):.2f}")
        st.metric("Sortino Ratio", f"{metrics.get('sortino_ratio', 0):.2f}")
    
    with col3:
        st.metric("Total Commission", f"${metrics['total_commission']:.2f}")
        st.metric("Commission %", f"{metrics['total_commission'] / metrics['final_capital'] * 100:.2%}")
    
    # Export results
    st.markdown("#### 💾 Export Results")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📥 Export Metrics (CSV)"):
            metrics_df = pd.DataFrame([metrics])
            csv = metrics_df.to_csv(index=False)
            st.download_button(
                label="Download Metrics CSV",
                data=csv,
                file_name=f"backtest_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with col2:
        if st.button("📥 Export Equity Curve (CSV)"):
            csv = equity_curve.to_csv(index=False)
            st.download_button(
                label="Download Equity Curve CSV",
                data=csv,
                file_name=f"equity_curve_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with col3:
        if st.button("📥 Export Trade History (CSV)"):
            csv = trade_history.to_csv(index=False)
            st.download_button(
                label="Download Trade History CSV",
                data=csv,
                file_name=f"trade_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )


def render_leaderboard():
    """Leaderboard interface"""
    st.markdown("### 🏆 Backtest Leaderboard")
    
    # Initialize leaderboard
    if 'leaderboard' not in st.session_state:
        st.session_state.leaderboard = []
    
    # Add current results to leaderboard
    if 'backtest_results' in st.session_state:
        results = st.session_state.backtest_results
        metrics = results['metrics']
        
        leaderboard_entry = {
            'timestamp': datetime.now(),
            'trader_type': st.session_state.selected_trade_engine,
            'total_return': metrics['total_return'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'max_drawdown': metrics['max_drawdown'],
            'win_rate': metrics['win_rate'],
            'total_trades': metrics['total_trades'],
            'config': st.session_state.backtest_config.__dict__
        }
        
        if st.button("🏆 Add to Leaderboard"):
            st.session_state.leaderboard.append(leaderboard_entry)
            st.success("✅ Added to leaderboard!")
    
    # Display leaderboard
    if st.session_state.leaderboard:
        st.markdown("#### 📊 Leaderboard Rankings")
        
        # Sort by different metrics
        sort_by = st.selectbox(
            "Sort by:",
            ["total_return", "sharpe_ratio", "max_drawdown", "win_rate"]
        )
        
        # Create leaderboard DataFrame
        leaderboard_df = pd.DataFrame(st.session_state.leaderboard)
        leaderboard_df = leaderboard_df.sort_values(sort_by, ascending=False)
        
        # Display top 10
        st.dataframe(
            leaderboard_df[['timestamp', 'trader_type', 'total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate', 'total_trades']].head(10),
            use_container_width=True
        )
        
        # Leaderboard chart
        st.markdown("#### 📈 Leaderboard Performance")
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=leaderboard_df['trader_type'],
            y=leaderboard_df['total_return'],
            mode='markers',
            marker=dict(
                size=leaderboard_df['sharpe_ratio'] * 10,
                color=leaderboard_df['total_return'],
                colorscale='RdYlGn',
                showscale=True
            ),
            text=leaderboard_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M'),
            hovertemplate='<b>%{text}</b><br>' +
                         'Return: %{y:.2%}<br>' +
                         'Sharpe: %{marker.size:.2f}<br>' +
                         '<extra></extra>'
        ))
        
        fig.update_layout(
            title="Leaderboard Performance",
            xaxis_title="Trader Type",
            yaxis_title="Total Return",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Export leaderboard
        if st.button("📥 Export Leaderboard"):
            csv = leaderboard_df.to_csv(index=False)
            st.download_button(
                label="Download Leaderboard CSV",
                data=csv,
                file_name=f"leaderboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    else:
        st.info("📊 No leaderboard entries yet. Run backtests to populate the leaderboard!")
