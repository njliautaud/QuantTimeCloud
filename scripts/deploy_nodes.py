#!/usr/bin/env python3
"""
Cross-Platform Node Deployment Script
Command-line tool for deploying QuantTime to Windows and Linux nodes using Ray+SSH
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

from quanttime.core.cross_platform_node_manager import CrossPlatformNodeManager, NodeHealthStatus

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
    print("🚀 Starting cross-platform deployment to all nodes...")
    
    # Initialize node manager
    manager = CrossPlatformNodeManager()
    
    cluster_overview = manager.get_cluster_overview()
    if cluster_overview["total_nodes"] <= 1:  # Only head node
        print("❌ No worker nodes configured. Please configure nodes first.")
        return False
    
    print(f"📋 Found {cluster_overview['total_nodes']} nodes ({cluster_overview['platform_counts']})")
    
    # Deploy to all nodes
    deploy_results = manager.deploy_to_all_nodes(force=True)
    
    # Show results
    all_success = True
    for node_id, (success, message) in deploy_results.items():
        if success:
            print(f"✅ {node_id}: {message}")
        else:
            print(f"❌ {node_id}: {message}")
            all_success = False
    
    if all_success:
        print("\n🎉 Cross-platform deployment completed successfully!")
    else:
        print("\n⚠️ Some deployments failed. Check the logs above.")
    
    return all_success

def check_health():
    """Check health of all nodes"""
    print("🏥 Checking cross-platform node health...")
    
    manager = CrossPlatformNodeManager()
    
    cluster_overview = manager.get_cluster_overview()
    if cluster_overview["total_nodes"] == 0:
        print("❌ No nodes configured")
        return False
    
    print(f"📊 Cluster Overview: {cluster_overview['total_nodes']} nodes")
    print(f"🟢 Healthy: {cluster_overview['health_counts']['green']}")
    print(f"🟡 Issues: {cluster_overview['health_counts']['yellow']}")
    print(f"🔴 Offline: {cluster_overview['health_counts']['red']}")
    print(f"💻 Platforms: {cluster_overview['platform_counts']}")
    
    all_healthy = True
    
    for node_id, node_info in cluster_overview["nodes"].items():
        print(f"\n🔍 Checking {node_id} ({node_info['name']})...")
        
        if node_info["health_status"] == "green":
            print(f"🟢 {node_id}: {node_info['health_message']} ({node_info['platform']})")
        elif node_info["health_status"] == "yellow":
            print(f"🟡 {node_id}: {node_info['health_message']} ({node_info['platform']})")
            all_healthy = False
        else:
            print(f"🔴 {node_id}: {node_info['health_message']} ({node_info['platform']})")
            all_healthy = False
    
    if all_healthy:
        print("\n✅ All nodes are healthy!")
    else:
        print("\n⚠️  Some nodes have issues")
    
    return all_healthy

def start_ray_clusters():
    """Start Ray clusters on all nodes"""
    print("⚡ Starting Ray workers on all nodes...")
    
    manager = CrossPlatformNodeManager()
    
    cluster_overview = manager.get_cluster_overview()
    worker_nodes = [node_id for node_id, node_info in cluster_overview["nodes"].items() 
                    if node_id != manager.config["head_node"]["node_id"]]
    
    if not worker_nodes:
        print("❌ No worker nodes configured")
        return False
    
    all_success = True
    for node_id in worker_nodes:
        print(f"\n🚀 Starting Ray worker on {node_id}...")
        
        success, message = manager.start_ray_cluster(node_id)
        if success:
            print(f"✅ {node_id}: {message}")
        else:
            print(f"❌ {node_id}: {message}")
            all_success = False
    
    if all_success:
        print("\n🎉 Ray workers started successfully!")
    else:
        print("\n⚠️ Some Ray workers failed to start")
    
    return all_success

def sync_files():
    """Sync large files to all nodes"""
    print("🔄 Syncing large files via SFTP...")
    
    manager = CrossPlatformNodeManager()
    
    cluster_overview = manager.get_cluster_overview()
    worker_nodes = [node_id for node_id, node_info in cluster_overview["nodes"].items() 
                    if node_id != manager.config["head_node"]["node_id"]]
    
    if not worker_nodes:
        print("❌ No worker nodes configured")
        return False
    
    all_success = True
    for node_id in worker_nodes:
        print(f"\n📁 Syncing large files to {node_id}...")
        
        success, message = manager.sync_large_files(node_id)
        if success:
            print(f"✅ {node_id}: {message}")
        else:
            print(f"❌ {node_id}: {message}")
            all_success = False
    
    if all_success:
        print("\n🎉 SFTP file sync completed!")
    else:
        print("\n⚠️ Some file syncs failed")
    
    return all_success

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
