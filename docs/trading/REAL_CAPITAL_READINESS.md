# Real Capital Readiness

## Verdict: NO-GO

Real capital deployment is **not approved**. Continue paper / dry-run validation.

## Strategy (frozen)

- Production: **A3_DP** only (EMA20/100 cloud breakout, ex-VIN3)
- Daily scan = source of truth (no OMS signal recompute)
- T1 50%, T2 50% on >=4% pullback within 30 bars (from scan `ADD_T2`)
- TP1 +18%, trail 2.5×ATR14, max hold 250 bars
- PTS shadow OFF | S3 research-only | Breadth manual review only | Sector L4 warning only
- Performance throttle: rejected | Macro: pending external data | AFL: visual only

## Implemented controls

- Data health checker
- Scan → order intents adapter
- Batch-aware risk
- Trade-intent lock (same day/symbol/side)
- Pre-submit re-risk
- Broker capacity check
- Baseline reconciliation
- Kill switch
- Paper ledger (`data/trading/live/`)
- DNSE real orders: disabled

## Gates before real capital

- [ ] 3 months paper trading
- [ ] 20–30 paper decisions logged
- [ ] 0 critical scan/order mismatches
- [ ] Data health PASS 20 consecutive trading days
- [ ] Broker dry-run passes
- [ ] Reconciliation clean consistently
- [ ] Kill switch tested
- [ ] Manual override documented
- [ ] DNSE API permission + regulatory scope confirmed
- [ ] `live_auto` remains disabled until separate approval
