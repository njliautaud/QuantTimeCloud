"""
Data Transmission Interface for QuantTime Dashboard

Provides comprehensive data transmission control and monitoring:
- Transfer scheduling and management
- Real-time transfer status monitoring
- Transfer history and statistics
- Manual sync operations
- Transfer configuration
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import streamlit as st
import pandas as pd

from server.core.data_transmission import data_transmission

# Configure logging
logger = logging.getLogger(__name__)

class DataTransmissionInterface:
    """
    Data transmission interface for QuantTime dashboard
    
    Features:
    - Transfer scheduling and management
    - Real-time status monitoring
    - Transfer history and statistics
    - Manual sync operations
    - Transfer configuration
    """
    
    def __init__(self):
        """Initialize data transmission interface"""
        self.transfer_types = {
            "models": {
                "name": "Model Files",
                "description": "Trained models, checkpoints, and metadata",
                "icon": "🤖",
                "priority": "high",
                "sync_interval": "5 minutes"
            },
            "data": {
                "name": "Data Files",
                "description": "Normalized data, features, and raw data",
                "icon": "📊",
                "priority": "high",
                "sync_interval": "10 minutes"
            },
            "results": {
                "name": "Backtest Results",
                "description": "Performance metrics, trade logs, equity curves",
                "icon": "📈",
                "priority": "medium",
                "sync_interval": "30 minutes"
            },
            "leaderboard": {
                "name": "Leaderboard Data",
                "description": "Rankings, statistics, and comparisons",
                "icon": "🏆",
                "priority": "medium",
                "sync_interval": "15 minutes"
            },
            "config": {
                "name": "Configuration Files",
                "description": "Settings, parameters, and configuration",
                "icon": "⚙️",
                "priority": "critical",
                "sync_interval": "1 minute"
            }
        }
    
    def render_data_transmission_interface(self):
        """Render the main data transmission interface"""
        st.markdown("## 📡 Data Transmission Center")
        
        # Overview metrics
        self._render_overview_metrics()
        
        # Transfer control section
        st.markdown("### 🚀 Transfer Control")
        self._render_transfer_control()
        
        # Active transfers
        st.markdown("### 🔄 Active Transfers")
        self._render_active_transfers()
        
        # Transfer history
        st.markdown("### 📋 Transfer History")
        self._render_transfer_history()
        
        # Statistics
        st.markdown("### 📊 Transfer Statistics")
        self._render_transfer_statistics()
    
    def _render_overview_metrics(self):
        """Render overview metrics"""
        try:
            all_transfers = data_transmission.get_all_transfers()
            stats = all_transfers.get("stats", {})
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Transfers", stats.get("total_transfers", 0))
            
            with col2:
                st.metric("Successful", stats.get("successful_transfers", 0))
            
            with col3:
                st.metric("Failed", stats.get("failed_transfers", 0))
            
            with col4:
                queue_size = all_transfers.get("queue_size", 0)
                st.metric("Queue Size", queue_size)
            
            # Success rate
            total = stats.get("total_transfers", 0)
            successful = stats.get("successful_transfers", 0)
            if total > 0:
                success_rate = (successful / total) * 100
                st.metric("Success Rate", f"{success_rate:.1f}%")
            
        except Exception as e:
            st.error(f"Failed to load overview metrics: {e}")
    
    def _render_transfer_control(self):
        """Render transfer control section"""
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📤 Manual Transfers")
            
            # Transfer type selection
            transfer_type = st.selectbox(
                "Transfer Type:",
                options=list(self.transfer_types.keys()),
                format_func=lambda x: f"{self.transfer_types[x]['icon']} {self.transfer_types[x]['name']}"
            )
            
            if transfer_type:
                transfer_info = self.transfer_types[transfer_type]
                st.markdown(f"**Description:** {transfer_info['description']}")
                st.markdown(f"**Priority:** {transfer_info['priority']}")
                st.markdown(f"**Sync Interval:** {transfer_info['sync_interval']}")
            
            # Source and target selection
            col1a, col1b = st.columns(2)
            with col1a:
                source = st.selectbox("Source:", ["laptop", "r630xl", "r810"], index=0)
            with col1b:
                target = st.selectbox("Target:", ["laptop", "r630xl", "r810"], index=1)
            
            # Priority selection
            priority = st.selectbox("Priority:", ["low", "medium", "high", "critical"], index=2)
            
            # Schedule transfer button
            if st.button("📋 Schedule Transfer", type="primary"):
                if source != target:
                    job_id = data_transmission.schedule_transfer(
                        source=source,
                        target=target,
                        transfer_type=transfer_type,
                        priority=priority
                    )
                    if job_id:
                        st.success(f"✅ Transfer scheduled: {job_id}")
                    else:
                        st.error("❌ Failed to schedule transfer")
                else:
                    st.warning("⚠️ Source and target must be different")
        
        with col2:
            st.markdown("#### ⚡ Quick Actions")
            
            # Quick sync buttons
            if st.button("🔄 Sync Models (All)", key="sync_models"):
                job_ids = data_transmission.sync_models()
                st.success(f"✅ Scheduled {len(job_ids)} model sync jobs")
            
            if st.button("📊 Sync Data (All)", key="sync_data"):
                job_ids = data_transmission.sync_data()
                st.success(f"✅ Scheduled {len(job_ids)} data sync jobs")
            
            if st.button("📈 Sync Results (To Laptop)", key="sync_results"):
                job_ids = data_transmission.sync_results()
                st.success(f"✅ Scheduled {len(job_ids)} result sync jobs")
            
            if st.button("🏆 Sync Leaderboard (To Laptop)", key="sync_leaderboard"):
                job_ids = data_transmission.sync_leaderboard()
                st.success(f"✅ Scheduled {len(job_ids)} leaderboard sync jobs")
            
            if st.button("⚙️ Sync Config (All)", key="sync_config"):
                job_ids = data_transmission.sync_config()
                st.success(f"✅ Scheduled {len(job_ids)} config sync jobs")
            
            st.markdown("---")
            
            # Force sync all
            if st.button("🚀 Force Sync All", type="primary", key="force_sync_all"):
                results = data_transmission.force_sync_all()
                total_jobs = sum(len(jobs) for jobs in results.values())
                st.success(f"✅ Scheduled {total_jobs} sync jobs across all types")
                
                # Show breakdown
                for transfer_type, job_ids in results.items():
                    if job_ids:
                        st.caption(f"{transfer_type}: {len(job_ids)} jobs")
    
    def _render_active_transfers(self):
        """Render active transfers section"""
        try:
            all_transfers = data_transmission.get_all_transfers()
            active_transfers = all_transfers.get("active", [])
            
            if not active_transfers:
                st.info("No active transfers")
                return
            
            # Create DataFrame for active transfers
            df = pd.DataFrame(active_transfers)
            
            # Format timestamps
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%H:%M:%S')
            if 'started_at' in df.columns:
                df['started_at'] = pd.to_datetime(df['started_at']).dt.strftime('%H:%M:%S')
            
            # Format bytes
            if 'bytes_transferred' in df.columns:
                df['bytes_transferred'] = df['bytes_transferred'].apply(
                    lambda x: f"{x/1024/1024:.1f} MB" if x > 0 else "0 B"
                )
            
            # Display active transfers
            for _, transfer in df.iterrows():
                with st.expander(f"{transfer['transfer_type']} - {transfer['job_id']}", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Status", transfer['status'])
                        st.caption(f"Priority: {transfer['priority']}")
                    
                    with col2:
                        st.metric("Source → Target", f"{transfer['source']} → {transfer['target']}")
                        st.caption(f"Type: {transfer['transfer_type']}")
                    
                    with col3:
                        st.metric("Bytes Transferred", transfer.get('bytes_transferred', '0 B'))
                        if transfer.get('started_at'):
                            st.caption(f"Started: {transfer['started_at']}")
                    
                    # Progress bar (simulated)
                    if transfer['status'] == 'running':
                        st.progress(0.5)  # This would be real progress in actual implementation
                    
                    # Action buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"🔄 Refresh", key=f"refresh_{transfer['job_id']}"):
                            st.rerun()
                    
                    with col2:
                        if st.button(f"❌ Cancel", key=f"cancel_{transfer['job_id']}"):
                            st.warning("Cancel functionality would be implemented here")
            
        except Exception as e:
            st.error(f"Failed to load active transfers: {e}")
    
    def _render_transfer_history(self):
        """Render transfer history section"""
        try:
            all_transfers = data_transmission.get_all_transfers()
            completed_transfers = all_transfers.get("completed", [])
            failed_transfers = all_transfers.get("failed", [])
            
            # Combine recent transfers
            recent_transfers = completed_transfers[-20:] + failed_transfers[-10:]
            
            if not recent_transfers:
                st.info("No transfer history available")
                return
            
            # Create DataFrame
            df = pd.DataFrame(recent_transfers)
            
            # Format timestamps
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
            if 'completed_at' in df.columns:
                df['completed_at'] = pd.to_datetime(df['completed_at']).dt.strftime('%H:%M:%S')
            
            # Format bytes
            if 'bytes_transferred' in df.columns:
                df['bytes_transferred'] = df['bytes_transferred'].apply(
                    lambda x: f"{x/1024/1024:.1f} MB" if x > 0 else "0 B"
                )
            
            # Display transfers in tabs
            tab1, tab2 = st.tabs(["📋 Recent Transfers", "❌ Failed Transfers"])
            
            with tab1:
                if completed_transfers:
                    st.dataframe(
                        df[df['status'] == 'completed'][['job_id', 'transfer_type', 'source', 'target', 'status', 'bytes_transferred', 'created_at']],
                        use_container_width=True
                    )
                else:
                    st.info("No completed transfers")
            
            with tab2:
                if failed_transfers:
                    failed_df = df[df['status'] == 'failed']
                    st.dataframe(
                        failed_df[['job_id', 'transfer_type', 'source', 'target', 'status', 'error_message', 'created_at']],
                        use_container_width=True
                    )
                else:
                    st.info("No failed transfers")
            
        except Exception as e:
            st.error(f"Failed to load transfer history: {e}")
    
    def _render_transfer_statistics(self):
        """Render transfer statistics section"""
        try:
            all_transfers = data_transmission.get_all_transfers()
            stats = all_transfers.get("stats", {})
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📊 Transfer Statistics")
                
                # Basic stats
                st.metric("Total Bytes Transferred", f"{stats.get('total_bytes_transferred', 0)/1024/1024:.1f} MB")
                st.metric("Average Transfer Time", f"{stats.get('average_transfer_time', 0):.1f} seconds")
                
                if stats.get('last_transfer'):
                    last_transfer = pd.to_datetime(stats['last_transfer']).strftime('%Y-%m-%d %H:%M:%S')
                    st.metric("Last Transfer", last_transfer)
            
            with col2:
                st.markdown("#### 📈 Transfer by Type")
                
                # This would show breakdown by transfer type
                # For now, show placeholder
                transfer_types = ["models", "data", "results", "leaderboard", "config"]
                for transfer_type in transfer_types:
                    st.caption(f"{self.transfer_types[transfer_type]['icon']} {self.transfer_types[transfer_type]['name']}: N/A")
            
            # Transfer rate chart (placeholder)
            st.markdown("#### 📈 Transfer Rate Over Time")
            st.info("Transfer rate visualization would be implemented here")
            
        except Exception as e:
            st.error(f"Failed to load transfer statistics: {e}")

# Global instance
data_transmission_interface = DataTransmissionInterface()

def render_data_transmission_interface():
    """Render the data transmission interface"""
    data_transmission_interface.render_data_transmission_interface()
