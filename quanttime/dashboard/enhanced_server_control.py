"""
Enhanced Server Control Center for QuantTime Dashboard

Provides comprehensive server management with:
- Slide tab device selection in sidebar
- Real-time server monitoring and status
- Job queue management
- Resource usage tracking
- Connection status monitoring
- Task submission and progress tracking
"""

import asyncio
import json
import logging
import time
import subprocess
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import streamlit as st
import paramiko

# Enhanced logging
from quanttime.utils.logging_config import log_device_operation, log_server_operation
from quanttime.dashboard.node_status_manager import node_status_manager

# Configure logging
logger = logging.getLogger(__name__)

class EnhancedServerControl:
    """
    Enhanced Server Control Center for managing distributed computing cluster
    
    Features:
    - Slide tab device selection in sidebar
    - Real-time server monitoring
    - Job queue management
    - File synchronization status
    - Resource usage tracking
    - Connection status monitoring
    """
    
    def __init__(self):
        """Initialize enhanced server control center"""
        self.refresh_interval = 5  # seconds
        self.servers = self._initialize_servers()
        self.selected_device = "laptop"  # Default to laptop
        self.server_status = {}
        self.job_queue = {}
        self._initialize_server_status()
        self._is_running_on_laptop = self._check_if_running_on_laptop()
        
    def _check_if_running_on_laptop(self) -> bool:
        """Check if the dashboard is running on the laptop (localhost)"""
        try:
            # Get the hostname
            hostname = socket.gethostname()
            # Get local IP address
            local_ip = socket.gethostbyname(hostname)
            
            # Check if we're running on localhost or local network
            return (local_ip.startswith('127.') or 
                   local_ip.startswith('192.168.') or 
                   local_ip.startswith('10.') or
                   hostname.lower() in ['laptop', 'desktop', 'razer'])
        except Exception as e:
            logger.warning(f"Could not determine if running on laptop: {e}")
            return True  # Default to True for safety
    
    def _initialize_servers(self) -> Dict[str, Dict[str, Any]]:
        """Initialize server configurations"""
        try:
            with open("server/config/servers.json", 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded server config for {len(config)} servers")
                return config
        except Exception as e:
            logger.error(f"Failed to load server config: {e}")
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
                }
            }
    
    def _initialize_server_status(self):
        """Initialize server status tracking"""
        for server_name in self.servers.keys():
            self.server_status[server_name] = {
                "connected": False,
                "last_check": None,
                "cpu_usage": 0,
                "memory_usage": 0,
                "disk_usage": 0,
                "uptime": "Unknown",
                "active_jobs": 0,
                "queued_jobs": 0,
                "error": None
            }
    
    def render_enhanced_sidebar(self):
        """Render the enhanced server control sidebar with slide tab device selection"""
        # Sync node status from initial config before rendering
        self.sync_node_status_from_initial_config()
        
        with st.sidebar:
            # Simple header
            st.markdown("## 🖥️ Server Control")
            
            # Connection status (simplified)
            self._render_simple_connection_status()
            
            # Device Selection (simplified)
            st.markdown("### 📱 Device Selection")
            self._render_simple_device_selector()
            
            # Quick Actions (simplified)
            st.markdown("### ⚡ Quick Actions")
            self._render_simple_quick_actions()
            
            # Server Status (only if needed)
            if st.checkbox("📊 Show Server Details", value=False):
                self._render_server_status_overview()
    
    def _render_simple_connection_status(self):
        """Render simplified connection status"""
        # Laptop status - online if we're running on it
        if self._is_running_on_laptop:
            st.success("🟢 Laptop (Local)")
        else:
            laptop_status = self.server_status.get("laptop", {}).get("connected", False)
            if laptop_status:
                st.success("🟢 Laptop")
            else:
                st.error("🔴 Laptop")
        
        # Remote servers
        r630xl_status = self.server_status.get("r630xl", {}).get("connected", False)
        r810_status = self.server_status.get("r810", {}).get("connected", False)
        
        col1, col2 = st.columns(2)
        with col1:
            if r630xl_status:
                st.success("🟢 R630XL")
            else:
                st.error("🔴 R630XL")
        with col2:
            if r810_status:
                st.success("🟢 R810")
            else:
                st.error("🔴 R810")
    
    def _render_simple_device_selector(self):
        """Render simplified device selector"""
        # Simple dropdown instead of tabs
        devices = list(self.servers.keys())
        device_names = []
        
        for device in devices:
            server_info = self.servers[device]
            if device == "laptop":
                if self._is_running_on_laptop:
                    status_icon = "🟢"
                else:
                    status = self.server_status.get(device, {}).get("connected", False)
                    status_icon = "🟢" if status else "🔴"
            else:
                status = self.server_status.get(device, {}).get("connected", False)
                status_icon = "🟢" if status else "🔴"
            
            device_names.append(f"{status_icon} {server_info['name']}")
        
        selected_index = devices.index(self.selected_device)
        new_selection = st.selectbox(
            "Select Device:",
            options=device_names,
            index=selected_index,
            key="device_selector"
        )
        
        # Update selected device
        new_index = device_names.index(new_selection)
        self.selected_device = devices[new_index]
        
        # Show selected device info
        server_info = self.servers[self.selected_device]
        st.caption(f"**Type:** {server_info['type']} | **CPU:** {server_info['specs']['cpu_cores']} cores | **RAM:** {server_info['specs']['memory_gb']} GB")
    
    def _render_simple_quick_actions(self):
        """Render simplified quick actions"""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔍 Check All", key="check_all", use_container_width=True):
                self._check_all_servers()
        
        with col2:
            if st.button("🔄 Sync Check", key="sync_check", use_container_width=True):
                self._check_sync_status()
        
        with col3:
            if st.button("🔄 Sync All", key="sync_all", use_container_width=True):
                self._sync_all_servers()
        
        # Device-specific actions
        if self.selected_device != "laptop":
            if st.button(f"🚀 Deploy to {self.servers[self.selected_device]['name']}", key="deploy", use_container_width=True):
                self._deploy_to_server(self.selected_device)
    
    def _render_server_status_overview(self):
        """Render server status overview"""
        for device, server_info in self.servers.items():
            status = self.server_status.get(device, {})
            
            with st.expander(f"{server_info['name']} Status", expanded=(device == self.selected_device)):
                # Connection status - laptop depends on where we're running
                if device == "laptop":
                    if self._is_running_on_laptop:
                        st.success("🟢 Online (Running on this device)")
                    elif status.get("connected", False):
                        st.success("🟢 Online")
                    else:
                        st.error("🔴 Offline")
                elif status.get("connected", False):
                    st.success("🟢 Online")
                else:
                    st.error("🔴 Offline")
                
                # Resource usage
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("CPU", f"{status.get('cpu_usage', 0):.1f}%")
                with col2:
                    st.metric("Memory", f"{status.get('memory_usage', 0):.1f}%")
                with col3:
                    st.metric("Disk", f"{status.get('disk_usage', 0):.1f}%")
                
                # Job counts
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Active Jobs", status.get("active_jobs", 0))
                with col2:
                    st.metric("Queued Jobs", status.get("queued_jobs", 0))
                
                # Last check
                last_check = status.get("last_check")
                if last_check:
                    st.caption(f"Last check: {last_check}")
    
    def _render_quick_actions(self):
        """Render quick action buttons"""
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔍 Check All", key="check_all"):
                self._check_all_servers()
        
        with col2:
            if st.button("🔄 Sync All", key="sync_all"):
                self._sync_all_servers()
        
        # Device-specific actions
        if self.selected_device != "laptop":
            if st.button(f"🚀 Deploy to {self.servers[self.selected_device]['name']}", key="deploy"):
                self._deploy_to_server(self.selected_device)
            
            if st.button(f"📊 Monitor {self.servers[self.selected_device]['name']}", key="monitor"):
                self._monitor_server(self.selected_device)
    
    def _render_job_queue(self):
        """Render job queue status"""
        total_active = sum(status.get("active_jobs", 0) for status in self.server_status.values())
        total_queued = sum(status.get("queued_jobs", 0) for status in self.server_status.values())
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Active", total_active)
        with col2:
            st.metric("Total Queued", total_queued)
        
        # Show recent jobs
        if total_active > 0 or total_queued > 0:
            st.markdown("**Recent Jobs:**")
            # This would be populated from actual job queue data
            st.caption("Job details would appear here")
    
    def sync_node_status_from_initial_config(self):
        """Sync node status from persistent storage with sidebar"""
        # Get persistent node status
        node_status = node_status_manager.get_all_node_status()
        logger.info(f"🔄 Syncing node status from persistent storage: {node_status}")
        
        for node_id, status in node_status.items():
            # Map node_id to device name
            device_mapping = {
                "laptop": "laptop",
                "r630xl": "r630xl", 
                "r810": "r810"
            }
            
            if node_id in device_mapping:
                device = device_mapping[node_id]
                if device in self.server_status:
                    # Update server status based on persistent storage
                    self.server_status[device]["connected"] = status.get("connected", False)
                    self.server_status[device]["last_check"] = datetime.now().strftime("%H:%M:%S")
                    
                    # Update health info if available
                    health_info = status.get("health_info", {})
                    if health_info:
                        self.server_status[device]["cpu_cores"] = health_info.get("cpu_cores", "Unknown")
                        self.server_status[device]["memory"] = health_info.get("memory", "Unknown")
                        self.server_status[device]["system"] = health_info.get("system", "Unknown")
                        self.server_status[device]["quanttime_installed"] = health_info.get("quanttime_installed", False)
                        self.server_status[device]["ray_running"] = health_info.get("ray_running", False)
                    
                    logger.info(f"   ✅ Updated {device} status: connected={status.get('connected', False)}")
        
        # Also update session state for compatibility
        st.session_state.node_status = node_status
    
    def _check_all_servers(self):
        """Check connection status for all servers"""
        try:
            # First sync with initial config status
            self.sync_node_status_from_initial_config()
            
            with st.spinner("Checking server connections..."):
                # Use existing connections from session state instead of creating new ones
                if "node_status" in st.session_state:
                    node_status = st.session_state.node_status
                    
                    for device in self.servers.keys():
                        if device == "laptop":
                            # Laptop is online if we're running on it
                            if self._is_running_on_laptop:
                                self.server_status[device]["connected"] = True
                                self.server_status[device]["last_check"] = datetime.now().strftime("%H:%M:%S")
                                self.server_status[device]["error"] = None
                            else:
                                # Check if laptop is connected in session state
                                laptop_status = node_status.get("laptop", {})
                                self.server_status[device]["connected"] = laptop_status.get("connected", False)
                                self.server_status[device]["last_check"] = datetime.now().strftime("%H:%M:%S")
                                self.server_status[device]["error"] = laptop_status.get("error", None)
                        else:
                            # Check if remote server is connected in session state
                            device_status = node_status.get(device, {})
                            self.server_status[device]["connected"] = device_status.get("connected", False)
                            self.server_status[device]["last_check"] = datetime.now().strftime("%H:%M:%S")
                            self.server_status[device]["error"] = device_status.get("error", None)
                            
                            # If connected, try to get system info using existing connection
                            if device_status.get("connected", False):
                                try:
                                    from quanttime.core.sftp_manager import sftp_manager
                                    ssh_client = sftp_manager._get_ssh_connection(device)
                                    if ssh_client:
                                        self._update_server_status(device, ssh_client)
                                        ssh_client.close()
                                except Exception as e:
                                    logger.warning(f"Could not update status for {device}: {e}")
                
                st.success("Server check completed!")
                
        except Exception as e:
            logger.error(f"Error in _check_all_servers: {e}")
            st.error(f"❌ Error checking servers: {str(e)}")
    
    def _sync_all_servers(self):
        """Sync data from all servers"""
        with st.spinner("Syncing from all servers..."):
            for device in self.servers.keys():
                if device != "laptop":
                    self._sync_server_data(device)
            st.success("Sync completed!")
    
    def _check_server_connection(self, device: str):
        """Check connection to a specific server"""
        try:
            server_info = self.servers[device]
            ip_address = server_info.get('tailscale_ip') or server_info.get('ip_address')
            username = server_info.get('username', 'quanttime')
            
            # Use the web-based SSH connection system
            from quanttime.dashboard.server_task_manager import task_manager
            ssh = task_manager._get_ssh_connection(ip_address, username, timeout=5)
            
            if ssh:
                self.server_status[device]["connected"] = True
                self.server_status[device]["error"] = None
                
                # Get system info
                self._update_server_status(device, ssh)
                
                ssh.close()
                logger.info(f"Successfully connected to {device}")
            else:
                self.server_status[device]["connected"] = False
                self.server_status[device]["error"] = "Connection failed"
                logger.error(f"Failed to connect to {device}")
                
        except Exception as e:
            logger.error(f"Error checking {device}: {e}")
            self.server_status[device]["connected"] = False
            self.server_status[device]["error"] = str(e)
    
    def _update_server_status(self, device: str, ssh: paramiko.SSHClient):
        """Update server status with system information"""
        try:
            # Get CPU usage
            stdin, stdout, stderr = ssh.exec_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
            cpu_usage = float(stdout.read().decode().strip() or 0)
            
            # Get memory usage
            stdin, stdout, stderr = ssh.exec_command("free | grep Mem | awk '{printf(\"%.2f\", $3/$2 * 100.0)}'")
            memory_usage = float(stdout.read().decode().strip() or 0)
            
            # Get disk usage
            stdin, stdout, stderr = ssh.exec_command("df / | tail -1 | awk '{print $5}' | sed 's/%//'")
            disk_usage = float(stdout.read().decode().strip() or 0)
            
            # Get uptime
            stdin, stdout, stderr = ssh.exec_command("uptime -p")
            uptime = stdout.read().decode().strip()
            
            # Update status
            self.server_status[device].update({
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "disk_usage": disk_usage,
                "uptime": uptime,
                "last_check": datetime.now().strftime("%H:%M:%S")
            })
            
        except Exception as e:
            logger.error(f"Error updating status for {device}: {e}")
    
    def _sync_server_data(self, device: str):
        """Sync data from a specific server"""
        try:
            server_info = self.servers[device]
            if not self.server_status[device].get("connected", False):
                st.error(f"Cannot sync from {device} - not connected")
                return False
            
            # This would implement actual data synchronization
            # For now, just log the action
            logger.info(f"Syncing data from {device}")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing from {device}: {e}")
            return False
    
    def _deploy_to_server(self, device: str):
        """Deploy code to a specific server"""
        try:
            server_info = self.servers[device]
            if not self.server_status[device].get("connected", False):
                st.error(f"Cannot deploy to {device} - not connected")
                return False
            
            # This would implement actual deployment
            # For now, just log the action
            logger.info(f"Deploying to {device}")
            return True
            
        except Exception as e:
            logger.error(f"Error deploying to {device}: {e}")
            return False
    
    def _monitor_server(self, device: str):
        """Open detailed monitoring for a specific server"""
        try:
            server_info = self.servers[device]
            if not self.server_status[device].get("connected", False):
                st.error(f"Cannot monitor {device} - not connected")
                return False
            
            # This would open detailed monitoring view
            # For now, just log the action
            logger.info(f"Opening monitoring for {device}")
            return True
            
        except Exception as e:
            logger.error(f"Error monitoring {device}: {e}")
            return False
    
    def get_selected_device(self) -> str:
        """Get the currently selected device"""
        return self.selected_device
    
    def get_server_info(self, device: str) -> Dict[str, Any]:
        """Get information about a specific server"""
        return self.servers.get(device, {})
    
    def get_server_status(self, device: str) -> Dict[str, Any]:
        """Get status of a specific server"""
        return self.server_status.get(device, {})
    
    def submit_job(self, device: str, job_type: str, parameters: Dict[str, Any]) -> bool:
        """Submit a job to a specific device"""
        try:
            if device == "laptop":
                # Execute locally
                return self._execute_local_job(job_type, parameters)
            else:
                # Submit to remote server
                return self._submit_remote_job(device, job_type, parameters)
        except Exception as e:
            logger.error(f"Error submitting job to {device}: {e}")
            return False
    
    def _execute_local_job(self, job_type: str, parameters: Dict[str, Any]) -> bool:
        """Execute a job locally on the laptop"""
        try:
            logger.info(f"Executing local job: {job_type}")
            # This would implement actual job execution
            return True
        except Exception as e:
            logger.error(f"Error executing local job: {e}")
            return False
    
    def _submit_remote_job(self, device: str, job_type: str, parameters: Dict[str, Any]) -> bool:
        """Submit a job to a remote server"""
        try:
            if not self.server_status[device].get("connected", False):
                logger.error(f"Cannot submit job to {device} - not connected")
                return False
            
            logger.info(f"Submitting job to {device}: {job_type}")
            # This would implement actual remote job submission
            return True
            
        except Exception as e:
            logger.error(f"Error submitting remote job: {e}")
            return False
    
    def _check_sync_status(self):
        """Check sync status between nodes and identify discrepancies"""
        try:
            st.info("🔄 Checking sync status between nodes...")
            
            # Get connected nodes from persistent storage
            connected_nodes = node_status_manager.get_connected_nodes()
            
            if not connected_nodes:
                st.warning("⚠️ No nodes are currently connected.")
                return
            
            # Import sync manager
            try:
                from quanttime.core.git_sync_manager import git_sync_manager
                from quanttime.dashboard.initial_config import InitialConfigManager
            except ImportError:
                st.error("❌ Sync managers not available")
                return
            
            # Initialize config manager for SSH connections
            config_manager = InitialConfigManager()
            
            # Check each connected node
            sync_results = {}
            
            for node_id in connected_nodes:
                with st.spinner(f"🔍 Checking sync status for {node_id}..."):
                    try:
                        # Get node info and credentials from persistent storage
                        node_info = config_manager.nodes.get(node_id, {})
                        node_status_info = node_status_manager.get_node_status(node_id)
                        
                        if not node_status_info.get("connected", False):
                            sync_results[node_id] = [{"type": "error", "message": "Node not connected"}]
                            continue
                        
                        # Get credentials from session state
                        username = node_status_info.get("username", "")
                        if not username:
                            sync_results[node_id] = [{"type": "error", "message": "No username available"}]
                            continue
                        
                        # Extract password from session state (if available)
                        password = None
                        if "ssh_credentials" in st.session_state:
                            password = st.session_state.ssh_credentials.get(node_id, {}).get("password")
                        
                        if not password:
                            sync_results[node_id] = [{"type": "error", "message": "No password available - please reconnect"}]
                            continue
                        
                        # Parse username@host format
                        if "@" in username:
                            username_part, host_part = username.split("@", 1)
                        else:
                            username_part = username
                            host_part = node_info.get("host", "")
                        
                        # Create SSH connection using the same method as initial config
                        ssh_client = config_manager._create_ssh_connection(host_part, username_part, password)
                        if ssh_client:
                            try:
                                # Check Git status
                                success, discrepancies = git_sync_manager.detect_sync_discrepancies(node_id, ssh_client)
                                
                                if success:
                                    sync_results[node_id] = discrepancies
                                else:
                                    sync_results[node_id] = [{"type": "error", "message": "Failed to detect discrepancies"}]
                            finally:
                                ssh_client.close()
                        else:
                            sync_results[node_id] = [{"type": "error", "message": "Failed to establish SSH connection"}]
                    except Exception as e:
                        logger.error(f"Error checking sync for {node_id}: {e}")
                        sync_results[node_id] = [{"type": "error", "message": f"Error: {str(e)}"}]
            
            # Display results
            st.markdown("### 📊 Sync Status Results")
            
            total_discrepancies = 0
            for node_id, discrepancies in sync_results.items():
                if discrepancies:
                    with st.expander(f"🔍 {node_id.upper()} Discrepancies ({len(discrepancies)} found)", expanded=True):
                        for i, discrepancy in enumerate(discrepancies):
                            self._render_discrepancy_item(discrepancy, i, node_id)
                        total_discrepancies += len(discrepancies)
                else:
                    st.success(f"✅ {node_id.upper()}: No discrepancies found")
            
            if total_discrepancies > 0:
                st.warning(f"⚠️ Found {total_discrepancies} discrepancies across {len(connected_nodes)} nodes")
                st.info("💡 Use 'Sync All' to fix these discrepancies")
            else:
                st.success("🎉 All nodes are in sync!")
            
            # Store results in session state for later use
            st.session_state.sync_check_results = sync_results
            
        except Exception as e:
            logger.error(f"Error checking sync status: {e}")
            st.error(f"❌ Error checking sync status: {str(e)}")
    
    def _render_discrepancy_item(self, discrepancy: Dict, index: int, node_id: str):
        """Render a single discrepancy item"""
        discrepancy_type = discrepancy.get("type", "unknown")
        severity = discrepancy.get("severity", "medium")
        
        # Color coding based on severity
        if severity == "high":
            st.error(f"🔴 **{discrepancy_type.replace('_', ' ').title()}**")
        elif severity == "medium":
            st.warning(f"🟡 **{discrepancy_type.replace('_', ' ').title()}**")
        else:
            st.info(f"🔵 **{discrepancy_type.replace('_', ' ').title()}**")
        
        # Display discrepancy details
        if discrepancy_type == "commit_mismatch":
            st.markdown(f"- **Laptop Commit:** `{discrepancy.get('laptop_commit', 'Unknown')}`")
            st.markdown(f"- **Node Commit:** `{discrepancy.get('node_commit', 'Unknown')}`")
        
        elif discrepancy_type == "local_changes":
            changes = discrepancy.get("changes", [])
            st.markdown(f"- **Local Changes:** {len(changes)} files modified")
            for change in changes[:3]:  # Show first 3 changes
                st.code(change)
            if len(changes) > 3:
                st.markdown(f"- *... and {len(changes) - 3} more changes*")
        
        elif discrepancy_type == "large_files_not_synced":
            files = discrepancy.get("files", [])
            st.markdown(f"- **Large Files:** {len(files)} files need syncing")
            for file_info in files[:3]:  # Show first 3 files
                st.markdown(f"  - `{file_info.get('path', 'Unknown')}` ({file_info.get('size', 'Unknown')})")
            if len(files) > 3:
                st.markdown(f"- *... and {len(files) - 3} more files*")
        
        elif discrepancy_type == "missing_directories":
            directories = discrepancy.get("directories", [])
            st.markdown(f"- **Missing Directories:** {len(directories)} directories")
            for directory in directories[:3]:  # Show first 3 directories
                st.markdown(f"  - `{directory}`")
            if len(directories) > 3:
                st.markdown(f"- *... and {len(directories) - 3} more directories*")
        
        elif discrepancy_type == "error":
            st.error(f"❌ **Error:** {discrepancy.get('message', 'Unknown error')}")
    
    def _sync_all_servers(self):
        """Sync all connected servers"""
        try:
            st.info("🔄 Starting sync for all connected servers...")
            
            # Get connected nodes from persistent storage
            connected_nodes = node_status_manager.get_connected_nodes()
            
            if not connected_nodes:
                st.warning("⚠️ No nodes are currently connected.")
                return
            
            # Import sync manager
            try:
                from quanttime.core.git_sync_manager import git_sync_manager
                from quanttime.dashboard.initial_config import InitialConfigManager
            except ImportError:
                st.error("❌ Sync managers not available")
                return
            
            # Initialize config manager for SSH connections
            config_manager = InitialConfigManager()
            
            # Sync each connected node
            results = {}
            
            for node_id in connected_nodes:
                with st.spinner(f"🔄 Syncing {node_id}..."):
                    try:
                        # Get node info and credentials from persistent storage
                        node_info = config_manager.nodes.get(node_id, {})
                        node_status_info = node_status_manager.get_node_status(node_id)
                        
                        if not node_status_info.get("connected", False):
                            results[node_id] = {
                                "success": False,
                                "message": "Node not connected",
                                "result": {}
                            }
                            continue
                        
                        # Get credentials from session state
                        username = node_status_info.get("username", "")
                        if not username:
                            results[node_id] = {
                                "success": False,
                                "message": "No username available",
                                "result": {}
                            }
                            continue
                        
                        # Extract password from session state (if available)
                        password = None
                        if "ssh_credentials" in st.session_state:
                            password = st.session_state.ssh_credentials.get(node_id, {}).get("password")
                        
                        if not password:
                            results[node_id] = {
                                "success": False,
                                "message": "No password available - please reconnect",
                                "result": {}
                            }
                            continue
                        
                        # Parse username@host format
                        if "@" in username:
                            username_part, host_part = username.split("@", 1)
                        else:
                            username_part = username
                            host_part = node_info.get("host", "")
                        
                        # Create SSH connection using the same method as initial config
                        ssh_client = config_manager._create_ssh_connection(host_part, username_part, password)
                        if ssh_client:
                            try:
                                # Perform full sync
                                success, message, sync_result = git_sync_manager.perform_full_sync(node_id, ssh_client)
                                
                                results[node_id] = {
                                    "success": success,
                                    "message": message,
                                    "result": sync_result
                                }
                            finally:
                                ssh_client.close()
                        else:
                            results[node_id] = {
                                "success": False,
                                "message": "Failed to establish SSH connection",
                                "result": {}
                            }
                    except Exception as e:
                        logger.error(f"Error syncing {node_id}: {e}")
                        results[node_id] = {
                            "success": False,
                            "message": f"Error: {str(e)}",
                            "result": {}
                        }
            
            # Display results
            st.markdown("### 📊 Sync Results")
            for node_id, result in results.items():
                if result["success"]:
                    st.success(f"✅ {node_id}: {result['message']}")
                    if result["result"].get("files_synced", 0) > 0:
                        st.info(f"   📁 Synced {result['result']['files_synced']} files")
                    if result["result"].get("directories_synced", 0) > 0:
                        st.info(f"   📁 Synced {result['result']['directories_synced']} directories")
                else:
                    st.error(f"❌ {node_id}: {result['message']}")
            
        except Exception as e:
            logger.error(f"Error syncing all servers: {e}")
            st.error(f"❌ Error syncing servers: {str(e)}")

# Global instance
enhanced_server_control = EnhancedServerControl()

def render_enhanced_server_control():
    """Render the enhanced server control interface"""
    enhanced_server_control.render_enhanced_sidebar()
