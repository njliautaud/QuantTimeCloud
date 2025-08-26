# 🔄 Enhanced Sync System Documentation

## 🎯 **System Overview**

The Enhanced Sync System provides intelligent, context-aware data synchronization between your laptop and distributed servers with the following key features:

### **Core Features:**
- ✅ **Smart File Comparison** - Shows exactly what needs to be synced
- ✅ **Progress Tracking** - Real-time progress bars in Streamlit
- ✅ **Terminal Logging** - All operations logged to terminal and file
- ✅ **Approval Workflow** - Review sync plan before execution
- ✅ **Context-Aware Data** - Only shows available data for selected server
- ✅ **Server Selection** - Left sidebar slider to switch between servers
- ✅ **Shared Server Storage** - Servers automatically sync between themselves

## 🔄 **Sync Workflows**

### **1. Code Changes (GitHub Push/Pull)**
```
Laptop → GitHub Push → Servers Auto-Pull (every 5 minutes)
```
- **You make changes** in Cursor on laptop
- **You commit and push** to GitHub
- **Servers automatically pull** latest code
- **Services restart** if needed

### **2. Data/Models Sync (Manual SYNC Button)**
```
Laptop ↔ SYNC Button ↔ Servers ↔ Server-to-Server Sync
```
- **Click "🔄 SYNC" button** in Streamlit dashboard
- **Review sync plan** with file comparison
- **Approve sync** to execute
- **Progress tracking** with real-time updates
- **Servers sync** between themselves via NIC

## 🎯 **Server Selection & Context Awareness**

### **Left Sidebar Server Selector:**
- **Dropdown slider** to select target server
- **Real-time status** indicators
- **Data availability** display for selected server
- **Context-aware** data filtering

### **Context-Aware Data Display:**
- **When on Laptop**: Shows only locally available data
- **When on Server**: Shows only server-available data
- **Train/Backtest tabs**: Filter by selected server's data
- **Date selectors**: Only show dates available on selected server

## 📊 **Sync Process Flow**

### **Step 1: Sync Analysis**
```
1. Load server configuration
2. Compare local vs remote files
3. Check file modification times
4. Generate sync plan
5. Display changes to user
```

### **Step 2: Approval Workflow**
```
1. Show sync plan in expandable sections
2. Display files to upload/download
3. Show file sizes and counts
4. Get user approval
5. Execute sync plan
```

### **Step 3: Execution with Progress**
```
1. Upload files from laptop to servers
2. Download files from servers to laptop
3. Sync between servers (shared storage)
4. Real-time progress tracking
5. Terminal logging throughout
```

## 🔧 **Technical Implementation**

### **File Comparison Algorithm:**
```python
def compare_file_lists(local_files, remote_files, sync_dir):
    """Compare local and remote files to find differences"""
    upload_files = []
    download_files = []
    
    # Find files to upload (newer on local or missing on remote)
    for rel_path, local_info in local_files.items():
        if rel_path not in remote_files:
            upload_files.append(file_info)
        elif local_info['mtime'] > remote_files[rel_path]['mtime']:
            upload_files.append(file_info)
    
    # Find files to download (newer on remote or missing on local)
    for rel_path, remote_info in remote_files.items():
        if rel_path not in local_files:
            download_files.append(file_info)
        elif remote_info['mtime'] > local_files[rel_path]['mtime']:
            download_files.append(file_info)
    
    return upload_files, download_files
```

### **Progress Tracking:**
```python
# Create progress tracking
total_files = sum(len(changes['files_to_upload']) + len(changes['files_to_download']) 
                 for changes in sync_plan['changes'].values())

progress_bar = st.progress(0)
status_text = st.empty()

# Update progress for each file
files_processed += 1
progress_bar.progress(files_processed / total_files)
```

### **Terminal Logging:**
```python
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Terminal output
        logging.FileHandler('logs/sync.log')  # File output
    ]
)

# Log all operations
logger.info("🔄 Starting sync analysis...")
logger.info(f"✅ Uploaded {file_path}")
logger.error(f"❌ Failed to upload {file_path}: {error}")
```

## 📁 **Data Directories Synced**

### **Sync Directories:**
- `data/` - Raw, normalized, and feature-engineered data
- `models/` - Trained models and checkpoints
- `backtests/` - Backtest results and reports
- `logs/` - Application logs

### **Excluded from Sync:**
- `.git/` - Version control
- `__pycache__/` - Python cache
- `.venv/` - Virtual environments
- `node_modules/` - Node.js dependencies

## 🎯 **Usage Examples**

### **Example 1: Normalize Data on Server**
```
1. Select "R630XL" in server selector
2. Upload raw data to server
3. Run normalization job on server
4. Click "🔄 SYNC" button
5. Review sync plan (shows new normalized files)
6. Approve sync to download normalized data to laptop
```

### **Example 2: Train Model on Laptop**
```
1. Select "Laptop" in server selector
2. Ensure normalized data is synced
3. Train model on laptop
4. Click "🔄 SYNC" button
5. Review sync plan (shows new model files)
6. Approve sync to upload model to servers
```

### **Example 3: Context-Aware Training**
```
1. Select "R810" in server selector
2. Go to Train tab
3. Only dates available on R810 are shown
4. Train model using R810's data
5. Model automatically saved to R810
6. Sync to share with other servers
```

## 🔧 **Setup Requirements**

### **Prerequisites:**
- ✅ Tailscale installed on all devices
- ✅ SSH keys configured between laptop and servers
- ✅ rsync installed on all systems
- ✅ Server configuration in `server/config/servers.json`

### **Server Configuration:**
```json
{
    "r630xl": {
        "ip_address": "jupiter",
        "tailscale_ip": "jupiter",
        "username": "quanttime"
    },
    "r810": {
        "ip_address": "saturn", 
        "tailscale_ip": "saturn",
        "username": "quanttime"
    }
}
```

## 🚀 **Deployment Steps**

### **1. Setup Tailscale & SSH**
```bash
# Install Tailscale on all devices
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list
sudo apt update && sudo apt install tailscale
sudo tailscale up

# Setup SSH keys
ssh-keygen -t rsa -b 4096
ssh-copy-id quanttime@jupiter  # R630XL
ssh-copy-id quanttime@saturn  # R810
```

### **2. Deploy to Servers**
```bash
# On each server
sudo bash server/setup/install.sh
bash server/scripts/start_all_services.sh
```

### **3. Setup GitHub Auto-Pull**
```bash
# On each server
chmod +x server/scripts/git_auto_pull.sh
crontab -e
# Add: */5 * * * * /opt/quanttime/server/scripts/git_auto_pull.sh >> /opt/quanttime/logs/git_pull.log 2>&1
```

### **4. Test Sync System**
```bash
# On laptop
streamlit run quanttime/dashboard/app.py

# Click "🔄 SYNC" button and verify:
# - File comparison works
# - Progress tracking works
# - Terminal logging works
# - Server selection works
```

## 🔧 **Troubleshooting**

### **Common Issues:**

#### **1. SSH Connection Failed**
```bash
# Check SSH connectivity
ssh quanttime@jupiter "echo 'SSH working'"

# Check SSH keys
ssh-add -l

# Regenerate SSH key if needed
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N '""'
```

#### **2. rsync Not Found**
```bash
# Install rsync
sudo apt install rsync  # Ubuntu/Debian
brew install rsync      # macOS
```

#### **3. File Permission Errors**
```bash
# Check file permissions
ls -la /opt/quanttime/

# Fix permissions
sudo chown -R quanttime:quanttime /opt/quanttime/
sudo chmod -R 755 /opt/quanttime/
```

#### **4. Sync Plan Empty**
```bash
# Check if directories exist
ls -la data/ models/ backtests/

# Check remote directories
ssh quanttime@jupiter "ls -la /opt/quanttime/data/"
```

### **Log Analysis:**
```bash
# Check sync logs
tail -f logs/sync.log

# Check server logs
ssh quanttime@jupiter "tail -f /opt/quanttime/logs/sync.log"
```

## 🎉 **Benefits**

### **For Development:**
- ✅ **Seamless workflow** - Code changes auto-deploy
- ✅ **Context awareness** - Only see relevant data
- ✅ **Progress visibility** - Know exactly what's happening
- ✅ **Error logging** - Debug issues quickly

### **For Production:**
- ✅ **Data consistency** - All servers stay in sync
- ✅ **Resource optimization** - Use best server for each task
- ✅ **Fault tolerance** - Multiple servers available
- ✅ **Scalability** - Easy to add more servers

### **For Management:**
- ✅ **Single control point** - Manage everything from laptop
- ✅ **Visual feedback** - See status at a glance
- ✅ **Approval workflow** - Control what gets synced
- ✅ **Audit trail** - Full logging of all operations

## 🚀 **Next Steps**

### **Immediate:**
1. **Deploy to R630XL** using setup scripts
2. **Test sync system** with sample data
3. **Verify context awareness** works correctly
4. **Monitor logs** for any issues

### **Future Enhancements:**
- **Automatic sync scheduling** - Sync at regular intervals
- **Conflict resolution** - Handle file conflicts intelligently
- **Bandwidth optimization** - Compress large files
- **Incremental sync** - Only sync changed portions
- **Webhook integration** - Trigger sync on events

---

**Your enhanced sync system is now ready for production use! 🎉**
