# Operating Manual — VN Agent System

## Non-negotiables

- **Facts-first.** Separate FACTS vs INTERPRETATION.
- **No hallucination:** If data is missing, say "Unknown" and list what would confirm/deny.
- **Always end weekly report with:**
  1. Signals to monitor next week
  2. If X happens → do Y

## Framework tags

- **Buffett/Munger:** moat, ROIC, capital allocation, debt discipline
- **Minervini/O'Neil/Morales:** trend, base, volume, risk control

## Output style

- Bullet-heavy, quantified when possible.
- Use Vietnam context and transmission channels: rates, credit, fiscal, FX, sentiment.

## Output Format Rules

Weekly report **MUST** include (in this order):

- **Global Macro + Fed:** what changed, what matters, what to watch next
- **Vietnam Policy:** new laws/resolutions/circulars + transmission map
- **Sectors & Companies:** earnings/broker notes + catalysts/risks
- **Decision layer:** Top 3 actions, Top 3 risks, Watchlist updates
- **End with:**
  - Signals to monitor next week
  - If X happens → do Y

## Core inputs (MVP — 8 số tối thiểu)

Pareto 20% data → 80% quyết định. Điền trong `data/raw/manual_inputs.json`:
- **Global (3):** ust_2y, ust_10y, dxy
- **Vietnam (3):** omo_net, interbank_on, credit_growth_yoy
- **Market (2):** vnindex_level, distribution_days_rolling_20

Chi tiết: `docs/runbook.md`.

## Environment (FRED key checklist)

Global macro (UST 2Y/10Y, DXY) is auto-filled from FRED when `FRED_API_KEY` is set.

1. **Get key:** https://fred.stlouisfed.org/docs/api/api_key.html (free, ~2 min).
2. **Windows (PowerShell):**  
   `$env:FRED_API_KEY = "your_key_here"` (session) or `setx FRED_API_KEY "your_key_here"` (persistent).  
   Open a new terminal after `setx`.
3. **Verify:**  
   `echo $env:FRED_API_KEY`  
   Then run `python -m src.report.weekly`; UST 2Y/10Y and DXY in the report should show numbers if the key works.
4. **Optional:** Copy `.env.example` to `.env`, add `FRED_API_KEY=...`. If you use `python-dotenv`, load `.env` in code; otherwise rely on system env.

## Watchlist (editable)

Edit `config/watchlist.txt` to change symbols. Current default:

SSI, VCI, SHS, TCX, MBB, STB, SHB, DCM, PVD, PC1, DXG, VSC, GMD, MWG

---

## Workflow v2.0 — End-to-end audit

### Layers / modules

| Layer | Module / path | Role |
|-------|----------------|------|
| Intake (market) | `src/intake/auto_inputs_fireant.py` | Pull VN30/HNX/UPCOM level+volume; distribution days LB=25 refined; MA20 trend; breadth |
| Intake (global) | `src/intake/auto_inputs_global.py`, `src/intake/fred_api.py` | UST 2Y/10Y, DXY when `FRED_API_KEY` set |
| Regime | `src/regime/state_machine.py` | LiquiditySignals, detect_regime |
| Risk | `src/exec/market_risk.py` | risk_flag (Normal/Elevated/High), dist_risk_composite |
| Allocation | `src/alloc/engine.py`, `src/alloc/overrides.py`, `src/alloc/core_gate.py`, `src/alloc/bucket_allocation.py` | Regime allocation, risk overrides, core allowed, buckets |
| Sell | `src/exec/sell_rules.py` | Evaluate sell/trim from `data/raw/tech_status.json` |
| Daily | `src/report/daily.py` | Snapshot: risk flag, overrides, core, bucket, sell signals |
| Weekly | `src/report/weekly.py` | Full report + archive to `data/history/YYYY-MM-DD/` |
| Intake (docs) | `src/ingest/run.py` | Inbox → sources + summaries; update weekly_notes (optional) |

### Automated vs manual — precise table

| Category | Source / module | Where stored | Notes |
|----------|-----------------|--------------|--------|
| **Automated inputs** | FireAnt (VN30, HNX, UPCOM) | Filled into `data/raw/manual_inputs.json` (non-destructive merge) | `build_auto_inputs()` in `auto_inputs_fireant.py` |
| | Distribution days (LB=25 refined) | `inputs["market"]["distribution_days"]`, `dist_risk_composite`, `dist_proxy_symbol` | `src/features/distribution_days.py` |
| | MA20 trend flags | `inputs["market"]["vn30_trend_ok"]`, `hnx_trend_ok`, `upcom_trend_ok` | Same intake |
| | UST 2Y/10Y, DXY | `inputs["global"]` | `build_auto_global()` when `FRED_API_KEY` set |
| **Manual inputs** | `data/raw/manual_inputs.json` | `asof_date`, `global` (ust_2y, ust_10y, dxy), `vietnam` (omo_net, interbank_on, credit_growth_yoy), `market` (overrides), `overrides` (global_liquidity, vn_liquidity) | See runbook.md — 8 core numbers |
| | `data/raw/weekly_notes.json` | `policy_facts`, `earnings_facts`, `broker_notes` | Policy/earnings/broker narrative |
| | `data/raw/tech_status.json` | Per-ticker tech state | For sell_rules; optional AmiBroker/PP export |
| **Outputs (daily)** | `data/decision/daily_snapshot.md` | Human-readable snapshot | |
| | `data/alerts/market_flags.json` | risk_flag, dist days, proxy | |
| | `data/alerts/sell_signals.json` | Sell/trim signals | |
| | `data/decision/allocation_plan.json` | Regime, allocation, overrides | |
| **Outputs (weekly)** | `data/decision/weekly_report.md` | Full packet | |
| | `data/state/regime_state.json` | asof_date, regime, shift | |
| | `data/decision/allocation_plan.json` | Same as daily (updated) | |
| | `data/features/core_features.json` | WoW deltas, features | |
| | `data/history/YYYY-MM-DD/*` | Copy of weekly_report.md, regime_state.json, allocation_plan.json, core_features.json, market_flags.json, sell_signals.json | Archive by asof_date |

### Runbook

- **Daily:** `make daily` or `python -m src.report.daily`. No manual numbers required if FireAnt + (optional) FRED key are set. Check: `data/decision/daily_snapshot.md`, `data/alerts/market_flags.json`.
- **Weekly:** Before `make weekly`: (1) Optionally drop files into `data/intake/inbox/` and run `make ingest`; (2) Fill VN liquidity (OMO/ON/credit) and policy/earnings in `data/raw/weekly_notes.json` or keep "Unknown"; (3) Run `make weekly` or `python -m src.report.weekly`. Archive is written to `data/history/<asof_date>/`.
- **Archive:** Each weekly run copies `weekly_report.md`, `regime_state.json`, `allocation_plan.json`, `core_features.json`, `market_flags.json`, `sell_signals.json` into `data/history/<asof_date>/`.
- **Decision audit log:** Each weekly run writes `decision_log/<asof_date>.json` with regime, suggested_regime, risk_flag, gross_cap, new_buys_allowed, composite_dist, and portfolio_health metrics. Use for later behavior audit (e.g. 3 months on).

### Debugging common failures

| Failure | Check | Fix |
|---------|--------|-----|
| Missing env vars | `FRED_API_KEY` for UST/DXY | Set in shell or `.env`; see Environment section above |
| API errors (FireAnt) | Logs from `build_auto_inputs`; cache in `data/cache/fireant/` | Network, rate limit, or symbol list in `auto_inputs_fireant.py` |
| Missing data | `manual_inputs.json` has null for core 8 | Fill manually or ensure FRED key for global; FireAnt for market |
| Regime always B or wrong | `overrides.global_liquidity` / `vn_liquidity` in manual_inputs | Set explicitly if engine not inferring |
| No sell signals | `data/raw/tech_status.json` missing or empty | Populate from AmiBroker/PP or leave empty |

### Intake pipeline (research docs)

- **Input:** Drop files into `data/intake/inbox/` and list them in `data/intake/inbox/manifest.json` (see `manifest.json.example`). Each entry: `filename`, `type` (macro_report | sector_report | company_report | policy_report), `date`, `tags`, and optionally `source`, `sector`, `ticker`.
- **Command:** `make ingest` or `python -m src.ingest.run`.
- **Behaviour:** For each entry: validate file exists; extract text (PDF/DOCX/XLSX/TXT); move file to `data/sources/{macro|policy|sector|company}/YYYY-MM/`; write markdown summary to `data/summaries/{same}/`; append takeaways to `data/raw/weekly_notes.json` (key `intake_takeaways`); move file from inbox to `data/intake/processed/`. If parse fails, file goes to `data/intake/rejected/` and a `_parse_failed.md` note is written; pipeline does not crash.
- **When:** Run before `make weekly` (e.g. Friday or weekend) so weekly report can use updated notes.

### Gaps / TODO

- Regime label: still manual or engine default (no full auto from macro only).
- Vietnam liquidity (OMO/ON/credit): manual by design.
- Policy facts / earnings: manual or from intake pipeline (`make ingest`); doc-ingest summarizer fills weekly_notes when used.
- AmiBroker/PP sell signals: optional; if not ported to Python, keep exporting CSV → tech_status.
- Optional: cache setup_quality per symbol for faster backtest re-runs.
