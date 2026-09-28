# QuantTime Server Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the QuantTime distributed computing infrastructure across your quant homelab servers (R630XL and R810) and integrating them with your laptop control center.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Laptop        │    │   R630XL        │    │   R810          │
│   (Control)     │    │   (Workhorse)   │    │   (Heavy)       │
│                 │    │                 │    │                 │
│ • Dashboard     │    │ • 16 CPU Cores  │    │ • 32 CPU Cores  │
│ • Task Control  │    │ • 64GB RAM      │    │ • 256GB RAM     │
│ • Monitoring    │    │ • Data Proc     │    │ • Model Train   │
│ • Results View  │    │ • Feature Eng   │    │ • Backtesting   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Tailscale     │
                    │   VPN Network   │
                    └─────────────────┘
```

## Prerequisites

### Hardware Requirements

1. **R630XL Server**
   - 16 CPU cores
   - 64GB RAM
   - 2TB storage
   - Network connectivity

2. **R810 Server**
   - 32 CPU cores (4x CPUs)
   - 256GB RAM
   - 4TB storage
   - Network connectivity

3. **Laptop (Control Center)**
   - 8+ CPU cores
   - 16GB+ RAM
   - Network connectivity
   - SSH access to servers

### Software Requirements

- Ubuntu 22.04 LTS on both servers
- Tailscale account and auth keys
- GitHub repository access
- SSH key pairs for secure communication

## Step 1: Prepare Tailscale Network

### 1.1 Create Tailscale Account
1. Go to [tailscale.com](https://tailscale.com)
2. Create a free account
3. Generate auth keys for each server

### 1.2 Get Auth Keys
```bash
# In Tailscale admin console, generate auth keys:
# - r630xl-auth-key
# - r810-auth-key
```

## Step 2: Server Network Configuration

### 2.1 Network Planning
```
Network: 192.168.2.0/24
Gateway: 192.168.2.1

R630XL: jupiter
R810:   saturn
Laptop: laptop (different subnet)
```

### 2.2 Configure Router
- Set up static DHCP reservations for both servers
- Ensure ports 22, 8000, 8501 are open
- Configure firewall rules

## Step 3: Deploy R630XL Server

### 3.1 Initial Setup
```bash
# Boot Ubuntu 22.04 installer
# Install with default settings
# Create user: quanttime
# Set a strong password (export it locally as R630XL_SSH_PASSWORD)
```

### 3.2 Run Automated Setup
```bash
# Download setup script
wget https://raw.githubusercontent.com/your-repo/QuantTime/main/server/setup/ubuntu_server_setup.sh

# Make executable
chmod +x ubuntu_server_setup.sh

# Run setup (replace with your actual values)
sudo ./ubuntu_server_setup.sh \
  --server-name r630xl \
  --static-ip jupiter \
  --gateway 192.168.2.1 \
  --tailscale-key tskey-xxx-r630xl \
  --github-token ghp_xxx
```

### 3.3 Verify Installation
```bash
# Check services
sudo systemctl status quanttime-api-server
sudo systemctl status quanttime-data-collector
sudo systemctl status quanttime-celery-worker
sudo systemctl status quanttime-monitoring

# Check network
tailscale ip -4
ip addr show

# Check health
quanttime-health
```

## Step 4: Deploy R810 Server

### 4.1 Initial Setup
```bash
# Boot Ubuntu 22.04 installer
# Install with default settings
# Create user: quanttime
# Set a strong password (export it locally as R630XL_SSH_PASSWORD)
```

### 4.2 Run Automated Setup
```bash
# Download setup script
wget https://raw.githubusercontent.com/your-repo/QuantTime/main/server/setup/ubuntu_server_setup.sh

# Make executable
chmod +x ubuntu_server_setup.sh

# Run setup (replace with your actual values)
sudo ./ubuntu_server_setup.sh \
  --server-name r810 \
  --static-ip saturn \
  --gateway 192.168.2.1 \
  --tailscale-key tskey-xxx-r810 \
  --github-token ghp_xxx
```

### 4.3 Verify Installation
```bash
# Check services
sudo systemctl status quanttime-api-server
sudo systemctl status quanttime-data-collector
sudo systemctl status quanttime-celery-worker
sudo systemctl status quanttime-monitoring

# Check network
tailscale ip -4
ip addr show

# Check health
quanttime-health
```

## Step 5: Clone and Deploy Code

### 5.1 On Both Servers
```bash
# Clone repository
sudo -u quanttime git clone https://github.com/your-repo/QuantTime.git /opt/quanttime/repo

# Copy configuration
sudo cp /opt/quanttime/repo/server/config/servers.json /opt/quanttime/config/

# Set up Python environment
cd /opt/quanttime/repo
sudo -u quanttime python3 -m venv venv
sudo -u quanttime venv/bin/pip install -r requirements.txt

# Start services
quanttime-start
```

## Step 6: Configure Laptop Control Center

### 6.1 Update Server Configuration
```bash
# Edit server configuration
nano server/config/servers.json

# Update with actual Tailscale IPs
{
  "r630xl": {
    "tailscale_ip": "jupiter",  # Actual R630XL Tailscale IP
    ...
  },
  "r810": {
    "tailscale_ip": "saturn",  # Actual R810 Tailscale IP
    ...
  }
}
```

### 6.2 Test Connections
```bash
# Test SSH connections
ssh quanttime@jupiter  # R630XL
ssh quanttime@saturn  # R810

# Test API endpoints
curl http://jupiter:8000/health  # R630XL
curl http://saturn:8000/health  # R810
```

## Step 7: Launch Dashboard

### 7.1 Start Dashboard
```bash
# On laptop
python run.py dashboard --port 8501
```

### 7.2 Access Dashboard
- Open browser to: `http://localhost:8501`
- Navigate to "Server Control Center" in sidebar
- Verify all servers show as connected

## Step 8: Test Distributed Computing

### 8.1 Submit Test Tasks
1. **Data Normalization Task**
   - Select R630XL as target device
   - Choose "Data Normalization" task type
   - Configure parameters (symbols: ES, date range: last 7 days)
   - Submit task

2. **Model Training Task**
   - Select R810 as target device
   - Choose "Model Training" task type
   - Configure parameters (model: lightgbm, trials: 100)
   - Submit task

3. **Backtesting Task**
   - Select R810 as target device
   - Choose "Backtesting" task type
   - Configure parameters (period: 1m, capital: 100k)
   - Submit task

### 8.2 Monitor Progress
- Use "Task Monitoring" section to track progress
- Check server status in sidebar
- View real-time resource usage

## Step 9: Production Configuration

### 9.1 Security Hardening
```bash
# On both servers
sudo ufw enable
sudo ufw default deny incoming
sudo ufw allow from 100.64.0.0/10  # Tailscale network
sudo ufw allow ssh

# Configure fail2ban
sudo nano /etc/fail2ban/jail.local
```

### 9.2 Monitoring Setup
```bash
# Set up log monitoring
sudo logwatch --mailto admin@yourdomain.com --detail high

# Set up disk monitoring
sudo apt install hdparm smartmontools
sudo smartctl -a /dev/sda
```

### 9.3 Backup Configuration
```bash
# Set up automated backups
sudo crontab -e

# Add backup job (daily at 2 AM)
0 2 * * * /opt/quanttime/scripts/backup.sh
```

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   ```bash
   # Check Tailscale status
   tailscale status
   
   # Check firewall
   sudo ufw status
   
   # Test connectivity
   ping jupiter
   ```

2. **Services Not Starting**
   ```bash
   # Check service logs
   sudo journalctl -u quanttime-api-server -f
   sudo journalctl -u quanttime-data-collector -f
   
   # Check dependencies
   sudo systemctl status postgresql
   sudo systemctl status redis-server
   ```

3. **Dashboard Can't Connect**
   ```bash
   # Check server config
   cat server/config/servers.json
   
   # Test API endpoints
   curl -v http://jupiter:8000/health
   
   # Check network connectivity
   traceroute jupiter
   ```

### Performance Optimization

1. **R630XL (Data Processing)**
   ```bash
   # Optimize for data processing
   sudo sysctl -w vm.swappiness=10
   sudo sysctl -w vm.dirty_ratio=15
   sudo sysctl -w vm.dirty_background_ratio=5
   ```

2. **R810 (Model Training)**
   ```bash
   # Optimize for heavy compute
   sudo sysctl -w vm.swappiness=1
   sudo sysctl -w vm.dirty_ratio=20
   sudo sysctl -w vm.dirty_background_ratio=10
   ```

## Maintenance

### Regular Tasks

1. **Weekly**
   - Check disk usage: `df -h`
   - Review logs: `tail -f /opt/quanttime/logs/*.log`
   - Update packages: `sudo apt update && sudo apt upgrade`

2. **Monthly**
   - Review performance metrics
   - Clean old data: `/opt/quanttime/scripts/cleanup.sh`
   - Update QuantTime code: `git pull`

3. **Quarterly**
   - Full system backup
   - Security audit
   - Performance tuning

### Monitoring Commands

```bash
# System resources
htop
iotop
nethogs

# QuantTime services
quanttime-health
systemctl status quanttime-*

# Network
tailscale status
ss -tulpn

# Storage
df -h
du -sh /opt/quanttime/data/*
```

## Support

For issues and questions:
1. Check logs in `/opt/quanttime/logs/`
2. Review this deployment guide
3. Check GitHub issues
4. Contact system administrator

## Next Steps

After successful deployment:
1. Configure data sources (Databento API keys)
2. Set up automated data collection
3. Create initial models and backtests
4. Implement monitoring alerts
5. Set up production trading (if applicable)

---

**Note**: This deployment creates a production-ready distributed computing infrastructure. Ensure proper security measures and monitoring are in place before running live trading operations.
