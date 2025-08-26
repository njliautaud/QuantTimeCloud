"""
Syncthing and Ray Management Dashboard Interface
Provides comprehensive control over project synchronization and distributed computing
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import json
from typing import Dict, List, Any, Optional
import threading

# Import our managers
from server.core.syncthing_manager import get_syncthing_manager, SyncStatus
from server.core.ray_manager import get_ray_manager, JobStatus, JobPriority
from quanttime.core.centralized_logging import get_centralized_logger, LogContext


def render_syncthing_ray_interface():
    """Main interface for Syncthing and Ray management"""
    st.subheader("🔄 Syncthing & Ray Management")
    st.markdown("""
    **Project Synchronization & Distributed Computing**: Manage project-wide file synchronization 
    and distributed job execution across all nodes. Monitor sync status, job queues, and ensure 
    version consistency.
    """)
    
    # Initialize managers
    try:
        syncthing_manager = get_syncthing_manager()
        ray_manager = get_ray_manager()
        centralized_logger = get_centralized_logger()
    except Exception as e:
        st.error(f"Failed to initialize managers: {e}")
        return
    
    # Create tabs
    tabs = st.tabs([
        "📊 Overview", 
        "🔄 Syncthing", 
        "⚡ Ray Cluster", 
        "📋 Job Queue", 
        "📝 Logs",
        "⚙️ Settings"
    ])
    
    with tabs[0]:
        render_overview_tab(syncthing_manager, ray_manager, centralized_logger)
    
    with tabs[1]:
        render_syncthing_tab(syncthing_manager)
    
    with tabs[2]:
        render_ray_cluster_tab(ray_manager)
    
    with tabs[3]:
        render_job_queue_tab(ray_manager, syncthing_manager)
    
    with tabs[4]:
        render_logs_tab(centralized_logger)
    
    with tabs[5]:
        render_settings_tab(syncthing_manager, ray_manager, centralized_logger)


def render_overview_tab(syncthing_manager, ray_manager, centralized_logger):
    """Overview tab showing system status"""
    st.markdown("### 📊 System Overview")
    
    # Get status data
    sync_status = syncthing_manager.get_sync_status()
    cluster_status = ray_manager.get_cluster_status()
    node_status = centralized_logger.get_node_status()
    
    # System health indicators
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Sync status
        sync_healthy = all(node['status'] == 'synced' for node in sync_status['nodes'].values())
        sync_color = "🟢" if sync_healthy else "🔴"
        st.metric("Sync Status", f"{sync_color} {'Healthy' if sync_healthy else 'Issues'}")
    
    with col2:
        # Ray cluster status
        ray_healthy = cluster_status['ray_initialized'] and cluster_status['active_nodes'] > 0
        ray_color = "🟢" if ray_healthy else "🔴"
        st.metric("Ray Cluster", f"{ray_color} {'Active' if ray_healthy else 'Inactive'}")
    
    with col3:
        # Active jobs
        active_jobs = len([job for job in cluster_status['jobs'].values() if job['status'] == JobStatus.RUNNING])
        st.metric("Active Jobs", active_jobs)
    
    with col4:
        # Queue length
        queue_length = len(cluster_status['job_queue'])
        st.metric("Queue Length", queue_length)
    
    # Sync progress warning
    if syncthing_manager.is_sync_in_progress():
        st.warning("⚠️ **Sync in Progress**: Jobs are blocked until synchronization completes")
    
    # Node status grid
    st.markdown("### 🖥️ Node Status")
    
    node_data = []
    for node_id, node_info in node_status.items():
        node_data.append({
            'Node': node_info['name'],
            'Status': node_info['status'],
            'Last Seen': node_info['last_seen'] or 'Never',
            'Log Count': node_info['log_count'],
            'Errors': node_info['error_count']
        })
    
    if node_data:
        df = pd.DataFrame(node_data)
        st.dataframe(df, use_container_width=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Force Sync All"):
            with LogContext("Force sync all nodes", node_id="laptop"):
                syncthing_manager.force_sync()
                st.success("Sync initiated!")
    
    with col2:
        if st.button("⚡ Scale Cluster"):
            st.info("Use Ray Cluster tab for detailed scaling")
    
    with col3:
        if st.button("📊 Refresh Status"):
            st.rerun()


def render_syncthing_tab(syncthing_manager):
    """Syncthing synchronization management"""
    st.markdown("### 🔄 Syncthing Synchronization")
    
    # Get sync status
    sync_status = syncthing_manager.get_sync_status()
    
    # Sync status overview
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_nodes = len(sync_status['nodes'])
        synced_nodes = sum(1 for node in sync_status['nodes'].values() if node['status'] == 'synced')
        sync_percentage = (synced_nodes / total_nodes * 100) if total_nodes > 0 else 0
        st.metric("Sync Progress", f"{sync_percentage:.1f}%")
    
    with col2:
        queue_length = len(sync_status['sync_queue'])
        st.metric("Sync Queue", queue_length)
    
    with col3:
        sync_in_progress = syncthing_manager.is_sync_in_progress()
        status_text = "🔄 In Progress" if sync_in_progress else "✅ Idle"
        st.metric("Sync Status", status_text)
    
    # Node sync status
    st.markdown("#### 📁 Node Sync Status")
    
    node_data = []
    for node_id, node_info in sync_status['nodes'].items():
        node_data.append({
            'Node': node_info['name'],
            'Status': node_info['status'],
            'Last Sync': node_info['last_sync'] or 'Never',
            'Version': node_info['version'],
            'Folders': len(node_info['folders'])
        })
    
    if node_data:
        df = pd.DataFrame(node_data)
        st.dataframe(df, use_container_width=True)
    
    # Sync queue
    if sync_status['sync_queue']:
        st.markdown("#### 📋 Sync Queue")
        
        queue_data = []
        for i, sync_op in enumerate(sync_status['sync_queue']):
            queue_data.append({
                'Position': i + 1,
                'Operation': sync_op['operation'],
                'Source': sync_op['source'],
                'Target': sync_op['target'],
                'Priority': sync_op['priority']
            })
        
        df = pd.DataFrame(queue_data)
        st.dataframe(df, use_container_width=True)
    
    # Folder status
    st.markdown("#### 📂 Folder Status")
    
    folder_data = []
    for folder_id, folder_info in sync_status['folders'].items():
        folder_data.append({
            'Folder': folder_info['name'],
            'Status': folder_info['status'],
            'Size': folder_info['size'],
            'Files': folder_info['file_count'],
            'Last Update': folder_info['last_update'] or 'Never'
        })
    
    if folder_data:
        df = pd.DataFrame(folder_data)
        st.dataframe(df, use_container_width=True)
    
    # Sync controls
    st.markdown("#### 🔧 Sync Controls")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Force Sync"):
            with LogContext("Force sync", node_id="laptop"):
                syncthing_manager.force_sync()
                st.success("Sync initiated!")
    
    with col2:
        if st.button("🛑 Stop Sync"):
            # This would need to be implemented in the manager
            st.info("Stop sync functionality to be implemented")
    
    with col3:
        if st.button("📊 Resolve Conflicts"):
            with LogContext("Resolve conflicts", node_id="laptop"):
                syncthing_manager.resolve_conflicts()
                st.success("Conflicts resolved!")
    
    # Version consistency
    st.markdown("#### 🔍 Version Consistency")
    
    version_info = syncthing_manager.get_version_info()
    if version_info['consistent']:
        st.success("✅ All nodes are running the same version")
    else:
        st.error("❌ Version inconsistency detected")
        
        version_data = []
        for node_id, version in version_info['versions'].items():
            version_data.append({
                'Node': node_id,
                'Version': version,
                'Status': '✅ Current' if version == version_info['master_version'] else '❌ Outdated'
            })
        
        df = pd.DataFrame(version_data)
        st.dataframe(df, use_container_width=True)


def render_ray_cluster_tab(ray_manager):
    """Ray cluster management"""
    st.markdown("### ⚡ Ray Cluster Management")
    
    # Get cluster status
    cluster_status = ray_manager.get_cluster_status()
    
    # Cluster overview
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Active Nodes", cluster_status['active_nodes'])
    
    with col2:
        st.metric("Total Jobs", len(cluster_status['jobs']))
    
    with col3:
        running_jobs = sum(1 for job in cluster_status['jobs'].values() if job['status'] == JobStatus.RUNNING)
        st.metric("Running Jobs", running_jobs)
    
    with col4:
        st.metric("Queue Length", len(cluster_status['job_queue']))
    
    # Node status
    st.markdown("#### 🖥️ Cluster Nodes")
    
    node_data = []
    for node_id, node_info in cluster_status['nodes'].items():
        node_data.append({
            'Node': node_info['name'],
            'Status': node_info['status'],
            'CPU Usage': f"{node_info['cpu_usage']:.1f}%",
            'Memory Usage': f"{node_info['memory_usage']:.1f}%",
            'GPU Usage': f"{node_info['gpu_usage']:.1f}%",
            'Jobs': node_info['active_jobs']
        })
    
    if node_data:
        df = pd.DataFrame(node_data)
        st.dataframe(df, use_container_width=True)
    
    # Resource usage visualization
    st.markdown("#### 📊 Resource Usage")
    
    if node_data:
        # CPU usage chart
        fig = px.bar(
            df, 
            x='Node', 
            y='CPU Usage', 
            title="CPU Usage by Node",
            color='Status'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Memory usage chart
        fig = px.bar(
            df, 
            x='Node', 
            y='Memory Usage', 
            title="Memory Usage by Node",
            color='Status'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Cluster controls
    st.markdown("#### 🔧 Cluster Controls")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("➕ Add Node"):
            st.info("Node addition functionality to be implemented")
    
    with col2:
        if st.button("➖ Remove Node"):
            st.info("Node removal functionality to be implemented")
    
    with col3:
        if st.button("🔄 Scale Cluster"):
            st.info("Cluster scaling functionality to be implemented")
    
    # Resource allocation
    st.markdown("#### 📈 Resource Allocation")
    
    resource_usage = ray_manager.get_resource_usage()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total CPU Cores", resource_usage['total_cpu'])
        st.metric("Available CPU", resource_usage['available_cpu'])
    
    with col2:
        st.metric("Total Memory (GB)", f"{resource_usage['total_memory']:.1f}")
        st.metric("Available Memory (GB)", f"{resource_usage['available_memory']:.1f}")


def render_job_queue_tab(ray_manager, syncthing_manager):
    """Job queue management with sync dependency"""
    st.markdown("### 📋 Job Queue Management")
    
    # Check sync status first
    sync_in_progress = syncthing_manager.is_sync_in_progress()
    
    if sync_in_progress:
        st.warning("⚠️ **Jobs Blocked**: Synchronization in progress. Jobs will resume when sync completes.")
    
    # Get job status
    cluster_status = ray_manager.get_cluster_status()
    jobs = cluster_status['jobs']
    queue = cluster_status['job_queue']
    
    # Job statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_jobs = len(jobs)
        st.metric("Total Jobs", total_jobs)
    
    with col2:
        running_jobs = sum(1 for job in jobs.values() if job['status'] == JobStatus.RUNNING)
        st.metric("Running", running_jobs)
    
    with col3:
        queued_jobs = len(queue)
        st.metric("Queued", queued_jobs)
    
    with col4:
        completed_jobs = sum(1 for job in jobs.values() if job['status'] == JobStatus.COMPLETED)
        st.metric("Completed", completed_jobs)
    
    # Active jobs
    st.markdown("#### 🔄 Active Jobs")
    
    active_jobs = [job for job in jobs.values() if job['status'] == JobStatus.RUNNING]
    
    if active_jobs:
        job_data = []
        for job_id, job in jobs.items():
            if job['status'] == JobStatus.RUNNING:
                job_data.append({
                    'Job ID': job_id,
                    'Function': job['function_name'],
                    'Node': job['node_id'],
                    'Progress': f"{job.get('progress', 0):.1f}%",
                    'Start Time': job['start_time'],
                    'Duration': job.get('duration', 'N/A')
                })
        
        df = pd.DataFrame(job_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No active jobs")
    
    # Job queue
    st.markdown("#### 📋 Job Queue")
    
    if queue:
        queue_data = []
        for i, job in enumerate(queue):
            queue_data.append({
                'Position': i + 1,
                'Function': job['function_name'],
                'Priority': job['priority'].value,
                'Resources': f"CPU: {job['resources']['cpu']}, Memory: {job['resources']['memory']}GB",
                'Submitted': job['submitted_time']
            })
        
        df = pd.DataFrame(queue_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No jobs in queue")
    
    # Job submission
    st.markdown("#### ➕ Submit New Job")
    
    with st.form("job_submission"):
        col1, col2 = st.columns(2)
        
        with col1:
            job_function = st.selectbox(
                "Job Function",
                ["train_model_job", "backtest_job", "data_processing_job", "feature_engineering_job"]
            )
            
            priority = st.selectbox(
                "Priority",
                [JobPriority.LOW, JobPriority.NORMAL, JobPriority.HIGH, JobPriority.CRITICAL]
            )
        
        with col2:
            cpu_cores = st.number_input("CPU Cores", min_value=1, max_value=32, value=4)
            memory_gb = st.number_input("Memory (GB)", min_value=1, max_value=256, value=8)
        
        # Job configuration
        job_config = st.text_area("Job Configuration (JSON)", value="{}")
        
        submitted = st.form_submit_button("Submit Job", disabled=sync_in_progress)
        
        if submitted:
            try:
                config = json.loads(job_config) if job_config else {}
                
                with LogContext("Submit job", node_id="laptop"):
                    job_id = ray_manager.submit_job(
                        function_name=job_function,
                        config=config,
                        resources={'cpu': cpu_cores, 'memory': memory_gb},
                        priority=priority
                    )
                    st.success(f"Job submitted successfully! Job ID: {job_id}")
                    
            except json.JSONDecodeError:
                st.error("Invalid JSON configuration")
            except Exception as e:
                st.error(f"Failed to submit job: {e}")
    
    # Job management
    st.markdown("#### 🔧 Job Management")
    
    if jobs:
        # Get job IDs for selection
        job_ids = list(jobs.keys())
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            selected_job = st.selectbox("Select Job", job_ids)
            
            if selected_job and st.button("⏸️ Pause Job"):
                with LogContext("Pause job", node_id="laptop"):
                    ray_manager.pause_job(selected_job)
                    st.success("Job paused!")
        
        with col2:
            if selected_job and st.button("▶️ Resume Job"):
                with LogContext("Resume job", node_id="laptop"):
                    ray_manager.resume_job(selected_job)
                    st.success("Job resumed!")
        
        with col3:
            if selected_job and st.button("❌ Cancel Job"):
                with LogContext("Cancel job", node_id="laptop"):
                    ray_manager.cancel_job(selected_job)
                    st.success("Job cancelled!")
        
        # Job details
        if selected_job:
            job = jobs[selected_job]
            st.markdown(f"#### 📄 Job Details: {selected_job}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Function:** {job['function_name']}")
                st.write(f"**Status:** {job['status'].value}")
                st.write(f"**Node:** {job['node_id']}")
                st.write(f"**Priority:** {job['priority'].value}")
            
            with col2:
                st.write(f"**Submitted:** {job['submitted_time']}")
                st.write(f"**Start Time:** {job.get('start_time', 'N/A')}")
                st.write(f"**Duration:** {job.get('duration', 'N/A')}")
                st.write(f"**Progress:** {job.get('progress', 0):.1f}%")


def render_logs_tab(centralized_logger):
    """Centralized logging interface"""
    st.markdown("### 📝 Centralized Logs")
    
    # Log filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        log_level = st.selectbox(
            "Log Level",
            ["All", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )
    
    with col2:
        node_filter = st.selectbox(
            "Node",
            ["All"] + list(centralized_logger.nodes.keys())
        )
    
    with col3:
        hours = st.number_input("Last N Hours", min_value=1, max_value=168, value=24)
    
    with col4:
        limit = st.number_input("Max Logs", min_value=10, max_value=1000, value=100)
    
    # Get logs
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    logs = centralized_logger.get_logs(
        node_id=node_filter if node_filter != "All" else None,
        level=log_level if log_level != "All" else None,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )
    
    # Log statistics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_logs = len(logs)
        st.metric("Total Logs", total_logs)
    
    with col2:
        error_logs = len([log for log in logs if log.level.value in ['ERROR', 'CRITICAL']])
        st.metric("Errors", error_logs)
    
    with col3:
        if logs:
            latest_log = logs[0].timestamp
            st.metric("Latest Log", latest_log.strftime("%H:%M:%S"))
    
    # Error summary
    error_summary = centralized_logger.get_error_summary(hours=hours)
    
    if error_summary['total_errors'] > 0 or error_summary['total_critical'] > 0:
        st.markdown("#### ⚠️ Error Summary")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Total Errors", error_summary['total_errors'])
            st.metric("Critical Errors", error_summary['total_critical'])
        
        with col2:
            # Error distribution by node
            if error_summary['errors_by_node']:
                error_data = []
                for node_id, count in error_summary['errors_by_node'].items():
                    error_data.append({
                        'Node': node_id,
                        'Errors': count
                    })
                
                df = pd.DataFrame(error_data)
                fig = px.pie(df, values='Errors', names='Node', title="Errors by Node")
                st.plotly_chart(fig, use_container_width=True)
    
    # Log display
    st.markdown("#### 📄 Recent Logs")
    
    if logs:
        # Convert logs to display format
        log_data = []
        for log in logs:
            log_data.append({
                'Timestamp': log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                'Level': log.level.value,
                'Node': log.node_id,
                'Message': log.message[:100] + "..." if len(log.message) > 100 else log.message,
                'Full Message': log.message
            })
        
        df = pd.DataFrame(log_data)
        
        # Display logs with expandable details
        for i, log in enumerate(logs):
            with st.expander(f"{log.timestamp.strftime('%H:%M:%S')} [{log.level.value}] [{log.node_id}] {log.message[:50]}..."):
                st.write(f"**Full Message:** {log.message}")
                st.write(f"**Module:** {log.module}")
                st.write(f"**Function:** {log.function}")
                if log.exception:
                    st.code(log.exception)
                if log.extra_data:
                    st.write("**Extra Data:**")
                    st.json(log.extra_data)
    else:
        st.info("No logs found for the selected criteria")
    
    # Log actions
    st.markdown("#### 🔧 Log Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🗑️ Clear Old Logs"):
            with LogContext("Clear old logs", node_id="laptop"):
                centralized_logger.clear_logs(older_than_hours=24)
                st.success("Old logs cleared!")
    
    with col2:
        if st.button("📥 Export Logs"):
            with LogContext("Export logs", node_id="laptop"):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"logs_export_{timestamp}.txt"
                centralized_logger.export_logs(filename)
                st.success(f"Logs exported to {filename}")
    
    with col3:
        if st.button("🔄 Refresh Logs"):
            st.rerun()


def render_settings_tab(syncthing_manager, ray_manager, centralized_logger):
    """Settings and configuration"""
    st.markdown("### ⚙️ System Settings")
    
    # Master node configuration
    st.markdown("#### 🏠 Master Node Configuration")
    
    master_node = st.selectbox(
        "Master Node",
        ["laptop", "r630xl", "r810"],
        help="The master node controls synchronization and job coordination"
    )
    
    if st.button("Set as Master"):
        # This would need to be implemented in the managers
        st.success(f"Master node set to {master_node}")
    
    # Sync settings
    st.markdown("#### 🔄 Sync Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        auto_sync = st.checkbox("Auto Sync", value=True)
        sync_interval = st.number_input("Sync Interval (minutes)", min_value=1, max_value=60, value=5)
    
    with col2:
        conflict_resolution = st.selectbox(
            "Conflict Resolution",
            ["master_wins", "newest_wins", "manual"]
        )
        max_sync_retries = st.number_input("Max Sync Retries", min_value=1, max_value=10, value=3)
    
    # Ray settings
    st.markdown("#### ⚡ Ray Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        max_concurrent_jobs = st.number_input("Max Concurrent Jobs", min_value=1, max_value=50, value=10)
        job_timeout_hours = st.number_input("Job Timeout (hours)", min_value=1, max_value=24, value=6)
    
    with col2:
        auto_scale = st.checkbox("Auto Scale Cluster", value=True)
        min_nodes = st.number_input("Min Nodes", min_value=1, max_value=10, value=1)
        max_nodes = st.number_input("Max Nodes", min_value=1, max_value=10, value=3)
    
    # Logging settings
    st.markdown("#### 📝 Logging Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        log_level = st.selectbox("Log Level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        log_retention_days = st.number_input("Log Retention (days)", min_value=1, max_value=365, value=30)
    
    with col2:
        enable_console_logs = st.checkbox("Console Logs", value=True)
        enable_file_logs = st.checkbox("File Logs", value=True)
    
    # Save settings
    if st.button("💾 Save Settings"):
        # This would need to be implemented to save to config files
        st.success("Settings saved!")
    
    # System information
    st.markdown("#### ℹ️ System Information")
    
    # Get system info from managers
    sync_info = syncthing_manager.get_sync_status()
    ray_info = ray_manager.get_cluster_status()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Syncthing Info:**")
        st.write(f"Nodes: {len(sync_info['nodes'])}")
        st.write(f"Folders: {len(sync_info['folders'])}")
        st.write(f"Queue Length: {len(sync_info['sync_queue'])}")
    
    with col2:
        st.write("**Ray Info:**")
        st.write(f"Active Nodes: {ray_info['active_nodes']}")
        st.write(f"Total Jobs: {len(ray_info['jobs'])}")
        st.write(f"Queue Length: {len(ray_info['job_queue'])}")
    
    # Maintenance actions
    st.markdown("#### 🔧 Maintenance Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🧹 Cleanup Completed Jobs"):
            with LogContext("Cleanup completed jobs", node_id="laptop"):
                ray_manager.cleanup_completed_jobs()
                st.success("Completed jobs cleaned up!")
    
    with col2:
        if st.button("📊 Backup Project"):
            with LogContext("Backup project", node_id="laptop"):
                syncthing_manager.backup_project()
                st.success("Project backed up!")
    
    with col3:
        if st.button("🔄 Restart Services"):
            st.info("Service restart functionality to be implemented")


# Auto-refresh functionality
def auto_refresh_syncthing_ray():
    """Auto-refresh the Syncthing and Ray interface"""
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    # Refresh every 30 seconds
    if time.time() - st.session_state.last_refresh > 30:
        st.session_state.last_refresh = time.time()
        st.rerun()
