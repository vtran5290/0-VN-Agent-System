# Real Capital Readiness

## Verdict: NO-GO

Real capital deployment is **not approved**. Continue paper / dry-run validation.

**Current phase:** **paper-live daily observation** — `paper-accounts run-all` with 30M pilot + 5B reference + 10B scale + 20B liquidity stress + optional S3 shadow.  
DSE/DNSE live API: **NO-GO**. `live_auto`: **NO-GO**. Real capital: **NO-GO**.

## Strategy (frozen)

- Production: **A3_DP** only (EMA20/100 cloud breakout, ex-VIN3)
- Daily scan = source of truth (no OMS signal recompute)
- T1 50%, T2 50% on >=4% pullback within 30 bars (from scan `ADD_T2`)
- TP1 +18%, trail 2.5×ATR14, max hold 250 bars
- PTS shadow OFF | S3 research-only | Breadth manual review only | Sector L4 warning only
- Performance throttle: rejected | Macro: pending external data | AFL: visual only

## Implemented controls

- Data health checker
- Phase35/36 scan resolver (no silent sample in prod)
- Scan → order intents adapter (incl. SELL exits from `final_action`)
- Batch-aware risk + batch trade-intent lock
- Trade-intent lock (same day/symbol/side)
- Pre-submit re-risk (no self-block bug)
- Broker capacity check
- Baseline reconciliation + dirty recon blocks execution
- Kill switch
- Paper ledger (`data/trading/live/accounts/<ACCOUNT_ID>/`) — separate from research `data/paper_trade/`
- Multi-account paper: per-account broker state, run locks, manual review queues
- Paper mode: real simulated fills; dry-run: no ledger mutation
- Exact `A3_PRODUCTION` classification required for capital intents
- SELL exits use risk-reducing path (not BUY sizing caps)
- MANUAL_REVIEW requires file-based approval in queue CSV
- S3 shadow: `data/trading/live/s3_shadow/` only
- Daily run lock + manifest
- S3 shadow: paper-only; no A3 P&L mix; no DNSE
- DNSE real orders: disabled

## Live mode status as of current phase

| Mode | Status |
|------|--------|
| **Real capital** | **NO-GO** — not approved |
| **live_auto** | Raises `RuntimeError` unless explicit enable flag is set; remains **disabled** by default |
| **live_manual** | Workflow remains **`dry_run=True` / `live_trading=False`** — observation only |
| **live_auto (workflow)** | Same fail-closed defaults; no unattended live routing |
| **DNSE / live broker** | **Disabled / fail-closed** — no production live orders |
| **Intraday CSV** | **Cannot** be used for OMS — blocked at `scan_resolver` |
| **S3** | **Cannot** create live orders — paper-shadow ledger only |
| **A3** | Only production candidate; OMS consumes **`final_action` only** |

All **9 real-capital readiness gates** below remain **unchecked** unless explicitly verified in a future approval cycle. Paper-live daily observation does **not** imply capital approval.

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
