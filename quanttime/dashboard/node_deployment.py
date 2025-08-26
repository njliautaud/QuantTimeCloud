#!/usr/bin/env python3
"""
Node Deployment and Health Monitoring System
Handles automatic deployment, synchronization, and health checks for all nodes
"""

import streamlit as st
import json
import subprocess
import paramiko
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml

class NodeHealthStatus:
    """Node health status enumeration"""
    RED = "red"      # Cannot connect
    YELLOW = "yellow"  # Connected but issues (version mismatch, missing deps)
    GREEN = "green"    # Fully operational

class NodeDeploymentManager:
    """Manages deployment and health monitoring of all nodes"""
    
    def __init__(self):
        self.config_file = Path("config/sftp_config.json")
        self.ray_config_file = Path("config/ray_config.json")
        self.nodes = {}
        self.health_status = {}
        self.load_config()
    
    def load_config(self):
        """Load node configuration"""
        if self.config_file.exists():
            with open(self.config_file) as f:
                config = json.load(f)
                self.nodes = config.get("nodes", {})
    
    def get_ssh_connection(self, node_name: str) -> Optional[paramiko.SSHClient]:
        """Establish SSH connection to node"""
        if node_name not in self.nodes:
            return None
        
        node_config = self.nodes[node_name]
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=node_config["host"],
                username=node_config["username"],
                port=node_config.get("port", 22),
                timeout=10
            )
            return ssh
        except Exception as e:
            st.error(f"SSH connection failed for {node_name}: {str(e)}")
            return None
    
    def check_node_connectivity(self, node_name: str) -> bool:
        """Check if node is reachable via SSH"""
        ssh = self.get_ssh_connection(node_name)
        if ssh:
            ssh.close()
            return True
        return False
    
    def check_git_repo_status(self, node_name: str) -> Tuple[bool, str]:
        """Check Git repository status on node"""
        ssh = self.get_ssh_connection(node_name)
        if not ssh:
            return False, "Cannot connect"
        
        try:
            # Check if repo exists
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && git status", timeout=10)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Repository not found"
            
            # Check for uncommitted changes
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && git status --porcelain", timeout=10)
            uncommitted = stdout.read().decode().strip()
            if uncommitted:
                return False, f"Uncommitted changes: {len(uncommitted.splitlines())} files"
            
            # Check if up to date with remote
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && git fetch origin && git status -uno", timeout=10)
            status = stdout.read().decode()
            if "behind" in status:
                return False, "Behind remote"
            
            return True, "Up to date"
            
        except Exception as e:
            return False, f"Error: {str(e)}"
        finally:
            ssh.close()
    
    def check_python_dependencies(self, node_name: str) -> Tuple[bool, str]:
        """Check Python dependencies on node"""
        ssh = self.get_ssh_connection(node_name)
        if not ssh:
            return False, "Cannot connect"
        
        try:
            # Check if virtual environment exists
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && ls -la .venv", timeout=10)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Virtual environment missing"
            
            # Check key dependencies
            dependencies = ["ray", "streamlit", "pandas", "numpy", "pysftp"]
            missing_deps = []
            
            for dep in dependencies:
                stdin, stdout, stderr = ssh.exec_command(f"cd /opt/quanttime && .venv/bin/python -c 'import {dep}'", timeout=10)
                if stdout.channel.recv_exit_status() != 0:
                    missing_deps.append(dep)
            
            if missing_deps:
                return False, f"Missing: {', '.join(missing_deps)}"
            
            return True, "All dependencies installed"
            
        except Exception as e:
            return False, f"Error: {str(e)}"
        finally:
            ssh.close()
    
    def check_ray_status(self, node_name: str) -> Tuple[bool, str]:
        """Check Ray cluster status on node"""
        ssh = self.get_ssh_connection(node_name)
        if not ssh:
            return False, "Cannot connect"
        
        try:
            # Check if Ray is installed
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && .venv/bin/python -c 'import ray'", timeout=10)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Ray not installed"
            
            # Check if Ray cluster is running
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && .venv/bin/python -c 'import ray; print(ray.is_initialized())'", timeout=10)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Ray not initialized"
            
            ray_status = stdout.read().decode().strip()
            if ray_status == "True":
                return True, "Ray cluster running"
            else:
                return False, "Ray cluster not running"
            
        except Exception as e:
            return False, f"Error: {str(e)}"
        finally:
            ssh.close()
    
    def get_node_health_status(self, node_name: str) -> Tuple[str, str]:
        """Get comprehensive health status for a node"""
        if not self.check_node_connectivity(node_name):
            return NodeHealthStatus.RED, "Cannot connect to node"
        
        # Check all components
        git_ok, git_msg = self.check_git_repo_status(node_name)
        deps_ok, deps_msg = self.check_python_dependencies(node_name)
        ray_ok, ray_msg = self.check_ray_status(node_name)
        
        if not git_ok or not deps_ok or not ray_ok:
            issues = []
            if not git_ok:
                issues.append(f"Git: {git_msg}")
            if not deps_ok:
                issues.append(f"Dependencies: {deps_msg}")
            if not ray_ok:
                issues.append(f"Ray: {ray_msg}")
            
            return NodeHealthStatus.YELLOW, "; ".join(issues)
        
        return NodeHealthStatus.GREEN, "All systems operational"
    
    def deploy_to_node(self, node_name: str) -> Tuple[bool, str]:
        """Deploy the project to a node"""
        ssh = self.get_ssh_connection(node_name)
        if not ssh:
            return False, "Cannot connect to node"
        
        try:
            # Create directory if it doesn't exist
            stdin, stdout, stderr = ssh.exec_command("sudo mkdir -p /opt/quanttime", timeout=10)
            stdin, stdout, stderr = ssh.exec_command("sudo chown jupiter:jupiter /opt/quanttime", timeout=10)
            
            # Check if repository exists
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && ls -la", timeout=10)
            repo_exists = ".git" in stdout.read().decode()
            
            if not repo_exists:
                # Clone repository
                git_url = "https://github.com/njliautaud/QuantTimeCloud.git"
                stdin, stdout, stderr = ssh.exec_command(f"cd /opt && git clone {git_url} quanttime", timeout=60)
                if stdout.channel.recv_exit_status() != 0:
                    return False, "Failed to clone repository"
            else:
                # Pull latest changes
                stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && git pull origin master", timeout=30)
                if stdout.channel.recv_exit_status() != 0:
                    return False, "Failed to pull latest changes"
            
            # Create virtual environment
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && python3 -m venv .venv", timeout=30)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Failed to create virtual environment"
            
            # Install dependencies
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && .venv/bin/pip install --upgrade pip", timeout=30)
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && .venv/bin/pip install -r requirements.txt", timeout=120)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Failed to install dependencies"
            
            # Install project in editable mode
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && .venv/bin/pip install -e .", timeout=30)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Failed to install project"
            
            return True, "Deployment successful"
            
        except Exception as e:
            return False, f"Deployment error: {str(e)}"
        finally:
            ssh.close()
    
    def start_ray_cluster(self, node_name: str) -> Tuple[bool, str]:
        """Start Ray cluster on a node"""
        ssh = self.get_ssh_connection(node_name)
        if not ssh:
            return False, "Cannot connect to node"
        
        try:
            # Start Ray head node
            if node_name == "laptop":
                # Start head node
                cmd = "cd /opt/quanttime && .venv/bin/ray start --head --port=10001 --dashboard-port=8265"
            else:
                # Start worker node
                cmd = "cd /opt/quanttime && .venv/bin/ray start --address=razer:10001"
            
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Failed to start Ray cluster"
            
            return True, "Ray cluster started"
            
        except Exception as e:
            return False, f"Ray start error: {str(e)}"
        finally:
            ssh.close()
    
    def sync_large_files(self, node_name: str) -> Tuple[bool, str]:
        """Sync large files to node using SFTP"""
        # This will use the existing SFTP manager
        try:
            from quanttime.core.sftp_manager import get_sftp_manager
            sftp_manager = get_sftp_manager()
            
            # Trigger sync for specific node
            success = sftp_manager.sync_node_files(node_name)
            if success:
                return True, "File sync completed"
            else:
                return False, "File sync failed"
                
        except Exception as e:
            return False, f"Sync error: {str(e)}"

def render_node_deployment_interface():
    """Render the node deployment interface"""
    st.subheader("🚀 Node Deployment & Health Monitoring")
    
    # Initialize deployment manager
    if "deployment_manager" not in st.session_state:
        st.session_state.deployment_manager = NodeDeploymentManager()
    
    manager = st.session_state.deployment_manager
    
    # Node health monitoring
    st.markdown("### 📊 Node Health Status")
    
    # Refresh health status
    if st.button("🔄 Refresh Health Status"):
        with st.spinner("Checking node health..."):
            for node_name in manager.nodes.keys():
                status, message = manager.get_node_health_status(node_name)
                manager.health_status[node_name] = (status, message)
    
    # Display health status
    cols = st.columns(len(manager.nodes))
    for i, (node_name, node_config) in enumerate(manager.nodes.items()):
        with cols[i]:
            if node_name in manager.health_status:
                status, message = manager.health_status[node_name]
            else:
                status, message = manager.get_node_health_status(node_name)
                manager.health_status[node_name] = (status, message)
            
            # Color-coded status
            if status == NodeHealthStatus.GREEN:
                st.success(f"🟢 {node_name.upper()}")
            elif status == NodeHealthStatus.YELLOW:
                st.warning(f"🟡 {node_name.upper()}")
            else:
                st.error(f"🔴 {node_name.upper()}")
            
            st.caption(f"**{node_config['host']}**")
            st.caption(message)
    
    st.markdown("---")
    
    # Deployment controls
    st.markdown("### 🚀 Deployment Controls")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📦 Deploy to All Nodes"):
            with st.spinner("Deploying to all nodes..."):
                for node_name in manager.nodes.keys():
                    if node_name != "laptop":  # Skip laptop
                        success, message = manager.deploy_to_node(node_name)
                        if success:
                            st.success(f"✅ {node_name}: {message}")
                        else:
                            st.error(f"❌ {node_name}: {message}")
    
    with col2:
        if st.button("⚡ Start Ray Clusters"):
            with st.spinner("Starting Ray clusters..."):
                for node_name in manager.nodes.keys():
                    success, message = manager.start_ray_cluster(node_name)
                    if success:
                        st.success(f"✅ {node_name}: {message}")
                    else:
                        st.error(f"❌ {node_name}: {message}")
    
    with col3:
        if st.button("🔄 Sync Files"):
            with st.spinner("Syncing large files..."):
                for node_name in manager.nodes.keys():
                    if node_name != "laptop":  # Skip laptop
                        success, message = manager.sync_large_files(node_name)
                        if success:
                            st.success(f"✅ {node_name}: {message}")
                        else:
                            st.error(f"❌ {node_name}: {message}")
    
    st.markdown("---")
    
    # Individual node controls
    st.markdown("### 🎛️ Individual Node Controls")
    
    for node_name, node_config in manager.nodes.items():
        with st.expander(f"Node: {node_name} ({node_config['host']})"):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button(f"Deploy", key=f"deploy_{node_name}"):
                    with st.spinner(f"Deploying to {node_name}..."):
                        success, message = manager.deploy_to_node(node_name)
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
            
            with col2:
                if st.button(f"Start Ray", key=f"ray_{node_name}"):
                    with st.spinner(f"Starting Ray on {node_name}..."):
                        success, message = manager.start_ray_cluster(node_name)
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
            
            with col3:
                if st.button(f"Sync Files", key=f"sync_{node_name}"):
                    with st.spinner(f"Syncing files to {node_name}..."):
                        success, message = manager.sync_large_files(node_name)
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
            
            with col4:
                if st.button(f"Health Check", key=f"health_{node_name}"):
                    with st.spinner(f"Checking {node_name} health..."):
                        status, message = manager.get_node_health_status(node_name)
                        manager.health_status[node_name] = (status, message)
                        if status == NodeHealthStatus.GREEN:
                            st.success(f"✅ {message}")
                        elif status == NodeHealthStatus.YELLOW:
                            st.warning(f"⚠️ {message}")
                        else:
                            st.error(f"❌ {message}")
    
    st.markdown("---")
    
    # Deployment logs
    st.markdown("### 📋 Deployment Logs")
    
    if "deployment_logs" not in st.session_state:
        st.session_state.deployment_logs = []
    
    # Display recent logs
    for log in st.session_state.deployment_logs[-10:]:  # Show last 10 logs
        st.text(log)
    
    # Clear logs
    if st.button("🗑️ Clear Logs"):
        st.session_state.deployment_logs = []
        st.rerun()

def add_deployment_log(message: str):
    """Add a message to deployment logs"""
    if "deployment_logs" not in st.session_state:
        st.session_state.deployment_logs = []
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.deployment_logs.append(f"[{timestamp}] {message}")
