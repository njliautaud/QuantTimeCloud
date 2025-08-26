# QuantTime Server Integration

## Overview

The QuantTime Server Integration provides a comprehensive distributed computing infrastructure for your quant homelab, enabling you to offload heavy computational workloads (data normalization, feature engineering, model training, backtesting) to dedicated servers while maintaining full control through a centralized dashboard on your laptop.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    QuantTime Distributed Computing              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │   Laptop        │    │   R630XL        │    │   R810          │ │
│  │   (Control)     │    │   (Workhorse)   │    │   (Heavy)       │ │
│  │                 │    │                 │    │                 │ │
│  │ • Dashboard     │    │ • 16 CPU Cores  │    │ • 32 CPU Cores  │ │
│  │ • Task Control  │    │ • 64GB RAM      │    │ • 256GB RAM     │ │
│  │ • Monitoring    │    │ • Data Proc     │    │ • Model Train   │ │
│  │ • Results View  │    │ • Feature Eng   │    │ • Backtesting   │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘ │
│           │                       │                       │       │
│           └───────────────────────┼───────────────────────┘       │
│                                   │                               │
│                      ┌─────────────────┐                         │
│                      │   Tailscale     │                         │
│                      │   VPN Network   │                         │
│                      └─────────────────┘                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

### 🖥️ **Enhanced Server Control Center**
- **Slide Tab Device Selection**: Visual device selector in sidebar with real-time status indicators
- **Real-time Monitoring**: Live resource usage, connection status, and job queue monitoring
- **Server Status Overview**: Comprehensive view of all servers with expandable details
- **Quick Actions**: One-click server management operations

### 🚀 **Task Submission Interface**
- **Multi-Task Support**: Data normalization, feature engineering, model training, backtesting
- **Parameter Configuration**: Intuitive parameter setup for each task type
- **Device Capability Checking**: Automatic validation of device capabilities
- **Progress Tracking**: Real-time task progress monitoring

### 📊 **Distributed Computing Capabilities**
- **Data Normalization**: Offload data cleaning and preprocessing to R630XL
- **Feature Engineering**: Generate features using R630XL's processing power
- **Model Training**: Leverage R810's 256GB RAM for large model training
- **Backtesting**: Run comprehensive backtests on R810's 32 CPU cores

### 🔧 **Infrastructure Management**
- **Automated Deployment**: One-command server setup with Ubuntu 22.04
- **Tailscale VPN**: Secure remote access without port forwarding
- **Systemd Services**: Production-ready service management
- **Health Monitoring**: Automated health checks and alerting

## Quick Start

### 1. Prepare Your Infrastructure

#### Hardware Requirements
- **R630XL Server**: 16 CPU cores, 64GB RAM, 2TB storage
- **R810 Server**: 32 CPU cores, 256GB RAM, 4TB storage
- **Laptop**: 8+ CPU cores, 16GB+ RAM (control center)

#### Software Requirements
- Ubuntu 22.04 LTS on both servers
- Tailscale account and auth keys
- Python 3.8+ on all devices

### 2. Deploy Servers

#### Option A: Interactive Deployment
```bash
# Run the interactive deployment script
python server/setup/quick_deploy.py
```

#### Option B: Manual Deployment
```bash
# Follow the detailed deployment guide
# See: server/docs/DEPLOYMENT_GUIDE.md
```

### 3. Launch Dashboard
```bash
# Start the enhanced dashboard
python run.py dashboard --port 8501
```

### 4. Test Distributed Computing
1. Navigate to "Task Submission" tab
2. Select target device (R630XL or R810)
3. Choose task type and configure parameters
4. Submit task and monitor progress

## Usage Guide

### Server Control Center

The enhanced sidebar provides comprehensive server management:

#### Device Selection
- **Visual Tabs**: Click on device tabs to select target server
- **Status Indicators**: Green/red indicators show connection status
- **Device Info**: View CPU cores, memory, and capabilities

#### Server Status
- **Connection Status**: Real-time online/offline status
- **Resource Usage**: CPU, memory, and disk utilization
- **Job Queue**: Active and queued job counts
- **Last Check**: Timestamp of last status update

#### Quick Actions
- **Check All**: Test connections to all servers
- **Sync All**: Synchronize data from all servers
- **Deploy**: Deploy code to selected server
- **Monitor**: Open detailed monitoring view

### Task Submission

Submit computational tasks to any device:

#### Available Task Types

1. **Data Normalization** 📊
   - Clean and normalize raw market data
   - Support for multiple data sources
   - Configurable normalization methods

2. **Feature Engineering** 🔧
   - Generate technical indicators
   - Create orderbook features
   - Customizable feature sets

3. **Model Training** 🤖
   - Train machine learning models
   - Hyperparameter optimization
   - Cross-validation support

4. **Backtesting** 📈
   - Run comprehensive backtests
   - Configurable trading parameters
   - Performance analysis

#### Task Configuration
- **Parameter Validation**: Automatic validation of input parameters
- **Device Compatibility**: Check device capabilities before submission
- **Progress Tracking**: Real-time progress updates
- **Result Collection**: Automatic result retrieval

### Task Monitoring

Monitor and manage submitted tasks:

#### Task Status
- **Submitted**: Task queued for execution
- **Running**: Task currently executing
- **Completed**: Task finished successfully
- **Failed**: Task encountered an error
- **Cancelled**: Task cancelled by user

#### Task Actions
- **Refresh**: Update task status
- **View Results**: Display task results
- **Cancel**: Stop running task

## Configuration

### Server Configuration

Edit `server/config/servers.json` to configure your servers:

```json
{
  "laptop": {
    "name": "Laptop Control Center",
    "type": "control",
    "tailscale_ip": "saturn",
    "capabilities": ["ALL TASKS", "control"],
    "specs": {
      "cpu_cores": 8,
      "memory_gb": 16
    }
  },
  "r630xl": {
    "name": "R630XL Server",
    "type": "hybrid",
    "tailscale_ip": "jupiter",
    "capabilities": ["ALL TASKS", "data_normalization", "feature_engineering"],
    "specs": {
      "cpu_cores": 16,
      "memory_gb": 64
    }
  },
  "r810": {
    "name": "R810 Heavy Compute",
    "type": "compute",
    "tailscale_ip": "saturn",
    "capabilities": ["ALL TASKS", "model_training", "backtesting"],
    "specs": {
      "cpu_cores": 32,
      "memory_gb": 256
    }
  }
}
```

### Deployment Configuration

The deployment system supports various configuration options:

- **Static IP Configuration**: Automatic network setup
- **Tailscale Integration**: Secure VPN connectivity
- **Service Management**: Systemd service configuration
- **Security Hardening**: Firewall and fail2ban setup

## Monitoring and Maintenance

### Health Monitoring

#### Automated Health Checks
- **Service Status**: Monitor all QuantTime services
- **Resource Usage**: Track CPU, memory, and disk usage
- **Network Connectivity**: Verify Tailscale connectivity
- **Database Health**: Check PostgreSQL and Redis status

#### Manual Health Checks
```bash
# Check system resources
quanttime-health

# Monitor services
systemctl status quanttime-*

# Check network
tailscale status
```

### Maintenance Tasks

#### Weekly
- Review system logs
- Check disk usage
- Update packages

#### Monthly
- Performance review
- Data cleanup
- Code updates

#### Quarterly
- Full system backup
- Security audit
- Performance tuning

## Troubleshooting

### Common Issues

#### Connection Problems
1. **Check Tailscale Status**
   ```bash
   tailscale status
   ```

2. **Verify Firewall Rules**
   ```bash
   sudo ufw status
   ```

3. **Test Network Connectivity**
   ```bash
   ping jupiter  # R630XL
   ping saturn  # R810
   ```

#### Service Issues
1. **Check Service Logs**
   ```bash
   sudo journalctl -u quanttime-api-server -f
   ```

2. **Restart Services**
   ```bash
   sudo systemctl restart quanttime-api-server
   ```

3. **Verify Dependencies**
   ```bash
   sudo systemctl status postgresql redis-server
   ```

#### Performance Issues
1. **Monitor Resources**
   ```bash
   htop
   iotop
   ```

2. **Check Disk Usage**
   ```bash
   df -h
   du -sh /opt/quanttime/data/*
   ```

3. **Review Logs**
   ```bash
   tail -f /opt/quanttime/logs/*.log
   ```

### Getting Help

1. **Check Documentation**: Review deployment and troubleshooting guides
2. **Review Logs**: Check system and application logs
3. **Test Connectivity**: Verify network and service connectivity
4. **Contact Support**: Reach out for additional assistance

## Advanced Features

### Custom Task Types

Extend the system with custom task types:

1. **Define Task Configuration**
2. **Implement Task Handler**
3. **Add Parameter Validation**
4. **Configure Device Capabilities**

### Performance Optimization

#### R630XL (Data Processing)
- Optimize for I/O operations
- Configure memory for data processing
- Tune PostgreSQL for data workloads

#### R810 (Model Training)
- Optimize for CPU-intensive tasks
- Configure memory for large models
- Tune system for parallel processing

### Security Features

- **Tailscale VPN**: Encrypted network communication
- **SSH Key Authentication**: Secure server access
- **Firewall Configuration**: Restrict network access
- **Fail2ban Protection**: Prevent brute force attacks

## Development

### Adding New Features

1. **Extend Task Types**: Add new computational tasks
2. **Enhance Monitoring**: Add new monitoring metrics
3. **Improve UI**: Enhance dashboard interface
4. **Optimize Performance**: Improve system performance

### Contributing

1. **Fork Repository**: Create your own fork
2. **Create Feature Branch**: Work on new features
3. **Test Thoroughly**: Ensure all tests pass
4. **Submit Pull Request**: Contribute back to the project

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Check the documentation in `server/docs/`
- Review troubleshooting guides
- Contact the development team

---

**Note**: This server integration creates a production-ready distributed computing infrastructure. Ensure proper security measures and monitoring are in place before running live trading operations.
