#!/usr/bin/env python3
"""
QuantTime Project Setup Script
Comprehensive setup script for the entire project

This script will:
1. Check Python version and dependencies
2. Install all required packages
3. Set up virtual environment
4. Check ports and services
5. Create necessary directories
6. Test imports and functionality
7. Set up configuration files

Usage:
    python scripts/setup_project.py [--force] [--check-only]
"""

import os
import sys
import subprocess
import platform
import argparse
import logging
import json
import socket
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/setup_project.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ProjectSetupManager:
    """Manages complete project setup and verification"""
    
    def __init__(self, force: bool = False, check_only: bool = False):
        self.force = force
        self.check_only = check_only
        self.platform = platform.system().lower()
        self.project_root = Path(__file__).parent.parent
        self.venv_path = self.project_root / ".venv"
        self.setup_log = []
        
        logger.info(f"Initializing project setup for: {self.project_root}")
        logger.info(f"Platform: {self.platform}")
        logger.info(f"Force mode: {self.force}")
        logger.info(f"Check only: {self.check_only}")
    
    def check_python_version(self) -> bool:
        """Check if Python version is compatible"""
        logger.info("Checking Python version...")
        
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 11):
            logger.error(f"Python 3.11+ required, found {version.major}.{version.minor}")
            return False
        
        logger.info(f"✓ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    
    def create_directories(self) -> bool:
        """Create all necessary project directories"""
        logger.info("Creating project directories...")
        
        directories = [
            "data",
            "logs", 
            "cache",
            "temp",
            "config",
            "models",
            "backtests",
            "scripts"
        ]
        
        for directory in directories:
            dir_path = self.project_root / directory
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"✓ Created directory: {directory}")
            except Exception as e:
                logger.error(f"✗ Failed to create directory {directory}: {e}")
                return False
        
        return True
    
    def setup_virtual_environment(self) -> bool:
        """Set up Python virtual environment"""
        if self.check_only:
            logger.info("Skipping virtual environment setup (check-only mode)")
            return True
        
        logger.info("Setting up virtual environment...")
        
        if self.venv_path.exists() and not self.force:
            logger.info(f"Virtual environment already exists at {self.venv_path}")
            return True
        
        if self.venv_path.exists() and self.force:
            logger.info(f"Removing existing virtual environment at {self.venv_path}")
            import shutil
            shutil.rmtree(self.venv_path)
        
        try:
            subprocess.run([sys.executable, "-m", "venv", str(self.venv_path)], check=True)
            logger.info(f"✓ Created virtual environment at {self.venv_path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Failed to create virtual environment: {e}")
            return False
    
    def get_pip_command(self) -> str:
        """Get the appropriate pip command"""
        if self.platform == "windows":
            return str(self.venv_path / "Scripts" / "pip.exe")
        else:
            return str(self.venv_path / "bin" / "pip")
    
    def get_python_command(self) -> str:
        """Get the appropriate python command"""
        if self.platform == "windows":
            return str(self.venv_path / "Scripts" / "python.exe")
        else:
            return str(self.venv_path / "bin" / "python")
    
    def install_dependencies(self) -> bool:
        """Install Python dependencies"""
        if self.check_only:
            logger.info("Skipping dependency installation (check-only mode)")
            return True
        
        logger.info("Installing dependencies...")
        
        pip_cmd = self.get_pip_command()
        requirements_file = self.project_root / "requirements.txt"
        
        if not requirements_file.exists():
            logger.error(f"Requirements file not found: {requirements_file}")
            return False
        
        try:
            # Upgrade pip
            subprocess.run([pip_cmd, "install", "--upgrade", "pip"], check=True)
            logger.info("✓ Upgraded pip")
            
            # Install requirements
            subprocess.run([pip_cmd, "install", "-r", str(requirements_file)], check=True)
            logger.info("✓ Installed requirements.txt dependencies")
            
            # Install project in editable mode
            subprocess.run([pip_cmd, "install", "-e", str(self.project_root)], check=True)
            logger.info("✓ Installed project in editable mode")
            
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Failed to install dependencies: {e}")
            return False
    
    def check_ports(self) -> Dict[str, bool]:
        """Check if required ports are available"""
        logger.info("Checking port availability...")
        
        ports_to_check = {
            "Streamlit": 8501,
            "Ray Dashboard": 8265,
            "Ray Head": 10001,
            "SFTP": 22
        }
        
        port_status = {}
        
        for service, port in ports_to_check.items():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(('localhost', port))
                    if result == 0:
                        logger.warning(f"⚠️ Port {port} ({service}) is already in use")
                        port_status[service] = False
                    else:
                        logger.info(f"✓ Port {port} ({service}) is available")
                        port_status[service] = True
            except Exception as e:
                logger.error(f"✗ Error checking port {port}: {e}")
                port_status[service] = False
        
        return port_status
    
    def test_imports(self) -> Dict[str, bool]:
        """Test importing key modules"""
        logger.info("Testing module imports...")
        
        python_cmd = self.get_python_command()
        
        test_modules = [
            "streamlit",
            "pandas", 
            "numpy",
            "plotly",
            "ray",
            "pysftp",
            "paramiko",
            "lightgbm",
            "torch",
            "transformers",
            "stable_baselines3",
            "optuna",
            "databento"
        ]
        
        import_results = {}
        
        for module in test_modules:
            try:
                subprocess.run([python_cmd, "-c", f"import {module}"], check=True, capture_output=True)
                logger.info(f"✓ {module} imported successfully")
                import_results[module] = True
            except subprocess.CalledProcessError:
                logger.warning(f"✗ Failed to import {module}")
                import_results[module] = False
        
        return import_results
    
    def test_project_imports(self) -> bool:
        """Test importing project modules"""
        logger.info("Testing project module imports...")
        
        python_cmd = self.get_python_command()
        
        project_modules = [
            "quanttime",
            "quanttime.dashboard.app",
            "quanttime.core.ray_manager",
            "quanttime.core.sftp_manager"
        ]
        
        for module in project_modules:
            try:
                subprocess.run([python_cmd, "-c", f"import {module}"], check=True, capture_output=True)
                logger.info(f"✓ {module} imported successfully")
            except subprocess.CalledProcessError as e:
                logger.error(f"✗ Failed to import {module}: {e}")
                return False
        
        return True
    
    def create_config_files(self) -> bool:
        """Create default configuration files"""
        logger.info("Creating configuration files...")
        
        # Create SFTP config template
        sftp_config = {
            "nodes": {
                "laptop": {
                    "host": "localhost",
                    "username": "user",
                    "port": 22,
                    "platform": "windows"
                },
                "r630xl": {
                    "host": "jupiter",
                    "username": "jupiter", 
                    "port": 22,
                    "platform": "linux"
                }
            },
            "sync_settings": {
                "large_file_threshold": 100000000,  # 100MB
                "excluded_patterns": [
                    ".env*",
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
        
        config_dir = self.project_root / "config"
        config_dir.mkdir(exist_ok=True)
        
        try:
            with open(config_dir / "sftp_config.json", 'w') as f:
                json.dump(sftp_config, f, indent=2)
            logger.info("✓ Created SFTP configuration template")
        except Exception as e:
            logger.error(f"✗ Failed to create SFTP config: {e}")
            return False
        
        return True
    
    def run_setup(self) -> bool:
        """Run complete project setup"""
        logger.info("=" * 80)
        logger.info("Starting QuantTime project setup")
        logger.info("=" * 80)
        
        steps = [
            ("Python version check", self.check_python_version),
            ("Creating directories", self.create_directories),
            ("Virtual environment setup", self.setup_virtual_environment),
            ("Installing dependencies", self.install_dependencies),
            ("Creating config files", self.create_config_files)
        ]
        
        for step_name, step_func in steps:
            logger.info(f"\n--- {step_name} ---")
            if not step_func():
                logger.error(f"Setup failed at: {step_name}")
                return False
        
        # Run checks
        logger.info("\n--- System Checks ---")
        
        port_status = self.check_ports()
        import_results = self.test_imports()
        project_imports_ok = self.test_project_imports()
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("SETUP SUMMARY")
        logger.info("=" * 80)
        
        logger.info("\n📊 Port Status:")
        for service, available in port_status.items():
            status = "✅ Available" if available else "❌ In Use"
            logger.info(f"  {service}: {status}")
        
        logger.info("\n📦 Module Imports:")
        successful_imports = sum(import_results.values())
        total_imports = len(import_results)
        logger.info(f"  {successful_imports}/{total_imports} modules imported successfully")
        
        for module, success in import_results.items():
            status = "✅" if success else "❌"
            logger.info(f"  {status} {module}")
        
        logger.info(f"\n🏗️ Project Imports: {'✅ Success' if project_imports_ok else '❌ Failed'}")
        
        # Overall status
        all_ports_available = all(port_status.values())
        all_imports_ok = all(import_results.values())
        
        if all_ports_available and all_imports_ok and project_imports_ok:
            logger.info("\n🎉 SETUP COMPLETED SUCCESSFULLY!")
            logger.info("\nNext steps:")
            logger.info("1. Configure your nodes in config/sftp_config.json")
            logger.info("2. Run: python run.py")
            logger.info("3. Access dashboard at: http://localhost:8501")
            return True
        else:
            logger.warning("\n⚠️ SETUP COMPLETED WITH ISSUES")
            if not all_ports_available:
                logger.warning("  - Some ports are in use")
            if not all_imports_ok:
                logger.warning("  - Some modules failed to import")
            if not project_imports_ok:
                logger.warning("  - Project modules failed to import")
            return False

def main():
    parser = argparse.ArgumentParser(description="QuantTime Project Setup Script")
    parser.add_argument("--force", action="store_true", help="Force recreation of virtual environment")
    parser.add_argument("--check-only", action="store_true", help="Only check system, don't install")
    
    args = parser.parse_args()
    
    # Create setup manager
    setup_manager = ProjectSetupManager(
        force=args.force,
        check_only=args.check_only
    )
    
    # Run setup
    success = setup_manager.run_setup()
    
    if success:
        logger.info("Setup completed successfully!")
        sys.exit(0)
    else:
        logger.error("Setup completed with issues!")
        sys.exit(1)

if __name__ == "__main__":
    main()
