#!/usr/bin/env python3
"""
QuantTime Server Deployment Script

Quick deployment and troubleshooting tool for distributed development.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

class ServerDeployer:
    def __init__(self, config_path: str = "server/config/servers.json"):
        self.config_path = config_path
        self.servers = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load server configuration"""
        with open(self.config_path, 'r') as f:
            return json.load(f)
    
    def deploy_to_server(self, server_name: str, restart_services: bool = True) -> bool:
        """Deploy current code to specific server"""
        if server_name not in self.servers:
            print(f"❌ Server '{server_name}' not found in config")
            return False
            
        server = self.servers[server_name]
        ip = server.get('tailscale_ip') or server['ip_address']
        username = server['username']
        
        print(f"🚀 Deploying to {server_name} ({ip})...")
        
        try:
            # 1. Sync code to server
            print("📤 Syncing code...")
            sync_cmd = [
                'rsync', '-avz', '--exclude=.git', '--exclude=__pycache__', 
                '--exclude=*.pyc', '--exclude=.venv', './', 
                f'{username}@{ip}:/opt/quanttime/'
            ]
            result = subprocess.run(sync_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ Sync failed: {result.stderr}")
                return False
                
            print("✅ Code synced successfully")
            
            # 2. Install dependencies if needed
            print("📦 Installing dependencies...")
            install_cmd = f"""
            ssh {username}@{ip} << 'EOF'
            cd /opt/quanttime
            source .venv/bin/activate
            pip install -r requirements.txt
            echo "✅ Dependencies installed"
            EOF
            """
            result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"⚠️ Dependency install warning: {result.stderr}")
            
            # 3. Restart services if requested
            if restart_services:
                print("🔄 Restarting services...")
                restart_cmd = f"""
                ssh {username}@{ip} << 'EOF'
                cd /opt/quanttime
                bash server/scripts/start_all_services.sh
                echo "✅ Services restarted"
                EOF
                """
                result = subprocess.run(restart_cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"⚠️ Service restart warning: {result.stderr}")
                else:
                    print("✅ Services restarted")
            
            print(f"🎉 Deployment to {server_name} complete!")
            return True
            
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            return False
    
    def deploy_all(self, restart_services: bool = True) -> bool:
        """Deploy to all servers"""
        success = True
        for server_name in self.servers.keys():
            if server_name != 'laptop':
                if not self.deploy_to_server(server_name, restart_services):
                    success = False
        return success
    
    def check_server_status(self, server_name: str) -> Dict:
        """Check status of specific server"""
        if server_name not in self.servers:
            return {"error": f"Server '{server_name}' not found"}
            
        server = self.servers[server_name]
        ip = server.get('tailscale_ip') or server['ip_address']
        username = server['username']
        
        try:
            # Check SSH connectivity
            ssh_cmd = f"ssh {username}@{ip} 'echo SSH_OK'"
            ssh_result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
            
            if ssh_result.returncode != 0:
                return {"status": "offline", "error": "SSH failed"}
            
            # Check API health
            api_cmd = f"ssh {username}@{ip} 'curl -s http://localhost:8000/api/v1/server/health'"
            api_result = subprocess.run(api_cmd, shell=True, capture_output=True, text=True)
            
            if api_result.returncode == 0 and api_result.stdout:
                try:
                    health_data = json.loads(api_result.stdout)
                    return {"status": "online", "health": health_data}
                except:
                    return {"status": "partial", "error": "API response invalid"}
            else:
                return {"status": "partial", "error": "API not responding"}
                
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_logs(self, server_name: str, service: str = "all", lines: int = 50) -> str:
        """Get logs from server"""
        if server_name not in self.servers:
            return f"Server '{server_name}' not found"
            
        server = self.servers[server_name]
        ip = server.get('tailscale_ip') or server['ip_address']
        username = server['username']
        
        try:
            if service == "all":
                log_cmd = f"""
                ssh {username}@{ip} << 'EOF'
                echo "=== System Logs ==="
                journalctl -u quanttime-* --no-pager -n {lines}
                echo "=== Application Logs ==="
                tail -n {lines} /opt/quanttime/logs/*.log 2>/dev/null || echo "No log files found"
                EOF
                """
            else:
                log_cmd = f"""
                ssh {username}@{ip} << 'EOF'
                echo "=== {service} Logs ==="
                journalctl -u quanttime-{service} --no-pager -n {lines}
                EOF
                """
            
            result = subprocess.run(log_cmd, shell=True, capture_output=True, text=True)
            return result.stdout if result.returncode == 0 else result.stderr
            
        except Exception as e:
            return f"Failed to get logs: {e}"
    
    def quick_fix(self, server_name: str, issue: str) -> bool:
        """Quick fixes for common issues"""
        if server_name not in self.servers:
            print(f"❌ Server '{server_name}' not found")
            return False
            
        server = self.servers[server_name]
        ip = server.get('tailscale_ip') or server['ip_address']
        username = server['username']
        
        fixes = {
            "services_down": f"""
            ssh {username}@{ip} << 'EOF'
            sudo systemctl restart quanttime-*
            echo "✅ Services restarted"
            EOF
            """,
            
            "permissions": f"""
            ssh {username}@{ip} << 'EOF'
            sudo chown -R quanttime:quanttime /opt/quanttime
            sudo chmod -R 755 /opt/quanttime
            echo "✅ Permissions fixed"
            EOF
            """,
            
            "redis": f"""
            ssh {username}@{ip} << 'EOF'
            sudo systemctl restart redis-server
            echo "✅ Redis restarted"
            EOF
            """,
            
            "postgres": f"""
            ssh {username}@{ip} << 'EOF'
            sudo systemctl restart postgresql
            echo "✅ PostgreSQL restarted"
            EOF
            """
        }
        
        if issue in fixes:
            print(f"🔧 Applying quick fix for '{issue}'...")
            result = subprocess.run(fixes[issue], shell=True, capture_output=True, text=True)
            return result.returncode == 0
        else:
            print(f"❌ No quick fix available for '{issue}'")
            return False

def main():
    deployer = ServerDeployer()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/deploy_to_servers.py deploy <server_name>")
        print("  python scripts/deploy_to_servers.py deploy-all")
        print("  python scripts/deploy_to_servers.py status <server_name>")
        print("  python scripts/deploy_to_servers.py logs <server_name> [service]")
        print("  python scripts/deploy_to_servers.py fix <server_name> <issue>")
        return
    
    command = sys.argv[1]
    
    if command == "deploy":
        server_name = sys.argv[2] if len(sys.argv) > 2 else "r630xl"
        deployer.deploy_to_server(server_name)
        
    elif command == "deploy-all":
        deployer.deploy_all()
        
    elif command == "status":
        server_name = sys.argv[2] if len(sys.argv) > 2 else "r630xl"
        status = deployer.check_server_status(server_name)
        print(json.dumps(status, indent=2))
        
    elif command == "logs":
        server_name = sys.argv[2] if len(sys.argv) > 2 else "r630xl"
        service = sys.argv[3] if len(sys.argv) > 3 else "all"
        logs = deployer.get_logs(server_name, service)
        print(logs)
        
    elif command == "fix":
        server_name = sys.argv[2] if len(sys.argv) > 2 else "r630xl"
        issue = sys.argv[3] if len(sys.argv) > 3 else "services_down"
        deployer.quick_fix(server_name, issue)

if __name__ == "__main__":
    main()
