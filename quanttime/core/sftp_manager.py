"""
SFTP Manager for Large File Synchronization
Handles automated sync of large files (models, data, backtest results) between nodes
"""

import os
import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import paramiko
import threading
from concurrent.futures import ThreadPoolExecutor
import ray

logger = logging.getLogger(__name__)


@dataclass
class SFTPNode:
    """Represents an SFTP node"""
    node_id: str
    name: str
    host: str
    port: int = 22
    username: str = "jupiter"
    key_path: Optional[str] = None
    password: Optional[str] = None
    large_file_dirs: List[str] = field(default_factory=list)
    status: str = "offline"
    last_sync: Optional[datetime] = None
    sync_errors: List[str] = field(default_factory=list)


@dataclass
class FileInfo:
    """File information for sync tracking"""
    path: str
    size: int
    modified_time: datetime
    checksum: str
    node_id: str


@dataclass
class SyncTask:
    """Represents a sync task"""
    task_id: str
    source_node: str
    target_node: str
    file_paths: List[str]
    priority: str = "normal"
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    errors: List[str] = field(default_factory=list)


class SFTPManager:
    """Manages SFTP connections and large file synchronization"""
    
    def __init__(self, config_path: str = "config/sftp_config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.nodes: Dict[str, SFTPNode] = {}
        self.sync_tasks: Dict[str, SyncTask] = {}
        self.file_registry: Dict[str, FileInfo] = {}
        self.sync_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Initialize nodes
        self._initialize_nodes()
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(target=self._monitor_sync, daemon=True)
        self.monitoring_thread.start()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load SFTP configuration"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            config = {
                "nodes": {
                    "laptop": {
                        "name": "Development Laptop",
                        "host": "localhost",
                        "port": 22,
                        "username": "jupiter",
                        "large_file_dirs": [
                            "data/es_futures",
                            "data/processed", 
                            "models",
                            "backtest/results",
                            "logs"
                        ]
                    },
                    "r630xl": {
                        "name": "R630XL Server",
                        "host": "jupiter",
                        "port": 22,
                        "username": "jupiter",
                        "large_file_dirs": [
                            "/opt/quanttime/data/es_futures",
                            "/opt/quanttime/data/processed",
                            "/opt/quanttime/models",
                            "/opt/quanttime/backtest/results",
                            "/opt/quanttime/logs"
                        ]
                    },
                    "r810": {
                        "name": "R810 Server", 
                        "host": "saturn",
                        "port": 22,
                        "username": "jupiter",
                        "large_file_dirs": [
                            "/opt/quanttime/data/es_futures",
                            "/opt/quanttime/data/processed",
                            "/opt/quanttime/models",
                            "/opt/quanttime/backtest/results",
                            "/opt/quanttime/logs"
                        ]
                    }
                },
                "sync_settings": {
                    "max_file_size_mb": 100,
                    "sync_interval_minutes": 5,
                    "retry_attempts": 3,
                    "chunk_size_mb": 10,
                    "parallel_transfers": 4
                }
            }
            
            # Save default config
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            return config
    
    def _initialize_nodes(self):
        """Initialize SFTP nodes"""
        for node_id, node_config in self.config["nodes"].items():
            node = SFTPNode(node_id=node_id, **node_config)
            self.nodes[node_id] = node
    
    def _get_ssh_connection(self, node: SFTPNode) -> Optional[paramiko.SSHClient]:
        """Get SSH connection to node"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if node.key_path and os.path.exists(node.key_path):
                ssh.connect(
                    node.host, 
                    port=node.port,
                    username=node.username,
                    key_filename=node.key_path
                )
            else:
                ssh.connect(
                    node.host,
                    port=node.port, 
                    username=node.username,
                    password=node.password
                )
            
            return ssh
        except Exception as e:
            logger.error(f"Failed to connect to {node.name}: {e}")
            node.status = "offline"
            node.sync_errors.append(str(e))
            return None
    
    def _calculate_file_checksum(self, file_path: str, node: SFTPNode) -> Optional[str]:
        """Calculate file checksum"""
        try:
            ssh = self._get_ssh_connection(node)
            if not ssh:
                return None
            
            # Use md5sum for checksum calculation
            stdin, stdout, stderr = ssh.exec_command(f"md5sum '{file_path}'")
            result = stdout.read().decode().strip()
            ssh.close()
            
            if result:
                return result.split()[0]
            return None
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return None
    
    def _get_file_info(self, file_path: str, node: SFTPNode) -> Optional[FileInfo]:
        """Get file information"""
        try:
            ssh = self._get_ssh_connection(node)
            if not ssh:
                return None
            
            # Get file stats
            stdin, stdout, stderr = ssh.exec_command(f"stat -c '%s %Y' '{file_path}'")
            result = stdout.read().decode().strip()
            ssh.close()
            
            if result:
                size, mtime = result.split()
                modified_time = datetime.fromtimestamp(int(mtime))
                checksum = self._calculate_file_checksum(file_path, node)
                
                return FileInfo(
                    path=file_path,
                    size=int(size),
                    modified_time=modified_time,
                    checksum=checksum or "",
                    node_id=node.node_id
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            return None
    
    def _scan_large_files(self, node: SFTPNode) -> List[FileInfo]:
        """Scan for large files on node"""
        large_files = []
        
        try:
            ssh = self._get_ssh_connection(node)
            if not ssh:
                return large_files
            
            max_size = self.config["sync_settings"]["max_file_size_mb"] * 1024 * 1024
            
            for directory in node.large_file_dirs:
                # Find files larger than threshold
                stdin, stdout, stderr = ssh.exec_command(
                    f"find '{directory}' -type f -size +{max_size}c 2>/dev/null"
                )
                files = stdout.read().decode().strip().split('\n')
                
                for file_path in files:
                    if file_path:
                        file_info = self._get_file_info(file_path, node)
                        if file_info:
                            large_files.append(file_info)
            
            ssh.close()
            return large_files
        except Exception as e:
            logger.error(f"Failed to scan large files on {node.name}: {e}")
            return large_files
    
    def _detect_sync_discrepancies(self) -> Dict[str, List[Dict[str, Any]]]:
        """Detect discrepancies between nodes"""
        discrepancies = {}
        
        # Scan all nodes
        node_files = {}
        for node_id, node in self.nodes.items():
            node_files[node_id] = self._scan_large_files(node)
        
        # Compare files between nodes
        for node_id, files in node_files.items():
            discrepancies[node_id] = []
            
            for file_info in files:
                file_key = f"{file_info.path}"
                
                # Check if file exists on other nodes
                for other_node_id, other_files in node_files.items():
                    if other_node_id == node_id:
                        continue
                    
                    other_file = next((f for f in other_files if f.path == file_info.path), None)
                    
                    if not other_file:
                        # File missing on other node
                        discrepancies[node_id].append({
                            "type": "missing",
                            "file_path": file_info.path,
                            "source_node": node_id,
                            "target_node": other_node_id,
                            "file_info": file_info
                        })
                    elif other_file.checksum != file_info.checksum:
                        # File checksum mismatch
                        discrepancies[node_id].append({
                            "type": "checksum_mismatch",
                            "file_path": file_info.path,
                            "source_node": node_id,
                            "target_node": other_node_id,
                            "source_file": file_info,
                            "target_file": other_file
                        })
        
        return discrepancies
    
    def _sync_file(self, source_node: SFTPNode, target_node: SFTPNode, file_path: str) -> bool:
        """Sync a single file between nodes"""
        try:
            source_ssh = self._get_ssh_connection(source_node)
            target_ssh = self._get_ssh_connection(target_node)
            
            if not source_ssh or not target_ssh:
                return False
            
            # Create target directory if it doesn't exist
            target_dir = os.path.dirname(file_path)
            target_ssh.exec_command(f"mkdir -p '{target_dir}'")
            
            # Use scp for file transfer
            scp_command = f"scp -o StrictHostKeyChecking=no '{file_path}' {target_node.username}@{target_node.host}:{file_path}"
            stdin, stdout, stderr = source_ssh.exec_command(scp_command)
            
            # Wait for transfer to complete
            exit_status = stdout.channel.recv_exit_status()
            
            source_ssh.close()
            target_ssh.close()
            
            return exit_status == 0
        except Exception as e:
            logger.error(f"Failed to sync file {file_path}: {e}")
            return False
    
    def _execute_sync_task(self, task: SyncTask):
        """Execute a sync task"""
        try:
            task.status = "running"
            task.started_at = datetime.now()
            
            source_node = self.nodes[task.source_node]
            target_node = self.nodes[task.target_node]
            
            total_files = len(task.file_paths)
            completed_files = 0
            
            for file_path in task.file_paths:
                if self._sync_file(source_node, target_node, file_path):
                    completed_files += 1
                else:
                    task.errors.append(f"Failed to sync {file_path}")
                
                task.progress = (completed_files / total_files) * 100
            
            task.status = "completed" if not task.errors else "failed"
            task.completed_at = datetime.now()
            
            # Update node sync time
            target_node.last_sync = datetime.now()
            
        except Exception as e:
            task.status = "failed"
            task.errors.append(str(e))
            task.completed_at = datetime.now()
    
    def _monitor_sync(self):
        """Monitor and execute sync tasks"""
        while True:
            try:
                with self.sync_lock:
                    # Check for pending tasks
                    for task_id, task in self.sync_tasks.items():
                        if task.status == "pending":
                            self.executor.submit(self._execute_sync_task, task)
                
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Error in sync monitoring: {e}")
                time.sleep(30)
    
    def create_sync_task(self, source_node: str, target_node: str, file_paths: List[str], 
                        priority: str = "normal") -> str:
        """Create a new sync task"""
        task_id = f"sync_{int(time.time())}"
        
        task = SyncTask(
            task_id=task_id,
            source_node=source_node,
            target_node=target_node,
            file_paths=file_paths,
            priority=priority
        )
        
        with self.sync_lock:
            self.sync_tasks[task_id] = task
        
        logger.info(f"Created sync task {task_id}: {source_node} -> {target_node}")
        return task_id
    
    def auto_sync_large_files(self):
        """Automatically sync large files based on discrepancies"""
        discrepancies = self._detect_sync_discrepancies()
        
        for node_id, node_discrepancies in discrepancies.items():
            for discrepancy in node_discrepancies:
                if discrepancy["type"] == "missing":
                    # Create sync task for missing file
                    self.create_sync_task(
                        source_node=discrepancy["source_node"],
                        target_node=discrepancy["target_node"],
                        file_paths=[discrepancy["file_path"]],
                        priority="high"
                    )
                elif discrepancy["type"] == "checksum_mismatch":
                    # Create sync task for mismatched file
                    source_file = discrepancy["source_file"]
                    target_file = discrepancy["target_file"]
                    
                    # Sync from newer file to older file
                    if source_file.modified_time > target_file.modified_time:
                        self.create_sync_task(
                            source_node=discrepancy["source_node"],
                            target_node=discrepancy["target_node"],
                            file_paths=[discrepancy["file_path"]],
                            priority="high"
                        )
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get comprehensive sync status"""
        return {
            "nodes": {
                node_id: {
                    "name": node.name,
                    "status": node.status,
                    "last_sync": node.last_sync.isoformat() if node.last_sync else None,
                    "sync_errors": node.sync_errors
                }
                for node_id, node in self.nodes.items()
            },
            "tasks": {
                task_id: {
                    "source_node": task.source_node,
                    "target_node": task.target_node,
                    "status": task.status,
                    "progress": task.progress,
                    "created_at": task.created_at.isoformat(),
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "errors": task.errors
                }
                for task_id, task in self.sync_tasks.items()
            },
            "discrepancies": self._detect_sync_discrepancies()
        }


# Ray remote functions for distributed SFTP operations
@ray.remote
def sftp_sync_large_files_job(config):
    """Ray job for SFTP large file synchronization"""
    import sys
    from pathlib import Path
    
    # Add QuantTime to path
    project_root = Path("/opt/quanttime")
    sys.path.insert(0, str(project_root))
    
    try:
        from quanttime.core.sftp_manager import SFTPManager
        
        # Get configuration
        source_node = config.get("source_node", "laptop")
        target_node = config.get("target_node", "r630xl")
        file_paths = config.get("file_paths", [])
        sync_type = config.get("sync_type", "auto")
        
        # Initialize SFTP manager
        sftp_manager = SFTPManager()
        
        if sync_type == "auto":
            # Auto-sync based on discrepancies
            sftp_manager.auto_sync_large_files()
        else:
            # Manual sync of specific files
            task_id = sftp_manager.create_sync_task(
                source_node=source_node,
                target_node=target_node,
                file_paths=file_paths,
                priority="high"
            )
        
        # Get sync status
        status = sftp_manager.get_sync_status()
        
        return {
            "status": "completed",
            "source_node": source_node,
            "target_node": target_node,
            "sync_type": sync_type,
            "sync_status": status
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "source_node": config.get("source_node", "unknown")
        }


# Global SFTP manager instance
sftp_manager = None


def get_sftp_manager() -> SFTPManager:
    """Get global SFTP manager instance"""
    global sftp_manager
    if sftp_manager is None:
        sftp_manager = SFTPManager()
    return sftp_manager
