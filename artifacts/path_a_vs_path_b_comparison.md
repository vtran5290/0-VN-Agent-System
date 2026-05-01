# Path A vs Path B Comparison

## Strategy identity

- **Path A:** Weekly pivot / accumulation system (weekly_pp on weekly bars, weekly EMA21/MA50, next week open).
- **Path B:** True daily Pocket Pivot (daily PP, daily EMA21>MA50, next day open).

## Performance by period

     period   cagr_a    cagr_b     mdd_a     mdd_b    mar_a     mar_b  n_trades_a  n_trades_b  trades_per_month_a  trades_per_month_b  final_equity_a  final_equity_b  avg_heat_a  avg_heat_b  avg_gross_exposure_a  avg_gross_exposure_b
  2018-2021 0.220346  0.004207 -0.122474 -0.182662 1.799125  0.023030          43         223            0.883562            4.585332    2.211811e+09    1.016910e+09    0.018717    0.014820              0.438431              0.293016
  2022-2024 0.071942 -0.027296 -0.093456 -0.154584 0.769800 -0.176579          39         169            1.068493            4.642857    1.230848e+09    9.205875e+08    0.018096    0.014431              0.360965              0.275144
2025-2026Q1 0.007143 -0.017492 -0.034505 -0.183573 0.207027 -0.095285           6         100            0.432692            7.371007    1.007944e+09    9.805285e+08    0.005574    0.022797              0.107850              0.433532
full_sample 0.114206  0.023295 -0.222214 -0.379427 0.513944  0.061394         219         806            1.272023            4.690592    4.596901e+09    1.384030e+09    0.022957    0.015929              0.450237              0.304183

## Conclusion

Compare CAGR, MDD, MAR and trades_per_month by period to decide which path to prioritize.
