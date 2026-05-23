# Institutional Accumulation Scan — Multi-AI Review Workflow

**Purpose:** External QA of methodology v1.1 without touching execution/OMS/live trading.

**Package:** `outputs/review_packages/institutional_accumulation_scan_chatgpt.zip`

## Five stages

| Stage | Who | Input | Output |
|-------|-----|-------|--------|
| **1** | ChatGPT | Zip + `REVIEW_PROMPT.md` | Initial PASS/FAIL + optimization ideas |
| **2** | Claude Code | Same zip + `prompts/CLAUDE_CODE_REVIEW_PROMPT.md` | Fresh-eyes code + output audit |
| **3** | Claude Code | Scan outputs + priors + regime | `institutional_accumulation_weekly_brief_{date}.md` (weekly-style, research-only) |
| **4** | Claude Code | Stages 2–3 | `RETURN_HANDOVER_TO_CHATGPT.md` + optional `claude_review_return.zip` |
| **5** | ChatGPT | Stage 1 + Stage 4 handover | Final `CURSOR_IMPLEMENTATION_PROMPT.md` for Cursor |

## Operator commands

```powershell
# Validate only (fail-closed checks, no zip)
python -m scripts.reporting.validate_institutional_accumulation_package

# Rebuild review zip (full scan + package, fail-closed)
python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of 2026-04-30

# Zip only (existing outputs; prints WARNING — aborts if prompt/outputs drift)
python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of 2026-04-30 --no-refresh
```

**Review safety:** Use only `institutional_accumulation_scan_chatgpt.zip`. Read `PACKAGE_INTEGRITY.json` inside the zip — not extracted folders under `review_packages/`.

## Hard boundaries (all stages)

- **In scope:** scan methodology, universe policy, fund context buckets, grouped money-flow, tiers, emerging branch, VIN distortion, validation blocks, report sections, compact JSON.
- **Out of scope:** `final_action`, A3/S3 production rules, OMS, DNSE, TP/trail, order routing, position sizing, live capital.

## Files in zip

See `MANIFEST.txt` inside the zip after build.
