# 🔄 Simple Sync Setup Guide

## 🎯 **Your Sync Strategy**

### **Code Changes: GitHub Push/Pull**
- **You push** code changes to GitHub from laptop
- **Servers pull** latest code automatically
- **No complex code sync needed**

### **Data/Models: SYNC Button**
- **One button** in Streamlit dashboard
- **Syncs data, models, backtests** between laptop and servers
- **Servers stay synced** via direct NIC connection

## 🚀 **Setup Steps**

### **1. Install Tailscale on All Devices**
```bash
# On each device (laptop, R630XL, R810):
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list
sudo apt update && sudo apt install tailscale
sudo tailscale up
```

### **2. Setup SSH Keys**
```bash
# Generate SSH key on laptop
ssh-keygen -t rsa -b 4096

# Copy to servers (replace with actual Tailscale IPs)
ssh-copy-id quanttime@jupiter  # R630XL
ssh-copy-id quanttime@r810-tailscale-ip  # R810
```

### **3. Deploy to Servers**
```bash
# On each server, run:
sudo bash server/setup/install.sh
bash server/scripts/start_all_services.sh
```

### **4. Setup GitHub Auto-Pull on Servers**
```bash
# On each server:
chmod +x server/scripts/git_auto_pull.sh

# Add to crontab to run every 5 minutes
crontab -e
# Add this line:
*/5 * * * * /opt/quanttime/server/scripts/git_auto_pull.sh >> /opt/quanttime/logs/git_pull.log 2>&1
```

## 🔄 **How It Works**

### **Code Changes Workflow:**
1. **You make changes** in Cursor on laptop
2. **You commit and push** to GitHub
3. **Servers automatically pull** every 5 minutes
4. **Services restart** if needed

### **Data/Model Sync Workflow:**
1. **You click SYNC button** in Streamlit dashboard
2. **Data syncs** from laptop to R630XL
3. **Data syncs** from laptop to R810
4. **Servers sync** between themselves via NIC

## 🎯 **Usage**

### **For Code Changes:**
```bash
# On laptop, after making changes:
git add .
git commit -m "Your changes"
git push origin main

# Servers will auto-pull within 5 minutes
```

### **For Data/Model Sync:**
1. **Open Streamlit dashboard**
2. **Click "🔄 SYNC" button** (top-left)
3. **Wait for sync to complete**

## ✅ **What Gets Synced**

### **Code (via GitHub):**
- All Python files
- Configuration files
- Scripts and utilities

### **Data/Models (via SYNC button):**
- `data/` - Datasets and processed data
- `models/` - Trained models and checkpoints
- `backtests/` - Backtest results and reports
- `logs/` - Application logs

## 🔧 **Troubleshooting**

### **If SYNC button fails:**
```bash
# Check SSH connectivity
ssh quanttime@jupiter "echo 'SSH working'"

# Check rsync is installed
which rsync

# Check server config
cat server/config/servers.json
```

### **If auto-pull fails:**
```bash
# Check git status on server
ssh quanttime@jupiter "cd /opt/quanttime && git status"

# Check crontab
ssh quanttime@jupiter "crontab -l"

# Check logs
ssh quanttime@jupiter "tail -f /opt/quanttime/logs/git_pull.log"
```

## 🎉 **That's It!**

**Your distributed system is now ready with:**
- ✅ **Automatic code deployment** via GitHub
- ✅ **One-click data sync** via SYNC button
- ✅ **Server-to-server sync** via NIC
- ✅ **Minimal manual intervention**

**Just push code to GitHub and click SYNC when needed!**
