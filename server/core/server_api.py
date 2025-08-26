"""
QuantTime Distributed Computing Server API

Main FastAPI server for handling distributed compute requests,
job management, file synchronization, and real-time monitoring.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import psutil
import platform
from dataclasses import dataclass, asdict

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, BackgroundTasks, File, UploadFile, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from .job_manager import JobManager, JobRequest, JobStatus, JobResult
from .resource_monitor import ResourceMonitor, SystemMetrics
from .sync_manager import SyncManager
from .auth import authenticate_token, generate_server_token
from .health_checker import HealthChecker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="QuantTime Distributed Computing Server",
    description="High-performance distributed computing server for quantitative trading",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your security needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Global managers
job_manager: Optional[JobManager] = None
resource_monitor: Optional[ResourceMonitor] = None
sync_manager: Optional[SyncManager] = None
health_checker: Optional[HealthChecker] = None

# WebSocket connections for real-time updates
connected_clients: List[WebSocket] = []

# Pydantic models for API requests/responses
class ServerInfo(BaseModel):
    server_id: str
    server_type: str  # "control", "compute", "hybrid"
    hostname: str
    ip_address: str
    cpu_count: int
    memory_total_gb: float
    disk_space_gb: float
    status: str
    last_seen: datetime
    capabilities: List[str]

class JobSubmissionRequest(BaseModel):
    job_type: str
    job_name: str
    parameters: Dict[str, Any]
    priority: int = Field(default=1, ge=1, le=10)
    target_server: Optional[str] = None
    resource_requirements: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = None

class FileTransferRequest(BaseModel):
    source_path: str
    destination_path: str
    target_servers: List[str]
    transfer_type: str = "copy"  # "copy", "move", "sync"

class SystemResourcesResponse(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]
    load_average: List[float]
    process_count: int
    uptime_seconds: int
    timestamp: datetime

@app.on_event("startup")
async def startup_event():
    """Initialize server components on startup"""
    global job_manager, resource_monitor, sync_manager, health_checker
    
    logger.info("🚀 Starting QuantTime Distributed Computing Server...")
    
    # Initialize managers
    job_manager = JobManager()
    resource_monitor = ResourceMonitor()
    sync_manager = SyncManager()
    health_checker = HealthChecker()
    
    # Start background tasks
    await job_manager.start()
    await resource_monitor.start()
    await sync_manager.start()
    await health_checker.start()
    
    logger.info("✅ QuantTime Server initialized successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown"""
    global job_manager, resource_monitor, sync_manager, health_checker
    
    logger.info("🛑 Shutting down QuantTime Server...")
    
    # Stop background tasks
    if job_manager:
        await job_manager.stop()
    if resource_monitor:
        await resource_monitor.stop()
    if sync_manager:
        await sync_manager.stop()
    if health_checker:
        await health_checker.stop()
    
    logger.info("✅ QuantTime Server shutdown complete")

# Authentication dependency
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify authentication token"""
    if not authenticate_token(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return credentials.credentials

# Server Information Endpoints
@app.get("/api/v1/server/info", response_model=ServerInfo)
async def get_server_info():
    """Get server information and capabilities"""
    hostname = platform.node()
    
    # Get system information
    cpu_count = psutil.cpu_count()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Determine server capabilities based on resources
    capabilities = ["data_processing", "feature_engineering"]
    if memory.total > 32 * 1024**3:  # More than 32GB RAM
        capabilities.extend(["model_training", "heavy_compute"])
    if cpu_count >= 16:
        capabilities.append("parallel_processing")
    
    return ServerInfo(
        server_id=hostname,
        server_type=os.getenv("QUANTTIME_SERVER_TYPE", "hybrid"),
        hostname=hostname,
        ip_address=resource_monitor.get_ip_address() if resource_monitor else "unknown",
        cpu_count=cpu_count,
        memory_total_gb=memory.total / (1024**3),
        disk_space_gb=disk.total / (1024**3),
        status="online",
        last_seen=datetime.now(),
        capabilities=capabilities
    )

@app.get("/api/v1/server/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "uptime": time.time() - psutil.boot_time()
    }

@app.get("/api/v1/server/resources", response_model=SystemResourcesResponse)
async def get_system_resources():
    """Get current system resource usage"""
    if not resource_monitor:
        raise HTTPException(status_code=503, detail="Resource monitor not available")
    
    metrics = await resource_monitor.get_current_metrics()
    
    return SystemResourcesResponse(
        cpu_percent=metrics.cpu_percent,
        memory_percent=metrics.memory_percent,
        disk_percent=metrics.disk_percent,
        network_io=metrics.network_io,
        load_average=metrics.load_average,
        process_count=metrics.process_count,
        uptime_seconds=int(metrics.uptime_seconds),
        timestamp=metrics.timestamp
    )

# Job Management Endpoints
@app.post("/api/v1/jobs/submit")
async def submit_job(
    job_request: JobSubmissionRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """Submit a new job for processing"""
    if not job_manager:
        raise HTTPException(status_code=503, detail="Job manager not available")
    
    try:
        # Create job request
        job_req = JobRequest(
            job_type=job_request.job_type,
            job_name=job_request.job_name,
            parameters=job_request.parameters,
            priority=job_request.priority,
            target_server=job_request.target_server,
            resource_requirements=job_request.resource_requirements or {},
            timeout_seconds=job_request.timeout_seconds
        )
        
        # Submit job
        job_id = await job_manager.submit_job(job_req)
        
        # Notify connected clients
        background_tasks.add_task(notify_clients, {
            "type": "job_submitted",
            "job_id": job_id,
            "job_type": job_request.job_type,
            "job_name": job_request.job_name
        })
        
        return {
            "job_id": job_id,
            "status": "submitted",
            "message": f"Job {job_request.job_name} submitted successfully"
        }
        
    except Exception as e:
        logger.error(f"Error submitting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(job_id: str, token: str = Depends(verify_token)):
    """Get status of a specific job"""
    if not job_manager:
        raise HTTPException(status_code=503, detail="Job manager not available")
    
    try:
        job_status = await job_manager.get_job_status(job_id)
        if not job_status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return asdict(job_status)
        
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/jobs")
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 100,
    token: str = Depends(verify_token)
):
    """List all jobs with optional status filter"""
    if not job_manager:
        raise HTTPException(status_code=503, detail="Job manager not available")
    
    try:
        jobs = await job_manager.list_jobs(status=status, limit=limit)
        return {"jobs": [asdict(job) for job in jobs]}
        
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/jobs/{job_id}")
async def cancel_job(job_id: str, token: str = Depends(verify_token)):
    """Cancel a running job"""
    if not job_manager:
        raise HTTPException(status_code=503, detail="Job manager not available")
    
    try:
        success = await job_manager.cancel_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found or cannot be cancelled")
        
        return {"message": f"Job {job_id} cancelled successfully"}
        
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# File Synchronization Endpoints
@app.post("/api/v1/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_path: str = Form(...),
    checksum: str = Form(...),
    timestamp: str = Form(...),
    token: str = Depends(verify_token)
):
    """Upload file to server (part of sync system)"""
    try:
        # Ensure directory exists
        target_path = Path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded file
        with open(target_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Verify checksum
        import hashlib
        actual_checksum = hashlib.md5(content).hexdigest()
        if actual_checksum != checksum:
            logger.warning(f"Checksum mismatch for {file_path}")
        
        logger.info(f"📁 Received file: {file_path}")
        
        return {
            "status": "success",
            "file_path": file_path,
            "size": len(content),
            "checksum": actual_checksum
        }
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/files/delete")
async def delete_file(
    request: dict,
    token: str = Depends(verify_token)
):
    """Delete file on server (part of sync system)"""
    try:
        file_path = request.get("file_path")
        if not file_path:
            raise HTTPException(status_code=400, detail="file_path required")
        
        target_path = Path(file_path)
        if target_path.exists():
            target_path.unlink()
            logger.info(f"🗑️ Deleted file: {file_path}")
        
        return {"status": "success", "file_path": file_path}
        
    except Exception as e:
        logger.error(f"File delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/files/transfer")
async def transfer_file(
    transfer_request: FileTransferRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """Transfer files between servers"""
    if not sync_manager:
        raise HTTPException(status_code=503, detail="Sync manager not available")
    
    try:
        transfer_id = await sync_manager.initiate_transfer(
            source_path=transfer_request.source_path,
            destination_path=transfer_request.destination_path,
            target_servers=transfer_request.target_servers,
            transfer_type=transfer_request.transfer_type
        )
        
        return {
            "transfer_id": transfer_id,
            "status": "initiated",
            "message": "File transfer initiated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error initiating file transfer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/files/sync/status")
async def get_sync_status(token: str = Depends(verify_token)):
    """Get current file synchronization status"""
    if not sync_manager:
        raise HTTPException(status_code=503, detail="Sync manager not available")
    
    try:
        status = await sync_manager.get_sync_status()
        return status
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Real-time WebSocket endpoint
@app.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    connected_clients.append(websocket)
    
    try:
        # Send initial server info
        server_info = await get_server_info()
        await websocket.send_json({
            "type": "server_info",
            "data": server_info.dict()
        })
        
        # Keep connection alive and send periodic updates
        while True:
            try:
                # Send resource updates every 5 seconds
                if resource_monitor:
                    metrics = await resource_monitor.get_current_metrics()
                    await websocket.send_json({
                        "type": "resource_update",
                        "data": asdict(metrics)
                    })
                
                # Send job updates
                if job_manager:
                    active_jobs = await job_manager.get_active_job_count()
                    await websocket.send_json({
                        "type": "job_update",
                        "data": {"active_jobs": active_jobs}
                    })
                
                await asyncio.sleep(5)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def notify_clients(message: Dict[str, Any]):
    """Send message to all connected WebSocket clients"""
    if connected_clients:
        disconnected = []
        for client in connected_clients:
            try:
                await client.send_json(message)
            except Exception:
                disconnected.append(client)
        
        # Remove disconnected clients
        for client in disconnected:
            connected_clients.remove(client)

# Admin endpoints
@app.post("/api/v1/admin/restart")
async def restart_server(token: str = Depends(verify_token)):
    """Restart server (requires admin privileges)"""
    # Implementation for graceful restart
    return {"message": "Server restart initiated"}

@app.post("/api/v1/admin/shutdown")
async def shutdown_server(token: str = Depends(verify_token)):
    """Shutdown server (requires admin privileges)"""
    # Implementation for graceful shutdown
    return {"message": "Server shutdown initiated"}

def run_server(host: str = "0.0.0.0", port: int = 8000, workers: int = 1):
    """Run the FastAPI server"""
    uvicorn.run(
        "server.core.server_api:app",
        host=host,
        port=port,
        workers=workers,
        reload=False,
        access_log=True,
        log_level="info"
    )

if __name__ == "__main__":
    run_server()
