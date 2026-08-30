# VN Agent — Structural TA confirmation gate — **new ask** (v5)

**Date:** 2026-08-30  
**Domain:** VN Agent System (research only)  
**Type:** Fresh authorization request — **no prior APPROVE on file** for v4 or this v5 pack.

**Ask:** May Cursor run **exactly one** authorized F5/F6 `confirm` with the pinned preflight below?

**Gate:** No F5/F6 IC in this pack. Confirmation artifacts remain absent until an authorized run.

---

## 1. Executive summary

- Frozen candidate: **iter_05**, spec hash `12c104d7c883269490a500f1b44676dfa466679ab6a2aff1f3b79876b0fa2481` (unchanged).
- Gate code **committed** at `afae2ff8b0fad2159c122c838c1169d54eaece6b` (`feat(research): structural TA confirm gate with identity pinning`).
- Metrics-suppressed preflight **regenerated from that commit**; embedded identity matches live gate hashes (**drift: none**).
- Tests: **26 passed** (`test_structural_ta_confirm_gate.py` + `test_structural_ta_predictive_loop.py`).
- F5/F6 sealed: no metrics, receipt, spent, lock, or summary.

## 2. Pin this preflight (v5)

**File SHA256 (required `--approved-preflight-sha256`):**

`b5a387989f3828f37fc14aec03696846ed037812234a030cd37e71a69ad78165`

**Git at preflight generation:** `afae2ff8b0fad2159c122c838c1169d54eaece6b`

**Embedded gate hashes (match live at regen time):**

| Field | SHA256 |
|-------|--------|
| `confirm_module_sha256` | `9242c1167ea69e7123c0e901a9154a194859924013b6fb29154268e118340987` |
| `score_loop_sha256` | `ca592287f054a3211b2ac3055dbc88599eeb8bea66ea2dd673303390bb615f0d` |
| `core_sha256` | `b49dfd1ac2ae4f674de1c78885ba7e2dbe731c3f5503597815130fc05b6e261f` |

**Coverage:** `counts.coverage_parity.valid` = true (F5/F6, ex-VIN and full).  
**IC:** `ic_computed: false`, `f5_f6_ic_disclosed: false`.

## 3. Gate behavior (unchanged from v3/v4 audit)

- Claim slot **before** F5/F6 IC computation.
- Post-claim failure → permanent `confirmation_spent.json` (no retry).
- Receipt binds `confirmation_metrics_sha256`.
- `enforce_approved_snapshot()` + `--approved-preflight-sha256` hash-pin.

**Caveat:** `confirmation_gate_declared_after_development_disclosure` — research evidence, not unbiased validation. F6: interpret **ex-VIN first** (`mixed/VIN_distorted`).

## 4. Command after APPROVE (only)

```text
python scripts/research/structural_ta_predictive_score_loop.py confirm \
  --authorize-chatgpt-reclear \
  --approved-preflight-sha256 b5a387989f3828f37fc14aec03696846ed037812234a030cd37e71a69ad78165 \
  --spec data/research/structural_ta_predictive/spec_iter_05.json \
  --iter-dir data/research/structural_ta_predictive/iter_05 \
  --spec-hash 12c104d7c883269490a500f1b44676dfa466679ab6a2aff1f3b79876b0fa2481 \
  --baseline-iter-dir data/research/structural_ta_predictive/iter_00
```

**Approval expires** if any pinned input changes before execution.

On **FAIL**, **INVALID**, or post-claim error: archive iter_05, stop loop, **no** fallback peek.  
Production CLI / OMS / `final_action` / `live_auto`: **not authorized**.

## 5. Decision requested

**APPROVE | REJECT | REDIRECT** — May Cursor run the one-shot confirm above?

## 6. Review files

- Commit: `afae2ff8` — `structural_ta_predictive_confirm.py`, `_core.py`, `_score_loop.py`, `test_structural_ta_confirm_gate.py`
- `data/research/structural_ta_predictive/iter_05/confirm_preflight.json` (regenerated 2026-08-30)
- Holistic context: `00. Command Center/05_AI_Handoffs/2026-08-30-0606_HolisticReview_VNAgent_ResearchGovernance.md`

**Obsolete — do not use:** preflight SHA `28822bf2…`, `521cb59d…`, or any chat APPROVE not filed with this v5 pin.
