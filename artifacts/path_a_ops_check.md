# Path A Operational Check

**Status:** data current = True; champion default = True; tuned challenger under watch = True; formal review open = False.

## 1. Data freshness summary

- Latest backtest end date: **2026-02-21**
- Latest rolling window end date: **2026-02-21**
- Monitoring snapshot period: **2024-01-01_to_2026-03-16**
- Latest any-date in stack: **2026-02-21** (staleness ≈ 24 days)
- Data looks current (<=45 days stale): **True**

## 2. Recent Champion vs Tuned Challenger snapshot

- Period: **2024-01-01_to_2026-02-21**

| config | period | CAGR | MDD | MAR | n_trades | trades_per_month | chosen_rate | rejected_max_positions |
|--------|--------|------|-----|-----|----------|------------------|------------|------------------------|
| Champion | 2024-01-01_to_2026-02-21 | 14.41% | -18.37% | 0.7845 | 67 | 2.57 | 0.02781 | 1332 |
| Tuned Challenger | 2024-01-01_to_2026-02-21 | 9.69% | -20.97% | 0.4622 | 82 | 3.15 | 0.02604 | 607 |

## 3. Drift & alerts

- No immediate drift alerts; continue normal monitoring cadence.

## 4. Governance status

- Champion default? **True**
- Tuned Challenger under watch? **True**
- Formal baseline review opened? **False**

## 5. Operating recommendation

- **Keep Champion as default Path A** and **keep Tuned Challenger under watch**. Data stack appears reasonably current; re-run this ops check periodically to see if rolling performance and risk justify opening a formal review.

## 6. Suggested cadence

- Recommended rerun cadence: **weekly** or whenever a fresh batch of FireAnt data is ingested.
- Trigger a **manual governance review** if:
  - data becomes stale by more than ~45 days;
  - Tuned Challenger sustains higher recent MAR over several ops checks **without** materially worse MDD;
  - or governance monitor (`path_a_governance_monitor.md`) starts flagging that promotion conditions are close to satisfied.
