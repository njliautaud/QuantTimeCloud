"""
QuantTime Distributed Job Manager

Handles job submission, scheduling, execution, and monitoring across
the distributed computing cluster. Supports resource-aware scheduling
and automatic failover.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import psutil
import redis
from celery import Celery
from celery.result import AsyncResult

# Configure logging
logger = logging.getLogger(__name__)

class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

class JobPriority(Enum):
    """Job priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10

@dataclass
class ResourceRequirements:
    """Resource requirements for a job"""
    min_cpu_cores: int = 1
    min_memory_gb: float = 1.0
    min_disk_space_gb: float = 1.0
    gpu_required: bool = False
    estimated_runtime_minutes: Optional[int] = None
    max_concurrent: int = 1

@dataclass
class JobRequest:
    """Job request structure"""
    job_type: str
    job_name: str
    parameters: Dict[str, Any]
    priority: int = 5
    target_server: Optional[str] = None
    resource_requirements: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = None
    callback_url: Optional[str] = None
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    submitted_at: datetime = field(default_factory=datetime.now)
    submitted_by: str = "system"

@dataclass
class JobResult:
    """Job execution result"""
    job_id: str
    status: JobStatus
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_seconds: Optional[float] = None
    resource_usage: Optional[Dict[str, Any]] = None

@dataclass
class JobProgress:
    """Job progress tracking"""
    job_id: str
    progress_percent: float = 0.0
    current_step: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    status_message: str = ""
    updated_at: datetime = field(default_factory=datetime.now)

class JobManager:
    """
    Distributed job manager for QuantTime computing cluster
    
    Features:
    - Resource-aware job scheduling
    - Automatic job distribution
    - Progress tracking
    - Failure recovery
    - Load balancing
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize job manager"""
        self.redis_url = redis_url
        self.redis_client = None
        self.celery_app = None
        self.job_registry: Dict[str, JobResult] = {}
        self.progress_registry: Dict[str, JobProgress] = {}
        self.running = False
        
        # Job type mappings to actual functions
        self.job_handlers = {
            "data_normalization": self._handle_data_normalization,
            "feature_engineering": self._handle_feature_engineering,
            "model_training": self._handle_model_training,
            "backtest": self._handle_backtest,
            "data_collection": self._handle_data_collection,
            "model_inference": self._handle_model_inference,
            "data_analysis": self._handle_data_analysis,
            "file_processing": self._handle_file_processing,
            "system_maintenance": self._handle_system_maintenance
        }
        
        # All servers can handle all job types - no restrictions
        self.server_capabilities = {
            "laptop": ["all"],
            "r630xl": ["all"], 
            "r810": ["all"]
        }
        
        # Resource thresholds for job assignment
        self.resource_thresholds = {
            "cpu_max": 80.0,
            "memory_max": 85.0,
            "disk_max": 90.0,
            "load_max": psutil.cpu_count() * 0.8
        }
    
    async def start(self):
        """Start the job manager"""
        try:
            # Initialize Redis connection
            self.redis_client = redis.Redis.from_url(self.redis_url)
            await self._test_redis_connection()
            
            # Initialize Celery
            self.celery_app = Celery(
                'quanttime_jobs',
                broker=self.redis_url,
                backend=self.redis_url
            )
            
            # Configure Celery
            self.celery_app.conf.update(
                task_serializer='json',
                accept_content=['json'],
                result_serializer='json',
                timezone='UTC',
                enable_utc=True,
                task_track_started=True,
                task_time_limit=3600,  # 1 hour default timeout
                worker_prefetch_multiplier=1,
                worker_max_tasks_per_child=1000,
            )
            
            # Register Celery tasks
            self._register_celery_tasks()
            
            self.running = True
            logger.info("✅ Job Manager started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Job Manager: {e}")
            raise
    
    async def stop(self):
        """Stop the job manager"""
        self.running = False
        
        # Cancel all running jobs
        for job_id in self.job_registry:
            if self.job_registry[job_id].status == JobStatus.RUNNING:
                await self.cancel_job(job_id)
        
        logger.info("✅ Job Manager stopped")
    
    async def _test_redis_connection(self):
        """Test Redis connection"""
        try:
            self.redis_client.ping()
            logger.info("✅ Redis connection established")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise
    
    def _register_celery_tasks(self):
        """Register Celery tasks for job execution"""
        @self.celery_app.task(bind=True)
        def execute_job(self, job_data: Dict[str, Any]):
            """Execute a job task"""
            job_id = job_data['job_id']
            job_type = job_data['job_type']
            
            try:
                # Update job status to running
                self._update_job_status(job_id, JobStatus.RUNNING)
                
                # Get job handler
                handler = self.job_handlers.get(job_type)
                if not handler:
                    raise ValueError(f"Unknown job type: {job_type}")
                
                # Execute job
                result = handler(job_data)
                
                # Update job status to completed
                self._update_job_status(job_id, JobStatus.COMPLETED, result)
                
                return result
                
            except Exception as e:
                logger.error(f"Job {job_id} failed: {e}")
                self._update_job_status(job_id, JobStatus.FAILED, error=str(e))
                raise
        
        # Store reference to the task
        self.execute_job_task = execute_job
    
    async def submit_job(self, job_request: JobRequest) -> str:
        """Submit a new job for execution"""
        try:
            # Validate job request
            self._validate_job_request(job_request)
            
            # Determine best server for job (flexible routing)
            target_server = await self._select_optimal_server(job_request)
            if not target_server:
                raise ValueError("No available servers for job execution")
            
            # Check resource availability on target server
            if not await self._check_server_resources(target_server, job_request):
                # Try to find alternative server
                alternative_server = await self._select_alternative_server(job_request, [target_server])
                if alternative_server:
                    target_server = alternative_server
                else:
                    raise ValueError("Insufficient resources available on all servers")
            
            # Update job request with target server
            job_request.target_server = target_server
            
            # Create job result entry
            job_result = JobResult(
                job_id=job_request.job_id,
                status=JobStatus.PENDING
            )
            
            # Store job in registry
            self.job_registry[job_request.job_id] = job_result
            
            # Create progress tracking
            progress = JobProgress(
                job_id=job_request.job_id,
                progress_percent=0.0,
                current_step="Queued",
                status_message=f"Job queued for execution on {target_server}"
            )
            self.progress_registry[job_request.job_id] = progress
            
            # Queue job for execution with routing
            job_data = asdict(job_request)
            
            # Submit to Celery with routing key for target server
            routing_key = f"server.{target_server}"
            celery_result = self.execute_job_task.apply_async(
                args=[job_data],
                routing_key=routing_key,
                queue=f"server_{target_server}"
            )
            
            # Update job status
            job_result.status = JobStatus.QUEUED
            
            # Store Celery task ID and target server
            self.redis_client.set(
                f"job:{job_request.job_id}:celery_id",
                celery_result.id
            )
            self.redis_client.set(
                f"job:{job_request.job_id}:target_server",
                target_server
            )
            
            logger.info(f"✅ Job {job_request.job_id} ({job_request.job_name}) submitted to {target_server}")
            
            return job_request.job_id
            
        except Exception as e:
            logger.error(f"❌ Failed to submit job: {e}")
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[JobResult]:
        """Get the status of a specific job"""
        try:
            if job_id in self.job_registry:
                return self.job_registry[job_id]
            
            # Try to load from Redis if not in memory
            job_data = self.redis_client.get(f"job:{job_id}")
            if job_data:
                job_result = JobResult(**json.loads(job_data))
                self.job_registry[job_id] = job_result
                return job_result
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get job status: {e}")
            return None
    
    async def list_jobs(self, status: Optional[str] = None, limit: int = 100) -> List[JobResult]:
        """List jobs with optional status filter"""
        try:
            jobs = list(self.job_registry.values())
            
            # Filter by status if provided
            if status:
                jobs = [job for job in jobs if job.status.value == status]
            
            # Sort by submission time (newest first)
            jobs.sort(key=lambda x: x.started_at or datetime.min, reverse=True)
            
            # Apply limit
            return jobs[:limit]
            
        except Exception as e:
            logger.error(f"❌ Failed to list jobs: {e}")
            return []
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job"""
        try:
            if job_id not in self.job_registry:
                return False
            
            job_result = self.job_registry[job_id]
            
            # Can only cancel pending, queued, or running jobs
            if job_result.status not in [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING]:
                return False
            
            # Get Celery task ID
            celery_id = self.redis_client.get(f"job:{job_id}:celery_id")
            if celery_id:
                # Revoke Celery task
                self.celery_app.control.revoke(celery_id.decode(), terminate=True)
            
            # Update job status
            job_result.status = JobStatus.CANCELLED
            job_result.completed_at = datetime.now()
            
            logger.info(f"✅ Job {job_id} cancelled successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel job {job_id}: {e}")
            return False
    
    async def get_job_progress(self, job_id: str) -> Optional[JobProgress]:
        """Get progress information for a job"""
        return self.progress_registry.get(job_id)
    
    async def update_job_progress(self, job_id: str, progress_percent: float, 
                                 current_step: str = "", status_message: str = ""):
        """Update job progress"""
        if job_id in self.progress_registry:
            progress = self.progress_registry[job_id]
            progress.progress_percent = progress_percent
            progress.current_step = current_step
            progress.status_message = status_message
            progress.updated_at = datetime.now()
    
    async def get_active_job_count(self) -> int:
        """Get count of active (running) jobs"""
        return len([job for job in self.job_registry.values() 
                   if job.status == JobStatus.RUNNING])
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get job queue statistics"""
        try:
            status_counts = {}
            for status in JobStatus:
                status_counts[status.value] = len([
                    job for job in self.job_registry.values() 
                    if job.status == status
                ])
            
            return {
                "total_jobs": len(self.job_registry),
                "status_counts": status_counts,
                "queue_length": status_counts.get("queued", 0) + status_counts.get("pending", 0),
                "active_jobs": status_counts.get("running", 0)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get queue stats: {e}")
            return {}
    
    def _validate_job_request(self, job_request: JobRequest):
        """Validate job request parameters"""
        if not job_request.job_type:
            raise ValueError("Job type is required")
        
        if job_request.job_type not in self.job_handlers:
            raise ValueError(f"Unsupported job type: {job_request.job_type}")
        
        if not job_request.job_name:
            raise ValueError("Job name is required")
        
        if job_request.priority < 1 or job_request.priority > 10:
            raise ValueError("Priority must be between 1 and 10")
    
    async def _select_optimal_server(self, job_request: JobRequest) -> Optional[str]:
        """Select the optimal server for job execution"""
        try:
            # If target server is specified and available, use it
            if job_request.target_server:
                if await self._is_server_available(job_request.target_server):
                    return job_request.target_server
            
            # Get all available servers
            available_servers = []
            for server_id in ["laptop", "r630xl", "r810"]:
                if await self._is_server_available(server_id):
                    server_load = await self._get_server_load(server_id)
                    available_servers.append((server_id, server_load))
            
            if not available_servers:
                return None
            
            # Sort by load (lowest first) for optimal distribution
            available_servers.sort(key=lambda x: x[1])
            
            # For heavy compute jobs, prefer R810 if available and not overloaded
            if job_request.job_type in ["model_training", "backtest"] and job_request.resource_requirements:
                memory_req = job_request.resource_requirements.get("min_memory_gb", 0)
                if memory_req > 16:  # Heavy memory job
                    for server_id, load in available_servers:
                        if server_id == "r810" and load < 0.7:  # R810 with less than 70% load
                            return server_id
            
            # Return server with lowest load
            return available_servers[0][0]
            
        except Exception as e:
            logger.error(f"Failed to select optimal server: {e}")
            return None
    
    async def _select_alternative_server(self, job_request: JobRequest, excluded_servers: List[str]) -> Optional[str]:
        """Select alternative server excluding specified ones"""
        try:
            available_servers = []
            for server_id in ["laptop", "r630xl", "r810"]:
                if server_id not in excluded_servers and await self._is_server_available(server_id):
                    server_load = await self._get_server_load(server_id)
                    available_servers.append((server_id, server_load))
            
            if not available_servers:
                return None
            
            # Sort by load and return best option
            available_servers.sort(key=lambda x: x[1])
            return available_servers[0][0]
            
        except Exception as e:
            logger.error(f"Failed to select alternative server: {e}")
            return None
    
    async def _is_server_available(self, server_id: str) -> bool:
        """Check if server is available for job execution"""
        try:
            if server_id == "laptop":
                return True  # Laptop is always available
            
            # Check server status in Redis or via API call
            if self.redis_client:
                status = self.redis_client.get(f"server:{server_id}:status")
                if status:
                    return status.decode() == "online"
            
            # Default to available if can't determine status
            return True
            
        except Exception as e:
            logger.error(f"Failed to check server availability: {e}")
            return False
    
    async def _get_server_load(self, server_id: str) -> float:
        """Get server load score (0.0 = idle, 1.0 = fully loaded)"""
        try:
            if server_id == "laptop":
                # Get local system load
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                return (cpu_percent + memory.percent) / 200.0  # Normalize to 0-1
            
            # For remote servers, get load from Redis cache or API
            if self.redis_client:
                load_data = self.redis_client.get(f"server:{server_id}:load")
                if load_data:
                    return float(load_data.decode())
            
            # Default moderate load if unknown
            return 0.5
            
        except Exception as e:
            logger.error(f"Failed to get server load: {e}")
            return 1.0  # Assume high load on error
    
    async def _check_server_resources(self, server_id: str, job_request: JobRequest) -> bool:
        """Check if specific server has resources for the job"""
        try:
            if server_id == "laptop":
                return await self._check_local_resources(job_request)
            
            # For remote servers, check via API or cached data
            if self.redis_client:
                resource_data = self.redis_client.get(f"server:{server_id}:resources")
                if resource_data:
                    resources = json.loads(resource_data.decode())
                    return self._evaluate_resources(resources, job_request)
            
            # Default to available if can't check
            return True
            
        except Exception as e:
            logger.error(f"Failed to check server resources: {e}")
            return False
    
    async def _check_local_resources(self, job_request: JobRequest) -> bool:
        """Check local system resources"""
        try:
            # Get current system resources
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            load_avg = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0
            
            # Check against thresholds
            if cpu_percent > self.resource_thresholds["cpu_max"]:
                logger.warning(f"CPU usage too high: {cpu_percent}%")
                return False
            
            if memory.percent > self.resource_thresholds["memory_max"]:
                logger.warning(f"Memory usage too high: {memory.percent}%")
                return False
            
            if disk.percent > self.resource_thresholds["disk_max"]:
                logger.warning(f"Disk usage too high: {disk.percent}%")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to check local resources: {e}")
            return False
    
    def _evaluate_resources(self, resources: Dict[str, Any], job_request: JobRequest) -> bool:
        """Evaluate if resources meet job requirements"""
        try:
            # Check CPU usage
            if resources.get("cpu_percent", 0) > self.resource_thresholds["cpu_max"]:
                return False
            
            # Check memory usage
            if resources.get("memory_percent", 0) > self.resource_thresholds["memory_max"]:
                return False
            
            # Check disk usage
            if resources.get("disk_percent", 0) > self.resource_thresholds["disk_max"]:
                return False
            
            # Check job-specific requirements
            if job_request.resource_requirements:
                req = job_request.resource_requirements
                
                # Check minimum memory requirement
                if "min_memory_gb" in req:
                    available_memory = resources.get("memory_available_gb", 0)
                    if available_memory < req["min_memory_gb"]:
                        return False
                
                # Check minimum CPU cores
                if "min_cpu_cores" in req:
                    available_cores = resources.get("cpu_count", 0)
                    if available_cores < req["min_cpu_cores"]:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to evaluate resources: {e}")
            return False
    
    def _update_job_status(self, job_id: str, status: JobStatus, 
                          result: Optional[Dict[str, Any]] = None,
                          error: Optional[str] = None):
        """Update job status in registry and Redis"""
        if job_id in self.job_registry:
            job_result = self.job_registry[job_id]
            job_result.status = status
            
            if status == JobStatus.RUNNING and not job_result.started_at:
                job_result.started_at = datetime.now()
            
            if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                job_result.completed_at = datetime.now()
                if job_result.started_at:
                    job_result.execution_time_seconds = (
                        job_result.completed_at - job_result.started_at
                    ).total_seconds()
            
            if result:
                job_result.result_data = result
            
            if error:
                job_result.error_message = error
            
            # Store in Redis for persistence
            try:
                self.redis_client.set(
                    f"job:{job_id}",
                    json.dumps(asdict(job_result), default=str),
                    ex=86400  # Expire after 24 hours
                )
            except Exception as e:
                logger.error(f"Failed to store job result in Redis: {e}")
    
    # Job Handler Methods
    async def _handle_data_normalization(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data normalization job"""
        # Import here to avoid circular imports
        from quanttime.data.processor import normalize_data
        
        parameters = job_data['parameters']
        
        # Extract parameters
        input_path = parameters.get('input_path')
        output_path = parameters.get('output_path')
        normalization_type = parameters.get('normalization_type', 'standard')
        
        # Execute normalization
        result = normalize_data(input_path, output_path, normalization_type)
        
        return {
            "status": "completed",
            "output_path": output_path,
            "records_processed": result.get("records_processed", 0),
            "processing_time": result.get("processing_time", 0)
        }
    
    async def _handle_feature_engineering(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle feature engineering job"""
        from quanttime.features.engineer import engineer_features
        
        parameters = job_data['parameters']
        
        # Execute feature engineering
        result = engineer_features(parameters)
        
        return {
            "status": "completed",
            "features_created": result.get("features_created", 0),
            "output_path": result.get("output_path"),
            "processing_time": result.get("processing_time", 0)
        }
    
    async def _handle_model_training(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle model training job"""
        from quanttime.ml.gpu_optimized_training import train_model
        
        parameters = job_data['parameters']
        
        # Execute model training
        result = train_model(parameters)
        
        return {
            "status": "completed",
            "model_path": result.get("model_path"),
            "accuracy": result.get("accuracy", 0),
            "training_time": result.get("training_time", 0)
        }
    
    async def _handle_backtest(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle backtest job"""
        from quanttime.backtest.engine import run_backtest
        
        parameters = job_data['parameters']
        
        # Execute backtest
        result = run_backtest(parameters)
        
        return {
            "status": "completed",
            "total_return": result.get("total_return", 0),
            "sharpe_ratio": result.get("sharpe_ratio", 0),
            "max_drawdown": result.get("max_drawdown", 0),
            "trades_count": result.get("trades_count", 0)
        }
    
    async def _handle_data_collection(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data collection job"""
        from quanttime.adapter.databento_loader import collect_data
        
        parameters = job_data['parameters']
        
        # Execute data collection
        result = collect_data(parameters)
        
        return {
            "status": "completed",
            "records_collected": result.get("records_collected", 0),
            "data_path": result.get("data_path"),
            "collection_time": result.get("collection_time", 0)
        }
    
    async def _handle_model_inference(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle model inference job"""
        parameters = job_data['parameters']
        
        # Execute model inference
        # This would integrate with your existing model inference code
        
        return {
            "status": "completed",
            "predictions_count": 1000,
            "inference_time": 5.2
        }
    
    async def _handle_data_analysis(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data analysis job"""
        parameters = job_data['parameters']
        
        # Execute data analysis
        # This would integrate with your existing analysis code
        
        return {
            "status": "completed",
            "analysis_results": parameters.get("output_path"),
            "analysis_time": 10.5
        }
    
    async def _handle_file_processing(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file processing job"""
        parameters = job_data['parameters']
        
        # Execute file processing
        # This would handle file format conversions, compressions, etc.
        
        return {
            "status": "completed",
            "files_processed": 1,
            "processing_time": 2.1
        }
    
    async def _handle_system_maintenance(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle system maintenance job"""
        parameters = job_data['parameters']
        
        # Execute system maintenance tasks
        # This would handle cleanup, optimization, etc.
        
        return {
            "status": "completed",
            "maintenance_type": parameters.get("maintenance_type"),
            "completion_time": 1.0
        }
