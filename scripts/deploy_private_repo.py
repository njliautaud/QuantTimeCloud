#!/usr/bin/env python3
"""
Deploy private QuantTime repository to R630XL server.
Handles private repository authentication via SSH keys or personal access tokens.
"""

import subprocess
import json
import sys
import os
from pathlib import Path

def read_settings():
    """Read settings from settings.txt."""
    settings = {}
    try:
        with open('settings.txt', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    settings[key] = value
    except FileNotFoundError:
        print("❌ settings.txt not found")
        sys.exit(1)
    return settings

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

def run_ssh_command_with_password(username: str, ip_address: str, password: str, command: str):
    """Run SSH command with password using paramiko."""
    try:
        import paramiko
        
        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        print(f"🔄 Running: {command}")
        
        # Connect to server
        ssh.connect(ip_address, username=username, password=password, timeout=10)
        
        # Execute command
        stdin, stdout, stderr = ssh.exec_command(command)
        
        # Get output
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        if output:
            print(f"   📤 Output: {output}")
        if error:
            print(f"   ⚠️  Stderr: {error}")
        
        ssh.close()
        return True
        
    except Exception as e:
        print(f"   ❌ SSH command failed: {e}")
        return False

def setup_github_ssh_on_server(username: str, ip_address: str, password: str):
    """Set up GitHub SSH authentication on the server."""
    print("🔑 Setting up GitHub SSH authentication on server...")
    
    # Check if SSH key exists on server
    if not run_ssh_command_with_password(username, ip_address, password, "test -f ~/.ssh/id_rsa"):
        print("📋 Generating SSH key on server...")
        if not run_ssh_command_with_password(username, ip_address, password, 
                                           "ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ''"):
            print("❌ Failed to generate SSH key on server")
            return False
    
    # Get the public key from server
    if not run_ssh_command_with_password(username, ip_address, password, 
                                       "cat ~/.ssh/id_rsa.pub"):
        print("❌ Failed to read SSH public key from server")
        return False
    
    print("\n📋 Next steps:")
    print("1. Copy the SSH public key above")
    print("2. Go to GitHub.com → Settings → SSH and GPG keys")
    print("3. Click 'New SSH key'")
    print("4. Paste the public key and save")
    print("5. Press Enter when done...")
    
    input("Press Enter to continue...")
    
    # Test GitHub SSH connection
    print("🧪 Testing GitHub SSH connection...")
    if not run_ssh_command_with_password(username, ip_address, password, 
                                       "ssh -T git@github.com"):
        print("❌ GitHub SSH connection failed")
        print("   Make sure you added the SSH key to your GitHub account")
        return False
    
    print("✅ GitHub SSH authentication working!")
    return True

def setup_github_token_on_server(username: str, ip_address: str, password: str):
    """Set up GitHub personal access token on the server."""
    print("🔑 Setting up GitHub personal access token...")
    
    # Ask for GitHub token
    github_token = input("Please enter your GitHub personal access token: ").strip()
    if not github_token:
        print("❌ GitHub token is required")
        return False
    
    # Configure git to use token
    commands = [
        f"git config --global credential.helper store",
        f"echo 'https://{github_token}@github.com' > ~/.git-credentials",
        f"chmod 600 ~/.git-credentials"
    ]
    
    for cmd in commands:
        if not run_ssh_command_with_password(username, ip_address, password, cmd):
            print(f"❌ Failed to run: {cmd}")
            return False
    
    print("✅ GitHub token authentication configured!")
    return True

def deploy_repository(username: str, ip_address: str, password: str, github_url: str):
    """Deploy the repository to the server."""
    print("📦 Deploying repository to server...")
    
    # Check if project already exists
    if run_ssh_command_with_password(username, ip_address, password, "test -d /opt/quanttime"):
        print("⚠️  Project directory already exists on server.")
        response = input("Do you want to remove it and start fresh? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            run_ssh_command_with_password(username, ip_address, password, "rm -rf /opt/quanttime")
        else:
            print("❌ Deployment cancelled.")
            return False
    
    # Create directory and clone repository
    commands = [
        "sudo mkdir -p /opt",
        "sudo chown quanttime:quanttime /opt",
        f"cd /opt && git clone {github_url} quanttime",
        "cd /opt/quanttime && git status"
    ]
    
    for cmd in commands:
        if not run_ssh_command_with_password(username, ip_address, password, cmd):
            print(f"❌ Failed to run: {cmd}")
            return False
    
    # Install Python dependencies
    print("📦 Installing Python dependencies...")
    if not run_ssh_command_with_password(username, ip_address, password, 
                                       "cd /opt/quanttime && pip install -r requirements.txt"):
        print("❌ Failed to install dependencies")
        return False
    
    # Set up auto-pull script
    print("🔧 Setting up auto-pull script...")
    auto_pull_script = '''#!/bin/bash
cd /opt/quanttime
echo "🔄 Pulling latest changes..."
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
    if not run_ssh_command_with_password(username, ip_address, password, 
                                       f'echo \'{auto_pull_script}\' > /opt/quanttime/auto_pull.sh'):
        print("❌ Failed to create auto-pull script")
        return False
    
    if not run_ssh_command_with_password(username, ip_address, password, 
                                       "chmod +x /opt/quanttime/auto_pull.sh"):
        print("❌ Failed to make auto-pull script executable")
        return False
    
    # Test the deployment
    print("🧪 Testing deployment...")
    if not run_ssh_command_with_password(username, ip_address, password, 
                                       "cd /opt/quanttime && python -c \"import quanttime; print('✅ Deployment successful!')\""):
        print("❌ Deployment test failed")
        return False
    
    return True

def main():
    """Main deployment function."""
    print("🚀 Private Repository Deployment")
    print("=" * 40)
    
    # Read settings
    settings = read_settings()
    
    username = settings.get('R630XL_SSH_USER', 'quanttime')
    ip_address = settings.get('R630XL_TAILSCALE_IP', 'jupiter')
    password = os.environ.get('R630XL_SSH_PASSWORD') or settings.get('R630XL_SSH_PASSWORD')
    
    if not password:
        print("❌ R630XL_SSH_PASSWORD not found in settings.txt")
        sys.exit(1)
    
    # Get GitHub URL
    github_url = get_github_url()
    print(f"📦 Using GitHub URL: {github_url}")
    
    print(f"🎯 Deploying to {username}@{ip_address}")
    print("-" * 30)
    
    # Choose authentication method
    print("🔐 Choose authentication method for private repository:")
    print("1. SSH Key (recommended)")
    print("2. Personal Access Token")
    print("3. Manual file transfer (rsync)")
    
    choice = input("Enter your choice (1-3): ").strip()
    
    if choice == "1":
        # SSH Key authentication
        if not setup_github_ssh_on_server(username, ip_address, password):
            print("❌ Failed to set up SSH authentication")
            sys.exit(1)
        
        # Convert HTTPS URL to SSH if needed
        if github_url.startswith("https://"):
            github_url = github_url.replace("https://github.com/", "git@github.com:")
    
    elif choice == "2":
        # Personal Access Token
        if not setup_github_token_on_server(username, ip_address, password):
            print("❌ Failed to set up token authentication")
            sys.exit(1)
    
    elif choice == "3":
        # Manual file transfer
        print("📁 Using manual file transfer...")
        print("This will transfer files directly without using Git.")
        response = input("Continue with manual transfer? (y/n): ").lower().strip()
        if response not in ['y', 'yes']:
            print("❌ Deployment cancelled.")
            sys.exit(1)
        
        # Use rsync for manual transfer
        print("🔄 Transferring files to server...")
        rsync_cmd = f'rsync -avz --exclude="data/" --exclude="models/" --exclude="logs/" --exclude=".git/" ./ {username}@{ip_address}:/opt/quanttime/'
        
        result = subprocess.run(rsync_cmd, shell=True)
        if result.returncode != 0:
            print("❌ File transfer failed")
            sys.exit(1)
        
        # Install dependencies on server
        if not run_ssh_command_with_password(username, ip_address, password, 
                                           "cd /opt/quanttime && pip install -r requirements.txt"):
            print("❌ Failed to install dependencies")
            sys.exit(1)
        
        print("✅ Manual deployment successful!")
        return
    
    else:
        print("❌ Invalid choice")
        sys.exit(1)
    
    # Deploy repository
    if not deploy_repository(username, ip_address, password, github_url):
        print("❌ Repository deployment failed")
        sys.exit(1)
    
    print(f"\n🎉 Successfully deployed to server!")
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
