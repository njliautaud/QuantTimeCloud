#!/usr/bin/env python3
"""
Test script for Syncthing and Ray integration
Verifies that all managers can be imported and initialized
"""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    try:
        from server.core.syncthing_manager import get_syncthing_manager, SyncStatus
        print("✅ Syncthing manager imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import syncthing_manager: {e}")
        return False
    
    try:
        from server.core.ray_manager import get_ray_manager, JobStatus, JobPriority
        print("✅ Ray manager imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import ray_manager: {e}")
        return False
    
    try:
        from quanttime.core.centralized_logging import get_centralized_logger, LogContext
        print("✅ Centralized logging imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import centralized_logging: {e}")
        return False
    
    try:
        from quanttime.dashboard.syncthing_ray_interface import render_syncthing_ray_interface
        print("✅ Syncthing Ray interface imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import syncthing_ray_interface: {e}")
        return False
    
    return True

def test_manager_initialization():
    """Test that managers can be initialized"""
    print("\nTesting manager initialization...")
    
    try:
        from server.core.syncthing_manager import get_syncthing_manager
        syncthing_manager = get_syncthing_manager()
        print("✅ Syncthing manager initialized successfully")
        
        # Test basic functionality
        status = syncthing_manager.get_sync_status()
        print(f"   - Sync status retrieved: {len(status['nodes'])} nodes")
        
    except Exception as e:
        print(f"❌ Failed to initialize syncthing_manager: {e}")
        return False
    
    try:
        from server.core.ray_manager import get_ray_manager
        ray_manager = get_ray_manager()
        print("✅ Ray manager initialized successfully")
        
        # Test basic functionality
        status = ray_manager.get_cluster_status()
        print(f"   - Cluster status retrieved: {status['active_nodes']} active nodes")
        
    except Exception as e:
        print(f"❌ Failed to initialize ray_manager: {e}")
        return False
    
    try:
        from quanttime.core.centralized_logging import get_centralized_logger
        logger = get_centralized_logger()
        print("✅ Centralized logger initialized successfully")
        
        # Test basic functionality
        node_status = logger.get_node_status()
        print(f"   - Node status retrieved: {len(node_status)} nodes")
        
    except Exception as e:
        print(f"❌ Failed to initialize centralized_logger: {e}")
        return False
    
    return True

def test_basic_functionality():
    """Test basic functionality of the managers"""
    print("\nTesting basic functionality...")
    
    try:
        from server.core.syncthing_manager import get_syncthing_manager
        from server.core.ray_manager import get_ray_manager
        from quanttime.core.centralized_logging import get_centralized_logger, LogContext
        
        syncthing_manager = get_syncthing_manager()
        ray_manager = get_ray_manager()
        logger = get_centralized_logger()
        
        # Test sync status
        sync_status = syncthing_manager.get_sync_status()
        print(f"✅ Sync status: {len(sync_status['nodes'])} nodes, {len(sync_status['folders'])} folders")
        
        # Test cluster status
        cluster_status = ray_manager.get_cluster_status()
        print(f"✅ Cluster status: {cluster_status['active_nodes']} active nodes, {len(cluster_status['jobs'])} jobs")
        
        # Test logging
        with LogContext("test_operation", node_id="laptop"):
            logger.info("Test log message")
        print("✅ Logging test completed")
        
        # Test version info
        version_info = syncthing_manager.get_version_info()
        print(f"✅ Version info: consistent={version_info['consistent']}")
        
        # Test resource usage
        resource_usage = ray_manager.get_resource_usage()
        print(f"✅ Resource usage: {resource_usage['total_cpu']} CPU cores, {resource_usage['total_memory']:.1f}GB memory")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("🧪 Testing Syncthing and Ray Integration")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import tests failed")
        return False
    
    # Test initialization
    if not test_manager_initialization():
        print("\n❌ Initialization tests failed")
        return False
    
    # Test basic functionality
    if not test_basic_functionality():
        print("\n❌ Basic functionality tests failed")
        return False
    
    print("\n🎉 All tests passed! Integration is working correctly.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
