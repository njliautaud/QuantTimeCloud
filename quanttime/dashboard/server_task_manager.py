#!/usr/bin/env python3
"""
Server Task Manager for QuantTime Dashboard.
Handles deployment, task execution, and progress synchronization.
"""

import os
import subprocess
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import streamlit as st
import paramiko
import queue

class ServerTaskManager:
    """Manages server deployment, tasks, and synchronization."""
    
    def __init__(self):
        self.servers = self._load_server_config()
        self.task_queue = queue.Queue()
        self.running_tasks = {}
        self.server_status = {}
        self._initialize_servers()
    
    def _get_ssh_connection(self, ip_address: str, username: str, timeout: int = 10):
        """Get SSH connection with web-based password authentication."""
        print(f"[REMOTE] Connecting to {ip_address} as {username}...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Try key-based authentication first
        try:
            ssh.connect(ip_address, username=username, timeout=timeout)
            print(f"[REMOTE] ✅ Connected to {ip_address} (key auth)")
            return ssh
        except:
            # If key auth fails, prompt for password in web interface
            print(f"[REMOTE] Key authentication failed, prompting for password...")
            return self._get_ssh_connection_with_password_prompt(ip_address, username, timeout)
    
    def _get_ssh_connection_with_password_prompt(self, ip_address: str, username: str, timeout: int = 10):
        """Get SSH connection with web-based password prompt."""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Create a unique key for this connection
        password_key = f"ssh_password_{ip_address}_{username}"
        
        # Check if we already have a password for this connection
        if password_key not in st.session_state:
            # Show password input dialog
            st.markdown(f"### 🔐 SSH Authentication Required")
            st.markdown(f"**Server:** {ip_address}")
            st.markdown(f"**Username:** {username}")
            
            # Password input with hidden text
            password = st.text_input(
                "Enter SSH Password:",
                type="password",
                key=f"password_input_{password_key}",
                help="Enter the SSH password for this server"
            )
            
            # Connect button
            if st.button("🔗 Connect", key=f"connect_btn_{password_key}"):
                if password:
                    try:
                        ssh.connect(ip_address, username=username, password=password, timeout=timeout)
                        # Store password in session state for future use
                        st.session_state[password_key] = password
                        st.success(f"✅ Connected to {ip_address}")
                        print(f"[REMOTE] ✅ Connected to {ip_address} (password auth)")
                        return ssh
                    except Exception as e:
                        st.error(f"❌ Connection failed: {e}")
                        print(f"[REMOTE] ❌ Connection failed: {e}")
                        return None
                else:
                    st.error("❌ Please enter a password")
                    return None
            
            # Show instructions
            st.info("💡 **Tip:** The password will be stored securely for this session")
            st.stop()  # Stop execution until password is provided
        else:
            # Use stored password
            password = st.session_state[password_key]
            try:
                ssh.connect(ip_address, username=username, password=password, timeout=timeout)
                print(f"[REMOTE] ✅ Connected to {ip_address} (stored password)")
                return ssh
            except Exception as e:
                # Password might have changed, clear it and retry
                del st.session_state[password_key]
                st.error(f"❌ Stored password failed, please re-enter: {e}")
                return self._get_ssh_connection_with_password_prompt(ip_address, username, timeout)
    
    def _load_server_config(self) -> Dict:
        """Load server configuration."""
        print(f"[LOCAL] Loading server configuration from server/config/servers.json...")
        config_path = Path("server/config/servers.json")
        if not config_path.exists():
            st.error("❌ Server config not found: server/config/servers.json")
            print(f"[LOCAL] ❌ Server config file not found")
            return {}
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            print(f"[LOCAL] ✅ Loaded config for {len(config)} servers")
            return config
    
    def _initialize_servers(self):
        """Initialize server connections and status."""
        for server_name, server_config in self.servers.items():
            self.server_status[server_name] = {
                "connected": False,
                "last_check": None,
                "tasks": [],
                "resources": {}
            }
    
    def deploy_to_server(self, server_name: str, progress_callback=None) -> bool:
        """Deploy the project to a server via dashboard."""
        if server_name not in self.servers:
            st.error(f"❌ Server '{server_name}' not found")
            return False
        
        server = self.servers[server_name]
        username = server.get('username', 'quanttime')
        ip_address = server.get('tailscale_ip') or server.get('ip_address')
        
        if progress_callback:
            progress_callback("Initializing deployment", 0, 100)
        
        try:
            # Step 1: Test SSH connection
            if progress_callback:
                progress_callback("Testing SSH connection", 10, 100)
            
            if not self._test_ssh_connection(username, ip_address):
                st.error(f"❌ Cannot connect to {server_name}")
                return False
            
            # Step 2: Set up GitHub SSH key
            if progress_callback:
                progress_callback("Setting up GitHub authentication", 20, 100)
            
            if not self._setup_github_ssh(username, ip_address, progress_callback):
                st.error(f"❌ Failed to set up GitHub authentication on {server_name}")
                return False
            
            # Step 3: Clone repository
            if progress_callback:
                progress_callback("Cloning repository", 40, 100)
            
            github_url = self._get_github_url()
            if not self._clone_repository(username, ip_address, github_url, progress_callback):
                st.error(f"❌ Failed to clone repository on {server_name}")
                return False
            
            # Step 4: Install dependencies
            if progress_callback:
                progress_callback("Installing dependencies", 60, 100)
            
            if not self._install_dependencies(username, ip_address, progress_callback):
                st.error(f"❌ Failed to install dependencies on {server_name}")
                return False
            
            # Step 5: Set up auto-pull script
            if progress_callback:
                progress_callback("Setting up auto-pull script", 80, 100)
            
            if not self._setup_auto_pull(username, ip_address):
                st.error(f"❌ Failed to set up auto-pull script on {server_name}")
                return False
            
            # Step 6: Test deployment
            if progress_callback:
                progress_callback("Testing deployment", 90, 100)
            
            if not self._test_deployment(username, ip_address):
                st.error(f"❌ Deployment test failed on {server_name}")
                return False
            
            if progress_callback:
                progress_callback("Deployment complete!", 100, 100)
            
            st.success(f"✅ Successfully deployed to {server_name}!")
            return True
            
        except Exception as e:
            st.error(f"❌ Deployment failed: {str(e)}")
            return False
    
    def _test_ssh_connection(self, username: str, ip_address: str) -> bool:
        """Test SSH connection to server."""
        try:
            print(f"[REMOTE] Testing SSH connection to {ip_address}...")
            ssh = self._get_ssh_connection(ip_address, username, timeout=10)
            ssh.close()
            print(f"[REMOTE] ✅ SSH connection test successful")
            return True
        except Exception as e:
            error_msg = f"SSH connection failed to {ip_address}: {e}"
            st.error(error_msg)
            print(f"[ERROR] {error_msg}")  # Terminal logging
            return False
    
    def _setup_github_ssh(self, username: str, ip_address: str, progress_callback=None) -> bool:
        """Set up GitHub SSH authentication on server."""
        try:
            ssh = self._get_ssh_connection(ip_address, username, timeout=10)
            
            # Check if SSH key exists
            stdin, stdout, stderr = ssh.exec_command("test -f ~/.ssh/id_rsa")
            if stdout.channel.recv_exit_status() != 0:
                if progress_callback:
                    progress_callback("Generating SSH key", 25, 100)
                
                # Generate SSH key
                stdin, stdout, stderr = ssh.exec_command("ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ''")
                if stdout.channel.recv_exit_status() != 0:
                    ssh.close()
                    return False
            
            # Get public key
            stdin, stdout, stderr = ssh.exec_command("cat ~/.ssh/id_rsa.pub")
            public_key = stdout.read().decode().strip()
            
            ssh.close()
            
            # Show public key to user
            st.info("🔑 Please add this SSH key to your GitHub account:")
            st.code(public_key)
            
            # Wait for user to add key
            if st.button("I've added the SSH key to GitHub", key=f"ssh_key_{username}"):
                # Test GitHub connection
                ssh = self._get_ssh_connection(ip_address, username, timeout=10)
                
                stdin, stdout, stderr = ssh.exec_command("ssh -T git@github.com")
                result = stdout.channel.recv_exit_status()
                ssh.close()
                
                return result == 0
            
            return False
            
        except Exception as e:
            st.error(f"GitHub SSH setup failed: {e}")
            return False
    
    def _get_github_url(self) -> str:
        """Get GitHub repository URL."""
        print(f"[LOCAL] Getting GitHub repository URL...")
        try:
            result = subprocess.run(["git", "remote", "get-url", "origin"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                url = result.stdout.strip()
                # Convert HTTPS to SSH if needed
                if url.startswith("https://"):
                    url = url.replace("https://github.com/", "git@github.com:")
                print(f"[LOCAL] ✅ Found GitHub URL: {url}")
                return url
        except Exception as e:
            print(f"[LOCAL] ❌ Error getting GitHub URL: {e}")
        
        # Fallback: ask user
        print(f"[LOCAL] ⚠️ No GitHub URL found, prompting user...")
        return st.text_input("Enter your GitHub repository URL (SSH format):", 
                           placeholder="git@github.com:username/repo.git")
    
    def _clone_repository(self, username: str, ip_address: str, github_url: str, progress_callback=None) -> bool:
        """Clone repository on server."""
        try:
            ssh = self._get_ssh_connection(ip_address, username, timeout=10)
            
            # Create directory and clone
            commands = [
                "sudo mkdir -p /opt",
                "sudo chown quanttime:quanttime /opt",
                f"cd /opt && git clone {github_url} quanttime",
                "cd /opt/quanttime && git status"
            ]
            
            for i, cmd in enumerate(commands):
                if progress_callback:
                    progress_callback(f"Running: {cmd}", 40 + (i * 10), 100)
                
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if stdout.channel.recv_exit_status() != 0:
                    ssh.close()
                    return False
            
            ssh.close()
            return True
            
        except Exception as e:
            st.error(f"Repository clone failed: {e}")
            return False
    
    def _install_dependencies(self, username: str, ip_address: str, progress_callback=None) -> bool:
        """Install Python dependencies on server."""
        try:
            ssh = self._get_ssh_connection(ip_address, username, timeout=10)
            
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && pip install -r requirements.txt")
            result = stdout.channel.recv_exit_status()
            ssh.close()
            
            return result == 0
            
        except Exception as e:
            st.error(f"Dependency installation failed: {e}")
            return False
    
    def _setup_auto_pull(self, username: str, ip_address: str) -> bool:
        """Set up auto-pull script on server."""
        try:
            ssh = self._get_ssh_connection(ip_address, username, timeout=10)
            
            auto_pull_script = '''#!/bin/bash
cd /opt/quanttime
echo "🔄 Pulling latest changes..."
git stash -u
git pull origin main
git stash pop
if git diff --name-only HEAD~1 HEAD | grep -q "requirements.txt"; then
    echo "📦 Requirements.txt changed, updating dependencies..."
    pip install -r requirements.txt
fi
echo "✅ Code updated successfully!"
'''
            
            # Write script to server
            stdin, stdout, stderr = ssh.exec_command(f'echo \'{auto_pull_script}\' > /opt/quanttime/auto_pull.sh')
            if stdout.channel.recv_exit_status() != 0:
                ssh.close()
                return False
            
            # Make executable
            stdin, stdout, stderr = ssh.exec_command("chmod +x /opt/quanttime/auto_pull.sh")
            result = stdout.channel.recv_exit_status()
            ssh.close()
            
            return result == 0
            
        except Exception as e:
            st.error(f"Auto-pull setup failed: {e}")
            return False
    
    def _test_deployment(self, username: str, ip_address: str) -> bool:
        """Test the deployment on server."""
        try:
            ssh = self._get_ssh_connection(ip_address, username, timeout=10)
            
            stdin, stdout, stderr = ssh.exec_command("cd /opt/quanttime && python -c \"import quanttime; print('✅ Deployment successful!')\"")
            result = stdout.channel.recv_exit_status()
            ssh.close()
            
            return result == 0
            
        except Exception as e:
            st.error(f"Deployment test failed: {e}")
            return False
    
    def send_task_to_server(self, server_name: str, task_type: str, task_params: Dict) -> bool:
        """Send a task to a server for execution."""
        if server_name not in self.servers:
            st.error(f"❌ Server '{server_name}' not found")
            return False
        
        server = self.servers[server_name]
        username = server.get('username', 'quanttime')
        ip_address = server.get('tailscale_ip') or server.get('ip_address')
        
        try:
            ssh = self._get_ssh_connection(ip_address, username, timeout=10)
            
            # Create task command based on type with proper parameters
            if task_type == "data_processing":
                date_str = task_params.get('date_str')
                schema_name = task_params.get('schema_name', 'basic_normalized_v1')
                trading_hours_only = task_params.get('trading_hours_only', True)
                max_rows = task_params.get('max_rows')
                intensity_level = task_params.get('intensity_level', 'medium')
                
                # Build the command with all parameters
                cmd_parts = [
                    "cd /opt/quanttime && python -c",
                    f"\"from quanttime.data.processor import get_processor;",
                    f"p = get_processor();",
                    f"p.process_raw_to_normalized('{date_str}', '{schema_name}',",
                    f"trading_hours_only={trading_hours_only},"
                ]
                
                if max_rows:
                    cmd_parts.append(f"max_rows={max_rows},")
                
                cmd_parts.append(f"intensity_level='{intensity_level}')\"")
                
                cmd = " ".join(cmd_parts)
                
            elif task_type == "model_training":
                model_name = task_params.get('model_name')
                data_schema = task_params.get('data_schema')
                epochs = task_params.get('epochs', 100)
                batch_size = task_params.get('batch_size', 1024)
                learning_rate = task_params.get('learning_rate', 0.001)
                use_gpu = task_params.get('use_gpu', True)
                
                cmd = f"cd /opt/quanttime && python -c \"from quanttime.ml.gpu_optimized_training import train_model; train_model('{model_name}', '{data_schema}', epochs={epochs}, batch_size={batch_size}, learning_rate={learning_rate}, use_gpu={use_gpu})\""
                
            elif task_type == "backtest":
                strategy_name = task_params.get('strategy_name')
                data_schema = task_params.get('data_schema')
                start_date = task_params.get('start_date')
                end_date = task_params.get('end_date')
                commission = task_params.get('commission', 2.5)
                slippage_ticks = task_params.get('slippage_ticks', 1)
                
                cmd = f"cd /opt/quanttime && python -c \"from quanttime.backtest.engine import run_backtest; run_backtest('{strategy_name}', '{data_schema}', start_date='{start_date}', end_date='{end_date}', commission={commission}, slippage_ticks={slippage_ticks})\""
                
            else:
                st.error(f"❌ Unknown task type: {task_type}")
                return False
            
            # Create logs directory if it doesn't exist
            stdin, stdout, stderr = ssh.exec_command("mkdir -p /opt/quanttime/logs")
            
            # Execute task in background with proper logging
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = f"/opt/quanttime/logs/{task_type}_{timestamp}.log"
            
            # Execute task in background
            stdin, stdout, stderr = ssh.exec_command(f"nohup {cmd} > {log_file} 2>&1 &")
            
            # Get process ID
            stdin, stdout, stderr = ssh.exec_command("echo $!")
            pid = stdout.read().decode().strip()
            
            ssh.close()
            
            # Store task info with PID for progress tracking
            task_id = f"{server_name}_{task_type}_{timestamp}"
            self.running_tasks[task_id] = {
                "server": server_name,
                "type": task_type,
                "params": task_params,
                "pid": pid,
                "start_time": datetime.now(),
                "status": "running",
                "log_file": log_file
            }
            
            st.success(f"✅ Task sent to {server_name} (PID: {pid})")
            print(f"[REMOTE] Task {task_id} started on {server_name} with PID {pid}")
            return True
            
        except Exception as e:
            st.error(f"❌ Failed to send task: {e}")
            print(f"[ERROR] Failed to send task to {server_name}: {e}")
            return False
    
    def get_server_status(self, server_name: str) -> Dict[str, Any]:
        """Get status of a specific server"""
        try:
            if server_name not in self.servers:
                return {"connected": False, "error": "Server not found"}
            
            server_config = self.servers[server_name]
            
            # Check if this is a local connection (laptop)
            if server_name == "laptop":
                # For laptop, check if we're running locally
                import socket
                try:
                    hostname = socket.gethostname()
                    local_ip = socket.gethostbyname(hostname)
                    # If we're running on localhost or local network, laptop is always online
                    if (local_ip.startswith('127.') or 
                        local_ip.startswith('192.168.') or 
                        local_ip.startswith('10.') or
                        hostname.lower() in ['laptop', 'desktop', 'razer']):
                        return {
                            "connected": True,
                            "error": None,
                            "local": True
                        }
                except:
                    pass
            
            # For remote servers, check SSH connection
            ip_address = server_config.get('tailscale_ip') or server_config.get('ip_address')
            username = server_config.get('username', 'quanttime')
            
            print(f"[REMOTE] Getting status from {server_name} ({ip_address})...")
            
            # Try SSH connection
            ssh = self._get_ssh_connection(ip_address, username, timeout=5)
            
            if ssh:
                ssh.close()
                return {"connected": True, "error": None}
            else:
                return {"connected": False, "error": "SSH connection failed"}
                
        except Exception as e:
            print(f"[ERROR] {server_name}: {e}")
            return {"connected": False, "error": str(e)}
    
    def sync_server_progress(self, server_name: str) -> bool:
        """Sync progress from server to laptop."""
        if server_name not in self.servers:
            st.error(f"❌ Server '{server_name}' not found")
            return False
        
        server = self.servers[server_name]
        username = server.get('username', 'quanttime')
        ip_address = server.get('tailscale_ip') or server.get('ip_address')
        
        try:
            print(f"[LOCAL] Starting sync from {server_name} ({ip_address}) to local ./data/...")
            # Use rsync with password authentication
            rsync_cmd = f'rsync -avz -e "sshpass -e ssh -o StrictHostKeyChecking=no" {username}@{ip_address}:/opt/quanttime/data/ ./data/'
            print(f"[LOCAL] Executing: {rsync_cmd}")
            ssh_env = {**os.environ, "SSHPASS": os.environ.get("R630XL_SSH_PASSWORD", "")}
            result = subprocess.run(rsync_cmd, shell=True, capture_output=True, text=True, env=ssh_env)
            
            if result.returncode == 0:
                st.success(f"✅ Synced data from {server_name}")
                print(f"[LOCAL] ✅ Sync completed successfully")
                return True
            else:
                error_msg = f"❌ Sync failed: {result.stderr}"
                st.error(error_msg)
                print(f"[LOCAL] ❌ Sync failed: {error_msg}")  # Terminal logging
                return False
                
        except Exception as e:
            error_msg = f"❌ Sync failed: {e}"
            st.error(error_msg)
            print(f"[LOCAL] ❌ Sync failed: {error_msg}")  # Terminal logging
            return False

# Global instance
task_manager = ServerTaskManager()
