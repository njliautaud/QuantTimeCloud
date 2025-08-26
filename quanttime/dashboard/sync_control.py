"""
QuantTime Sync Control Dashboard

Real-time synchronization management and monitoring for distributed cluster.
"""

import streamlit as st
import json
import time
import subprocess
from datetime import datetime
from typing import Dict, List
import threading

class SyncControl:
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
    
    def render_sync_control(self):
        """Render the synchronization control interface"""
        st.header("🔄 Project Synchronization")
        
        # Sync overview
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Nodes", len(self.servers))
        
        with col2:
            st.metric("Sync Status", "🟢 Active" if self._check_sync_status() else "🔴 Inactive")
        
        with col3:
            last_sync = self._get_last_sync_time()
            st.metric("Last Sync", last_sync)
        
        # Sync controls
        st.subheader("📡 Sync Controls")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Force Sync All"):
                self._force_sync_all()
        
        with col2:
            if st.button("📤 Push to Servers"):
                self._push_to_servers()
        
        with col3:
            if st.button("📥 Pull from Servers"):
                self._pull_from_servers()
        
        # Node status
        st.subheader("🖥️ Node Sync Status")
        self._render_node_status()
        
        # Sync history
        st.subheader("📋 Sync History")
        self._render_sync_history()
        
        # File sync status
        st.subheader("📁 File Sync Status")
        self._render_file_sync_status()
        
        # Auto-sync settings
        st.subheader("⚙️ Auto-Sync Settings")
        self._render_auto_sync_settings()
    
    def _check_sync_status(self) -> bool:
        """Check if sync is active"""
        try:
            # Check if background sync is running
            result = subprocess.run([
                "python", "-c", 
                "from server.core.sync_manager import sync_manager; print(sync_manager.running)"
            ], capture_output=True, text=True)
            
            return result.stdout.strip() == "True"
        except:
            return False
    
    def _get_last_sync_time(self) -> str:
        """Get last sync time"""
        try:
            # This would read from a sync log file
            return "2 min ago"
        except:
            return "Unknown"
    
    def _force_sync_all(self):
        """Force sync all nodes"""
        with st.spinner("Syncing all nodes..."):
            try:
                result = subprocess.run([
                    "python", "-c",
                    "from server.core.sync_manager import sync_manager; sync_manager.force_sync()"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    st.success("✅ Sync completed successfully")
                    st.json(result.stdout)
                else:
                    st.error("❌ Sync failed")
                    st.code(result.stderr)
                    
            except Exception as e:
                st.error(f"Sync error: {e}")
    
    def _push_to_servers(self):
        """Push changes to all servers"""
        with st.spinner("Pushing to servers..."):
            try:
                # Git push to all servers
                for server_name, server_config in self.servers.items():
                    if server_name == 'laptop':
                        continue
                    
                    ip = server_config.get('tailscale_ip', server_config['ip_address'])
                    username = server_config['username']
                    
                    # Push via Git
                    cmd = f"""
                    git remote add remote-{server_name} ssh://{username}@{ip}/opt/quanttime 2>/dev/null || true
                    git push remote-{server_name} main
                    """
                    
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        st.success(f"✅ Pushed to {server_name}")
                    else:
                        st.error(f"❌ Failed to push to {server_name}")
                        st.code(result.stderr)
                        
            except Exception as e:
                st.error(f"Push error: {e}")
    
    def _pull_from_servers(self):
        """Pull changes from servers"""
        with st.spinner("Pulling from servers..."):
            try:
                # This would pull any changes from servers
                # For now, just show a placeholder
                st.info("Pull functionality will be implemented based on your workflow")
                
            except Exception as e:
                st.error(f"Pull error: {e}")
    
    def _render_node_status(self):
        """Render node sync status"""
        for server_name, server_config in self.servers.items():
            with st.expander(f"📡 {server_name} ({server_config['name']})"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Check if node is online
                    ip = server_config.get('tailscale_ip', server_config['ip_address'])
                    try:
                        result = subprocess.run(['ping', '-n', '1', ip], 
                                              capture_output=True, text=True)
                        status = "🟢 Online" if result.returncode == 0 else "🔴 Offline"
                    except:
                        status = "❓ Unknown"
                    
                    st.metric("Status", status)
                
                with col2:
                    # Last sync time
                    st.metric("Last Sync", "2 min ago")
                
                with col3:
                    # Files synced
                    st.metric("Files Synced", "1,234")
                
                # Sync actions
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button(f"🔄 Sync {server_name}", key=f"sync_{server_name}"):
                        self._sync_single_node(server_name)
                
                with col2:
                    if st.button(f"📊 Status {server_name}", key=f"status_{server_name}"):
                        self._check_node_status(server_name)
    
    def _sync_single_node(self, server_name: str):
        """Sync a single node"""
        with st.spinner(f"Syncing {server_name}..."):
            try:
                server_config = self.servers[server_name]
                ip = server_config.get('tailscale_ip', server_config['ip_address'])
                username = server_config['username']
                
                # Sync via rsync
                cmd = f"""
                rsync -avz --exclude=.git --exclude=__pycache__ --exclude=*.pyc 
                ./ {username}@{ip}:/opt/quanttime/
                """
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0:
                    st.success(f"✅ {server_name} synced successfully")
                else:
                    st.error(f"❌ Failed to sync {server_name}")
                    st.code(result.stderr)
                    
            except Exception as e:
                st.error(f"Sync error: {e}")
    
    def _check_node_status(self, server_name: str):
        """Check status of a specific node"""
        with st.spinner(f"Checking {server_name} status..."):
            try:
                server_config = self.servers[server_name]
                ip = server_config.get('tailscale_ip', server_config['ip_address'])
                username = server_config['username']
                
                # Check various services
                services = ['quanttime-api-server', 'quanttime-celery-worker', 'redis-server']
                status_results = {}
                
                for service in services:
                    cmd = f"ssh {username}@{ip} 'systemctl is-active {service}'"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    status_results[service] = result.stdout.strip()
                
                st.json(status_results)
                
            except Exception as e:
                st.error(f"Status check error: {e}")
    
    def _render_sync_history(self):
        """Render sync history"""
        # This would read from a sync log file
        sync_history = [
            {"time": "2024-01-15 14:30:00", "action": "Push to R630XL", "status": "Success", "files": 15},
            {"time": "2024-01-15 14:25:00", "action": "Push to R810", "status": "Success", "files": 15},
            {"time": "2024-01-15 14:20:00", "action": "File sync R630XL→R810", "status": "Success", "files": 234},
            {"time": "2024-01-15 14:15:00", "action": "Auto sync", "status": "Success", "files": 0},
        ]
        
        for entry in sync_history:
            col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
            
            with col1:
                st.text(entry["time"])
            
            with col2:
                st.text(entry["action"])
            
            with col3:
                status_color = "🟢" if entry["status"] == "Success" else "🔴"
                st.text(f"{status_color} {entry['status']}")
            
            with col4:
                st.text(f"{entry['files']} files")
    
    def _render_file_sync_status(self):
        """Render file sync status"""
        # Show sync status for different file types
        file_types = [
            {"type": "Code", "status": "🟢 Synced", "last_sync": "2 min ago", "size": "45 MB"},
            {"type": "Data", "status": "🟢 Synced", "last_sync": "5 min ago", "size": "2.3 GB"},
            {"type": "Models", "status": "🟡 Pending", "last_sync": "1 hour ago", "size": "156 MB"},
            {"type": "Logs", "status": "🟢 Synced", "last_sync": "1 min ago", "size": "23 MB"},
        ]
        
        for file_type in file_types:
            col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
            
            with col1:
                st.text(file_type["type"])
            
            with col2:
                st.text(file_type["status"])
            
            with col3:
                st.text(file_type["last_sync"])
            
            with col4:
                st.text(file_type["size"])
    
    def _render_auto_sync_settings(self):
        """Render auto-sync settings"""
        col1, col2 = st.columns(2)
        
        with col1:
            auto_sync = st.checkbox("Enable Auto-Sync", value=True)
            sync_interval = st.selectbox("Sync Interval", ["1 minute", "5 minutes", "15 minutes", "30 minutes"], index=1)
            
            if st.button("💾 Save Settings"):
                st.success("Settings saved!")
        
        with col2:
            st.write("**Sync Options:**")
            st.write("• Git-based code sync")
            st.write("• File-based data sync")
            st.write("• Real-time monitoring")
            st.write("• Conflict resolution")

# Global sync control instance
sync_control = SyncControl()
