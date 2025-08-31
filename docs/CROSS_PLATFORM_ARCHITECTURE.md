# QuantTime Cross-Platform Architecture

## Overview

QuantTime has been refactored from a Docker/Coolify-based deployment system to a **cross-platform Ray+SSH+Git monitoring architecture** that seamlessly supports both Windows and Linux nodes. This eliminates the Ubuntu-only limitation and provides a more flexible, lightweight deployment system.

## Architecture Changes

### Removed Components
- ✅ **Coolify Docker containers** - Ubuntu-only limitation
- ✅ **Docker Compose files** - Too heavy for current needs
- ✅ **Kubernetes dependencies** - Unnecessary complexity
- ✅ **Ubuntu-only deployment scripts** - Platform limitation

### New Cross-Platform Components
- ✅ **CrossPlatformGitWatcher** - Repository monitoring and auto-deployment
- ✅ **CrossPlatformNodeManager** - Unified node management 
- ✅ **Enhanced SFTP Manager** - Large file synchronization
- ✅ **Ray Cluster Integration** - Distributed computing
- ✅ **SSH-based Communication** - Secure cross-platform connections

## System Components

### 1. Cross-Platform Git Watcher (`quanttime/core/cross_platform_git_watcher.py`)

**Purpose**: Replaces Coolify with native Git repository monitoring and auto-deployment.

**Features**:
- Monitors GitHub repository for changes every 30 seconds
- Automatically deploys code to all connected nodes
- Supports Windows PowerShell and Linux Bash commands
- Maintains SSH connections to remote nodes
- Provides deployment status and error tracking

**Key Methods**:
- `start_monitoring()` - Begin repository monitoring
- `manual_deploy()` - Trigger manual deployment
- `get_deployment_status()` - Get current deployment state
- `get_node_health()` - Check individual node health

### 2. Cross-Platform Node Manager (`quanttime/core/cross_platform_node_manager.py`)

**Purpose**: Unified interface for managing Windows and Linux nodes.

**Features**:
- Deploy QuantTime to mixed OS environments
- Start/stop Ray workers on remote nodes
- Monitor node health with color-coded status
- Execute commands on remote nodes
- Sync large files via SFTP

**Health Status**:
- 🟢 **Green**: All systems operational
- 🟡 **Yellow**: Connected but has issues
- 🔴 **Red**: Cannot connect to node

### 3. Enhanced SFTP Manager (`quanttime/core/sftp_manager.py`)

**Purpose**: Cross-platform large file synchronization.

**Enhanced Features**:
- Windows and Linux path handling
- Cross-platform file patterns
- Automated sync scheduling
- Git integration for discrepancy detection
- Progress monitoring and error recovery

### 4. Ray Cluster Configuration

**Updated Configuration** (`config/ray_cluster_config.json`):
```json
{
  "head_node": {
    "platform": "windows",
    "paths": {
      "project_root": "C:\\Users\\user\\Documents\\GitHub\\QuantTime",
      "python_executable": "python"
    }
  },
  "worker_nodes": [
    {
      "node_id": "windows_gpu",
      "platform": "windows",
      "resources": {"CPU": 16, "GPU": 1, "memory": 32.0}
    },
    {
      "node_id": "r630xl", 
      "platform": "linux",
      "resources": {"CPU": 16, "GPU": 0, "memory": 64.0}
    }
  ],
  "git_config": {
    "auto_pull_enabled": true,
    "monitor_interval_seconds": 30
  }
}
```

## Deployment Flow

### Automatic Deployment (Replaces Coolify)

1. **Git Monitoring**: System monitors GitHub repository every 30 seconds
2. **Change Detection**: Detects new commits on main branch
3. **Local Update**: Pulls changes to head node (laptop)
4. **Remote Deployment**: Deploys to all worker nodes via SSH
5. **SFTP Sync**: Synchronizes large files not in Git
6. **Ray Management**: Restarts Ray workers if needed
7. **Health Check**: Verifies all nodes are operational

### Manual Deployment

```bash
# Deploy to all nodes
python scripts/deploy_nodes.py full

# Deploy to specific node
python scripts/deploy_nodes.py deploy --node windows_gpu

# Check cluster health
python scripts/deploy_nodes.py health
```

## Node Communication

### SSH-Based Management

**Windows Nodes**:
- Uses OpenSSH Server (Windows 10/11)
- PowerShell command execution
- Windows path handling (`C:\QuantTime`)
- Registry-based configuration

**Linux Nodes**:
- Standard SSH server
- Bash command execution  
- Unix path handling (`/opt/quanttime`)
- Environment-based configuration

### Platform-Specific Commands

**Git Operations**:
```bash
# Windows
cd /d "C:\QuantTime" && git pull origin main

# Linux  
cd /opt/quanttime && git pull origin main
```

**Ray Workers**:
```bash
# Windows
ray start --address=laptop:10001 --working-dir="C:\QuantTime\temp\ray"

# Linux
ray start --address=laptop:10001 --working-dir=/opt/quanttime/temp/ray
```

## File Synchronization

### Git-Tracked Files
- **Method**: Git pull/push operations
- **Scope**: Source code, configuration, documentation
- **Frequency**: On commit detection (30-second intervals)

### Large Files (SFTP)
- **Method**: Secure File Transfer Protocol
- **Scope**: Models, data files, backtest results
- **Patterns**: `*.parquet`, `*.pkl`, `*.joblib`, `*.h5`
- **Frequency**: On deployment or manual trigger

### Sync Exclusions
- Virtual environments (`.venv`)
- Compiled files (`*.pyc`, `__pycache__`)
- Temporary files (`temp/*`)
- Git metadata (`.git`)

## Integration Points

### Dashboard Integration
- Real-time node status display
- Manual deployment triggers
- Health monitoring alerts
- File sync progress tracking

### Ray Job Distribution
- Automatic worker node detection
- Cross-platform job scheduling
- Resource-aware task assignment
- Windows GPU utilization

### Error Handling
- SSH connection recovery
- Git conflict resolution
- SFTP retry mechanisms
- Ray worker restart logic

## Security Considerations

### SSH Authentication
- Password-based authentication
- SSH key support
- Connection pooling and reuse
- Timeout handling

### Network Security
- Tailscale VPN networking
- Firewall-friendly ports
- Encrypted file transfers
- Secure credential storage

## Performance Optimizations

### Connection Management
- SSH connection pooling
- Parallel deployment operations
- Async file transfers
- Batch command execution

### Resource Efficiency
- Minimal memory footprint
- No Docker overhead
- Native OS process management
- Efficient file watching

## Monitoring and Logging

### Health Monitoring
- Node connectivity checks
- Git sync status tracking
- Ray worker health monitoring
- SFTP transfer logging

### Error Recovery
- Automatic retry mechanisms
- Graceful degradation
- Connection restoration
- Service restart capabilities

## Migration Benefits

### Advantages Over Coolify
- ✅ **Cross-Platform**: Windows + Linux support
- ✅ **Lightweight**: No Docker overhead
- ✅ **Faster**: Direct SSH communication
- ✅ **Flexible**: Native OS integration
- ✅ **Maintainable**: Pure Python implementation

### Maintained Capabilities
- ✅ **Auto-Deployment**: Git monitoring with auto-deploy
- ✅ **Health Monitoring**: Color-coded node status
- ✅ **File Sync**: SFTP for large files
- ✅ **Distributed Computing**: Ray cluster management
- ✅ **Dashboard Integration**: Unified web interface

## Usage Examples

### Basic Startup
```bash
# Start with automatic deployment
python run.py

# Dashboard available at: http://localhost:8501
# Ray dashboard at: http://localhost:8265
```

### Node Management
```python
from quanttime.core.cross_platform_node_manager import get_node_manager

manager = get_node_manager()

# Check cluster status
status = manager.get_cluster_overview()
print(f"Connected nodes: {status['connected_nodes']}")

# Deploy to specific node
success, message = manager.deploy_to_node("windows_gpu")

# Start Ray worker
success, message = manager.start_ray_cluster("windows_gpu")
```

### Git Monitoring
```python
from quanttime.core.cross_platform_git_watcher import get_git_watcher

watcher = get_git_watcher()

# Set GitHub PAT
watcher.set_github_pat("ghp_your_token_here")

# Start monitoring
watcher.start_monitoring()

# Manual deployment
results = watcher.manual_deploy(force=True)
```

This architecture provides a robust, cross-platform foundation for QuantTime's distributed computing needs while maintaining the automated deployment capabilities that Coolify provided, but with better flexibility and platform support.
