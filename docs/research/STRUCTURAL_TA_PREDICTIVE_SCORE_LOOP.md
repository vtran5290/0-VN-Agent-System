# Structural TA score — predictive value research loop (RESEARCH ONLY)

**Status:** Development loop frozen at **iter_05** (`FROZEN_CANDIDATE.json`). Confirmation **gate patched** (2026-08-29); F5/F6 remain sealed until ChatGPT **re-clears** the gate. Do **not** run `confirm --authorize-chatgpt-reclear` without that APPROVE.  
**Does not change:** `vn_ta_fireant_cli.py` production scoring, OMS, `final_action`, weekly lean `#structural-ta`.

## Goal

Find a **weekly structural support score** (re-weight / ablate six existing buckets) with the best **development/validation** date-level predictive value, then **once** confirm on sealed F5/F6. Not a production signal.

## Current score (FACTS)

Source: `scripts/vn_ta_fireant_cli.py` → `weekly_structure.structural_support_score` / `score_breakdown`.

| Bucket | Cap |
|--------|-----|
| `ma_confluence` | 20 |
| `horizontal_pivot` | 20 |
| `role_reversal` | 15 |
| `prior_base_origin_markup` | 15 |
| `volume_absorption` | 20 |
| `momentum_invalidation` | 10 |

v1 varies **multipliers / enabled flags only**. Bucket logic stays in CLI.

## ChatGPT REDIRECT (binding)

1. **PIT universe:** ADV50 from FireAnt `value`, trailing 50 sessions as-of each Friday (zeros count; active = any value>0 in last 10). Cap 236; dates with &lt;80 names are underpowered and excluded. Weekly history counted **as-of**, not full-panel. Missing scores stay **null**. ex-VIN is the **selection** primary; full is disclosed. Do **not** use the 2026-08-27 ADV50 list as historical membership.
2. **Folds:** reference `walkforward_folds.yaml` v1.1 by ID. **F1–F4** = development/validation. **F5/F6 sealed** until frozen spec hash + `confirm`. Store `target_date`; drop rows whose forward window ends after the fold `oos_end`.
3. **Metric:** mean **per-Friday** cross-sectional Spearman IC, 13w, **ex-VIN**, development dates. Quintiles **within date**. Moving-block bootstrap (block=13 IC obs, PCG64 seed 20260828). Stop metric is **development/validation IC**, not untouched OOS.
4. **Grid:** `week_step=1` for evidence. `--smoke` (`week_step=4`) stamps `DIAGNOSTIC_NOT_EVIDENCE` and must not emit IC.
5. **Cache:** `build-features` once (pinned hashes) → cheap `recompose` per weight iteration. Hash-mismatch resume refused. No overwrite of `iter_XX` without `--run-id`.

DeepSeek COLLECT (EXTERNAL-DRAFT) also required: missing-as-null, symbol uppercase before join, duplicate-date drop — implemented in `normalize_panel` / `composite_score`.

## Commands

```text
python scripts/research/structural_ta_predictive_score_loop.py preflight --spec data/research/structural_ta_predictive/spec_baseline.json
python scripts/research/structural_ta_predictive_score_loop.py build-features --spec ...
python scripts/research/structural_ta_predictive_score_loop.py recompose --spec ... --iteration 0
python scripts/research/structural_ta_predictive_score_loop.py evaluate --spec ... --iter-dir data/research/structural_ta_predictive/iter_00
# After freeze (F5/F6 still sealed):
python scripts/research/structural_ta_predictive_score_loop.py record-freeze --spec .../spec_iter_05.json --iter-dir .../iter_05 --spec-hash <frozen>
python scripts/research/structural_ta_predictive_score_loop.py confirm-preflight --spec ... --iter-dir .../iter_05 --spec-hash <frozen> --baseline-iter-dir .../iter_00
# Only after ChatGPT APPROVE of patched confirmation gate:
python scripts/research/structural_ta_predictive_score_loop.py confirm \
  --authorize-chatgpt-reclear \
  --approved-preflight-sha256 <sha256 of reviewed confirm_preflight.json> \
  --spec ... --iter-dir .../iter_05 --spec-hash <frozen> \
  --baseline-iter-dir .../iter_00
```

Legacy `run` is **REFUSED**. `evaluate` cannot open F5/F6. `confirm` without `--authorize-chatgpt-reclear` is **REFUSED**.

## Confirmation gate (patched 2026-08-29; pending ChatGPT re-clear)

Module: `scripts/research/structural_ta_predictive_confirm.py`.

- **Primary:** F5/F6 (and combined) **ex-VIN** mean date-level Spearman IC 13w — not F1–F4 development IC.
- **Disclosure:** full-universe alongside ex-VIN; F6 labeled `mixed/VIN_distorted`.
- **Comparator:** CLI baseline (`iter_00`) and paired per-Friday IC delta for **ex-VIN and full** in the same confirm event.
- **Approved snapshot:** `confirm` validates `FROZEN_CANDIDATE.json` + `confirm_preflight.json` identity bindings (obs parquet SHA, gate module SHA, baseline path/hash) before IC.
- **Coverage:** `audit_paired_coverage` — candidate vs baseline must share identical eligible date/symbol sets; else `coverage_invalid` → readout `INVALID`.
- **One-shot:** exclusive lock claimed **before** F5/F6 IC; `--approved-preflight-sha256` hash-pins reviewed `confirm_preflight.json`; atomic metrics+receipt write with metrics SHA on receipt; post-claim failure → permanent `confirmation_spent.json` (no retry); no `--run-id` escape.
- **Readout (predeclared):** `FAIL` | `DIRECTIONAL_PASS_INCONCLUSIVE` | `RESEARCH_CONFIRM_PASS` | `INVALID`.
- **Preflight:** hashes + row/date counts only — **never** F5/F6 IC.
- **Caveat on receipt:** `confirmation_gate_declared_after_development_disclosure` (gate written after F1–F4 disclosure).

On confirm **FAIL**: archive candidate; stop loop; no fallback peek of other iters on F5/F6.

## Loop (after feature panel is pinned)

Grok may change multipliers/enabled **inside** `search_space` without ChatGPT re-clear. ChatGPT/council re-clears protocol-boundary changes and must review the frozen spec **before F5/F6 confirm** or any production proposal.

Stop (development): min 5 iterations; stop after 2 consecutive non-improvements on mean date-level ex-VIN IC (F1–F4). Then `record-freeze` → `confirm-preflight` → ChatGPT gate re-clear → authorized `confirm`.

## If X happens → do Y

- If preflight usable dates have &lt;80 names → those dates unavailable; do not backfill with future members
- If ex-VIN IC and full IC disagree in sign → do not select that spec
- If Grok changes universe/folds/metric/horizon/search_space → stop; ChatGPT re-clear
