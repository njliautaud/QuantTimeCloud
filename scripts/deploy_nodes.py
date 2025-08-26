#!/usr/bin/env python3
"""
Node Deployment Script
Command-line tool for deploying QuantTime to all nodes
"""

import argparse
import json
import sys
from pathlib import Path
import subprocess
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from quanttime.dashboard.node_deployment import NodeDeploymentManager, NodeHealthStatus

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

def check_git_status():
    """Check if current repository is ready for deployment"""
    print("🔍 Checking Git repository status...")
    
    # Check if we're in a Git repository
    success, output, error = run_command("git status", check=False)
    if not success:
        print("❌ Not in a Git repository")
        return False
    
    # Check for uncommitted changes
    success, output, error = run_command("git status --porcelain", check=False)
    if output.strip():
        print("⚠️  Uncommitted changes detected:")
        for line in output.strip().split('\n'):
            print(f"   {line}")
        
        response = input("Do you want to commit these changes? (y/n): ")
        if response.lower() == 'y':
            success, output, error = run_command('git add . && git commit -m "Auto-commit before deployment"')
            if not success:
                print(f"❌ Failed to commit changes: {error}")
                return False
            print("✅ Changes committed")
        else:
            print("❌ Deployment cancelled due to uncommitted changes")
            return False
    
    # Check if we're up to date with remote
    success, output, error = run_command("git fetch origin && git status -uno", check=False)
    if "behind" in output:
        print("⚠️  Local repository is behind remote")
        response = input("Do you want to pull latest changes? (y/n): ")
        if response.lower() == 'y':
            success, output, error = run_command("git pull origin master")
            if not success:
                print(f"❌ Failed to pull changes: {error}")
                return False
            print("✅ Latest changes pulled")
        else:
            print("❌ Deployment cancelled - repository not up to date")
            return False
    
    print("✅ Git repository ready for deployment")
    return True

def deploy_all_nodes():
    """Deploy to all configured nodes"""
    print("🚀 Starting deployment to all nodes...")
    
    # Initialize deployment manager
    manager = NodeDeploymentManager()
    
    if not manager.nodes:
        print("❌ No nodes configured. Please run the configuration wizard first.")
        return False
    
    print(f"📋 Found {len(manager.nodes)} nodes: {', '.join(manager.nodes.keys())}")
    
    # Deploy to each node
    for node_name, node_config in manager.nodes.items():
        if node_name == "laptop":
            print(f"⏭️  Skipping laptop node")
            continue
        
        print(f"\n📦 Deploying to {node_name} ({node_config['host']})...")
        
        success, message = manager.deploy_to_node(node_name)
        if success:
            print(f"✅ {node_name}: {message}")
        else:
            print(f"❌ {node_name}: {message}")
            return False
    
    print("\n🎉 Deployment completed successfully!")
    return True

def check_health():
    """Check health of all nodes"""
    print("🏥 Checking node health...")
    
    manager = NodeDeploymentManager()
    
    if not manager.nodes:
        print("❌ No nodes configured")
        return False
    
    all_healthy = True
    
    for node_name, node_config in manager.nodes.items():
        print(f"\n🔍 Checking {node_name} ({node_config['host']})...")
        
        status, message = manager.get_node_health_status(node_name)
        
        if status == NodeHealthStatus.GREEN:
            print(f"🟢 {node_name}: {message}")
        elif status == NodeHealthStatus.YELLOW:
            print(f"🟡 {node_name}: {message}")
            all_healthy = False
        else:
            print(f"🔴 {node_name}: {message}")
            all_healthy = False
    
    if all_healthy:
        print("\n✅ All nodes are healthy!")
    else:
        print("\n⚠️  Some nodes have issues")
    
    return all_healthy

def start_ray_clusters():
    """Start Ray clusters on all nodes"""
    print("⚡ Starting Ray clusters...")
    
    manager = NodeDeploymentManager()
    
    if not manager.nodes:
        print("❌ No nodes configured")
        return False
    
    for node_name, node_config in manager.nodes.items():
        print(f"\n🚀 Starting Ray on {node_name}...")
        
        success, message = manager.start_ray_cluster(node_name)
        if success:
            print(f"✅ {node_name}: {message}")
        else:
            print(f"❌ {node_name}: {message}")
            return False
    
    print("\n🎉 Ray clusters started successfully!")
    return True

def sync_files():
    """Sync large files to all nodes"""
    print("🔄 Syncing large files...")
    
    manager = NodeDeploymentManager()
    
    if not manager.nodes:
        print("❌ No nodes configured")
        return False
    
    for node_name, node_config in manager.nodes.items():
        if node_name == "laptop":
            continue
        
        print(f"\n📁 Syncing files to {node_name}...")
        
        success, message = manager.sync_large_files(node_name)
        if success:
            print(f"✅ {node_name}: {message}")
        else:
            print(f"❌ {node_name}: {message}")
            return False
    
    print("\n🎉 File sync completed!")
    return True

def full_deployment():
    """Perform full deployment: check Git, deploy, start Ray, sync files"""
    print("🚀 Starting full deployment process...")
    
    # Step 1: Check Git status
    if not check_git_status():
        return False
    
    # Step 2: Deploy to all nodes
    if not deploy_all_nodes():
        return False
    
    # Step 3: Start Ray clusters
    if not start_ray_clusters():
        return False
    
    # Step 4: Sync files
    if not sync_files():
        return False
    
    # Step 5: Final health check
    print("\n🏥 Performing final health check...")
    if not check_health():
        print("⚠️  Deployment completed but some nodes have issues")
        return False
    
    print("\n🎉 Full deployment completed successfully!")
    print("🌐 Dashboard available at: http://localhost:8501")
    print("⚡ Ray dashboard available at: http://localhost:8265")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Deploy QuantTime to all nodes")
    parser.add_argument("command", choices=[
        "deploy", "health", "ray", "sync", "full", "git-check"
    ], help="Deployment command to run")
    
    args = parser.parse_args()
    
    if args.command == "git-check":
        success = check_git_status()
    elif args.command == "deploy":
        success = deploy_all_nodes()
    elif args.command == "health":
        success = check_health()
    elif args.command == "ray":
        success = start_ray_clusters()
    elif args.command == "sync":
        success = sync_files()
    elif args.command == "full":
        success = full_deployment()
    else:
        print("❌ Unknown command")
        return 1
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
