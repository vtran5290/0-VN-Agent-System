# Pre-Registration: S17 — VN Cumulative Buy-Sell Flow Indicator
# Belief ID: S17
# Status: TESTED — FAIL (2026-07-05)
# Harness verdict: Q2 PASS (putthroughVolume confirmed separate; clean matched-order flow)
#                  G1a FAIL: best candidate C2_ratio5d OOS MAR 1.7533 (target ≥1.850; miss 0.097 — not borderline)
#                  G1b PASS, G2 PASS (N_OOS 271-307 per candidate)
#                  sub-B collapse: C2 sub-A 3.9455 → sub-B 0.0976 (regime pattern — same as S6/S18)
# Regime observation: 5-day cumulative buy pressure was highly predictive in sub-A (2020-2022 trending/COVID
#   rally) but collapsed in sub-B (2023-2026 choppy regime). Mechanism may be regime-dependent.
# P75 thresholds locked: ratio_1d=1.1564, ratio_5d=1.1543, ratio_20d=1.1213 (from 1304 S1-filtered IS days)
# Date: 2026-07-05
# Prepared by: Claude CLI (Schwager hidden gems extraction session)
# Source: Mark Cook, Stock Market Wizards (2001/2008), "The Egg Timer Trade"
#   — cumulative tick indicator; extremes predict high-probability reversals
# VN adaptation: user's "bid/ask ratio over 1/5/20 days" is the VN operationalization
#
# THIS IS A PRE-REGISTRATION DOCUMENT.
# Gates must be locked BEFORE Cursor runs the harness.
# No gate changes after data is seen.

---

## Belief statement (LOCKED)

"Cumulative buying pressure minus selling pressure (buyer volume − seller volume, summed over 1/5/20 trading days) is a reliable short-term signal: stocks/periods with extreme net buyer dominance over 1/5/20 days predict above-baseline next-day (or next N-day) forward returns."

VN operationalization:
- `ratio_1d[t]` = buyer_volume[t] / seller_volume[t]        (today only)
- `ratio_5d[t]` = sum(buyer_vol, t-4:t) / sum(seller_vol, t-4:t)   (5-day rolling)
- `ratio_20d[t]` = sum(buyer_vol, t-19:t) / sum(seller_vol, t-19:t) (20-day rolling)

Signal hypothesis: ratio > threshold → next-day return > baseline (A3_RS universe)

---

## Data requirements (check before running)

1. **FireAnt buyer/seller volume field:** confirm `buyer_volume` and `seller_volume` are available per ticker per day in the FireAnt data feed used by A3_RS scanner. This is the VN equivalent of the NYSE "tick" (buyer-initiated vs seller-initiated trades). If FireAnt calls these something different ("KLMB mua"/"KLMB bán", "vol_buy"/"vol_sell"), document the field names here before running.

2. **Missing data handling:** if buyer/seller split is unavailable for a ticker on a given day, exclude that ticker from S17 signal generation that day. Do NOT impute.

3. **Minimum history:** 20-day ratio requires 20 consecutive trading days of buyer/seller data. Exclude stocks with < 20 days of clean data from ratio_20d computation.

---

## Degeneracy pre-check (MUST COMPLETE BEFORE GATE PARAMETERS ARE LOCKED)

**Pre-check Question 1:** Is the ratio distribution non-degenerate?
- Compute ratio_1d, ratio_5d, ratio_20d across all A3_RS OOS candidates
- If >70% of observations are within [0.95, 1.05] (ratio ≈ 1.0, no buyer/seller imbalance), the signal is degenerate → S17 becomes VN-SUBSUMED (binding constraint: HOSE/HNX order matching produces near-equal buyer/seller splits mechanically)
- If ratio distribution has meaningful spread (std dev > 0.15 across observations), PROCEED to Lane A backtest

**Pre-check Question 2:** Does ratio_1d vary across A3_RS signal days?
- Check if ratio_1d on A3_RS entry days shows variation (different values on different signal days)
- If all A3_RS entry days have ratio_1d ≈ 1.0, signal provides no information → degenerate

**Pre-check verdict:**
```
RATIO_1D_STD:  [FILL IN] — degenerate if < 0.10
RATIO_5D_STD:  [FILL IN]
RATIO_20D_STD: [FILL IN]
VERDICT: EXPRESSIBLE | DEGENERATE
```

---

## Lane A test design (activate ONLY if pre-check = EXPRESSIBLE)

### Candidate parameters (k=3 per protocol)

| Candidate | Signal condition | Hypothesis |
|-----------|-----------------|------------|
| C1_ratio1d | ratio_1d > [PRE-CHECK P75] AND A3_RS signal | ratio_1d buyer dominance predicts next-day forward return |
| C2_ratio5d | ratio_5d > [PRE-CHECK P75] AND A3_RS signal | 5-day buyer dominance predicts 5-day forward return |
| C3_ratio20d | ratio_20d > [PRE-CHECK P75] AND A3_RS signal | 20-day buyer dominance predicts 20-day forward return |

Percentile thresholds (P75): to be computed from IS data distribution. Lock before OOS run. Do NOT adjust after seeing OOS results.

### Test universe
- All A3_RS OOS signal days where buyer/seller volume data is available
- IS period: same as existing S1/S2 IS period
- OOS period: same as existing OOS periods (2020-2022 sub-A, 2023-2026 sub-B)

### Baseline
- S1-filtered OOS MAR: 1.7844 (deployment baseline — S17 is tested as S1+S17 overlay)
- NOTE: re-scoped 2026-07-05 per opus advisor REDIRECT verdict. Original isolated test (A3_RS raw 0.8386) was replaced because an isolated gate can PASS while S17 fails to add value on top of S1 — the actual deployment context. The TESTED/CALIBRATED label must carry the scope it was tested under.

### Test universe
- All A3_RS+S1-filtered OOS signal days where buyer/seller volume data is available
  (S1 filter = within_15pct proximity; applies before S17 ratio filter)

### Outcome measure
- Primary: S1+S17 combined OOS MAR vs S1-alone baseline (1.7844)
- Secondary: daily forward return on (S1+S17) signal days vs S1-alone signal days

### Gate parameters (LOCKED 2026-07-05 — pre-check EXPRESSIBLE; re-scoped 2026-07-05 per opus REDIRECT)

Pre-check result: ratio_1d std=0.513, pct_near_1.0=13.3% → EXPRESSIBLE.
Data discovery: Q1-Q5 PROCEED (Q2 PARTIAL — put-through to verify; Q4 MEDIUM survivorship).

```
Baseline:       S1-filtered OOS MAR = 1.7844 (deployment baseline; S17 overlaid on S1, not tested in isolation)
                [RESCOPED from A3_RS raw 0.8386 — opus REDIRECT 2026-07-05]
k = 3 candidates (ratio_1d, ratio_5d, ratio_20d)
k-adjustment:   log2(3) × 0.010 = 0.016 (additive to base margin)

G1a (relative): S1+S17 combined OOS MAR ≥ 1.7844 + 0.050 + 0.016 = 1.850
                (base 0.050 absolute margin above S1 baseline + k-adjustment 0.016;
                 S17 must beat S1 alone by this margin — not just beat a retired baseline)
G1b (absolute): S1+S17 combined OOS MAR ≥ 0.516 (standard floor)
G2 (sample):    N_OOS ≥ 30 filtered signal instances per candidate (S1+S17 filtered)
G3 (Q2 guard):  put-through verification complete before OOS run
                (if putthroughVolume is NOT separated in buyQuantity/sellQuantity → flag [Q2-UNRESOLVED];
                 test proceeds but result carries [Q2-RISK] annotation)
Borderline rule: if G1a margin < 0.020 MAR units above 1.850 → CONDITIONAL-ADVANCE; confirmation run required
Standing guardrail: if S1+S17 combined OOS MAR < 0 → PARKED regardless of relative improvement
```

P75 threshold derivation: Cursor computes P75 of ratio_1d/ratio_5d/ratio_20d from IS data (2013-2019 or existing S1/S2 IS window), conditioned on S1-filtered signal days. Lock P75 values in `2026-07-05_schwager_s17_gates_addendum.md` BEFORE running OOS.

NOTE: G1a threshold uses a 0.050 absolute margin above S1 baseline (same additive structure as S18) plus the k=3 k-adjustment. This is more conservative than a pure 2% relative gate (1.820) because S17 adds a secondary filter atop a 1.7844 baseline — the marginal improvement must clear multiple-testing noise at this MAR level.

---

## Interaction test design

**S17 interaction with S1 (52wk high proximity filter):**
- NOTE: with the re-scope (2026-07-05 opus REDIRECT), S1+S17 is now the PRIMARY test, not an interaction follow-on.
  The harness runs S1+S17 combined directly (S1-filtered pool, ratio filter applied on top).
  No separate "interaction test" needed — the G1a gate already tests S1+S17 vs S1-alone.
- If S17 PASSES primary gate: document the S17 mechanism attribution (which ratio window dominated).
- Follow-on: if both S17 standalone (diagnostic, non-promoting) and S1+S17 (primary) are run for comparison, document delta separately.

**S17 interaction with C1 (bear gate):**
- C1 is a hard machine rule that suppresses ALL signals in bear regime
- S17 operates only within C1-permitted (bull) periods — no interaction test needed; C1 wins by architecture

---

## Relationship to user's "bid/ask ratio 1/5/20 days" finding

The user identified "bid/ask ratio over recent 1/5/20 days" as a strong short-term indicator applicable to the VN market, found in a Schwager interview. This pre-registration is the formalization of that finding.

**Terminology mapping:**
| User's term | Schwager source | VN data field |
|-------------|----------------|---------------|
| "bid/ask ratio" | Cook "cumulative tick" | buyer_volume / seller_volume |
| "1 day lookback" | tick on single day | ratio_1d |
| "5 day lookback" | (Cook doesn't specify rolling period; concept) | ratio_5d |
| "20 day lookback" | Cook "cumulative tick" (intermediate, sets up 2-4×/year) | ratio_20d |

The 20-day window most closely matches Cook's "intermediate" cumulative tick indicator (which he says sets up only 2-4 times per year at its most extreme readings). The 1/5-day windows test the shorter-term version that Cook used for day-trading conjunctions.

---

## VN data discovery task (for Cursor)

Before running the pre-check, Cursor must:
1. Check `data_fetchers/` or `src/data/` for FireAnt API field names for buyer/seller volume
2. If not available: check HOSE/HNX raw data files (CSV/Excel exports in `data/raw/`)
3. If neither available: check VNDirect/SSI data feeds (if the agent uses any alternative source)
4. Document the exact field name and add to `data/config/signal_data_schema.md`
5. If no buyer/seller split is available in any data source: S17 becomes VN-SUBSUMED (data unavailability = binding constraint; document in belief evidence field)

---

## Files to create (Cursor)

1. `pp_backtest/cortex_schwager_s17_buysell.py` — harness script (after pre-check passes)
2. `data/config/signal_data_schema.md` — document buyer/seller volume field availability
3. `knowledge/backtests/2026-07-05_schwager_s17_gates_addendum.md` — gates addendum (after pre-check, before OOS run)

---

## HARD RULES

- Do NOT run the harness before pre-check Q1 and Q2 are answered
- Do NOT change thresholds after seeing OOS results
- Do NOT count S3 VN-SUBSUMED (data unavailability) as INVALIDATED
- If buyer/seller volume is unavailable: status = VN-SUBSUMED, retest_trigger = "FireAnt API adds buyer/seller volume field OR HOSE provides order-book data stream"

---

## ChatGPT data-discovery requirements (added 2026-07-05, Phase B decision)

Before running the pre-check, the FireAnt buyer/seller volume field must answer ALL 5 questions. If any answer invalidates the assumption, S17 remains conceptual only.

**Q1: What is the classification basis?**
Is the buyer/seller volume split based on: aggressor buy/sell volume (initiating side), bid/ask matched flow (ask-hit = buy, bid-hit = sell), broker-classified flow (HOSE/HNX reporting standard), or inferred tick direction? → Impacts whether the signal measures actual buying pressure or a proxy.

**Q2: Are put-through and block trades excluded?**
Do buyer_volume / seller_volume fields exclude put-through trades (thỏa thuận) and block trades? → These do not reflect market sentiment — including them contaminates the signal.

**Q3: Historical availability across HOSE/HNX universe?**
Available daily historically for ALL HOSE/HNX names back to A3_RS IS period start? Or partial coverage (large-caps only, post a certain date)? → Partial coverage limits pre-check sample and may introduce selection bias.

**Q4: Survivorship and data-revision risk?**
Is there survivorship bias (delisted stocks excluded retroactively)? Are there data revisions (buy/sell reclassification post-hoc)? → Both inflate backtested performance.

**Q5: Can 1/5/20-day ratio be rebuilt exactly?**
Can `ratio_Nd[t] = sum(buyer_vol, t-N+1:t) / sum(seller_vol, t-N+1:t)` be computed exactly from raw fields? Are there days with missing data (NaN) that break the rolling sum? → Gaps in any rolling period make pre-check results unreliable.

**S17 data-discovery verdict (Cursor to fill in):**
```
Q1 classification basis: FireAnt REST buyQuantity/sellQuantity — HOSE/HNX matched-order buy vs sell counts (not NYSE tick)
Q2 put-through excluded:  PARTIAL — putthroughVolume separate field; buyQuantity/sellQuantity are deal-matched (verify HOSE spec)
Q3 historical coverage:   full OOS 2020-2026 for 261/261 A3 OOS symbols; earliest probe 2012-01-03 (VNM/ACB/AAA)
Q4 survivorship risk:     MEDIUM — trade-conditioned universe; delisted names may be absent
Q5 ratio rebuildable:     YES — 4844/4889 signal days matched (99.1%); 1d/5d/20d ratios computable
OVERALL VERDICT: PROCEED TO PRE-CHECK
Batch pre-check 2026-07-05: ratio_1d std=0.513, pct_near_1.0=13.3% → EXPRESSIBLE. Report: knowledge/backtests/2026-07-05_schwager_s17_s18_s19_precheck_batch.md

GATE RESCOPE (2026-07-05, opus REDIRECT): baseline changed from A3_RS raw 0.8386 → S1-filtered 1.7844.
New G1a = 1.850. See gate parameters section above.
```

---

## References
- Belief source: Cook, Stock Market Wizards (2001), "The Egg Timer Trade" — esp. pp. describing cumulative tick indicator, tick buy at −1000, conjunction trade at tick < −400 + tiki < −22
- Extraction document: D:\V\knowledge_base\2026-07-05_Schwager_HiddenGems_Extraction.md (GEM-SMW-1, Phase 5 analysis)
- Data discovery questions: ChatGPT Phase B decision, 2026-07-05 (see 2026-07-05-2100_SchwagerPACandidates_DecisionReceived.md)
- Council: 2026-07-05-2100_SchwagerPACandidates_Council.md
- Verification: verification-harness.md § VN Agent System → promotion gate design section
