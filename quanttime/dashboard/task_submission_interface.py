"""
Task Submission Interface for QuantTime Dashboard

Provides comprehensive task submission capabilities:
- Data normalization tasks
- Feature engineering tasks
- Model training tasks
- Backtesting tasks
- Progress monitoring
- Result collection
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import streamlit as st
import pandas as pd

from .enhanced_server_control import enhanced_server_control

# Configure logging
logger = logging.getLogger(__name__)

class TaskSubmissionInterface:
    """
    Task submission interface for QuantTime dashboard
    
    Features:
    - Task type selection
    - Parameter configuration
    - Device selection
    - Progress monitoring
    - Result collection
    """
    
    def __init__(self):
        """Initialize task submission interface"""
        self.task_types = {
            "data_normalization": {
                "name": "Data Normalization",
                "description": "Normalize and clean raw market data",
                "icon": "📊",
                "capabilities": ["ALL TASKS", "data_normalization"],
                "parameters": {
                    "data_source": {
                        "type": "selectbox",
                        "label": "Data Source",
                        "options": ["databento", "live_stream", "historical"],
                        "default": "databento"
                    },
                    "symbols": {
                        "type": "multiselect",
                        "label": "Symbols",
                        "options": ["ES", "NQ", "RTY", "CL", "GC", "SI"],
                        "default": ["ES"]
                    },
                    "date_range": {
                        "type": "date_input",
                        "label": "Date Range",
                        "default": [datetime.now() - timedelta(days=7), datetime.now()]
                    },
                    "normalization_type": {
                        "type": "selectbox",
                        "label": "Normalization Type",
                        "options": ["zscore", "minmax", "robust", "none"],
                        "default": "zscore"
                    }
                }
            },
            "feature_engineering": {
                "name": "Feature Engineering",
                "description": "Generate features from normalized data",
                "icon": "🔧",
                "capabilities": ["ALL TASKS", "feature_engineering"],
                "parameters": {
                    "feature_set": {
                        "type": "selectbox",
                        "label": "Feature Set",
                        "options": ["basic", "advanced", "custom"],
                        "default": "advanced"
                    },
                    "window_sizes": {
                        "type": "multiselect",
                        "label": "Window Sizes",
                        "options": ["5", "10", "20", "50", "100"],
                        "default": ["10", "20", "50"]
                    },
                    "include_technical_indicators": {
                        "type": "checkbox",
                        "label": "Include Technical Indicators",
                        "default": True
                    },
                    "include_orderbook_features": {
                        "type": "checkbox",
                        "label": "Include Orderbook Features",
                        "default": True
                    }
                }
            },
            "model_training": {
                "name": "Model Training",
                "description": "Train machine learning models",
                "icon": "🤖",
                "capabilities": ["ALL TASKS", "model_training"],
                "parameters": {
                    "model_type": {
                        "type": "selectbox",
                        "label": "Model Type",
                        "options": ["lightgbm", "xgboost", "random_forest", "neural_network"],
                        "default": "lightgbm"
                    },
                    "hyperparameter_optimization": {
                        "type": "checkbox",
                        "label": "Enable Hyperparameter Optimization",
                        "default": True
                    },
                    "optimization_trials": {
                        "type": "number_input",
                        "label": "Optimization Trials",
                        "min_value": 10,
                        "max_value": 1000,
                        "value": 100,
                        "step": 10
                    },
                    "cross_validation_folds": {
                        "type": "number_input",
                        "label": "Cross Validation Folds",
                        "min_value": 3,
                        "max_value": 10,
                        "value": 5,
                        "step": 1
                    },
                    "training_data_ratio": {
                        "type": "slider",
                        "label": "Training Data Ratio",
                        "min_value": 0.5,
                        "max_value": 0.9,
                        "value": 0.8,
                        "step": 0.05
                    }
                }
            },
            "backtesting": {
                "name": "Backtesting",
                "description": "Run backtests on trained models",
                "icon": "📈",
                "capabilities": ["ALL TASKS", "backtesting"],
                "parameters": {
                    "model_id": {
                        "type": "text_input",
                        "label": "Model ID",
                        "placeholder": "Enter model ID or leave empty for latest"
                    },
                    "backtest_period": {
                        "type": "selectbox",
                        "label": "Backtest Period",
                        "options": ["1d", "1w", "1m", "3m", "6m", "1y"],
                        "default": "1m"
                    },
                    "initial_capital": {
                        "type": "number_input",
                        "label": "Initial Capital",
                        "min_value": 1000,
                        "max_value": 1000000,
                        "value": 100000,
                        "step": 1000
                    },
                    "commission_rate": {
                        "type": "number_input",
                        "label": "Commission Rate (%)",
                        "min_value": 0.0,
                        "max_value": 1.0,
                        "value": 0.1,
                        "step": 0.01
                    },
                    "slippage": {
                        "type": "number_input",
                        "label": "Slippage (ticks)",
                        "min_value": 0,
                        "max_value": 10,
                        "value": 1,
                        "step": 1
                    }
                }
            }
        }
    
    def render_task_submission(self):
        """Render the main task submission interface"""
        st.markdown("## 🚀 Task Submission Center")
        
        # Get selected device
        selected_device = enhanced_server_control.get_selected_device()
        server_info = enhanced_server_control.get_server_info(selected_device)
        
        # Device info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Selected Device", server_info.get('name', 'Unknown'))
        with col2:
            st.metric("CPU Cores", server_info.get('specs', {}).get('cpu_cores', 0))
        with col3:
            st.metric("Memory", f"{server_info.get('specs', {}).get('memory_gb', 0)} GB")
        
        # Task type selection
        st.markdown("### 📋 Select Task Type")
        task_type = st.selectbox(
            "Choose task type:",
            options=list(self.task_types.keys()),
            format_func=lambda x: f"{self.task_types[x]['icon']} {self.task_types[x]['name']}"
        )
        
        if task_type:
            task_info = self.task_types[task_type]
            st.markdown(f"**Description:** {task_info['description']}")
            
            # Check if device supports this task
            device_capabilities = server_info.get('capabilities', [])
            task_capabilities = task_info.get('capabilities', [])
            
            if not any(cap in device_capabilities for cap in task_capabilities):
                st.error(f"❌ {server_info.get('name', 'Selected device')} does not support {task_info['name']}")
                return
            
            # Parameter configuration
            st.markdown("### ⚙️ Task Parameters")
            parameters = self._render_task_parameters(task_type)
            
            # Submit button
            if st.button(f"🚀 Submit {task_info['name']} Task", type="primary"):
                if self._submit_task(selected_device, task_type, parameters):
                    st.success(f"✅ {task_info['name']} task submitted successfully!")
                else:
                    st.error(f"❌ Failed to submit {task_info['name']} task")
    
    def _render_task_parameters(self, task_type: str) -> Dict[str, Any]:
        """Render parameter configuration for a specific task type"""
        task_info = self.task_types[task_type]
        parameters = {}
        
        for param_name, param_config in task_info['parameters'].items():
            param_type = param_config['type']
            param_label = param_config['label']
            param_default = param_config.get('default')
            
            if param_type == "selectbox":
                parameters[param_name] = st.selectbox(
                    param_label,
                    options=param_config['options'],
                    index=param_config['options'].index(param_default) if param_default in param_config['options'] else 0
                )
            
            elif param_type == "multiselect":
                parameters[param_name] = st.multiselect(
                    param_label,
                    options=param_config['options'],
                    default=param_default
                )
            
            elif param_type == "checkbox":
                parameters[param_name] = st.checkbox(
                    param_label,
                    value=param_default
                )
            
            elif param_type == "number_input":
                parameters[param_name] = st.number_input(
                    param_label,
                    min_value=param_config.get('min_value'),
                    max_value=param_config.get('max_value'),
                    value=param_config.get('value', param_default),
                    step=param_config.get('step', 1)
                )
            
            elif param_type == "slider":
                parameters[param_name] = st.slider(
                    param_label,
                    min_value=param_config.get('min_value'),
                    max_value=param_config.get('max_value'),
                    value=param_config.get('value', param_default),
                    step=param_config.get('step', 0.1)
                )
            
            elif param_type == "text_input":
                parameters[param_name] = st.text_input(
                    param_label,
                    value=param_default,
                    placeholder=param_config.get('placeholder', '')
                )
            
            elif param_type == "date_input":
                parameters[param_name] = st.date_input(
                    param_label,
                    value=param_default
                )
        
        return parameters
    
    def _submit_task(self, device: str, task_type: str, parameters: Dict[str, Any]) -> bool:
        """Submit a task to the selected device"""
        try:
            # Create task object
            task = {
                "id": f"{task_type}_{int(time.time())}",
                "type": task_type,
                "device": device,
                "parameters": parameters,
                "status": "submitted",
                "submitted_at": datetime.now().isoformat(),
                "progress": 0
            }
            
            # Submit to device
            success = enhanced_server_control.submit_job(device, task_type, parameters)
            
            if success:
                # Store task in session state for tracking
                if 'submitted_tasks' not in st.session_state:
                    st.session_state.submitted_tasks = []
                
                st.session_state.submitted_tasks.append(task)
                logger.info(f"Task submitted successfully: {task['id']}")
                return True
            else:
                logger.error(f"Failed to submit task: {task['id']}")
                return False
                
        except Exception as e:
            logger.error(f"Error submitting task: {e}")
            return False
    
    def render_task_monitoring(self):
        """Render task monitoring interface"""
        st.markdown("## 📊 Task Monitoring")
        
        if 'submitted_tasks' not in st.session_state or not st.session_state.submitted_tasks:
            st.info("No tasks submitted yet. Submit a task to see monitoring information.")
            return
        
        # Task list
        for task in st.session_state.submitted_tasks:
            with st.expander(f"{task['type'].replace('_', ' ').title()} - {task['id']}", expanded=True):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Status", task['status'])
                
                with col2:
                    st.metric("Device", task['device'])
                
                with col3:
                    st.metric("Progress", f"{task['progress']}%")
                
                # Progress bar
                st.progress(task['progress'] / 100)
                
                # Task details
                st.markdown("**Parameters:**")
                for key, value in task['parameters'].items():
                    st.caption(f"{key}: {value}")
                
                # Action buttons
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button(f"🔄 Refresh", key=f"refresh_{task['id']}"):
                        self._refresh_task_status(task)
                
                with col2:
                    if st.button(f"📊 View Results", key=f"results_{task['id']}"):
                        self._view_task_results(task)
                
                with col3:
                    if st.button(f"❌ Cancel", key=f"cancel_{task['id']}"):
                        self._cancel_task(task)
    
    def _refresh_task_status(self, task: Dict[str, Any]):
        """Refresh the status of a specific task"""
        try:
            # This would query the actual task status from the device
            # For now, just simulate progress
            if task['status'] == 'submitted':
                task['status'] = 'running'
                task['progress'] = 25
            elif task['status'] == 'running' and task['progress'] < 100:
                task['progress'] += 25
                if task['progress'] >= 100:
                    task['status'] = 'completed'
            
            st.success("Task status refreshed!")
            
        except Exception as e:
            logger.error(f"Error refreshing task status: {e}")
            st.error("Failed to refresh task status")
    
    def _view_task_results(self, task: Dict[str, Any]):
        """View results of a completed task"""
        if task['status'] != 'completed':
            st.warning("Task is not completed yet. Cannot view results.")
            return
        
        st.markdown(f"### 📊 Results for {task['type'].replace('_', ' ').title()}")
        
        # This would load and display actual results
        # For now, show placeholder
        st.info("Results would be displayed here based on task type")
        
        if task['type'] == 'model_training':
            st.markdown("**Training Results:**")
            st.caption("Model performance metrics, feature importance, etc.")
        
        elif task['type'] == 'backtesting':
            st.markdown("**Backtest Results:**")
            st.caption("Returns, Sharpe ratio, drawdown, trade statistics, etc.")
        
        elif task['type'] == 'data_normalization':
            st.markdown("**Normalization Results:**")
            st.caption("Data quality metrics, processing statistics, etc.")
        
        elif task['type'] == 'feature_engineering':
            st.markdown("**Feature Engineering Results:**")
            st.caption("Feature statistics, correlation analysis, etc.")
    
    def _cancel_task(self, task: Dict[str, Any]):
        """Cancel a running task"""
        if task['status'] not in ['submitted', 'running']:
            st.warning("Cannot cancel completed or failed tasks.")
            return
        
        try:
            # This would send cancellation signal to the device
            task['status'] = 'cancelled'
            task['progress'] = 0
            st.success("Task cancelled successfully!")
            
        except Exception as e:
            logger.error(f"Error cancelling task: {e}")
            st.error("Failed to cancel task")

# Global instance
task_submission_interface = TaskSubmissionInterface()

def render_task_submission_interface():
    """Render the task submission interface"""
    task_submission_interface.render_task_submission()

def render_task_monitoring():
    """Render the task monitoring interface"""
    task_submission_interface.render_task_monitoring()
