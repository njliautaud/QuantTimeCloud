#!/usr/bin/env python3
"""
Configuration Wizard for QuantTime Dashboard
Handles initial setup and configuration through the UI
"""

import streamlit as st
import json
import os
import subprocess
from pathlib import Path
import sys

def run_command(command, cwd=None, check=True):
    """Run a shell command"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr

def get_tailscale_ip():
    """Get Tailscale IP address"""
    success, output, error = run_command("tailscale ip", check=False)
    if success and output.strip():
        # Return the first IPv4 address
        for line in output.strip().split('\n'):
            if line and '.' in line:  # IPv4 address
                return line.strip()
    return None

def check_git_repo():
    """Check if current directory is a Git repository"""
    git_dir = Path(".git")
    if not git_dir.exists():
        return False, "Not a Git repository"
    
    success, output, error = run_command("git remote get-url origin", check=False)
    if not success:
        return False, "No remote origin configured"
    
    return True, output

def setup_git_repo(remote_url):
    """Setup Git repository"""
    if not Path(".git").exists():
        success, output, error = run_command("git init")
        if not success:
            return False, f"Failed to initialize Git: {error}"
        
        success, output, error = run_command("git add .")
        if not success:
            return False, f"Failed to add files: {error}"
        
        success, output, error = run_command('git commit -m "Initial commit - QuantTime setup"')
        if not success:
            return False, f"Failed to create initial commit: {error}"
    
    if remote_url:
        success, output, error = run_command(f"git remote add origin {remote_url}")
        if not success:
            return False, f"Failed to add remote: {error}"
        
        success, output, error = run_command("git push -u origin main")
        if not success:
            return False, f"Failed to push to remote: {error}"
    
    return True, "Git repository configured successfully"

def create_sftp_config(nodes_config):
    """Create SFTP configuration file"""
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    config = {
        "nodes": nodes_config,
        "sync_settings": {
            "max_file_size_mb": 100,
            "sync_interval_minutes": 5,
            "retry_attempts": 3,
            "chunk_size_mb": 10,
            "parallel_transfers": 4
        },
        "large_file_dirs": [
            "data/es_futures",
            "data/processed",
            "models",
            "backtest/results",
            "logs"
        ]
    }
    
    config_file = config_dir / "sftp_config.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    return True, f"SFTP config created at {config_file}"

def create_ray_config(ray_settings):
    """Create Ray configuration file"""
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    config = {
        "head_node": {
            "host": ray_settings["head_host"],
            "port": ray_settings["head_port"],
            "dashboard_port": ray_settings["dashboard_port"]
        },
        "worker_nodes": ray_settings["worker_nodes"],
        "resources": {
            "cpu_per_node": ray_settings["cpu_per_node"],
            "gpu_per_node": ray_settings["gpu_per_node"],
            "memory_gb_per_node": ray_settings["memory_gb_per_node"]
        },
        "job_settings": {
            "max_concurrent_jobs": ray_settings["max_concurrent_jobs"],
            "job_timeout_minutes": ray_settings["job_timeout_minutes"]
        }
    }
    
    config_file = config_dir / "ray_config.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    return True, f"Ray config created at {config_file}"

def render_config_wizard():
    """Render the configuration wizard"""
    st.set_page_config(
        page_title="QuantTime Setup Wizard",
        page_icon="⚙️",
        layout="wide"
    )
    
    st.title("🚀 QuantTime Setup Wizard")
    st.markdown("Configure your QuantTime environment for distributed computing")
    
    # Check if already configured
    if Path("config/sftp_config.json").exists() and Path("config/ray_config.json").exists():
        st.success("✅ Configuration already exists!")
        if st.button("Continue to Dashboard"):
            st.session_state.config_complete = True
            st.rerun()
        if st.button("Reconfigure"):
            st.session_state.config_complete = False
            st.rerun()
        return
    
    # Wizard steps
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 1
    
    # Step 1: Git Repository Setup
    if st.session_state.wizard_step == 1:
        st.header("📁 Step 1: Git Repository Setup")
        
        is_repo, remote = check_git_repo()
        
        if is_repo:
            st.success(f"✅ Git repository found: {remote}")
        else:
            st.warning("⚠️ No Git repository detected")
        
        git_remote = st.text_input(
            "GitHub Repository URL (optional):",
            value="",
            help="Enter your GitHub repository URL to enable code synchronization"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Skip Git Setup"):
                st.session_state.wizard_step = 2
                st.rerun()
        
        with col2:
            if st.button("Setup Git Repository"):
                with st.spinner("Setting up Git repository..."):
                    success, message = setup_git_repo(git_remote)
                    if success:
                        st.success(message)
                        st.session_state.wizard_step = 2
                        st.rerun()
                    else:
                        st.error(message)
    
    # Step 2: Node Configuration
    elif st.session_state.wizard_step == 2:
        st.header("🖥️ Step 2: Node Configuration")
        
        # Get Tailscale IP
        tailscale_ip = get_tailscale_ip()
        if tailscale_ip:
            st.info(f"🔍 Detected Tailscale IP: {tailscale_ip}")
        
        st.subheader("Laptop (Head Node)")
        laptop_host = st.text_input(
            "Laptop Hostname/IP:",
            value=tailscale_ip or "localhost",
            help="IP address other nodes will use to connect to your laptop"
        )
        laptop_username = st.text_input(
            "Laptop Username:",
            value="user",
            help="Your Windows username"
        )
        
        st.subheader("Server Nodes")
        
        # R630XL
        st.markdown("**R630XL Server:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            r630xl_host = st.text_input("Host:", value="jupiter", key="r630xl_host")
        with col2:
            r630xl_username = st.text_input("Username:", value="jupiter", key="r630xl_user")
        with col3:
            r630xl_enabled = st.checkbox("Enable", value=True, key="r630xl_enabled")
        
        # R810
        st.markdown("**R810 Server:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            r810_host = st.text_input("Host:", value="saturn", key="r810_host")
        with col2:
            r810_username = st.text_input("Username:", value="jupiter", key="r810_user")
        with col3:
            r810_enabled = st.checkbox("Enable", value=False, key="r810_enabled")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back"):
                st.session_state.wizard_step = 1
                st.rerun()
        
        with col2:
            if st.button("Next →"):
                # Save node config
                nodes_config = {
                    "laptop": {
                        "name": "laptop",
                        "host": laptop_host,
                        "username": laptop_username,
                        "port": 22,
                        "large_file_dirs": [
                            "data/es_futures",
                            "data/processed",
                            "models",
                            "backtest/results",
                            "logs"
                        ]
                    }
                }
                
                if r630xl_enabled:
                    nodes_config["r630xl"] = {
                        "name": "r630xl",
                        "host": r630xl_host,
                        "username": r630xl_username,
                        "port": 22,
                        "large_file_dirs": [
                            "/opt/quanttime/data/es_futures",
                            "/opt/quanttime/data/processed",
                            "/opt/quanttime/models",
                            "/opt/quanttime/backtest/results",
                            "/opt/quanttime/logs"
                        ]
                    }
                
                if r810_enabled:
                    nodes_config["r810"] = {
                        "name": "r810",
                        "host": r810_host,
                        "username": r810_username,
                        "port": 22,
                        "large_file_dirs": [
                            "/opt/quanttime/data/es_futures",
                            "/opt/quanttime/data/processed",
                            "/opt/quanttime/models",
                            "/opt/quanttime/backtest/results",
                            "/opt/quanttime/logs"
                        ]
                    }
                
                st.session_state.nodes_config = nodes_config
                st.session_state.wizard_step = 3
                st.rerun()
    
    # Step 3: Ray Configuration
    elif st.session_state.wizard_step == 3:
        st.header("⚡ Step 3: Ray Cluster Configuration")
        
        st.subheader("Head Node Settings")
        col1, col2 = st.columns(2)
        with col1:
            head_host = st.text_input("Head Node Host:", value="localhost")
            head_port = st.number_input("Ray Port:", value=10001, min_value=1000, max_value=65535)
        with col2:
            dashboard_port = st.number_input("Dashboard Port:", value=8265, min_value=1000, max_value=65535)
            max_concurrent_jobs = st.number_input("Max Concurrent Jobs:", value=4, min_value=1, max_value=20)
        
        st.subheader("Resource Allocation")
        col1, col2, col3 = st.columns(3)
        with col1:
            cpu_per_node = st.number_input("CPU per Node:", value=4, min_value=1, max_value=32)
        with col2:
            gpu_per_node = st.number_input("GPU per Node:", value=0, min_value=0, max_value=8)
        with col3:
            memory_gb_per_node = st.number_input("Memory (GB) per Node:", value=8, min_value=1, max_value=128)
        
        st.subheader("Job Settings")
        job_timeout = st.number_input("Job Timeout (minutes):", value=60, min_value=5, max_value=1440)
        
        # Worker nodes from previous step
        worker_nodes = []
        if "r630xl" in st.session_state.nodes_config:
            worker_nodes.append({
                "name": "r630xl",
                "host": st.session_state.nodes_config["r630xl"]["host"],
                "port": 10001
            })
        if "r810" in st.session_state.nodes_config:
            worker_nodes.append({
                "name": "r810",
                "host": st.session_state.nodes_config["r810"]["host"],
                "port": 10001
            })
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back"):
                st.session_state.wizard_step = 2
                st.rerun()
        
        with col2:
            if st.button("Next →"):
                ray_settings = {
                    "head_host": head_host,
                    "head_port": head_port,
                    "dashboard_port": dashboard_port,
                    "worker_nodes": worker_nodes,
                    "cpu_per_node": cpu_per_node,
                    "gpu_per_node": gpu_per_node,
                    "memory_gb_per_node": memory_gb_per_node,
                    "max_concurrent_jobs": max_concurrent_jobs,
                    "job_timeout_minutes": job_timeout
                }
                
                st.session_state.ray_settings = ray_settings
                st.session_state.wizard_step = 4
                st.rerun()
    
    # Step 4: Final Setup
    elif st.session_state.wizard_step == 4:
        st.header("🎯 Step 4: Complete Setup")
        
        st.subheader("Configuration Summary")
        
        # Display nodes
        st.markdown("**Nodes:**")
        for name, config in st.session_state.nodes_config.items():
            st.markdown(f"- **{name}**: {config['host']} ({config['username']})")
        
        # Display Ray settings
        st.markdown("**Ray Cluster:**")
        st.markdown(f"- Head Node: {st.session_state.ray_settings['head_host']}:{st.session_state.ray_settings['head_port']}")
        st.markdown(f"- Dashboard: {st.session_state.ray_settings['dashboard_port']}")
        st.markdown(f"- Resources: {st.session_state.ray_settings['cpu_per_node']} CPU, {st.session_state.ray_settings['gpu_per_node']} GPU, {st.session_state.ray_settings['memory_gb_per_node']} GB RAM per node")
        
        if st.button("🚀 Complete Setup"):
            with st.spinner("Creating configuration files..."):
                # Create SFTP config
                success, message = create_sftp_config(st.session_state.nodes_config)
                if not success:
                    st.error(f"SFTP config error: {message}")
                    return
                
                # Create Ray config
                success, message = create_ray_config(st.session_state.ray_settings)
                if not success:
                    st.error(f"Ray config error: {message}")
                    return
                
                st.success("✅ Configuration complete!")
                st.info("🎉 You can now use the dashboard!")
                
                if st.button("Continue to Dashboard"):
                    st.session_state.config_complete = True
                    st.rerun()

def check_configuration():
    """Check if configuration exists and is valid"""
    sftp_config = Path("config/sftp_config.json")
    ray_config = Path("config/ray_config.json")
    
    if not sftp_config.exists() or not ray_config.exists():
        return False
    
    try:
        with open(sftp_config) as f:
            json.load(f)
        with open(ray_config) as f:
            json.load(f)
        return True
    except:
        return False

def show_config_wizard():
    """Show configuration wizard if needed"""
    if not check_configuration():
        render_config_wizard()
        return True
    return False
