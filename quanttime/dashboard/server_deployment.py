#!/usr/bin/env python3
"""
Server Deployment and Task Management Dashboard Component.

Provides interfaces for:
- Server deployment and configuration
- Task submission (data processing, model training, backtesting)
- Progress monitoring and synchronization
- Performance benchmarking
"""

import streamlit as st
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from .server_task_manager import task_manager
from .server_benchmark import benchmarker
from .task_progress_tracker import progress_tracker

def render_server_deployment():
    """Render the server deployment and task management interface."""
    st.markdown("## 🖥️ Server Deployment & Task Management")
    
    # Server deployment section
    with st.expander("🚀 Server Deployment", expanded=True):
        render_deployment_section()
    
    # Task submission section
    with st.expander("📋 Task Submission", expanded=True):
        render_task_submission_section()
    
    # Progress monitoring section
    with st.expander("📊 Progress Monitoring", expanded=True):
        render_progress_monitoring_section()
    
    # Performance benchmarking section
    with st.expander("⚡ Performance Benchmarking", expanded=True):
        render_benchmarking_section()

def render_deployment_section():
    """Render server deployment controls."""
    st.markdown("### Deploy to Server")
    
    # Server selection
    server_options = list(task_manager.servers.keys())
    if not server_options:
        st.error("❌ No servers configured. Please add servers to `server/config/servers.json`")
        return
    
    selected_server = st.selectbox(
        "Select target server:",
        server_options,
        format_func=lambda x: f"{x.upper()} - {task_manager.servers[x].get('name', 'Unknown')}"
    )
    
    # Deployment status
    server_status = task_manager.get_server_status(selected_server)
    if server_status.get("connected", False):
        st.success(f"✅ {selected_server.upper()} is online")
        
        # Show server info
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Status", "🟢 Online")
            st.metric("Uptime", server_status.get("uptime", "Unknown"))
        with col2:
            st.metric("Memory", server_status.get("memory", "Unknown"))
            st.metric("Disk", server_status.get("disk", "Unknown"))
    else:
        st.error(f"❌ {selected_server.upper()} is offline")
        if "error" in server_status:
            st.error(f"Connection error: {server_status['error']}")
    
    # Deployment button
    if st.button(f"🚀 Deploy to {selected_server.upper()}", type="primary"):
        with st.spinner(f"Deploying to {selected_server.upper()}..."):
            success = task_manager.deploy_to_server(selected_server)
            if success:
                st.success(f"✅ Successfully deployed to {selected_server.upper()}")
            else:
                st.error(f"❌ Deployment failed for {selected_server.upper()}")
    
    # Sync button
    if st.button(f"🔄 Sync from {selected_server.upper()}"):
        with st.spinner(f"Syncing from {selected_server.upper()}..."):
            success = task_manager.sync_server_progress(selected_server)
            if success:
                st.success(f"✅ Successfully synced from {selected_server.upper()}")
            else:
                st.error(f"❌ Sync failed for {selected_server.upper()}")

def render_task_submission_section():
    """Render task submission interface."""
    st.markdown("### Submit Tasks to Server")
    
    # Server selection
    server_options = list(task_manager.servers.keys())
    if not server_options:
        st.error("❌ No servers configured")
        return
    
    selected_server = st.selectbox(
        "Target server:",
        server_options,
        key="task_server"
    )
    
    # Task type selection
    task_type = st.selectbox(
        "Task type:",
        ["data_processing", "model_training", "backtest"],
        format_func=lambda x: {
            "data_processing": "📊 Data Processing & Feature Engineering",
            "model_training": "🤖 Model Training",
            "backtest": "📈 Backtesting"
        }[x]
    )
    
    # Task-specific parameters
    task_params = get_task_parameters(task_type)
    
    # Submit button
    if st.button("🚀 Submit Task", type="primary"):
        if task_params:
            with st.spinner(f"Submitting {task_type} to {selected_server.upper()}..."):
                success = task_manager.send_task_to_server(selected_server, task_type, task_params)
                if success:
                    st.success(f"✅ Task submitted to {selected_server.upper()}")
                    # Add to progress tracker
                    progress_tracker.add_task(selected_server, task_type, task_params)
                else:
                    st.error(f"❌ Task submission failed")

def get_task_parameters(task_type: str) -> Optional[Dict[str, Any]]:
    """Get task-specific parameters based on task type."""
    if task_type == "data_processing":
        st.markdown("#### Data Processing Parameters")
        
        # Date selection
        available_dates = get_available_dates()
        if not available_dates:
            st.warning("⚠️ No raw data dates available")
            return None
        
        selected_date = st.selectbox("Select date to process:", available_dates)
        
        # Schema selection
        schema_options = ["basic_normalized_v1", "execution_aware_light_v1", "comprehensive_v1"]
        selected_schema = st.selectbox("Select schema:", schema_options)
        
        # Processing options
        col1, col2 = st.columns(2)
        with col1:
            trading_hours_only = st.checkbox("Trading hours only", value=True)
            max_rows = st.number_input("Max rows (0 = all)", min_value=0, value=0)
        with col2:
            intensity_level = st.selectbox("Intensity level:", ["light", "medium", "heavy"])
        
        return {
            "date_str": selected_date,
            "schema_name": selected_schema,
            "trading_hours_only": trading_hours_only,
            "max_rows": max_rows if max_rows > 0 else None,
            "intensity_level": intensity_level
        }
    
    elif task_type == "model_training":
        st.markdown("#### Model Training Parameters")
        
        # Model configuration
        col1, col2 = st.columns(2)
        with col1:
            model_name = st.text_input("Model name:", value=f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            model_type = st.selectbox("Model type:", ["LGBM", "LSTM", "TRANSFORMER", "TCN"])
        with col2:
            data_schema = st.selectbox("Data schema:", ["basic_normalized_v1", "execution_aware_light_v1"])
            epochs = st.number_input("Training epochs:", min_value=1, value=100)
        
        # Training options
        batch_size = st.number_input("Batch size:", min_value=1, value=1024)
        learning_rate = st.number_input("Learning rate:", min_value=0.0001, max_value=1.0, value=0.001, format="%.4f")
        use_gpu = st.checkbox("Use GPU acceleration", value=True)
        
        return {
            "model_name": model_name,
            "model_type": model_type,
            "data_schema": data_schema,
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "use_gpu": use_gpu
        }
    
    elif task_type == "backtest":
        st.markdown("#### Backtesting Parameters")
        
        # Strategy configuration
        col1, col2 = st.columns(2)
        with col1:
            strategy_name = st.text_input("Strategy name:", value="basic_strategy")
            data_schema = st.selectbox("Data schema:", ["basic_normalized_v1", "execution_aware_light_v1"])
        with col2:
            start_date = st.date_input("Start date")
            end_date = st.date_input("End date")
        
        # Backtest options
        commission = st.number_input("Commission per contract:", min_value=0.0, value=2.5)
        slippage_ticks = st.number_input("Slippage (ticks):", min_value=0, value=1)
        
        return {
            "strategy_name": strategy_name,
            "data_schema": data_schema,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "commission": commission,
            "slippage_ticks": slippage_ticks
        }
    
    return None

def get_available_dates() -> list:
    """Get available raw data dates."""
    try:
        from quanttime.data.processor import get_processor
        processor = get_processor()
        return processor.list_available_dates("mbo")
    except Exception as e:
        st.error(f"Error getting available dates: {e}")
        return []

def render_progress_monitoring_section():
    """Render progress monitoring interface."""
    st.markdown("### Task Progress Monitoring")
    
    # Refresh button
    if st.button("🔄 Refresh Progress"):
        st.rerun()
    
    # Show active tasks
    active_tasks = progress_tracker.get_active_tasks()
    if not active_tasks:
        st.info("No active tasks")
        return
    
    for task in active_tasks:
        with st.container():
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**{task['type']}** on {task['server'].upper()}")
                st.caption(f"Started: {task['start_time']}")
            
            with col2:
                progress = task.get('progress', 0)
                st.progress(progress / 100)
                st.caption(f"{progress:.0f}%")
            
            with col3:
                if st.button("⏹️ Stop", key=f"stop_{task['id']}"):
                    progress_tracker.stop_task(task['id'])
                    st.rerun()

def render_benchmarking_section():
    """Render performance benchmarking interface."""
    st.markdown("### Performance Benchmarking")
    
    # Server selection for benchmarking
    server_options = list(task_manager.servers.keys())
    if not server_options:
        st.error("❌ No servers configured")
        return
    
    benchmark_server = st.selectbox(
        "Select server to benchmark:",
        server_options,
        key="benchmark_server"
    )
    
    # Benchmark button
    if st.button("⚡ Run Performance Benchmark", type="primary"):
        with st.spinner(f"Benchmarking {benchmark_server.upper()}..."):
            try:
                results = benchmarker.benchmark_remote_server(benchmark_server)
                if results:
                    st.success("✅ Benchmark completed")
                    
                    # Display results
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("CPU Score", f"{results.get('cpu_score', 0):.1f}")
                    with col2:
                        st.metric("Memory Score", f"{results.get('memory_score', 0):.1f}")
                    with col3:
                        st.metric("Disk Score", f"{results.get('disk_score', 0):.1f}")
                    
                    # Show detailed results
                    with st.expander("Detailed Benchmark Results"):
                        st.json(results)
                else:
                    st.error("❌ Benchmark failed")
            except Exception as e:
                st.error(f"❌ Benchmark error: {e}")

def run_performance_benchmark():
    """Run performance benchmark on selected server."""
    st.info("Performance benchmarking functionality will be implemented here")
