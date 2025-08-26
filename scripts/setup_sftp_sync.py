#!/usr/bin/env python3
"""
SFTP Sync Setup Script
Initializes SFTP large file sync system and migrates from Syncthing
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
import argparse

def run_command(command, cwd=None, check=True):
    """Run a shell command"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr

def check_git_repo():
    """Check if current directory is a Git repository"""
    git_dir = Path(".git")
    if not git_dir.exists():
        return False, "Not a Git repository"
    
    # Check if remote is configured
    success, output, error = run_command("git remote get-url origin", check=False)
    if not success:
        return False, "No remote origin configured"
    
    return True, output

def setup_git_repo():
    """Setup Git repository if not already configured"""
    print("🔧 Setting up Git repository...")
    
    # Check if already a Git repo
    is_repo, remote = check_git_repo()
    
    if not is_repo:
        # Initialize Git repository
        success, output, error = run_command("git init")
        if not success:
            print(f"❌ Failed to initialize Git repository: {error}")
            return False
        
        print("✅ Git repository initialized")
        
        # Add all files
        success, output, error = run_command("git add .")
        if not success:
            print(f"❌ Failed to add files: {error}")
            return False
        
        # Initial commit
        success, output, error = run_command('git commit -m "Initial commit - SFTP sync setup"')
        if not success:
            print(f"❌ Failed to create initial commit: {error}")
            return False
        
        print("✅ Initial commit created")
        
        # Ask for remote URL
        remote_url = input("Enter GitHub repository URL (or press Enter to skip): ").strip()
        if remote_url:
            success, output, error = run_command(f"git remote add origin {remote_url}")
            if not success:
                print(f"❌ Failed to add remote: {error}")
                return False
            
            success, output, error = run_command("git push -u origin main")
            if not success:
                print(f"❌ Failed to push to remote: {error}")
                return False
            
            print("✅ Repository pushed to remote")
    else:
        print(f"✅ Git repository already configured: {remote}")
    
    return True

def create_sftp_config():
    """Create SFTP configuration file"""
    print("🔧 Creating SFTP configuration...")
    
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    config_file = config_dir / "sftp_config.json"
    
    if config_file.exists():
        print("✅ SFTP configuration already exists")
        return True
    
    # Default configuration
    config = {
        "nodes": {
            "laptop": {
                "name": "Development Laptop",
                "host": "localhost",
                "port": 22,
                "username": "jupiter",
                "large_file_dirs": [
                    "data/es_futures",
                    "data/processed",
                    "models",
                    "backtest/results",
                    "logs"
                ]
            },
            "r630xl": {
                "name": "R630XL Server",
                "host": "jupiter",
                "port": 22,
                "username": "jupiter",
                "large_file_dirs": [
                    "/opt/quanttime/data/es_futures",
                    "/opt/quanttime/data/processed",
                    "/opt/quanttime/models",
                    "/opt/quanttime/backtest/results",
                    "/opt/quanttime/logs"
                ]
            },
            "r810": {
                "name": "R810 Server",
                "host": "saturn",
                "port": 22,
                "username": "jupiter",
                "large_file_dirs": [
                    "/opt/quanttime/data/es_futures",
                    "/opt/quanttime/data/processed",
                    "/opt/quanttime/models",
                    "/opt/quanttime/backtest/results",
                    "/opt/quanttime/logs"
                ]
            }
        },
        "sync_settings": {
            "max_file_size_mb": 100,
            "sync_interval_minutes": 5,
            "retry_attempts": 3,
            "chunk_size_mb": 10,
            "parallel_transfers": 4
        }
    }
    
    # Customize configuration
    print("\n📝 Customizing SFTP configuration...")
    
    # Laptop configuration
    laptop_host = input("Enter laptop hostname/IP (default: localhost): ").strip() or "localhost"
    laptop_username = input("Enter laptop username (default: jupiter): ").strip() or "jupiter"
    
    config["nodes"]["laptop"]["host"] = laptop_host
    config["nodes"]["laptop"]["username"] = laptop_username
    
    # R630XL configuration
    r630xl_host = input("Enter R630XL hostname/IP (default: jupiter): ").strip() or "jupiter"
    r630xl_username = input("Enter R630XL username (default: jupiter): ").strip() or "jupiter"
    
    config["nodes"]["r630xl"]["host"] = r630xl_host
    config["nodes"]["r630xl"]["username"] = r630xl_username
    
    # R810 configuration
    r810_host = input("Enter R810 hostname/IP (default: saturn): ").strip() or "saturn"
    r810_username = input("Enter R810 username (default: jupiter): ").strip() or "jupiter"
    
    config["nodes"]["r810"]["host"] = r810_host
    config["nodes"]["r810"]["username"] = r810_username
    
    # Save configuration
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ SFTP configuration saved to {config_file}")
    return True

def test_ssh_connections():
    """Test SSH connections to all nodes"""
    print("🔧 Testing SSH connections...")
    
    config_file = Path("config/sftp_config.json")
    if not config_file.exists():
        print("❌ SFTP configuration not found")
        return False
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    all_connected = True
    
    for node_id, node_config in config["nodes"].items():
        print(f"Testing connection to {node_id} ({node_config['host']})...")
        
        # Test SSH connection
        test_command = f"ssh -o ConnectTimeout=10 -o BatchMode=yes {node_config['username']}@{node_config['host']} 'echo Connection successful'"
        success, output, error = run_command(test_command, check=False)
        
        if success:
            print(f"✅ {node_id}: Connected successfully")
        else:
            print(f"❌ {node_id}: Connection failed - {error}")
            all_connected = False
    
    return all_connected

def stop_syncthing():
    """Stop Syncthing services"""
    print("🛑 Stopping Syncthing services...")
    
    # Stop Syncthing processes
    success, output, error = run_command("pkill -f syncthing", check=False)
    if success:
        print("✅ Syncthing processes stopped")
    
    # Stop systemd service if exists
    success, output, error = run_command("sudo systemctl stop syncthing@jupiter", check=False)
    if success:
        print("✅ Syncthing systemd service stopped")
    
    # Disable systemd service
    success, output, error = run_command("sudo systemctl disable syncthing@jupiter", check=False)
    if success:
        print("✅ Syncthing systemd service disabled")
    
    return True

def install_dependencies():
    """Install required Python dependencies"""
    print("🔧 Installing Python dependencies...")
    
    # Check if paramiko is installed
    try:
        import paramiko
        print("✅ paramiko already installed")
    except ImportError:
        print("Installing paramiko...")
        success, output, error = run_command("pip install paramiko==3.4.0")
        if not success:
            print(f"❌ Failed to install paramiko: {error}")
            return False
        print("✅ paramiko installed")
    
    # Check if pysftp is installed
    try:
        import pysftp
        print("✅ pysftp already installed")
    except ImportError:
        print("Installing pysftp...")
        success, output, error = run_command("pip install pysftp==0.2.9")
        if not success:
            print(f"❌ Failed to install pysftp: {error}")
            return False
        print("✅ pysftp installed")
    
    return True

def create_sync_scripts():
    """Create sync automation scripts"""
    print("🔧 Creating sync automation scripts...")
    
    # Create systemd service for auto-git-sync
    service_content = """[Unit]
Description=QuantTime Git Auto Sync
After=network.target

[Service]
Type=simple
User=jupiter
WorkingDirectory=/opt/quanttime
ExecStart=/opt/quanttime/venv/bin/python scripts/auto_git_sync.py --watch --interval 60
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path("/etc/systemd/system/quanttime-git-sync.service")
    if not service_file.exists():
        try:
            with open(service_file, 'w') as f:
                f.write(service_content)
            print("✅ Git sync systemd service created")
        except PermissionError:
            print("⚠️  Cannot create systemd service (requires sudo)")
    
    # Create startup script
    startup_script = Path("scripts/start_sync_services.sh")
    startup_content = """#!/bin/bash
# QuantTime Sync Services Startup Script

echo "Starting QuantTime sync services..."

# Start Git auto-sync
cd /opt/quanttime
nohup venv/bin/python scripts/auto_git_sync.py --watch --interval 60 > logs/git_sync.log 2>&1 &

# Start SFTP manager
nohup venv/bin/python -c "from quanttime.core.sftp_manager import get_sftp_manager; get_sftp_manager()" > logs/sftp_manager.log 2>&1 &

echo "Sync services started"
"""
    
    with open(startup_script, 'w') as f:
        f.write(startup_content)
    
    # Make executable
    startup_script.chmod(0o755)
    print("✅ Sync startup script created")
    
    return True

def verify_setup():
    """Verify the setup is complete"""
    print("🔍 Verifying setup...")
    
    checks = [
        ("Git repository", Path(".git").exists()),
        ("SFTP configuration", Path("config/sftp_config.json").exists()),
        ("Git ignore file", Path(".gitignore").exists()),
        ("Auto-git-sync script", Path("scripts/auto_git_sync.py").exists()),
        ("SFTP manager", Path("quanttime/core/sftp_manager.py").exists()),
        ("SFTP interface", Path("quanttime/dashboard/sftp_interface.py").exists()),
    ]
    
    all_good = True
    for check_name, exists in checks:
        status = "✅" if exists else "❌"
        print(f"{status} {check_name}")
        if not exists:
            all_good = False
    
    if all_good:
        print("\n🎉 Setup verification complete!")
        return True
    else:
        print("\n⚠️  Some components are missing")
        return False

def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description="Setup SFTP sync system")
    parser.add_argument("--skip-syncthing", action="store_true", help="Skip stopping Syncthing")
    parser.add_argument("--skip-ssh-test", action="store_true", help="Skip SSH connection test")
    parser.add_argument("--verify-only", action="store_true", help="Only verify setup")
    
    args = parser.parse_args()
    
    print("🚀 QuantTime SFTP Sync Setup")
    print("=" * 50)
    
    if args.verify_only:
        return verify_setup()
    
    # Step 1: Setup Git repository
    if not setup_git_repo():
        print("❌ Git setup failed")
        return False
    
    # Step 2: Create SFTP configuration
    if not create_sftp_config():
        print("❌ SFTP configuration failed")
        return False
    
    # Step 3: Install dependencies
    if not install_dependencies():
        print("❌ Dependency installation failed")
        return False
    
    # Step 4: Stop Syncthing (if not skipped)
    if not args.skip_syncthing:
        stop_syncthing()
    
    # Step 5: Test SSH connections (if not skipped)
    if not args.skip_ssh_test:
        if not test_ssh_connections():
            print("⚠️  Some SSH connections failed - please check your configuration")
    
    # Step 6: Create sync scripts
    create_sync_scripts()
    
    # Step 7: Verify setup
    if not verify_setup():
        print("❌ Setup verification failed")
        return False
    
    print("\n🎉 SFTP Sync Setup Complete!")
    print("\n📋 Next Steps:")
    print("1. Start the dashboard: python run.py")
    print("2. Navigate to Settings → SFTP Large File Sync")
    print("3. Test sync operations")
    print("4. Start auto-sync: python scripts/auto_git_sync.py --watch")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
