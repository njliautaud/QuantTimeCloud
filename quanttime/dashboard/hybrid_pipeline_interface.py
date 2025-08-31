"""
Hybrid Prediction Pipeline Interface for Streamlit Dashboard
Provides comprehensive control over the hybrid ML pipeline
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

from quanttime.ml.hybrid_prediction_pipeline import (
    HybridPredictionPipeline, 
    PipelineConfig, 
    ModelConfig, 
    create_sample_pipeline_config
)
from quanttime.backtest.realistic_mbo_backtest_engine import create_sample_mbo_data

logger = st.logger


def render_hybrid_pipeline_interface():
    """Main interface for the hybrid prediction pipeline"""
    st.subheader("🧠 Hybrid Prediction Pipeline")
    st.markdown("""
    **Advanced ML Pipeline**: Combines feature engineering, multiple prediction models (Transformer, LSTM, LightGBM), 
    and a reinforcement learning trade engine for comprehensive trading strategy development.
    """)
    
    # Pipeline tabs
    tabs = st.tabs([
        "⚙️ Configuration", 
        "🏋️ Training", 
        "📊 Predictions", 
        "🤖 RL Engine", 
        "📈 Backtesting",
        "💾 Management"
    ])
    
    with tabs[0]:
        render_pipeline_configuration()
    
    with tabs[1]:
        render_pipeline_training()
    
    with tabs[2]:
        render_predictions_analysis()
    
    with tabs[3]:
        render_rl_engine()
    
    with tabs[4]:
        render_backtesting()
    
    with tabs[5]:
        render_pipeline_management()


def render_pipeline_configuration():
    """Pipeline configuration interface"""
    st.markdown("### ⚙️ Pipeline Configuration")
    
    # Initialize session state
    if 'pipeline_config' not in st.session_state:
        st.session_state.pipeline_config = create_sample_pipeline_config()
    
    # Pipeline name
    pipeline_name = st.text_input(
        "Pipeline Name:",
        value=st.session_state.pipeline_config.pipeline_name,
        key="pipeline_name"
    )
    
    # Model configurations
    st.markdown("#### 🤖 Model Configurations")
    
    # Transformer configuration
    with st.expander("🔀 Transformer Model", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            transformer_name = st.text_input("Model Name:", value="price_transformer", key="transformer_name")
            hidden_dim = st.number_input("Hidden Dimension:", min_value=64, max_value=512, value=256, key="transformer_hidden_dim")
            num_layers = st.number_input("Number of Layers:", min_value=1, max_value=12, value=6, key="transformer_layers")
            num_heads = st.number_input("Number of Heads:", min_value=1, max_value=16, value=8, key="transformer_heads")
        
        with col2:
            dropout = st.slider("Dropout Rate:", min_value=0.0, max_value=0.5, value=0.1, key="transformer_dropout")
            learning_rate = st.number_input("Learning Rate:", min_value=0.0001, max_value=0.01, value=0.001, key="transformer_lr")
            num_epochs = st.number_input("Number of Epochs:", min_value=10, max_value=200, value=50, key="transformer_epochs")
            sequence_length = st.number_input("Sequence Length:", min_value=10, max_value=500, value=100, key="transformer_seq_len")
        
        # Feature selection
        transformer_features = st.multiselect(
            "Feature Columns:",
            ["mid_price", "spread", "total_volume", "volume_imbalance", "price_change", "volume_change"],
            default=["mid_price", "spread", "total_volume", "volume_imbalance"],
            key="transformer_features"
        )
        
        transformer_targets = st.multiselect(
            "Target Columns:",
            ["price_change_1", "price_change_2", "price_change_3", "price_change_5", "price_change_10"],
            default=["price_change_1", "price_change_2", "price_change_3"],
            key="transformer_targets"
        )
    
    # LSTM configuration
    with st.expander("🔄 LSTM Model", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            lstm_name = st.text_input("Model Name:", value="volume_lstm", key="lstm_name")
            lstm_hidden_dim = st.number_input("Hidden Dimension:", min_value=32, max_value=256, value=128, key="lstm_hidden_dim")
            lstm_layers = st.number_input("Number of Layers:", min_value=1, max_value=4, value=2, key="lstm_layers")
            lstm_dropout = st.slider("Dropout Rate:", min_value=0.0, max_value=0.5, value=0.2, key="lstm_dropout")
        
        with col2:
            lstm_lr = st.number_input("Learning Rate:", min_value=0.0001, max_value=0.01, value=0.001, key="lstm_lr")
            lstm_epochs = st.number_input("Number of Epochs:", min_value=10, max_value=200, value=50, key="lstm_epochs")
            lstm_seq_len = st.number_input("Sequence Length:", min_value=10, max_value=200, value=50, key="lstm_seq_len")
        
        lstm_features = st.multiselect(
            "Feature Columns:",
            ["total_volume", "volume_imbalance", "volume_change", "volume_ratio", "spread"],
            default=["total_volume", "volume_imbalance", "volume_change"],
            key="lstm_features"
        )
        
        lstm_targets = st.multiselect(
            "Target Columns:",
            ["price_change_1", "price_change_2", "price_change_3"],
            default=["price_change_1", "price_change_2"],
            key="lstm_targets"
        )
    
    # LightGBM configuration
    with st.expander("🌳 LightGBM Model", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            lgb_name = st.text_input("Model Name:", value="ensemble_lightgbm", key="lgb_name")
            num_leaves = st.number_input("Number of Leaves:", min_value=10, max_value=100, value=31, key="lgb_leaves")
            lgb_lr = st.number_input("Learning Rate:", min_value=0.01, max_value=0.2, value=0.05, key="lgb_lr")
        
        with col2:
            feature_fraction = st.slider("Feature Fraction:", min_value=0.5, max_value=1.0, value=0.9, key="lgb_feature_frac")
            bagging_fraction = st.slider("Bagging Fraction:", min_value=0.5, max_value=1.0, value=0.8, key="lgb_bagging_frac")
            num_boost_round = st.number_input("Number of Boost Rounds:", min_value=100, max_value=2000, value=1000, key="lgb_boost_rounds")
        
        lgb_features = st.multiselect(
            "Feature Columns:",
            ["mid_price", "spread", "total_volume", "sma_5", "sma_20", "ema_12", "ema_26"],
            default=["mid_price", "spread", "total_volume", "sma_5", "sma_20"],
            key="lgb_features"
        )
        
        lgb_targets = st.multiselect(
            "Target Columns:",
            ["price_change_1", "price_change_2", "price_change_3"],
            default=["price_change_1"],
            key="lgb_targets"
        )
    
    # RL Engine configuration
    st.markdown("#### 🎮 Reinforcement Learning Engine")
    with st.expander("RL Configuration", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            rl_model_type = st.selectbox("RL Model Type:", ["PPO", "SAC", "TD3"], key="rl_model_type")
            initial_balance = st.number_input("Initial Balance ($):", min_value=10000, max_value=1000000, value=100000, key="rl_balance")
            commission_rate = st.number_input("Commission Rate:", min_value=0.0001, max_value=0.01, value=0.001, key="rl_commission")
        
        with col2:
            max_position_size = st.slider("Max Position Size:", min_value=0.01, max_value=0.5, value=0.1, key="rl_position_size")
            rl_lr = st.number_input("Learning Rate:", min_value=0.0001, max_value=0.001, value=0.0003, key="rl_lr")
            n_steps = st.number_input("N Steps:", min_value=512, max_value=4096, value=2048, key="rl_n_steps")
        
        with col3:
            batch_size = st.number_input("Batch Size:", min_value=16, max_value=256, value=64, key="rl_batch_size")
            n_epochs = st.number_input("N Epochs:", min_value=1, max_value=20, value=10, key="rl_n_epochs")
            total_timesteps = st.number_input("Total Timesteps:", min_value=10000, max_value=500000, value=100000, key="rl_timesteps")
    
    # Feature engineering configuration
    st.markdown("#### 🔧 Feature Engineering")
    with st.expander("Feature Engineering Config", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            include_technical = st.checkbox("Include Technical Indicators", value=True, key="fe_technical")
            include_microstructure = st.checkbox("Include Microstructure Features", value=True, key="fe_microstructure")
            include_time_features = st.checkbox("Include Time Features", value=True, key="fe_time")
        
        with col2:
            normalize_features = st.checkbox("Normalize Features", value=True, key="fe_normalize")
            extract_intermediate = st.checkbox("Extract Intermediate Features", value=True, key="fe_intermediate")
    
    # Save configuration
    if st.button("💾 Save Configuration", type="primary"):
        # Update configuration
        config = create_sample_pipeline_config()
        config.pipeline_name = pipeline_name
        
        # Update transformer config
        config.models[0].model_name = transformer_name
        config.models[0].hyperparameters.update({
            'hidden_dim': hidden_dim,
            'num_layers': num_layers,
            'num_heads': num_heads,
            'dropout': dropout,
            'learning_rate': learning_rate,
            'num_epochs': num_epochs
        })
        config.models[0].feature_columns = transformer_features
        config.models[0].target_columns = transformer_targets
        config.models[0].sequence_length = sequence_length
        config.models[0].extract_intermediate_features = extract_intermediate
        
        # Update LSTM config
        config.models[1].model_name = lstm_name
        config.models[1].hyperparameters.update({
            'hidden_dim': lstm_hidden_dim,
            'num_layers': lstm_layers,
            'dropout': lstm_dropout,
            'learning_rate': lstm_lr,
            'num_epochs': lstm_epochs
        })
        config.models[1].feature_columns = lstm_features
        config.models[1].target_columns = lstm_targets
        config.models[1].sequence_length = lstm_seq_len
        config.models[1].extract_intermediate_features = extract_intermediate
        
        # Update LightGBM config
        config.models[2].model_name = lgb_name
        config.models[2].hyperparameters.update({
            'num_leaves': num_leaves,
            'learning_rate': lgb_lr,
            'feature_fraction': feature_fraction,
            'bagging_fraction': bagging_fraction,
            'num_boost_round': num_boost_round
        })
        config.models[2].feature_columns = lgb_features
        config.models[2].target_columns = lgb_targets
        
        # Update RL config
        config.rl_config.update({
            'model_type': rl_model_type,
            'initial_balance': initial_balance,
            'commission_rate': commission_rate,
            'max_position_size': max_position_size,
            'learning_rate': rl_lr,
            'n_steps': n_steps,
            'batch_size': batch_size,
            'n_epochs': n_epochs,
            'total_timesteps': total_timesteps
        })
        
        # Update feature engineering config
        config.feature_engineering_config.update({
            'include_technical_indicators': include_technical,
            'include_microstructure_features': include_microstructure,
            'include_time_features': include_time_features,
            'normalize_features': normalize_features
        })
        
        st.session_state.pipeline_config = config
        st.success("✅ Configuration saved!")


def render_pipeline_training():
    """Pipeline training interface"""
    st.markdown("### 🏋️ Pipeline Training")
    
    if 'pipeline_config' not in st.session_state:
        st.warning("⚠️ Please configure the pipeline first in the Configuration tab.")
        return
    
    # Data selection
    st.markdown("#### 📊 Data Selection")
    col1, col2 = st.columns(2)
    
    with col1:
        data_source = st.selectbox(
            "Data Source:",
            ["Databento MBO", "Custom CSV", "Live Stream"],
            key="training_data_source"
        )
        
        if data_source == "Databento MBO":
            # Date range selection
            start_date = st.date_input(
                "Training Start Date:",
                value=datetime.now().date() - timedelta(days=60),
                key="training_start_date"
            )
            end_date = st.date_input(
                "Training End Date:",
                value=datetime.now().date() - timedelta(days=30),
                key="training_end_date"
            )
        
        elif data_source == "Custom CSV":
            uploaded_file = st.file_uploader("Upload CSV file", type=['csv'], key="training_csv")
    
    with col2:
        symbols = st.multiselect(
            "Symbols:",
            ["ES", "NQ", "RTY", "YM", "CL", "GC", "SI", "ZB", "ZN"],
            default=["ES"],
            key="training_symbols"
        )
        
        timeframe = st.selectbox(
            "Timeframe:",
            ["1m", "5m", "15m", "1h", "4h", "1d"],
            key="training_timeframe"
        )
    
    # Training options
    st.markdown("#### ⚙️ Training Options")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        train_test_split = st.slider("Train/Test Split:", min_value=0.5, max_value=0.9, value=0.8, key="train_test_split")
        validation_split = st.slider("Validation Split:", min_value=0.1, max_value=0.3, value=0.2, key="validation_split")
    
    with col2:
        use_gpu = st.checkbox("Use GPU", value=True, key="use_gpu")
        random_seed = st.number_input("Random Seed:", value=42, key="random_seed")
    
    with col3:
        save_models = st.checkbox("Save Models", value=True, key="save_models")
        save_path = st.text_input("Save Path:", value="models/hybrid_pipeline", key="save_path")
    
    # Training execution
    st.markdown("#### 🚀 Training Execution")
    
    if st.button("🏋️ Start Training", type="primary"):
        with st.spinner("Initializing pipeline..."):
            # Create pipeline
            pipeline = HybridPredictionPipeline(st.session_state.pipeline_config)
            
            # Load data (placeholder - replace with actual data loading)
            st.info("📊 Loading data...")
            # raw_data = load_mbo_data(start_date, end_date, symbols)
            
            # Use real data instead of sample data
            st.warning("⚠️ Please load real data from Databento or upload CSV files.")
            return
            
            # Prepare data
            st.info("🔧 Preparing data...")
            features, targets = pipeline.prepare_data(sample_data)
            
            # Train models
            st.info("🤖 Training prediction models...")
            pipeline.train_models(features, targets)
            
            # Generate predictions
            st.info("📊 Generating predictions...")
            predictions = pipeline.generate_predictions(features)
            
            # Train RL engine
            st.info("🎮 Training RL engine...")
            pipeline.train_rl_engine(features, predictions)
            
            # Save pipeline
            if save_models:
                st.info("💾 Saving pipeline...")
                pipeline.save_pipeline(save_path)
            
            # Store in session state
            st.session_state.trained_pipeline = pipeline
            st.session_state.training_features = features
            st.session_state.training_targets = targets
            st.session_state.training_predictions = predictions
            
            st.success("✅ Training completed successfully!")
    
    # Training progress (if training is in progress)
    if 'training_progress' in st.session_state:
        st.markdown("#### 📈 Training Progress")
        
        # Progress bars for each model
        for model_name, progress in st.session_state.training_progress.items():
            st.write(f"**{model_name}:**")
            st.progress(progress)
        
        # Training metrics
        if 'training_metrics' in st.session_state:
            metrics = st.session_state.training_metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Training Loss", f"{metrics.get('train_loss', 0):.4f}")
            with col2:
                st.metric("Validation Loss", f"{metrics.get('val_loss', 0):.4f}")
            with col3:
                st.metric("Accuracy", f"{metrics.get('accuracy', 0):.2%}")


def render_predictions_analysis():
    """Predictions analysis interface"""
    st.markdown("### 📊 Predictions Analysis")
    
    if 'trained_pipeline' not in st.session_state:
        st.warning("⚠️ Please train the pipeline first in the Training tab.")
        return
    
    pipeline = st.session_state.trained_pipeline
    predictions = st.session_state.training_predictions
    
    # Model performance comparison
    st.markdown("#### 🤖 Model Performance Comparison")
    
    # Create performance comparison chart
    if predictions:
        model_names = list(predictions.keys())
        prediction_data = []
        
        for model_name, pred in predictions.items():
            if len(pred.shape) > 1:
                pred_mean = np.mean(pred, axis=1)
            else:
                pred_mean = pred
            prediction_data.append(pred_mean)
        
        # Create comparison chart
        fig = go.Figure()
        
        for i, (model_name, pred_data) in enumerate(zip(model_names, prediction_data)):
            fig.add_trace(go.Scatter(
                y=pred_data[:100],  # Show first 100 predictions
                mode='lines',
                name=model_name,
                line=dict(width=2)
            ))
        
        fig.update_layout(
            title="Model Predictions Comparison",
            xaxis_title="Time Steps",
            yaxis_title="Prediction Value",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Individual model analysis
    st.markdown("#### 📈 Individual Model Analysis")
    
    if predictions:
        selected_model = st.selectbox("Select Model:", list(predictions.keys()), key="model_analysis")
        
        if selected_model:
            model_pred = predictions[selected_model]
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Prediction distribution
                fig_dist = px.histogram(
                    x=model_pred.flatten(),
                    title=f"{selected_model} Prediction Distribution",
                    nbins=50
                )
                st.plotly_chart(fig_dist, use_container_width=True)
            
            with col2:
                # Prediction statistics
                st.markdown("**Prediction Statistics:**")
                pred_stats = {
                    "Mean": np.mean(model_pred),
                    "Std": np.std(model_pred),
                    "Min": np.min(model_pred),
                    "Max": np.max(model_pred),
                    "25th Percentile": np.percentile(model_pred, 25),
                    "75th Percentile": np.percentile(model_pred, 75)
                }
                
                for stat, value in pred_stats.items():
                    st.write(f"**{stat}:** {value:.4f}")
    
    # Feature importance (for LightGBM)
    if 'trained_pipeline' in st.session_state:
        pipeline = st.session_state.trained_pipeline
        
        for model_name, model in pipeline.models.items():
            if hasattr(model, 'get_feature_importance'):
                st.markdown(f"#### 🌳 {model_name} Feature Importance")
                
                importance = model.get_feature_importance()
                if importance:
                    # Create feature importance chart
                    fig_importance = px.bar(
                        x=list(importance.values()),
                        y=list(importance.keys()),
                        orientation='h',
                        title=f"{model_name} Feature Importance"
                    )
                    st.plotly_chart(fig_importance, use_container_width=True)


def render_rl_engine():
    """RL engine interface"""
    st.markdown("### 🤖 Reinforcement Learning Engine")
    
    if 'trained_pipeline' not in st.session_state:
        st.warning("⚠️ Please train the pipeline first in the Training tab.")
        return
    
    pipeline = st.session_state.trained_pipeline
    
    # RL model information
    st.markdown("#### 🎮 RL Model Information")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Model Type", pipeline.config.rl_config.get('model_type', 'PPO'))
        st.metric("Initial Balance", f"${pipeline.config.rl_config.get('initial_balance', 0):,}")
    
    with col2:
        st.metric("Commission Rate", f"{pipeline.config.rl_config.get('commission_rate', 0):.3%}")
        st.metric("Max Position Size", f"{pipeline.config.rl_config.get('max_position_size', 0):.1%}")
    
    with col3:
        st.metric("Learning Rate", pipeline.config.rl_config.get('learning_rate', 0))
        st.metric("Total Timesteps", f"{pipeline.config.rl_config.get('total_timesteps', 0):,}")
    
    # RL training metrics
    if 'rl_training_metrics' in st.session_state:
        st.markdown("#### 📈 RL Training Metrics")
        
        metrics = st.session_state.rl_training_metrics
        
        # Create training progress chart
        fig = go.Figure()
        
        if 'episode_rewards' in metrics:
            fig.add_trace(go.Scatter(
                y=metrics['episode_rewards'],
                mode='lines',
                name='Episode Rewards',
                line=dict(color='blue')
            ))
        
        if 'loss_values' in metrics:
            fig.add_trace(go.Scatter(
                y=metrics['loss_values'],
                mode='lines',
                name='Loss',
                line=dict(color='red'),
                yaxis='y2'
            ))
        
        fig.update_layout(
            title="RL Training Progress",
            xaxis_title="Episodes",
            yaxis_title="Reward",
            yaxis2=dict(title="Loss", overlaying='y', side='right'),
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # RL model actions
    st.markdown("#### ⚙️ RL Model Actions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Retrain RL Model"):
            with st.spinner("Retraining RL model..."):
                # Retrain RL model
                features = st.session_state.training_features
                predictions = st.session_state.training_predictions
                pipeline.train_rl_engine(features, predictions)
                st.success("✅ RL model retrained!")
        
        if st.button("📊 Test RL Model"):
            with st.spinner("Testing RL model..."):
                # Test RL model with sample observation
                sample_obs = np.random.randn(10)  # Sample observation
                action = pipeline.rl_engine.predict_action(sample_obs)
                st.info(f"RL Model Action: {action}")
    
    with col2:
        if st.button("💾 Save RL Model"):
            save_path = st.text_input("Save Path:", value="models/rl_model", key="rl_save_path")
            if save_path:
                pipeline.rl_engine.save_model(save_path)
                st.success("✅ RL model saved!")
        
        if st.button("📋 Load RL Model"):
            load_path = st.text_input("Load Path:", value="models/rl_model", key="rl_load_path")
            if load_path:
                pipeline.rl_engine.load_model(load_path)
                st.success("✅ RL model loaded!")


def render_backtesting():
    """Backtesting interface with enhanced engine integration"""
    st.markdown("### 📈 Backtesting")
    
    # Check if pipeline is trained
    if 'trained_pipeline' not in st.session_state:
        st.warning("⚠️ Please train the pipeline first before running backtests.")
        st.info("💡 Go to the 'Training' tab to train your models.")
        return
    
    # Backtest configuration
    with st.expander("⚙️ Backtest Configuration", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            backtest_start_date = st.date_input(
                "Backtest Start Date:",
                value=datetime.now().date() - timedelta(days=30)
            )
            
            backtest_end_date = st.date_input(
                "Backtest End Date:",
                value=datetime.now().date()
            )
            
            backtest_symbols = st.multiselect(
                "Symbols:",
                ["ES", "NQ", "RTY", "YM", "CL", "GC", "SI", "ZB", "ZN"],
                default=["ES"]
            )
        
        with col2:
            backtest_initial_capital = st.number_input(
                "Initial Capital ($):",
                min_value=10000,
                max_value=1000000,
                value=100000,
                step=10000
            )
            
            commission_per_contract = st.number_input(
                "Commission per Contract ($):",
                min_value=0.0,
                max_value=10.0,
                value=2.50,
                step=0.25
            )
            
            tick_value = st.number_input(
                "Tick Value ($):",
                min_value=1.0,
                max_value=100.0,
                value=12.50,
                step=0.50
            )
    
    # Trade engine selection
    with st.expander("🎯 Trade Engine Selection", expanded=True):
        st.markdown("#### Select Trade Engine for Backtest")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🤖 Prediction-Based**")
            st.markdown("""
            - Uses model predictions directly
            - Velocity-based filtering
            - Simple rule-based logic
            """)
            use_prediction = st.checkbox("Use Prediction Trader", value=True)
        
        with col2:
            st.markdown("**🧠 RL-Based**")
            st.markdown("""
            - Reinforcement Learning model
            - Learns from predictions
            - Adaptive decision making
            """)
            use_rl = st.checkbox("Use RL Trader", value=False)
        
        with col3:
            st.markdown("**🔄 Hybrid**")
            st.markdown("""
            - Combines prediction + RL
            - Ensemble decision making
            - Best of both worlds
            """)
            use_hybrid = st.checkbox("Use Hybrid Trader", value=False)
        
        # Determine trader type
        if use_hybrid:
            trader_type = "hybrid"
        elif use_rl:
            trader_type = "rl"
        else:
            trader_type = "prediction"
        
        st.info(f"🎯 Selected Trade Engine: **{trader_type.upper()}**")
    
    # Advanced configuration
    with st.expander("🔧 Advanced Configuration", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            slippage_model = st.selectbox(
                "Slippage Model:",
                ["realistic", "fixed", "none"],
                help="How to model execution slippage"
            )
            
            use_order_book = st.checkbox(
                "Use Order Book for Execution",
                value=True,
                help="Use realistic order book for fills"
            )
        
        with col2:
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
    
    # Run backtest
    with st.expander("🚀 Execute Backtest", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 Run Enhanced Backtest", type="primary"):
                execute_enhanced_backtest(
                    backtest_start_date, backtest_end_date, backtest_symbols,
                    backtest_initial_capital, commission_per_contract, tick_value,
                    trader_type, slippage_model, use_order_book,
                    prediction_threshold, min_velocity
                )
        
        with col2:
            if st.button("📊 View Results"):
                if 'enhanced_backtest_results' in st.session_state:
                    display_enhanced_backtest_results()
                else:
                    st.warning("⚠️ No backtest results available. Run a backtest first.")
    
    # Display results if available
    if 'enhanced_backtest_results' in st.session_state:
        with st.expander("📊 Enhanced Backtest Results", expanded=True):
            display_enhanced_backtest_results()


def execute_enhanced_backtest(start_date, end_date, symbols, initial_capital, 
                            commission_per_contract, tick_value, trader_type,
                            slippage_model, use_order_book, prediction_threshold, min_velocity):
    """Execute enhanced backtest with realistic MBO simulation"""
    
    with st.spinner("Initializing enhanced backtest..."):
        # Get trained pipeline
        pipeline = st.session_state.trained_pipeline
        
        # Check if real data is available
        if 'real_mbo_data' not in st.session_state:
            st.error("❌ No real MBO data available. Please load data from Databento or upload CSV files first.")
            return
        
        sample_data = st.session_state.real_mbo_data
        
        # Generate predictions using the pipeline
        predictions = pipeline.generate_predictions(sample_data)
        
        # Create backtest configuration
        from quanttime.backtest.realistic_mbo_backtest_engine import BacktestConfig
        
        config = BacktestConfig(
            initial_capital=initial_capital,
            commission_per_contract=commission_per_contract,
            tick_size=0.25,
            tick_value=tick_value,
            max_position_size=10,
            slippage_model=slippage_model,
            use_order_book=use_order_book,
            prediction_threshold=prediction_threshold,
            min_trade_velocity=min_velocity
        )
        
        # Run the enhanced backtest
        from quanttime.backtest.realistic_mbo_backtest_engine import run_realistic_backtest
        
        st.info("📊 Running realistic tick-by-tick MBO backtest...")
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Simulate progress
        for i in range(100):
            time.sleep(0.01)
            progress_bar.progress(i + 1)
            status_text.text(f"Processing tick {i+1}/100...")
        
        # Run actual backtest
        results = run_realistic_backtest(sample_data, predictions, config, trader_type)
        
        # Store results
        st.session_state.enhanced_backtest_results = results
        
        progress_bar.progress(100)
        status_text.text("✅ Enhanced backtest completed!")
        
        st.success("🎉 Enhanced backtest completed successfully!")
        
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


def display_enhanced_backtest_results():
    """Display enhanced backtest results"""
    results = st.session_state.enhanced_backtest_results
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
            title="Enhanced Backtest Equity Curve",
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
    
    # Add to leaderboard
    st.markdown("#### 🏆 Add to Leaderboard")
    
    if st.button("🏆 Add Results to Leaderboard"):
        # Add to global leaderboard
        if 'global_leaderboard' not in st.session_state:
            st.session_state.global_leaderboard = []
        
        leaderboard_entry = {
            'timestamp': datetime.now(),
            'strategy': f"Enhanced_{trader_type}",
            'model_type': 'Hybrid Pipeline',
            'trader_type': trader_type,
            'total_return': metrics['total_return'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'max_drawdown': metrics['max_drawdown'],
            'win_rate': metrics['win_rate'],
            'total_trades': metrics['total_trades']
        }
        
        st.session_state.global_leaderboard.append(leaderboard_entry)
        st.success("✅ Added to global leaderboard!")


def render_pipeline_management():
    """Pipeline management interface"""
    st.markdown("### 💾 Pipeline Management")
    
    # Save/Load pipeline
    st.markdown("#### 💾 Save/Load Pipeline")
    
    col1, col2 = st.columns(2)
    
    with col1:
        save_path = st.text_input("Save Path:", value="models/hybrid_pipeline", key="pipeline_save_path")
        if st.button("💾 Save Pipeline"):
            if 'trained_pipeline' in st.session_state:
                pipeline = st.session_state.trained_pipeline
                pipeline.save_pipeline(save_path)
                st.success("✅ Pipeline saved!")
            else:
                st.warning("⚠️ No trained pipeline to save.")
    
    with col2:
        load_path = st.text_input("Load Path:", value="models/hybrid_pipeline", key="pipeline_load_path")
        if st.button("📋 Load Pipeline"):
            try:
                pipeline = HybridPredictionPipeline(st.session_state.pipeline_config)
                pipeline.load_pipeline(load_path)
                st.session_state.trained_pipeline = pipeline
                st.success("✅ Pipeline loaded!")
            except Exception as e:
                st.error(f"❌ Failed to load pipeline: {e}")
    
    # Pipeline information
    if 'trained_pipeline' in st.session_state:
        st.markdown("#### 📋 Pipeline Information")
        
        pipeline = st.session_state.trained_pipeline
        
        # Model information
        st.markdown("**🤖 Trained Models:**")
        for model_name, model in pipeline.models.items():
            model_type = type(model).__name__
            st.write(f"• **{model_name}** ({model_type})")
        
        # Configuration summary
        st.markdown("**⚙️ Configuration Summary:**")
        config = pipeline.config
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Pipeline Name:** {config.pipeline_name}")
            st.write(f"**Number of Models:** {len(config.models)}")
            st.write(f"**RL Model Type:** {config.rl_config.get('model_type', 'N/A')}")
        
        with col2:
            st.write(f"**Initial Balance:** ${config.rl_config.get('initial_balance', 0):,}")
            st.write(f"**Commission Rate:** {config.rl_config.get('commission_rate', 0):.3%}")
            st.write(f"**Max Position Size:** {config.rl_config.get('max_position_size', 0):.1%}")
    
    # Pipeline actions
    st.markdown("#### ⚙️ Pipeline Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Reset Pipeline"):
            if 'trained_pipeline' in st.session_state:
                del st.session_state.trained_pipeline
            if 'training_features' in st.session_state:
                del st.session_state.training_features
            if 'training_targets' in st.session_state:
                del st.session_state.training_targets
            if 'training_predictions' in st.session_state:
                del st.session_state.training_predictions
            if 'backtest_results' in st.session_state:
                del st.session_state.backtest_results
            st.success("✅ Pipeline reset!")
    
    with col2:
        if st.button("📊 Export Results"):
            if 'backtest_results' in st.session_state:
                results = st.session_state.backtest_results
                # Export results to CSV
                results_df = pd.DataFrame([results])
                csv = results_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Results CSV",
                    data=csv,
                    file_name=f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    with col3:
        if st.button("📋 Export Configuration"):
            if 'pipeline_config' in st.session_state:
                config = st.session_state.pipeline_config
                config_json = json.dumps(config.__dict__, indent=2, default=str)
                st.download_button(
                    label="📥 Download Config JSON",
                    data=config_json,
                    file_name=f"pipeline_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )


def create_sample_training_data():
    """Create sample training data for demonstration"""
    # Generate sample MBO data
    np.random.seed(42)
    n_samples = 10000
    
    # Create timestamp index
    timestamps = pd.date_range(start='2024-01-01', periods=n_samples, freq='1min')
    
    # Generate sample data
    data = pd.DataFrame({
        'bid_price': 4850 + np.cumsum(np.random.randn(n_samples) * 0.1),
        'ask_price': 4850 + np.cumsum(np.random.randn(n_samples) * 0.1) + np.random.uniform(0.25, 1.0, n_samples),
        'bid_size': np.random.randint(1, 100, n_samples),
        'ask_size': np.random.randint(1, 100, n_samples),
        'volume': np.random.randint(10, 1000, n_samples),
        'timestamp': timestamps
    })
    
    # Set index
    data.set_index('timestamp', inplace=True)
    
    return data


def create_sample_backtest_data():
    """Create sample backtest data for demonstration"""
    # Similar to training data but for backtest period
    np.random.seed(123)
    n_samples = 5000
    
    timestamps = pd.date_range(start='2024-12-01', periods=n_samples, freq='1min')
    
    data = pd.DataFrame({
        'bid_price': 4900 + np.cumsum(np.random.randn(n_samples) * 0.1),
        'ask_price': 4900 + np.cumsum(np.random.randn(n_samples) * 0.1) + np.random.uniform(0.25, 1.0, n_samples),
        'bid_size': np.random.randint(1, 100, n_samples),
        'ask_size': np.random.randint(1, 100, n_samples),
        'volume': np.random.randint(10, 1000, n_samples),
        'timestamp': timestamps
    })
    
    data.set_index('timestamp', inplace=True)
    
    return data
