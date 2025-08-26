## LLM Troubleshooting Tools

These tools are intended solely for AI-assisted diagnostics. The end-user should NOT use the CLI; all user interactions occur via the Streamlit UI.

### Commands (for LLM/operator use only)

- Run all core checks:
  - `sierraflow tools run_all`

- Ingest Sierra Chart backtest results for a specific run:
  - `sierraflow tools sc_ingest --run-id <ID>`

### Coverage

- Config, ZMQ, DTC link, data discovery, feature generation, model wrappers, registry, runtime snapshot, SC backtest ingestion.

### Sierra Automation (ACSIL Orchestrator)

- The Streamlit Backtests tab includes a "Run Sierra Automated Backtest (ACSIL)" section to drive Sierra replay/backtests via an ACSIL command listener.
- Commands issued: `LOAD_CHART`, `WAIT_READY`, `SET_REPLAY_MODE`, `SET_DATES`, `ENABLE_AUTOTRADE`, `START_REPLAY`, `GET_RESULTS`, `RESET_STATS`.
- Results are saved to `SC_BACKTEST_DIR` for ingestion with the existing "Ingest SC Results" button in the Leaderboard tab.

Environment variables:

- `SIERRA_CHART_EXE` path to SierraChart.exe
- `SIERRA_CHARTBOOK_PATH` path to a stable Chartbook layout
- `SIERRA_ACSIL_HOST` and `SIERRA_ACSIL_PORT` for the ACSIL IPC server
- `SC_USE_ACCURATE_MODE`, `SC_REPLAY_ALL_CHARTS`, `SC_REPLAY_SPEED` preferences
- `SC_ACSIL_STUDY_NAME` the display name of your ACSIL study to ensure it is added via UI automation
- `SIERRA_ACSIL_ENDPOINTS` to define multiple endpoints for fleet runs (comma-separated)

### Backtest Queue (Crash-safe)

- Enqueuing runs persists to the database (`backtest_jobs` table). A background worker claims queued jobs and updates job status (`queued|running|succeeded|failed`).
- Job events are recorded to `backtest_job_events` for auditing.

### Notes

- These commands print machine-friendly outputs (`ok`, `details`, `error`) for automated parsing.
- The Tools package does not expose any critical write operations beyond SC result ingestion and standard registry updates.


