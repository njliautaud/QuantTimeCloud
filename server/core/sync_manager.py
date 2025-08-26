"""
QuantTime Distributed Sync Manager

Handles synchronization between laptop (control center) and servers.
Supports both Git-based and file-based synchronization.
"""

import os
import time
import json
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import threading
import queue

@dataclass
class SyncStatus:
    """Sync status for a node"""
    node_name: str
    last_sync: datetime
    sync_type: str  # 'git', 'file', 'both'
    status: str  # 'synced', 'pending', 'error'
    files_changed: int
    error_message: Optional[str] = None

class GitSyncManager:
    """Handles Git-based synchronization"""
    
    def __init__(self, repo_path: str = "/opt/quanttime"):
        self.repo_path = Path(repo_path)
        self.logger = logging.getLogger(__name__)
        
    def setup_git_remotes(self, servers: Dict) -> bool:
        """Setup Git remotes for all servers"""
        try:
            # Add remotes for each server
            for server_name, server_config in servers.items():
                if server_name == 'laptop':
                    continue
                    
                remote_name = f"remote-{server_name}"
                remote_url = f"ssh://{server_config['username']}@{server_config.get('tailscale_ip', server_config['ip_address'])}/opt/quanttime"
                
                # Remove existing remote if it exists
                subprocess.run(['git', 'remote', 'remove', remote_name], 
                             cwd=self.repo_path, capture_output=True)
                
                # Add new remote
                result = subprocess.run(['git', 'remote', 'add', remote_name, remote_url],
                                      cwd=self.repo_path, capture_output=True, text=True)
                
                if result.returncode != 0:
                    self.logger.error(f"Failed to add remote {remote_name}: {result.stderr}")
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up Git remotes: {e}")
            return False
    
    def push_to_servers(self, servers: Dict) -> Dict[str, SyncStatus]:
        """Push changes to all servers"""
        results = {}
        
        for server_name, server_config in servers.items():
            if server_name == 'laptop':
                continue
                
            try:
                remote_name = f"remote-{server_name}"
                
                # Push to server
                result = subprocess.run(['git', 'push', remote_name, 'main'],
                                      cwd=self.repo_path, capture_output=True, text=True)
                
                status = SyncStatus(
                    node_name=server_name,
                    last_sync=datetime.now(),
                    sync_type='git',
                    status='synced' if result.returncode == 0 else 'error',
                    files_changed=0,
                    error_message=result.stderr if result.returncode != 0 else None
                )
                
                results[server_name] = status
                
            except Exception as e:
                results[server_name] = SyncStatus(
                    node_name=server_name,
                    last_sync=datetime.now(),
                    sync_type='git',
                    status='error',
                    files_changed=0,
                    error_message=str(e)
                )
                
        return results
    
    def pull_from_laptop(self) -> SyncStatus:
        """Pull changes from laptop (run on servers)"""
        try:
            # Fetch from laptop remote
            result = subprocess.run(['git', 'fetch', 'origin'],
                                  cwd=self.repo_path, capture_output=True, text=True)
            
            if result.returncode != 0:
                return SyncStatus(
                    node_name='laptop',
                    last_sync=datetime.now(),
                    sync_type='git',
                    status='error',
                    files_changed=0,
                    error_message=result.stderr
                )
            
            # Check if there are changes to pull
            result = subprocess.run(['git', 'rev-list', 'HEAD..origin/main', '--count'],
                                  cwd=self.repo_path, capture_output=True, text=True)
            
            commits_behind = int(result.stdout.strip()) if result.returncode == 0 else 0
            
            if commits_behind > 0:
                # Pull changes
                result = subprocess.run(['git', 'pull', 'origin', 'main'],
                                      cwd=self.repo_path, capture_output=True, text=True)
                
                return SyncStatus(
                    node_name='laptop',
                    last_sync=datetime.now(),
                    sync_type='git',
                    status='synced' if result.returncode == 0 else 'error',
                    files_changed=commits_behind,
                    error_message=result.stderr if result.returncode != 0 else None
                )
            else:
                return SyncStatus(
                    node_name='laptop',
                    last_sync=datetime.now(),
                    sync_type='git',
                    status='synced',
                    files_changed=0
                )
                
        except Exception as e:
            return SyncStatus(
                node_name='laptop',
                last_sync=datetime.now(),
                sync_type='git',
                status='error',
                files_changed=0,
                error_message=str(e)
            )

class FileSyncManager:
    """Handles file-based synchronization for large files"""
    
    def __init__(self, base_path: str = "/opt/quanttime"):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
        
    def sync_data_files(self, source_server: str, target_server: str, 
                       source_config: Dict, target_config: Dict) -> SyncStatus:
        """Sync data files between servers"""
        try:
            source_ip = source_config.get('tailscale_ip', source_config['ip_address'])
            target_ip = target_config.get('tailscale_ip', target_config['ip_address'])
            
            # Sync data directories
            data_dirs = ['data', 'models', 'logs', 'backtests']
            files_changed = 0
            
            for data_dir in data_dirs:
                source_path = f"{source_config['username']}@{source_ip}:/opt/quanttime/{data_dir}/"
                target_path = f"{target_config['username']}@{target_ip}:/opt/quanttime/{data_dir}/"
                
                # Use rsync for efficient file transfer
                cmd = [
                    'rsync', '-avz', '--delete', '--exclude=*.tmp',
                    source_path, target_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    # Count files transferred
                    lines = result.stdout.split('\n')
                    files_changed += len([l for l in lines if l.strip() and not l.startswith('sending')])
            
            return SyncStatus(
                node_name=target_server,
                last_sync=datetime.now(),
                sync_type='file',
                status='synced',
                files_changed=files_changed
            )
            
        except Exception as e:
            return SyncStatus(
                node_name=target_server,
                last_sync=datetime.now(),
                sync_type='file',
                status='error',
                files_changed=0,
                error_message=str(e)
            )

class SyncManager:
    """Main synchronization manager"""
    
    def __init__(self, config_path: str = "server/config/servers.json"):
        self.config_path = config_path
        self.servers = self._load_config()
        self.git_sync = GitSyncManager()
        self.file_sync = FileSyncManager()
        self.logger = logging.getLogger(__name__)
        
        # Sync queue for background processing
        self.sync_queue = queue.Queue()
        self.sync_thread = None
        self.running = False
        
    def _load_config(self) -> Dict:
        """Load server configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
    
    def start_background_sync(self):
        """Start background synchronization"""
        if self.sync_thread and self.sync_thread.is_alive():
            return
            
        self.running = True
        self.sync_thread = threading.Thread(target=self._background_sync_worker)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        self.logger.info("Background sync started")
    
    def stop_background_sync(self):
        """Stop background synchronization"""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join()
        self.logger.info("Background sync stopped")
    
    def _background_sync_worker(self):
        """Background sync worker thread"""
        while self.running:
            try:
                # Sync every 5 minutes
                self.sync_all()
                time.sleep(300)  # 5 minutes
            except Exception as e:
                self.logger.error(f"Background sync error: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def sync_all(self) -> Dict[str, SyncStatus]:
        """Sync all nodes"""
        results = {}
        
        # Git-based sync (laptop to servers)
        git_results = self.git_sync.push_to_servers(self.servers)
        results.update(git_results)
        
        # File-based sync between servers
        server_names = [name for name in self.servers.keys() if name != 'laptop']
        
        if len(server_names) >= 2:
            # Sync between servers
            for i in range(len(server_names) - 1):
                source = server_names[i]
                target = server_names[i + 1]
                
                file_result = self.file_sync.sync_data_files(
                    source, target,
                    self.servers[source], self.servers[target]
                )
                results[f"{source}_to_{target}"] = file_result
        
        return results
    
    def force_sync(self) -> Dict[str, SyncStatus]:
        """Force immediate sync"""
        return self.sync_all()
    
    def get_sync_status(self) -> Dict[str, SyncStatus]:
        """Get current sync status"""
        # This would check the actual status of each node
        # For now, return the last known status
        return {}
    
    def setup_initial_sync(self) -> bool:
        """Setup initial synchronization"""
        try:
            # Setup Git remotes
            if not self.git_sync.setup_git_remotes(self.servers):
                return False
            
            # Create sync directories
            for server_name, server_config in self.servers.items():
                if server_name == 'laptop':
                    continue
                    
                # Ensure sync directories exist
                sync_dirs = ['data', 'models', 'logs', 'backtests']
                for sync_dir in sync_dirs:
                    dir_path = Path(f"/opt/quanttime/{sync_dir}")
                    dir_path.mkdir(parents=True, exist_ok=True)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup initial sync: {e}")
            return False

# Global sync manager instance
sync_manager = SyncManager()
