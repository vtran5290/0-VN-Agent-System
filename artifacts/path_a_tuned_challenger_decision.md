# Path A Tuned Challenger — Final Decision

Configs under review:

- **Champion**: extension_first, 8 positions, risk_per_trade=0.005, max_heat=0.04
- **Challenger_tuned**: simple_composite, 12 positions, risk_per_trade=0.004, max_heat=0.04

## 1. Did the tuned Challenger materially improve risk?

- Champion MDD (ref period): -18.45%
- Challenger_tuned MDD (ref period): -22.10%
- **Result:** Tuned Challenger does **not** improve drawdown vs Champion.

## 2. Is it still under watch only, or does it now deserve formal baseline review?

- Rolling MAR wins — Champion: 8, Challenger_tuned: 12 (win rate for Challenger_tuned ≈ 60.0%).
- **Conclusion:** Tuned Challenger does **not yet** satisfy the spirit of the promotion rule; it remains **under watch only**.

## 3. Should Champion remain default?

- **Recommendation:** **Keep Champion as default Path A.** Tuned Challenger stays as a monitored research branch; re-run this validation after more out-of-sample data.
