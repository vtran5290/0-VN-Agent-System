# VNINDEX Distribution Risk Lens — 2026-06-12

- Report status: **OK**
- Method: `distribution_risk_lens_v1.2`

### VNINDEX Distribution Risk Lens
- Primary view: **ex_vin_proxy**
- Lens report status: **OK**
#### Index view freshness
| View | Last data date | Requested as-of | Stale |
| --- | --- | --- | --- |
| vnindex_raw | 2026-06-12 | 2026-06-12 | no |
| ex_vin_proxy | 2026-06-12 | 2026-06-12 | no |
| vin_group | 2026-06-12 | 2026-06-12 | no |
#### v1.3 breadth staleness (read-only)
- Breadth status: **OK**
- Breadth as-of: **2026-06-12**
- Index as-of: **2026-06-12**
- Breadth lag (sessions): **0**
- _Research context only; not used for final_action, OMS, A3/S3, or position sizing._
- VNINDEX raw: **DOWNTREND_WARNING** (dist 10/25/50: 3/8/9)
- ex-VIN proxy: **CORRECTION_RISK** (dist 10/25/50: 3/8/9)
- VIN distortion flag: **False**
- VIN group warning: **DOWNTREND_WARNING**
- Distribution Risk Lens is market context only and does not change final_action.
- **ex-VIN proxy is derived and is NOT a native exchange index.**
- _NOT true ex-VIN index; see vnindex_low_dist_ex_vin.py methodology_
- _ex-VIN proxy drawdown/correction probabilities are close-based; high/low are synthetic from close when native OHLC is unavailable._
- P(25D return < 0) ex-VIN: **41.6% (base 39.1%)**
- P(-5% correction within 25D) ex-VIN: **42.1% (base 40.7%)**
- P(-10% correction within 75D) ex-VIN: **47.8% (base 44.5%)**
- Comparison: Raw and ex-VIN proxy broadly aligned on distribution warning.

- WARN: Data starts 2012-01-03; shorter history flagged
- Distribution Risk Lens is market context only and does not change final_action.
- Distribution Risk SSOT: `data/research/market_risk/distribution_risk_latest.json`
