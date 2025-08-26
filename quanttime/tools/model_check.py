import sys
from pathlib import Path
import numpy as np

from .types import CheckResult
from quanttime.models.lgbm_tabular import LGBMModel
from quanttime.models.torch_lstm import LSTMConfig, LSTMModel
from quanttime.models.transformer_seq import TransformerConfig, TransformerModel
from quanttime.models.temporal_cnn import TCNConfig, TemporalCNNModel


def run() -> CheckResult:
    try:
        X = np.random.normal(size=(256, 8)).astype(float)
        y = (np.random.random(256) > 0.5).astype(int)
        results = {}
        # LGBM
        m1 = LGBMModel(n_estimators=10, max_depth=3)
        m1.fit(X, y)
        results["lgbm_pred_mean"] = float(m1.predict(X).mean())
        # LSTM
        m2 = LSTMModel(LSTMConfig(input_size=8, epochs=1, batch_size=64))
        m2.fit(X, y)
        results["lstm_pred_mean"] = float(m2.predict_proba(X).mean())
        # Transformer
        m3 = TransformerModel(TransformerConfig(input_size=8, epochs=1, batch_size=64))
        m3.fit(X, y)
        results["tr_pred_mean"] = float(m3.predict_proba(X).mean())
        # TCN
        m4 = TemporalCNNModel(TCNConfig(input_size=8, epochs=1, batch_size=64))
        m4.fit(X, y)
        results["tcn_pred_mean"] = float(m4.predict_proba(X).mean())
        return CheckResult(name="model", ok=True, details=results)
    except Exception as e:
        return CheckResult(name="model", ok=False, details={}, error=str(e))


