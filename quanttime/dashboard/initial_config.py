"""
Initial Configuration Page for QuantTime
Runs before the main dashboard to set up node connections and configurations
"""

import streamlit as st
import paramiko
import json
import logging
import subprocess
import psutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import pandas as pd

# Import persistent node status manager
from quanttime.dashboard.node_status_manager import node_status_manager

logger = logging.getLogger(__name__)


class InitialConfigManager:
    """Manages initial configuration and node setup"""
    
    def __init__(self):
        # Available Tailscale IPs for remote nodes
        self.available_ips = [
            "jupiter",  # R630XL
            "saturn",  # R810
        ]
        
        self.nodes = {
            "laptop": {
                "name": "Development Laptop",
                "host": "localhost",
                "port": 22,
                "description": "Local development machine",
                "type": "control",
                "auto_detect": True
            },
            "r630xl": {
                "name": "R630XL Server", 
                "host": "jupiter",
                "port": 22,
                "description": "R630XL compute server",
                "type": "compute",
                "auto_detect": False
            },
            "r810": {
                "name": "R810 Server",
                "host": "saturn", 
                "port": 22,
                "description": "R810 compute server",
                "type": "compute",
                "auto_detect": False
            }
        }
        self.connections = {}
        
        # Load persistent node status instead of using session state
        self.node_status = node_status_manager.get_all_node_status()
        
        # Auto-detect local system stats
        self._detect_local_system()
    
    def _detect_local_system(self):
        """Auto-detect local system information"""
        try:
            import psutil
            import platform
            
            # Get CPU info
            cpu_cores = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get memory info
            memory = psutil.virtual_memory()
            ram_gb = round(memory.total / (1024**3), 1)
            
            # Get system info
            system_info = platform.system()
            system_version = platform.version()
            
            # Check if QuantTime is installed locally
            import os
            quanttime_installed = os.path.exists("run.py") or os.path.exists("quanttime")
            
            # Check if Ray is running locally
            ray_running = False
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    if 'ray' in proc.info['name'].lower() or any('ray' in str(cmd).lower() for cmd in proc.info['cmdline'] or []):
                        ray_running = True
                        break
            except:
                pass
            
            # Update laptop node with detected info
            self.nodes["laptop"].update({
                "cpu_cores": cpu_cores,
                "ram_gb": ram_gb,
                "system_info": f"{system_info} {system_version}",
                "quanttime_installed": quanttime_installed,
                "ray_running": ray_running,
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent
            })
            
            # Mark laptop as automatically connected
            laptop_status = {
                "connected": True,
                "username": "local",
                "status": "🟢 Auto-Detected",
                "health_info": {
                    "system": f"{system_info} {system_version}",
                    "cpu_cores": str(cpu_cores),
                    "memory": f"{ram_gb} GB",
                    "quanttime_installed": quanttime_installed,
                    "ray_running": ray_running
                }
            }
            self.node_status["laptop"] = laptop_status
            node_status_manager.update_node_status("laptop", laptop_status)
            
        except Exception as e:
            logger.error(f"Failed to detect local system: {e}")
            # Fallback values
            self.nodes["laptop"].update({
                "cpu_cores": "Unknown",
                "ram_gb": "Unknown",
                "system_info": "Detection failed",
                "quanttime_installed": False,
                "ray_running": False
            })
    
    def _create_ssh_connection(self, host: str, username: str, password: str, port: int = 22) -> Optional[paramiko.SSHClient]:
        """Create SSH connection using the same pattern as test_node_connection"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # For localhost, try without authentication first
            if host in ["localhost", "127.0.0.1"]:
                try:
                    ssh.connect(
                        host,
                        port=port,
                        username=username,
                        timeout=10
                    )
                    logger.info(f"✅ Localhost connection successful (no auth)")
                    return ssh
                except Exception as e:
                    logger.warning(f"⚠️ Localhost connection failed: {e}")
                    logger.info(f"🔄 Trying password authentication...")
                    # Try password authentication
                    ssh.connect(
                        host,
                        port=port,
                        username=username,
                        password=password,
                        timeout=10
                    )
                    logger.info(f"✅ Localhost connection successful (password)")
                    return ssh
            else:
                # Remote node - use password authentication
                logger.info(f"🔄 Attempting remote connection with password...")
                ssh.connect(
                    host,
                    port=port,
                    username=username,
                    password=password,
                    timeout=15  # Increased timeout
                )
                logger.info(f"✅ Remote connection successful")
                return ssh
                
        except Exception as e:
            logger.error(f"❌ SSH connection failed: {e}")
            if 'ssh' in locals():
                ssh.close()
            return None
        
    def test_node_connection(self, node_id: str, username: str, password: str) -> Tuple[bool, str, Dict]:
        """Test connection to a specific node and get health info"""
        node = self.nodes[node_id]
        
        logger.info(f"🔍 Testing connection to {node_id} with username: {username}")
        logger.info(f"   Target node: {node['name']} ({node['host']}:{node['port']})")
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Parse username@host format
            if "@" in username:
                username_part, host_part = username.split("@", 1)
                target_host = host_part
                target_username = username_part
                logger.info(f"   Parsed username@host: {target_username}@{target_host}")
            else:
                target_host = node["host"]
                target_username = username
                logger.info(f"   Using direct host: {target_username}@{target_host}")
            
            # For localhost, try without authentication first
            if target_host in ["localhost", "127.0.0.1"]:
                logger.info(f"   Attempting localhost connection...")
                try:
                    ssh.connect(
                        target_host,
                        port=node["port"],
                        username=target_username,
                        timeout=10
                    )
                    auth_method = "localhost"
                    logger.info(f"   ✅ Localhost connection successful (no auth)")
                except Exception as e:
                    logger.warning(f"   ⚠️ Localhost connection failed: {e}")
                    logger.info(f"   🔄 Trying password authentication...")
                    # Try password authentication
                    ssh.connect(
                        target_host,
                        port=node["port"],
                        username=target_username,
                        password=password,
                        timeout=10
                    )
                    auth_method = "password"
                    logger.info(f"   ✅ Localhost connection successful (password)")
            else:
                # Remote node - use password authentication
                logger.info(f"   🔄 Attempting remote connection with password...")
            try:
                ssh.connect(
                    target_host,
                    port=node["port"],
                    username=target_username,
                    password=password,
                    timeout=15  # Increased timeout
                )
                auth_method = "password"
                logger.info(f"   ✅ Remote connection successful")
            except Exception as conn_error:
                logger.error(f"   ❌ SSH connection failed: {conn_error}")
                ssh.close()
                raise conn_error
            
            # Test basic commands
            logger.info(f"   🔍 Running health checks...")
            health_info = {}
            
            # Get system info
            logger.info(f"   📋 Getting system info...")
            stdin, stdout, stderr = ssh.exec_command("uname -a", timeout=5)
            system_info = stdout.read().decode().strip()
            health_info["system"] = system_info
            logger.info(f"   ✅ System: {system_info}")
            
            # Get CPU info
            logger.info(f"   🖥️ Getting CPU info...")
            stdin, stdout, stderr = ssh.exec_command("nproc", timeout=5)
            cpu_info = stdout.read().decode().strip()
            health_info["cpu_cores"] = cpu_info
            logger.info(f"   ✅ CPU cores: {cpu_info}")
            
            # Get memory info
            logger.info(f"   💾 Getting memory info...")
            stdin, stdout, stderr = ssh.exec_command("free -h | grep Mem", timeout=5)
            memory_info = stdout.read().decode().strip()
            health_info["memory"] = memory_info
            logger.info(f"   ✅ Memory: {memory_info}")
            
            # Check if QuantTime is installed
            logger.info(f"   📦 Checking QuantTime installation...")
            stdin, stdout, stderr = ssh.exec_command("ls -la /opt/quanttime 2>/dev/null || echo 'Not found'", timeout=5)
            quanttime_path = stdout.read().decode().strip()
            health_info["quanttime_installed"] = "Not found" not in quanttime_path
            logger.info(f"   ✅ QuantTime installed: {health_info['quanttime_installed']}")
            
            # Check if Ray is running
            logger.info(f"   ⚡ Checking Ray status...")
            stdin, stdout, stderr = ssh.exec_command("ps aux | grep ray | grep -v grep || echo 'Not running'", timeout=5)
            ray_running = stdout.read().decode().strip()
            health_info["ray_running"] = "Not running" not in ray_running
            logger.info(f"   ✅ Ray running: {health_info['ray_running']}")
            
            ssh.close()
            logger.info(f"   🔗 SSH connection closed")
            
            return True, f"Connected successfully via {auth_method}", health_info
            
        except Exception as e:
            logger.error(f"   ❌ Connection failed for {node_id}: {str(e)}")
            logger.error(f"   🔍 Error details: {type(e).__name__}: {e}")
            if hasattr(e, 'args') and e.args:
                logger.error(f"   📋 Error args: {e.args}")
            return False, f"Connection failed: {str(e)}", {}
    
    def launch_quanttime_on_node(self, node_id: str, username: str, password: str) -> Tuple[bool, str]:
        """Launch QuantTime on a specific node"""
        node = self.nodes[node_id]
        
        logger.info(f"🚀 Launching QuantTime on {node_id} with username: {username}")
        logger.info(f"   Target node: {node['name']} ({node['host']}:{node['port']})")
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Parse username@host format
            if "@" in username:
                username_part, host_part = username.split("@", 1)
                target_host = host_part
                target_username = username_part
                logger.info(f"   Parsed username@host: {target_username}@{target_host}")
            else:
                target_host = node["host"]
                target_username = username
                logger.info(f"   Using direct host: {target_username}@{target_host}")
            
            logger.info(f"   🔗 Establishing SSH connection...")
            connection_established = False
            
            if target_host in ["localhost", "127.0.0.1"]:
                try:
                    ssh.connect(target_host, port=node["port"], username=target_username, timeout=10)
                    logger.info(f"   ✅ Localhost connection successful (no auth)")
                    connection_established = True
                except Exception as e:
                    logger.warning(f"   ⚠️ Localhost connection failed: {e}")
                    logger.info(f"   🔄 Trying password authentication...")
                    try:
                        ssh.connect(target_host, port=node["port"], username=target_username, password=password, timeout=10)
                        logger.info(f"   ✅ Localhost connection successful (password)")
                        connection_established = True
                    except Exception as e2:
                        logger.error(f"   ❌ Localhost connection failed with password: {e2}")
                        ssh.close()
                        raise e2
            else:
                try:
                    ssh.connect(target_host, port=node["port"], username=target_username, password=password, timeout=15)
                    logger.info(f"   ✅ Remote connection successful")
                    connection_established = True
                except Exception as conn_error:
                    logger.error(f"   ❌ SSH connection failed: {conn_error}")
                    ssh.close()
                    raise conn_error
            
            if not connection_established:
                raise Exception("Failed to establish SSH connection")
            
            # Launch QuantTime in background
            logger.info(f"   🚀 Executing launch command...")
            command = "cd /opt/quanttime && source venv/bin/activate && nohup python run.py > quanttime.log 2>&1 &"
            logger.info(f"   📋 Command: {command}")
            
            stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
            exit_status = stdout.channel.recv_exit_status()
            logger.info(f"   📊 Command exit status: {exit_status}")
            
            if exit_status != 0:
                stderr_output = stderr.read().decode().strip()
                logger.error(f"   ❌ Command failed with stderr: {stderr_output}")
            
            # Wait a moment and check if it started
            logger.info(f"   ⏳ Waiting 2 seconds for process to start...")
            time.sleep(2)
            
            logger.info(f"   🔍 Checking if QuantTime is running...")
            stdin, stdout, stderr = ssh.exec_command("ps aux | grep 'python run.py' | grep -v grep", timeout=10)
            running = stdout.read().decode().strip()
            logger.info(f"   📋 Process check result: {running}")
            
            ssh.close()
            logger.info(f"   🔗 SSH connection closed")
            
            if running:
                logger.info(f"   ✅ QuantTime successfully launched on {node_id}")
                return True, f"QuantTime launched successfully on {node_id}"
            else:
                logger.warning(f"   ⚠️ QuantTime process not found on {node_id}")
                return False, f"Failed to launch QuantTime on {node_id} - process not found"
                
        except Exception as e:
            logger.error(f"   ❌ Failed to launch QuantTime on {node_id}: {str(e)}")
            logger.error(f"   🔍 Error details: {type(e).__name__}: {e}")
            if hasattr(e, 'args') and e.args:
                logger.error(f"   📋 Error args: {e.args}")
            return False, f"Failed to launch QuantTime on {node_id}: {str(e)}"

    def _should_retry_connection(self, node_id: str) -> bool:
        """Check if we should retry connection based on recent failures"""
        node_status = self.node_status.get(node_id, {})
        last_failure = node_status.get("last_auth_failure")
        
        if not last_failure:
            return True
        
        try:
            failure_time = datetime.fromisoformat(last_failure)
            time_since_failure = datetime.now() - failure_time
            
            # Don't retry if last failure was within 30 seconds
            return time_since_failure.total_seconds() > 30
        except:
            return True
    
    def _validate_credentials(self, username: str, password: str, host: str) -> Tuple[bool, str]:
        """Validate SSH credentials before attempting connection"""
        if not username or username.strip() == "":
            return False, "Username cannot be empty"
        
        if not password or password.strip() == "":
            return False, "Password cannot be empty"
        
        # Check for common credential issues
        if len(password) < 3:
            return False, "Password seems too short"
        
        # Check if we've had recent auth failures for this host
        node_id = self._get_node_id_by_host(host)
        if node_id:
            node_status = self.node_status.get(node_id, {})
            last_failure = node_status.get("last_auth_failure")
            if last_failure:
                try:
                    failure_time = datetime.fromisoformat(last_failure)
                    time_since_failure = datetime.now() - failure_time
                    if time_since_failure.total_seconds() < 60:  # Within last minute
                        return False, f"Recent authentication failure. Please check credentials and try again in {60 - int(time_since_failure.total_seconds())} seconds."
                except:
                    pass
        
        return True, "Credentials appear valid"
    
    def _get_node_id_by_host(self, host: str) -> Optional[str]:
        """Get node_id based on host address"""
        for node_id, node_info in self.nodes.items():
            if node_info.get("host") == host:
                return node_id
        return None


def render_initial_config_page():
    """Render the initial configuration page"""
    st.markdown("""
    # ⚙️ QuantTime Initial Configuration
    
    Welcome to QuantTime! Let's set up your node connections and configurations.
    """)
    
    # Initialize config manager
    if "initial_config_manager" not in st.session_state:
        st.session_state.initial_config_manager = InitialConfigManager()
    
    manager = st.session_state.initial_config_manager
    
    # Configuration steps
    st.markdown("## 📋 Configuration Steps")
    
    # Step 1: Node Connection Setup
    st.markdown("### Step 1: Node Connection Setup")
    
    # Create tabs for each node
    node_tabs = st.tabs([f"🖥️ {node['name']}" for node in manager.nodes.values()])
    
    for i, (node_id, node_info) in enumerate(manager.nodes.items()):
        with node_tabs[i]:
            st.markdown(f"**{node_info['name']}**")
            st.markdown(f"*{node_info['description']}*")
            
            # Check if this is the laptop (auto-detected)
            if node_info.get("auto_detect", False):
                # Show auto-detected laptop info
                status = manager.node_status.get(node_id, {})
                if status.get("connected", False):
                    st.success("🟢 **Auto-Detected & Online**")
                    
                    # Display detected system info
                    health_info = status.get("health_info", {})
                    if health_info:
                        st.markdown("**System Information:**")
                        st.markdown(f"- **System:** {health_info.get('system', 'Unknown')}")
                        st.markdown(f"- **CPU:** {health_info.get('cpu_cores', 'Unknown')} cores")
                        st.markdown(f"- **Memory:** {health_info.get('memory', 'Unknown')}")
                        st.markdown(f"- **QuantTime:** {'✅ Installed' if health_info.get('quanttime_installed', False) else '❌ Not installed'}")
                        st.markdown(f"- **Ray:** {'✅ Running' if health_info.get('ray_running', False) else '❌ Not running'}")
                    
                    # Show current stats
                    if "cpu_percent" in node_info and "memory_percent" in node_info:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("CPU Usage", f"{node_info['cpu_percent']:.1f}%")
                        with col2:
                            st.metric("Memory Usage", f"{node_info['memory_percent']:.1f}%")
                    
                    # Launch QuantTime button for local machine
                    if st.button("🚀 Launch QuantTime Locally", key=f"launch_local_{node_id}"):
                        st.success("✅ QuantTime is already running on this machine!")
                else:
                    st.error("❌ Auto-detection failed")
            else:
                # Show remote node connection interface
                st.markdown(f"**Host:** `{node_info['host']}:{node_info['port']}`")
                
                # IP input and quick selection (outside form)
                st.markdown("**Connection Settings:**")
                
                # IP input with suggestions
                col1, col2 = st.columns([2, 1])
                with col1:
                    ip_input = st.text_input(
                        "Tailscale IP Address:",
                        value=node_info['host'],  # Use the configured host as default
                        key=f"ip_input_{node_id}",
                        help="Enter the Tailscale IP address for this node"
                    )
                with col2:
                    if st.button("Use Default IP", key=f"default_ip_{node_id}"):
                        st.session_state[f"ip_input_{node_id}"] = node_info['host']
                        st.rerun()
                
                # Show available IPs as quick selection buttons
                st.markdown("**Quick Select IP:**")
                ip_cols = st.columns(len(manager.available_ips))
                for i, ip in enumerate(manager.available_ips):
                    with ip_cols[i]:
                        if st.button(f"{ip}", key=f"quick_ip_{node_id}_{i}"):
                            st.session_state[f"ip_input_{node_id}"] = ip
                            st.rerun()
                
                # Connection form for remote nodes
                with st.form(key=f"initial_connect_{node_id}"):
                    # Username input (user types part before @)
                    username_prefix = st.text_input(
                        "Username (before @):",
                        value="jupiter",
                        key=f"username_prefix_{node_id}",
                        help="Enter the username part before @ (e.g., 'jupiter' for 'jupiter@jupiter')"
                    )
                    
                    # Show full username preview
                    full_username = f"{username_prefix}@{ip_input}"
                    st.info(f"**Full Username:** `{full_username}`")
                    
                    # SSH password
                    password = st.text_input(
                        "SSH Password:",
                        type="password",
                        key=f"ssh_password_{node_id}",
                        help="Enter the SSH password for the selected IP"
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        test_btn = st.form_submit_button("🔍 Test Connection")
                    with col2:
                        launch_btn = st.form_submit_button("🚀 Launch QuantTime")
                
                if test_btn:
                    # Get IP input from session state (outside form)
                    current_ip = st.session_state.get(f"ip_input_{node_id}", node_info['host'])
                    if username_prefix and password and current_ip:
                        full_username = f"{username_prefix}@{current_ip}"
                        with st.spinner(f"Testing connection to {node_id} ({current_ip})..."):
                            success, message, health_info = manager.test_node_connection(node_id, full_username, password)
                            if success:
                                st.success(f"✅ {message}")
                                
                                # Display health info
                                if health_info:
                                    st.markdown("**System Health:**")
                                    for key, value in health_info.items():
                                        if key == "quanttime_installed":
                                            status = "✅ Installed" if value else "❌ Not installed"
                                            st.markdown(f"- **QuantTime:** {status}")
                                        elif key == "ray_running":
                                            status = "✅ Running" if value else "❌ Not running"
                                            st.markdown(f"- **Ray:** {status}")
                                        else:
                                            st.markdown(f"- **{key.title()}:** {value}")
                                
                                # Store connection info
                                connection_status = {
                                    "connected": True,
                                    "username": full_username,
                                    "health_info": health_info,
                                    "status": "🟢 Connected"
                                }
                                manager.node_status[node_id] = connection_status
                                node_status_manager.update_node_status(node_id, connection_status)
                                
                                # Update session state for sidebar sync
                                st.session_state.node_status = manager.node_status
                                
                                # Force sidebar refresh
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                                
                                # Check if this is an authentication failure
                                if "authentication" in message.lower() or "auth" in message.lower():
                                    st.warning("🔑 **Authentication Issue Detected**")
                                    st.markdown("""
                                    **Possible solutions:**
                                    - Check if the password is correct
                                    - Verify the username format (should be just the username part)
                                    - Ensure SSH is enabled on the server
                                    - Try reconnecting with fresh credentials
                                    """)
                                    
                                    # Add a reset credentials button
                                    if st.button("🔄 Reset Credentials & Retry", key=f"reset_creds_{node_id}"):
                                        # Clear stored credentials
                                        if "ssh_credentials" in st.session_state:
                                            st.session_state.ssh_credentials.pop(node_id, None)
                                        # Clear form fields
                                        st.session_state[f"username_prefix_{node_id}"] = ""
                                        st.session_state[f"ssh_password_{node_id}"] = ""
                                        st.rerun()
                                
                                error_status = {
                                    "connected": False,
                                    "username": full_username,
                                    "status": "🔴 Connection Failed",
                                    "error": message
                                }
                                manager.node_status[node_id] = error_status
                                node_status_manager.update_node_status(node_id, error_status)
                    else:
                        st.error("Please enter username, IP address, and SSH password")
                
                if launch_btn:
                    # Get IP input from session state (outside form)
                    current_ip = st.session_state.get(f"ip_input_{node_id}", node_info['host'])
                    if username_prefix and password and current_ip:
                        full_username = f"{username_prefix}@{current_ip}"
                        with st.spinner(f"Launching QuantTime on {node_id} ({current_ip})..."):
                            success, message = manager.launch_quanttime_on_node(node_id, full_username, password)
                            if success:
                                st.success(f"✅ {message}")
                                # Update node status
                                running_status = {
                                    "connected": True,
                                    "username": full_username,
                                    "quanttime_running": True,
                                    "status": "🟢 Connected & Running"
                                }
                                manager.node_status[node_id] = running_status
                                node_status_manager.update_node_status(node_id, running_status)
                                
                                # Update session state for sidebar sync
                                st.session_state.node_status = manager.node_status
                                
                                # Force sidebar refresh
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                                # Check if this is a connection failure or launch failure
                                if "timed out" in message.lower() or "connection" in message.lower():
                                    # Connection failed - update status accordingly
                                    failed_status = {
                                        "connected": False,
                                        "username": full_username,
                                        "quanttime_running": False,
                                        "status": "🔴 Connection Failed",
                                        "error": message
                                    }
                                    manager.node_status[node_id] = failed_status
                                    node_status_manager.update_node_status(node_id, failed_status)
                                else:
                                    # Connection succeeded but launch failed
                                    if node_id in manager.node_status:
                                        manager.node_status[node_id]["quanttime_running"] = False
                                        manager.node_status[node_id]["status"] = "🟡 Connected (Launch Failed)"
                                    else:
                                        # No previous connection status, create new entry
                                        launch_failed_status = {
                                            "connected": True,
                                            "username": full_username,
                                            "quanttime_running": False,
                                            "status": "🟡 Connected (Launch Failed)",
                                            "error": message
                                        }
                                        manager.node_status[node_id] = launch_failed_status
                                        node_status_manager.update_node_status(node_id, launch_failed_status)
                                # Update session state for sidebar sync
                                st.session_state.node_status = manager.node_status
                    else:
                        st.error("Please enter username, IP address, and SSH password")
    
    # Step 2: Configuration Summary
    st.markdown("### Step 2: Configuration Summary")
    
    # Display status table
    status_data = []
    for node_id, node_info in manager.nodes.items():
        status = manager.node_status.get(node_id, {"connected": False, "status": "🔴 Not Tested"})
        status_data.append({
            "Node": node_info["name"],
            "Type": node_info["type"],
            "Host": node_info["host"],
            "Status": status.get("status", "🔴 Not Tested"),
            "Username": status.get("username", "N/A"),
            "QuantTime": "✅ Running" if status.get("quanttime_running", False) else "❌ Not Running"
        })
    
    if status_data:
        df = pd.DataFrame(status_data)
        st.dataframe(df, use_container_width=True)
    
    # Step 3: Proceed to Dashboard
    st.markdown("### Step 3: Proceed to Dashboard")
    
    # Check if at least one node is connected
    connected_nodes = [node_id for node_id, status in manager.node_status.items() 
                      if status.get("connected", False)]
    
    if connected_nodes:
        st.success(f"✅ Configuration complete! {len(connected_nodes)} node(s) connected.")
        
        if st.button("🚀 Launch Dashboard", type="primary"):
            # Store configuration in session state
            st.session_state.initial_config_complete = True
            st.session_state.connected_nodes = connected_nodes
            st.session_state.node_status = manager.node_status
            
            # Reload the page to show main dashboard
            st.rerun()
    else:
        st.warning("⚠️ Please connect to at least one node before proceeding to the dashboard.")
    
    # Manual dashboard access
    st.markdown("---")
    st.markdown("**Manual Access:**")
    if st.button("🔧 Skip Configuration & Go to Dashboard"):
        st.session_state.initial_config_complete = True
        st.rerun()


if __name__ == "__main__":
    render_initial_config_page()
