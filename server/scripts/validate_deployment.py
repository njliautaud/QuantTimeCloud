"""
QuantTime Deployment Validation Script

Validates that the distributed computing cluster is properly configured
and ready for deployment.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

import requests
import redis
import psutil

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeploymentValidator:
    """Validates QuantTime distributed computing deployment"""
    
    def __init__(self):
        """Initialize validator"""
        self.errors = []
        self.warnings = []
        self.checks_passed = 0
        self.total_checks = 0
        
    def validate_all(self) -> bool:
        """Run all validation checks"""
        logger.info("🔍 Validating QuantTime Distributed Computing Deployment")
        logger.info("=" * 60)
        
        # Core validation checks
        self._validate_project_structure()
        self._validate_dependencies()
        self._validate_configuration()
        self._validate_server_code()
        self._validate_dashboard_integration()
        self._validate_sync_system()
        self._validate_deployment_scripts()
        
        # Print results
        self._print_results()
        
        return len(self.errors) == 0
    
    def _check(self, description: str, condition: bool, error_msg: str = None, warning_msg: str = None):
        """Perform a validation check"""
        self.total_checks += 1
        
        if condition:
            self.checks_passed += 1
            logger.info(f"✅ {description}")
        else:
            logger.error(f"❌ {description}")
            if error_msg:
                self.errors.append(error_msg)
            elif warning_msg:
                self.warnings.append(warning_msg)
            else:
                self.errors.append(f"Failed: {description}")
    
    def _validate_project_structure(self):
        """Validate project directory structure"""
        logger.info("\n📁 Validating Project Structure")
        
        required_files = [
            "server/core/server_api.py",
            "server/core/job_manager.py", 
            "server/core/resource_monitor.py",
            "server/core/sync_manager.py",
            "server/core/health_checker.py",
            "server/core/auth.py",
            "server/scripts/celery_app.py",
            "server/scripts/server_main.py",
            "server/setup/install.sh",
            "server/setup/configure_servers.py",
            "server/setup/quick_deploy.sh",
            "server/config/deployment.yaml",
            "server/config/servers.json",
            "quanttime/dashboard/server_control.py",
            "requirements.txt",
            "DEPLOYMENT_GUIDE.md"
        ]
        
        for file_path in required_files:
            exists = Path(file_path).exists()
            self._check(f"Required file exists: {file_path}", exists)
        
        required_dirs = [
            "server/core",
            "server/scripts", 
            "server/setup",
            "server/config",
            "quanttime/dashboard"
        ]
        
        for dir_path in required_dirs:
            exists = Path(dir_path).exists()
            self._check(f"Required directory exists: {dir_path}", exists)
    
    def _validate_dependencies(self):
        """Validate Python dependencies"""
        logger.info("\n📦 Validating Dependencies")
        
        required_packages = [
            "fastapi", "uvicorn", "celery", "redis", 
            "psutil", "requests", "streamlit", "pandas", "numpy",
            "pydantic", "pyarrow"
        ]
        
        optional_packages = [
            "paramiko", "psycopg2"  # These might not be installed on Windows
        ]
        
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
                self._check(f"Package available: {package}", True)
            except ImportError:
                self._check(f"Package available: {package}", False, 
                           f"Missing required package: {package}")
        
        for package in optional_packages:
            try:
                __import__(package.replace("-", "_"))
                self._check(f"Optional package available: {package}", True)
            except ImportError:
                self._check(f"Optional package available: {package}", False, 
                           warning_msg=f"Optional package not installed: {package} (will install on servers)")
    
    def _validate_configuration(self):
        """Validate configuration files"""
        logger.info("\n⚙️ Validating Configuration")
        
        # Check deployment.yaml
        deployment_config = Path("server/config/deployment.yaml")
        if deployment_config.exists():
            self._check("Deployment config exists", True)
            try:
                import yaml
                with open(deployment_config) as f:
                    config = yaml.safe_load(f)
                self._check("Deployment config is valid YAML", True)
            except Exception as e:
                self._check("Deployment config is valid YAML", False, 
                           f"Invalid YAML in deployment config: {e}")
        
        # Check servers.json
        servers_config = Path("server/config/servers.json")
        if servers_config.exists():
            self._check("Servers config exists", True)
            try:
                with open(servers_config) as f:
                    config = json.load(f)
                
                required_servers = ["laptop", "r630xl", "r810"]
                for server in required_servers:
                    has_server = server in config
                    self._check(f"Server config for {server}", has_server)
            except Exception as e:
                self._check("Servers config is valid JSON", False,
                           f"Invalid JSON in servers config: {e}")
    
    def _validate_server_code(self):
        """Validate server implementation"""
        logger.info("\n🖥️ Validating Server Implementation")
        
        # Test imports
        try:
            from server.core.server_api import app
            self._check("Server API imports successfully", True)
        except Exception as e:
            self._check("Server API imports successfully", False,
                       f"Server API import error: {e}")
        
        try:
            from server.core.job_manager import JobManager
            self._check("Job Manager imports successfully", True)
        except Exception as e:
            self._check("Job Manager imports successfully", False,
                       f"Job Manager import error: {e}")
        
        try:
            from server.core.resource_monitor import ResourceMonitor
            self._check("Resource Monitor imports successfully", True)
        except Exception as e:
            self._check("Resource Monitor imports successfully", False,
                       f"Resource Monitor import error: {e}")
        
        try:
            from server.core.sync_manager import SyncManager
            self._check("Sync Manager imports successfully", True)
        except Exception as e:
            self._check("Sync Manager imports successfully", False,
                       f"Sync Manager import error: {e}")
        
        try:
            from server.core.health_checker import HealthChecker
            self._check("Health Checker imports successfully", True)
        except Exception as e:
            self._check("Health Checker imports successfully", False,
                       f"Health Checker import error: {e}")
    
    def _validate_dashboard_integration(self):
        """Validate dashboard integration"""
        logger.info("\n📊 Validating Dashboard Integration")
        
        try:
            from quanttime.dashboard.server_control import ServerControlCenter
            self._check("Server Control Center imports successfully", True)
        except Exception as e:
            self._check("Server Control Center imports successfully", False,
                       f"Server Control import error: {e}")
        
        # Check dashboard app integration
        dashboard_app = Path("quanttime/dashboard/app.py")
        if dashboard_app.exists():
            with open(dashboard_app, encoding='utf-8') as f:
                content = f.read()
            
            has_server_import = "server_control" in content
            self._check("Dashboard has server control import", has_server_import)
            
            has_servers_tab = "servers_tab" in content
            self._check("Dashboard has servers tab", has_servers_tab)
    
    def _validate_sync_system(self):
        """Validate file synchronization system"""
        logger.info("\n🔄 Validating Sync System")
        
        # Check sync manager implementation
        sync_manager_file = Path("server/core/sync_manager.py")
        if sync_manager_file.exists():
            with open(sync_manager_file) as f:
                content = f.read()
            
            has_transfer_methods = "transfer_file" in content
            self._check("Sync manager has transfer methods", has_transfer_methods)
            
            has_conflict_resolution = "resolve_conflict" in content
            self._check("Sync manager has conflict resolution", has_conflict_resolution)
        
        # Check distributed sync implementation
        distributed_sync_file = Path("server/core/distributed_sync.py")
        if distributed_sync_file.exists():
            with open(distributed_sync_file) as f:
                content = f.read()
            
            has_real_time_sync = "sync_loop" in content
            self._check("Distributed sync has real-time sync", has_real_time_sync)
    
    def _validate_deployment_scripts(self):
        """Validate deployment scripts"""
        logger.info("\n🚀 Validating Deployment Scripts")
        
        # Check install script
        install_script = Path("server/setup/install.sh")
        if install_script.exists():
            self._check("Install script exists", True)
            
            # Check if executable (Linux/Mac only)
            if sys.platform != "win32":
                is_executable = os.access(install_script, os.X_OK)
                self._check("Install script is executable", is_executable)
        
        # Check configuration script
        config_script = Path("server/setup/configure_servers.py")
        if config_script.exists():
            self._check("Configuration script exists", True)
            
            try:
                with open(config_script) as f:
                    content = f.read()
                
                has_ssh_setup = "setup_ssh_keys" in content
                self._check("Config script has SSH setup", has_ssh_setup)
                
                has_deployment = "deploy_to_servers" in content
                self._check("Config script has deployment logic", has_deployment)
            except Exception as e:
                self._check("Configuration script is readable", False,
                           f"Cannot read config script: {e}")
        
        # Check quick deploy script
        quick_deploy = Path("server/setup/quick_deploy.sh")
        if quick_deploy.exists():
            self._check("Quick deploy script exists", True)
    
    def _validate_celery_setup(self):
        """Validate Celery configuration"""
        logger.info("\n🔄 Validating Celery Setup")
        
        celery_app_file = Path("server/scripts/celery_app.py")
        if celery_app_file.exists():
            with open(celery_app_file) as f:
                content = f.read()
            
            has_server_queues = "server_laptop" in content
            self._check("Celery has server-specific queues", has_server_queues)
            
            has_distributed_config = "task_routes" in content
            self._check("Celery has distributed routing", has_distributed_config)
    
    def _print_results(self):
        """Print validation results"""
        logger.info("\n" + "=" * 60)
        logger.info("🔍 VALIDATION RESULTS")
        logger.info("=" * 60)
        
        success_rate = (self.checks_passed / self.total_checks) * 100 if self.total_checks > 0 else 0
        
        logger.info(f"✅ Checks Passed: {self.checks_passed}/{self.total_checks} ({success_rate:.1f}%)")
        
        if self.errors:
            logger.error(f"❌ Errors: {len(self.errors)}")
            for error in self.errors:
                logger.error(f"   • {error}")
        
        if self.warnings:
            logger.warning(f"⚠️ Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                logger.warning(f"   • {warning}")
        
        if len(self.errors) == 0:
            logger.info("🎉 DEPLOYMENT VALIDATION PASSED!")
            logger.info("Your QuantTime distributed computing cluster is ready for deployment.")
        else:
            logger.error("❌ DEPLOYMENT VALIDATION FAILED!")
            logger.error("Please fix the errors above before deploying.")
        
        return len(self.errors) == 0

def main():
    """Main validation entry point"""
    validator = DeploymentValidator()
    success = validator.validate_all()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
