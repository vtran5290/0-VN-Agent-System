# Path A Regime Reactivation Gap (Champion buy gate)

## 1) Current mapped benchmark row (latest weekly decision)

- Weekly date: **2026-03-20**
- Mapped VN30 daily date used: **2026-03-18**

## 2) Current values (VN30)

- close: **1868.84**
- MA50: **1998.90**
- close − MA50 gap: **−130.06** (below MA50)
- MA50 slope (20d): **−0.001436**

## 3) Which regime_ftd conditions are failing?

`regime_ftd = (close > MA50) AND (MA50 slope > 0)`

- close > MA50: **False**
- MA50 slope > 0: **False**

## 4) Scenario view (simple yes/no)

- If price rises above MA50 but MA50 slope stays negative → regime still off? **Yes**
- If MA50 slope turns positive but close stays below MA50 → regime still off? **Yes**
- regime_ftd turns on only when both are true: **(close > MA50) AND (MA50 slope > 0)**

## 5) Minimum close needed to exceed current MA50 (on mapped row)

- Need close **> 1998.90** → minimum **1998.91**

## Conclusion

**Champion can buy again only when VN30 close moves above its MA50 and the MA50 slope turns positive (no_new_positions already False on this week).**

