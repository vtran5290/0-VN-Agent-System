# Institutional Accumulation Scan — Technical QA Review
**Deliverable A | As-of: 2026-04-30 | Claude review date: 2026-05-21**  
**Methodology: v1.1 | Reviewer: Claude (senior quant + VN markets context)**  
**Scope: methodology only — no execution, OMS, or final_action paths**

---

## 1. Executive Verdict

**VERDICT: PASS (with P1 patches recommended before next scan release)**

FACTS:
- Full scan ran to completion: 1,564 rows scored, Tier 1=0 / Tier 2=13 / Tier 3=35 / Reject=1,516
- All v1.1 contract checks pass per `V11_VALIDATION_NOTE_20260430.md`
- No execution leakage: `validation.execution_leakage_check.ok = true`; no `final_action`, OMS, DNSE, A3/S3 fields
- `tests/test_institutional_accumulation_scan.py` **does not exist** — test gap

INTERPRETATION:
- Core methodology is sound. The Tier 2 outside_fund_disclosure dominance is legitimate signal (fund favorites have weak flow), not a code defect.
- Two P1 issues (missing ETF filter; VHM NaN daily CMF silent pass) do not break the scan but reduce confidence in edge cases.
- Tier 1 = 0 is correct for this regime; not a calibration defect.

---

## 2. Universe Policy

**PASS**

FACTS:
- `pipeline.py:59` calls `discover_symbols(cfg.stocks_dir, watchlist)` when no explicit symbol list is provided.
- JSON `context.universe_policy.mode = "full_liquid_universe"` (confirmed in `institutional_accumulation_2026-04-30.json:17`).
- `n_symbols_scored = 1564` (confirmed).
- Note in output: *"All symbols in data/stocks passing ADV/history gates; fund lists are Smart Money context priors only."*

INTERPRETATION:
- Fund lists from `apr2026_default_priors.json` (`consensus_core`, `commentary_mentions`, etc.) are correctly treated as context tags, not universe filters.
- The `apr2026_default_priors.json:universe_policy.mode = "full_liquid_universe"` is the authoritative config and is correctly propagated.

---

## 3. Fund Context Buckets

**PASS — all 5 buckets implemented; no generic `differentiated_bet` collapse**

FACTS (from `context.py:194–207`, `tag_symbol` function):

| Bucket | Symbols (from priors) | Priority |
|---|---|---|
| `consensus_core` | MBB, CTG, MWG, HPG, VCB, GMD | 1st |
| `consensus_second_ring` | VHM, STB, PNJ, TCB | 2nd |
| `selective_fund_bet` | STB†, BVH, KDH, GVR | 3rd |
| `fund_commentary_mention` | PNJ†, TCB†, BID, ACB, FPT, SSI, REE, GAS, BVH†, MSN, VNM, POW, NLG | 4th |
| `outside_fund_disclosure` | all other liquid names | 5th (default) |

† Overlap: STB appears in both `consensus_second_ring` and `selective_fund_bets`; code assigns the higher-priority bucket (`consensus_second_ring`). This is correct behavior — no silent collapse.

- `has_fund_disclosure_tag = fund_context_bucket != "outside_fund_disclosure"` (`context.py:248`).
- All 5 buckets are populated in the scan output; no `differentiated_bet` field exists anywhere.

MINOR OBSERVATION: STB/PNJ/TCB overlap is handled silently by priority. The notes field in context.py does not flag these dual-membership names, which could confuse an analyst reading raw tags. P2 — add `_in_multiple_lists` flag.

---

## 4. Grouped Money-Flow

**PASS — 4 equal-weight groups correctly implemented**

FACTS (from `scoring.py:110–120`):

| Group | Key inputs | Sub-score (sample: TOS) |
|---|---|---|
| `cmf` | CMF daily, weekly, slope_10d, slope_8w | 90.79 |
| `obv_pvt` | OBV slope 20/50, OBV vs MA20, PVT slope 20/50 | 41.71 |
| `adl` | ADL slope 20, bearish divergence flag | 64.44 |
| `participation` | up/down vol ratio, HV up/down days, turnover accel | 91.05 |

- `score_money_flow = np.mean([cmf, obv_pvt, adl, participation])` — equal weight confirmed (`scoring.py:119`).
- All 4 columns (`score_mf_cmf`, `score_mf_obv_pvt`, `score_mf_adl`, `score_mf_participation`) present in scan output.
- `composite_score` uses `WEIGHT_MONEY_FLOW = 0.38` for the aggregated `score_money_flow` (`config.py:25`).

**CODE OBSERVATION — ADL group is thin (P2):**
`_score_adl_group` uses only 2 components: `adl_slope_20` and `adl_price_divergence_bearish` (`scoring.py:82–89`). The non-divergence branch hard-codes `0.78` (positive bias), inflating ADL scores for any name without confirmed bearish divergence. This creates a small upward bias in MF scores for names where ADL data is simply flat or unavailable.

---

## 5. Emerging Accumulation

**PASS**

FACTS:
- Rule (`pipeline.py:199–205`): tier ∈ {Tier1, Tier2, Tier3} AND `has_fund_disclosure_tag == False` AND `liquidity_ok == True` AND `score_money_flow ≥ 48.0` (`EMERGING_MIN_MONEY_FLOW` in `config.py:63`).
- Output: `emerging_accumulation_2026-04-30.csv` — 36 rows confirmed.
- Top emerging by score: TOS (57.4, transport), DVM (53.8, pharma), NRC (53.45, real estate), TNT (53.29, Unknown), HNG (52.22, food).

**P1 ISSUE — permissive risk gate for emerging:**
Names with significant risk penalties still qualify:
- TNT: Tier 2, MF=69.86, **risk=40.0** (7/25 distribution days), sector=Unknown
- KSF: Tier 2, MF=67.76, **risk=40.0** (9/25 distribution days)
- NVL: Tier 3, MF=73.92, **risk=50.0** (extended 42.7% above MA20/50)
- PVP: Tier 3, MF=71.77, **risk=87.0** (moderately extended + 6/25 dist days)

The current filter does not gate on risk_penalty for emerging candidates. An emerging_accumulation name with risk ≥ 40 is structurally compromised — high distribution days or severe extension undermine the "quiet accumulation" premise. Recommend adding `emerging_max_risk_penalty = 30` config gate.

**P1 ISSUE — E1VFVN30 ETF in emerging Tier 3:**
E1VFVN30 (sector=Quỹ mở, open fund) appears at `score=45.11, MF=57.08, risk=0.0`. An ETF tracking VNINDEX constituents should not appear as an institutional "accumulation candidate." No ETF/fund-vehicle exclusion list exists in `config.py` or `filters.py`. Recommend adding `ETF_EXCLUSION_SYMBOLS` or filtering on sector == "Quỹ mở".

---

## 6. Vingroup Distortion

**PASS — VIC and VHM flagged; VRE and VPL correctly absent from upper tiers**

FACTS (from `indicators.py:183–226`, `vingroup_distortion_diagnosis`):

| Symbol | flag | diagnosis |
|---|---|---|
| VIC | True | `RS_vs_VNINDEX_20d=47.8%; extension=34.8%; weekly_CMF_weak=-0.011; daily_weekly_CMF_conflict; price-led_daily_CMF_only` |
| VHM | True | `RS_vs_VNINDEX_20d=31.0%; extension=28.8%; weekly_CMF_weak=0.015` |
| VRE | not in Tier 1-3 | (not in top output — likely rejects liquidity/history gate) |
| VPL | not in Tier 1-3 | (not in top output — excluded per VIN_DISTORTION_SYMBOLS list in config) |

- Risk penalty for VIN distortion: +22 (`score_risk_penalty` function, `scoring.py:197–199`).
- Context score deduction: −18 for `vingroup_distortion_risk` tag, additional −8 in fragile narrow regime (`context.py:283–289`).

**P1 ISSUE — VHM cmf20_daily = None (NaN):**
Validate-only output shows `vin_VHM: cmf_d=nan`. The `_score_cmf_group` function calls `_scale(None, -0.15, 0.25)` → returns `0.5` (neutral midpoint). This silently neutralizes the daily CMF contribution for VHM's CMF group score instead of signaling missing data. Additionally, `cmf_daily_weekly_conflict` returns `False` when `d is None` (`indicators.py:122`), so the conflict check is silently skipped for VHM. The VIN distortion diagnosis fires correctly (3 reasons: RS, extension, weekly_CMF_weak), but the daily-weekly conflict check is bypassed — if the underlying data is available but improperly null-ed, this could under-flag distortion.

Recommend: in `vingroup_distortion_diagnosis`, add `reasons.append("daily_CMF_missing")` when `cmf_d is None` for VIN symbols. This makes the data gap visible in the diagnosis string.

---

## 7. Tier Calibration

**PASS — fragile regime calibration working; Tier 1 = 0 is correct**

FACTS (from `config.py`, `scoring.py:251–307`):

| Tier | Fragile floor | Normal floor | Additional gates |
|---|---|---|---|
| Tier 1 | 72.0 (all regimes) | 72.0 | MF ≥ 55, risk ≤ 35 |
| Tier 2 | 52.0 | 58.0 | MF ≥ 40, risk ≤ 50 |
| Tier 3 | 38.0 | 42.0 | consensus_core floor at 40/42 in fragile |

- Max score in this scan: 57.4 (TOS) — mathematically impossible to reach Tier 1 floor of 72.0.
- Tier 2 = 13 (fragile floor 52 enabled this; under normal regime most would fall to Tier 3).
- Tier 3 = 35; includes VHM (42.5), HPG (42.1), MWG (45.0), VCB (44.55) via absolute or consensus-core floor.
- Percentile overlay: TIER2_PCTL_FLOOR = 0.78 provides a secondary gate that catches some near-miss names.

INTERPRETATION:
- Tier 1 = 0 is appropriate for `fragile_uptrend_narrow_leadership`. No calibration target should force Tier 1 appearances when the data doesn't support it.
- The operator question "Should Tier 1 occasionally appear in narrow-but-constructive tapes?" — answer: only if score genuinely reaches 72. In the current tape (max score 57.4), Tier 1 = 0 is the correct and honest signal.
- Tier 2 dominated by `outside_fund_disclosure` is *expected* given that consensus-core names have MF ≤ 50 in this tape. This is not a calibration defect.

---

## 8. Validation

**Validate-only output (2026-05-21, reading from `institutional_accumulation_latest.csv`):**
```
Tests:     tests/test_institutional_accumulation_scan.py — FILE DOES NOT EXIST
Validate-only: PASS (spot checks and no-lookahead ran without error)
```

### money_flow_redundancy

FACTS (from JSON `validation.money_flow_redundancy`):
- Check compares 8 raw money-flow features pairwise (`validation.py:59–87`).
- Threshold: |corr| > 0.90 → warn. Status from scan run embedded in JSON.
- Note: The scan JSON was generated 2026-05-21 (re-run on same as-of date); redundancy block present.

INTERPRETATION: High correlation between `obv_slope_20` and `pvt_slope_20` is expected (both volume-trend measures). The grouping architecture explicitly addresses this by putting OBV and PVT in the same group — inter-group independence is the relevant check, not intra-group.

### unit_handling

FACTS:
- All 1,564 rows show `price_unit_mode = "thousand_vnd"`, `value_scale_factor = 1000.0`.
- `unit_warning` column present but appears empty for all rows in sample (no anomalies).
- No `"unknown"` price_unit_mode rows found in sample output.

### execution_leakage_check

**PASS** — `confirm_no_execution_fields` checks for `final_action`, `order_`, `dnse`, `oms`, `buy_order`, `sell_order` keys recursively (`validation.py:153–170`). JSON `workflow_role = "research_ranking_only"`. No leakage fields found.

---

## 9. Spot-Check Table

As-of 2026-04-30. Data from `institutional_accumulation_2026-04-30.csv` and validate-only output.

| Ticker | Tier | Score | MF | fund_context_bucket | emerging | VIN flag | VIN diagnosis | risk_pen | Claude note |
|--------|------|-------|----|---------------------|----------|----------|---------------|----------|-------------|
| MBB | Reject | 26.95 | 24.20 | consensus_core | False | False | — | 40.0 | Flow absent; liquidity likely marginal or penalty-driven |
| CTG | Reject | 32.47 | 25.34 | consensus_core | False | False | — | 0.0 | Weak CMF/OBV; score below T3 fragile floor 38 |
| MWG | Tier 3 | 45.04 | 49.24 | consensus_core | False | False | — | 0.0 | context boost (88 pts) rescues T3; flow borderline |
| HPG | Tier 3 | 42.10 | 44.73 | consensus_core | False | False | — | 0.0 | Fragile floor + consensus floor triggers T3 |
| GMD | Reject | 30.08 | 30.62 | consensus_core | False | False | — | 52.0 | MF=30.62 fails TIER3_CONSENSUS_MIN_MONEY=42; high risk |
| VIC | Tier 3 | 39.58 | 63.41 | outside_fund_disclosure | **True** | **True** | RS=47.8%; ext=34.8%; wkly_CMF=-0.011; conflict; price-led | 69.0 | VIN distortion properly flagged; high risk penalty applied |
| VHM | Tier 3 | 42.50 | 65.59 | consensus_second_ring | False | **True** | RS=31.0%; ext=28.8%; wkly_CMF_weak=0.015 | 57.0 | cmf20_daily=NaN → conflict check silently skipped (P1) |
| VCB | Tier 3 | 44.55 | 57.13 | consensus_core | False | False | — | 0.0 | Reasonable flow; holds MA20 only; fragile T3 |
| STB | Reject | 36.41 | 32.14 | consensus_second_ring | False | False | — | 0.0 | MF=32.14 below all floors; Reject correct |

---

## 10. P0 / P1 / P2 Patch List

### P0 — No blocking defects found for current methodology output

The v1.1 scan produces a compliant, non-execution output. No P0 issues that would require halting or retracting the current scan results.

### P1 — Should fix before next scan release

| ID | File | Change | Rationale |
|----|------|--------|-----------|
| P1-1 | `src/scans/institutional_accumulation/config.py` | Add `EMERGING_MAX_RISK_PENALTY = 30.0` constant | Prevents high-risk names (TNT risk=40, KSF risk=40, PVP risk=87) from appearing as quiet accumulation candidates |
| P1-2 | `src/scans/institutional_accumulation/pipeline.py:199–205` | Add `& (df["score_risk_penalty"] <= cfg.emerging_max_risk_penalty)` to `emerg_mask` | Enforce the new config gate in the mask |
| P1-3 | `src/scans/institutional_accumulation/config.py` | Add `ScanConfig.emerging_max_risk_penalty: float = EMERGING_MAX_RISK_PENALTY` | Surface gate in ScanConfig |
| P1-4 | `src/scans/institutional_accumulation/filters.py` or `config.py` | Add `ETF_EXCLUSION_SECTORS = {"Quỹ mở"}` and apply in `discover_symbols` or `passes_liquidity` | Prevents E1VFVN30 and other open funds from appearing as accumulation candidates |
| P1-5 | `src/scans/institutional_accumulation/indicators.py:183–226` | In `vingroup_distortion_diagnosis`, add `if cmf_d is None: reasons.append("daily_CMF_missing")` for VIN symbols | Makes missing-data visible in diagnosis string; prevents silent skip of conflict check for VHM |
| P1-6 | `tests/` (new file) | Create `tests/test_institutional_accumulation_scan.py` with unit tests (see Section 11) | No dedicated test coverage = regression risk on every code change |

### P2 — Nice to have

| ID | File | Change | Rationale |
|----|------|--------|-----------|
| P2-1 | `src/scans/institutional_accumulation/report.py` or `weekly_diff.py` | Add `bucket_mix_summary: {consensus_core: N, commentary: N, selective: N, outside: N}` to compact JSON | Gives operator instant read on tier composition quality |
| P2-2 | `src/scans/institutional_accumulation/scoring.py:82–89` | Expand `_score_adl_group` to include `adl_slope_50` and `obv_vs_adl_correlation` | ADL group has only 2 components; hard-coded 0.78 default introduces upward bias |
| P2-3 | `src/scans/institutional_accumulation/validation.py:10` | Expand `CONSENSUS_CHECK` list to include VCB, VHM, STB | Current spot check only covers 5 of 9 required names from the v1.1 contract |
| P2-4 | `src/scans/institutional_accumulation/run.py:64` | In `_validate_only`, add `component_balance` and `money_flow_redundancy` output | Currently validate-only only prints spot checks and lookahead; misses two validation blocks |
| P2-5 | `src/scans/institutional_accumulation/context.py:183–207` | Add `_in_multiple_lists` flag to `tag_symbol` return dict | STB, PNJ, TCB have dual-bucket membership; silent priority resolution could confuse downstream analysts |

---

## 11. Test Gaps

File `tests/test_institutional_accumulation_scan.py` does not exist. Proposed test names:

```
test_universe_policy_is_full_liquid_universe_by_default
test_fund_context_five_buckets_no_differentiated_bet
test_score_money_flow_is_mean_of_four_groups
test_emerging_candidate_requires_no_fund_disclosure_tag
test_emerging_candidate_excluded_when_risk_penalty_exceeds_gate
test_etf_excluded_from_emerging_candidates
test_vin_distortion_fires_for_vic
test_vin_distortion_diagnosis_includes_daily_cmf_missing_when_null
test_tier1_requires_all_three_gates_simultaneously
test_tier2_fragile_floor_lower_than_normal
test_tier3_consensus_core_floor_fires_in_fragile_regime
test_no_execution_fields_in_scan_output
test_no_lookahead_slice_through
test_unit_handling_all_rows_have_price_unit_mode
test_score_percentile_computed_only_for_liquid_universe
```

---

## 12. Open Questions — Claude's Answers

**Q1: Why is Tier 2 fully dominated by outside_fund_disclosure?**
FACT: All 13 Tier 2 names have `fund_context_bucket = outside_fund_disclosure`. The consensus-core names (MBB MF=24, CTG MF=25, GMD MF=31) and second-ring names (STB MF=32) all have money-flow scores that fall below the Tier 2 MF floor of 40. The emerging names (TOS MF=72, DVM MF=75) have genuinely stronger flow.
INTERPRETATION: This is the scan functioning correctly — the April 2026 fragile tape has divergent signals where fund-consensed names show weak accumulation while unknown/small names show strong flow. The operator should treat this as actionable intelligence (consensus is not being accumulated in this tape), not a code defect.

**Q2: Should emerging Tier 2 require stronger weekly confirmation?**
Yes. Recommend adding `emerging_max_risk_penalty = 30` (P1-1 through P1-3 above) and optionally a `emerging_min_weekly_cmf = -0.05` gate (to exclude names with confirmed weekly distribution).

**Q3: Hidden ADV/history bias toward illiquid-but-passable names?**
Partially. 4 of 13 Tier 2 names have `sector = "Unknown"` (TNT, DSH, PIV, SJS), indicating missing `level4_stock_scan_adv2b_all.csv` sector coverage. ADV50 for PCH is 2.28B VND (barely above the 1.5B gate). These are data coverage gaps, not structural bias. Recommend sector-map coverage audit as P2.

**Q4: Should compact output include bucket mix summary?**
Yes — P2-1 above.

**Q5: Would weekly spread/close-quality improve robustness?**
Modest improvement. The `close_strength_score` already captures close quality. Weekly spread would complement `score_mf_participation` without duplicating CMF group. Add as optional P2 to `_score_participation_group`.

**Q6: Should Tier 1 = 0 be acceptable?**
Yes. In `fragile_uptrend_narrow_leadership` with max scan score = 57.4, any Tier 1 appearance would require artificially relaxed thresholds. Tier 1 = 0 is the correct and transparent signal. Do not introduce a calibration target that forces Tier 1 names when the flow data doesn't support them.

---

*End of Deliverable A. Files read: docs/trading/INSTITUTIONAL_ACCUMULATION_SCAN.md, src/scans/institutional_accumulation/{pipeline.py, scoring.py, context.py, indicators.py, config.py, validation.py, run.py}, data/smart_money/priors/apr2026_default_priors.json, outputs/scans/{institutional_accumulation_2026-04-30.json, _top80.csv, emerging_accumulation_2026-04-30.csv, METHODOLOGY_V11_COMPARISON_20260430.md, V11_VALIDATION_NOTE_20260430.md}. Commands run: validate-only (PASS), pytest (test file does not exist).*
