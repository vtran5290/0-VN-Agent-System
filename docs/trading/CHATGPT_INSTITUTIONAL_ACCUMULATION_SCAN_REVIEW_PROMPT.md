# ChatGPT Orchestrator — Institutional Accumulation Scan v1.1 (5-Stage Review)

**Attach:** `institutional_accumulation_scan_chatgpt.zip`  
**Paste:** this entire file into a **new ChatGPT** conversation.

## Two dates (do not conflate)

| Layer | Date in this package | Rule |
|-------|----------------------|------|
| **Market / accumulation scan** | **`2026-05-21`** (`scan_date` in CSV/JSON; filenames `*_2026-05-21.*`) | OHLCV, money-flow, tiers, emerging — all sliced **through scan_date** (no lookahead). |
| **Fund disclosure context** | **April 2026** (`apr2026_default_priors.json`; build uses `--smart-money-month 2026-04`) | Fund lists/tags are **context only** — not the price as-of. |

**Wrong:** Treating April fund month as the market as-of. **Right:** May-21 prices + April fund priors.

## Review safety (package integrity)

- Review **only** the attached **`.zip` file** — not folders previously extracted under `outputs/review_packages/`.
- Extracted copies are **not** refreshed when the zip is rebuilt and are often **stale**.
- **`PACKAGE_INTEGRITY.json`** inside the zip is the machine-readable source of truth for row counts, emerging count, tests, and file hashes.
- **`REVIEW_PROMPT.md`** delivery facts must match `PACKAGE_INTEGRITY.json` (the build pipeline enforces this before zipping).

You coordinate a **3-tool review loop**: ChatGPT (you) → Claude Code (fresh eyes + weekly brief) → ChatGPT (synthesis) → Cursor (implementation).

---

## Safety invariant (all stages)

> Institutional Accumulation Scan is **research / prioritization only**. It does **not** set `final_action`, issue orders, or change OMS/DNSE/live trading.

**Out of scope for every stage:** execution logic, A3/S3, TP/trail, position sizing, capital deployment.

---

## Package contents

| Path in zip | Role |
|-------------|------|
| `REVIEW_PROMPT.md` | **This file** — ChatGPT orchestrator |
| `WORKFLOW.md` | Stage diagram + operator commands |
| `prompts/CLAUDE_CODE_REVIEW_PROMPT.md` | Paste into **Claude Code** (Stage 2–4) |
| `prompts/INSTITUTIONAL_ACCUMULATION_WEEKLY_REPORT_SPEC.md` | Weekly-style brief structure for Claude |
| `prompts/RETURN_HANDOVER_TO_CHATGPT_TEMPLATE.md` | Claude fills and returns to you (Stage 4) |
| `prompts/CURSOR_IMPLEMENTATION_TEMPLATE.md` | Your Stage 5 output shape for Cursor |
| `docs/INSTITUTIONAL_ACCUMULATION_SCAN.md` | Methodology v1.1 |
| `outputs/*` | Full scan **`2026-05-21`** + operator summary `.html` / `.md` (operators start with `.html`) |
| `src/scans/institutional_accumulation/` | Implementation |
| `PACKAGE_INTEGRITY.json` | **Source of truth** — rows, emerging, ETF/VIC/VHM checks, test count, hashes |

---

# STAGE 1 — Your initial review (do this first)

## Your role

Independent **QA / quantitative research reviewer**. Validate methodology v1.1:

1. Full liquid universe (`universe_policy.mode = full_liquid_universe`)  
2. Fund context: core, second_ring, commentary, selective_bet, outside_disclosure + **emerging** branch  
3. Grouped money-flow (4 sub-scores → `score_money_flow`)  
4. Vingroup distortion + diagnosis  
5. Fragile-regime tier calibration  
6. Validation: redundancy, units, execution leakage  
7. Zip manifest matches claims (top80, emerging csv, comparison md)

**Do not** recommend buy/sell orders or OMS changes.

## Critical universe rule

| Concept | Correct |
|---------|---------|
| Scan universe | ALL liquid `data/stocks/*.csv` after ADV/history gates |
| Fund lists | Context tags/scores only — **not** universe filter |
| Emerging | Tier1–3 + MF≥48 + liquid + **no** fund disclosure tag + **risk_penalty ≤ 30** |
| ETF / open-fund | Excluded (`Quỹ mở`, `E1VFVN30`) — not in scan or emerging CSV |

## Delivery facts (verify in zip)

**Source of truth for counts:** `PACKAGE_INTEGRITY.json` inside the zip (must match this table).

| Item | Expected |
|------|----------|
| Methodology | `v1.1` (+ P1 hardening) |
| Market scan as-of | **`2026-05-21`** (filenames `*_2026-05-21.*`) |
| Fund context month | **April 2026** (`apr2026_default_priors.json`; not May OHLCV) |
| Rows scored | **1562** (2 ETF/open-fund excluded) |
| Emerging candidates | **28** |
| OHLCV | `data/stocks/` + VNINDEX benchmark — sliced through **2026-05-21** |
| Tests in repo | `tests/test_institutional_accumulation_scan.py` — **17 passed** |

## P1 hardening (verify in code + outputs)

| ID | Fix | Acceptance |
|----|-----|------------|
| P1-a | `EMERGING_MAX_RISK_PENALTY = 30` | TNT, KSF, PVP not emerging; VIC not emerging |
| P1-b | ETF exclusion | `E1VFVN30` absent from all scan outputs |
| P1-c | VIN diagnosis | When `vingroup_distortion_flag` on VHM, diagnosis cites `daily_CMF_missing` if daily CMF null |
| P1-d | Regression tests | 17 methodology-only tests pass |

**Spot-check (2026-05-21):** Use `outputs/consensus_spot_check_reference.csv` + `outputs/institutional_accumulation_2026-05-21.csv`; confirm VIC **not** emerging, E1VFVN30 absent.

## Stage 1 checks (11)

1. Research-only boundary  
2. Full-universe scan  
3. Commentary + emerging  
4. Smart Money integration + `universe_policy` in JSON  
5. No lookahead  
6. Money-flow de-correlation (grouped + redundancy block)  
7. Vingroup distortion logic (flags may be off at this as-of — verify code + actual CSV)  
8. Tier calibration (fragile sample: non-empty Tier2/3)  
9. Output schema (`fund_context_bucket`, `score_mf_*`, `price_unit_mode`, …)  
10. Compact JSON (`tier3_near_miss` when Tier1/2 empty)  
11. Emerging vs consensus balance in full run  

## Stage 1 output format

```markdown
## STAGE 1 VERDICT: PASS | NEEDS_REVISION | FAIL

### Checks 1–11
(table: check | PASS/FAIL | evidence)

### Optimization proposals (methodology only)
| ID | Priority | Change | Rationale |

### Open questions for Claude Code
(bullet list)
```

**Stop after Stage 1** and tell the operator:

> **Next:** Open Claude Code in the repo, unzip/use this package, paste `prompts/CLAUDE_CODE_REVIEW_PROMPT.md`, run the review, produce the weekly brief + filled `RETURN_HANDOVER_TO_CHATGPT.md`, then paste that handover back here for Stage 5.

---

# STAGE 2–4 — Claude Code (operator runs; you wait)

Operator instructions (copy to operator):

1. Unzip `institutional_accumulation_scan_chatgpt.zip` into repo (or use repo that built it).  
2. In **Claude Code**, paste full text of **`prompts/CLAUDE_CODE_REVIEW_PROMPT.md`**.  
3. Claude produces:  
   - `outputs/scans/institutional_accumulation_claude_review_{as_of}.md`  
   - `outputs/scans/institutional_accumulation_weekly_brief_{as_of}.md`  
   - `RETURN_HANDOVER_TO_CHATGPT.md` (from template)  
4. Optional: `python -m scripts.reporting.build_institutional_accumulation_claude_return_zip --as-of 2026-04-30`  
5. Operator pastes **`RETURN_HANDOVER_TO_CHATGPT.md`** (+ Claude review md if useful) **back into this chat**.

---

# STAGE 5 — Your final synthesis (after Claude handover)

When operator returns Claude's handover:

1. **Reconcile** Stage 1 vs Claude findings — mark agreements/conflicts with evidence.  
2. **Merge** P0/P1 lists (de-duplicate; escalate true P0 conflicts).  
3. **Produce final artifact for Cursor** using template below.

## Required final block

```markdown
## FINAL VERDICT (post Claude + ChatGPT)

### Reconciliation
| Topic | ChatGPT S1 | Claude | Resolved |

### Consolidated P0/P1 (methodology only)
...

## CURSOR_IMPLEMENTATION_PROMPT

**Scope:** `src/scans/institutional_accumulation/` + docs + tests + scan outputs only.
**Forbidden:** execution, OMS, `final_action`, A3/S3, DNSE, live trading.

### P0 tasks
1. [file path] — change — acceptance criterion
...

### P1 tasks
...

### Tests to run after patch
```powershell
python -m pytest tests/test_institutional_accumulation_scan.py -q
python -m src.scans.institutional_accumulation.run --as-of YYYY-MM-DD
python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of YYYY-MM-DD --no-refresh
```

### Definition of done
- [ ] All P0 resolved
- [ ] Spot-check 9 symbols unchanged or explained
- [ ] execution_leakage_check ok
- [ ] Zip rebuilt and manifest matches
```

Operator then pastes **`CURSOR_IMPLEMENTATION_PROMPT`** into **Cursor** as the last implementation step.

---

## Regenerate package (operator)

```powershell
# Market as-of today; fund context pinned to April 2026
python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of 2026-05-21 --smart-money-month 2026-04
```

---

*VN Agent System — Institutional Accumulation Scan external review orchestrator.*
