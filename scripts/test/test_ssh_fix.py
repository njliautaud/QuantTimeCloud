#!/usr/bin/env python3
"""
Test script to verify SSH connection fix
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from quanttime.dashboard.initial_config import InitialConfigManager

def test_ssh_connection():
    """Test the SSH connection method"""
    print("🔍 Testing SSH connection fix...")
    
    # Initialize config manager
    config_manager = InitialConfigManager()
    
    # Test connection to R630XL
    host = "jupiter"
    username = "jupiter"
    password = "your_password_here"  # You'll need to provide this
    
    print(f"📡 Testing connection to {username}@{host}...")
    
    try:
        ssh_client = config_manager._create_ssh_connection(host, username, password)
        if ssh_client:
            print("✅ SSH connection successful!")
            
            # Test a simple command
            stdin, stdout, stderr = ssh_client.exec_command("uname -a", timeout=5)
            result = stdout.read().decode().strip()
            print(f"📋 System info: {result}")
            
            ssh_client.close()
            print("🔒 SSH connection closed")
            return True
        else:
            print("❌ SSH connection failed")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_ssh_connection()
