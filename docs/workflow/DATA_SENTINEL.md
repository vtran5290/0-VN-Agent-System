# Data Sentinel — VN Agent System

**Purpose:** Single machine-readable source for data freshness rules and auto-checks.
Consolidates scattered stale-data logic from memory-protocol.md, .claude/CLAUDE.md, and
session-start gate into one file agents can reference directly.

Referenced by: `.claude/CLAUDE.md` session-start checklist, `knowledge/research_backlog.md` queue mechanics.

---

## Freshness rules (auto-checkable)

| File / Path | Max age | Action if stale | Flag |
|---|---|---|---|
| `data/state/regime_state.json` | 7 days | Run regime check before any signal work | `[STALE-REGIME]` |
| `knowledge/weekly_notes/` (newest file) | 10 days | Flag; suggest running weekly update | `[STALE-WEEKLY-NOTE]` |
| `data/decision/kill_criterion_status.json` | 1 business day | Flag; check paper run | `[STALE-KILL-STATUS]` |
| `data/state/policy_trigger_radar.json` | 7 days | Flag; run `/macro-ingest` | `[STALE-MACRO]` |
| `data/state/capital_formation_pulse.json` | 7 days | Flag; run `/sbv` | `[STALE-SBV]` |
| `data/state/position_context_daily.json` | 1 business day | Flag; check paper run | `[STALE-POSITION]` |
| `data/state/s2_evidence_tracker.json` | 7 days | Flag; update S2 evidence | `[STALE-S2]` |
| `D:\V\.claude\rules\*.md` (any file) | 90 days | Flag for Stale Rule Audit (memory-protocol.md) | `[STALE-RULE]` |

---

## Data quality checks (auto-checkable)

| Check | Command / Method | Pass condition | Action if fail |
|---|---|---|---|
| `.env` not git-tracked | `git status .env` | "nothing to commit" or "untracked" | HALT — secrets-policy.md |
| `final_action/` write-protected from S2 | `grep -r "shadow_a3rs_s1" data/decision/final_action/` | No results | HALT — source-of-truth conflict |
| Shadow runner quarantined | `ls data/decision/shadow_a3rs_s1/` | Files present; no overlap with `final_action/` | Alert user |
| Kill criterion status | `cat data/decision/kill_criterion_status.json` | No KILL-CANDIDATE flag | If KILL-CANDIDATE → escalate immediately |
| Paper check gap | `ls data/decision/ | grep paper_check | tail -1` | Date within 1 business day | Flag `[PAPER-CHECK-GAP]` |

---

## Session-start sentinel (run in this order)

```
1. regime_state.json age check → [STALE-REGIME] if >7 days
2. kill_criterion_status.json → escalate if KILL-CANDIDATE
3. .env git status → halt if tracked
4. S2 quarantine check → halt if S2 signals in final_action/
5. paper check gap → flag if >1 business day
6. weekly_notes age → [STALE-WEEKLY-NOTE] if >10 days
7. macro/SBV pulse → [STALE-MACRO] / [STALE-SBV] if >7 days
```

Automated-agent rule: steps 1–5 are AUTO-checkable (binary pass/fail).
Steps 6–7 are HUMAN-IN-LOOP if stale — agent flags, human decides whether to update before proceeding.

---

## Mixed-source / provisional data rules

These checks require judgment — NOT auto-resolvable:

| Situation | Rule | Classification |
|---|---|---|
| SBV macro value is provisional (marked `[P]` in source) | Suppress exact pp; show direction only | HUMAN-IN-LOOP |
| Two data sources disagree on the same metric | Flag [SOURCE UNCLEAR] — Trigger #3 | HUMAN-IN-LOOP |
| Interbank rate from mixed sources (OMO + FireAnt) | Label source explicitly; do not blend | HUMAN-IN-LOOP |
| Model forward-return estimate vs realized data | Label as [ESTIMATE]; never substitute for realized | NOT-AUTOMATABLE |

---

## What NOT to automate

Per transcript principle ("if you cannot evaluate it, do not auto-research it"):

| Task | Why not auto | Required human role |
|---|---|---|
| Regime narrative interpretation | Soft evaluation; judgment-heavy | Human reads macro + decides regime label |
| Mixed-source data reconciliation | Requires source hierarchy decision | Human invokes Trigger #3 protocol if conflict |
| SBV policy tone assessment | No objective metric; narrative | Human reads policy text |
| kill_criterion_status escalation | High stakes — live capital | Human must acknowledge; cannot be deferred |

---

## Quarterly sentinel audit

Each quarter, check:
1. Are all files in the freshness table still the correct SSOT files? (Names may have changed.)
2. Did any stale flag get missed in the last quarter's sessions? (Review session transcripts.)
3. Are there new state files that should be added to this table?

Update this file when files are renamed, deprecated, or added.
Last reviewed: 2026-07-09
