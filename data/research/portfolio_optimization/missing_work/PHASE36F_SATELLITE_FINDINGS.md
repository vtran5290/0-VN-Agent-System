# Phase36F — Satellite Sleeve

Generated: 2026-05-17 | Baseline MAR=0.416 | Accept threshold=0.446

## Method

Blend A3 and S3 equity curves (both normalized to start=1.0, simulated separately).
S3 sleeve: EMA21/55, max_hold=60, TP=18%, trail=3.5×. NO REAL CAPITAL.

This is PAPER RESEARCH ONLY. S3 portion represents paper shadow returns.
Any implementation requires S3 paper gate passage (12 months, MAR≥0.35).

| Blend | MAR | CAGR | MaxDD | Δ-MAR | Accept? |
|-------|-----|------|-------|-------|---------|
| A3=60%/S3=40% | 0.3675 | 6.69% | -18.19% | -0.0485 | no |
| A3=70%/S3=30% | 0.3535 | 6.46% | -18.27% | -0.0625 | no |
| A3=80%/S3=20% | 0.3226 | 6.23% | -19.30% | -0.0934 | no |
| A3=90%/S3=10% | 0.2895 | 5.99% | -20.68% | -0.1265 | no |
| A3=100%/S3=0% | 0.2629 | 5.82% | -22.12% | -0.1531 | no |

## Hard Rules

- S3 sleeve = PAPER_TRADE_SHADOW only. No real capital. No DNSE.
- S3 sleeve P&L tracked SEPARATELY from A3 equity curve
- Satellite sleeve adoption requires S3 shadow gate passage first (Gate 10/11)
- Any sleeve > 20% S3 requires explicit operator decision + separate broker account
