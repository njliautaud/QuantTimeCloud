import json
import threading
import time
from collections import deque
from typing import Optional, Tuple, List, Dict

import pandas as pd
import zmq

from quanttime.utils.config import AppConfig
from quanttime.utils.logging import get_logger


class ChartStreamService:
    """High-speed ZeroMQ SUB receiver buffering recent ticks for chart overlays."""

    def __init__(self, cfg: AppConfig, maxlen: int = 200000):
        self.cfg = cfg
        self.logger = get_logger(self.__class__.__name__)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.SUB)
        self._buf: deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._direct_thread: Optional[threading.Thread] = None
        self._symbol: str = cfg.databento_symbol
        self._quote: Dict[str, float] = {"bid": 0.0, "ask": 0.0, "bid_size": 0.0, "ask_size": 0.0}
        self._depth_bids: Dict[float, float] = {}
        self._depth_asks: Dict[float, float] = {}

    def start(self, symbol: Optional[str] = None) -> None:
        if self._thread and self._thread.is_alive():
            return
        if symbol:
            self._symbol = symbol
        try:
            self._sock.connect(f"tcp://localhost:{self.cfg.zmq_sub_port}")
            self._sock.setsockopt_string(zmq.SUBSCRIBE, "ticks")
        except Exception:
            self.logger.exception("Failed to connect SUB socket")
            # Fallback: if ZeroMQ not available, return
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.logger.info("Chart stream started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        try:
            self._sock.close(0)
        except Exception:
            pass
        self.logger.info("Chart stream stopped")

    def _loop(self) -> None:
        poller = zmq.Poller()
        poller.register(self._sock, zmq.POLLIN)
        while not self._stop.is_set():
            events = dict(poller.poll(timeout=100))
            if self._sock in events and events[self._sock] == zmq.POLLIN:
                try:
                    _topic, payload = self._sock.recv_multipart(flags=zmq.NOBLOCK)
                    msg = json.loads(payload.decode("utf-8"))
                    row = {
                        "ts": float(msg.get("ts", time.time())),
                        "price": float(msg.get("price", 0.0)),
                        "size": float(msg.get("size", 1.0)),
                        "side": str(msg.get("side", "buy")),
                        "bid": float(msg.get("bid", 0.0)),
                        "ask": float(msg.get("ask", 0.0)),
                        "bid_size": float(msg.get("bid_size", 0.0)),
                        "ask_size": float(msg.get("ask_size", 0.0)),
                    }
                    with self._lock:
                        self._buf.append(row)
                except Exception as e:
                    self.logger.exception("ZMQ stream decode failed: %s", e)
                    continue
            else:
                time.sleep(0.01)

    def get_dataframe(self, minutes: int = 60) -> pd.DataFrame:
        """Return a DataFrame of buffered ticks restricted to last N minutes."""
        with self._lock:
            if not self._buf:
                return pd.DataFrame(columns=["ts", "price", "size", "side"])
            df = pd.DataFrame(list(self._buf))
        # Convert ts to datetime and filter
        ts = pd.to_datetime(df["ts"], unit="s", errors="coerce") if pd.api.types.is_numeric_dtype(df["ts"]) else pd.to_datetime(df["ts"], errors="coerce")
        df = df.assign(ts=ts).dropna(subset=["ts"])  # type: ignore
        cutoff = df["ts"].max() - pd.Timedelta(minutes=int(minutes))
        return df[df["ts"] >= cutoff]

    def get_depth_snapshot(self, levels: int = 10) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        with self._lock:
            bids = sorted(self._depth_bids.items(), key=lambda x: x[0], reverse=True)[:levels]
            asks = sorted(self._depth_asks.items(), key=lambda x: x[0])[:levels]
        return bids, asks

    def get_quote(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._quote)


_chart_stream_singleton: Optional[ChartStreamService] = None


def get_chart_stream_service(cfg: AppConfig) -> ChartStreamService:
    global _chart_stream_singleton
    if _chart_stream_singleton is None:
        _chart_stream_singleton = ChartStreamService(cfg)
    return _chart_stream_singleton


