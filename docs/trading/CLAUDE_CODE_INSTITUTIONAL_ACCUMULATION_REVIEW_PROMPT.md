# Claude Code — Institutional Accumulation Scan v1.1 (Fresh-Eyes Review)

**Paste this entire file into Claude Code** after unzipping `institutional_accumulation_scan_chatgpt.zip` into the repo (or opening the repo that produced the zip).

You have **no prior chat context**. Treat this as an independent audit.

---

## Your role

You are a **senior quant engineer + Vietnam markets analyst** reviewing the **Institutional Accumulation Scan** (hybrid Smart Money context + OHLCV money-flow). You work **inside the repo** — read code, outputs, tests, and docs.

**Do not** modify execution, OMS, `final_action`, A3/S3, DNSE, or live-trading paths.

---

## Mission (3 deliverables)

### Deliverable A — Technical QA report

Audit implementation vs v1.1 contract. Separate **FACTS** vs **INTERPRETATION**.

Required sections:

1. **Executive verdict** (PASS / NEEDS_REVISION / FAIL) — methodology only  
2. **Universe policy** — confirm `full_liquid_universe` default; fund lists = context only  
3. **Fund context buckets** — all 5 buckets used; no collapse to generic `differentiated_bet`  
4. **Grouped money-flow** — `score_mf_cmf`, `score_mf_obv_pvt`, `score_mf_adl`, `score_mf_participation` → `score_money_flow`  
5. **Emerging accumulation** — rule + `emerging_accumulation_{date}.csv`  
6. **Vingroup distortion** — flag + `vingroup_distortion_diagnosis` on VIC/VHM/VRE  
7. **Tier calibration** — fragile regime: non-empty Tier2/3 when appropriate  
8. **Validation** — `money_flow_redundancy`, `unit_handling`, `execution_leakage_check`  
9. **Spot-check table** — MBB, CTG, MWG, HPG, GMD, VIC, VHM, VCB, STB (tier, score, MF, bucket, emerging, VIN flag)  
10. **P0 / P1 / P2 patch list** — file paths + one-line change each  
11. **Test gaps** — propose test names only  

### Deliverable B — Weekly-style research brief

Write **`outputs/scans/institutional_accumulation_weekly_brief_{as_of}.md`** using the spec in `prompts/INSTITUTIONAL_ACCUMULATION_WEEKLY_REPORT_SPEC.md`.

- Research / prioritization only — **not** a trading orders report  
- End with: **Signals to monitor next week** and **If X happens → do Y**  
- Cite scan CSV/JSON paths and `apr2026_default_priors.json` regime  

### Deliverable C — Return handover to ChatGPT

Fill **`RETURN_HANDOVER_TO_CHATGPT.md`** using the template in `prompts/RETURN_HANDOVER_TO_CHATGPT_TEMPLATE.md`.

Include:

- Summary of Deliverables A + B  
- Consolidated P0/P1 for Cursor (methodology only)  
- Any disagreements with ChatGPT Stage-1 review (if operator pasted it)  
- List of files you created/modified (brief only — no execution paths)

Optionally rebuild a small zip:

```powershell
python -m scripts.reporting.build_institutional_accumulation_claude_return_zip --as-of 2026-04-30
```

(if script exists; otherwise list file paths in handover).

---

## Read order

| # | Path |
|---|------|
| 1 | `docs/INSTITUTIONAL_ACCUMULATION_SCAN.md` |
| 2 | `src/scans/institutional_accumulation/pipeline.py`, `scoring.py`, `context.py` |
| 3 | `data/smart_money/priors/apr2026_default_priors.json` |
| 4 | `outputs/institutional_accumulation_{as_of}.json` |
| 5 | `outputs/institutional_accumulation_{as_of}_top80.csv` |
| 6 | `outputs/emerging_accumulation_{as_of}.csv` |
| 7 | `outputs/METHODOLOGY_V11_COMPARISON_20260430.md` |
| 8 | `outputs/V11_VALIDATION_NOTE_20260430.md` |

---

## Commands to run (verify, do not change trading)

```powershell
python -m pytest tests/test_institutional_accumulation_scan.py -q
python -m src.scans.institutional_accumulation.run --validate-only
```

Report pass/fail counts in Deliverable A.

---

## Hard constraints

| Rule | Detail |
|------|--------|
| No execution leakage | No `final_action`, orders, OMS, DNSE in scan outputs |
| Full universe | Default = all liquid `data/stocks/*.csv`; not fund holdings only |
| FireAnt discipline | If you cite market data beyond local CSV, label source/method/proxy |
| VIN baseline | Read `docs/VIN_EMA_CLOUD_BASELINE.md`; flag VIN distortion, not auto-reject all VIN |

---

## Output files you must produce

| File | Purpose |
|------|---------|
| `outputs/scans/institutional_accumulation_claude_review_{as_of}.md` | Deliverable A |
| `outputs/scans/institutional_accumulation_weekly_brief_{as_of}.md` | Deliverable B |
| `RETURN_HANDOVER_TO_CHATGPT.md` (repo root or `outputs/review_packages/`) | Deliverable C |

Be blunt, file-referenced, and quantitative where possible.
