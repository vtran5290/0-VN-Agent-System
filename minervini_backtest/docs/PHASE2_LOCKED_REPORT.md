# Phase 2 Locked Report (Facts-Only)

## Survivorship summary

| Metric | Value |
|--------|--------|
| total_symbols | 85 |
| symbols_present_pre2017 (first FA row ≤ 2016-12-31) | 84 |
| symbols_first_seen_2017_2018 | 1 |
| symbols_first_seen_post2019 | 0 |

**Caveat:** Universe is watchlist_80 as of 2024; survivorship bias likely present. **Results represent upper bound.**

---

## Phase 2 v1 locked — Decision metrics (FA_only vs Hybrid breakout_20d, window30)

| strategy | variant | horizon | median_yearly_alpha | sharpe | trade_count |
|----------|---------|---------|---------------------|--------|-------------|
| FA_only | FA_only | 8 | 0.0355 | 0.399 | 175 |
| FA_only | FA_only | 10 | 0.0255 | 0.385 | 175 |
| FA_only | FA_only | 13 | 0.0602 | 0.410 | 175 |
| Hybrid | breakout_20d | 8 | 0.0635 | 0.432 | 144 |
| Hybrid | breakout_20d | 10 | 0.0410 | 0.392 | 144 |
| Hybrid | breakout_20d | 13 | 0.0720 | 0.428 | 144 |

---

## Phase 2 v1.1 candidate — Decision metrics (Hybrid MA stacked, window30)

| strategy | variant | horizon | median_yearly_alpha | sharpe | trade_count |
|----------|---------|---------|---------------------|--------|-------------|
| Hybrid | ma5_gt_ma10_gt_ma20 | 8 | 0.0511 | 0.449 | 165 |
| Hybrid | ma5_gt_ma10_gt_ma20 | 10 | 0.0462 | 0.424 | 165 |
| Hybrid | ma5_gt_ma10_gt_ma20 | 13 | 0.0861 | 0.442 | 165 |

---

## Conclusion

**FA-first; timing adds incremental edge; v1 locked (breakout_20d + window30); v1.1 candidate (ma5_gt_ma10_gt_ma20 + window30).**
