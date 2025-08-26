import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from quanttime.adapter.subscriber import subscribe_ticks
from quanttime.data.io import save_ticks_parquet
from quanttime.utils.config import AppConfig, ensure_data_dirs


def main():
    parser = argparse.ArgumentParser(description="Collect ticks from ZeroMQ and write to Parquet")
    parser.add_argument("--rows", type=int, default=2000, help="Number of rows to collect before writing")
    args = parser.parse_args()

    cfg = AppConfig()
    ensure_data_dirs(cfg)
    rows = []
    for _, msg in subscribe_ticks(cfg.zmq_sub_endpoint):
        rows.append({
            "ts": float(msg["ts"]),
            "price": float(msg["price"]),
            "size": float(msg.get("size", 1.0)),
            "side": str(msg.get("side", "buy")),
        })
        if len(rows) >= args.rows:
            df = pd.DataFrame(rows)
            ts_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"ticks_{ts_str}.parquet"
            path = save_ticks_parquet(df, cfg, filename)
            print(f"Wrote {len(df)} rows to {path}")
            break


if __name__ == "__main__":
    main()


