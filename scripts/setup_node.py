#!/usr/bin/env python3
"""
QuantTime Node Setup Script
Complete setup script for individual nodes to establish their own environment

This script should be run on each node (laptop, R630XL, R810) to:
1. Detect the node's platform and architecture
2. Set up node-specific environment variables and paths
3. Install Python dependencies
4. Configure Ray cluster settings
5. Set up logging and monitoring
6. Create node-specific configuration files

Usage:
    python scripts/setup_node.py [--node-name NODE_NAME] [--head-node HEAD_IP] [--force]
"""

import os
import sys
import json
import subprocess
import platform
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/setup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NodeSetupManager:
    """Manages complete node setup and environment configuration"""
    
    def __init__(self, node_name: Optional[str] = None, head_node_ip: Optional[str] = None, force: bool = False):
        self.node_name = node_name or self._detect_node_name()
        self.head_node_ip = head_node_ip
        self.force = force
        self.platform = platform.system().lower()
        self.arch = platform.machine()
        self.project_root = Path(__file__).parent.parent
        self.setup_log = []
        
        logger.info(f"Initializing setup for node: {self.node_name}")
        logger.info(f"Platform: {self.platform}, Architecture: {self.arch}")
        logger.info(f"Project root: {self.project_root}")
    
    def _detect_node_name(self) -> str:
        """Detect node name based on hostname or environment"""
        hostname = platform.node().lower()
        
        # Map hostnames to node names
        hostname_mapping = {
            'jupiter-desktop': 'r630xl',
            'r810': 'r810',
            'dev-laptop': 'laptop',
            'dev-desktop': 'laptop'
        }
        
        for host, node in hostname_mapping.items():
            if host in hostname:
                return node
        
        # Default to hostname if no mapping found
        return hostname
    
    def get_node_environment_config(self) -> Dict:
        """Generate node-specific environment configuration"""
        # Base paths
        if self.platform == "windows":
            base_path = Path("C:/Users/user/Documents/GitHub/QuantTime")
            venv_path = base_path / ".venv"
            ray_temp_dir = base_path / "temp" / "ray"
            ray_log_dir = base_path / "logs" / "ray"
        else:
            base_path = Path("/opt/quanttime")
            venv_path = base_path / ".venv"
            ray_temp_dir = Path("/tmp/ray")
            ray_log_dir = base_path / "logs" / "ray"
        
        config = {
            "node": {
                "name": self.node_name,
                "platform": self.platform,
                "arch": self.arch,
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
                "hostname": platform.node(),
                "user": os.getenv("USER", os.getenv("USERNAME", "unknown"))
            },
            "paths": {
                "project_root": str(base_path),
                "data": str(base_path / "data"),
                "logs": str(base_path / "logs"),
                "cache": str(base_path / "cache"),
                "temp": str(base_path / "temp"),
                "venv": str(venv_path),
                "config": str(base_path / "config"),
                "scripts": str(base_path / "scripts")
            },
            "ray": {
                "temp_dir": str(ray_temp_dir),
                "log_dir": str(ray_log_dir),
                "dashboard_port": 8265,
                "head_port": 10001,
                "object_store_memory": "2000000000",  # 2GB
                "num_cpus": os.cpu_count(),
                "memory": "8000000000"  # 8GB
            },
            "environment": {
                "isolated": True,
                "auto_setup": True,
                "sync_exclusions": [
                    ".env",
                    ".env.local",
                    "config/local_*",
                    "logs/*",
                    "cache/*",
                    "temp/*",
                    ".venv/*",
                    "__pycache__/*",
                    "*.pyc",
                    "node_*.json"
                ]
            }
        }
        
        # Add head node IP if provided
        if self.head_node_ip:
            config["ray"]["head_node_ip"] = self.head_node_ip
        
        return config
    
    def create_directories(self) -> bool:
        """Create all necessary directories"""
        logger.info("Creating directories...")
        
        config = self.get_node_environment_config()
        paths = config["paths"]
        
        directories = [
            paths["data"],
            paths["logs"],
            paths["cache"],
            paths["temp"],
            paths["config"],
            paths["scripts"],
            config["ray"]["temp_dir"],
            config["ray"]["log_dir"]
        ]
        
        for directory in directories:
            try:
                Path(directory).mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {directory}")
            except Exception as e:
                logger.error(f"Failed to create directory {directory}: {e}")
                return False
        
        return True
    
    def setup_virtual_environment(self) -> bool:
        """Set up Python virtual environment"""
        logger.info("Setting up virtual environment...")
        
        config = self.get_node_environment_config()
        venv_path = Path(config["paths"]["venv"])
        
        # Check if venv already exists
        if venv_path.exists() and not self.force:
            logger.info(f"Virtual environment already exists at {venv_path}")
            return True
        
        # Remove existing venv if force flag is set
        if venv_path.exists() and self.force:
            logger.info(f"Removing existing virtual environment at {venv_path}")
            shutil.rmtree(venv_path)
        
        try:
            # Create virtual environment
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
            logger.info(f"Created virtual environment at {venv_path}")
            
            # Upgrade pip
            pip_cmd = self._get_pip_command()
            subprocess.run([pip_cmd, "install", "--upgrade", "pip"], check=True)
            logger.info("Upgraded pip")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create virtual environment: {e}")
            return False
    
    def _get_pip_command(self) -> str:
        """Get the appropriate pip command for the platform"""
        config = self.get_node_environment_config()
        venv_path = Path(config["paths"]["venv"])
        
        if self.platform == "windows":
            return str(venv_path / "Scripts" / "pip.exe")
        else:
            return str(venv_path / "bin" / "pip")
    
    def _get_python_command(self) -> str:
        """Get the appropriate python command for the platform"""
        config = self.get_node_environment_config()
        venv_path = Path(config["paths"]["venv"])
        
        if self.platform == "windows":
            return str(venv_path / "Scripts" / "python.exe")
        else:
            return str(venv_path / "bin" / "python")
    
    def install_dependencies(self) -> bool:
        """Install Python dependencies"""
        logger.info("Installing dependencies...")
        
        pip_cmd = self._get_pip_command()
        requirements_file = self.project_root / "requirements.txt"
        
        if not requirements_file.exists():
            logger.error(f"Requirements file not found: {requirements_file}")
            return False
        
        try:
            # Install requirements
            subprocess.run([pip_cmd, "install", "-r", str(requirements_file)], check=True)
            logger.info("Installed requirements.txt dependencies")
            
            # Install project in editable mode
            subprocess.run([pip_cmd, "install", "-e", str(self.project_root)], check=True)
            logger.info("Installed project in editable mode")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e}")
            return False
    
    def create_environment_script(self) -> bool:
        """Create node-specific environment setup script"""
        logger.info("Creating environment setup script...")
        
        config = self.get_node_environment_config()
        script_path = self.project_root / "setup_env.sh"
        
        if self.platform == "windows":
            script_path = self.project_root / "setup_env.bat"
            script_content = self._create_windows_env_script(config)
        else:
            script_content = self._create_linux_env_script(config)
        
        try:
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Make executable on Linux
            if self.platform != "windows":
                os.chmod(script_path, 0o755)
            
            logger.info(f"Created environment script: {script_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create environment script: {e}")
            return False
    
    def _create_linux_env_script(self, config: Dict) -> str:
        """Create Linux environment setup script"""
        return f"""#!/bin/bash
# Node-specific environment setup for {config['node']['name']}
# Generated automatically - DO NOT EDIT MANUALLY

export NODE_NAME="{config['node']['name']}"
export PLATFORM="{config['node']['platform']}"
export ARCH="{config['node']['arch']}"
export PYTHON_VERSION="{config['node']['python_version']}"

# Project paths
export QUANTTIME_ROOT="{config['paths']['project_root']}"
export QUANTTIME_DATA="{config['paths']['data']}"
export QUANTTIME_LOGS="{config['paths']['logs']}"
export QUANTTIME_CACHE="{config['paths']['cache']}"
export QUANTTIME_TEMP="{config['paths']['temp']}"
export QUANTTIME_VENV="{config['paths']['venv']}"

# Ray configuration
export RAY_TEMP_DIR="{config['ray']['temp_dir']}"
export RAY_LOG_DIR="{config['ray']['log_dir']}"
export RAY_DASHBOARD_PORT="{config['ray']['dashboard_port']}"
export RAY_HEAD_PORT="{config['ray']['head_port']}"

# Create directories
mkdir -p "$QUANTTIME_DATA" "$QUANTTIME_LOGS" "$QUANTTIME_CACHE" "$QUANTTIME_TEMP" "$RAY_TEMP_DIR" "$RAY_LOG_DIR"

# Set permissions
chmod 755 "$QUANTTIME_DATA" "$QUANTTIME_LOGS" "$QUANTTIME_CACHE" "$QUANTTIME_TEMP"

# Python path
export PYTHONPATH="$QUANTTIME_ROOT:$PYTHONPATH"

# Activate virtual environment
if [ -f "$QUANTTIME_VENV/bin/activate" ]; then
    source "$QUANTTIME_VENV/bin/activate"
fi

echo "Environment setup complete for {config['node']['name']}"
"""
    
    def _create_windows_env_script(self, config: Dict) -> str:
        """Create Windows environment setup script"""
        return f"""@echo off
REM Node-specific environment setup for {config['node']['name']}
REM Generated automatically - DO NOT EDIT MANUALLY

set NODE_NAME={config['node']['name']}
set PLATFORM={config['node']['platform']}
set ARCH={config['node']['arch']}
set PYTHON_VERSION={config['node']['python_version']}

REM Project paths
set QUANTTIME_ROOT={config['paths']['project_root']}
set QUANTTIME_DATA={config['paths']['data']}
set QUANTTIME_LOGS={config['paths']['logs']}
set QUANTTIME_CACHE={config['paths']['cache']}
set QUANTTIME_TEMP={config['paths']['temp']}
set QUANTTIME_VENV={config['paths']['venv']}

REM Ray configuration
set RAY_TEMP_DIR={config['ray']['temp_dir']}
set RAY_LOG_DIR={config['ray']['log_dir']}
set RAY_DASHBOARD_PORT={config['ray']['dashboard_port']}
set RAY_HEAD_PORT={config['ray']['head_port']}

REM Create directories
if not exist "%QUANTTIME_DATA%" mkdir "%QUANTTIME_DATA%"
if not exist "%QUANTTIME_LOGS%" mkdir "%QUANTTIME_LOGS%"
if not exist "%QUANTTIME_CACHE%" mkdir "%QUANTTIME_CACHE%"
if not exist "%QUANTTIME_TEMP%" mkdir "%QUANTTIME_TEMP%"
if not exist "%RAY_TEMP_DIR%" mkdir "%RAY_TEMP_DIR%"
if not exist "%RAY_LOG_DIR%" mkdir "%RAY_LOG_DIR%"

REM Python path
set PYTHONPATH=%QUANTTIME_ROOT%;%PYTHONPATH%

REM Activate virtual environment
if exist "%QUANTTIME_VENV%\\Scripts\\activate.bat" (
    call "%QUANTTIME_VENV%\\Scripts\\activate.bat"
)

echo Environment setup complete for {config['node']['name']}
"""
    
    def create_node_config_file(self) -> bool:
        """Create node-specific configuration file"""
        logger.info("Creating node configuration file...")
        
        config = self.get_node_environment_config()
        config_path = self.project_root / "config" / f"node_{self.node_name}.json"
        
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Created node config: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create node config: {e}")
            return False
    
    def setup_ray_config(self) -> bool:
        """Set up Ray cluster configuration"""
        logger.info("Setting up Ray configuration...")
        
        config = self.get_node_environment_config()
        ray_config_path = self.project_root / "config" / "ray_config.json"
        
        ray_config = {
            "cluster": {
                "head_node": {
                    "ip": self.head_node_ip or "localhost",
                    "port": config["ray"]["head_port"],
                    "dashboard_port": config["ray"]["dashboard_port"]
                },
                "worker_nodes": []
            },
            "resources": {
                "num_cpus": config["ray"]["num_cpus"],
                "memory": config["ray"]["memory"],
                "object_store_memory": config["ray"]["object_store_memory"]
            },
            "temp_dir": config["ray"]["temp_dir"],
            "log_dir": config["ray"]["log_dir"]
        }
        
        try:
            with open(ray_config_path, 'w') as f:
                json.dump(ray_config, f, indent=2)
            
            logger.info(f"Created Ray config: {ray_config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create Ray config: {e}")
            return False
    
    def test_installation(self) -> bool:
        """Test the installation by importing key modules"""
        logger.info("Testing installation...")
        
        python_cmd = self._get_python_command()
        
        test_modules = [
            "ray",
            "streamlit", 
            "pandas",
            "numpy",
            "pysftp",
            "paramiko",
            "plotly",
            "lightgbm"
        ]
        
        failed_modules = []
        
        for module in test_modules:
            try:
                subprocess.run([python_cmd, "-c", f"import {module}"], check=True, capture_output=True)
                logger.info(f"✓ {module} imported successfully")
            except subprocess.CalledProcessError:
                logger.warning(f"✗ Failed to import {module}")
                failed_modules.append(module)
        
        if failed_modules:
            logger.error(f"Failed to import modules: {', '.join(failed_modules)}")
            return False
        
        logger.info("All key modules imported successfully")
        return True
    
    def run_setup(self) -> bool:
        """Run complete node setup"""
        logger.info("=" * 60)
        logger.info(f"Starting QuantTime node setup for: {self.node_name}")
        logger.info("=" * 60)
        
        steps = [
            ("Creating directories", self.create_directories),
            ("Setting up virtual environment", self.setup_virtual_environment),
            ("Installing dependencies", self.install_dependencies),
            ("Creating environment script", self.create_environment_script),
            ("Creating node config", self.create_node_config_file),
            ("Setting up Ray config", self.setup_ray_config),
            ("Testing installation", self.test_installation)
        ]
        
        for step_name, step_func in steps:
            logger.info(f"\n--- {step_name} ---")
            if not step_func():
                logger.error(f"Setup failed at: {step_name}")
                return False
        
        logger.info("\n" + "=" * 60)
        logger.info("Node setup completed successfully!")
        logger.info("=" * 60)
        
        # Print next steps
        logger.info("\nNext steps:")
        logger.info("1. Run the environment script to activate the environment:")
        if self.platform == "windows":
            logger.info(f"   {self.project_root}\\setup_env.bat")
        else:
            logger.info(f"   source {self.project_root}/setup_env.sh")
        
        logger.info("2. Start Ray cluster:")
        if self.node_name == "laptop":
            logger.info("   ray start --head --port=10001 --dashboard-port=8265")
        else:
            logger.info(f"   ray start --address={self.head_node_ip or 'localhost'}:10001")
        
        logger.info("3. Run the dashboard:")
        logger.info("   python run.py")
        
        return True

def main():
    parser = argparse.ArgumentParser(description="QuantTime Node Setup Script")
    parser.add_argument("--node-name", help="Name of the node (laptop, r630xl, r810)")
    parser.add_argument("--head-node", help="IP address of the Ray head node")
    parser.add_argument("--force", action="store_true", help="Force recreation of virtual environment")
    
    args = parser.parse_args()
    
    # Create setup manager
    setup_manager = NodeSetupManager(
        node_name=args.node_name,
        head_node_ip=args.head_node,
        force=args.force
    )
    
    # Run setup
    success = setup_manager.run_setup()
    
    if success:
        logger.info("Setup completed successfully!")
        sys.exit(0)
    else:
        logger.error("Setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
