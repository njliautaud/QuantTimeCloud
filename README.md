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
- Python 3.8+
- Databento account with MBO data access
- Local Databento MBO data files (`.dbn.zst` format)
- Ray distributed computing cluster (optional for distributed processing)

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd QuantTime

# Start the dashboard (configuration wizard will appear automatically)
python run.py
```

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

### Distributed Computing
- **Ray Cluster Management**: Submit jobs to multiple servers via dashboard
- **Distributed Training**: Train models across multiple nodes
- **Distributed Backtesting**: Run backtests on high-performance servers
- **Job Queue Management**: Monitor and manage distributed jobs
- **Resource Monitoring**: Real-time cluster resource utilization
- **Node Deployment**: Automatic deployment and health monitoring
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

### Ray Cluster Configuration (`config/ray_cluster_config.json`)
```json
{
  "head_node": {
    "node_id": "laptop",
    "name": "Development Laptop",
    "address": "localhost",
    "port": 10001,
    "dashboard_port": 8265,
    "is_head": true
  },
  "worker_nodes": [
    {
      "node_id": "r630xl",
      "name": "R630XL Server (Jupiter)",
      "address": "jupiter",
      "port": 6379,
      "dashboard_port": 8265,
      "is_head": false
    },
    {
      "node_id": "r810",
      "name": "R810 Server",
      "address": "saturn",
      "port": 6379,
      "dashboard_port": 8265,
      "is_head": false
    }
  ]
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

## 🚀 Deployment

### Dashboard Deployment
1. **Run the dashboard**: `python run.py`
2. **Follow the configuration wizard** for initial setup
3. **Go to Settings → "🚀 Deploy"** for node management

### Command-Line Deployment
```bash
# Full deployment (recommended)
python scripts/deploy_nodes.py full

# Individual commands
python scripts/deploy_nodes.py git-check    # Check Git status
python scripts/deploy_nodes.py deploy       # Deploy to all nodes
python scripts/deploy_nodes.py health       # Check node health
python scripts/deploy_nodes.py ray          # Start Ray clusters
python scripts/deploy_nodes.py sync         # Sync large files
```

### Node Health Monitoring
- **🟢 Green**: All systems operational
- **🟡 Yellow**: Connected but issues (missing dependencies, version mismatch)
- **🔴 Red**: Cannot connect to node

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


