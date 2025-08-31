"""
Peer-to-Peer Sync Manager
No head nodes, no leaders - just equal peers that sync everything
"""

import os
import json
import time
import socket
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import paramiko
import ray

logger = logging.getLogger(__name__)

@dataclass
class PeerNode:
    """A peer node in the distributed system - all nodes are equal"""
    node_id: str
    hostname: str
    platform: str
    address: str
    
    # Services
    ray_port: int = 10001
    dashboard_port: int = 8265
    ssh_port: int = 22
    
    # Resources (for job assignment decisions)
    cpu_count: int = 0
    memory_gb: float = 0.0
    gpu_count: int = 0
    
    # Connection info
    ssh_username: str = ""
    project_root: str = ""
    python_executable: str = "python"
    
    # Status
    last_seen: datetime = field(default_factory=datetime.now)
    is_online: bool = False
    is_trusted: bool = False
    
    # Git sync status
    git_sync_enabled: bool = True
    last_git_sync: Optional[datetime] = None
    current_git_hash: str = ""

class PeerSyncManager:
    """
    Manages peer-to-peer synchronization without head nodes
    
    Key Features:
    - All nodes are equal peers
    - Git sync from any node triggers sync on all nodes  
    - Jobs can be assigned to any specific node from any node
    - Remote logging visibility across all nodes
    - Manual SSH key exchange with clear instructions
    """
    
    def __init__(self, config_path: str = "config/ray_cluster_config.json"):
        self.config_path = Path(config_path)
        self.node_id = self._generate_node_id()
        self.discovery_port = 10002
        self.sync_interval = 30  # seconds
        
        # Peer tracking
        self.known_peers: Dict[str, PeerNode] = {}
        self.local_node = self._create_local_peer()
        
        # Threading
        self.running = False
        self.threads: List[threading.Thread] = []
        
        # Ray cluster (distributed, no head)
        self.ray_initialized = False
        
        # SSH connections
        self.ssh_connections: Dict[str, paramiko.SSHClient] = {}
        
        logger.info(f"🔄 Peer Sync Manager initialized - Node: {self.node_id}")
    
    def _generate_node_id(self) -> str:
        """Generate unique node ID"""
        hostname = socket.gethostname()
        return f"{hostname}_{int(time.time() % 100000)}"
    
    def _create_local_peer(self) -> PeerNode:
        """Create local peer node info"""
        hostname = socket.gethostname()
        platform = "windows" if os.name == "nt" else "linux"
        
        # Get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "127.0.0.1"
        
        # Detect resources
        import psutil
        cpu_count = psutil.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # Try to detect GPU
        gpu_count = 0
        try:
            result = subprocess.run(["nvidia-smi", "--query-gpu=count", "--format=csv,noheader,nounits"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                gpu_count = int(result.stdout.strip())
        except:
            pass
        
        return PeerNode(
            node_id=self.node_id,
            hostname=hostname,
            platform=platform,
            address=local_ip,
            cpu_count=cpu_count,
            memory_gb=memory_gb,
            gpu_count=gpu_count,
            project_root=str(Path.cwd()),
            is_online=True,
            is_trusted=True  # Trust self
        )
    
    def start_peer_services(self):
        """Start all peer synchronization services"""
        if self.running:
            return
        
        self.running = True
        logger.info("🚀 Starting peer synchronization services...")
        
        # Start peer discovery
        discovery_thread = threading.Thread(target=self._peer_discovery_loop, daemon=True)
        discovery_thread.start()
        self.threads.append(discovery_thread)
        
        # Start Git sync monitoring
        git_sync_thread = threading.Thread(target=self._git_sync_loop, daemon=True)
        git_sync_thread.start()
        self.threads.append(git_sync_thread)
        
        # Start health monitoring
        health_thread = threading.Thread(target=self._health_monitoring_loop, daemon=True)
        health_thread.start()
        self.threads.append(health_thread)
        
        # Initialize Ray in distributed mode (no head)
        self._initialize_ray_distributed()
        
        logger.info("✅ Peer services started - ready for sync and job distribution")
    
    def stop_peer_services(self):
        """Stop all peer services"""
        self.running = False
        
        # Close SSH connections
        for node_id, ssh in self.ssh_connections.items():
            try:
                ssh.close()
            except:
                pass
        
        # Shutdown Ray
        if self.ray_initialized:
            try:
                ray.shutdown()
            except:
                pass
        
        # Wait for threads
        for thread in self.threads:
            thread.join(timeout=5)
        
        logger.info("🛑 Peer services stopped")
    
    def _peer_discovery_loop(self):
        """Discover and maintain connections to peer nodes"""
        
        # Setup UDP discovery
        discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        discovery_socket.settimeout(1.0)
        
        try:
            discovery_socket.bind(("", self.discovery_port))
        except Exception as e:
            logger.error(f"Could not bind discovery socket: {e}")
            return
        
        logger.info(f"🔍 Peer discovery listening on port {self.discovery_port}")
        last_broadcast = 0
        
        while self.running:
            try:
                # Broadcast presence every 15 seconds
                current_time = time.time()
                if current_time - last_broadcast > 15:
                    self._broadcast_presence(discovery_socket)
                    last_broadcast = current_time
                
                # Listen for other peers
                try:
                    data, addr = discovery_socket.recvfrom(1024)
                    self._handle_peer_discovery(data, addr)
                except socket.timeout:
                    continue
                    
            except Exception as e:
                if self.running:
                    logger.error(f"Peer discovery error: {e}")
                time.sleep(5)
        
        discovery_socket.close()
    
    def _broadcast_presence(self, socket):
        """Broadcast this node's presence to find peers"""
        presence_message = {
            "type": "peer_discovery",
            "node_id": self.node_id,
            "hostname": self.local_node.hostname,
            "platform": self.local_node.platform,
            "address": self.local_node.address,
            "ray_port": self.local_node.ray_port,
            "dashboard_port": self.local_node.dashboard_port,
            "resources": {
                "cpu_count": self.local_node.cpu_count,
                "memory_gb": self.local_node.memory_gb,
                "gpu_count": self.local_node.gpu_count
            },
            "git_status": {
                "current_hash": self.local_node.current_git_hash,
                "last_sync": self.local_node.last_git_sync.isoformat() if self.local_node.last_git_sync else None
            },
            "timestamp": datetime.now().isoformat()
        }
        
        message_bytes = json.dumps(presence_message).encode()
        
        # Optimize for Tailscale networks (100.x.x.x range)
        broadcast_addresses = []
        
        # Priority 1: Tailscale broadcast (100.x.x.255)
        if self.local_node.address.startswith("100."):
            tailscale_broadcast = ".".join(self.local_node.address.split(".")[:-1] + ["255"])
            broadcast_addresses.append(tailscale_broadcast)
        
        # Priority 2: Local network broadcasts
        local_ip = self.local_node.address
        if local_ip.startswith("192.168."):
            local_broadcast = ".".join(local_ip.split(".")[:-1] + ["255"])
            broadcast_addresses.append(local_broadcast)
        elif local_ip.startswith("10."):
            broadcast_addresses.append("10.255.255.255")
        
        # Fallback: General broadcast
        broadcast_addresses.append("255.255.255.255")
        
        for broadcast_addr in broadcast_addresses:
            try:
                socket.sendto(message_bytes, (broadcast_addr, self.discovery_port))
            except Exception:
                pass  # Ignore broadcast failures
    
    def _handle_peer_discovery(self, data: bytes, addr: Tuple[str, int]):
        """Handle discovery message from peer"""
        try:
            message = json.loads(data.decode())
            
            if message.get("type") == "peer_discovery" and message.get("node_id") != self.node_id:
                peer_id = message["node_id"]
                
                # Create or update peer info
                peer = PeerNode(
                    node_id=peer_id,
                    hostname=message["hostname"],
                    platform=message["platform"],
                    address=message["address"],
                    ray_port=message["ray_port"],
                    dashboard_port=message["dashboard_port"],
                    cpu_count=message["resources"]["cpu_count"],
                    memory_gb=message["resources"]["memory_gb"],
                    gpu_count=message["resources"]["gpu_count"],
                    current_git_hash=message["git_status"]["current_hash"],
                    last_seen=datetime.now(),
                    is_online=True
                )
                
                if peer_id not in self.known_peers:
                    logger.info(f"🔍 Discovered peer: {peer_id} ({peer.hostname}) at {peer.address}")
                    self._initiate_peer_handshake(peer)
                
                self.known_peers[peer_id] = peer
                
        except Exception as e:
            logger.debug(f"Invalid discovery message: {e}")
    
    def _initiate_peer_handshake(self, peer: PeerNode):
        """Initiate handshake with newly discovered peer"""
        logger.info(f"🤝 Initiating handshake with {peer.node_id}")
        
        # Check if SSH keys are available
        ssh_key_path = Path.home() / ".ssh" / "quanttime_automation"
        if ssh_key_path.exists():
            # Try to establish SSH connection
            success = self._test_ssh_connection(peer)
            if success:
                peer.is_trusted = True
                logger.info(f"✅ SSH handshake successful with {peer.node_id}")
            else:
                logger.warning(f"⚠️ SSH handshake failed with {peer.node_id} - manual key exchange needed")
        else:
            logger.warning(f"⚠️ No SSH automation key found - manual setup needed")
    
    def _test_ssh_connection(self, peer: PeerNode) -> bool:
        """Test SSH connection to peer"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Try with automation key
            ssh_key_path = str(Path.home() / ".ssh" / "quanttime_automation")
            ssh.connect(
                peer.address,
                port=peer.ssh_port,
                username=peer.ssh_username or "quanttime",
                key_filename=ssh_key_path,
                timeout=10
            )
            
            # Test basic command
            stdin, stdout, stderr = ssh.exec_command("echo 'test'")
            result = stdout.read().decode().strip()
            
            if result == "test":
                self.ssh_connections[peer.node_id] = ssh
                return True
            else:
                ssh.close()
                return False
                
        except Exception as e:
            logger.debug(f"SSH connection test failed for {peer.node_id}: {e}")
            return False
    
    def _git_sync_loop(self):
        """Monitor Git repository and sync changes across all peers"""
        while self.running:
            try:
                # Check local Git status
                current_hash = self._get_current_git_hash()
                
                if current_hash and current_hash != self.local_node.current_git_hash:
                    logger.info(f"🔄 Git changes detected: {current_hash[:8]}")
                    self.local_node.current_git_hash = current_hash
                    self.local_node.last_git_sync = datetime.now()
                    
                    # Trigger sync on all trusted peers
                    self._trigger_git_sync_on_peers()
                
                # Check if we need to pull from origin
                self._check_and_pull_from_origin()
                
                time.sleep(self.sync_interval)
                
            except Exception as e:
                logger.error(f"Git sync error: {e}")
                time.sleep(60)
    
    def _get_current_git_hash(self) -> str:
        """Get current Git commit hash"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return ""
    
    def _check_and_pull_from_origin(self):
        """Check and pull changes from origin"""
        try:
            # Fetch to see if there are changes
            subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=30)
            
            # Check if behind origin
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..origin/master"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0 and int(result.stdout.strip()) > 0:
                logger.info("🔄 Pulling changes from origin...")
                pull_result = subprocess.run(["git", "pull", "origin", "master"], capture_output=True, text=True)
                
                if pull_result.returncode == 0:
                    logger.info("✅ Successfully pulled changes from origin")
                    self.local_node.current_git_hash = self._get_current_git_hash()
                    self.local_node.last_git_sync = datetime.now()
                else:
                    logger.error(f"Failed to pull: {pull_result.stderr}")
                    
        except Exception as e:
            logger.error(f"Git pull check error: {e}")
    
    def _trigger_git_sync_on_peers(self):
        """Trigger Git sync on all trusted peer nodes"""
        for peer_id, peer in self.known_peers.items():
            if peer.is_trusted and peer.is_online:
                self._trigger_git_sync_on_peer(peer)
    
    def _trigger_git_sync_on_peer(self, peer: PeerNode):
        """Trigger Git sync on a specific peer"""
        if peer.node_id not in self.ssh_connections:
            return
        
        try:
            ssh = self.ssh_connections[peer.node_id]
            
            # Commands to sync Git on remote peer
            sync_commands = [
                f"cd {peer.project_root}",
                "git fetch origin",
                "git pull origin master"
            ]
            
            for cmd in sync_commands:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                result = stdout.read().decode()
                error = stderr.read().decode()
                
                if error and "Already up to date" not in error:
                    logger.warning(f"Git sync warning on {peer.node_id}: {error}")
            
            logger.info(f"🔄 Git sync triggered on {peer.node_id}")
            
        except Exception as e:
            logger.error(f"Failed to trigger Git sync on {peer.node_id}: {e}")
    
    def _health_monitoring_loop(self):
        """Monitor health of all peer nodes"""
        while self.running:
            try:
                current_time = datetime.now()
                
                # Mark peers as offline if not seen recently
                for peer_id, peer in list(self.known_peers.items()):
                    if (current_time - peer.last_seen).total_seconds() > 60:
                        if peer.is_online:
                            logger.warning(f"📡 Peer {peer_id} appears offline")
                            peer.is_online = False
                        
                        # Remove very old peers
                        if (current_time - peer.last_seen).total_seconds() > 300:
                            logger.info(f"🗑️ Removing stale peer {peer_id}")
                            del self.known_peers[peer_id]
                            if peer_id in self.ssh_connections:
                                self.ssh_connections[peer_id].close()
                                del self.ssh_connections[peer_id]
                
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                time.sleep(60)
    
    def _initialize_ray_distributed(self):
        """Initialize Ray in distributed mode with Windows compatibility"""
        try:
            # Try to connect to existing Ray cluster first
            connected = False
            
            # Check if any peers have Ray running
            for peer in self.known_peers.values():
                if peer.is_online and peer.is_trusted:
                    try:
                        ray.init(address=f"ray://{peer.address}:{peer.ray_port}")
                        connected = True
                        logger.info(f"🔗 Connected to Ray cluster on {peer.node_id}")
                        break
                    except Exception:
                        continue
            
            # If no existing cluster, start our own
            if not connected:
                # Windows-specific Ray configuration
                ray_config = {
                    "address": None,  # Start new cluster
                    "dashboard_host": "0.0.0.0",
                    "dashboard_port": self.local_node.dashboard_port,
                    "num_cpus": self.local_node.cpu_count,
                    "num_gpus": self.local_node.gpu_count,
                    "object_store_memory": min(int(self.local_node.memory_gb * 0.3 * 1024**3), 2**30),  # 30% of RAM, max 1GB
                    "logging_level": logging.WARNING,  # Reduce noise
                }
                
                # Windows-specific settings
                if os.name == "nt":
                    ray_config["_system_config"] = {
                        "object_spilling_config": json.dumps({
                            "type": "filesystem", 
                            "params": {"directory_path": str(Path(self.local_node.project_root) / "temp" / "ray_spill")}
                        })
                    }
                
                ray.init(**ray_config)
                logger.info(f"🎯 Started new Ray cluster on port {self.local_node.dashboard_port}")
            
            self.ray_initialized = True
            
        except Exception as e:
            logger.warning(f"Ray initialization failed: {e}")
            logger.info("🔄 Ray cluster will be available when other nodes connect")
            # Don't fail completely - peer sync can work without Ray
    
    def assign_job_to_node(self, job_function, target_node_id: str, *args, **kwargs):
        """Assign a Ray job to a specific node"""
        if not self.ray_initialized:
            raise RuntimeError("Ray cluster not initialized")
        
        # Get target node info
        target_peer = self.known_peers.get(target_node_id)
        if not target_peer:
            raise ValueError(f"Unknown target node: {target_node_id}")
        
        if not target_peer.is_online:
            raise RuntimeError(f"Target node {target_node_id} is offline")
        
        # Create Ray remote task with node affinity
        @ray.remote(num_cpus=1)
        def remote_job(*args, **kwargs):
            return job_function(*args, **kwargs)
        
        logger.info(f"🎯 Assigning job to {target_node_id} ({target_peer.hostname})")
        
        # Submit job and return future
        future = remote_job.remote(*args, **kwargs)
        return future
    
    def get_peer_status(self) -> Dict[str, Any]:
        """Get status of all peers"""
        return {
            "local_node": {
                "node_id": self.local_node.node_id,
                "hostname": self.local_node.hostname,
                "platform": self.local_node.platform,
                "address": self.local_node.address,
                "resources": {
                    "cpu_count": self.local_node.cpu_count,
                    "memory_gb": self.local_node.memory_gb,
                    "gpu_count": self.local_node.gpu_count
                },
                "git_hash": self.local_node.current_git_hash[:8] if self.local_node.current_git_hash else "unknown",
                "last_sync": self.local_node.last_git_sync.isoformat() if self.local_node.last_git_sync else None
            },
            "known_peers": {
                peer_id: {
                    "hostname": peer.hostname,
                    "platform": peer.platform,
                    "address": peer.address,
                    "resources": {
                        "cpu_count": peer.cpu_count,
                        "memory_gb": peer.memory_gb,
                        "gpu_count": peer.gpu_count
                    },
                    "is_online": peer.is_online,
                    "is_trusted": peer.is_trusted,
                    "git_hash": peer.current_git_hash[:8] if peer.current_git_hash else "unknown",
                    "last_seen": peer.last_seen.isoformat()
                }
                for peer_id, peer in self.known_peers.items()
            },
            "cluster_info": {
                "total_peers": len(self.known_peers) + 1,
                "online_peers": len([p for p in self.known_peers.values() if p.is_online]) + 1,
                "trusted_peers": len([p for p in self.known_peers.values() if p.is_trusted]) + 1,
                "ray_initialized": self.ray_initialized
            }
        }
    
    def get_ssh_setup_instructions(self) -> str:
        """Get instructions for manual SSH key exchange"""
        ssh_key_path = Path.home() / ".ssh" / "quanttime_automation"
        
        if not ssh_key_path.exists():
            return """
🔑 SSH Key Setup Required

1. Generate SSH automation key:
   ssh-keygen -t ed25519 -C "quanttime-automation" -f ~/.ssh/quanttime_automation
   (Press Enter for no passphrase)

2. Copy the public key:
   cat ~/.ssh/quanttime_automation.pub

3. Add this public key to each peer node's ~/.ssh/authorized_keys

4. Test connection:
   ssh -i ~/.ssh/quanttime_automation username@peer-node-ip
"""
        else:
            try:
                with open(f"{ssh_key_path}.pub", 'r') as f:
                    public_key = f.read().strip()
                
                return f"""
🔑 SSH Key Exchange Instructions

Your public key:
{public_key}

For each peer node, run:
1. ssh username@peer-node-ip
2. echo "{public_key}" >> ~/.ssh/authorized_keys
3. chmod 600 ~/.ssh/authorized_keys

Test with: ssh -i ~/.ssh/quanttime_automation username@peer-node-ip
"""
            except Exception:
                return "Error reading SSH public key"
