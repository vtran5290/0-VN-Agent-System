# Decision layer (from decision_matrix + gate waterfall)

## Core thesis (from gate waterfall)
T? (check waterfall manually)

## Survivors (fee=30, min_hold=3)
- **Core:** [chọn 1 từ Survivors]
- **Backup:** [chọn 1 backup]
- **Experimental:** M9/M10/M11 tùy thesis

## Top 3 actions
1. [ ] Deploy: run scanner (Tier A) với core version; Tier B checklist 5 phút/mã
2. [ ] Sweep: (nếu chưa survivor) I1 M9+M6 / I2 M4+M10 / I3 M7+M4
3. [ ] Refactor: (nếu T1) simplify VCP to soft filter; (nếu T2) tune retest window

## Top 3 risks
1. **Edge source:** confirm from waterfall (see thesis above)
2. **Concentration:** top10_pct_pnl < 60% on holdout (run deploy_gates_check D2)
3. **Regime dependency:** val/holdout both exp_r>0 (run deploy_gates_check D1); consider M11

## Watchlist update
Scan hàng tuần: version **M4 or M3** (core). Backup for confirmation: M4 or M3.
