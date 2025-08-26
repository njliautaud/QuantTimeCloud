"""
QuantTime Health Checker

Monitors system health, service status, and performs automatic recovery actions.
"""

import asyncio
import json
import logging
import platform
import psutil
import socket
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
import redis
import requests

# Configure logging
logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class ServiceStatus(Enum):
    """Service status enumeration"""
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    STARTING = "starting"
    STOPPING = "stopping"

@dataclass
class HealthCheck:
    """Health check result"""
    check_name: str
    status: HealthStatus
    message: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class ServiceHealth:
    """Service health information"""
    service_name: str
    status: ServiceStatus
    pid: Optional[int] = None
    uptime_seconds: Optional[int] = None
    memory_usage_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    last_check: datetime = None
    
    def __post_init__(self):
        if self.last_check is None:
            self.last_check = datetime.now()

@dataclass
class SystemHealth:
    """Overall system health"""
    overall_status: HealthStatus
    checks: List[HealthCheck]
    services: List[ServiceHealth]
    timestamp: datetime
    node_id: str
    alerts: List[str] = None
    
    def __post_init__(self):
        if self.alerts is None:
            self.alerts = []

class HealthChecker:
    """
    Comprehensive health monitoring system
    
    Features:
    - System resource monitoring
    - Service health checks
    - Network connectivity tests
    - Automatic recovery actions
    - Alert generation
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize health checker"""
        self.redis_url = redis_url
        self.redis_client = None
        self.running = False
        
        # Configuration
        self.check_interval = 30  # seconds
        self.alert_threshold_consecutive = 3  # alerts after X consecutive failures
        
        # Health check thresholds
        self.thresholds = {
            "cpu_percent": 85.0,
            "memory_percent": 90.0,
            "disk_percent": 95.0,
            "load_average": psutil.cpu_count() * 0.9,
            "temperature": 80.0,
            "network_latency_ms": 100.0,
            "service_response_time_ms": 5000.0
        }
        
        # Services to monitor
        self.monitored_services = {
            "quanttime-data-collector": {
                "systemd_name": "quanttime-data-collector",
                "port": None,
                "health_endpoint": None
            },
            "quanttime-data-warehouse": {
                "systemd_name": "quanttime-data-warehouse",
                "port": None,
                "health_endpoint": None
            },
            "quanttime-model-deployer": {
                "systemd_name": "quanttime-model-deployer",
                "port": None,
                "health_endpoint": None
            },
            "quanttime-celery-worker": {
                "systemd_name": "quanttime-celery-worker",
                "port": None,
                "health_endpoint": None
            },
            "redis": {
                "systemd_name": "redis",
                "port": 6379,
                "health_endpoint": None
            },
            "postgresql": {
                "systemd_name": "postgresql",
                "port": 5432,
                "health_endpoint": None
            },
            "nginx": {
                "systemd_name": "nginx",
                "port": 80,
                "health_endpoint": "http://localhost/health"
            }
        }
        
        # External endpoints to check
        self.external_endpoints = {
            "google_dns": "8.8.8.8",
            "databento_api": "https://api.databento.com/health",
            "quanttime_api": "http://localhost:8000/api/v1/server/health"
        }
        
        # Health history
        self.health_history: List[SystemHealth] = []
        self.max_history_size = 288  # 24 hours at 5-minute intervals
        
        # Alert tracking
        self.consecutive_failures: Dict[str, int] = {}
        self.alert_cooldown: Dict[str, datetime] = {}
        self.alert_cooldown_minutes = 15
        
        # Recovery actions
        self.auto_recovery_enabled = True
        self.recovery_actions = {
            "restart_service": self._restart_service,
            "clear_cache": self._clear_cache,
            "cleanup_temp": self._cleanup_temp_files,
            "restart_networking": self._restart_networking
        }
    
    async def start(self):
        """Start the health checker"""
        try:
            # Initialize Redis connection
            self.redis_client = redis.Redis.from_url(self.redis_url)
            self.redis_client.ping()
            
            self.running = True
            
            # Start health monitoring loop
            asyncio.create_task(self._health_monitoring_loop())
            
            logger.info("✅ Health Checker started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Health Checker: {e}")
            raise
    
    async def stop(self):
        """Stop the health checker"""
        self.running = False
        logger.info("✅ Health Checker stopped")
    
    async def _health_monitoring_loop(self):
        """Main health monitoring loop"""
        while self.running:
            try:
                # Perform comprehensive health check
                health_report = await self.perform_health_check()
                
                # Store health report
                await self._store_health_report(health_report)
                
                # Check for alerts and recovery actions
                await self._process_alerts(health_report)
                
                # Clean up old data
                await self._cleanup_old_data()
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def perform_health_check(self) -> SystemHealth:
        """Perform comprehensive health check"""
        try:
            checks = []
            services = []
            alerts = []
            
            # System resource checks
            checks.extend(await self._check_system_resources())
            
            # Service health checks
            services.extend(await self._check_services())
            
            # Network connectivity checks
            checks.extend(await self._check_network_connectivity())
            
            # External endpoint checks
            checks.extend(await self._check_external_endpoints())
            
            # Determine overall status
            overall_status = self._determine_overall_status(checks, services)
            
            # Generate alerts
            alerts = self._generate_alerts(checks, services)
            
            health_report = SystemHealth(
                overall_status=overall_status,
                checks=checks,
                services=services,
                timestamp=datetime.now(),
                node_id=platform.node(),
                alerts=alerts
            )
            
            # Add to history
            self.health_history.append(health_report)
            
            # Trim history if too long
            if len(self.health_history) > self.max_history_size:
                self.health_history.pop(0)
            
            return health_report
            
        except Exception as e:
            logger.error(f"❌ Failed to perform health check: {e}")
            raise
    
    async def _check_system_resources(self) -> List[HealthCheck]:
        """Check system resource usage"""
        checks = []
        
        try:
            # CPU check
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_status = HealthStatus.HEALTHY
            if cpu_percent > self.thresholds["cpu_percent"]:
                cpu_status = HealthStatus.CRITICAL
            elif cpu_percent > self.thresholds["cpu_percent"] * 0.8:
                cpu_status = HealthStatus.WARNING
            
            checks.append(HealthCheck(
                check_name="cpu_usage",
                status=cpu_status,
                message=f"CPU usage: {cpu_percent:.1f}%",
                value=cpu_percent,
                threshold=self.thresholds["cpu_percent"]
            ))
            
            # Memory check
            memory = psutil.virtual_memory()
            memory_status = HealthStatus.HEALTHY
            if memory.percent > self.thresholds["memory_percent"]:
                memory_status = HealthStatus.CRITICAL
            elif memory.percent > self.thresholds["memory_percent"] * 0.8:
                memory_status = HealthStatus.WARNING
            
            checks.append(HealthCheck(
                check_name="memory_usage",
                status=memory_status,
                message=f"Memory usage: {memory.percent:.1f}%",
                value=memory.percent,
                threshold=self.thresholds["memory_percent"]
            ))
            
            # Disk check
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_status = HealthStatus.HEALTHY
            if disk_percent > self.thresholds["disk_percent"]:
                disk_status = HealthStatus.CRITICAL
            elif disk_percent > self.thresholds["disk_percent"] * 0.8:
                disk_status = HealthStatus.WARNING
            
            checks.append(HealthCheck(
                check_name="disk_usage",
                status=disk_status,
                message=f"Disk usage: {disk_percent:.1f}%",
                value=disk_percent,
                threshold=self.thresholds["disk_percent"]
            ))
            
            # Load average check (Linux only)
            if hasattr(psutil, 'getloadavg'):
                load_avg = psutil.getloadavg()[0]
                load_status = HealthStatus.HEALTHY
                if load_avg > self.thresholds["load_average"]:
                    load_status = HealthStatus.CRITICAL
                elif load_avg > self.thresholds["load_average"] * 0.8:
                    load_status = HealthStatus.WARNING
                
                checks.append(HealthCheck(
                    check_name="load_average",
                    status=load_status,
                    message=f"Load average: {load_avg:.2f}",
                    value=load_avg,
                    threshold=self.thresholds["load_average"]
                ))
            
            # Temperature check (if available)
            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()
                if temps:
                    max_temp = 0
                    for name, entries in temps.items():
                        for entry in entries:
                            if entry.current and entry.current > max_temp:
                                max_temp = entry.current
                    
                    if max_temp > 0:
                        temp_status = HealthStatus.HEALTHY
                        if max_temp > self.thresholds["temperature"]:
                            temp_status = HealthStatus.CRITICAL
                        elif max_temp > self.thresholds["temperature"] * 0.8:
                            temp_status = HealthStatus.WARNING
                        
                        checks.append(HealthCheck(
                            check_name="temperature",
                            status=temp_status,
                            message=f"Max temperature: {max_temp:.1f}°C",
                            value=max_temp,
                            threshold=self.thresholds["temperature"]
                        ))
            
        except Exception as e:
            logger.error(f"Failed to check system resources: {e}")
            checks.append(HealthCheck(
                check_name="system_resources",
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check system resources: {e}"
            ))
        
        return checks
    
    async def _check_services(self) -> List[ServiceHealth]:
        """Check health of monitored services"""
        services = []
        
        for service_name, config in self.monitored_services.items():
            try:
                service_health = await self._check_service(service_name, config)
                services.append(service_health)
                
            except Exception as e:
                logger.error(f"Failed to check service {service_name}: {e}")
                services.append(ServiceHealth(
                    service_name=service_name,
                    status=ServiceStatus.FAILED
                ))
        
        return services
    
    async def _check_service(self, service_name: str, config: Dict[str, Any]) -> ServiceHealth:
        """Check individual service health"""
        try:
            # Check systemd service status
            systemd_name = config.get("systemd_name", service_name)
            
            result = subprocess.run(
                ["systemctl", "is-active", systemd_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip() == "active":
                status = ServiceStatus.RUNNING
                
                # Get service PID and stats
                pid_result = subprocess.run(
                    ["systemctl", "show", systemd_name, "--property=MainPID"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                pid = None
                memory_usage = None
                cpu_percent = None
                uptime_seconds = None
                
                if pid_result.returncode == 0:
                    pid_line = pid_result.stdout.strip()
                    if "MainPID=" in pid_line:
                        try:
                            pid = int(pid_line.split("=")[1])
                            if pid > 0:
                                # Get process info
                                process = psutil.Process(pid)
                                memory_usage = process.memory_info().rss / (1024 * 1024)  # MB
                                cpu_percent = process.cpu_percent()
                                uptime_seconds = int(time.time() - process.create_time())
                        except (psutil.NoSuchProcess, ValueError):
                            pass
                
            else:
                status = ServiceStatus.STOPPED
                if result.stdout.strip() == "failed":
                    status = ServiceStatus.FAILED
            
            # Additional port check if configured
            if config.get("port") and status == ServiceStatus.RUNNING:
                port_check = await self._check_port(config["port"])
                if not port_check:
                    status = ServiceStatus.FAILED
            
            # Health endpoint check if configured
            if config.get("health_endpoint") and status == ServiceStatus.RUNNING:
                endpoint_check = await self._check_http_endpoint(config["health_endpoint"])
                if not endpoint_check:
                    status = ServiceStatus.FAILED
            
            return ServiceHealth(
                service_name=service_name,
                status=status,
                pid=pid,
                uptime_seconds=uptime_seconds,
                memory_usage_mb=memory_usage,
                cpu_percent=cpu_percent
            )
            
        except subprocess.TimeoutExpired:
            return ServiceHealth(
                service_name=service_name,
                status=ServiceStatus.UNKNOWN
            )
        except Exception as e:
            logger.error(f"Error checking service {service_name}: {e}")
            return ServiceHealth(
                service_name=service_name,
                status=ServiceStatus.FAILED
            )
    
    async def _check_network_connectivity(self) -> List[HealthCheck]:
        """Check network connectivity"""
        checks = []
        
        # Check internet connectivity
        try:
            start_time = time.time()
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            latency = (time.time() - start_time) * 1000
            
            latency_status = HealthStatus.HEALTHY
            if latency > self.thresholds["network_latency_ms"]:
                latency_status = HealthStatus.WARNING
            
            checks.append(HealthCheck(
                check_name="internet_connectivity",
                status=HealthStatus.HEALTHY,
                message=f"Internet connectivity OK (latency: {latency:.1f}ms)",
                value=latency,
                threshold=self.thresholds["network_latency_ms"]
            ))
            
        except Exception as e:
            checks.append(HealthCheck(
                check_name="internet_connectivity",
                status=HealthStatus.CRITICAL,
                message=f"Internet connectivity failed: {e}"
            ))
        
        # Check local network interfaces
        try:
            interfaces = psutil.net_if_stats()
            active_interfaces = [name for name, stats in interfaces.items() if stats.isup]
            
            if active_interfaces:
                checks.append(HealthCheck(
                    check_name="network_interfaces",
                    status=HealthStatus.HEALTHY,
                    message=f"Active interfaces: {', '.join(active_interfaces)}"
                ))
            else:
                checks.append(HealthCheck(
                    check_name="network_interfaces",
                    status=HealthStatus.CRITICAL,
                    message="No active network interfaces"
                ))
                
        except Exception as e:
            checks.append(HealthCheck(
                check_name="network_interfaces",
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check network interfaces: {e}"
            ))
        
        return checks
    
    async def _check_external_endpoints(self) -> List[HealthCheck]:
        """Check external endpoints"""
        checks = []
        
        for endpoint_name, url in self.external_endpoints.items():
            try:
                start_time = time.time()
                
                if url.startswith("http"):
                    # HTTP endpoint
                    response = requests.get(url, timeout=10)
                    response_time = (time.time() - start_time) * 1000
                    
                    if response.status_code == 200:
                        status = HealthStatus.HEALTHY
                        message = f"{endpoint_name} OK (response time: {response_time:.1f}ms)"
                    else:
                        status = HealthStatus.WARNING
                        message = f"{endpoint_name} returned status {response.status_code}"
                else:
                    # IP endpoint (ping)
                    socket.create_connection((url, 53), timeout=5)
                    response_time = (time.time() - start_time) * 1000
                    status = HealthStatus.HEALTHY
                    message = f"{endpoint_name} reachable (latency: {response_time:.1f}ms)"
                
                checks.append(HealthCheck(
                    check_name=f"endpoint_{endpoint_name}",
                    status=status,
                    message=message,
                    value=response_time,
                    threshold=self.thresholds["service_response_time_ms"]
                ))
                
            except Exception as e:
                checks.append(HealthCheck(
                    check_name=f"endpoint_{endpoint_name}",
                    status=HealthStatus.CRITICAL,
                    message=f"{endpoint_name} unreachable: {e}"
                ))
        
        return checks
    
    async def _check_port(self, port: int, host: str = "localhost") -> bool:
        """Check if port is accessible"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    async def _check_http_endpoint(self, url: str) -> bool:
        """Check HTTP endpoint health"""
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def _determine_overall_status(self, checks: List[HealthCheck], 
                                 services: List[ServiceHealth]) -> HealthStatus:
        """Determine overall system health status"""
        # Check for critical issues
        critical_checks = [c for c in checks if c.status == HealthStatus.CRITICAL]
        failed_services = [s for s in services if s.status == ServiceStatus.FAILED]
        
        if critical_checks or failed_services:
            return HealthStatus.CRITICAL
        
        # Check for warnings
        warning_checks = [c for c in checks if c.status == HealthStatus.WARNING]
        if warning_checks:
            return HealthStatus.WARNING
        
        # Check for unknown status
        unknown_checks = [c for c in checks if c.status == HealthStatus.UNKNOWN]
        if unknown_checks:
            return HealthStatus.WARNING
        
        return HealthStatus.HEALTHY
    
    def _generate_alerts(self, checks: List[HealthCheck], 
                        services: List[ServiceHealth]) -> List[str]:
        """Generate alerts based on health checks"""
        alerts = []
        
        # Critical checks
        for check in checks:
            if check.status == HealthStatus.CRITICAL:
                alerts.append(f"CRITICAL: {check.message}")
        
        # Failed services
        for service in services:
            if service.status == ServiceStatus.FAILED:
                alerts.append(f"SERVICE FAILED: {service.service_name}")
        
        return alerts
    
    async def _process_alerts(self, health_report: SystemHealth):
        """Process alerts and trigger recovery actions"""
        try:
            for alert in health_report.alerts:
                alert_key = alert.split(":")[0] if ":" in alert else alert
                
                # Track consecutive failures
                if alert_key not in self.consecutive_failures:
                    self.consecutive_failures[alert_key] = 0
                
                self.consecutive_failures[alert_key] += 1
                
                # Check if we should trigger alert
                if (self.consecutive_failures[alert_key] >= self.alert_threshold_consecutive and
                    self._should_send_alert(alert_key)):
                    
                    await self._send_alert(alert)
                    await self._trigger_recovery_action(alert_key, health_report)
                    
                    # Set cooldown
                    self.alert_cooldown[alert_key] = datetime.now()
            
            # Reset counters for resolved issues
            all_alert_keys = {alert.split(":")[0] for alert in health_report.alerts}
            for key in list(self.consecutive_failures.keys()):
                if key not in all_alert_keys:
                    self.consecutive_failures[key] = 0
                    
        except Exception as e:
            logger.error(f"Failed to process alerts: {e}")
    
    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if alert should be sent (considering cooldown)"""
        if alert_key in self.alert_cooldown:
            cooldown_end = self.alert_cooldown[alert_key] + timedelta(minutes=self.alert_cooldown_minutes)
            return datetime.now() > cooldown_end
        return True
    
    async def _send_alert(self, alert: str):
        """Send alert notification"""
        try:
            # Store alert in Redis
            if self.redis_client:
                alert_data = {
                    "message": alert,
                    "timestamp": datetime.now().isoformat(),
                    "node_id": platform.node(),
                    "severity": "critical" if "CRITICAL" in alert else "warning"
                }
                
                self.redis_client.lpush("health:alerts", json.dumps(alert_data))
                self.redis_client.ltrim("health:alerts", 0, 999)  # Keep last 1000 alerts
            
            logger.warning(f"ALERT: {alert}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    async def _trigger_recovery_action(self, alert_key: str, health_report: SystemHealth):
        """Trigger automatic recovery action"""
        if not self.auto_recovery_enabled:
            return
        
        try:
            # Service restart recovery
            if "SERVICE FAILED" in alert_key:
                service_name = alert_key.replace("SERVICE FAILED", "").strip()
                await self._restart_service(service_name)
            
            # High resource usage recovery
            elif "CRITICAL" in alert_key:
                if "cpu_usage" in alert_key:
                    await self._clear_cache()
                elif "memory_usage" in alert_key:
                    await self._cleanup_temp_files()
                elif "disk_usage" in alert_key:
                    await self._cleanup_temp_files()
                    
        except Exception as e:
            logger.error(f"Recovery action failed: {e}")
    
    async def _restart_service(self, service_name: str):
        """Restart a systemd service"""
        try:
            systemd_name = self.monitored_services.get(service_name, {}).get("systemd_name", service_name)
            
            result = subprocess.run(
                ["sudo", "systemctl", "restart", systemd_name],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully restarted service: {systemd_name}")
            else:
                logger.error(f"Failed to restart service {systemd_name}: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Failed to restart service {service_name}: {e}")
    
    async def _clear_cache(self):
        """Clear system caches"""
        try:
            # Clear Redis cache
            if self.redis_client:
                self.redis_client.flushdb()
            
            # Clear system page cache (Linux)
            subprocess.run(["sudo", "sync"], check=True)
            subprocess.run(["sudo", "sysctl", "vm.drop_caches=1"], check=True)
            
            logger.info("Cleared system caches")
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
    
    async def _cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            temp_dirs = ["/tmp", "/var/tmp", "temp/server"]
            
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    # Remove files older than 1 day
                    subprocess.run([
                        "find", temp_dir, "-type", "f", "-mtime", "+1", "-delete"
                    ], check=True)
            
            logger.info("Cleaned up temporary files")
            
        except Exception as e:
            logger.error(f"Failed to cleanup temp files: {e}")
    
    async def _restart_networking(self):
        """Restart networking services"""
        try:
            subprocess.run(["sudo", "systemctl", "restart", "networking"], check=True)
            logger.info("Restarted networking")
            
        except Exception as e:
            logger.error(f"Failed to restart networking: {e}")
    
    async def _store_health_report(self, health_report: SystemHealth):
        """Store health report in Redis"""
        try:
            if self.redis_client:
                # Store current health
                self.redis_client.set(
                    f"health:current:{health_report.node_id}",
                    json.dumps(asdict(health_report), default=str),
                    ex=3600
                )
                
                # Store in time series
                timestamp = int(health_report.timestamp.timestamp())
                self.redis_client.zadd(
                    f"health:history:{health_report.node_id}",
                    {json.dumps(asdict(health_report), default=str): timestamp}
                )
                
                # Clean up old data (keep last 24 hours)
                cutoff = timestamp - (24 * 3600)
                self.redis_client.zremrangebyscore(
                    f"health:history:{health_report.node_id}",
                    0, cutoff
                )
                
        except Exception as e:
            logger.error(f"Failed to store health report: {e}")
    
    async def _cleanup_old_data(self):
        """Clean up old health data"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.health_history = [
                report for report in self.health_history
                if report.timestamp >= cutoff_time
            ]
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    async def get_current_health(self) -> Optional[SystemHealth]:
        """Get current health status"""
        if self.health_history:
            return self.health_history[-1]
        else:
            return await self.perform_health_check()
    
    async def get_health_history(self, hours: int = 1) -> List[SystemHealth]:
        """Get health history for specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            report for report in self.health_history
            if report.timestamp >= cutoff_time
        ]
