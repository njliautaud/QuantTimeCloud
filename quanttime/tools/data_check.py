import os
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .types import CheckResult
from quanttime.utils.config import AppConfig


def run(latest_only: bool = True) -> CheckResult:
    try:
        cfg = AppConfig()
        data_dir = Path(cfg.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        files = [p for p in data_dir.iterdir() if p.suffix.lower() in {".csv", ".parquet"}]
        files.sort()
        result = {"data_dir": str(data_dir), "files": [p.name for p in files][-5:]}
        sample: Optional[pd.DataFrame] = None
        if files:
            p = files[-1] if latest_only else files[0]
            sample = pd.read_csv(p) if p.suffix.lower() == ".csv" else pd.read_parquet(p)
            result["sample_rows"] = int(min(len(sample), 5))
            result["sample_columns"] = list(sample.columns)[:10]
        return CheckResult(name="data", ok=True, details=result)
    except Exception as e:
        return CheckResult(name="data", ok=False, details={}, error=str(e))


