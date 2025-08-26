import threading
import time
from typing import Callable, Optional

from sierraflow.adapter.acsil_client import ACSILClient
from sierraflow.utils.config import AppConfig
from sierraflow.utils.logging import get_logger


class ACSILEventsService:
    """Background listener that yields ACSIL events to a callback for UI updates."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.logger = get_logger(self.__class__.__name__)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._client: Optional[ACSILClient] = None
        self._callback: Optional[Callable[[dict], None]] = None

    def start(self, callback: Callable[[dict], None]) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._callback = callback

        def _run():
            try:
                self._client = ACSILClient(self.cfg.acsil_host, self.cfg.acsil_port, timeout=2.0)
                self._client.connect()
                for evt in self._client.events():
                    if self._stop.is_set():
                        break
                    try:
                        if self._callback:
                            self._callback(evt)
                    except Exception:
                        self.logger.exception("Callback error")
            except Exception:
                self.logger.exception("Events service error")
            finally:
                try:
                    if self._client:
                        self._client.close()
                except Exception:
                    pass

        self._stop.clear()
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)


