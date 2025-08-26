import os
from pathlib import Path
from typing import Optional

from quanttime.utils.config import AppConfig


def ensure_model_dir(cfg: AppConfig) -> Path:
    path = Path(cfg.model_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def model_artifact_path(cfg: AppConfig, run_id: int, name: str, ext: str = "joblib") -> Path:
    root = ensure_model_dir(cfg)
    safe_name = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_"))
    return root / f"run_{run_id}_{safe_name}.{ext}"


def find_artifact(cfg: AppConfig, run_id: int) -> Optional[Path]:
    root = ensure_model_dir(cfg)
    for p in root.glob(f"run_{run_id}_*.*"):
        return p
    return None


