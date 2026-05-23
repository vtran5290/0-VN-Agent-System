# CURSOR_IMPLEMENTATION_PROMPT (Template — filled by ChatGPT Stage 5)

**Paste this block into Cursor** after ChatGPT reconciles Claude Code handover.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `src/scans/institutional_accumulation/` | `src/trading/`, OMS, DNSE |
| `docs/trading/INSTITUTIONAL_ACCUMULATION_SCAN.md` | `final_action`, A3/S3 rules |
| `data/smart_money/priors/` | TP/trail, order routing |
| `tests/test_institutional_accumulation_scan.py` | Live capital / position sizing |
| `scripts/reporting/build_institutional_accumulation_scan_chatgpt_zip.py` | |

---

## Context

- Methodology: **v1.1**
- Scan as-of: `YYYY-MM-DD`
- Regime: `(from priors)`
- ChatGPT Stage 1 verdict: `PASS | NEEDS_REVISION | FAIL`
- Claude Code verdict: `PASS | NEEDS_REVISION | FAIL`

---

## P0 tasks (must complete)

### P0-1
- **File(s):**
- **Change:**
- **Acceptance:**

---

## P1 tasks (should complete)

### P1-1
- **File(s):**
- **Change:**
- **Acceptance:**

---

## P2 (optional)

---

## Tests & regenerate

```powershell
python -m pytest tests/test_institutional_accumulation_scan.py -q
python -m src.scans.institutional_accumulation.run --as-of YYYY-MM-DD
python -m scripts.reporting.institutional_accumulation_v11_comparison --as-of YYYY-MM-DD
python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of YYYY-MM-DD --no-refresh
```

---

## Definition of done

- [ ] P0 complete; spot-check MBB CTG MWG HPG GMD VIC VHM VCB STB documented
- [ ] `validation.execution_leakage_check.ok == true`
- [ ] `universe_policy.mode == full_liquid_universe` on default run
- [ ] top80 + emerging csv in `outputs/scans/`
- [ ] Review zip rebuilt; MANIFEST matches REVIEW_PROMPT file list

---

*Filled by ChatGPT — do not edit template in repo; copy filled version to Cursor only.*
