# ChatGPT Review Prompt — RS Correction Lens + Daily Scan + Cloud Daily + Weekly

**Paste this entire file into ChatGPT and attach:** `rs_correction_daily_scan_chatgpt_YYYYMMDD.zip`

No prior chat context required.

---

## Your role

You are an **independent QA / research reviewer** for a Vietnam equities operator stack. Validate:

1. **RS Correction Lens v1.0** — anchor detection, RS definitions, VIN handling, universe coverage
2. **Integration** — `daily_scan.md`, `cloud_daily_report`, `weekly_report.md`, Phase36 CSV columns
3. **Safety** — lens does **not** change `final_action`, OMS, or capital rules
4. **Alpha workflow** — whether RS + Phase36 + Distribution Risk compose a coherent post-correction leader filter

**Do not** recommend changing `final_action`, A3/S3 rules, OMS, or live capital deployment without explicit operator request.

---

## Patch / delivery summary (FACTS — update from zip outputs)

| Item | Expected |
|------|----------|
| **Method version** | `rs_correction_lens_v1.0` |
| **Benchmark** | VNINDEX native (`ta_vnindex.parquet`) |
| **Stock OHLCV** | `ema_cloud/ohlcv_panel_ext2012.parquet` |
| **Universe** | `config/universe_liquid_adv50_2b.txt` (~272 symbols) |
| **Anchor** | Auto peak in 60-bar lookback, or `config/rs_correction_anchor.txt` override |
| **RS definition** | `rs_pct` = stock return − VNINDEX return (anchor close → end close) |
| **RS improving** | `rs20_end > rs20_anchor + 1pp` |
| **Safety invariant** | RS lens is **market context only** — does **not** change `final_action` |

**Distribution Risk Lens** (if present in same package): unchanged safety rule — context only.

**VIN baseline:** Dual view discipline — flag VIC/VHM/VRE/VPL; VPL history &lt;252 bars; cap-weight VNINDEX may be VIN-skewed 2025–2026.

---

## Data source discipline (mandatory in your review)

When citing market data:

- **source** = FireAnt (SSOT parquet exports)
- **method** = native VNINDEX + stock panel merge; RS is **derived**
- **symbols** = liquid universe file + holdings crosswalk in daily_scan
- **date range** = correction anchor date → panel end date (see `rs_correction_latest.json` → `anchor`)
- **limitations** = panel may lag `ta_ohlcv_panel` for non-universe symbols; RS is close-to-close not intraday

---

## Files in this package

| Path in zip | Role |
|-------------|------|
| `REVIEW_PROMPT.md` | This file |
| `README.txt` | How to use zip |
| `docs/research/VIN_EMA_CLOUD_BASELINE.md` | VIN / ex-VIN rules |
| `src/market/rs_correction_lens/` | Lens core (anchor + compute + pipeline) |
| `src/trading/reports/rs_correction_card.py` | Report card + scan merge |
| `src/trading/reports/distribution_risk_card.py` | Distribution risk card (if bundled) |
| `scripts/reporting/daily_scan_report.py` | `daily_scan.md` / `.json` |
| `src/trading/reports/cloud_daily_report.py` | Cloud daily report |
| `scripts/research/rs_correction_scan.py` | CLI runner |
| `config/rs_correction_anchor.txt` | Optional anchor override |
| `outputs/rs_correction_latest.json` | RS SSOT snapshot |
| `outputs/rs_correction_latest.csv` | Per-symbol RS table |
| `outputs/daily_scan.md` | Operator daily scan |
| `outputs/daily_scan.json` | Machine-readable daily scan |
| `outputs/cloud_daily_report_latest.md` | Cloud report markdown |
| `outputs/phase36_daily_scan_latest.csv` | Scan SSOT (with `rs_correction_*` columns) |
| `tests/test_rs_correction_lens.py` | Unit tests |

---

## Specific review tasks

### A. Methodology (`rs_correction_lens`)

| Check | Pass criteria |
|-------|----------------|
| Anchor detection | Peak in lookback is sensible vs operator narrative (e.g. 2026-05-15 top) |
| Override file | Documented; empty = auto |
| RS vs RS line | `rs_pct` and `rs_line_chg_pct` consistent |
| Buckets | `leader_strong` (+3%), `outperform` (+1%), `relative_flat` (≥0), `underperform` (&lt;0) |
| Improving flag | Not always true on leaders; false positives? |

### B. Integration

| Surface | Verify |
|---------|--------|
| `daily_scan.md` | Section **RS vs VNINDEX (correction leg)** after Distribution Risk; holdings table |
| `daily_scan.json` | `rs_correction_lens` summary object |
| `cloud_daily_report` | Section G includes RS card; JSON payload keys |
| `weekly_report.md` | RS section before “Signals to monitor next week” |
| Phase36 CSV | Columns `rs_correction_pct`, `rs_correction_bucket`, etc. |

### C. Alpha composition (interpretation only)

Given **defense breadth** + **distribution cluster** (if in zip):

- Do **RS leaders ∩ Phase36 NEW_T1** names form a coherent “post-correction leader” list?
- Are **BDS / energy laggards** correctly weak on RS?
- Is **bank rotation** (VCB/MSB vs CTG/STB) visible in RS tables?
- Recommend **at most 3** filter refinements (e.g. min ADV, exclude VIN-only leaders, require `rs_improving_flag`).

### D. Gaps / risks

List **P0 / P1 / P2** issues only with evidence:

- P0 = wrong anchor, stale panel, RS changes `final_action`, missing safety note
- P1 = holdings not in universe, HTML render broken, weekly missing section
- P2 = UX (table width), extra thresholds (2/4/6% RS buckets), sector column merge

---

## Output format (your reply)

```markdown
## Verdict
[APPROVE / APPROVE WITH CHANGES / NEEDS REWORK]

## Scores (1–5)
- RS methodology: 
- Daily scan integration: 
- Cloud/weekly integration: 
- Alpha workflow usefulness: 

## P0 / P1 / P2 findings
...

## RS leader shortlist (from zip data)
Top 5 names you'd monitor for next leg + 1-line why each

## Suggested operator filter (one paragraph)
...

## Tests / commands to re-run
...
```

---

## Commands (operator regenerate)

```powershell
cd "D:\V\0. VN Agent System"
.\.venv\Scripts\python.exe scripts\research\rs_correction_scan.py
.\.venv\Scripts\python.exe scripts\reporting\daily_scan_report.py
.\.venv\Scripts\python.exe -m src.trading.cli cloud-daily-report
.\.venv\Scripts\python.exe -m src.report.weekly --render
.\.venv\Scripts\python.exe -m scripts.reporting.build_rs_correction_daily_scan_chatgpt_zip
```

---

## Questions for ChatGPT to answer explicitly

1. Is auto anchor detection stable when VNINDEX rebounds to prior peak (anchor reset behavior)?
2. Should `rs_correction_*` columns affect `a3_rank_score`? (Expected answer: **no** — display/context only.)
3. What is the minimum extra field to add for sector-aware RS rotation view?
4. Any duplication vs Distribution Risk Lens that should be merged in UI?

---

_End of prompt._
