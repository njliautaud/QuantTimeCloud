import sys
from pathlib import Path
import pandas as pd

from .types import CheckResult
from quanttime.features.engineer import compute_basic_features
from quanttime.utils.config import AppConfig
from quanttime.data.io import load_ticks_parquet


def run() -> CheckResult:
    try:
        cfg = AppConfig()
        df = load_ticks_parquet(cfg)
        if df is None or df.empty:
            # Create a tiny synthetic sample
            df = pd.DataFrame({
                "ts": pd.RangeIndex(200).astype(float),
                "price": 5000 + pd.RangeIndex(200) * 0.1,
                "size": 1.0,
                "side": ["buy" if i % 2 == 0 else "sell" for i in range(200)],
            })
        feats = compute_basic_features(df)
        cols = [c for c in feats.columns if c not in ("ts", "price", "side")]
        details = {"num_features": len(cols), "head_columns": cols[:10], "rows": len(feats)}
        return CheckResult(name="features", ok=bool(cols), details=details)
    except Exception as e:
        return CheckResult(name="features", ok=False, details={}, error=str(e))


