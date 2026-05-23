# Institutional Accumulation Scan v1.1 — Claude Code Fresh-Eyes Review

**As-of:** 2026-05-21 | **Fund context:** April 2026 (`apr2026_default_priors.json`) | **Review date:** 2026-05-21  
**Sources:** `outputs/scans/institutional_accumulation_2026-05-21.{csv,json}`, `src/scans/institutional_accumulation/`, `data/smart_money/priors/apr2026_default_priors.json`

---

## 1. Executive verdict

**NEEDS_REVISION** (methodology-only; package is **reviewable**)

**FACTS**

- Scan completed: **1562** rows, `scan_date=2026-05-21`, `methodology_version=v1.1`
- Tiers: Tier 1 **0** | Tier 2 **18** | Tier 3 **33** | Reject **1511**
- Emerging: **28** (`emerging_accumulation_2026-05-21.csv` rows match)
- Tests: **17/17** passed (`test_institutional_accumulation_scan.py`); **+4** operator tests pass separately
- `execution_leakage_check.ok: true`; `money_flow_redundancy.status: ok` (max pairwise corr **0.53**)
- `universe_policy.mode: full_liquid_universe`; `n_symbols_scored: 1564` → **2** ETF/open-fund excluded → **1562** output rows

**INTERPRETATION**

- Core v1.1 contract is implemented and outputs are internally consistent for **2026-05-21**.
- No P0 methodology blockers for research use.
- P1 items are documentation/integrity clarity and sector-label degradation — not scoring logic errors.

---

## 2. Universe policy

| Check | Result | Evidence |
|-------|--------|----------|
| Full liquid universe default | **PASS** | `pipeline.py` discovers `data/stocks/*.csv`; JSON `context.universe_policy.mode=full_liquid_universe` |
| Fund lists = context only | **PASS** | `tag_symbol()` sets `fund_context_bucket`; no filter to holdings-only |
| ETF exclusion | **PASS** | `E1VFVN30` absent; `etf_exclusion_sectors` includes `Quỹ mở` |

---

## 3. Fund context buckets

| Bucket | Count (CSV) |
|--------|-------------|
| outside_fund_disclosure | 1539 |
| fund_commentary_mention | 10 |
| consensus_core | 6 |
| consensus_second_ring | 4 |
| selective_fund_bet | 3 |

**PASS** — Five distinct buckets in `context.py`; no `differentiated_bet` collapse.

---

## 4. Grouped money-flow

**PASS** — Columns present on all rows: `score_mf_cmf`, `score_mf_obv_pvt`, `score_mf_adl`, `score_mf_participation` → `score_money_flow`.

`validation.money_flow_redundancy`: **ok**, `high_corr_pairs: []`, threshold 0.9.

---

## 5. Emerging accumulation

**Rule (FACTS):** Tier 1–3 + `score_money_flow ≥ 48` + liquid + `has_fund_disclosure_tag=false` + `score_risk_penalty ≤ 30` (`config.emerging_max_risk_penalty`).

**PASS** — 28 emerging; **0** emerging with `risk_penalty > 30`; VIC **not** emerging.

Top by score: TCI, DRI, HHP, VPI, PIV (all Tier 2, outside_fund_disclosure).

---

## 6. Vingroup distortion

**FACTS (this as-of):**

- `vingroup_distortion_flag` count in full CSV: **0**
- VIC: Tier 3, MF 56, risk 50, `vin_distortion=False`, daily CMF **present** (~0.25)
- VHM: Tier 3, MF 48, risk 50, `vin_distortion=False`, daily CMF **present** (~0.08)
- VIC appears in `outside_fund_disclosure` (not core/ring tag on this priors pass)

**INTERPRETATION**

- Distortion **logic** exists (`indicators.vingroup_distortion_diagnosis`); flags require RS+extension thresholds — not met on **2026-05-21**.
- VHM/VIC still surface in **caution-proxy** (risk ≥ 45) in operator summary — consistent with operator layer, not a scan bug.

**PASS** (logic) / **N/A** (active flags this run)

---

## 7. Tier calibration (fragile regime)

**PASS** — `regime_label=fragile_uptrend_narrow_leadership`; fragile floors yield **18** Tier 2 + **33** Tier 3 with **0** Tier 1 (max score **56.9** &lt; Tier 1 floor 72).

---

## 8. Validation blocks

| Block | Status | Note |
|-------|--------|------|
| `execution_leakage_check` | **ok** | No forbidden fields in outputs |
| `money_flow_redundancy` | **ok** | No pair ≥ 0.9 |
| `unit_handling` | **ok** | `thousand_vnd` mode, 1562 rows |
| `spot_checks` | **present** | MBB/MWG/GMD Reject; CTG/VCB/STB Tier 3 |
| No-lookahead | **PASS** | `confirm_no_lookahead` True for MBB, VIC |

---

## 9. Spot-check table

| Ticker | Tier | Score | MF | fund_context_bucket | emerging | VIN flag | Note |
|--------|------|-------|-----|---------------------|----------|----------|------|
| MBB | Reject | 23.0 | 21 | consensus_core | false | false | Weak MF; core reject |
| CTG | Tier 3 | 40.9 | 50 | consensus_core | false | false | Context-led Tier 3 |
| MWG | Reject | 31.8 | 27 | consensus_core | false | false | Weak MF |
| HPG | Reject | 28.0 | 23 | consensus_core | false | false | Weak MF |
| GMD | Reject | 37.3 | 46 | consensus_core | false | false | Risk/dist flags |
| VIC | Tier 3 | 40.4 | 56 | outside_fund_disclosure | false | false | Risk 50; no VIN flag |
| VHM | Tier 3 | 40.5 | 48 | consensus_second_ring | false | false | Risk 50; no VIN flag |
| VCB | Tier 3 | 39.5 | 42 | consensus_core | false | false | Context-led |
| STB | Tier 3 | 46.2 | 42 | consensus_second_ring | false | false | Highest fund-backed score |

---

## 10. P0 / P1 / P2 patch list (methodology only)

### P0

_None._

### P1

| ID | File | Change |
|----|------|--------|
| P1-1 | `scripts/reporting/validate_institutional_accumulation_package.py` | Expose `vhm_p1c_check_status` in README; deprecate ambiguous `vhm_daily_cmf_missing` boolean |
| P1-2 | `outputs/scans/PACKAGE_INTEGRITY_AUDIT_20260521.md` | Keep synced with active as-of (28 emerging / May 21) — done in latest build |
| P1-3 | `docs/trading/CHATGPT_*_REVIEW_PROMPT.md` | Stage 1 examples must not imply VIC/VHM always flagged (aligned) |
| P1-4 | `context.py` / sector map | Reduce `Unknown` in Tier 1–2 (13/51 top-tier) — enrich from `data/master/sector_map.csv` at **scan** time, not only operator display |

### P2

| ID | File | Change |
|----|------|--------|
| P2-1 | `weekly_diff.py` | Already excludes `_top80` from previous scan — add test |
| P2-2 | Zip build | Include `tests/test_institutional_accumulation_operator.py` in review package |
| P2-3 | `institutional_accumulation_weekly_brief_*.md` | Auto-generate from operator payload to avoid stale manual briefs |

---

## 11. Test gaps (propose names only)

- `test_vingroup_distortion_flag_when_rs_and_extension_met`
- `test_emerging_excludes_risk_above_max_penalty`
- `test_diff_vs_previous_ignores_top80_and_latest`
- `test_operator_html_matches_payload_scan_date`
- `test_sector_map_fallback_reduces_unknown_count`

---

## 12. top80 + manifest

**PASS** — `institutional_accumulation_2026-05-21_top80.csv` top row TCI 56.93 Tier 2; aligns with main CSV sort.

---

*End Claude technical review — no execution/OMS recommendations.*
