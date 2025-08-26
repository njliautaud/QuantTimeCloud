import os
from pathlib import Path
from typing import Optional, Tuple

from quanttime.models.lgbm_tabular import LGBMModel
from quanttime.models.torch_lstm import LSTMConfig, LSTMModel
from quanttime.models.transformer_seq import TransformerConfig, TransformerModel
from quanttime.models.temporal_cnn import TCNConfig, TemporalCNNModel
from quanttime.models.base import ModelBase
from quanttime.registry.service import get_run
from quanttime.utils.config import AppConfig


def load_model_by_run_id(cfg: AppConfig, run_id: int) -> Tuple[Optional[ModelBase], Optional[str]]:
    run = get_run(cfg, run_id)
    if not run or not run.artifact_path:
        return None, "Artifact not found"
    art = Path(run.artifact_path)
    arch = (run.architecture or "").lower()
    if arch.startswith("lgbm"):
        model = LGBMModel()
        model.load(str(art))
        return model, None
    if arch.startswith("lstm"):
        # Try to infer input size; fall back to config stored in artifact
        cfg_lstm = LSTMConfig(input_size=16)
        model = LSTMModel(cfg_lstm)
        model.load(str(art))
        return model, None
    if arch.startswith("transformer"):
        cfg_tr = TransformerConfig(input_size=16)
        model = TransformerModel(cfg_tr)
        model.load(str(art))
        return model, None
    if arch.startswith("tcn") or arch.startswith("temporal_cnn"):
        cfg_tcn = TCNConfig(input_size=16)
        model = TemporalCNNModel(cfg_tcn)
        model.load(str(art))
        return model, None
    return None, f"Unknown architecture: {run.architecture}"


