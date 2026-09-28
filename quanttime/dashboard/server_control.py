"""
QuantTime Server Control Center

Comprehensive server management and monitoring interface for the distributed computing cluster.
This provides real-time monitoring, job management, and server control capabilities.
"""

import asyncio
import json
import logging
import os
import time
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import streamlit as st

# Enhanced logging
from quanttime.utils.logging_config import log_device_operation, log_server_operation

# Configure logging
logger = logging.getLogger(__name__)

class ServerControlCenter:
    """
    Server Control Center for managing distributed computing cluster
    
    Features:
    - Real-time server monitoring
    - Job queue management
    - File synchronization status
    - Resource usage tracking
    - Connection status monitoring
    """
    
    def __init__(self):
        """Initialize server control center"""
        self.refresh_interval = 5  # seconds
        self.servers = self._initialize_servers()
        self.selected_server = "laptop"  # Default to laptop
        
    def _initialize_servers(self) -> Dict[str, Dict[str, Any]]:
        """Initialize server configurations"""
        return {
            "laptop": {
                "name": "Laptop (Control)",
                "type": "control",
                "url": "http://localhost:8000",
                "capabilities": ["ALL TASKS", "control", "data_normalization", "feature_engineering", "model_training", "backtesting"],
                "status": "online",
                "specs": {
                    "cpu_cores": 8,
                    "memory_gb": 16,
                    "description": "Control center - can run any task"
                }
            },
            "r630xl": {
                "name": "R630XL (Versatile Workhorse)",
                "type": "workhorse",
                "url": "http://r630xl:8000",
                "capabilities": ["ALL TASKS", "data_normalization", "feature_engineering", "model_training", "backtesting"],
                "status": "connecting",
                "specs": {
                    "cpu_cores": 16,
                    "memory_gb": 64,
                    "description": "Versatile server - handles any workload"
                }
            },
            "r810": {
                "name": "R810 (Power Workhorse)",
                "type": "workhorse",
                "url": "http://r810:8000",
                "capabilities": ["ALL TASKS", "data_normalization", "feature_engineering", "model_training", "backtesting"],
                "status": "offline",
                "specs": {
                    "cpu_cores": 32,  # 4 CPUs with multiple cores each
                    "memory_gb": 256,
                    "description": "High-performance server - handles any workload"
                }
            }
        }
    
    def render_sidebar(self):
        """Render the server control sidebar"""
        with st.sidebar:
            # Connection status at the very top (small)
            self._render_connection_status()
            
            st.markdown("## 🖥️ Server Control Center")
            
            # Auto-refresh toggle
            auto_refresh = st.checkbox("🔄 Auto Refresh", value=True)
            if auto_refresh:
                # Use st.rerun() instead of st_autorefresh for now
                if st.button("🔄 Refresh Now"):
                    st.rerun()
            
            # Server selection
            self._render_server_selector()
            
            # Quick actions
            self._render_quick_actions()
            
            # Resource overview
            self._render_resource_overview()
            
            # Job queue status
            self._render_job_queue_status()
            
            # File sync status
            self._render_sync_status()
            
            # Bottom left task progress window (static)
            self._render_task_progress_window()
    
    def _render_server_selector(self):
        """Render server selection controls with slide tabs"""
        st.markdown("### 🎯 Device Selection")
        
        # Create slide tabs for device selection (remove duplicate laptop)
        device_options = ["laptop"] + [s for s in self.servers.keys() if s != "laptop"]
        device_labels = ["💻 Laptop"] + [f"🖥️ {self.servers[s]['name'].split(' ')[0]}" for s in self.servers.keys() if s != "laptop"]
        
        # Use radio buttons styled as tabs
        selected_device = st.radio(
            "Select device:",
            device_options,
            format_func=lambda x: device_labels[device_options.index(x)],
            horizontal=True,
            key="device_tabs"
        )
        
        self.selected_server = selected_device
        st.session_state.selected_server = self.selected_server
        
        # Display selected device info with dynamic specs
        if self.selected_server == "laptop":
            # Get real laptop specs
            try:
                import psutil
                cpu_count = psutil.cpu_count()
                memory = psutil.virtual_memory()
                memory_gb = round(memory.total / (1024**3), 1)
                
                st.markdown(f"""
                **🟢 💻 Laptop (Control)**  
                Type: Control  
                CPU: {cpu_count} cores  
                RAM: {memory_gb} GB  
                """)
                st.caption("Capabilities: ALL TASKS, control, data_normalization, feature_engineering, model_training, backtesting")
            except:
                st.markdown(f"""
                **🟢 💻 Laptop (Control)**  
                Type: Control  
                CPU: Unknown cores  
                RAM: Unknown GB  
                """)
        else:
            # Remote server info
            server_info = self.servers[self.selected_server]
            
            # Get real-time status
            try:
                from quanttime.dashboard.server_task_manager import task_manager
                status = task_manager.get_server_status(self.selected_server)
                is_online = status.get("connected", False)
                status_emoji = "🟢" if is_online else "🔴"
            except:
                status_emoji = "⚪"
            
            st.markdown(f"""
            **{status_emoji} {server_info['name']}**  
            Type: {server_info['type'].title()}  
            CPU: {server_info['specs']['cpu_cores']} cores  
            RAM: {server_info['specs']['memory_gb']} GB  
            Disk: {server_info['specs']['disk_gb']} GB  
            """)
            
            # Capabilities
            capabilities = ", ".join(server_info["capabilities"])
            st.caption(f"Capabilities: {capabilities}")
        
        # Data availability for selected server
        self._render_data_availability()
    
    def _render_connection_status(self):
        """Render connection status for all servers (small at top)"""
        # Small connection status at top
        st.markdown("**🔗 Connection Status**")
        
        # Compact status display
        status_cols = st.columns(3)
        
        # Laptop (always online)
        with status_cols[0]:
            st.markdown("🟢 Laptop", help="Control Center")
        
        # Remote servers
        server_count = 0
        for server_id, server_info in self.servers.items():
            if server_count < 2:  # Show max 2 servers in 3 columns
                with status_cols[server_count + 1]:
                    # Get real-time status
                    try:
                        from quanttime.dashboard.server_task_manager import task_manager
                        status = task_manager.get_server_status(server_id)
                        is_online = status.get("connected", False)
                        status_emoji = "🟢" if is_online else "🔴"
                    except:
                        status_emoji = "⚪"
                    
                    st.markdown(f"{status_emoji} {server_info['name'].split(' ')[0]}")
                server_count += 1
        
        st.markdown("---")
    
    def _render_data_availability(self):
        """Render data availability for selected server"""
        st.markdown("### 📊 Data Availability")
        
        if self.selected_server == "laptop":
            # Show local data availability
            self._show_local_data_availability()
        else:
            # Show remote server data availability
            self._show_remote_data_availability()
    
    def _show_local_data_availability(self):
        """Show data available on local laptop"""
        try:
            from pathlib import Path
            
            # Check data directories
            data_dirs = {
                "📁 Raw Data": "data/raw",
                "📁 Normalized Data": "data/normalized", 
                "📁 Feature Engineered": "data/features",
                "📁 Models": "models",
                "📁 Backtests": "backtests",
                "📁 Results": "results"
            }
            
            for label, path in data_dirs.items():
                dir_path = Path(path)
                if dir_path.exists():
                    # Count files
                    file_count = len(list(dir_path.rglob("*.parquet"))) + len(list(dir_path.rglob("*.csv")))
                    if file_count > 0:
                        st.success(f"{label}: {file_count} files")
                    else:
                        st.info(f"{label}: No data")
                else:
                    st.warning(f"{label}: Not available")
                    
        except Exception as e:
            st.error(f"❌ Error checking local data: {e}")
    
    def _show_remote_data_availability(self):
        """Show data available on remote server"""
        try:
            # Get server config
            config_path = "server/config/servers.json"
            with open(config_path, 'r') as f:
                servers = json.load(f)
            
            if self.selected_server not in servers:
                st.error(f"❌ Server {self.selected_server} not found in config")
                return
            
            server_config = servers[self.selected_server]
            ip = server_config.get('tailscale_ip', server_config['ip_address'])
            username = server_config['username']
            
            # Check remote data directories
            data_dirs = {
                "📁 Raw Data": "data/raw",
                "📁 Normalized Data": "data/normalized",
                "📁 Feature Engineered": "data/features", 
                "📁 Models": "models",
                "📁 Backtests": "backtests",
                "📁 Results": "results"
            }
            
            for label, path in data_dirs.items():
                try:
                    # Use paramiko for password authentication
                    import paramiko
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    
                    try:
                        ssh.connect(ip, username=username, password=os.environ.get("R630XL_SSH_PASSWORD", ""), timeout=5)
                    except:
                        # Fallback to key-based authentication
                        ssh.connect(ip, username=username, timeout=5)
                    
                    # Check if directory exists and has files
                    stdin, stdout, stderr = ssh.exec_command(f'find /opt/quanttime/{path} -name "*.parquet" -o -name "*.csv" | wc -l')
                    file_count = int(stdout.read().decode().strip())
                    ssh.close()
                    
                    if file_count > 0:
                        st.success(f"{label}: {file_count} files available")
                    else:
                        st.info(f"{label}: Directory exists, no data files")
                        
                except Exception as e:
                    st.warning(f"{label}: Error checking ({e})")
                    print(f"[ERROR] Remote data check failed for {label}: {e}")  # Terminal logging
                    
        except Exception as e:
            st.error(f"❌ Error checking remote data: {e}")
    
    def get_available_data_for_server(self, server_name: str) -> Dict[str, List[str]]:
        """Get available data for a specific server"""
        available_data = {
            "raw_data": [],
            "normalized_data": [],
            "feature_data": [],
            "models": [],
            "backtests": []
        }
        
        try:
            if server_name == "laptop":
                # Get local data
                from pathlib import Path
                
                # Raw data
                raw_path = Path("data/raw")
                if raw_path.exists():
                    available_data["raw_data"] = [f.name for f in raw_path.glob("*.parquet")]
                
                # Normalized data
                norm_path = Path("data/normalized")
                if norm_path.exists():
                    available_data["normalized_data"] = [f.name for f in norm_path.glob("*.parquet")]
                
                # Feature data
                feat_path = Path("data/features")
                if feat_path.exists():
                    available_data["feature_data"] = [f.name for f in feat_path.glob("*.parquet")]
                
                # Models
                models_path = Path("models")
                if models_path.exists():
                    available_data["models"] = [f.name for f in models_path.glob("*.pkl")]
                
                # Backtests
                backtest_path = Path("backtests")
                if backtest_path.exists():
                    available_data["backtests"] = [f.name for f in backtest_path.glob("*.json")]
                    
            else:
                # Get remote server data
                config_path = "server/config/servers.json"
                with open(config_path, 'r') as f:
                    servers = json.load(f)
                
                if server_name not in servers:
                    return available_data
                
                server_config = servers[server_name]
                ip = server_config.get('tailscale_ip', server_config['ip_address'])
                username = server_config['username']
                
                # Get remote file lists
                for data_type, remote_path in [
                    ("raw_data", "data/raw"),
                    ("normalized_data", "data/normalized"),
                    ("feature_data", "data/features"),
                    ("models", "models"),
                    ("backtests", "backtests")
                ]:
                    try:
                        cmd = f"ssh {username}@{ip} 'find /opt/quanttime/{remote_path} -name \"*.parquet\" -o -name \"*.pkl\" -o -name \"*.json\" -printf \"%f\\n\" 2>/dev/null || echo \"\"'"
                        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                        
                        if result.returncode == 0 and result.stdout.strip():
                            available_data[data_type] = result.stdout.strip().split('\n')
                    except Exception as e:
                        logger.error(f"Error getting {data_type} for {server_name}: {e}")
            
            return available_data
            
        except Exception as e:
            logger.error(f"Error getting available data for {server_name}: {e}")
            return available_data
    
    def get_current_server_data(self) -> Dict[str, List[str]]:
        """Get available data for currently selected server"""
        return self.get_available_data_for_server(self.selected_server)
    
    def _render_quick_actions(self):
        """Render quick action buttons"""
        st.markdown("### ⚡ Quick Actions")
        
        # Job control actions
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("▶️ Start Jobs", key="start_jobs"):
                self._start_job_processing()
            
            if st.button("📊 Monitor", key="open_monitor"):
                self._open_monitoring_dashboard()
        
        with col2:
            if st.button("⏸️ Pause Jobs", key="pause_jobs"):
                self._pause_job_processing()
            
            if st.button("🔄 Sync Files", key="sync_files"):
                self._trigger_file_sync()
        
        # Emergency actions
        st.markdown("#### 🚨 Emergency")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⏹️ Stop All", key="emergency_stop", type="secondary"):
                self._emergency_stop_all()
        
        with col2:
            if st.button("🔄 Restart", key="restart_server", type="secondary"):
                self._restart_selected_server()
    
    def _render_resource_overview(self):
        """Render resource usage overview (concise)"""
        st.markdown("**📊 Resources**")
        
        if self.selected_server == "laptop":
            # Get real-time laptop resources
            try:
                import psutil
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("CPU", f"{cpu_percent:.0f}%")
                    st.progress(cpu_percent / 100)
                with col2:
                    st.metric("Memory", f"{memory.percent:.0f}%")
                    st.progress(memory.percent / 100)
            except:
                st.caption("Unable to fetch resources")
        else:
            # Remote server info
            server_info = self.servers[self.selected_server]
            
            # Show server specs
            col1, col2 = st.columns(2)
            with col1:
                st.metric("CPU", f"{server_info['specs']['cpu_cores']} cores")
                st.metric("Memory", f"{server_info['specs']['memory_gb']} GB")
            with col2:
                st.metric("Disk", f"{server_info['specs']['disk_gb']} GB")
                st.metric("Type", server_info['type'].title())
            
            # Get real-time server status
            try:
                from quanttime.dashboard.server_task_manager import task_manager
                status = task_manager.get_server_status(self.selected_server)
                
                if status.get("connected", False):
                    uptime = status.get("uptime", "")
                    if uptime:
                        st.caption(f"🕒 {uptime}")
                else:
                    st.caption("⚠️ Offline")
            except Exception as e:
                st.caption("⚠️ Connection error")
    
    def _render_job_queue_status(self):
        """Render job queue status (concise)"""
        st.markdown("**📋 Jobs**")
        
        # Get job queue data
        queue_data = self._get_job_queue_data(self.selected_server)
        
        if queue_data:
            # Queue metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Queued", queue_data.get("pending", 0))
                st.metric("Running", queue_data.get("running", 0))
            with col2:
                st.metric("Completed", queue_data.get("completed", 0))
                st.metric("Failed", queue_data.get("failed", 0))
        else:
            st.caption("No job data")
        
        # Simple action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 View", key="view_all_jobs", help="View all jobs"):
                self._show_job_manager()
        with col2:
            if st.button("➕ Submit", key="submit_job", help="Submit new job"):
                self._show_job_submission()
    
    def _render_sync_status(self):
        """Render file synchronization status (concise)"""
        st.markdown("**🔄 Sync**")
        
        # Get sync status
        sync_data = self._get_sync_status()
        
        if sync_data:
            # Sync metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Synced", sync_data.get("synced_files", 0))
                st.metric("Pending", sync_data.get("pending_sync", 0))
            with col2:
                last_sync = sync_data.get("last_sync")
                if last_sync:
                    last_sync_time = datetime.fromisoformat(last_sync)
                    time_ago = datetime.now() - last_sync_time
                    st.caption(f"Last: {self._format_time_ago(time_ago)} ago")
                else:
                    st.caption("Last: Never")
            
            # Sync conflicts
            conflicts = sync_data.get("conflicts", 0)
            if conflicts > 0:
                st.caption(f"⚠️ {conflicts} conflicts")
        else:
            st.caption("No sync data")
        
        # Simple action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Sync", key="force_sync", help="Force sync"):
                self._force_sync_all()
        with col2:
            if st.button("📁 Browse", key="browse_files", help="Browse files"):
                self._show_file_browser()
    
    def _render_task_progress_window(self):
        """Render bottom left task progress window (static)"""
        st.markdown("---")
        st.markdown("**📋 Active Tasks**")
        
        # Get current tasks for selected device
        tasks = self._get_current_device_tasks()
        
        if tasks:
            for task in tasks:
                # Compact task display
                status_emoji = {
                    "running": "🔄",
                    "queued": "⏳", 
                    "completed": "✅",
                    "failed": "❌",
                    "paused": "⏸️"
                }.get(task.get("status", "unknown"), "❓")
                
                st.markdown(f"{status_emoji} {task.get('name', 'Unknown Task')}")
                
                # Simple progress indicator
                if task.get("progress", 0) > 0:
                    st.progress(task.get("progress", 0) / 100)
                else:
                    st.caption("Running...")
                
                st.markdown("---")
        else:
            st.caption("No active tasks")
        
        # Simple action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ New", key="new_task", help="Create new task"):
                self._show_task_creation()
        with col2:
            if st.button("📊 All", key="all_tasks", help="View all tasks"):
                self._show_task_manager()
    
    def render_main_dashboard(self):
        """Render the main server management dashboard"""
        st.markdown("# 🖥️ Server Management Dashboard")
        
        # Overview cards
        self._render_overview_cards()
        
        # Server grid
        self._render_server_grid()
        
        # Performance charts
        self._render_performance_charts()
        
        # Job management
        self._render_job_management()
        
        # File management
        self._render_file_management()
    
    def _render_overview_cards(self):
        """Render overview metric cards"""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            online_servers = len([s for s in self.servers.values() if s["status"] == "online"])
            st.metric(
                "Online Servers",
                f"{online_servers}/{len(self.servers)}",
                delta=f"+{online_servers - 1}" if online_servers > 1 else None
            )
        
        with col2:
            total_jobs = self._get_total_active_jobs()
            st.metric("Active Jobs", total_jobs, delta=None)
        
        with col3:
            sync_status = "✅ Synced" if self._all_servers_synced() else "🔄 Syncing"
            st.metric("Sync Status", sync_status, delta=None)
        
        with col4:
            cluster_health = self._get_cluster_health()
            health_emoji = "🟢" if cluster_health > 90 else "🟡" if cluster_health > 70 else "🔴"
            st.metric("Cluster Health", f"{health_emoji} {cluster_health}%", delta=None)
    
    def _render_server_grid(self):
        """Render server status grid"""
        st.markdown("## 🖥️ Server Status")
        
        # Render server cards without nested columns
        for server_id, server_info in self.servers.items():
            self._render_server_card(server_id, server_info)
    
    def _render_server_card(self, server_id: str, server_info: Dict[str, Any]):
        """Render individual server status card"""
        status_color = {
            "online": "#28a745",
            "connecting": "#ffc107", 
            "offline": "#dc3545",
            "error": "#dc3545"
        }.get(server_info["status"], "#6c757d")
        
        st.markdown(f"""
        <div style="
            border: 2px solid {status_color};
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
            background-color: {status_color}15;
        ">
            <h4 style="margin: 0; color: {status_color};">
                {server_info['name']}
            </h4>
            <p style="margin: 5px 0; font-size: 14px;">
                <strong>Status:</strong> {server_info['status'].title()}<br>
                <strong>Type:</strong> {server_info['type'].title()}<br>
                <strong>CPU:</strong> {server_info['specs']['cpu_cores']} cores<br>
                <strong>RAM:</strong> {server_info['specs']['memory_gb']} GB
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Server actions - use horizontal layout instead of columns
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Create a container for buttons
        button_container = st.container()
        with button_container:
            # Use st.button with custom styling for horizontal layout
            if st.button("📊 Monitor", key=f"monitor_{server_id}", use_container_width=False):
                self._open_server_monitor(server_id)
            
            st.write(" ")  # Small spacer
            
            if st.button("⚙️ Manage", key=f"manage_{server_id}", use_container_width=False):
                self._open_server_management(server_id)
    
    def _render_performance_charts(self):
        """Render performance monitoring charts"""
        st.markdown("## 📊 Performance Monitoring")
        
        # Resource usage charts
        col1, col2 = st.columns(2)
        
        with col1:
            self._render_cpu_usage_chart()
        
        with col2:
            self._render_memory_usage_chart()
        
        # Network and job throughput
        col1, col2 = st.columns(2)
        
        with col1:
            self._render_network_chart()
        
        with col2:
            self._render_job_throughput_chart()
    
    def _render_resource_charts(self):
        """Render mini resource trend charts"""
        # Generate sample historical data
        times = [datetime.now() - timedelta(minutes=x*5) for x in range(12, 0, -1)]
        
        # CPU chart
        cpu_data = [45 + i*2 + (i%3)*5 for i in range(12)]
        fig_cpu = go.Figure()
        fig_cpu.add_trace(go.Scatter(
            x=times,
            y=cpu_data,
            mode='lines+markers',
            name='CPU %',
            line=dict(color='#ff6b6b', width=2)
        ))
        fig_cpu.update_layout(
            height=200,
            margin=dict(l=0, r=0, t=20, b=0),
            showlegend=False,
            title="CPU Usage (1h)"
        )
        st.plotly_chart(fig_cpu, use_container_width=True)
        
        # Memory chart
        memory_data = [60 + i*1.5 + (i%2)*3 for i in range(12)]
        fig_mem = go.Figure()
        fig_mem.add_trace(go.Scatter(
            x=times,
            y=memory_data,
            mode='lines+markers',
            name='Memory %',
            line=dict(color='#4ecdc4', width=2)
        ))
        fig_mem.update_layout(
            height=200,
            margin=dict(l=0, r=0, t=20, b=0),
            showlegend=False,
            title="Memory Usage (1h)"
        )
        st.plotly_chart(fig_mem, use_container_width=True)
    
    # Helper methods for data fetching (these would connect to actual APIs)
    
    def _get_server_latency(self, server_id: str) -> Optional[int]:
        """Get server latency in milliseconds"""
        # Mock implementation
        return {"laptop": 1, "r630xl": 25, "r810": None}.get(server_id)
    
    def _get_server_resources(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get server resource usage"""
        if server_id == "laptop":
            return {
                "cpu_percent": 45.2,
                "memory_percent": 62.1,
                "disk_percent": 78.5,
                "network_io": {
                    "bytes_sent": 1024*1024*150,  # 150 MB
                    "bytes_recv": 1024*1024*89    # 89 MB
                }
            }
        elif server_id == "r630xl":
            return {
                "cpu_percent": 78.9,
                "memory_percent": 45.3,
                "disk_percent": 65.2,
                "network_io": {
                    "bytes_sent": 1024*1024*1024*2,  # 2 GB
                    "bytes_recv": 1024*1024*1024*1.5  # 1.5 GB
                }
            }
        return None
    
    def _get_job_queue_data(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get job queue status"""
        if server_id == "laptop":
            return {
                "pending": 3,
                "running": 1,
                "completed": 15,
                "failed": 0,
                "active_jobs": [
                    {"name": "Feature Engineering - AAPL", "progress": 65},
                    {"name": "Model Training - LGBM", "progress": 23}
                ]
            }
        elif server_id == "r630xl":
            return {
                "pending": 8,
                "running": 3,
                "completed": 42,
                "failed": 1,
                "active_jobs": [
                    {"name": "Data Normalization - SPY", "progress": 89},
                    {"name": "Backtest - Strategy_v2", "progress": 45},
                    {"name": "Model Training - XGBoost", "progress": 12}
                ]
            }
        return None
    
    def _get_sync_status(self) -> Optional[Dict[str, Any]]:
        """Get file synchronization status"""
        return {
            "synced_files": 1247,
            "pending_sync": 3,
            "last_sync": (datetime.now() - timedelta(minutes=2)).isoformat(),
            "conflicts": 0,
            "active_transfers": [
                {"filename": "model_weights_v2.pkl", "progress": 73},
                {"filename": "features_data.parquet", "progress": 34}
            ]
        }
    
    def _get_current_device_tasks(self) -> List[Dict[str, Any]]:
        """Get current tasks for the selected device"""
        if self.selected_server == "laptop":
            # Check for real running processes
            try:
                import psutil
                running_processes = []
                
                # Look for Python processes related to quanttime
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['name'] == 'python' and proc.info['cmdline']:
                            cmdline = ' '.join(proc.info['cmdline'])
                            if 'quanttime' in cmdline.lower() or 'run.py' in cmdline:
                                running_processes.append({
                                    "id": f"laptop_task_{proc.info['pid']}",
                                    "name": f"Process {proc.info['pid']}",
                                    "status": "running",
                                    "progress": 0,  # Can't determine progress
                                    "current_step": "Running",
                                    "device": "Laptop",
                                    "started": "Unknown",
                                    "eta": "Unknown"
                                })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                return running_processes
            except:
                return []
        else:
            # Remote server tasks
            try:
                from quanttime.dashboard.server_task_manager import task_manager
                status = task_manager.get_server_status(self.selected_server)
                
                if status.get("connected", False):
                    # Parse running processes to get tasks
                    processes = status.get("processes", "")
                    if processes:
                        return [
                            {
                                "id": f"{self.selected_server}_task_1",
                                "name": f"Data Processing - {self.selected_server.upper()}",
                                "status": "running",
                                "progress": 45,
                                "current_step": "Normalizing data",
                                "device": self.selected_server.upper(),
                                "started": "10 minutes ago",
                                "eta": "15 minutes"
                            }
                        ]
                    else:
                        return []
                else:
                    return []
            except:
                return []
    
    def _pause_task(self, task_id: str):
        """Pause a specific task"""
        st.info(f"⏸️ Pausing task {task_id}...")
    
    def _resume_task(self, task_id: str):
        """Resume a specific task"""
        st.info(f"▶️ Resuming task {task_id}...")
    
    def _stop_task(self, task_id: str):
        """Stop a specific task"""
        st.info(f"⏹️ Stopping task {task_id}...")
    
    def _show_task_creation(self):
        """Show task creation dialog"""
        st.info("Task creation dialog would open here")
    
    def _show_task_manager(self):
        """Show comprehensive task manager"""
        st.info("Task manager interface would open here")
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f}PB"
    
    def _format_time_ago(self, time_delta: timedelta) -> str:
        """Format time delta to human readable format"""
        total_seconds = int(time_delta.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            return f"{total_seconds // 60}m"
        elif total_seconds < 86400:
            return f"{total_seconds // 3600}h"
        else:
            return f"{total_seconds // 86400}d"
    
    # Action methods (these would connect to actual server APIs)
    
    def _refresh_server_connections(self):
        """Refresh server connection status"""
        st.info("🔄 Refreshing server connections...")
        # Implementation would ping all servers
    
    def _start_job_processing(self):
        """Start job processing on selected server"""
        st.success(f"▶️ Started job processing on {self.selected_server}")
    
    def _pause_job_processing(self):
        """Pause job processing on selected server"""
        st.warning(f"⏸️ Paused job processing on {self.selected_server}")
    
    def _trigger_file_sync(self):
        """Trigger file synchronization"""
        st.info("🔄 Triggering file synchronization...")
    
    def _emergency_stop_all(self):
        """Emergency stop all operations"""
        if st.button("⚠️ Confirm Emergency Stop", key="confirm_emergency"):
            st.error("🚨 Emergency stop initiated on all servers!")
    
    def _restart_selected_server(self):
        """Restart selected server"""
        if st.button(f"⚠️ Confirm Restart {self.selected_server}", key="confirm_restart"):
            st.warning(f"🔄 Restarting {self.selected_server}...")
    
    def _force_sync_all(self):
        """Force synchronization of all files"""
        st.info("🔄 Forcing synchronization of all files...")
    
    def _get_total_active_jobs(self) -> int:
        """Get total active jobs across all servers"""
        return 7  # Mock data
    
    def _all_servers_synced(self) -> bool:
        """Check if all servers are synchronized"""
        return True  # Mock data
    
    def _get_cluster_health(self) -> int:
        """Get overall cluster health percentage"""
        return 87  # Mock data
    
    # Placeholder methods for UI components
    def _show_server_configuration(self):
        st.info("Server configuration dialog would open here")
    
    def _open_monitoring_dashboard(self):
        st.info("Monitoring dashboard would open here")
    
    def _show_job_manager(self):
        st.info("Job manager interface would open here")
    
    def _show_job_submission(self):
        st.info("Job submission dialog would open here")
    
    def _show_conflict_resolution(self):
        st.info("Conflict resolution interface would open here")
    
    def _show_file_browser(self):
        st.info("File browser would open here")
    
    def _open_server_monitor(self, server_id: str):
        st.info(f"Server monitor for {server_id} would open here")
    
    def _open_server_management(self, server_id: str):
        st.info(f"Server management for {server_id} would open here")
    
    def _render_cpu_usage_chart(self):
        st.markdown("### CPU Usage")
        # Mock chart implementation
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(10)),
            y=[20, 25, 30, 35, 40, 45, 50, 55, 60, 65],
            mode='lines+markers',
            name='CPU %'
        ))
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_memory_usage_chart(self):
        st.markdown("### Memory Usage")
        # Mock chart implementation
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(10)),
            y=[40, 42, 45, 48, 50, 52, 55, 58, 60, 62],
            mode='lines+markers',
            name='Memory %'
        ))
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_network_chart(self):
        st.markdown("### Network I/O")
        # Mock chart implementation
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(10)),
            y=[10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
            mode='lines+markers',
            name='Network MB/s'
        ))
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_job_throughput_chart(self):
        st.markdown("### Job Throughput")
        # Mock chart implementation
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(10)),
            y=[5, 8, 12, 15, 18, 22, 25, 28, 30, 32],
            mode='lines+markers',
            name='Jobs/hour'
        ))
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_job_management(self):
        st.markdown("## 📋 Job Management")
        st.info("Comprehensive job management interface would be rendered here")
    
    def _render_file_management(self):
        st.markdown("## 📁 File Management")
        st.info("File synchronization and management interface would be rendered here")

# Global instance
server_control = ServerControlCenter()
