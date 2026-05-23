# Return Handover — Claude Code → ChatGPT (Institutional Accumulation Scan)

**Operator:** Copy this filled document back into the **same ChatGPT thread** from Stage 1, together with any new files listed below.

**As-of scan date:** `2026-05-21`  
**Claude review date:** `2026-05-21`  
**Repo path reviewed:** `D:\V\0. VN Agent System` (local CSV scan + April 2026 fund priors)

---

## 1. Executive summary (≤10 sentences)

**FACTS:**

- Scan rows scored: **1562** (1564 liquid universe − 2 ETF/open-fund excluded)  
- Tier1 / Tier2 / Tier3 / Reject: **0 / 18 / 33 / 1511**  
- Emerging candidates: **28**  
- Tests: **17 passed / 0 failed** (`test_institutional_accumulation_scan.py`); operator layer **+4 passed** separately  
- Execution leakage check: **ok** (`execution_leakage_check.issues=[]`)

**INTERPRETATION:**

- Overall methodology health: **sound for v1.1 research use** on this as-of.  
- Biggest gap vs v1.1 contract: **sector Unknown labels** (13/51 top-tier) and **zero Tier 1** under fragile regime (expected, not a bug).  
- VHM/VIC **do not** have `vingroup_distortion_flag` on 2026-05-21 — P1-c is N/A; caution via **risk penalty** only.

---

## 2. Stage 2 verdict (fresh-eyes code review)

| Check | PASS / FAIL | Evidence (file:line or output path) |
|-------|-------------|-------------------------------------|
| Full liquid universe default | **PASS** | `pipeline.py` universe discovery; JSON `context.universe_policy.mode=full_liquid_universe` |
| Fund context buckets (5 types) | **PASS** | `context.py:194-206`; CSV counts for 5 buckets |
| Grouped money-flow scores | **PASS** | `score_mf_*` columns; `validation.money_flow_redundancy.status=ok` |
| Emerging branch + CSV | **PASS** | 28 rows `emerging_accumulation_2026-05-21.csv`; `emerging_max_risk_penalty=30` in JSON config |
| VIN distortion + diagnosis | **PASS** (logic) | `indicators.py:183-228`; flags **0** this run; spot_checks vin_VIC/vin_VHM |
| Tier calibration (fragile regime) | **PASS** | 18 Tier2 + 33 Tier3; 0 Tier1; `FRAGILE_REGIME_LABEL` in priors |
| money_flow_redundancy validation | **PASS** | `institutional_accumulation_2026-05-21.json` validation block |
| execution_leakage_check | **PASS** | Same JSON; `validation.py:155` forbidden field scan |
| top80 + zip manifest consistency | **PASS** | `*_top80.csv` leader TCI 56.93 matches main CSV |

**Claude Deliverable A verdict:** **NEEDS_REVISION** (P1 doc/sector only — no P0)

---

## 3. Spot-check (9 symbols)

| Ticker | Tier | Score | MF | fund_context_bucket | emerging | VIN flag | Claude note |
|--------|------|------:|----:|---------------------|----------|----------|-------------|
| MBB | Reject | 23.0 | 21 | consensus_core | false | false | Core name; weak MF |
| CTG | Tier 3 | 40.9 | 50 | consensus_core | false | false | Context-led Tier 3 |
| MWG | Reject | 31.8 | 27 | consensus_core | false | false | Weak MF |
| HPG | Reject | 28.0 | 23 | consensus_core | false | false | Weak MF |
| GMD | Reject | 37.3 | 46 | consensus_core | false | false | Risk/dist elevated |
| VIC | Tier 3 | 40.4 | 56 | outside_fund_disclosure | false | false | Risk 50; flag off |
| VHM | Tier 3 | 40.5 | 48 | consensus_second_ring | false | false | Risk 50; flag off |
| VCB | Tier 3 | 39.5 | 42 | consensus_core | false | false | Context-led |
| STB | Tier 3 | 46.2 | 42 | consensus_second_ring | false | false | Top fund-backed score |

---

## 4. Weekly brief pointer

- Path: `outputs/scans/institutional_accumulation_weekly_brief_2026-05-21.md`  
- One-paragraph summary of Top 3 research actions from that brief:  
  1) Forensic Tier 2 emerging leaders (TCI, DRI, HHP, VPI).  
  2) Bank flow repair watch on consensus names (MBB/MWG/CTG).  
  3) Reconcile VIC/VHM caution-proxy vs absent distortion flags.

---

## 5. Consolidated patch backlog (for ChatGPT → Cursor)

### P0 (must fix before next scan release)

_None identified._

### P1 (should fix)

| ID | File(s) | Change | Rationale |
|----|---------|--------|-----------|
| P1-1 | `validate_institutional_accumulation_package.py` | Document `vhm_p1c_check_status`; stop over-reading `vhm_daily_cmf_missing` | Integrity JSON clarity |
| P1-2 | `pipeline.py` / `load_sector_map` | Merge `data/master/sector_map.csv` fallback at scan time | 13/51 top-tier Unknown degrades sector stats |
| P1-3 | `build_institutional_accumulation_scan_chatgpt_zip.py` | Exclude or refresh April-only comparison markdowns | Review reproducibility |
| P1-4 | `CHATGPT_*_REVIEW_PROMPT.md` | Keep conditional P1-c wording (done) | Matches May 21 outputs |

### P2 (nice to have)

| ID | File(s) | Change | Rationale |
|----|---------|--------|-----------|
| P2-1 | `tests/` | Add `test_diff_excludes_top80_previous` | Prevent WoW noise regression |
| P2-2 | Review zip | Ship `test_institutional_accumulation_operator.py` | 21 tests total disclosure |
| P2-3 | `operator_summary.py` | Auto-sync weekly brief from payload | Avoid stale `weekly_brief_*.md` |

---

## 6. Disagreements / additions vs ChatGPT Stage 1

| Topic | ChatGPT QA note | Claude view | Resolution |
|-------|-----------------|-------------|------------|
| `vhm_daily_cmf_missing: true` in integrity | Misleading vs CSV | Agree — use `vhm_p1c_check_status=not_applicable_flag_off` | Validator updated; ChatGPT was right |
| VHM diagnosis required this run | Conditional on flag | **Disagree** for flat requirement — flag off, CMF present | Prompt P1-c is conditional only |
| Package PASS WITH FIXES | Reviewable | Agree — proceed to methodology review | Align Stage 5 |
| Stale `PACKAGE_INTEGRITY_AUDIT` in zip | P1 | Refreshed in latest zip build | Operator should re-upload zip if old attachment |

---

## 7. Files produced by Claude Code

| Path | Description |
|------|-------------|
| `outputs/scans/institutional_accumulation_claude_review_2026-05-21.md` | Deliverable A — technical QA |
| `outputs/scans/institutional_accumulation_weekly_brief_2026-05-21.md` | Deliverable B — weekly-style research brief |
| `outputs/review_packages/RETURN_HANDOVER_TO_CHATGPT.md` | Deliverable C — this file |

**Optional zip:**

```powershell
python -m scripts.reporting.build_institutional_accumulation_claude_return_zip --as-of 2026-05-21
```

---

## 8. Instructions for ChatGPT (Stage 5)

ChatGPT should:

1. Reconcile Stage 1 + this handover  
2. De-duplicate P0/P1 items (expect **empty P0**)  
3. Produce final **`CURSOR_IMPLEMENTATION_PROMPT`** block (methodology-only; explicit file paths; acceptance tests)  
4. Explicitly state: **no execution/OMS/final_action changes**  
5. Treat **2026-05-21 market + April 2026 fund** as the frozen package contract

---

*End of handover template.*
