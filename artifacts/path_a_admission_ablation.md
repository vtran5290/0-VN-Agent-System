# Path A Admission / Ranking Ablation

Ranking modes: current, extension_first, tightness_first, volume_thrust_first, liquidity_first, simple_composite.
max_positions: 8, 10, 12.

## Top 10 by MAR — 2018-2021

| ranking_mode | max_positions | mar | cagr | mdd | n_trades | chosen_rate | rejected_max_positions |
|---|---|---|---|---|---|---|---|
| current | 8 | nan | nan | nan | 0 | 0 | 0 |
| current | 10 | nan | nan | nan | 0 | 0 | 0 |
| current | 12 | nan | nan | nan | 0 | 0 | 0 |
| extension_first | 8 | nan | nan | nan | 0 | 0 | 0 |
| extension_first | 10 | nan | nan | nan | 0 | 0 | 0 |
| extension_first | 12 | nan | nan | nan | 0 | 0 | 0 |
| tightness_first | 8 | nan | nan | nan | 0 | 0 | 0 |
| tightness_first | 10 | nan | nan | nan | 0 | 0 | 0 |
| tightness_first | 12 | nan | nan | nan | 0 | 0 | 0 |
| volume_thrust_first | 8 | nan | nan | nan | 0 | 0 | 0 |

## Top 10 by MAR — 2024-2026Q1

| ranking_mode | max_positions | mar | cagr | mdd | n_trades | chosen_rate | rejected_max_positions |
|---|---|---|---|---|---|---|---|
| liquidity_first | 8 | 1.028 | 0.155 | -0.1508 | 23 | 0.01396 | 1301 |
| liquidity_first | 12 | 0.9929 | 0.1744 | -0.1756 | 33 | 0.02002 | 763 |
| liquidity_first | 10 | 0.8621 | 0.1482 | -0.1719 | 31 | 0.01881 | 1160 |
| simple_composite | 12 | 0.7334 | 0.1501 | -0.2047 | 38 | 0.02306 | 695 |
| volume_thrust_first | 12 | 0.6664 | 0.1036 | -0.1554 | 34 | 0.02063 | 807 |
| volume_thrust_first | 10 | 0.6344 | 0.09648 | -0.1521 | 30 | 0.0182 | 1102 |
| volume_thrust_first | 8 | 0.5972 | 0.09482 | -0.1588 | 27 | 0.01638 | 1307 |
| simple_composite | 10 | 0.5384 | 0.1163 | -0.2161 | 37 | 0.02245 | 1117 |
| simple_composite | 8 | 0.4354 | 0.07613 | -0.1748 | 31 | 0.01881 | 1305 |
| extension_first | 8 | 0.3869 | 0.07138 | -0.1845 | 44 | 0.0267 | 1305 |

## Top 10 by MAR — 2022-2024

| ranking_mode | max_positions | mar | cagr | mdd | n_trades | chosen_rate | rejected_max_positions |
|---|---|---|---|---|---|---|---|
| extension_first | 12 | 0.3521 | 0.03159 | -0.08971 | 36 | 0.01725 | 415 |
| extension_first | 8 | 0.3309 | 0.02894 | -0.08745 | 25 | 0.01198 | 835 |
| extension_first | 10 | 0.2322 | 0.02362 | -0.1017 | 31 | 0.01485 | 729 |
| simple_composite | 8 | -0.08187 | -0.009406 | -0.1149 | 28 | 0.01342 | 823 |
| simple_composite | 10 | -0.09514 | -0.01146 | -0.1204 | 36 | 0.01725 | 638 |
| current | 10 | -0.111 | -0.01308 | -0.1179 | 36 | 0.01725 | 524 |
| tightness_first | 10 | -0.111 | -0.01308 | -0.1179 | 36 | 0.01725 | 524 |
| current | 8 | -0.1137 | -0.01345 | -0.1182 | 31 | 0.01485 | 818 |
| tightness_first | 8 | -0.1137 | -0.01345 | -0.1182 | 31 | 0.01485 | 818 |
| current | 12 | -0.1218 | -0.01463 | -0.1201 | 40 | 0.01917 | 348 |

## Top 10 by MAR — full_sample

| ranking_mode | max_positions | mar | cagr | mdd | n_trades | chosen_rate | rejected_max_positions |
|---|---|---|---|---|---|---|---|
| volume_thrust_first | 8 | 0.1934 | 0.02234 | -0.1155 | 52 | 0.00464 | 2117 |
| volume_thrust_first | 12 | 0.1932 | 0.02352 | -0.1217 | 71 | 0.006336 | 1012 |
| volume_thrust_first | 10 | 0.1822 | 0.02265 | -0.1243 | 64 | 0.005711 | 1800 |
| liquidity_first | 8 | 0.1146 | 0.0177 | -0.1545 | 51 | 0.004551 | 2125 |
| liquidity_first | 12 | 0.1117 | 0.02022 | -0.181 | 72 | 0.006425 | 1033 |
| extension_first | 8 | 0.09775 | 0.01804 | -0.1845 | 67 | 0.005979 | 2140 |
| liquidity_first | 10 | 0.09352 | 0.01642 | -0.1756 | 66 | 0.00589 | 1705 |
| simple_composite | 12 | 0.09273 | 0.01992 | -0.2149 | 81 | 0.007228 | 908 |
| extension_first | 12 | 0.07387 | 0.01477 | -0.2 | 97 | 0.008656 | 415 |
| extension_first | 10 | 0.06791 | 0.01364 | -0.2009 | 87 | 0.007764 | 1696 |

## Top 10 by robustness (avg MAR − penalties)

| ranking_mode | max_positions | robustness | mar | n_trades | chosen_rate |
|---|---|---|---|---|---|
| liquidity_first | 8 | 0.3232 | 0.3232 | 102 | 0.007981 |
| liquidity_first | 12 | 0.3082 | 0.3082 | 143 | 0.01116 |
| extension_first | 8 | 0.2718 | 0.2718 | 136 | 0.01116 |
| liquidity_first | 10 | 0.2584 | 0.2584 | 132 | 0.01037 |
| simple_composite | 12 | 0.2306 | 0.2306 | 159 | 0.01236 |
| extension_first | 12 | 0.2167 | 0.2167 | 195 | 0.01588 |
| volume_thrust_first | 12 | 0.2159 | 0.2159 | 141 | 0.01105 |
| volume_thrust_first | 10 | 0.2031 | 0.2031 | 126 | 0.009812 |
| volume_thrust_first | 8 | 0.1958 | 0.1958 | 105 | 0.00837 |
| extension_first | 10 | 0.18 | 0.18 | 177 | 0.0146 |

## Ranking vs max_positions

Does ranking matter more than max_positions? See summary.

## chosen_rate by max_positions

| max_positions | chosen_rate | mar |
|---|---|---|
| 8 | 0.009821 | 0.1444 |
| 10 | 0.01198 | 0.123 |
| 12 | 0.01305 | 0.1625 |
