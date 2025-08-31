#!/usr/bin/env python3
"""
Node Deployment and Health Monitoring System
Handles automatic deployment, synchronization, and health checks for all nodes
with proper environment isolation
"""

import streamlit as st
import json
import subprocess
import paramiko
import time
import threading
import os
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml

class NodeHealthStatus:
    """Node health status enumeration"""
    RED = "red"      # Cannot connect
    YELLOW = "yellow"  # Connected but issues (version mismatch, missing deps)
    GREEN = "green"    # Fully operational

class EnvironmentIsolationManager:
    """Manages environment isolation between nodes"""
    
    def __init__(self):
        self.local_platform = platform.system().lower()
        self.local_arch = platform.machine()
    
    def get_node_environment_config(self, node_name: str, node_config: Dict) -> Dict:
        """Generate node-specific environment configuration"""
        node_platform = node_config.get("platform", "linux")  # Default to linux for servers
        node_arch = node_config.get("arch", "x86_64")
        
        # Base environment config
        env_config = {
            "node_name": node_name,
            "platform": node_platform,
            "arch": node_arch,
            "python_version": "3.11",  # Default, can be overridden
            "project_path": "/opt/quanttime",  # Server path
            "data_path": "/opt/quanttime/data",
            "logs_path": "/opt/quanttime/logs",
            "cache_path": "/opt/quanttime/cache",
            "temp_path": "/opt/quanttime/temp",
            "venv_path": "/opt/quanttime/.venv",
            "ray_temp_dir": "/tmp/ray",
            "ray_log_dir": "/opt/quanttime/logs/ray",
        }
        
        # Platform-specific adjustments
        if node_platform == "windows":
            env_config.update({
                "project_path": "C:\\Users\\user\\Documents\\GitHub\\QuantTime",
                "data_path": "C:\\Users\\user\\Documents\\GitHub\\QuantTime\\data",
                "logs_path": "C:\\Users\\user\\Documents\\GitHub\\QuantTime\\logs",
                "cache_path": "C:\\Users\\user\\Documents\\GitHub\\QuantTime\\cache",
                "temp_path": "C:\\Users\\user\\Documents\\GitHub\\QuantTime\\temp",
                "venv_path": "C:\\Users\\user\\Documents\\GitHub\\QuantTime\\.venv",
                "ray_temp_dir": "C:\\Users\\user\\Documents\\GitHub\\QuantTime\\temp\\ray",
                "ray_log_dir": "C:\\Users\\user\\Documents\\GitHub\\QuantTime\\logs\\ray",
            })
        
        return env_config
    
    def create_node_environment_script(self, node_name: str, env_config: Dict) -> str:
        """Create a node-specific environment setup script"""
        platform = env_config["platform"]
        
        if platform == "windows":
            return self._create_windows_env_script(node_name, env_config)
        else:
            return self._create_linux_env_script(node_name, env_config)
    
    def _create_linux_env_script(self, node_name: str, env_config: Dict) -> str:
        """Create Linux environment setup script"""
        script = f"""#!/bin/bash
# Node-specific environment setup for {node_name}
# Generated automatically - DO NOT EDIT MANUALLY

export NODE_NAME="{node_name}"
export PLATFORM="{env_config['platform']}"
export ARCH="{env_config['arch']}"
export PYTHON_VERSION="{env_config['python_version']}"

# Project paths
export QUANTTIME_ROOT="{env_config['project_path']}"
export QUANTTIME_DATA="{env_config['data_path']}"
export QUANTTIME_LOGS="{env_config['logs_path']}"
export QUANTTIME_CACHE="{env_config['cache_path']}"
export QUANTTIME_TEMP="{env_config['temp_path']}"
export QUANTTIME_VENV="{env_config['venv_path']}"

# Ray configuration
export RAY_TEMP_DIR="{env_config['ray_temp_dir']}"
export RAY_LOG_DIR="{env_config['ray_log_dir']}"

# Create directories
mkdir -p "$QUANTTIME_DATA" "$QUANTTIME_LOGS" "$QUANTTIME_CACHE" "$QUANTTIME_TEMP" "$RAY_TEMP_DIR" "$RAY_LOG_DIR"

# Set permissions
chmod 755 "$QUANTTIME_DATA" "$QUANTTIME_LOGS" "$QUANTTIME_CACHE" "$QUANTTIME_TEMP"

# Python path
export PYTHONPATH="$QUANTTIME_ROOT:$PYTHONPATH"

# Activate virtual environment
if [ -f "$QUANTTIME_VENV/bin/activate" ]; then
    source "$QUANTTIME_VENV/bin/activate"
fi

echo "Environment setup complete for {node_name}"
"""
        return script
    
    def _create_windows_env_script(self, node_name: str, env_config: Dict) -> str:
        """Create Windows environment setup script"""
        script = f"""@echo off
REM Node-specific environment setup for {node_name}
REM Generated automatically - DO NOT EDIT MANUALLY

set NODE_NAME={node_name}
set PLATFORM={env_config['platform']}
set ARCH={env_config['arch']}
set PYTHON_VERSION={env_config['python_version']}

REM Project paths
set QUANTTIME_ROOT={env_config['project_path']}
set QUANTTIME_DATA={env_config['data_path']}
set QUANTTIME_LOGS={env_config['logs_path']}
set QUANTTIME_CACHE={env_config['cache_path']}
set QUANTTIME_TEMP={env_config['temp_path']}
set QUANTTIME_VENV={env_config['venv_path']}

REM Ray configuration
set RAY_TEMP_DIR={env_config['ray_temp_dir']}
set RAY_LOG_DIR={env_config['ray_log_dir']}

REM Create directories
if not exist "%QUANTTIME_DATA%" mkdir "%QUANTTIME_DATA%"
if not exist "%QUANTTIME_LOGS%" mkdir "%QUANTTIME_LOGS%"
if not exist "%QUANTTIME_CACHE%" mkdir "%QUANTTIME_CACHE%"
if not exist "%QUANTTIME_TEMP%" mkdir "%QUANTTIME_TEMP%"
if not exist "%RAY_TEMP_DIR%" mkdir "%RAY_TEMP_DIR%"
if not exist "%RAY_LOG_DIR%" mkdir "%RAY_LOG_DIR%"

REM Python path
set PYTHONPATH=%QUANTTIME_ROOT%;%PYTHONPATH%

REM Activate virtual environment
if exist "%QUANTTIME_VENV%\\Scripts\\activate.bat" (
    call "%QUANTTIME_VENV%\\Scripts\\activate.bat"
)

echo Environment setup complete for {node_name}
"""
        return script
    
    def create_node_config_file(self, node_name: str, env_config: Dict) -> str:
        """Create a node-specific configuration file"""
        config = {
            "node": {
                "name": node_name,
                "platform": env_config["platform"],
                "arch": env_config["arch"],
                "python_version": env_config["python_version"]
            },
            "paths": {
                "project_root": env_config["project_path"],
                "data": env_config["data_path"],
                "logs": env_config["logs_path"],
                "cache": env_config["cache_path"],
                "temp": env_config["temp_path"],
                "venv": env_config["venv_path"]
            },
            "ray": {
                "temp_dir": env_config["ray_temp_dir"],
                "log_dir": env_config["ray_log_dir"],
                "dashboard_port": 8265,
                "head_port": 10001
            },
            "environment": {
                "isolated": True,
                "auto_setup": True,
                "sync_exclusions": [
                    ".env",
                    ".env.local",
                    "config/local_*",
                    "logs/*",
                    "cache/*",
                    "temp/*",
                    ".venv/*",
                    "__pycache__/*",
                    "*.pyc"
                ]
            }
        }
        
        return json.dumps(config, indent=2)

class NodeDeploymentManager:
    """Manages deployment and health monitoring of all nodes with environment isolation"""
    
    def __init__(self):
        self.config_file = Path("config/sftp_config.json")
        self.ray_config_file = Path("config/ray_config.json")
        self.nodes = {}
        self.health_status = {}
        self.env_manager = EnvironmentIsolationManager()
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
            # Get node environment config
            env_config = self.env_manager.get_node_environment_config(node_name, self.nodes[node_name])
            project_path = env_config["project_path"]
            
            # Check if repo exists
            stdin, stdout, stderr = ssh.exec_command(f"cd {project_path} && git status", timeout=10)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Repository not found"
            
            # Check for uncommitted changes
            stdin, stdout, stderr = ssh.exec_command(f"cd {project_path} && git status --porcelain", timeout=10)
            uncommitted = stdout.read().decode().strip()
            if uncommitted:
                return False, f"Uncommitted changes: {len(uncommitted.splitlines())} files"
            
            # Check if up to date with remote
            stdin, stdout, stderr = ssh.exec_command(f"cd {project_path} && git fetch origin && git status -uno", timeout=10)
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
            # Get node environment config
            env_config = self.env_manager.get_node_environment_config(node_name, self.nodes[node_name])
            project_path = env_config["project_path"]
            venv_path = env_config["venv_path"]
            
            # Check if virtual environment exists
            stdin, stdout, stderr = ssh.exec_command(f"cd {project_path} && ls -la {venv_path}", timeout=10)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Virtual environment missing"
            
            # Check key dependencies
            dependencies = ["ray", "streamlit", "pandas", "numpy", "pysftp"]
            missing_deps = []
            
            for dep in dependencies:
                if env_config["platform"] == "windows":
                    cmd = f"cd {project_path} && {venv_path}\\Scripts\\python.exe -c 'import {dep}'"
                else:
                    cmd = f"cd {project_path} && {venv_path}/bin/python -c 'import {dep}'"
                
                stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
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
            # Get node environment config
            env_config = self.env_manager.get_node_environment_config(node_name, self.nodes[node_name])
            project_path = env_config["project_path"]
            venv_path = env_config["venv_path"]
            
            # Check if Ray is installed
            if env_config["platform"] == "windows":
                cmd = f"cd {project_path} && {venv_path}\\Scripts\\python.exe -c 'import ray'"
            else:
                cmd = f"cd {project_path} && {venv_path}/bin/python -c 'import ray'"
            
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Ray not installed"
            
            # Check if Ray cluster is running
            if env_config["platform"] == "windows":
                cmd = f"cd {project_path} && {venv_path}\\Scripts\\python.exe -c 'import ray; print(ray.is_initialized())'"
            else:
                cmd = f"cd {project_path} && {venv_path}/bin/python -c 'import ray; print(ray.is_initialized())'"
            
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
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
        """Deploy the project to a node with environment isolation"""
        ssh = self.get_ssh_connection(node_name)
        if not ssh:
            return False, "Cannot connect to node"
        
        try:
            # Get node environment config
            env_config = self.env_manager.get_node_environment_config(node_name, self.nodes[node_name])
            project_path = env_config["project_path"]
            
            # Create directory if it doesn't exist
            stdin, stdout, stderr = ssh.exec_command(f"sudo mkdir -p {project_path}", timeout=10)
            stdin, stdout, stderr = ssh.exec_command(f"sudo chown {self.nodes[node_name]['username']}:{self.nodes[node_name]['username']} {project_path}", timeout=10)
            
            # Check if repository exists
            stdin, stdout, stderr = ssh.exec_command(f"cd {project_path} && ls -la", timeout=10)
            repo_exists = ".git" in stdout.read().decode()
            
            if not repo_exists:
                # Clone repository
                git_url = "https://github.com/njliautaud/QuantTimeCloud.git"
                stdin, stdout, stderr = ssh.exec_command(f"cd {project_path}/.. && git clone {git_url} quanttime", timeout=60)
                if stdout.channel.recv_exit_status() != 0:
                    return False, "Failed to clone repository"
            else:
                # Pull latest changes
                stdin, stdout, stderr = ssh.exec_command(f"cd {project_path} && git pull origin master", timeout=30)
                if stdout.channel.recv_exit_status() != 0:
                    return False, "Failed to pull latest changes"
            
            # Run the setup script on the node
            if env_config["platform"] == "windows":
                setup_cmd = f"cd {project_path} && python scripts/setup_node.py --node-name {node_name}"
            else:
                setup_cmd = f"cd {project_path} && python3 scripts/setup_node.py --node-name {node_name}"
            
            stdin, stdout, stderr = ssh.exec_command(setup_cmd, timeout=300)  # 5 minutes timeout
            if stdout.channel.recv_exit_status() != 0:
                stderr_output = stderr.read().decode()
                return False, f"Setup script failed: {stderr_output}"
            
            return True, "Deployment successful - node setup completed"
            
        except Exception as e:
            return False, f"Deployment error: {str(e)}"
        finally:
            ssh.close()
    
    def start_ray_cluster(self, node_name: str) -> Tuple[bool, str]:
        """Start Ray cluster on a node using the launcher script"""
        ssh = self.get_ssh_connection(node_name)
        if not ssh:
            return False, "Cannot connect to node"
        
        try:
            # Get node environment config
            env_config = self.env_manager.get_node_environment_config(node_name, self.nodes[node_name])
            project_path = env_config["project_path"]
            
            # Determine if this is the head node
            is_head = node_name == "laptop"
            
            # Run the launcher script on the node
            if env_config["platform"] == "windows":
                launch_cmd = f"cd {project_path} && python scripts/launch_node.py --node-name {node_name}"
                if is_head:
                    launch_cmd += " --head"
            else:
                launch_cmd = f"cd {project_path} && python3 scripts/launch_node.py --node-name {node_name}"
                if is_head:
                    launch_cmd += " --head"
            
            # Start the launcher in the background
            stdin, stdout, stderr = ssh.exec_command(f"nohup {launch_cmd} > logs/launch.log 2>&1 &", timeout=30)
            if stdout.channel.recv_exit_status() != 0:
                return False, "Failed to start launcher script"
            
            # Wait a moment for Ray to start
            time.sleep(10)
            
            return True, "Ray cluster launcher started"
            
        except Exception as e:
            return False, f"Ray start error: {str(e)}"
        finally:
            ssh.close()
    
    def sync_large_files(self, node_name: str) -> Tuple[bool, str]:
        """Sync large files to node using SFTP with environment isolation"""
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
