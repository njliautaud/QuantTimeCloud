"""
QuantTime Development Tools Dashboard

Real-time monitoring and troubleshooting for distributed development.
"""

import streamlit as st
import subprocess
import json
import time
from typing import Dict, List, Optional
from pathlib import Path

class DevTools:
    def __init__(self):
        self.config_path = "server/config/servers.json"
        self.servers = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load server configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Failed to load config: {e}")
            return {}
    
    def render_dev_tools(self):
        """Render the development tools interface"""
        st.header("🔧 Development Tools")
        
        # Server selection
        server_names = [name for name in self.servers.keys() if name != 'laptop']
        selected_server = st.selectbox("Select Server", server_names, index=0)
        
        # Quick actions
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("🚀 Deploy"):
                self.deploy_to_server(selected_server)
        
        with col2:
            if st.button("📊 Status"):
                self.show_server_status(selected_server)
        
        with col3:
            if st.button("📋 Logs"):
                self.show_server_logs(selected_server)
        
        with col4:
            if st.button("🔄 Restart"):
                self.restart_server_services(selected_server)
        
        # Real-time monitoring
        st.subheader("📈 Real-Time Monitoring")
        
        if st.button("Start Monitoring"):
            self.start_monitoring(selected_server)
        
        # Quick fixes
        st.subheader("🔧 Quick Fixes")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Fix Services"):
                self.quick_fix(selected_server, "services_down")
            
            if st.button("Fix Permissions"):
                self.quick_fix(selected_server, "permissions")
        
        with col2:
            if st.button("Fix Redis"):
                self.quick_fix(selected_server, "redis")
            
            if st.button("Fix PostgreSQL"):
                self.quick_fix(selected_server, "postgres")
        
        # File sync status
        st.subheader("🔄 File Sync Status")
        self.show_sync_status(selected_server)
    
    def deploy_to_server(self, server_name: str):
        """Deploy code to server"""
        with st.spinner(f"Deploying to {server_name}..."):
            try:
                result = subprocess.run([
                    "python", "scripts/deploy_to_servers.py", "deploy", server_name
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    st.success(f"✅ Deployed to {server_name}")
                    st.code(result.stdout)
                else:
                    st.error(f"❌ Deployment failed")
                    st.code(result.stderr)
                    
            except Exception as e:
                st.error(f"Deployment error: {e}")
    
    def show_server_status(self, server_name: str):
        """Show server status"""
        with st.spinner(f"Checking {server_name} status..."):
            try:
                result = subprocess.run([
                    "python", "scripts/deploy_to_servers.py", "status", server_name
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    try:
                        status = json.loads(result.stdout)
                        st.json(status)
                        
                        if status.get("status") == "online":
                            st.success("🟢 Server Online")
                        elif status.get("status") == "partial":
                            st.warning("🟡 Server Partially Online")
                        else:
                            st.error("🔴 Server Offline")
                            
                    except json.JSONDecodeError:
                        st.text(result.stdout)
                else:
                    st.error(f"Status check failed: {result.stderr}")
                    
            except Exception as e:
                st.error(f"Status check error: {e}")
    
    def show_server_logs(self, server_name: str):
        """Show server logs"""
        with st.spinner(f"Fetching {server_name} logs..."):
            try:
                result = subprocess.run([
                    "python", "scripts/deploy_to_servers.py", "logs", server_name
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    st.text_area("Server Logs", result.stdout, height=400)
                else:
                    st.error(f"Failed to get logs: {result.stderr}")
                    
            except Exception as e:
                st.error(f"Log fetch error: {e}")
    
    def restart_server_services(self, server_name: str):
        """Restart server services"""
        with st.spinner(f"Restarting {server_name} services..."):
            try:
                server = self.servers[server_name]
                ip = server.get('tailscale_ip') or server['ip_address']
                username = server['username']
                
                cmd = f"""
                ssh {username}@{ip} << 'EOF'
                cd /opt/quanttime
                bash server/scripts/start_all_services.sh
                echo "✅ Services restarted"
                EOF
                """
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0:
                    st.success(f"✅ {server_name} services restarted")
                    st.code(result.stdout)
                else:
                    st.error(f"❌ Service restart failed")
                    st.code(result.stderr)
                    
            except Exception as e:
                st.error(f"Restart error: {e}")
    
    def quick_fix(self, server_name: str, issue: str):
        """Apply quick fix"""
        with st.spinner(f"Applying {issue} fix to {server_name}..."):
            try:
                result = subprocess.run([
                    "python", "scripts/deploy_to_servers.py", "fix", server_name, issue
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    st.success(f"✅ {issue} fix applied to {server_name}")
                    st.code(result.stdout)
                else:
                    st.error(f"❌ Fix failed")
                    st.code(result.stderr)
                    
            except Exception as e:
                st.error(f"Fix error: {e}")
    
    def start_monitoring(self, server_name: str):
        """Start real-time monitoring"""
        st.info("Real-time monitoring started...")
        
        # Create a placeholder for live updates
        status_placeholder = st.empty()
        logs_placeholder = st.empty()
        
        # Monitor for 60 seconds
        for i in range(60):
            # Update status
            try:
                result = subprocess.run([
                    "python", "scripts/deploy_to_servers.py", "status", server_name
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    status = json.loads(result.stdout)
                    with status_placeholder.container():
                        st.metric("Status", status.get("status", "unknown"))
                        if "health" in status:
                            health = status["health"]
                            st.metric("CPU", f"{health.get('cpu_percent', 0):.1f}%")
                            st.metric("Memory", f"{health.get('memory_percent', 0):.1f}%")
                
                # Update logs (last 10 lines)
                result = subprocess.run([
                    "python", "scripts/deploy_to_servers.py", "logs", server_name, "all"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    with logs_placeholder.container():
                        st.text_area("Live Logs", result.stdout, height=200)
                        
            except Exception as e:
                st.error(f"Monitoring error: {e}")
            
            time.sleep(1)
    
    def show_sync_status(self, server_name: str):
        """Show file sync status"""
        try:
            server = self.servers[server_name]
            ip = server.get('tailscale_ip') or server['ip_address']
            username = server['username']
            
            # Check sync status via API
            cmd = f"ssh {username}@{ip} 'curl -s http://localhost:8000/api/v1/files/sync/status'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout:
                try:
                    sync_status = json.loads(result.stdout)
                    st.json(sync_status)
                except json.JSONDecodeError:
                    st.text("Sync status: " + result.stdout)
            else:
                st.warning("Sync status not available")
                
        except Exception as e:
            st.error(f"Sync status error: {e}")

# Global instance
dev_tools = DevTools()
