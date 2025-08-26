#!/usr/bin/env python3
"""
Deploy QuantTime codebase to R630XL server via Git.
This script sets up Git remotes and deploys only the codebase (excluding data/models).
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

def load_server_config() -> Dict:
    """Load server configuration."""
    config_path = Path("server/config/servers.json")
    if not config_path.exists():
        print("❌ Server config not found: server/config/servers.json")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        return json.load(f)

def run_command(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"🔄 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    
    if result.stdout:
        print(f"📤 Output: {result.stdout.strip()}")
    if result.stderr:
        print(f"⚠️  Stderr: {result.stderr.strip()}")
    
    if check and result.returncode != 0:
        print(f"❌ Command failed with return code {result.returncode}")
        sys.exit(1)
    
    return result

def check_git_status() -> bool:
    """Check if we're in a git repository and if there are changes."""
    try:
        # Check if we're in a git repo
        result = run_command(["git", "status"], check=False)
        if result.returncode != 0:
            print("❌ Not in a git repository. Please initialize git first.")
            return False
        
        # Check for uncommitted changes
        result = run_command(["git", "diff", "--quiet"], check=False)
        if result.returncode != 0:
            print("⚠️  You have uncommitted changes. Please commit or stash them first.")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Error checking git status: {e}")
        return False

def setup_git_remote(server_name: str, server_config: Dict) -> bool:
    """Set up Git remote for the server."""
    try:
        # Get server details
        server = server_config.get(server_name)
        if not server:
            print(f"❌ Server '{server_name}' not found in config")
            return False
        
        username = server.get('username', 'quanttime')
        ip_address = server.get('tailscale_ip') or server.get('ip_address')
        
        if not ip_address:
            print(f"❌ No IP address found for server {server_name}")
            return False
        
        remote_name = f"remote-{server_name}"
        remote_url = f"ssh://{username}@{ip_address}/opt/quanttime"
        
        print(f"🔧 Setting up Git remote '{remote_name}' for {server_name}")
        print(f"   URL: {remote_url}")
        
        # Remove existing remote if it exists
        run_command(["git", "remote", "remove", remote_name], check=False)
        
        # Add new remote
        run_command(["git", "remote", "add", remote_name, remote_url])
        
        # Test the remote connection
        print(f"🔍 Testing connection to {server_name}...")
        test_result = run_command(["git", "ls-remote", remote_name], check=False)
        
        if test_result.returncode == 0:
            print(f"✅ Successfully connected to {server_name}")
            return True
        else:
            print(f"❌ Failed to connect to {server_name}")
            print("   Make sure:")
            print("   1. SSH key is properly set up")
            print("   2. Server is accessible via Tailscale")
            print("   3. Git repository exists on server")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up Git remote: {e}")
        return False

def deploy_to_server(server_name: str, server_config: Dict) -> bool:
    """Deploy codebase to server via Git push."""
    try:
        server = server_config.get(server_name)
        if not server:
            print(f"❌ Server '{server_name}' not found in config")
            return False
        
        remote_name = f"remote-{server_name}"
        
        print(f"🚀 Deploying to {server_name}...")
        
        # Get current branch
        branch_result = run_command(["git", "branch", "--show-current"])
        current_branch = branch_result.stdout.strip()
        
        print(f"📦 Pushing branch '{current_branch}' to {server_name}...")
        
        # Push to server
        run_command(["git", "push", remote_name, f"{current_branch}:main", "--force"])
        
        print(f"✅ Successfully deployed to {server_name}")
        return True
        
    except Exception as e:
        print(f"❌ Error deploying to server: {e}")
        return False

def setup_server_repository(server_name: str, server_config: Dict) -> bool:
    """Set up the Git repository on the server."""
    try:
        server = server_config.get(server_name)
        if not server:
            print(f"❌ Server '{server_name}' not found in config")
            return False
        
        username = server.get('username', 'quanttime')
        ip_address = server.get('tailscale_ip') or server.get('ip_address')
        
        if not ip_address:
            print(f"❌ No IP address found for server {server_name}")
            return False
        
        print(f"🔧 Setting up Git repository on {server_name}...")
        
        # Create the directory structure on server
        setup_commands = [
            f"ssh {username}@{ip_address} 'mkdir -p /opt/quanttime'",
            f"ssh {username}@{ip_address} 'cd /opt/quanttime && git init --bare'",
            f"ssh {username}@{ip_address} 'cd /opt/quanttime && git config --bool core.bare false'",
            f"ssh {username}@{ip_address} 'cd /opt/quanttime && git config receive.denyCurrentBranch updateInstead'"
        ]
        
        for cmd in setup_commands:
            print(f"🔄 Running: {cmd}")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"⚠️  Command failed: {result.stderr.strip()}")
                # Continue anyway, might already be set up
        
        print(f"✅ Server repository setup complete for {server_name}")
        return True
        
    except Exception as e:
        print(f"❌ Error setting up server repository: {e}")
        return False

def main():
    """Main deployment function."""
    print("🚀 QuantTime Server Deployment")
    print("=" * 50)
    
    # Load server configuration
    server_config = load_server_config()
    
    # Check git status
    if not check_git_status():
        return
    
    # Deploy to R630XL
    server_name = "r630xl"
    
    print(f"\n🎯 Deploying to {server_name.upper()}")
    print("-" * 30)
    
    # Set up server repository
    if not setup_server_repository(server_name, server_config):
        print("❌ Failed to set up server repository")
        return
    
    # Set up Git remote
    if not setup_git_remote(server_name, server_config):
        print("❌ Failed to set up Git remote")
        return
    
    # Deploy codebase
    if not deploy_to_server(server_name, server_config):
        print("❌ Failed to deploy to server")
        return
    
    print(f"\n🎉 Successfully deployed to {server_name}!")
    print("\n📋 Next steps:")
    print("1. SSH into the server: ssh quanttime@jupiter")
    print("2. Navigate to: cd /opt/quanttime")
    print("3. Install dependencies: pip install -r requirements.txt")
    print("4. Run setup script: python server/setup/quick_deploy.sh")
    print("5. Test the deployment: python -c \"import quanttime; print('✅ Deployment successful!')\"")

if __name__ == "__main__":
    main()
