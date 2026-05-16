# Macro Data Missing

As of: 2026-05-16

The following macro data sources are required for full macro decomposition.
They are NOT available in the current repo. Do not fabricate values.

## Required Data Sources

| Source | Required Columns | Expected Frequency | Purpose |
|--------|-----------------|--------------------|---------|
| SBV OMO | date, net_omo_VND, overnight_rate | Daily | Domestic liquidity proxy |
| SBV Policy Rate | date, base_rate_pct, repo_rate_pct | Monthly | Rate cycle regime |
| USD/VND | date, usdvnd_close | Daily | FX pressure |
| DXY | date, dxy_close | Daily | Global USD strength |
| MSCI EM | date, em_close | Daily | Global risk-on/off proxy |
| VN CPI | date, cpi_yoy_pct | Monthly | Inflation regime |
| VN GDP Growth | date, gdp_growth_pct | Quarterly | Macro expansion/contraction |
| Market Total Value | date, total_value_VND | Daily | Market liquidity regime |

## Proxy Available (from panel)

- Market breadth (A3/S3 universe): computed from panel, available in regime_decomposition_breadth.csv
- VNINDEX EMA regimes: computed from VNINDEX data, available in regime_decomposition_market.csv
- Stock ADV50: computed per symbol, available per trade in corrected ledgers

## Action Required

- Load SBV data from scripts/run_weekly_full_fetch.py or FireAnt API
- Load USD/VND and DXY from public sources (Stooq, Yahoo Finance)
- Once loaded, join on entry_date in decomp analysis
