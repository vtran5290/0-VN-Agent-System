# VIN Group + EMA-cloud / price-level pipeline — research baseline (SSOT)

**Status:** working truth for interpretation and robustness checks until code-backed evidence updates it.  
**Scope:** Vietnam equities research that uses EMA-cloud + price-level logic, breakout/retest clusters, or aggregate success rates where Vingroup names matter.

---

## Symbols in scope

| Symbol | Role in baseline |
|--------|-------------------|
| **VIC** | Structural outlier; special-case bucket |
| **VHM** | Mixed; not clean retest confirmation |
| **VRE** | Systematic signal stress / falsification bucket |
| **VPL** | **Exclude** from event studies, backtests, regime aggregates until ≥ **252** daily bars |

**Default exclusion sets**

- `ex_vin_symbols = ["VIC", "VHM", "VRE"]`
- `exclude_vpl_if_bars_lt_252 = True`

---

## Working interpretation (not standalone “proof” of edge)

### 1) VIC — structural outlier

- **FACT (user research baseline):** VIC breakout cluster (e.g. March 2025) showed very high success and large returns (~+77% to +131% in ~63 days in that narrative).
- **INTERPRETATION:** tied to Vingroup restructuring / policy / VinFast / real-estate re-rating dynamics — **not** evidence that EMA-cloud + price levels has broad, repeatable edge across names and years.

### 2) VHM — mixed

- **INTERPRETATION:** breakouts may be helped by a 2025 mega-move; **retests are often poor / catastrophic**. Do not cite VHM alone as “retest quality works.”

### 3) VRE — adversarial

- **INTERPRETATION:** many false breakouts; breakout / retest / reclaim behavior **poor**. Use as **stress-test / falsification** case, not confirmation.

### 4) VPL — exclude until history

- **RULE:** no VPL in event studies, walk-forward folds, or regime panels until **252** daily bars exist.

### 5) Aggregate distortion

- **INTERPRETATION:** VIN names may **not** massively change **full-sample breakout success rate** when excluded, but they **can heavily distort return distribution**, especially **2025+**.
- **Implication:** a small number of VIN mega-winners can make OOS folds or return summaries look better than the “general” signal.

### 6) VNINDEX regime overlay (2025–2026)

- **INTERPRETATION:** cap-weighted **VNINDEX** can partly reflect “Vingroup is going up.” A stock passing VNINDEX R4/R5 in mid-2025 **does not** necessarily mean broad market strength.
- **Policy:** do **not** treat cap-weighted VNINDEX EMA overlay as the sole market-health filter for conclusions in 2025–2026; prefer **breadth-based** proxies (see below).

---

## Non-negotiable rules for future runs

### A) Universe — always two cuts where results matter

1. **Full universe**
2. **ex-VIN** = exclude `VIC`, `VHM`, `VRE`  
3. **Exclude VPL** until 252 bars

### B) Reporting

- Always report **full** and **ex-VIN** (and `vin_only` when sample size is meaningful).
- If mean return, tails, or OOS fold outcomes **materially** differ → call it out explicitly.
- Never summarize “the strategy works in 2025” **without** isolating VIN effects.

### C) Signal interpretation

- Do **not** let VIC’s 2025 cluster justify a **general** bullish conclusion about the signal.
- Treat **VIC** as structural-event bucket; **VRE** as adversarial bucket.

### D) Regime filter

- Add warning when using cap-weighted VNINDEX as filter:

  > “VNINDEX cap-weighted filter may be distorted by Vingroup concentration in 2025–2026.”

- Prefer breadth-style checks where possible, e.g.:

  1. % of universe above EMA50  
  2. Advance–decline slope (or proxy from panel)  
  3. Median 20-day stock return cross-section  

### E) Model selection / robustness

- If a parameter set looks good **only** because it catches VIC → mark **VIN-contaminated**.
- If it stays **decent ex-VIN** → stronger evidence.

---

## Minimum columns for new result tables (when relevant)

| Column | Meaning |
|--------|---------|
| `metric_full` | Full universe |
| `metric_ex_vin` | Excluding VIC, VHM, VRE |
| `metric_vin_only` | VIC/VHM/VRE subset if n meaningful |
| `note_on_distortion` | Short flag if VIN drives tails / folds |

---

## Default experiment priorities (when user asks “what next”)

1. Matched-random baseline — **full + ex-VIN**  
2. Ablation: cloud-only vs cloud+levels — **full + ex-VIN**  
3. Breadth-based regime replacement for cap-weighted VNINDEX overlay  
4. Single-split OOS on **2025–2026 ex-VIN**  
5. Episode / de-duplication testing (already canonical elsewhere)  
6. Simpler triggers (e.g. recent-base / simple base-high breakout) vs broad clustered levels  

---

## Response convention (for any assistant in this repo)

- Separate **FACT** vs **INTERPRETATION**
- State whether numbers are **full-universe** or **ex-VIN**
- Flag **VIN-contaminated** conclusions when unsure, and name the **exact** test to de-contaminate (e.g. re-run fold table ex-VIN, exclude March–May 2025 VIC window, etc.)
- Prefer **robustness** over headline returns

---

## File purpose

This file is the **single written baseline** for Vin + EMA-cloud research judgment. Cursor rules and `AGENTS.md` / `CLAUDE.md` point here so future sessions load the same policy without re-auditing the whole repo.
