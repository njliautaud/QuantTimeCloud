# QuantTime Node Setup Guide

This guide explains how to set up individual nodes (laptop, R630XL, R810) with complete environment isolation, ensuring each node maintains its own configuration and dependencies.

## Overview

The QuantTime distributed system uses a **node-based setup approach** where each node:
1. **Runs its own setup script** to create a complete environment
2. **Maintains environment isolation** - no shared configurations between nodes
3. **Uses node-specific paths and settings** based on platform detection
4. **Can be launched independently** after setup

## Node Setup Process

### Step 1: Initial Setup (One-time per node)

Each node must run the setup script to establish its environment:

#### On Windows (Laptop):
```bash
# Navigate to project directory
cd C:\Users\user\Documents\GitHub\QuantTime

# Run setup script
python scripts/setup_node.py --node-name laptop
```

#### On Linux (R630XL/R810):
```bash
# Navigate to project directory
cd /opt/quanttime

# Run setup script
python3 scripts/setup_node.py --node-name r630xl
```

### Step 2: Environment Activation

After setup, activate the node-specific environment:

#### Windows:
```bash
# Run the environment script
C:\Users\user\Documents\GitHub\QuantTime\setup_env.bat
```

#### Linux:
```bash
# Source the environment script
source /opt/quanttime/setup_env.sh
```

### Step 3: Launch Node Services

Use the launcher script to start Ray and dashboard services:

#### Head Node (Laptop):
```bash
# Start as head node with dashboard
python scripts/launch_node.py --head --dashboard
```

#### Worker Nodes (R630XL/R810):
```bash
# Start as worker node
python3 scripts/launch_node.py
```

## Environment Isolation Features

### Automatic Platform Detection
- **Windows**: Uses Windows-specific paths and commands
- **Linux**: Uses Linux-specific paths and commands
- **Architecture**: Detects CPU architecture for optimization

### Node-Specific Configuration
Each node creates its own configuration files:
- `config/node_{node_name}.json` - Node-specific settings
- `config/ray_config.json` - Ray cluster configuration
- `setup_env.sh` / `setup_env.bat` - Environment activation script

### Path Isolation
Each node uses platform-appropriate paths:

#### Windows Paths:
```
Project Root: C:\Users\user\Documents\GitHub\QuantTime
Data: C:\Users\user\Documents\GitHub\QuantTime\data
Logs: C:\Users\user\Documents\GitHub\QuantTime\logs
Virtual Env: C:\Users\user\Documents\GitHub\QuantTime\.venv
Ray Temp: C:\Users\user\Documents\GitHub\QuantTime\temp\ray
```

#### Linux Paths:
```
Project Root: /opt/quanttime
Data: /opt/quanttime/data
Logs: /opt/quanttime/logs
Virtual Env: /opt/quanttime/.venv
Ray Temp: /tmp/ray
```

### Sync Exclusions
Environment-specific files are excluded from synchronization:
- `.env` files
- `config/local_*` files
- `logs/*` directories
- `cache/*` directories
- `temp/*` directories
- `.venv/*` virtual environments
- `__pycache__/*` Python cache
- `*.pyc` compiled Python files
- `node_*.json` node-specific configs

## Dashboard Deployment

### Automated Deployment
The dashboard can deploy to all nodes automatically:

1. **Navigate to Dashboard**: Settings → 🚀 Deploy
2. **Check Health Status**: See color-coded node status
3. **Deploy All Nodes**: One-click deployment to all nodes
4. **Start Ray Clusters**: Launch Ray on all nodes
5. **Sync Large Files**: Transfer data files via SFTP

### Manual Deployment
For manual deployment, use the command-line script:

```bash
# Deploy to all nodes
python scripts/deploy_nodes.py full

# Deploy to specific node
python scripts/deploy_nodes.py deploy

# Check health status
python scripts/deploy_nodes.py health
```

## Node Health Monitoring

### Color-Coded Status
- **🟢 Green**: All systems operational
- **🟡 Yellow**: Connected but issues (missing deps, version mismatch)
- **🔴 Red**: Cannot connect

### Health Checks
Each node is checked for:
1. **Connectivity**: SSH reachability
2. **Git Status**: Repository existence and sync status
3. **Dependencies**: Python packages and virtual environment
4. **Ray Status**: Ray installation and cluster status

## Troubleshooting

### Setup Issues
```bash
# Force recreation of virtual environment
python scripts/setup_node.py --node-name laptop --force

# Check setup logs
tail -f logs/setup.log
```

### Launch Issues
```bash
# Check launcher logs
tail -f logs/launch.log

# Manual Ray start
ray start --head --port=10001 --dashboard-port=8265
```

### Environment Issues
```bash
# Recreate environment script
python scripts/setup_node.py --node-name laptop

# Check node config
cat config/node_laptop.json
```

## Best Practices

### Node Independence
- Each node should be able to run independently
- No shared state between nodes
- Environment variables are node-specific
- Configuration files are generated per node

### Deployment Workflow
1. **Setup**: Run `setup_node.py` on each node
2. **Activate**: Source environment script
3. **Launch**: Use `launch_node.py` to start services
4. **Monitor**: Use dashboard for health monitoring
5. **Deploy**: Use dashboard for code updates

### Maintenance
- Regularly check node health status
- Update dependencies via dashboard
- Monitor logs for issues
- Use SFTP for large file synchronization

## Configuration Files

### Node Configuration (`config/node_{name}.json`)
```json
{
  "node": {
    "name": "laptop",
    "platform": "windows",
    "arch": "x86_64",
    "python_version": "3.11"
  },
  "paths": {
    "project_root": "C:\\Users\\user\\Documents\\GitHub\\QuantTime",
    "data": "C:\\Users\\user\\Documents\\GitHub\\QuantTime\\data",
    "logs": "C:\\Users\\user\\Documents\\GitHub\\QuantTime\\logs"
  },
  "ray": {
    "temp_dir": "C:\\Users\\user\\Documents\\GitHub\\QuantTime\\temp\\ray",
    "log_dir": "C:\\Users\\user\\Documents\\GitHub\\QuantTime\\logs\\ray",
    "dashboard_port": 8265,
    "head_port": 10001
  },
  "environment": {
    "isolated": true,
    "auto_setup": true,
    "sync_exclusions": [".env", "logs/*", ".venv/*"]
  }
}
```

### Ray Configuration (`config/ray_config.json`)
```json
{
  "cluster": {
    "head_node": {
      "ip": "localhost",
      "port": 10001,
      "dashboard_port": 8265
    },
    "worker_nodes": []
  },
  "resources": {
    "num_cpus": 8,
    "memory": "8000000000",
    "object_store_memory": "2000000000"
  },
  "temp_dir": "/tmp/ray",
  "log_dir": "/opt/quanttime/logs/ray"
}
```

## Next Steps

After completing node setup:

1. **Start Dashboard**: Run `python run.py` on the head node
2. **Monitor Health**: Check node status in dashboard
3. **Submit Jobs**: Use dashboard to submit Ray jobs
4. **Sync Data**: Use SFTP interface for large file transfer
5. **Scale**: Add more nodes as needed

For additional help, see the main [README.md](../README.md) or contact the development team.
