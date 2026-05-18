# Weekly Report ↔ Production Strategy Sync (SSOT plan)

**Status:** design / handoff (not fully implemented)  
**Owner intent:** Weekly HTML command center should reflect the **same truths** as the live/paper trading path: **A3_DP / B_cloud20_100** (EMA 20/100 cloud), with room to add **B_cloud21_55**, **C_GK_regime**, etc. after validation — without forking signal logic inside the report.

---

## Current production strategy (frozen)

| Item | Value |
|------|--------|
| Production classification | `A3_PRODUCTION` in phase36 scan |
| Research / book label | `B_cloud20_100` |
| Cloud | EMA **20** (fast) / **100** (slow); bull = fast > slow and close above cloud |
| Universe | ex-VIN3 (`in_a3_universe`); VPL excluded if &lt;252 bars |
| Signal SSOT | phase36 CSV — `final_action`, exit prices, breadth permissions |
| OMS | Adapter only — **no** EMA recompute in order path |
| Capital | **NO-GO** (paper/dry-run only) — see `docs/trading/REAL_CAPITAL_READINESS.md` |

Secondary (research / shadow only): `B_cloud21_55` (S3), `C_GK_regime` — show in report **labeled research**, not mixed into production command center without explicit toggle.

---

## What the weekly report uses today

| Block | Source today | Strategy-aligned? |
|-------|----------------|-------------------|
| Command center regime | `regime_engine` (STATE A–E) | Partial — council macro regime, not cloud `regime_bull` |
| Gross / cash | `allocation_plan` / probability_allocation | Yes — same band rules as council |
| Execution actions | `sell_signals.json` + `tech_status.json` | **Gap** — not scan `final_action` / trail / TP1 |
| Watchlist | Latest `phase36*daily_scan*.csv` | **Partial** — all rows; no `active_strategy` filter |
| Position prices | FQuery derive + optional FireAnt close | OK for P/L; stops from tech_status often stale |
| WoW macro | `manual_inputs` vs `manual_inputs_prev` | OK (orthogonal to strategy) |
| Downtrend v2 | `vnindex_downtrend_probability_v2.json` | OK overlay |

---

## Target architecture (single enrich pass)

Add to `scripts/ingest/portfolio_decision_enrich.py` (or sibling `strategy_scan_join.py`):

### 1. Config SSOT

```yaml
# config/weekly_report_strategy.yaml (proposed)
active_production_strategy: B_cloud20_100
production_classification: A3_PRODUCTION
scan_path_override: null   # null → resolver latest phase36
research_strategies:
  - B_cloud21_55
  - C_GK_regime
show_research_watchlist: false
```

### 2. Scan join on holdings

For each ticker in `current_positions_derived.json`:

- Left-join phase36 row on `symbol`  
- Attach: `final_action`, `final_action_reason`, `strategy_classification`, `tp1_price`, `trail_price`, `pb_trigger_price`, `a3_cloud_bull`, `breadth_zone`, `a3_rank_score` (sort only), `ed_score`, `a3_ema_dist_pct`  
- **Technical status** derived from scan when present: e.g. `TRAIL_EXIT` → “Stop breach”, `NEW_T1*` → “Leader / Constructive”, `WAIT_PB` → “Pullback normal”  
- **Next trigger** from scan columns (not invented): e.g. “Add above pb_trigger with volume”, “Exit if close &lt; trail_price”

### 3. Watchlist board

- Filter: `strategy_classification == A3_PRODUCTION` (when production mode)  
- Buckets map from `final_action`:

| final_action pattern | Bucket |
|---------------------|--------|
| NEW_T1*, full_T1 | Buy Now Candidate |
| WAIT_PB | Buy on Pullback |
| (reclaim rules TBD from scan) | Buy on Reclaim |
| HOLD*, ADD_T2 | Hold / Monitor |
| TRAIL_EXIT, MAX_HOLD_EXIT, SKIP*, WATCH_ONLY | Avoid / Remove |

- Sort: `a3_rank_score` desc (display only — does not change trading logic)

### 4. Command center additions

Keep council STATE A–E band rules. Add read-only strip:

- `VNINDEX cloud (20/100):` `regime_bull` from scan panel row or index aggregate  
- `A3 universe % bull cloud:` `pct_cloud_bull_a3` + `breadth_zone`  
- Caveat string from `VIN_EMA_CLOUD_BASELINE.md` when citing VNINDEX  

### 5. Regime rules display

Option A (minimal): keep A–E table; footnote “Cloud regime may differ — see strip above”.  
Option B: add row source column “Council” vs “Cloud (VNINDEX 20/100)”.

Do **not** auto-merge STATE B with cloud bear without owner-approved mapping table.

### 6. Multi-strategy future

When `B_cloud21_55` graduates from research:

- Add `strategy_book` on each position in derive step  
- Command center `active_strategy` selector in config only (no HTML hard-code)  
- Separate watchlist sections per strategy OR filter toggle  

---

## Files to touch (implementation checklist)

| File | Change |
|------|--------|
| `config/weekly_report_strategy.yaml` | New — active strategy + scan resolver hints |
| `scripts/ingest/portfolio_decision_enrich.py` | Scan join; filter watchlist; cloud strip |
| `src/trading/live/scan_resolver.py` | Reuse resolver from weekly enrich (import, don’t duplicate) |
| `templates/weekly_report.html.j2` | Cloud strip UI; strategy column in execution |
| `data/raw/current_positions_derived.json` | Optional `strategy_book` field from ledger |
| `tests/test_portfolio_command_center_report.py` | Scan join fixture; A3_PRODUCTION-only watchlist |

---

## Non-goals

- Recomputing EMA clouds inside the report pipeline  
- Changing `final_action` logic or risk engine  
- Presenting S3 shadow fills as production actions without label  

---

## Verification after sync

1. MWG (or any forced exit) shows same action in report as scan/ledger  
2. Watchlist count matches operator dashboard for `A3_PRODUCTION` only  
3. `trail_price` / `tp1_price` in execution table match scan CSV for open positions  
4. Turning `active_production_strategy` to a research-only id empties production watchlist with explicit message  
