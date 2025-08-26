# QuantTime Syncthing Setup Guide

## 🎯 Overview

This guide walks you through setting up Syncthing for your QuantTime project across all nodes (laptop, R630XL, R810) using Tailscale for secure connectivity.

## 🚨 Important: The Chicken-and-Egg Problem

**Problem**: We need Syncthing on the servers to sync the project, but we need the project on the servers to set up Syncthing properly.

**Solution**: We use a **two-phase deployment**:
1. **Phase 1**: Install basic Syncthing on servers first
2. **Phase 2**: Sync the project over, then configure full QuantTime setup

## 📋 Prerequisites

### Required Software
- **SSH access** to all servers via Tailscale
- **jq** (JSON processor) - `sudo apt-get install jq` (Linux) or `choco install jq` (Windows)
- **Syncthing** - Will be installed automatically
- **PowerShell** (Windows) or **Bash** (Linux/Mac)

### Network Requirements
- **Tailscale** running on all nodes
- **SSH keys** configured for passwordless access
- **Port 8384** accessible for Syncthing web interface

### Server Configuration
Ensure your `server/config/servers.json` is properly configured with:
- Tailscale IPs for all servers
- Correct usernames
- SSH access working

## 🚀 Phase 1: Initial Syncthing Deployment

### Step 1: Run the Initial Deployment Script

**Windows (PowerShell):**
```powershell
# Run the full deployment
.\scripts\deploy_syncthing_initial.ps1

# Or run step by step
.\scripts\deploy_syncthing_initial.ps1 -Step 1  # Install on servers
.\scripts\deploy_syncthing_initial.ps1 -Step 2  # Setup local
.\scripts\deploy_syncthing_initial.ps1 -Step 3  # Get device IDs
# ... continue with steps 4-9
```

**Linux/Mac (Bash):**
```bash
# Make script executable
chmod +x scripts/deploy_syncthing_initial.sh

# Run the full deployment
./scripts/deploy_syncthing_initial.sh

# Or run step by step
./scripts/deploy_syncthing_initial.sh -s 1  # Install on servers
./scripts/deploy_syncthing_initial.sh -s 2  # Setup local
./scripts/deploy_syncthing_initial.sh -s 3  # Get device IDs
# ... continue with steps 4-9
```

### What Each Step Does

1. **Install Syncthing on servers** - Installs Syncthing on R630XL and R810
2. **Setup local Syncthing** - Installs and configures Syncthing on your laptop
3. **Get device IDs** - Collects unique device IDs from all nodes
4. **Create initial folder config** - Creates basic folder configuration
5. **Deploy initial config to servers** - Applies configuration to servers
6. **Apply local config** - Applies configuration to local machine
7. **Copy project to sync folder** - Copies project to Syncthing folder
8. **Wait for initial sync** - Waits for files to sync across nodes
9. **Deploy full setup** - Runs full QuantTime setup on servers

### Step 2: Verify Installation

Check that Syncthing is running on all nodes:

**Local (Windows):**
```powershell
# Check if Syncthing is running
Get-Process syncthing -ErrorAction SilentlyContinue

# Access web interface
Start-Process "http://localhost:8384"
```

**Servers:**
```bash
# Check Syncthing service status
ssh quanttime@jupiter "sudo systemctl status syncthing@quanttime"
ssh quanttime@saturn "sudo systemctl status syncthing@quanttime"

# Access web interfaces
# R630XL: http://jupiter:8384
# R810: http://saturn:8384
```

## 🔄 Phase 2: Full QuantTime Integration

### Step 1: Run Full Setup

Once the initial sync is complete, run the full QuantTime setup:

```bash
# Run full setup
python scripts/setup_syncthing.py --action full

# Or test connections first
python scripts/setup_syncthing.py --action test
```

### Step 2: Configure Syncthing Folders

The full setup will create these Syncthing folders:

- **quanttime-project** (`/opt/quanttime`) - Main project files
- **quanttime-data** (`/opt/quanttime/data`) - Data files
- **quanttime-models** (`/opt/quanttime/models`) - ML models

### Step 3: Verify Integration

Check that your existing Syncthing manager is working:

```python
from quanttime.core.syncthing_manager import get_syncthing_manager

# Get sync status
syncthing = get_syncthing_manager()
status = syncthing.get_sync_status()
print(status)
```

## 🔧 Manual Configuration (If Needed)

### Syncthing Web Interface Setup

If automatic configuration fails, manually configure via web interface:

1. **Access web interfaces:**
   - Local: http://localhost:8384
   - R630XL: http://jupiter:8384
   - R810: http://saturn:8384

2. **Add devices:**
   - Click "Add Remote Device"
   - Enter device ID from other nodes
   - Set device name (laptop, r630xl, r810)

3. **Add folders:**
   - Click "Add Folder"
   - Set folder ID: `quanttime-project`
   - Set path: `/opt/quanttime` (Linux) or `C:\opt\quanttime` (Windows)
   - Select all devices
   - Set type: "Send & Receive"

### Device IDs

You can find device IDs in:

**Windows:**
```
%APPDATA%\Syncthing\config.xml
```

**Linux:**
```
~/.config/syncthing/config.xml
```

**Servers:**
```
/home/quanttime/.config/syncthing/config.xml
```

Look for: `<device id="ABCDEFGH-1234-5678-9ABC-DEF123456789">`

## 🎛️ Integration with Ray Tune

### Automatic Sync Before Training

Your existing `ray_manager.py` can now integrate with Syncthing:

```python
from quanttime.core.ray_manager import get_ray_manager
from quanttime.core.syncthing_manager import get_syncthing_manager

# Ensure sync before distributed training
syncthing = get_syncthing_manager()
syncthing.force_sync("models")
syncthing.force_sync("data")

# Start Ray Tune training
ray_manager = get_ray_manager()
job_id = ray_manager.submit_job(
    name="mbo_training",
    function=train_model_job,
    config=training_config,
    resources={"CPU": 8, "GPU": 1},
    priority=JobPriority.HIGH
)
```

### Monitor Sync Status in Dashboard

Add sync status to your Streamlit dashboard:

```python
# In your dashboard
sync_status = syncthing.get_sync_status()
cluster_status = ray_manager.get_cluster_status()

st.subheader("Sync Status")
st.json(sync_status)

st.subheader("Cluster Status")
st.json(cluster_status)
```

## 🛠️ Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   ```bash
   # Test SSH connection
   ssh quanttime@jupiter "echo 'SSH working'"
   ```

2. **Syncthing Not Starting**
   ```bash
   # Check service status
   sudo systemctl status syncthing@quanttime
   
   # Check logs
   sudo journalctl -u syncthing@quanttime -f
   ```

3. **Web Interface Not Accessible**
   ```bash
   # Check if port is open
   netstat -tlnp | grep 8384
   
   # Check firewall
   sudo ufw status
   ```

4. **Files Not Syncing**
   ```bash
   # Check folder permissions
   ls -la /opt/quanttime/
   
   # Check Syncthing logs
   tail -f ~/.config/syncthing/syncthing.log
   ```

### Reset Syncthing (If Needed)

**Complete reset:**
```bash
# Stop Syncthing
sudo systemctl stop syncthing@quanttime

# Remove configuration
sudo rm -rf /home/quanttime/.config/syncthing

# Restart Syncthing
sudo systemctl start syncthing@quanttime
```

## 📊 Monitoring and Maintenance

### Regular Checks

1. **Sync Status:**
   ```bash
   python scripts/setup_syncthing.py --action test
   ```

2. **Disk Space:**
   ```bash
   df -h /opt/quanttime
   ```

3. **Service Status:**
   ```bash
   sudo systemctl status syncthing@quanttime
   ```

### Performance Optimization

1. **Bandwidth Limits:**
   - Set in Syncthing web interface
   - Limit during business hours if needed

2. **Folder Exclusions:**
   - Exclude large data files from sync
   - Use `.stignore` files for specific exclusions

3. **Versioning:**
   - Configure versioning for important folders
   - Set retention policies

## 🎯 Next Steps

After successful setup:

1. **Test Ray Tune integration** with distributed training
2. **Configure monitoring** in your Streamlit dashboard
3. **Set up automated backups** using Syncthing versioning
4. **Optimize sync performance** based on your usage patterns

## 📞 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review Syncthing logs: `~/.config/syncthing/syncthing.log`
3. Check system logs: `sudo journalctl -u syncthing@quanttime`
4. Verify Tailscale connectivity between nodes

The combination of **Syncthing + Tailscale + Ray Tune** provides a robust foundation for your distributed quantitative trading platform!
