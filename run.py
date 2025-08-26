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


def run_up(rows: int = 5000, port: int = 8501) -> None:
    py = venv_python()
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
        print("=" * 68)
        print(" QuantTime ML Trading Suite")
        print("=" * 68)
        print(f" Dashboard: http://localhost:{port}")
        print(f"            http://{host_ip}:{port}")
        print(f" Database:  {db_status}")
        print(f" ZeroMQ:    {zmq_status}")
        print(f" Databento MBO: {databento_status}")
        print("=" * 68)
        print(" Press Ctrl+C to stop.\n")

        run_streamlit(port=port)
    except KeyboardInterrupt:
        pass
    finally:
        print("[run.py] Shutting down services...")
        collector.terminate()
        sim.terminate()


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
        run_streamlit(port=getattr(args, "port", 8501))
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


