from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from quanttime.registry.db import Base, get_engine, get_session_factory
from quanttime.registry.models import ModelRun, BacktestJob, BacktestJobEvent
from quanttime.utils.config import AppConfig


def init_registry(cfg: AppConfig) -> None:
    engine = get_engine(cfg)
    Base.metadata.create_all(engine)


def list_runs(cfg: AppConfig, limit: int = 100) -> List[ModelRun]:
    Session = get_session_factory(cfg)
    with Session() as s:
        return s.execute(
            select(ModelRun).order_by(ModelRun.created_at.desc()).limit(limit)
        ).scalars().all()


def get_run(cfg: AppConfig, run_id: int) -> Optional[ModelRun]:
    Session = get_session_factory(cfg)
    with Session() as s:
        return s.get(ModelRun, run_id)


def set_live_ready(cfg: AppConfig, run_id: int, live_ready: bool) -> None:
    Session = get_session_factory(cfg)
    with Session() as s:
        s.execute(update(ModelRun).where(ModelRun.id == run_id).values(live_ready=live_ready))
        s.commit()


def set_status(cfg: AppConfig, run_id: int, status: str) -> None:
    Session = get_session_factory(cfg)
    with Session() as s:
        s.execute(update(ModelRun).where(ModelRun.id == run_id).values(status=status))
        s.commit()


def update_score_and_metrics(cfg: AppConfig, run_id: int, score: float, metrics: dict, status: Optional[str] = None) -> None:
    Session = get_session_factory(cfg)
    with Session() as s:
        values = {"score": score, "metrics": metrics}
        if status is not None:
            values["status"] = status
        s.execute(update(ModelRun).where(ModelRun.id == run_id).values(**values))
        s.commit()


def bulk_insert(cfg: AppConfig, runs: Iterable[ModelRun]) -> None:
    Session = get_session_factory(cfg)
    with Session() as s:
        s.add_all(list(runs))
        s.commit()


def enqueue_backtest_job(
    cfg: AppConfig,
    run_id: int,
    symbol: str,
    start_iso: str,
    end_iso: str,
    study_params: dict,
    replay_speed: int,
    accurate: bool,
    all_charts: bool,
    endpoint_host: str = "",
    endpoint_port: int = 0,
) -> int:
    Session = get_session_factory(cfg)
    with Session() as s:
        job = BacktestJob(
            run_id=run_id,
            symbol=symbol,
            start_iso=start_iso,
            end_iso=end_iso,
            study_params=study_params,
            replay_speed=replay_speed,
            accurate=accurate,
            all_charts=all_charts,
            endpoint_host=endpoint_host,
            endpoint_port=endpoint_port,
            status="queued",
        )
        s.add(job)
        s.commit()
        return int(job.id)


def claim_next_backtest_job(cfg: AppConfig) -> Optional[BacktestJob]:
    Session = get_session_factory(cfg)
    with Session() as s:
        job = s.execute(
            select(BacktestJob).where(BacktestJob.status == "queued").order_by(BacktestJob.created_at.asc())
        ).scalars().first()
        if job is None:
            return None
        s.execute(update(BacktestJob).where(BacktestJob.id == job.id).values(status="running"))
        s.commit()
        return job


def set_backtest_job_result(
    cfg: AppConfig,
    job_id: int,
    status: str,
    metrics: Optional[dict] = None,
    result_path: str = "",
    error: str = "",
) -> None:
    Session = get_session_factory(cfg)
    with Session() as s:
        values = {
            "status": status,
            "result_path": result_path,
            "error": error,
        }
        if metrics is not None:
            values["metrics"] = metrics
        s.execute(update(BacktestJob).where(BacktestJob.id == job_id).values(**values))
        s.commit()


def append_backtest_job_event(cfg: AppConfig, job_id: int, payload: dict) -> None:
    Session = get_session_factory(cfg)
    with Session() as s:
        ev = BacktestJobEvent(job_id=job_id, payload=payload)
        s.add(ev)
        s.commit()


def list_backtest_jobs(cfg: AppConfig, limit: int = 100) -> List[BacktestJob]:
    Session = get_session_factory(cfg)
    with Session() as s:
        return s.execute(
            select(BacktestJob).order_by(BacktestJob.created_at.desc()).limit(limit)
        ).scalars().all()

