import sys
from pathlib import Path
from quanttime.runtime.live_service import get_live_service
from quanttime.utils.config import AppConfig
from quanttime.utils.logging import get_logger


def run() -> CheckResult:
    try:
        cfg = AppConfig()
        svc = get_live_service(cfg)
        snap = svc.snapshot()
        details = {
            "running": snap.is_running,
            "position": snap.position,
            "last_price": snap.last_price,
            "last_prediction": snap.last_prediction,
            "zmq_pub": cfg.zmq_pub_endpoint,
            "zmq_sub": cfg.zmq_sub_endpoint,
            "hist_port": cfg.sierra_hist_port,
            "dtc_host": cfg.sierra_host,
        }
        return CheckResult(name="runtime", ok=True, details=details)
    except Exception as e:
        return CheckResult(name="runtime", ok=False, details={}, error=str(e))


