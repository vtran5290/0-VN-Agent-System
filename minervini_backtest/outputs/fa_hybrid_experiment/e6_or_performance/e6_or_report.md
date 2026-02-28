# E6 OR Performance Report

## Inputs

- **breakout_dir**: `C:\Users\LOLII\Documents\V\0. VN Agent System\minervini_backtest\outputs\fa_hybrid_experiment\window30\hybrid_breakout_20d`
- **ma_dir**: `C:\Users\LOLII\Documents\V\0. VN Agent System\minervini_backtest\outputs\fa_hybrid_experiment\window30\hybrid_ma5_gt_ma10_gt_ma20`
- **out_dir**: `C:\Users\LOLII\Documents\V\0. VN Agent System\minervini_backtest\outputs\fa_hybrid_experiment\e6_or_performance`
- **tolerance_days**: 3
- **max_trade_increase_pct**: 25.0

## Per-strategy metrics by horizon

strategy                             variant  horizon  median_yearly_alpha   sharpe  trade_count
  Hybrid OR_breakout_20d_ma5_gt_ma10_gt_ma20        8             0.045713 0.436635          221
  Hybrid                        breakout_20d        8             0.063489 0.431965          144
  Hybrid                 ma5_gt_ma10_gt_ma20        8             0.051050 0.449137          165
  Hybrid OR_breakout_20d_ma5_gt_ma10_gt_ma20       10             0.013953 0.399959          221
  Hybrid                        breakout_20d       10             0.040970 0.391668          144
  Hybrid                 ma5_gt_ma10_gt_ma20       10             0.046182 0.424485          165
  Hybrid OR_breakout_20d_ma5_gt_ma10_gt_ma20       13             0.018737 0.397253          221
  Hybrid                        breakout_20d       13             0.072031 0.428013          144
  Hybrid                 ma5_gt_ma10_gt_ma20       13             0.086091 0.441859          165
  Hybrid OR_breakout_20d_ma5_gt_ma10_gt_ma20       16             0.049376 0.426475          221
  Hybrid                        breakout_20d       16             0.060139 0.472596          144
  Hybrid                 ma5_gt_ma10_gt_ma20       16             0.065991 0.470209          165
  Hybrid OR_breakout_20d_ma5_gt_ma10_gt_ma20       20             0.075615 0.463701          221
  Hybrid                        breakout_20d       20             0.088842 0.493985          144
  Hybrid                 ma5_gt_ma10_gt_ma20       20             0.084614 0.482000          165


## OR vs best(single) per horizon

- **Horizon 8w**:
  OR alpha=0.0457, best_single alpha=0.0635, delta=-0.0178
  OR sharpe=0.4366, best_single sharpe=0.4320, delta=0.0047
  OR trades=221 vs best_single trades=144, delta=77 (limit=180.0)
  flags: alpha_improved=False, sharpe_ok=True, trades_ok=False
- **Horizon 10w**:
  OR alpha=0.0140, best_single alpha=0.0462, delta=-0.0322
  OR sharpe=0.4000, best_single sharpe=0.4245, delta=-0.0245
  OR trades=221 vs best_single trades=165, delta=56 (limit=206.2)
  flags: alpha_improved=False, sharpe_ok=False, trades_ok=False
- **Horizon 13w**:
  OR alpha=0.0187, best_single alpha=0.0861, delta=-0.0674
  OR sharpe=0.3973, best_single sharpe=0.4419, delta=-0.0446
  OR trades=221 vs best_single trades=165, delta=56 (limit=206.2)
  flags: alpha_improved=False, sharpe_ok=False, trades_ok=False
- **Horizon 16w**:
  OR alpha=0.0494, best_single alpha=0.0660, delta=-0.0166
  OR sharpe=0.4265, best_single sharpe=0.4702, delta=-0.0437
  OR trades=221 vs best_single trades=165, delta=56 (limit=206.2)
  flags: alpha_improved=False, sharpe_ok=False, trades_ok=False
- **Horizon 20w**:
  OR alpha=0.0756, best_single alpha=0.0888, delta=-0.0132
  OR sharpe=0.4637, best_single sharpe=0.4940, delta=-0.0303
  OR trades=221 vs best_single trades=144, delta=77 (limit=180.0)
  flags: alpha_improved=False, sharpe_ok=False, trades_ok=False


## Verdict

**Verdict**: `NO_OR`

- alpha_improved_enough (>= 3 horizons): False
- sharpe_not_worse_0_02 (all horizons): False
- trades_not_increase_too_much (all horizons, max_trade_increase_pct=25.0): False