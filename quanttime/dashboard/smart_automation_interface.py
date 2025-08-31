#!/usr/bin/env python3
"""
Smart Automation Interface for QuantTime Dashboard
Provides user-friendly controls for smart automation features
"""

import streamlit as st
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

logger = logging.getLogger(__name__)

def render_smart_automation_dashboard():
    """Render the smart automation dashboard page"""
    
    st.title("🤖 Smart Automation Control Center")
    st.markdown("*AI-powered automation to minimize manual tasks and maximize efficiency*")
    
    # Get smart automation manager
    try:
        from quanttime.core.smart_automation_manager import get_smart_automation_manager
        automation_manager = get_smart_automation_manager()
    except Exception as e:
        st.error(f"Failed to load smart automation manager: {e}")
        return
    
    # Top-level status
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if automation_manager.running:
            st.success("🟢 **Smart Automation**\n\nACTIVE")
        else:
            st.error("🔴 **Smart Automation**\n\nINACTIVE")
    
    with col2:
        discovered_count = len(automation_manager.discovered_nodes)
        st.metric("🔍 Discovered Nodes", discovered_count)
    
    with col3:
        healthy_nodes = sum(1 for health in automation_manager.health_cache.values() 
                          if health.get("overall_health") == "good")
        st.metric("💚 Healthy Nodes", healthy_nodes)
    
    with col4:
        cached_creds = len(automation_manager.ssh_key_manager.cached_credentials)
        st.metric("🔑 Cached Credentials", cached_creds)
    
    # Control Panel
    st.markdown("---")
    st.header("🎛️ Control Panel")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Start Smart Automation", disabled=automation_manager.running):
            automation_manager.start_smart_automation()
            st.success("Smart automation started!")
            st.rerun()
    
    with col2:
        if st.button("🛑 Stop Smart Automation", disabled=not automation_manager.running):
            automation_manager.stop_smart_automation()
            st.warning("Smart automation stopped!")
            st.rerun()
    
    # Smart Features Configuration
    st.markdown("---")
    st.header("⚙️ Smart Features Configuration")
    
    config = automation_manager.automation_config
    
    # Create tabs for different automation areas
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔍 Discovery & Detection", 
        "🔑 Credential Management", 
        "📊 Health & Monitoring", 
        "🚀 Deployment & Operations"
    ])
    
    with tab1:
        st.subheader("Network & Node Discovery")
        
        col1, col2 = st.columns(2)
        with col1:
            network_discovery = st.checkbox(
                "Enable Network Auto-Discovery",
                value=config["smart_features"]["network_auto_discovery"],
                help="Automatically scan for and configure QuantTime nodes on the network"
            )
        
        with col2:
            scan_interval = st.number_input(
                "Scan Interval (minutes)",
                min_value=1,
                max_value=60,
                value=config["automation_intervals"]["network_scan_minutes"],
                help="How often to scan for new nodes"
            )
        
        if st.button("🔍 Scan Network Now"):
            with st.spinner("Scanning network for QuantTime nodes..."):
                discovered = automation_manager.network_scanner.scan_for_quanttime_nodes()
                if discovered:
                    st.success(f"Found {len(discovered)} nodes!")
                    for node_id, node_info in discovered.items():
                        st.write(f"- **{node_id}**: {node_info['host']}")
                else:
                    st.info("No new nodes discovered")
        
        # Show discovered nodes
        if automation_manager.discovered_nodes:
            st.subheader("📡 Discovered Nodes")
            nodes_df = pd.DataFrame([
                {
                    "Node ID": node_id,
                    "Host": info["host"],
                    "Auto-Discovered": info.get("auto_discovered", False),
                    "Discovered At": info.get("discovered_at", "Unknown")
                }
                for node_id, info in automation_manager.discovered_nodes.items()
            ])
            st.dataframe(nodes_df, use_container_width=True)
    
    with tab2:
        st.subheader("SSH Credential Management")
        
        col1, col2 = st.columns(2)
        with col1:
            auto_ssh_setup = st.checkbox(
                "Auto SSH Key Setup",
                value=config["smart_features"]["auto_ssh_key_setup"],
                help="Automatically generate and manage SSH keys"
            )
        
        with col2:
            smart_cred_detection = st.checkbox(
                "Smart Credential Detection",
                value=config["smart_features"]["smart_credential_detection"],
                help="Automatically detect and cache working credentials"
            )
        
        # Show SSH key status
        ssh_manager = automation_manager.ssh_key_manager
        
        st.subheader("🔑 SSH Key Status")
        if ssh_manager.key_cache:
            for key_name, key_path in ssh_manager.key_cache.items():
                st.write(f"- **{key_name}**: `{key_path}`")
        else:
            st.warning("No SSH keys found")
        
        if st.button("🔑 Generate SSH Key"):
            key_path = ssh_manager._generate_ssh_key()
            if key_path:
                st.success(f"Generated SSH key: {key_path}")
                st.rerun()
        
        # Show cached credentials
        st.subheader("💾 Cached Credentials")
        if ssh_manager.cached_credentials:
            creds_df = pd.DataFrame([
                {
                    "Host": host,
                    "Type": creds["type"],
                    "Details": creds.get("username", "Key-based") if creds["type"] == "password" else "SSH Key"
                }
                for host, creds in ssh_manager.cached_credentials.items()
            ])
            st.dataframe(creds_df, use_container_width=True)
        else:
            st.info("No cached credentials")
    
    with tab3:
        st.subheader("Predictive Health Monitoring")
        
        col1, col2 = st.columns(2)
        with col1:
            predictive_monitoring = st.checkbox(
                "Enable Predictive Monitoring",
                value=config["smart_features"]["predictive_health_monitoring"],
                help="Use AI to predict and prevent system failures"
            )
        
        with col2:
            health_interval = st.number_input(
                "Health Check Interval (minutes)",
                min_value=1,
                max_value=30,
                value=config["automation_intervals"]["health_check_minutes"],
                help="How often to perform health checks"
            )
        
        # Health visualization
        if automation_manager.health_cache:
            st.subheader("📊 Node Health Overview")
            
            health_data = []
            for node_id, health in automation_manager.health_cache.items():
                health_data.append({
                    "Node": node_id,
                    "Overall Health": health.get("overall_health", "unknown"),
                    "CPU Trend": health.get("cpu_trend", "unknown"),
                    "Memory Trend": health.get("memory_trend", "unknown"),
                    "Prediction Confidence": health.get("prediction_confidence", 0),
                    "Last Check": health.get("timestamp", "Never")
                })
            
            if health_data:
                health_df = pd.DataFrame(health_data)
                st.dataframe(health_df, use_container_width=True)
                
                # Health trends chart
                fig = px.bar(
                    health_df, 
                    x="Node", 
                    y="Prediction Confidence",
                    title="Health Prediction Confidence by Node",
                    color="Overall Health",
                    color_discrete_map={
                        "good": "green",
                        "warning": "orange", 
                        "critical": "red",
                        "unknown": "gray"
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No health data available yet")
        
        # Alert thresholds
        st.subheader("⚠️ Alert Thresholds")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            cpu_threshold = st.slider(
                "CPU Warning (%)",
                min_value=50,
                max_value=95,
                value=config["thresholds"]["cpu_warning"],
                help="CPU usage threshold for warnings"
            )
        
        with col2:
            memory_threshold = st.slider(
                "Memory Warning (%)",
                min_value=50,
                max_value=95,
                value=config["thresholds"]["memory_warning"],
                help="Memory usage threshold for warnings"
            )
        
        with col3:
            latency_threshold = st.number_input(
                "Latency Warning (ms)",
                min_value=100,
                max_value=5000,
                value=config["thresholds"]["latency_warning_ms"],
                help="Network latency threshold for warnings"
            )
    
    with tab4:
        st.subheader("Zero-Touch Deployment & Operations")
        
        col1, col2 = st.columns(2)
        with col1:
            zero_touch_deployment = st.checkbox(
                "Enable Zero-Touch Deployment",
                value=config["smart_features"]["zero_touch_deployment"],
                help="Automatically deploy QuantTime to discovered nodes"
            )
        
        with col2:
            auto_troubleshooting = st.checkbox(
                "Enable Auto-Troubleshooting",
                value=config["smart_features"]["automated_troubleshooting"],
                help="Automatically detect and fix common issues"
            )
        
        # Auto-actions configuration
        st.subheader("🤖 Automated Actions")
        
        col1, col2 = st.columns(2)
        with col1:
            auto_restart = st.checkbox(
                "Auto-restart Unhealthy Services",
                value=config["auto_actions"]["restart_unhealthy_services"]
            )
            auto_scale = st.checkbox(
                "Auto-scale Ray Workers",
                value=config["auto_actions"]["auto_scale_ray_workers"]
            )
            optimize_resources = st.checkbox(
                "Optimize Resource Allocation",
                value=config["auto_actions"]["optimize_resource_allocation"]
            )
        
        with col2:
            auto_deploy = st.checkbox(
                "Auto-deploy Updates",
                value=config["auto_actions"]["auto_deploy_updates"]
            )
            clean_temp = st.checkbox(
                "Clean Temporary Files",
                value=config["auto_actions"]["clean_temp_files"]
            )
        
        # Manual actions
        st.subheader("🔧 Manual Actions")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🚀 Deploy to All Nodes"):
                st.info("Deploying to all discovered nodes...")
                # Implementation would trigger zero-touch deployment
        
        with col2:
            if st.button("🔧 Run Health Checks"):
                st.info("Running comprehensive health checks...")
                # Implementation would trigger health checks
        
        with col3:
            if st.button("🧹 Clean & Optimize"):
                st.info("Cleaning and optimizing all nodes...")
                # Implementation would trigger cleanup/optimization
    
    # Save configuration button
    st.markdown("---")
    if st.button("💾 Save Configuration"):
        # Update configuration with form values
        config["smart_features"]["network_auto_discovery"] = network_discovery
        config["smart_features"]["auto_ssh_key_setup"] = auto_ssh_setup
        config["smart_features"]["smart_credential_detection"] = smart_cred_detection
        config["smart_features"]["predictive_health_monitoring"] = predictive_monitoring
        config["smart_features"]["zero_touch_deployment"] = zero_touch_deployment
        config["smart_features"]["automated_troubleshooting"] = auto_troubleshooting
        
        config["automation_intervals"]["network_scan_minutes"] = scan_interval
        config["automation_intervals"]["health_check_minutes"] = health_interval
        
        config["thresholds"]["cpu_warning"] = cpu_threshold
        config["thresholds"]["memory_warning"] = memory_threshold
        config["thresholds"]["latency_warning_ms"] = latency_threshold
        
        config["auto_actions"]["restart_unhealthy_services"] = auto_restart
        config["auto_actions"]["auto_scale_ray_workers"] = auto_scale
        config["auto_actions"]["optimize_resource_allocation"] = optimize_resources
        config["auto_actions"]["auto_deploy_updates"] = auto_deploy
        config["auto_actions"]["clean_temp_files"] = clean_temp
        
        # Save to file
        config_file = Path(__file__).parent.parent.parent / "config" / "automation_config.json"
        config_file.parent.mkdir(exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        st.success("✅ Configuration saved!")
        st.rerun()


def render_automation_activity_log():
    """Render activity log for automation actions"""
    st.subheader("📋 Automation Activity Log")
    
    # Mock activity data (in production, this would come from the automation manager)
    activities = [
        {
            "timestamp": "2024-01-15 10:30:00",
            "action": "Node Discovery",
            "details": "Discovered new node: auto_100_69_154_70",
            "status": "success"
        },
        {
            "timestamp": "2024-01-15 10:25:00", 
            "action": "SSH Key Setup",
            "details": "Generated SSH key for automated connections",
            "status": "success"
        },
        {
            "timestamp": "2024-01-15 10:20:00",
            "action": "Health Check",
            "details": "Predictive analysis detected potential memory issue on r630xl",
            "status": "warning"
        },
        {
            "timestamp": "2024-01-15 10:15:00",
            "action": "Auto-deployment",
            "details": "Deployed QuantTime to auto_100_69_154_70",
            "status": "success"
        }
    ]
    
    # Display activities
    for activity in activities:
        status_icon = {
            "success": "✅",
            "warning": "⚠️", 
            "error": "❌",
            "info": "ℹ️"
        }.get(activity["status"], "📋")
        
        with st.expander(f"{status_icon} {activity['action']} - {activity['timestamp']}"):
            st.write(activity["details"])


if __name__ == "__main__":
    render_smart_automation_dashboard()
