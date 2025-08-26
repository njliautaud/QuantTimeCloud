import numpy as np
import pandas as pd


def compute_event_features(df: pd.DataFrame) -> pd.DataFrame:
    """Heuristic microstructure event signals derived from tick data.

    Inputs: df with columns ts, price, size, side and optional precomputed fields (delta, cum_delta).

    Returns df with added columns:
      - absorption_strength
      - iceberg_score
      - spoofing_flag (0/1)
      - aggression_surge (0/1)
      - liquidity_void (0/1)
    """
    out = df.copy()
    if "delta" not in out.columns:
        out["delta"] = out["size"].where(out["side"].str.lower().eq("buy"), -out["size"]).fillna(0.0)
    out["price_change"] = out["price"].diff().fillna(0.0)

    # Absorption: large opposing volume with minimal price change
    vol_roll = out["size"].rolling(50, min_periods=1).sum()
    abs_vol = out["delta"].rolling(20, min_periods=1).sum().abs()
    small_move = out["price_change"].abs().rolling(20, min_periods=1).sum() + 1e-6
    out["absorption_strength"] = (abs_vol / vol_roll.replace(0, np.nan)).fillna(0.0) * (1.0 / small_move)
    out["absorption_strength"] = out["absorption_strength"].clip(0, 10)

    # Iceberg: repeated prints at/near same price with sustained volume
    price_bucket = (out["price"] / max(out["price"].abs().median() * 1e-6, 0.01)).round(2)
    replenishment = out.groupby(price_bucket)["size"].transform(lambda s: s.rolling(10, min_periods=1).sum())
    out["iceberg_score"] = (replenishment / (out["size"].rolling(50, min_periods=1).mean() + 1e-6)).fillna(0.0).clip(0, 10)

    # Spoofing/fading: surge in apparent activity without follow-through and quick reversal
    delta_roll = out["delta"].rolling(30, min_periods=1).sum()
    price_roll = out["price_change"].rolling(30, min_periods=1).sum()
    reversal = (price_roll.shift(-10).fillna(0.0) * price_roll < 0).astype(int)
    no_follow = price_roll.abs() < (out["price"].rolling(50, min_periods=1).std().fillna(0.0) * 0.2)
    out["spoofing_flag"] = ((delta_roll.abs() > delta_roll.abs().rolling(200, min_periods=1).median().fillna(0.0) * 3) & no_follow & (reversal > 0)).astype(int)

    # Aggression surge: bursty market orders by size/velocity
    buy_vel = out["size"].where(out["side"].str.lower().eq("buy"), 0.0).rolling(20, min_periods=1).sum()
    sell_vel = out["size"].where(out["side"].str.lower().eq("sell"), 0.0).rolling(20, min_periods=1).sum()
    vel = (buy_vel + sell_vel)
    out["aggression_surge"] = (vel > (vel.rolling(200, min_periods=1).median().fillna(0.0) * 3)).astype(int)

    # Liquidity void: stretches with very low traded size
    out["liquidity_void"] = (out["size"].rolling(50, min_periods=1).mean() < out["size"].rolling(500, min_periods=1).mean().fillna(0.0) * 0.25).astype(int)

    return out


