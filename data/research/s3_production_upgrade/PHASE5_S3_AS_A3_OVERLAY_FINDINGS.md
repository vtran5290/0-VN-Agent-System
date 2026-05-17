# Phase 5 — S3 as A3 Overlay Findings

Date: 2026-05-17

---

## A3 Lead Overlay — MAR Comparison

| Window | Group | N | MAR | CAGR | MaxDD | Hit Rate | TP1 Rate |
|--------|-------|---|-----|------|-------|----------|----------|
| 3b | with_s3 | 4,365 | 0.261 | 5.9% | -22.6% | 68.9% | 63.4% |
| 3b | without_s3 | 4,666 | 0.152 | 4.2% | -27.8% | 69.9% | 64.4% |
| 5b | with_s3 | 5,329 | 0.291 | 7.1% | -24.4% | 68.9% | 63.6% |
| 5b | without_s3 | 3,702 | 0.208 | 5.6% | -27.0% | 70.2% | 64.4% |
| 10b | with_s3 | 6,379 | 0.189 | 4.6% | -24.1% | 69.1% | 63.9% |
| 10b | without_s3 | 2,652 | 0.205 | 5.2% | -25.4% | 70.2% | 64.1% |
| 20b | with_s3 | 7,013 | 0.170 | 4.9% | -28.6% | 69.6% | 64.2% |
| 20b | without_s3 | 2,018 | 0.180 | 5.1% | -28.5% | 68.9% | 63.2% |

---

## 5-Bar Lead Verdict (Confirmed Selection)

- A3 with S3 lead (5-bar): MAR=0.291
- A3 without S3 lead: MAR=0.208
- Delta: +0.083

**OVERLAY_SUPPORTED: S3Lead5 provides A3 priority ranking benefit.**
`a3_s3_lead_5d` confirmed as ranking-only signal (does NOT block A3).

---

## A3 Size Overlay (Approximate)

| Size Boost | N | N with Lead | MAR | CAGR | MaxDD |
|-----------|---|------------|-----|------|-------|
| 1.0× | 9,031.0 | 5,329.0 | 0.263 | 5.8% | -22.1% |
| 1.1× | 9,031.0 | 5,329.0 | 0.263 | 6.1% | -23.2% |
| 1.2× | 9,031.0 | 5,329.0 | 0.263 | 6.4% | -24.3% |
