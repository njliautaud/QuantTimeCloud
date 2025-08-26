"""
SFTP Large File Sync Dashboard Interface
Provides Streamlit components for managing SFTP synchronization
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List
import json

from quanttime.core.sftp_manager import get_sftp_manager, sftp_sync_large_files_job
from quanttime.core.ray_manager import get_ray_manager


def render_sftp_interface():
    """Render the SFTP Large File Sync interface"""
    
    st.header("🔗 SFTP Large File Sync Management")
    st.markdown("Manage synchronization of large files (models, data, backtest results) between nodes")
    
    # Get SFTP manager
    try:
        sftp_manager = get_sftp_manager()
    except Exception as e:
        st.error(f"Failed to initialize SFTP manager: {e}")
        return
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Sync Status", "🔄 Manual Sync", "⚙️ Configuration", "📈 Analytics"])
    
    with tab1:
        render_sync_status_tab(sftp_manager)
    
    with tab2:
        render_manual_sync_tab(sftp_manager)
    
    with tab3:
        render_configuration_tab(sftp_manager)
    
    with tab4:
        render_analytics_tab(sftp_manager)


def render_sync_status_tab(sftp_manager):
    """Render sync status tab"""
    
    st.subheader("📊 Current Sync Status")
    
    # Get sync status
    try:
        status = sftp_manager.get_sync_status()
    except Exception as e:
        st.error(f"Failed to get sync status: {e}")
        return
    
    # Node Status
    st.markdown("### Node Status")
    
    node_data = []
    for node_id, node_info in status["nodes"].items():
        node_data.append({
            "Node ID": node_id,
            "Name": node_info["name"],
            "Status": node_info["status"],
            "Last Sync": node_info["last_sync"] or "Never",
            "Errors": len(node_info["sync_errors"])
        })
    
    if node_data:
        df_nodes = pd.DataFrame(node_data)
        st.dataframe(df_nodes, use_container_width=True)
    else:
        st.info("No nodes configured")
    
    # Active Tasks
    st.markdown("### Active Sync Tasks")
    
    task_data = []
    for task_id, task_info in status["tasks"].items():
        if task_info["status"] in ["pending", "running"]:
            task_data.append({
                "Task ID": task_id,
                "Source": task_info["source_node"],
                "Target": task_info["target_node"],
                "Status": task_info["status"],
                "Progress": f"{task_info['progress']:.1f}%",
                "Created": task_info["created_at"]
            })
    
    if task_data:
        df_tasks = pd.DataFrame(task_data)
        st.dataframe(df_tasks, use_container_width=True)
    else:
        st.info("No active sync tasks")
    
    # Discrepancies
    st.markdown("### Sync Discrepancies")
    
    discrepancy_data = []
    for node_id, discrepancies in status["discrepancies"].items():
        for discrepancy in discrepancies:
            discrepancy_data.append({
                "Node": node_id,
                "Type": discrepancy["type"],
                "File": discrepancy["file_path"],
                "Source": discrepancy["source_node"],
                "Target": discrepancy["target_node"]
            })
    
    if discrepancy_data:
        df_discrepancies = pd.DataFrame(discrepancy_data)
        st.dataframe(df_discrepancies, use_container_width=True)
        
        # Auto-sync button
        if st.button("🔄 Auto-Sync Discrepancies", type="primary"):
            with st.spinner("Auto-syncing discrepancies..."):
                try:
                    sftp_manager.auto_sync_large_files()
                    st.success("Auto-sync initiated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Auto-sync failed: {e}")
    else:
        st.success("✅ No sync discrepancies detected")


def render_manual_sync_tab(sftp_manager):
    """Render manual sync tab"""
    
    st.subheader("🔄 Manual File Sync")
    
    # Get available nodes
    nodes = list(sftp_manager.nodes.keys())
    
    col1, col2 = st.columns(2)
    
    with col1:
        source_node = st.selectbox("Source Node", nodes, key="source_node")
    
    with col2:
        target_node = st.selectbox("Target Node", [n for n in nodes if n != source_node], key="target_node")
    
    # File selection
    st.markdown("### Select Files to Sync")
    
    # Get large files from source node
    try:
        source_node_obj = sftp_manager.nodes[source_node]
        large_files = sftp_manager._scan_large_files(source_node_obj)
        
        if large_files:
            file_options = [f"{f.path} ({f.size / (1024*1024):.1f} MB)" for f in large_files]
            selected_files = st.multiselect("Select files to sync:", file_options)
            
            if selected_files:
                # Extract file paths
                file_paths = [f.split(" (")[0] for f in selected_files]
                
                # Sync options
                st.markdown("### Sync Options")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    priority = st.selectbox("Priority", ["normal", "high", "low"])
                
                with col2:
                    sync_method = st.selectbox("Sync Method", ["Direct SFTP", "Ray Distributed"])
                
                # Sync button
                if st.button("🚀 Start Sync", type="primary"):
                    with st.spinner("Starting sync..."):
                        try:
                            if sync_method == "Direct SFTP":
                                # Direct sync
                                task_id = sftp_manager.create_sync_task(
                                    source_node=source_node,
                                    target_node=target_node,
                                    file_paths=file_paths,
                                    priority=priority
                                )
                                st.success(f"Sync task created: {task_id}")
                            else:
                                # Ray distributed sync
                                ray_manager = get_ray_manager()
                                job_id = ray_manager.submit_job(
                                    name="sftp_sync_large_files",
                                    function=sftp_sync_large_files_job,
                                    config={
                                        "source_node": source_node,
                                        "target_node": target_node,
                                        "file_paths": file_paths,
                                        "sync_type": "manual"
                                    },
                                    resources={"CPU": 1},
                                    priority="high" if priority == "high" else "normal"
                                )
                                st.success(f"Ray sync job submitted: {job_id}")
                            
                            st.rerun()
                        except Exception as e:
                            st.error(f"Sync failed: {e}")
        else:
            st.info(f"No large files found on {source_node}")
    except Exception as e:
        st.error(f"Failed to scan files: {e}")


def render_configuration_tab(sftp_manager):
    """Render configuration tab"""
    
    st.subheader("⚙️ SFTP Configuration")
    
    # Display current config
    st.markdown("### Current Configuration")
    
    config = sftp_manager.config
    
    # Nodes configuration
    st.markdown("#### Nodes")
    
    for node_id, node_config in config["nodes"].items():
        with st.expander(f"Node: {node_id}"):
            st.json(node_config)
    
    # Sync settings
    st.markdown("#### Sync Settings")
    st.json(config["sync_settings"])
    
    # Configuration actions
    st.markdown("### Configuration Actions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Reload Configuration"):
            try:
                sftp_manager.config = sftp_manager._load_config()
                sftp_manager._initialize_nodes()
                st.success("Configuration reloaded!")
            except Exception as e:
                st.error(f"Failed to reload config: {e}")
    
    with col2:
        if st.button("📊 Test Connections"):
            with st.spinner("Testing node connections..."):
                results = {}
                for node_id, node in sftp_manager.nodes.items():
                    try:
                        ssh = sftp_manager._get_ssh_connection(node)
                        if ssh:
                            results[node_id] = "✅ Connected"
                            ssh.close()
                        else:
                            results[node_id] = "❌ Failed"
                    except Exception as e:
                        results[node_id] = f"❌ Error: {str(e)}"
                
                # Display results
                for node_id, result in results.items():
                    st.write(f"{node_id}: {result}")


def render_analytics_tab(sftp_manager):
    """Render analytics tab"""
    
    st.subheader("📈 Sync Analytics")
    
    # Get sync status for analytics
    try:
        status = sftp_manager.get_sync_status()
    except Exception as e:
        st.error(f"Failed to get sync status: {e}")
        return
    
    # Sync statistics
    st.markdown("### Sync Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_nodes = len(status["nodes"])
        st.metric("Total Nodes", total_nodes)
    
    with col2:
        online_nodes = sum(1 for node in status["nodes"].values() if node["status"] == "online")
        st.metric("Online Nodes", online_nodes)
    
    with col3:
        active_tasks = sum(1 for task in status["tasks"].values() if task["status"] in ["pending", "running"])
        st.metric("Active Tasks", active_tasks)
    
    with col4:
        total_discrepancies = sum(len(discrepancies) for discrepancies in status["discrepancies"].values())
        st.metric("Discrepancies", total_discrepancies)
    
    # Task history
    st.markdown("### Recent Sync Tasks")
    
    task_history = []
    for task_id, task_info in status["tasks"].items():
        task_history.append({
            "Task ID": task_id,
            "Source": task_info["source_node"],
            "Target": task_info["target_node"],
            "Status": task_info["status"],
            "Progress": f"{task_info['progress']:.1f}%",
            "Created": task_info["created_at"],
            "Completed": task_info["completed_at"] or "In Progress",
            "Errors": len(task_info["errors"])
        })
    
    if task_history:
        df_history = pd.DataFrame(task_history)
        df_history = df_history.sort_values("Created", ascending=False)
        st.dataframe(df_history.head(10), use_container_width=True)
    else:
        st.info("No sync tasks found")
    
    # Node health
    st.markdown("### Node Health")
    
    health_data = []
    for node_id, node_info in status["nodes"].items():
        health_data.append({
            "Node": node_id,
            "Status": node_info["status"],
            "Last Sync": node_info["last_sync"] or "Never",
            "Error Count": len(node_info["sync_errors"])
        })
    
    if health_data:
        df_health = pd.DataFrame(health_data)
        st.dataframe(df_health, use_container_width=True)
    
    # Export data
    st.markdown("### Export Data")
    
    if st.button("📥 Export Sync Report"):
        try:
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "summary": {
                    "total_nodes": len(status["nodes"]),
                    "online_nodes": sum(1 for node in status["nodes"].values() if node["status"] == "online"),
                    "active_tasks": sum(1 for task in status["tasks"].values() if task["status"] in ["pending", "running"]),
                    "total_discrepancies": sum(len(discrepancies) for discrepancies in status["discrepancies"].values())
                }
            }
            
            st.download_button(
                label="📄 Download JSON Report",
                data=json.dumps(report_data, indent=2),
                file_name=f"sync_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        except Exception as e:
            st.error(f"Failed to export report: {e}")


def render_sftp_ray_integration():
    """Render SFTP-Ray integration interface"""
    
    st.header("🚀 SFTP-Ray Integration")
    st.markdown("Submit SFTP sync jobs to Ray cluster for distributed processing")
    
    # Get Ray manager
    try:
        ray_manager = get_ray_manager()
    except Exception as e:
        st.error(f"Failed to initialize Ray manager: {e}")
        return
    
    # Job submission form
    st.subheader("Submit SFTP Sync Job")
    
    col1, col2 = st.columns(2)
    
    with col1:
        source_node = st.selectbox("Source Node", ["laptop", "r630xl", "r810"], key="ray_source")
    
    with col2:
        target_node = st.selectbox("Target Node", ["laptop", "r630xl", "r810"], key="ray_target")
    
    sync_type = st.selectbox("Sync Type", ["auto", "manual"], key="ray_sync_type")
    
    if sync_type == "manual":
        file_paths = st.text_area("File Paths (one per line)", key="ray_file_paths")
        file_paths_list = [path.strip() for path in file_paths.split('\n') if path.strip()]
    else:
        file_paths_list = []
    
    priority = st.selectbox("Priority", ["low", "normal", "high"], key="ray_priority")
    
    if st.button("🚀 Submit Ray Job", type="primary"):
        with st.spinner("Submitting Ray job..."):
            try:
                job_id = ray_manager.submit_job(
                    name="sftp_sync_large_files",
                    function=sftp_sync_large_files_job,
                    config={
                        "source_node": source_node,
                        "target_node": target_node,
                        "file_paths": file_paths_list,
                        "sync_type": sync_type
                    },
                    resources={"CPU": 1},
                    priority=priority
                )
                st.success(f"Ray job submitted successfully! Job ID: {job_id}")
            except Exception as e:
                st.error(f"Failed to submit Ray job: {e}")
    
    # Job monitoring
    st.subheader("Ray Job Status")
    
    try:
        jobs = ray_manager.get_all_jobs()
        
        ray_jobs = []
        for job_id, job_info in jobs.items():
            if "sftp" in job_info.get("name", "").lower():
                ray_jobs.append({
                    "Job ID": job_id,
                    "Name": job_info.get("name", ""),
                    "Status": job_info.get("status", ""),
                    "Progress": f"{job_info.get('progress', 0):.1f}%",
                    "Created": job_info.get("created_at", ""),
                    "Completed": job_info.get("completed_at", "")
                })
        
        if ray_jobs:
            df_ray_jobs = pd.DataFrame(ray_jobs)
            st.dataframe(df_ray_jobs, use_container_width=True)
        else:
            st.info("No SFTP Ray jobs found")
    except Exception as e:
        st.error(f"Failed to get Ray job status: {e}")
