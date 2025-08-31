# 🖥️ Windows Node Deployment Guide

Complete guide for deploying QuantTime to Windows machines with Tailscale integration.

## 🎯 Prerequisites

### Required Software
1. **Python 3.11+** - [Download](https://www.python.org/downloads/)
2. **Git** - [Download](https://git-scm.com/download/win)
3. **Tailscale** - [Download](https://tailscale.com/download)

### Network Requirements
- Tailscale VPN connection active
- Windows Firewall configured (handled automatically)
- Internet access for GitHub and package downloads

## 🚀 Automated Deployment

### Option 1: PowerShell Script (Recommended)

Run this **as Administrator** in PowerShell:

```powershell
# Download and run deployment script
iwr -useb https://raw.githubusercontent.com/njliautaud/QuantTimeCloud/master/deploy_windows_node.ps1 | iex
```

Or manually:

```powershell
# Clone repository
git clone https://github.com/njliautaud/QuantTimeCloud.git C:\QuantTime
cd C:\QuantTime

# Run deployment script
.\deploy_windows_node.ps1
```

### Option 2: Manual Installation

```powershell
# 1. Clone repository
git clone https://github.com/njliautaud/QuantTimeCloud.git C:\QuantTime
cd C:\QuantTime

# 2. Run setup
python setup.py --init

# 3. Generate SSH key
ssh-keygen -t ed25519 -C "quanttime-automation" -f ~/.ssh/quanttime_automation

# 4. Configure firewall
New-NetFirewallRule -DisplayName "QuantTime Ray" -Direction Inbound -Port 10001 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "QuantTime Dashboard" -Direction Inbound -Port 8265 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "QuantTime Discovery" -Direction Inbound -Port 10002 -Protocol UDP -Action Allow
```

## 🔑 SSH Key Exchange

After deployment, you'll need to exchange SSH keys between nodes:

### 1. Get Your Public Key
```powershell
Get-Content ~/.ssh/quanttime_automation.pub
```

### 2. Add to Other Nodes
For each existing QuantTime node, run:

**Windows nodes:**
```powershell
ssh user@peer-tailscale-ip "echo 'YOUR_PUBLIC_KEY_HERE' >> ~/.ssh/authorized_keys"
```

**Linux nodes:**
```bash
ssh user@peer-tailscale-ip "echo 'YOUR_PUBLIC_KEY_HERE' >> ~/.ssh/authorized_keys"
```

### 3. Test Connection
```powershell
ssh -i ~/.ssh/quanttime_automation user@peer-tailscale-ip
```

## 🌐 Network Discovery

QuantTime automatically discovers peers on your Tailscale network:

### Tailscale IP Detection
- Automatically detects IPs in `100.x.x.x` range
- Broadcasts to `100.x.x.255` for peer discovery
- Fallback to local network ranges

### Discovery Process
1. **Broadcast Presence**: Every 15 seconds on UDP port 10002
2. **Peer Response**: Other nodes respond with their info
3. **SSH Handshake**: Establish trust using SSH keys
4. **Ray Integration**: Join or create Ray cluster
5. **Git Sync**: Start monitoring for repository changes

## 🔧 Configuration

### Automatic Configuration
The setup script creates:
- `config/dynamic_cluster_config.json` - Node configuration
- `settings.txt` - Updated with cluster settings
- SSH automation keys
- Windows Firewall rules

### Manual Configuration (if needed)

Edit `settings.txt`:
```ini
# Tailscale Configuration
CLUSTER_NODE_IP=razer
CLUSTER_AUTO_DISCOVERY=true
CLUSTER_DISCOVERY_PORT=10002

# SSH Configuration  
SSH_AUTOMATION_PRIVATE_KEY_PATH=C:\Users\YourUser\.ssh\quanttime_automation
GIT_SSH_KEY_PATH=C:\Users\YourUser\.ssh\quanttime_automation
```

## 🎯 Starting the Node

### Method 1: Desktop Shortcut
Double-click the "QuantTime" shortcut created on your desktop.

### Method 2: Command Line
```powershell
cd C:\QuantTime
python run.py
```

### Method 3: Background Service
```powershell
# Start in background
Start-Process -NoNewWindow python -ArgumentList "run.py"
```

## 📊 Verification

### Check Node Status
```powershell
# Open dashboard
Start-Process "http://localhost:8501"

# Check Ray dashboard
Start-Process "http://localhost:8265"

# View logs
Get-Content logs\quanttime.log -Tail 50
```

### Test Peer Discovery
```powershell
# Check for discovered peers
python -c "
from quanttime.core.peer_sync_manager import PeerSyncManager
manager = PeerSyncManager()
status = manager.get_peer_status()
print(f'Discovered {len(status[\"known_peers\"])} peers')
for peer_id, peer in status['known_peers'].items():
    print(f'  {peer[\"hostname\"]} ({peer[\"address\"]}) - {\"Online\" if peer[\"is_online\"] else \"Offline\"}')
"
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Python Not Found
```powershell
# Add Python to PATH
$env:PATH += ";C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python311"
```

#### 2. Tailscale Not Running
```powershell
# Check Tailscale status
tailscale status

# Start Tailscale
tailscale up
```

#### 3. Firewall Blocking
```powershell
# Check firewall rules
Get-NetFirewallRule -DisplayName "*QuantTime*"

# Manually add rules if needed
New-NetFirewallRule -DisplayName "QuantTime" -Direction Inbound -Port 10001,8265,10002 -Protocol TCP -Action Allow
```

#### 4. SSH Key Issues
```powershell
# Regenerate SSH key
Remove-Item ~/.ssh/quanttime_automation*
ssh-keygen -t ed25519 -C "quanttime-automation" -f ~/.ssh/quanttime_automation
```

#### 5. Git Authentication
```powershell
# Configure Git to use SSH key
git config core.sshCommand "ssh -i C:/Users/$env:USERNAME/.ssh/quanttime_automation -o IdentitiesOnly=yes"
```

### Debug Mode
```powershell
# Run with verbose logging
python run.py --debug
```

### Log Files
- **Application logs**: `logs\quanttime.log`
- **Ray logs**: `temp\ray\logs\`
- **Git logs**: Check Git operations in main log

## 🔄 Node Management

### Start/Stop Service
```powershell
# Start
python run.py

# Stop (Ctrl+C or)
taskkill /F /IM python.exe
```

### Update Node
```powershell
cd C:\QuantTime
git pull origin master
python setup.py --update
```

### Remove Node
```powershell
# Stop service
taskkill /F /IM python.exe

# Remove installation
Remove-Item -Recurse -Force C:\QuantTime

# Remove firewall rules
Remove-NetFirewallRule -DisplayName "*QuantTime*"
```

## 📋 Deployment Checklist

- [ ] Python 3.11+ installed
- [ ] Git installed and configured
- [ ] Tailscale connected
- [ ] Repository cloned to `C:\QuantTime`
- [ ] Setup script completed successfully
- [ ] SSH automation key generated
- [ ] Windows Firewall configured
- [ ] SSH keys exchanged with other nodes
- [ ] Databento API key added to `settings.txt`
- [ ] Node started and dashboard accessible
- [ ] Peer discovery working (check dashboard)
- [ ] Git sync active
- [ ] Ray cluster joined/created

## 🎯 Expected Behavior

After successful deployment:

1. **Node Discovery**: Automatically finds other QuantTime nodes on Tailscale
2. **SSH Handshake**: Establishes secure communication
3. **Ray Cluster**: Joins existing cluster or creates new one
4. **Git Sync**: Monitors repository for changes every 30 seconds
5. **Job Assignment**: Can receive and execute jobs from any peer
6. **Dashboard**: Accessible at `http://100.x.x.x:8501`
7. **Ray Dashboard**: Available at `http://100.x.x.x:8265`

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review log files for error messages
3. Ensure all prerequisites are met
4. Verify network connectivity with Tailscale
5. Test SSH connectivity to other nodes

The system is designed to be fault-tolerant - if some components fail, others will continue working.
