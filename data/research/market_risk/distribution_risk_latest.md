# VNINDEX Distribution Risk Lens — 2026-05-21

- Report status: **OK**
- Method: `distribution_risk_lens_v1.2`

### VNINDEX Distribution Risk Lens
- Primary view: **ex_vin_proxy**
- Lens report status: **OK**
#### Index view freshness
| View | Last data date | Requested as-of | Stale |
| --- | --- | --- | --- |
| vnindex_raw | 2026-05-21 | 2026-05-21 | no |
| ex_vin_proxy | 2026-05-21 | 2026-05-21 | no |
| vin_group | 2026-05-21 | 2026-05-21 | no |
- VNINDEX raw: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 3/4/8)
- ex-VIN proxy: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 3/4/7)
- VIN distortion flag: **False**
- VIN group warning: **CORRECTION_RISK**
- Distribution Risk Lens is market context only and does not change final_action.
- **ex-VIN proxy is derived and is NOT a native exchange index.**
- _NOT true ex-VIN index; see vnindex_low_dist_ex_vin.py methodology_
- _ex-VIN proxy drawdown/correction probabilities are close-based; high/low are synthetic from close when native OHLC is unavailable._
- P(25D return < 0) ex-VIN: **44.4% (base 39.0%)**
- P(-5% correction within 25D) ex-VIN: **42.4% (base 40.5%)**
- P(-10% correction within 75D) ex-VIN: **44.4% (base 44.3%)**
- Comparison: Raw and ex-VIN proxy broadly aligned on distribution warning.

- WARN: Data starts 2012-01-03 (after 2012); shorter history flagged
