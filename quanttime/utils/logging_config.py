"""
Enhanced Logging Configuration for QuantTime Distributed System.

This module provides centralized logging with device tagging, remote logging,
and unified error reporting across laptop and server environments.
"""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import json
import socket
import platform

# Device identification
DEVICE_NAME = os.getenv('QUANTTIME_DEVICE_NAME', socket.gethostname())
DEVICE_TYPE = os.getenv('QUANTTIME_DEVICE_TYPE', 'laptop')  # laptop, server
DEVICE_IP = os.getenv('QUANTTIME_DEVICE_IP', 'unknown')

class DeviceTaggedFormatter(logging.Formatter):
    """Custom formatter that includes device information in log messages."""
    
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self.device_info = f"[{DEVICE_TYPE.upper()}:{DEVICE_NAME}]"
    
    def format(self, record):
        # Add device info to the record
        record.device_info = self.device_info
        record.device_type = DEVICE_TYPE
        record.device_name = DEVICE_NAME
        record.device_ip = DEVICE_IP
        
        # Add timestamp
        record.timestamp = datetime.now().isoformat()
        
        return super().format(record)

class RemoteLogHandler(logging.Handler):
    """Handler for sending logs to remote devices via SSH/network."""
    
    def __init__(self, remote_host: str, remote_user: str, remote_log_path: str):
        super().__init__()
        self.remote_host = remote_host
        self.remote_user = remote_user
        self.remote_log_path = remote_log_path
    
    def emit(self, record):
        try:
            import subprocess
            log_entry = self.format(record)
            
            # Send log entry to remote device
            cmd = f'ssh {self.remote_user}@{self.remote_host} "echo \'{log_entry}\' >> {self.remote_log_path}"'
            subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            
        except Exception as e:
            # Fallback to local logging if remote fails
            sys.stderr.write(f"Remote logging failed: {e}\n")

def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    device_name: Optional[str] = None,
    device_type: Optional[str] = None,
    enable_remote_logging: bool = False,
    remote_host: Optional[str] = None,
    remote_user: Optional[str] = None
) -> logging.Logger:
    """
    Setup enhanced logging with device tagging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        device_name: Override device name
        device_type: Override device type
        enable_remote_logging: Enable remote log forwarding
        remote_host: Remote host for log forwarding
        remote_user: Remote user for log forwarding
    """
    
    # Set device information
    global DEVICE_NAME, DEVICE_TYPE
    if device_name:
        DEVICE_NAME = device_name
    if device_type:
        DEVICE_TYPE = device_type
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Default log file if not specified
    if not log_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"{DEVICE_TYPE}_{DEVICE_NAME}_{timestamp}.log"
    
    # Create formatter
    formatter = DeviceTaggedFormatter(
        fmt='%(timestamp)s | %(device_info)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Remote handler (if enabled)
    if enable_remote_logging and remote_host and remote_user:
        remote_handler = RemoteLogHandler(remote_host, remote_user, f"/opt/quanttime/logs/{DEVICE_NAME}.log")
        remote_handler.setFormatter(formatter)
        root_logger.addHandler(remote_handler)
    
    # Create device-specific logger
    logger = logging.getLogger(f"quanttime.{DEVICE_TYPE}")
    
    # Log startup information
    logger.info(f"🚀 Logging system initialized on {DEVICE_TYPE.upper()}:{DEVICE_NAME}")
    logger.info(f"📁 Log file: {log_file}")
    logger.info(f"🖥️  Platform: {platform.system()} {platform.release()}")
    logger.info(f"🌐 IP Address: {DEVICE_IP}")
    
    return logger

def log_device_operation(
    operation: str,
    status: str = "INFO",
    details: Optional[Dict[str, Any]] = None,
    error: Optional[Exception] = None
):
    """
    Log device-specific operations with structured information.
    
    Args:
        operation: Operation being performed
        status: Status (INFO, SUCCESS, WARNING, ERROR)
        details: Additional details
        error: Exception if any
    """
    logger = logging.getLogger(f"quanttime.{DEVICE_TYPE}")
    
    # Create structured log entry
    log_data = {
        "operation": operation,
        "status": status,
        "device": {
            "type": DEVICE_TYPE,
            "name": DEVICE_NAME,
            "ip": DEVICE_IP
        },
        "timestamp": datetime.now().isoformat()
    }
    
    if details:
        log_data["details"] = details
    
    if error:
        log_data["error"] = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": getattr(error, '__traceback__', None)
        }
    
    # Log based on status
    if status == "ERROR":
        logger.error(f"❌ {operation} | {json.dumps(log_data, default=str)}")
    elif status == "WARNING":
        logger.warning(f"⚠️  {operation} | {json.dumps(log_data, default=str)}")
    elif status == "SUCCESS":
        logger.info(f"✅ {operation} | {json.dumps(log_data, default=str)}")
    else:
        logger.info(f"ℹ️  {operation} | {json.dumps(log_data, default=str)}")

def log_server_operation(
    server_name: str,
    operation: str,
    status: str = "INFO",
    details: Optional[Dict[str, Any]] = None,
    error: Optional[Exception] = None
):
    """
    Log server-specific operations.
    
    Args:
        server_name: Name of the server
        operation: Operation being performed
        status: Status (INFO, SUCCESS, WARNING, ERROR)
        details: Additional details
        error: Exception if any
    """
    logger = logging.getLogger(f"quanttime.server.{server_name}")
    
    # Create structured log entry
    log_data = {
        "server": server_name,
        "operation": operation,
        "status": status,
        "source_device": {
            "type": DEVICE_TYPE,
            "name": DEVICE_NAME,
            "ip": DEVICE_IP
        },
        "timestamp": datetime.now().isoformat()
    }
    
    if details:
        log_data["details"] = details
    
    if error:
        log_data["error"] = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": getattr(error, '__traceback__', None)
        }
    
    # Log based on status
    if status == "ERROR":
        logger.error(f"🖥️❌ {server_name}: {operation} | {json.dumps(log_data, default=str)}")
    elif status == "WARNING":
        logger.warning(f"🖥️⚠️  {server_name}: {operation} | {json.dumps(log_data, default=str)}")
    elif status == "SUCCESS":
        logger.info(f"🖥️✅ {server_name}: {operation} | {json.dumps(log_data, default=str)}")
    else:
        logger.info(f"🖥️ℹ️  {server_name}: {operation} | {json.dumps(log_data, default=str)}")

# Initialize logging on import
if not logging.getLogger().handlers:
    setup_logging()
