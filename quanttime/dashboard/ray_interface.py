"""
Ray Cluster Management Interface
Integrated Ray cluster management for QuantTime dashboard
"""

import streamlit as st
import subprocess
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import threading
import queue

logger = logging.getLogger(__name__)

class RayClusterManager:
    """Manages Ray cluster operations and monitoring"""
    
    def __init__(self):
        self.config_file = Path("config/ray_config.json")
        self.cluster_status = {}
        self.job_queue = queue.Queue()
        
    def load_config(self) -> Dict:
        """Load Ray cluster configuration"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            else:
                return self._create_default_config()
        except Exception as e:
            logger.error(f"Failed to load Ray config: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict:
        """Create default Ray configuration"""
        config = {
            "head_node": {
                "ip": "localhost",
                "port": 10001,
                "dashboard_port": 8265
            },
            "worker_nodes": [],
            "resources": {
                "num_cpus": 4,
                "memory": "8GB",
                "object_store_memory": "2GB"
            },
            "temp_dir": "./temp/ray",
            "log_dir": "./logs/ray"
        }
        
        # Save default config
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        return config
    
    def start_head_node(self) -> Tuple[bool, str]:
        """Start Ray head node"""
        try:
            config = self.load_config()
            head_config = config["head_node"]
            
            cmd = [
                "ray", "start", "--head",
                f"--port={head_config['port']}",
                f"--dashboard-port={head_config['dashboard_port']}",
                f"--temp-dir={config['temp_dir']}",
                f"--log-dir={config['log_dir']}",
                f"--object-store-memory={config['resources']['object_store_memory']}",
                f"--num-cpus={config['resources']['num_cpus']}",
                f"--memory={config['resources']['memory']}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True, "Ray head node started successfully"
            else:
                return False, f"Failed to start Ray head node: {result.stderr}"
                
        except Exception as e:
            return False, f"Error starting Ray head node: {e}"
    
    def connect_worker_node(self, node_ip: str, node_port: int = 10001) -> Tuple[bool, str]:
        """Connect a worker node to the cluster"""
        try:
            config = self.load_config()
            head_ip = config["head_node"]["ip"]
            head_port = config["head_node"]["port"]
            
            cmd = [
                "ray", "start",
                f"--address={head_ip}:{head_port}",
                f"--temp-dir={config['temp_dir']}",
                f"--log-dir={config['log_dir']}",
                f"--object-store-memory={config['resources']['object_store_memory']}",
                f"--num-cpus={config['resources']['num_cpus']}",
                f"--memory={config['resources']['memory']}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True, f"Worker node {node_ip} connected successfully"
            else:
                return False, f"Failed to connect worker node {node_ip}: {result.stderr}"
                
        except Exception as e:
            return False, f"Error connecting worker node {node_ip}: {e}"
    
    def get_cluster_status(self) -> Dict:
        """Get current cluster status"""
        try:
            import ray
            
            if not ray.is_initialized():
                return {"status": "not_initialized", "nodes": [], "resources": {}}
            
            # Get cluster resources
            resources = ray.cluster_resources()
            available_resources = ray.available_resources()
            
            # Get node information
            nodes = []
            try:
                # Try to get node info from Ray dashboard API
                dashboard_port = self.load_config()["head_node"]["dashboard_port"]
                response = requests.get(f"http://localhost:{dashboard_port}/api/cluster")
                if response.status_code == 200:
                    cluster_info = response.json()
                    nodes = cluster_info.get("nodes", [])
            except:
                # Fallback to basic info
                nodes = [{"node_id": "head", "status": "alive"}]
            
            return {
                "status": "running",
                "nodes": nodes,
                "resources": {
                    "total": resources,
                    "available": available_resources
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting cluster status: {e}")
            return {"status": "error", "error": str(e), "nodes": [], "resources": {}}
    
    def submit_job(self, job_type: str, job_config: Dict) -> str:
        """Submit a job to the Ray cluster"""
        try:
            import ray
            
            if not ray.is_initialized():
                return "Ray not initialized"
            
            # Submit job based on type
            if job_type == "training":
                job_id = self._submit_training_job(job_config)
            elif job_type == "backtest":
                job_id = self._submit_backtest_job(job_config)
            elif job_type == "data_processing":
                job_id = self._submit_data_processing_job(job_config)
            else:
                return f"Unknown job type: {job_type}"
            
            return f"Job submitted with ID: {job_id}"
            
        except Exception as e:
            return f"Error submitting job: {e}"
    
    def _submit_training_job(self, config: Dict) -> str:
        """Submit a training job"""
        import ray
        
        @ray.remote
        def train_model(model_config):
            # Training logic here
            return {"status": "completed", "model_path": "/path/to/model"}
        
        job_id = train_model.remote(config)
        return str(job_id)
    
    def _submit_backtest_job(self, config: Dict) -> str:
        """Submit a backtest job"""
        import ray
        
        @ray.remote
        def run_backtest(backtest_config):
            # Backtest logic here
            return {"status": "completed", "results": "/path/to/results"}
        
        job_id = run_backtest.remote(config)
        return str(job_id)
    
    def _submit_data_processing_job(self, config: Dict) -> str:
        """Submit a data processing job"""
        import ray
        
        @ray.remote
        def process_data(data_config):
            # Data processing logic here
            return {"status": "completed", "processed_data": "/path/to/data"}
        
        job_id = process_data.remote(config)
        return str(job_id)
    
    def get_job_status(self, job_id: str) -> Dict:
        """Get status of a specific job"""
        try:
            import ray
            
            if not ray.is_initialized():
                return {"status": "ray_not_initialized"}
            
            # Get job status from Ray
            job_status = ray.get_runtime_context().get_object_refs()
            
            return {
                "job_id": job_id,
                "status": "running",  # Placeholder
                "progress": 0.5,  # Placeholder
                "result": None
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

def render_ray_cluster_dashboard():
    """Render the Ray cluster management dashboard"""
    st.header("⚡ Ray Cluster Management")
    
    # Initialize cluster manager
    manager = RayClusterManager()
    
    # Load configuration
    config = manager.load_config()
    
    # Create tabs for different functions
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Cluster Status", "🚀 Start Cluster", "📋 Job Management", "⚙️ Configuration"])
    
    with tab1:
        render_cluster_status_tab(manager)
    
    with tab2:
        render_start_cluster_tab(manager, config)
    
    with tab3:
        render_job_management_tab(manager)
    
    with tab4:
        render_configuration_tab(manager, config)

def render_cluster_status_tab(manager: RayClusterManager):
    """Render cluster status tab"""
    st.subheader("📊 Cluster Status")
    
    # Get current status
    status = manager.get_cluster_status()
    
    # Display status
    if status["status"] == "running":
        st.success("🟢 Ray cluster is running")
        
        # Show resources
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total CPUs", status["resources"]["total"].get("CPU", 0))
            st.metric("Total Memory", f"{status['resources']['total'].get('memory', 0) / 1e9:.1f} GB")
        
        with col2:
            st.metric("Available CPUs", status["resources"]["available"].get("CPU", 0))
            st.metric("Available Memory", f"{status['resources']['available'].get('memory', 0) / 1e9:.1f} GB")
        
        # Show nodes
        st.subheader("🖥️ Cluster Nodes")
        for node in status["nodes"]:
            st.info(f"Node: {node.get('node_id', 'Unknown')} - Status: {node.get('status', 'Unknown')}")
            
    elif status["status"] == "not_initialized":
        st.warning("🟡 Ray cluster is not initialized")
        st.info("Use the 'Start Cluster' tab to initialize the cluster")
        
    else:
        st.error("🔴 Ray cluster error")
        st.error(f"Error: {status.get('error', 'Unknown error')}")
    
    # Refresh button
    if st.button("🔄 Refresh Status"):
        st.rerun()

def render_start_cluster_tab(manager: RayClusterManager, config: Dict):
    """Render start cluster tab"""
    st.subheader("🚀 Start Ray Cluster")
    
    # Head node section
    st.write("### Head Node")
    
    col1, col2 = st.columns(2)
    with col1:
        head_ip = st.text_input("Head Node IP", value=config["head_node"]["ip"])
        head_port = st.number_input("Head Node Port", value=config["head_node"]["port"])
    
    with col2:
        dashboard_port = st.number_input("Dashboard Port", value=config["head_node"]["dashboard_port"])
    
    # Start head node button
    if st.button("🚀 Start Head Node"):
        with st.spinner("Starting Ray head node..."):
            success, message = manager.start_head_node()
            if success:
                st.success(message)
                st.info(f"Ray dashboard available at: http://localhost:{dashboard_port}")
            else:
                st.error(message)
    
    # Worker nodes section
    st.write("### Worker Nodes")
    
    # Add worker node
    worker_ip = st.text_input("Worker Node IP")
    if st.button("➕ Add Worker Node"):
        if worker_ip:
            with st.spinner(f"Connecting worker node {worker_ip}..."):
                success, message = manager.connect_worker_node(worker_ip)
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    # Show existing worker nodes
    if config["worker_nodes"]:
        st.write("**Connected Worker Nodes:**")
        for worker in config["worker_nodes"]:
            st.info(f"Worker: {worker['ip']}:{worker['port']}")

def render_job_management_tab(manager: RayClusterManager):
    """Render job management tab"""
    st.subheader("📋 Job Management")
    
    # Job submission
    st.write("### Submit Job")
    
    job_type = st.selectbox("Job Type", ["training", "backtest", "data_processing"])
    
    if job_type == "training":
        job_config = {
            "model": st.selectbox("Model", ["lightgbm", "xgboost", "neural_network"]),
            "data_path": st.text_input("Data Path", value="./data"),
            "epochs": st.number_input("Epochs", value=100)
        }
    elif job_type == "backtest":
        job_config = {
            "strategy": st.selectbox("Strategy", ["momentum", "mean_reversion", "ml_based"]),
            "start_date": st.date_input("Start Date"),
            "end_date": st.date_input("End Date"),
            "symbol": st.text_input("Symbol", value="ES.FUT")
        }
    else:  # data_processing
        job_config = {
            "input_path": st.text_input("Input Path", value="./data/raw"),
            "output_path": st.text_input("Output Path", value="./data/processed"),
            "batch_size": st.number_input("Batch Size", value=1000)
        }
    
    if st.button("📤 Submit Job"):
        with st.spinner("Submitting job..."):
            result = manager.submit_job(job_type, job_config)
            st.info(result)
    
    # Job monitoring
    st.write("### Job Status")
    job_id = st.text_input("Job ID")
    if st.button("🔍 Check Job Status"):
        if job_id:
            status = manager.get_job_status(job_id)
            st.json(status)

def render_configuration_tab(manager: RayClusterManager, config: Dict):
    """Render configuration tab"""
    st.subheader("⚙️ Ray Configuration")
    
    # Display current configuration
    st.json(config)
    
    # Configuration editor
    st.write("### Edit Configuration")
    
    # Resources
    st.write("**Resources:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        num_cpus = st.number_input("Number of CPUs", value=config["resources"]["num_cpus"])
    with col2:
        memory = st.text_input("Memory", value=config["resources"]["memory"])
    with col3:
        object_store_memory = st.text_input("Object Store Memory", value=config["resources"]["object_store_memory"])
    
    # Directories
    st.write("**Directories:**")
    col1, col2 = st.columns(2)
    with col1:
        temp_dir = st.text_input("Temp Directory", value=config["temp_dir"])
    with col2:
        log_dir = st.text_input("Log Directory", value=config["log_dir"])
    
    # Save configuration
    if st.button("💾 Save Configuration"):
        config["resources"]["num_cpus"] = num_cpus
        config["resources"]["memory"] = memory
        config["resources"]["object_store_memory"] = object_store_memory
        config["temp_dir"] = temp_dir
        config["log_dir"] = log_dir
        
        with open(manager.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        st.success("Configuration saved successfully!")

# Export the main function for use in the dashboard
def ray_interface():
    """Main Ray interface function"""
    render_ray_cluster_dashboard()
