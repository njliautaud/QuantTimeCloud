#!/usr/bin/env python3
"""
QuantTime Syncthing Setup Script

Automated setup and configuration of Syncthing across all nodes:
- Laptop (Control Center)
- R630XL (Hybrid Server)  
- R810 (Heavy Compute)

Integrates with existing Tailscale network and Ray Tune infrastructure.
"""

import os
import sys
import json
import time
import subprocess
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/syncthing_setup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SyncthingSetup:
    def __init__(self, config_path: str = "server/config/servers.json"):
        self.config_path = config_path
        self.servers = self._load_config()
        self.project_root = Path.cwd()
        
        # Syncthing configuration
        self.syncthing_config = {
            "folders": {
                "quanttime-project": {
                    "id": "quanttime-project",
                    "label": "QuantTime Project",
                    "path": "/opt/quanttime",
                    "type": "sendreceive",
                    "devices": ["laptop", "r630xl", "r810"],
                    "versioning": {
                        "type": "simple",
                        "params": {
                            "keep": "10"
                        }
                    },
                    "ignorePerms": False,
                    "autoNormalize": True,
                    "minDiskFree": {
                        "unit": "GB",
                        "value": 1
                    }
                },
                "quanttime-data": {
                    "id": "quanttime-data", 
                    "label": "QuantTime Data",
                    "path": "/opt/quanttime/data",
                    "type": "sendreceive",
                    "devices": ["laptop", "r630xl", "r810"],
                    "versioning": {
                        "type": "simple",
                        "params": {
                            "keep": "5"
                        }
                    },
                    "ignorePerms": False,
                    "autoNormalize": True,
                    "minDiskFree": {
                        "unit": "GB", 
                        "value": 10
                    }
                },
                "quanttime-models": {
                    "id": "quanttime-models",
                    "label": "QuantTime Models",
                    "path": "/opt/quanttime/models",
                    "type": "sendreceive", 
                    "devices": ["laptop", "r630xl", "r810"],
                    "versioning": {
                        "type": "simple",
                        "params": {
                            "keep": "5"
                        }
                    },
                    "ignorePerms": False,
                    "autoNormalize": True,
                    "minDiskFree": {
                        "unit": "GB",
                        "value": 5
                    }
                }
            },
            "devices": {
                "laptop": {
                    "deviceID": "LAPTOP-DEVICE-ID",
                    "name": "Laptop Control Center",
                    "addresses": ["dynamic"],
                    "compression": "metadata",
                    "certName": "",
                    "introducer": False,
                    "skipIntroductionRemovals": False,
                    "introducedBy": "",
                    "paused": False,
                    "allowedNetworks": [],
                    "autoAcceptFolders": False,
                    "maxSendKbps": 0,
                    "maxRecvKbps": 0,
                    "ignoredFolders": [],
                    "pendingFolders": [],
                    "maxRequestKiB": 0
                },
                "r630xl": {
                    "deviceID": "R630XL-DEVICE-ID", 
                    "name": "R630XL Server",
                    "addresses": ["dynamic"],
                    "compression": "metadata",
                    "certName": "",
                    "introducer": False,
                    "skipIntroductionRemovals": False,
                    "introducedBy": "",
                    "paused": False,
                    "allowedNetworks": [],
                    "autoAcceptFolders": False,
                    "maxSendKbps": 0,
                    "maxRecvKbps": 0,
                    "ignoredFolders": [],
                    "pendingFolders": [],
                    "maxRequestKiB": 0
                },
                "r810": {
                    "deviceID": "R810-DEVICE-ID",
                    "name": "R810 Heavy Compute", 
                    "addresses": ["dynamic"],
                    "compression": "metadata",
                    "certName": "",
                    "introducer": False,
                    "skipIntroductionRemovals": False,
                    "introducedBy": "",
                    "paused": False,
                    "allowedNetworks": [],
                    "autoAcceptFolders": False,
                    "maxSendKbps": 0,
                    "maxRecvKbps": 0,
                    "ignoredFolders": [],
                    "pendingFolders": [],
                    "maxRequestKiB": 0
                }
            }
        }
        
    def _load_config(self) -> Dict:
        """Load server configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def install_syncthing_on_server(self, server_name: str) -> bool:
        """Install Syncthing on a specific server"""
        server_config = self.servers.get(server_name)
        if not server_config:
            logger.error(f"Server {server_name} not found in config")
            return False
        
        try:
            ip = server_config.get('tailscale_ip', server_config['ip_address'])
            username = server_config['username']
            
            logger.info(f"Installing Syncthing on {server_name} ({ip})...")
            
            # Install Syncthing via SSH
            install_commands = [
                # Add Syncthing repository
                "curl -s https://syncthing.net/release-key.txt | sudo apt-key add -",
                "echo 'deb https://apt.syncthing.net/ syncthing stable' | sudo tee /etc/apt/sources.list.d/syncthing.list",
                
                # Update and install
                "sudo apt-get update",
                "sudo apt-get install -y syncthing",
                
                # Create systemd service
                "sudo systemctl enable syncthing@quanttime",
                "sudo systemctl start syncthing@quanttime",
                
                # Create project directory
                "sudo mkdir -p /opt/quanttime",
                f"sudo chown {username}:{username} /opt/quanttime",
                
                # Create data directories
                "mkdir -p /opt/quanttime/data",
                "mkdir -p /opt/quanttime/models", 
                "mkdir -p /opt/quanttime/logs",
                "mkdir -p /opt/quanttime/config"
            ]
            
            for cmd in install_commands:
                ssh_cmd = f"ssh {username}@{ip} '{cmd}'"
                result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"Failed to run command on {server_name}: {cmd}")
                    logger.error(f"Error: {result.stderr}")
                    return False
                else:
                    logger.info(f"✅ Successfully ran: {cmd}")
            
            logger.info(f"✅ Syncthing installed on {server_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error installing Syncthing on {server_name}: {e}")
            return False
    
    def get_syncthing_device_id(self, server_name: str) -> Optional[str]:
        """Get Syncthing device ID from a server"""
        server_config = self.servers.get(server_name)
        if not server_config:
            return None
        
        try:
            ip = server_config.get('tailscale_ip', server_config['ip_address'])
            username = server_config['username']
            
            # Get device ID from Syncthing config
            cmd = f"ssh {username}@{ip} 'cat ~/.config/syncthing/config.xml | grep -o \"device id=\\\"[^\\\"]*\\\"\" | head -1 | cut -d\\\" -f2'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                device_id = result.stdout.strip()
                logger.info(f"Found device ID for {server_name}: {device_id}")
                return device_id
            else:
                logger.warning(f"Could not get device ID for {server_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting device ID for {server_name}: {e}")
            return None
    
    def configure_syncthing_folders(self, server_name: str) -> bool:
        """Configure Syncthing folders on a server"""
        server_config = self.servers.get(server_name)
        if not server_config:
            return False
        
        try:
            ip = server_config.get('tailscale_ip', server_config['ip_address'])
            username = server_config['username']
            
            logger.info(f"Configuring Syncthing folders on {server_name}...")
            
            # Create folder configuration
            folder_config = {
                "folders": list(self.syncthing_config["folders"].values()),
                "devices": list(self.syncthing_config["devices"].values())
            }
            
            # Write config to temporary file
            config_file = f"/tmp/syncthing_config_{server_name}.json"
            with open(config_file, 'w') as f:
                json.dump(folder_config, f, indent=2)
            
            # Upload and apply config
            upload_cmd = f"scp {config_file} {username}@{ip}:/tmp/syncthing_config.json"
            result = subprocess.run(upload_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to upload config to {server_name}")
                return False
            
            # Apply configuration via Syncthing API
            apply_cmd = f"""ssh {username}@{ip} '
                # Wait for Syncthing to start
                sleep 10
                
                # Apply folder configuration
                curl -X POST http://localhost:8384/rest/config/folders \
                    -H "Content-Type: application/json" \
                    -d @/tmp/syncthing_config.json
                
                # Restart Syncthing to apply changes
                sudo systemctl restart syncthing@{username}
            '"""
            
            result = subprocess.run(apply_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"✅ Syncthing folders configured on {server_name}")
                return True
            else:
                logger.error(f"Failed to configure folders on {server_name}: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error configuring Syncthing on {server_name}: {e}")
            return False
    
    def setup_syncthing_web_interface(self, server_name: str) -> bool:
        """Setup Syncthing web interface access"""
        server_config = self.servers.get(server_name)
        if not server_config:
            return False
        
        try:
            ip = server_config.get('tailscale_ip', server_config['ip_address'])
            username = server_config['username']
            
            logger.info(f"Setting up Syncthing web interface on {server_name}...")
            
            # Configure web interface
            web_config_commands = [
                # Enable web interface
                f"ssh {username}@{ip} 'sed -i \"s/<address>127.0.0.1:8384<\\/address>/<address>0.0.0.0:8384<\\/address>/g\" ~/.config/syncthing/config.xml'",
                
                # Restart Syncthing
                f"ssh {username}@{ip} 'sudo systemctl restart syncthing@{username}'",
                
                # Wait for restart
                "sleep 10"
            ]
            
            for cmd in web_config_commands:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"Command failed: {cmd}")
            
            # Test web interface
            web_url = f"http://{ip}:8384"
            try:
                response = requests.get(web_url, timeout=10)
                if response.status_code == 200:
                    logger.info(f"✅ Syncthing web interface accessible at {web_url}")
                    return True
                else:
                    logger.warning(f"Web interface returned status {response.status_code}")
                    return False
            except Exception as e:
                logger.warning(f"Could not access web interface: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting up web interface on {server_name}: {e}")
            return False
    
    def create_syncthing_config_file(self) -> bool:
        """Create Syncthing configuration file for QuantTime"""
        try:
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)
            
            # Update device IDs with actual values
            for server_name in ["laptop", "r630xl", "r810"]:
                device_id = self.get_syncthing_device_id(server_name)
                if device_id:
                    self.syncthing_config["devices"][server_name]["deviceID"] = device_id
            
            # Create configuration file
            config_file = config_dir / "syncthing_config.json"
            with open(config_file, 'w') as f:
                json.dump(self.syncthing_config, f, indent=2)
            
            logger.info(f"✅ Created Syncthing config: {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating config file: {e}")
            return False
    
    def setup_local_syncthing(self) -> bool:
        """Setup Syncthing on local machine (laptop)"""
        try:
            logger.info("Setting up Syncthing on local machine...")
            
            # Check if Syncthing is installed
            result = subprocess.run(["syncthing", "--version"], capture_output=True, text=True)
            if result.returncode != 0:
                logger.info("Installing Syncthing on local machine...")
                
                # Install Syncthing (Ubuntu/Debian)
                install_commands = [
                    "curl -s https://syncthing.net/release-key.txt | sudo apt-key add -",
                    "echo 'deb https://apt.syncthing.net/ syncthing stable' | sudo tee /etc/apt/sources.list.d/syncthing.list",
                    "sudo apt-get update",
                    "sudo apt-get install -y syncthing"
                ]
                
                for cmd in install_commands:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.error(f"Failed to install Syncthing locally: {cmd}")
                        return False
            
            # Create project directory
            project_dir = Path("/opt/quanttime")
            project_dir.mkdir(parents=True, exist_ok=True)
            
            # Create data directories
            (project_dir / "data").mkdir(exist_ok=True)
            (project_dir / "models").mkdir(exist_ok=True)
            (project_dir / "logs").mkdir(exist_ok=True)
            (project_dir / "config").mkdir(exist_ok=True)
            
            # Start Syncthing
            subprocess.run(["syncthing"], start_new_session=True)
            
            logger.info("✅ Local Syncthing setup complete")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up local Syncthing: {e}")
            return False
    
    def test_syncthing_connection(self) -> Dict[str, bool]:
        """Test Syncthing connections between all nodes"""
        results = {}
        
        for server_name in self.servers.keys():
            if server_name == "laptop":
                continue
                
            server_config = self.servers[server_name]
            ip = server_config.get('tailscale_ip', server_config['ip_address'])
            
            try:
                # Test web interface
                web_url = f"http://{ip}:8384"
                response = requests.get(web_url, timeout=10)
                results[server_name] = response.status_code == 200
                
                if results[server_name]:
                    logger.info(f"✅ {server_name} Syncthing accessible")
                else:
                    logger.warning(f"⚠️ {server_name} Syncthing not accessible")
                    
            except Exception as e:
                logger.error(f"❌ {server_name} Syncthing connection failed: {e}")
                results[server_name] = False
        
        return results
    
    def full_setup(self) -> Dict:
        """Perform complete Syncthing setup"""
        logger.info("🚀 Starting complete Syncthing setup...")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'local_setup': False,
            'server_setups': {},
            'config_created': False,
            'connections_tested': {},
            'overall_success': False
        }
        
        # 1. Setup local Syncthing
        logger.info("📱 Setting up local Syncthing...")
        results['local_setup'] = self.setup_local_syncthing()
        
        # 2. Setup servers
        for server_name in ["r630xl", "r810"]:
            logger.info(f"🖥️ Setting up {server_name}...")
            
            server_results = {
                'installed': False,
                'configured': False,
                'web_interface': False
            }
            
            # Install Syncthing
            server_results['installed'] = self.install_syncthing_on_server(server_name)
            
            if server_results['installed']:
                # Configure folders
                server_results['configured'] = self.configure_syncthing_folders(server_name)
                
                # Setup web interface
                server_results['web_interface'] = self.setup_syncthing_web_interface(server_name)
            
            results['server_setups'][server_name] = server_results
        
        # 3. Create configuration file
        logger.info("📝 Creating configuration file...")
        results['config_created'] = self.create_syncthing_config_file()
        
        # 4. Test connections
        logger.info("🔍 Testing connections...")
        results['connections_tested'] = self.test_syncthing_connection()
        
        # 5. Overall success
        results['overall_success'] = (
            results['local_setup'] and
            all(setup['installed'] for setup in results['server_setups'].values()) and
            results['config_created']
        )
        
        # Log results
        logger.info("📊 Setup Results:")
        logger.info(f"  Local setup: {results['local_setup']}")
        for server, setup in results['server_setups'].items():
            logger.info(f"  {server}: installed={setup['installed']}, configured={setup['configured']}, web={setup['web_interface']}")
        logger.info(f"  Config created: {results['config_created']}")
        logger.info(f"  Overall success: {results['overall_success']}")
        
        return results

def main():
    parser = argparse.ArgumentParser(description='QuantTime Syncthing Setup')
    parser.add_argument('--action', choices=['full', 'local', 'servers', 'test'], 
                       default='full', help='Setup action to perform')
    parser.add_argument('--server', choices=['r630xl', 'r810'], 
                       help='Specific server to setup')
    parser.add_argument('--config', default='server/config/servers.json', 
                       help='Path to server configuration')
    
    args = parser.parse_args()
    
    # Create logs directory
    Path('logs').mkdir(exist_ok=True)
    
    # Initialize setup
    setup = SyncthingSetup(args.config)
    
    if args.action == 'full':
        results = setup.full_setup()
        print(json.dumps(results, indent=2))
        sys.exit(0 if results['overall_success'] else 1)
    
    elif args.action == 'local':
        success = setup.setup_local_syncthing()
        sys.exit(0 if success else 1)
    
    elif args.action == 'servers':
        if args.server:
            success = setup.install_syncthing_on_server(args.server)
            sys.exit(0 if success else 1)
        else:
            for server in ['r630xl', 'r810']:
                setup.install_syncthing_on_server(server)
    
    elif args.action == 'test':
        results = setup.test_syncthing_connection()
        print(json.dumps(results, indent=2))
        sys.exit(0 if all(results.values()) else 1)

if __name__ == "__main__":
    main()
