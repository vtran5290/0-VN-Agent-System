# Dual Cloud Accumulation / Wyckoff Feature Research

**Status:** RESEARCH ONLY — paper validation workstream.
No production changes. No live orders. No OMS modifications.

---

## Research question

Does adding price tightness, volume tightness, breakout quality, and mechanical
Wyckoff-style accumulation tags to the existing dual EMA-cloud system improve:

1. Predictive value of A3 signals
2. A3 candidate ranking (top-scored vs all-signal baseline)
3. A3 T2 add-on timing (4% pullback within 30 bars)
4. S3 max60 shadow quality
5. Marginal value of Wyckoff tags beyond simple tightness features
6. Robustness across years, regimes, sectors, and liquidity buckets

---

## Strategy contracts (frozen — do not modify)

### A3 — EMA20/100 cloud (PRODUCTION_CANDIDATE / PAPER_TRADE_PRIMARY)
- Universe: ex-VIN (excludes VIC, VHM, VRE; VPL excluded until 252 bars)
- Entry: A3 cloud signal (EMA20 > EMA100, price above EMA20)
- T1 = 50% at signal; T2 = 50% on ≥4% pullback within 30 bars
- TP1 = +18%; trail = 2.5× ATR14; max_hold = 250 bars
- ADV50 ≥ 2B VND (corrected: close_kVND × volume × 1000)

### S3 — EMA21/55 cloud (PAPER_TRADE_SHADOW / offensive only)
- Entry: S3 cloud signal (EMA21 > EMA55)
- TP1 = +18%; trail = 3.5× ATR14; max_hold = 60 bars
- VNINDEX regime gate required
- ADV50 ≥ 2B VND (corrected formula above)
- No real capital, no DNSE/live orders

---

## Staged implementation

| Stage | Script | Purpose | Output |
|-------|--------|---------|--------|
| 1 | `stage1_feature_value.py` | Predictive value: do features correlate with forward returns? | `stage1_*.csv/md` |
| 2 | `stage2_a3_ranking.py` | A3 ranking: does top-quintile score beat all-signal baseline? | `stage2_*.csv/md` |
| 3 | `stage3_a3_t2_timing.py` | T2 timing: do features predict T2 pullback success? | `stage3_*.csv/md` |
| 4 | `stage4_s3_quality.py` | S3 shadow: does score filter improve S3 max60 quality? | `stage4_*.csv/md` |
| 5 | `stage5_wyckoff_tags.py` | Wyckoff tags: marginal value beyond tightness? | `stage5_*.csv/md` |
| 6 | `stage6_robustness.py` | Robustness: by-year, regime, sector, liquidity | `stage6_*.csv/md` |

---

## Feature taxonomy

### Price tightness
| Feature | Description | Signal direction |
|---------|-------------|-----------------|
| `pt_20` | Rolling 20-bar close std / mean | Lower = tighter |
| `pt_40` | Rolling 40-bar close std / mean | Lower = tighter |
| `atr_ratio` | ATR14 / ATR50 | < 1 = contracting volatility |
| `bar_range_pct` | (high−low) / close | Lower = narrower bars |
| `range_vs_ma20` | bar_range_pct / its 20-bar mean | < 1 = compression |

### Volume tightness
| Feature | Description | Signal direction |
|---------|-------------|-----------------|
| `vol_ratio` | volume / vol_ma(20) | < 1 = below-avg volume |
| `vol_trend_10` | Normalized slope of volume, 10 bars | Negative = drying up |
| `vol_below_streak` | Consecutive bars of below-avg volume (cap 20) | Higher = more drying |
| `vol_drying` | Fraction of last 10 bars with volume < 0.8× vol_ma20 | Higher = more drying |

### Breakout quality
| Feature | Description | Signal direction |
|---------|-------------|-----------------|
| `bo_vol_exp` | volume / vol_ma20 at signal bar | > 1 = volume expansion |
| `bo_close_str` | (close−low) / (high−low) | > 0.7 = strong close |
| `bo_range_exp` | (high−low) / ATR14 | > 1 = range expanded |

### Mechanical Wyckoff tags (bool)
| Tag | Mechanical definition |
|-----|-----------------------|
| `spring` | Close violated 20-bar support low, then reclaimed it within 3 bars |
| `sos` | Close > 20-bar resistance high on volume ≥ 1.5× vol_ma20 |
| `lps` | Pullback to within 3% of prior SOS level on volume < 0.7× vol_ma20 |
| `utad` | Close broke above resistance, failed back below within 5 bars |
| `efvr` | \|close−open\| / (high−low) / vol_ratio — low = effort without result |

### Composite accumulation score
Weighted rank sum of price tightness (inverted), volume tightness (inverted),
vol_drying, bo_vol_exp, and bo_close_str. Range [0, 1], higher = more evidence.

---

## Running stages

```powershell
# Single stage
.venv\Scripts\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage1_feature_value.py

# Full pipeline
.venv\Scripts\python.exe scripts/research/dual_cloud_accumulation_wyckoff/run_all.py

# Skip data fetch (use cached panel)
.venv\Scripts\python.exe scripts/research/dual_cloud_accumulation_wyckoff/run_all.py --no-fetch

# Ex-VIN cut
.venv\Scripts\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage1_feature_value.py --ex-vin
```

---

## Non-negotiable constraints (from research brief)

1. Do not break or alter the A3 production contract
2. Do not promote S3 to production
3. Do not mix A3 and S3 P&L unless explicitly testing combined sleeves
4. Do not use S3 to gate A3
5. Do not use LLMs in the trading decision path
6. Do not use breadth as a hard A3 T1 block
7. Do not silently skip ADV cap if ADV is missing
8. Do not recommend real capital, DNSE live, or live_auto

---

## Interpretation notes

- A Wyckoff tag adds value if it improves 63-day success rate by >3 pp vs tightness-only after year/regime split.
- Ranking overlay adds value if Q5 (top quintile by score) win rate > all-signal baseline by >5 pp with n > 40 trades.
- T2 timing adds value if score predicts ≥50% T2 fill rate vs <35% for low-score group, in OOS period (2025+).
- All findings require by-year split. A result that only holds in 2020–2022 is not actionable.
- Regime check: does the feature help more in bull regime than bear? (Expected: yes for tightness, ambiguous for spring.)
