import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from quanttime.backtest.metrics import max_drawdown, sharpe_ratio, sortino_ratio


@dataclass
class BacktestConfig:
    commission_per_contract: float
    slippage_ticks: int
    tick_size: float


def simple_backtest(
    df: pd.DataFrame, predictions: np.ndarray, cfg: BacktestConfig
) -> Dict[str, float]:
    px = df["price"].values.astype(float)
    direction = (predictions * 2 - 1).astype(float)  # 1 -> long, 0 -> short as -1
    # PnL: direction times price change minus costs
    price_change = np.diff(px, prepend=px[0])
    gross = direction * price_change
    slip_cost = np.abs(np.diff(direction, prepend=0)) * cfg.slippage_ticks * cfg.tick_size
    commission = np.abs(np.diff(direction, prepend=0)) * cfg.commission_per_contract
    pnl = gross - slip_cost - commission
    equity = pnl.cumsum()
    metrics = {
        "pnl": float(pnl.sum()),
        "sharpe": sharpe_ratio(pnl),
        "sortino": sortino_ratio(pnl),
        "max_drawdown": max_drawdown(equity),
        "win_rate": float((pnl > 0).mean()) if pnl.size else 0.0,
    }
    return metrics


def backtest_with_trades(
    df: pd.DataFrame, predictions: np.ndarray, cfg: BacktestConfig
) -> Tuple[Dict[str, float], pd.DataFrame]:
    px = df["price"].values.astype(float)
    direction = (predictions * 2 - 1).astype(float)
    price_change = np.diff(px, prepend=px[0])
    gross = direction * price_change
    slip_cost = np.abs(np.diff(direction, prepend=0)) * cfg.slippage_ticks * cfg.tick_size
    commission = np.abs(np.diff(direction, prepend=0)) * cfg.commission_per_contract
    pnl = gross - slip_cost - commission
    equity = pnl.cumsum()
    metrics = {
        "pnl": float(pnl.sum()),
        "sharpe": sharpe_ratio(pnl),
        "sortino": sortino_ratio(pnl),
        "max_drawdown": max_drawdown(equity),
        "win_rate": float((pnl > 0).mean()) if pnl.size else 0.0,
    }
    trades = pd.DataFrame({
        "ts": df["ts"].values,
        "price": px,
        "prediction": predictions,
        "direction": direction,
        "pnl": pnl,
        "equity": equity,
    })
    return metrics, trades


def walk_forward_slices(n_rows: int, train_frac: float = 0.6, val_frac: float = 0.2, min_rows: int = 100) -> List[Tuple[int, int, int, int]]:
    """Return list of (tr_start, tr_end, val_start, val_end) indices for walk-forward.

    The test slice is implied as the remainder; outer caller can compute metrics on it.
    """
    if n_rows < min_rows:
        return [(0, int(n_rows * train_frac), int(n_rows * train_frac), int(n_rows * (train_frac + val_frac)))]
    step = max(min_rows, int(n_rows * 0.1))
    slices: List[Tuple[int, int, int, int]] = []
    start = 0
    while True:
        tr_end = start + int(n_rows * train_frac)
        val_end = tr_end + int(n_rows * val_frac)
        if val_end >= n_rows:
            break
        slices.append((start, tr_end, tr_end, val_end))
        start += step
        if start + int(n_rows * (train_frac + val_frac)) >= n_rows:
            break
    if not slices:
        slices.append((0, int(n_rows * train_frac), int(n_rows * train_frac), int(n_rows * (train_frac + val_frac))))
    return slices


def monte_carlo_bootstrap(pnl: np.ndarray, iterations: int = 1000) -> Dict[str, float]:
    """Bootstrap PnL sequence to estimate Sharpe confidence interval."""
    if pnl.size == 0:
        return {"sharpe_p50": 0.0, "sharpe_p05": 0.0, "sharpe_p95": 0.0}
    rng = np.random.default_rng(42)
    sharpes = []
    for _ in range(iterations):
        sample = rng.choice(pnl, size=pnl.size, replace=True)
        sharpes.append(sharpe_ratio(sample))
    arr = np.array(sharpes)
    return {
        "sharpe_p50": float(np.percentile(arr, 50)),
        "sharpe_p05": float(np.percentile(arr, 5)),
        "sharpe_p95": float(np.percentile(arr, 95)),
    }


