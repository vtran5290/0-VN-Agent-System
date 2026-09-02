# Gates Addendum — Cortex Book 2: S2 — O'Neil Breakout Volume Filter
# LOCKED 2026-07-05 — Do not adjust post-run

**Pre-registration file:** knowledge/backtests/2026-07-04_cortex_book2_s2_breakout_volume_prereg.md
**Harness script:** pp_backtest/cortex_book2_s2_volume.py
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

## VN-THIN pre-check result (LOCKED 2026-07-05)

**Verdict: NOT TRIGGERED — k=3 stands**

Empirical check run on `data/fireant_ssot/ta_ohlcv_panel.parquet` (OOS 2020-2026, ADV-qualified):

| Threshold | % OOS stock-days passing | Est. OOS filtered trades |
|-----------|--------------------------|--------------------------|
| volume >= 1.2× 50d avg | 29.1% | ~1,106 |
| volume >= 1.3× 50d avg | 24.6% | ~933 |
| volume >= 1.4× 50d avg | 20.8% | ~788 |

All three thresholds produce >>30 OOS trades. No threshold reduction required. k=3 locked as pre-registered.

---

## Candidate configuration (locked)

**Filter type:** Signal-bar volume multiple filter (vol / 50-day average)
**Signal stream:** A3_RS (frozen — no changes)
**Sizing:** D3 sector slot sizing (unchanged — 1.25× leading / 0.75× lagging)
**D4 cash yield:** 3.8% (same as baseline)
**Entry timing:** T+1 open after A3_RS signal bar (P1 honest execution — unchanged)

**k = 3** (three threshold candidates — multiple testing adjustment applied)
**Threshold labels and values:**

| Label | min_vol_mult | Interpretation |
|-------|-------------|----------------|
| `vol_1_2x` | 1.2 | Signal-bar volume >= 1.2× rolling 50d average |
| `vol_1_3x` | 1.3 | Signal-bar volume >= 1.3× rolling 50d average |
| `vol_1_4x` | 1.4 | Signal-bar volume >= 1.4× rolling 50d average |

**Volume average definition:** `vol_pos.rolling(50, min_periods=10).mean().shift(1)` — point-in-time;
excludes signal bar itself from the rolling average (shift(1) applied before lookup).
Signal-bar volume compared against this prior-50d average.

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
     G1b_floor = 0.500
     G1b_adj = 0.500 + 0.016 = 0.516
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
| Clears G1a AND G1b (both sub-windows pass N_OOS) | CALIBRATED → update S2 in knowledge.md |
| G1a fails, belief expressed (N_OOS >= 30) | INVALIDATED → update S2 in knowledge.md |
| N_OOS < 30 full OOS for a threshold | VN-THIN for that threshold → reduce k, recompute G1a/G1b |
| G1a passes, G1b fails | CALIBRATED-CONDITIONAL → flag, discuss with ChatGPT |

**Exception rule (from pre-reg):** If any individual threshold produces VN-THIN N_OOS < 30,
reduce k count for gate computation (e.g. k=2 if one of three fails) and recompute:
- New k_adj = 0.010 × log2(k_new)
- Recompute G1a and G1b with new k_adj
- Document the reduction in the report

---

## Realism conventions (match baseline exactly)

- ADV participation cap: 10% of 30-day average daily volume
- Transaction costs: 40 bps round-trip
- Minimum hold: 3 days
- Entry: next-open after signal bar (T+1)
- Settlement: T+2
- Floor/ceiling: VN ±7% daily price band enforced
- No look-ahead: vol_mult uses rolling average EXCLUDING signal bar (shift(1) enforced)

---

## Files this addendum locks

| File | Role |
|------|------|
| `pp_backtest/cortex_book2_s2_volume.py` | Harness script — imports constants from cortex_book2_common.py |
| `pp_backtest/cortex_book2_common.py` | Shared infrastructure — G1a/G1b/k constants hardcoded here |
| `knowledge/backtests/2026-07-04_cortex_book2_s2_breakout_volume_prereg.md` | Parent pre-registration |

**Do not change G1A_THRESHOLD (0.9046), G1B_ADJ (0.516), or S2_VOLUME_THRESHOLDS ([1.2, 1.3, 1.4])
in cortex_book2_common.py after this addendum is written.**

---

## Cursor run command

```bash
# From repo root, .venv active:
cd "D:\V\0. VN Agent System"
python pp_backtest/cortex_book2_s2_volume.py
```

Expected output:
- `data/research/cortex_book2/s2_volume_report.md`
- `data/research/cortex_book2/s2_volume_report_meta.json`

Expected runtime: ~5-10 minutes.

**Note:** Run S1 harness first (shared baseline build); S2 is structurally identical with volume filter substituted.
