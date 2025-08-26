## Master Plan: Sierra Chart DTC + Automated Backtesting Wrapper

This file captures the authoritative plan used for implementation in SierraFlow. It defines the architecture, command surface, and automation rules we implemented across the Python orchestrator, Streamlit UI, and OS automation hooks.

### A) Goal & Big Picture

- Use Sierra Chart DTC for live connectivity (market data, depth, orders, account/positions).
- Run high-fidelity backtests inside Sierra using Replay in Accurate Trading System Back Test Mode.
- External controller orchestrates experiments and ingests results.

Why: You get Sierra’s depth + fill realism without rebuilding an order-book simulator.

### B) Architecture Overview

- External Orchestrator (Python): sends commands (JSON over IPC) to ACSIL, receives status/results.
- ACSIL "Backtest Control" Study: listens for commands, controls replay, emits results.
- OS Automation Helper: fills UI-only gaps (replay panel toggles, etc.).
- Sierra Chart (Denali): DTC server; native replay/backtest engine.

### C) ACSIL Control Surface (implemented client-side)

Commands used by the orchestrator:

- `PING`, `GET_STATUS`
- `LOAD_CHART {symbol, timeframe, session, study_params}`
- `WAIT_READY`
- `SET_REPLAY_MODE {accurate, all_charts}`
- `SET_DATES {start, end}`
- `START_REPLAY {speed}` / `STOP_REPLAY`
- `ENABLE_AUTOTRADE {chart_id, on}`
- `GET_RESULTS`
- `RESET_STATS`

Expected ACSIL behaviors leveraged:

- `sc.StartChartReplay*`, `sc.ReplayStatus`, `sc.IsChartDataLoadingCompleteForAllCharts()`
- Study input changes via `sc.SetChartStudyInput*`
- Trade entry/exit via standard ACSIL order functions

### D) OS Automation Hooks

- Launch Sierra with the target Chartbook and ensure the ACSIL study is added via UI automation if not present.
- Optionally open the Replay Control Panel and set UI-only toggles.
- Prefer stable selectors and hotkeys; retry and verify via polling `sc.ReplayStatus`.

### E) Runbook: Automated Backtest Lifecycle

1. Launch Sierra with Chartbook; ACSIL study opens IPC port.
2. `LOAD_CHART` and `WAIT_READY` until data is loaded.
3. Configure replay mode/dates; enable auto-trading.
4. `START_REPLAY` at chosen speed; monitor.
5. On completion, `GET_RESULTS`; persist to disk/DB. UI shows real-time progress by consuming ACSIL `PROGRESS` events.
6. `RESET_STATS`; proceed to next parameter set.

### F) Data & Results to Export

- Strategy metadata; time range, symbols; fills; equity curve; trade stats; environment (depth, mode, speed).

### G) DTC Capabilities (live)

- Auth & Session: `LOGON_REQUEST`, `HEARTBEAT`, `LOGOFF`
- Streaming Market Data: `MARKET_DATA_REQUEST`, `MARKET_DEPTH_REQUEST`
- Historical Data: `HISTORICAL_PRICE_DATA_REQUEST`
- Orders: `SUBMIT_NEW_SINGLE_ORDER`, `CANCEL_REPLACE_ORDER`, etc.
- Positions/Accounts: `CURRENT_POSITIONS_REQUEST`, `ACCOUNT_BALANCE_REQUEST`, fills (if supported)
- Discovery: `EXCHANGE_LIST_REQUEST`, `SYMBOL_SEARCH_REQUEST`, `SECURITY_DEFINITION_FOR_SYMBOL_REQUEST`

Note: Use DTC for live; use ACSIL automation for Sierra backtests.

Binary DTC Client
-----------------

- We provide a minimal Protobuf-based DTC client (`sierraflow/adapter/dtc_binary.py`) with Logon, Heartbeat, and Historical Ticks.
- To enable, set `DTC_TRANSPORT=tcp_binary` and configure `SIERRA_DTC_PORT`.
- For full coverage (depth, orders), extend the client with additional message types per the DTC spec.

### H) Decision Guidance

- Need depth realism → automate Sierra replay.
- Need massive sweeps with simpler fills → use an external scriptable engine, validate finalists in Sierra.

### I) Milestones

- Week 1–2: ACSIL skeleton + IPC, DTC client scaffolding, basic commands.
- Week 3–4: Param sweeps, retries, idempotent runs, UI dashboard for results.
- Week 5–6: Harden automation, add telemetry, parallelize across Sierra instances. Add queue persistence and a fleet orchestrator.

### J) Notes & Caveats

- Some replay toggles are UI-only; keep a small OS automation component.
- Always wait for chart data load before starting replay.
- Treat DTC spec pages as on-wire schema truth.


