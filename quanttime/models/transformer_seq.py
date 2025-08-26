from dataclasses import dataclass, asdict
from typing import Any, Dict

import numpy as np
import torch
import torch.nn as nn

from .base import ModelBase


class _TinyTransformer(nn.Module):
    def __init__(self, input_size: int, d_model: int = 64, nhead: int = 4, num_layers: int = 2):
        super().__init__()
        self.input_proj = nn.Linear(input_size, d_model)
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, batch_first=True)
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.head = nn.Linear(d_model, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.input_proj(x)
        enc = self.encoder(z)
        last = enc[:, -1, :]
        return self.head(last)


@dataclass
class TransformerConfig:
    input_size: int
    seq_len: int = 32
    d_model: int = 64
    nhead: int = 4
    num_layers: int = 2
    epochs: int = 5
    lr: float = 1e-3
    batch_size: int = 256


class TransformerModel(ModelBase):
    def __init__(self, config: TransformerConfig):
        self.config = config
        self.model = _TinyTransformer(config.input_size, config.d_model, config.nhead, config.num_layers)
        self.loss_fn = nn.BCEWithLogitsLoss()
        self.device = torch.device("cpu")
        self.model.to(self.device)

    def _to_seq(self, X: np.ndarray) -> torch.Tensor:  # noqa: N803
        N, F = X.shape
        seq = np.repeat(X[:, None, :], self.config.seq_len, axis=1)
        return torch.tensor(seq, dtype=torch.float32, device=self.device)

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:  # noqa: N803
        self.model.train()
        X_seq = self._to_seq(X)
        y_t = torch.tensor(y.reshape(-1, 1), dtype=torch.float32, device=self.device)
        opt = torch.optim.Adam(self.model.parameters(), lr=self.config.lr)
        N = X_seq.shape[0]
        bs = max(1, int(self.config.batch_size))
        for _ in range(self.config.epochs):
            for start in range(0, N, bs):
                end = min(N, start + bs)
                xb = X_seq[start:end]
                yb = y_t[start:end]
                opt.zero_grad()
                logits = self.model(xb)
                loss = self.loss_fn(logits, yb)
                loss.backward()
                opt.step()

    def predict(self, X: np.ndarray) -> np.ndarray:  # noqa: N803
        self.model.eval()
        with torch.no_grad():
            X_t = self._to_seq(X)
            logits = self.model(X_t)
            probs = torch.sigmoid(logits).cpu().numpy().reshape(-1)
            return (probs > 0.5).astype(np.int64)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:  # noqa: N803
        self.model.eval()
        with torch.no_grad():
            X_t = self._to_seq(X)
            logits = self.model(X_t)
            probs = torch.sigmoid(logits).cpu().numpy().reshape(-1)
            return probs

    def save(self, path: str) -> None:
        torch.save({"state_dict": self.model.state_dict(), "config": asdict(self.config)}, path)

    def load(self, path: str) -> None:
        ckpt = torch.load(path, map_location=self.device)
        self.model.load_state_dict(ckpt["state_dict"])
        cfg = ckpt.get("config")
        if cfg is not None:
            self.config = TransformerConfig(**cfg)

    def get_params(self) -> Dict[str, Any]:
        return asdict(self.config)


