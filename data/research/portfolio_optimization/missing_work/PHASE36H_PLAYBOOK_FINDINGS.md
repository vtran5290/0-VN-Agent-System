# Phase36H — Interaction Matrix & Playbook

Generated: 2026-05-17 | A3 baseline MAR=0.416 | Threshold=0.446

## Summary: Accepted Variants (MAR ≥ 0.446)

Total accepted: 0 of 44

_No variants reached the +0.03 MAR threshold._

## Recommendations

1. **Ranking (Phase36B)**: If a3_rank_score improves MAR ≥ +0.03 at 20 slots,
   adopt it as the same-day NEW_T1 sort order in the scan output.

2. **Sizing (Phase36C)**: Lead-bucket size multiplier is low-risk additive.
   Adopt only if MAR improvement verified AND does not increase portfolio volatility.

3. **T2 Policy (Phase36D)**: T2 conditional on S3 lead adds complexity with
   uncertain benefit. Default: keep current T2 policy (breadth + regime gates).

4. **Exit overlay (Phase36E)**: Trail parameter changes affect ALL trades globally.
   Only adopt if clear MAR improvement. Conservative default: keep 2.5×ATR14.

5. **Satellite sleeve (Phase36F)**: PAPER RESEARCH ONLY. Requires S3 paper gate
   passage before any implementation. Not a production decision now.

6. **Risk warning (Phase36G)**: Implement DD correlation monitor as advisory panel.
   Does not change A3 production logic.

## Decision Framework

| Condition | Action |
|-----------|--------|
| Ranking MAR Δ ≥ +0.03 | Adopt a3_rank_score as NEW_T1 sort |
| Ranking MAR Δ < +0.03 | Keep ema_dist_at_entry sort (current) |
| Sizing MAR Δ ≥ +0.03 | Adopt lead-bucket multiplier (operator-approved) |
| Sizing MAR Δ < +0.03 | Keep equal weight |
| Exit overlay MAR Δ ≥ +0.03 | Propose exit param change for review |
| Exit overlay MAR Δ < +0.03 | Keep 2.5×ATR14 / max_hold=250 |
| Satellite: S3 paper gate not met | No implementation (Gate 10/11 required first) |

## Hard Rules (unchanged)

- A3 EMA20/100 + DP-first entry: locked
- S3 EMA21/55 max_hold=60: paper shadow only, no real capital
- VNINDEX EMA20>EMA100 hard block: locked
- Breadth T2 block (<35%): locked
- ADV50 10% participation cap: locked
