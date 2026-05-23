# Institutional Accumulation Scan — v1.0 sample vs v1.1 full universe
As-of: **2026-04-30** | methodology **v1.1**

| Ticker | v1.0 tier | v1.1 tier | v1.0 score | v1.1 score | MF | fund_context | emerging | VIN flag |
|--------|-----------|-----------|------------|------------|-----|--------------|----------|----------|
| MBB | Reject | Reject | 26.86 | 26.95 | 24.2 | consensus_core | False |  |
| CTG | Reject | Reject | 31.94 | 32.47 | 25.34 | consensus_core | False |  |
| MWG | Tier 3 | Tier 3 | 45.99 | 45.04 | 49.24 | consensus_core | False |  |
| HPG | Tier 3 | Tier 3 | 42.8 | 42.1 | 44.73 | consensus_core | False |  |
| GMD | Reject | Reject | 31.04 | 30.08 | 30.62 | consensus_core | False |  |
| VIC | Reject | Tier 3 | 39.98 | 39.58 | 63.41 | outside_fund_disclosure | False | Y |
| VHM | Tier 3 | Tier 3 | 44.13 | 42.5 | 65.59 | consensus_second_ring | False | Y |
| VCB | Tier 3 | Tier 3 | 43.28 | 44.55 | 57.13 | consensus_core | False |  |
| STB | Reject | Reject | 36.69 | 36.41 | 32.14 | consensus_second_ring | False |  |

## Notes
- v1.0 column = pre–full-universe sample run (not full liquid universe).
- v1.1 = full `data/stocks` liquid universe + grouped money-flow + fragile tier calibration.

```json
[
  {
    "ticker": "MBB",
    "v10_tier": "Reject",
    "v11_tier": "Reject",
    "v10_score": 26.86,
    "v11_score": 26.95,
    "v11_score_money_flow": 24.2,
    "fund_context_bucket": "consensus_core",
    "emerging": false,
    "vingroup_distortion_flag": false,
    "vingroup_distortion_diagnosis": NaN
  },
  {
    "ticker": "CTG",
    "v10_tier": "Reject",
    "v11_tier": "Reject",
    "v10_score": 31.94,
    "v11_score": 32.47,
    "v11_score_money_flow": 25.34,
    "fund_context_bucket": "consensus_core",
    "emerging": false,
    "vingroup_distortion_flag": false,
    "vingroup_distortion_diagnosis": NaN
  },
  {
    "ticker": "MWG",
    "v10_tier": "Tier 3",
    "v11_tier": "Tier 3",
    "v10_score": 45.99,
    "v11_score": 45.04,
    "v11_score_money_flow": 49.24,
    "fund_context_bucket": "consensus_core",
    "emerging": false,
    "vingroup_distortion_flag": false,
    "vingroup_distortion_diagnosis": NaN
  },
  {
    "ticker": "HPG",
    "v10_tier": "Tier 3",
    "v11_tier": "Tier 3",
    "v10_score": 42.8,
    "v11_score": 42.1,
    "v11_score_money_flow": 44.73,
    "fund_context_bucket": "consensus_core",
    "emerging": false,
    "vingroup_distortion_flag": false,
    "vingroup_distortion_diagnosis": NaN
  },
  {
    "ticker": "GMD",
    "v10_tier": "Reject",
    "v11_tier": "Reject",
    "v10_score": 31.04,
    "v11_score": 30.08,
    "v11_score_money_flow": 30.62,
    "fund_context_bucket": "consensus_core",
    "emerging": false,
    "vingroup_distortion_flag": false,
    "vingroup_distortion_diagnosis": NaN
  },
  {
    "ticker": "VIC",
    "v10_tier": "Reject",
    "v11_tier": "Tier 3",
    "v10_score": 39.98,
    "v11_score": 39.58,
    "v11_score_money_flow": 63.41,
    "fund_context_bucket": "outside_fund_disclosure",
    "emerging": false,
    "vingroup_distortion_flag": true,
    "vingroup_distortion_diagnosis": "RS_vs_VNINDEX_20d=47.8%; extension=34.8%; weekly_CMF_weak=-0.011; daily_weekly_CMF_conflict; price-led_daily_CMF_only"
  },
  {
    "ticker": "VHM",
    "v10_tier": "Tier 3",
    "v11_tier": "Tier 3",
    "v10_score": 44.13,
    "v11_score": 42.5,
    "v11_score_money_flow": 65.59,
    "fund_context_bucket": "consensus_second_ring",
    "emerging": false,
    "vingroup_distortion_flag": true,
    "vingroup_distortion_diagnosis": "RS_vs_VNINDEX_20d=31.0%; extension=28.8%; daily_CMF_missing; weekly_CMF_weak=0.015"
  },
  {
    "ticker": "VCB",
    "v10_tier": "Tier 3",
    "v11_tier": "Tier 3",
    "v10_score": 43.28,
    "v11_score": 44.55,
    "v11_score_money_flow": 57.13,
    "fund_context_bucket": "consensus_core",
    "emerging": false,
    "vingroup_distortion_flag": false,
    "vingroup_distortion_diagnosis": NaN
  },
  {
    "ticker": "STB",
    "v10_tier": "Reject",
    "v11_tier": "Reject",
    "v10_score": 36.69,
    "v11_score": 36.41,
    "v11_score_money_flow": 32.14,
    "fund_context_bucket": "consensus_second_ring",
    "emerging": false,
    "vingroup_distortion_flag": false,
    "vingroup_distortion_diagnosis": NaN
  }
]
```