"""
Cross-Platform Git Repository Watcher and Auto-Deploy System
Replaces Coolify with native Ray+SSH+Git monitoring for seamless cross-platform deployment
"""

import os
import json
import time
import threading
import logging
import platform
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import paramiko
import requests
from git import Repo
import psutil

logger = logging.getLogger(__name__)


class DeploymentStatus(Enum):
    IDLE = "idle"
    MONITORING = "monitoring"
    DEPLOYING = "deploying"
    SYNCING = "syncing"
    FAILED = "failed"
    SUCCESS = "success"


@dataclass
class NodeInfo:
    """Cross-platform node information"""
    node_id: str
    name: str
    address: str
    platform: str  # "windows" or "linux"
    ssh_enabled: bool
    ssh_port: int = 22
    ssh_username: str = ""
    ssh_password: Optional[str] = None
    ssh_key_path: Optional[str] = None
    project_root: str = ""
    python_executable: str = "python"
    ray_working_dir: str = ""
    last_sync: Optional[datetime] = None
    last_commit_hash: Optional[str] = None
    deployment_status: DeploymentStatus = DeploymentStatus.IDLE
    errors: List[str] = field(default_factory=list)


@dataclass
class GitWatcherConfig:
    """Git watcher configuration"""
    repository_url: str
    branch: str = "main"
    github_pat: Optional[str] = None
    monitor_interval_seconds: int = 30
    auto_deploy_enabled: bool = True
    auto_pull_enabled: bool = True
    github_pat_required: bool = True
    exclude_patterns: List[str] = field(default_factory=list)


class CrossPlatformGitWatcher:
    """
    Cross-platform Git repository watcher that replaces Coolify functionality
    
    Features:
    - Monitors GitHub repository for changes
    - Automatically deploys to Windows and Linux nodes
    - Uses SSH for cross-platform communication
    - Integrates with Ray for distributed job execution
    - Maintains SFTP sync for large files
    - Provides seamless auto-deploy like Coolify but cross-platform
    """
    
    def __init__(self, config_path: str = "config/ray_cluster_config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.git_config = GitWatcherConfig(**self.config.get("git_config", {}))
        self.nodes: Dict[str, NodeInfo] = {}
        self.local_repo: Optional[Repo] = None
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.deployment_callbacks: List[Callable] = []
        self.ssh_connections: Dict[str, paramiko.SSHClient] = {}
        
        # Initialize nodes
        self._initialize_nodes()
        
        # Initialize local repository
        self._initialize_local_repo()
        
        logger.info("Cross-Platform Git Watcher initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration"""
        with open(self.config_path, 'r') as f:
            return json.load(f)
    
    def _initialize_nodes(self):
        """Initialize node information from config"""
        # Initialize head node
        head_config = self.config["head_node"]
        head_node = NodeInfo(
            node_id=head_config["node_id"],
            name=head_config["name"],
            address=head_config["address"],
            platform=head_config.get("platform", "windows"),
            ssh_enabled=head_config.get("ssh", {}).get("enabled", False),
            ssh_port=head_config.get("ssh", {}).get("port", 22),
            ssh_username=head_config.get("ssh", {}).get("username", ""),
            project_root=head_config.get("paths", {}).get("project_root", ""),
            python_executable=head_config.get("paths", {}).get("python_executable", "python"),
            ray_working_dir=head_config.get("paths", {}).get("ray_working_dir", "")
        )
        self.nodes[head_node.node_id] = head_node
        
        # Initialize worker nodes
        for worker_config in self.config["worker_nodes"]:
            worker_node = NodeInfo(
                node_id=worker_config["node_id"],
                name=worker_config["name"],
                address=worker_config["address"],
                platform=worker_config.get("platform", "linux"),
                ssh_enabled=worker_config.get("ssh", {}).get("enabled", True),
                ssh_port=worker_config.get("ssh", {}).get("port", 22),
                ssh_username=worker_config.get("ssh", {}).get("username", ""),
                project_root=worker_config.get("paths", {}).get("project_root", ""),
                python_executable=worker_config.get("paths", {}).get("python_executable", "python"),
                ray_working_dir=worker_config.get("paths", {}).get("ray_working_dir", "")
            )
            self.nodes[worker_node.node_id] = worker_node
    
    def _initialize_local_repo(self):
        """Initialize local Git repository"""
        try:
            project_root = self.nodes[self.config["head_node"]["node_id"]].project_root
            self.local_repo = Repo(project_root)
            logger.info(f"Initialized local repository at {project_root}")
        except Exception as e:
            logger.error(f"Failed to initialize local repository: {e}")
    
    def set_node_credentials(self, node_id: str, password: str = None, key_path: str = None):
        """Set SSH credentials for a node"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.ssh_password = password
            node.ssh_key_path = key_path
            logger.info(f"Credentials set for node {node_id}")
    
    def set_github_pat(self, pat: str):
        """Set GitHub Personal Access Token"""
        self.git_config.github_pat = pat
        logger.info("GitHub PAT configured")
    
    def _get_ssh_connection(self, node: NodeInfo) -> Optional[paramiko.SSHClient]:
        """Get SSH connection to node with platform-specific handling"""
        if not node.ssh_enabled:
            return None
        
        try:
            # Check if connection already exists and is active
            if node.node_id in self.ssh_connections:
                ssh = self.ssh_connections[node.node_id]
                try:
                    # Test connection
                    ssh.exec_command("echo test", timeout=5)
                    return ssh
                except:
                    # Connection is dead, remove it
                    del self.ssh_connections[node.node_id]
            
            # Create new connection
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Platform-specific connection logic
            if node.platform == "windows":
                # Windows SSH connection
                ssh.connect(
                    node.address,
                    port=node.ssh_port,
                    username=node.ssh_username,
                    password=node.ssh_password,
                    timeout=10
                )
            else:
                # Linux SSH connection
                if node.ssh_password:
                    ssh.connect(
                        node.address,
                        port=node.ssh_port,
                        username=node.ssh_username,
                        password=node.ssh_password,
                        timeout=10
                    )
                elif node.ssh_key_path and os.path.exists(node.ssh_key_path):
                    ssh.connect(
                        node.address,
                        port=node.ssh_port,
                        username=node.ssh_username,
                        key_filename=node.ssh_key_path,
                        timeout=10
                    )
                else:
                    raise Exception("No valid authentication method")
            
            self.ssh_connections[node.node_id] = ssh
            logger.info(f"SSH connection established to {node.name}")
            return ssh
            
        except Exception as e:
            logger.error(f"Failed to connect to {node.name}: {e}")
            node.errors.append(f"SSH connection failed: {str(e)}")
            return None
    
    def _execute_command(self, node: NodeInfo, command: str, timeout: int = 30) -> Tuple[bool, str, str]:
        """Execute command on node with platform-specific handling"""
        try:
            if node.node_id == self.config["head_node"]["node_id"]:
                # Local execution
                if platform.system().lower().startswith("win"):
                    # Windows command execution
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        cwd=node.project_root
                    )
                else:
                    # Linux/Mac command execution
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        cwd=node.project_root
                    )
                
                return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
            
            else:
                # Remote execution via SSH
                ssh = self._get_ssh_connection(node)
                if not ssh:
                    return False, "", "SSH connection failed"
                
                # Platform-specific command adaptation
                if node.platform == "windows":
                    # Windows PowerShell command
                    if node.project_root:
                        command = f"cd /d \"{node.project_root}\" && {command}"
                else:
                    # Linux bash command
                    if node.project_root:
                        command = f"cd {node.project_root} && {command}"
                
                stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
                exit_status = stdout.channel.recv_exit_status()
                
                return exit_status == 0, stdout.read().decode().strip(), stderr.read().decode().strip()
        
        except Exception as e:
            logger.error(f"Command execution failed on {node.name}: {e}")
            return False, "", str(e)
    
    def _get_remote_commit_hash(self, node: NodeInfo) -> Optional[str]:
        """Get current commit hash from remote node"""
        try:
            if node.platform == "windows":
                command = "git rev-parse HEAD"
            else:
                command = "git rev-parse HEAD"
            
            success, stdout, stderr = self._execute_command(node, command)
            if success:
                return stdout.strip()
            else:
                logger.warning(f"Failed to get commit hash from {node.name}: {stderr}")
                return None
        except Exception as e:
            logger.error(f"Error getting commit hash from {node.name}: {e}")
            return None
    
    def _check_repository_changes(self) -> Tuple[bool, str]:
        """Check if there are new changes in the repository"""
        try:
            if not self.local_repo:
                return False, "Local repository not initialized"
            
            # Fetch latest changes
            origin = self.local_repo.remotes.origin
            origin.fetch()
            
            # Get current and remote commit hashes
            local_commit = self.local_repo.head.commit.hexsha
            remote_commit = origin.refs[self.git_config.branch].commit.hexsha
            
            if local_commit != remote_commit:
                return True, f"New changes detected: {remote_commit[:8]}"
            
            return False, "No changes"
            
        except Exception as e:
            logger.error(f"Error checking repository changes: {e}")
            return False, f"Error: {str(e)}"
    
    def _deploy_to_node(self, node: NodeInfo, force: bool = False) -> Tuple[bool, str]:
        """Deploy latest code to a specific node"""
        logger.info(f"Deploying to {node.name} ({node.platform})...")
        node.deployment_status = DeploymentStatus.DEPLOYING
        
        try:
            # Check if node needs update
            if not force:
                local_commit = self.local_repo.head.commit.hexsha if self.local_repo else None
                remote_commit = self._get_remote_commit_hash(node)
                
                if local_commit and remote_commit and local_commit == remote_commit:
                    node.deployment_status = DeploymentStatus.SUCCESS
                    return True, f"Node {node.name} is already up to date"
            
            # Platform-specific deployment commands
            if node.platform == "windows":
                commands = [
                    "git fetch origin",
                    f"git reset --hard origin/{self.git_config.branch}",
                    "git clean -fd",
                    # Update dependencies if requirements.txt changed
                    f"{node.python_executable} -m pip install -r requirements.txt --quiet"
                ]
            else:
                commands = [
                    "git fetch origin",
                    f"git reset --hard origin/{self.git_config.branch}",
                    "git clean -fd",
                    # Update dependencies if requirements.txt changed
                    f"{node.python_executable} -m pip install -r requirements.txt --quiet"
                ]
            
            # Execute deployment commands
            for command in commands:
                success, stdout, stderr = self._execute_command(node, command, timeout=60)
                if not success:
                    error_msg = f"Deployment command failed: {command} - {stderr}"
                    node.errors.append(error_msg)
                    node.deployment_status = DeploymentStatus.FAILED
                    return False, error_msg
            
            # Update node status
            node.last_sync = datetime.now()
            node.last_commit_hash = self._get_remote_commit_hash(node)
            node.deployment_status = DeploymentStatus.SUCCESS
            
            # Restart Ray worker if needed
            success, message = self._restart_ray_worker(node)
            if not success:
                logger.warning(f"Ray restart failed on {node.name}: {message}")
            
            logger.info(f"Successfully deployed to {node.name}")
            return True, f"Successfully deployed to {node.name}"
            
        except Exception as e:
            error_msg = f"Deployment failed on {node.name}: {str(e)}"
            node.errors.append(error_msg)
            node.deployment_status = DeploymentStatus.FAILED
            logger.error(error_msg)
            return False, error_msg
    
    def _restart_ray_worker(self, node: NodeInfo) -> Tuple[bool, str]:
        """Restart Ray worker on node"""
        try:
            if node.platform == "windows":
                # Windows Ray commands
                stop_cmd = "ray stop"
                start_cmd = f"ray start --address={self.config['head_node']['address']}:{self.config['head_node']['port']} --working-dir=\"{node.ray_working_dir}\""
            else:
                # Linux Ray commands
                stop_cmd = "ray stop"
                start_cmd = f"ray start --address={self.config['head_node']['address']}:{self.config['head_node']['port']} --working-dir={node.ray_working_dir}"
            
            # Stop Ray
            self._execute_command(node, stop_cmd, timeout=30)
            time.sleep(2)
            
            # Start Ray
            success, stdout, stderr = self._execute_command(node, start_cmd, timeout=60)
            if success:
                return True, "Ray worker restarted"
            else:
                return False, f"Failed to start Ray worker: {stderr}"
                
        except Exception as e:
            return False, f"Ray restart error: {str(e)}"
    
    def _deploy_to_all_nodes(self, force: bool = False) -> Dict[str, Tuple[bool, str]]:
        """Deploy to all worker nodes"""
        results = {}
        
        for node_id, node in self.nodes.items():
            if node_id == self.config["head_node"]["node_id"]:
                continue  # Skip head node (local)
            
            success, message = self._deploy_to_node(node, force)
            results[node_id] = (success, message)
        
        return results
    
    def _monitor_repository(self):
        """Main monitoring loop"""
        logger.info("Starting Git repository monitoring...")
        
        while self.monitoring_active:
            try:
                # Check for repository changes
                has_changes, change_info = self._check_repository_changes()
                
                if has_changes and self.git_config.auto_deploy_enabled:
                    logger.info(f"Repository changes detected: {change_info}")
                    
                    # Pull latest changes locally first
                    if self.git_config.auto_pull_enabled:
                        try:
                            origin = self.local_repo.remotes.origin
                            origin.pull(self.git_config.branch)
                            logger.info("Local repository updated")
                        except Exception as e:
                            logger.error(f"Failed to pull changes locally: {e}")
                            continue
                    
                    # Deploy to all nodes
                    deploy_results = self._deploy_to_all_nodes()
                    
                    # Call deployment callbacks
                    for callback in self.deployment_callbacks:
                        try:
                            callback(deploy_results)
                        except Exception as e:
                            logger.error(f"Deployment callback failed: {e}")
                    
                    # Log results
                    for node_id, (success, message) in deploy_results.items():
                        if success:
                            logger.info(f"✅ {node_id}: {message}")
                        else:
                            logger.error(f"❌ {node_id}: {message}")
                
                # Sleep for monitoring interval
                time.sleep(self.git_config.monitor_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)  # Wait longer on error
    
    def start_monitoring(self):
        """Start Git repository monitoring"""
        if self.monitoring_active:
            logger.warning("Monitoring is already active")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitor_repository, daemon=True)
        self.monitoring_thread.start()
        logger.info("Git repository monitoring started")
    
    def stop_monitoring(self):
        """Stop Git repository monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)
        logger.info("Git repository monitoring stopped")
    
    def manual_deploy(self, node_id: str = None, force: bool = False) -> Dict[str, Tuple[bool, str]]:
        """Manually trigger deployment"""
        if node_id:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                success, message = self._deploy_to_node(node, force)
                return {node_id: (success, message)}
            else:
                return {node_id: (False, "Node not found")}
        else:
            return self._deploy_to_all_nodes(force)
    
    def add_deployment_callback(self, callback: Callable):
        """Add callback to be called after deployments"""
        self.deployment_callbacks.append(callback)
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Get current deployment status"""
        return {
            "monitoring_active": self.monitoring_active,
            "git_config": {
                "repository_url": self.git_config.repository_url,
                "branch": self.git_config.branch,
                "auto_deploy_enabled": self.git_config.auto_deploy_enabled,
                "auto_pull_enabled": self.git_config.auto_pull_enabled,
                "monitor_interval_seconds": self.git_config.monitor_interval_seconds
            },
            "nodes": {
                node_id: {
                    "name": node.name,
                    "platform": node.platform,
                    "address": node.address,
                    "deployment_status": node.deployment_status.value,
                    "last_sync": node.last_sync.isoformat() if node.last_sync else None,
                    "last_commit_hash": node.last_commit_hash[:8] if node.last_commit_hash else None,
                    "errors": node.errors[-5:] if node.errors else []  # Last 5 errors
                }
                for node_id, node in self.nodes.items()
            }
        }
    
    def get_node_health(self, node_id: str) -> Dict[str, Any]:
        """Get health status of a specific node"""
        if node_id not in self.nodes:
            return {"status": "not_found", "message": "Node not found"}
        
        node = self.nodes[node_id]
        
        try:
            # Test SSH connection if enabled
            if node.ssh_enabled:
                ssh = self._get_ssh_connection(node)
                if not ssh:
                    return {
                        "status": "offline",
                        "message": "SSH connection failed",
                        "platform": node.platform,
                        "last_sync": node.last_sync.isoformat() if node.last_sync else None
                    }
            
            # Test Git repository status
            success, stdout, stderr = self._execute_command(node, "git status", timeout=10)
            if not success:
                return {
                    "status": "degraded",
                    "message": f"Git repository issue: {stderr}",
                    "platform": node.platform,
                    "last_sync": node.last_sync.isoformat() if node.last_sync else None
                }
            
            # Test Ray status
            success, stdout, stderr = self._execute_command(node, "ray status", timeout=10)
            ray_status = "running" if success else "stopped"
            
            return {
                "status": "healthy",
                "message": "All systems operational",
                "platform": node.platform,
                "ray_status": ray_status,
                "last_sync": node.last_sync.isoformat() if node.last_sync else None,
                "last_commit_hash": node.last_commit_hash[:8] if node.last_commit_hash else None
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "platform": node.platform,
                "last_sync": node.last_sync.isoformat() if node.last_sync else None
            }
    
    def cleanup_connections(self):
        """Clean up SSH connections"""
        for ssh in self.ssh_connections.values():
            try:
                ssh.close()
            except:
                pass
        self.ssh_connections.clear()
    
    def __del__(self):
        """Cleanup on destruction"""
        self.stop_monitoring()
        self.cleanup_connections()


# Global instance
git_watcher = None


def get_git_watcher() -> CrossPlatformGitWatcher:
    """Get global Git watcher instance"""
    global git_watcher
    if git_watcher is None:
        git_watcher = CrossPlatformGitWatcher()
    return git_watcher


def init_git_watcher(config_path: str = None) -> CrossPlatformGitWatcher:
    """Initialize Git watcher with custom config"""
    global git_watcher
    if config_path:
        git_watcher = CrossPlatformGitWatcher(config_path)
    else:
        git_watcher = CrossPlatformGitWatcher()
    return git_watcher
