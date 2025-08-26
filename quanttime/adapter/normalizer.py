import pandas as pd
from quanttime.data.schemas import Tick


def normalize_tick(msg: Dict[str, Any]) -> Tick:
    # Expected generic mapping; adapt as needed for DTC message schema
    return Tick(
        ts=float(msg.get("ts", msg.get("timestamp", 0.0))),
        price=float(msg.get("price")),
        size=float(msg.get("size", 1.0)),
        side=str(msg.get("side", "buy")),
    )


