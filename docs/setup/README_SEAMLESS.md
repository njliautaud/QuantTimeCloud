# QuantTime ML Trading Suite - Seamless Setup

## 🚀 One-Command Launch

**Just run this single command and everything is automatic:**

```bash
python launch.py
```

That's it! The system will:
- ✅ Auto-detect your environment
- ✅ Auto-configure all services
- ✅ Auto-detect your nodes via Tailscale
- ✅ Auto-start the dashboard
- ✅ Auto-open in your browser

## 🔧 What Gets Set Up Automatically

### 1. **Environment Detection**
- Operating system detection
- Python version compatibility
- Available port detection (auto-finds free ports)
- Node detection via Tailscale

### 2. **Directory Structure**
```
data/
├── results/          # Trading results
├── models/           # ML models
└── sync_history/     # File sync logs
logs/                 # Application logs
monitoring/           # Monitoring configs
├── grafana/
└── prometheus/
```

### 3. **Configuration Files**
- `sync_config.json` - File sync settings
- `monitoring_config.json` - Monitoring settings
- `coolify_config.json` - Deployment settings
- `setup_summary.json` - Setup results

### 4. **Services Started**
- Streamlit Dashboard (port 8501)
- Prometheus Monitoring (port 9090)
- Grafana Dashboards (port 3001)
- Coolify Deployment (port 3000)

## 📊 Dashboard Features

### **Main Dashboard**
- Real-time trading data
- Model performance metrics
- Node status monitoring
- File sync management

### **📊 Monitoring Tab**
- Embedded Prometheus metrics
- Grafana dashboards
- System resource monitoring
- Performance analytics

### **🚀 Coolify Tab**
- Automated deployments
- Git-based code sync
- Container orchestration
- Node management

### **📁 File Management**
- Peer-to-peer file sync
- Cross-platform compatibility
- Large file handling
- Sync status tracking

## 🔄 How Coolify Works in This Project

### **Role of Coolify**

Coolify serves as the **automated deployment and orchestration engine** for QuantTime:

#### **1. Code Deployment**
- **Git Integration**: Automatically detects your GitHub repository
- **Auto-Deploy**: When you push code changes, Coolify automatically deploys to all nodes
- **Version Control**: Manages different versions across your cluster
- **Rollback**: Can quickly revert to previous versions if needed

#### **2. Container Orchestration**
- **Docker Management**: Handles container builds and deployments
- **Multi-Node Deployment**: Deploys to R630XL, R810, and other nodes
- **Health Checks**: Monitors container health and restarts if needed
- **Resource Management**: Optimizes resource allocation across nodes

#### **3. Configuration Management**
- **Environment Variables**: Manages different configs for different environments
- **Secrets Management**: Securely handles API keys and credentials
- **Node-Specific Configs**: Different settings for different server types

#### **4. Monitoring Integration**
- **Metrics Collection**: Gathers performance metrics from all nodes
- **Log Aggregation**: Centralizes logs from all deployments
- **Alerting**: Notifies you of issues or performance problems

### **Seamless Integration**

The Coolify integration is **completely embedded** in your Streamlit dashboard:

1. **No Separate UI**: Everything is managed through the "🚀 Coolify" tab
2. **Auto-Detection**: Automatically finds your nodes and repositories
3. **One-Click Deploy**: Deploy to all nodes with a single click
4. **Real-Time Status**: See deployment status in real-time
5. **Integrated Logs**: View deployment logs directly in the dashboard

### **Workflow Example**

1. **Develop**: Make changes to your code locally
2. **Push**: Push to GitHub
3. **Auto-Deploy**: Coolify automatically detects the push
4. **Build**: Builds new Docker containers
5. **Deploy**: Deploys to all your nodes (R630XL, R810, etc.)
6. **Monitor**: Watch deployment progress in the dashboard
7. **Verify**: Check that all nodes are running the new version

### **Benefits**

- **Zero Manual Setup**: Everything is automated
- **Consistent Deployments**: Same code runs everywhere
- **Easy Rollbacks**: One click to revert changes
- **Scalable**: Add new nodes and they're automatically included
- **Integrated**: No need to learn separate tools

## 🛠️ Advanced Setup Options

### **Full Docker Setup** (Optional)
If you want full containerization:

```bash
python setup_coolify_integration.py
```

This adds:
- Full Prometheus/Grafana monitoring
- Containerized deployments
- Advanced orchestration

### **Simple Setup** (Default)
The default setup includes:
- Embedded monitoring
- Peer-to-peer file sync
- Basic deployment management

## 🔍 Troubleshooting

### **Port Conflicts**
The system automatically detects and uses available ports. If you see port conflicts, the auto-setup will find alternatives.

### **Node Detection**
If nodes aren't detected:
1. Ensure Tailscale is running
2. Check node connectivity
3. Verify SSH credentials

### **Dashboard Issues**
If the dashboard doesn't start:
1. Check if port 8501 is available
2. Verify Python dependencies
3. Check logs in the `logs/` directory

## 📋 System Requirements

- **Python**: 3.8+
- **OS**: Windows, macOS, Linux
- **Network**: Tailscale for node connectivity
- **Optional**: Docker for full containerization

## 🎯 Key Features

- **Zero Configuration**: Everything auto-detects and configures
- **Cross-Platform**: Works on Windows, macOS, Linux
- **Scalable**: Add nodes seamlessly
- **Integrated**: All tools work together
- **Self-Healing**: Automatically recovers from issues
- **Real-Time**: Live monitoring and updates

## 🚀 Getting Started

1. **Clone the repository**
2. **Run one command**: `python launch.py`
3. **Everything else is automatic!**

The system will guide you through any remaining setup steps, but most users will have everything working immediately.
