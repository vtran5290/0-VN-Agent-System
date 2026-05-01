# Path A Weekly Entry Debug 2024–2026

Period: 2024-01-01 to 2026-02-21.

## A. Reject breakdown after signal + trend + regime

- Total candidates after filters: 1218
- chosen_flag == True: 35

| reject_reason | count |
|---------------|-------|
| max_positions | 944 |
| ineligible | 144 |
| already_open | 95 |

## B. First 20 failed cases

| date | symbol | candidate_rank | adtv20 | ext_vs_ma10 | tightness_3w | stop_dist | free_heat_vnd | open_positions_count | cash_vnd | reject_reason |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025-02-07 | BIC | 7 | 4.422e+08 | 0.03913 | 0.05663 | nan | 1.5e+07 | 5 | 5.314e+08 | ineligible |
| 2025-02-07 | TCB | 12 | 2.211e+11 | 0.06229 | 0.06869 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | STB | 13 | 2.893e+11 | 0.05836 | 0.07703 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | MSH | 14 | 5.5e+09 | 0.04134 | 0.08462 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | VIB | 15 | 1.294e+11 | 0.04619 | 0.08475 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | SCS | 16 | 2.415e+10 | 0.01399 | 0.08653 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | TDP | 18 | 4.185e+09 | 0.01751 | 0.09159 | nan | 0 | 8 | 2.31e+08 | ineligible |
| 2025-02-07 | ELC | 19 | 1.034e+10 | 0.06828 | 0.09336 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | CTD | 20 | 5.89e+10 | 0.1744 | 0.09686 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | NNC | 22 | 3.6e+08 | 0.1216 | 0.1012 | nan | 0 | 8 | 2.31e+08 | ineligible |
| 2025-02-07 | PAN | 25 | 3.082e+10 | 0.1171 | 0.1135 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | DPR | 27 | 1.137e+10 | 0.06698 | 0.1165 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | SBT | 28 | 1.516e+10 | 0.1372 | 0.1168 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | BVB | 30 | 1.009e+10 | 0.1854 | 0.12 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | CSM | 31 | 1.937e+10 | 0.09116 | 0.1254 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | DRI | 34 | 6.177e+09 | 0.05055 | 0.1349 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | GEE | 37 | 5.842e+09 | 0.3296 | 0.1497 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | TAL | 39 | 8.478e+08 | 0.1349 | 0.1675 | nan | 0 | 8 | 2.31e+08 | ineligible |
| 2025-02-07 | LPB | 40 | 1.044e+11 | 0.1783 | 0.1785 | nan | 0 | 8 | 2.31e+08 | max_positions |
| 2025-02-07 | FRT | 41 | 8.793e+10 | 0.01176 | 0.1811 | nan | 0 | 8 | 2.31e+08 | max_positions |


## C. Plain-English conclusion

The main downstream blocker is 'max_positions'.

## D. Classification

- Classified as: **genuine portfolio constraint**

## E. Recommended next step

- Next step: Inspect representative failed candidates for the dominant reject_reason to decide whether it reflects a design choice or a correctable bug.
