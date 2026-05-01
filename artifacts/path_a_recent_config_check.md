# Path A Recent Config Check

Fresh runs: 2024-01-01 to 2026-02-21 (recent) and 2022-01-01 to 2024-12-31 (mid-period). Direct comparison using current code wiring (Champion = default).

## 1. Champion vs Challenger vs baseline_old — Recent period (2024-01-01 to 2026-02-21)

| config       | MAR   | CAGR   | MDD    | n_trades | trades_per_month | chosen_rate | rejected_max_positions |
|-------------|-------|--------|--------|----------|------------------|-------------|------------------------|
| champion    | 0.44  | 8.10%  | -18.4% | 44       | 1.69             | 0.0267      | 1,298                  |
| challenger  | 0.75  | 15.50% | -20.6% | 39       | 1.50             | 0.0237      | 607                    |
| baseline_old| 0.06  | 0.66%  | -10.8% | 38       | ~1.46            | ~0.023      | 1,296                  |

## 2. MAR / CAGR / MDD (recent period)

- **Champion:** MAR 0.44, CAGR 8.10%, MDD -18.4%
- **Challenger:** MAR 0.75, CAGR 15.50%, MDD -20.6%
- **baseline_old:** MAR 0.06, CAGR 0.66%, MDD -10.8%

## 3. chosen_rate (recent period)

- Champion: 0.0267 (44 entries / 1,648 post-regime candidates)
- Challenger: 0.0237 (39 / 1,648)
- baseline_old: ~0.023 (38 / 1,648). Champion has slightly higher chosen_rate with same 8 slots (extension_first ranking).

## 4. rejected_max_positions (recent period)

- Champion: 1,298
- Challenger: 607 (12 slots → fewer rejections)
- baseline_old: 1,296

## 5. trades_per_month (recent period)

- Champion: 1.69
- Challenger: 1.50
- baseline_old: ~1.46. Champion has more trades in this window.

## 6. Mid-period (2022-01-01 to 2024-12-31) — context

| config       | MAR   | CAGR   | MDD    | n_trades | rejected_max_positions |
|-------------|-------|--------|--------|----------|------------------------|
| champion    | 0.34  | 3.29%  | -9.7%  | 43       | 1,518                  |
| challenger  | 0.20  | 2.84%  | -14.0% | 62       | 772                    |
| baseline_old| 0.77  | 7.19%  | -9.4%  | 39       | 1,513                  |

On 2022-2024, baseline_old had the highest MAR (0.77); Champion was 0.34; Challenger 0.20. So Champion is not best in every sub-period but was chosen for robustness across periods and for recent-period improvement over baseline_old.

## 7. Plain-English conclusion

- **Champion still primary.** On the recent period (2024–2026), Champion (MAR 0.44, 44 trades) clearly beats baseline_old (MAR 0.06, 38 trades) and has higher chosen_rate and more trades. Champion remains the right production default.
- **Challenger under watch.** Challenger has the best recent-period MAR (0.75) and CAGR (15.5%) with fewer rejected_max_positions (607). It is a strong research branch; keep running the monitoring snapshot to see if this edge holds.
- **baseline_old remains deprecated.** Recent-period MAR (0.06) and CAGR (0.66%) are far below Champion and Challenger; do not use for production.
