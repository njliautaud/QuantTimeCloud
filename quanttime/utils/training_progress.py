"""
Training Progress Tracker for Real-time Model Training Updates.

This module provides utilities for tracking and displaying training progress
in real-time during model training sessions.
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import threading
import queue

logger = logging.getLogger(__name__)


@dataclass
class TrainingMetrics:
    """Container for training metrics."""
    epoch: int = 0
    total_epochs: int = 0
    train_loss: float = 0.0
    val_loss: float = 0.0
    train_r2: float = 0.0
    val_r2: float = 0.0
    train_accuracy: float = 0.0
    val_accuracy: float = 0.0
    learning_rate: float = 0.0
    best_val_loss: float = float('inf')
    patience_counter: int = 0
    training_time: float = 0.0
    phase: str = "initializing"
    message: str = ""


@dataclass
class TrainingProgress:
    """Training progress tracker."""
    model_type: str
    start_time: datetime = field(default_factory=datetime.now)
    current_phase: str = "initializing"
    phases_completed: list = field(default_factory=list)
    current_metrics: TrainingMetrics = field(default_factory=TrainingMetrics)
    history: list = field(default_factory=list)
    is_training: bool = False
    is_complete: bool = False
    error_message: Optional[str] = None
    
    def update_phase(self, phase: str, message: str = ""):
        """Update the current training phase."""
        self.current_phase = phase
        if phase not in self.phases_completed:
            self.phases_completed.append(phase)
        logger.info(f"Training Phase: {phase} - {message}")
    
    def update_metrics(self, metrics: TrainingMetrics):
        """Update current training metrics."""
        self.current_metrics = metrics
        self.history.append(metrics)
        logger.info(f"Epoch {metrics.epoch}/{metrics.total_epochs} - "
                   f"Train Loss: {metrics.train_loss:.6f}, Val Loss: {metrics.val_loss:.6f}, "
                   f"Train R²: {metrics.train_r2:.4f}, Val R²: {metrics.val_r2:.4f}")
    
    def get_progress_percentage(self) -> float:
        """Get overall training progress percentage."""
        if self.current_metrics.total_epochs == 0:
            return 0.0
        return (self.current_metrics.epoch / self.current_metrics.total_epochs) * 100
    
    def get_elapsed_time(self) -> float:
        """Get elapsed training time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()


class TrainingProgressCallback:
    """Callback for tracking training progress."""
    
    def __init__(self, progress: TrainingProgress, update_callback: Optional[Callable] = None):
        self.progress = progress
        self.update_callback = update_callback
        self.start_time = time.time()
    
    def on_phase_start(self, phase: str, message: str = ""):
        """Called when a training phase starts."""
        self.progress.update_phase(phase, message)
        if self.update_callback:
            self.update_callback(self.progress)
    
    def on_epoch_end(self, epoch: int, total_epochs: int, train_loss: float, val_loss: float,
                    train_r2: float = 0.0, val_r2: float = 0.0, train_accuracy: float = 0.0,
                    val_accuracy: float = 0.0, learning_rate: float = 0.0,
                    best_val_loss: float = float('inf'), patience_counter: int = 0):
        """Called at the end of each epoch."""
        metrics = TrainingMetrics(
            epoch=epoch,
            total_epochs=total_epochs,
            train_loss=train_loss,
            val_loss=val_loss,
            train_r2=train_r2,
            val_r2=val_r2,
            train_accuracy=train_accuracy,
            val_accuracy=val_accuracy,
            learning_rate=learning_rate,
            best_val_loss=best_val_loss,
            patience_counter=patience_counter,
            training_time=time.time() - self.start_time
        )
        self.progress.update_metrics(metrics)
        if self.update_callback:
            self.update_callback(self.progress)
    
    def on_training_complete(self, final_metrics: Dict[str, Any]):
        """Called when training is complete."""
        self.progress.is_complete = True
        self.progress.is_training = False
        self.progress.update_phase("completed", "Training completed successfully")
        if self.update_callback:
            self.update_callback(self.progress)
    
    def on_error(self, error_message: str):
        """Called when an error occurs during training."""
        self.progress.error_message = error_message
        self.progress.is_training = False
        self.progress.update_phase("error", f"Training failed: {error_message}")
        if self.update_callback:
            self.update_callback(self.progress)


class StreamlitProgressUpdater:
    """Streamlit-specific progress updater."""
    
    def __init__(self, progress_placeholder, metrics_placeholder, chart_placeholder):
        self.progress_placeholder = progress_placeholder
        self.metrics_placeholder = metrics_placeholder
        self.chart_placeholder = chart_placeholder
        self.update_queue = queue.Queue()
        self.is_running = True
        
        # Start update thread
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
    
    def _update_loop(self):
        """Main update loop for Streamlit components."""
        while self.is_running:
            try:
                progress = self.update_queue.get(timeout=1.0)
                self._update_streamlit_components(progress)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
    
    def _update_streamlit_components(self, progress: TrainingProgress):
        """Update Streamlit components with progress data."""
        try:
            # Update progress bar
            if self.progress_placeholder:
                import streamlit as st
                with self.progress_placeholder.container():
                    st.progress(progress.get_progress_percentage() / 100)
                    st.write(f"**Phase:** {progress.current_phase}")
                    st.write(f"**Elapsed Time:** {progress.get_elapsed_time():.1f}s")
            
            # Update metrics
            if self.metrics_placeholder and progress.current_metrics:
                import streamlit as st
                with self.metrics_placeholder.container():
                    metrics = progress.current_metrics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Epoch", f"{metrics.epoch}/{metrics.total_epochs}")
                        st.metric("Train Loss", f"{metrics.train_loss:.6f}")
                    
                    with col2:
                        st.metric("Val Loss", f"{metrics.val_loss:.6f}")
                        st.metric("Train R²", f"{metrics.train_r2:.4f}")
                    
                    with col3:
                        st.metric("Val R²", f"{metrics.val_r2:.4f}")
                        st.metric("Learning Rate", f"{metrics.learning_rate:.6f}")
                    
                    with col4:
                        st.metric("Best Val Loss", f"{metrics.best_val_loss:.6f}")
                        st.metric("Patience", metrics.patience_counter)
            
            # Update training chart
            if self.chart_placeholder and len(progress.history) > 1:
                import streamlit as st
                import plotly.graph_objects as go
                import pandas as pd
                
                with self.chart_placeholder.container():
                    # Create training history dataframe
                    df = pd.DataFrame([
                        {
                            'epoch': m.epoch,
                            'train_loss': m.train_loss,
                            'val_loss': m.val_loss,
                            'train_r2': m.train_r2,
                            'val_r2': m.val_r2
                        }
                        for m in progress.history
                    ])
                    
                    if not df.empty:
                        # Create loss plot
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=df['epoch'], y=df['train_loss'],
                            mode='lines', name='Train Loss',
                            line=dict(color='blue')
                        ))
                        fig.add_trace(go.Scatter(
                            x=df['epoch'], y=df['val_loss'],
                            mode='lines', name='Val Loss',
                            line=dict(color='red')
                        ))
                        fig.update_layout(
                            title='Training Progress',
                            xaxis_title='Epoch',
                            yaxis_title='Loss',
                            height=300
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Create R² plot
                        fig2 = go.Figure()
                        fig2.add_trace(go.Scatter(
                            x=df['epoch'], y=df['train_r2'],
                            mode='lines', name='Train R²',
                            line=dict(color='green')
                        ))
                        fig2.add_trace(go.Scatter(
                            x=df['epoch'], y=df['val_r2'],
                            mode='lines', name='Val R²',
                            line=dict(color='orange')
                        ))
                        fig2.update_layout(
                            title='R² Progress',
                            xaxis_title='Epoch',
                            yaxis_title='R² Score',
                            height=300
                        )
                        st.plotly_chart(fig2, use_container_width=True)
        
        except Exception as e:
            logger.error(f"Error updating Streamlit components: {e}")
    
    def update(self, progress: TrainingProgress):
        """Queue an update to the Streamlit components."""
        try:
            self.update_queue.put(progress, timeout=0.1)
        except queue.Full:
            pass  # Skip update if queue is full
    
    def stop(self):
        """Stop the update thread."""
        self.is_running = False
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=1.0)


def create_training_progress(model_type: str) -> TrainingProgress:
    """Create a new training progress tracker."""
    return TrainingProgress(model_type=model_type)


def create_progress_callback(progress: TrainingProgress, 
                           update_callback: Optional[Callable] = None) -> TrainingProgressCallback:
    """Create a training progress callback."""
    return TrainingProgressCallback(progress, update_callback)
