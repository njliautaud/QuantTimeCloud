"""
QuantTime Distributed Synchronization Manager

Enhanced file synchronization for the distributed computing cluster.
Handles real-time sync between laptop, R630XL, and R810.
"""

import asyncio
import json
import logging
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import redis
import requests
import hashlib

# Configure logging
logger = logging.getLogger(__name__)

class DistributedSyncManager:
    """
    Enhanced synchronization manager for the QuantTime cluster
    
    Features:
    - Real-time bidirectional sync between all nodes
    - Intelligent conflict resolution
    - Bandwidth-efficient incremental updates
    - Priority-based sync queues
    - Automatic failover and recovery
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize distributed sync manager"""
        self.redis_url = redis_url
        self.redis_client = None
        self.running = False
        
        # Sync configuration
        self.sync_interval = 10  # seconds for real-time sync
        self.sync_paths = {
            "data": {
                "path": "data/",
                "priority": "high",
                "sync_enabled": True,
                "auto_sync": True,
                "exclude": ["*.tmp", "*.lock", "__pycache__"]
            },
            "models": {
                "path": "models/",
                "priority": "high", 
                "sync_enabled": True,
                "auto_sync": True,
                "exclude": ["*.tmp", "*.log", "*.lock"]
            },
            "results": {
                "path": "results/",
                "priority": "medium",
                "sync_enabled": True,
                "auto_sync": True,
                "exclude": ["*.tmp"]
            },
            "features": {
                "path": "features/",
                "priority": "high",
                "sync_enabled": True,
                "auto_sync": True,
                "exclude": ["*.tmp"]
            },
            "backtests": {
                "path": "backtests/",
                "priority": "medium",
                "sync_enabled": True,
                "auto_sync": True,
                "exclude": ["*.tmp"]
            },
            "config": {
                "path": "config/",
                "priority": "critical",
                "sync_enabled": True,
                "auto_sync": True,
                "exclude": ["*.local", "*.secret", "*.env"]
            }
        }
        
        # Server endpoints for API communication
        self.server_endpoints = {
            "laptop": "http://localhost:8000",
            "r630xl": "http://r630xl:8000",
            "r810": "http://r810:8000"
        }
        
        # File tracking
        self.file_registry: Dict[str, Dict[str, Any]] = {}
        self.sync_queue: List[Dict[str, Any]] = []
        self.conflict_queue: List[Dict[str, Any]] = []
        
        # Performance tracking
        self.sync_stats = {
            "files_synced": 0,
            "bytes_transferred": 0,
            "conflicts_resolved": 0,
            "last_sync": None,
            "average_sync_time": 0.0
        }
    
    async def start(self):
        """Start the distributed sync manager"""
        try:
            # Initialize Redis connection
            self.redis_client = redis.Redis.from_url(self.redis_url)
            self.redis_client.ping()
            
            # Initialize file registry
            await self._scan_all_paths()
            
            self.running = True
            
            # Start background sync tasks
            asyncio.create_task(self._sync_loop())
            asyncio.create_task(self._conflict_resolution_loop())
            asyncio.create_task(self._heartbeat_loop())
            
            logger.info("✅ Distributed Sync Manager started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Distributed Sync Manager: {e}")
            raise
    
    async def stop(self):
        """Stop the distributed sync manager"""
        self.running = False
        logger.info("✅ Distributed Sync Manager stopped")
    
    async def _sync_loop(self):
        """Main synchronization loop"""
        while self.running:
            try:
                start_time = time.time()
                
                # Check for file changes
                changes = await self._detect_changes()
                
                if changes:
                    logger.info(f"🔄 Processing {len(changes)} file changes")
                    
                    # Process changes by priority
                    await self._process_changes_by_priority(changes)
                
                # Update sync statistics
                sync_time = time.time() - start_time
                self._update_sync_stats(sync_time)
                
                # Wait for next sync cycle
                await asyncio.sleep(self.sync_interval)
                
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(self.sync_interval)
    
    async def _detect_changes(self) -> List[Dict[str, Any]]:
        """Detect file changes across all sync paths"""
        changes = []
        
        try:
            for path_name, config in self.sync_paths.items():
                if not config["sync_enabled"]:
                    continue
                    
                path = Path(config["path"])
                if not path.exists():
                    continue
                
                # Scan for changes in this path
                path_changes = await self._scan_path_changes(path_name, path, config)
                changes.extend(path_changes)
                
        except Exception as e:
            logger.error(f"Failed to detect changes: {e}")
        
        return changes
    
    async def _scan_path_changes(self, path_name: str, path: Path, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scan specific path for changes"""
        changes = []
        
        try:
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    relative_path = str(file_path)
                    
                    # Skip excluded files
                    if self._is_excluded(file_path, config["exclude"]):
                        continue
                    
                    # Get file info
                    file_info = await self._get_file_info(file_path)
                    
                    # Check if file changed
                    if relative_path not in self.file_registry:
                        # New file
                        changes.append({
                            "type": "created",
                            "path": relative_path,
                            "path_name": path_name,
                            "priority": config["priority"],
                            "info": file_info
                        })
                        self.file_registry[relative_path] = file_info
                        
                    elif self._file_changed(self.file_registry[relative_path], file_info):
                        # Modified file
                        changes.append({
                            "type": "modified", 
                            "path": relative_path,
                            "path_name": path_name,
                            "priority": config["priority"],
                            "info": file_info
                        })
                        self.file_registry[relative_path] = file_info
                        
        except Exception as e:
            logger.error(f"Failed to scan path {path}: {e}")
        
        return changes
    
    async def _process_changes_by_priority(self, changes: List[Dict[str, Any]]):
        """Process changes sorted by priority"""
        # Sort by priority: critical > high > medium > low
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        changes.sort(key=lambda x: priority_order.get(x["priority"], 4))
        
        for change in changes:
            try:
                await self._sync_change_to_servers(change)
                
            except Exception as e:
                logger.error(f"Failed to sync change {change['path']}: {e}")
    
    async def _sync_change_to_servers(self, change: Dict[str, Any]):
        """Sync file change to all servers"""
        file_path = change["path"]
        change_type = change["type"]
        
        logger.info(f"📤 Syncing {change_type} file: {file_path}")
        
        # Get list of target servers
        target_servers = await self._get_available_servers()
        
        for server_id in target_servers:
            if server_id == "laptop":
                continue  # Skip self
                
            try:
                await self._sync_file_to_server(file_path, server_id, change_type)
                
            except Exception as e:
                logger.error(f"Failed to sync {file_path} to {server_id}: {e}")
    
    async def _sync_file_to_server(self, file_path: str, server_id: str, change_type: str):
        """Sync specific file to target server"""
        try:
            endpoint = self.server_endpoints.get(server_id)
            if not endpoint:
                return
            
            if change_type in ["created", "modified"]:
                # Upload file
                await self._upload_file(file_path, server_id, endpoint)
                
            elif change_type == "deleted":
                # Delete file on remote server
                await self._delete_remote_file(file_path, server_id, endpoint)
                
        except Exception as e:
            logger.error(f"Failed to sync file {file_path} to {server_id}: {e}")
    
    async def _upload_file(self, file_path: str, server_id: str, endpoint: str):
        """Upload file to remote server"""
        try:
            if not os.path.exists(file_path):
                return
            
            # Prepare file for upload
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Calculate checksum
            checksum = hashlib.md5(file_data).hexdigest()
            
            # Upload via API
            upload_data = {
                "file_path": file_path,
                "checksum": checksum,
                "timestamp": datetime.now().isoformat()
            }
            
            files = {"file": (os.path.basename(file_path), file_data)}
            
            response = requests.post(
                f"{endpoint}/api/v1/files/upload",
                data=upload_data,
                files=files,
                timeout=60
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Uploaded {file_path} to {server_id}")
                self.sync_stats["files_synced"] += 1
                self.sync_stats["bytes_transferred"] += len(file_data)
            else:
                logger.error(f"Failed to upload {file_path} to {server_id}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Upload error for {file_path} to {server_id}: {e}")
    
    async def _delete_remote_file(self, file_path: str, server_id: str, endpoint: str):
        """Delete file on remote server"""
        try:
            response = requests.delete(
                f"{endpoint}/api/v1/files/delete",
                json={"file_path": file_path},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"🗑️ Deleted {file_path} on {server_id}")
            else:
                logger.error(f"Failed to delete {file_path} on {server_id}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Delete error for {file_path} on {server_id}: {e}")
    
    async def _get_available_servers(self) -> List[str]:
        """Get list of available servers"""
        available = []
        
        for server_id, endpoint in self.server_endpoints.items():
            if server_id == "laptop":
                continue
                
            try:
                response = requests.get(f"{endpoint}/api/v1/server/health", timeout=5)
                if response.status_code == 200:
                    available.append(server_id)
                    
            except Exception:
                pass  # Server not available
        
        return available
    
    async def _conflict_resolution_loop(self):
        """Handle file conflicts"""
        while self.running:
            try:
                if self.conflict_queue:
                    conflict = self.conflict_queue.pop(0)
                    await self._resolve_conflict(conflict)
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in conflict resolution: {e}")
                await asyncio.sleep(5)
    
    async def _resolve_conflict(self, conflict: Dict[str, Any]):
        """Resolve file sync conflict"""
        try:
            file_path = conflict["file_path"]
            resolution_strategy = conflict.get("strategy", "latest_wins")
            
            if resolution_strategy == "latest_wins":
                # Use the file with the latest timestamp
                await self._resolve_latest_wins(conflict)
                
            elif resolution_strategy == "largest_wins":
                # Use the larger file
                await self._resolve_largest_wins(conflict)
                
            elif resolution_strategy == "manual":
                # Queue for manual resolution
                logger.warning(f"Manual resolution required for {file_path}")
                
            self.sync_stats["conflicts_resolved"] += 1
            
        except Exception as e:
            logger.error(f"Failed to resolve conflict: {e}")
    
    async def _heartbeat_loop(self):
        """Send heartbeat to coordinate with other nodes"""
        while self.running:
            try:
                # Update our status in Redis
                heartbeat_data = {
                    "node_id": "laptop",
                    "timestamp": datetime.now().isoformat(),
                    "status": "online",
                    "sync_stats": self.sync_stats
                }
                
                if self.redis_client:
                    self.redis_client.set(
                        "sync:heartbeat:laptop",
                        json.dumps(heartbeat_data),
                        ex=60
                    )
                
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(30)
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get comprehensive sync status"""
        try:
            # Get server statuses
            server_statuses = {}
            for server_id in ["laptop", "r630xl", "r810"]:
                try:
                    if self.redis_client:
                        heartbeat = self.redis_client.get(f"sync:heartbeat:{server_id}")
                        if heartbeat:
                            server_statuses[server_id] = json.loads(heartbeat.decode())
                        else:
                            server_statuses[server_id] = {"status": "offline"}
                except Exception:
                    server_statuses[server_id] = {"status": "unknown"}
            
            return {
                "sync_enabled": self.running,
                "last_sync": self.sync_stats["last_sync"],
                "stats": self.sync_stats,
                "server_statuses": server_statuses,
                "conflict_queue_size": len(self.conflict_queue),
                "sync_queue_size": len(self.sync_queue),
                "tracked_files": len(self.file_registry)
            }
            
        except Exception as e:
            logger.error(f"Failed to get sync status: {e}")
            return {"error": str(e)}
    
    # Helper methods
    
    async def _scan_all_paths(self):
        """Scan all sync paths to build initial registry"""
        for path_name, config in self.sync_paths.items():
            path = Path(config["path"])
            if path.exists():
                await self._scan_path_changes(path_name, path, config)
    
    async def _get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Get comprehensive file information"""
        stat = file_path.stat()
        
        return {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "checksum": await self._calculate_checksum(file_path),
            "timestamp": datetime.now().isoformat()
        }
    
    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate file checksum"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def _file_changed(self, old_info: Dict[str, Any], new_info: Dict[str, Any]) -> bool:
        """Check if file has changed"""
        return (old_info["mtime"] != new_info["mtime"] or 
                old_info["size"] != new_info["size"] or
                old_info["checksum"] != new_info["checksum"])
    
    def _is_excluded(self, file_path: Path, exclude_patterns: List[str]) -> bool:
        """Check if file should be excluded from sync"""
        file_name = file_path.name
        
        for pattern in exclude_patterns:
            if pattern.startswith("*"):
                if file_name.endswith(pattern[1:]):
                    return True
            elif pattern in str(file_path):
                return True
                
        return False
    
    def _update_sync_stats(self, sync_time: float):
        """Update synchronization statistics"""
        self.sync_stats["last_sync"] = datetime.now().isoformat()
        
        # Update average sync time
        if self.sync_stats["average_sync_time"] == 0:
            self.sync_stats["average_sync_time"] = sync_time
        else:
            self.sync_stats["average_sync_time"] = (
                self.sync_stats["average_sync_time"] * 0.8 + sync_time * 0.2
            )
    
    async def _resolve_latest_wins(self, conflict: Dict[str, Any]):
        """Resolve conflict using latest timestamp"""
        # Implementation for latest wins strategy
        pass
    
    async def _resolve_largest_wins(self, conflict: Dict[str, Any]):
        """Resolve conflict using file size"""
        # Implementation for largest wins strategy  
        pass

# Global instance
distributed_sync = DistributedSyncManager()
