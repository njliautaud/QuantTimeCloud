import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from sierraflow.runtime.acsil_orchestrator import ACSILOrchestrator, BacktestRequest
from sierraflow.utils.config import AppConfig
from sierraflow.utils.logging import get_logger
from sierraflow.registry.service import (
    enqueue_backtest_job,
    claim_next_backtest_job,
    set_backtest_job_result,
    append_backtest_job_event,
)


@dataclass
class QueueItem:
    run_id: int
    symbol: str
    start_iso: str
    end_iso: str
    study_params: Dict[str, float]
    replay_speed: int
    accurate: bool
    all_charts: bool


class BacktestQueue:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._queue: List[QueueItem] = []
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.logger = get_logger(self.__class__.__name__)

    def add(self, item: QueueItem) -> None:
        # Persist to DB immediately for crash-safe queueing
        from datetime import datetime
        job_id = enqueue_backtest_job(
            self.cfg,
            run_id=item.run_id,
            symbol=item.symbol,
            start_iso=item.start_iso,
            end_iso=item.end_iso,
            study_params=item.study_params,
            replay_speed=item.replay_speed,
            accurate=item.accurate,
            all_charts=item.all_charts,
        )
        self.logger.info("Enqueued job id=%s", job_id)

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def _run():
            while not self._stop.is_set():
                # Claim next job from DB, not memory
                job = claim_next_backtest_job(self.cfg)
                if job is None:
                    time.sleep(0.3)
                    continue
                try:
                    orch = ACSILOrchestrator(self.cfg)
                    orch.connect()
                    req = BacktestRequest(
                        run_id=job.run_id,
                        symbol=job.symbol,
                        start=_parse_iso(job.start_iso),
                        end=_parse_iso(job.end_iso),
                        study_params=job.study_params,
                        replay_speed=job.replay_speed,
                        accurate_mode=job.accurate,
                        all_charts=job.all_charts,
                    )
                    res = orch.run_backtest(req, job_id=job.id)
                    # Append event snapshot for audit
                    append_backtest_job_event(self.cfg, job.id, {"type": "COMPLETED", "job_id": job.id})
                    # Save results path if known
                    set_backtest_job_result(
                        self.cfg,
                        job.id,
                        status="succeeded",
                        metrics=res.get("metrics", {}),
                        result_path=str(res.get("result_path", "")),
                        error=str(res.get("error", "")),
                    )
                    orch.close()
                except Exception:
                    self.logger.exception("Backtest job failed: %s", job.id)
                    set_backtest_job_result(self.cfg, job.id, status="failed", error="exception")

        self._stop.clear()
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)


def _parse_iso(s: str):
    import datetime as dt
    return dt.datetime.fromisoformat(s)


