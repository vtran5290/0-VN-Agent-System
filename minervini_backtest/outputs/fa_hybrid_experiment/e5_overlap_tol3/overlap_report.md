# E5 Overlap Matrix Report

## Inputs

- **breakout_dir**: `C:\Users\LOLII\Documents\V\0. VN Agent System\minervini_backtest\outputs\fa_hybrid_experiment\window30\hybrid_breakout_20d`
- **ma_dir**: `C:\Users\LOLII\Documents\V\0. VN Agent System\minervini_backtest\outputs\fa_hybrid_experiment\window30\hybrid_ma5_gt_ma10_gt_ma20`
- **out_dir**: `C:\Users\LOLII\Documents\V\0. VN Agent System\minervini_backtest\outputs\fa_hybrid_experiment\e5_overlap_tol3`
- **tolerance_days**: 3

## Overlap rate

- **n_breakout**: 720
- **n_ma**: 825
- **n_intersection**: 440
- **n_union**: 1105
- **overlap_rate**: 0.3982

## Group metrics (by horizon)

        group  horizon  trade_count  median_alpha  mean_alpha  sharpe_like
         BOTH        8           88      0.061780    0.088087     0.464292
         BOTH       10           88      0.047404    0.096357     0.435558
         BOTH       13           88      0.086799    0.120978     0.528842
         BOTH       16           88      0.102546    0.142600     0.582628
         BOTH       20           88      0.102897    0.163921     0.555388
         BOTH       -1          440      0.086337    0.122389     0.509711
BREAKOUT_ONLY        8           56      0.033682    0.055064     0.381853
BREAKOUT_ONLY       10           56      0.002078    0.054553     0.317232
BREAKOUT_ONLY       13           56      0.028843    0.044023     0.252021
BREAKOUT_ONLY       16           56      0.035642    0.068154     0.301251
BREAKOUT_ONLY       20           56      0.034246    0.096981     0.393540
BREAKOUT_ONLY       -1          280      0.026425    0.063755     0.323280
      MA_ONLY        8           77      0.033240    0.056583     0.400488
      MA_ONLY       10           77      0.025394    0.060342     0.394980
      MA_ONLY       13           77      0.029783    0.051799     0.301253
      MA_ONLY       16           77      0.041966    0.064409     0.308211
      MA_ONLY       20           77      0.033672    0.084685     0.372237
      MA_ONLY       -1          385      0.031052    0.063564     0.345803


## Correlations (BOTH group)

 horizon  corr_alpha  trade_count
       8    0.987925           88
      10    0.991741           88
      13    0.986828           88
      16    0.995396           88
      20    0.993896           88
      -1    0.991860          440


## Verdict

**Verdict**: `NO_OR`

- overlap_rate < 0.70: True (value=0.3982)
- ONLY group median_alpha > 0 on main horizons [10, 13]: True
- pooled corr < 0.75 (or >=2 horizons corr<0.75): False (pooled=0.9919)