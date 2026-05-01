# Path A Monitoring Snapshot

Period: 2024-01-01 to 2026-03-16

## 1. Champion vs Challenger (recent period)

| config_name | MAR | CAGR | MDD | n_trades | chosen_rate | rejected_max_positions |
|-------------|-----|------|-----|----------|-------------|------------------------|
| champion | 0.5414 | 9.94% | -18.37% | 47 | 0.02781 | 1332 |
| challenger | 0.6887 | 14.19% | -20.61% | 44 | 0.02604 | 607 |

## 2. chosen_rate difference

- Challenger chosen_rate − Champion chosen_rate = -0.001775
- Champion: 0.02781; Challenger: 0.02604

## 3. rejected_max_positions difference

- Champion rejected_max_positions − Challenger = 725 (Challenger has more slots, so fewer rejections expected)
- Champion: 1332; Challenger: 607

## 4. Recommendation

- **Keep Champion as primary** (extension_first, 8 slots) for production.
- **Keep Challenger under watch** (simple_composite, 12 slots) as research branch; re-run this snapshot periodically to compare recent-period MAR and admission pressure.
