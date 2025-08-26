import numpy as np
import pandas as pd
from .events import compute_event_features


def _rolling_safe(series: pd.Series, window: int, func: str) -> pd.Series:
    if func == "sum":
        return series.rolling(window, min_periods=1).sum()
    if func == "mean":
        return series.rolling(window, min_periods=1).mean()
    if func == "std":
        return series.rolling(window, min_periods=1).std().fillna(0)
    raise ValueError(f"Unsupported func {func}")


def compute_basic_features(ticks: pd.DataFrame) -> pd.DataFrame:
    df = ticks.copy()
    
    # Handle Databento timestamp columns properly
    from quanttime.utils.databento_utils import handle_databento_timestamps, sort_mbo_data
    df = handle_databento_timestamps(df)
    df = sort_mbo_data(df)
    
    df["price_change"] = df["price"].diff().fillna(0.0)
    df["direction"] = (df["price_change"] > 0).astype(int)
    
    # Use proper Databento side values (B/A instead of buy/sell)
    df["delta"] = df["size"].where(df["side"].eq("B"), -df["size"]).fillna(0)
    df["cum_delta"] = df["delta"].cumsum()
    df["imbalance"] = _rolling_safe(df["delta"], 20, "sum")
    df["volatility"] = _rolling_safe(df["price"].pct_change(), 50, "std")

    # Normalizations relative to recent regimes
    vol_norm = _rolling_safe(df["size"], 100, "mean").replace(0, np.nan)
    df["size_norm"] = (df["size"] / vol_norm).fillna(0.0)
    df["delta_norm"] = (df["delta"] / (_rolling_safe(df["size"], 100, "std") + 1e-6)).fillna(0.0)

    # Aggression: buy vs sell pressure velocity (using Databento side values)
    df["buy_size"] = df["size"].where(df["side"].eq("B"), 0.0)
    df["sell_size"] = df["size"].where(df["side"].eq("A"), 0.0)
    df["buy_velocity"] = _rolling_safe(df["buy_size"], 20, "sum")
    df["sell_velocity"] = _rolling_safe(df["sell_size"], 20, "sum")
    denom = (df["buy_velocity"] + df["sell_velocity"]).replace(0, np.nan)
    df["bid_ask_imbalance_ratio"] = ((df["buy_velocity"] - df["sell_velocity"]) / denom).fillna(0.0)

    # Delta pressure gradient (rate of change of cumulative delta)
    df["delta_pressure_gradient"] = df["cum_delta"].diff().fillna(0.0)

    # Hybrid: VWAP deviation markers (approximate tick VWAP)
    vol_window = _rolling_safe(df["size"], 50, "sum").replace(0, np.nan)
    vwap_num = _rolling_safe(df["price"] * df["size"], 50, "sum")
            df["vwap50"] = (vwap_num / vol_window).ffill().fillna(df["price"]).astype(float)
    df["vwap_dev"] = (df["price"] - df["vwap50"]) / (df["vwap50"].replace(0, np.nan))
    df["vwap_dev"] = df["vwap_dev"].replace([np.inf, -np.inf], 0.0).fillna(0.0)

    # Momentum exhaustion: price extension + delta divergence
    df["price_mom"] = _rolling_safe(df["price_change"], 20, "sum")
    df["delta_mom"] = _rolling_safe(df["delta"], 20, "sum")
    df["mom_divergence"] = (df["price_mom"].where(df["price_mom"].abs() > 1e-9, 1.0) - df["delta_mom"]).astype(float)

    df = df.dropna().reset_index(drop=True)
    # Append event-driven features
    df = compute_event_features(df)
    return df


