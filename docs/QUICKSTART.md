# Quick start — VN Agent System (10 steps)

1. **Clone / open repo** and ensure Python 3.10+ and venv (e.g. `.venv`) are ready.
2. **Install deps:** `pip install -r requirements.txt`
3. **Core config:** Ensure `data/raw/manual_inputs.json` exists with at least `asof_date`; optional: set `FRED_API_KEY` for UST 2Y/10Y and DXY auto-fill.
4. **Daily run:** `make daily` (or `python -m src.report.daily`) — pulls market data from FireAnt, computes risk flag and allocation overrides, writes `data/decision/daily_snapshot.md` and `data/alerts/market_flags.json`.
5. **Weekly prep:** Fill VN liquidity (OMO net, interbank ON, credit growth YoY) and policy/earnings in `data/raw/weekly_notes.json` if you have them; otherwise leave "Unknown".
6. **Optional — ingest research:** Drop PDF/Word/Excel into `data/intake/inbox/`, add entries to `data/intake/inbox/manifest.json`, then run `make ingest` to move files, generate summaries, and update notes.
7. **Weekly run:** `make weekly` (or `python -m src.report.weekly`) — produces `data/decision/weekly_report.md`, updates `data/state/regime_state.json` and `data/decision/allocation_plan.json`, and archives to `data/history/<asof_date>/`.
8. **Check outputs:** Open `data/decision/weekly_report.md`; confirm regime and allocation in `data/decision/allocation_plan.json` and `data/alerts/market_flags.json`.
9. **Roll week (optional):** Before next week, run `make roll` to copy current `manual_inputs.json` → `manual_inputs_prev.json` and `weekly_notes.json` → `weekly_notes_prev.json`.
10. **Watchlist:** Edit `config/watchlist.txt` or `data/raw/watchlist.json` for symbols; weekly report uses it for decision layer and backtest knowledge.

For full runbook and troubleshooting, see `docs/OPERATING_MANUAL.md` and `docs/runbook.md`.
