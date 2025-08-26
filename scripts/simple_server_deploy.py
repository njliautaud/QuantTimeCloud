#!/usr/bin/env python3
"""
Simple deployment script to set up QuantTime on R630XL server.
This script will SSH into the server and clone the repository.
"""

import subprocess
import json
import sys
from pathlib import Path

def load_server_config():
    """Load server configuration."""
    config_path = Path("server/config/servers.json")
    if not config_path.exists():
        print("❌ Server config not found: server/config/servers.json")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        return json.load(f)

def run_ssh_command(username: str, ip_address: str, command: str, description: str = ""):
    """Run a command on the server via SSH."""
    if description:
        print(f"🔄 {description}")
    
    ssh_cmd = f'ssh {username}@{ip_address} "{command}"'
    print(f"   Running: {ssh_cmd}")
    
    result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print(f"   📤 Output: {result.stdout.strip()}")
    if result.stderr:
        print(f"   ⚠️  Stderr: {result.stderr.strip()}")
    
    if result.returncode != 0:
        print(f"   ❌ Command failed with return code {result.returncode}")
        return False
    
    return True

def get_github_url():
    """Get the GitHub repository URL."""
    try:
        result = subprocess.run(["git", "remote", "get-url", "origin"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    
    # Fallback: ask user
    print("🔍 Could not detect GitHub URL automatically.")
    github_url = input("Please enter your GitHub repository URL: ").strip()
    if not github_url:
        print("❌ GitHub URL is required for deployment.")
        sys.exit(1)
    
    return github_url

def main():
    """Main deployment function."""
    print("🚀 Simple QuantTime Server Deployment")
    print("=" * 50)
    
    # Load server configuration
    server_config = load_server_config()
    server_name = "r630xl"
    server = server_config.get(server_name)
    
    if not server:
        print(f"❌ Server '{server_name}' not found in config")
        sys.exit(1)
    
    username = server.get('username', 'quanttime')
    ip_address = server.get('tailscale_ip') or server.get('ip_address')
    
    if not ip_address:
        print(f"❌ No IP address found for server {server_name}")
        sys.exit(1)
    
    print(f"🎯 Deploying to {server_name.upper()} ({ip_address})")
    print("-" * 40)
    
    # Test SSH connection
    print("🔍 Testing SSH connection...")
    if not run_ssh_command(username, ip_address, "echo 'SSH connection successful'", "Testing SSH connection"):
        print("❌ SSH connection failed. Please check:")
        print("   1. SSH key is properly set up")
        print("   2. Server is accessible via Tailscale")
        print("   3. Username and IP are correct")
        sys.exit(1)
    
    # Get GitHub URL
    github_url = get_github_url()
    print(f"📦 Using GitHub URL: {github_url}")
    
    # Check if project already exists on server
    print("🔍 Checking if project already exists on server...")
    if run_ssh_command(username, ip_address, "test -d /opt/quanttime", "Checking if /opt/quanttime exists"):
        print("⚠️  Project directory already exists on server.")
        response = input("Do you want to remove it and start fresh? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            run_ssh_command(username, ip_address, "rm -rf /opt/quanttime", "Removing existing project directory")
        else:
            print("❌ Deployment cancelled.")
            sys.exit(1)
    
    # Create directory and clone repository
    print("📂 Setting up project directory...")
    commands = [
        ("mkdir -p /opt", "Creating /opt directory"),
        ("cd /opt && git clone " + github_url + " quanttime", "Cloning repository"),
        ("cd /opt/quanttime && git status", "Verifying repository"),
    ]
    
    for command, description in commands:
        if not run_ssh_command(username, ip_address, command, description):
            print(f"❌ Failed to {description.lower()}")
            sys.exit(1)
    
    # Install Python dependencies
    print("📦 Installing Python dependencies...")
    if not run_ssh_command(username, ip_address, 
                          "cd /opt/quanttime && pip install -r requirements.txt", 
                          "Installing Python dependencies"):
        print("❌ Failed to install dependencies")
        sys.exit(1)
    
    # Set up auto-pull script
    print("🔧 Setting up auto-pull script...")
    auto_pull_script = '''#!/bin/bash
cd /opt/quanttime
git stash -u
git pull origin main
git stash pop
if git diff --name-only HEAD~1 HEAD | grep -q "requirements.txt"; then
    echo "📦 Requirements.txt changed, updating dependencies..."
    pip install -r requirements.txt
fi
echo "✅ Code updated successfully!"
'''
    
    # Write auto-pull script to server
    run_ssh_command(username, ip_address, 
                   f'echo \'{auto_pull_script}\' > /opt/quanttime/auto_pull.sh', 
                   "Creating auto-pull script")
    
    run_ssh_command(username, ip_address, 
                   "chmod +x /opt/quanttime/auto_pull.sh", 
                   "Making auto-pull script executable")
    
    # Test the deployment
    print("🧪 Testing deployment...")
    if not run_ssh_command(username, ip_address, 
                          "cd /opt/quanttime && python -c \"import quanttime; print('✅ Deployment successful!')\"", 
                          "Testing Python import"):
        print("❌ Deployment test failed")
        sys.exit(1)
    
    print(f"\n🎉 Successfully deployed to {server_name}!")
    print("\n📋 Next steps:")
    print("1. SSH into server: ssh quanttime@jupiter")
    print("2. Navigate to project: cd /opt/quanttime")
    print("3. Run auto-pull to update: ./auto_pull.sh")
    print("4. Start the application: python run.py")
    print("\n🔄 For future updates:")
    print("   - Make changes on your laptop")
    print("   - Commit and push to GitHub")
    print("   - SSH to server and run: ./auto_pull.sh")
    print("   - Or use the SYNC button in the dashboard for data/models")

if __name__ == "__main__":
    main()
