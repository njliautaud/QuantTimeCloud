#!/usr/bin/env python3
"""
QuantTime ML Trading Suite - Root Setup Script
Handles configuration, environment setup, and library management

This is the main setup script for QuantTime that provides:
1. Automated environment detection and setup
2. Cross-platform dependency installation  
3. Configuration management and validation
4. Database and service initialization
5. SSH key and authentication setup
6. Development and production modes

Usage:
    python setup.py --help              # Show all options
    python setup.py --init              # Initialize project 
    python setup.py --dev               # Development setup
    python setup.py --prod              # Production setup
    python setup.py --check             # Check environment
    python setup.py --update            # Update dependencies
    python setup.py --clean             # Clean temporary files
"""

import os
import sys
import json
import subprocess
import platform
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class QuantTimeSetup:
    """Comprehensive QuantTime setup and configuration manager"""
    
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.platform = platform.system().lower()
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        self.is_windows = self.platform == "windows"
        self.is_linux = self.platform == "linux"
        
        # Core directories
        self.config_dir = self.root_dir / "config"
        self.data_dir = self.root_dir / "data"
        self.logs_dir = self.root_dir / "logs"
        self.models_dir = self.root_dir / "models"
        self.scripts_dir = self.root_dir / "scripts"
        
        # Configuration files
        self.settings_file = self.root_dir / "settings.txt"
        self.pyproject_file = self.root_dir / "pyproject.toml"
        self.requirements_file = self.root_dir / "requirements.txt"
        
    def check_python_version(self) -> bool:
        """Check if Python version is compatible"""
        min_version = (3, 11)
        current_version = (sys.version_info.major, sys.version_info.minor)
        
        if current_version < min_version:
            logger.error(f"Python {min_version[0]}.{min_version[1]}+ required. Current: {self.python_version}")
            return False
        
        logger.info(f"✅ Python version: {self.python_version}")
        return True
    
    def create_directories(self) -> bool:
        """Create necessary directories"""
        directories = [
            self.config_dir, self.data_dir, self.logs_dir, 
            self.models_dir, self.data_dir / "processed",
            self.data_dir / "raw", self.data_dir / "backup",
            self.root_dir / "temp", self.root_dir / "temp" / "ray"
        ]
        
        try:
            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"✅ Directory: {directory}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create directories: {e}")
            return False
    
    def setup_virtual_environment(self) -> bool:
        """Setup Python virtual environment if needed"""
        venv_path = self.root_dir / ".venv"
        
        if venv_path.exists():
            logger.info("✅ Virtual environment exists")
            return True
        
        try:
            logger.info("🔧 Creating virtual environment...")
            subprocess.run([
                sys.executable, "-m", "venv", str(venv_path)
            ], check=True, capture_output=True)
            
            logger.info("✅ Virtual environment created")
            
            # Provide activation instructions
            if self.is_windows:
                activate_script = venv_path / "Scripts" / "activate.bat"
                logger.info(f"💡 Activate with: {activate_script}")
            else:
                activate_script = venv_path / "bin" / "activate"
                logger.info(f"💡 Activate with: source {activate_script}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to create virtual environment: {e}")
            return False
    
    def install_dependencies(self, dev_mode: bool = False) -> bool:
        """Install Python dependencies"""
        if not self.requirements_file.exists():
            logger.warning("⚠️ requirements.txt not found")
            return False
        
        try:
            # Determine pip command
            pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
            
            # Install basic requirements
            logger.info("📦 Installing dependencies...")
            subprocess.run(
                pip_cmd + ["-r", str(self.requirements_file)],
                check=True, capture_output=True
            )
            
            # Install development dependencies if requested
            if dev_mode:
                dev_packages = [
                    "pytest>=7.0.0", "pytest-cov>=4.0.0", "black>=23.0.0",
                    "flake8>=6.0.0", "mypy>=1.0.0", "pre-commit>=3.0.0",
                    "jupyter>=1.0.0", "ipykernel>=6.0.0"
                ]
                
                logger.info("🔧 Installing development packages...")
                subprocess.run(pip_cmd + dev_packages, check=True, capture_output=True)
            
            # Install package in editable mode
            logger.info("📦 Installing QuantTime package...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", "."],
                check=True, capture_output=True
            )
            
            logger.info("✅ Dependencies installed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install dependencies: {e}")
            return False
    
    def setup_configuration(self) -> bool:
        """Setup configuration files"""
        try:
            # Check if settings.txt exists
            if not self.settings_file.exists():
                logger.info("🔧 Creating default settings.txt...")
                default_settings = """# QuantTime Configuration
# Databento Configuration
DATABENTO_KEY=your_databento_key_here
DATABENTO_DATASET=GLBX.MDP3
DATABENTO_SYMBOL=ES.FUT
DATABENTO_SCHEMA=mbo

# Data Configuration
DATA_DIR=./data
BACKTEST_DIR=./backtests
MODEL_DIR=./models
LOG_DIR=./logs

# Logging
LOG_LEVEL=INFO

# Live Trading Configuration
LIVE_TRADING_ENABLED=false
LIVE_TRADING_ACCOUNT=paper
LIVE_TRADING_RISK_LIMIT=1000.0

# SSH Automation Keys (Passphrase-free for automated Git sync)
SSH_AUTOMATION_PUBLIC_KEY=
SSH_AUTOMATION_PRIVATE_KEY_PATH=

# Git Configuration  
GIT_SSH_KEY_PATH=
GIT_AUTO_SYNC_ENABLED=true
GIT_MONITOR_INTERVAL_SECONDS=30
"""
                self.settings_file.write_text(default_settings)
            
            # Check Ray cluster config
            ray_config_file = self.config_dir / "ray_cluster_config.json"
            if not ray_config_file.exists():
                logger.info("🔧 Creating default Ray cluster config...")
                default_ray_config = {
                    "head_node": {
                        "node_id": "laptop",
                        "name": "Development Laptop",
                        "address": "localhost",
                        "port": 10001,
                        "dashboard_port": 8265,
                        "is_head": True,
                        "platform": self.platform,
                        "resources": {"CPU": 8, "GPU": 0, "memory": 16.0},
                        "ssh": {"enabled": False},
                        "paths": {
                            "project_root": str(self.root_dir),
                            "python_executable": "python"
                        }
                    },
                    "worker_nodes": [],
                    "cluster_settings": {
                        "auto_scaling": True,
                        "git_sync_enabled": True,
                        "sftp_sync_enabled": True
                    },
                    "git_config": {
                        "repository_url": "https://github.com/yourusername/QuantTime.git",
                        "branch": "master",
                        "auto_pull_enabled": True,
                        "github_pat_required": True
                    }
                }
                
                ray_config_file.write_text(json.dumps(default_ray_config, indent=2))
            
            logger.info("✅ Configuration setup complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup configuration: {e}")
            return False
    
    def setup_database(self) -> bool:
        """Initialize SQLite database"""
        try:
            db_file = self.root_dir / "quanttime.db"
            
            if not db_file.exists():
                logger.info("🔧 Initializing database...")
                # Create empty database file
                db_file.touch()
                logger.info("✅ Database initialized")
            else:
                logger.info("✅ Database exists")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup database: {e}")
            return False
    
    def check_ssh_keys(self) -> bool:
        """Check and setup SSH keys for automation"""
        ssh_dir = Path.home() / ".ssh"
        automation_key = ssh_dir / "quanttime_automation"
        
        if automation_key.exists():
            logger.info("✅ SSH automation key exists")
            
            # Update settings.txt with key path
            try:
                settings_content = self.settings_file.read_text()
                if "SSH_AUTOMATION_PRIVATE_KEY_PATH=" in settings_content:
                    # Update the path
                    lines = settings_content.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith("SSH_AUTOMATION_PRIVATE_KEY_PATH="):
                            lines[i] = f"SSH_AUTOMATION_PRIVATE_KEY_PATH={automation_key}"
                        elif line.startswith("GIT_SSH_KEY_PATH="):
                            lines[i] = f"GIT_SSH_KEY_PATH={automation_key}"
                    
                    self.settings_file.write_text('\n'.join(lines))
                    logger.info("✅ SSH key paths updated in settings")
            except Exception as e:
                logger.warning(f"⚠️ Could not update SSH paths in settings: {e}")
            
            return True
        else:
            logger.warning("⚠️ SSH automation key not found")
            logger.info("💡 Run: ssh-keygen -t ed25519 -C 'quanttime-automation' -f ~/.ssh/quanttime_automation")
            return False
    
    def check_system_requirements(self) -> bool:
        """Check system requirements and dependencies"""
        logger.info(f"🖥️ Platform: {platform.system()} {platform.release()}")
        logger.info(f"🐍 Python: {sys.version}")
        
        # Check Git
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"✅ Git: {result.stdout.strip()}")
            else:
                logger.error("❌ Git not found")
                return False
        except FileNotFoundError:
            logger.error("❌ Git not installed")
            return False
        
        # Check SSH
        try:
            result = subprocess.run(["ssh", "-V"], capture_output=True, text=True)
            logger.info("✅ SSH available")
        except FileNotFoundError:
            logger.warning("⚠️ SSH not found")
        
        return True
    
    def setup_dynamic_cluster(self) -> bool:
        """Setup dynamic cluster configuration and node broadcasting"""
        try:
            logger.info("🌐 Configuring dynamic cluster management...")
            
            # Start discovery broadcast to announce this node
            logger.info("📡 Starting node discovery broadcast...")
            
            # Create or update dynamic cluster config
            dynamic_config_file = self.config_dir / "dynamic_cluster_config.json"
            
            # Get local network info
            import socket
            hostname = socket.gethostname()
            
            # Try to get external IP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except:
                local_ip = "127.0.0.1"
            
            # Get resource info
            import psutil
            cpu_count = psutil.cpu_count()
            memory_gb = round(psutil.virtual_memory().total / (1024**3), 1)
            
            # Try to detect GPU
            gpu_count = 0
            try:
                import subprocess
                result = subprocess.run(["nvidia-smi", "--query-gpu=count", "--format=csv,noheader,nounits"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    gpu_count = int(result.stdout.strip())
            except:
                pass
            
            dynamic_config = {
                "node_configuration": {
                    "auto_discovery_enabled": True,
                    "discovery_port": 10002,
                    "sync_interval_seconds": 30,
                    "health_check_interval_seconds": 30
                },
                "local_node": {
                    "hostname": hostname,
                    "platform": self.platform,
                    "address": local_ip,
                    "cluster_port": 10001,
                    "dashboard_port": 8265,
                    "ssh_port": 22,
                    "resources": {
                        "cpu_count": cpu_count,
                        "memory_gb": memory_gb,
                        "gpu_count": gpu_count
                    },
                    "paths": {
                        "project_root": str(self.root_dir),
                        "python_executable": "python"
                    }
                },
                "security": {
                    "ssh_key_path": str(Path.home() / ".ssh" / "quanttime_automation"),
                    "auto_key_exchange": True,
                    "trust_on_first_use": True
                },
                "sync_preferences": {
                    "git_auto_pull": True,
                    "sftp_auto_sync": True,
                    "peer_trust_on_first_use": False
                }
            }
            
            dynamic_config_file.write_text(json.dumps(dynamic_config, indent=2))
            
            logger.info("✅ Dynamic cluster configuration created")
            logger.info(f"🖥️ Local node: {hostname} ({local_ip}) - {cpu_count} CPU, {memory_gb}GB RAM, {gpu_count} GPU")
            
            # Update settings.txt with cluster info
            try:
                settings_content = self.settings_file.read_text()
                cluster_settings = f"""
# Dynamic Cluster Configuration
CLUSTER_AUTO_DISCOVERY=true
CLUSTER_DISCOVERY_PORT=10002
CLUSTER_NODE_HOSTNAME={hostname}
CLUSTER_NODE_IP={local_ip}
CLUSTER_NODE_PORT=10001
CLUSTER_DASHBOARD_PORT=8265
"""
                
                if "# Dynamic Cluster Configuration" not in settings_content:
                    settings_content += cluster_settings
                    self.settings_file.write_text(settings_content)
                    logger.info("✅ Cluster settings added to settings.txt")
                    
            except Exception as e:
                logger.warning(f"⚠️ Could not update cluster settings in settings.txt: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup dynamic cluster: {e}")
            return False
    
    def run_initialization(self, dev_mode: bool = False, prod_mode: bool = False) -> bool:
        """Run complete initialization with dynamic cluster integration"""
        logger.info("🚀 Starting QuantTime initialization...")
        
        steps = [
            ("Python version", self.check_python_version),
            ("System requirements", self.check_system_requirements),
            ("Directories", self.create_directories),
            ("Virtual environment", self.setup_virtual_environment),
            ("Dependencies", lambda: self.install_dependencies(dev_mode)),
            ("Configuration", self.setup_configuration),
            ("Database", self.setup_database),
            ("SSH keys", self.check_ssh_keys),
            ("Dynamic cluster setup", self.setup_dynamic_cluster),
        ]
        
        for step_name, step_func in steps:
            logger.info(f"🔧 {step_name}...")
            if not step_func():
                logger.error(f"❌ Failed: {step_name}")
                return False
        
        logger.info("🎉 QuantTime initialization complete!")
        
        # Print next steps
        logger.info("\n📋 Next steps:")
        logger.info("1. Update settings.txt with your Databento API key")
        logger.info("2. Run: python run.py")
        logger.info("3. 🔍 Node will auto-discover peer QuantTime nodes on network")
        logger.info("4. 🔄 Automatic Git sync will keep all nodes synchronized")
        logger.info("5. 🔑 SSH keys enable secure peer-to-peer communication")
        logger.info("6. 🎯 Jobs can be assigned to any specific node from any node")
        
        return True
    
    def clean_temp_files(self) -> bool:
        """Clean temporary files and caches"""
        try:
            import shutil
            
            temp_dirs = [
                self.root_dir / "temp",
                self.root_dir / "__pycache__",
                self.root_dir / ".pytest_cache",
                self.root_dir / "quanttime" / "__pycache__",
            ]
            
            for temp_dir in temp_dirs:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    logger.info(f"🧹 Cleaned: {temp_dir}")
            
            # Recreate temp directory
            (self.root_dir / "temp").mkdir(exist_ok=True)
            
            logger.info("✅ Cleanup complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
            return False

def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description="QuantTime Setup Script")
    parser.add_argument("--init", action="store_true", help="Initialize project")
    parser.add_argument("--dev", action="store_true", help="Development setup")
    parser.add_argument("--prod", action="store_true", help="Production setup")
    parser.add_argument("--check", action="store_true", help="Check environment")
    parser.add_argument("--update", action="store_true", help="Update dependencies")
    parser.add_argument("--clean", action="store_true", help="Clean temporary files")
    
    args = parser.parse_args()
    
    setup = QuantTimeSetup()
    
    # If no arguments, run basic initialization
    if not any(vars(args).values()):
        return setup.run_initialization()
    
    success = True
    
    if args.check:
        success &= setup.check_system_requirements()
        success &= setup.check_python_version()
        success &= setup.check_ssh_keys()
    
    if args.clean:
        success &= setup.clean_temp_files()
    
    if args.init or args.dev or args.prod:
        dev_mode = args.dev
        success &= setup.run_initialization(dev_mode=dev_mode)
    
    if args.update:
        success &= setup.install_dependencies(dev_mode=args.dev)
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
