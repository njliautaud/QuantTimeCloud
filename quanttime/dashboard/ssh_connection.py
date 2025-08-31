"""
SSH Connection Interface for QuantTime Nodes
Simple interface to connect to nodes via Tailscale IPs and launch services
"""

import streamlit as st
import paramiko
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class SSHConnectionManager:
    """Manages SSH connections to QuantTime nodes"""
    
    def __init__(self):
        self.connections: Dict[str, paramiko.SSHClient] = {}
        self.node_status: Dict[str, Dict] = {}
        
        # Default Tailscale IPs for nodes
        self.default_nodes = {
            "laptop": {
                "name": "Development Laptop",
                "host": "localhost",
                "port": 22,
                "description": "Local development machine"
            },
            "r630xl": {
                "name": "R630XL Server", 
                "host": "jupiter",
                "port": 22,
                "description": "R630XL compute server"
            },
            "r810": {
                "name": "R810 Server",
                "host": "saturn", 
                "port": 22,
                "description": "R810 compute server"
            }
        }
    
    def test_connection(self, host: str, port: int, username: str, password: str) -> Tuple[bool, str]:
        """Test SSH connection to a node"""
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
                    ssh.close()
                    return True, "Connection successful (localhost)"
                except Exception as e:
                    logger.warning(f"Localhost connection failed: {e}")
            
            # Try password authentication
            ssh.connect(
                host,
                port=port,
                username=username,
                password=password,
                timeout=10
            )
            
            ssh.close()
            return True, "Connection successful"
            
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def connect_to_node(self, node_id: str, host: str, port: int, username: str, password: str) -> Tuple[bool, str]:
        """Connect to a specific node"""
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
                    
                    self.connections[node_id] = ssh
                    self.node_status[node_id] = {
                        "connected": True,
                        "connected_at": datetime.now().isoformat(),
                        "host": host,
                        "username": username,
                        "auth_method": "localhost"
                    }
                    
                    return True, f"Connected to {node_id} (localhost)"
                except Exception as e:
                    logger.warning(f"Localhost connection failed for {node_id}: {e}")
            
            # Try password authentication
            ssh.connect(
                host,
                port=port,
                username=username,
                password=password,
                timeout=10
            )
            
            self.connections[node_id] = ssh
            self.node_status[node_id] = {
                "connected": True,
                "connected_at": datetime.now().isoformat(),
                "host": host,
                "username": username,
                "auth_method": "password"
            }
            
            return True, f"Connected to {node_id}"
            
        except Exception as e:
            self.node_status[node_id] = {
                "connected": False,
                "error": str(e),
                "host": host,
                "username": username
            }
            return False, f"Failed to connect to {node_id}: {str(e)}"
    
    def execute_command(self, node_id: str, command: str) -> Tuple[bool, str, str]:
        """Execute a command on a connected node"""
        if node_id not in self.connections:
            return False, "", f"Not connected to {node_id}"
        
        try:
            ssh = self.connections[node_id]
            stdin, stdout, stderr = ssh.exec_command(command)
            
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            return True, output, error
            
        except Exception as e:
            return False, "", f"Command execution failed: {str(e)}"
    
    def launch_quanttime_on_node(self, node_id: str) -> Tuple[bool, str]:
        """Launch QuantTime services on a node"""
        commands = [
            "cd /opt/quanttime",
            "source venv/bin/activate",
            "python run.py"
        ]
        
        full_command = " && ".join(commands)
        success, output, error = self.execute_command(node_id, full_command)
        
        if success:
            return True, f"QuantTime launched on {node_id}"
        else:
            return False, f"Failed to launch QuantTime on {node_id}: {error}"
    
    def disconnect_node(self, node_id: str):
        """Disconnect from a node"""
        if node_id in self.connections:
            try:
                self.connections[node_id].close()
                del self.connections[node_id]
            except:
                pass
        
        if node_id in self.node_status:
            self.node_status[node_id]["connected"] = False
    
    def get_node_status(self, node_id: str) -> Dict:
        """Get status of a specific node"""
        status = self.node_status.get(node_id, {"connected": False})
        
        # Update session state for sidebar consistency
        if "node_status" not in st.session_state:
            st.session_state.node_status = {}
        
        st.session_state.node_status[node_id] = status
        return status


def render_ssh_connection_interface():
    """Render the SSH connection interface"""
    st.markdown("## 🔐 SSH Node Connection")
    st.markdown("Connect to QuantTime nodes using Tailscale IPs and launch services")
    
    # Initialize connection manager
    if "ssh_manager" not in st.session_state:
        st.session_state.ssh_manager = SSHConnectionManager()
    
    manager = st.session_state.ssh_manager
    
    # Node selection and connection
    st.markdown("### 📡 Connect to Nodes")
    
    # Create tabs for each node
    node_tabs = st.tabs(["🖥️ Laptop", "🖥️ R630XL", "🖥️ R810"])
    
    for i, (node_id, node_info) in enumerate(manager.default_nodes.items()):
        with node_tabs[i]:
            st.markdown(f"**{node_info['name']}**")
            st.markdown(f"*{node_info['description']}*")
            st.markdown(f"**Host:** `{node_info['host']}:{node_info['port']}`")
            
            # Check current connection status
            status = manager.get_node_status(node_id)
            
            if status.get("connected", False):
                st.success(f"✅ Connected as {status.get('username', 'unknown')}")
                
                # Launch QuantTime button
                if st.button(f"🚀 Launch QuantTime on {node_id}", key=f"launch_{node_id}"):
                    with st.spinner(f"Launching QuantTime on {node_id}..."):
                        success, message = manager.launch_quanttime_on_node(node_id)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                
                # Disconnect button
                if st.button(f"❌ Disconnect from {node_id}", key=f"disconnect_{node_id}"):
                    manager.disconnect_node(node_id)
                    st.rerun()
                
                # Execute custom command
                st.markdown("**Execute Custom Command:**")
                custom_cmd = st.text_input(f"Command for {node_id}:", key=f"cmd_{node_id}")
                if st.button(f"Execute on {node_id}", key=f"exec_{node_id}"):
                    if custom_cmd:
                        with st.spinner(f"Executing command on {node_id}..."):
                            success, output, error = manager.execute_command(node_id, custom_cmd)
                            if success:
                                st.success("Command executed successfully")
                                if output:
                                    st.code(output)
                                if error:
                                    st.warning(f"Stderr: {error}")
                            else:
                                st.error(f"Command failed: {error}")
            else:
                st.warning("❌ Not connected")
                
                # Connection form
                with st.form(key=f"connect_{node_id}"):
                    st.markdown("**Connection Details:**")
                    
                    # Use default host/port with unique keys
                    host = st.text_input("Host:", value=node_info["host"], key=f"ssh_host_{node_id}")
                    port = st.number_input("Port:", value=node_info["port"], key=f"ssh_port_{node_id}")
                    username = st.text_input("Username:", key=f"ssh_username_{node_id}")
                    password = st.text_input("Password:", type="password", key=f"ssh_password_{node_id}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        test_connection = st.form_submit_button("🔍 Test Connection")
                    with col2:
                        connect = st.form_submit_button("🔗 Connect")
                    
                    if test_connection:
                        if username and password:
                            with st.spinner("Testing connection..."):
                                success, message = manager.test_connection(host, port, username, password)
                                if success:
                                    st.success(message)
                                else:
                                    st.error(message)
                        else:
                            st.error("Please enter username and password")
                    
                    if connect:
                        if username and password:
                            with st.spinner(f"Connecting to {node_id}..."):
                                success, message = manager.connect_to_node(node_id, host, port, username, password)
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)
                        else:
                            st.error("Please enter username and password")
    
    # Global actions
    st.markdown("### 🌐 Global Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🚀 Launch All Connected Nodes"):
            connected_nodes = [node_id for node_id, status in manager.node_status.items() 
                             if status.get("connected", False)]
            
            if connected_nodes:
                with st.spinner("Launching QuantTime on all connected nodes..."):
                    for node_id in connected_nodes:
                        success, message = manager.launch_quanttime_on_node(node_id)
                        if success:
                            st.success(f"{node_id}: {message}")
                        else:
                            st.error(f"{node_id}: {message}")
            else:
                st.warning("No nodes connected")
    
    with col2:
        if st.button("📊 Refresh Status", key="refresh_status_global"):
            st.rerun()
    
    with col3:
        if st.button("❌ Disconnect All", key="disconnect_all_global"):
            for node_id in list(manager.connections.keys()):
                manager.disconnect_node(node_id)
            st.rerun()
    
    # Connection status summary
    st.markdown("### 📋 Connection Status")
    
    status_data = []
    for node_id, node_info in manager.default_nodes.items():
        status = manager.get_node_status(node_id)
        status_data.append({
            "Node": node_info["name"],
            "Host": node_info["host"],
            "Status": "🟢 Connected" if status.get("connected", False) else "🔴 Disconnected",
            "Username": status.get("username", "N/A"),
            "Connected At": status.get("connected_at", "N/A")
        })
    
    if status_data:
        import pandas as pd
        df = pd.DataFrame(status_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No connection status available")
