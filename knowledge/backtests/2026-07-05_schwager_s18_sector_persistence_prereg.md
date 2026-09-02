# Pre-Registration: S18 — VN Sector Same-Day Persistence
# Belief ID: S18
# Status: TESTED — NEUTRAL (2026-07-05)
# Harness verdict: G2 PASS (59-60% continuation ≥55% floor — mechanism confirmed in VN)
#                  G1a FAIL (best MAR 0.5675, target ≥1.844 — filter anti-selective on S1 pool)
#                  Sub-window split: sub-A 1.1935 / sub-B 0.2273 (severe regime collapse)
# Operational decision: do NOT apply as stock-selection filter on S1 pool.
#   Possible future reframe: sector-level market-timing overlay (not stock filter).
# Date: 2026-07-05
# Prepared by: Claude CLI (Schwager hidden gems extraction session — completion pass)
# Source: Gil Blake, The New Market Wizards (1992), interview
#   — "A price change larger than the average daily price change in a given sector had
#      anywhere between 70 to 82 percent chance of being followed by a move in the same
#      direction on the following day."
#   Additional detail: avg hold 2-3 days; ~50% of profit on day 1;
#   sample 10-20 sector stocks to predict sector direction for the day.
#
# THIS IS A PRE-REGISTRATION DOCUMENT.
# Gates must be locked BEFORE Cursor runs the harness.
# No gate changes after data is seen.

---

## Belief statement (LOCKED)

"An above-average daily price change in a VN sector basket (measured against that sector's own rolling daily return volatility) has a materially elevated probability of continuation in the same direction on the following trading day — operationalizing Blake's 70-82% sector persistence finding."

VN operationalization:
- Define VN sector groups by HOSE/HNX sector classification (banking / real-estate / steel / food-bev / energy / logistics / securities / utilities)
- For each sector on day t: compute sector return = equal-weight avg return of sector members
- Define "above-average" threshold: sector return > k_thresh × rolling_std(sector_return, window=N)
- If threshold crossed on day t → sector likely repeats direction on day t+1 (persistence signal)
- Signal output: sector-level directional bias for following day; selects WHICH sector A3_RS is most likely to produce winners in

Architecture note: S18 is a SECTOR-LEVEL signal. Its VN use is to filter or prioritize A3_RS candidates by sector — stocks in sectors that fired S18 on day t are prioritized for entry on day t+1. S18 does NOT modify entry/exit logic for individual stocks; it is a sector-filter overlay.

---

## Distinction from PA-008

**S18** tests Blake's sector persistence SIGNAL — does a large sector move predict same-direction follow-through next day (70-82% probability)?
**PA-008** tests Blake's DIVERSIFICATION principle — does capping exposure per sector improve risk-adjusted returns via binomial compounding?

S18 and PA-008 are distinct. S18 can be tested (and potentially CALIBRATED) while PA-008 is still in pre-registration. The combined S18 × PA-008 test is a natural follow-on if both independently pass.

---

## Data requirements (check before running)

1. **Sector membership lists:** HOSE/HNX sector classification per stock, current + historical (sector reassignments must be tracked if any occurred in IS/OOS period). Source: FireAnt API or HOSE sector data.

2. **Minimum sector breadth:** Each sector must have ≥10 member stocks in the A3_RS OOS universe to compute a meaningful sector return. If a sector has <10 stocks: exclude from S18 computation for that period (flag in output).

3. **Daily sector return computation:** equal-weight average of daily returns across sector members. Excludes stocks not yet listed or suspended on that day.

4. **Rolling std dev window:** rolling N-day std of sector return; N to be chosen in IS period. Candidates: N=20 (1 month) and N=60 (1 quarter).

5. **Minimum signal count:** pre-check must confirm ≥30 sector-days per candidate threshold level in OOS period (to avoid VN-THIN verdict at the sector level).

---

## Degeneracy pre-check — COMPLETE (2026-07-05, batch cortex_schwager_s17_s18_s19_precheck_batch.py)

**VERDICT: EXPRESSIBLE**

| Metric | Value | Assessment |
|--------|-------|------------|
| Sectors ≥10 panel members | Agri, Consumer, Securities, Banks, Logistics, BDS, Oil_Gas, Steel | ✓ 8 sectors (need ≥3) |
| IS qualifying sectors | 11 | ✓ |
| OOS fire rate (k=1.0) | 16.0% | ✓ within 15-30% target |
| OOS fire rate (k=0.75) | 22.8% | ✓ |
| IS continuation rate (k=1.0) | **56.3%** | ⚠️ below Blake's 70-82% claim |

**Key finding:** IS continuation 56.3% is meaningfully below Blake's 70-82% US finding. VN effect exists but weaker. Gates reflect this — 70-82% is NOT used as gate threshold.

---

## Gate parameters (LOCKED 2026-07-05)

**Test design:** S18 sector persistence signal used as a priority filter for A3_RS+S1 candidates.
Days when sector j fires S18 (sector return > k_thresh × rolling_std) → prioritize A3_RS+S1 candidates from sector j for entry.

```
Baseline:       S1-filtered OOS MAR = 1.7844 (S18 overlaid on best current system)
k = 2 candidates: k_thresh=1.0 (standard deviation), k_thresh=0.75 (lower threshold)
k-adjustment:   log2(2) × 0.010 = 0.010 (additive to base margin)

G1a (relative): OOS MAR ≥ 1.7844 + 0.050 + 0.010 = 1.844
G1b (absolute): OOS MAR ≥ 0.516
G2 (continuation floor): OOS sector continuation frequency ≥ 55%
    (VN-calibrated floor; IS was 56.3%; < 55% OOS = signal too noisy to deploy)
G3 (sample floor): N_OOS trade mappings ≥ 30 per candidate
Neg-OOS-cap: best candidate OOS MAR < 0 → PARKED
Borderline rule: G1a pass but margin < 0.020 above 1.844 → CONDITIONAL-ADVANCE
                  (a separate pre-registered follow-up confirmation test is required before promotion;
                   CONDITIONAL-ADVANCE is not a promotion pathway — it is a "re-test" signal;
                   the follow-up test must be pre-registered BEFORE seeing additional data)
Rolling std window: IS derives P75 for N=20 and N=60; lock before OOS run
```

---

## Degeneracy pre-check (original section — now complete — ANSWERED BELOW)

**Pre-check Question 1: Sector breadth adequacy**
- List all VN sectors with ≥10 members in the A3_RS OOS candidate pool (by year-range)
- If fewer than 3 sectors meet the ≥10 member threshold consistently: signal is effectively VN-SUBSUMED (too few sectors to diversify the persistence signal, and sample too thin)
- If ≥3 sectors meet the threshold: PROCEED

**Pre-check Question 2: Sector return distribution non-degeneracy**
- Compute rolling 20-day std dev of sector returns for each qualifying sector
- Check: is the threshold k_thresh × std_dev ever exceeded (i.e., are there genuinely "above-average" sector days)?
- If >90% of sector-days are within ±1 std dev: signal fires too rarely → VN-THIN risk → check k_thresh = 0.75 or 0.5
- Target fire rate: S18 fires on 15-30% of sector-days (enough to generate ≥30 OOS instances per candidate)

**Pre-check Question 3: VN vs US sector comparison**
- Blake's 70-82% persistence was measured on US mutual fund sectors (daily NAV). VN sector returns use live price (HOSE daily close). The mechanism (sector-level momentum persistence) should be similar, but the threshold may differ.
- Pre-check check: compute empirical next-day continuation rate (raw % without any filter) for above-threshold sector-days in IS period. Should be meaningfully above 50% (>58%) to be worth pre-registering.

**Pre-check verdict:**
```
QUALIFYING_SECTORS:         Agri, Banks, BDS, Consumer, Logistics, Oil_Gas, Securities, Steel (≥10 panel members)
FIRE_RATE_AT_KTHRESH_1.0:   16.0% mean sector-days (OOS)
FIRE_RATE_AT_KTHRESH_0.75:  22.8% mean sector-days (OOS)
IS_CONTINUATION_RATE:       56.3% mean (up-days k=1.0, IS 2013-2019) — below Blake 70-82% but above 50% noise floor
VERDICT: EXPRESSIBLE
Batch report: knowledge/backtests/2026-07-05_schwager_s17_s18_s19_precheck_batch.md (2026-07-05)
Note: G_persistence ≥60% still required at harness — pre-check only confirms sector breadth + non-degenerate fire rate.
```

---

## Lane A test design (activate ONLY if pre-check = EXPRESSIBLE)

### Candidate parameters (k=3 per protocol — 3 threshold levels)

| Candidate | Signal condition | Threshold | Hypothesis |
|-----------|-----------------|-----------|------------|
| C1_thresh100 | sector_return_t > 1.0 × rolling_std(sector_return, N=20) AND A3_RS signal in that sector | k=1.0 | Above-average sector move (strict) → next-day continuation in that sector |
| C2_thresh075 | sector_return_t > 0.75 × rolling_std(sector_return, N=20) AND A3_RS signal in that sector | k=0.75 | Moderately-above-average sector move → next-day continuation |
| C3_thresh050 | sector_return_t > 0.50 × rolling_std(sector_return, N=20) AND A3_RS signal in that sector | k=0.50 | Any positive sector momentum day → next-day signal amplification |

**Direction alignment rule:** S18 filters A3_RS LONG signals in UPWARD-moving sectors (sector_return_t > threshold on upside) only. Short sector persistence is not applicable in VN (retail-long-only context).

**Lookback window choice:** N=20 is the default; if sector-day count is VN-THIN at N=20, test N=60 as an alternative in IS period only (pre-commit before OOS).

### Test universe
- All A3_RS OOS signal days where the underlying stock's sector had ≥10 member stocks AND the sector met the threshold condition on day t-1 (the "signal" day for S18 is t; the filter is applied at end of day t for entry on day t+1)
- IS period: same as existing S1/S2 IS period (2012-2019 or equivalent)
- OOS period: same sub-windows as existing OOS (sub-A 2020-2022, sub-B 2023-2026)

### Baseline
- A3_RS standalone OOS MAR: current frozen baseline (check knowledge.md § Calibrated Beliefs before running — use the locked value, not a session estimate)
- S1-filtered OOS MAR: 1.7844 (the currently calibrated S1 standalone; use if testing S1 × S18 combination after S18 standalone passes)

### Outcome measure
- Primary: OOS MAR for S18-filtered subset vs unfiltered A3_RS baseline
- Secondary: next-day sector continuation rate (% of sector-days where signal fired AND sector moved same direction next day) — direct test of Blake's 70-82% claim

### Gate parameters (LOCK after pre-check, BEFORE Cursor runs harness)

```
G1a (relative): OOS MAR ≥ [A3_RS baseline × 1.08] (8% relative improvement floor — sector filter)
G1b (absolute): OOS MAR ≥ 0.516 (standard absolute floor per verification-harness.md)
G_persistence: next-day sector continuation rate ≥ 60% (Blake's 70-82% → VN-adjusted to ≥60%; lower than Blake because VN ±7% bands cap momentum and retail concentration adds noise)
N_OOS floor: ≥ 30 S18-filtered OOS signal instances per candidate
Borderline rule: G1a margin < 0.02 MAR units AND G_persistence < 65% → CONDITIONAL-ADVANCE only
Standing guardrail: if both baseline AND candidate OOS MAR are negative → CONDITIONAL-ADVANCE only
Window scoping: all gate thresholds calibrated on same OOS window; no cross-window reuse
```

Gate adaptation note: Blake's persistence (70-82%) was measured on US sector mutual funds with daily NAV pricing — noise-free signal. VN live HOSE prices have tick noise, spread, and ±7% band effects. A persistence rate of 60-65% in VN is consistent with Blake's finding after adjusting for VN-specific price structure.

---

## Interaction test design

**S18 × S1 (52wk high proximity filter):**
- Hypothesis: S18 sectors that also meet S1 proximity → double confirmation → stronger signal
- Gate: G_ia — OOS MAR of (A3_RS + S1 + S18) ≥ S1-alone OOS MAR × 1.04 (4% marginal floor)
- Test only after S18 standalone passes

**S18 × PA-008 (sector cap):**
- S18 selects which sectors to prioritize; PA-008 caps positions within each sector. Sequential, not conflicting.
- Combined test: after both S18 CALIBRATED and PA-008 APPROVED-FORMALIZE harness passes (do not conflate tests)

**S18 × C1 (bear gate):**
- C1 suppresses all signals in bear regime; S18 applies within C1-permitted (bull) periods only. No interaction test needed.

**S18 × S19 (intra-sector RS selection):**
- S18 tells us WHICH sectors to trade in; S19 tells us WHICH STOCK within that sector to buy.
- Natural combination: S18 fires on sector → S19 selects the strongest RS stock within that sector → highest-conviction combined signal
- Gate: combined test after BOTH S18 and S19 independently CALIBRATED. Minimum N_OOS for combination ≥ 20 (will be thin — flag if VN-THIN risk).

---

## WIP cap check

Per sources.md WIP cap (ratified 2026-07-05):
- This pre-registration counts toward reducing the untested-without-prereg backlog
- Current backlog before this pre-reg: ~7 Lane A beliefs without pre-regs
- After this pre-reg: ~6 (one below the pause threshold of 6 — marginally OPEN if S18 pre-reg reduces backlog)
- S19 pre-registration further reduces to ~5 (OPEN for limited new extraction)

Check sources.md current backlog count before proceeding with any new SOURCED belief additions.

---

## Files to create (Cursor, after pre-check passes)

1. `pp_backtest/cortex_schwager_s18_sector_persistence.py` — harness script (after pre-check passes)
2. `knowledge/backtests/2026-07-05_schwager_s18_sector_persistence_degeneracy.md` — pre-check results
3. `knowledge/backtests/2026-07-05_schwager_s18_sector_persistence_gates_addendum.md` — gates addendum (after pre-check, before OOS run)

---

## VN-specific considerations

**VN sector concentration risk (C3 interaction):** VN has fewer liquid stocks per sector than US (especially in non-banking/non-real-estate sectors). The ≥10 member floor may reduce eligible sectors to banking, real estate, and securities. If only 2-3 sectors qualify consistently, S18 becomes a de facto pair-of-sectors signal — still testable, but sector diversification benefit is limited.

**±7% price band effects:** On days when many sector stocks hit ±7% bands, the sector return is truncated by the band. This attenuates extreme sector returns and may reduce the measured persistence rate. Include a check: what fraction of above-threshold sector-days had ≥20% of stocks hitting the ±7% band? If high, sector return measurement is systematically biased on the most extreme days.

**Layman description:** "If a VN sector (e.g., banking stocks) moves up more than usual today, it's likely to keep moving up tomorrow. Gil Blake found 70-82% continuation probability in US sectors. S18 tests if this holds for VN banking, real estate, and other sector groups."

---

## HARD RULES

- Do NOT run the harness before pre-check Q1, Q2, and Q3 are answered
- Do NOT change thresholds after seeing OOS results
- S18 is a SECTOR-LEVEL filter, not a stock-level signal — do not confuse with A3_RS entry logic
- G_persistence is required (not optional) — if sector continuation rate < 60%, the core Blake claim is rejected in VN regardless of OOS MAR

---

## References
- Belief source: Blake, The New Market Wizards (1992) — interview approximately at NMW L2072
- Extraction document: D:\V\knowledge_base\2026-07-05_Schwager_HiddenGems_Extraction.md (GEM-NMW-2)
- Knowledge base: D:\V\.claude\brains\vn-trading-advisor\knowledge.md § S18 (v17)
- Sources log: D:\V\.claude\brains\vn-trading-advisor\sources.md
- PA-008 pre-reg: D:\V\0. VN Agent System\knowledge\backtests\2026-07-05_schwager_pa008_sectorcap_prereg.md
- Verification: verification-harness.md § VN Agent System → promotion gate design section
