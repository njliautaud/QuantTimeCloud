import os
import sys
import time
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
import json
import signal

import zmq

from quanttime.utils.config import AppConfig
from quanttime.utils.logging import get_logger


@dataclass
class CollectorStatus:
    running: bool
    rows: int
    file_path: Optional[str]
    started_at: float
    last_price: Optional[float]


class CollectorService:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.logger = get_logger(self.__class__.__name__)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._rows = 0
        self._file_path: Optional[Path] = None
        self._started_at: float = 0.0
        self._last_price: Optional[float] = None
        self._ctx = zmq.Context.instance()
        self._sock: Optional[zmq.Socket] = None
        self._log: deque[str] = deque(maxlen=200)

    def start(self, symbol: str, target_days: int) -> None:
        if self._thread and self._thread.is_alive():
            return
        data_dir = Path(self.cfg.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        # CSV for easy preview in UI. Parquet can be added later in a batch job.
        self._file_path = data_dir / f"ticks_{symbol.upper()}_{ts}.csv"
        # Initialize file with header
        with self._file_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["ts", "price", "size", "side"])
            writer.writeheader()

        self._rows = 0
        self._started_at = time.time()
        self._stop.clear()
        # (Re)create SUB socket for a fresh start
        try:
            if self._sock is not None:
                try:
                    self._sock.close(0)
                except Exception:
                    pass
            self._sock = self._ctx.socket(zmq.SUB)
            # Auto-fallback ports if base port is busy or no data
            base = self.cfg.zmq_sub_endpoint
            host = "tcp://127.0.0.1:"
            candidates = [base]
            if base.startswith(host):
                try:
                    p0 = int(base.split(":")[-1])
                    candidates = [f"{host}{p}" for p in range(p0, p0 + 8)]
                except Exception:
                    candidates = [base]
            connected = False
            last_err = None
            for ep in candidates:
                try:
                    self._sock.connect(ep)
                    connected = True
                    break
                except Exception as e:
                    last_err = e
                    continue
            if not connected:
                raise RuntimeError(f"Failed to connect any SUB endpoint; last error: {last_err}")
            self._sock.setsockopt_string(zmq.SUBSCRIBE, "ticks")
        except Exception:
            self._sock = None
            raise
        self._log.append(f"[{ts}] Collector started at {self.cfg.zmq_sub_endpoint} for {symbol.upper()}")
        self._log.append("Waiting for tick messages... (ensure simulator or DTC publisher is running)")
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.logger.info(f"Collector started -> {self._file_path}")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        try:
            if self._sock is not None:
                self._sock.close(0)
                self._sock = None
        except Exception:
            pass
        self.logger.info("Collector stopped")
        self._log.append("Collector stopped")

    def _loop(self):
        buffer = []
        poller = zmq.Poller()
        if self._sock is not None:
            poller.register(self._sock, zmq.POLLIN)
        while not self._stop.is_set():
            events = dict(poller.poll(timeout=500))
            if self._sock is not None and self._sock in events and events[self._sock] == zmq.POLLIN:
                topic, payload = self._sock.recv_multipart()
                msg = json.loads(payload.decode("utf-8"))
                row = {
                    "ts": float(msg.get("ts", time.time())),
                    "price": float(msg.get("price", 0.0)),
                    "size": float(msg.get("size", 1.0)),
                    "side": str(msg.get("side", "buy")),
                }
                buffer.append(row)
                self._last_price = row["price"]
                if len(buffer) >= 1000:
                    self._flush(buffer)
            else:
                time.sleep(0.05)
                # periodically emit heartbeat in log
                if int(time.time()) % 5 == 0:
                    self._log.append("waiting for data...")
        if buffer:
            self._flush(buffer)

    def _flush(self, buffer):
        if not self._file_path:
            return
        with self._file_path.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["ts", "price", "size", "side"])
            writer.writerows(buffer)
        self._rows += len(buffer)
        buffer.clear()
        self._log.append(f"Flushed {self._rows} rows -> {self._file_path.name}")

    def status(self) -> CollectorStatus:
        return CollectorStatus(
            running=bool(self._thread and self._thread.is_alive()),
            rows=self._rows,
            file_path=str(self._file_path) if self._file_path else None,
            started_at=self._started_at,
            last_price=self._last_price,
        )

    def log_tail(self) -> str:
        return "\n".join(self._log)


_collector_singleton: Optional[CollectorService] = None


def get_collector_service(cfg: AppConfig) -> CollectorService:
    global _collector_singleton
    if _collector_singleton is None:
        _collector_singleton = CollectorService(cfg)
    return _collector_singleton


