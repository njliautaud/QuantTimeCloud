"""
Progress Bar Component for QuantTime ML Trading Suite.

This module provides a comprehensive progress tracking system for long-running
operations like data loading, model training, and backtesting.
"""

import streamlit as st
import time
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class ProgressState:
    """Progress state for tracking operations."""
    task: str
    current: int
    total: int
    subtask: str
    subprogress: float
    start_time: float
    last_update: float


class ProgressTracker:
    """
    Progress tracker for long-running operations.
    
    Provides both task-level and subtask-level progress tracking with
    time estimates and memory usage monitoring.
    """
    
    def __init__(self, container=None):
        """
        Initialize progress tracker.
        
        Args:
            container: Streamlit container to place progress bars in
        """
        self.container = container or st
        self.progress_state = None
        self.task_progress_bar = None
        self.subtask_progress_bar = None
        self.status_text = None
        self.time_estimate_text = None
        self.memory_text = None
    
    def start_task(self, task: str, total: int):
        """
        Start a new task.
        
        Args:
            task: Task description
            total: Total number of steps
        """
        self.progress_state = ProgressState(
            task=task,
            current=0,
            total=total,
            subtask="Initializing...",
            subprogress=0.0,
            start_time=time.time(),
            last_update=time.time()
        )
        
        # Create progress bars
        self.task_progress_bar = self.container.progress(0.0, text=f"**{task}**")
        self.subtask_progress_bar = self.container.progress(0.0, text="Initializing...")
        
        # Create status containers
        col1, col2, col3 = self.container.columns(3)
        with col1:
            self.status_text = self.container.empty()
        with col2:
            self.time_estimate_text = self.container.empty()
        with col3:
            self.memory_text = self.container.empty()
        
        self._update_display()
    
    def update_progress(self, current: int, subtask: str, subprogress: float = 0.0):
        """
        Update progress for current task.
        
        Args:
            current: Current step number
            subtask: Current subtask description
            subprogress: Progress within current subtask (0.0 to 1.0)
        """
        if self.progress_state is None:
            return
        
        self.progress_state.current = current
        self.progress_state.subtask = subtask
        self.progress_state.subprogress = subprogress
        self.progress_state.last_update = time.time()
        
        self._update_display()
    
    def _update_display(self):
        """Update all progress displays."""
        if self.progress_state is None:
            return
        
        # Update task progress
        task_progress = self.progress_state.current / self.progress_state.total
        self.task_progress_bar.progress(
            task_progress, 
            text=f"**{self.progress_state.task}** ({self.progress_state.current}/{self.progress_state.total})"
        )
        
        # Update subtask progress
        self.subtask_progress_bar.progress(
            self.progress_state.subprogress,
            text=self.progress_state.subtask
        )
        
        # Update status text
        self.status_text.markdown(f"**Status:** {self.progress_state.subtask}")
        
        # Update time estimate
        elapsed_time = time.time() - self.progress_state.start_time
        if self.progress_state.current > 0:
            avg_time_per_step = elapsed_time / self.progress_state.current
            remaining_steps = self.progress_state.total - self.progress_state.current
            estimated_remaining = avg_time_per_step * remaining_steps
            
            self.time_estimate_text.markdown(
                f"**Time:** {self._format_time(elapsed_time)} elapsed, "
                f"{self._format_time(estimated_remaining)} remaining"
            )
        else:
            self.time_estimate_text.markdown(f"**Time:** {self._format_time(elapsed_time)} elapsed")
        
        # Update memory usage
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_gb = memory.used / (1024**3)
            memory_percent = memory.percent
            
            self.memory_text.markdown(
                f"**Memory:** {memory_gb:.1f}GB ({memory_percent:.1f}%)"
            )
        except ImportError:
            self.memory_text.markdown("**Memory:** Monitoring unavailable")
    
    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    def complete(self, message: str = "Completed successfully!"):
        """
        Mark task as complete.
        
        Args:
            message: Completion message
        """
        if self.progress_state is None:
            return
        
        # Set progress to 100%
        self.task_progress_bar.progress(1.0, text=f"**{self.progress_state.task}** - {message}")
        self.subtask_progress_bar.progress(1.0, text=message)
        
        # Update final status
        total_time = time.time() - self.progress_state.start_time
        self.status_text.markdown(f"**Status:** {message}")
        self.time_estimate_text.markdown(f"**Total Time:** {self._format_time(total_time)}")
        
        # Clear memory text
        self.memory_text.markdown("")
        
        # Clear progress state
        self.progress_state = None


def create_progress_callback(progress_tracker: ProgressTracker) -> Callable:
    """
    Create a progress callback function for use with data loaders.
    
    Args:
        progress_tracker: Progress tracker instance
        
    Returns:
        Callback function that can be passed to data loaders
    """
    def progress_callback(task: str, current: int, total: int, subtask: str, subprogress: float):
        """Progress callback function."""
        if progress_tracker.progress_state is None:
            progress_tracker.start_task(task, total)
        
        progress_tracker.update_progress(current, subtask, subprogress)
    
    return progress_callback


def show_loading_progress(operation_name: str, total_steps: int, container=None):
    """
    Context manager for showing loading progress.
    
    Args:
        operation_name: Name of the operation
        total_steps: Total number of steps
        container: Streamlit container
        
    Yields:
        Progress tracker instance
    """
    tracker = ProgressTracker(container)
    tracker.start_task(operation_name, total_steps)
    
    try:
        yield tracker
    finally:
        tracker.complete()


# Example usage:
"""
# In your Streamlit app:
with show_loading_progress("Loading DBN Data", len(selected_dates)) as progress:
    for i, date in enumerate(selected_dates):
        progress.update_progress(
            current=i + 1,
            subtask=f"Processing {date}",
            subprogress=0.5
        )
        # ... process date ...
        progress.update_progress(
            current=i + 1,
            subtask=f"Completed {date}",
            subprogress=1.0
        )
"""
