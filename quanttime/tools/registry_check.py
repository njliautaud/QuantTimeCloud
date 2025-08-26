import sys
from pathlib import Path
from quanttime.registry.service import init_registry, list_runs
from quanttime.utils.config import AppConfig


def run(limit: int = 5) -> CheckResult:
    try:
        cfg = AppConfig()
        init_registry(cfg)
        rows = list_runs(cfg, limit=limit)
        details = {"count": len(rows), "ids": [r.id for r in rows], "names": [r.name for r in rows]}
        return CheckResult(name="registry", ok=True, details=details)
    except Exception as e:
        return CheckResult(name="registry", ok=False, details={}, error=str(e))


