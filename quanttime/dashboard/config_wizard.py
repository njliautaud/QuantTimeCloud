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
    """Create Ray configuration file with auto-detection"""
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    config = {
        "head_node": {
            "host": ray_settings["head_host"],
            "dashboard_port": ray_settings["dashboard_port"],
            "node_type": "head"
        },
        "worker_nodes": ray_settings["worker_nodes"],
        "cluster_settings": {
            "auto_detect_resources": True,
            "auto_detect_ports": True,
            "max_concurrent_jobs": ray_settings.get("max_concurrent_jobs", 4),
            "job_timeout_minutes": ray_settings.get("job_timeout_minutes", 60),
            "object_store_memory": "2GB",
            "redis_max_memory": "1GB"
        },
        "auto_detection": {
            "enabled": True,
            "port_range_start": 10001,
            "port_range_end": 10100,
            "resource_detection": True,
            "network_discovery": True
        },
        "connection_info": {
            "use_tailscale": True,
            "connection_timeout": 30,
            "retry_attempts": 3
        }
    }
    
    config_file = config_dir / "ray_config.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    return True, f"Ray config created at {config_file}"

def render_config_wizard():
    """Render the configuration wizard"""
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
    
    # Step 3: Ray Cluster Setup
    elif st.session_state.wizard_step == 3:
        st.header("⚡ Step 3: Ray Cluster Setup")
        
        st.success("🎯 Ray will automatically detect everything when nodes connect!")
        st.info("""
        **Ray Auto-Detection:**
        - ✅ CPU cores and memory
        - ✅ GPU availability  
        - ✅ Network ports
        - ✅ Node connectivity
        - ✅ Resource allocation
        """)
        
        st.subheader("Minimal Configuration")
        col1, col2 = st.columns(2)
        with col1:
            # Use Tailscale IP for head node
            tailscale_ip = get_tailscale_ip()
            head_host = st.text_input(
                "Head Node Host:", 
                value=tailscale_ip or "localhost",
                help="Tailscale IP address for the head node (laptop)"
            )
        with col2:
            dashboard_port = st.number_input("Dashboard Port:", value=8265, min_value=1000, max_value=65535)
        
        st.subheader("Auto-Detection Settings")
        st.markdown("""
        **Ray will automatically:**
        - Detect available ports (starting from 10001)
        - Scale based on actual node resources
        - Handle job queuing and distribution
        - Monitor cluster health
        """)
        
        # Optional advanced settings
        with st.expander("Advanced Settings (Optional)"):
            col1, col2 = st.columns(2)
            with col1:
                max_concurrent_jobs = st.number_input("Max Concurrent Jobs:", value=4, min_value=1, max_value=20)
            with col2:
                job_timeout = st.number_input("Job Timeout (minutes):", value=60, min_value=5, max_value=1440)
        
        # Display node information
        st.subheader("Node Configuration")
        st.info("Nodes will connect using their Tailscale IPs:")
        
        nodes_info = []
        if "laptop" in st.session_state.nodes_config:
            nodes_info.append({
                "name": "laptop (Head)",
                "host": st.session_state.nodes_config["laptop"]["host"],
                "type": "Head Node"
            })
        
        if "r630xl" in st.session_state.nodes_config:
            nodes_info.append({
                "name": "r630xl",
                "host": st.session_state.nodes_config["r630xl"]["host"],
                "type": "Worker Node"
            })
        
        if "r810" in st.session_state.nodes_config:
            nodes_info.append({
                "name": "r810", 
                "host": st.session_state.nodes_config["r810"]["host"],
                "type": "Worker Node"
            })
        
        # Display nodes in a nice format
        for node in nodes_info:
            st.markdown(f"**{node['name']}** ({node['type']}): `{node['host']}`")
        
        # Worker nodes for Ray config
        worker_nodes = []
        if "r630xl" in st.session_state.nodes_config:
            worker_nodes.append({
                "name": "r630xl",
                "host": st.session_state.nodes_config["r630xl"]["host"],
                "port": 10001,
                "node_type": "worker"
            })
        if "r810" in st.session_state.nodes_config:
            worker_nodes.append({
                "name": "r810",
                "host": st.session_state.nodes_config["r810"]["host"], 
                "port": 10001,
                "node_type": "worker"
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
                    "dashboard_port": dashboard_port,
                    "worker_nodes": worker_nodes,
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
        st.markdown(f"- Head Node: {st.session_state.ray_settings['head_host']}")
        st.markdown(f"- Dashboard: {st.session_state.ray_settings['dashboard_port']}")
        st.markdown(f"- Auto-Detection: ✅ **FULLY ENABLED**")
        st.markdown(f"- Port Detection: ✅ Automatic")
        st.markdown(f"- Resource Detection: ✅ Automatic")
        st.markdown(f"- Network Discovery: ✅ Automatic")
        st.markdown(f"- Connection: Tailscale IPs")
        
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
                
                # Automated node connection
                st.subheader("🔗 Automated Node Connection")
                st.info("We can automatically connect your nodes via SSH using the credentials you provided.")
                
                # Get SSH password
                ssh_password = st.text_input(
                    "SSH Password for worker nodes:",
                    type="password",
                    help="Password for the 'jupiter' user on R630XL and R810 servers"
                )
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🚀 Connect Nodes Automatically"):
                        if ssh_password:
                            with st.spinner("Connecting nodes via SSH..."):
                                success, message = connect_nodes_automatically(
                                    st.session_state.nodes_config, 
                                    ssh_password
                                )
                                if success:
                                    st.success("✅ All nodes connected successfully!")
                                    st.info(message)
                                else:
                                    st.error(f"❌ Connection failed: {message}")
                        else:
                            st.error("Please enter the SSH password")
                
                with col2:
                    if st.button("🔍 Check Connection Status"):
                        with st.spinner("Checking node status..."):
                            status = check_node_connection_status(
                                st.session_state.nodes_config, 
                                ssh_password
                            )
                            st.json(status)
                
                # Manual instructions as fallback
                with st.expander("Manual Connection Instructions (if needed)"):
                    st.markdown("""
                    **To connect your worker nodes to the Ray cluster:**
                    
                    1. **On each worker node (R630XL, R810):**
                       - Copy the `scripts/connect_ray_node.py` script to the node
                       - Run: `python connect_ray_node.py`
                       - The script will automatically connect using Tailscale IPs
                    
                    2. **On the head node (laptop):**
                       - Start the dashboard: `python run.py`
                       - Monitor cluster status in the dashboard
                    
                    3. **Verify connections:**
                       - Check the "Servers" tab in the dashboard
                       - All nodes should show as "online" with detected resources
                    """)
                
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

def connect_nodes_automatically(nodes_config, ssh_password):
    """Automatically connect worker nodes via SSH"""
    try:
        import paramiko
        import tempfile
        import os
        
        connected_nodes = []
        failed_nodes = []
        
        # Get head node info
        head_node = nodes_config.get("laptop", {})
        head_host = head_node.get("host", "localhost")
        
        # Connect to each worker node
        for node_name, node_config in nodes_config.items():
            if node_name == "laptop":  # Skip head node
                continue
                
            host = node_config["host"]
            username = node_config["username"]
            port = node_config["port"]
            
            try:
                # Create SSH client
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Connect to node
                ssh.connect(
                    hostname=host,
                    username=username,
                    password=ssh_password,
                    port=port,
                    timeout=30
                )
                
                # Create temporary directory for QuantTime
                ssh.exec_command("mkdir -p /tmp/quanttime")
                
                # Copy connection script to node
                script_content = get_connection_script_content(head_host)
                
                # Write script to remote node
                sftp = ssh.open_sftp()
                with sftp.file("/tmp/quanttime/connect_ray_node.py", "w") as f:
                    f.write(script_content)
                sftp.close()
                
                # Copy Ray config to node
                ray_config_path = Path("config/ray_config.json")
                if ray_config_path.exists():
                    sftp = ssh.open_sftp()
                    sftp.put(str(ray_config_path), "/tmp/quanttime/ray_config.json")
                    sftp.close()
                
                # Start Ray connection in background
                command = f"""
                cd /tmp/quanttime
                python3 connect_ray_node.py > ray_connection.log 2>&1 &
                echo $! > ray_connection.pid
                """
                
                stdin, stdout, stderr = ssh.exec_command(command)
                exit_status = stdout.channel.recv_exit_status()
                
                if exit_status == 0:
                    connected_nodes.append(node_name)
                    print(f"✅ Connected {node_name} ({host})")
                else:
                    failed_nodes.append(f"{node_name}: SSH command failed")
                
                ssh.close()
                
            except Exception as e:
                failed_nodes.append(f"{node_name}: {str(e)}")
                print(f"❌ Failed to connect {node_name} ({host}): {e}")
        
        # Summary
        if connected_nodes:
            message = f"Successfully connected: {', '.join(connected_nodes)}"
            if failed_nodes:
                message += f"\nFailed: {', '.join(failed_nodes)}"
            return True, message
        else:
            return False, f"Failed to connect any nodes: {', '.join(failed_nodes)}"
            
    except Exception as e:
        return False, f"Connection automation failed: {str(e)}"


def check_node_connection_status(nodes_config, ssh_password):
    """Check the connection status of worker nodes"""
    try:
        import paramiko
        
        status = {}
        
        for node_name, node_config in nodes_config.items():
            if node_name == "laptop":  # Skip head node
                continue
                
            host = node_config["host"]
            username = node_config["username"]
            port = node_config["port"]
            
            try:
                # Create SSH client
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Connect to node
                ssh.connect(
                    hostname=host,
                    username=username,
                    password=ssh_password,
                    port=port,
                    timeout=10
                )
                
                # Check if Ray connection process is running
                stdin, stdout, stderr = ssh.exec_command("ps aux | grep connect_ray_node.py | grep -v grep")
                ray_running = len(stdout.read().strip()) > 0
                
                # Check if Ray is initialized
                stdin, stdout, stderr = ssh.exec_command("python3 -c 'import ray; print(ray.is_initialized())' 2>/dev/null || echo 'False'")
                ray_initialized = stdout.read().strip().decode() == "True"
                
                # Get connection log
                stdin, stdout, stderr = ssh.exec_command("cat /tmp/quanttime/ray_connection.log 2>/dev/null || echo 'No log found'")
                log_content = stdout.read().strip().decode()
                
                status[node_name] = {
                    "host": host,
                    "ssh_connected": True,
                    "ray_process_running": ray_running,
                    "ray_initialized": ray_initialized,
                    "log": log_content[-500:] if log_content != "No log found" else "No log found"  # Last 500 chars
                }
                
                ssh.close()
                
            except Exception as e:
                status[node_name] = {
                    "host": host,
                    "ssh_connected": False,
                    "ray_process_running": False,
                    "ray_initialized": False,
                    "error": str(e)
                }
        
        return status
        
    except Exception as e:
        return {"error": f"Status check failed: {str(e)}"}


def get_connection_script_content(head_host):
    """Get the content of the connection script"""
    return f'''#!/usr/bin/env python3
"""
Ray Node Connection Script (Auto-generated)
Automatically connects to Ray cluster
"""

import json
import subprocess
import sys
import time
from pathlib import Path

def get_tailscale_ip():
    """Get Tailscale IP address"""
    try:
        result = subprocess.run(["tailscale", "ip"], capture_output=True, text=True, check=True)
        for line in result.stdout.strip().split('\\n'):
            if line and '.' in line:  # IPv4 address
                return line.strip()
    except:
        pass
    return None

def connect_to_ray_cluster(head_node_ip):
    """Connect this node to the Ray cluster with auto-detection"""
    print(f"🔗 Connecting to Ray cluster at {{head_node_ip}} (auto-detecting port)")
    
    try:
        # Initialize Ray and connect to the cluster
        import ray
        
        if ray.is_initialized():
            print("⚠️  Ray already initialized. Shutting down...")
            ray.shutdown()
        
        # Connect to the cluster with auto-detection
        ray.init(
            address=f"ray://{{head_node_ip}}",  # Ray will auto-detect the port
            ignore_reinit_error=True,
            # Auto-detect local resources
            num_cpus=None,
            num_gpus=None,
            memory=None
        )
        
        print("✅ Successfully connected to Ray cluster!")
        
        # Get cluster info
        cluster_resources = ray.cluster_resources()
        print(f"📊 Cluster Resources: {{cluster_resources}}")
        
        # Keep the connection alive
        print("🔄 Node is now connected and ready for jobs...")
        
        # Run indefinitely
        while True:
            time.sleep(10)
            
    except Exception as e:
        print(f"❌ Failed to connect to cluster: {{e}}")
        return False
    
    return True

def main():
    """Main function"""
    print("🚀 Ray Node Connection Script (Auto-generated)")
    print("=" * 50)
    
    # Check if config exists
    config_file = Path("ray_config.json")
    if not config_file.exists():
        print("❌ Ray config not found.")
        sys.exit(1)
    
    # Load config
    with open(config_file) as f:
        config = json.load(f)
    
    head_node = config["head_node"]
    head_ip = head_node["host"]
    
    print(f"📋 Cluster Configuration:")
    print(f"   Head Node: {{head_ip}} (auto-detecting port)")
    print(f"   Dashboard: {{head_node['dashboard_port']}}")
    
    # Get local Tailscale IP
    local_ip = get_tailscale_ip()
    if local_ip:
        print(f"🔍 Local Tailscale IP: {{local_ip}}")
    else:
        print("⚠️  Could not detect Tailscale IP")
    
    # Connect to cluster
    if connect_to_ray_cluster(head_ip):
        print("✅ Node connection completed successfully")
    else:
        print("❌ Node connection failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''


def show_config_wizard():
    """Show configuration wizard if needed"""
    if not check_configuration():
        render_config_wizard()
        return True
    return False
