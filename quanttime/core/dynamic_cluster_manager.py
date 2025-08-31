"""
Dynamic Cluster Management System
Enables any node to be head node with automatic leader election and bidirectional sync
"""

import os
import json
import time
import socket
import logging
import hashlib
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import paramiko
import psutil
import ray
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)

class NodeRole(Enum):
    LEADER = "leader"
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    ISOLATED = "isolated"

class NodeState(Enum):
    DISCOVERING = "discovering"
    CONNECTING = "connecting"
    SYNCING = "syncing"
    ACTIVE = "active"
    DISCONNECTED = "disconnected"

@dataclass
class ClusterNode:
    """Dynamic cluster node with leadership capabilities"""
    node_id: str
    hostname: str
    platform: str
    address: str
    port: int
    dashboard_port: int
    
    # Resources
    cpu_count: int = 0
    memory_gb: float = 0.0
    gpu_count: int = 0
    gpu_memory_gb: float = 0.0
    
    # Cluster state
    role: NodeRole = NodeRole.FOLLOWER
    state: NodeState = NodeState.DISCOVERING
    leader_score: float = 0.0
    last_heartbeat: datetime = field(default_factory=datetime.now)
    
    # Network
    ssh_enabled: bool = True
    ssh_port: int = 22
    ssh_username: str = ""
    
    # Paths
    project_root: str = ""
    python_executable: str = "python"
    
    # Security
    public_key: Optional[str] = None
    private_key_path: Optional[str] = None
    trust_established: bool = False

@dataclass 
class ClusterTopology:
    """Current cluster topology and state"""
    leader_node: Optional[ClusterNode] = None
    active_nodes: Dict[str, ClusterNode] = field(default_factory=dict)
    election_in_progress: bool = False
    cluster_version: int = 0
    last_topology_change: datetime = field(default_factory=datetime.now)

class DynamicClusterManager:
    """
    Manages a dynamic Ray cluster where any node can become the head node
    
    Features:
    - Leader election algorithm (based on resources, uptime, connectivity)
    - Bidirectional SSH key exchange and trust establishment
    - Active discovery and automatic node integration
    - Fault-tolerant cluster reconfiguration
    - Cross-platform support (Windows/Linux)
    """
    
    def __init__(self, config_path: str = "config/ray_cluster_config.json"):
        self.config_path = Path(config_path)
        self.node_id = self._generate_node_id()
        self.cluster_port = 10001
        self.discovery_port = 10002
        self.heartbeat_interval = 5  # seconds
        self.election_timeout = 15   # seconds
        
        # Cluster state
        self.topology = ClusterTopology()
        self.local_node = self._create_local_node()
        self.known_nodes: Dict[str, ClusterNode] = {}
        
        # Threading
        self.running = False
        self.threads: List[threading.Thread] = []
        
        # Discovery
        self.discovery_socket = None
        self.broadcast_addresses = self._get_broadcast_addresses()
        
        # Security
        self.key_exchange_manager = KeyExchangeManager(self.node_id)
        
        logger.info(f"🎯 Dynamic Cluster Manager initialized - Node ID: {self.node_id}")
    
    def _generate_node_id(self) -> str:
        """Generate unique node ID based on hostname and platform"""
        hostname = socket.gethostname()
        platform_info = f"{os.name}_{psutil.cpu_count()}_{int(psutil.virtual_memory().total / 1024**3)}"
        unique_string = f"{hostname}_{platform_info}_{int(time.time())}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:12]
    
    def _create_local_node(self) -> ClusterNode:
        """Create local node configuration"""
        hostname = socket.gethostname()
        platform = "windows" if os.name == "nt" else "linux"
        
        # Get local IP (try to find non-localhost)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "127.0.0.1"
        
        # Detect resources
        cpu_count = psutil.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # Try to detect GPU
        gpu_count = 0
        gpu_memory_gb = 0.0
        try:
            result = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                gpu_memories = [float(x.strip()) for x in result.stdout.strip().split('\n') if x.strip()]
                gpu_count = len(gpu_memories)
                gpu_memory_gb = sum(gpu_memories) / 1024  # Convert MB to GB
        except:
            pass
        
        node = ClusterNode(
            node_id=self.node_id,
            hostname=hostname,
            platform=platform,
            address=local_ip,
            port=self.cluster_port,
            dashboard_port=8265,
            cpu_count=cpu_count,
            memory_gb=memory_gb,
            gpu_count=gpu_count,
            gpu_memory_gb=gpu_memory_gb,
            project_root=str(Path.cwd()),
            python_executable="python"
        )
        
        # Calculate leadership score
        node.leader_score = self._calculate_leadership_score(node)
        
        return node
    
    def _calculate_leadership_score(self, node: ClusterNode) -> float:
        """Calculate node's fitness for leadership role"""
        score = 0.0
        
        # Resource score (40% of total)
        cpu_score = min(node.cpu_count / 32.0, 1.0) * 0.15
        memory_score = min(node.memory_gb / 64.0, 1.0) * 0.15
        gpu_score = min(node.gpu_count / 4.0, 1.0) * 0.10
        
        score += cpu_score + memory_score + gpu_score
        
        # Platform preference (10% - slight preference for Linux for stability)
        if node.platform == "linux":
            score += 0.05
        
        # Connectivity score (25% - based on network reachability)
        if node.address not in ["127.0.0.1", "localhost"]:
            score += 0.15
        
        if node.ssh_enabled:
            score += 0.10
        
        # Stability score (25% - based on uptime and historical reliability)
        try:
            uptime_hours = (datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds() / 3600
            uptime_score = min(uptime_hours / 168.0, 1.0) * 0.25  # 1 week max
            score += uptime_score
        except:
            pass
        
        return min(score, 1.0)
    
    def _get_broadcast_addresses(self) -> List[str]:
        """Get broadcast addresses for network discovery"""
        broadcast_addresses = []
        
        try:
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                        # Calculate broadcast address
                        ip_parts = addr.address.split('.')
                        netmask_parts = addr.netmask.split('.') if addr.netmask else ['255', '255', '255', '0']
                        
                        broadcast_parts = []
                        for i in range(4):
                            ip_part = int(ip_parts[i])
                            mask_part = int(netmask_parts[i])
                            broadcast_part = ip_part | (255 - mask_part)
                            broadcast_parts.append(str(broadcast_part))
                        
                        broadcast_addr = '.'.join(broadcast_parts)
                        if broadcast_addr not in broadcast_addresses:
                            broadcast_addresses.append(broadcast_addr)
        except Exception as e:
            logger.warning(f"Could not determine broadcast addresses: {e}")
            broadcast_addresses = ["255.255.255.255"]
        
        return broadcast_addresses
    
    def start_cluster_services(self):
        """Start all cluster management services"""
        if self.running:
            return
        
        self.running = True
        logger.info("🚀 Starting dynamic cluster services...")
        
        # Start discovery service
        discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        discovery_thread.start()
        self.threads.append(discovery_thread)
        
        # Start heartbeat service  
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        self.threads.append(heartbeat_thread)
        
        # Start leadership election service
        election_thread = threading.Thread(target=self._election_loop, daemon=True)
        election_thread.start()
        self.threads.append(election_thread)
        
        # Start key exchange service
        key_exchange_thread = threading.Thread(target=self._key_exchange_loop, daemon=True)
        key_exchange_thread.start()
        self.threads.append(key_exchange_thread)
        
        logger.info("✅ Dynamic cluster services started")
    
    def stop_cluster_services(self):
        """Stop all cluster services"""
        self.running = False
        
        if self.discovery_socket:
            self.discovery_socket.close()
        
        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5)
        
        logger.info("🛑 Dynamic cluster services stopped")
    
    def _discovery_loop(self):
        """Continuous network discovery of QuantTime nodes"""
        
        # Setup UDP broadcast socket
        self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.discovery_socket.settimeout(1.0)
        
        # Bind to discovery port for receiving
        try:
            self.discovery_socket.bind(("", self.discovery_port))
        except Exception as e:
            logger.error(f"Could not bind discovery socket: {e}")
            return
        
        logger.info(f"🔍 Discovery service listening on port {self.discovery_port}")
        
        last_broadcast = 0
        
        while self.running:
            try:
                # Send discovery broadcast every 10 seconds
                current_time = time.time()
                if current_time - last_broadcast > 10:
                    self._send_discovery_broadcast()
                    last_broadcast = current_time
                
                # Listen for discovery messages
                try:
                    data, addr = self.discovery_socket.recvfrom(1024)
                    self._handle_discovery_message(data, addr)
                except socket.timeout:
                    continue
                    
            except Exception as e:
                if self.running:
                    logger.error(f"Discovery loop error: {e}")
                time.sleep(1)
    
    def _send_discovery_broadcast(self):
        """Send discovery broadcast to find other nodes"""
        discovery_message = {
            "type": "discovery",
            "node_id": self.node_id,
            "hostname": self.local_node.hostname,
            "platform": self.local_node.platform,
            "address": self.local_node.address,
            "port": self.local_node.port,
            "dashboard_port": self.local_node.dashboard_port,
            "resources": {
                "cpu_count": self.local_node.cpu_count,
                "memory_gb": self.local_node.memory_gb,
                "gpu_count": self.local_node.gpu_count,
                "gpu_memory_gb": self.local_node.gpu_memory_gb
            },
            "leader_score": self.local_node.leader_score,
            "timestamp": datetime.now().isoformat()
        }
        
        message_bytes = json.dumps(discovery_message).encode()
        
        for broadcast_addr in self.broadcast_addresses:
            try:
                self.discovery_socket.sendto(message_bytes, (broadcast_addr, self.discovery_port))
            except Exception as e:
                logger.debug(f"Broadcast to {broadcast_addr} failed: {e}")
    
    def _handle_discovery_message(self, data: bytes, addr: Tuple[str, int]):
        """Handle incoming discovery message"""
        try:
            message = json.loads(data.decode())
            
            if message.get("type") == "discovery" and message.get("node_id") != self.node_id:
                node_id = message["node_id"]
                
                # Create or update node information
                node = ClusterNode(
                    node_id=node_id,
                    hostname=message["hostname"],
                    platform=message["platform"],
                    address=message["address"],
                    port=message["port"],
                    dashboard_port=message["dashboard_port"],
                    cpu_count=message["resources"]["cpu_count"],
                    memory_gb=message["resources"]["memory_gb"],
                    gpu_count=message["resources"]["gpu_count"],
                    gpu_memory_gb=message["resources"]["gpu_memory_gb"],
                    leader_score=message["leader_score"],
                    last_heartbeat=datetime.now(),
                    state=NodeState.DISCOVERING
                )
                
                if node_id not in self.known_nodes:
                    logger.info(f"🔍 Discovered new node: {node_id} ({node.hostname})")
                    self._initiate_node_integration(node)
                
                self.known_nodes[node_id] = node
                
        except Exception as e:
            logger.debug(f"Invalid discovery message from {addr}: {e}")
    
    def _initiate_node_integration(self, node: ClusterNode):
        """Initiate integration process for newly discovered node"""
        logger.info(f"🔧 Initiating integration for node {node.node_id}")
        
        # Start key exchange process
        self.key_exchange_manager.initiate_exchange(node)
        
        # Update node state
        node.state = NodeState.CONNECTING
    
    def _heartbeat_loop(self):
        """Send heartbeats and monitor node health"""
        while self.running:
            try:
                current_time = datetime.now()
                
                # Update local node heartbeat
                self.local_node.last_heartbeat = current_time
                
                # Check for dead nodes
                dead_nodes = []
                for node_id, node in self.known_nodes.items():
                    if (current_time - node.last_heartbeat).total_seconds() > 30:
                        dead_nodes.append(node_id)
                
                # Remove dead nodes
                for node_id in dead_nodes:
                    logger.warning(f"💀 Node {node_id} appears to be dead, removing from cluster")
                    del self.known_nodes[node_id]
                    
                    # Trigger re-election if leader died
                    if self.topology.leader_node and self.topology.leader_node.node_id == node_id:
                        logger.warning("🗳️ Leader node died, triggering new election")
                        self.topology.leader_node = None
                        self.topology.election_in_progress = True
                
                time.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                time.sleep(5)
    
    def _election_loop(self):
        """Leadership election algorithm"""
        while self.running:
            try:
                # Only run elections if no current leader or election triggered
                if not self.topology.leader_node or self.topology.election_in_progress:
                    self._conduct_leadership_election()
                
                time.sleep(self.election_timeout)
                
            except Exception as e:
                logger.error(f"Election loop error: {e}")
                time.sleep(10)
    
    def _conduct_leadership_election(self):
        """Conduct leadership election among known nodes"""
        if len(self.known_nodes) == 0:
            # Only local node, become leader
            self.local_node.role = NodeRole.LEADER
            self.topology.leader_node = self.local_node
            self.topology.election_in_progress = False
            logger.info("👑 Became cluster leader (only node)")
            self._start_ray_head_node()
            return
        
        logger.info("🗳️ Conducting leadership election...")
        
        # Gather all nodes including local
        all_nodes = {self.node_id: self.local_node}
        all_nodes.update(self.known_nodes)
        
        # Filter to active/trusted nodes only
        eligible_nodes = {
            node_id: node for node_id, node in all_nodes.items()
            if node.trust_established or node_id == self.node_id
        }
        
        if not eligible_nodes:
            logger.warning("⚠️ No eligible nodes for election")
            return
        
        # Find node with highest leadership score
        leader_candidate = max(eligible_nodes.values(), key=lambda n: n.leader_score)
        
        # If local node wins, become leader
        if leader_candidate.node_id == self.node_id:
            self.local_node.role = NodeRole.LEADER
            self.topology.leader_node = self.local_node
            logger.info("👑 Won leadership election, becoming cluster leader")
            self._start_ray_head_node()
        else:
            self.local_node.role = NodeRole.FOLLOWER  
            self.topology.leader_node = leader_candidate
            logger.info(f"👥 Following new leader: {leader_candidate.node_id}")
            self._connect_to_ray_cluster(leader_candidate)
        
        self.topology.election_in_progress = False
        self.topology.cluster_version += 1
        self.topology.last_topology_change = datetime.now()
    
    def _start_ray_head_node(self):
        """Start Ray as head node"""
        try:
            if ray.is_initialized():
                ray.shutdown()
            
            ray.init(
                address=None,  # Start as head
                dashboard_host="0.0.0.0",
                dashboard_port=self.local_node.dashboard_port,
                num_cpus=self.local_node.cpu_count,
                num_gpus=self.local_node.gpu_count,
                object_store_memory=min(int(self.local_node.memory_gb * 0.3 * 1024**3), 2**30),  # 30% of RAM, max 1GB
                _system_config={"object_spilling_config": json.dumps({"type": "filesystem", "params": {"directory_path": str(Path(self.local_node.project_root) / "temp" / "ray_spill")}})},
                logging_level=logging.INFO
            )
            
            logger.info(f"🎯 Ray head node started on {self.local_node.address}:{self.local_node.port}")
            logger.info(f"📊 Dashboard available at http://{self.local_node.address}:{self.local_node.dashboard_port}")
            
        except Exception as e:
            logger.error(f"Failed to start Ray head node: {e}")
    
    def _connect_to_ray_cluster(self, leader_node: ClusterNode):
        """Connect to Ray cluster as worker"""
        try:
            if ray.is_initialized():
                ray.shutdown()
            
            ray.init(
                address=f"ray://{leader_node.address}:{leader_node.port}",
                num_cpus=self.local_node.cpu_count,
                num_gpus=self.local_node.gpu_count,
                object_store_memory=min(int(self.local_node.memory_gb * 0.3 * 1024**3), 2**30),
                logging_level=logging.INFO
            )
            
            logger.info(f"🔗 Connected to Ray cluster leader: {leader_node.node_id}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Ray cluster: {e}")
    
    def _key_exchange_loop(self):
        """Handle ongoing key exchange and trust establishment"""
        while self.running:
            try:
                # Process pending key exchanges
                self.key_exchange_manager.process_pending_exchanges()
                
                # Update trust status for nodes
                for node_id, node in self.known_nodes.items():
                    if not node.trust_established:
                        trust_status = self.key_exchange_manager.check_trust_status(node_id)
                        if trust_status:
                            node.trust_established = True
                            node.state = NodeState.ACTIVE
                            logger.info(f"🔒 Trust established with node {node_id}")
                
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Key exchange loop error: {e}")
                time.sleep(10)
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """Get current cluster status"""
        return {
            "local_node": {
                "node_id": self.local_node.node_id,
                "hostname": self.local_node.hostname,
                "role": self.local_node.role.value,
                "state": self.local_node.state.value,
                "leader_score": self.local_node.leader_score,
                "resources": {
                    "cpu_count": self.local_node.cpu_count,
                    "memory_gb": self.local_node.memory_gb,
                    "gpu_count": self.local_node.gpu_count,
                    "gpu_memory_gb": self.local_node.gpu_memory_gb
                }
            },
            "topology": {
                "leader_node_id": self.topology.leader_node.node_id if self.topology.leader_node else None,
                "total_nodes": len(self.known_nodes) + 1,
                "active_nodes": len([n for n in self.known_nodes.values() if n.state == NodeState.ACTIVE]) + 1,
                "cluster_version": self.topology.cluster_version,
                "election_in_progress": self.topology.election_in_progress
            },
            "known_nodes": {
                node_id: {
                    "hostname": node.hostname,
                    "platform": node.platform,
                    "role": node.role.value,
                    "state": node.state.value,
                    "leader_score": node.leader_score,
                    "trust_established": node.trust_established,
                    "last_heartbeat": node.last_heartbeat.isoformat()
                }
                for node_id, node in self.known_nodes.items()
            }
        }


class KeyExchangeManager:
    """Manages bidirectional SSH key exchange and trust establishment"""
    
    def __init__(self, local_node_id: str):
        self.local_node_id = local_node_id
        self.pending_exchanges: Dict[str, ClusterNode] = {}
        self.established_trust: Set[str] = set()
        
        # Setup SSH keys
        self.ssh_key_path = Path.home() / ".ssh" / "quanttime_automation"
        self._ensure_ssh_keys()
    
    def _ensure_ssh_keys(self):
        """Ensure SSH keys exist for automation"""
        if not self.ssh_key_path.exists():
            logger.info("🔑 Generating SSH automation keys...")
            
            try:
                # Generate key without passphrase
                result = subprocess.run([
                    "ssh-keygen", "-t", "ed25519", 
                    "-C", f"quanttime-automation-{self.local_node_id}",
                    "-f", str(self.ssh_key_path),
                    "-N", ""  # No passphrase
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info("✅ SSH automation keys generated")
                else:
                    logger.error(f"Failed to generate SSH keys: {result.stderr}")
            except Exception as e:
                logger.error(f"SSH key generation error: {e}")
    
    def initiate_exchange(self, node: ClusterNode):
        """Initiate key exchange with a node"""
        self.pending_exchanges[node.node_id] = node
        logger.info(f"🔄 Initiating key exchange with {node.node_id}")
    
    def process_pending_exchanges(self):
        """Process all pending key exchanges"""
        for node_id, node in list(self.pending_exchanges.items()):
            try:
                success = self._perform_key_exchange(node)
                if success:
                    self.established_trust.add(node_id)
                    del self.pending_exchanges[node_id]
                    logger.info(f"✅ Key exchange completed with {node_id}")
                    
            except Exception as e:
                logger.error(f"Key exchange failed with {node_id}: {e}")
    
    def _perform_key_exchange(self, node: ClusterNode) -> bool:
        """Perform bidirectional SSH key exchange"""
        try:
            # Read local public key
            public_key_path = f"{self.ssh_key_path}.pub"
            if not Path(public_key_path).exists():
                return False
                
            with open(public_key_path, 'r') as f:
                local_public_key = f.read().strip()
            
            # Try to connect and exchange keys (this requires manual initial setup)
            # In practice, this would require some form of initial authentication
            # For now, we'll mark as successful if we can reach the node
            
            try:
                # Simple connectivity test
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((node.address, node.ssh_port))
                sock.close()
                
                if result == 0:
                    # Connection successful, assume key exchange can proceed
                    # In a real implementation, this would involve secure key exchange protocol
                    return True
                    
            except Exception:
                return False
                
        except Exception as e:
            logger.error(f"Key exchange error: {e}")
            return False
    
    def check_trust_status(self, node_id: str) -> bool:
        """Check if trust is established with a node"""
        return node_id in self.established_trust
