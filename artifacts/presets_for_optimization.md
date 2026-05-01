# Berkshire-style FA cohort presets — for parameter optimization

Context: Vietnam stock backtest. Each preset is a set of fundamental filters (sales growth, ROE, D/E, gross margin, earnings growth, acceleration flags). Backtest ranks stocks by these filters, forms cohorts, and measures **median alpha vs benchmark** over multiple holding horizons (weeks).

**Goal:** Propose new preset(s) or adjust existing parameters to improve median alpha across horizons (especially 104w and 156w) while keeping verdict PASS (no large negative alpha at any horizon).

## Parameter definitions (for optimization)

| Parameter | Type | Description | Typical range / notes |
|-----------|------|-------------|------------------------|
| sales_yoy_min | number or null | Minimum YoY sales growth (%) | 0–15; null = no filter |
| roe_min | number | Minimum ROE (%) | 10–20 |
| debt_to_equity_max | number | Maximum D/E ratio | 0.8–1.5 |
| gross_margin_min | number | Minimum gross margin (0–1) | 0.10–0.30 |
| earnings_yoy_min | number or null | Minimum YoY earnings growth (%) | 0–10; null = no filter |
| eps_yoy_min | number or null | Minimum YoY EPS growth (%) | null in current presets |
| margin_yoy_min | number | Minimum YoY margin change | 0 in current presets |
| require_eps_accel | boolean | Require EPS acceleration (q/q or y/y) | false = more cohorts; true = stricter, fewer |
| require_earnings_accel | boolean | Require earnings acceleration | false = more cohorts; true = stricter |

---

## Current presets and backtest results

### Preset: `B1_strict` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 0.8
- `earnings_yoy_min`: 5
- `eps_yoy_min`: None
- `gross_margin_min`: 0.25
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 18
- `sales_yoy_min`: 10

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0356 (3.56%)
- 52w: 0.0176 (1.76%)
- 78w: 0.0297 (2.97%)
- 104w: 0.0678 (6.78%)
- 156w: 0.1531 (15.31%)
- 208w: 0.0664 (6.64%)
- 260w: 0.0445 (4.45%)


### Preset: `B1_base` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 1.0
- `earnings_yoy_min`: 0
- `eps_yoy_min`: None
- `gross_margin_min`: 0.2
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 15
- `sales_yoy_min`: 8

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0416 (4.16%)
- 52w: 0.0195 (1.95%)
- 78w: 0.0332 (3.32%)
- 104w: 0.0726 (7.26%)
- 156w: 0.1587 (15.87%)
- 208w: 0.0402 (4.02%)
- 260w: 0.0516 (5.16%)


### Preset: `B1_relaxed` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 1.2
- `earnings_yoy_min`: None
- `eps_yoy_min`: None
- `gross_margin_min`: 0.15
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 12
- `sales_yoy_min`: 5

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0265 (2.65%)
- 52w: 0.0207 (2.07%)
- 78w: 0.0147 (1.47%)
- 104w: 0.0546 (5.46%)
- 156w: 0.0972 (9.72%)
- 208w: 0.0269 (2.69%)
- 260w: 0.0484 (4.84%)


### Preset: `B2_pro` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 0.8
- `earnings_yoy_min`: 5
- `eps_yoy_min`: None
- `gross_margin_min`: 0.3
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 15
- `sales_yoy_min`: 10

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0324 (3.24%)
- 52w: 0.0301 (3.01%)
- 78w: 0.0142 (1.42%)
- 104w: 0.0779 (7.79%)
- 156w: 0.1680 (16.80%)
- 208w: 0.1052 (10.52%)
- 260w: 0.0639 (6.39%)


### Preset: `B_cigar` (verdict: **FAIL**)

**Config:**
- `debt_to_equity_max`: 1.5
- `earnings_yoy_min`: None
- `eps_yoy_min`: None
- `gross_margin_min`: 0.1
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 10
- `sales_yoy_min`: 0

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0227 (2.27%)
- 52w: -0.0000 (-0.00%)
- 78w: -0.0163 (-1.63%)
- 104w: 0.0580 (5.80%)
- 156w: 0.0875 (8.75%)
- 208w: -0.0047 (-0.47%)
- 260w: 0.0389 (3.89%)


### Preset: `B1_tuned` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 1.0
- `earnings_yoy_min`: 0
- `eps_yoy_min`: None
- `gross_margin_min`: 0.18
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 14
- `sales_yoy_min`: 8

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0461 (4.61%)
- 52w: 0.0250 (2.50%)
- 78w: 0.0359 (3.59%)
- 104w: 0.0726 (7.26%)
- 156w: 0.1531 (15.31%)
- 208w: 0.0402 (4.02%)
- 260w: 0.0636 (6.36%)


### Preset: `B1_long_only` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 0.9
- `earnings_yoy_min`: 3
- `eps_yoy_min`: None
- `gross_margin_min`: 0.22
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 15
- `sales_yoy_min`: 10

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0486 (4.86%)
- 52w: 0.0213 (2.13%)
- 78w: 0.0450 (4.50%)
- 104w: 0.0726 (7.26%)
- 156w: 0.1692 (16.92%)
- 208w: 0.0251 (2.51%)
- 260w: 0.0374 (3.74%)


### Preset: `B_quality_first` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 0.9
- `earnings_yoy_min`: 5
- `eps_yoy_min`: None
- `gross_margin_min`: 0.2
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 16
- `sales_yoy_min`: 10

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0389 (3.89%)
- 52w: 0.0172 (1.72%)
- 78w: 0.0388 (3.88%)
- 104w: 0.0686 (6.86%)
- 156w: 0.1656 (16.56%)
- 208w: 0.0394 (3.94%)
- 260w: 0.0288 (2.88%)


### Preset: `B_margin_safety` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 1.0
- `earnings_yoy_min`: 5
- `eps_yoy_min`: None
- `gross_margin_min`: 0.18
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 14
- `sales_yoy_min`: 8

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0507 (5.07%)
- 52w: 0.0252 (2.52%)
- 78w: 0.0359 (3.59%)
- 104w: 0.0706 (7.06%)
- 156w: 0.1465 (14.65%)
- 208w: 0.0356 (3.56%)
- 260w: 0.0226 (2.26%)


### Preset: `B_low_leverage` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 0.85
- `earnings_yoy_min`: 0
- `eps_yoy_min`: None
- `gross_margin_min`: 0.18
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 14
- `sales_yoy_min`: 8

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0396 (3.96%)
- 52w: 0.0241 (2.41%)
- 78w: 0.0385 (3.85%)
- 104w: 0.0940 (9.40%)
- 156w: 0.1738 (17.38%)
- 208w: 0.0257 (2.57%)
- 260w: 0.0666 (6.66%)


### Preset: `B_moat_plus` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 0.95
- `earnings_yoy_min`: 3
- `eps_yoy_min`: None
- `gross_margin_min`: 0.22
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 15
- `sales_yoy_min`: 8

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0484 (4.84%)
- 52w: 0.0183 (1.83%)
- 78w: 0.0450 (4.50%)
- 104w: 0.0686 (6.86%)
- 156w: 0.1680 (16.80%)
- 208w: 0.0261 (2.61%)
- 260w: 0.0157 (1.57%)


### Preset: `B_long_softer_gm` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 0.9
- `earnings_yoy_min`: 3
- `eps_yoy_min`: None
- `gross_margin_min`: 0.2
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 15
- `sales_yoy_min`: 10

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0458 (4.58%)
- 52w: 0.0204 (2.04%)
- 78w: 0.0356 (3.56%)
- 104w: 0.0726 (7.26%)
- 156w: 0.1621 (16.21%)
- 208w: 0.0323 (3.23%)
- 260w: 0.0507 (5.07%)


### Preset: `B_sweet_spot` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 0.95
- `earnings_yoy_min`: 3
- `eps_yoy_min`: None
- `gross_margin_min`: 0.19
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 14
- `sales_yoy_min`: 8

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0463 (4.63%)
- 52w: 0.0132 (1.32%)
- 78w: 0.0385 (3.85%)
- 104w: 0.0686 (6.86%)
- 156w: 0.1514 (15.14%)
- 208w: 0.0498 (4.98%)
- 260w: 0.0333 (3.33%)


### Preset: `B_margin_moat` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 1.0
- `earnings_yoy_min`: 5
- `eps_yoy_min`: None
- `gross_margin_min`: 0.2
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 14
- `sales_yoy_min`: 8

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0513 (5.13%)
- 52w: 0.0172 (1.72%)
- 78w: 0.0332 (3.32%)
- 104w: 0.0686 (6.86%)
- 156w: 0.1522 (15.22%)
- 208w: 0.0323 (3.23%)
- 260w: 0.0112 (1.12%)


### Preset: `B_margin_low_debt` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 0.9
- `earnings_yoy_min`: 5
- `eps_yoy_min`: None
- `gross_margin_min`: 0.18
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 14
- `sales_yoy_min`: 8

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0480 (4.80%)
- 52w: 0.0261 (2.61%)
- 78w: 0.0385 (3.85%)
- 104w: 0.0726 (7.26%)
- 156w: 0.1582 (15.82%)
- 208w: 0.0394 (3.94%)
- 260w: 0.0381 (3.81%)


### Preset: `B_margin_strict` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 1.0
- `earnings_yoy_min`: 7
- `eps_yoy_min`: None
- `gross_margin_min`: 0.18
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 15
- `sales_yoy_min`: 10

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0526 (5.26%)
- 52w: 0.0280 (2.80%)
- 78w: 0.0289 (2.89%)
- 104w: 0.0551 (5.51%)
- 156w: 0.1414 (14.14%)
- 208w: 0.0330 (3.30%)
- 260w: 0.0300 (3.00%)


### Preset: `B_margin_elite` (verdict: **PASS**)

**Config:**
- `debt_to_equity_max`: 1.0
- `earnings_yoy_min`: 7
- `eps_yoy_min`: None
- `gross_margin_min`: 0.18
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: False
- `roe_min`: 14
- `sales_yoy_min`: 8

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0539 (5.39%)
- 52w: 0.0280 (2.80%)
- 78w: 0.0289 (2.89%)
- 104w: 0.0551 (5.51%)
- 156w: 0.1465 (14.65%)
- 208w: 0.0402 (4.02%)
- 260w: 0.0300 (3.00%)


### Preset: `B_exec_elite` (verdict: **FAIL**)

**Config:**
- `debt_to_equity_max`: 1.0
- `earnings_yoy_min`: 7
- `eps_yoy_min`: None
- `gross_margin_min`: 0.18
- `margin_yoy_min`: 0
- `require_earnings_accel`: False
- `require_eps_accel`: True
- `roe_min`: 14
- `sales_yoy_min`: 8

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0766 (7.66%)
- 52w: 0.0331 (3.31%)
- 78w: -0.0230 (-2.30%)
- 104w: -0.0012 (-0.12%)
- 156w: -0.0354 (-3.54%)
- 208w: -0.0012 (-0.12%)
- 260w: -0.0012 (-0.12%)


### Preset: `B_exec_compounder` (verdict: **FAIL**)

**Config:**
- `debt_to_equity_max`: 1.0
- `earnings_yoy_min`: 7
- `eps_yoy_min`: None
- `gross_margin_min`: 0.18
- `margin_yoy_min`: 0
- `require_earnings_accel`: True
- `require_eps_accel`: True
- `roe_min`: 14
- `sales_yoy_min`: 8

**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**
- 26w: 0.0523 (5.23%)
- 52w: 0.0651 (6.51%)
- 78w: 0.0568 (5.68%)
- 104w: 0.0398 (3.98%)
- 156w: -0.0279 (-2.79%)
- 208w: 0.0581 (5.81%)
- 260w: 0.1196 (11.96%)

