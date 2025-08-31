#!/usr/bin/env python3
"""
Poetry Setup Script for QuantTime
Installs Poetry and initializes the project environment consistently across all nodes
"""

import os
import sys
import subprocess
import platform
import json
from pathlib import Path
from typing import Optional, List, Dict, Any


class PoetrySetup:
    """Poetry setup and environment management"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.poetry_config_dir = Path.home() / ".config" / "pypoetry"
        self.poetry_bin = self._find_poetry_binary()
    
    def _find_poetry_binary(self) -> Optional[Path]:
        """Find Poetry binary in system"""
        # Check if poetry is already installed
        try:
            result = subprocess.run(
                ["poetry", "--version"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            print(f"✅ Poetry found: {result.stdout.strip()}")
            return Path("poetry")  # Use system poetry
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Check common installation locations
        common_paths = [
            Path.home() / ".local" / "bin" / "poetry",
            Path.home() / ".poetry" / "bin" / "poetry",
            Path("/usr/local/bin/poetry"),
            Path("/usr/bin/poetry"),
        ]
        
        for path in common_paths:
            if path.exists():
                print(f"✅ Poetry found at: {path}")
                return path
        
        return None
    
    def install_poetry(self) -> bool:
        """Install Poetry if not already installed"""
        if self.poetry_bin:
            print("✅ Poetry is already installed")
            return True
        
        print("📦 Installing Poetry...")
        
        try:
            # Use official installer
            install_script = """
import sys
import subprocess
import sysconfig

def install_poetry():
    import urllib.request
    import os
    
    # Download and run official installer
    url = "https://install.python-poetry.org"
    subprocess.check_call([sys.executable, "-m", "pip", "install", "poetry"])
    
    # Configure poetry to install virtual environments in project directory
    subprocess.check_call(["poetry", "config", "virtualenvs.in-project", "true"])
    
install_poetry()
"""
            
            # Run installation
            subprocess.run([sys.executable, "-c", install_script], check=True)
            
            # Verify installation
            result = subprocess.run(
                ["poetry", "--version"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            print(f"✅ Poetry installed successfully: {result.stdout.strip()}")
            
            # Configure poetry
            self._configure_poetry()
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install Poetry: {e}")
            return False
    
    def _configure_poetry(self):
        """Configure Poetry settings"""
        print("⚙️ Configuring Poetry...")
        
        try:
            # Configure virtual environments to be created in project directory
            subprocess.run(["poetry", "config", "virtualenvs.in-project", "true"], check=True)
            
            # Configure virtual environments to use Python version from pyproject.toml
            subprocess.run(["poetry", "config", "virtualenvs.prefer-active-python", "true"], check=True)
            
            # Configure to not create virtual environment if one is already active
            subprocess.run(["poetry", "config", "virtualenvs.create", "true"], check=True)
            
            print("✅ Poetry configured successfully")
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Warning: Could not configure Poetry: {e}")
    
    def install_dependencies(self, dev: bool = False) -> bool:
        """Install project dependencies"""
        print("📦 Installing project dependencies...")
        
        try:
            if dev:
                subprocess.run(["poetry", "install"], check=True)
                print("✅ Development dependencies installed")
            else:
                subprocess.run(["poetry", "install", "--no-dev"], check=True)
                print("✅ Production dependencies installed")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False
    
    def create_environment_file(self) -> bool:
        """Create .env file with default configuration"""
        env_file = self.project_root / ".env"
        
        if env_file.exists():
            print("✅ .env file already exists")
            return True
        
        print("📝 Creating .env file...")
        
        env_content = """# QuantTime Environment Configuration
# This file contains environment-specific configuration
# Copy this to .env.local and modify as needed

# Application settings
QUANTTIME_ENV=development
QUANTTIME_DEBUG=true
QUANTTIME_LOG_LEVEL=INFO

# Database settings
DATABASE_URL=sqlite:///quanttime.db
DATABASE_ECHO=false

# Databento settings
DATABENTO_KEY=your_databento_key_here
DATABENTO_DATASET=GLBX.MDP3

# Server settings
SERVER_HOST=0.0.0.0
SERVER_PORT=5000
SERVER_WORKERS=4

# Ray settings
RAY_DASHBOARD_HOST=0.0.0.0
RAY_DASHBOARD_PORT=8265

# Syncthing settings
SYNCTHING_API_KEY=your_syncthing_api_key_here
SYNCTHING_HOST=localhost
SYNCTHING_PORT=8384

# Logging settings
LOG_LEVEL=INFO
LOG_FILE=logs/quanttime.log
LOG_FORMAT=%(asctime)s [%(levelname)s] [%(name)s] %(message)s

# Model settings
MODEL_CACHE_DIR=models/cache
MODEL_CHECKPOINT_DIR=models/checkpoints

# Data settings
DATA_DIR=data
CACHE_DIR=cache
TEMP_DIR=temp

# Security settings
SECRET_KEY=your_secret_key_here_change_in_production
JWT_SECRET_KEY=your_jwt_secret_key_here_change_in_production

# Development settings
DEBUG=true
RELOAD=true
TESTING=false

# Production settings (override in production)
# QUANTTIME_ENV=production
# QUANTTIME_DEBUG=false
# DEBUG=false
# RELOAD=false
"""
        
        try:
            with open(env_file, 'w') as f:
                f.write(env_content)
            print("✅ .env file created")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create .env file: {e}")
            return False
    
    def create_directories(self) -> bool:
        """Create necessary directories"""
        print("📁 Creating project directories...")
        
        directories = [
            "logs",
            "data",
            "models",
            "cache",
            "temp",
            "config",
            "config/secrets",
            "config/credentials",
            "server/logs",
            "server/data",
            "server/models",
            "server/cache",
            "server/temp",
            "tests",
            "docs",
            "scripts",
            "notebooks",
            "examples"
        ]
        
        try:
            for directory in directories:
                dir_path = self.project_root / directory
                dir_path.mkdir(parents=True, exist_ok=True)
            
            print("✅ Project directories created")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create directories: {e}")
            return False
    
    def generate_poetry_lock(self) -> bool:
        """Generate poetry.lock file"""
        print("🔒 Generating poetry.lock file...")
        
        try:
            subprocess.run(["poetry", "lock"], check=True)
            print("✅ poetry.lock file generated")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to generate poetry.lock: {e}")
            return False
    
    def validate_environment(self) -> bool:
        """Validate the environment setup"""
        print("🔍 Validating environment...")
        
        checks = [
            ("Poetry installed", self.poetry_bin is not None or self._find_poetry_binary() is not None),
            ("pyproject.toml exists", (self.project_root / "pyproject.toml").exists()),
            ("poetry.lock exists", (self.project_root / "poetry.lock").exists()),
            ("requirements.txt exists", (self.project_root / "requirements.txt").exists()),
            ("logs directory", (self.project_root / "logs").exists()),
            ("data directory", (self.project_root / "data").exists()),
            ("models directory", (self.project_root / "models").exists()),
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"  {status} {check_name}")
            if not passed:
                all_passed = False
        
        return all_passed
    
    def run_tests(self) -> bool:
        """Run basic tests to verify installation"""
        print("🧪 Running basic tests...")
        
        try:
            # Test poetry environment
            result = subprocess.run(
                ["poetry", "run", "python", "-c", "import sys; print('Python version:', sys.version)"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✅ Poetry environment test: {result.stdout.strip()}")
            
            # Test basic imports
            test_imports = """
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import torch
import lightgbm as lgb
print('✅ All core dependencies imported successfully')
"""
            
            result = subprocess.run(
                ["poetry", "run", "python", "-c", test_imports],
                capture_output=True,
                text=True,
                check=True
            )
            print(result.stdout.strip())
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Test failed: {e}")
            if e.stderr:
                print(f"Error output: {e.stderr}")
            return False
    
    def setup_complete(self) -> Dict[str, Any]:
        """Complete setup process"""
        print("🚀 Starting QuantTime Poetry Setup")
        print("=" * 50)
        
        results = {
            "poetry_installed": False,
            "dependencies_installed": False,
            "environment_created": False,
            "directories_created": False,
            "lock_generated": False,
            "environment_valid": False,
            "tests_passed": False
        }
        
        # Install Poetry
        results["poetry_installed"] = self.install_poetry()
        if not results["poetry_installed"]:
            print("❌ Poetry installation failed")
            return results
        
        # Generate lock file
        results["lock_generated"] = self.generate_poetry_lock()
        
        # Install dependencies
        results["dependencies_installed"] = self.install_dependencies(dev=True)
        if not results["dependencies_installed"]:
            print("❌ Dependency installation failed")
            return results
        
        # Create directories
        results["directories_created"] = self.create_directories()
        
        # Create environment file
        results["environment_created"] = self.create_environment_file()
        
        # Validate environment
        results["environment_valid"] = self.validate_environment()
        
        # Run tests
        results["tests_passed"] = self.run_tests()
        
        print("\n" + "=" * 50)
        print("📊 Setup Results:")
        for check, passed in results.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check.replace('_', ' ').title()}")
        
        if all(results.values()):
            print("\n🎉 Setup completed successfully!")
            print("\n📋 Next steps:")
            print("  1. Copy .env to .env.local and configure your settings")
            print("  2. Run: poetry run streamlit run quanttime/dashboard/app.py")
            print("  3. Access the dashboard at: http://localhost:8501")
        else:
            print("\n⚠️ Setup completed with some issues. Please review the results above.")
        
        return results


def main():
    """Main setup function"""
    project_root = Path(__file__).parent
    
    setup = PoetrySetup(project_root)
    results = setup.setup_complete()
    
    # Return appropriate exit code
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
