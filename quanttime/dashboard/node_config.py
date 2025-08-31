"""
Node Configuration and Health Monitoring
Comprehensive node management with self-checks and status indicators
"""

import streamlit as st
import paramiko
import json
import logging
import subprocess
import psutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class NodeHealthChecker:
    """Comprehensive node health and configuration checker"""
    
    def __init__(self):
        self.nodes = {
            "laptop": {
                "name": "Development Laptop",
                "host": "localhost",
                "port": 22,
                "description": "Local development machine",
                "quanttime_path": "C:/Users/user/Documents/GitHub/QuantTime",
                "expected_services": ["streamlit", "python", "ray"]
            },
            "r630xl": {
                "name": "R630XL Server",
                "host": "jupiter",
                "port": 22,
                "description": "R630XL compute server",
                "quanttime_path": "/opt/quanttime",
                "expected_services": ["ray", "python", "ssh"]
            },
            "r810": {
                "name": "R810 Server",
                "host": "saturn",
                "port": 22,
                "description": "R810 compute server",
                "quanttime_path": "/opt/quanttime",
                "expected_services": ["ray", "python", "ssh"]
            }
        }
        self.connections = {}
        self.health_status = {}
    
    def check_ssh_connection(self, node_id: str, username: str, password: str) -> Dict[str, Any]:
        """Check SSH connection to a node"""
        node = self.nodes[node_id]
        status = {
            "connected": False,
            "error": None,
            "auth_method": None,
            "response_time": None
        }
        
        try:
            start_time = time.time()
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # For localhost, try without authentication first
            if node["host"] in ["localhost", "127.0.0.1"]:
                try:
                    ssh.connect(
                        node["host"],
                        port=node["port"],
                        username=username,
                        timeout=10
                    )
                    status.update({
                        "connected": True,
                        "auth_method": "localhost",
                        "response_time": time.time() - start_time
                    })
                    self.connections[node_id] = ssh
                    return status
                except Exception as e:
                    logger.warning(f"Localhost connection failed: {e}")
            
            # Try password authentication
            ssh.connect(
                node["host"],
                port=node["port"],
                username=username,
                password=password,
                timeout=10
            )
            
            status.update({
                "connected": True,
                "auth_method": "password",
                "response_time": time.time() - start_time
            })
            self.connections[node_id] = ssh
            
        except Exception as e:
            status["error"] = str(e)
        
        return status
    
    def check_node_resources(self, node_id: str) -> Dict[str, Any]:
        """Check node system resources"""
        if node_id not in self.connections:
            return {"error": "Not connected"}
        
        try:
            ssh = self.connections[node_id]
            
            # Get CPU info
            stdin, stdout, stderr = ssh.exec_command("nproc")
            cpu_cores = int(stdout.read().decode().strip())
            
            # Get memory info
            stdin, stdout, stderr = ssh.exec_command("free -m | grep Mem")
            mem_line = stdout.read().decode().strip()
            total_mem = int(mem_line.split()[1])
            used_mem = int(mem_line.split()[2])
            mem_usage = (used_mem / total_mem) * 100
            
            # Get disk usage
            stdin, stdout, stderr = ssh.exec_command("df -h / | tail -1")
            disk_line = stdout.read().decode().strip()
            disk_usage = int(disk_line.split()[4].replace('%', ''))
            
            # Get load average
            stdin, stdout, stderr = ssh.exec_command("uptime")
            uptime_line = stdout.read().decode().strip()
            load_avg = uptime_line.split('load average:')[1].strip()
            
            return {
                "cpu_cores": cpu_cores,
                "total_memory_mb": total_mem,
                "memory_usage_percent": mem_usage,
                "disk_usage_percent": disk_usage,
                "load_average": load_avg,
                "status": "healthy" if mem_usage < 90 and disk_usage < 90 else "warning"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def check_quanttime_installation(self, node_id: str) -> Dict[str, Any]:
        """Check QuantTime installation on node"""
        if node_id not in self.connections:
            return {"error": "Not connected"}
        
        try:
            ssh = self.connections[node_id]
            node = self.nodes[node_id]
            
            # Check if QuantTime directory exists
            stdin, stdout, stderr = ssh.exec_command(f"test -d {node['quanttime_path']} && echo 'exists'")
            dir_exists = stdout.read().decode().strip() == "exists"
            
            # Check if virtual environment exists
            venv_path = f"{node['quanttime_path']}/.venv"
            stdin, stdout, stderr = ssh.exec_command(f"test -d {venv_path} && echo 'exists'")
            venv_exists = stdout.read().decode().strip() == "exists"
            
            # Check if run.py exists
            stdin, stdout, stderr = ssh.exec_command(f"test -f {node['quanttime_path']}/run.py && echo 'exists'")
            run_py_exists = stdout.read().decode().strip() == "exists"
            
            # Check Python version
            stdin, stdout, stderr = ssh.exec_command("python3 --version")
            python_version = stdout.read().decode().strip()
            
            return {
                "directory_exists": dir_exists,
                "venv_exists": venv_exists,
                "run_py_exists": run_py_exists,
                "python_version": python_version,
                "status": "complete" if all([dir_exists, venv_exists, run_py_exists]) else "incomplete"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def check_ray_status(self, node_id: str) -> Dict[str, Any]:
        """Check Ray cluster status on node"""
        if node_id not in self.connections:
            return {"error": "Not connected"}
        
        try:
            ssh = self.connections[node_id]
            
            # Check if Ray is running
            stdin, stdout, stderr = ssh.exec_command("ps aux | grep ray | grep -v grep")
            ray_processes = stdout.read().decode().strip()
            
            # Check Ray cluster status
            stdin, stdout, stderr = ssh.exec_command("ray status 2>/dev/null || echo 'not_running'")
            ray_status = stdout.read().decode().strip()
            
            # Check Ray dashboard port
            stdin, stdout, stderr = ssh.exec_command("netstat -tlnp | grep :8265 || echo 'not_listening'")
            ray_dashboard = stdout.read().decode().strip()
            
            return {
                "processes_running": len(ray_processes.split('\n')) if ray_processes else 0,
                "cluster_status": ray_status,
                "dashboard_accessible": "not_listening" not in ray_dashboard,
                "status": "running" if ray_processes and "not_running" not in ray_status else "stopped"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def check_services(self, node_id: str) -> Dict[str, Any]:
        """Check expected services on node"""
        if node_id not in self.connections:
            return {"error": "Not connected"}
        
        try:
            ssh = self.connections[node_id]
            node = self.nodes[node_id]
            service_status = {}
            
            for service in node["expected_services"]:
                stdin, stdout, stderr = ssh.exec_command(f"systemctl is-active {service} 2>/dev/null || echo 'not_found'")
                status = stdout.read().decode().strip()
                service_status[service] = status
            
            return {
                "services": service_status,
                "all_healthy": all(status == "active" for status in service_status.values()),
                "status": "healthy" if all(status == "active" for status in service_status.values()) else "issues"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def run_comprehensive_check(self, node_id: str, username: str, password: str) -> Dict[str, Any]:
        """Run comprehensive health check on a node"""
        results = {
            "node_id": node_id,
            "node_name": self.nodes[node_id]["name"],
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }
        
        # Check SSH connection
        ssh_status = self.check_ssh_connection(node_id, username, password)
        results["checks"]["ssh_connection"] = ssh_status
        
        if ssh_status["connected"]:
            # Check resources
            results["checks"]["resources"] = self.check_node_resources(node_id)
            
            # Check QuantTime installation
            results["checks"]["quanttime"] = self.check_quanttime_installation(node_id)
            
            # Check Ray status
            results["checks"]["ray"] = self.check_ray_status(node_id)
            
            # Check services
            results["checks"]["services"] = self.check_services(node_id)
        
        # Determine overall status
        overall_status = self._determine_overall_status(results["checks"])
        results["overall_status"] = overall_status
        
        return results
    
    def _determine_overall_status(self, checks: Dict) -> str:
        """Determine overall node status based on all checks"""
        if "ssh_connection" not in checks or not checks["ssh_connection"]["connected"]:
            return "🔴 Disconnected"
        
        # Check for critical failures
        for check_name, check_result in checks.items():
            if "error" in check_result:
                return "🔴 Error"
        
        # Check for warnings
        warnings = []
        if "resources" in checks and checks["resources"].get("status") == "warning":
            warnings.append("High resource usage")
        if "quanttime" in checks and checks["quanttime"].get("status") == "incomplete":
            warnings.append("Incomplete QuantTime installation")
        if "ray" in checks and checks["ray"].get("status") == "stopped":
            warnings.append("Ray not running")
        if "services" in checks and checks["services"].get("status") == "issues":
            warnings.append("Service issues")
        
        if warnings:
            return "🟡 Warning"
        
        return "🟢 Healthy"
    
    def disconnect_node(self, node_id: str):
        """Disconnect from a node"""
        if node_id in self.connections:
            try:
                self.connections[node_id].close()
                del self.connections[node_id]
            except:
                pass


def render_node_configuration_interface():
    """Render the comprehensive node configuration interface"""
    st.markdown("## 🖥️ Node Configuration & Health Monitoring")
    st.markdown("Comprehensive node management with self-checks and status indicators")
    
    # Initialize health checker
    if "node_health_checker" not in st.session_state:
        st.session_state.node_health_checker = NodeHealthChecker()
    
    checker = st.session_state.node_health_checker
    
    # Node overview
    st.markdown("### 📊 Node Overview")
    
    # Create status cards for each node
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🖥️ Laptop**")
        st.markdown("*Local development machine*")
        if "laptop" in checker.health_status:
            status = checker.health_status["laptop"]["overall_status"]
            if "🟢" in status:
                st.success(status)
            elif "🟡" in status:
                st.warning(status)
            else:
                st.error(status)
        else:
            st.info("Not checked")
    
    with col2:
        st.markdown("**🖥️ R630XL**")
        st.markdown("*R630XL compute server*")
        if "r630xl" in checker.health_status:
            status = checker.health_status["r630xl"]["overall_status"]
            if "🟢" in status:
                st.success(status)
            elif "🟡" in status:
                st.warning(status)
            else:
                st.error(status)
        else:
            st.info("Not checked")
    
    with col3:
        st.markdown("**🖥️ R810**")
        st.markdown("*R810 compute server*")
        if "r810" in checker.health_status:
            status = checker.health_status["r810"]["overall_status"]
            if "🟢" in status:
                st.success(status)
            elif "🟡" in status:
                st.warning(status)
            else:
                st.error(status)
        else:
            st.info("Not checked")
    
    # Node configuration tabs
    st.markdown("### ⚙️ Node Configuration")
    
    node_tabs = st.tabs(["🖥️ Laptop", "🖥️ R630XL", "🖥️ R810"])
    
    for i, node_id in enumerate(["laptop", "r630xl", "r810"]):
        with node_tabs[i]:
            node_info = checker.nodes[node_id]
            
            st.markdown(f"**{node_info['name']}**")
            st.markdown(f"*{node_info['description']}*")
            st.markdown(f"**Host:** `{node_info['host']}:{node_info['port']}`")
            st.markdown(f"**QuantTime Path:** `{node_info['quanttime_path']}`")
            
            # Connection form
            with st.form(key=f"node_config_{node_id}"):
                st.markdown("**Connection Details:**")
                
                username = st.text_input("Username:", key=f"config_username_{node_id}")
                password = st.text_input("Password:", type="password", key=f"config_password_{node_id}")
                
                col1, col2 = st.columns(2)
                with col1:
                    test_connection = st.form_submit_button("🔍 Test Connection")
                with col2:
                    run_health_check = st.form_submit_button("🏥 Run Health Check")
                
                if test_connection:
                    if username and password:
                        with st.spinner("Testing connection..."):
                            ssh_status = checker.check_ssh_connection(node_id, username, password)
                            if ssh_status["connected"]:
                                st.success(f"✅ Connected via {ssh_status['auth_method']}")
                                if ssh_status["response_time"]:
                                    st.info(f"Response time: {ssh_status['response_time']:.2f}s")
                            else:
                                st.error(f"❌ Connection failed: {ssh_status['error']}")
                    else:
                        st.error("Please enter username and password")
                
                if run_health_check:
                    if username and password:
                        with st.spinner("Running comprehensive health check..."):
                            results = checker.run_comprehensive_check(node_id, username, password)
                            checker.health_status[node_id] = results
                            st.rerun()
                    else:
                        st.error("Please enter username and password")
            
            # Display health check results
            if node_id in checker.health_status:
                results = checker.health_status[node_id]
                
                st.markdown("### 📋 Health Check Results")
                
                # Overall status
                overall_status = results["overall_status"]
                if "🟢" in overall_status:
                    st.success(f"**Overall Status:** {overall_status}")
                elif "🟡" in overall_status:
                    st.warning(f"**Overall Status:** {overall_status}")
                else:
                    st.error(f"**Overall Status:** {overall_status}")
                
                # Detailed checks
                for check_name, check_result in results["checks"].items():
                    st.markdown(f"**{check_name.replace('_', ' ').title()}:**")
                    
                    if "error" in check_result:
                        st.error(f"Error: {check_result['error']}")
                    else:
                        # Display check results in a nice format
                        if check_name == "ssh_connection":
                            if check_result["connected"]:
                                st.success(f"✅ Connected via {check_result['auth_method']}")
                                if check_result["response_time"]:
                                    st.info(f"Response time: {check_result['response_time']:.2f}s")
                            else:
                                st.error(f"❌ Not connected: {check_result['error']}")
                        
                        elif check_name == "resources":
                            if "error" not in check_result:
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("CPU Cores", check_result["cpu_cores"])
                                with col2:
                                    st.metric("Memory Usage", f"{check_result['memory_usage_percent']:.1f}%")
                                with col3:
                                    st.metric("Disk Usage", f"{check_result['disk_usage_percent']:.1f}%")
                                st.info(f"Load Average: {check_result['load_average']}")
                        
                        elif check_name == "quanttime":
                            if "error" not in check_result:
                                status_icon = "✅" if check_result["status"] == "complete" else "⚠️"
                                st.write(f"{status_icon} Installation: {check_result['status']}")
                                st.write(f"Python: {check_result['python_version']}")
                                st.write(f"Directory: {'✅' if check_result['directory_exists'] else '❌'}")
                                st.write(f"Virtual Env: {'✅' if check_result['venv_exists'] else '❌'}")
                                st.write(f"run.py: {'✅' if check_result['run_py_exists'] else '❌'}")
                        
                        elif check_name == "ray":
                            if "error" not in check_result:
                                status_icon = "✅" if check_result["status"] == "running" else "❌"
                                st.write(f"{status_icon} Ray Status: {check_result['status']}")
                                st.write(f"Processes: {check_result['processes_running']}")
                                st.write(f"Dashboard: {'✅' if check_result['dashboard_accessible'] else '❌'}")
                        
                        elif check_name == "services":
                            if "error" not in check_result:
                                for service, status in check_result["services"].items():
                                    icon = "✅" if status == "active" else "❌"
                                    st.write(f"{icon} {service}: {status}")
    
    # Global actions
    st.markdown("### 🌐 Global Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🏥 Check All Nodes"):
            st.info("Please use individual node health checks above")
    
    with col2:
        if st.button("📊 Refresh Status"):
            st.rerun()
    
    with col3:
        if st.button("❌ Disconnect All"):
            for node_id in list(checker.connections.keys()):
                checker.disconnect_node(node_id)
            st.rerun()
    
    # Status summary table
    st.markdown("### 📋 Node Status Summary")
    
    if checker.health_status:
        summary_data = []
        for node_id, results in checker.health_status.items():
            node_info = checker.nodes[node_id]
            summary_data.append({
                "Node": node_info["name"],
                "Host": node_info["host"],
                "Status": results["overall_status"],
                "Last Check": results["timestamp"][:19].replace("T", " "),
                "SSH": "✅" if results["checks"]["ssh_connection"]["connected"] else "❌",
                "Resources": "✅" if "resources" in results["checks"] and "error" not in results["checks"]["resources"] else "❌",
                "QuantTime": "✅" if "quanttime" in results["checks"] and results["checks"]["quanttime"].get("status") == "complete" else "❌",
                "Ray": "✅" if "ray" in results["checks"] and results["checks"]["ray"].get("status") == "running" else "❌"
            })
        
        df = pd.DataFrame(summary_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No health check results available. Run health checks on individual nodes above.")
