#!/usr/bin/env python3
"""
QuantTime Installation Script
Simple installation script using setup.py

This script will:
1. Create virtual environment
2. Install QuantTime in development mode
3. Set up all dependencies
4. Create necessary directories

Usage:
    python install.py
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def print_status(message, status="INFO"):
    """Print formatted status message"""
    colors = {
        "INFO": "\033[94m",    # Blue
        "SUCCESS": "\033[92m", # Green
        "WARNING": "\033[93m", # Yellow
        "ERROR": "\033[91m",   # Red
        "RESET": "\033[0m"     # Reset
    }
    print(f"{colors.get(status, colors['INFO'])}[{status}] {message}{colors['RESET']}")

def check_python_version():
    """Check Python version compatibility"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print_status("Python 3.11+ required", "ERROR")
        return False
    print_status(f"Python {version.major}.{version.minor}.{version.micro} ✓", "SUCCESS")
    return True

def create_virtual_environment():
    """Create virtual environment"""
    project_root = Path(__file__).parent
    venv_path = project_root / ".venv"
    
    if venv_path.exists():
        print_status("Virtual environment already exists", "INFO")
        return str(venv_path)
    
    print_status("Creating virtual environment...", "INFO")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        print_status("Virtual environment created ✓", "SUCCESS")
        return str(venv_path)
    except subprocess.CalledProcessError:
        print_status("Failed to create virtual environment", "ERROR")
        return None

def get_pip_command(venv_path):
    """Get pip command for virtual environment"""
    if platform.system().lower() == "windows":
        return str(Path(venv_path) / "Scripts" / "pip.exe")
    else:
        return str(Path(venv_path) / "bin" / "pip")

def install_quanttime(venv_path):
    """Install QuantTime in development mode"""
    pip_cmd = get_pip_command(venv_path)
    project_root = Path(__file__).parent
    
    print_status("Installing QuantTime in development mode...", "INFO")
    
    try:
        # Upgrade pip
        subprocess.run([pip_cmd, "install", "--upgrade", "pip"], check=True, capture_output=True)
        print_status("Pip upgraded ✓", "SUCCESS")
        
        # Install QuantTime in development mode
        subprocess.run([pip_cmd, "install", "-e", str(project_root)], check=True, capture_output=True)
        print_status("QuantTime installed ✓", "SUCCESS")
        
        return True
    except subprocess.CalledProcessError as e:
        print_status(f"Failed to install QuantTime: {e}", "ERROR")
        return False

def create_directories():
    """Create necessary project directories"""
    directories = ["data", "logs", "cache", "temp", "config", "models", "backtests"]
    project_root = Path(__file__).parent
    
    for directory in directories:
        dir_path = project_root / directory
        dir_path.mkdir(exist_ok=True)
    
    print_status("Project directories created ✓", "SUCCESS")

def test_installation(venv_path):
    """Test the installation"""
    if platform.system().lower() == "windows":
        python_cmd = str(Path(venv_path) / "Scripts" / "python.exe")
    else:
        python_cmd = str(Path(venv_path) / "bin" / "python")
    
    print_status("Testing installation...", "INFO")
    
    test_script = """
import sys
try:
    import quanttime
    print(f"QuantTime version: {quanttime.__version__}")
    print("SUCCESS")
except ImportError as e:
    print(f"FAILED: {e}")
    sys.exit(1)
"""
    
    try:
        result = subprocess.run([python_cmd, "-c", test_script], 
                              capture_output=True, text=True, check=True)
        if "SUCCESS" in result.stdout:
            print_status("Installation test successful ✓", "SUCCESS")
            return True
        else:
            print_status("Installation test failed", "ERROR")
            return False
    except subprocess.CalledProcessError:
        print_status("Installation test failed", "ERROR")
        return False

def main():
    """Main installation function"""
    print_status("=" * 60, "INFO")
    print_status("QuantTime Installation", "INFO")
    print_status("=" * 60, "INFO")
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Create virtual environment
    venv_path = create_virtual_environment()
    if not venv_path:
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Install QuantTime
    if not install_quanttime(venv_path):
        sys.exit(1)
    
    # Test installation
    if not test_installation(venv_path):
        sys.exit(1)
    
    print_status("=" * 60, "SUCCESS")
    print_status("Installation completed successfully!", "SUCCESS")
    print_status("=" * 60, "SUCCESS")
    
    print_status("\nNext steps:", "INFO")
    print_status("1. Activate virtual environment:", "INFO")
    if platform.system().lower() == "windows":
        print_status(f"   .venv\\Scripts\\activate", "INFO")
    else:
        print_status(f"   source .venv/bin/activate", "INFO")
    
    print_status("2. Run the dashboard:", "INFO")
    print_status("   python run.py", "INFO")
    print_status("   or", "INFO")
    print_status("   python start_quanttime.py", "INFO")

if __name__ == "__main__":
    main()
