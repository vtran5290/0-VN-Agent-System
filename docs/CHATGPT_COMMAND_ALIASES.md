# ChatGPT command aliases (contract reference)

Use these in ChatGPT to drive the hybrid workflow. Cursor engine consumes **machine output only** (JSON); human prompts are markdown-only.

| Alias | Contract | Cadence |
|-------|----------|---------|
| **PromptList** | List of prompts / steps for the week. | Weekly |
| **DualExtract** | One long report → deep markdown (human) + **strict JSON** machine intake (Dual Output). | Per report |
| **ResearchEngine** | **STRICT JSON only.** Non-fund documents: macro, sector, company, policy, strategy_note, flashnote. No allocation, no trade advice, no sizing. Output: research_engine_pack with extraction_mode=non_fund_intake_v1, drift_guard.interpretation_added=false, decision_added=false. | Weekly (Information Flow) |
| **BizSummary** | Human-only: markdown company/sector deep dive. | Ad hoc |
| **MacroDeep** | Human-only: markdown macro deep dive. | Ad hoc |
| **SectorDeep** | Human-only: markdown sector deep dive. | Ad hoc |
| **CouncilRun** | After Cursor weekly: run council prompts (orchestrator → constraint_enforcer); save council_output.json. | Weekly |
| **MonthlyRegimeRun** | Monthly regime / Capital Flow: consensus pack (fund commentary / holdings). | Monthly |
| **BondSnapshot** | Extract bond/monetary snapshot (US + VN rates) → bond_monetary_snapshot.json; Cursor applies via `make bond-snapshot-apply`. | When new data |
| **ParetoWeeklyRun** | Weekly decision-support only: positions → scan → weekly report → optional order-intent dry run. **No orders.** Script: `.\scripts\trading\weekly_pareto_operator.ps1`. | Weekly |
| **ManualCloudException** | Log when manual EMA/cloud view disagrees with phase36 CSV. Template: `templates/manual_decision_log_template.md`. Manual override is outside OMS. | As needed |
| **RoadmapStatus** | Show current stage, next gate, evidence counters, blockers. Command: `python -m src.review.cli roadmap-status`. Tracker: `data/roadmap/stage_tracker.yaml`. | Weekly / monthly |
| **OrderIntentDryRun** | Generate `data/trading/order_intent/order_intent_YYYY-MM-DD.csv` from positions + scan; `order_sent=NO`. **This command does not send broker orders.** | Weekly |

## Lane rules

1. **ResearchEngine** = STRICT JSON only; no interpretation, no decision in pack.
2. **DualExtract** = deep markdown + JSON machine intake for one long report.
3. **Human prompts** (BizSummary, MacroDeep, SectorDeep) = markdown only; no JSON.

## Cursor targets (after ChatGPT produces JSON)

- Research pack → `make research-pack-apply` (or `make research-pack-apply-strict`).
- Consensus pack → `make consensus-apply`.
- Bond snapshot → `make bond-snapshot-apply`.
- Weekly flow → `make weekly` → `make council-secretary-weekly` → (CouncilRun in ChatGPT) → optional `make weekly` again.
