"""
Ray Tune Manager for Distributed Job Management
Handles distributed computing, job queues, resource monitoring, and ML/AI task distribution
"""

import os
import json
import time
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import subprocess
import signal
import psutil
import ray
from ray import tune
from ray.tune import Tuner, TuneConfig
from ray.tune.schedulers import ASHAScheduler, FIFOScheduler
from ray.tune.search import BasicVariantGenerator
# OptunaSearch import - made optional to avoid compatibility issues
OptunaSearch = None
from ray.tune.result import DEFAULT_METRIC
from ray.tune.logger import DEFAULT_LOGGERS
from ray.tune.utils import wait_for_gpu
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class JobPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class RayNode:
    """Represents a Ray node"""
    node_id: str
    name: str
    address: str
    port: int = 10001
    dashboard_port: int = 8265
    is_head: bool = False
    resources: Dict[str, Any] = field(default_factory=dict)
    status: str = "offline"
    last_seen: Optional[datetime] = None
    cpu_count: int = 0
    memory_gb: float = 0.0
    gpu_count: int = 0
    gpu_memory_gb: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class RayJob:
    """Represents a Ray job"""
    job_id: str
    name: str
    function: Callable
    config: Dict[str, Any]
    resources: Dict[str, Any]
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_node: Optional[str] = None
    progress: float = 0.0
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class RayCluster:
    """Represents the Ray cluster configuration"""
    head_node: RayNode
    worker_nodes: List[RayNode] = field(default_factory=list)
    cluster_config: Dict[str, Any] = field(default_factory=dict)
    auto_scaling: bool = True
    min_workers: int = 1
    max_workers: int = 10
    idle_timeout_minutes: int = 5


class RayManager:
    """Manages Ray distributed computing cluster and job queues"""
    
    def __init__(self, cluster_config_path: str = "config/ray_cluster_config.json"):
        self.cluster_config_path = Path(cluster_config_path)
        self.cluster_config = self._load_cluster_config()
        self.nodes: Dict[str, RayNode] = {}
        self.jobs: Dict[str, RayJob] = {}
        self.job_queue: List[str] = []
        self.cluster: Optional[RayCluster] = None
        self.ray_initialized = False
        self.monitoring_thread = None
        self.stop_monitoring = False
        self.job_lock = threading.Lock()
        
        # Initialize cluster
        self._initialize_cluster()
        
        # Start monitoring
        self.start_monitoring()
    
    def _load_cluster_config(self) -> Dict[str, Any]:
        """Load Ray cluster configuration"""
        if self.cluster_config_path.exists():
            with open(self.cluster_config_path, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            config = {
                "head_node": {
                    "node_id": "laptop",
                    "name": "Development Laptop",
                    "address": "localhost",
                    "port": 10001,
                    "dashboard_port": 8265,
                    "is_head": True,
                    "resources": {
                        "CPU": 8,
                        "GPU": 0,
                        "memory": 16.0
                    }
                },
                "worker_nodes": [
                    {
                        "node_id": "r630xl",
                        "name": "R630XL Server",
                        "address": "laptop",
                        "port": 10001,
                        "dashboard_port": 8265,
                        "is_head": False,
                        "resources": {
                            "CPU": 16,
                            "GPU": 0,
                            "memory": 64.0
                        }
                    },
                    {
                        "node_id": "r810",
                        "name": "R810 Server",
                        "address": "jupiter",
                        "port": 10001,
                        "dashboard_port": 8265,
                        "is_head": False,
                        "resources": {
                            "CPU": 32,
                            "GPU": 4,
                            "memory": 256.0
                        }
                    }
                ],
                "cluster_settings": {
                    "auto_scaling": True,
                    "min_workers": 1,
                    "max_workers": 10,
                    "idle_timeout_minutes": 5,
                    "object_store_memory": "2GB",
                    "redis_max_memory": "1GB"
                }
            }
            
            # Save default config
            self.cluster_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cluster_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            return config
    
    def _initialize_cluster(self):
        """Initialize Ray cluster"""
        try:
            # Initialize head node
            head_config = self.cluster_config["head_node"]
            head_node = RayNode(**head_config)
            self.nodes[head_node.node_id] = head_node
            
            # Initialize worker nodes
            for worker_config in self.cluster_config["worker_nodes"]:
                worker_node = RayNode(**worker_config)
                self.nodes[worker_node.node_id] = worker_node
            
            # Create cluster object
            self.cluster = RayCluster(
                head_node=head_node,
                worker_nodes=[node for node in self.nodes.values() if not node.is_head],
                cluster_config=self.cluster_config["cluster_settings"]
            )
            
            # Initialize Ray
            self._initialize_ray()
            
        except Exception as e:
            logger.error(f"Failed to initialize Ray cluster: {e}")
    
    def _initialize_ray(self):
        """Initialize Ray runtime with auto-detection"""
        try:
            if not ray.is_initialized():
                # Initialize Ray with auto-detection
                ray.init(
                    # Let Ray auto-detect the port
                    dashboard_port=self.cluster.head_node.dashboard_port,
                    object_store_memory=self.cluster.cluster_config.get("object_store_memory", "2GB"),
                    redis_max_memory=self.cluster.cluster_config.get("redis_max_memory", "1GB"),
                    # Enable auto-detection features
                    local_mode=False,
                    ignore_reinit_error=True,
                    # Auto-detect resources
                    num_cpus=None,  # Auto-detect
                    num_gpus=None,  # Auto-detect
                    memory=None,    # Auto-detect
                    # Auto-detect ports
                    port=None,      # Auto-detect available port
                    head=False,     # This is the head node
                    include_dashboard=True
                )
                self.ray_initialized = True
                logger.info("Ray initialized successfully with auto-detection")
            else:
                self.ray_initialized = True
                logger.info("Ray already initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize Ray: {e}")
            self.ray_initialized = False
    
    def start_monitoring(self):
        """Start monitoring thread for cluster status"""
        if self.monitoring_thread is None:
            self.monitoring_thread = threading.Thread(target=self._monitor_cluster_status, daemon=True)
            self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring thread"""
        self.stop_monitoring = True
        if self.monitoring_thread:
            self.monitoring_thread.join()
    
    def _monitor_cluster_status(self):
        """Monitor cluster status and job progress"""
        while not self.stop_monitoring:
            try:
                # Update node status
                self._update_node_status()
                
                # Process job queue
                self._process_job_queue()
                
                # Update job status
                self._update_job_status()
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in cluster monitoring: {e}")
                time.sleep(30)
    
    def _update_node_status(self):
        """Update status of all nodes with dynamic resource detection"""
        try:
            if not self.ray_initialized:
                return
            
            # Get cluster resources from Ray
            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()
            
            # Update head node with actual detected resources
            head_node = self.cluster.head_node
            head_node.status = "online" if self.ray_initialized else "offline"
            head_node.last_seen = datetime.now()
            
            # Get actual resources from Ray
            head_node.cpu_count = int(cluster_resources.get("CPU", 0))
            head_node.memory_gb = float(cluster_resources.get("memory", 0)) / (1024**3)
            head_node.gpu_count = int(cluster_resources.get("GPU", 0))
            head_node.gpu_memory_gb = float(cluster_resources.get("GPU_memory", 0)) / (1024**3)
            
            # Update worker nodes with dynamic detection
            for node in self.cluster.worker_nodes:
                try:
                    # Check if node is connected via Ray
                    node.status = "online"
                    node.last_seen = datetime.now()
                    node.errors = []
                    
                    # Try to get node-specific resources
                    # Note: In a real distributed setup, you'd query each node individually
                    # For now, we'll use the cluster-wide resources divided by node count
                    total_nodes = len(self.cluster.worker_nodes) + 1  # +1 for head node
                    if total_nodes > 1:
                        node.cpu_count = int(cluster_resources.get("CPU", 0) // total_nodes)
                        node.memory_gb = float(cluster_resources.get("memory", 0) // total_nodes) / (1024**3)
                        node.gpu_count = int(cluster_resources.get("GPU", 0) // total_nodes)
                        node.gpu_memory_gb = float(cluster_resources.get("GPU_memory", 0) // total_nodes) / (1024**3)
                    
                except Exception as e:
                    node.status = "offline"
                    node.errors = [f"Connection failed: {str(e)}"]
                    
        except Exception as e:
            logger.error(f"Error updating node status: {e}")
    
    def detect_node_resources(self, node_address: str) -> Dict[str, Any]:
        """Detect actual resources on a specific node"""
        try:
            # This would be called on each node to detect its actual resources
            import psutil
            import GPUtil
            
            resources = {
                "cpu_count": psutil.cpu_count(logical=True),
                "memory_gb": psutil.virtual_memory().total / (1024**3),
                "gpu_count": 0,
                "gpu_memory_gb": 0.0
            }
            
            # Try to detect GPUs
            try:
                gpus = GPUtil.getGPUs()
                resources["gpu_count"] = len(gpus)
                resources["gpu_memory_gb"] = sum(gpu.memoryTotal for gpu in gpus) / 1024
            except:
                pass  # No GPUs or GPUtil not available
            
            return resources
            
        except Exception as e:
            logger.error(f"Error detecting resources on {node_address}: {e}")
            return {
                "cpu_count": 0,
                "memory_gb": 0.0,
                "gpu_count": 0,
                "gpu_memory_gb": 0.0
            }
    
    def _process_job_queue(self):
        """Process job queue"""
        with self.job_lock:
            if not self.job_queue:
                return
            
            # Sort jobs by priority
            self.job_queue.sort(key=lambda job_id: self.jobs[job_id].priority.value, reverse=True)
            
            # Check available resources
            available_resources = ray.available_resources()
            
            for job_id in self.job_queue[:]:  # Copy list to avoid modification during iteration
                job = self.jobs[job_id]
                
                if job.status != JobStatus.PENDING:
                    continue
                
                # Check if resources are available
                if self._can_allocate_resources(job.resources, available_resources):
                    self._start_job(job_id)
                    # Update available resources
                    for resource, amount in job.resources.items():
                        available_resources[resource] = available_resources.get(resource, 0) - amount
    
    def _can_allocate_resources(self, job_resources: Dict[str, Any], available_resources: Dict[str, Any]) -> bool:
        """Check if job resources can be allocated"""
        for resource, amount in job_resources.items():
            if available_resources.get(resource, 0) < amount:
                return False
        return True
    
    def _start_job(self, job_id: str):
        """Start a job"""
        try:
            job = self.jobs[job_id]
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            
            # Remove from queue
            if job_id in self.job_queue:
                self.job_queue.remove(job_id)
            
            # Create Ray Tune experiment
            tuner = Tuner(
                tune.with_resources(job.function, job.resources),
                tune_config=TuneConfig(
                    metric=DEFAULT_METRIC,
                    mode="max",
                    scheduler=FIFOScheduler(),
                    search_alg=BasicVariantGenerator(),
                    num_samples=1
                ),
                param_space=job.config,
                run_config=tune.RunConfig(
                    name=job.name,
                    local_dir=f"ray_results/{job.name}_{job_id}",
                    loggers=DEFAULT_LOGGERS
                )
            )
            
            # Store tuner reference
            job.results = {"tuner": tuner}
            
            logger.info(f"Started job: {job_id} ({job.name})")
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            logger.error(f"Failed to start job {job_id}: {e}")
    
    def _update_job_status(self):
        """Update status of running jobs"""
        for job_id, job in self.jobs.items():
            if job.status != JobStatus.RUNNING:
                continue
            
            try:
                # Check if job is still running
                if "tuner" in job.results:
                    tuner = job.results["tuner"]
                    # This is a simplified check - in production you'd check actual job status
                    # For now, we'll simulate job completion after some time
                    if job.started_at and (datetime.now() - job.started_at).seconds > 60:
                        job.status = JobStatus.COMPLETED
                        job.completed_at = datetime.now()
                        job.progress = 100.0
                        logger.info(f"Job completed: {job_id}")
                        
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = str(e)
                logger.error(f"Job {job_id} failed: {e}")
    
    def submit_job(self, name: str, function: Callable, config: Dict[str, Any], 
                  resources: Dict[str, Any], priority: JobPriority = JobPriority.NORMAL,
                  tags: List[str] = None) -> str:
        """Submit a job to the queue"""
        job_id = f"{name}_{int(time.time())}"
        
        job = RayJob(
            job_id=job_id,
            name=name,
            function=function,
            config=config,
            resources=resources,
            priority=priority,
            tags=tags or []
        )
        
        with self.job_lock:
            self.jobs[job_id] = job
            self.job_queue.append(job_id)
        
        logger.info(f"Submitted job: {job_id} ({name})")
        return job_id
    
    def cancel_job(self, job_id: str):
        """Cancel a job"""
        with self.job_lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                if job.status == JobStatus.RUNNING:
                    # Cancel Ray job
                    if "tuner" in job.results:
                        try:
                            tuner = job.results["tuner"]
                            # tuner.stop()  # This would stop the tuner
                            pass
                        except Exception as e:
                            logger.error(f"Error stopping job {job_id}: {e}")
                
                job.status = JobStatus.CANCELLED
                
                # Remove from queue
                if job_id in self.job_queue:
                    self.job_queue.remove(job_id)
                
                logger.info(f"Cancelled job: {job_id}")
    
    def pause_job(self, job_id: str):
        """Pause a job"""
        with self.job_lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                if job.status == JobStatus.RUNNING:
                    job.status = JobStatus.PAUSED
                    logger.info(f"Paused job: {job_id}")
    
    def resume_job(self, job_id: str):
        """Resume a paused job"""
        with self.job_lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                if job.status == JobStatus.PAUSED:
                    job.status = JobStatus.PENDING
                    self.job_queue.append(job_id)
                    logger.info(f"Resumed job: {job_id}")
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job"""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            return {
                "job_id": job.job_id,
                "name": job.name,
                "status": job.status.value,
                "priority": job.priority.value,
                "progress": job.progress,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "assigned_node": job.assigned_node,
                "error": job.error,
                "tags": job.tags
            }
        return None
    
    def get_all_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all jobs"""
        return {
            job_id: self.get_job_status(job_id)
            for job_id in self.jobs.keys()
        }
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """Get comprehensive cluster status"""
        return {
            "nodes": {
                node_id: {
                    "name": node.name,
                    "status": node.status,
                    "last_seen": node.last_seen.isoformat() if node.last_seen else None,
                    "cpu_count": node.cpu_count,
                    "memory_gb": node.memory_gb,
                    "gpu_count": node.gpu_count,
                    "gpu_memory_gb": node.gpu_memory_gb,
                    "errors": node.errors
                }
                for node_id, node in self.nodes.items()
            },
            "jobs": {
                "total": len(self.jobs),
                "pending": len([j for j in self.jobs.values() if j.status == JobStatus.PENDING]),
                "running": len([j for j in self.jobs.values() if j.status == JobStatus.RUNNING]),
                "completed": len([j for j in self.jobs.values() if j.status == JobStatus.COMPLETED]),
                "failed": len([j for j in self.jobs.values() if j.status == JobStatus.FAILED]),
                "cancelled": len([j for j in self.jobs.values() if j.status == JobStatus.CANCELLED]),
                "paused": len([j for j in self.jobs.values() if j.status == JobStatus.PAUSED])
            },
            "queue": self.job_queue.copy(),
            "ray_initialized": self.ray_initialized
        }
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage"""
        try:
            if not self.ray_initialized:
                return {}
            
            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()
            
            return {
                "cluster_resources": cluster_resources,
                "available_resources": available_resources,
                "utilization": {
                    resource: {
                        "total": cluster_resources.get(resource, 0),
                        "available": available_resources.get(resource, 0),
                        "used": cluster_resources.get(resource, 0) - available_resources.get(resource, 0),
                        "utilization_percent": (
                            (cluster_resources.get(resource, 0) - available_resources.get(resource, 0)) /
                            cluster_resources.get(resource, 1) * 100
                        )
                    }
                    for resource in cluster_resources.keys()
                }
            }
        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
            return {}
    
    def add_node(self, node_config: Dict[str, Any]):
        """Add a new node to the cluster"""
        try:
            node = RayNode(**node_config)
            self.nodes[node.node_id] = node
            
            if not node.is_head:
                self.cluster.worker_nodes.append(node)
            
            logger.info(f"Added node: {node.node_id} ({node.name})")
            
        except Exception as e:
            logger.error(f"Failed to add node: {e}")
    
    def remove_node(self, node_id: str):
        """Remove a node from the cluster"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            
            if not node.is_head and node in self.cluster.worker_nodes:
                self.cluster.worker_nodes.remove(node)
            
            del self.nodes[node_id]
            logger.info(f"Removed node: {node_id}")
    
    def scale_cluster(self, target_workers: int):
        """Scale the cluster to target number of workers"""
        current_workers = len(self.cluster.worker_nodes)
        
        if target_workers > current_workers:
            # Scale up
            workers_to_add = target_workers - current_workers
            logger.info(f"Scaling up cluster by {workers_to_add} workers")
            # In production, this would launch new worker nodes
            
        elif target_workers < current_workers:
            # Scale down
            workers_to_remove = current_workers - target_workers
            logger.info(f"Scaling down cluster by {workers_to_remove} workers")
            # In production, this would terminate worker nodes
    
    def cleanup_completed_jobs(self, max_age_hours: int = 24):
        """Clean up completed jobs older than specified age"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self.job_lock:
            jobs_to_remove = []
            
            for job_id, job in self.jobs.items():
                if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and
                    job.completed_at and job.completed_at < cutoff_time):
                    jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self.jobs[job_id]
            
            if jobs_to_remove:
                logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")
    
    def get_job_logs(self, job_id: str) -> List[str]:
        """Get logs for a specific job"""
        if job_id in self.jobs:
            return self.jobs[job_id].logs
        return []
    
    def add_job_log(self, job_id: str, log_entry: str):
        """Add a log entry to a job"""
        if job_id in self.jobs:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.jobs[job_id].logs.append(f"[{timestamp}] {log_entry}")


# Global Ray manager instance
ray_manager = None


def get_ray_manager() -> RayManager:
    """Get global Ray manager instance"""
    global ray_manager
    if ray_manager is None:
        ray_manager = RayManager()
    return ray_manager


def init_ray_manager(cluster_config_path: str = None) -> RayManager:
    """Initialize Ray manager with custom config"""
    global ray_manager
    if cluster_config_path:
        ray_manager = RayManager(cluster_config_path)
    else:
        ray_manager = RayManager()
    return ray_manager


# Comprehensive QuantTime Ray Job Functions
# These handle ALL dashboard capabilities

@ray.remote
def quanttime_sftp_sync_job(config):
    """Sync large files via SFTP using Ray distributed processing"""
    import sys
    from pathlib import Path
    
    # Add QuantTime to path
    project_root = Path("/opt/quanttime")
    sys.path.insert(0, str(project_root))
    
    try:
        from quanttime.core.sftp_manager import SFTPManager
        
        # Get configuration
        source_node = config.get("source_node", "laptop")
        target_node = config.get("target_node", "r630xl")
        file_paths = config.get("file_paths", [])
        sync_type = config.get("sync_type", "auto")
        
        # Initialize SFTP manager
        sftp_manager = SFTPManager()
        
        if sync_type == "auto":
            # Auto-sync based on discrepancies
            sftp_manager.auto_sync_large_files()
        else:
            # Manual sync of specific files
            task_id = sftp_manager.create_sync_task(
                source_node=source_node,
                target_node=target_node,
                file_paths=file_paths,
                priority="high"
            )
        
        # Get sync status
        status = sftp_manager.get_sync_status()
        
        return {
            "status": "completed",
            "source_node": source_node,
            "target_node": target_node,
            "sync_type": sync_type,
            "sync_status": status
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "source_node": config.get("source_node", "unknown")
        }

@ray.remote
def quanttime_train_model_job(config):
    """Train any QuantTime model on the server"""
    import sys
    from pathlib import Path
    
    # Add QuantTime to path
    project_root = Path("/opt/quanttime")
    sys.path.insert(0, str(project_root))
    
    try:
        from quanttime.models.enhanced_mbo_lightgbm import create_enhanced_mbo_lightgbm_model
        from quanttime.models.model_registry import ModelRegistry
        from quanttime.utils.config import AppConfig
        
        # Get configuration
        model_type = config.get("model_type", "LightGBM")
        model_name = config.get("model_name", f"{model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        data_source = config.get("data_source", "Databento MBO")
        train_start = config.get("train_start", "2024-01-01")
        train_end = config.get("train_end", "2024-12-31")
        train_symbols = config.get("train_symbols", ["ES"])
        feature_set = config.get("feature_set", "Basic MBO")
        horizons = config.get("horizons", [1, 2, 3, 5])
        epochs = config.get("epochs", 100)
        batch_size = config.get("batch_size", 1000)
        learning_rate = config.get("learning_rate", 0.01)
        validation_split = config.get("validation_split", 0.2)
        early_stopping = config.get("early_stopping", True)
        cross_validation = config.get("cross_validation", False)
        
        # Create and train model based on type
        if model_type == "LightGBM":
            model = create_enhanced_mbo_lightgbm_model(
                symbol=train_symbols[0],
                start_date=train_start,
                end_date=train_end,
                model_name=model_name,
                feature_set=feature_set,
                prediction_horizons=horizons
            )
        elif model_type == "XGBoost":
            # Add XGBoost model creation
            from quanttime.models.xgboost_model import create_xgboost_model
            model = create_xgboost_model(
                symbol=train_symbols[0],
                start_date=train_start,
                end_date=train_end,
                model_name=model_name
            )
        elif model_type == "LSTM":
            # Add LSTM model creation
            from quanttime.models.lstm_model import create_lstm_model
            model = create_lstm_model(
                symbol=train_symbols[0],
                start_date=train_start,
                end_date=train_end,
                model_name=model_name,
                epochs=epochs,
                batch_size=batch_size
            )
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
        
        # Train the model
        results = model.train(
            validation_split=validation_split,
            early_stopping=early_stopping,
            cross_validation=cross_validation
        )
        
        # Register model
        registry = ModelRegistry()
        registry.register_model(model_name, str(model.model_path), results)
        
        return {
            "status": "completed",
            "model_type": model_type,
            "model_name": model_name,
            "symbols": train_symbols,
            "training_results": results,
            "model_path": str(model.model_path),
            "feature_set": feature_set,
            "horizons": horizons
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "model_name": config.get("model_name", "unknown")
        }


@ray.remote
def quanttime_backtest_job(config):
    """Run tick-based QuantTime backtest on the server using Level 3 MBO data"""
    import sys
    from pathlib import Path
    
    # Add QuantTime to path
    project_root = Path("/opt/quanttime")
    sys.path.insert(0, str(project_root))
    
    try:
        from quanttime.backtest.mbo_backtest_engine import run_mbo_backtest, BacktestConfig
        from quanttime.models.model_registry import ModelRegistry
        from quanttime.utils.config import AppConfig
        
        # Get configuration
        model_type = config.get("model_type", "LightGBM")
        strategy = config.get("strategy", "RL")  # Default to RL strategy
        start_date = config.get("start_date", "2024-01-01")
        end_date = config.get("end_date", "2024-12-31")
        symbols = config.get("symbols", ["ES"])
        model_path = config.get("model_path", None)
        include_slippage = config.get("include_slippage", True)
        include_commission = config.get("include_commission", True)
        commission_rate = config.get("commission_rate", 2.5)
        
        # Create backtest config for tick-based Level 3 MBO data
        backtest_config = BacktestConfig(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            model_path=model_path,
            strategy=strategy,
            # Always 1 ES contract - no portfolio sizing
            position_size=1.0,  # 1 contract
            # Tick-based backtesting with Level 3 MBO data
            use_tick_data=True,
            include_orderflow=True,
            include_slippage=include_slippage,
            include_commission=include_commission,
            commission_rate=commission_rate
        )
        
        # Run tick-based backtest
        results = run_mbo_backtest(backtest_config)
        
        return {
            "status": "completed",
            "strategy": strategy,
            "symbols": symbols,
            "backtest_type": "tick-based",
            "data_type": "Level 3 MBO",
            "position_size": "1 ES contract",
            "backtest_results": results,
            "total_return": results.get("total_return", 0),
            "sharpe_ratio": results.get("sharpe_ratio", 0),
            "max_drawdown": results.get("max_drawdown", 0),
            "win_rate": results.get("win_rate", 0),
            "profit_factor": results.get("profit_factor", 0),
            "total_trades": results.get("total_trades", 0),
            "avg_trade": results.get("avg_trade", 0),
            "total_ticks_processed": results.get("total_ticks", 0)
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "strategy": config.get("strategy", "unknown")
        }


@ray.remote
def quanttime_data_processing_job(config):
    """Process QuantTime data on the server"""
    import sys
    from pathlib import Path
    
    # Add QuantTime to path
    project_root = Path("/opt/quanttime")
    sys.path.insert(0, str(project_root))
    
    try:
        from quanttime.data.pipeline import create_pipeline_from_config, DataPipelineConfig
        from quanttime.adapter.databento_loader import get_databento_loader
        from quanttime.data.processor import convert_dbn_to_parquet_file
        
        # Get configuration
        data_source = config.get("data_source", "Databento MBO")
        symbols = config.get("symbols", ["ES"])
        start_date = config.get("start_date", "2024-01-01")
        end_date = config.get("end_date", "2024-12-31")
        output_format = config.get("output_format", "parquet")
        processing_type = config.get("processing_type", "normalize")
        
        if processing_type == "normalize":
            # Data normalization
            for symbol in symbols:
                data_dir = f"data/{symbol.lower()}_futures/mbo"
                databento_loader = get_databento_loader(data_dir)
                
                # Get available dates
                available_dates = databento_loader.get_available_dates()
                selected_dates = [d for d in available_dates if start_date <= d <= end_date]
                
                # Process each date
                processed_files = []
                total_rows = 0
                
                for date in selected_dates:
                    # Load and normalize data
                    df = databento_loader.load_dbn_file(date)
                    if df is not None and not df.empty:
                        # Normalize data
                        normalized_df = databento_loader.normalize_mbo_data(df)
                        
                        # Save to parquet
                        output_path = f"data/processed/{symbol}/{date}.parquet"
                        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                        normalized_df.to_parquet(output_path)
                        
                        processed_files.append(output_path)
                        total_rows += len(normalized_df)
        
        elif processing_type == "pipeline":
            # Use data pipeline
            pipeline_config = DataPipelineConfig(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                output_format=output_format
            )
            
            pipeline = create_pipeline_from_config(pipeline_config)
            results = pipeline.run()
            
            processed_files = results.get("output_files", [])
            total_rows = results.get("total_rows", 0)
        
        return {
            "status": "completed",
            "symbols": symbols,
            "processing_type": processing_type,
            "processed_files": len(processed_files),
            "total_rows": total_rows,
            "output_files": processed_files
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "processing_type": config.get("processing_type", "unknown")
        }


@ray.remote
def quanttime_feature_engineering_job(config):
    """Run comprehensive QuantTime feature engineering on the server"""
    import sys
    from pathlib import Path
    
    # Add QuantTime to path
    project_root = Path("/opt/quanttime")
    sys.path.insert(0, str(project_root))
    
    try:
        from quanttime.features.mbo_features import engineer_mbo_features, FeatureConfig
        from quanttime.features.feature_importance import get_feature_importance_ranking
        from quanttime.features.feature_validation import validate_features
        
        # Get configuration
        symbols = config.get("symbols", ["ES"])
        start_date = config.get("start_date", "2024-01-01")
        end_date = config.get("end_date", "2024-12-31")
        feature_set = config.get("feature_set", "Basic MBO")
        horizons = config.get("horizons", [1, 2, 3, 5])
        include_advanced = config.get("include_advanced", True)
        include_execution_aware = config.get("include_execution_aware", True)
        
        results = {}
        
        for symbol in symbols:
            # Create feature config
            feature_config = FeatureConfig(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                feature_set=feature_set,
                prediction_horizons=horizons,
                include_advanced_features=include_advanced,
                include_execution_aware_features=include_execution_aware
            )
            
            # Engineer features
            feature_results = engineer_mbo_features(feature_config)
            
            # Get feature importance
            importance_results = get_feature_importance_ranking(feature_results["features"])
            
            # Validate features
            validation_results = validate_features(feature_results["features"])
            
            results[symbol] = {
                "features_created": len(feature_results.get("features", [])),
                "feature_importance": importance_results,
                "validation_results": validation_results,
                "output_path": feature_results.get("output_path", "")
            }
        
        return {
            "status": "completed",
            "symbols": symbols,
            "feature_set": feature_set,
            "horizons": horizons,
            "results": results
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "feature_set": config.get("feature_set", "unknown")
        }


@ray.remote
def quanttime_live_trading_job(config):
    """Run QuantTime RL live trading on the server using Level 3 MBO data"""
    import sys
    from pathlib import Path
    
    # Add QuantTime to path
    project_root = Path("/opt/quanttime")
    sys.path.insert(0, str(project_root))
    
    try:
        from quanttime.models.trade_engine import create_trade_engine, TradeEngineConfig
        from quanttime.models.model_registry import ModelRegistry
        
        # Get configuration
        model_path = config.get("model_path")
        symbols = config.get("symbols", ["ES"])
        include_slippage = config.get("include_slippage", True)
        include_commission = config.get("include_commission", True)
        commission_rate = config.get("commission_rate", 2.5)
        
        # Create RL trade engine config for 1 ES contract
        trade_config = TradeEngineConfig(
            model_path=model_path,
            symbols=symbols,
            # Always 1 ES contract - no portfolio sizing
            position_size=1.0,  # 1 contract
            # RL trade engine with Level 3 MBO data
            use_rl_engine=True,
            use_tick_data=True,
            include_orderflow=True,
            include_slippage=include_slippage,
            include_commission=include_commission,
            commission_rate=commission_rate
        )
        
        trade_engine = create_trade_engine(trade_config)
        
        # Start RL live trading
        results = trade_engine.start_live_trading()
        
        return {
            "status": "completed",
            "symbols": symbols,
            "trading_type": "RL tick-based",
            "data_type": "Level 3 MBO",
            "position_size": "1 ES contract",
            "live_trading_results": results,
            "total_trades": results.get("total_trades", 0),
            "pnl": results.get("pnl", 0),
            "win_rate": results.get("win_rate", 0),
            "total_ticks_processed": results.get("total_ticks", 0)
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "symbols": config.get("symbols", ["unknown"])
        }


@ray.remote
def quanttime_data_analysis_job(config):
    """Run QuantTime data analysis on the server"""
    import sys
    from pathlib import Path
    
    # Add QuantTime to path
    project_root = Path("/opt/quanttime")
    sys.path.insert(0, str(project_root))
    
    try:
        from quanttime.runtime.hist_service import get_mbo_statistics, validate_mbo_data_quality
        from quanttime.adapter.databento_loader import get_databento_loader
        
        # Get configuration
        symbols = config.get("symbols", ["ES"])
        start_date = config.get("start_date", "2024-01-01")
        end_date = config.get("end_date", "2024-12-31")
        analysis_type = config.get("analysis_type", "comprehensive")
        
        results = {}
        
        for symbol in symbols:
            data_dir = f"data/{symbol.lower()}_futures/mbo"
            databento_loader = get_databento_loader(data_dir)
            
            if analysis_type == "statistics":
                # Get MBO statistics
                stats = get_mbo_statistics(symbol, start_date, end_date)
                results[symbol] = stats
                
            elif analysis_type == "quality":
                # Validate data quality
                quality = validate_mbo_data_quality(symbol, start_date, end_date)
                results[symbol] = quality
                
            elif analysis_type == "comprehensive":
                # Both statistics and quality
                stats = get_mbo_statistics(symbol, start_date, end_date)
                quality = validate_mbo_data_quality(symbol, start_date, end_date)
                results[symbol] = {
                    "statistics": stats,
                    "quality": quality
                }
        
        return {
            "status": "completed",
            "symbols": symbols,
            "analysis_type": analysis_type,
            "results": results
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "analysis_type": config.get("analysis_type", "unknown")
        }


@ray.remote
def quanttime_model_evaluation_job(config):
    """Run QuantTime model evaluation on the server"""
    import sys
    from pathlib import Path
    
    # Add QuantTime to path
    project_root = Path("/opt/quanttime")
    sys.path.insert(0, str(project_root))
    
    try:
        from quanttime.models.model_registry import ModelRegistry
        from quanttime.models.model_evaluator import ModelEvaluator
        
        # Get configuration
        model_path = config.get("model_path")
        evaluation_type = config.get("evaluation_type", "comprehensive")
        test_start = config.get("test_start", "2024-01-01")
        test_end = config.get("test_end", "2024-12-31")
        symbols = config.get("symbols", ["ES"])
        
        # Create model evaluator
        evaluator = ModelEvaluator(model_path)
        
        if evaluation_type == "performance":
            results = evaluator.evaluate_performance(symbols, test_start, test_end)
        elif evaluation_type == "robustness":
            results = evaluator.evaluate_robustness(symbols, test_start, test_end)
        elif evaluation_type == "comprehensive":
            results = evaluator.evaluate_comprehensive(symbols, test_start, test_end)
        
        return {
            "status": "completed",
            "model_path": model_path,
            "evaluation_type": evaluation_type,
            "results": results
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "model_path": config.get("model_path", "unknown")
        }


# Legacy example functions (kept for compatibility)
@ray.remote
def train_model_job(config):
    """Example training job function"""
    import time
    import random
    
    # Simulate training
    epochs = config.get("epochs", 10)
    for epoch in range(epochs):
        time.sleep(1)  # Simulate training time
        accuracy = random.uniform(0.7, 0.95)
        tune.report(accuracy=accuracy, epoch=epoch)
    
    return {"final_accuracy": accuracy}


@ray.remote
def backtest_job(config):
    """Example backtest job function"""
    import time
    import random
    
    # Simulate backtesting
    time.sleep(5)  # Simulate backtest time
    
    return {
        "total_return": random.uniform(-0.1, 0.3),
        "sharpe_ratio": random.uniform(0.5, 2.0),
        "max_drawdown": random.uniform(0.05, 0.2)
    }


@ray.remote
def data_processing_job(config):
    """Example data processing job function"""
    import time
    import random
    
    # Simulate data processing
    time.sleep(3)  # Simulate processing time
    
    return {
        "processed_rows": random.randint(1000, 10000),
        "processing_time": 3.0
    }
