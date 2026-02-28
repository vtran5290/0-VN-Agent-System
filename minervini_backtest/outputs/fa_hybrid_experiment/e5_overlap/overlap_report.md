# E5 Overlap Matrix Report

## Inputs

- **breakout_dir**: `minervini_backtest\outputs\fa_hybrid_experiment\window30\hybrid_breakout_20d`
- **ma_dir**: `minervini_backtest\outputs\fa_hybrid_experiment\window30\hybrid_ma5_gt_ma10_gt_ma20`
- **out_dir**: `minervini_backtest\outputs\fa_hybrid_experiment\e5_overlap`
- **tolerance_days**: 0

## Overlap rate

- **n_breakout**: 720
- **n_ma**: 825
- **n_intersection**: 205
- **n_union**: 1340
- **overlap_rate**: 0.1530

## Group metrics (by horizon)

        group  horizon  trade_count  median_alpha  mean_alpha  sharpe_like
         BOTH        8           41      0.098417    0.123172     0.552536
         BOTH       10           41      0.126414    0.145879     0.550980
         BOTH       13           41      0.119016    0.167491     0.672545
         BOTH       16           41      0.117781    0.179033     0.655233
         BOTH       20           41      0.098841    0.189358     0.619901
         BOTH       -1          205      0.111088    0.160987     0.606214
BREAKOUT_ONLY        8          103      0.038397    0.056166     0.384295
BREAKOUT_ONLY       10          103      0.008641    0.053917     0.321287
BREAKOUT_ONLY       13          103      0.044348    0.060624     0.322539
BREAKOUT_ONLY       16          103      0.069805    0.087622     0.396842
BREAKOUT_ONLY       20          103      0.059127    0.117401     0.442738
BREAKOUT_ONLY       -1          515      0.044516    0.075146     0.369428
      MA_ONLY        8          124      0.035695    0.061353     0.419017
      MA_ONLY       10          124      0.025329    0.063924     0.384648
      MA_ONLY       13          124      0.059318    0.068322     0.360337
      MA_ONLY       16          124      0.066125    0.088167     0.406354
      MA_ONLY       20          124      0.072386    0.114076     0.435155
      MA_ONLY       -1          620      0.043769    0.079168     0.393125


## Correlations (BOTH group)

 horizon  corr_alpha  trade_count
       8         1.0           41
      10         1.0           41
      13         1.0           41
      16         1.0           41
      20         1.0           41
      -1         1.0          205


## Verdict

**Verdict**: `NO_OR`

- overlap_rate < 0.70: True (value=0.1530)
- ONLY group median_alpha > 0 on main horizons [10, 13]: True
- pooled corr < 0.75 (or >=2 horizons corr<0.75): False (pooled=1.0000)