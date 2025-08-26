## Master Model Specification & Rulebook for Order Flow–Driven Quant Models

### Core Objective

Build quantitative and algorithmic trading models that utilize order flow, market microstructure data, and price action to identify high-probability entries/exits, maximize risk-adjusted returns, and adapt dynamically to changing market conditions.

### I. Data Acquisition & Processing

- **Primary Data Source**
  - All historical and live data is pulled via DTC from Sierra Chart.
  - Data includes Level 1 (top-of-book) and Level 2 (full depth) order book data, time & sales, and bar-based OHLC data for price context.
  - Data quality is paramount — use unfiltered tick-by-tick order flow data.

- **Order Flow Data Types to Capture**
  - Bid/Ask Volume Delta (per price level & aggregated per candle)
  - Cumulative Delta
  - Limit Order Additions/Removals (resting liquidity tracking)
  - Market Order Aggression (buy/sell pressure by size & velocity)
  - Iceberg Detection (hidden liquidity revealed via replenishment patterns)
  - Absorption Levels (large passive liquidity holding price)
  - Spoofing/Fading Detection (large visible orders that vanish quickly)

- **Data Preprocessing Rules**
  - Normalize all values relative to recent volatility & volume regimes.
  - Bucket large trades into size tiers (small/medium/large/very large) for behavioral tracking.
  - Maintain rolling window statistics for:
    - Average queue size per price level
    - Execution velocity (trades/sec)
    - Depth imbalance ratios

### II. Feature Engineering Guidelines

- **Order Flow & Microstructure Features**
  - Bid/Ask Imbalance Ratio: (Sum(Bid Volume) - Sum(Ask Volume)) / Total Volume
  - Delta Pressure Gradient: Rate of change of cumulative delta over micro timeframes.
  - Liquidity Void Zones: Price areas with historically low resting liquidity — likely breakout points.
  - Absorption Strength: Volume absorbed at a price without price movement.
  - Aggression Surges: Short bursts of heavy market buying/selling.

- **Hybrid Features (Price + Order Flow)**
  - VWAP with order flow deviation markers.
  - Micro pullback detection using delta flips + price stall.
  - Momentum exhaustion signals: price extension + delta divergence.

- **Event-Driven Features**
  - Large lot sweeps across multiple price levels.
  - Unusual liquidity pulls (liquidity evaporates ahead of a move).
  - High correlation between aggression spikes and price breakout probability.

### III. Modeling Rules

- **Model Families to Use**
  - Short-term predictive models: LSTM, Transformer, Temporal CNN for sequence-based prediction.
  - State-based decision-making: Reinforcement Learning for execution strategy refinement.
  - Ensemble methods: Blend statistical models (LightGBM/XGBoost) with deep learning signals.

- **Prediction Targets**
  - Very short-term price movement (1–5 ticks ahead).
  - Breakout vs. fakeout probability.
  - Volatility regime classification.

- **Execution Strategy**
  - Adaptive: Model adjusts aggressiveness based on liquidity conditions.
  - Place orders where predicted imbalance + execution cost is favorable.
  - Avoid entries during detected spoofing/fading events.

### IV. Risk Management Rules

- **Trade Filtering**
  - Only trade when signal strength > threshold based on backtested Sharpe ratio per signal.
  - No trades in low-liquidity chop zones unless clear liquidity sweep detected.

- **Position Sizing**
  - Size scales dynamically with predicted move probability × volatility regime.
  - Reduce size during periods of erratic microstructure behavior.

- **Stop & Exit Logic**
  - Hard stops placed just beyond liquidity walls.
  - Early exit if order flow reverses sharply against position.

### V. Backtesting Rules (Sierra Chart + DTC)

- **Environment**
  - All historical simulations use Sierra Chart’s built-in backtesting engine.
  - All tick/order book data streamed from DTC-compatible Sierra Chart data feeds for accuracy.
  - Backtest environment replicates real market latency & order execution logic.

- **Execution Simulation**
  - Simulate queue position in limit order fills based on real historical depth.
  - Include partial fills and slippage from aggressive orders.
  - Account for liquidity depletion & replenishment in simulation.

- **Performance Evaluation**
  - Metrics: Sharpe, Sortino, Max Drawdown, Win Rate, Average R/R, Execution Efficiency.
  - Walk-forward testing to ensure model robustness.
  - Monte Carlo simulations of trades to stress-test strategy under varying fill conditions.

### VI. Continuous Improvement Rules

- **Post-Live Feedback Loop**
  - Live trades are logged with the full order book snapshot at entry & exit.
  - Discrepancy analysis between predicted vs. actual fills & moves.
  - Model retraining schedule: Weekly for microstructure, monthly for macro filters.

- **Drift Detection**
  - Monitor statistical distributions of features; trigger retrain if drift exceeds thresholds.

- **Strategy Versioning**
  - Each change in feature set, model architecture, or execution logic is tagged & backtested independently.

---

This master spec is the LLM rulebook for model generation, ensuring consistency, profitability focus, and compatibility with Sierra Chart’s DTC-based backtesting environment.

### Interaction Policy (UI-Only)

- All capabilities must be exposed via the Streamlit dashboard. The user will not interact with the CLI.
- If a feature exists only as a script/CLI, add a Streamlit button/input to trigger it before relying on it.
- Documentation and examples should reference the Streamlit UI workflows.


