"""
QuantTime Resource Monitor

Real-time system resource monitoring for distributed computing cluster.
Tracks CPU, memory, disk, network, and custom metrics.
"""

import asyncio
import json
import logging
import platform
import socket
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import psutil
import redis

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    """System resource metrics"""
    # Basic metrics
    cpu_percent: float
    cpu_count: int
    cpu_freq_current: float
    memory_percent: float
    memory_total_gb: float
    memory_available_gb: float
    memory_used_gb: float
    disk_percent: float
    disk_total_gb: float
    disk_free_gb: float
    disk_used_gb: float
    
    # Network metrics
    network_io: Dict[str, int]
    network_connections: int
    
    # System metrics
    load_average: List[float]
    process_count: int
    uptime_seconds: int
    boot_time: datetime
    
    # Custom metrics
    temperature: Optional[Dict[str, float]] = None
    gpu_info: Optional[Dict[str, Any]] = None
    
    # Metadata
    hostname: str = ""
    ip_address: str = ""
    platform_info: str = ""
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class ProcessInfo:
    """Process information"""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    status: str
    username: str
    create_time: datetime

@dataclass
class DiskInfo:
    """Disk usage information"""
    device: str
    mountpoint: str
    total_gb: float
    used_gb: float
    free_gb: float
    percent: float
    fstype: str

@dataclass
class NetworkInfo:
    """Network interface information"""
    interface: str
    ip_address: str
    mac_address: str
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    is_up: bool

class ResourceMonitor:
    """
    Real-time system resource monitoring
    
    Features:
    - CPU, memory, disk, and network monitoring
    - Process tracking
    - Historical data retention
    - Alerting on resource thresholds
    - Performance metrics collection
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize resource monitor"""
        self.redis_url = redis_url
        self.redis_client = None
        self.running = False
        self.monitoring_interval = 5  # seconds
        self.history_retention_hours = 24
        
        # Alert thresholds
        self.alert_thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
            "load_average": psutil.cpu_count() * 0.8,
            "temperature": 75.0  # Celsius
        }
        
        # Metrics history
        self.metrics_history: List[SystemMetrics] = []
        self.max_history_size = int((self.history_retention_hours * 3600) / self.monitoring_interval)
        
        # Process tracking
        self.tracked_processes: Dict[int, ProcessInfo] = {}
        
        # Network baseline
        self.network_baseline: Dict[str, Dict[str, int]] = {}
        
        # GPU monitoring (if available)
        self.gpu_available = self._check_gpu_availability()
    
    async def start(self):
        """Start the resource monitor"""
        try:
            # Initialize Redis connection
            self.redis_client = redis.Redis.from_url(self.redis_url)
            self.redis_client.ping()
            
            # Initialize network baseline
            self._initialize_network_baseline()
            
            self.running = True
            
            # Start monitoring task
            asyncio.create_task(self._monitoring_loop())
            
            logger.info("✅ Resource Monitor started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Resource Monitor: {e}")
            raise
    
    async def stop(self):
        """Stop the resource monitor"""
        self.running = False
        logger.info("✅ Resource Monitor stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Collect current metrics
                metrics = await self.collect_metrics()
                
                # Store metrics
                await self._store_metrics(metrics)
                
                # Check for alerts
                await self._check_alerts(metrics)
                
                # Clean up old data
                await self._cleanup_old_data()
                
                # Wait for next collection
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def collect_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            cpu_freq_current = cpu_freq.current if cpu_freq else 0.0
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_total_gb = memory.total / (1024**3)
            memory_available_gb = memory.available / (1024**3)
            memory_used_gb = memory.used / (1024**3)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_total_gb = disk.total / (1024**3)
            disk_free_gb = disk.free / (1024**3)
            disk_used_gb = disk.used / (1024**3)
            
            # Network metrics
            network_io = self._get_network_io()
            network_connections = len(psutil.net_connections())
            
            # System metrics
            load_average = list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [0.0, 0.0, 0.0]
            process_count = len(psutil.pids())
            uptime_seconds = int(time.time() - psutil.boot_time())
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            
            # Temperature (if available)
            temperature = self._get_temperature()
            
            # GPU info (if available)
            gpu_info = self._get_gpu_info() if self.gpu_available else None
            
            # System info
            hostname = platform.node()
            ip_address = self.get_ip_address()
            platform_info = f"{platform.system()} {platform.release()}"
            
            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                cpu_freq_current=cpu_freq_current,
                memory_percent=memory.percent,
                memory_total_gb=memory_total_gb,
                memory_available_gb=memory_available_gb,
                memory_used_gb=memory_used_gb,
                disk_percent=disk.percent,
                disk_total_gb=disk_total_gb,
                disk_free_gb=disk_free_gb,
                disk_used_gb=disk_used_gb,
                network_io=network_io,
                network_connections=network_connections,
                load_average=load_average,
                process_count=process_count,
                uptime_seconds=uptime_seconds,
                boot_time=boot_time,
                temperature=temperature,
                gpu_info=gpu_info,
                hostname=hostname,
                ip_address=ip_address,
                platform_info=platform_info
            )
            
            # Add to history
            self.metrics_history.append(metrics)
            
            # Trim history if too long
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history.pop(0)
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Failed to collect metrics: {e}")
            raise
    
    async def get_current_metrics(self) -> SystemMetrics:
        """Get the most recent metrics"""
        if self.metrics_history:
            return self.metrics_history[-1]
        else:
            return await self.collect_metrics()
    
    async def get_historical_metrics(self, hours: int = 1) -> List[SystemMetrics]:
        """Get historical metrics for specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            metrics for metrics in self.metrics_history
            if metrics.timestamp >= cutoff_time
        ]
    
    async def get_process_info(self, limit: int = 10) -> List[ProcessInfo]:
        """Get information about running processes"""
        try:
            processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 
                                          'memory_info', 'status', 'username', 'create_time']):
                try:
                    pinfo = proc.info
                    process_info = ProcessInfo(
                        pid=pinfo['pid'],
                        name=pinfo['name'],
                        cpu_percent=pinfo['cpu_percent'] or 0.0,
                        memory_percent=pinfo['memory_percent'] or 0.0,
                        memory_mb=pinfo['memory_info'].rss / (1024**2) if pinfo['memory_info'] else 0.0,
                        status=pinfo['status'],
                        username=pinfo['username'] or "unknown",
                        create_time=datetime.fromtimestamp(pinfo['create_time'])
                    )
                    processes.append(process_info)
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            # Sort by CPU usage and return top processes
            processes.sort(key=lambda x: x.cpu_percent, reverse=True)
            return processes[:limit]
            
        except Exception as e:
            logger.error(f"❌ Failed to get process info: {e}")
            return []
    
    async def get_disk_info(self) -> List[DiskInfo]:
        """Get disk usage information for all mounted drives"""
        try:
            disks = []
            
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    
                    disk_info = DiskInfo(
                        device=partition.device,
                        mountpoint=partition.mountpoint,
                        total_gb=usage.total / (1024**3),
                        used_gb=usage.used / (1024**3),
                        free_gb=usage.free / (1024**3),
                        percent=(usage.used / usage.total) * 100 if usage.total > 0 else 0,
                        fstype=partition.fstype
                    )
                    disks.append(disk_info)
                    
                except (PermissionError, OSError):
                    continue
            
            return disks
            
        except Exception as e:
            logger.error(f"❌ Failed to get disk info: {e}")
            return []
    
    async def get_network_info(self) -> List[NetworkInfo]:
        """Get network interface information"""
        try:
            networks = []
            
            # Get network interfaces
            interfaces = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            io_counters = psutil.net_io_counters(pernic=True)
            
            for interface, addrs in interfaces.items():
                # Get IP address
                ip_address = ""
                mac_address = ""
                
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        ip_address = addr.address
                    elif addr.family == psutil.AF_LINK:
                        mac_address = addr.address
                
                # Get stats
                stat = stats.get(interface)
                io = io_counters.get(interface)
                
                if stat and io:
                    network_info = NetworkInfo(
                        interface=interface,
                        ip_address=ip_address,
                        mac_address=mac_address,
                        bytes_sent=io.bytes_sent,
                        bytes_recv=io.bytes_recv,
                        packets_sent=io.packets_sent,
                        packets_recv=io.packets_recv,
                        is_up=stat.isup
                    )
                    networks.append(network_info)
            
            return networks
            
        except Exception as e:
            logger.error(f"❌ Failed to get network info: {e}")
            return []
    
    def get_ip_address(self) -> str:
        """Get the primary IP address"""
        try:
            # Connect to a remote address to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def _get_network_io(self) -> Dict[str, int]:
        """Get network I/O statistics"""
        try:
            io_counters = psutil.net_io_counters()
            return {
                "bytes_sent": io_counters.bytes_sent,
                "bytes_recv": io_counters.bytes_recv,
                "packets_sent": io_counters.packets_sent,
                "packets_recv": io_counters.packets_recv
            }
        except Exception:
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_sent": 0,
                "packets_recv": 0
            }
    
    def _get_temperature(self) -> Optional[Dict[str, float]]:
        """Get system temperature (if available)"""
        try:
            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()
                if temps:
                    result = {}
                    for name, entries in temps.items():
                        for entry in entries:
                            if entry.current:
                                result[f"{name}_{entry.label or 'temp'}"] = entry.current
                    return result if result else None
            return None
        except Exception:
            return None
    
    def _get_gpu_info(self) -> Optional[Dict[str, Any]]:
        """Get GPU information (if available)"""
        try:
            # Try to get GPU info using nvidia-ml-py or similar
            # This is a placeholder - implement based on your GPU monitoring needs
            return None
        except Exception:
            return None
    
    def _check_gpu_availability(self) -> bool:
        """Check if GPU monitoring is available"""
        try:
            # Check for NVIDIA GPU
            import subprocess
            result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            return False
    
    def _initialize_network_baseline(self):
        """Initialize network baseline for rate calculations"""
        try:
            io_counters = psutil.net_io_counters(pernic=True)
            self.network_baseline = {
                interface: {
                    "bytes_sent": counters.bytes_sent,
                    "bytes_recv": counters.bytes_recv,
                    "timestamp": time.time()
                }
                for interface, counters in io_counters.items()
            }
        except Exception:
            self.network_baseline = {}
    
    async def _store_metrics(self, metrics: SystemMetrics):
        """Store metrics in Redis for persistence"""
        try:
            if self.redis_client:
                # Store current metrics
                self.redis_client.set(
                    f"metrics:current:{metrics.hostname}",
                    json.dumps(asdict(metrics), default=str),
                    ex=3600  # Expire after 1 hour
                )
                
                # Store in time series (for historical data)
                timestamp = int(metrics.timestamp.timestamp())
                self.redis_client.zadd(
                    f"metrics:history:{metrics.hostname}",
                    {json.dumps(asdict(metrics), default=str): timestamp}
                )
                
                # Clean up old historical data (keep last 24 hours)
                cutoff = timestamp - (24 * 3600)
                self.redis_client.zremrangebyscore(
                    f"metrics:history:{metrics.hostname}",
                    0, cutoff
                )
                
        except Exception as e:
            logger.error(f"Failed to store metrics in Redis: {e}")
    
    async def _check_alerts(self, metrics: SystemMetrics):
        """Check if any metrics exceed alert thresholds"""
        try:
            alerts = []
            
            # CPU alert
            if metrics.cpu_percent > self.alert_thresholds["cpu_percent"]:
                alerts.append({
                    "type": "cpu_high",
                    "value": metrics.cpu_percent,
                    "threshold": self.alert_thresholds["cpu_percent"],
                    "message": f"High CPU usage: {metrics.cpu_percent:.1f}%"
                })
            
            # Memory alert
            if metrics.memory_percent > self.alert_thresholds["memory_percent"]:
                alerts.append({
                    "type": "memory_high",
                    "value": metrics.memory_percent,
                    "threshold": self.alert_thresholds["memory_percent"],
                    "message": f"High memory usage: {metrics.memory_percent:.1f}%"
                })
            
            # Disk alert
            if metrics.disk_percent > self.alert_thresholds["disk_percent"]:
                alerts.append({
                    "type": "disk_high",
                    "value": metrics.disk_percent,
                    "threshold": self.alert_thresholds["disk_percent"],
                    "message": f"High disk usage: {metrics.disk_percent:.1f}%"
                })
            
            # Load average alert
            if metrics.load_average[0] > self.alert_thresholds["load_average"]:
                alerts.append({
                    "type": "load_high",
                    "value": metrics.load_average[0],
                    "threshold": self.alert_thresholds["load_average"],
                    "message": f"High load average: {metrics.load_average[0]:.2f}"
                })
            
            # Temperature alert
            if metrics.temperature:
                for sensor, temp in metrics.temperature.items():
                    if temp > self.alert_thresholds["temperature"]:
                        alerts.append({
                            "type": "temperature_high",
                            "sensor": sensor,
                            "value": temp,
                            "threshold": self.alert_thresholds["temperature"],
                            "message": f"High temperature on {sensor}: {temp:.1f}°C"
                        })
            
            # Store alerts in Redis
            if alerts and self.redis_client:
                for alert in alerts:
                    self.redis_client.lpush(
                        f"alerts:{metrics.hostname}",
                        json.dumps(alert, default=str)
                    )
                    # Keep only last 100 alerts
                    self.redis_client.ltrim(f"alerts:{metrics.hostname}", 0, 99)
            
        except Exception as e:
            logger.error(f"Failed to check alerts: {e}")
    
    async def _cleanup_old_data(self):
        """Clean up old data from memory"""
        try:
            # Keep only recent metrics in memory
            cutoff_time = datetime.now() - timedelta(hours=self.history_retention_hours)
            self.metrics_history = [
                metrics for metrics in self.metrics_history
                if metrics.timestamp >= cutoff_time
            ]
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary over the last hour"""
        try:
            recent_metrics = await self.get_historical_metrics(hours=1)
            
            if not recent_metrics:
                return {}
            
            # Calculate averages
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
            avg_disk = sum(m.disk_percent for m in recent_metrics) / len(recent_metrics)
            
            # Calculate peaks
            max_cpu = max(m.cpu_percent for m in recent_metrics)
            max_memory = max(m.memory_percent for m in recent_metrics)
            max_disk = max(m.disk_percent for m in recent_metrics)
            
            return {
                "time_period": "1 hour",
                "samples": len(recent_metrics),
                "averages": {
                    "cpu_percent": round(avg_cpu, 2),
                    "memory_percent": round(avg_memory, 2),
                    "disk_percent": round(avg_disk, 2)
                },
                "peaks": {
                    "cpu_percent": round(max_cpu, 2),
                    "memory_percent": round(max_memory, 2),
                    "disk_percent": round(max_disk, 2)
                },
                "current": {
                    "cpu_percent": round(recent_metrics[-1].cpu_percent, 2),
                    "memory_percent": round(recent_metrics[-1].memory_percent, 2),
                    "disk_percent": round(recent_metrics[-1].disk_percent, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {}
