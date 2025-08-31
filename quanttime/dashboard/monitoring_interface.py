#!/usr/bin/env python3
"""
Monitoring Interface - Embeds Prometheus/Grafana into main dashboard
"""

import streamlit as st
import requests
import json
import time
from datetime import datetime, timedelta
import subprocess
import logging

logger = logging.getLogger(__name__)

class MonitoringInterface:
    """Integrates Prometheus/Grafana monitoring into main dashboard"""
    
    def __init__(self):
        self.grafana_url = "http://localhost:3000"
        self.prometheus_url = "http://localhost:9090"
        self.grafana_user = "admin"
        self.grafana_password = "REDACTED_GRAFANA_ADMIN_PASSWORD"
        
    def check_monitoring_status(self):
        """Check if monitoring services are running"""
        try:
            # Check Grafana
            grafana_response = requests.get(f"{self.grafana_url}/api/health", timeout=5)
            grafana_ok = grafana_response.status_code == 200
            
            # Check Prometheus
            prometheus_response = requests.get(f"{self.prometheus_url}/-/healthy", timeout=5)
            prometheus_ok = prometheus_response.status_code == 200
            
            return grafana_ok, prometheus_ok
        except Exception as e:
            logger.error(f"Error checking monitoring status: {e}")
            return False, False
    
    def start_monitoring_services(self):
        """Start monitoring services if not running"""
        try:
            subprocess.run([
                'python', 'start_monitoring.py', 'start'
            ], check=True, capture_output=True, text=True)
            st.success("✅ Monitoring services started!")
            time.sleep(5)  # Wait for services to fully start
            return True
        except subprocess.CalledProcessError as e:
            st.error(f"❌ Failed to start monitoring: {e}")
            return False
    
    def get_node_metrics(self):
        """Get basic node metrics from Prometheus"""
        try:
            # Get node status
            status_query = 'up{job="quanttime-nodes"}'
            status_response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={'query': status_query}
            )
            
            if status_response.status_code == 200:
                data = status_response.json()
                return data.get('data', {}).get('result', [])
            return []
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return []
    
    def render_monitoring_tab(self):
        """Render monitoring tab in main dashboard"""
        st.header("📊 System Monitoring")
        
        # Check if monitoring is running
        grafana_ok, prometheus_ok = self.check_monitoring_status()
        
        if not (grafana_ok and prometheus_ok):
            st.warning("⚠️ Monitoring services not running")
            if st.button("🚀 Start Monitoring Services"):
                if self.start_monitoring_services():
                    st.rerun()
            return
        
        # Monitoring is running - show embedded dashboard
        st.success("✅ Monitoring services running")
        
        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["📈 Live Metrics", "📊 Grafana Dashboard", "⚙️ Monitoring Config"])
        
        with tab1:
            self._render_live_metrics()
        
        with tab2:
            self._render_grafana_embed()
        
        with tab3:
            self._render_monitoring_config()
    
    def _render_live_metrics(self):
        """Render live metrics from Prometheus"""
        st.subheader("Live Node Metrics")
        
        # Get current metrics
        metrics = self.get_node_metrics()
        
        if not metrics:
            st.info("No metrics available yet. Nodes may be offline.")
            return
        
        # Display node status
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Active Nodes", len(metrics))
        
        with col2:
            st.metric("Monitoring Status", "🟢 Active")
        
        # Node details
        st.subheader("Node Status")
        for metric in metrics:
            node = metric['metric'].get('instance', 'Unknown')
            status = "🟢 Online" if metric['value'][1] == '1' else "🔴 Offline"
            
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(f"**{node}**")
            with col2:
                st.write(status)
            with col3:
                if st.button(f"Details", key=f"details_{node}"):
                    st.info(f"Detailed metrics for {node} would appear here")
        
        # Auto-refresh
        if st.button("🔄 Refresh Metrics"):
            st.rerun()
    
    def _render_grafana_embed(self):
        """Embed Grafana dashboard"""
        st.subheader("Grafana Dashboard")
        
        # Create iframe for Grafana
        grafana_embed_url = f"{self.grafana_url}/d/quanttime-overview/quanttime-overview?orgId=1&refresh=10s&theme=dark"
        
        st.components.v1.iframe(
            grafana_embed_url,
            height=600,
            scrolling=True
        )
        
        # Quick actions
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🌐 Open Grafana Full Screen"):
                st.markdown(f"[Open Grafana Dashboard]({self.grafana_url})")
        
        with col2:
            if st.button("📊 Open Prometheus"):
                st.markdown(f"[Open Prometheus]({self.prometheus_url})")
    
    def _render_monitoring_config(self):
        """Render monitoring configuration"""
        st.subheader("Monitoring Configuration")
        
        # Service status
        grafana_ok, prometheus_ok = self.check_monitoring_status()
        
        col1, col2 = st.columns(2)
        with col1:
            status = "🟢 Running" if grafana_ok else "🔴 Stopped"
            st.metric("Grafana", status)
        
        with col2:
            status = "🟢 Running" if prometheus_ok else "🔴 Stopped"
            st.metric("Prometheus", status)
        
        # Configuration options
        st.subheader("Configuration")
        
        if st.button("🔄 Restart Monitoring"):
            if self.start_monitoring_services():
                st.success("Monitoring restarted!")
                st.rerun()
        
        if st.button("🛑 Stop Monitoring"):
            try:
                subprocess.run(['python', 'start_monitoring.py', 'stop'], check=True)
                st.success("Monitoring stopped!")
                st.rerun()
            except subprocess.CalledProcessError as e:
                st.error(f"Failed to stop monitoring: {e}")

# Global instance
monitoring_interface = MonitoringInterface()
