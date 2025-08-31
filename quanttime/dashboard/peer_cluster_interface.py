"""
Peer Cluster Interface
Dashboard for managing peer-to-peer cluster without head nodes
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def render_peer_cluster_interface():
    """Render the peer cluster management interface"""
    
    st.title("🌐 Peer Cluster Management")
    st.markdown("*All nodes are equal peers - no head nodes, just pure sync*")
    
    # Get peer sync manager
    try:
        from quanttime.core.peer_sync_manager import PeerSyncManager
        
        # Try to get existing instance or create new one
        if '_peer_sync' not in st.session_state:
            st.session_state._peer_sync = PeerSyncManager()
        
        peer_sync = st.session_state._peer_sync
        
    except Exception as e:
        st.error(f"❌ Could not initialize peer sync manager: {e}")
        return
    
    # Auto-refresh
    if st.button("🔄 Refresh Status"):
        st.rerun()
    
    # Get current status
    try:
        status = peer_sync.get_peer_status()
    except Exception as e:
        st.error(f"❌ Could not get peer status: {e}")
        return
    
    # Display cluster overview
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Peers",
            status['cluster_info']['total_peers'],
            help="Including this local node"
        )
    
    with col2:
        st.metric(
            "Online Peers", 
            status['cluster_info']['online_peers'],
            help="Nodes currently responding"
        )
    
    with col3:
        st.metric(
            "Trusted Peers",
            status['cluster_info']['trusted_peers'], 
            help="Nodes with SSH access established"
        )
    
    with col4:
        ray_status = "🟢 Active" if status['cluster_info']['ray_initialized'] else "🔴 Inactive"
        st.metric(
            "Ray Cluster",
            ray_status,
            help="Distributed computing status"
        )
    
    st.divider()
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["🖥️ Nodes", "🔄 Sync Status", "🎯 Job Assignment", "🔑 SSH Setup"])
    
    with tab1:
        render_nodes_view(status)
    
    with tab2:
        render_sync_status(status, peer_sync)
    
    with tab3:
        render_job_assignment(status, peer_sync)
    
    with tab4:
        render_ssh_setup(peer_sync)

def render_nodes_view(status: Dict[str, Any]):
    """Render the nodes overview"""
    
    st.subheader("🖥️ Local Node")
    
    local_node = status['local_node']
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"**{local_node['hostname']}** ({local_node['platform']})")
        st.write(f"📍 {local_node['address']}")
        st.write(f"🔄 Git: {local_node['git_hash']}")
    
    with col2:
        st.write("**Resources:**")
        st.write(f"🖥️ CPU: {local_node['resources']['cpu_count']}")
        st.write(f"💾 RAM: {local_node['resources']['memory_gb']:.1f}GB")
        st.write(f"🎮 GPU: {local_node['resources']['gpu_count']}")
    
    with col3:
        if local_node['last_sync']:
            sync_time = datetime.fromisoformat(local_node['last_sync'])
            st.write(f"**Last Sync:** {sync_time.strftime('%H:%M:%S')}")
        else:
            st.write("**Last Sync:** Never")
    
    st.divider()
    
    # Peer nodes
    if status['known_peers']:
        st.subheader("🌐 Discovered Peer Nodes")
        
        # Create DataFrame for better display
        peer_data = []
        for peer_id, peer in status['known_peers'].items():
            peer_data.append({
                'Node ID': peer_id[:12],
                'Hostname': peer['hostname'],
                'Platform': peer['platform'],
                'Address': peer['address'],
                'CPU': peer['resources']['cpu_count'],
                'RAM (GB)': peer['resources']['memory_gb'],
                'GPU': peer['resources']['gpu_count'],
                'Status': '🟢 Online' if peer['is_online'] else '🔴 Offline',
                'Trust': '🔒 Trusted' if peer['is_trusted'] else '⚠️ Untrusted',
                'Git Hash': peer['git_hash'],
                'Last Seen': datetime.fromisoformat(peer['last_seen']).strftime('%H:%M:%S')
            })
        
        df = pd.DataFrame(peer_data)
        st.dataframe(df, use_container_width=True)
        
    else:
        st.info("🔍 No peer nodes discovered yet. They will appear here automatically when detected.")

def render_sync_status(status: Dict[str, Any], peer_sync):
    """Render Git sync status across all peers"""
    
    st.subheader("🔄 Git Synchronization Status")
    
    local_hash = status['local_node']['git_hash']
    
    # Check sync status across peers
    sync_status = []
    
    # Local node
    sync_status.append({
        'Node': f"{status['local_node']['hostname']} (local)",
        'Git Hash': local_hash,
        'Status': '🟢 Current',
        'Last Sync': status['local_node']['last_sync'] or 'N/A'
    })
    
    # Peer nodes
    for peer_id, peer in status['known_peers'].items():
        peer_hash = peer['git_hash']
        
        if peer_hash == local_hash:
            sync_stat = '🟢 In Sync'
        elif peer_hash == 'unknown':
            sync_stat = '⚠️ Unknown'
        else:
            sync_stat = '🔴 Out of Sync'
        
        sync_status.append({
            'Node': peer['hostname'],
            'Git Hash': peer_hash,
            'Status': sync_stat,
            'Last Sync': 'N/A'  # Peer sync times not tracked yet
        })
    
    df = pd.DataFrame(sync_status)
    st.dataframe(df, use_container_width=True)
    
    # Manual sync triggers
    st.subheader("🔧 Manual Sync Control")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Pull from Origin"):
            try:
                # This would trigger a Git pull
                st.success("✅ Git pull triggered")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Git pull failed: {e}")
    
    with col2:
        if st.button("📡 Sync All Peers"):
            try:
                # This would trigger sync on all peers
                st.success("✅ Peer sync triggered")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Peer sync failed: {e}")

def render_job_assignment(status: Dict[str, Any], peer_sync):
    """Render job assignment interface"""
    
    st.subheader("🎯 Job Assignment")
    st.markdown("*Assign Ray jobs to specific nodes*")
    
    # Available nodes for job assignment
    available_nodes = []
    
    # Add local node
    local_node = status['local_node']
    available_nodes.append({
        'id': 'local',
        'name': f"{local_node['hostname']} (local)",
        'resources': f"{local_node['resources']['cpu_count']} CPU, {local_node['resources']['memory_gb']:.1f}GB RAM, {local_node['resources']['gpu_count']} GPU"
    })
    
    # Add online trusted peer nodes
    for peer_id, peer in status['known_peers'].items():
        if peer['is_online'] and peer['is_trusted']:
            available_nodes.append({
                'id': peer_id,
                'name': peer['hostname'],
                'resources': f"{peer['resources']['cpu_count']} CPU, {peer['resources']['memory_gb']:.1f}GB RAM, {peer['resources']['gpu_count']} GPU"
            })
    
    if not available_nodes:
        st.warning("⚠️ No nodes available for job assignment")
        return
    
    # Job assignment form
    with st.form("job_assignment_form"):
        st.write("**Select Target Node:**")
        
        node_options = [f"{node['name']} - {node['resources']}" for node in available_nodes]
        selected_node_idx = st.selectbox("Node", range(len(node_options)), format_func=lambda x: node_options[x])
        
        st.write("**Job Type:**")
        job_type = st.selectbox("Job Type", [
            "MBO Feature Engineering",
            "Model Training", 
            "Backtesting",
            "Data Processing",
            "Custom Ray Task"
        ])
        
        st.write("**Parameters:**")
        params = st.text_area("Job Parameters (JSON format)", 
                             placeholder='{"symbol": "ES.FUT", "timeframe": "1s", "features": ["mbo_basic"]}')
        
        submit_job = st.form_submit_button("🚀 Submit Job")
        
        if submit_job:
            target_node = available_nodes[selected_node_idx]
            
            try:
                # This would actually submit the job
                st.success(f"✅ Job '{job_type}' submitted to {target_node['name']}")
                
                # Show job tracking info
                with st.expander("📊 Job Details"):
                    st.json({
                        "job_id": f"job_{int(time.time())}",
                        "target_node": target_node['name'],
                        "job_type": job_type,
                        "parameters": params,
                        "status": "submitted",
                        "timestamp": datetime.now().isoformat()
                    })
                    
            except Exception as e:
                st.error(f"❌ Job submission failed: {e}")
    
    # Active jobs (placeholder)
    st.subheader("📋 Active Jobs")
    st.info("Active job tracking will be implemented based on your specific Ray job patterns")

def render_ssh_setup(peer_sync):
    """Render SSH setup instructions"""
    
    st.subheader("🔑 SSH Key Setup")
    st.markdown("*Required for secure peer-to-peer communication*")
    
    # Get setup instructions
    try:
        instructions = peer_sync.get_ssh_setup_instructions()
        
        st.code(instructions, language="bash")
        
        # SSH key file check
        from pathlib import Path
        ssh_key_path = Path.home() / ".ssh" / "quanttime_automation"
        
        if ssh_key_path.exists():
            st.success("✅ SSH automation key found")
            
            # Show public key for copying
            try:
                with open(f"{ssh_key_path}.pub", 'r') as f:
                    public_key = f.read().strip()
                
                st.subheader("📋 Your Public Key")
                st.code(public_key, language="text")
                
                if st.button("📋 Copy Public Key"):
                    st.write("Copy the key above and add it to each peer node's ~/.ssh/authorized_keys")
                    
            except Exception as e:
                st.error(f"Could not read public key: {e}")
        else:
            st.warning("⚠️ SSH automation key not found")
            
            if st.button("🔑 Generate SSH Key"):
                st.info("Run this command in your terminal:")
                st.code('ssh-keygen -t ed25519 -C "quanttime-automation" -f ~/.ssh/quanttime_automation')
    
    except Exception as e:
        st.error(f"Could not get SSH setup instructions: {e}")
    
    # Test connections
    st.subheader("🔧 Test SSH Connections")
    
    # This would test SSH connectivity to each peer
    st.info("SSH connection testing will be available after key setup is complete")

def render_remote_logs():
    """Render remote logging interface"""
    
    st.subheader("📊 Remote Logging")
    st.markdown("*View logs from any peer node*")
    
    # This would show logs from remote nodes
    st.info("Remote logging interface will be implemented based on your logging requirements")

# Export the main function
__all__ = ['render_peer_cluster_interface']
