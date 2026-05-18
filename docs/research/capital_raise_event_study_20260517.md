# Vietnam Equity Capital Raise Event Study

*Report date: 2026-05-17*

## 1. Scope and methodology

### Data sources
- **source = FireAnt** | **method = REST API** (`restv2.fireant.vn`) for fundamentals; OHLCV panel built from FireAnt historical quotes.
- **Events:** curated seed JSON + quarterly `shares_outstanding` change scan (derived).
- **VNINDEX:** FireAnt historical quotes / panel.

### Universe
- Panel symbols with OHLCV: 229.
- Priority sectors: Real Estate, Securities, Banks (49 tickers in priority list).
- Primary liquidity filter: ADV50 ≥ VND 2bn (trading value at T-1).

### Event types
Rights offering, private placement, stock dividend, ESOP, conversion, mixed, and derived share-count increases.

### Event dates
Primary anchor: **T0_announce**. Ex-right and result dates used when available. Calendar dates aligned to next trading day.

### Return windows
Standard pre/event/post windows per research brief; see `capital_raise_event_returns.csv` columns.

### Adjustments and limitations
- FireAnt posts API only returns recent social posts — not used for historical event dates.
- FiinGroup/HOSE GetShareIssue API not available without separate license.
- Many events are inferred from quarterly shares_outstanding; T0_announce is proxied.
- OHLCV may not be dividend-adjusted; ex-right windows can conflate mechanical gaps.
- Seed dates for press-sourced events should be cross-checked against official disclosures.
- Survivorship: panel is current listed universe with history from 2018.

## 2. Dataset overview

- Raw / merged events: **934**
- Primary-analysis events (liquidity pass): **840**

### Events by sector
```
sector
banks            4
other          678
real_estate     96
securities      62
```

### Events by event type
```
event_type
private_placement             6
rights_offering               5
stock_dividend                2
unknown_capital_increase    827
```

### Events by use of proceeds
```
use_of_proceeds
debt_repayment                3
project_investment            1
regulatory_capital            6
technical_stock_dividend      2
unclear                     828
```

### Disclosed events only (tier 1, n=12)
- Median post T+60: **2.44%** | VNINDEX excess: **1.99%**

- Rights (n=4) median post60=-5.89% vs Private placement (n=6)=2.44%

## 3. Overall price behavior (primary sample)

- Median pre-event 60d return (T-60→T-1): **-4.76%**
- Median post T+20 (T0→T+20): **-1.84%**
- Median post T+60: **-3.73%**
- Median VNINDEX-excess T+60: **-10.70%**
- Hit rate T+60 > 0: **40.1%**
- Outperform VNINDEX T+60: **31.0%**

## 4. By sector

### Real Estate (n=96): median pre60=-4.11%, post20=1.36%, post60=2.48%, excess60=0.40%
### Securities (n=62): median pre60=-8.92%, post20=0.13%, post60=-1.78%, excess60=-3.89%
### Banks (n=4): median pre60=2.88%, post20=-3.28%, post60=-0.90%, excess60=-1.60%
### Other (n=678): median pre60=-3.92%, post20=-2.16%, post60=-4.64%, excess60=-13.58%

## 5. By event type

- **private_placement** (n=6): median post60=2.44%, excess60=1.99%
- **rights_offering** (n=5): median post60=-5.89%, excess60=-10.49%
- **stock_dividend** (n=2): median post60=20.78%, excess60=15.46%
- **unknown_capital_increase** (n=827): median post60=-3.97%, excess60=-10.90%

## 8. Case studies
See `data/research/capital_raise_event_case_studies.csv` for top/bottom T+60 excess names.

## 9. Observed empirical patterns

In the historical sample, post-announcement returns are heterogeneous. Events with disclosed debt-repayment purpose and derived-only metadata should be interpreted separately. Results may be affected by market regime, incomplete event calendars, and unadjusted OHLCV around ex-right dates. **This does not imply causation.**

## 10. Open questions

- FireAnt posts API only returns recent social posts — not used for historical event dates.
- FiinGroup/HOSE GetShareIssue API not available without separate license.
- Many events are inferred from quarterly shares_outstanding; T0_announce is proxied.
- OHLCV may not be dividend-adjusted; ex-right windows can conflate mechanical gaps.
- Seed dates for press-sourced events should be cross-checked against official disclosures.
- Survivorship: panel is current listed universe with history from 2018.