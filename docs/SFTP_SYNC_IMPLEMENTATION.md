# SFTP Large File Sync Implementation

## Overview

This document describes the implementation of the **SFTP Large File Synchronization System** for QuantTime, which replaces Syncthing for managing large files (models, data, backtest results) between nodes while using Git for code synchronization.

## Architecture

### **Segmented Sync Strategy**

```
QuantTime/
├── Code Repository (Git)           # Fast, version-controlled sync
│   ├── quanttime/                  # Python code
│   ├── scripts/                    # Automation scripts
│   ├── config/                     # Configuration files
│   └── docs/                       # Documentation
└── Large Files (SFTP)              # Large file sync
    ├── data/es_futures/            # MBO data (31.7 GiB)
    ├── models/                     # Trained models
    ├── backtest/results/           # Backtest outputs
    └── logs/                       # Log files
```

### **Sync Protocols**

1. **Git (Code)**: Fast, version-controlled synchronization
2. **SFTP (Large Files)**: Efficient large file transfer with conflict detection

## Components

### **1. SFTP Manager (`quanttime/core/sftp_manager.py`)**

**Core Features:**
- **Multi-node SFTP management** with SSH connections
- **Automatic discrepancy detection** using file checksums
- **Smart sync scheduling** with priority queues
- **Ray integration** for distributed processing
- **Real-time monitoring** and status tracking

**Key Classes:**
- `SFTPNode`: Represents a node with connection details
- `FileInfo`: File metadata for sync tracking
- `SyncTask`: Represents a sync operation
- `SFTPManager`: Main manager class

### **2. Dashboard Interface (`quanttime/dashboard/sftp_interface.py`)**

**Features:**
- **Sync Status Monitoring**: Real-time node and task status
- **Manual Sync Control**: Select files and nodes for sync
- **Configuration Management**: Node and sync settings
- **Analytics Dashboard**: Sync statistics and history
- **Ray Integration**: Submit sync jobs to Ray cluster

### **3. Automated Git Sync (`scripts/auto_git_sync.py`)**

**Features:**
- **Watch mode**: Continuous monitoring and sync
- **Auto-commit**: Automatic code change detection
- **Conflict resolution**: Smart merge strategies
- **Logging**: Comprehensive sync logging

## Configuration

### **SFTP Configuration (`config/sftp_config.json`)**

```json
{
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
```

### **Git Ignore Configuration (`.gitignore`)**

```gitignore
# Large data files (managed by SFTP)
data/es_futures/
data/backup/
data/processed/
data/raw/
data/live/

# Model files
models/*.pkl
models/*.joblib
models/*.h5
models/*.pt
models/trained/

# Backtest results
backtest/results/
backtest/output/

# Log files
logs/
*.log

# Cache and temporary files
cache/
temp/
__pycache__/
*.pyc
```

## Usage

### **1. Dashboard Management**

**Access SFTP Interface:**
1. Start QuantTime dashboard: `python run.py`
2. Navigate to **Settings** → **SFTP Large File Sync**
3. Monitor sync status and manage operations

**Key Dashboard Features:**
- **Sync Status**: Real-time node connectivity and sync progress
- **Manual Sync**: Select specific files and nodes for sync
- **Auto-Sync**: Automatically resolve discrepancies
- **Analytics**: Sync statistics and performance metrics

### **2. Command Line Usage**

**Git Auto-Sync:**
```bash
# Single sync
python scripts/auto_git_sync.py

# Watch mode (continuous sync)
python scripts/auto_git_sync.py --watch --interval 60

# Status check
python scripts/auto_git_sync.py --status
```

**SFTP Manual Sync:**
```python
from quanttime.core.sftp_manager import get_sftp_manager

# Get SFTP manager
sftp_manager = get_sftp_manager()

# Auto-sync discrepancies
sftp_manager.auto_sync_large_files()

# Manual sync specific files
task_id = sftp_manager.create_sync_task(
    source_node="laptop",
    target_node="r630xl",
    file_paths=["/path/to/large/file.dat"],
    priority="high"
)
```

### **3. Ray Integration**

**Submit SFTP Sync Job:**
```python
from quanttime.core.ray_manager import get_ray_manager

ray_manager = get_ray_manager()

# Submit distributed sync job
job_id = ray_manager.submit_job(
    name="sftp_sync_large_files",
    function=quanttime_sftp_sync_job,
    config={
        "source_node": "laptop",
        "target_node": "r630xl",
        "sync_type": "auto"
    },
    resources={"CPU": 1},
    priority="high"
)
```

## Smart Features

### **1. Discrepancy Detection**

**Automatic Detection:**
- **File existence**: Missing files on target nodes
- **Checksum comparison**: File content differences
- **Timestamp comparison**: Version conflicts
- **Size validation**: Corrupted or incomplete files

**Resolution Strategies:**
- **Missing files**: Copy from source to target
- **Checksum mismatch**: Sync newer version
- **Size mismatch**: Re-sync corrupted files

### **2. Intelligent Sync**

**Priority Management:**
- **High priority**: Critical model files, recent backtest results
- **Normal priority**: Regular data files
- **Low priority**: Log files, temporary data

**Parallel Processing:**
- **Multiple transfers**: Up to 4 parallel file transfers
- **Chunked transfers**: Large files split into 10MB chunks
- **Resume capability**: Interrupted transfers can resume

### **3. Monitoring & Analytics**

**Real-time Monitoring:**
- **Node status**: Online/offline status
- **Sync progress**: File-by-file progress tracking
- **Error tracking**: Failed transfers and retry attempts
- **Performance metrics**: Transfer speeds and completion times

**Analytics Dashboard:**
- **Sync statistics**: Total files, transfer volumes
- **Performance trends**: Speed improvements over time
- **Error analysis**: Common failure patterns
- **Resource utilization**: CPU and network usage

## Integration with Ray

### **Distributed Sync Jobs**

**Ray Job Types:**
- **Auto-sync**: Automatic discrepancy detection and resolution
- **Manual sync**: User-selected files and nodes
- **Bulk sync**: Large dataset synchronization
- **Incremental sync**: Only changed files

**Resource Management:**
- **CPU allocation**: Dedicated CPU cores for sync operations
- **Memory management**: Efficient memory usage for large files
- **Network optimization**: Bandwidth-aware transfer scheduling

### **Job Monitoring**

**Ray Dashboard Integration:**
- **Job status**: Real-time sync job progress
- **Resource usage**: CPU, memory, and network utilization
- **Error reporting**: Detailed error logs and stack traces
- **Performance metrics**: Transfer speeds and completion rates

## Security

### **SSH Authentication**

**Supported Methods:**
- **SSH Key Authentication**: Secure key-based access
- **Password Authentication**: Traditional password access
- **Multi-factor Authentication**: Enhanced security options

**Security Features:**
- **Encrypted transfers**: All data encrypted in transit
- **Host verification**: SSH host key validation
- **Connection logging**: Comprehensive access logs
- **Error handling**: Secure error reporting

## Performance Optimization

### **Transfer Optimization**

**Efficient Protocols:**
- **SCP**: Fast file transfer protocol
- **Chunked transfers**: Large file segmentation
- **Parallel connections**: Multiple simultaneous transfers
- **Compression**: Optional data compression

**Network Optimization:**
- **Bandwidth monitoring**: Real-time bandwidth usage
- **Throttling**: Configurable transfer speed limits
- **Retry logic**: Automatic retry with exponential backoff
- **Connection pooling**: Reuse SSH connections

### **Resource Management**

**Memory Efficiency:**
- **Streaming transfers**: Large files processed in chunks
- **Garbage collection**: Automatic memory cleanup
- **Connection limits**: Prevent resource exhaustion
- **Timeout handling**: Automatic connection cleanup

## Troubleshooting

### **Common Issues**

**Connection Problems:**
```bash
# Test SSH connectivity
ssh jupiter@jupiter "echo 'Connection successful'"

# Check SFTP manager status
python -c "from quanttime.core.sftp_manager import get_sftp_manager; print(get_sftp_manager().get_sync_status())"
```

**Sync Failures:**
```bash
# Check sync logs
tail -f auto_git_sync.log

# Verify file permissions
ls -la /opt/quanttime/data/

# Test file transfer manually
scp /path/to/file jupiter@jupiter:/opt/quanttime/
```

**Ray Job Issues:**
```python
# Check Ray cluster status
import ray
ray.init()
print(ray.cluster_resources())

# Monitor Ray jobs
from quanttime.core.ray_manager import get_ray_manager
ray_manager = get_ray_manager()
print(ray_manager.get_all_jobs())
```

### **Debugging Tools**

**SFTP Manager Debug:**
```python
from quanttime.core.sftp_manager import get_sftp_manager

sftp_manager = get_sftp_manager()

# Test node connections
for node_id, node in sftp_manager.nodes.items():
    ssh = sftp_manager._get_ssh_connection(node)
    print(f"{node_id}: {'Connected' if ssh else 'Failed'}")
    if ssh:
        ssh.close()

# Scan for large files
for node_id, node in sftp_manager.nodes.items():
    files = sftp_manager._scan_large_files(node)
    print(f"{node_id}: {len(files)} large files found")
```

## Migration from Syncthing

### **Migration Steps**

1. **Stop Syncthing Services:**
   ```bash
   # On all nodes
   sudo pkill -f syncthing
   sudo systemctl stop syncthing@jupiter
   ```

2. **Initialize Git Repository:**
   ```bash
   # On laptop
   cd /path/to/quanttime
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo>
   git push -u origin main
   ```

3. **Setup SFTP Configuration:**
   ```bash
   # Create SFTP config
   mkdir -p config
   # Edit config/sftp_config.json with your node details
   ```

4. **Start Auto-Sync Services:**
   ```bash
   # Start Git auto-sync
   python scripts/auto_git_sync.py --watch &

   # Start SFTP manager
   python -c "from quanttime.core.sftp_manager import get_sftp_manager; get_sftp_manager()"
   ```

### **Verification**

**Check Sync Status:**
```python
# Verify Git sync
git status
git log --oneline -5

# Verify SFTP sync
from quanttime.core.sftp_manager import get_sftp_manager
status = get_sftp_manager().get_sync_status()
print(status)
```

## Future Enhancements

### **Planned Features**

1. **Advanced Conflict Resolution:**
   - **Merge strategies**: Automatic file merging
   - **Version control**: File versioning for large files
   - **Conflict detection**: Advanced conflict identification

2. **Performance Improvements:**
   - **Delta sync**: Only sync changed portions of files
   - **Compression**: Advanced compression algorithms
   - **Caching**: Local file caching for faster access

3. **Enhanced Monitoring:**
   - **Webhooks**: Real-time sync notifications
   - **Metrics export**: Prometheus/Grafana integration
   - **Alerting**: Automated error notifications

4. **Scalability Features:**
   - **Multi-region sync**: Cross-region file synchronization
   - **Load balancing**: Automatic load distribution
   - **Auto-scaling**: Dynamic resource allocation

## Conclusion

The SFTP Large File Sync implementation provides a robust, scalable solution for managing large files in the QuantTime distributed computing environment. By separating code sync (Git) from large file sync (SFTP), the system achieves optimal performance while maintaining data integrity and providing comprehensive monitoring capabilities.

The integration with Ray enables distributed processing of sync operations, making the system suitable for large-scale deployments with multiple nodes and extensive datasets.
