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
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔍 Check All", key="check_all", use_container_width=True):
                self._check_all_servers()
        
        with col2:
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
    
    def _check_all_servers(self):
        """Check connection status for all servers"""
        with st.spinner("Checking server connections..."):
            for device in self.servers.keys():
                if device == "laptop":
                    # Laptop is online if we're running on it, otherwise check connection
                    if self._is_running_on_laptop:
                        self.server_status[device]["connected"] = True
                        self.server_status[device]["last_check"] = datetime.now().strftime("%H:%M:%S")
                        self.server_status[device]["error"] = None
                    else:
                        self._check_server_connection(device)
                else:
                    self._check_server_connection(device)
            st.success("Server check completed!")
    
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

# Global instance
enhanced_server_control = EnhancedServerControl()

def render_enhanced_server_control():
    """Render the enhanced server control interface"""
    enhanced_server_control.render_enhanced_sidebar()
