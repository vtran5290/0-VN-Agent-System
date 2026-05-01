# Path A Governance Decision — Champion vs Tuned Challenger

## Current configs

- **Champion (default Path A)**  
  - ranking_mode = `extension_first`  
  - max_positions = 8  
  - risk_per_trade = 0.005  
  - max_heat = 0.04  

- **Tuned Challenger (research branch)**  
  - ranking_mode = `simple_composite`  
  - max_positions = 12  
  - risk_per_trade = 0.004  
  - max_heat = 0.04  

## Evidence base

- **Full-sample 2012-01-01 to 2026-02-21** (from `path_a_champion_vs_challenger.csv` and tuned risk-shape runs):
  - Champion: MAR ≈ 0.51, MDD ≈ −25.5%, CAGR ≈ 13.1%.
  - Tuned Challenger: MAR ≈ 0.52, MDD ≈ −26.6%, CAGR ≈ 13.8%.
  - **Interpretation:** Tuned Challenger gains a bit of CAGR but with slightly *worse* drawdown and only marginal MAR improvement.

- **Mid-recent 2022-01-01 to 2024-12-31**:
  - Champion: MAR ≈ 0.34, MDD ≈ −9.7%, CAGR ≈ 3.3%.
  - Tuned Challenger: MAR ≈ 0.25, MDD ≈ −14.1%, CAGR ≈ 3.5%.
  - **Interpretation:** Champion has clearly cleaner risk/return; tuned Challenger trades higher drawdown for worse MAR.

- **Recent 2024-01-01 to 2026-02-21**:
  - Champion: MAR ≈ 0.44, MDD ≈ −18.4%, CAGR ≈ 8.1%.
  - Tuned Challenger: MAR ≈ 0.94, MDD ≈ −18.3%, CAGR ≈ 17.2%.
  - **Interpretation:** Tuned Challenger is much stronger in this recent slice, with similar drawdown.

- **Rolling 6m/12m windows (Champion vs Tuned Challenger)**:
  - As of this note, the dedicated tuned-Challenger rolling validation run (`run_path_a_tuned_challenger_validation.py`) is still in progress; the final rolling artifacts
    `path_a_tuned_challenger_rolling_review.csv` / `.md` are **not yet fully written**.
  - **Therefore:** no additional quantitative rolling evidence beyond the existing Champion vs (old) Challenger review is available yet for Tuned Challenger.

## Governance decision rule

- **Default rule:**  
  - **Keep Champion as default** unless a Challenger configuration shows:
    1. **Consistent rolling superiority on MAR** (wins a large share of recent 6m/12m windows), **and**
    2. **MDD not materially worse** than Champion (no more than ~3–5 percentage points deeper on typical windows), and
    3. **Full-sample MAR not clearly worse** than Champion.

- **Formal baseline review trigger:**  
  - Open a **formal baseline review** of Tuned Challenger *only if*:
    - In the tuned rolling review, Tuned Challenger wins a **clear majority** of recent 6m/12m windows on MAR, **and**
    - Its average MDD across those windows is **no worse than Champion by more than ~3–4 ppts**, preferably better.

## Status of Tuned Challenger

- Given the current evidence:
  - Tuned Challenger is **strong in the very recent period** (2024–2026Q1) with a large MAR edge and similar drawdown.
  - Over **full history and 2022–2024**, it **does not deliver a clean risk improvement** vs Champion; MDD is slightly worse full-sample and materially worse in 2022–2024, with lower MAR.
  - Dedicated tuned-Challenger rolling artifacts are **still pending**, so there is **no confirmed rolling-win pattern** yet.

- **Governance status:**  
  - **Champion remains the default Path A configuration.**  
  - **Tuned Challenger remains “under watch” as a research branch**, not yet a formal baseline-review candidate.

## Simple governance rule (for future checks)

- **Keep Champion as default** if **either**:
  - Tuned Challenger **does not clearly win** both:
    - MAR consistency on rolling 6m/12m windows, **and**
    - Acceptable MDD (not materially worse than Champion),  
  **or**
  - Tuned Challenger’s full-sample MAR is only marginally better (or worse) while MDD is not clearly improved.

- **Open formal baseline review** for Tuned Challenger only when:
  - Tuned Challenger wins a **large share of recent rolling windows on MAR** (e.g. ≥60% of the last 10 windows), **and**
  - Its rolling and full-sample MDD are **not materially worse** than Champion (ideally shallower), **and**
  - Its full-sample MAR is **at least comparable** to Champion.

Under the current data, these conditions are **not yet met**, so **Champion stays default and Tuned Challenger stays under watch** until the tuned rolling validation artifacts are available and re-evaluated.

