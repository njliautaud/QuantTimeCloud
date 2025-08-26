#!/usr/bin/env python3
"""
Server Performance Benchmarking for QuantTime Dashboard.
Tests CPU, memory, disk I/O, and network performance.
"""

import subprocess
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import streamlit as st
import paramiko
import psutil
import numpy as np

class ServerBenchmarker:
    """Benchmarks server performance and compares devices."""
    
    def __init__(self):
        self.benchmark_results = {}
        self.local_benchmark = None
    
    def benchmark_local_system(self) -> Dict:
        """Benchmark the local laptop/desktop system."""
        st.info("🔄 Benchmarking local system...")
        
        results = {
            "device": "Laptop",
            "timestamp": datetime.now().isoformat(),
            "cpu": {},
            "memory": {},
            "disk": {},
            "network": {}
        }
        
        # CPU Benchmark
        start_time = time.time()
        # Simple CPU test - matrix multiplication
        a = np.random.rand(1000, 1000)
        b = np.random.rand(1000, 1000)
        c = np.dot(a, b)
        cpu_time = time.time() - start_time
        
        results["cpu"] = {
            "cores": psutil.cpu_count(),
            "frequency": psutil.cpu_freq().current if psutil.cpu_freq() else "Unknown",
            "matrix_mult_time": cpu_time,
            "cpu_percent": psutil.cpu_percent(interval=1)
        }
        
        # Memory Benchmark
        memory = psutil.virtual_memory()
        results["memory"] = {
            "total_gb": memory.total / (1024**3),
            "available_gb": memory.available / (1024**3),
            "used_percent": memory.percent
        }
        
        # Disk Benchmark
        try:
            disk = psutil.disk_usage('/')
            results["disk"] = {
                "total_gb": disk.total / (1024**3),
                "free_gb": disk.free / (1024**3),
                "used_percent": (disk.used / disk.total) * 100
            }
        except:
            results["disk"] = {"error": "Cannot access disk info"}
        
        # Network Benchmark (simplified)
        results["network"] = {
            "status": "Local system - no network test needed"
        }
        
        self.local_benchmark = results
        return results
    
    def benchmark_remote_server(self, server_name: str, username: str, ip_address: str) -> Dict:
        """Benchmark a remote server."""
        st.info(f"🔄 Benchmarking {server_name}...")
        
        try:
            from quanttime.dashboard.server_task_manager import task_manager
            ssh = task_manager._get_ssh_connection(ip_address, username, timeout=10)
            
            results = {
                "device": server_name,
                "timestamp": datetime.now().isoformat(),
                "cpu": {},
                "memory": {},
                "disk": {},
                "network": {}
            }
            
            # CPU Benchmark
            cpu_script = '''
import time
import numpy as np
start_time = time.time()
a = np.random.rand(1000, 1000)
b = np.random.rand(1000, 1000)
c = np.dot(a, b)
print(f"CPU_TIME:{time.time() - start_time}")
print(f"CPU_CORES:{len(np.__config__.get_info('lapack_opt_info')['libraries'])}")
'''
            
            stdin, stdout, stderr = ssh.exec_command(f"python3 -c '{cpu_script}'")
            output = stdout.read().decode().strip()
            
            for line in output.split('\n'):
                if line.startswith('CPU_TIME:'):
                    cpu_time = float(line.split(':')[1])
                elif line.startswith('CPU_CORES:'):
                    cpu_cores = int(line.split(':')[1])
            
            # Get CPU info
            stdin, stdout, stderr = ssh.exec_command("nproc")
            cores = stdout.read().decode().strip()
            
            stdin, stdout, stderr = ssh.exec_command("lscpu | grep 'CPU MHz' | awk '{print $3}'")
            freq = stdout.read().decode().strip()
            
            results["cpu"] = {
                "cores": int(cores),
                "frequency": float(freq) if freq else "Unknown",
                "matrix_mult_time": cpu_time,
                "cpu_percent": "N/A"
            }
            
            # Memory Benchmark
            stdin, stdout, stderr = ssh.exec_command("free -g")
            memory_output = stdout.read().decode().strip()
            lines = memory_output.split('\n')
            if len(lines) > 1:
                mem_line = lines[1].split()
                results["memory"] = {
                    "total_gb": int(mem_line[1]),
                    "available_gb": int(mem_line[6]),
                    "used_percent": (int(mem_line[2]) / int(mem_line[1])) * 100
                }
            
            # Disk Benchmark
            stdin, stdout, stderr = ssh.exec_command("df -h /opt | tail -1")
            disk_output = stdout.read().decode().strip()
            if disk_output:
                disk_parts = disk_output.split()
                total_gb = float(disk_parts[1].replace('G', ''))
                used_gb = float(disk_parts[2].replace('G', ''))
                results["disk"] = {
                    "total_gb": total_gb,
                    "free_gb": total_gb - used_gb,
                    "used_percent": (used_gb / total_gb) * 100
                }
            
            # Network Benchmark (ping test)
            stdin, stdout, stderr = ssh.exec_command("ping -c 3 8.8.8.8 | tail -1")
            ping_output = stdout.read().decode().strip()
            if "avg" in ping_output:
                avg_ping = ping_output.split('/')[-3]
                results["network"] = {
                    "ping_ms": float(avg_ping),
                    "status": "Connected"
                }
            else:
                results["network"] = {
                    "ping_ms": "N/A",
                    "status": "No internet"
                }
            
            ssh.close()
            return results
            
        except Exception as e:
            st.error(f"❌ Failed to benchmark {server_name}: {e}")
            return {
                "device": server_name,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def compare_devices(self) -> Dict:
        """Compare performance across all devices."""
        if not self.local_benchmark:
            self.benchmark_local_system()
        
        comparison = {
            "devices": [self.local_benchmark],
            "summary": {}
        }
        
        # Add server benchmarks
        for server_name, result in self.benchmark_results.items():
            if "error" not in result:
                comparison["devices"].append(result)
        
        # Calculate performance scores
        for device in comparison["devices"]:
            if "error" in device:
                device["performance_score"] = 0
                continue
            
            # Simple performance scoring (lower is better for time-based metrics)
            cpu_score = 1.0 / (device["cpu"].get("matrix_mult_time", 1.0) + 0.1)
            memory_score = device["memory"].get("total_gb", 1) / 100  # Normalize to 100GB
            disk_score = device["disk"].get("total_gb", 1) / 1000  # Normalize to 1TB
            
            # Weighted score
            device["performance_score"] = (
                cpu_score * 0.4 +  # CPU is 40% of score
                memory_score * 0.4 +  # Memory is 40% of score
                disk_score * 0.2  # Disk is 20% of score
            )
        
        # Rank devices
        comparison["devices"].sort(key=lambda x: x.get("performance_score", 0), reverse=True)
        
        return comparison
    
    def run_full_benchmark(self, servers: Dict) -> Dict:
        """Run benchmarks on all devices."""
        st.info("🚀 Starting comprehensive performance benchmark...")
        
        # Benchmark local system
        self.benchmark_local_system()
        
        # Benchmark all servers
        for server_name, server_config in servers.items():
            username = server_config.get('username', 'quanttime')
            ip_address = server_config.get('tailscale_ip') or server_config.get('ip_address')
            
            result = self.benchmark_remote_server(server_name, username, ip_address)
            self.benchmark_results[server_name] = result
        
        # Compare all devices
        comparison = self.compare_devices()
        
        return comparison

# Global instance
benchmarker = ServerBenchmarker()
