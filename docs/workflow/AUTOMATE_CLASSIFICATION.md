# Automate Classification — VN Agent System

**Purpose:** Evaluation-first gate for every recurring task in this system.
Before assigning a task to an agent loop, classify it by whether it has a hard evaluator.

Core principle (from auto-research framework): "If you cannot evaluate it, do not auto-research it."
Agent loops work best when the output is verifiable by an objective metric — not when the
evaluation requires judgment, narrative interpretation, or consequence-awareness.

---

## Classification table

### FULLY AUTO — agent runs, verifies against objective metric, logs result

These tasks have a hard pass/fail criterion. Agent can run indefinitely without human-in-loop
for the core loop. Human only reviews exceptions or gate fires.

| Task | Evaluator | Agent action on fail |
|---|---|---|
| Data freshness sentinel checks | File age vs. threshold (DATA_SENTINEL.md) | Flag + halt downstream |
| Backtest run (pre-registered candidate) | OOS MAR, MaxDD, sub-regime floors | Log PASS/FAIL per pre-reg gate |
| Schema validation (`/schema-guardian`) | JSON schema match | Log violations |
| Paper check existence | File date vs. current date | Flag `[PAPER-CHECK-GAP]` |
| Kill criterion status check | KILL-CANDIDATE present/absent | Escalate immediately if present |
| `.env` git tracking check | git status output | HALT if tracked |
| S2 quarantine check | `final_action/` contains no S2 files | HALT if violated |
| Report render (`/report-render`) | File exists with today's date | Log failure |
| Stale rule audit (quarterly) | File mtime vs. 90-day threshold | Flag list to user |
| Research backlog queue scan | Item has `Exec-class`, `Priority`, `Kill criterion` | Flag incomplete items |

### HUMAN-IN-LOOP — agent preps, human approves or routes to judge

These tasks have structured outputs but require a judgment call at a gate.
Agent does all the preparation; human does the decision.

| Task | Agent role | Human decision |
|---|---|---|
| Strategy promotion (Trigger #5) | Build review pack + pre-reg gate assessment | Dual-judge + written approval |
| Regime state update | Extract data + produce regime briefing | Confirm regime label |
| Weekly note + Cortex belief update | Propose belief updates from week's data | Approve or reject each proposal |
| Decision-quality log entry | Draft log entry for qualifying decisions | Confirm rating before finalizing |
| New research queue item | Draft pre-reg with gates + kill criterion | Approve before any test run |
| Council session routing | Build slate, probe fable, run seats | Review verdicts; break ties |
| CursorHandoff.md creation | Draft all required fields | Review before opening in Cursor |
| Review pack assembly | Build full 9-section review pack | Confirm before sending to ChatGPT |
| Data source conflict resolution | Flag [SOURCE UNCLEAR] + cite both sources | User decides source hierarchy |
| SBV macro ingest + policy tone | Fetch + structure data | Interpret direction + update macro state |

### NOT SUITABLE FOR AUTOMATION — human-driven; agent only extracts and summarizes

These tasks require nuanced judgment, have high consequence, or lack a verifiable evaluation metric.
Agent involvement is limited to extraction and summary — not evaluation or decision.

| Task | Why not auto | Correct agent role |
|---|---|---|
| Regime narrative interpretation | No objective metric; narrative-heavy | Extract data; present structure; human labels |
| Legal/M&A clause judgment | High consequence; requires professional judgment | Pre-screen extraction only; escalate to opus + ChatGPT |
| Live_auto flip | Highest stakes; no partial credit for errors | Gate check only; dual-judge + user sign-off required |
| IC memo investment conclusion | Wrong conclusion = real capital at risk | Fact-check only; human + ChatGPT own conclusion |
| Kill-candidate escalation | Requires human acknowledgment; cannot be deferred | Alert user immediately; halt all downstream |
| Source-of-truth conflict (Trigger #3) | Two SSOT files disagree; framework-level decision | Flag conflict; surface both; wait for user |
| Secrets rotation | High security consequence | Detect and alert; never touch credentials autonomously |
| Sizing / exit promotion (first-of-class) | Novel class = fable council required | Route to council; never self-approve |
| FA cohort survivorship bias correction | Requires historical universe change | Flag bias; human decides when to address |
| Research program scope expansion | Risk of unbounded search / overfitting | Require new pre-reg; escalate to user |

---

## Classification workflow (use when adding any task to a pipeline or queue)

```
1. What is the output? (file, metric, signal, decision)
2. Is there a hard evaluator? (objective metric, schema, pre-registered threshold)
   → NO: NOT-AUTOMATABLE. Stop. Assign to human.
   → YES: continue
3. If the evaluator fires (fail/flag), what is the consequence?
   → HIGH CONSEQUENCE (live capital, SSOT override, secrets): HUMAN-IN-LOOP.
   → LOW/MEDIUM CONSEQUENCE (flag, log, halt downstream): FULLY AUTO.
4. Does it require a judgment call at any point?
   → YES: HUMAN-IN-LOOP (agent preps, human decides).
   → NO: FULLY AUTO.
```

---

## Application to current research programs

| Current task | Classification | Notes |
|---|---|---|
| S2 evidence tracker daily update | AUTO | Metric-based; agent logs; no human needed unless threshold fires |
| Shadow A3_RS paper check | AUTO | File existence + signal count check |
| PM7 Rate-Cut Pivot Watch | HUMAN-IN-LOOP | Agent monitors metrics; human confirms pivot classification |
| PA-010/PA-011 pre-reg execution | HUMAN-IN-LOOP | Pre-regs exist; agent runs backtest; human reviews gate verdict |
| Weekly regime report | HUMAN-IN-LOOP | Agent builds; human confirms regime label + Cortex belief updates |
| Session-start gate | AUTO (steps 1-5) + HUMAN-IN-LOOP (steps 6-7) | See DATA_SENTINEL.md |
| Promotion council (any new overlay) | NOT-AUTOMATABLE (council) + HUMAN-IN-LOOP (prep) | Agent builds review pack only |

---

## Anti-patterns to avoid

Per the transcript: the failure mode is applying agent loops to tasks where the evaluation is soft.

| Anti-pattern | What it looks like | Correct action |
|---|---|---|
| "Explore and see what you find" | Agent runs open-ended parameter search without pre-reg | Stop. Write pre-reg first. |
| "Let the agent decide the regime" | Agent interprets policy narratives and sets regime label | Stop. Agent extracts; human labels. |
| "Run the council automatically" | Agent invokes judges without human reviewing the review pack | Stop. Human reviews pack before sending. |
| "Test a wider range and pick the best" | Post-hoc parameter selection from wide sweep | Stop. This is the overfitting failure mode. |
| "Keep testing until something works" | No kill criterion, indefinite program | Stop. Declare kill criterion before first run. |

---

Last reviewed: 2026-07-09
