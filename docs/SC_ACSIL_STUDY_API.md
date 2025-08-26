## ACSIL Backtest Control Study: Command API (expected)

This describes the JSON-lines IPC protocol the Sierra ACSIL study should implement. Each command/response is a single JSON object per line over TCP.

General:
- Each command includes `id` (string), `type` (command name), and optional payload.
- Responses include the same `id` and a `type` field indicating the response/event name.

Commands

- PING
  - Request: `{ "id": "...", "type": "PING" }`
  - Response: `{ "id": "...", "type": "PING", "ok": true }`

- GET_STATUS
  - Request: `{ "id": "...", "type": "GET_STATUS" }`
  - Response: `{ "id": "...", "type": "GET_STATUS", "replay_status": "stopped|running|paused", "ready": true }`

- LOAD_CHART
  - Request: `{ "id": "...", "type": "LOAD_CHART", "symbol": "ESZ4", "timeframe": "1m", "session": null, "study_params": {"thresh": 0.1} }`
  - Response: `{ "id": "...", "type": "LOAD_CHART", "ok": true, "chart_id": 5 }`

- WAIT_READY
  - Request: `{ "id": "...", "type": "WAIT_READY" }`
  - Response: `{ "id": "...", "type": "WAIT_READY", "ready": true }`

- SET_REPLAY_MODE
  - Request: `{ "id": "...", "type": "SET_REPLAY_MODE", "accurate": true, "all_charts": true }`
  - Response: `{ "id": "...", "type": "SET_REPLAY_MODE", "ok": true }`

- SET_DATES
  - Request: `{ "id": "...", "type": "SET_DATES", "start": "2025-01-01T09:30:00", "end": "2025-01-01T16:00:00" }`
  - Response: `{ "id": "...", "type": "SET_DATES", "ok": true }`

- START_REPLAY
  - Request: `{ "id": "...", "type": "START_REPLAY", "speed": 1 }`
  - Response: `{ "id": "...", "type": "START_REPLAY", "ok": true }`

- STOP_REPLAY
  - Request: `{ "id": "...", "type": "STOP_REPLAY" }`
  - Response: `{ "id": "...", "type": "STOP_REPLAY", "ok": true }`

- ENABLE_AUTOTRADE
  - Request: `{ "id": "...", "type": "ENABLE_AUTOTRADE", "chart_id": null, "on": true }`
  - Response: `{ "id": "...", "type": "ENABLE_AUTOTRADE", "ok": true }`

- GET_RESULTS
  - Request: `{ "id": "...", "type": "GET_RESULTS" }`
  - Response: `{ "id": "...", "type": "GET_RESULTS", "metrics": {"sharpe": 1.2, "net_pnl": 1250.0}, "fills": [ ... ], "equity": [ ... ], "result_path": "C:\\SierraChart\\Data\\run_123_20250101_163000.json" }`

- RESET_STATS
  - Request: `{ "id": "...", "type": "RESET_STATS" }`
  - Response: `{ "id": "...", "type": "RESET_STATS", "ok": true }`

Events (optional)

- `{ "type": "PROGRESS", "job_id": 42, "bar_ts": "2025-01-01T10:15:00", "replay_status": "running", "equity": 10325.0 }`
- `{ "type": "FILL", "ts": 1700000000.0, "side": "buy", "price": 5000.25, "qty": 1 }`


