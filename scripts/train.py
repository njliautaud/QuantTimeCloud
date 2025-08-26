import argparse
import sys
from pathlib import Path

import pandas as pd

from quanttime.jobs.runner import run_training_job
from quanttime.utils.config import AppConfig, ensure_data_dirs


def main():
    parser = argparse.ArgumentParser(description="Train a model on ticks.parquet or synthetic data")
    parser.add_argument("--name", type=str, default="exp-cli", help="Model run name")
    parser.add_argument("--arch", type=str, default="LGBM", help="Model architecture: LGBM|LSTM|TRANSFORMER|TCN")
    args = parser.parse_args()

    cfg = AppConfig()
    ensure_data_dirs(cfg)
    ticks_path = Path(cfg.data_dir) / "ticks.parquet"
    if ticks_path.exists():
        df = pd.read_parquet(ticks_path)
    else:
        n = 200
        ts = pd.Series(pd.RangeIndex(n)).astype(float)
        price = 5000 + (ts - ts.mean()) * 0.1
        side = ["buy" if (i % 2 == 0) else "sell" for i in range(n)]
        size = 1
        df = pd.DataFrame({"ts": ts, "price": price, "side": side, "size": size})

    res = run_training_job(cfg, args.name, df, model_type=args.arch)
    print(f"Trained run id={res['id']} metrics={res['metrics']}")


if __name__ == "__main__":
    main()


