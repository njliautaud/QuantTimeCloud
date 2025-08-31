#!/usr/bin/env python3
"""
Test script to verify persistent node status storage
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from quanttime.dashboard.node_status_manager import node_status_manager

def test_persistent_storage():
    """Test persistent node status storage"""
    print("🔍 Testing persistent node status storage...")
    
    # Test 1: Update node status
    print("\n📝 Test 1: Updating node status...")
    test_status = {
        "connected": True,
        "username": "jupiter@jupiter",
        "status": "🟢 Connected & Running",
        "health_info": {
            "system": "Linux Ubuntu",
            "cpu_cores": "16",
            "memory": "46GB"
        }
    }
    
    node_status_manager.update_node_status("r630xl", test_status)
    print("✅ Updated r630xl status")
    
    # Test 2: Retrieve node status
    print("\n📖 Test 2: Retrieving node status...")
    retrieved_status = node_status_manager.get_node_status("r630xl")
    print(f"Retrieved status: {retrieved_status}")
    
    # Test 3: Check if connected
    print("\n🔗 Test 3: Checking connection status...")
    is_connected = node_status_manager.is_node_connected("r630xl")
    print(f"R630XL connected: {is_connected}")
    
    # Test 4: Get all status
    print("\n📋 Test 4: Getting all node status...")
    all_status = node_status_manager.get_all_node_status()
    print(f"All status: {all_status}")
    
    # Test 5: Get connected nodes
    print("\n🟢 Test 5: Getting connected nodes...")
    connected_nodes = node_status_manager.get_connected_nodes()
    print(f"Connected nodes: {connected_nodes}")
    
    print("\n✅ All tests completed!")
    return True

if __name__ == "__main__":
    test_persistent_storage()
