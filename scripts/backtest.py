import argparse
import json
import os

import numpy as np
import pandas as pd

from sierraflow.backtest.engine import BacktestConfig, backtest_with_trades
from sierraflow.features.engineer import compute_basic_features
from sierraflow.utils.config import AppConfig


def main():
    parser = argparse.ArgumentParser(description="Run a simple backtest on ticks.parquet given binary predictions")
    parser.add_argument("--pred-prob", type=float, default=0.5, help="Probability of predicting long vs short (toy)")
    args = parser.parse_args()

    cfg = AppConfig()
    df = pd.read_parquet(f"{cfg.data_dir}/ticks.parquet")
    df = compute_basic_features(df)
    rng = np.random.default_rng(42)
    preds = (rng.random(len(df)) < args.pred_prob).astype(int)

    bt_cfg = BacktestConfig(
        commission_per_contract=cfg.commission_per_contract,
        slippage_ticks=cfg.slippage_ticks,
        tick_size=cfg.tick_size,
    )
    metrics, trades = backtest_with_trades(df, preds, bt_cfg)
    print(json.dumps(metrics, indent=2))
    out_dir = cfg.data_dir
    trades_path = os.path.join(out_dir, "trades.csv")
    trades.to_csv(trades_path, index=False)
    print(f"Wrote trades to {trades_path}")


if __name__ == "__main__":
    main()


