# FX Reserve–Liquidity–Deposit Transmission — Cursor Review Pack

**Date:** 2026-08-21 23:21 ICT  
**Agent:** Cursor  
**Branch:** `session/2026-07-16-c4-mistier-fix`  
**Design SoT:** `reports/2026-08-21_fx_reserve_deposit_transmission_design.md` (`38c121c4`)  
**Plan SoT:** `reports/2026-08-21_fx_reserve_deposit_transmission_implementation_plan.md` (`f30aaaea`)  
**Handoff:** `00. Command Center/05_AI_Handoffs/2026-08-21-2129_VNAgent_FXReserveDepositTransmission_CursorHandoff.md`

## FACTS

- Canonical object `fx_reserve_deposit_transmission` added to `data/research/rate_pivot_monitor.json`.
- Current normalized state: **State 1 · FX PRESSURE EASING · SETUP / APPROACHING · NOT_CONFIRMED**.
- Integrity: `VALID`.
- Evidence hash (shared PM ↔ La Bàn): `sha256:06133d36cefc90df729e24c05dd3c32788e0015a4bce76262b8c8e7d0ab72ee7`.
- Legacy C3: `CONFIRMED → APPROACHING`. Legacy C6: `APPROACHING → WATCH`.
- V2 P2 remains `MIXED`; V2 score remains `0`. All `scoring_effect` values `NONE`.
- PM Regime is primary full panel; La Bàn T6 is non-scoring mirror loaded **after** `run_engine()`.
- `/verifier` verdict: **PASS_WITH_RESERVATIONS** ([verifier](11a6cecd-d33b-42cd-a604-3a1f4e413563)). Architecture-advisor: not required.

## FILES CHANGED

| Commit | Message |
|---|---|
| `64db72f9` | feat(macro): add FX transmission contract validator |
| `ccf477c9` | data(macro): add State 1 FX liquidity transmission monitor |
| `594b38a5` | feat(reporting): render FX transmission in PM Regime |
| `3b3fc071` | feat(laban): mirror FX liquidity state in T6 |
| (this) | docs(macro): verify FX liquidity transmission rollout |

Paths:

- `scripts/reporting/rate_pivot_transmission.py` (create)
- `tests/test_rate_pivot_transmission.py` (create)
- `tests/test_pm_dashboard_rate_pivot_transmission.py` (create)
- `tests/test_laban_transmission_mirror.py` (create)
- `data/research/rate_pivot_monitor.json` (extend + C3/C6)
- `scripts/reporting/generate_pm_regime_dashboard.py` (panel + Macro Pulse badge + G2 binding)
- `scripts/reporting/build_vn_structural_signals.py` (post-engine load)
- `scripts/reporting/laban_render.py` (T6 mirror only)
- `reports/pm_regime_dashboard_latest.html` (regen)
- `reports/tollbooth_tracker_latest.html` (regen)
- `reports/vn_structural_signals_fragment.html` (regen)
- `reports/2026-08-21_fx_reserve_deposit_transmission_cursor_review.md` (this file)

## FILES NOT TOUCHED

- `scripts/reporting/laban_engine.py`
- `data/decision/laban_axis_state.json`
- `data/decision/vn_structural_signals.json`
- `data/decision/laban_scenarios.json`
- A3/S3/OMS, `final_action`, signal math, backtests, DNSE, `live_auto`, real-capital paths
- Axes, weights, scenarios, hard-invalidation logic

## SECTIONS/CARDS CHANGED

- **PM Rate Pivot Monitor:** full FX→reserve→deposit transmission panel prepended above V2.
- **PM Macro Pulse:** badge `FX → Liquidity: STATE 1 · NOT CONFIRMED`.
- **PM V2 binding callout:** when G1 passes and G2 fails → G2 inflation is binding (no longer mislabels G1).
- **La Bàn T6:** compact `FX–LIQUIDITY TRANSMISSION` mirror above GT1/assumptions.

## OLD STATE → NEW STATE

| Surface | Old | New |
|---|---|---|
| FX transmission | Absent | State 1 · SETUP/APPROACHING · NOT_CONFIRMED |
| Legacy C3 | CONFIRMED | APPROACHING |
| Legacy C6 | APPROACHING | WATCH |
| V2 P2 | MIXED | MIXED (unchanged) |
| V2 score | 0 / GATED | 0 (unchanged) |
| PM overall regime | existing | unchanged (non-scoring) |
| La Bàn axes/weights/regime | existing | unchanged (engine invariance True/True/True) |

## MONITORING VARIABLES ADDED (18)

| # | Variable | Status | Freshness | Claim |
|---|---|---|---|---|
| 1 | free_market_usd_vnd | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 2 | official_interbank_usd_vnd | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 3 | sbv_central_reference | PARTIAL | STALE | FACT |
| 4 | comparable_leg_premium | NOT_COMPARABLE | UNKNOWN | UNCONFIRMED |
| 5 | trade_balance | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 6 | fdi_disbursement | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 7 | foreign_portfolio_flows | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 8 | remittances | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 9 | bop_proxies | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 10 | sbv_fx_purchases | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 11 | fx_reserve_estimates | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 12 | omo_sbv_liquidity | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 13 | on_1w_vnd_interbank | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 14 | big4_6_12m_deposit | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 15 | tier2_6_12m_deposit | PARTIAL | STALE | MARKET_CHATTER |
| 16 | deposit_vs_credit_growth | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 17 | ldr | UNKNOWN | UNKNOWN | UNCONFIRMED |
| 18 | nim_trajectory | UNKNOWN | UNKNOWN | UNCONFIRMED |

Checklist: items 1 and 6 = `PARTIAL`; items 2–5, 7–9 = `UNKNOWN`.  
Regulatory LDR 50% Treasury-deposit item remains `SOURCE_SECONDARY / UNCONFIRMED_PRIMARY`.

## CHECKS RUN AND EXACT RESULTS

```text
.\.venv\Scripts\python.exe -m pytest tests/test_rate_pivot_transmission.py -q
→ 12 passed

.\.venv\Scripts\python.exe -m pytest tests/test_pm_dashboard_rate_pivot_transmission.py -q
→ 3 passed

.\.venv\Scripts\python.exe -m pytest tests/test_laban_transmission_mirror.py -q
→ 3 passed

.\.venv\Scripts\python.exe -m pytest tests/test_rate_pivot_transmission.py tests/test_pm_dashboard_rate_pivot_transmission.py tests/test_laban_transmission_mirror.py tests/test_pm_dashboard_macro_semantics.py tests/test_laban_engine.py -q
→ 44 passed, 2 failed (pre-existing / unrelated):
   - test_ftse_aug21_is_list_date_not_upgrade_decision (CPI refresh → Unknown; not in FX files)
   - TestLabanEngine.test_21_html_no_fixture_and_armed_card_ship (MÂU THUẪN count 7≠6 in tollbooth shell content; not in FX mirror)

python scripts/reporting/generate_pm_regime_dashboard.py → exit 0
python scripts/reporting/build_vn_structural_signals.py --as-of 2026-08-21 --inject → exit 0

Parity: PM and La Bàn HTML both contain evidence_hash sha256:06133d36…
Forbidden labels absent on both surfaces.
Secret grep on new scripts/tests: no matches.
```

## LA BÀN/PM SCORE INVARIANCE

- Engine before/after Task 4: `weights_equal=True`, `axis_equal=True`, `hard_equal=True` (`as_of=2026-08-21`).
- V2 score still `0`; P2 still `MIXED`.
- Transmission contract not present in axis/signals/scenarios decision files.
- `laban_engine.py` not modified.

## DATA GAPS / UNKNOWN

- Official interbank USD/VND, disclosed SBV FX purchases, reliable reserve estimates, 1W VND interbank, remittances/BOP, clean exact-key multi-bank deposit panel.
- Same-leg formal FX premium still unavailable → `NOT_COMPARABLE`.
- Original SBV Decision 1743/QĐ-NHNN not retrieved.

## RISKS

- Legacy C3/C6 older prose still mentions prior CONFIRMED/APPROACHING wording before the `[2026-08-21 TX]` append — top-level status fields are correct; narrative can mislead if read in isolation.
- La Bàn mirror Observation/Inference/Confirmation lines are State-1 template text (not ladder-driven) — can drift if state advances without renderer update.
- Regenerating tollbooth can churn unrelated shell content counts (see test_21).
- Dirty worktree remains heavily dirty outside this feature; only task paths were staged.

## ACTIONS

1. ChatGPT: `APPROVE | REJECT | REDIRECT` on this implementation fidelity pack.
2. Optional follow-up (not done here): scrub leftover C3/C6 historical prose; retrieve Decision 1743 primary PDF; fill UNKNOWN legs when primary sources exist.
3. No deployment / push / live trading authorized.

## In Plain English

Cursor added a careful FX→reserves→deposit “state light” to the PM dashboard, with a small mirror on La Bàn T6. It currently says State 1 only (FX pressure easing), not confirmed. Scores and trading paths were not changed. Most hard data legs are still blank on purpose. ChatGPT should approve or redirect the build before any further use.
