# Intraday A3/S3 Preview Scan — Full Review Prompt (VN Agent System v3.1)

**Paste this entire document into the other AI session.**  
Attach or extract the intraday review zip from `outputs/review_packages/` (build via `scripts/trading/build_ai_auto_trading_setup_review_package.py`).

---

## 1. Your role

You are an independent reviewer for the **VN Agent System intraday preview scan** (Vietnam equities, FireAnt data). The operator runs this **before lunch** and **before ATC** to see *“if today closed now, what would Phase36 say?”*

You must **not** assume production orders come from intraday output. EOD daily scan is SSOT for OMS.

**Deliverable from you:**

1. **VERDICT:** `APPROVED_FOR_OPERATOR_PREVIEW` | `NEEDS_FIXES` | `BLOCKED`
2. **P0/P1 issues** (if any) with file + function references
3. **Operator-safety check** (can a human mistakenly route intraday CSV to live orders?)
4. Confirm **27/27 tests** logic (or run if you have the zip + Python env)

---

## 2. System purpose (FACTS)

| Layer | What it does |
|-------|----------------|
| **EOD SSOT** | `python pp_backtest/portfolio_optimization_final_steps.py --step scan` → `phase36_daily_scan_sample.csv` |
| **Intraday preview** | `python -m src.trading.cli intraday-scan --mode pre-lunch\|pre-atc\|ad-hoc` |
| **Data** | FireAnt REST `GET /symbols/{symbol}/historical-quotes?startDate={today}&endDate={today}` (partial daily OHLCV) |
| **VNINDEX** | Same endpoint, symbol `VNINDEX`; in-memory overlay on `vnx` (no parquet write) |
| **Equity panel** | In-memory overlay on `ohlcv_panel_ext2012.parquet` (no write) |
| **Engine** | `compute_phase36_scan_df(..., intraday_macro=True)` — same A3/S3 rules as EOD, live breadth |
| **Policy layer** | Sets `would_be_final_action` = engine result; `final_action` = `INTRADAY_PREVIEW`; gates manual review |

**S3:** Paper-shadow only; `s3_no_real_order_flag` must stay True. No change to S3 production logic requested.

---

## 3. Hard constraints (non-negotiable)

1. **Do not** change A3 `final_action` production rules, T1/T2 sizing, or exits for EOD path.
2. **Do not** write intraday bars to `data/research/ema_cloud/ohlcv_panel_ext2012.parquet` or `data/fireant_ssot/ta_vnindex.parquet`.
3. **Do not** allow OMS / `build-intents` to consume intraday CSV (`scan_resolver._is_intraday_preview()`).
4. **`auto_order_allowed=False`** on every row, always.
5. **`final_action=INTRADAY_PREVIEW`** for actionable preview rows (not EOD actions).
6. Tradeable preview field is **`would_be_final_action`** (IF_CLOSE_NOW semantics).

---

## 4. Architecture (read in zip)

```
FireAnt partial daily (equities + VNINDEX)
  → data_adapter.py (quotes, capability probe)
  → panel_overlay.py (provisional today bar, no parquet write)
  → vnindex_overlay.py (VNINDEX in-memory, regime compare fix)
  → compute_phase36_scan_df(intraday_macro=True)  [portfolio_optimization_final_steps.py]
  → intraday_scan._apply_intraday_policy()
  → report.py (MD + HTML)
  → data/research/intraday/phase36_intraday_scan_*.{csv,md,html,meta.json}
```

**Key files in zip:**

| Path | Role |
|------|------|
| `bundle/src/trading/intraday/intraday_scan.py` | Orchestrator, policy, meta, `_write_outputs` |
| `bundle/src/trading/intraday/vnindex_overlay.py` | VNINDEX overlay + `vnindex_regime_changed` |
| `bundle/src/trading/intraday/report.py` | Operator MD/HTML |
| `bundle/src/trading/intraday/data_adapter.py` | FireAnt fetch |
| `bundle/src/trading/live/scan_resolver.py` | OMS guard |
| `bundle/tests/test_intraday_scan.py` | 27 unit tests |
| `bundle/configs/intraday_scan.yaml` | Session times, holdings_path |
| `bundle/patches/final_steps_compute_phase36_scan_df.md` | EOD refactor note |
| `bundle/samples/*` | Latest run artifacts |

---

## 5. v3 / v3.1 policy (verify in code)

### 5.1 Unquoted symbols

If a scan row’s symbol has **no** valid intraday equity quote:

| Field | Required value |
|-------|----------------|
| `intraday_data_quality` | `MISSING_INTRADAY_QUOTE` |
| `intraday_action_status` | `STALE_DATA_NO_ACTION` |
| `manual_review_required` | `False` |
| `intraday_candidate` | `False` |
| `auto_order_allowed` | `False` |

**Bug that was fixed:** Unquoted rows used EOD prices but could still get `MANUAL_REVIEW_REQUIRED` during active session.

### 5.2 Quote coverage meta

Must appear in `*_meta.json` and report section A:

- `intraday_quote_coverage_pct` = `quoted_symbols_count / len(symbols_requested)`
- `quoted_symbols_count`
- `scan_symbols_count`
- `missing_quote_count` = \|scan_symbols − quoted\|
- `breadth_source`:
  - `live_panel_full_intraday` — all scan symbols quoted
  - `mixed_intraday_eod_panel` — partial quotes (typical: 14 holdings quoted, ~95 scan rows)
  - `eod_fallback` — no equity quotes

### 5.3 VNINDEX regime warning

`vnindex_regime_changed` must compare **EOD regime at target date** vs **newly computed** `intraday_regime_bull`, not `meta["vnindex_intraday_regime_bull"]` before it was set (was `None` → false positive).

### 5.4 Latest outputs on failure

On `SOURCE_UNAVAILABLE` or `NO_VALID_QUOTES`, must still overwrite:

- `phase36_intraday_scan_latest.csv` (empty or header-only)
- `phase36_intraday_scan_latest.md`
- `phase36_intraday_scan_latest.html`
- `phase36_intraday_scan_latest_meta.json`

No stale prior-run rows.

### 5.5 HTML dashboard

If `session_phase` ∈ `{LUNCH_BREAK, CLOSED}` **or** no rows with `intraday_candidate=True`:

- Show **"No manual-review candidates"**
- Do **not** fall back to `scan_df.head(40)` as “top candidates”

### 5.6 Holdings

- Default `holdings_path: data/trading/holdings.txt` in yaml
- Report must state path and warn if file missing
- Holdings overlap section (report F) only when file exists

### 5.7 Explicit `--symbols`

When CLI passes explicit symbols, output is filtered to that set only.

---

## 6. Sample run snapshot (FACTS — bundled `samples/`)

From latest ad-hoc run (2026-05-18 ~17:34 +07, market closed):

| Meta field | Value |
|------------|--------|
| `status` | OK |
| `session_phase` | CLOSED |
| `symbols_requested` | 14 (portfolio holdings) |
| `quoted_symbols_count` | 14 |
| `scan_symbols_count` | 95 |
| `missing_quote_count` | 85 |
| `intraday_quote_coverage_pct` | 100% (of requested) |
| `breadth_source` | mixed_intraday_eod_panel |
| `breadth_zone` | defense (~32%) |
| `vnindex_regime_changed` | false |
| `holdings_file_exists` | true |

**Interpretation:** All **holdings** get intraday quotes; full **scan universe** still includes many EOD-only names → most rows correctly `MISSING_INTRADAY_QUOTE` / no manual review.

---

## 7. Commands to reproduce

```bash
cd "D:/V/0. VN Agent System"   # or unzip path
export FIREANT_TOKEN=<jwt>      # required for live run

python -m pytest tests/test_intraday_scan.py -q
# Expected: 27 passed

python -m src.trading.cli intraday-scan --mode pre-lunch
python -m src.trading.cli intraday-scan --mode pre-atc
python scripts/research/fireant_intraday_probe.py --symbols STB,BID,VPB
```

EOD (unchanged):

```bash
python pp_backtest/portfolio_optimization_final_steps.py --step scan
```

---

## 8. Test matrix (27 tests in `bundle/tests/test_intraday_scan.py`)

| Test | What it proves |
|------|----------------|
| capability discovery | FireAnt probe structure |
| validate missing/stale quotes | data_adapter |
| panel overlay no write | EOD parquet mtime unchanged |
| provisional close | last_price used |
| volume projection lunch/early | session.py |
| intraday policy flags | INTRADAY_PREVIEW, auto_order false |
| manual review on NEW_T1 | quoted symbol only |
| S3 paper flag preserved | s3_no_real_order_flag |
| source unavailable policy | SOURCE_UNAVAILABLE status |
| output filename timestamp | stamped CSV |
| vnindex overlay no parquet write | ta_vnindex untouched |
| intraday_macro flag exists | compute_phase36_scan_df signature |
| OMS blocks intraday path | scan_resolver |
| unquoted ≠ manual review | **P0 fix** |
| explicit symbols filter | **P0 fix** |
| vnindex True/True no warning | **P1 fix** |
| failure overwrites latest | **P1 fix** |
| lunch HTML no fake table | **P1 fix** |
| mixed breadth source | breadth_source enum |
| attach quote coverage meta | v3.1 counts |
| failure meta has counts | v3.1 |
| holdings missing warning | v3.1 |
| final_action always preview | acceptance |

---

## 9. Review checklist (tick each)

### Safety
- [ ] OMS cannot resolve intraday CSV for order intents
- [ ] `auto_order_allowed` never True
- [ ] Report/HTML says PREVIEW ONLY prominently

### Policy
- [ ] Unquoted symbol cannot be `intraday_candidate=True`
- [ ] Stale / SOURCE_UNAVAILABLE / OUT_OF_SESSION paths correct
- [ ] `would_be_final_action` preserved separately from `final_action`

### Data integrity
- [ ] No EOD parquet writes from intraday code paths
- [ ] Proxy/disclosure: partial daily bar, not tick-by-tick
- [ ] VNINDEX overlay does not write `ta_vnindex.parquet`

### Meta / reporting
- [ ] Coverage counts present
- [ ] `breadth_source` logic matches quoted vs scan sets
- [ ] Failure clears `*_latest.*`
- [ ] Holdings path + missing-file warning

### Regression
- [ ] EOD `run_scan()` still uses `intraday_macro=False` by default
- [ ] A3 production logic file not altered for intraday-only behavior

---

## 10. Known limitations (not bugs — document only)

1. **Macro breadth** with `mixed_intraday_eod_panel`: unquoted names still on EOD bar in panel → breadth is approximate.
2. **Quote universe = watchlist/holdings** (14), not full scan (95) — by config design.
3. **No dedicated quote API** on FireAnt (404 on `/quotes`, `/quote`, `/priceboard`).
4. **Partial daily timestamp** often midnight — adapter treats as non-stale for partial bar.
5. **Full panel load** ~10–15s even for 14 symbols.

---

## 11. Optional improvements (P2 — do not block preview)

- Filter `compute_phase36_scan_df` to holdings-only panel for faster runs
- `VNINDEX_ONLY_MACRO` mode when zero equity quotes but VNINDEX OK
- Stamp `phase36_intraday_scan_latest_meta.json` on mode-specific prefix files too

---

## 12. Response format (use this structure)

```markdown
## VERDICT
APPROVED_FOR_OPERATOR_PREVIEW | NEEDS_FIXES | BLOCKED

## P0 (must fix before operator use)
- ...

## P1 (should fix)
- ...

## P2 (nice to have)
- ...

## FACTS verified from zip
- ...

## TESTS
- pytest: X passed / Y failed (or not run + reason)

## OPERATOR READINESS
One paragraph: safe for pre-lunch/pre-ATC planning? What must operator remember?
```

---

## 13. Zip manifest

See `FILE_MANIFEST.md` in the zip root.  
Primary prompt: **this file** (`INTRADAY_SCAN_REVIEW_PROMPT.md`).

**Maintainer verdict (pre-review):** `INTRADAY_SCAN_READY_FOR_PREVIEW` (v3.1) — pending your independent confirmation.
