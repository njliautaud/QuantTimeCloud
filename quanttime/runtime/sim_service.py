import time
import threading
from typing import Optional

from quanttime.adapter.simulator import run_tick_simulator
from quanttime.utils.config import AppConfig
from quanttime.utils.logging import get_logger


class SimulatorService:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.logger = get_logger(self.__class__.__name__)
        self._endpoint_used: Optional[str] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        def _run():
            try:
                # Try bind; if address in use, try a small range of ports
                base = self.cfg.zmq_pub_endpoint
                host = "tcp://127.0.0.1:"
                candidates = []
                if base.startswith(host):
                    try:
                        port0 = int(base.split(":")[-1])
                        candidates = [f"{host}{p}" for p in range(port0, port0 + 8)]
                    except Exception:
                        candidates = [base]
                else:
                    candidates = [base]
                last_err: Optional[Exception] = None
                for ep in candidates:
                    try:
                        self._endpoint_used = ep
                        run_tick_simulator(ep)
                        return
                    except Exception as e:  # bind failure or other
                        last_err = e
                        self.logger.exception("Simulator failed on endpoint %s", ep)
                        continue
                if last_err:
                    raise last_err
            except Exception:
                self.logger.exception("Simulator crashed")

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        self.logger.info("Simulator started")

    def stop(self) -> None:
        # Simulator loop listens for KeyboardInterrupt; thread will end on process exit.
        # We don't have a direct stop; inform via log.
        self.logger.info("Stop simulator not supported in-thread; restart app to stop.")

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def endpoint(self) -> Optional[str]:
        return self._endpoint_used or self.cfg.zmq_pub_endpoint


_sim_singleton: Optional[SimulatorService] = None


def get_simulator_service(cfg: AppConfig) -> SimulatorService:
    global _sim_singleton
    if _sim_singleton is None:
        _sim_singleton = SimulatorService(cfg)
    return _sim_singleton


