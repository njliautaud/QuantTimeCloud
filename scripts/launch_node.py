#!/usr/bin/env python3
"""
QuantTime Node Launcher
Launches Ray cluster and dashboard on individual nodes

This script should be run on each node after setup_node.py has been completed.
It will:
1. Load the node-specific configuration
2. Start Ray cluster (head or worker)
3. Launch the dashboard (if head node)
4. Provide status monitoring

Usage:
    python scripts/launch_node.py [--head] [--dashboard] [--monitor]
"""

import os
import sys
import json
import subprocess
import time
import argparse
import logging
import signal
import threading
from pathlib import Path
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/launch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NodeLauncher:
    """Launches and manages node services"""
    
    def __init__(self, node_name: Optional[str] = None, head: bool = False, dashboard: bool = False):
        self.node_name = node_name or self._detect_node_name()
        self.head = head
        self.dashboard = dashboard
        self.project_root = Path(__file__).parent.parent
        self.config = self._load_node_config()
        self.processes = []
        self.running = True
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"Initializing launcher for node: {self.node_name}")
        logger.info(f"Head node: {self.head}, Dashboard: {self.dashboard}")
    
    def _detect_node_name(self) -> str:
        """Detect node name based on hostname"""
        import platform
        hostname = platform.node().lower()
        
        hostname_mapping = {
            'jupiter-desktop': 'r630xl',
            'r810': 'r810',
            'dev-laptop': 'laptop',
            'dev-desktop': 'laptop'
        }
        
        for host, node in hostname_mapping.items():
            if host in hostname:
                return node
        
        return hostname
    
    def _load_node_config(self) -> Dict:
        """Load node-specific configuration"""
        config_path = self.project_root / "config" / f"node_{self.node_name}.json"
        
        if not config_path.exists():
            logger.error(f"Node config not found: {config_path}")
            logger.error("Please run setup_node.py first")
            sys.exit(1)
        
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load node config: {e}")
            sys.exit(1)
    
    def _get_python_command(self) -> str:
        """Get the appropriate python command"""
        venv_path = Path(self.config["paths"]["venv"])
        
        if self.config["node"]["platform"] == "windows":
            return str(venv_path / "Scripts" / "python.exe")
        else:
            return str(venv_path / "bin" / "python")
    
    def _get_ray_command(self) -> str:
        """Get the appropriate ray command"""
        venv_path = Path(self.config["paths"]["venv"])
        
        if self.config["node"]["platform"] == "windows":
            return str(venv_path / "Scripts" / "ray.exe")
        else:
            return str(venv_path / "bin" / "ray")
    
    def start_ray_cluster(self) -> bool:
        """Start Ray cluster"""
        logger.info("Starting Ray cluster...")
        
        ray_cmd = self._get_ray_command()
        ray_config = self.config["ray"]
        
        if self.head:
            # Start head node
            cmd = [
                ray_cmd, "start", "--head",
                f"--port={ray_config['head_port']}",
                f"--dashboard-port={ray_config['dashboard_port']}",
                f"--temp-dir={ray_config['temp_dir']}",
                f"--log-dir={ray_config['log_dir']}",
                f"--object-store-memory={ray_config['object_store_memory']}",
                f"--num-cpus={ray_config['num_cpus']}",
                f"--memory={ray_config['memory']}"
            ]
        else:
            # Start worker node
            head_ip = ray_config.get("head_node_ip", "localhost")
            cmd = [
                ray_cmd, "start",
                f"--address={head_ip}:{ray_config['head_port']}",
                f"--temp-dir={ray_config['temp_dir']}",
                f"--log-dir={ray_config['log_dir']}",
                f"--object-store-memory={ray_config['object_store_memory']}",
                f"--num-cpus={ray_config['num_cpus']}",
                f"--memory={ray_config['memory']}"
            ]
        
        try:
            # Change to project directory
            os.chdir(self.project_root)
            
            # Start Ray process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes.append(("ray", process))
            logger.info(f"Started Ray cluster with PID: {process.pid}")
            
            # Wait a moment for Ray to start
            time.sleep(5)
            
            # Check if Ray started successfully
            if process.poll() is None:
                logger.info("Ray cluster started successfully")
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"Ray failed to start: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Ray cluster: {e}")
            return False
    
    def start_dashboard(self) -> bool:
        """Start the Streamlit dashboard"""
        if not self.head:
            logger.info("Dashboard only runs on head node")
            return True
        
        logger.info("Starting Streamlit dashboard...")
        
        python_cmd = self._get_python_command()
        
        try:
            # Change to project directory
            os.chdir(self.project_root)
            
            # Start dashboard process
            process = subprocess.Popen(
                [python_cmd, "run.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes.append(("dashboard", process))
            logger.info(f"Started dashboard with PID: {process.pid}")
            
            # Wait a moment for dashboard to start
            time.sleep(10)
            
            # Check if dashboard started successfully
            if process.poll() is None:
                logger.info("Dashboard started successfully")
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"Dashboard failed to start: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start dashboard: {e}")
            return False
    
    def monitor_processes(self):
        """Monitor running processes"""
        logger.info("Monitoring processes...")
        
        while self.running:
            for name, process in self.processes:
                if process.poll() is not None:
                    logger.warning(f"Process {name} (PID: {process.pid}) has stopped")
                    # Remove stopped process from list
                    self.processes = [(n, p) for n, p in self.processes if p.poll() is None]
            
            time.sleep(5)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        self.shutdown()
    
    def shutdown(self):
        """Shutdown all processes gracefully"""
        logger.info("Shutting down processes...")
        
        for name, process in self.processes:
            try:
                logger.info(f"Stopping {name} (PID: {process.pid})")
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing {name}")
                    process.kill()
                    process.wait()
                    
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")
        
        logger.info("Shutdown complete")
    
    def run(self) -> bool:
        """Run the node launcher"""
        logger.info("=" * 60)
        logger.info(f"Starting QuantTime node launcher for: {self.node_name}")
        logger.info("=" * 60)
        
        try:
            # Start Ray cluster
            if not self.start_ray_cluster():
                logger.error("Failed to start Ray cluster")
                return False
            
            # Start dashboard if requested
            if self.dashboard and self.head:
                if not self.start_dashboard():
                    logger.error("Failed to start dashboard")
                    return False
            
            # Start monitoring in a separate thread
            monitor_thread = threading.Thread(target=self.monitor_processes, daemon=True)
            monitor_thread.start()
            
            logger.info("Node launcher is running. Press Ctrl+C to stop.")
            
            # Keep main thread alive
            while self.running:
                time.sleep(1)
            
            return True
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            return True
        except Exception as e:
            logger.error(f"Launcher error: {e}")
            return False
        finally:
            self.shutdown()

def main():
    parser = argparse.ArgumentParser(description="QuantTime Node Launcher")
    parser.add_argument("--node-name", help="Name of the node")
    parser.add_argument("--head", action="store_true", help="Start as Ray head node")
    parser.add_argument("--dashboard", action="store_true", help="Start dashboard (head node only)")
    parser.add_argument("--monitor", action="store_true", help="Monitor processes")
    
    args = parser.parse_args()
    
    # Create launcher
    launcher = NodeLauncher(
        node_name=args.node_name,
        head=args.head,
        dashboard=args.dashboard
    )
    
    # Run launcher
    success = launcher.run()
    
    if success:
        logger.info("Launcher completed successfully")
        sys.exit(0)
    else:
        logger.error("Launcher failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
