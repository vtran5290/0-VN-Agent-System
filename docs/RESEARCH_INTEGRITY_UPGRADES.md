# Research Integrity Upgrades (Execution + PIT + Robustness)

## What changed

- **Execution semantics centralized** in `src/backtest/execution.py`:
  - Default research mode = **signal on bar t** (info known by end of t) → **fill at bar t+1 open**.
  - Centralized: fee/slippage, optional execution delays (for stress testing), liquidity cap metadata.
- **PP single-symbol ledger now carries raw fill inputs**:
  - `entry_open_raw`, `exit_open_raw`, plus fee/slip bps and delays.
  - Enables consistent post-hoc robustness without re-running signals.
- **Bias/execution audit artifacts**:
  - `pp_backtest/run.py` writes `artifacts/execution_audit_pp_<config_hash>.json`.
- **Tests added for look-ahead mistakes**:
  - `tests/test_execution_semantics.py` enforces “signal t → fill t+1 open” and verifies `meta_v1` uses shift(1) for entry gating.

## What remains unresolved (honesty)

- **Survivorship bias cannot be “solved” without data**:
  - The PIT machinery in `pp_backtest/monthly_universe.py` is time-sliced correctly, but
  - true survivorship elimination requires an authoritative listing/delist history or historical constituents.

## New utilities / how to run

- **Survivorship/PIT audit**:
  - `python -m pp_backtest.audit_survivorship`
  - Outputs: `artifacts/survivorship_audit_pp.json` and `.md`

- **Robustness layer (cost stress + bootstrap drawdowns)**:
  - `python -m pp_backtest.run_robustness --tag latest`
  - Outputs: `artifacts/robustness_pp_latest.json` and `.md`

## Expected impact on results

- **PP backtests**: strategy logic unchanged; trade returns should match (except added columns/audits).
- **Portfolio sim**: now applies costs via centralized helper (fee already existed; slippage default remains 0 unless provided).
- **CANSLIM**: pending upgrade to align default execution to next-open (see TODO in issue/plan).

