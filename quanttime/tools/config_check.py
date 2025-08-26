import sys
from quanttime.utils.config import AppConfig


def run() -> CheckResult:
    try:
        cfg = AppConfig()
        details = {
            "database_url": cfg.database_url,
            "zmq_pub_endpoint": cfg.zmq_pub_endpoint,
            "zmq_sub_endpoint": cfg.zmq_sub_endpoint,
            "data_dir": cfg.data_dir,
            "model_dir": cfg.model_dir,
            "sc_backtest_dir": cfg.sc_backtest_dir,
            "sierra": {
                "host": cfg.sierra_host,
                "port": cfg.sierra_port,
                "hist_port": cfg.sierra_hist_port,
                "symbol": cfg.sierra_symbol,
                "exchange": cfg.sierra_exchange,
            },
        }
        if os.getenv("DTC_USERNAME"):
            details["dtc_username_set"] = True
        if os.getenv("DTC_PASSWORD"):
            details["dtc_password_set"] = True
        return CheckResult(name="config", ok=True, details=details)
    except Exception as e:
        return CheckResult(name="config", ok=False, details={}, error=str(e))


