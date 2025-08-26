import pandas as pd


def ticks_to_bars(ticks: pd.DataFrame, rule: str = "1S") -> pd.DataFrame:
    if ticks.empty:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
    df = ticks.copy()
    df["dt"] = pd.to_datetime(df["ts"], unit="s")
    df = df.set_index("dt").sort_index()
    price = df["price"].astype(float)
    volume = df.get("size", 1.0).astype(float)
    ohlc = price.resample(rule).ohlc()
    vol = volume.resample(rule).sum().rename("volume")
    bars = pd.concat([ohlc, vol], axis=1).dropna(how="all").reset_index()
    bars = bars.rename(columns={"index": "dt"})
    bars["ts"] = (bars["dt"].astype("int64") // 10**9).astype(float)
    return bars[["ts", "open", "high", "low", "close", "volume"]]


