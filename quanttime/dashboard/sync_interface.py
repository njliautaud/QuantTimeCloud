"""
Sync Interface for QuantTime Dashboard
Provides comprehensive Git + SFTP synchronization management
"""

import streamlit as st
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime

from quanttime.core.git_sync_manager import git_sync_manager
from quanttime.core.sftp_manager import sftp_manager

logger = logging.getLogger(__name__)


def render_sync_interface():
    """Render the comprehensive sync interface"""
    st.markdown("""
    # 🔄 QuantTime Sync Management
    
    Manage Git synchronization and SFTP file transfers across all nodes.
    """)
    
    # Initialize sync manager in session state
    if "git_sync_manager" not in st.session_state:
        st.session_state.git_sync_manager = git_sync_manager
    
    sync_manager = st.session_state.git_sync_manager
    
    # Create tabs for different sync operations
    sync_tabs = st.tabs([
        "🔐 GitHub PAT", 
        "🔄 Sync Operations", 
        "🔍 Discrepancy Detection", 
        "📊 Sync Status",
        "⚙️ Sync Settings"
    ])
    
    with sync_tabs[0]:
        render_github_pat_config(sync_manager)
    
    with sync_tabs[1]:
        render_sync_operations(sync_manager)
    
    with sync_tabs[2]:
        render_discrepancy_detection(sync_manager)
    
    with sync_tabs[3]:
        render_sync_status(sync_manager)
    
    with sync_tabs[4]:
        render_sync_settings(sync_manager)


def render_github_pat_config(sync_manager):
    """Render GitHub PAT configuration"""
    st.markdown("### 🔐 GitHub Personal Access Token Configuration")
    
    # Check if PAT is already configured
    current_pat = sync_manager.github_pat
    pat_status = "✅ Configured" if current_pat else "❌ Not Configured"
    
    st.info(f"**Current Status:** {pat_status}")
    
    if current_pat:
        st.success(f"GitHub PAT is configured and valid")
        if st.button("🔄 Test PAT Validity"):
            with st.spinner("Testing PAT validity..."):
                if sync_manager._test_github_pat():
                    st.success("✅ GitHub PAT is valid and working!")
                else:
                    st.error("❌ GitHub PAT is invalid or expired")
    
    # PAT configuration form
    with st.form("github_pat_config"):
        st.markdown("**Configure GitHub Personal Access Token:**")
        
        # Instructions
        st.markdown("""
        **To create a GitHub PAT:**
        1. Go to GitHub Settings → Developer settings → Personal access tokens
        2. Generate a new token with `repo` permissions
        3. Copy the token and paste it below
        """)
        
        new_pat = st.text_input(
            "GitHub Personal Access Token:",
            type="password",
            help="Enter your GitHub Personal Access Token for repository access"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            test_pat = st.form_submit_button("🧪 Test PAT")
        with col2:
            save_pat = st.form_submit_button("💾 Save PAT")
        
        if test_pat and new_pat:
            with st.spinner("Testing PAT..."):
                # Temporarily set PAT for testing
                original_pat = sync_manager.github_pat
                sync_manager.github_pat = new_pat
                
                if sync_manager._test_github_pat():
                    st.success("✅ PAT is valid! You can now save it.")
                else:
                    st.error("❌ PAT is invalid. Please check your token.")
                
                # Restore original PAT
                sync_manager.github_pat = original_pat
        
        if save_pat and new_pat:
            with st.spinner("Saving PAT..."):
                if sync_manager.set_github_pat(new_pat):
                    st.success("✅ GitHub PAT saved successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to save PAT. Please check if it's valid.")


def render_sync_operations(sync_manager):
    """Render sync operations interface"""
    st.markdown("### 🔄 Sync Operations")
    
    # Check if PAT is configured
    if not sync_manager.github_pat:
        st.warning("⚠️ Please configure GitHub PAT first in the 'GitHub PAT' tab.")
        return
    
    # Get connected nodes from session state
    connected_nodes = []
    if "node_status" in st.session_state:
        node_status = st.session_state.node_status
        connected_nodes = [node_id for node_id, status in node_status.items() 
                          if status.get("connected", False)]
    
    if not connected_nodes:
        st.warning("⚠️ No nodes are currently connected. Please connect to nodes first.")
        return
    
    st.success(f"✅ {len(connected_nodes)} node(s) connected: {', '.join(connected_nodes)}")
    
    # Sync operations
    st.markdown("#### 🚀 Sync Operations")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Sync All Nodes", type="primary"):
            perform_sync_all_nodes(sync_manager, connected_nodes)
    
    with col2:
        if st.button("🔍 Check All Discrepancies"):
            check_all_discrepancies(sync_manager, connected_nodes)
    
    with col3:
        if st.button("📊 Refresh Sync Status"):
            st.rerun()
    
    # Individual node sync
    st.markdown("#### 📋 Individual Node Sync")
    
    for node_id in connected_nodes:
        with st.expander(f"🖥️ {node_id.upper()} Sync Operations", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button(f"🔄 Git Sync", key=f"git_sync_{node_id}"):
                    perform_git_sync(sync_manager, node_id)
            
            with col2:
                if st.button(f"🔍 Check Discrepancies", key=f"check_discrepancies_{node_id}"):
                    check_node_discrepancies(sync_manager, node_id)
            
            with col3:
                if st.button(f"📁 SFTP Sync", key=f"sftp_sync_{node_id}"):
                    perform_sftp_sync(sync_manager, node_id)


def render_discrepancy_detection(sync_manager):
    """Render discrepancy detection interface"""
    st.markdown("### 🔍 Discrepancy Detection")
    
    # Check if PAT is configured
    if not sync_manager.github_pat:
        st.warning("⚠️ Please configure GitHub PAT first in the 'GitHub PAT' tab.")
        return
    
    # Get connected nodes
    connected_nodes = []
    if "node_status" in st.session_state:
        node_status = st.session_state.node_status
        connected_nodes = [node_id for node_id, status in node_status.items() 
                          if status.get("connected", False)]
    
    if not connected_nodes:
        st.warning("⚠️ No nodes are currently connected.")
        return
    
    # Discrepancy detection options
    st.markdown("#### 🔍 Detection Options")
    
    detection_types = st.multiselect(
        "Select discrepancy types to detect:",
        [
            "commit_mismatch",
            "local_changes", 
            "untracked_files",
            "large_files_not_synced",
            "missing_directories"
        ],
        default=["commit_mismatch", "local_changes", "large_files_not_synced"],
        help="Select which types of discrepancies to detect"
    )
    
    if st.button("🔍 Run Discrepancy Detection"):
        if detection_types:
            run_discrepancy_detection(sync_manager, connected_nodes, detection_types)
        else:
            st.warning("Please select at least one detection type.")
    
    # Display current discrepancies
    st.markdown("#### 📊 Current Discrepancies")
    
    if "sync_discrepancies" in st.session_state:
        discrepancies = st.session_state.sync_discrepancies
        
        if discrepancies:
            for node_id, node_discrepancies in discrepancies.items():
                if node_discrepancies:
                    with st.expander(f"🔍 {node_id.upper()} Discrepancies ({len(node_discrepancies)} found)", expanded=True):
                        for i, discrepancy in enumerate(node_discrepancies):
                            render_discrepancy_item(discrepancy, i, node_id)
        else:
            st.success("✅ No discrepancies found across all nodes!")
    else:
        st.info("No discrepancy detection has been run yet.")


def render_discrepancy_item(discrepancy: Dict, index: int, node_id: str):
    """Render a single discrepancy item"""
    discrepancy_type = discrepancy.get("type", "unknown")
    severity = discrepancy.get("severity", "medium")
    
    # Color coding based on severity
    if severity == "high":
        st.error(f"🔴 **{discrepancy_type.replace('_', ' ').title()}**")
    elif severity == "medium":
        st.warning(f"🟡 **{discrepancy_type.replace('_', ' ').title()}**")
    else:
        st.info(f"🔵 **{discrepancy_type.replace('_', ' ').title()}**")
    
    # Display discrepancy details
    if discrepancy_type == "commit_mismatch":
        st.markdown(f"- **Laptop Commit:** `{discrepancy.get('laptop_commit', 'Unknown')}`")
        st.markdown(f"- **Node Commit:** `{discrepancy.get('node_commit', 'Unknown')}`")
        
        if st.button(f"🔄 Fix Commit Mismatch", key=f"fix_commit_{node_id}_{index}"):
            fix_commit_mismatch(node_id)
    
    elif discrepancy_type == "local_changes":
        changes = discrepancy.get("changes", [])
        st.markdown(f"- **Local Changes:** {len(changes)} files modified")
        for change in changes[:5]:  # Show first 5 changes
            st.code(change)
        if len(changes) > 5:
            st.markdown(f"- *... and {len(changes) - 5} more changes*")
        
        if st.button(f"🔄 Reset Local Changes", key=f"reset_changes_{node_id}_{index}"):
            reset_local_changes(node_id)
    
    elif discrepancy_type == "large_files_not_synced":
        files = discrepancy.get("files", [])
        st.markdown(f"- **Large Files:** {len(files)} files need syncing")
        for file_info in files[:3]:  # Show first 3 files
            st.markdown(f"  - `{file_info.get('path', 'Unknown')}` ({file_info.get('size', 'Unknown')})")
        if len(files) > 3:
            st.markdown(f"- *... and {len(files) - 3} more files*")
        
        if st.button(f"📁 Sync Large Files", key=f"sync_files_{node_id}_{index}"):
            sync_large_files(node_id, files)
    
    elif discrepancy_type == "missing_directories":
        directories = discrepancy.get("directories", [])
        st.markdown(f"- **Missing Directories:** {len(directories)} directories")
        for directory in directories[:3]:  # Show first 3 directories
            st.markdown(f"  - `{directory}`")
        if len(directories) > 3:
            st.markdown(f"- *... and {len(directories) - 3} more directories*")
        
        if st.button(f"📁 Sync Directories", key=f"sync_dirs_{node_id}_{index}"):
            sync_missing_directories(node_id, directories)


def render_sync_status(sync_manager):
    """Render sync status dashboard"""
    st.markdown("### 📊 Sync Status Dashboard")
    
    # Get sync status
    sync_status = sync_manager.get_sync_status()
    
    # Overall status
    col1, col2, col3 = st.columns(3)
    
    with col1:
        pat_status = "✅ Configured" if sync_status["github_pat_configured"] else "❌ Not Configured"
        st.metric("GitHub PAT", pat_status)
    
    with col2:
        last_sync = sync_status["sync_status"].get("last_sync", "Never")
        if last_sync != "Never" and isinstance(last_sync, str):
            try:
                last_sync = datetime.fromisoformat(last_sync).strftime("%H:%M:%S")
            except (ValueError, TypeError):
                last_sync = str(last_sync)
        st.metric("Last Sync", last_sync)
    
    with col3:
        nodes_synced = len(sync_status["sync_status"].get("nodes_synced", []))
        st.metric("Nodes Synced", nodes_synced)
    
    # Detailed status
    st.markdown("#### 📋 Detailed Status")
    
    # Connected nodes status
    if "node_status" in st.session_state:
        node_status = st.session_state.node_status
        
        for node_id, status in node_status.items():
            if status.get("connected", False):
                with st.expander(f"🖥️ {node_id.upper()} Status", expanded=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**Connection:** {'✅ Connected' if status.get('connected') else '❌ Disconnected'}")
                        st.markdown(f"**Status:** {status.get('status', 'Unknown')}")
                    
                    with col2:
                        # Get sync info if available
                        if "sync_info" in status:
                            sync_info = status["sync_info"]
                            st.markdown(f"**Commit:** `{sync_info.get('commit_hash', 'Unknown')[:8]}`")
                            st.markdown(f"**Branch:** {sync_info.get('current_branch', 'Unknown')}")
                        
                        # Check if node is in synced list
                        is_synced = node_id in sync_status["sync_status"].get("nodes_synced", [])
                        st.markdown(f"**Synced:** {'✅ Yes' if is_synced else '❌ No'}")
    
    # Sync errors
    sync_errors = sync_status["sync_status"].get("sync_errors", [])
    if sync_errors:
        st.markdown("#### ❌ Sync Errors")
        for error in sync_errors:
            st.error(error)


def render_sync_settings(sync_manager):
    """Render sync settings"""
    st.markdown("### ⚙️ Sync Settings")
    
    # Auto-sync settings
    st.markdown("#### 🔄 Auto-Sync Settings")
    
    auto_sync_enabled = st.checkbox(
        "Enable Auto-Sync",
        value=st.session_state.get("auto_sync_enabled", False),
        help="Automatically sync nodes when discrepancies are detected"
    )
    st.session_state.auto_sync_enabled = auto_sync_enabled
    
    if auto_sync_enabled:
        sync_interval = st.slider(
            "Sync Interval (minutes)",
            min_value=5,
            max_value=60,
            value=st.session_state.get("sync_interval", 15),
            help="How often to check for and sync discrepancies"
        )
        st.session_state.sync_interval = sync_interval
    
    # Sync preferences
    st.markdown("#### 📋 Sync Preferences")
    
    sync_preferences = st.multiselect(
        "Sync Operations to Perform:",
        [
            "git_pull",
            "large_files",
            "missing_directories",
            "local_changes_reset"
        ],
        default=st.session_state.get("sync_preferences", ["git_pull", "large_files"]),
        help="Select which sync operations to perform automatically"
    )
    st.session_state.sync_preferences = sync_preferences
    
    # File size threshold
    file_size_threshold = st.number_input(
        "Large File Threshold (MB)",
        min_value=1,
        max_value=1000,
        value=st.session_state.get("file_size_threshold", 10),
        help="Files larger than this size will be considered 'large files'"
    )
    st.session_state.file_size_threshold = file_size_threshold
    
    # Save settings
    if st.button("💾 Save Settings"):
        st.success("✅ Sync settings saved!")


# Sync operation functions
def perform_sync_all_nodes(sync_manager, connected_nodes):
    """Perform sync on all connected nodes"""
    st.info(f"🔄 Starting sync for {len(connected_nodes)} nodes...")
    
    results = {}
    
    for node_id in connected_nodes:
        with st.spinner(f"Syncing {node_id}..."):
            # Get SSH connection from SFTP manager
            ssh_client = sftp_manager._get_ssh_connection(node_id)
            if ssh_client:
                success, message, sync_result = sync_manager.perform_full_sync(node_id, ssh_client)
                results[node_id] = {
                    "success": success,
                    "message": message,
                    "result": sync_result
                }
                ssh_client.close()
            else:
                results[node_id] = {
                    "success": False,
                    "message": "No SSH connection available",
                    "result": {}
                }
    
    # Display results
    st.markdown("#### 📊 Sync Results")
    for node_id, result in results.items():
        if result["success"]:
            st.success(f"✅ {node_id}: {result['message']}")
            if result["result"].get("files_synced", 0) > 0:
                st.info(f"   📁 Synced {result['result']['files_synced']} files")
            if result["result"].get("directories_synced", 0) > 0:
                st.info(f"   📁 Synced {result['result']['directories_synced']} directories")
        else:
            st.error(f"❌ {node_id}: {result['message']}")


def perform_git_sync(sync_manager, node_id):
    """Perform Git sync for a specific node"""
    with st.spinner(f"🔄 Syncing {node_id} with GitHub..."):
        ssh_client = sftp_manager._get_ssh_connection(node_id)
        if ssh_client:
            success, message, sync_info = sync_manager.sync_node_with_github(node_id, ssh_client)
            ssh_client.close()
            
            if success:
                st.success(f"✅ {message}")
                if sync_info:
                    st.info(f"📋 Commit: {sync_info.get('commit_hash', 'Unknown')[:8]}")
                    st.info(f"📋 Branch: {sync_info.get('current_branch', 'Unknown')}")
            else:
                st.error(f"❌ {message}")
        else:
            st.error(f"❌ No SSH connection available for {node_id}")


def check_all_discrepancies(sync_manager, connected_nodes):
    """Check discrepancies for all connected nodes"""
    st.info(f"🔍 Checking discrepancies for {len(connected_nodes)} nodes...")
    
    all_discrepancies = {}
    
    for node_id in connected_nodes:
        with st.spinner(f"Checking {node_id}..."):
            ssh_client = sftp_manager._get_ssh_connection(node_id)
            if ssh_client:
                success, discrepancies = sync_manager.detect_sync_discrepancies(node_id, ssh_client)
                ssh_client.close()
                
                if success:
                    all_discrepancies[node_id] = discrepancies
                else:
                    all_discrepancies[node_id] = [{"type": "error", "message": "Failed to detect discrepancies"}]
            else:
                all_discrepancies[node_id] = [{"type": "error", "message": "No SSH connection available"}]
    
    # Store in session state
    st.session_state.sync_discrepancies = all_discrepancies
    
    # Display summary
    total_discrepancies = sum(len(discs) for discs in all_discrepancies.values())
    st.success(f"🔍 Discrepancy detection completed! Found {total_discrepancies} discrepancies across {len(connected_nodes)} nodes.")


def check_node_discrepancies(sync_manager, node_id):
    """Check discrepancies for a specific node"""
    with st.spinner(f"🔍 Checking discrepancies for {node_id}..."):
        ssh_client = sftp_manager._get_ssh_connection(node_id)
        if ssh_client:
            success, discrepancies = sync_manager.detect_sync_discrepancies(node_id, ssh_client)
            ssh_client.close()
            
            if success:
                if discrepancies:
                    st.warning(f"🔍 Found {len(discrepancies)} discrepancies for {node_id}")
                    for discrepancy in discrepancies:
                        render_discrepancy_item(discrepancy, 0, node_id)
                else:
                    st.success(f"✅ No discrepancies found for {node_id}")
            else:
                st.error(f"❌ Failed to detect discrepancies for {node_id}")
        else:
            st.error(f"❌ No SSH connection available for {node_id}")


def perform_sftp_sync(sync_manager, node_id):
    """Perform SFTP sync for a specific node"""
    with st.spinner(f"📁 Performing SFTP sync for {node_id}..."):
        ssh_client = sftp_manager._get_ssh_connection(node_id)
        if ssh_client:
            # First detect discrepancies
            success, discrepancies = sync_manager.detect_sync_discrepancies(node_id, ssh_client)
            
            if success and discrepancies:
                files_synced = 0
                directories_synced = 0
                
                for discrepancy in discrepancies:
                    if discrepancy["type"] == "large_files_not_synced":
                        if sync_manager.sync_large_files_via_sftp(node_id, ssh_client, discrepancy["files"]):
                            files_synced += len(discrepancy["files"])
                    
                    elif discrepancy["type"] == "missing_directories":
                        if sync_manager.sync_missing_directories_via_sftp(node_id, ssh_client, discrepancy["directories"]):
                            directories_synced += len(discrepancy["directories"])
                
                ssh_client.close()
                
                if files_synced > 0 or directories_synced > 0:
                    st.success(f"✅ SFTP sync completed for {node_id}")
                    if files_synced > 0:
                        st.info(f"📁 Synced {files_synced} files")
                    if directories_synced > 0:
                        st.info(f"📁 Synced {directories_synced} directories")
                else:
                    st.info(f"ℹ️ No files or directories needed syncing for {node_id}")
            else:
                ssh_client.close()
                st.success(f"✅ No discrepancies found for {node_id}")
        else:
            st.error(f"❌ No SSH connection available for {node_id}")


# Discrepancy fix functions
def fix_commit_mismatch(node_id):
    """Fix commit mismatch by pulling latest changes"""
    with st.spinner(f"🔄 Fixing commit mismatch for {node_id}..."):
        ssh_client = sftp_manager._get_ssh_connection(node_id)
        if ssh_client:
            success, message, sync_info = sync_manager.sync_node_with_github(node_id, ssh_client)
            ssh_client.close()
            
            if success:
                st.success(f"✅ Commit mismatch fixed for {node_id}")
            else:
                st.error(f"❌ Failed to fix commit mismatch for {node_id}: {message}")
        else:
            st.error(f"❌ No SSH connection available for {node_id}")


def reset_local_changes(node_id):
    """Reset local changes on node"""
    with st.spinner(f"🔄 Resetting local changes for {node_id}..."):
        ssh_client = sftp_manager._get_ssh_connection(node_id)
        if ssh_client:
            cmd = "cd /opt/quanttime && git reset --hard HEAD && git clean -fd"
            stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=30)
            exit_status = stdout.channel.recv_exit_status()
            ssh_client.close()
            
            if exit_status == 0:
                st.success(f"✅ Local changes reset for {node_id}")
            else:
                st.error(f"❌ Failed to reset local changes for {node_id}")
        else:
            st.error(f"❌ No SSH connection available for {node_id}")


def sync_large_files(node_id, files):
    """Sync large files to node"""
    with st.spinner(f"📁 Syncing {len(files)} large files to {node_id}..."):
        ssh_client = sftp_manager._get_ssh_connection(node_id)
        if ssh_client:
            success = sync_manager.sync_large_files_via_sftp(node_id, ssh_client, files)
            ssh_client.close()
            
            if success:
                st.success(f"✅ Successfully synced {len(files)} files to {node_id}")
            else:
                st.error(f"❌ Failed to sync files to {node_id}")
        else:
            st.error(f"❌ No SSH connection available for {node_id}")


def sync_missing_directories(node_id, directories):
    """Sync missing directories to node"""
    with st.spinner(f"📁 Syncing {len(directories)} directories to {node_id}..."):
        ssh_client = sftp_manager._get_ssh_connection(node_id)
        if ssh_client:
            success = sync_manager.sync_missing_directories_via_sftp(node_id, ssh_client, directories)
            ssh_client.close()
            
            if success:
                st.success(f"✅ Successfully synced {len(directories)} directories to {node_id}")
            else:
                st.error(f"❌ Failed to sync directories to {node_id}")
        else:
            st.error(f"❌ No SSH connection available for {node_id}")


def run_discrepancy_detection(sync_manager, connected_nodes, detection_types):
    """Run discrepancy detection with specified types"""
    st.info(f"🔍 Running discrepancy detection for {len(connected_nodes)} nodes...")
    
    all_discrepancies = {}
    
    for node_id in connected_nodes:
        with st.spinner(f"Checking {node_id}..."):
            ssh_client = sftp_manager._get_ssh_connection(node_id)
            if ssh_client:
                success, discrepancies = sync_manager.detect_sync_discrepancies(node_id, ssh_client)
                ssh_client.close()
                
                if success:
                    # Filter by detection types
                    filtered_discrepancies = [
                        d for d in discrepancies 
                        if d.get("type") in detection_types
                    ]
                    all_discrepancies[node_id] = filtered_discrepancies
                else:
                    all_discrepancies[node_id] = [{"type": "error", "message": "Failed to detect discrepancies"}]
            else:
                all_discrepancies[node_id] = [{"type": "error", "message": "No SSH connection available"}]
    
    # Store in session state
    st.session_state.sync_discrepancies = all_discrepancies
    
    # Display summary
    total_discrepancies = sum(len(discs) for discs in all_discrepancies.values())
    st.success(f"🔍 Discrepancy detection completed! Found {total_discrepancies} discrepancies across {len(connected_nodes)} nodes.")
