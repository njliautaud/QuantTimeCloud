#!/usr/bin/env python3
"""
QuantTime Project Synchronization Script

Automated synchronization between laptop (control center) and servers.
Handles both Git-based and file-based synchronization.
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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ProjectSync:
    def __init__(self, config_path: str = "server/config/servers.json"):
        self.config_path = config_path
        self.servers = self._load_config()
        self.project_root = Path.cwd()
        
    def _load_config(self) -> Dict:
        """Load server configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def setup_git_remotes(self) -> bool:
        """Setup Git remotes for all servers"""
        logger.info("Setting up Git remotes...")
        
        try:
            for server_name, server_config in self.servers.items():
                if server_name == 'laptop':
                    continue
                
                remote_name = f"remote-{server_name}"
                ip = server_config.get('tailscale_ip', server_config['ip_address'])
                username = server_config['username']
                remote_url = f"ssh://{username}@{ip}/opt/quanttime"
                
                # Remove existing remote if it exists
                subprocess.run(['git', 'remote', 'remove', remote_name], 
                             cwd=self.project_root, capture_output=True)
                
                # Add new remote
                result = subprocess.run(['git', 'remote', 'add', remote_name, remote_url],
                                      cwd=self.project_root, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"Failed to add remote {remote_name}: {result.stderr}")
                    return False
                else:
                    logger.info(f"Added remote: {remote_name} -> {remote_url}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up Git remotes: {e}")
            return False
    
    def push_to_servers(self, force: bool = False) -> Dict[str, bool]:
        """Push changes to all servers"""
        logger.info("Pushing changes to servers...")
        
        results = {}
        
        for server_name, server_config in self.servers.items():
            if server_name == 'laptop':
                continue
            
            try:
                remote_name = f"remote-{server_name}"
                ip = server_config.get('tailscale_ip', server_config['ip_address'])
                
                # Check if server is reachable
                if not self._ping_server(ip):
                    logger.warning(f"Server {server_name} ({ip}) is not reachable")
                    results[server_name] = False
                    continue
                
                # Push to server
                cmd = ['git', 'push', remote_name, 'main']
                if force:
                    cmd.append('--force')
                
                result = subprocess.run(cmd, cwd=self.project_root, 
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"✅ Successfully pushed to {server_name}")
                    results[server_name] = True
                else:
                    logger.error(f"❌ Failed to push to {server_name}: {result.stderr}")
                    results[server_name] = False
                
            except Exception as e:
                logger.error(f"Error pushing to {server_name}: {e}")
                results[server_name] = False
        
        return results
    
    def sync_files_to_servers(self) -> Dict[str, bool]:
        """Sync files to servers using rsync"""
        logger.info("Syncing files to servers...")
        
        results = {}
        
        for server_name, server_config in self.servers.items():
            if server_name == 'laptop':
                continue
            
            try:
                ip = server_config.get('tailscale_ip', server_config['ip_address'])
                username = server_config['username']
                
                # Check if server is reachable
                if not self._ping_server(ip):
                    logger.warning(f"Server {server_name} ({ip}) is not reachable")
                    results[server_name] = False
                    continue
                
                # Sync files using rsync
                cmd = [
                    'rsync', '-avz', '--delete',
                    '--exclude=.git',
                    '--exclude=__pycache__',
                    '--exclude=*.pyc',
                    '--exclude=.venv',
                    '--exclude=logs',
                    '--exclude=data',
                    '--exclude=models',
                    f'{self.project_root}/',
                    f'{username}@{ip}:/opt/quanttime/'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"✅ Successfully synced files to {server_name}")
                    results[server_name] = True
                else:
                    logger.error(f"❌ Failed to sync files to {server_name}: {result.stderr}")
                    results[server_name] = False
                
            except Exception as e:
                logger.error(f"Error syncing files to {server_name}: {e}")
                results[server_name] = False
        
        return results
    
    def sync_data_between_servers(self) -> Dict[str, bool]:
        """Sync data files between servers"""
        logger.info("Syncing data between servers...")
        
        results = {}
        server_names = [name for name in self.servers.keys() if name != 'laptop']
        
        if len(server_names) < 2:
            logger.info("Not enough servers for inter-server sync")
            return results
        
        # Sync between servers
        for i in range(len(server_names) - 1):
            source = server_names[i]
            target = server_names[i + 1]
            
            try:
                source_config = self.servers[source]
                target_config = self.servers[target]
                
                source_ip = source_config.get('tailscale_ip', source_config['ip_address'])
                target_ip = target_config.get('tailscale_ip', target_config['ip_address'])
                
                source_user = source_config['username']
                target_user = target_config['username']
                
                # Sync data directories
                data_dirs = ['data', 'models', 'logs', 'backtests']
                
                for data_dir in data_dirs:
                    source_path = f"{source_user}@{source_ip}:/opt/quanttime/{data_dir}/"
                    target_path = f"{target_user}@{target_ip}:/opt/quanttime/{data_dir}/"
                    
                    cmd = [
                        'rsync', '-avz', '--delete', '--exclude=*.tmp',
                        source_path, target_path
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        logger.info(f"✅ Synced {data_dir} from {source} to {target}")
                    else:
                        logger.error(f"❌ Failed to sync {data_dir} from {source} to {target}: {result.stderr}")
                
                results[f"{source}_to_{target}"] = True
                
            except Exception as e:
                logger.error(f"Error syncing from {source} to {target}: {e}")
                results[f"{source}_to_{target}"] = False
        
        return results
    
    def pull_from_servers(self) -> Dict[str, bool]:
        """Pull changes from servers (for specific files)"""
        logger.info("Pulling changes from servers...")
        
        results = {}
        
        for server_name, server_config in self.servers.items():
            if server_name == 'laptop':
                continue
            
            try:
                ip = server_config.get('tailscale_ip', server_config['ip_address'])
                username = server_config['username']
                
                # Check if server is reachable
                if not self._ping_server(ip):
                    logger.warning(f"Server {server_name} ({ip}) is not reachable")
                    results[server_name] = False
                    continue
                
                # Pull specific directories that might have been modified on servers
                pull_dirs = ['data', 'models', 'logs', 'backtests']
                
                for pull_dir in pull_dirs:
                    remote_path = f"{username}@{ip}:/opt/quanttime/{pull_dir}/"
                    local_path = f"{self.project_root}/{pull_dir}/"
                    
                    # Create local directory if it doesn't exist
                    Path(local_path).mkdir(parents=True, exist_ok=True)
                    
                    cmd = [
                        'rsync', '-avz', '--update',
                        remote_path, local_path
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        logger.info(f"✅ Pulled {pull_dir} from {server_name}")
                    else:
                        logger.error(f"❌ Failed to pull {pull_dir} from {server_name}: {result.stderr}")
                
                results[server_name] = True
                
            except Exception as e:
                logger.error(f"Error pulling from {server_name}: {e}")
                results[server_name] = False
        
        return results
    
    def _ping_server(self, ip: str) -> bool:
        """Ping server to check connectivity"""
        try:
            result = subprocess.run(['ping', '-n', '1', ip], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def get_sync_status(self) -> Dict:
        """Get sync status for all servers"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'servers': {}
        }
        
        for server_name, server_config in self.servers.items():
            if server_name == 'laptop':
                continue
            
            ip = server_config.get('tailscale_ip', server_config['ip_address'])
            
            server_status = {
                'reachable': self._ping_server(ip),
                'last_check': datetime.now().isoformat(),
                'services': {}
            }
            
            # Check services if reachable
            if server_status['reachable']:
                try:
                    username = server_config['username']
                    services = ['quanttime-api-server', 'quanttime-celery-worker', 'redis-server']
                    
                    for service in services:
                        cmd = f"ssh {username}@{ip} 'systemctl is-active {service}'"
                        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                        server_status['services'][service] = result.stdout.strip()
                        
                except Exception as e:
                    logger.error(f"Error checking services on {server_name}: {e}")
            
            status['servers'][server_name] = server_status
        
        return status
    
    def full_sync(self, force: bool = False) -> Dict:
        """Perform full synchronization"""
        logger.info("Starting full synchronization...")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'git_setup': False,
            'git_push': {},
            'file_sync': {},
            'data_sync': {},
            'status': {}
        }
        
        # 1. Setup Git remotes
        results['git_setup'] = self.setup_git_remotes()
        
        # 2. Push code changes
        results['git_push'] = self.push_to_servers(force=force)
        
        # 3. Sync files
        results['file_sync'] = self.sync_files_to_servers()
        
        # 4. Sync data between servers
        results['data_sync'] = self.sync_data_between_servers()
        
        # 5. Get final status
        results['status'] = self.get_sync_status()
        
        # Log results
        logger.info("Full sync completed:")
        logger.info(f"  Git setup: {results['git_setup']}")
        logger.info(f"  Git push: {sum(results['git_push'].values())}/{len(results['git_push'])} successful")
        logger.info(f"  File sync: {sum(results['file_sync'].values())}/{len(results['file_sync'])} successful")
        
        return results

def main():
    parser = argparse.ArgumentParser(description='QuantTime Project Synchronization')
    parser.add_argument('--action', choices=['setup', 'push', 'sync', 'pull', 'status', 'full'], 
                       default='full', help='Sync action to perform')
    parser.add_argument('--force', action='store_true', help='Force push changes')
    parser.add_argument('--config', default='server/config/servers.json', 
                       help='Path to server configuration')
    
    args = parser.parse_args()
    
    # Create logs directory
    Path('logs').mkdir(exist_ok=True)
    
    # Initialize sync manager
    sync = ProjectSync(args.config)
    
    if args.action == 'setup':
        success = sync.setup_git_remotes()
        sys.exit(0 if success else 1)
    
    elif args.action == 'push':
        results = sync.push_to_servers(force=args.force)
        success = all(results.values())
        sys.exit(0 if success else 1)
    
    elif args.action == 'sync':
        results = sync.sync_files_to_servers()
        success = all(results.values())
        sys.exit(0 if success else 1)
    
    elif args.action == 'pull':
        results = sync.pull_from_servers()
        success = all(results.values())
        sys.exit(0 if success else 1)
    
    elif args.action == 'status':
        status = sync.get_sync_status()
        print(json.dumps(status, indent=2))
        sys.exit(0)
    
    elif args.action == 'full':
        results = sync.full_sync(force=args.force)
        print(json.dumps(results, indent=2))
        success = results['git_setup'] and all(results['git_push'].values())
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
