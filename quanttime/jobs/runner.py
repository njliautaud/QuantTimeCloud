import os
import sys
import time
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Dict, Tuple, Optional, Any

import numpy as np
import pandas as pd

from quanttime.backtest.engine import BacktestConfig, simple_backtest, backtest_with_trades, walk_forward_slices, monte_carlo_bootstrap
from quanttime.features.engineer import compute_basic_features
from quanttime.models.lgbm_tabular import LGBMModel
from quanttime.models.storage import model_artifact_path
from quanttime.registry.db import Base, get_engine, get_session_factory
from quanttime.registry.models import ModelRun
from quanttime.registry.service import set_status
from quanttime.utils.config import AppConfig
from quanttime.utils.logging import get_logger


@contextmanager
def db_session(cfg: AppConfig):
    Session = get_session_factory(cfg)
    engine = get_engine(cfg)
    Base.metadata.create_all(engine)
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _train_val_test_split_time(df: pd.DataFrame, train_frac: float = 0.6, val_frac: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n = len(df)
    tr_end = max(1, int(n * train_frac))
    val_end = max(tr_end + 1, int(n * (train_frac + val_frac)))
    return df.iloc[:tr_end].copy(), df.iloc[tr_end:val_end].copy(), df.iloc[val_end:].copy()


def run_training_job(cfg: AppConfig, name: str, ticks_df: pd.DataFrame, model_type: str = "LGBM", 
                    timeframe_filter: Optional[Any] = None) -> Dict:
    logger = get_logger("TrainingJob")
    
    # Apply timeframe filtering if provided
    if timeframe_filter is not None:
        logger.info(f"Applying timeframe filter: {timeframe_filter.tag}")
        from quanttime.utils.timeframe_filter import filter_mbo_data_by_timeframe
        ticks_df = filter_mbo_data_by_timeframe(ticks_df, timeframe_filter)
        logger.info(f"Filtered data: {len(ticks_df)} rows remaining")
    
    logger.info("Computing features")
    df = compute_basic_features(ticks_df)
    features = [c for c in df.columns if c not in ["ts", "price", "side", "direction"]]
    train_df, val_df, test_df = _train_val_test_split_time(df)
    X_tr = train_df[features].values.astype(float)
    y_tr = train_df["direction"].values.astype(int)
    X_val = val_df[features].values.astype(float) if len(val_df) else X_tr
    y_val = val_df["direction"].values.astype(int) if len(val_df) else y_tr
    X_te = test_df[features].values.astype(float) if len(test_df) else X_val
    y_te = test_df["direction"].values.astype(int) if len(test_df) else y_val

    if X_tr.shape[0] < 50:
        logger.warning("Too few rows; generating synthetic data for training")
        rng = np.random.default_rng(0)
        X_tr = rng.normal(size=(500, len(features) or 4))
        y_tr = (rng.random(500) > 0.5).astype(int)
        X_val = rng.normal(size=(200, len(features) or 4))
        y_val = (rng.random(200) > 0.5).astype(int)

    model_type_u = model_type.upper()
    if model_type_u == "LGBM":
        model = LGBMModel(n_estimators=50, max_depth=4)
    elif model_type_u == "LSTM":
        from quanttime.models.torch_lstm import LSTMConfig, LSTMModel
        input_size = len(features) or 4
        model = LSTMModel(LSTMConfig(input_size=input_size, hidden_size=32, epochs=2))
    elif model_type_u in {"TRANSFORMER", "TR"}:
        from quanttime.models.transformer_seq import TransformerConfig, TransformerModel
        input_size = len(features) or 4
        model = TransformerModel(TransformerConfig(input_size=input_size, seq_len=32, epochs=2))
    elif model_type_u in {"TCN", "TEMPORAL_CNN"}:
        from quanttime.models.temporal_cnn import TCNConfig, TemporalCNNModel
        input_size = len(features) or 4
        model = TemporalCNNModel(TCNConfig(input_size=input_size, seq_len=32, channels=32, epochs=2))
    else:
        input_size = len(features) or 4
        model = LGBMModel(n_estimators=50, max_depth=4)
    model.fit(X_tr, y_tr)
    preds_tr = model.predict(X_tr)
    preds_val = model.predict(X_val)
    preds_te = model.predict(X_te)

    bt_cfg = BacktestConfig(
        commission_per_contract=cfg.commission_per_contract,
        slippage_ticks=cfg.slippage_ticks,
        tick_size=cfg.tick_size,
    )
    metrics_tr = simple_backtest(train_df, preds_tr, bt_cfg)
    metrics_val = simple_backtest(val_df if len(val_df) else train_df, preds_val, bt_cfg)
    metrics_te, trades_te = backtest_with_trades(test_df if len(test_df) else val_df, preds_te, bt_cfg)

    # Walk-forward and Monte Carlo robustness checks
    wf = []
    slices = walk_forward_slices(len(df))
    for (a, b, c, d) in slices:
        Xwf_tr = df.iloc[a:b][features].values.astype(float)
        ywf_tr = df.iloc[a:b]["direction"].values.astype(int)
        Xwf_val = df.iloc[c:d][features].values.astype(float)
        model.fit(Xwf_tr, ywf_tr)
        wf_pred = model.predict(Xwf_val)
        wf_metrics = simple_backtest(df.iloc[c:d], wf_pred, bt_cfg)
        wf.append(wf_metrics)
    mc = monte_carlo_bootstrap(trades_te["pnl"].values if len(test_df) else np.array([]))
    metrics = {
        **{f"train_{k}": v for k, v in metrics_tr.items()},
        **{f"val_{k}": v for k, v in metrics_val.items()},
        **{f"test_{k}": v for k, v in metrics_te.items()},
        **mc,
        "wf_avg_sharpe": float(np.mean([m.get("sharpe", 0.0) for m in wf])) if wf else 0.0,
    }

    # Add timeframe information to model name and dataset description
    timeframe_info = ""
    if timeframe_filter is not None:
        timeframe_info = f"_{timeframe_filter.tag}"
        dataset_desc = f"rows={len(df)}_timeframe={timeframe_filter.tag}"
    else:
        dataset_desc = f"rows={len(df)}_timeframe=24h"
    
    # Get timeframe tag for database
    timeframe_tag = timeframe_filter.tag if timeframe_filter else "24h"
    
    run = ModelRun(
        name=f"{name}{timeframe_info}",
        architecture=model_type_u,
        hyperparameters=model.get_params(),
        dataset=dataset_desc,
        timeframe=timeframe_tag,
        metrics=metrics,
        score=0.0,  # Leaderboard excludes internal backtest; score assigned after Sierra Chart BT
        status="ready_for_sc_backtest",
    )
    with db_session(cfg) as s:
        s.add(run)
        s.flush()
        # Save artifact after ID is assigned
        path = model_artifact_path(cfg, run.id, name, ext="joblib")
        try:
            model.save(str(path))
            run.artifact_path = str(path)
        except Exception:
            logger.exception("Failed to save model artifact")
    logger.info(f"Stored model run id={run.id}")
    try:
        set_status(cfg, run.id, "ready_for_sc_backtest")
    except Exception:
        logger.exception("Failed to set status for run")
    return {"id": run.id, "metrics": metrics}


