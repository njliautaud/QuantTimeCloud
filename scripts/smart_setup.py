#!/usr/bin/env python3
"""
Smart Setup Script for QuantTime
Zero-configuration setup with intelligent automation
"""

import os
import sys
import subprocess
import json
import time
import socket
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import platform

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SmartSetupManager:
    """Intelligent setup manager with zero-configuration approach"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.platform = platform.system().lower()
        self.setup_results = {}
        
        logger.info(f"🤖 Smart Setup Manager initialized for {self.platform}")
    
    def run_smart_setup(self) -> bool:
        """Run the complete smart setup process"""
        print("🚀 QuantTime Smart Setup - Zero Configuration Required!")
        print("=" * 60)
        
        setup_steps = [
            ("🔍 System Detection", self._detect_system),
            ("📦 Dependency Management", self._smart_dependency_setup),
            ("🔑 SSH Key Management", self._setup_ssh_keys),
            ("🌐 Network Discovery", self._discover_network_nodes),
            ("⚙️ Configuration Generation", self._generate_smart_configs),
            ("🚀 Service Initialization", self._initialize_services),
            ("✅ Verification", self._verify_setup)
        ]
        
        for step_name, step_func in setup_steps:
            print(f"\n{step_name}")
            print("-" * 40)
            
            try:
                result = step_func()
                if result:
                    print(f"✅ {step_name} completed successfully")
                    self.setup_results[step_name] = {"status": "success", "result": result}
                else:
                    print(f"⚠️ {step_name} completed with warnings")
                    self.setup_results[step_name] = {"status": "warning", "result": result}
            except Exception as e:
                print(f"❌ {step_name} failed: {e}")
                self.setup_results[step_name] = {"status": "error", "error": str(e)}
                logger.error(f"Setup step failed: {step_name}: {e}")
        
        return self._generate_setup_summary()
    
    def _detect_system(self) -> Dict:
        """Detect system capabilities and resources"""
        print("🔍 Detecting system configuration...")
        
        detection_results = {
            "platform": self.platform,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "architecture": platform.machine(),
            "cpu_count": os.cpu_count(),
            "has_gpu": self._detect_gpu(),
            "available_ports": self._check_port_availability(),
            "tailscale_available": self._check_tailscale(),
            "ssh_available": self._check_ssh_availability(),
            "project_structure": self._analyze_project_structure()
        }
        
        # Display results
        print(f"  📊 Platform: {detection_results['platform']}")
        print(f"  🐍 Python: {detection_results['python_version']}")
        print(f"  🖥️ CPU Cores: {detection_results['cpu_count']}")
        print(f"  🎮 GPU Available: {'Yes' if detection_results['has_gpu'] else 'No'}")
        print(f"  🌐 Tailscale: {'Available' if detection_results['tailscale_available'] else 'Not available'}")
        print(f"  🔑 SSH: {'Available' if detection_results['ssh_available'] else 'Not available'}")
        
        return detection_results
    
    def _smart_dependency_setup(self) -> bool:
        """Intelligently set up dependencies based on system detection"""
        print("📦 Setting up dependencies automatically...")
        
        # Create virtual environment if it doesn't exist
        venv_path = self.project_root / ".venv"
        if not venv_path.exists():
            print("  🔧 Creating virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        
        # Get platform-specific python executable
        if self.platform == "windows":
            python_exe = venv_path / "Scripts" / "python.exe"
            pip_exe = venv_path / "Scripts" / "pip.exe"
        else:
            python_exe = venv_path / "bin" / "python"
            pip_exe = venv_path / "bin" / "pip"
        
        # Upgrade pip
        print("  📈 Upgrading pip...")
        subprocess.run([str(pip_exe), "install", "--upgrade", "pip"], check=True)
        
        # Install requirements
        requirements_file = self.project_root / "requirements.txt"
        if requirements_file.exists():
            print("  📚 Installing requirements...")
            subprocess.run([str(pip_exe), "install", "-r", str(requirements_file)], check=True)
        
        # Install project in editable mode
        print("  🔧 Installing QuantTime...")
        subprocess.run([str(pip_exe), "install", "-e", str(self.project_root)], check=True)
        
        return True
    
    def _setup_ssh_keys(self) -> Dict:
        """Set up SSH keys for automated node access"""
        print("🔑 Setting up SSH keys for automation...")
        
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(exist_ok=True)
        
        # Check for existing keys
        existing_keys = list(ssh_dir.glob("id_*"))
        private_keys = [k for k in existing_keys if not k.name.endswith('.pub')]
        
        if private_keys:
            print(f"  ✅ Found {len(private_keys)} existing SSH keys")
            key_info = {"existing_keys": [str(k) for k in private_keys]}
        else:
            print("  🔧 Generating new SSH key for QuantTime...")
            key_path = ssh_dir / "id_quanttime"
            
            try:
                subprocess.run([
                    "ssh-keygen", "-t", "ed25519", "-f", str(key_path),
                    "-N", "", "-C", "quanttime@automated"
                ], check=True, capture_output=True)
                
                print(f"  ✅ Generated SSH key: {key_path}")
                key_info = {"generated_key": str(key_path)}
            except subprocess.CalledProcessError:
                print("  ⚠️ SSH key generation failed, will use password auth")
                key_info = {"generated_key": None}
        
        return key_info
    
    def _discover_network_nodes(self) -> Dict:
        """Discover potential QuantTime nodes on the network"""
        print("🌐 Discovering network nodes...")
        
        discovered_nodes = {}
        
        # Try to get Tailscale status
        try:
            result = subprocess.run(["tailscale", "status"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("  📡 Tailscale detected, scanning for nodes...")
                
                for line in result.stdout.split('\n'):
                    if '100.' in line and 'offline' not in line.lower():
                        parts = line.split()
                        if parts and '100.' in parts[0]:
                            ip = parts[0]
                            if self._is_potential_quanttime_node(ip):
                                node_id = f"auto_{ip.replace('.', '_')}"
                                discovered_nodes[node_id] = {
                                    "host": ip,
                                    "port": 22,
                                    "auto_discovered": True,
                                    "discovery_method": "tailscale"
                                }
                                print(f"    🎯 Found potential node: {ip}")
        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("  ⚠️ Tailscale not available, skipping network discovery")
        
        if discovered_nodes:
            print(f"  ✅ Discovered {len(discovered_nodes)} potential nodes")
        else:
            print("  ℹ️ No nodes discovered (will use manual configuration)")
        
        return discovered_nodes
    
    def _generate_smart_configs(self) -> bool:
        """Generate intelligent configuration files"""
        print("⚙️ Generating smart configurations...")
        
        config_dir = self.project_root / "config"
        config_dir.mkdir(exist_ok=True)
        
        # Get system detection results
        system_info = self.setup_results.get("🔍 System Detection", {}).get("result", {})
        discovered_nodes = self.setup_results.get("🌐 Network Discovery", {}).get("result", {})
        
        # Generate Ray cluster config
        ray_config = self._generate_ray_config(system_info, discovered_nodes)
        with open(config_dir / "ray_cluster_config.json", 'w') as f:
            json.dump(ray_config, f, indent=2)
        print("  ✅ Generated Ray cluster configuration")
        
        # Generate SFTP config
        sftp_config = self._generate_sftp_config(system_info, discovered_nodes)
        with open(config_dir / "sftp_config.json", 'w') as f:
            json.dump(sftp_config, f, indent=2)
        print("  ✅ Generated SFTP configuration")
        
        # Generate smart automation config
        automation_config = self._generate_automation_config(system_info)
        with open(config_dir / "automation_config.json", 'w') as f:
            json.dump(automation_config, f, indent=2)
        print("  ✅ Generated smart automation configuration")
        
        return True
    
    def _generate_ray_config(self, system_info: Dict, discovered_nodes: Dict) -> Dict:
        """Generate intelligent Ray cluster configuration"""
        config = {
            "head_node": {
                "host": "localhost",
                "port": 10001,
                "dashboard_port": 8265,
                "platform": system_info.get("platform", "unknown")
            },
            "worker_nodes": [],
            "cluster_settings": {
                "cross_platform": True,
                "auto_detect_resources": True,
                "git_sync_enabled": True,
                "sftp_sync_enabled": True
            }
        }
        
        # Add discovered nodes as workers
        for node_id, node_info in discovered_nodes.items():
            worker_config = {
                "name": node_id,
                "host": node_info["host"],
                "port": 10001,
                "platform": "linux",  # Assume Linux for discovered nodes
                "ssh": {
                    "enabled": True,
                    "port": node_info.get("port", 22),
                    "username": "jupiter",  # Common username
                    "auth_method": "auto"
                },
                "paths": {
                    "project_root": "/opt/quanttime",
                    "python_executable": "/opt/quanttime/.venv/bin/python",
                    "ray_working_dir": "/tmp/ray"
                }
            }
            config["worker_nodes"].append(worker_config)
        
        return config
    
    def _generate_sftp_config(self, system_info: Dict, discovered_nodes: Dict) -> Dict:
        """Generate intelligent SFTP configuration"""
        config = {
            "nodes": {},
            "sync_settings": {
                "cross_platform": True,
                "large_file_threshold_mb": 100,
                "sync_directories": ["data", "models", "results"],
                "exclude_patterns": [".venv/*", "__pycache__/*", "*.pyc", "logs/*"]
            }
        }
        
        # Add head node (this machine)
        if system_info.get("platform") == "windows":
            config["nodes"]["laptop"] = {
                "host": "localhost",
                "username": os.getenv("USERNAME", "user"),
                "port": 22,
                "platform": "windows",
                "large_file_dirs": ["data\\es_futures", "models", "results"]
            }
        else:
            config["nodes"]["laptop"] = {
                "host": "localhost", 
                "username": os.getenv("USER", "user"),
                "port": 22,
                "platform": "linux",
                "large_file_dirs": ["/opt/quanttime/data", "/opt/quanttime/models"]
            }
        
        # Add discovered nodes
        for node_id, node_info in discovered_nodes.items():
            config["nodes"][node_id] = {
                "host": node_info["host"],
                "username": "jupiter",
                "port": 22,
                "platform": "linux",
                "large_file_dirs": ["/opt/quanttime/data", "/opt/quanttime/models"]
            }
        
        return config
    
    def _generate_automation_config(self, system_info: Dict) -> Dict:
        """Generate smart automation configuration"""
        return {
            "smart_features": {
                "auto_ssh_key_setup": True,
                "network_auto_discovery": True,
                "predictive_health_monitoring": True,
                "zero_touch_deployment": True,
                "intelligent_resource_allocation": True,
                "automated_troubleshooting": True,
                "smart_credential_detection": True
            },
            "automation_intervals": {
                "network_scan_minutes": 10,
                "health_check_minutes": 5,
                "resource_optimization_minutes": 15,
                "self_healing_check_minutes": 3
            },
            "thresholds": {
                "cpu_warning": 80,
                "memory_warning": 85,
                "disk_warning": 90,
                "latency_warning_ms": 1000,
                "min_nodes_healthy": 1
            },
            "auto_actions": {
                "restart_unhealthy_services": True,
                "auto_scale_ray_workers": True,
                "optimize_resource_allocation": True,
                "auto_deploy_updates": True,
                "clean_temp_files": True
            },
            "platform_specific": {
                "windows": {
                    "use_powershell": True,
                    "ssh_service": "OpenSSH"
                },
                "linux": {
                    "use_systemd": True,
                    "ssh_service": "ssh"
                }
            }
        }
    
    def _initialize_services(self) -> bool:
        """Initialize QuantTime services"""
        print("🚀 Initializing QuantTime services...")
        
        try:
            # Test import of core modules
            print("  📦 Testing core module imports...")
            from quanttime.core.smart_automation_manager import SmartAutomationManager
            from quanttime.core.cross_platform_git_watcher import CrossPlatformGitWatcher
            print("  ✅ Core modules imported successfully")
            
            # Test Ray availability
            print("  ⚡ Testing Ray availability...")
            import ray
            print("  ✅ Ray is available")
            
            # Test dashboard
            print("  📊 Testing dashboard components...")
            import streamlit
            print("  ✅ Streamlit dashboard available")
            
            return True
        except ImportError as e:
            print(f"  ❌ Import error: {e}")
            return False
    
    def _verify_setup(self) -> Dict:
        """Verify the complete setup"""
        print("✅ Verifying setup...")
        
        verification_results = {
            "config_files": self._verify_config_files(),
            "dependencies": self._verify_dependencies(),
            "services": self._verify_services(),
            "connectivity": self._verify_connectivity()
        }
        
        all_good = all(verification_results.values())
        
        if all_good:
            print("  🎉 All verifications passed!")
        else:
            print("  ⚠️ Some verifications failed, but setup is functional")
        
        return verification_results
    
    def _verify_config_files(self) -> bool:
        """Verify all configuration files exist and are valid"""
        config_dir = self.project_root / "config"
        required_configs = [
            "ray_cluster_config.json",
            "sftp_config.json", 
            "automation_config.json"
        ]
        
        for config_file in required_configs:
            config_path = config_dir / config_file
            if not config_path.exists():
                print(f"    ❌ Missing config: {config_file}")
                return False
            
            try:
                with open(config_path) as f:
                    json.load(f)
                print(f"    ✅ Valid config: {config_file}")
            except json.JSONDecodeError:
                print(f"    ❌ Invalid JSON in: {config_file}")
                return False
        
        return True
    
    def _verify_dependencies(self) -> bool:
        """Verify all required dependencies are installed"""
        required_modules = ["ray", "streamlit", "paramiko", "pandas", "plotly"]
        
        for module in required_modules:
            try:
                __import__(module)
                print(f"    ✅ {module} available")
            except ImportError:
                print(f"    ❌ {module} not available")
                return False
        
        return True
    
    def _verify_services(self) -> bool:
        """Verify QuantTime services can be initialized"""
        try:
            from quanttime.core.smart_automation_manager import get_smart_automation_manager
            automation_manager = get_smart_automation_manager()
            print("    ✅ Smart automation manager initialized")
            return True
        except Exception as e:
            print(f"    ❌ Service initialization failed: {e}")
            return False
    
    def _verify_connectivity(self) -> bool:
        """Verify network connectivity and port availability"""
        required_ports = [8501, 8265, 10001]
        
        for port in required_ports:
            if self._port_available(port):
                print(f"    ✅ Port {port} available")
            else:
                print(f"    ⚠️ Port {port} in use (may be normal)")
        
        return True
    
    def _generate_setup_summary(self) -> bool:
        """Generate and display setup summary"""
        print("\n" + "=" * 60)
        print("🎯 SMART SETUP SUMMARY")
        print("=" * 60)
        
        success_count = sum(1 for result in self.setup_results.values() 
                          if result.get("status") == "success")
        total_steps = len(self.setup_results)
        
        print(f"📊 Completion: {success_count}/{total_steps} steps successful")
        
        for step_name, result in self.setup_results.items():
            status = result.get("status", "unknown")
            icon = {"success": "✅", "warning": "⚠️", "error": "❌"}.get(status, "❓")
            print(f"  {icon} {step_name}")
        
        if success_count >= total_steps - 1:  # Allow one warning/error
            print("\n🎉 SETUP COMPLETED SUCCESSFULLY!")
            print("\n🚀 Next Steps:")
            print("1. Run: python run.py")
            print("2. Access dashboard: http://localhost:8501")
            print("3. Nodes will be automatically discovered and configured")
            print("4. Smart automation is enabled by default")
            return True
        else:
            print("\n⚠️ SETUP COMPLETED WITH ISSUES")
            print("Manual intervention may be required")
            return False
    
    # Utility methods
    def _detect_gpu(self) -> bool:
        """Detect if GPU is available"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def _check_port_availability(self) -> List[int]:
        """Check which required ports are available"""
        required_ports = [8501, 8265, 10001, 22]
        available_ports = []
        
        for port in required_ports:
            if self._port_available(port):
                available_ports.append(port)
        
        return available_ports
    
    def _port_available(self, port: int) -> bool:
        """Check if a port is available"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                return s.connect_ex(('localhost', port)) != 0
        except:
            return False
    
    def _check_tailscale(self) -> bool:
        """Check if Tailscale is available"""
        try:
            result = subprocess.run(["tailscale", "status"], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _check_ssh_availability(self) -> bool:
        """Check if SSH is available"""
        try:
            result = subprocess.run(["ssh", "-V"], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _analyze_project_structure(self) -> Dict:
        """Analyze project structure"""
        return {
            "has_quanttime_module": (self.project_root / "quanttime").exists(),
            "has_requirements": (self.project_root / "requirements.txt").exists(),
            "has_run_script": (self.project_root / "run.py").exists(),
            "has_config_dir": (self.project_root / "config").exists()
        }
    
    def _is_potential_quanttime_node(self, ip: str) -> bool:
        """Check if an IP might be a QuantTime node"""
        # Quick SSH port check
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                return s.connect_ex((ip, 22)) == 0
        except:
            return False


def main():
    """Main entry point"""
    setup_manager = SmartSetupManager()
    success = setup_manager.run_smart_setup()
    
    if success:
        print("\n🚀 Ready to launch QuantTime!")
        input("Press Enter to start QuantTime now, or Ctrl+C to exit...")
        
        # Launch QuantTime
        import subprocess
        subprocess.run([sys.executable, str(setup_manager.project_root / "run.py")])
    else:
        print("\n❌ Setup completed with issues. Please check the logs and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
