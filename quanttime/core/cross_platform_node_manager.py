"""
Cross-Platform Node Management System
Manages Ray workers, deployment, and health monitoring across Windows and Linux nodes
"""

import os
import json
import time
import logging
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import paramiko
import psutil

# Imports moved inside methods to avoid circular imports

logger = logging.getLogger(__name__)


class NodeHealthStatus(Enum):
    GREEN = "green"      # All systems operational
    YELLOW = "yellow"    # Connected but issues
    RED = "red"          # Cannot connect


@dataclass
class NodeHealth:
    """Node health information"""
    status: NodeHealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    last_check: datetime = field(default_factory=datetime.now)


class CrossPlatformNodeManager:
    """
    Manages cross-platform nodes for QuantTime deployment
    
    Features:
    - Deploys QuantTime to Windows and Linux nodes
    - Manages Ray worker connections
    - Monitors node health
    - Handles SFTP file synchronization
    - Provides unified interface for node management
    """
    
    def __init__(self, config_path: str = "config/ray_cluster_config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        # Import here to avoid circular imports
        from .cross_platform_git_watcher import CrossPlatformGitWatcher
        from .sftp_manager import SFTPManager
        
        self.git_watcher = CrossPlatformGitWatcher(config_path)
        self.sftp_manager = SFTPManager()
        self.node_health: Dict[str, NodeHealth] = {}
        
        logger.info("Cross-Platform Node Manager initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration"""
        with open(self.config_path, 'r') as f:
            return json.load(f)
    
    def set_node_credentials(self, node_id: str, password: str = None, key_path: str = None):
        """Set credentials for a node"""
        self.git_watcher.set_node_credentials(node_id, password, key_path)
        self.sftp_manager.set_node_password(node_id, password)
    
    def deploy_to_node(self, node_id: str, force: bool = False) -> Tuple[bool, str]:
        """Deploy QuantTime to a specific node"""
        try:
            # Use Git watcher for deployment
            results = self.git_watcher.manual_deploy(node_id, force)
            
            if node_id in results:
                success, message = results[node_id]
                
                if success:
                    # Also sync large files via SFTP
                    try:
                        if self.sftp_manager.sync_node_files(node_id):
                            return True, f"{message} + SFTP sync completed"
                        else:
                            return True, f"{message} (SFTP sync failed)"
                    except Exception as e:
                        return True, f"{message} (SFTP sync error: {e})"
                else:
                    return False, message
            else:
                return False, "Node not found"
                
        except Exception as e:
            logger.error(f"Deployment failed for {node_id}: {e}")
            return False, str(e)
    
    def deploy_to_all_nodes(self, force: bool = False) -> Dict[str, Tuple[bool, str]]:
        """Deploy to all worker nodes"""
        results = self.git_watcher.manual_deploy(force=force)
        
        # Also sync large files for successful deployments
        for node_id, (success, message) in results.items():
            if success:
                try:
                    if self.sftp_manager.sync_node_files(node_id):
                        results[node_id] = (True, f"{message} + SFTP sync completed")
                    else:
                        results[node_id] = (True, f"{message} (SFTP sync failed)")
                except Exception as e:
                    results[node_id] = (True, f"{message} (SFTP sync error: {e})")
        
        return results
    
    def start_ray_cluster(self, node_id: str) -> Tuple[bool, str]:
        """Start Ray worker on a specific node"""
        try:
            if node_id not in self.git_watcher.nodes:
                return False, "Node not found"
            
            node = self.git_watcher.nodes[node_id]
            
            if node_id == self.config["head_node"]["node_id"]:
                return False, "Cannot start worker on head node"
            
            # Get head node address
            head_node = self.git_watcher.nodes[self.config["head_node"]["node_id"]]
            head_address = f"{head_node.address}:{self.config['head_node']['port']}"
            
            # Platform-specific Ray start command
            if node.platform == "windows":
                cmd = f'ray start --address={head_address} --working-dir="{node.ray_working_dir}"'
            else:
                cmd = f'ray start --address={head_address} --working-dir={node.ray_working_dir}'
            
            success, stdout, stderr = self.git_watcher._execute_command(node, cmd, timeout=60)
            
            if success:
                return True, f"Ray worker started on {node.name}"
            else:
                return False, f"Failed to start Ray worker: {stderr}"
                
        except Exception as e:
            logger.error(f"Ray start failed for {node_id}: {e}")
            return False, str(e)
    
    def stop_ray_worker(self, node_id: str) -> Tuple[bool, str]:
        """Stop Ray worker on a specific node"""
        try:
            if node_id not in self.git_watcher.nodes:
                return False, "Node not found"
            
            node = self.git_watcher.nodes[node_id]
            
            success, stdout, stderr = self.git_watcher._execute_command(node, "ray stop", timeout=30)
            
            if success or "No Ray processes found" in stderr:
                return True, f"Ray worker stopped on {node.name}"
            else:
                return False, f"Failed to stop Ray worker: {stderr}"
                
        except Exception as e:
            logger.error(f"Ray stop failed for {node_id}: {e}")
            return False, str(e)
    
    def get_node_health_status(self, node_id: str) -> Tuple[NodeHealthStatus, str]:
        """Get health status of a specific node"""
        try:
            if node_id not in self.git_watcher.nodes:
                return NodeHealthStatus.RED, "Node not found"
            
            node = self.git_watcher.nodes[node_id]
            health_details = self.git_watcher.get_node_health(node_id)
            
            if health_details["status"] == "healthy":
                self.node_health[node_id] = NodeHealth(
                    status=NodeHealthStatus.GREEN,
                    message="All systems operational",
                    details=health_details
                )
                return NodeHealthStatus.GREEN, "All systems operational"
            
            elif health_details["status"] == "degraded":
                self.node_health[node_id] = NodeHealth(
                    status=NodeHealthStatus.YELLOW,
                    message=health_details["message"],
                    details=health_details
                )
                return NodeHealthStatus.YELLOW, health_details["message"]
            
            else:
                self.node_health[node_id] = NodeHealth(
                    status=NodeHealthStatus.RED,
                    message=health_details["message"],
                    details=health_details
                )
                return NodeHealthStatus.RED, health_details["message"]
                
        except Exception as e:
            logger.error(f"Health check failed for {node_id}: {e}")
            self.node_health[node_id] = NodeHealth(
                status=NodeHealthStatus.RED,
                message=f"Health check error: {str(e)}",
                details={}
            )
            return NodeHealthStatus.RED, f"Health check error: {str(e)}"
    
    def get_all_node_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all nodes"""
        status = {}
        
        for node_id, node in self.git_watcher.nodes.items():
            health_status, health_message = self.get_node_health_status(node_id)
            
            status[node_id] = {
                "name": node.name,
                "platform": node.platform,
                "address": node.address,
                "health_status": health_status.value,
                "health_message": health_message,
                "deployment_status": node.deployment_status.value,
                "last_sync": node.last_sync.isoformat() if node.last_sync else None,
                "last_commit_hash": node.last_commit_hash[:8] if node.last_commit_hash else None,
                "errors": node.errors[-3:] if node.errors else []  # Last 3 errors
            }
        
        return status
    
    def get_connected_nodes(self) -> List[str]:
        """Get list of connected node IDs"""
        connected = []
        
        for node_id in self.git_watcher.nodes.keys():
            health_status, _ = self.get_node_health_status(node_id)
            if health_status in [NodeHealthStatus.GREEN, NodeHealthStatus.YELLOW]:
                connected.append(node_id)
        
        return connected
    
    def sync_large_files(self, node_id: str) -> Tuple[bool, str]:
        """Sync large files to a specific node"""
        try:
            success = self.sftp_manager.sync_node_files(node_id)
            if success:
                return True, f"Large files synced to {node_id}"
            else:
                return False, f"Failed to sync large files to {node_id}"
                
        except Exception as e:
            logger.error(f"File sync failed for {node_id}: {e}")
            return False, str(e)
    
    def execute_command_on_node(self, node_id: str, command: str, timeout: int = 30) -> Tuple[bool, str, str]:
        """Execute a command on a specific node"""
        try:
            if node_id not in self.git_watcher.nodes:
                return False, "", "Node not found"
            
            node = self.git_watcher.nodes[node_id]
            return self.git_watcher._execute_command(node, command, timeout)
            
        except Exception as e:
            logger.error(f"Command execution failed on {node_id}: {e}")
            return False, "", str(e)
    
    def setup_new_node(self, node_config: Dict[str, Any], credentials: Dict[str, str]) -> Tuple[bool, str]:
        """Setup a new node with QuantTime"""
        try:
            node_id = node_config["node_id"]
            
            # Add node to configuration
            self.git_watcher._add_node(node_config)
            
            # Set credentials
            if "password" in credentials:
                self.set_node_credentials(node_id, password=credentials["password"])
            elif "key_path" in credentials:
                self.set_node_credentials(node_id, key_path=credentials["key_path"])
            
            # Test connection
            health_status, message = self.get_node_health_status(node_id)
            if health_status == NodeHealthStatus.RED:
                return False, f"Cannot connect to new node: {message}"
            
            # Deploy QuantTime
            success, deploy_message = self.deploy_to_node(node_id, force=True)
            if not success:
                return False, f"Deployment failed: {deploy_message}"
            
            # Start Ray worker
            success, ray_message = self.start_ray_cluster(node_id)
            if not success:
                logger.warning(f"Ray setup failed for {node_id}: {ray_message}")
            
            return True, f"Node {node_id} setup completed successfully"
            
        except Exception as e:
            logger.error(f"Node setup failed: {e}")
            return False, str(e)
    
    def get_cluster_overview(self) -> Dict[str, Any]:
        """Get comprehensive cluster overview"""
        node_status = self.get_all_node_status()
        deployment_status = self.git_watcher.get_deployment_status()
        
        # Count nodes by health status
        health_counts = {
            "green": len([n for n in node_status.values() if n["health_status"] == "green"]),
            "yellow": len([n for n in node_status.values() if n["health_status"] == "yellow"]),
            "red": len([n for n in node_status.values() if n["health_status"] == "red"])
        }
        
        # Count nodes by platform
        platform_counts = {}
        for node in node_status.values():
            platform = node["platform"]
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        return {
            "total_nodes": len(node_status),
            "connected_nodes": len(self.get_connected_nodes()),
            "health_counts": health_counts,
            "platform_counts": platform_counts,
            "nodes": node_status,
            "git_monitoring": deployment_status["monitoring_active"],
            "auto_deploy_enabled": deployment_status["git_config"]["auto_deploy_enabled"]
        }
    
    def enable_auto_deploy(self, enabled: bool = True):
        """Enable or disable automatic deployment"""
        self.git_watcher.git_config.auto_deploy_enabled = enabled
        if enabled and not self.git_watcher.monitoring_active:
            self.git_watcher.start_monitoring()
        elif not enabled and self.git_watcher.monitoring_active:
            self.git_watcher.stop_monitoring()
    
    def set_github_pat(self, pat: str):
        """Set GitHub Personal Access Token"""
        self.git_watcher.set_github_pat(pat)
    
    def cleanup(self):
        """Cleanup resources"""
        self.git_watcher.stop_monitoring()
        self.git_watcher.cleanup_connections()


# Global instance
node_manager = None


def get_node_manager() -> CrossPlatformNodeManager:
    """Get global node manager instance"""
    global node_manager
    if node_manager is None:
        node_manager = CrossPlatformNodeManager()
    return node_manager


def init_node_manager(config_path: str = None) -> CrossPlatformNodeManager:
    """Initialize node manager with custom config"""
    global node_manager
    if config_path:
        node_manager = CrossPlatformNodeManager(config_path)
    else:
        node_manager = CrossPlatformNodeManager()
    return node_manager
