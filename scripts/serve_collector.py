import argparse
import sys
import time
import threading
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from quanttime.adapter.subscriber import subscribe_ticks
from quanttime.utils.config import AppConfig, ensure_data_dirs


_running = True


def _handle_sig(signum, frame):  # noqa: ARG001
    global _running
    _running = False


def main():
    parser = argparse.ArgumentParser(description="Persistent ZeroMQ collector with rotation")
    parser.add_argument("--max-rows", type=int, default=20000, help="Rotate file after this many rows")
    args = parser.parse_args()

    cfg = AppConfig()
    ensure_data_dirs(cfg)
    # signal.signal(signal.SIGINT, _handle_sig) # Removed as per new_code
    # signal.signal(signal.SIGTERM, _handle_sig) # Removed as per new_code

    rows = []
    ts_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(cfg.data_dir, f"ticks_{ts_str}.parquet")
    for _, msg in subscribe_ticks(f"tcp://localhost:{cfg.zmq_sub_port}"):
        if not _running:
            break
        rows.append({
            "ts": float(msg["ts"]),
            "price": float(msg["price"]),
            "size": float(msg.get("size", 1.0)),
            "side": str(msg.get("side", "buy")),
        })
        if len(rows) >= args.max_rows:
            df = pd.DataFrame(rows)
            df.to_parquet(out_path, index=False)
            print(f"Rotated file: {out_path} rows={len(df)}")
            rows.clear()
            ts_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(cfg.data_dir, f"ticks_{ts_str}.parquet")

    if rows:
        df = pd.DataFrame(rows)
        df.to_parquet(out_path, index=False)
        print(f"Flushed file: {out_path} rows={len(df)}")


if __name__ == "__main__":
    main()


