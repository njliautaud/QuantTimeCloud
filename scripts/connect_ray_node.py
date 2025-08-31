#!/usr/bin/env python3
"""
Ray Node Connection Script
Helps connect worker nodes to the Ray cluster using Tailscale IPs
"""

import json
import subprocess
import sys
from pathlib import Path

def get_tailscale_ip():
    """Get Tailscale IP address"""
    try:
        result = subprocess.run(["tailscale", "ip"], capture_output=True, text=True, check=True)
        for line in result.stdout.strip().split('\n'):
            if line and '.' in line:  # IPv4 address
                return line.strip()
    except:
        pass
    return None

def connect_to_ray_cluster(head_node_ip):
    """Connect this node to the Ray cluster with auto-detection"""
    print(f"🔗 Connecting to Ray cluster at {head_node_ip} (auto-detecting port)")
    
    try:
        # Initialize Ray and connect to the cluster
        import ray
        
        if ray.is_initialized():
            print("⚠️  Ray already initialized. Shutting down...")
            ray.shutdown()
        
        # Connect to the cluster with auto-detection
        ray.init(
            address=f"ray://{head_node_ip}",  # Ray will auto-detect the port
            ignore_reinit_error=True,
            # Auto-detect local resources
            num_cpus=None,
            num_gpus=None,
            memory=None
        )
        
        print("✅ Successfully connected to Ray cluster!")
        
        # Get cluster info
        cluster_resources = ray.cluster_resources()
        print(f"📊 Cluster Resources: {cluster_resources}")
        
        # Keep the connection alive
        print("🔄 Node is now connected and ready for jobs...")
        print("Press Ctrl+C to disconnect")
        
        try:
            while True:
                import time
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n👋 Disconnecting from cluster...")
            ray.shutdown()
            print("✅ Disconnected successfully")
            
    except Exception as e:
        print(f"❌ Failed to connect to cluster: {e}")
        return False
    
    return True

def main():
    """Main function"""
    print("🚀 Ray Node Connection Script")
    print("=" * 40)
    
    # Check if config exists
    config_file = Path("config/ray_config.json")
    if not config_file.exists():
        print("❌ Ray config not found. Please run the setup wizard first.")
        sys.exit(1)
    
    # Load config
    with open(config_file) as f:
        config = json.load(f)
    
    head_node = config["head_node"]
    head_ip = head_node["host"]
    
    print(f"📋 Cluster Configuration:")
    print(f"   Head Node: {head_ip} (auto-detecting port)")
    print(f"   Dashboard: {head_node['dashboard_port']}")
    
    # Get local Tailscale IP
    local_ip = get_tailscale_ip()
    if local_ip:
        print(f"🔍 Local Tailscale IP: {local_ip}")
    else:
        print("⚠️  Could not detect Tailscale IP")
    
    # Connect to cluster
    if connect_to_ray_cluster(head_ip):
        print("✅ Node connection completed successfully")
    else:
        print("❌ Node connection failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
