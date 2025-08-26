#!/usr/bin/env python3
"""
Task Progress Tracker for QuantTime Dashboard.

Provides real-time monitoring of distributed compute tasks including:
- Data processing and feature engineering
- Model training
- Backtesting
- Progress tracking and synchronization
"""

import streamlit as st
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import queue
import logging

from .server_task_manager import task_manager

logger = logging.getLogger(__name__)

class TaskProgressTracker:
    """
    Tracks progress of distributed compute tasks across servers.
    
    Features:
    - Real-time task monitoring
    - Progress tracking with step counters
    - Server error logging
    - Task lifecycle management
    """
    
    def __init__(self):
        self.active_tasks = {}  # task_id -> task_info
        self.completed_tasks = {}  # task_id -> completion_info
        self.failed_tasks = {}  # task_id -> error_info
        self.task_logs = {}  # task_id -> log_messages
        self.monitoring_thread = None
        self.stop_monitoring = False
        
        # Start monitoring thread
        self._start_monitoring()
    
    def _start_monitoring(self):
        """Start background monitoring thread."""
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.stop_monitoring = False
            self.monitoring_thread = threading.Thread(target=self._monitor_tasks, daemon=True)
            self.monitoring_thread.start()
            logger.info("Task monitoring thread started")
    
    def _monitor_tasks(self):
        """Background thread to monitor task progress."""
        while not self.stop_monitoring:
            try:
                self._update_task_progress()
                time.sleep(5)  # Check every 5 seconds
            except Exception as e:
                logger.error(f"Error in task monitoring: {e}")
                time.sleep(10)  # Wait longer on error
    
    def _update_task_progress(self):
        """Update progress for all active tasks."""
        for task_id, task_info in list(self.active_tasks.items()):
            try:
                server_name = task_info['server']
                task_type = task_info['type']
                
                # Get server status
                server_status = task_manager.get_server_status(server_name)
                if not server_status.get("connected", False):
                    self._mark_task_failed(task_id, f"Server {server_name} is offline")
                    continue
                
                # Check if process is still running
                if not self._is_process_running(task_id, task_info):
                    self._mark_task_completed(task_id)
                    continue
                
                # Update progress based on task type
                self._update_task_specific_progress(task_id, task_info)
                
            except Exception as e:
                logger.error(f"Error updating task {task_id}: {e}")
                self._mark_task_failed(task_id, str(e))
    
    def _is_process_running(self, task_id: str, task_info: Dict) -> bool:
        """Check if the task process is still running on the server."""
        try:
            server_name = task_info['server']
            pid = task_info.get('pid')
            
            if not pid:
                return False
            
            server = task_manager.servers[server_name]
            username = server.get('username', 'quanttime')
            ip_address = server.get('tailscale_ip') or server.get('ip_address')
            
            ssh = task_manager._get_ssh_connection(ip_address, username, timeout=5)
            stdin, stdout, stderr = ssh.exec_command(f"ps -p {pid}")
            result = stdout.channel.recv_exit_status()
            ssh.close()
            
            return result == 0  # Process exists if exit code is 0
            
        except Exception as e:
            logger.error(f"Error checking process {task_id}: {e}")
            return False
    
    def _update_task_specific_progress(self, task_id: str, task_info: Dict):
        """Update progress based on task type and server logs."""
        try:
            server_name = task_info['server']
            task_type = task_info['type']
            
            # Get recent log entries
            log_entries = self._get_task_logs(task_id, task_info)
            
            # Update progress based on log analysis
            progress = self._analyze_log_progress(task_type, log_entries)
            
            # Update task info
            self.active_tasks[task_id]['progress'] = progress
            self.active_tasks[task_id]['current_step'] = self._get_current_step(task_type, log_entries)
            self.active_tasks[task_id]['last_update'] = datetime.now()
            
            # Add log entries to task logs
            if log_entries:
                if task_id not in self.task_logs:
                    self.task_logs[task_id] = []
                self.task_logs[task_id].extend(log_entries[-10:])  # Keep last 10 entries
            
        except Exception as e:
            logger.error(f"Error updating task-specific progress for {task_id}: {e}")
    
    def _get_task_logs(self, task_id: str, task_info: Dict) -> List[str]:
        """Get recent log entries for a task."""
        try:
            server_name = task_info['server']
            task_type = task_info['type']
            
            server = task_manager.servers[server_name]
            username = server.get('username', 'quanttime')
            ip_address = server.get('tailscale_ip') or server.get('ip_address')
            
            # Get log file path
            log_filename = f"{task_type}_{task_info['start_time'].strftime('%Y%m%d_%H%M%S')}.log"
            log_path = f"/opt/quanttime/logs/{log_filename}"
            
            ssh = task_manager._get_ssh_connection(ip_address, username, timeout=5)
            stdin, stdout, stderr = ssh.exec_command(f"tail -20 {log_path} 2>/dev/null || echo 'Log file not found'")
            log_content = stdout.read().decode().strip()
            ssh.close()
            
            if log_content and "Log file not found" not in log_content:
                return log_content.split('\n')
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting logs for task {task_id}: {e}")
            return []
    
    def _analyze_log_progress(self, task_type: str, log_entries: List[str]) -> int:
        """Analyze log entries to determine progress percentage."""
        if not log_entries:
            return 0
        
        # Look for progress indicators in logs
        progress_keywords = {
            "data_processing": [
                "Loading DBN", "Converting to DataFrame", "Feature engineering", 
                "Saving processed data", "Successfully processed"
            ],
            "model_training": [
                "Loading data", "Training started", "Epoch", "Validation", 
                "Model saved", "Training completed"
            ],
            "backtest": [
                "Loading data", "Running backtest", "Processing trades", 
                "Calculating metrics", "Backtest completed"
            ]
        }
        
        keywords = progress_keywords.get(task_type, [])
        found_keywords = []
        
        for entry in log_entries:
            for keyword in keywords:
                if keyword.lower() in entry.lower():
                    found_keywords.append(keyword)
        
        # Calculate progress based on found keywords
        if keywords:
            progress = min(100, int((len(found_keywords) / len(keywords)) * 100))
        else:
            progress = 50  # Default progress if no keywords found
        
        return progress
    
    def _get_current_step(self, task_type: str, log_entries: List[str]) -> str:
        """Get current step from log entries."""
        if not log_entries:
            return "Initializing..."
        
        # Get the last meaningful log entry
        for entry in reversed(log_entries):
            if entry.strip() and not entry.startswith('['):
                return entry.strip()[:50] + "..." if len(entry) > 50 else entry.strip()
        
        return "Processing..."
    
    def _mark_task_completed(self, task_id: str):
        """Mark a task as completed."""
        if task_id in self.active_tasks:
            task_info = self.active_tasks.pop(task_id)
            task_info['completion_time'] = datetime.now()
            task_info['status'] = 'completed'
            task_info['progress'] = 100
            self.completed_tasks[task_id] = task_info
            logger.info(f"Task {task_id} completed")
    
    def _mark_task_failed(self, task_id: str, error_message: str):
        """Mark a task as failed."""
        if task_id in self.active_tasks:
            task_info = self.active_tasks.pop(task_id)
            task_info['completion_time'] = datetime.now()
            task_info['status'] = 'failed'
            task_info['error'] = error_message
            self.failed_tasks[task_id] = task_info
            logger.error(f"Task {task_id} failed: {error_message}")
    
    def add_task(self, server_name: str, task_type: str, task_params: Dict) -> str:
        """Add a new task to tracking."""
        task_id = f"{server_name}_{task_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        task_info = {
            'id': task_id,
            'server': server_name,
            'type': task_type,
            'params': task_params,
            'start_time': datetime.now(),
            'status': 'running',
            'progress': 0,
            'current_step': 'Initializing...',
            'last_update': datetime.now()
        }
        
        self.active_tasks[task_id] = task_info
        logger.info(f"Added task {task_id} to tracking")
        return task_id
    
    def get_active_tasks(self) -> List[Dict]:
        """Get list of active tasks."""
        return list(self.active_tasks.values())
    
    def get_completed_tasks(self) -> List[Dict]:
        """Get list of completed tasks."""
        return list(self.completed_tasks.values())
    
    def get_failed_tasks(self) -> List[Dict]:
        """Get list of failed tasks."""
        return list(self.failed_tasks.values())
    
    def stop_task(self, task_id: str) -> bool:
        """Stop a running task."""
        if task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]
            server_name = task_info['server']
            pid = task_info.get('pid')
            
            if pid:
                try:
                    server = task_manager.servers[server_name]
                    username = server.get('username', 'quanttime')
                    ip_address = server.get('tailscale_ip') or server.get('ip_address')
                    
                    ssh = task_manager._get_ssh_connection(ip_address, username, timeout=5)
                    stdin, stdout, stderr = ssh.exec_command(f"kill {pid}")
                    ssh.close()
                    
                    self._mark_task_failed(task_id, "Task stopped by user")
                    logger.info(f"Task {task_id} stopped by user")
                    return True
                    
                except Exception as e:
                    logger.error(f"Error stopping task {task_id}: {e}")
                    return False
            else:
                self._mark_task_failed(task_id, "Task stopped by user")
                return True
        
        return False
    
    def get_task_logs(self, task_id: str) -> List[str]:
        """Get log entries for a specific task."""
        return self.task_logs.get(task_id, [])
    
    def clear_completed_tasks(self):
        """Clear completed and failed tasks."""
        self.completed_tasks.clear()
        self.failed_tasks.clear()
        self.task_logs.clear()
        logger.info("Cleared completed and failed tasks")
    
    def render_sidebar_progress(self):
        """Render task progress in sidebar."""
        st.markdown("### 📋 Active Tasks")
        
        active_tasks = self.get_active_tasks()
        if not active_tasks:
            st.caption("No active tasks")
            return
        
        for task in active_tasks:
            with st.container():
                # Task header
                status_emoji = {
                    "running": "🔄",
                    "completed": "✅",
                    "failed": "❌",
                    "paused": "⏸️"
                }.get(task.get("status", "unknown"), "❓")
                
                st.markdown(f"{status_emoji} **{task['type']}** on {task['server'].upper()}")
                
                # Progress bar
                progress = task.get("progress", 0)
                st.progress(progress / 100)
                
                # Progress details
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.caption(f"Step: {task.get('current_step', 'Unknown')}")
                with col2:
                    st.caption(f"{progress:.0f}%")
                
                # Task details in expander
                with st.expander("Details", expanded=False):
                    st.caption(f"**Started:** {task.get('started', 'Unknown')}")
                    st.caption(f"**Last Update:** {task.get('last_update', 'Unknown')}")
                    
                    # Action buttons
                    if st.button("⏹️ Stop", key=f"stop_{task['id']}"):
                        self.stop_task(task['id'])
                        st.rerun()
                
                st.markdown("---")
        
        # Quick actions
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh", key="refresh_tasks"):
                st.rerun()
        with col2:
            if st.button("🗑️ Clear", key="clear_tasks"):
                self.clear_completed_tasks()
                st.rerun()

# Global instance
progress_tracker = TaskProgressTracker()
