# Path A Governance Monitor

## 1. Current default

- Champion: **default Path A** (extension_first, max_positions=8).
- Tuned Challenger: **under watch** (simple_composite, max_positions=12, max_heat=0.04, risk_per_trade=0.004).

## 2. Recent-period comparison

- Period: 2024-01-01_to_2026-02-21

| config | CAGR | MDD | MAR |
|--------|------|-----|-----|
| Champion | 14.41% | -18.37% | 0.7845 |
| Tuned Challenger | 9.69% | -20.97% | 0.4622 |

Chosen/admission pressure (if snapshot available):

| config | chosen_rate | rejected_max_positions |
|--------|-------------|------------------------|
| Champion | 0.02781 | 1332 |
| Tuned Challenger | 0.02604 | 607 |

## 3. Rolling evidence

### 6m windows

- Champion MAR wins: 5
- Tuned Challenger MAR wins: 9

| config | avg_MAR_6m | avg_MDD_6m |
|--------|------------|-----------|
| Champion | 2.0276 | -6.13% |
| Tuned Challenger | 4.4895 | -8.30% |

### 12m windows

- Champion MAR wins: 7
- Tuned Challenger MAR wins: 9

| config | avg_MAR_12m | avg_MDD_12m |
|--------|-------------|------------|
| Champion | 1.4199 | -9.77% |
| Tuned Challenger | 2.8742 | -12.50% |

## 4. Governance rule status

- Does Tuned Challenger qualify for **formal baseline review**? **no**.
- 6m rolling win rate (Tuned Challenger): 64.3%; 12m: 56.2%.
- MDD acceptable? 6m: True, 12m: True.
- Recent MAR acceptable (Tuned vs Champion)? False.

### Why it does / does not qualify

- Although Tuned Challenger has some rolling wins, its average MDD is meaningfully worse on key windows, and/or its recent MAR is not clearly superior. It therefore does **not** meet the promotion rule for formal baseline review.

## 5. What would change the decision

- Tuned Challenger would need to show **repeated 6m/12m rolling superiority on MAR** (e.g. ≥60% of recent windows)
  **and** keep average MDD no more than ~3–4 percentage points worse than Champion, ideally better.
- Full-sample and recent-period MAR should be at least comparable to Champion, not structurally lower.

## 6. Final operating recommendation

- **Keep Champion as default** and **keep Tuned Challenger under watch**. Re-run this governance monitor periodically; only open formal review if the rolling and risk profile shifts clearly in favor of Tuned Challenger.
