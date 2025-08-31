import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
import socket


ROOT = Path(__file__).parent.resolve()
VENV_DIR = ROOT / ".venv"


def venv_python() -> str:
    if platform.system().lower().startswith("win"):
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "bin" / "python")


def ensure_venv() -> None:
    if not VENV_DIR.exists():
        print("[run.py] Creating virtual environment .venv...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)


def pip_install() -> None:
    py = venv_python()
    print("[run.py] Upgrading pip...")
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    req = ROOT / "requirements.txt"
    if req.exists():
        print("[run.py] Installing requirements.txt...")
        subprocess.run([py, "-m", "pip", "install", "-q", "-r", str(req)], check=True)
    print("[run.py] Installing project (editable)...")
    subprocess.run([py, "-m", "pip", "install", "-q", "-e", str(ROOT)], check=True)


def clear_console() -> None:
    if platform.system().lower().startswith("win"):
        os.system("cls")
    else:
        os.system("clear") 


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def check_db_status() -> str:
    try:
        from quanttime.utils.config import AppConfig
        from quanttime.registry.db import get_engine
        from sqlalchemy import text

        cfg = AppConfig()
        engine = get_engine(cfg)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "connected"
    except Exception as e:
        return f"error: {str(e)[:80]}"


def check_databento_status() -> str:
    """Check Databento MBO data availability."""
    try:
        from quanttime.adapter.databento_mbo import DatabentoMBOReader
        from quanttime.utils.config import AppConfig
        from pathlib import Path
        
        cfg = AppConfig()
        data_dir = Path(cfg.data_dir)
        
        if not data_dir.exists():
            return f"data directory not found: {data_dir}"
        
        reader = DatabentoMBOReader(str(data_dir))
        dates = reader.get_available_dates()
        
        if dates:
            return f"available ({len(dates)} dates)"
        else:
            return "no data files found"
            
    except Exception as e:
        return f"error: {str(e)[:80]}"


def check_zmq_status(poll_ms: int = 800) -> str:
    try:
        import zmq
        from quanttime.utils.config import AppConfig

        cfg = AppConfig()
        ctx = zmq.Context.instance()
        sock = ctx.socket(zmq.SUB)
        sock.connect(f"tcp://localhost:{cfg.zmq_sub_port}")
        sock.setsockopt_string(zmq.SUBSCRIBE, "ticks")
        poller = zmq.Poller()
        poller.register(sock, zmq.POLLIN)
        events = dict(poller.poll(timeout=poll_ms))
        sock.close(0)
        if events.get(sock) == zmq.POLLIN:
            return "receiving"
        return "no data (yet)"
    except Exception as e:
        return f"error: {e}"


def run_streamlit(port: int = 8501) -> int:
    py = venv_python()
    app_path = ROOT / "quanttime" / "dashboard" / "app.py"
    cmd = [
        py,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.address",
        "0.0.0.0",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env.setdefault("LOG_LEVEL", "INFO")
    return subprocess.call(cmd, env=env)

def run_dashboard_with_integration(port: int = 8501) -> None:
    """Start dashboard with Ray cluster and cross-platform Git monitoring"""
    print("[run.py] Starting QuantTime Dashboard with Ray+SSH integration...")
    
    # Start integrated services (Ray only)
    integrated_services = start_integrated_services()
    
    try:
        host_ip = get_local_ip()
        
        clear_console()
        print("=" * 80)
        print(" QuantTime ML Trading Suite - RAY+SSH INTEGRATED")
        print("=" * 80)
        print(f" 📊 Dashboard:      http://localhost:{port}")
        print(f"            http://{host_ip}:{port}")
        print(f" ⚡ Ray Dashboard:  http://localhost:8265")
        print("=" * 80)
        print(" 🎯 Cross-platform services running!")
        print(" 📋 Available features:")
        print("    • Cross-platform deployments (Ray+SSH)")
        print("    • Distributed computing (Ray cluster)")
        print("    • AI-powered smart automation")
        print("    • Automated Git sync monitoring")
        print("    • SFTP large file synchronization")
        print("    • Zero-touch node deployment")
        print("    • Predictive health monitoring")
        print("    • Real-time trading dashboard")
        print("    • Windows + Linux node support")
        print("=" * 80)
        print(" Press Ctrl+C to stop.\n")

        run_streamlit(port=port)
    except KeyboardInterrupt:
        pass
    finally:
        print("[run.py] Shutting down integrated services...")
        
        # Stop integrated services
        for service_name, process in integrated_services:
            try:
                print(f"[run.py] Stopping {service_name}...")
                process.terminate()
            except:
                pass
        
        # Stop Smart Automation
        try:
            print("[run.py] Stopping Smart Automation...")
            from quanttime.core.smart_automation_manager import get_smart_automation_manager
            smart_automation = get_smart_automation_manager()
            smart_automation.stop_smart_automation()
        except Exception as e:
            print(f"[run.py] ⚠️ Smart automation shutdown issue: {e}")
        
        # Stop Git monitoring and SSH connections
        try:
            print("[run.py] Stopping Git monitoring...")
            from quanttime.core.cross_platform_git_watcher import get_git_watcher
            git_watcher = get_git_watcher()
            git_watcher.stop_monitoring()
            git_watcher.cleanup_connections()
        except Exception as e:
            print(f"[run.py] ⚠️ Git watcher shutdown issue: {e}")
        
        # Stop Ray
        try:
            print("[run.py] Stopping Ray cluster...")
            subprocess.run(['ray', 'stop'], capture_output=True, timeout=15)
        except Exception as e:
            print(f"[run.py] ⚠️ Ray shutdown issue: {e}")
        
        print("[run.py] All services stopped.")


def start_integrated_services():
    """Start dynamic cluster, cross-platform Git monitoring, and smart automation"""
    print("[run.py] Starting dynamic cluster, Git monitoring, and smart automation...")
    
    services = []
    
    # Start Peer Sync Manager (no head nodes, all nodes equal)
    try:
        print("[run.py] Starting Peer Sync Manager...")
        from quanttime.core.peer_sync_manager import PeerSyncManager
        
        # Initialize and start peer sync
        peer_sync = PeerSyncManager()
        peer_sync.start_peer_services()
        
        services.append(("Peer Sync", None))
        print("[run.py] ✅ Peer sync started - discovering other nodes")
        print("[run.py] 🔍 Broadcasting presence on network...")
        print("[run.py] 🔄 Git sync monitoring active...")
        
        # Give peer system time to initialize
        time.sleep(3)
        
        # Show peer status
        status = peer_sync.get_peer_status()
        local_node = status["local_node"]
        print(f"[run.py] 🖥️ Local node: {local_node['hostname']} ({local_node['platform']})")
        print(f"[run.py] 📊 Resources: {local_node['resources']['cpu_count']} CPU, {local_node['resources']['memory_gb']}GB RAM, {local_node['resources']['gpu_count']} GPU")
        print(f"[run.py] 🌐 Discovered {len(status['known_peers'])} peer nodes")
        print(f"[run.py] 🔗 Ray cluster: {'Active' if status['cluster_info']['ray_initialized'] else 'Initializing'}")
        
        # Store peer manager globally for shutdown
        globals()['_peer_sync'] = peer_sync
        
    except Exception as e:
        print(f"[run.py] ⚠️ Could not start dynamic cluster: {e}")
        # Fallback to static Ray
        try:
            print("[run.py] 🔄 Falling back to static Ray cluster...")
            ray_process = subprocess.Popen([
                'ray', 'start', '--head', '--port=10001', '--dashboard-port=8265', '--include-dashboard'
            ], cwd=str(ROOT))
            services.append(("Ray (Fallback)", ray_process))
            print("[run.py] ✅ Static Ray cluster started")
        except Exception as ray_e:
            print(f"[run.py] ❌ Ray fallback also failed: {ray_e}")
    
    # Start Smart Automation Manager
    try:
        print("[run.py] Starting Smart Automation Manager...")
        from quanttime.core.smart_automation_manager import get_smart_automation_manager
        smart_automation = get_smart_automation_manager()
        smart_automation.start_smart_automation()
        services.append(("Smart Automation", None))
        print("[run.py] ✅ Smart automation started (AI-powered node management)")
    except Exception as e:
        print(f"[run.py] ⚠️ Could not start smart automation: {e}")
    
    # Start Git monitoring and deployment system
    try:
        print("[run.py] Starting Git monitoring and deployment system...")
        from quanttime.core.cross_platform_git_watcher import get_git_watcher
        git_watcher = get_git_watcher()
        git_watcher.start_monitoring()
        services.append(("Git Watcher", None))  # No process object for this service
        print("[run.py] ✅ Git monitoring started (auto-deploy enabled)")
    except Exception as e:
        print(f"[run.py] ⚠️ Could not start Git monitoring: {e}")
    
    # Initialize SFTP manager
    try:
        print("[run.py] Initializing SFTP manager...")
        from quanttime.core.sftp_manager import get_sftp_manager
        sftp_manager = get_sftp_manager()
        services.append(("SFTP Manager", None))  # No process object for this service
        print("[run.py] ✅ SFTP manager initialized")
    except Exception as e:
        print(f"[run.py] ⚠️ Could not initialize SFTP manager: {e}")
    
    return services

def check_docker():
    """Check if Docker is available and running"""
    try:
        # Check if Docker command exists
        result = subprocess.run(['docker', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False
        
        # Check if Docker daemon is running
        result = subprocess.run(['docker', 'info'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False

def run_up(rows: int = 5000, port: int = 8501) -> None:
    py = venv_python()
    print("[run.py] Starting QuantTime ML Trading Suite with Ray+SSH integration...")
    
    # Start integrated services first
    integrated_services = start_integrated_services()
    
    # Start core services
    print("[run.py] Starting simulator and collector...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    sim = subprocess.Popen([py, str(ROOT / "scripts" / "ingest.py"), "--simulate", "--publish"], env=env, cwd=str(ROOT))  # noqa: S603
    time.sleep(0.5)
    collector = subprocess.Popen([py, str(ROOT / "scripts" / "serve_collector.py"), "--max-rows", str(rows)], env=env, cwd=str(ROOT))  # noqa: S603
    
    try:
        # Status checks
        db_status = check_db_status()
        zmq_status = check_zmq_status()
        databento_status = check_databento_status()
        host_ip = get_local_ip()

        clear_console()
        print("=" * 80)
        print(" QuantTime ML Trading Suite - RAY+SSH INTEGRATED")
        print("=" * 80)
        print(f" 📊 Main Dashboard: http://localhost:{port}")
        print(f"            http://{host_ip}:{port}")
        print(f" ⚡ Ray Dashboard:  http://localhost:8265")
        print("=" * 80)
        print(f" Database:  {db_status}")
        print(f" ZeroMQ:    {zmq_status}")
        print(f" Databento MBO: {databento_status}")
        print("=" * 80)
        print(" 🎯 Cross-platform services integrated and running!")
        print(" 📋 Features available:")
        print("    • Cross-platform deployments (Ray+SSH)")
        print("    • Distributed computing (Ray cluster)")
        print("    • Automated Git sync monitoring")
        print("    • SFTP large file synchronization")
        print("    • Real-time trading dashboard")
        print("    • Windows + Linux node support")
        print("=" * 80)
        print(" Press Ctrl+C to stop.\n")

        run_streamlit(port=port)
    except KeyboardInterrupt:
        pass
    finally:
        print("[run.py] Shutting down all services...")
        
        # Stop core services
        collector.terminate()
        sim.terminate()
        
        # Stop integrated services
        for service_name, process in integrated_services:
            try:
                if process:  # Only terminate if there's a process object
                    print(f"[run.py] Stopping {service_name}...")
                    process.terminate()
            except:
                pass
        
        # Stop Smart Automation
        try:
            print("[run.py] Stopping Smart Automation...")
            from quanttime.core.smart_automation_manager import get_smart_automation_manager
            smart_automation = get_smart_automation_manager()
            smart_automation.stop_smart_automation()
        except Exception as e:
            print(f"[run.py] ⚠️ Smart automation shutdown issue: {e}")
        
        # Stop Git monitoring and SSH connections
        try:
            print("[run.py] Stopping Git monitoring...")
            from quanttime.core.cross_platform_git_watcher import get_git_watcher
            git_watcher = get_git_watcher()
            git_watcher.stop_monitoring()
            git_watcher.cleanup_connections()
        except Exception as e:
            print(f"[run.py] ⚠️ Git watcher shutdown issue: {e}")
        
        # Stop Ray
        try:
            print("[run.py] Stopping Ray cluster...")
            subprocess.run(['ray', 'stop'], capture_output=True, timeout=15)
        except Exception as e:
            print(f"[run.py] ⚠️ Ray shutdown issue: {e}")
        
        print("[run.py] All services stopped.")


def run_train(name: str) -> None:
    py = venv_python()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run([py, str(ROOT / "scripts" / "train.py"), "--name", name], check=True, cwd=str(ROOT), env=env)


def run_backtest(pred_prob: float) -> None:
    py = venv_python()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run([py, str(ROOT / "scripts" / "backtest.py"), "--pred-prob", str(pred_prob)], check=True, cwd=str(ROOT), env=env)


def run_live(run_id: int, threshold: float) -> None:
    py = venv_python()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run([py, "-m", "quanttime", "live", "--run-id", str(run_id), "--threshold", str(threshold)], check=True, cwd=str(ROOT), env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QuantTime with automatic venv and install")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("install", help="Create venv and install dependencies")

    p_up = sub.add_parser("up", help="Start simulator, collector and dashboard")
    p_up.add_argument("--rows", type=int, default=5000)
    p_up.add_argument("--port", type=int, default=8501)

    p_dash = sub.add_parser("dashboard", help="Start the Streamlit dashboard")
    p_dash.add_argument("--port", type=int, default=8501)

    p_tr = sub.add_parser("train", help="Train a model")
    p_tr.add_argument("--name", type=str, default="exp-cli")

    p_bt = sub.add_parser("backtest", help="Run a toy backtest")
    p_bt.add_argument("--pred-prob", type=float, default=0.55)

    p_lv = sub.add_parser("live", help="Run live inference and execution")
    p_lv.add_argument("--run-id", type=int, required=True)
    p_lv.add_argument("--threshold", type=float, default=0.1)

    args = parser.parse_args()

    # Default to 'up' if no subcommand
    cmd = args.cmd or "up"

    # Only install if this is the 'install' command or if venv doesn't exist
    if cmd == "install" or not VENV_DIR.exists():
        ensure_venv()
        pip_install()
        if cmd == "install":
            print("[run.py] Installation completed.")
            return
    else:
        print("[run.py] Using existing environment.")

    if cmd == "up":
        run_up(rows=getattr(args, "rows", 5000), port=getattr(args, "port", 8501))
        return
    if cmd == "dashboard":
        run_dashboard_with_integration(port=getattr(args, "port", 8501))
        return
    if cmd == "train":
        run_train(name=getattr(args, "name", "exp-cli"))
        return
    if cmd == "backtest":
        run_backtest(pred_prob=getattr(args, "pred_prob", 0.55))
        return
    if cmd == "live":
        run_live(run_id=getattr(args, "run_id"), threshold=getattr(args, "threshold", 0.1))
        return


if __name__ == "__main__":
    main()


