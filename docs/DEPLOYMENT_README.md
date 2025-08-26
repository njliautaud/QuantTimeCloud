# QuantTime Deployment Guide

## Overview

This guide explains how to deploy QuantTime across multiple nodes (laptop, desktop, server) while maintaining full current functionality. The system is designed as **laptop-first**, meaning your laptop can operate entirely independently, with desktop and server deployments as optional extensions.

## Quick Start

### Option 1: Laptop Only (Current Setup)
**No changes required!** Your current QuantTime installation continues to work exactly as before.

### Option 2: Laptop + Desktop
For enhanced training capabilities:
1. Run `desktop/setup/install.sh` on your desktop machine
2. Configure SSH access between laptop and desktop
3. Use the enhanced Streamlit dashboard to manage both nodes

### Option 3: Laptop + Server
For 24/7 data warehousing:
1. Run `server/setup/install.sh` on your server (as root)
2. Configure SSH access between laptop and server
3. Use the enhanced Streamlit dashboard to manage both nodes

### Option 4: Full Deployment (Laptop + Desktop + Server)
For maximum capability:
1. Deploy all three nodes using the scripts above
2. Configure SSH access between all nodes
3. Use the enhanced Streamlit dashboard to manage all nodes

## Architecture Overview

```
┌─────────────────┐    SSH    ┌─────────────────┐    SSH    ┌─────────────────┐
│     LAPTOP      │◄─────────►│     DESKTOP     │◄─────────►│     SERVER      │
│   (Primary)     │           │   (Training)    │           │  (Data/24-7)    │
│                 │           │                 │           │                 │
│ • Streamlit UI  │           │ • Enhanced      │           │ • Data          │
│ • Live Trading  │           │   Training      │           │   Collection    │
│ • Development   │           │ • Data          │           │ • Model         │
│ • Model         │           │   Processing    │           │   Deployment    │
│   Deployment    │           │ • Resource      │           │ • Monitoring    │
│                 │           │   Management    │           │                 │
└─────────────────┘           └─────────────────┘           └─────────────────┘
```

## Current Functionality Preservation

### ✅ What Stays the Same
- **All existing code**: No changes to your current QuantTime installation
- **All existing features**: Databento integration, data management, model training, etc.
- **All existing workflows**: Your current development and trading processes
- **All existing data**: Your current data files and models remain untouched
- **All existing configuration**: Your current settings and API keys

### 🆕 What's Added (Optional)
- **Desktop extension**: Enhanced training and data processing
- **Server extension**: 24/7 data warehousing and automated operations
- **Cross-node management**: Single dashboard to control all nodes
- **Resource management**: Automatic throttling and optimization
- **Data synchronization**: Automatic sync between nodes

## Deployment Options

### 1. Laptop Only (Recommended for Start)
**Perfect for**: Development, testing, small-scale trading
**Capabilities**: Everything you have now
**Setup**: No changes required

```bash
# Your current setup continues to work
python run.py
```

### 2. Laptop + Desktop
**Perfect for**: Enhanced training, large-scale data processing
**Capabilities**: 
- Laptop: Live trading, development, model deployment
- Desktop: Intensive training, data processing, resource management

**Setup**:
```bash
# On desktop machine
cd /path/to/quanttime
chmod +x desktop/setup/install.sh
./desktop/setup/install.sh

# Configure SSH access from laptop to desktop
# Edit .env file with your API keys
# Start desktop services
./desktop/scripts/start_desktop.sh
```

### 3. Laptop + Server
**Perfect for**: 24/7 data collection, production trading
**Capabilities**:
- Laptop: Development, model training, strategy testing
- Server: 24/7 data collection, automated model deployment

**Setup**:
```bash
# On server machine (as root)
cd /opt/quanttime
chmod +x server/setup/install.sh
./server/setup/install.sh

# Configure SSH access from laptop to server
# Edit /opt/quanttime/.env file with your API keys
# Start server services
/opt/quanttime/server/scripts/start_server.sh
```

### 4. Full Deployment
**Perfect for**: Maximum capability, enterprise-scale operations
**Capabilities**: All features from all deployment options

## Configuration

### Environment Variables
Each deployment type has its own `.env` file:

**Laptop** (current):
```bash
# No changes needed - your current setup continues to work
```

**Desktop**:
```bash
# desktop/.env
QUANTTIME_DEPLOYMENT=desktop
QUANTTIME_NODE_TYPE=desktop
QUANTTIME_CONFIG_PATH=desktop/config/deployment.yaml
# ... other desktop-specific settings
```

**Server**:
```bash
# /opt/quanttime/.env
QUANTTIME_DEPLOYMENT=server
QUANTTIME_NODE_TYPE=server
QUANTTIME_CONFIG_PATH=server/config/deployment.yaml
# ... other server-specific settings
```

### SSH Configuration
Set up SSH access between nodes:

```bash
# Generate SSH keys (if not already present)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""

# Copy public key to other nodes
ssh-copy-id user@desktop-ip
ssh-copy-id user@server-ip

# Test connectivity
ssh desktop "echo 'Desktop connection successful'"
ssh server "echo 'Server connection successful'"
```

## Usage

### Starting Services

**Laptop** (current):
```bash
python run.py
```

**Desktop**:
```bash
./desktop/scripts/start_desktop.sh
```

**Server**:
```bash
/opt/quanttime/server/scripts/start_server.sh
```

### Stopping Services

**Desktop**:
```bash
./desktop/scripts/stop_desktop.sh
```

**Server**:
```bash
/opt/quanttime/server/scripts/stop_server.sh
```

### Monitoring

**Check service status**:
```bash
# Desktop
systemctl status quanttime-desktop

# Server
systemctl status quanttime-*
```

**View logs**:
```bash
# Desktop
tail -f logs/desktop.log

# Server
tail -f /opt/quanttime/logs/server.log
```

## Enhanced Streamlit Dashboard

When you have multiple nodes deployed, the Streamlit dashboard automatically detects them and provides additional tabs:

### New Tabs (when nodes are deployed)

**Node Management**:
- View status of all nodes
- Monitor resource usage
- Check connectivity
- View health metrics

**Job Management**:
- Deploy training jobs to desktop
- Monitor job progress
- View job logs
- Manage job queues

**Data Sync**:
- Monitor data synchronization
- Manual sync controls
- Sync history and status
- Conflict resolution

**Model Management**:
- Deploy models to server
- Monitor model performance
- Model version control
- Rollback capabilities

## Data Flow

### Laptop → Desktop
- **Models**: Trained models for deployment
- **Configurations**: Trading strategies and parameters
- **Results**: Backtest results and analysis

### Laptop → Server
- **Models**: Production-ready models
- **Configurations**: Live trading parameters
- **Commands**: Start/stop trading operations

### Server → Laptop/Desktop
- **Live Data**: Real-time market data feeds
- **Historical Data**: Processed historical datasets
- **Logs**: System and trading logs

### Desktop → Laptop
- **Training Results**: Model performance metrics
- **Processed Data**: Feature-engineered datasets
- **Analysis**: Detailed backtest reports

## Resource Management

### Training While Trading
- **Desktop**: Allowed with hard-capped resources
- **Auto-throttling**: CPU/IO/GPU limits when live latency rises
- **Priority System**: Live trading takes precedence over training

### Resource Limits
**Desktop**:
- CPU: 80% maximum during training
- Memory: 85% maximum
- GPU: 90% maximum
- Auto-throttle when live trading active

**Server**:
- CPU: 70% maximum
- Memory: 80% maximum
- Disk: 85% maximum
- Continuous operation with monitoring

## Troubleshooting

### Common Issues

**SSH Connection Failed**:
```bash
# Check SSH keys
ls -la ~/.ssh/

# Test connection
ssh -v user@node-ip

# Regenerate keys if needed
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
```

**Service Won't Start**:
```bash
# Check logs
journalctl -u quanttime-* -f

# Check configuration
python -c "import yaml; yaml.safe_load(open('config/deployment.yaml'))"

# Restart service
systemctl restart quanttime-*
```

**Data Sync Issues**:
```bash
# Check sync status
python shared/utils/sync_manager.py --status

# Manual sync
python shared/utils/sync_manager.py --sync

# Check conflicts
python shared/utils/sync_manager.py --conflicts
```

### Getting Help

1. **Check logs**: All services log to their respective log directories
2. **Check status**: Use `systemctl status` for service status
3. **Check connectivity**: Use SSH to test node-to-node communication
4. **Check configuration**: Validate YAML configuration files

## Migration Strategy

### Phase 1: Test Current Setup
1. Verify your current QuantTime installation works perfectly
2. Document your current configuration and workflows
3. Create a backup of your current setup

### Phase 2: Add Desktop (Optional)
1. Set up desktop deployment
2. Test data synchronization
3. Test training job deployment
4. Verify no impact on laptop functionality

### Phase 3: Add Server (Optional)
1. Set up server deployment
2. Test data collection
3. Test model deployment
4. Verify no impact on laptop/desktop functionality

### Phase 4: Integration
1. Test cross-node communication
2. Test enhanced dashboard features
3. Optimize performance
4. Document new workflows

## Security Considerations

### SSH Security
- Use key-based authentication only
- Disable password authentication
- Use non-standard SSH ports (optional)
- Regularly rotate SSH keys

### Network Security
- Use firewalls to restrict access
- Only allow necessary ports
- Use VPN for remote access (recommended)
- Monitor network traffic

### Data Security
- Encrypt sensitive data
- Use secure API keys
- Regular backups
- Access control and logging

## Performance Optimization

### Desktop Optimization
- Use SSD storage for data
- Optimize GPU usage
- Configure appropriate batch sizes
- Monitor resource usage

### Server Optimization
- Use RAID storage for data
- Optimize database performance
- Configure appropriate worker counts
- Monitor system resources

### Network Optimization
- Use high-speed connections
- Optimize data transfer protocols
- Compress data during transfer
- Monitor network latency

## Maintenance

### Regular Tasks
- **Daily**: Check service status and logs
- **Weekly**: Review performance metrics
- **Monthly**: Update dependencies and security patches
- **Quarterly**: Full system audit and optimization

### Backup Strategy
- **Configuration**: Backup all config files
- **Data**: Regular data backups
- **Models**: Version control for models
- **Logs**: Archive old logs

### Monitoring
- **System**: CPU, memory, disk usage
- **Application**: Service status, error rates
- **Network**: Connectivity, latency
- **Business**: Trading performance, model accuracy

## Support

### Documentation
- `docs/DEPLOYMENT_ARCHITECTURE.md`: Detailed architecture
- `docs/IMPLEMENTATION_PLAN.md`: Implementation details
- `desktop/docs/`: Desktop-specific documentation
- `server/docs/`: Server-specific documentation

### Getting Help
1. Check the troubleshooting section above
2. Review the logs for error messages
3. Check the documentation for your specific deployment
4. Create an issue with detailed error information

## Conclusion

The QuantTime deployment architecture is designed to be **incremental** and **non-disruptive**. You can:

1. **Start with your current setup** - no changes required
2. **Add desktop when needed** - for enhanced training
3. **Add server when needed** - for 24/7 operations
4. **Use all three** - for maximum capability

Each step is optional and builds upon the previous one, ensuring you always have a working system while gaining additional capabilities as needed.

**Remember**: Your laptop remains the primary control center, and all existing functionality continues to work exactly as before.
