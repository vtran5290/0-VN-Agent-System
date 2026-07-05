# Gates Addendum — Cortex Book 2: S1 — O'Neil 52-Week High Proximity Filter
# LOCKED 2026-07-05 — Do not adjust post-run

**Pre-registration file:** knowledge/backtests/2026-07-04_cortex_book2_s1_52wkhi_prereg.md
**Harness script:** pp_backtest/cortex_book2_s1_52wkhi.py
**Locked by:** Claude session 2026-07-05 (Cortex Book 2 S1/S2 pipeline run)

---

## Baseline (locked — from cortex_book1_sizing_meta.json)

| Metric | Value |
|--------|-------|
| Baseline OOS MAR (2020-present) | **0.8386** |
| Baseline full-sample MAR (2012-present) | **0.5321** |
| Baseline OOS trade count | 8,827 (full window); OOS subset from this |
| Source | data/research/cortex_book1_sizing/cortex_book1_sizing_meta.json |

---

## Candidate configuration (locked)

**Filter type:** 52-week high proximity filter
**Signal stream:** A3_RS (frozen — no changes)
**Sizing:** D3 sector slot sizing (unchanged — 1.25× leading / 0.75× lagging)
**D4 cash yield:** 3.8% (same as baseline)
**Entry timing:** T+1 open after A3_RS signal bar (P1 honest execution — unchanged)

**k = 3** (three threshold candidates — multiple testing adjustment applied)
**Threshold labels and values:**

| Label | min_prox | Interpretation |
|-------|----------|----------------|
| `within_15pct` | 0.85 | Price >= 85% of 52-week high |
| `within_20pct` | 0.80 | Price >= 80% of 52-week high |
| `within_25pct` | 0.75 | Price >= 75% of 52-week high |

**52-week high definition:** `max(high[max(0, si-251) : si+1])` — includes signal bar; lookback 252 trading days.

**Empirical degeneracy confirmation (2026-07-05):**
- within_15pct: ~36.0% OOS stock-days pass → ~1,368 est. filtered OOS trades
- within_20pct: ~47.5% OOS stock-days pass → ~1,805 est. filtered OOS trades
- within_25pct: ~57.6% OOS stock-days pass → ~2,189 est. filtered OOS trades
- Spread: ~21pp — IV clearly varies. CLEAN (not degenerate).

---

## Locked gates (do not adjust post-run)

### G1a — Relative gate (primary)

```
G1a: candidate OOS MAR >= baseline OOS MAR + G1a_margin_adjusted
     G1a_margin_adjusted = base_margin + k_adj = 0.050 + 0.016 = 0.066
     k_adj = 0.010 × log2(3) ≈ 0.016

     Numerically: candidate OOS MAR >= 0.8386 + 0.066 = 0.9046
```

**G1a threshold: OOS MAR >= 0.9046** ← LOCKED

### G1b — Absolute floor

```
G1b: candidate OOS MAR >= G1b_floor_adjusted
     G1b_floor = 0.500 (economically meaningful minimum)
     G1b_adj = G1b_floor + k_adj = 0.500 + 0.016 = 0.516
```

**G1b threshold: OOS MAR >= 0.516** ← LOCKED

### Negative-OOS cap

If both baseline OOS MAR AND candidate OOS MAR are negative → max status = CONDITIONAL-ADVANCE.
(Not applicable at current baseline 0.8386 — documented for protocol compliance.)

### N_OOS minimums

| Window | Minimum trades required |
|--------|------------------------|
| Full primary OOS (2020-present) | >= 30 |
| Sub-window A (2020-2022) | >= 12 |
| Sub-window B (2023-present) | >= 12 |

If any candidate fails N_OOS minimum: verdict = VN-THIN for that threshold (not INVALIDATED).

---

## OOS windows (pre-committed)

| Window | Years | Role |
|--------|-------|------|
| Primary OOS | 2020–2026 | Main gate (G1a, G1b) |
| Sub-window A | 2020–2022 | Consistency check |
| Sub-window B | 2023–2026 | Recency check |
| IS (in-sample) | 2013–2019 | Reference only — no gate decisions from IS |

---

## Verdict mapping (pre-committed)

| Outcome | Status assigned |
|---------|-----------------|
| Clears G1a AND G1b (both sub-windows pass N_OOS) | CALIBRATED → update S1 in knowledge.md |
| G1a fails, belief expressed (N_OOS >= 30) | INVALIDATED → update S1 in knowledge.md |
| N_OOS < 30 full OOS | VN-THIN → S1 stays SOURCED, defer |
| G1a passes, G1b fails | CALIBRATED-CONDITIONAL → flag, discuss with ChatGPT |

---

## Realism conventions (match baseline exactly)

- ADV participation cap: 10% of 30-day average daily volume
- Transaction costs: 40 bps round-trip
- Minimum hold: 3 days
- Entry: next-open after signal bar (T+1)
- Settlement: T+2
- Floor/ceiling: VN ±7% daily price band enforced
- No look-ahead: proximity computed on signal bar data only; 50d vol average shifted by 1

---

## Files this addendum locks

| File | Role |
|------|------|
| `pp_backtest/cortex_book2_s1_52wkhi.py` | Harness script — imports constants from cortex_book2_common.py |
| `pp_backtest/cortex_book2_common.py` | Shared infrastructure — G1a/G1b/k constants are hardcoded here |
| `knowledge/backtests/2026-07-04_cortex_book2_s1_52wkhi_prereg.md` | Parent pre-registration |

**Do not change G1A_THRESHOLD (0.9046), G1B_ADJ (0.516), or S1_PROXIMITY_THRESHOLDS ([0.85, 0.80, 0.75])
in cortex_book2_common.py after this addendum is written.**

---

## Cursor run command

```bash
# From repo root, .venv active:
cd "D:\V\0. VN Agent System"
python pp_backtest/cortex_book2_s1_52wkhi.py
```

Expected output:
- `data/research/cortex_book2/s1_52wkhi_report.md`
- `data/research/cortex_book2/s1_52wkhi_report_meta.json`

Expected runtime: ~5-10 minutes (dominated by panel load + capital simulation).
