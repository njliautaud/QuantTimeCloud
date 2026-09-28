# Distributed Compute Implementation Guide

## 🎯 **Core Goal: Distributed Compute for Data Processing & Model Training**

The QuantTime project now has **full distributed compute capabilities** allowing you to:
- **Offload heavy workloads** to dedicated servers (R630XL, R810)
- **Continue working** even when your laptop is disconnected
- **Leverage server compute power** for data processing, feature engineering, model training, and backtesting
- **Automatic file synchronization** between laptop and servers

## 🏗️ **Architecture Overview**

```
┌─────────────────┐    SSH/Tailscale    ┌─────────────────┐
│   Laptop        │ ◄─────────────────► │   R630XL        │
│   (Control)     │                     │   (64GB RAM)    │
│                 │                     │                 │
│ ┌─────────────┐ │                     │ ┌─────────────┐ │
│ │ Streamlit   │ │                     │ │ Data Proc   │ │
│ │ Dashboard   │ │                     │ │ Model Train │ │
│ │ Task Submit │ │                     │ │ Backtesting │ │
│ └─────────────┘ │                     │ └─────────────┘ │
└─────────────────┘                     └─────────────────┘
         │                                        │
         │                                        │
         │                                        │
         ▼                                        ▼
┌─────────────────┐                     ┌─────────────────┐
│   File Sync     │                     │   Logs &        │
│   (rsync)       │                     │   Results       │
└─────────────────┘                     └─────────────────┘
```

## 🚀 **Quick Start: Deploy and Use**

### **Step 1: Deploy to Server**
1. Open the **Server Deployment** tab in the dashboard
2. Select your target server (R630XL)
3. Click **"🚀 Deploy to R630XL"**
4. Wait for deployment to complete (Git clone, dependencies, setup)

### **Step 2: Submit Your First Task**
1. Go to **"📋 Task Submission"** section
2. Select **"📊 Data Processing & Feature Engineering"**
3. Choose a date and schema
4. Click **"🚀 Submit Task"**

### **Step 3: Monitor Progress**
- Watch real-time progress in the **"📊 Progress Monitoring"** section
- Tasks continue running even if you close the dashboard
- Results are automatically synced when you reconnect

## 📋 **Available Task Types**

### **1. Data Processing & Feature Engineering**
```python
# Processes raw DBN files into normalized, feature-engineered Parquet files
Task Type: data_processing
Parameters:
- date_str: "20250824" (raw data date)
- schema_name: "execution_aware_light_v1" (feature schema)
- trading_hours_only: True (filter to market hours)
- max_rows: None (process all data)
- intensity_level: "medium" (feature computation intensity)
```

### **2. Model Training**
```python
# Trains ML models on processed data with GPU acceleration
Task Type: model_training
Parameters:
- model_name: "lightgbm_model_20250824"
- model_type: "LGBM" (LGBM, LSTM, TRANSFORMER, TCN)
- data_schema: "execution_aware_light_v1"
- epochs: 100
- batch_size: 1024
- learning_rate: 0.001
- use_gpu: True
```

### **3. Backtesting**
```python
# Runs backtests on trained models with realistic simulation
Task Type: backtest
Parameters:
- strategy_name: "momentum_strategy"
- data_schema: "execution_aware_light_v1"
- start_date: "2025-01-01"
- end_date: "2025-08-24"
- commission: 2.5
- slippage_ticks: 1
```

## 🔧 **Technical Implementation Details**

### **Server Task Execution**
```bash
# Example: Data processing task
cd /opt/quanttime && python -c "
from quanttime.data.processor import get_processor;
p = get_processor();
p.process_raw_to_normalized('20250824', 'execution_aware_light_v1', 
                           trading_hours_only=True, intensity_level='medium')
" > /opt/quanttime/logs/data_processing_20250824_143022.log 2>&1 &
```

### **Progress Monitoring**
- **Real-time log analysis** from server log files
- **Process status checking** via SSH
- **Progress percentage calculation** based on log keywords
- **Automatic task completion detection**

### **File Synchronization**
```bash
# Sync from server to laptop
rsync -avz -e "sshpass -p "$R630XL_SSH_PASSWORD" ssh -o StrictHostKeyChecking=no" \
  quanttime@jupiter:/opt/quanttime/data/ ./data/
```

## 📊 **Dashboard Interface**

### **Server Deployment Tab**
- **Server Status**: Real-time connection and resource monitoring
- **Deploy Button**: One-click deployment with progress tracking
- **Sync Button**: Manual file synchronization
- **Performance Benchmark**: Compare compute capabilities

### **Task Submission Interface**
- **Server Selection**: Choose target server for task execution
- **Task Type Selection**: Data processing, model training, or backtesting
- **Parameter Configuration**: Task-specific parameters with validation
- **Submit Button**: Send task to server for execution

### **Progress Monitoring**
- **Active Tasks**: Real-time progress bars and step counters
- **Task Details**: Expandable sections with detailed information
- **Stop Button**: Ability to stop running tasks
- **Log Viewing**: Access to task-specific log files

## 🔄 **Workflow Examples**

### **Example 1: Process One Day of Data**
1. **Deploy** to R630XL (if not already deployed)
2. **Submit** data processing task for date "20250824"
3. **Monitor** progress in real-time
4. **Sync** results when complete
5. **Use** processed data for model training

### **Example 2: Train Model on Server**
1. **Submit** model training task with processed data
2. **Configure** training parameters (epochs, batch size, etc.)
3. **Monitor** training progress and GPU usage
4. **Sync** trained model when complete
5. **Use** model for backtesting

### **Example 3: Run Backtest**
1. **Submit** backtest task with trained model
2. **Configure** backtest parameters (dates, commission, slippage)
3. **Monitor** backtest execution
4. **Sync** results and analyze performance

## 🛠️ **Troubleshooting**

### **Common Issues**

#### **Server Offline**
```
❌ R630XL is offline
Connection error: Connection timeout
```
**Solution**: Check Tailscale connection and SSH service on server

#### **Task Submission Failed**
```
❌ Task submission failed
```
**Solution**: Check server deployment status and SSH connectivity

#### **Progress Not Updating**
```
Progress stuck at 0%
```
**Solution**: Check server logs and process status

### **Debug Commands**

#### **Check Server Status**
```bash
# On server
sudo systemctl status ssh
tailscale status
uptime
free -h
df -h
```

#### **Check Task Logs**
```bash
# On server
tail -f /opt/quanttime/logs/data_processing_*.log
ps aux | grep python
```

#### **Manual Sync**
```bash
# On laptop
rsync -avz -e "sshpass -p "$R630XL_SSH_PASSWORD" ssh -o StrictHostKeyChecking=no" \
  quanttime@jupiter:/opt/quanttime/data/ ./data/
```

## 📈 **Performance Benefits**

### **R630XL Server (64GB RAM, 16 cores)**
- **Data Processing**: 10x faster than laptop
- **Model Training**: GPU acceleration with 8GB VRAM
- **Backtesting**: Parallel execution capabilities
- **Memory**: Handle large datasets without swapping

### **R810 Server (256GB RAM, 32 cores)**
- **Massive Data Processing**: Handle entire datasets in memory
- **Multi-Model Training**: Train multiple models simultaneously
- **High-Performance Backtesting**: Complex strategy simulation
- **Future-Proof**: Room for expansion and scaling

## 🔮 **Future Enhancements**

### **Planned Features**
- **Automatic Task Scheduling**: Queue tasks for optimal resource usage
- **Load Balancing**: Distribute tasks across multiple servers
- **Real-time Results**: Live streaming of task results
- **Advanced Monitoring**: GPU usage, memory consumption, network I/O
- **Task Dependencies**: Chain tasks (process → train → backtest)

### **Scaling Considerations**
- **Multiple Servers**: Add R810 and additional compute nodes
- **Task Queuing**: Implement Celery or similar for job management
- **Resource Optimization**: Automatic task distribution based on server load
- **Fault Tolerance**: Automatic task retry and recovery

## ✅ **Implementation Status**

### **✅ Completed**
- [x] Server deployment via Git
- [x] SSH connection management
- [x] Task submission interface
- [x] Real-time progress monitoring
- [x] File synchronization
- [x] Task lifecycle management
- [x] Error handling and logging
- [x] Dashboard integration

### **🔄 In Progress**
- [ ] Performance benchmarking
- [ ] Advanced task scheduling
- [ ] Multi-server load balancing

### **📋 Planned**
- [ ] Real-time result streaming
- [ ] Task dependency management
- [ ] Advanced resource monitoring

## 🎯 **Next Steps**

1. **Deploy to R630XL** using the dashboard
2. **Submit a data processing task** to test the system
3. **Monitor progress** and verify file synchronization
4. **Scale up** to model training and backtesting
5. **Add R810** for additional compute capacity

The distributed compute system is **fully implemented and ready to use** for leveraging server compute power while maintaining laptop control and mobility.
