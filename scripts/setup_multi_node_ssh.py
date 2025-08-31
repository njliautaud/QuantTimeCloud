#!/usr/bin/env python3
"""
Multi-Node SSH Key Distribution and Persistent Ray Task Setup
Distributes SSH keys across nodes and sets up tmux/screen for persistent Ray tasks
"""

import os
import sys
import json
import subprocess
import paramiko
from pathlib import Path
from typing import Dict, List, Optional

def copy_ssh_key_to_node(node_address: str, node_username: str, node_password: str, 
                        local_key_path: str, node_platform: str = "linux"):
    """Copy SSH key to remote node for Git authentication"""
    
    print(f"📡 Copying SSH key to {node_address}...")
    
    try:
        # Connect to remote node
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(node_address, username=node_username, password=node_password)
        
        # Create .ssh directory if it doesn't exist
        if node_platform == "windows":
            ssh_dir = f"C:\\Users\\{node_username}\\.ssh"
            commands = [
                f"if not exist \"{ssh_dir}\" mkdir \"{ssh_dir}\"",
                f"icacls \"{ssh_dir}\" /inheritance:r /grant:r \"{node_username}\":F"
            ]
        else:
            ssh_dir = f"/home/{node_username}/.ssh"
            commands = [
                f"mkdir -p {ssh_dir}",
                f"chmod 700 {ssh_dir}"
            ]
        
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()
        
        # Copy private key
        with open(local_key_path, 'r') as f:
            private_key_content = f.read()
        
        # Copy public key
        with open(f"{local_key_path}.pub", 'r') as f:
            public_key_content = f.read()
        
        # Write keys to remote node
        if node_platform == "windows":
            private_key_path = f"{ssh_dir}\\id_ed25519"
            public_key_path = f"{ssh_dir}\\id_ed25519.pub"
        else:
            private_key_path = f"{ssh_dir}/id_ed25519"
            public_key_path = f"{ssh_dir}/id_ed25519.pub"
        
        # Write private key
        sftp = ssh.open_sftp()
        with sftp.open(private_key_path, 'w') as f:
            f.write(private_key_content)
        
        # Write public key
        with sftp.open(public_key_path, 'w') as f:
            f.write(public_key_content)
        
        # Set permissions
        if node_platform != "windows":
            ssh.exec_command(f"chmod 600 {private_key_path}")
            ssh.exec_command(f"chmod 644 {public_key_path}")
        
        sftp.close()
        ssh.close()
        
        print(f"✅ SSH key copied to {node_address}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to copy SSH key to {node_address}: {e}")
        return False

def setup_persistent_ray_session(node_address: str, node_username: str, node_password: str,
                                node_platform: str, project_root: str):
    """Setup tmux/screen session for persistent Ray tasks"""
    
    print(f"🖥️  Setting up persistent Ray session on {node_address}...")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(node_address, username=node_username, password=node_password)
        
        if node_platform == "windows":
            # Use Windows Terminal or PowerShell background jobs
            setup_commands = [
                # Install tmux equivalent for Windows (if not already)
                "if (Get-Command tmux -ErrorAction SilentlyContinue) { Write-Output 'tmux already installed' } else { scoop install tmux }",
                
                # Create persistent Ray session
                f"cd {project_root}",
                "tmux new-session -d -s quanttime_ray",
                "tmux send-keys -t quanttime_ray 'cd /c/QuantTime' Enter",
                "tmux send-keys -t quanttime_ray 'python -m ray start --head --dashboard-host=0.0.0.0 --dashboard-port=8265' Enter"
            ]
        else:
            # Linux setup with screen/tmux
            setup_commands = [
                # Install screen if not available
                "which screen || sudo apt-get update && sudo apt-get install -y screen",
                
                # Create persistent Ray session
                f"cd {project_root}",
                "screen -dmS quanttime_ray",
                f"screen -S quanttime_ray -X stuff 'cd {project_root}\\n'",
                "screen -S quanttime_ray -X stuff 'source .venv/bin/activate\\n'",
                "screen -S quanttime_ray -X stuff 'python -m ray start --head --dashboard-host=0.0.0.0 --dashboard-port=8265\\n'"
            ]
        
        for cmd in setup_commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            result = stdout.read().decode()
            error = stderr.read().decode()
            if error:
                print(f"Warning: {error.strip()}")
        
        # Create management script
        management_script = f"""#!/bin/bash
# QuantTime Ray Session Management

case "$1" in
    start)
        {'tmux new-session -d -s quanttime_ray' if node_platform == 'windows' else 'screen -dmS quanttime_ray'}
        echo "Ray session started"
        ;;
    stop)
        {'tmux kill-session -t quanttime_ray' if node_platform == 'windows' else 'screen -S quanttime_ray -X quit'}
        echo "Ray session stopped" 
        ;;
    status)
        {'tmux list-sessions | grep quanttime_ray' if node_platform == 'windows' else 'screen -list | grep quanttime_ray'}
        ;;
    attach)
        {'tmux attach-session -t quanttime_ray' if node_platform == 'windows' else 'screen -r quanttime_ray'}
        ;;
    *)
        echo "Usage: $0 {{start|stop|status|attach}}"
        exit 1
        ;;
esac
"""
        
        script_path = f"{project_root}/manage_ray_session.sh"
        sftp = ssh.open_sftp()
        with sftp.open(script_path, 'w') as f:
            f.write(management_script)
        
        if node_platform != "windows":
            ssh.exec_command(f"chmod +x {script_path}")
        
        sftp.close()
        ssh.close()
        
        print(f"✅ Persistent Ray session setup complete on {node_address}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to setup persistent session on {node_address}: {e}")
        return False

def distribute_ssh_keys_to_all_nodes():
    """Distribute SSH keys to all configured nodes"""
    
    # Load node configuration
    with open('config/ray_cluster_config.json', 'r') as f:
        config = json.load(f)
    
    local_key_path = os.path.expanduser("~/.ssh/id_ed25519")
    
    if not os.path.exists(local_key_path):
        print("❌ SSH key not found. Please generate one first.")
        return False
    
    print("🔑 Distributing SSH keys to all nodes...")
    
    success_count = 0
    total_nodes = 0
    
    # Process worker nodes
    for node in config['worker_nodes']:
        if node['ssh']['enabled']:
            total_nodes += 1
            
            success = copy_ssh_key_to_node(
                node['address'],
                node['ssh']['username'], 
                node['ssh'].get('password', ''),  # You'd need to add passwords to config
                local_key_path,
                node['platform']
            )
            
            if success:
                success_count += 1
                
                # Setup persistent Ray session
                setup_persistent_ray_session(
                    node['address'],
                    node['ssh']['username'],
                    node['ssh'].get('password', ''),
                    node['platform'],
                    node['paths']['project_root']
                )
    
    print(f"\n📊 SSH Key Distribution Summary:")
    print(f"✅ Successful: {success_count}/{total_nodes} nodes")
    print(f"🔄 All nodes can now auto-sync from Git after pushes")
    print(f"🖥️  Persistent Ray sessions configured for uninterrupted tasks")
    
    return success_count == total_nodes

if __name__ == "__main__":
    print("🚀 Multi-Node SSH Key Distribution & Persistent Ray Setup")
    print("=" * 60)
    
    distribute_ssh_keys_to_all_nodes()
