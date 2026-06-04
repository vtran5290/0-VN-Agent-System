"""
P1 Test 7 — Dashboard-safe group rotation ranking feature proposal.
Produces GROUP_BREADTH_RANKING_FEATURE_PROPOSAL.md.
DASHBOARD ONLY — no OMS/A3/final_action changes.
"""
from __future__ import annotations
import logging
from datetime import date

import numpy as np
import pandas as pd

from .p1_config import P1_RANKING_PROPOSAL_PATH, P1_MIN_EVENTS

log = logging.getLogger(__name__)


def _top_groups(df: pd.DataFrame, metric_col: str, n: int = 5) -> str:
    if df is None or df.empty or metric_col not in df.columns:
        return "  (data not available)\n"
    top = df.nlargest(n, metric_col)[["grouping_layer", "group_name", metric_col]]
    lines = ""
    for _, r in top.iterrows():
        lines += f"  - [{r['grouping_layer']}] **{r['group_name']}**: {metric_col}={r[metric_col]:.3f}\n"
    return lines


def write_ranking_feature_proposal(
    lead_lag_summary: pd.DataFrame,
    filter_value_ablation: pd.DataFrame,
    leader_classification: pd.DataFrame,
    regime_stability: pd.DataFrame,
    a3_replay: pd.DataFrame,
) -> str:
    today = date.today().isoformat()

    # ── Summarize lead/lag evidence ───────────────────────────────────────────
    if lead_lag_summary is not None and not lead_lag_summary.empty:
        leads_grps = lead_lag_summary[lead_lag_summary["conclusion_tag"] == "sector_leads"]
        n_leads  = len(leads_grps)
        median_lift = lead_lag_summary["excess_turn_pct_t1_t10"].median()
        top_ll_lines = _top_groups(lead_lag_summary, "excess_turn_pct_t1_t10")
    else:
        n_leads, median_lift = 0, np.nan
        top_ll_lines = "  (data not available)\n"

    # ── Summarize filter value at 60d ─────────────────────────────────────────
    if filter_value_ablation is not None and not filter_value_ablation.empty:
        fv60 = filter_value_ablation[
            (filter_value_ablation["rule_id"] == "breadth_ew_ge_40") &
            (filter_value_ablation["horizon"] == 60)
        ]
        g2_pass = fv60[fv60["delta_hit_rate"].fillna(0) >= 0.03]
        n_g2_pass = len(g2_pass)
        top_fv_lines = _top_groups(fv60, "delta_hit_rate")
    else:
        n_g2_pass = 0
        top_fv_lines = "  (data not available)\n"

    # ── Summarize leader analysis ─────────────────────────────────────────────
    if leader_classification is not None and not leader_classification.empty and "group_classification" in leader_classification.columns:
        grp_clf = leader_classification.drop_duplicates(["grouping_layer", "group_name", "group_classification"])
        broad = grp_clf[grp_clf["group_classification"] == "BROAD_BASED"]
        n_broad = len(broad)
        broad_names = ", ".join([f"[{r['grouping_layer']}] {r['group_name']}" for _, r in broad.head(5).iterrows()])
    else:
        n_broad = 0
        broad_names = "(data not available)"

    # ── A3 replay summary ─────────────────────────────────────────────────────
    if a3_replay is not None and not a3_replay.empty:
        a3_gate40 = a3_replay[a3_replay["rule_id"] == "breadth_ew_ge_40"]
        n_a3_pass = len(a3_gate40[a3_gate40["gate_pass"] == 1]) if "gate_pass" in a3_gate40.columns else 0
        best_a3 = a3_gate40.nlargest(3, "delta_trade_level_mar_proxy") if "delta_trade_level_mar_proxy" in a3_gate40.columns else pd.DataFrame()
        a3_lines = ""
        for _, r in best_a3.iterrows():
            a3_lines += f"  - [{r['grouping_layer']}] {r['group_name']}: d_tmar={r['delta_trade_level_mar_proxy']:.4f}, bl_ratio={r['blocked_loser_winner_ratio']:.2f}, gate={'PASS' if r['gate_pass']==1 else 'FAIL'}\n"
        if not a3_lines:
            a3_lines = "  (no A3 gate passes detected)\n"
    else:
        n_a3_pass = 0
        a3_lines = "  (A3 replay data not available)\n"

    text = f"""# GROUP BREADTH RANKING FEATURE PROPOSAL

**Date:** {today}
**Status:** DASHBOARD-ONLY — NOT production code
**Approved use:** Operator review priority, watchlist booster, visual dashboard context

---

## CRITICAL CONSTRAINTS

> This document proposes a DASHBOARD FEATURE ONLY.
> No changes to: A3 production logic, OMS, Phase36 `final_action`, A3 entry/exit contract,
> S3 status, DNSE routing, or position sizing.
> This score CANNOT create, block, size, or modify any orders.
> Upgrade to production requires a separate operator-approved production-change memo.

---

## 1. Evidence Summary

### 1.1 Lead/Lag Evidence [FACTS]

- Groups with "sector_leads" classification (excess turns >=15% above random): **{n_leads}**
- Median relative lift across all eligible groups: **{median_lift:.1%}**
- Top groups by excess turn lift:
{top_ll_lines}

### 1.2 Filter Value at 60d [FACTS]

- Groups passing G2 gate (delta_hit_rate_60d >= 3pp with breadth_ew >= 40%): **{n_g2_pass}**
- Top groups by delta_hit_rate_60d:
{top_fv_lines}

### 1.3 Leader Classification [FACTS]

- BROAD_BASED groups (leader precedes sector <30% of events): **{n_broad}**
- Broad-based groups: {broad_names}
- LEADER_DRIVEN groups are less reliable as breadth signals (leader identity matters more than breadth).

### 1.4 A3 Ledger Replay [FACTS]

- Groups where breadth gate improves trade-level MAR proxy AND bl_ratio >= 1.2: **{n_a3_pass}**
- Best A3 gate candidates (breadth_ew >= 40%):
{a3_lines}
- Note: trade-level MAR proxy is NOT portfolio MAR. Multiple simultaneous trades, no daily NAV.

---

## 2. Proposed Ranking Score

### Formula

```
group_rotation_score(group, date) =
    breadth_score(group, date)
    + turn_recency_score(group, date)
    + follower_score(group, date)
    - leader_drag_penalty(group, date)
```

### Component Definitions

**breadth_score** ∈ [0, 1]
```
breadth_score = l.l.l.clamp(group_breadth_ew / 0.60, 0, 1)
# Scales from 0 at 0% breadth to 1.0 at 60%+
```

**turn_recency_score** ∈ [0, 0.5]
```
if group had primary turn (40/35) within last 5 sessions:  +0.50
elif within last 10 sessions:                               +0.30
elif within last 20 sessions:                               +0.15
else:                                                        0.00
```

**follower_score** ∈ [0, 0.3]
```
n_stock_cloud_turns_past_5d = count of group members with cloud 0->1 in last 5 sessions
follower_score = clamp(n_stock_cloud_turns_past_5d / 3, 0, 0.3)
# 3 follower flips in 5 sessions = max score
```

**leader_drag_penalty** ∈ [0, 0.5]
```
if group_classification == "LEADER_DRIVEN":    penalty = 0.50
elif group_classification == "COINCIDENT":     penalty = 0.20
else:                                          penalty = 0.00
```

### Score Interpretation

| Score Range | Interpretation | Operator Action |
|---|---|---|
| >= 1.5 | Strong rotation signal | Add to review watchlist, increase monitoring frequency |
| 1.0–1.5 | Moderate signal | Flag in daily scan as context |
| 0.5–1.0 | Weak signal | Dashboard color only |
| < 0.5 | No signal | No action |

### What this score does NOT do

- Does NOT create, modify, or block any A3/OMS orders
- Does NOT affect `final_action` or position sizing
- Does NOT replace Phase36 signal logic
- Is NOT a backtested strategy — it is a visual operator-review aid

---

## 3. Recommended Groups for Dashboard

### Priority 1 — BROAD_BASED + G2_pass_candidate (Highest quality)

Use for watchlist boosting. If score >= 1.5 AND group has >=5 members:
- Symbol appearing in a broad rotation may merit closer review before entry.

### Priority 2 — LEADER_DRIVEN groups (Leader identity matters)

If score > 1.0 but group is LEADER_DRIVEN:
- Focus on identifying the leader stock specifically.
- Sector breadth less meaningful.
- Consider leader stock's individual cloud turn as the primary signal.

### Priority 3 — L3 groups (broader coverage)

L3 groups provide more symbols per group, reducing n=1 mechanical bias.
Use L3 as the primary rotation layer in daily dashboard views.
L4 strict groups remain valid for Private Bank, Small Broker, Small Developer.

---

## 4. Not Recommended

- Flag-based buckets with bl_ratio < 1.0 in A3 replay: not useful as A3 hard filters.
- NOISY_OR_THIN groups (< {P1_MIN_EVENTS} turn events): insufficient history, use L3 parent instead.
- Any score-based auto-execution or automated position adjustment.

---

## 5. Open Issues

### OI-P1-1 (HIGH): No daily NAV series for true portfolio MAR
A3 ledger has trade-level returns only. True portfolio MAR requires daily NAV with capital allocation.
Fix: Build daily NAV proxy from ledger using sequential trade timestamps and capital fraction.

### OI-P1-2 (MEDIUM): Theme tag coverage varies
Some theme tags have <50 stock cloud turns despite n>=5 symbols. Results for low-coverage themes
should be treated as indicative only.

### OI-P1-3 (LOW): follower_score requires real-time daily computation
The proposed follower_score needs a daily counter of group member cloud flips.
This requires integrating into the Phase36 daily scan output.

### OI-P1-4 (LOW): leader_drag_penalty requires classification refresh
Leader classification uses historical data. A group classified as LEADER_DRIVEN historically
may be BROAD_BASED in the current market. Consider a rolling 12-month re-classification.

---

## 6. Production Change Required (Future)

If evidence clears all adoption gates, a separate production-change memo must be written and
approved before any integration with A3/OMS. Required gates for hard filter:
- A3 replay: trade-level MAR improvement >= +0.05 AND bl_ratio >= 1.2 for the target group
- Filter value: Δhit_rate_60d >= 3pp AND Δmean >= 1% for n>=5 groups
- Survives ex-VIN universe
- Survives 2012–2019 and 2020–2026 split
- Placebo validation >= 95th percentile

Current status: **No group has cleared all gates. Dashboard feature only.**
"""

    P1_RANKING_PROPOSAL_PATH.write_text(text, encoding="utf-8")
    log.info("Ranking feature proposal saved to %s", P1_RANKING_PROPOSAL_PATH)
    return text
