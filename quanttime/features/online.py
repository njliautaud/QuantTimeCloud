from collections import deque
from typing import Deque, Dict, List, Tuple

import numpy as np
import pandas as pd

from quanttime.features.engineer import compute_basic_features


class OnlineFeatureWindow:
    def __init__(self, maxlen: int = 512):
        self.rows: Deque[Dict] = deque(maxlen=maxlen)

    def append(self, msg: Dict) -> None:
        self.rows.append({
            "ts": float(msg["ts"]),
            "price": float(msg["price"]),
            "size": float(msg.get("size", 1.0)),
            "side": str(msg.get("side", "buy")),
        })

    def latest_frame(self) -> pd.DataFrame:
        if not self.rows:
            return pd.DataFrame(columns=["ts", "price", "size", "side"])  # empty
        df = pd.DataFrame(list(self.rows))
        return df

    def features_and_labels(self) -> Tuple[pd.DataFrame, List[str]]:
        df = compute_basic_features(self.latest_frame())
        # Expose richer microstructure features; exclude label-like cols
        exclude = {"ts", "price", "side", "direction"}
        features = [c for c in df.columns if c not in exclude]
        return df, features


