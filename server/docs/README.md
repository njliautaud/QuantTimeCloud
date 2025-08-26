# QuantTime Distributed Computing Server

Welcome to the QuantTime Distributed Computing Server! This comprehensive infrastructure enables you to leverage multiple servers as a high-performance computing cluster for quantitative trading operations.

## 🏗️ Architecture Overview

The QuantTime distributed system consists of:

- **Laptop**: Main command and control center running the Streamlit dashboard
- **R630XL**: Secondary control + compute node (16 cores, 64GB RAM)
- **R810**: Heavy compute workload server (32 cores, 256GB RAM)

## ✨ Features

### 🖥️ Server Management
- **Real-time Monitoring**: CPU, memory, disk, and network usage
- **Connection Status**: Live status of all servers in the cluster
- **Resource Allocation**: Dynamic job distribution based on available resources
- **Health Checks**: Automatic monitoring and recovery

### 📋 Job Management
- **Distributed Processing**: Automatically distribute jobs across servers
- **Queue Management**: Priority-based job scheduling
- **Progress Tracking**: Real-time progress monitoring for all jobs
- **Resource-Aware Scheduling**: Jobs assigned based on server capabilities

### 🔄 File Synchronization
- **Automatic Sync**: Real-time synchronization between all machines
- **Conflict Resolution**: Intelligent handling of file conflicts
- **Incremental Updates**: Efficient transfer of only changed data
- **Bidirectional Sync**: Data flows seamlessly between all nodes

### 📊 Real-time Dashboard
- **Server Control Center**: Comprehensive control panel in Streamlit sidebar
- **Performance Charts**: Visual monitoring of cluster performance
- **Job Queue Visualization**: See active, pending, and completed jobs
- **Resource Usage Graphs**: Historical and real-time resource usage

## 🚀 Quick Start

### 1. Initial Setup

```bash
# Run the quick deployment script
bash server/setup/quick_deploy.sh
```

This script will:
- Install all dependencies
- Configure networking between servers
- Set up SSH keys
- Deploy the project to all servers
- Start all services

### 2. Configuration

#### Server Configuration
Edit `server/config/servers.json` to match your server setup:

```json
{
  "r630xl": {
    "name": "R630XL Server",
    "ip_address": "jupiter",
    "username": "quanttime",
    "specs": {
      "cpu_cores": 16,
      "memory_gb": 64
    }
  },
  "r810": {
    "name": "R810 Heavy Compute",
    "ip_address": "saturn",
    "username": "quanttime",
    "specs": {
      "cpu_cores": 32,
      "memory_gb": 256
    }
  }
}
```

#### Environment Variables
Set your API keys and configuration in `.env`:

```bash
# API Keys
DATABENTO_API_KEY=your_databento_api_key_here

# Server Configuration
QUANTTIME_SERVER_HOST=0.0.0.0
QUANTTIME_SERVER_PORT=8000

# Database
DATABASE_URL=postgresql://quanttime:password@localhost/quanttime

# Redis
REDIS_URL=redis://localhost:6379/0
```

### 3. Starting the Dashboard

```bash
streamlit run quanttime/dashboard/app.py
```

The dashboard will be available at `http://localhost:8501` with the server control center in the left sidebar.

## 🛠️ Manual Setup

If you prefer manual setup or need to configure individual components:

### Server Installation

On each server (R630XL and R810):

```bash
# 1. Copy the project
rsync -avz QuantTime/ user@server:/opt/quanttime/

# 2. Run installation script
ssh user@server 'cd /opt/quanttime && sudo bash server/setup/install.sh'

# 3. Start services
ssh user@server 'cd /opt/quanttime && bash server/scripts/start_server.sh'
```

### Service Management

```bash
# Check service status
systemctl status quanttime-*

# Start services
sudo systemctl start quanttime-data-collector
sudo systemctl start quanttime-monitoring
sudo systemctl start quanttime-celery-worker

# View logs
journalctl -u quanttime-data-collector -f
```

## 📊 Using the Server Control Center

### Sidebar Controls

The left sidebar provides:

1. **Server Selection**: Choose which server to target for operations
2. **Connection Status**: Real-time status of all servers
3. **Resource Usage**: CPU, memory, and disk usage for selected server
4. **Job Queue**: Active, pending, and completed jobs
5. **File Sync Status**: Synchronization status and conflicts

### Main Dashboard

The "Servers" tab contains:

1. **Server Grid**: Visual status of all servers
2. **Performance Charts**: Historical resource usage
3. **Job Management**: Comprehensive job control interface
4. **File Management**: File synchronization tools

### Job Submission

Submit jobs to any server:

```python
# Example: Submit feature engineering job to R630XL
job_params = {
    "input_path": "data/AAPL_2024.parquet",
    "output_path": "features/AAPL_features.parquet",
    "feature_types": ["technical", "order_flow"]
}

# Job will be automatically routed to the selected server
```

## 🔧 Advanced Configuration

### Resource Thresholds

Configure when jobs should be rejected due to high resource usage:

```yaml
# server/config/deployment.yaml
monitoring:
  alert_thresholds:
    cpu_usage: 80
    memory_usage: 85
    disk_usage: 90
```

### Job Priorities

Jobs can be assigned priorities (1-10):

- **1-3**: Low priority (background tasks)
- **4-6**: Normal priority (default)
- **7-9**: High priority (time-sensitive)
- **10**: Critical priority (emergency tasks)

### File Sync Paths

Configure which directories are synchronized:

```python
sync_paths = {
    "data": {
        "local_path": "data/",
        "sync_enabled": True,
        "bidirectional": True
    },
    "models": {
        "local_path": "models/",
        "sync_enabled": True,
        "bidirectional": True
    }
}
```

## 🔒 Security

### SSH Key Setup

The system uses SSH keys for secure communication:

```bash
# Generate SSH key (if not exists)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa

# Copy to servers
ssh-copy-id quanttime@r630xl
ssh-copy-id quanttime@r810
```

### Firewall Configuration

Ensure these ports are open:

- **8000**: Main API server
- **6379**: Redis
- **5432**: PostgreSQL
- **22**: SSH

### API Authentication

All API calls require authentication tokens. Tokens are automatically managed by the dashboard.

## 📈 Monitoring and Alerting

### Health Checks

The system continuously monitors:

- **System Resources**: CPU, memory, disk usage
- **Service Status**: All QuantTime services
- **Network Connectivity**: Between servers
- **Job Performance**: Execution times and success rates

### Alerts

Alerts are triggered for:

- High resource usage (>80% CPU, >85% memory)
- Service failures
- Network connectivity issues
- Job failures or timeouts

### Metrics Collection

All metrics are stored in Redis and can be exported for external monitoring systems.

## 🐛 Troubleshooting

### Common Issues

1. **Server Offline**
   ```bash
   # Check SSH connectivity
   ssh quanttime@server_ip
   
   # Check services
   systemctl status quanttime-*
   ```

2. **Job Stuck in Queue**
   ```bash
   # Check Celery workers
   celery -A server.scripts.celery_app inspect active
   
   # Restart worker
   sudo systemctl restart quanttime-celery-worker
   ```

3. **File Sync Issues**
   ```bash
   # Check sync status
   curl http://server:8000/api/v1/files/sync/status
   
   # Force sync
   curl -X POST http://server:8000/api/v1/files/sync/force
   ```

### Log Files

Important log locations:

- **Main Server**: `logs/server.log`
- **Data Collector**: `logs/data_collector.log`
- **Monitoring**: `logs/monitoring.log`
- **Celery**: `logs/celery.log`

### Performance Tuning

For optimal performance:

1. **Increase Worker Processes**: Based on CPU cores
2. **Adjust Memory Limits**: Based on available RAM
3. **Configure Batch Sizes**: For data processing jobs
4. **Optimize Network**: Use dedicated network interfaces

## 🔄 Backup and Recovery

### Automated Backups

Daily backups are automatically created:

- **Data**: Compressed and encrypted
- **Models**: Versioned storage
- **Configuration**: Full system state

### Recovery Procedures

In case of server failure:

1. **Automatic Failover**: Jobs redirect to available servers
2. **Data Recovery**: From latest backup
3. **Service Restart**: Automatic recovery attempts

## 📚 API Reference

### Server Management

```bash
# Get server info
GET /api/v1/server/info

# Get system resources
GET /api/v1/server/resources

# Health check
GET /api/v1/server/health
```

### Job Management

```bash
# Submit job
POST /api/v1/jobs/submit

# Get job status
GET /api/v1/jobs/{job_id}

# List all jobs
GET /api/v1/jobs

# Cancel job
DELETE /api/v1/jobs/{job_id}
```

### File Synchronization

```bash
# Transfer files
POST /api/v1/files/transfer

# Sync status
GET /api/v1/files/sync/status
```

## 🤝 Contributing

When adding new features to the distributed system:

1. **Server Component**: Add to `server/core/`
2. **Dashboard Integration**: Update `quanttime/dashboard/server_control.py`
3. **API Endpoints**: Extend `server/core/server_api.py`
4. **Documentation**: Update this README

## 📞 Support

For issues or questions:

1. Check the troubleshooting section above
2. Review log files for error messages
3. Test network connectivity between servers
4. Verify all services are running

The QuantTime distributed computing system is designed to be robust and self-healing, but proper monitoring and maintenance will ensure optimal performance.
