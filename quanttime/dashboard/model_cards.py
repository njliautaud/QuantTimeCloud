"""
Model Card Display Components for QuantTime ML Trading Suite.
Provides card-based display for trained models with Kanban-style organization.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from ..models.model_registry import ModelRegistry

def render_model_cards_dashboard():
    """Render the main model cards dashboard."""
    st.header("🤖 Model Management")
    
    # Initialize model registry
    model_registry = ModelRegistry()
    
    # Get model statistics
    stats = model_registry.get_model_statistics()
    
    # Display statistics
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Models", stats.get('total_models', 0))
        with col2:
            st.metric("Avg Training Time", f"{stats.get('avg_training_time', 0):.1f} min")
        with col3:
            st.metric("Avg Test RMSE", f"{stats.get('avg_test_rmse', 0):.4f}")
        with col4:
            st.metric("Avg Test R²", f"{stats.get('avg_test_r2', 0):.3f}")
    
    # Filter options
    st.subheader("📊 Model Overview")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        model_type_filter = st.selectbox(
            "Model Type",
            ["All"] + list(stats.get('models_by_type', {}).keys()),
            key="model_type_filter"
        )
    with col2:
        symbol_filter = st.selectbox(
            "Symbol",
            ["All"] + list(stats.get('models_by_symbol', {}).keys()),
            key="symbol_filter"
        )
    with col3:
        status_filter = st.selectbox(
            "Status",
            ["All"] + list(stats.get('models_by_status', {}).keys()),
            key="status_filter"
        )
    
    # Get filtered models
    model_type = None if model_type_filter == "All" else model_type_filter
    symbol = None if symbol_filter == "All" else symbol_filter
    status = None if status_filter == "All" else status_filter
    
    model_cards = model_registry.get_model_cards(
        model_type=model_type,
        symbol=symbol
    )
    
    if not model_cards:
        st.info("No models found. Train a model first to see it here.")
        return
    
    # Render Kanban board
    render_kanban_board(model_cards, model_registry)

def render_kanban_board(model_cards: List[Dict[str, Any]], model_registry: ModelRegistry):
    """Render Kanban-style board with model cards."""
    
    # Define columns
    columns = {
        "trained": "✅ Trained",
        "ready_for_backtest": "🧪 Ready for Backtest", 
        "backtested": "📈 Backtested",
        "deployed": "🚀 Deployed"
    }
    
    # Group models by status
    model_groups = {}
    for status in columns.keys():
        model_groups[status] = [card for card in model_cards if card['status'] == status]
    
    # Create columns
    cols = st.columns(len(columns))
    
    for i, (status, title) in enumerate(columns.items()):
        with cols[i]:
            st.subheader(f"{title} ({len(model_groups[status])})")
            
            # Render cards in this column
            for card in model_groups[status]:
                render_model_card(card, model_registry)

def render_model_card(card: Dict[str, Any], model_registry: ModelRegistry):
    """Render a single model card."""
    
    # Card container with custom styling
    with st.container():
        # Card header with color
        st.markdown(f"""
        <div style="
            border: 2px solid {card['card_color']};
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
            background: linear-gradient(135deg, {card['card_color']}20, {card['card_color']}10);
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        ">
        """, unsafe_allow_html=True)
        
        # Model type badge
        st.markdown(f"""
        <div style="
            background-color: {card['card_color']};
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
            display: inline-block;
            margin-bottom: 8px;
        ">
            {card['model_type'].upper()}
        </div>
        """, unsafe_allow_html=True)
        
        # Model title
        st.markdown(f"""
        <h4 style="margin: 8px 0; color: #333;">
            {card['title']}
        </h4>
        """, unsafe_allow_html=True)
        
        # Subtitle
        st.markdown(f"""
        <p style="margin: 4px 0; color: #666; font-size: 14px;">
            {card['subtitle']}
        </p>
        """, unsafe_allow_html=True)
        
        # Performance metrics
        st.markdown(f"""
        <div style="margin: 8px 0; padding: 8px; background: rgba(255,255,255,0.7); border-radius: 6px;">
            <strong>Performance:</strong><br>
            <span style="font-size: 13px; color: #444;">{card['performance']}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Training info
        st.markdown(f"""
        <div style="margin: 6px 0; font-size: 12px; color: #555;">
            📊 {card['training_info']}
        </div>
        """, unsafe_allow_html=True)
        
        # Timeframe info (if available)
        if 'timeframe' in card and card['timeframe']:
            timeframe_badge = "🕐 Market Hours" if "market_hours" in card['timeframe'] else "🕐 24H"
            st.markdown(f"""
            <div style="margin: 6px 0; font-size: 12px; color: #555;">
                {timeframe_badge} {card['timeframe']}
            </div>
            """, unsafe_allow_html=True)
        
        # Parameters
        st.markdown(f"""
        <div style="margin: 6px 0; font-size: 12px; color: #555;">
            ⚙️ {card['parameters']}
        </div>
        """, unsafe_allow_html=True)
        
        # Top features
        if card['top_features']:
            features_text = ", ".join(card['top_features'][:3])
            st.markdown(f"""
            <div style="margin: 6px 0; font-size: 12px; color: #555;">
                🎯 Top: {features_text}
            </div>
            """, unsafe_allow_html=True)
        
        # Model size
        st.markdown(f"""
        <div style="margin: 6px 0; font-size: 12px; color: #555;">
            💾 {card['model_size_mb']:.1f} MB
        </div>
        """, unsafe_allow_html=True)
        
        # Created date
        created_date = datetime.fromisoformat(card['created_at'].replace('Z', '+00:00'))
        st.markdown(f"""
        <div style="margin: 6px 0; font-size: 12px; color: #555;">
            📅 {created_date.strftime('%Y-%m-%d %H:%M')}
        </div>
        """, unsafe_allow_html=True)
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔍 View", key=f"view_{card['id']}", use_container_width=True):
                st.session_state['selected_model_id'] = card['id']
                st.rerun()
        
        with col2:
            if card['ready_for_backtest']:
                if st.button("🧪 Backtest", key=f"backtest_{card['id']}", use_container_width=True):
                    st.session_state['backtest_model_id'] = card['id']
                    st.rerun()
            else:
                st.button("⏳ Training...", key=f"wait_{card['id']}", use_container_width=True, disabled=True)
        
        with col3:
            if st.button("🗑️ Delete", key=f"delete_{card['id']}", use_container_width=True):
                if model_registry.delete_model(card['id']):
                    st.success(f"Model {card['title']} deleted successfully")
                    st.rerun()
                else:
                    st.error("Failed to delete model")
        
        st.markdown("</div>", unsafe_allow_html=True)

def render_model_details(model_id: str):
    """Render detailed view of a specific model."""
    model_registry = ModelRegistry()
    metadata = model_registry.get_model_metadata(model_id)
    
    if not metadata:
        st.error("Model not found")
        return
    
    st.header(f"🔍 Model Details: {metadata.model_name}")
    
    # Back button
    if st.button("← Back to Models"):
        if 'selected_model_id' in st.session_state:
            del st.session_state['selected_model_id']
        st.rerun()
    
    # Model information tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Overview", "📊 Performance", "🎯 Features", "⚙️ Configuration", "📈 Predictions"])
    
    with tab1:
        render_model_overview(metadata)
    
    with tab2:
        render_model_performance(metadata)
    
    with tab3:
        render_model_features(metadata)
    
    with tab4:
        render_model_configuration(metadata)
    
    with tab5:
        render_model_predictions(metadata)

def render_model_overview(metadata):
    """Render model overview tab."""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Model Information")
        st.write(f"**Model ID:** {metadata.model_id}")
        st.write(f"**Name:** {metadata.model_name}")
        st.write(f"**Type:** {metadata.model_type}")
        st.write(f"**Symbol:** {metadata.symbol}")
        st.write(f"**Data Source:** {metadata.data_source}")
        st.write(f"**Status:** {metadata.status}")
        st.write(f"**Created:** {metadata.created_at}")
        st.write(f"**Last Updated:** {metadata.last_updated}")
        
        # Status indicators
        col_a, col_b = st.columns(2)
        with col_a:
            if metadata.ready_for_backtest:
                st.success("✅ Ready for Backtest")
            else:
                st.warning("⏳ Not Ready")
        
        with col_b:
            if metadata.ready_for_deployment:
                st.success("✅ Ready for Deployment")
            else:
                st.info("📋 Not Deployed")
    
    with col2:
        st.subheader("Training Information")
        st.write(f"**Training Duration:** {metadata.training_duration_minutes:.1f} minutes")
        st.write(f"**Training Samples:** {metadata.training_samples:,}")
        st.write(f"**Validation Samples:** {metadata.validation_samples:,}")
        st.write(f"**Test Samples:** {metadata.test_samples:,}")
        st.write(f"**Model Size:** {metadata.model_size_mb:.1f} MB")
        st.write(f"**Training Start:** {metadata.training_start_date}")
        st.write(f"**Training End:** {metadata.training_end_date}")
        
        if metadata.notes:
            st.subheader("Notes")
            st.write(metadata.notes)

def render_model_performance(metadata):
    """Render model performance tab."""
    st.subheader("Performance Metrics")
    
    # Create performance comparison chart
    metrics_data = {
        'Dataset': ['Train', 'Validation', 'Test'],
        'RMSE': [metadata.train_rmse, metadata.val_rmse, metadata.test_rmse],
        'MAE': [metadata.train_mae, metadata.val_mae, metadata.test_mae],
        'R²': [metadata.train_r2, metadata.val_r2, metadata.test_r2]
    }
    
    df_metrics = pd.DataFrame(metrics_data)
    
    # RMSE comparison
    fig_rmse = px.bar(df_metrics, x='Dataset', y='RMSE', 
                     title='RMSE by Dataset',
                     color='Dataset',
                     color_discrete_map={'Train': '#1f77b4', 'Validation': '#ff7f0e', 'Test': '#2ca02c'})
    st.plotly_chart(fig_rmse, use_container_width=True)
    
    # R² comparison
    fig_r2 = px.bar(df_metrics, x='Dataset', y='R²',
                   title='R² Score by Dataset',
                   color='Dataset',
                   color_discrete_map={'Train': '#1f77b4', 'Validation': '#ff7f0e', 'Test': '#2ca02c'})
    st.plotly_chart(fig_r2, use_container_width=True)
    
    # Metrics table
    st.subheader("Detailed Metrics")
    st.dataframe(df_metrics, use_container_width=True)

def render_model_features(metadata):
    """Render model features tab."""
    st.subheader("Feature Importance")
    
    if metadata.top_features and metadata.feature_importance_scores:
        # Create feature importance chart
        fig = px.bar(
            x=metadata.top_features,
            y=metadata.feature_importance_scores,
            title='Top Feature Importance',
            labels={'x': 'Feature', 'y': 'Importance Score'}
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        
        # Feature importance table
        feature_df = pd.DataFrame({
            'Feature': metadata.top_features,
            'Importance Score': metadata.feature_importance_scores
        })
        st.dataframe(feature_df, use_container_width=True)
    else:
        st.info("No feature importance data available")

def render_model_configuration(metadata):
    """Render model configuration tab."""
    st.subheader("Model Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Model Parameters:**")
        st.write(f"• Orderbook Depth: {metadata.orderbook_depth}")
        st.write(f"• Sequence Length: {metadata.sequence_length}")
        st.write(f"• Feature Window: {metadata.feature_window}")
        st.write(f"• Prediction Horizon: {metadata.prediction_horizon}")
        st.write(f"• Batch Size: {metadata.batch_size}")
        st.write(f"• Learning Rate: {metadata.learning_rate}")
    
    with col2:
        if metadata.hyperparameters:
            st.write("**Hyperparameters:**")
            for key, value in metadata.hyperparameters.items():
                st.write(f"• {key}: {value}")
        
        if metadata.training_config:
            st.write("**Training Configuration:**")
            for key, value in metadata.training_config.items():
                st.write(f"• {key}: {value}")

def render_model_predictions(metadata):
    """Render model predictions tab."""
    st.subheader("Real-time Predictions")
    
    # Load the actual model to get current predictions
    model_registry = ModelRegistry()
    model = model_registry.get_model(metadata.model_id)
    
    if model:
        # This would show real-time predictions if the model is loaded
        st.info("Model loaded successfully. Real-time predictions would be displayed here.")
        
        # Placeholder for prediction display
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("1min Prediction", "0.0023", delta="0.0012")
        with col2:
            st.metric("3min Prediction", "0.0045", delta="-0.0021")
        with col3:
            st.metric("5min Prediction", "0.0067", delta="0.0034")
    else:
        st.warning("Model could not be loaded. Predictions unavailable.")

def render_backtest_model_selector():
    """Render model selector for backtesting."""
    st.subheader("🧪 Select Model for Backtesting")
    
    model_registry = ModelRegistry()
    ready_models = model_registry.list_models(status='trained')
    
    if not ready_models:
        st.info("No models ready for backtesting. Train a model first.")
        return None
    
    # Create model selection interface
    model_options = {f"{m.model_name} ({m.symbol})": m.model_id for m in ready_models}
    
    selected_model_name = st.selectbox(
        "Choose a model to backtest:",
        list(model_options.keys()),
        key="backtest_model_selector"
    )
    
    if selected_model_name:
        selected_model_id = model_options[selected_model_name]
        selected_model = model_registry.get_model_metadata(selected_model_id)
        
        # Display model summary
        st.subheader("Selected Model Summary")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Model:** {selected_model.model_name}")
            st.write(f"**Type:** {selected_model.model_type}")
            st.write(f"**Symbol:** {selected_model.symbol}")
            st.write(f"**Test RMSE:** {selected_model.test_rmse:.4f}")
        
        with col2:
            st.write(f"**Test R²:** {selected_model.test_r2:.3f}")
            st.write(f"**Training Samples:** {selected_model.training_samples:,}")
            st.write(f"**Model Size:** {selected_model.model_size_mb:.1f} MB")
            st.write(f"**Created:** {selected_model.created_at[:10]}")
        
        return selected_model_id
    
    return None
