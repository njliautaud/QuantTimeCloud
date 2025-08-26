"""
QuantTime Server Configuration Script

Automated script to configure and set up the distributed computing servers.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServerConfigurator:
    """Server configuration and setup manager"""
    
    def __init__(self):
        """Initialize server configurator"""
        self.config_file = Path("server/config/servers.json")
        self.servers = self._load_server_config()
        
    def _load_server_config(self) -> Dict[str, Any]:
        """Load server configuration"""
        default_config = {
            "laptop": {
                "name": "Laptop Control Center",
                "type": "control",
                "hostname": "laptop",
                "ip_address": "laptop",
                "ssh_port": 22,
                "username": "user",
                "ssh_key_path": "~/.ssh/id_rsa",
                "roles": ["control", "light_compute"],
                "specs": {
                    "cpu_cores": 8,
                    "memory_gb": 16,
                    "disk_gb": 512
                }
            },
            "r630xl": {
                "name": "R630XL Server",
                "type": "hybrid",
                "hostname": "r630xl",
                "ip_address": "jupiter",
                "ssh_port": 22,
                "username": "quanttime",
                "ssh_key_path": "~/.ssh/id_rsa",
                "roles": ["control", "compute", "data_processing"],
                "specs": {
                    "cpu_cores": 16,
                    "memory_gb": 64,
                    "disk_gb": 2000
                }
            },
            "r810": {
                "name": "R810 Heavy Compute",
                "type": "compute",
                "hostname": "r810",
                "ip_address": "saturn",
                "ssh_port": 22,
                "username": "quanttime",
                "ssh_key_path": "~/.ssh/id_rsa",
                "roles": ["heavy_compute", "model_training"],
                "specs": {
                    "cpu_cores": 32,
                    "memory_gb": 256,
                    "disk_gb": 4000
                }
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load config file, using defaults: {e}")
        
        # Save default config
        self._save_server_config(default_config)
        return default_config
    
    def _save_server_config(self, config: Dict[str, Any]):
        """Save server configuration"""
        try:
            os.makedirs(self.config_file.parent, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved server configuration to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save server config: {e}")
    
    def setup_ssh_keys(self):
        """Set up SSH keys for all servers"""
        logger.info("🔐 Setting up SSH keys...")
        
        # Generate SSH key if it doesn't exist
        ssh_key_path = os.path.expanduser("~/.ssh/id_rsa")
        if not os.path.exists(ssh_key_path):
            logger.info("Generating SSH key pair...")
            subprocess.run([
                "ssh-keygen", "-t", "rsa", "-b", "4096",
                "-f", ssh_key_path, "-N", ""
            ], check=True)
        
        # Copy SSH key to servers
        for server_id, server_config in self.servers.items():
            if server_id == "laptop":
                continue
                
            try:
                logger.info(f"Copying SSH key to {server_id}...")
                subprocess.run([
                    "ssh-copy-id", "-i", f"{ssh_key_path}.pub",
                    f"{server_config['username']}@{server_config['ip_address']}"
                ], check=True)
                logger.info(f"✅ SSH key copied to {server_id}")
                
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to copy SSH key to {server_id}: {e}")
    
    def deploy_to_servers(self):
        """Deploy QuantTime project to all servers"""
        logger.info("🚀 Deploying QuantTime to servers...")
        
        project_root = Path(__file__).parent.parent.parent
        
        for server_id, server_config in self.servers.items():
            if server_id == "laptop":
                continue
                
            try:
                logger.info(f"Deploying to {server_id}...")
                
                # Create remote directory
                self._run_ssh_command(
                    server_config,
                    "mkdir -p /opt/quanttime"
                )
                
                # Sync project files
                subprocess.run([
                    "rsync", "-avz", "--exclude=.git", "--exclude=__pycache__",
                    "--exclude=*.pyc", "--exclude=logs", "--exclude=data",
                    str(project_root) + "/",
                    f"{server_config['username']}@{server_config['ip_address']}:/opt/quanttime/"
                ], check=True)
                
                logger.info(f"✅ Deployed to {server_id}")
                
            except Exception as e:
                logger.error(f"❌ Failed to deploy to {server_id}: {e}")
    
    def install_dependencies(self):
        """Install dependencies on all servers"""
        logger.info("📦 Installing dependencies on servers...")
        
        for server_id, server_config in self.servers.items():
            if server_id == "laptop":
                continue
                
            try:
                logger.info(f"Installing dependencies on {server_id}...")
                
                # Run installation script
                self._run_ssh_command(
                    server_config,
                    "cd /opt/quanttime && sudo bash server/setup/install.sh"
                )
                
                logger.info(f"✅ Dependencies installed on {server_id}")
                
            except Exception as e:
                logger.error(f"❌ Failed to install dependencies on {server_id}: {e}")
    
    def start_services(self):
        """Start QuantTime services on all servers"""
        logger.info("▶️ Starting QuantTime services...")
        
        for server_id, server_config in self.servers.items():
            if server_id == "laptop":
                continue
                
            try:
                logger.info(f"Starting services on {server_id}...")
                
                # Start services
                self._run_ssh_command(
                    server_config,
                    "cd /opt/quanttime && bash server/scripts/start_server.sh"
                )
                
                logger.info(f"✅ Services started on {server_id}")
                
            except Exception as e:
                logger.error(f"❌ Failed to start services on {server_id}: {e}")
    
    def check_status(self):
        """Check status of all servers"""
        logger.info("🔍 Checking server status...")
        
        for server_id, server_config in self.servers.items():
            try:
                logger.info(f"Checking {server_id}...")
                
                if server_id == "laptop":
                    logger.info(f"✅ {server_id}: Local (control center)")
                    continue
                
                # Test SSH connection
                result = subprocess.run([
                    "ssh", "-o", "ConnectTimeout=5",
                    f"{server_config['username']}@{server_config['ip_address']}",
                    "echo 'Connection test successful'"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    logger.info(f"✅ {server_id}: Online")
                    
                    # Check services
                    service_result = subprocess.run([
                        "ssh",
                        f"{server_config['username']}@{server_config['ip_address']}",
                        "systemctl is-active quanttime-*"
                    ], capture_output=True, text=True, timeout=10)
                    
                    if "active" in service_result.stdout:
                        logger.info(f"   Services: Running")
                    else:
                        logger.warning(f"   Services: Not running")
                        
                else:
                    logger.error(f"❌ {server_id}: Offline or unreachable")
                    
            except Exception as e:
                logger.error(f"❌ {server_id}: Error checking status - {e}")
    
    def _run_ssh_command(self, server_config: Dict[str, Any], command: str):
        """Run command on remote server via SSH"""
        subprocess.run([
            "ssh",
            f"{server_config['username']}@{server_config['ip_address']}",
            command
        ], check=True)
    
    def configure_networking(self):
        """Configure networking between servers"""
        logger.info("🌐 Configuring server networking...")
        
        # Generate hosts entries
        hosts_entries = []
        for server_id, server_config in self.servers.items():
            hosts_entries.append(
                f"{server_config['ip_address']} {server_config['hostname']}"
            )
        
        hosts_content = "\n".join(hosts_entries)
        
        # Update hosts file on each server
        for server_id, server_config in self.servers.items():
            if server_id == "laptop":
                continue
                
            try:
                logger.info(f"Updating hosts file on {server_id}...")
                
                # Create temporary hosts file
                temp_hosts = f"/tmp/quanttime_hosts_{server_id}"
                with open(temp_hosts, 'w') as f:
                    f.write(hosts_content)
                
                # Copy to server and append to hosts file
                subprocess.run([
                    "scp", temp_hosts,
                    f"{server_config['username']}@{server_config['ip_address']}:/tmp/quanttime_hosts"
                ], check=True)
                
                self._run_ssh_command(
                    server_config,
                    "sudo bash -c 'cat /tmp/quanttime_hosts >> /etc/hosts'"
                )
                
                # Clean up
                os.remove(temp_hosts)
                
                logger.info(f"✅ Networking configured on {server_id}")
                
            except Exception as e:
                logger.error(f"❌ Failed to configure networking on {server_id}: {e}")
    
    def full_setup(self):
        """Perform full server setup"""
        logger.info("🚀 Starting full QuantTime server setup...")
        
        try:
            # Step 1: Configure networking
            self.configure_networking()
            
            # Step 2: Set up SSH keys
            self.setup_ssh_keys()
            
            # Step 3: Deploy project
            self.deploy_to_servers()
            
            # Step 4: Install dependencies
            self.install_dependencies()
            
            # Step 5: Start services
            self.start_services()
            
            # Step 6: Check status
            self.check_status()
            
            logger.info("✅ Full server setup completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Server setup failed: {e}")
            raise

def main():
    """Main entry point"""
    configurator = ServerConfigurator()
    
    if len(sys.argv) < 2:
        print("Usage: python configure_servers.py <command>")
        print("Commands:")
        print("  setup       - Full server setup")
        print("  ssh-keys    - Set up SSH keys")
        print("  deploy      - Deploy project to servers")
        print("  install     - Install dependencies")
        print("  start       - Start services")
        print("  status      - Check server status")
        print("  networking  - Configure networking")
        return
    
    command = sys.argv[1]
    
    try:
        if command == "setup":
            configurator.full_setup()
        elif command == "ssh-keys":
            configurator.setup_ssh_keys()
        elif command == "deploy":
            configurator.deploy_to_servers()
        elif command == "install":
            configurator.install_dependencies()
        elif command == "start":
            configurator.start_services()
        elif command == "status":
            configurator.check_status()
        elif command == "networking":
            configurator.configure_networking()
        else:
            print(f"Unknown command: {command}")
            
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
