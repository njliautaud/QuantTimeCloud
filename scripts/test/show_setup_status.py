#!/usr/bin/env python3
"""
Show QuantTime Setup Status
Displays what's been configured and what's available
"""

import json
import os
from pathlib import Path
import subprocess
import sys

def check_file_exists(file_path: str) -> bool:
    """Check if a file exists"""
    return Path(file_path).exists()

def check_service_running(port: int) -> bool:
    """Check if a service is running on a port"""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            return result == 0
    except:
        return False

def main():
    """Show setup status"""
    print("🔍 QuantTime Setup Status")
    print("=" * 50)
    
    # Check if setup has been run
    if check_file_exists("setup_summary.json"):
        print("✅ Auto-setup has been completed")
        
        # Load setup summary
        with open("setup_summary.json", 'r') as f:
            summary = json.load(f)
        
        print(f"📅 Setup completed: {summary['timestamp']}")
        print(f"🖥️ Environment: {summary['environment']['os']} with Python {summary['environment']['python_version'].split()[0]}")
        print(f"🖥️ Nodes detected: {len(summary['nodes'])}")
        
        # Show test results
        print("\n🧪 Component Tests:")
        for test, result in summary['test_results'].items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {status} {test}")
        
        # Show ports
        print(f"\n🌐 Services:")
        ports = summary['environment']['ports']
        for service, port in ports.items():
            running = "🟢 RUNNING" if check_service_running(port) else "🔴 STOPPED"
            print(f"  {running} {service.title()}: http://localhost:{port}")
        
        # Show nodes
        print(f"\n🖥️ Detected Nodes:")
        for node_id, node_info in summary['nodes'].items():
            status = "🟢 ONLINE" if node_info.get('status') == 'online' else "🔴 OFFLINE"
            print(f"  {status} {node_info.get('ip', node_id)} ({node_info.get('username', 'unknown')})")
        
    else:
        print("❌ Auto-setup has not been run yet")
        print("💡 Run: python launch.py")
        return
    
    # Check configuration files
    print(f"\n📁 Configuration Files:")
    config_files = [
        "sync_config.json",
        "monitoring_config.json", 
        "coolify_config.json"
    ]
    
    for config_file in config_files:
        exists = "✅" if check_file_exists(config_file) else "❌"
        print(f"  {exists} {config_file}")
    
    # Check directories
    print(f"\n📂 Directory Structure:")
    directories = [
        "data",
        "data/results",
        "data/models", 
        "logs",
        "monitoring"
    ]
    
    for directory in directories:
        exists = "✅" if Path(directory).exists() else "❌"
        print(f"  {exists} {directory}/")
    
    # Show next steps
    print(f"\n🚀 Next Steps:")
    print("  1. Dashboard is ready at: http://localhost:8501")
    print("  2. Go to '📊 Monitoring' tab to start monitoring")
    print("  3. Go to '🚀 Coolify' tab to configure deployments")
    print("  4. Use '📁 File Management' for peer-to-peer file sync")
    
    print(f"\n🎉 Everything is set up and ready to use!")
    print("=" * 50)

if __name__ == "__main__":
    main()
