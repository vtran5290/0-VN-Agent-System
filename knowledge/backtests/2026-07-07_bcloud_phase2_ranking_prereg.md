# B_cloud Phase 2 — Ranking Mode Research Pre-Registration

**Pre-registered:** 2026-07-07  
**Domain:** VN Agent System — B_cloud research program Phase 2  
**Parent program:** `2026-07-07_bcloud_research_program_prereg.md`  
**Phase:** 2 of 3 — RS-proxy ranking modes vs FIFO baseline  
**Status:** PRE-REGISTERED — RESEARCH-ONLY

Context: Phase 1 (S1/S2 filter overlays) returned RESEARCH-NEGATIVE — 8/8 candidates FAIL G1a. The structural explanation (FIFO ranking does not concentrate quality; filters can't recover that) points to the ranking architecture as the primary lever. Phase 2 tests existing `ema_portfolio_sim` ranking modes as RS-score proxies using the SAME B_cloud trade set, without re-simulating trade entries.

---

## 1. Architecture

**Same as Phase 1:**
- B_cloud PRIMARY: EMA20/100, cloud_only, partial_tp, ex_vin3, max_pos=20, cost=40bps
- `compute_all_trades()` output from Phase 1 is REUSED (no new simulation needed)
- Only `build_portfolio_v2()` rank_mode parameter varies

**Available rank modes in `ema_portfolio_sim._build_equity_v2()`:**
- `fifo` — baseline (used in Phase 1)
- `ema_dist` — entry price distance above slow EMA, descending (entries with more momentum above cloud ranked higher)
- `mom20` — 20-bar price ROC at entry, descending (short-term momentum)
- `mom60` — 60-bar price ROC at entry, descending (~3-month momentum, closest proxy to A3_RS 3m component)
- `ema_dist_mom20` — per-date percentile rank sum of ema_dist + mom20 (composite momentum quality)
- `ema_dist_mom60` — per-date percentile rank sum of ema_dist + mom60 (composite momentum quality, longer)

Note: `ema_dist_mom20` and `ema_dist_mom60` are the closest available proxies to the A3_RS RS score (which uses 3m+6m momentum + 52wk high proximity + ADV percentile). They use `build_portfolio_v2()` with causal per-date percentile ranking.

---

## 2. Windows

Same as Phase 1 (for comparability):
| Window | Range |
|--------|-------|
| Full panel | ~2012–2026 |
| Primary OOS | 2020–2026 |
| OOS sub-A | 2020–2022 |
| OOS sub-B | 2023–2026 |
| IS | 2013–2019 |

---

## 3. Baseline

**B_cloud FIFO baseline (measured in Phase 1):**
- OOS MAR: **0.4698**
- OOS CAGR: 13.1%
- OOS MaxDD: -27.8%
- N_OOS: 7445

---

## 4. Gate Thresholds (pre-registered, locked before run)

### G1a — Relative gate (binding)
```
candidate OOS MAR >= 0.4698 + 0.066 = 0.5357
```
Same +0.066 margin as Phase 1 (k=5 candidates, k-adjustment same protocol).

### G1b — Absolute floor (advisory, not binding)
```
candidate OOS MAR >= max(0.10, 0.4698 × 0.50) = max(0.10, 0.2349) = 0.2349
```
Already derived from the Phase 1 baseline; no runtime derivation needed.

### N_OOS thresholds
```
N_filled (full): >= 30
N_filled (OOS sub-A): >= 12
N_filled (OOS sub-B): >= 12
```
Note: `build_portfolio_v2()` reports `n_filled_trades` — use this as the N count. Ranking changes the COMPOSITION of filled trades (which signals get slots), not the total portfolio capacity. N_filled may be lower than N_OOS from Phase 1 (FIFO fills more slots; ranking is selective).

### Neg-OOS cap
Both baseline AND candidate OOS MAR negative → CONDITIONAL-ADVANCE cap.

---

## 5. Candidates (pre-registered, k=5)

| # | Rank mode | Description | Priority |
|---|-----------|-------------|----------|
| 1 | `ema_dist_mom20` | Composite: EMA distance + 20-bar momentum (strongest RS proxy) | HIGH |
| 2 | `ema_dist_mom60` | Composite: EMA distance + 60-bar momentum (~3m, closer to A3_RS) | HIGH |
| 3 | `mom60` | 60-bar momentum alone (isolate 3m factor) | MEDIUM |
| 4 | `ema_dist` | EMA distance alone (isolate momentum quality) | MEDIUM |
| 5 | `mom20` | 20-bar momentum alone (isolate short-term factor) | LOW |

All 5 candidates use `build_portfolio_v2()` with the same B_cloud trade set. No new `compute_all_trades()` call needed — trades are identical to Phase 1 baseline.

---

## 6. Direction Expectations (pre-registered)

| Candidate | Expected direction | Rationale |
|-----------|-------------------|-----------|
| `ema_dist_mom20` | POSITIVE — primary target | Composite RS proxy; should concentrate momentum-quality entries |
| `ema_dist_mom60` | POSITIVE — primary target | Longer momentum window; closer to A3_RS 3m component |
| `mom60` | POSITIVE | 3m momentum isolate; directional signal confirmed in A3_RS universe |
| `ema_dist` | NEUTRAL-to-POSITIVE | EMA distance = momentum quality, but may concentrate overextended entries (anti-selective risk) |
| `mom20` | UNCERTAIN | Short-term momentum may mean-revert with partial_tp exit; unclear direction |

**Brain advisory caveat (S19 INVALIDATED):** Within S1+A3_RS pool, RS-highest (sector leader) underperformed RS-lowest (sector laggard) in OOS. Scope: S1-filtered A3_RS pool, 2023–2026. B_cloud FIFO pool is different (wider, unfiltered) — this result may NOT transfer. Pre-registered direction expectation stands; S19 is a caution, not a prior that inverts the hypothesis.

**If ALL 5 candidates FAIL:** Log RESEARCH-NEGATIVE for Phase 2. Review implies that ranking quality overlays do not add value on B_cloud's partial_tp exit architecture in this regime. Program pre-reg's kill criterion applies: if no candidate achieves OOS MAR ≥ 2.0 after Phase 3, program FAILS.

---

## 7. Kill / Invalidity Conditions

| Condition | Action |
|-----------|--------|
| N_filled (OOS) < 30 for all candidates | RESEARCH-THIN; check if ranking is too restrictive |
| All candidates degrade below baseline MAR | RESEARCH-NEGATIVE; log, proceed only if Phase 3 has independent justification |
| `build_portfolio_v2()` v1 vs v2 API mismatch | Fix API; do not mix v1 and v2 equity curves in comparison |

---

## 8. Output Location

```
data/research/bcloud_rs/bcloud_ranking_report.md
data/research/bcloud_rs/bcloud_ranking_meta.json
```

No update to `s2_evidence_tracker.json` from Phase 2 alone — that tracker is for S2 forward evidence. Phase 2 feeds into the B_cloud research program summary only.

---

## 9. Scope

**IN SCOPE:**
- 5 ranking mode variants on Phase 1 B_cloud trade set
- OOS gate evaluation per §4
- Sub-period breakdown for all candidates

**OUT OF SCOPE:**
- New exit modes (partial_tp is locked for Phase 2)
- New filter overlays (those were Phase 1)
- Phase 3 (RS ranking + filter overlay combination) — separate pre-reg required
- Any production integration — Trigger #5 required

`RESEARCH_ONLY_NOT_PRODUCTION`
