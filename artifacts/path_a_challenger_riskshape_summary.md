# Path A Challenger Risk-Shaping — Summary

## 1. Can Challenger keep better recent/rolling behavior with lower MDD?

Partially: some risk-shaped configs reduce MDD but may give up some MAR.

## 2. Best risk-shaped Challenger config

- **Best by full-sample MAR:** max_positions=12, max_heat=0.04, risk_per_trade=0.005
- **Best MAR among configs with materially better MDD:** max_positions=10, max_heat=0.03, risk_per_trade=0.004 (MAR=0.0591, MDD=-19.03%)

## 3. Does any risk-shaped Challenger satisfy the spirit of the promotion rule better?

No: either MDD does not improve enough or MAR drops too much.

## 4. Should Challenger stay under watch only, or move to formal baseline review candidate?

**Stay under watch only.** Re-run rolling review with the best risk-shaped Challenger before considering promotion.
