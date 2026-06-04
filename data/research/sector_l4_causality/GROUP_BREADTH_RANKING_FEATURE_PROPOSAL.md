# GROUP BREADTH RANKING FEATURE PROPOSAL

**Date:** 2026-05-25
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

- Groups with "sector_leads" classification (excess turns >=15% above random): **39**
- Median relative lift across all eligible groups: **73.6%**
- Top groups by excess turn lift:
  - [theme_tag] **sec**: excess_turn_pct_t1_t10=2.892
  - [L3] **Brokerage**: excess_turn_pct_t1_t10=2.425
  - [theme_tag] **broker**: excess_turn_pct_t1_t10=2.405
  - [flag_bucket] **broker**: excess_turn_pct_t1_t10=2.315
  - [theme_tag] **logistics**: excess_turn_pct_t1_t10=1.360


### 1.2 Filter Value at 60d [FACTS]

- Groups passing G2 gate (delta_hit_rate_60d >= 3pp with breadth_ew >= 40%): **21**
- Top groups by delta_hit_rate_60d:
  - [flag_bucket] **construction**: delta_hit_rate=0.077
  - [theme_tag] **const**: delta_hit_rate=0.077
  - [theme_tag] **retail**: delta_hit_rate=0.076
  - [L3] **Brokerage**: delta_hit_rate=0.062
  - [flag_bucket] **broker**: delta_hit_rate=0.062


### 1.3 Leader Classification [FACTS]

- BROAD_BASED groups (leader precedes sector <30% of events): **12**
- Broad-based groups: [L3] General Contractor, [flag_bucket] retail, [flag_bucket] steel, [theme_tag] agri, [theme_tag] chem
- LEADER_DRIVEN groups are less reliable as breadth signals (leader identity matters more than breadth).

### 1.4 A3 Ledger Replay [FACTS]

- Groups where breadth gate improves trade-level MAR proxy AND bl_ratio >= 1.2: **1**
- Best A3 gate candidates (breadth_ew >= 40%):
  - [theme_tag] rubber: d_tmar=0.0568, bl_ratio=1.44, gate=PASS
  - [flag_bucket] construction: d_tmar=0.0559, bl_ratio=0.80, gate=FAIL
  - [theme_tag] const: d_tmar=0.0559, bl_ratio=0.80, gate=FAIL

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
- NOISY_OR_THIN groups (< 5 turn events): insufficient history, use L3 parent instead.
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
