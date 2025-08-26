#!/usr/bin/env python3
"""
Fix SSH key authentication for R630XL server.
This script will properly copy the SSH public key to the server.
"""

import subprocess
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
        
    except ImportError:
        print("❌ paramiko not installed. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "paramiko"])
        return run_ssh_command_with_password(username, ip_address, password, command)
    except Exception as e:
        print(f"   ❌ SSH command failed: {e}")
        return False

def copy_ssh_key_with_password(username: str, ip_address: str, password: str):
    """Copy SSH public key to server using password authentication."""
    print("🔑 Setting up SSH key authentication...")
    
    # Check if SSH key exists
    ssh_key_path = Path.home() / ".ssh" / "id_rsa.pub"
    if not ssh_key_path.exists():
        print("❌ SSH public key not found. Generating new key pair...")
        # Generate new SSH key
        subprocess.run(["ssh-keygen", "-t", "rsa", "-b", "4096", "-f", str(Path.home() / ".ssh" / "id_rsa"), "-N", '""'])
    
    # Read the public key
    with open(ssh_key_path, 'r') as f:
        public_key = f.read().strip()
    
    print(f"📋 Public key: {public_key[:50]}...")
    
    # Create .ssh directory on server
    if not run_ssh_command_with_password(username, ip_address, password, "mkdir -p ~/.ssh"):
        print("❌ Failed to create .ssh directory on server")
        return False
    
    # Copy public key to server
    copy_command = f'echo "{public_key}" >> ~/.ssh/authorized_keys'
    if not run_ssh_command_with_password(username, ip_address, password, copy_command):
        print("❌ Failed to copy public key to server")
        return False
    
    # Set proper permissions
    if not run_ssh_command_with_password(username, ip_address, password, "chmod 700 ~/.ssh"):
        print("❌ Failed to set .ssh directory permissions")
        return False
    
    if not run_ssh_command_with_password(username, ip_address, password, "chmod 600 ~/.ssh/authorized_keys"):
        print("❌ Failed to set authorized_keys permissions")
        return False
    
    print("✅ SSH key authentication set up successfully!")
    return True

def test_ssh_connection(username: str, ip_address: str):
    """Test SSH connection without password."""
    print("🧪 Testing SSH connection without password...")
    
    test_cmd = f'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no {username}@{ip_address} "echo SSH key authentication successful"'
    result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ SSH key authentication working!")
        return True
    else:
        print("❌ SSH key authentication failed")
        print(f"   Error: {result.stderr.strip()}")
        return False

def main():
    """Main function."""
    print("🔧 SSH Key Authentication Fix")
    print("=" * 40)
    
    # Read settings
    settings = read_settings()
    
    username = settings.get('R630XL_SSH_USER', 'quanttime')
    ip_address = settings.get('R630XL_TAILSCALE_IP', 'jupiter')
    password = settings.get('R630XL_SSH_PASSWORD')
    
    if not password:
        print("❌ R630XL_SSH_PASSWORD not found in settings.txt")
        sys.exit(1)
    
    print(f"🎯 Setting up SSH for {username}@{ip_address}")
    print("-" * 30)
    
    # Copy SSH key to server
    if not copy_ssh_key_with_password(username, ip_address, password):
        print("❌ Failed to set up SSH key authentication")
        sys.exit(1)
    
    # Test the connection
    if not test_ssh_connection(username, ip_address):
        print("❌ SSH key authentication test failed")
        print("\n📋 Troubleshooting steps:")
        print("1. Verify the password is correct in settings.txt")
        print("2. Check if the server's SSH service is running")
        print("3. Try connecting manually: ssh quanttime@jupiter")
        sys.exit(1)
    
    print("\n🎉 SSH key authentication is now working!")
    print("📋 You can now run SSH commands without entering a password.")

if __name__ == "__main__":
    main()
