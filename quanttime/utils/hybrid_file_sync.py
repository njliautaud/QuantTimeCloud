#!/usr/bin/env python3
"""
Hybrid File Sync Solution
Works on both Windows and Ubuntu for data/model/results synchronization
"""

import os
import shutil
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
import paramiko
import threading
import queue
import time

logger = logging.getLogger(__name__)

class HybridFileSync:
    """Cross-platform file synchronization for Windows/Ubuntu environments"""
    
    def __init__(self, sync_config: Dict):
        self.sync_config = sync_config
        self.sync_history_file = Path("data/sync_history.json")
        self.sync_history_file.parent.mkdir(parents=True, exist_ok=True)
        self.sync_history = self._load_sync_history()
        
    def _load_sync_history(self) -> Dict:
        """Load sync history from file"""
        try:
            if self.sync_history_file.exists():
                with open(self.sync_history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading sync history: {e}")
        return {}
    
    def _save_sync_history(self):
        """Save sync history to file"""
        try:
            with open(self.sync_history_file, 'w') as f:
                json.dump(self.sync_history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving sync history: {e}")
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""
    
    def get_file_info(self, file_path: Path) -> Dict:
        """Get file information for sync comparison"""
        try:
            stat = file_path.stat()
            return {
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "hash": self.calculate_file_hash(file_path)
            }
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return {}
    
    def scan_directory(self, directory: Path, patterns: List[str] = None) -> Dict[str, Dict]:
        """Scan directory for files matching patterns"""
        files = {}
        
        if not directory.exists():
            return files
        
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    # Check if file matches patterns
                    if patterns:
                        if not any(pattern in str(file_path) for pattern in patterns):
                            continue
                    
                    relative_path = str(file_path.relative_to(directory))
                    files[relative_path] = self.get_file_info(file_path)
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
        
        return files
    
    def compare_directories(self, local_dir: Path, remote_dir: Path, 
                          ssh_client: paramiko.SSHClient = None) -> Dict:
        """Compare local and remote directories"""
        comparison = {
            "local_only": [],
            "remote_only": [],
            "different": [],
            "same": []
        }
        
        # Scan local directory
        local_files = self.scan_directory(local_dir)
        
        # Scan remote directory
        if ssh_client:
            remote_files = self._scan_remote_directory(remote_dir, ssh_client)
        else:
            remote_files = self.scan_directory(remote_dir)
        
        # Compare files
        all_files = set(local_files.keys()) | set(remote_files.keys())
        
        for file_path in all_files:
            local_info = local_files.get(file_path)
            remote_info = remote_files.get(file_path)
            
            if local_info and not remote_info:
                comparison["local_only"].append(file_path)
            elif remote_info and not local_info:
                comparison["remote_only"].append(file_path)
            elif local_info and remote_info:
                if local_info["hash"] == remote_info["hash"]:
                    comparison["same"].append(file_path)
                else:
                    comparison["different"].append(file_path)
        
        return comparison
    
    def _scan_remote_directory(self, remote_dir: Path, ssh_client: paramiko.SSHClient) -> Dict:
        """Scan remote directory via SSH"""
        files = {}
        
        try:
            # List files in remote directory
            stdin, stdout, stderr = ssh_client.exec_command(f"find {remote_dir} -type f")
            remote_files = stdout.read().decode().strip().split('\n')
            
            for file_path in remote_files:
                if file_path:
                    try:
                        # Get file info
                        stdin, stdout, stderr = ssh_client.exec_command(
                            f"stat -c '%s %Y' {file_path}"
                        )
                        stat_output = stdout.read().decode().strip()
                        
                        if stat_output:
                            size, mtime = stat_output.split()
                            
                            # Calculate hash
                            stdin, stdout, stderr = ssh_client.exec_command(
                                f"sha256sum {file_path}"
                            )
                            hash_output = stdout.read().decode().strip()
                            file_hash = hash_output.split()[0] if hash_output else ""
                            
                            relative_path = str(Path(file_path).relative_to(remote_dir))
                            files[relative_path] = {
                                "size": int(size),
                                "mtime": float(mtime),
                                "hash": file_hash
                            }
                    except Exception as e:
                        logger.error(f"Error getting remote file info for {file_path}: {e}")
                        
        except Exception as e:
            logger.error(f"Error scanning remote directory {remote_dir}: {e}")
        
        return files
    
    def sync_file(self, source_path: Path, dest_path: Path, 
                 ssh_client: paramiko.SSHClient = None) -> bool:
        """Sync a single file"""
        try:
            if ssh_client:
                # Remote sync via SFTP
                sftp = ssh_client.open_sftp()
                sftp.put(str(source_path), str(dest_path))
                sftp.close()
            else:
                # Local sync
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, dest_path)
            
            # Update sync history
            file_hash = self.calculate_file_hash(source_path)
            self.sync_history[str(dest_path)] = {
                "hash": file_hash,
                "last_sync": datetime.now().isoformat(),
                "source": str(source_path)
            }
            self._save_sync_history()
            
            return True
        except Exception as e:
            logger.error(f"Error syncing file {source_path} to {dest_path}: {e}")
            return False
    
    def sync_directory(self, source_dir: Path, dest_dir: Path, 
                      ssh_client: paramiko.SSHClient = None,
                      patterns: List[str] = None) -> Dict:
        """Sync entire directory"""
        sync_results = {
            "success": [],
            "failed": [],
            "skipped": []
        }
        
        # Compare directories
        comparison = self.compare_directories(source_dir, dest_dir, ssh_client)
        
        # Sync files that need updating
        files_to_sync = comparison["local_only"] + comparison["different"]
        
        for file_path in files_to_sync:
            source_path = source_dir / file_path
            dest_path = dest_dir / file_path
            
            # Check patterns
            if patterns and not any(pattern in file_path for pattern in patterns):
                sync_results["skipped"].append(file_path)
                continue
            
            # Sync file
            if self.sync_file(source_path, dest_path, ssh_client):
                sync_results["success"].append(file_path)
            else:
                sync_results["failed"].append(file_path)
        
        return sync_results
    
    def bidirectional_sync(self, local_dir: Path, remote_dir: Path,
                          ssh_client: paramiko.SSHClient,
                          patterns: List[str] = None) -> Dict:
        """Perform bidirectional sync between local and remote"""
        results = {
            "local_to_remote": {},
            "remote_to_local": {}
        }
        
        # Sync local to remote
        results["local_to_remote"] = self.sync_directory(
            local_dir, remote_dir, ssh_client, patterns
        )
        
        # Sync remote to local
        results["remote_to_local"] = self.sync_directory(
            remote_dir, local_dir, None, patterns
        )
        
        return results
    
    def get_sync_status(self, local_dir: Path, remote_dir: Path,
                       ssh_client: paramiko.SSHClient = None) -> Dict:
        """Get current sync status"""
        comparison = self.compare_directories(local_dir, remote_dir, ssh_client)
        
        return {
            "total_files": len(comparison["same"]) + len(comparison["different"]) + 
                          len(comparison["local_only"]) + len(comparison["remote_only"]),
            "synced": len(comparison["same"]),
            "out_of_sync": len(comparison["different"]),
            "local_only": len(comparison["local_only"]),
            "remote_only": len(comparison["remote_only"]),
            "details": comparison
        }

# Example usage and configuration
SYNC_CONFIG = {
    "data_patterns": ["*.csv", "*.parquet", "*.json"],
    "model_patterns": ["*.pkl", "*.joblib", "*.h5"],
    "result_patterns": ["*.png", "*.jpg", "*.pdf", "*.html"],
    "exclude_patterns": ["*.tmp", "*.log", "__pycache__"],
    "max_file_size": 1024 * 1024 * 100,  # 100MB
    "sync_interval": 300  # 5 minutes
}

# Global instance
hybrid_file_sync = HybridFileSync(SYNC_CONFIG)
