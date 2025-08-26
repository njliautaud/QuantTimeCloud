import os
import json
from typing import List

import pandas as pd
import streamlit as st
# type: ignore comment to silence static checkers for optional Plotly
# mypy: ignore-errors
import plotly.graph_objects as go

from quanttime.utils.config import AppConfig
from quanttime.registry.models import ModelRun
import streamlit as st
from streamlit.components.v1 import html as st_html


def list_parquet_files(cfg: AppConfig) -> List[str]:
    if not os.path.isdir(cfg.data_dir):
        return []
    return [os.path.join(cfg.data_dir, f) for f in os.listdir(cfg.data_dir) if f.endswith(".parquet")]


def equity_chart(trades: pd.DataFrame):
    if "equity" in trades.columns:
        st.line_chart(trades[["equity"]])


def model_card(name: str, arch: str, score: float, metrics: dict):
    st.markdown(
        f"**{name}**  ".strip()
    )
    st.caption(f"{arch} | Score: {score:.3f}")
    cols = st.columns(3)
    cols[0].metric("Sharpe", f"{metrics.get('val_sharpe', 0):.2f}")
    cols[1].metric("PnL", f"{metrics.get('val_pnl', 0):.0f}")
    cols[2].metric("DD", f"{metrics.get('val_max_drawdown', 0):.2f}")


def model_card_clickable(run: ModelRun, section: str = "queue") -> None:
    """Render a clickable card with stage tag.

    section in {training, ready_for_sc_backtest, sc_backtested, live}
    """
    with st.container(border=True):
        st.markdown(f"**{run.name}**  ")
        st.caption(f"{run.architecture} | Stage: {run.status}")
        cols = st.columns(4)
        cols[0].metric("WF Sharpe", f"{(run.metrics or {}).get('wf_avg_sharpe', 0):.2f}")
        cols[1].metric("Test Sharpe", f"{(run.metrics or {}).get('test_sharpe', 0):.2f}")
        cols[2].metric("Test PnL", f"{(run.metrics or {}).get('test_pnl', 0):.0f}")
        cols[3].metric("MC p50", f"{(run.metrics or {}).get('sharpe_p50', 0):.2f}")
        st.button("Select", key=f"select_{run.id}_{section}", args=None)


def list_datasets(cfg: AppConfig) -> List[str]:
    if not os.path.isdir(cfg.data_dir):
        return []
    files = []
    for f in os.listdir(cfg.data_dir):
        if f.endswith((".parquet", ".csv")):
            files.append(os.path.join(cfg.data_dir, f))
    return sorted(files)


def footprint_chart(df: pd.DataFrame, dark: bool = False):
    """Render a basic footprint chart with normalized delta below.

    Expects df with columns: ts, price, size, side; will compute 1-min aggregation.
    """
    if df.empty:
        st.info("No data to display")
        return
    # Ensure ts is datetime
    ts = pd.to_datetime(df["ts"], unit="s", errors="coerce") if pd.api.types.is_numeric_dtype(df["ts"]) else pd.to_datetime(df["ts"], errors="coerce")
    df = df.assign(ts=ts).dropna(subset=["ts"])  # type: ignore

    # Compute delta per tick
    df = df.copy()
    df["delta"] = df["size"].where(df["side"].str.lower().eq("buy"), -df["size"]).fillna(0.0)
    df.set_index("ts", inplace=True)
    # 1-minute bars footprint approximation
    g = df.resample("1min")
    o = g["price"].first()
    h = g["price"].max()
    l = g["price"].min()
    c = g["price"].last()
    vol = g["size"].sum().fillna(0.0)
    delta = g["delta"].sum().fillna(0.0)
    bars = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": vol, "delta": delta}).dropna()
    if bars.empty:
        st.info("No aggregated bars to display")
        return
    # Normalized delta
    denom = bars["volume"].replace(0, pd.NA).astype(float)
    bars["delta_norm"] = (bars["delta"].astype(float) / denom).fillna(0.0).clip(-1, 1)

    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=bars.index, open=bars["open"], high=bars["high"], low=bars["low"], close=bars["close"], name="Price"))
    fig.update_layout(xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=20, b=10), height=500, template=("plotly_dark" if dark else "plotly"))

    # Secondary axis for delta
    fig.add_trace(go.Bar(x=bars.index, y=bars["delta_norm"], name="Delta (norm)", marker_color=["#2ca02c" if v >= 0 else "#d62728" for v in bars["delta_norm"]], yaxis="y2"))
    fig.update_layout(
        yaxis=dict(title="Price"),
        yaxis2=dict(title="Norm Delta", overlaying="y", side="right", position=1.0, showgrid=False),
        barmode="relative",
    )
    st.plotly_chart(fig, use_container_width=True)


def _bars_from_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert OHLCV candle data to TradingView format.
    
    Reference: databento-python-main/examples/historical_timeseries_to_df.py - DataFrame structure and timestamp handling
    """
    if df.empty:
        return pd.DataFrame()
    
    # Ensure we have the required columns
    required_cols = ['timestamp', 'open', 'high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        return pd.DataFrame()
    
    # Convert timestamp to Unix timestamp
    # Reference: databento-python-main/examples/historical_timeseries_to_df.py - Timestamp conversion patterns
    df = df.copy()
    if 'timestamp' in df.columns:
        df['time'] = pd.to_datetime(df['timestamp']).astype(int) // 10**9
    else:
        df['time'] = pd.to_datetime(df.index).astype(int) // 10**9
    
    # Select and rename columns for TradingView format
    result = df[['time', 'open', 'high', 'low', 'close']].copy()
    result = result.dropna()
    
    return result


def _bars_from_ticks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert tick data to OHLC bars for TradingView.
    
    Reference: databento-python-main/examples/historical_timeseries_to_df.py - Data aggregation and resampling patterns
    """
    if df.empty:
        return pd.DataFrame()
    
    # Check if this is already OHLCV data
    if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
        return _bars_from_ohlcv(df)
    
    # Check if this is tick data
    if 'price' not in df.columns:
        return pd.DataFrame()
    
    # Convert tick data to OHLC bars
    ts_col = 'ts' if 'ts' in df.columns else 'datetime'
    if ts_col not in df.columns:
        return pd.DataFrame()
    
    # Reference: databento-python-main/examples/historical_timeseries_to_df.py - Timestamp handling
    ts = pd.to_datetime(df[ts_col], unit="s", errors="coerce") if pd.api.types.is_numeric_dtype(df[ts_col]) else pd.to_datetime(df[ts_col], errors="coerce")
    df = df.assign(ts=ts).dropna(subset=["ts"])  # type: ignore
    g = df.set_index("ts").resample("1min")
    o = g["price"].first()
    h = g["price"].max()
    l = g["price"].min()
    c = g["price"].last()
    return pd.DataFrame({"time": o.index.astype(int) // 10**9, "open": o, "high": h, "low": l, "close": c}).dropna()


def tradingview_chart(
    df: pd.DataFrame,
    dark: bool = False,
    height: int = 520,
    show_footprint: bool = True,
    volume_heatmap: bool = True,
    bids_asks: tuple | None = None,
):
    """
    Render TradingView-style chart using Lightweight Charts CDN.

    If df has tick-level columns (ts, price), we aggregate to 1-min OHLC for display.
    
    Reference: databento-python-main/examples/historical_timeseries_to_df.py - DataFrame processing and display patterns
    """
    if df is None or df.empty:
        st.info("No data to display")
        return
    bars = _bars_from_ticks(df)
    if bars.empty:
        st.info("No aggregated bars to display")
        return
    data = bars.to_dict(orient="records")
    js_data = json.dumps(data)
    # Simple volume heatmap per bar: use volume from underlying ticks
    # Reference: databento-python-main/examples/historical_timeseries_to_df.py - Volume data handling
    vol = (
        df.assign(ts=pd.to_datetime(df["ts"], unit="s", errors="coerce") if pd.api.types.is_numeric_dtype(df["ts"]) else pd.to_datetime(df["ts"], errors="coerce"))
        .dropna(subset=["ts"])  # type: ignore
        .set_index("ts")["size"].resample("1min").sum().reindex(pd.to_datetime(bars["time"], unit="s"), fill_value=0.0)
    )
    vol_js = json.dumps([float(v) for v in vol.values])
    bg = "#000000" if dark else "#FFFFFF"
    fg = "#D1D4DC" if dark else "#333333"
    grid = "#1f2430" if dark else "#e1e3e6"
    vol_color = "#60a5fa" if dark else "#3b82f6"
    bids, asks = (bids_asks or ([], []))
    bids_js = json.dumps([[float(p), float(s)] for p, s in bids])
    asks_js = json.dumps([[float(p), float(s)] for p, s in asks])
    html_tmpl = """
    <div style="display:flex; gap:8px;">
      <div id="tv_chart" style="flex:1; height:%(height)s"></div>
      <div id="dom_panel" style="width:260px; height:%(height)s; overflow:hidden; border:1px solid #e1e3e6; border-radius:6px; padding:6px; background:%(bg)s; color:%(fg)s;"></div>
    </div>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>
      const container = document.getElementById('tv_chart');
      const chart = LightweightCharts.createChart(container, {
        layout: { background: { color: '%(bg)s' }, textColor: '%(fg)s' },
        rightPriceScale: { borderColor: '%(grid)s' },
        timeScale: { borderColor: '%(grid)s' },
        grid: { vertLines: { color: '%(grid)s' }, horzLines: { color: '%(grid)s' } },
        crosshair: { mode: 1 }
      });
      const series = chart.addCandlestickSeries();
      const data = %(js_data)s;
      series.setData(data);
      // Volume heatmap overlay via histogram (approximate liquidity/volume per bar)
      const vols = %(vol_js)s;
      const volSeries = chart.addHistogramSeries({ priceScaleId: 'right', color: '%(vol_color)s', base: 0 });
      const volData = data.map((d, i) => ({ time: d.time, value: vols[i] || 0 }));
      volSeries.setData(volData);
      chart.timeScale().fitContent();

      // DOM ladder placeholder: expects global function setDomLadder(bids, asks)
      const domEl = document.getElementById('dom_panel');
      window.setDomLadder = function(bids, asks) {
        const fmt = (x) => (typeof x === 'number' && isFinite(x)) ? x.toFixed(2) : (x ?? '');
        const rows = [];
        const depth = Math.max(bids.length, asks.length);
        for (let i = depth - 1; i >= 0; i--) {
          const bd = bids[i] || [null, null];
          const ak = asks[depth - 1 - i] || [null, null];
          rows.push(
            '<div style="display:flex; justify-content:space-between;">' +
            '<div style="width:45%%; text-align:left; color:#16a34a;">' + fmt(bd[1]) + '</div>' +
            '<div style="width:10%%; text-align:center;">' + fmt(bd[0]) + '</div>' +
            '<div style="width:10%%; text-align:center;">|</div>' +
            '<div style="width:10%%; text-align:center;">' + fmt(ak[0]) + '</div>' +
            '<div style="width:45%%; text-align:right; color:#ef4444;">' + fmt(ak[1]) + '</div>' +
            '</div>'
          );
        }
        domEl.innerHTML = '<div style="font-weight:600; margin-bottom:6px;">DOM</div>' + rows.join('');
      }

      // Initialize DOM with provided snapshot
      try { window.setDomLadder(%(bids_js)s, %(asks_js)s); } catch(e) {}
    </script>
    """
    html = html_tmpl % {
        "height": f"{height}px",
        "bg": bg,
        "fg": fg,
        "grid": grid,
        "js_data": js_data,
        "vol_js": vol_js,
        "vol_color": vol_color,
        "bids_js": bids_js,
        "asks_js": asks_js,
    }
    st_html(html, height=height + 20)

