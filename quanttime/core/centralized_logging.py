"""
Centralized Logging System for Multi-Node Monitoring
Aggregates logs from all nodes and displays them on the master node terminal
"""

import os
import json
import time
import threading
import logging
import logging.handlers
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import queue
import socket
import struct
import select
import sys
import traceback
from collections import deque
import requests

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """Represents a log entry"""
    timestamp: datetime
    level: LogLevel
    node_id: str
    node_name: str
    logger_name: str
    message: str
    module: str = ""
    function: str = ""
    line_number: int = 0
    exception: Optional[str] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LogNode:
    """Represents a logging node"""
    node_id: str
    name: str
    address: str
    port: int = 5000
    is_master: bool = False
    status: str = "offline"
    last_seen: Optional[datetime] = None
    log_count: int = 0
    error_count: int = 0
    last_log: Optional[LogEntry] = None


class CentralizedLogger:
    """Centralized logging system for multi-node monitoring"""
    
    def __init__(self, config_path: str = "config/logging_config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.nodes: Dict[str, LogNode] = {}
        self.log_queue = queue.Queue()
        self.log_buffer = deque(maxlen=10000)  # Keep last 10k logs
        self.log_file = None
        self.log_handler = None
        self.monitoring_thread = None
        self.stop_monitoring = False
        self.log_lock = threading.Lock()
        
        # Initialize nodes
        self._initialize_nodes()
        
        # Setup logging
        self._setup_logging()
        
        # Start monitoring
        self.start_monitoring()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load logging configuration"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            config = {
                "master_node": {
                    "node_id": "laptop",
                    "name": "Development Laptop",
                    "address": "localhost",
                    "port": 5000,
                    "is_master": True
                },
                "nodes": [
                    {
                        "node_id": "r630xl",
                        "name": "R630XL Server",
                        "address": "laptop",
                        "port": 5000,
                        "is_master": False
                    },
                    {
                        "node_id": "r810",
                        "name": "R810 Server",
                        "address": "jupiter",
                        "port": 5000,
                        "is_master": False
                    }
                ],
                "logging_settings": {
                    "log_level": "INFO",
                    "max_logs": 10000,
                    "log_file": "logs/quanttime_centralized.log",
                    "log_format": "%(asctime)s [%(levelname)s] [%(node_id)s] %(message)s",
                    "enable_console": True,
                    "enable_file": True,
                    "enable_remote": True,
                    "retention_days": 30,
                    "rotation_size_mb": 100
                }
            }
            
            # Save default config
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            return config
    
    def _initialize_nodes(self):
        """Initialize logging nodes"""
        # Add master node
        master_config = self.config["master_node"]
        self.nodes[master_config["node_id"]] = LogNode(**master_config)
        
        # Add other nodes
        for node_config in self.config["nodes"]:
            self.nodes[node_config["node_id"]] = LogNode(**node_config)
    
    def _setup_logging(self):
        """Setup logging handlers"""
        settings = self.config["logging_settings"]
        
        # Create log directory
        log_file_path = Path(settings["log_file"])
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup formatter
        formatter = logging.Formatter(settings["log_format"])
        
        # Setup handlers
        handlers = []
        
        if settings["enable_console"]:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(getattr(logging, settings["log_level"]))
            handlers.append(console_handler)
        
        if settings["enable_file"]:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file_path,
                maxBytes=settings["rotation_size_mb"] * 1024 * 1024,
                backupCount=5
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(getattr(logging, settings["log_level"]))
            handlers.append(file_handler)
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings["log_level"]))
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Add new handlers
        for handler in handlers:
            root_logger.addHandler(handler)
        
        self.log_handler = handlers
    
    def start_monitoring(self):
        """Start monitoring thread for log collection"""
        if self.monitoring_thread is None:
            self.monitoring_thread = threading.Thread(target=self._monitor_logs, daemon=True)
            self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring thread"""
        self.stop_monitoring = True
        if self.monitoring_thread:
            self.monitoring_thread.join()
    
    def _monitor_logs(self):
        """Monitor and collect logs from all nodes"""
        while not self.stop_monitoring:
            try:
                # Collect logs from remote nodes
                self._collect_remote_logs()
                
                # Process log queue
                self._process_log_queue()
                
                # Update node status
                self._update_node_status()
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                print(f"Error in log monitoring: {e}")
                time.sleep(10)
    
    def _collect_remote_logs(self):
        """Collect logs from remote nodes"""
        for node_id, node in self.nodes.items():
            if node.is_master:
                continue
            
            try:
                # Try to connect to node's logging endpoint
                url = f"http://{node.address}:{node.port}/logs"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    logs_data = response.json()
                    
                    # Process received logs
                    for log_data in logs_data.get("logs", []):
                        log_entry = self._create_log_entry_from_data(log_data, node_id, node.name)
                        self.log_queue.put(log_entry)
                    
                    # Update node status
                    node.status = "online"
                    node.last_seen = datetime.now()
                    node.log_count += len(logs_data.get("logs", []))
                    node.error_count = logs_data.get("error_count", 0)
                    
                else:
                    node.status = "offline"
                    node.errors = [f"HTTP {response.status_code}"]
                    
            except requests.exceptions.RequestException as e:
                node.status = "offline"
                node.errors = [f"Connection failed: {str(e)}"]
            except Exception as e:
                node.status = "offline"
                node.errors = [f"Unexpected error: {str(e)}"]
    
    def _create_log_entry_from_data(self, log_data: Dict[str, Any], node_id: str, node_name: str) -> LogEntry:
        """Create LogEntry from received data"""
        return LogEntry(
            timestamp=datetime.fromisoformat(log_data["timestamp"]),
            level=LogLevel(log_data["level"]),
            node_id=node_id,
            node_name=node_name,
            logger_name=log_data.get("logger_name", ""),
            message=log_data["message"],
            module=log_data.get("module", ""),
            function=log_data.get("function", ""),
            line_number=log_data.get("line_number", 0),
            exception=log_data.get("exception"),
            extra_data=log_data.get("extra_data", {})
        )
    
    def _process_log_queue(self):
        """Process log queue"""
        while not self.log_queue.empty():
            try:
                log_entry = self.log_queue.get_nowait()
                self._handle_log_entry(log_entry)
            except queue.Empty:
                break
            except Exception as e:
                print(f"Error processing log entry: {e}")
    
    def _handle_log_entry(self, log_entry: LogEntry):
        """Handle a log entry"""
        with self.log_lock:
            # Add to buffer
            self.log_buffer.append(log_entry)
            
            # Update node info
            if log_entry.node_id in self.nodes:
                node = self.nodes[log_entry.node_id]
                node.last_log = log_entry
                node.log_count += 1
                
                if log_entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                    node.error_count += 1
            
            # Log to system
            log_level = getattr(logging, log_entry.level.value)
            log_message = f"[{log_entry.node_id}] {log_entry.message}"
            
            if log_entry.exception:
                log_message += f"\nException: {log_entry.exception}"
            
            logging.log(log_level, log_message)
    
    def _update_node_status(self):
        """Update node status"""
        current_time = datetime.now()
        
        for node in self.nodes.values():
            if node.last_seen:
                # Mark node as offline if not seen for 30 seconds
                if (current_time - node.last_seen).seconds > 30:
                    node.status = "offline"
    
    def log(self, level: LogLevel, message: str, node_id: str = "laptop", 
            logger_name: str = "", module: str = "", function: str = "", 
            line_number: int = 0, exception: str = None, extra_data: Dict[str, Any] = None):
        """Log a message"""
        log_entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            node_id=node_id,
            node_name=self.nodes.get(node_id, LogNode(node_id, "Unknown", "")).name,
            logger_name=logger_name,
            message=message,
            module=module,
            function=function,
            line_number=line_number,
            exception=exception,
            extra_data=extra_data or {}
        )
        
        self.log_queue.put(log_entry)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.log(LogLevel.CRITICAL, message, **kwargs)
    
    def get_logs(self, node_id: str = None, level: LogLevel = None, 
                start_time: datetime = None, end_time: datetime = None, 
                limit: int = 100) -> List[LogEntry]:
        """Get logs with filters"""
        with self.log_lock:
            logs = list(self.log_buffer)
        
        # Apply filters
        if node_id:
            logs = [log for log in logs if log.node_id == node_id]
        
        if level:
            logs = [log for log in logs if log.level == level]
        
        if start_time:
            logs = [log for log in logs if log.timestamp >= start_time]
        
        if end_time:
            logs = [log for log in logs if log.timestamp <= end_time]
        
        # Sort by timestamp (newest first)
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Apply limit
        return logs[:limit]
    
    def get_node_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all nodes"""
        return {
            node_id: {
                "name": node.name,
                "status": node.status,
                "last_seen": node.last_seen.isoformat() if node.last_seen else None,
                "log_count": node.log_count,
                "error_count": node.error_count,
                "last_log": {
                    "timestamp": node.last_log.timestamp.isoformat(),
                    "level": node.last_log.level.value,
                    "message": node.last_log.message
                } if node.last_log else None
            }
            for node_id, node in self.nodes.items()
        }
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get error summary for the last N hours"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        error_logs = self.get_logs(
            level=LogLevel.ERROR,
            start_time=start_time,
            end_time=end_time
        )
        
        critical_logs = self.get_logs(
            level=LogLevel.CRITICAL,
            start_time=start_time,
            end_time=end_time
        )
        
        # Group by node
        errors_by_node = {}
        for log in error_logs + critical_logs:
            if log.node_id not in errors_by_node:
                errors_by_node[log.node_id] = []
            errors_by_node[log.node_id].append(log)
        
        return {
            "total_errors": len(error_logs),
            "total_critical": len(critical_logs),
            "errors_by_node": {
                node_id: len(logs) for node_id, logs in errors_by_node.items()
            },
            "time_period": f"Last {hours} hours"
        }
    
    def clear_logs(self, older_than_hours: int = 24):
        """Clear logs older than specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        with self.log_lock:
            # Remove old logs from buffer
            self.log_buffer = deque(
                [log for log in self.log_buffer if log.timestamp > cutoff_time],
                maxlen=self.log_buffer.maxlen
            )
    
    def export_logs(self, file_path: str, node_id: str = None, 
                   start_time: datetime = None, end_time: datetime = None):
        """Export logs to file"""
        logs = self.get_logs(node_id=node_id, start_time=start_time, end_time=end_time)
        
        with open(file_path, 'w') as f:
            for log in logs:
                f.write(f"{log.timestamp.isoformat()} [{log.level.value}] [{log.node_id}] {log.message}\n")
                if log.exception:
                    f.write(f"Exception: {log.exception}\n")
                f.write("\n")
    
    def get_live_logs(self, callback: callable):
        """Get live logs with callback"""
        def live_log_monitor():
            last_log_count = len(self.log_buffer)
            
            while not self.stop_monitoring:
                current_log_count = len(self.log_buffer)
                
                if current_log_count > last_log_count:
                    # New logs available
                    new_logs = list(self.log_buffer)[last_log_count:]
                    for log in new_logs:
                        callback(log)
                    
                    last_log_count = current_log_count
                
                time.sleep(1)
        
        # Start live monitoring thread
        live_thread = threading.Thread(target=live_log_monitor, daemon=True)
        live_thread.start()
        return live_thread


# Global centralized logger instance
centralized_logger = None


def get_centralized_logger() -> CentralizedLogger:
    """Get global centralized logger instance"""
    global centralized_logger
    if centralized_logger is None:
        centralized_logger = CentralizedLogger()
    return centralized_logger


def init_centralized_logger(config_path: str = None) -> CentralizedLogger:
    """Initialize centralized logger with custom config"""
    global centralized_logger
    if config_path:
        centralized_logger = CentralizedLogger(config_path)
    else:
        centralized_logger = CentralizedLogger()
    return centralized_logger


# Convenience functions for easy logging
def log_debug(message: str, **kwargs):
    """Log debug message"""
    logger = get_centralized_logger()
    logger.debug(message, **kwargs)


def log_info(message: str, **kwargs):
    """Log info message"""
    logger = get_centralized_logger()
    logger.info(message, **kwargs)


def log_warning(message: str, **kwargs):
    """Log warning message"""
    logger = get_centralized_logger()
    logger.warning(message, **kwargs)


def log_error(message: str, **kwargs):
    """Log error message"""
    logger = get_centralized_logger()
    logger.error(message, **kwargs)


def log_critical(message: str, **kwargs):
    """Log critical message"""
    logger = get_centralized_logger()
    logger.critical(message, **kwargs)


# Exception logging decorator
def log_exceptions(func):
    """Decorator to automatically log exceptions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger = get_centralized_logger()
            logger.error(
                f"Exception in {func.__name__}: {str(e)}",
                exception=traceback.format_exc(),
                function=func.__name__,
                module=func.__module__
            )
            raise
    return wrapper


# Context manager for logging
class LogContext:
    """Context manager for logging operations"""
    
    def __init__(self, operation: str, node_id: str = "laptop", **kwargs):
        self.operation = operation
        self.node_id = node_id
        self.kwargs = kwargs
        self.start_time = None
        self.logger = get_centralized_logger()
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Started: {self.operation}", node_id=self.node_id, **self.kwargs)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = datetime.now() - self.start_time
        
        if exc_type is None:
            self.logger.info(
                f"Completed: {self.operation} (Duration: {duration.total_seconds():.2f}s)",
                node_id=self.node_id,
                **self.kwargs
            )
        else:
            self.logger.error(
                f"Failed: {self.operation} (Duration: {duration.total_seconds():.2f}s) - {str(exc_val)}",
                node_id=self.node_id,
                exception=traceback.format_exc(),
                **self.kwargs
            )
