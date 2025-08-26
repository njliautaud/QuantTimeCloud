import pandas as pd
from pathlib import Path
from typing import Optional
import logging
from quanttime.utils.config import AppConfig


def save_ticks_parquet(df: pd.DataFrame, cfg: AppConfig, filename: str = "ticks.parquet") -> Path:
    data_dir = Path(cfg.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / filename
    df.to_parquet(path, index=False)
    return path


def load_ticks_parquet(cfg: AppConfig, filename: str = "ticks.parquet") -> Optional[pd.DataFrame]:
    path = Path(cfg.data_dir) / filename
    if not path.exists():
        return None
    return pd.read_parquet(path)


