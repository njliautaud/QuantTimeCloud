from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from quanttime.utils.config import AppConfig


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    architecture: Mapped[str] = mapped_column(String(64), index=True)
    hyperparameters: Mapped[dict] = mapped_column(JSON, default={})
    dataset: Mapped[str] = mapped_column(Text)
    timeframe: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # Timeframe filter used
    metrics: Mapped[dict] = mapped_column(JSON, default={})
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    live_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    artifact_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")  # stages: training, ready_for_sc_backtest, sc_backtested, live
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class BacktestJob(Base):
    __tablename__ = "backtest_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(64))
    start_iso: Mapped[str] = mapped_column(String(32))
    end_iso: Mapped[str] = mapped_column(String(32))
    study_params: Mapped[dict] = mapped_column(JSON, default={})
    replay_speed: Mapped[int] = mapped_column(Integer, default=1)
    accurate: Mapped[bool] = mapped_column(Boolean, default=True)
    all_charts: Mapped[bool] = mapped_column(Boolean, default=True)
    endpoint_host: Mapped[str] = mapped_column(String(128), default="")
    endpoint_port: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="queued")  # queued|running|succeeded|failed
    error: Mapped[str] = mapped_column(Text, default="")
    result_path: Mapped[str] = mapped_column(Text, default="")
    metrics: Mapped[dict] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class BacktestJobEvent(Base):
    __tablename__ = "backtest_job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer, index=True)
    ts: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    payload: Mapped[dict] = mapped_column(JSON, default={})


