"""
Syncthing Manager for Multi-Node Project Synchronization
Handles real-time file synchronization, sync queue management, and version control
"""

import os
import json
import time
import subprocess
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import requests
import hashlib
import shutil
from enum import Enum

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"
    CONFLICT = "conflict"
    UPTODATE = "uptodate"


@dataclass
class SyncNode:
    """Represents a Syncthing node"""
    node_id: str
    name: str
    address: str
    port: int = 22000
    api_port: int = 8384
    api_key: Optional[str] = None
    is_master: bool = False
    status: SyncStatus = SyncStatus.IDLE
    last_seen: Optional[datetime] = None
    version: Optional[str] = None
    sync_progress: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class SyncFolder:
    """Represents a Syncthing folder"""
    folder_id: str
    label: str
    path: str
    type: str = "sendreceive"  # sendreceive, sendonly, receiveonly
    ignore_perms: bool = False
    auto_normalize: bool = True
    min_disk_free: int = 1
    versioning: Dict[str, Any] = field(default_factory=dict)
    devices: List[str] = field(default_factory=list)
    status: SyncStatus = SyncStatus.IDLE
    last_scan: Optional[datetime] = None
    last_sync: Optional[datetime] = None
    sync_progress: float = 0.0
    pending_files: int = 0
    errors: List[str] = field(default_factory=list)


class SyncthingManager:
    """Manages Syncthing synchronization across all nodes"""
    
    def __init__(self, config_path: str = "config/syncthing_config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.nodes: Dict[str, SyncNode] = {}
        self.folders: Dict[str, SyncFolder] = {}
        self.sync_queue: List[str] = []
        self.sync_in_progress = False
        self.sync_lock = threading.Lock()
        self.monitoring_thread = None
        self.stop_monitoring = False
        
        # Initialize nodes and folders
        self._initialize_nodes()
        self._initialize_folders()
        
        # Start monitoring
        self.start_monitoring()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load Syncthing configuration"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            config = {
                "master_node": {
                    "node_id": "laptop",
                    "name": "Development Laptop",
                    "address": "localhost",
                    "port": 22000,
                    "api_port": 8384,
                    "api_key": None,
                    "is_master": True
                },
                "nodes": [
                    {
                        "node_id": "r630xl",
                        "name": "R630XL Server",
                        "address": "laptop",
                        "port": 22000,
                        "api_port": 8384,
                        "api_key": None,
                        "is_master": False
                    },
                    {
                        "node_id": "r810",
                        "name": "R810 Server",
                        "address": "jupiter",
                        "port": 22000,
                        "api_port": 8384,
                        "api_key": None,
                        "is_master": False
                    }
                ],
                "folders": [
                    {
                        "folder_id": "quanttime-project",
                        "label": "QuantTime Project",
                        "path": "/opt/quanttime",
                        "type": "sendreceive",
                        "devices": ["laptop", "r630xl", "r810"]
                    }
                ],
                "sync_settings": {
                    "max_concurrent_syncs": 1,
                    "sync_timeout": 300,
                    "retry_attempts": 3,
                    "version_control": True,
                    "backup_enabled": True
                }
            }
            
            # Save default config
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            return config
    
    def _initialize_nodes(self):
        """Initialize Syncthing nodes"""
        # Add master node
        master_config = self.config["master_node"]
        self.nodes[master_config["node_id"]] = SyncNode(**master_config)
        
        # Add other nodes
        for node_config in self.config["nodes"]:
            self.nodes[node_config["node_id"]] = SyncNode(**node_config)
    
    def _initialize_folders(self):
        """Initialize Syncthing folders"""
        for folder_config in self.config["folders"]:
            self.folders[folder_config["folder_id"]] = SyncFolder(**folder_config)
    
    def start_monitoring(self):
        """Start monitoring thread for sync status"""
        if self.monitoring_thread is None:
            self.monitoring_thread = threading.Thread(target=self._monitor_sync_status, daemon=True)
            self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring thread"""
        self.stop_monitoring = True
        if self.monitoring_thread:
            self.monitoring_thread.join()
    
    def _monitor_sync_status(self):
        """Monitor sync status across all nodes"""
        while not self.stop_monitoring:
            try:
                # Update sync status for all nodes
                for node_id, node in self.nodes.items():
                    if not node.is_master:
                        self._update_node_status(node)
                
                # Update folder status
                for folder_id, folder in self.folders.items():
                    self._update_folder_status(folder)
                
                # Check sync queue
                self._process_sync_queue()
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in sync monitoring: {e}")
                time.sleep(10)
    
    def _update_node_status(self, node: SyncNode):
        """Update status of a specific node"""
        try:
            # Try to connect to node's Syncthing API
            api_url = f"http://{node.address}:{node.api_port}/rest/system/status"
            response = requests.get(api_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                node.status = SyncStatus.UPTODATE
                node.last_seen = datetime.now()
                node.version = data.get("version", "unknown")
                node.errors = []
            else:
                node.status = SyncStatus.ERROR
                node.errors = [f"API returned status {response.status_code}"]
                
        except requests.exceptions.RequestException as e:
            node.status = SyncStatus.ERROR
            node.errors = [f"Connection failed: {str(e)}"]
        except Exception as e:
            node.status = SyncStatus.ERROR
            node.errors = [f"Unexpected error: {str(e)}"]
    
    def _update_folder_status(self, folder: SyncFolder):
        """Update status of a specific folder"""
        try:
            # Get folder status from master node
            master_node = self._get_master_node()
            if not master_node:
                return
            
            api_url = f"http://{master_node.address}:{master_node.api_port}/rest/db/status"
            response = requests.get(api_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                folder_status = data.get(folder.folder_id, {})
                
                # Update folder status
                if folder_status.get("inSync"):
                    folder.status = SyncStatus.UPTODATE
                elif folder_status.get("scanning"):
                    folder.status = SyncStatus.SYNCING
                else:
                    folder.status = SyncStatus.IDLE
                
                folder.last_scan = datetime.now()
                folder.pending_files = folder_status.get("pendingFiles", 0)
                folder.errors = folder_status.get("errors", [])
                
        except Exception as e:
            folder.status = SyncStatus.ERROR
            folder.errors = [f"Status update failed: {str(e)}"]
    
    def _get_master_node(self) -> Optional[SyncNode]:
        """Get the master node"""
        for node in self.nodes.values():
            if node.is_master:
                return node
        return None
    
    def _process_sync_queue(self):
        """Process sync queue"""
        with self.sync_lock:
            if self.sync_in_progress or not self.sync_queue:
                return
            
            # Check if any sync is in progress
            for folder in self.folders.values():
                if folder.status == SyncStatus.SYNCING:
                    self.sync_in_progress = True
                    return
            
            # Start next sync if queue is not empty
            if self.sync_queue:
                folder_id = self.sync_queue.pop(0)
                self._start_sync(folder_id)
    
    def _start_sync(self, folder_id: str):
        """Start synchronization for a folder"""
        try:
            folder = self.folders.get(folder_id)
            if not folder:
                logger.error(f"Folder {folder_id} not found")
                return
            
            folder.status = SyncStatus.SYNCING
            folder.last_sync = datetime.now()
            self.sync_in_progress = True
            
            logger.info(f"Started sync for folder: {folder_id}")
            
            # Trigger sync via Syncthing API
            master_node = self._get_master_node()
            if master_node:
                api_url = f"http://{master_node.address}:{master_node.api_port}/rest/db/scan"
                data = {"folder": folder_id}
                response = requests.post(api_url, json=data, timeout=10)
                
                if response.status_code != 200:
                    folder.status = SyncStatus.ERROR
                    folder.errors = [f"Sync failed: {response.status_code}"]
                    logger.error(f"Sync failed for {folder_id}: {response.status_code}")
            
        except Exception as e:
            folder.status = SyncStatus.ERROR
            folder.errors = [f"Sync error: {str(e)}"]
            logger.error(f"Error starting sync for {folder_id}: {e}")
        finally:
            self.sync_in_progress = False
    
    def add_to_sync_queue(self, folder_id: str):
        """Add folder to sync queue"""
        with self.sync_lock:
            if folder_id not in self.sync_queue:
                self.sync_queue.append(folder_id)
                logger.info(f"Added {folder_id} to sync queue")
    
    def is_sync_in_progress(self) -> bool:
        """Check if any sync is in progress"""
        with self.sync_lock:
            return self.sync_in_progress or any(
                folder.status == SyncStatus.SYNCING 
                for folder in self.folders.values()
            )
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get comprehensive sync status"""
        return {
            "nodes": {
                node_id: {
                    "name": node.name,
                    "status": node.status.value,
                    "last_seen": node.last_seen.isoformat() if node.last_seen else None,
                    "version": node.version,
                    "errors": node.errors
                }
                for node_id, node in self.nodes.items()
            },
            "folders": {
                folder_id: {
                    "label": folder.label,
                    "status": folder.status.value,
                    "sync_progress": folder.sync_progress,
                    "pending_files": folder.pending_files,
                    "last_sync": folder.last_sync.isoformat() if folder.last_sync else None,
                    "errors": folder.errors
                }
                for folder_id, folder in self.folders.items()
            },
            "queue": self.sync_queue.copy(),
            "sync_in_progress": self.is_sync_in_progress()
        }
    
    def get_version_info(self) -> Dict[str, str]:
        """Get version information for all nodes"""
        versions = {}
        for node_id, node in self.nodes.items():
            versions[node_id] = node.version or "unknown"
        return versions
    
    def check_version_consistency(self) -> bool:
        """Check if all nodes have the same version"""
        versions = self.get_version_info()
        if not versions:
            return False
        
        master_version = versions.get("laptop")
        if not master_version:
            return False
        
        return all(v == master_version for v in versions.values())
    
    def force_sync(self, folder_id: str = None):
        """Force synchronization for a folder or all folders"""
        if folder_id:
            folders_to_sync = [folder_id]
        else:
            folders_to_sync = list(self.folders.keys())
        
        for fid in folders_to_sync:
            self.add_to_sync_queue(fid)
        
        logger.info(f"Force sync initiated for folders: {folders_to_sync}")
    
    def resolve_conflicts(self, folder_id: str):
        """Resolve conflicts in a folder"""
        try:
            folder = self.folders.get(folder_id)
            if not folder:
                logger.error(f"Folder {folder_id} not found")
                return
            
            # Get conflicts from Syncthing API
            master_node = self._get_master_node()
            if not master_node:
                return
            
            api_url = f"http://{master_node.address}:{master_node.api_port}/rest/db/ignores"
            response = requests.get(api_url, timeout=5)
            
            if response.status_code == 200:
                conflicts = response.json().get(folder_id, [])
                logger.info(f"Found {len(conflicts)} conflicts in {folder_id}")
                
                # Auto-resolve conflicts (use master version)
                for conflict in conflicts:
                    self._resolve_conflict(folder_id, conflict)
            
        except Exception as e:
            logger.error(f"Error resolving conflicts for {folder_id}: {e}")
    
    def _resolve_conflict(self, folder_id: str, conflict_file: str):
        """Resolve a specific conflict"""
        try:
            # Use master version (laptop)
            master_node = self._get_master_node()
            if not master_node:
                return
            
            api_url = f"http://{master_node.address}:{master_node.api_port}/rest/db/override"
            data = {
                "folder": folder_id,
                "device": "laptop",
                "name": conflict_file
            }
            
            response = requests.post(api_url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info(f"Resolved conflict: {conflict_file}")
            else:
                logger.error(f"Failed to resolve conflict: {conflict_file}")
                
        except Exception as e:
            logger.error(f"Error resolving conflict {conflict_file}: {e}")
    
    def get_sync_progress(self) -> Dict[str, float]:
        """Get sync progress for all folders"""
        return {
            folder_id: folder.sync_progress
            for folder_id, folder in self.folders.items()
        }
    
    def wait_for_sync_completion(self, timeout: int = 300) -> bool:
        """Wait for sync completion with timeout"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if not self.is_sync_in_progress():
                return True
            time.sleep(1)
        
        return False
    
    def backup_project(self, backup_path: str = None):
        """Create a backup of the project"""
        if not backup_path:
            backup_path = f"backups/quanttime_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            backup_path = Path(backup_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get project path from master node
            master_node = self._get_master_node()
            if not master_node:
                logger.error("Master node not found for backup")
                return False
            
            project_path = Path("/opt/quanttime")
            if not project_path.exists():
                logger.error(f"Project path not found: {project_path}")
                return False
            
            # Create backup
            shutil.copytree(project_path, backup_path, ignore=shutil.ignore_patterns(
                '*.pyc', '__pycache__', '.git', 'node_modules', '*.log'
            ))
            
            logger.info(f"Backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
    
    def restore_project(self, backup_path: str):
        """Restore project from backup"""
        try:
            backup_path = Path(backup_path)
            if not backup_path.exists():
                logger.error(f"Backup path not found: {backup_path}")
                return False
            
            project_path = Path("/opt/quanttime")
            
            # Stop sync temporarily
            self.stop_monitoring()
            
            # Restore from backup
            if project_path.exists():
                shutil.rmtree(project_path)
            
            shutil.copytree(backup_path, project_path)
            
            # Restart monitoring
            self.start_monitoring()
            
            logger.info(f"Project restored from: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False


# Global Syncthing manager instance
syncthing_manager = None


def get_syncthing_manager() -> SyncthingManager:
    """Get global Syncthing manager instance"""
    global syncthing_manager
    if syncthing_manager is None:
        syncthing_manager = SyncthingManager()
    return syncthing_manager


def init_syncthing_manager(config_path: str = None) -> SyncthingManager:
    """Initialize Syncthing manager with custom config"""
    global syncthing_manager
    if config_path:
        syncthing_manager = SyncthingManager(config_path)
    else:
        syncthing_manager = SyncthingManager()
    return syncthing_manager
