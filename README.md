# QuantTime ML Trading Suite

A comprehensive quantitative trading platform built around **Databento MBO (Market By Order) Level 3 data** for high-frequency market analysis and algorithmic trading. Designed for **tick-based trading strategies** with 1-5 minute price predictions using **1 ES contract positions** and **Reinforcement Learning trade engine**.

## 🎯 Core Philosophy

**Tick-based Level 3 MBO trading** - We focus on sustainable trading strategies using every tick of orderflow data:
- **Tick-based backtesting** using Level 3 MBO data with orderflow
- **1 ES contract positions** - no portfolio sizing, consistent position management
- **Reinforcement Learning trade engine** for adaptive decision making
- **Session-based data splits** for robust model training
- **Walk-forward analysis** for realistic backtesting
- **Live-like tick-by-tick processing** for accurate simulation

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Databento account with MBO data access
- Local Databento MBO data files (`.dbn.zst` format)
- Cross-platform Ray cluster (Windows + Linux nodes supported)
- SSH access to remote nodes

### One-Click Startup (Recommended)
Simply run:
```bash
python run.py
```

This will automatically:
- ✅ Start Ray cluster head node
- ✅ Initialize AI-powered smart automation
- ✅ Auto-discover and configure network nodes
- ✅ Setup intelligent SSH key management
- ✅ Initialize cross-platform Git monitoring
- ✅ Setup SFTP file synchronization
- ✅ Launch the integrated dashboard with smart automation
- ✅ Monitor repository for auto-deployment
- ✅ Enable predictive health monitoring
- ✅ Start self-healing system management

### Smart Setup (Zero Configuration)
For completely automated setup with intelligent detection:
```bash
# Clone the repository
git clone <repository-url>
cd QuantTime

# Run smart setup (automatically detects everything)
python scripts/smart_setup.py
```
This will automatically:
- 🔍 Detect your system configuration
- 📦 Install all dependencies
- 🔑 Generate SSH keys for automation
- 🌐 Discover network nodes via Tailscale
- ⚙️ Generate intelligent configurations
- 🚀 Initialize and start QuantTime
- ✅ Verify all systems are working

### Manual Setup
```bash
# Clone the repository
git clone <repository-url>
cd QuantTime

# Install dependencies
python run.py install

# Start with full integration
python run.py up
```

### Cross-Platform Node Setup

QuantTime now supports **Windows and Linux nodes** seamlessly:

#### Windows Node Setup
```powershell
# Clone repository on Windows node
git clone <repository-url> C:\QuantTime
cd C:\QuantTime

# Install Python dependencies
python -m pip install -r requirements.txt

# Configure SSH server (if needed)
# Enable OpenSSH Server in Windows Features
```

#### Linux Node Setup  
```bash
# Clone repository on Linux node
git clone <repository-url> /opt/quanttime
cd /opt/quanttime

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Ensure SSH server is running
sudo systemctl enable ssh
sudo systemctl start ssh
```

### Automated Deployment
The system automatically:
- ✅ Monitors GitHub repository for changes
- ✅ Deploys code to all connected nodes
- ✅ Synchronizes large files via SFTP
- ✅ Manages Ray worker connections
- ✅ Provides cross-platform compatibility

### Environment Activation Commands
After installation, you can activate the virtual environment manually:

**Windows:**
```cmd
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

**Deactivate environment:**
```bash
deactivate
```

### Available Scripts
- `setup_quanttime.py` - Complete setup with environment activation and launch
- `setup_server.py` - Ubuntu server setup (Tailscale, SSH, QuantTime environment)
- `run.py` - Main application entry point
- Additional scripts available in `scripts/` folder

### Configuration
1. **Follow the setup wizard** that appears when you first run `python run.py`:
   - Configure Git repository for code synchronization
   - Set up node connections (laptop, R630XL, R810)
   - Configure Ray cluster settings
   - Set up SFTP for large file synchronization

2. Copy your Databento API key to `settings.txt`:
```
DATABENTO_KEY=your_api_key_here
```

3. Ensure your MBO data is in the `data/es_futures/mbo/` directory

4. The dashboard will be available at `http://localhost:8501`

## 📊 Features

### Smart Automation (NEW)
- **🤖 AI-Powered Node Management**: Intelligent discovery, configuration, and deployment
- **🔍 Zero-Touch Setup**: Automatic system detection and configuration generation
- **🔑 Smart Credential Management**: Automatic SSH key generation and credential detection
- **🌐 Network Auto-Discovery**: Scan and configure Tailscale nodes automatically
- **📊 Predictive Health Monitoring**: AI-powered trend analysis and failure prediction
- **🔧 Self-Healing Systems**: Automatic issue detection and resolution
- **⚡ Intelligent Resource Allocation**: Dynamic optimization based on workload patterns
- **🚀 Zero-Touch Deployment**: Fully automated QuantTime installation on discovered nodes

### Data Pipeline
- **MBO Level 3 Data Processing**: Full pipeline for Databento `.dbn.zst` files
- **Order Book Reconstruction**: Real-time order book from MBO events
- **Feature Engineering**: 100+ features for 1-5 minute predictions
- **Session-Based Splits**: Asia, London, New York, and overnight sessions
- **Memory-Efficient Processing**: Batching and streaming for large datasets
- **Tick-by-Tick Assembly**: Sequential MBO event processing (A/C/F/M/R/T)
- **Cumulative Delta**: Non-lagging volume flow indicator
- **Level 2 Aggregation**: Efficient processing of distant orders

### AI/ML Models
- **Multi-Horizon Predictions**: 1, 3, and 5-minute price forecasts
- **Feature Selection**: Automated feature importance ranking
- **Model Validation**: Walk-forward and Monte Carlo robustness checks
- **Session Randomization**: Prevents overfitting to specific market sessions
- **MBO-Specific Training**: Tick-by-tick order book context with cumulative delta
- **GPU Acceleration**: PyTorch-based models with CUDA support
- **Localized Order Book**: ±100 point focus for relevant training data

### Backtesting Engine
- **Tick-based Simulation**: Every tick processed with Level 3 MBO data
- **1 ES Contract Positions**: Consistent position sizing, no portfolio management
- **Walk-Forward Analysis**: Multiple time periods for robust validation
- **Session-Based Testing**: Separate validation by trading sessions
- **Risk Management**: Stop-loss and drawdown limits
- **Performance Metrics**: Sharpe ratio, drawdown, win rate, and more

### Trading Interface
- **Streamlit Dashboard**: Interactive web interface with Ray job management
- **Real-Time Charts**: TradingView-style charts with MBO data
- **Order Flow Analysis**: Footprint charts and DOM visualization
- **Live Trading**: Paper and live trading capabilities with RL engine

### Cross-Platform Distributed Computing
- **Ray Cluster Management**: Submit jobs to Windows and Linux nodes via dashboard
- **Cross-Platform Deployment**: Automatic deployment to mixed OS environments
- **Distributed Training**: Train models across Windows GPU and Linux CPU nodes
- **Distributed Backtesting**: Run backtests on high-performance servers
- **Job Queue Management**: Monitor and manage distributed jobs
- **Resource Monitoring**: Real-time cluster resource utilization
- **SSH-Based Management**: Secure cross-platform node communication
- **SFTP File Synchronization**: Automatic large file sync between nodes
- **Git Auto-Deployment**: Repository monitoring with automatic updates
- **Color-Coded Health Status**: Red (cannot connect), Yellow (issues), Green (operational)

## 🏗️ Architecture

```
QuantTime/
├── quanttime/                 # Main application package
│   ├── adapter/               # Data adapters
│   │   └── databento_mbo.py   # MBO data processing
│   ├── features/              # Feature engineering
│   │   └── mbo_features.py    # 100+ MBO features
│   ├── backtest/              # Backtesting engine
│   │   └── mbo_backtest_engine.py  # Tick-based simulation
│   ├── dashboard/             # Streamlit interface
│   │   ├── app.py            # Main dashboard
│   │   └── syncthing_ray_interface.py  # Ray job management
│   ├── core/                  # Core services
│   │   └── ray_manager.py    # Distributed computing management
│   ├── models/               # ML models and RL trade engine
│   ├── runtime/              # Runtime services
│   └── utils/                # Utilities
├── data/                      # Data directory
│   ├── es_futures/           # ES futures data
│   │   ├── mbo/              # Level 3 MBO data
│   │   ├── mbp/              # Market by Price data
│   │   └── trades/           # Trade data
│   └── processed/            # Processed data
├── config/                    # Configuration files
│   └── ray_cluster_config.json  # Ray cluster configuration
├── settings.txt              # Configuration
└── run.py                    # Main entry point
```

## 📈 Trading Strategy Focus

### Tick-Based Processing
- **Level 3 MBO Data**: Every order book event processed
- **Orderflow Analysis**: Add/Cancel/Fill/Modify/Remove/Trade events
- **Cumulative Delta**: Real-time volume flow tracking
- **1 ES Contract**: Consistent position sizing

### Time Horizons
- **1-minute predictions**: Immediate market conditions
- **3-minute predictions**: Short-term trends
- **5-minute predictions**: Medium-term momentum

### Trade Duration
- **Minimum hold time**: 30 seconds
- **Maximum hold time**: 30 minutes
- **Typical duration**: 2-10 minutes

### Risk Management
- **Position sizing**: Always 1 ES contract
- **Risk per trade**: Configurable stop-loss
- **Drawdown limits**: Daily and total limits

## 🔧 Configuration

### Key Settings (`settings.txt`)
```ini
# Databento Configuration
DATABENTO_KEY=your_api_key
DATABENTO_DATASET=GLBX.MDP3
DATABENTO_SYMBOL=ES.FUT

# Trading Strategy
MIN_HOLD_TIME_SECONDS=30
MAX_HOLD_TIME_MINUTES=30
POSITION_SIZE=1  # Always 1 ES contract

# Model Configuration
MODEL_PREDICTION_HORIZONS=1,3,5
MODEL_TRAIN_SPLIT_RATIO=0.6,0.2,0.2
MODEL_SESSION_SPLIT_SEED=42

# Ray Cluster Configuration
RAY_HEAD_NODE=localhost:10001
RAY_WORKER_NODES=r630xl:6379,r810:6379
```

### Cross-Platform Ray Cluster Configuration (`config/ray_cluster_config.json`)
```json
{
  "head_node": {
    "node_id": "laptop",
    "name": "Development Laptop (Windows)",
    "address": "localhost",
    "port": 10001,
    "platform": "windows",
    "paths": {
      "project_root": "C:\\Users\\user\\Documents\\GitHub\\QuantTime",
      "python_executable": "python"
    }
  },
  "worker_nodes": [
    {
      "node_id": "windows_gpu",
      "name": "Windows GPU Node (NVIDIA)",
      "address": "windows-gpu-node",
      "platform": "windows",
      "resources": {"CPU": 16, "GPU": 1, "memory": 32.0},
      "paths": {
        "project_root": "C:\\QuantTime",
        "python_executable": "python"
      }
    },
    {
      "node_id": "r630xl",
      "name": "R630XL Server (Ubuntu)",
      "address": "jupiter",
      "platform": "linux",
      "resources": {"CPU": 16, "GPU": 0, "memory": 64.0},
      "paths": {
        "project_root": "/opt/quanttime",
        "python_executable": "/opt/quanttime/.venv/bin/python"
      }
    }
  ],
  "git_config": {
    "repository_url": "https://github.com/njliautaud/QuantTime.git",
    "auto_pull_enabled": true,
    "monitor_interval_seconds": 30
  }
}
```

## 📊 Data Processing

### MBO Data Structure
```
data/es_futures/mbo/
├── manifest.json
├── metadata.json
├── symbology.json
└── glbx-mdp3-YYYYMMDD.mbo.dbn.zst
```

### Feature Categories
1. **Order Book Features**: Bid/ask spreads, depth, imbalance
2. **Order Flow Features**: Volume, net flow, add/cancel ratios
3. **Market Microstructure**: Price momentum, volatility, efficiency
4. **Rolling Features**: Moving averages, standard deviations
5. **Cross Features**: Interaction terms between features

## 🚀 Distributed Computing

### Ray Job Types
- **Model Training**: Distributed training across multiple nodes
- **Backtesting**: Tick-based backtesting on high-performance servers
- **Data Processing**: Normalization and feature engineering
- **Live Trading**: RL trade engine execution
- **Data Analysis**: MBO statistics and quality validation
- **Model Evaluation**: Performance and robustness testing

### Dashboard Integration
- **Job Submission**: Submit jobs via Streamlit dashboard
- **Progress Monitoring**: Real-time job status and progress
- **Resource Management**: Cluster resource utilization
- **Results Collection**: Automatic result synchronization

## 🚀 Cross-Platform Deployment

### Automated Deployment
The system provides seamless cross-platform deployment:

1. **Start QuantTime**: `python run.py`
2. **Configure nodes** via dashboard Settings
3. **Enable auto-deployment** for hands-free operation

### Manual Deployment Commands
```bash
# Full cross-platform deployment
python scripts/deploy_nodes.py full

# Individual commands
python scripts/deploy_nodes.py git-check    # Check Git repository status
python scripts/deploy_nodes.py deploy       # Deploy to Windows + Linux nodes
python scripts/deploy_nodes.py health       # Check all node health
python scripts/deploy_nodes.py ray          # Start Ray workers
python scripts/deploy_nodes.py sync         # SFTP sync large files
```

### Cross-Platform Features
- **🔄 Git Auto-Sync**: Monitors repository for changes
- **📡 SSH Management**: Secure connections to all nodes
- **📁 SFTP Sync**: Large file synchronization
- **⚡ Ray Integration**: Distributed job execution
- **🖥️ Windows Support**: Native Windows node management
- **🐧 Linux Support**: Ubuntu/Debian server management

### Node Health Monitoring
- **🟢 Green**: All systems operational (Git synced, Ray connected)
- **🟡 Yellow**: Connected but issues (outdated code, Ray disconnected)
- **🔴 Red**: Cannot connect to node (SSH/network issues)

## 🧪 Testing

Run the comprehensive test suite:
```bash
python test_mbo_pipeline.py
```

This tests:
- MBO data reading and parsing
- Feature engineering pipeline
- Tick-based backtesting engine functionality
- Session-based data splits
- Ray job submission and execution

## 📚 Documentation

- **Master Model Rulebook**: `docs/MASTER_MODEL_RULEBOOK.md`
- **LLM Tools**: `docs/LLM_TOOLS.md`
- **Ray Implementation**: `docs/ENHANCED_MODEL_SYSTEM_GUIDE.md`
- **Distributed Computing**: `docs/DISTRIBUTED_COMPUTE_IMPLEMENTATION.md`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📁 Clean Directory Structure

The root directory has been cleaned to show only essential files:

```
QuantTime/
├── run.py                    # Main application entry point
├── setup_quanttime.py        # Complete setup script
├── requirements.txt          # Python dependencies
├── pyproject.toml           # Project configuration
├── settings.txt             # Application settings
├── README.md                # This file
├── .gitignore               # Git ignore rules
├── .gitattributes           # Git attributes
├── quanttime/               # Main application package
├── data/                    # Data directory
├── config/                  # Configuration files
├── models/                  # Trained models
├── backtests/               # Backtest results
├── logs/                    # Application logs
├── cache/                   # Cache files
├── temp/                    # Temporary files
├── shared/                  # Shared resources
├── server/                  # Server components
├── tools/                   # Utility tools
├── docs/                    # Documentation (moved from root)
├── scripts/                 # Setup and utility scripts (moved from root)
└── external/                # External libraries (moved from root)
```

### Moved Files
- **Documentation**: All `.md` files moved to `docs/`
- **Setup Scripts**: Additional setup scripts moved to `scripts/`
- **External Libraries**: `databento-python-main/` and `lightweight-charts-master/` moved to `external/`
- **Docker Files**: `docker-compose.yml` and `Dockerfile` moved to `scripts/`

This keeps the root directory clean and focused on the essential files you need to run the application.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading involves substantial risk of loss and is not suitable for all investors. Past performance does not guarantee future results.

## 🔄 Migration from Sierra Chart

This project has been **completely migrated** from Sierra Chart to Databento with Ray distributed computing:
- ✅ All Sierra Chart DTC components archived
- ✅ Full Databento MBO integration
- ✅ Tick-based Level 3 MBO processing
- ✅ 1 ES contract position management
- ✅ RL trade engine implementation
- ✅ Ray distributed computing integration
- ✅ Session-based data splits implemented
- ✅ Walk-forward backtesting added

The archived Sierra Chart components are available in `archive/sierra_chart/` for reference only.


