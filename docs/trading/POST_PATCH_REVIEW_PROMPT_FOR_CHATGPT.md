# ChatGPT Final Review Prompt — VN Agent Auto-Trading (Post P1 Patch)

**Paste this entire file.** Review against the live repo (or a zip from `outputs/review_packages/` if the maintainer regenerated one). No prior chat context required.

---

## Your role

You are the **final reviewer** after:
1. Independent third-party review → **APPROVED_FOR_PAPER_PREVIEW** with P1 fixes
2. Cursor implementation of those P1 fixes (tests + docs only — **no strategy changes**)

Confirm the system is safe for **continued paper-live observation** only. **Real capital remains NO-GO.**

---

## Hard constraints (do not violate)

- Do **not** recommend real capital, DNSE live, or `live_auto`
- Do **not** change A3 T1/T2/TP/trail/maxhold/breadth contract
- Do **not** promote S3 or PTS to production
- Do **not** route intraday CSV to OMS
- Do **not** recommend OMS signal recompute
- `a3_rank_score` = operator review sort only — cannot create/block/size/modify orders

---

## Verified contracts (must remain true)

| Layer | Contract |
|-------|----------|
| **A3** | Only production candidate; EOD scan CSV SSOT; OMS uses `final_action` only |
| **S3 max60** | Paper-shadow only; separate ledger; no live/DNSE; max_hold=60 |
| **Phase36** | Sorting layer only (commit `1116480`); no A3 logic change |
| **Intraday v3.1** | `INTRADAY_PREVIEW`; `auto_order_allowed=False`; OMS blocks intraday paths |
| **Kill switch** | `block_on_kill_switch=True` by default |
| **Defaults** | `LIVE_TRADING=false`, `DRY_RUN=true`; real capital **NO-GO** |

---

## P1 fixes implemented (verify in zip)

| ID | Fix | Evidence in zip |
|----|-----|-----------------|
| P1-A | `test_s3_phase35.py` collects — guards on `s3_shadow_paper_ledger.py` | `src/trading/live/s3_shadow_paper_ledger.py`, tests |
| P1-B | `test_sorting_does_not_add_buy_intent` passes | `tests/test_phase36_daily_scan.py` |
| P1-C | Kill switch default blocks | `tests/test_trading_kill_switch.py`, `config/live_trading.yaml` |
| P2 | Intraday OMS block integration test | `tests/test_intraday_scan.py` |
| P2 | Docs: freeze note, VNINDEX overlay, real-capital live-mode | `docs/trading/*.md` |
| P2 | S3 max60 validation warnings (no routing) | `src/trading/live/s3_shadow_validation.py` |

**Claimed test results (re-run 2026-05-18):** 95 focused + **194** broader (14 modules) + **124** `test_trading_*` — see `review_outputs/post_third_ai_patch_test_output.txt` and `PATCH_SUMMARY.md`. Prior claim of **108** broader was **not** reproduced; do not use stale `pytest_broad.txt`.

---

## Read order in zip

1. `PATCH_SUMMARY.md`
2. `REMAINING_OPEN_ITEMS.md`
3. `docs/trading/REAL_CAPITAL_READINESS.md`
4. `docs/trading/PHASE36_FREEZE_NOTE.md`
5. `docs/trading/INTRADAY_PREVIEW_V3_1_REVIEW_NOTE.md` (if present)
6. `docs/trading/INTRADAY_VNINDEX_OVERLAY.md`
7. Patched tests + `src/trading/live/scan_resolver.py`, `order_intent.py` (if included)
8. `review_outputs/post_third_ai_patch_test_output.txt`

---

## Required output format

### 1. FACTS
What you verified from the zip vs what you infer.

### 2. P1 FIX VERIFICATION
For each P1-A/B/C: PASS / FAIL + one line evidence.

### 3. RISKS — P0 / P1 / P2
Ranked; note any regression vs third-party review.

### 4. PAPER CYCLE READINESS
Can operator run next 16:30 paper-live cycle? What pre-checks?

### 5. VERDICT (exactly one)
- **APPROVED_FOR_PAPER_PREVIEW** — continue paper observation; real capital NO-GO
- **NEEDS_FIXES** — list minimal patches only
- **BLOCKED** — critical safety issue

### 6. CURSOR PROMPT (if NEEDS_FIXES)
Copy-paste implementation prompt for Cursor; no strategy changes.

---

## Operator context

- Daily scan: `python pp_backtest/portfolio_optimization_final_steps.py --step scan`
- Paper workflow: `scripts/trading/daily_paper_live_full_run.ps1` (16:30 task)
- Intraday preview: `python -m src.trading.cli intraday-scan` — **planning only**
- Latest EOD `as_of_date` may lag calendar → stale STOP is **intended**

---

*End of ChatGPT final review prompt*
