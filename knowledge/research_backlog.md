# VN Agent System — Research Backlog

Items approved for research but not yet implemented. Each item has pre-registered decision gates.

---

## Queue Mechanics (added 2026-07-09)

### Autonomous execution classification

Before any item enters this backlog, classify it:

| Class | Meaning | Agent can run without human prompt? |
|---|---|---|
| **AUTO** | Objective metric, pre-registered gate, verifiable output | Yes — agent runs, logs result, flags if gate fires |
| **HUMAN-IN-LOOP** | Requires judgment call or dual-judge approval at gate | No — agent preps review pack; human routes to judge |
| **NOT-AUTOMATABLE** | Soft evaluation, regime-narrative, source-of-truth conflicts | No — human-driven; agent only extracts/summarizes |

Add `Exec-class:` field to each item. No item without a classification enters the queue.

### Priority tiers

| Tier | Meaning |
|---|---|
| **P1** | Blocks live promotion gate or active strategy config |
| **P2** | Active research program — runs next available worker cycle |
| **P3** | Deferred — revisit only after P1+P2 resolved |
| **REF** | Reference-only — no action pending; closed item retained for audit trail |

### Worker assignment

Current focus (2026-07-09):
- P1 worker: none (no live promotion gate open)
- P2 worker: shadow_a3rs_s1 monitoring + S2 evidence tracker
- Autonomous loop: DATA_SENTINEL checks (see `docs/workflow/DATA_SENTINEL.md`)

**To add a new item:** Paste below existing items. Required fields: Added, Priority, Exec-class, Status, Objective, Pre-registered gates, Kill criterion.

---

## 1. Diversity-Weighted Benchmark Test

**Added:** 2026-06-28
**Status:** Gate B IMPLEMENTED → FAIL. Gate A/C remain DEFERRED.
**Gate B result:** r=-0.058, hit=50.6%, rolling stability 0%. Bull-only exploratory: r=0.51/hit=68% (n=28, not actionable).
**Priority:** Reference-only diagnostic. Gate A/C deferred to A3_RS review cycle — low priority given Gate B failure.
**Review pack:** `00. Command Center/05_AI_Handoffs/2026-06-28-0300_ReviewPack_DiversityBenchmark.md`
**Decision:** `00. Command Center/05_AI_Handoffs/diversity-benchmark-20260628_DecisionReceived.md`

### Objective
Evaluate diversity-weighted VN liquid universe as: (a) A3_RS benchmark, (b) breadth/market-health indicator, (c) concentration-control reference.

### Method
w_i = μ_i^p / Σ μ_j^p, where μ_i = median trailing 60d ADV.
p = {1.00, 0.75, 0.625, 0.50, 0.375, 0.25, 0.00}

### Universe (point-in-time required)
- VN100 with frozen reconstitution log (no survivorship bias)
- ex-VIN, ex-bank, top-ADV-filtered variants

### Pre-registered Decision Gates

**Gate A — Investable benchmark (deferred to A3_RS review):**
- Post-cost (20bp) excess return ≥ 1.0% ann., IR ≥ 0.3 vs VN100
- Turnover ≤ 100% ann., maxDD ≤ VN100 + 5pp
- Factor attribution: residual > 50% of excess (not just size + low-vol)
- Clarification: these gates determine investable/hurdle status, not required for reference-only use

**Gate B — Breadth indicator (approved for earlier standalone build):**
- Diversity spread (p=0.50 minus p=1.00) correlates with subsequent 1-month VN100 return (r > 0.15)
- OR: diversity spread regime-classifies with hit rate > 55%
- Additional requirement: stability across rolling windows and regimes before adding to weekly monitor
- Label: RESEARCH_ONLY until stability validated

**Gate C — Concentration reference (deferred to A3_RS review):**
- HHI at p=0.50 ≤ 50% of HHI at p=1.00
- Sector active weight max deviation > 3pp from cap-weighted

### VN microstructure modeling required
- 7% daily limit → no-fill model
- T+2.5 settlement → cash drag on weekly rebalance
- 100-share lot rounding
- FOL constraint (run with and without)
- Suspended names → redistribute pro-rata

### Blocking dependency
Point-in-time VN100 membership data availability (FireAnt or HOSE historical records)

### Next action
Confirm data availability for point-in-time universe. If available → write Cursor handoff for Gate B standalone build.

---

## 2. Regime-Based Exit (Dai/Zhang/Zhu 2010)

**Added:** 2026-06-28
**Status:** HOLD — requires IS/OOS backtest before touching production
**Priority:** After Gate B diversity benchmark validates (provides regime-conditional infrastructure)
**Review pack:** `00. Command Center/05_AI_Handoffs/2026-06-28-0251_ReviewPack_KnowledgeIntegration.md`

### Objective
Evaluate regime-probability-threshold exit as complement to -8% kill-switch.

### Key design notes (from Opus council)
- Complements kill-switch, does not replace it (different failure modes: idiosyncratic vs systemic)
- Run as earlier, softer overlay; keep -8% as backstop
- Validate no destructive double-trigger in backtest
- VN inputs available: VN-Index momentum, foreign flow (FireAnt), SBV liquidity (FRED)

### Integration target
3WT pilot exit rule + A3_DP (TREND_OVERLAY) exit logic

### Backtest required
IS/OOS on VN universe 2012-2026, regime instability check, placebo pass

### Next action
Design backtest spec with pre-registered gates (follow diversity benchmark gate pattern)
