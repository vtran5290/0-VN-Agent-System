# S3 Phase 3.1 Top Findings

As of: 2026-05-16

## Context

- S3: EMA21/55 cloud breakout, full universe, TP1 +18%, trail 3.5×ATR, max_hold 250
- Corrected ADV50: panel['value'].rolling(50).fillna(c×v×1000)
- Reference portfolio: 5B VND, 10% participation cap

## Top S3 DP Pullback Configs (at 5B/10%)

| Rank | Config | MAR | CAGR | MaxDD | Excl_T1 |
|------|--------|-----|------|-------|----------|
| 1 | S3_dp_d3_w20_fast_ema_t160 | 0.190 | 3.12% | -16.46% | 0.7% |
| 2 | S3_dp_d5_w20_slow_097_t150 | 0.183 | 3.12% | -17.05% | 0.7% |
| 3 | S3_dp_d3_w20_fast_ema_t150 | 0.183 | 2.58% | -14.09% | 0.7% |
| 4 | S3_dp_d3_w25_fast_ema_t160 | 0.183 | 3.08% | -16.84% | 0.7% |
| 5 | S3_dp_d4_w20_fast_ema_t160 | 0.182 | 2.79% | -15.34% | 0.7% |

## Top S3 PTS Configs (at 5B/10%)

| Rank | Config | MAR | CAGR | MaxDD | pct_pb | pct_str |
|------|--------|-----|------|-------|--------|----------|
| 1 | pts_pb5w30_str6w10 | 0.183 | 3.78% | -20.65% | 36.9% | 32.9% |
| 2 | pts_pb5w20_str6w10 | 0.152 | 3.40% | -22.34% | 31.1% | 34.4% |
| 3 | pts_pb5w20_str4w10 | 0.150 | 3.43% | -22.87% | 31.1% | 39.1% |
| 4 | pts_pb4w20_str4w10 | 0.074 | 2.15% | -28.84% | 41.4% | 35.6% |

## Comparison vs A3 DP Reference

- A3 DP at 5B/10%: MAR=0.416 (Phase 3.1 result)
- S3 best DP at 5B/10%: MAR=0.190 (S3_dp_d3_w20_fast_ema_t160)
- S3 vs A3: A3 wins (delta=-0.226)

## Decision Classification

- S3 best DP: **RESEARCH_ONLY** — Low MAR after corrected liquidity, not ready for paper trade
