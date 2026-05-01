# Path A Champion vs Tuned Challenger — Full-Sample Comparison

Configs:

- **Champion**: extension_first, max_positions=8, risk_per_trade=0.005, max_heat=0.04
- **Challenger_tuned**: simple_composite, max_positions=12, risk_per_trade=0.004, max_heat=0.04

## Period: 2012-01-01_to_2026-02-21

| config_name | ranking_mode | max_positions | CAGR | MDD | MAR | n_trades | trades_per_month | final_equity | avg_heat | avg_gross_exposure |
|-------------|--------------|---------------|------|-----|-----|----------|------------------|--------------|----------|--------------------|
| champion | extension_first | 8 | 1.80% | -18.45% | 0.0977 | 67 | 0.39 | 1286790090 | 0.0050 | 0.1006 |
| challenger_tuned | simple_composite | 12 | 0.73% | -22.10% | 0.0328 | 88 | 0.51 | 1107367201 | 0.0045 | 0.1090 |

## Period: 2022-01-01_to_2024-12-31

| config_name | ranking_mode | max_positions | CAGR | MDD | MAR | n_trades | trades_per_month | final_equity | avg_heat | avg_gross_exposure |
|-------------|--------------|---------------|------|-----|-----|----------|------------------|--------------|----------|--------------------|
| champion | extension_first | 8 | 2.85% | -8.75% | 0.3264 | 25 | 0.68 | 1087212324 | 0.0102 | 0.2204 |
| challenger_tuned | simple_composite | 12 | -1.77% | -14.12% | -0.1252 | 43 | 1.18 | 948380178 | 0.0103 | 0.2418 |

## Period: 2024-01-01_to_2026-02-21

| config_name | ranking_mode | max_positions | CAGR | MDD | MAR | n_trades | trades_per_month | final_equity | avg_heat | avg_gross_exposure |
|-------------|--------------|---------------|------|-----|-----|----------|------------------|--------------|----------|--------------------|
| champion | extension_first | 8 | 12.71% | -18.45% | 0.6885 | 67 | 2.57 | 1286790090 | 0.0296 | 0.6625 |
| challenger_tuned | simple_composite | 12 | 8.97% | -20.93% | 0.4285 | 84 | 3.22 | 1198512863 | 0.0304 | 0.7160 |

