# Cross-Asset Opportunity Transmission Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mandatory, machine-validated, non-scoring cross-asset sidecar that fails closed when a material shock has incomplete Vietnam-listed proxy coverage while leaving La Bàn weights and all trading paths unchanged.

**Architecture:** Add a pure stdlib validator/evaluator and a separate renderer module. The clean La Bàn builder loads the sidecar and persistent exposure registry before any write, runs the existing engine without those artifacts, then composes a T1 status strip and T3 research card. The current modified `laban_render.py`, untracked `laban_engine.py`, untracked legacy test file, generated reports, scenario data, and all trading paths remain untouched.

**Tech Stack:** Python 3 stdlib (`json`, `copy`, `datetime`, `html`, `pathlib`, `unittest`), JSON sidecars, existing La Bàn HTML marker injection, Git.

---

## Approved sources

- Design: `reports/2026-08-21_cross_asset_opportunity_gate_design.md`
- ReviewPack: `reports/2026-08-21_cross_asset_opportunity_gate_review_pack.md`
- Approval: V — `APPROVE`, 2026-08-21
- Builder: `scripts/reporting/build_vn_structural_signals.py`
- Current renderer: `scripts/reporting/laban_render.py` — read-only for this implementation
- Existing regression suite: `tests/test_laban_engine.py` — read-only for this implementation
- Workflow reference: `docs/WORKFLOW_ENGINE_EXTRACT.md`

## File map

### Create

- `scripts/reporting/laban_cross_asset_gate.py` — schema validation, reference validation, terminal-state evaluation, fail-closed rules.
- `scripts/reporting/laban_cross_asset_render.py` — pure T1/T3 HTML composition using existing CSS classes/variables.
- `data/decision/laban_cross_asset_gate.json` — operator-maintained current-run state; initial state `NOT_APPLICABLE`.
- `data/decision/laban_cross_asset_proxy_map.json` — persistent exposure-edge registry; initial PNJ/gold row is `DRAFT_POST_HOC`, not an accepted causal mapping.
- `tests/test_laban_cross_asset_gate.py` — focused unit, contract, renderer, and builder fail-before-write tests.

### Modify

- `scripts/reporting/build_vn_structural_signals.py` — add CLI paths, validate before first write, compose the sidecar into T1/T3 only.
- `docs/WORKFLOW_ENGINE_EXTRACT.md` — document the mandatory workflow and non-scoring boundary.

### Do not touch

- `scripts/reporting/laban_engine.py`
- `scripts/reporting/laban_render.py`
- `tests/test_laban_engine.py`
- `data/decision/vn_structural_signals.json`
- `data/decision/laban_scenarios.json`
- `data/decision/laban_signatures.json`
- `data/decision/laban_axis_state.json`
- `data/decision/laban_frame_log.json`
- `data/decision/laban_kill_conditions.json`
- `reports/tollbooth_tracker_latest.html` in the real workspace
- `reports/vn_structural_signals_fragment.html` in the real workspace
- A3/S3, ThemePack candidate outputs, backtest parameters, `final_action`, OMS, broker or live paths

## Task 0: Verify protected working-tree baseline

**Files:**

- No changes.

- [ ] **Step 1: Confirm the known dirty-state boundary**

Run:

```powershell
git status --short -- scripts/reporting/laban_render.py scripts/reporting/laban_engine.py tests/test_laban_engine.py reports/tollbooth_tracker_latest.html reports/vn_structural_signals_fragment.html data/decision/vn_structural_signals.json data/decision/laban_scenarios.json data/decision/laban_axis_state.json data/decision/laban_frame_log.json
```

Expected pre-existing status:

```text
 M scripts/reporting/laban_render.py
?? scripts/reporting/laban_engine.py
?? tests/test_laban_engine.py
?? reports/tollbooth_tracker_latest.html
?? reports/vn_structural_signals_fragment.html
```

The four `data/decision` files must have no status line.

- [ ] **Step 2: Confirm protected file hashes**

Run:

```powershell
$expected = @{
  "scripts/reporting/laban_render.py" = "2a0d9d8668351be770291662bc4b529795ea748ab09d6184966d9f285fd3627c"
  "scripts/reporting/laban_engine.py" = "da5bf11c6a4d7d077d82197309552ecbc1b8ad1472eb82cf8a07b24cc076293f"
  "tests/test_laban_engine.py" = "9d72ea26ca28b7ec418f60ff635e6c4a748e4ccf9fe4a3e515ea31f9193b1e75"
  "reports/tollbooth_tracker_latest.html" = "9d1b0a4bd47224c93b93992c7f28fb4fc8de6ec00a80203d2a3b56fd8b35ad58"
  "reports/vn_structural_signals_fragment.html" = "88661dacd461f2d1f75eb399b2da195d2cb7f53358937a3450684378b6543c47"
  "data/decision/vn_structural_signals.json" = "f19fda696ffdd502bbc15b3aaf28d06370d7dd669c65b36e757dbf8e93a2757d"
  "data/decision/laban_scenarios.json" = "744e1842f832d2de249f234b5c936a46465db6245647c37fe1da6ad059118607"
  "data/decision/laban_axis_state.json" = "d4ee678277d16e7a9a6dc1db9f16df8aebf73ef74238c35e46d5c43a877b4e06"
  "data/decision/laban_frame_log.json" = "8d49403fe8c06a76acdaf22a2b33b9915e75e69620a3fb948236f0c03b5fdfcd"
}
foreach ($path in $expected.Keys) {
  $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower()
  if ($actual -ne $expected[$path]) { throw "PROTECTED_BASELINE_CHANGED: $path" }
}
```

Expected: exit code 0 with no output. If a hash differs, stop and return `NEEDS_HUMAN`; do not overwrite or normalize the changed file.

## Task 1: Lock policy constants and schema boundaries

**Files:**

- Create: `tests/test_laban_cross_asset_gate.py`
- Create: `scripts/reporting/laban_cross_asset_gate.py`

- [ ] **Step 1: Write the failing policy-contract tests**

Create `tests/test_laban_cross_asset_gate.py` with this initial content:

```python
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "reporting"))

from laban_cross_asset_gate import (
    HARD_GATE_BLOCKED,
    HARD_GATE_PROXY,
    CrossAssetGateError,
    evaluate_gate,
    load_and_evaluate,
    validate_gate_document,
    validate_registry,
)


def base_effects() -> dict[str, str]:
    return {
        "weights": "NONE",
        "state": "NONE",
        "coverage": "NONE",
        "confidence": "NONE",
        "universe": "NONE",
        "final_action": "NONE",
        "oms": "NONE",
    }


def empty_gate() -> dict:
    return {
        "schema": "laban_cross_asset_gate",
        "version": "1.0",
        "as_of": "2026-08-21",
        "policy_constants": {
            "blocked_transmission": "Main transmission blocked → search harder, not stop.",
            "proxy_question": "What is moving that VNINDEX cannot currently express, and which listed Vietnamese company is the best proxy for that move?",
        },
        "effects": base_effects(),
        "status": "NOT_APPLICABLE",
        "recommendation_gate": "NOT_APPLICABLE",
        "active_shocks": [],
        "coverage_summary": {
            "source": "FireAnt",
            "method": "REST API or web-side endpoint",
            "universe_as_of": None,
            "listed_total": 0,
            "eligible_count": 0,
            "scanned_count": 0,
            "excluded_count": 0,
            "coverage_gaps": [],
        },
        "warnings": ["No active material shock registered as of 2026-08-21."],
    }


def empty_registry() -> dict:
    return {
        "schema": "laban_cross_asset_proxy_map",
        "version": "1.0",
        "as_of": "2026-08-21",
        "entries": [],
    }


class PolicyContractTests(unittest.TestCase):
    def test_exact_policy_constants(self):
        self.assertEqual(
            HARD_GATE_BLOCKED,
            "Main transmission blocked → search harder, not stop.",
        )
        self.assertEqual(
            HARD_GATE_PROXY,
            "What is moving that VNINDEX cannot currently express, and which listed Vietnamese company is the best proxy for that move?",
        )

    def test_empty_not_applicable_document_is_valid(self):
        validate_gate_document(empty_gate())
        validate_registry(empty_registry())

    def test_policy_constant_drift_is_rejected(self):
        doc = empty_gate()
        doc["policy_constants"]["blocked_transmission"] = "search harder"
        with self.assertRaisesRegex(CrossAssetGateError, "POLICY_CONSTANT_MISMATCH"):
            validate_gate_document(doc)

    def test_scoring_or_trading_effect_is_rejected(self):
        doc = empty_gate()
        doc["effects"]["weights"] = "READ"
        with self.assertRaisesRegex(CrossAssetGateError, "EFFECT_MUST_BE_NONE"):
            validate_gate_document(doc)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py PolicyContractTests -v
```

Expected: import failure containing `No module named 'laban_cross_asset_gate'`.

- [ ] **Step 3: Implement the policy and structural validator**

Create `scripts/reporting/laban_cross_asset_gate.py` with:

```python
"""Non-scoring Cross-Asset Opportunity Transmission Gate.

This module validates operator-maintained research artifacts. It never imports
La Bàn weight code and never emits trading, sizing, final_action, or OMS fields.
"""
from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

HARD_GATE_BLOCKED = "Main transmission blocked → search harder, not stop."
HARD_GATE_PROXY = (
    "What is moving that VNINDEX cannot currently express, and which listed "
    "Vietnamese company is the best proxy for that move?"
)

EFFECT_KEYS = (
    "weights",
    "state",
    "coverage",
    "confidence",
    "universe",
    "final_action",
    "oms",
)
TERMINAL_STATUSES = {
    "NOT_APPLICABLE",
    "COMPLETE_CANDIDATES",
    "COMPLETE_NO_DEFENSIBLE_PROXY",
    "FAIL_CLOSED",
}
RECOMMENDATION_GATES = {"OPEN", "BLOCKED", "NOT_APPLICABLE"}
RESEARCH_STATUSES = {
    "EARLY — RESEARCH NOW",
    "WATCH FOR TRIGGER",
    "RESEARCH-READY — HUMAN REVIEW REQUIRED",
    "EXTENDED — DO NOT CHASE",
    "THESIS INVALID",
    "INSUFFICIENT DATA",
}
PROHIBITED_KEYS = {
    "buy",
    "sell",
    "position_size",
    "sizing",
    "target_price",
    "stop_loss",
    "final_action",
    "oms_action",
    "backtest_universe",
    "trading_universe",
}


class CrossAssetGateError(ValueError):
    """Raised when a sidecar violates the non-scoring contract."""


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise CrossAssetGateError(f"{code}: {detail}")


def _require_keys(obj: dict[str, Any], keys: tuple[str, ...], where: str) -> None:
    missing = [key for key in keys if key not in obj]
    _require(not missing, "MISSING_KEYS", f"{where}: {missing}")


def _reject_prohibited_keys(value: Any, where: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_lower = str(key).lower()
            allowed_effect_declaration = where == "root.effects" and key_lower == "final_action"
            _require(
                key_lower not in PROHIBITED_KEYS or allowed_effect_declaration,
                "PROHIBITED_KEY",
                f"{where}.{key}",
            )
            _reject_prohibited_keys(child, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_prohibited_keys(child, f"{where}[{index}]")


def validate_gate_document(doc: dict[str, Any]) -> None:
    _require_keys(
        doc,
        (
            "schema",
            "version",
            "as_of",
            "policy_constants",
            "effects",
            "status",
            "recommendation_gate",
            "active_shocks",
            "coverage_summary",
            "warnings",
        ),
        "gate",
    )
    _require(doc["schema"] == "laban_cross_asset_gate", "SCHEMA_MISMATCH", str(doc["schema"]))
    policy = doc["policy_constants"]
    _require(
        policy.get("blocked_transmission") == HARD_GATE_BLOCKED,
        "POLICY_CONSTANT_MISMATCH",
        "blocked_transmission",
    )
    _require(
        policy.get("proxy_question") == HARD_GATE_PROXY,
        "POLICY_CONSTANT_MISMATCH",
        "proxy_question",
    )
    effects = doc["effects"]
    for key in EFFECT_KEYS:
        _require(effects.get(key) == "NONE", "EFFECT_MUST_BE_NONE", key)
    _require(doc["status"] in TERMINAL_STATUSES, "INVALID_STATUS", str(doc["status"]))
    _require(
        doc["recommendation_gate"] in RECOMMENDATION_GATES,
        "INVALID_RECOMMENDATION_GATE",
        str(doc["recommendation_gate"]),
    )
    _require(isinstance(doc["active_shocks"], list), "TYPE_ERROR", "active_shocks")
    _require(isinstance(doc["warnings"], list), "TYPE_ERROR", "warnings")
    _reject_prohibited_keys(doc)


def validate_registry(registry: dict[str, Any]) -> None:
    _require_keys(registry, ("schema", "version", "as_of", "entries"), "registry")
    _require(
        registry["schema"] == "laban_cross_asset_proxy_map",
        "SCHEMA_MISMATCH",
        str(registry["schema"]),
    )
    _require(isinstance(registry["entries"], list), "TYPE_ERROR", "entries")
    ids: set[str] = set()
    for entry in registry["entries"]:
        _require_keys(
            entry,
            (
                "mapping_id",
                "asset_id",
                "mechanism_id",
                "symbol",
                "exposure_type",
                "company_exposure_fact",
                "adverse_mechanism",
                "falsifier",
                "status",
                "last_verified",
                "staleness",
            ),
            "registry.entry",
        )
        mapping_id = str(entry["mapping_id"])
        _require(mapping_id not in ids, "DUPLICATE_MAPPING_ID", mapping_id)
        ids.add(mapping_id)
        _require(
            entry["status"] in {"ACTIVE", "DRAFT_POST_HOC", "RETIRED"},
            "INVALID_MAPPING_STATUS",
            mapping_id,
        )
    _reject_prohibited_keys(registry)
```

- [ ] **Step 4: Run the policy tests to verify GREEN**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py PolicyContractTests -v
```

Expected: `Ran 4 tests` and `OK`.

- [ ] **Step 5: Commit the policy contract**

Run:

```powershell
git add -- scripts/reporting/laban_cross_asset_gate.py tests/test_laban_cross_asset_gate.py
git diff --cached --name-status
git commit -m "feat(laban): add cross-asset gate contract"
```

Expected staged paths: only the two files above.

## Task 2: Implement reference integrity and fail-closed evaluation

**Files:**

- Modify: `tests/test_laban_cross_asset_gate.py`
- Modify: `scripts/reporting/laban_cross_asset_gate.py`

- [ ] **Step 1: Add failing evaluator fixtures and tests**

Insert above `PolicyContractTests`:

```python
def complete_shock() -> dict:
    return {
        "shock_id": "fixture_gold_2026_08_21",
        "asset": "gold",
        "direction": "UP",
        "magnitude": "SYNTHETIC_FIXTURE",
        "timeframe": "5D",
        "activation_basis": "TEST_ONLY — not a market fact",
        "as_of": "2026-08-21",
        "source": "TEST_FIXTURE",
        "is_stale": False,
        "facts": [
            {
                "fact_id": "f1",
                "statement": "Synthetic gold move for contract testing only.",
                "as_of": "2026-08-21",
                "source": "TEST_FIXTURE",
                "source_quality": "CONFIRMED",
            },
            {
                "fact_id": "f2",
                "statement": "Synthetic PNJ exposure evidence for contract testing only.",
                "as_of": "2026-08-21",
                "source": "TEST_FIXTURE",
                "source_quality": "CONFIRMED",
            },
        ],
        "inferences": [
            {
                "inference_id": "i1",
                "fact_ids": ["f1"],
                "order": 2,
                "mechanism": "Synthetic substitution mechanism.",
                "persistence": "TACTICAL",
                "falsifier": "Synthetic falsifier.",
            }
        ],
        "main_vn_transmission": {
            "status": "BLOCKED",
            "blockers": ["Synthetic FX blocker."],
            "fact_ids": ["f1"],
            "inference_ids": ["i1"],
        },
        "alternative_transmission": {
            "completed": True,
            "categories_checked": ["gold / precious metals", "listed asset proxies"],
            "findings": ["Synthetic candidate path."],
            "missing_branches": [],
            "confirm_or_falsify": "Synthetic fixture evidence only.",
        },
        "universe_scan": {
            "source": "FireAnt",
            "method": "REST API",
            "universe_as_of": "2026-08-21",
            "listed_total": 2,
            "eligible_count": 1,
            "scanned_count": 1,
            "excluded_count": 1,
            "excluded_symbols": [{"symbol": "ZZZ", "reason": "Synthetic exclusion."}],
            "unmapped_symbols": [],
            "coverage_gaps": [],
        },
        "candidates": [
            {
                "symbol": "PNJ",
                "mapping_ids": ["gold_pnj_active_fixture"],
                "exposure_type": "STRONG_INDIRECT",
                "fact_ids": ["f2"],
                "inference_ids": ["i1"],
                "transmission_directness": "STRONG_INDIRECT",
                "earnings_sensitivity": "MEDIUM",
                "timing": "IMMEDIATE",
                "persistence": "TACTICAL",
                "market_awareness": "PARTIALLY_PRICED",
                "technical": {
                    "state": "ACCUMULATING",
                    "as_of": "2026-08-21",
                    "source": "TEST_FIXTURE",
                },
                "liquidity": {
                    "state": "TRADABLE",
                    "as_of": "2026-08-21",
                    "source": "TEST_FIXTURE",
                },
                "valuation": {
                    "state": "CHECKED",
                    "as_of": "2026-08-21",
                    "source": "TEST_FIXTURE",
                },
                "adverse_order_risk": "MEDIUM",
                "falsifier": "Synthetic candidate falsifier.",
                "research_status": "RESEARCH-READY — HUMAN REVIEW REQUIRED",
            }
        ],
        "best_proxy_answer": {
            "status": "QUALIFIED_PROXY",
            "symbol": "PNJ",
            "rationale": "Synthetic fixture only; not a historical or investment conclusion.",
        },
    }


def active_registry() -> dict:
    doc = empty_registry()
    doc["entries"] = [
        {
            "mapping_id": "gold_pnj_active_fixture",
            "asset_id": "gold",
            "mechanism_id": "i1",
            "symbol": "PNJ",
            "exposure_type": "STRONG_INDIRECT",
            "company_exposure_fact": {
                "statement": "Synthetic test-only exposure.",
                "source": "TEST_FIXTURE",
                "as_of": "2026-08-21",
                "source_quality": "CONFIRMED",
            },
            "adverse_mechanism": "Synthetic adverse mechanism.",
            "falsifier": "Synthetic falsifier.",
            "status": "ACTIVE",
            "last_verified": "2026-08-21",
            "staleness": "FRESH",
        }
    ]
    return doc
```

Add this test class before the final `if __name__` block:

```python
class EvaluationTests(unittest.TestCase):
    def active_gate(self) -> dict:
        doc = empty_gate()
        doc["active_shocks"] = [complete_shock()]
        return doc

    def test_blocked_transmission_complete_scan_opens_human_review(self):
        result = evaluate_gate(self.active_gate(), active_registry(), "2026-08-21")
        self.assertEqual(result["status"], "COMPLETE_CANDIDATES")
        self.assertEqual(result["recommendation_gate"], "OPEN")

    def test_blocked_transmission_incomplete_alternative_fails_closed(self):
        doc = self.active_gate()
        doc["active_shocks"][0]["alternative_transmission"]["completed"] = False
        result = evaluate_gate(doc, active_registry(), "2026-08-21")
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertEqual(result["recommendation_gate"], "BLOCKED")
        self.assertIn("COVERAGE GAP — further ticker scan required", result["warnings"])

    def test_incomplete_universe_fails_closed(self):
        doc = self.active_gate()
        doc["active_shocks"][0]["universe_scan"]["scanned_count"] = 0
        result = evaluate_gate(doc, active_registry(), "2026-08-21")
        self.assertEqual(result["status"], "FAIL_CLOSED")

    def test_complete_scan_can_return_no_proxy(self):
        doc = self.active_gate()
        shock = doc["active_shocks"][0]
        shock["candidates"] = []
        shock["best_proxy_answer"] = {
            "status": "NO_DEFENSIBLE_PROXY",
            "symbol": None,
            "rationale": "Complete synthetic scan; no candidate qualified.",
        }
        result = evaluate_gate(doc, active_registry(), "2026-08-21")
        self.assertEqual(result["status"], "COMPLETE_NO_DEFENSIBLE_PROXY")
        self.assertEqual(result["recommendation_gate"], "BLOCKED")

    def test_extended_candidate_is_forced_to_do_not_chase(self):
        doc = self.active_gate()
        candidate = doc["active_shocks"][0]["candidates"][0]
        candidate["technical"]["state"] = "EXTENDED"
        result = evaluate_gate(doc, active_registry(), "2026-08-21")
        candidate_out = result["active_shocks"][0]["candidates"][0]
        self.assertEqual(candidate_out["research_status"], "EXTENDED — DO NOT CHASE")
        self.assertEqual(result["recommendation_gate"], "BLOCKED")

    def test_broken_fact_reference_is_invalid(self):
        doc = self.active_gate()
        doc["active_shocks"][0]["inferences"][0]["fact_ids"] = ["missing"]
        with self.assertRaisesRegex(CrossAssetGateError, "UNKNOWN_FACT_REF"):
            evaluate_gate(doc, active_registry(), "2026-08-21")

    def test_draft_post_hoc_mapping_cannot_qualify_proxy(self):
        registry = active_registry()
        registry["entries"][0]["status"] = "DRAFT_POST_HOC"
        result = evaluate_gate(self.active_gate(), registry, "2026-08-21")
        self.assertEqual(result["status"], "FAIL_CLOSED")
```

- [ ] **Step 2: Run evaluator tests to verify RED**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py EvaluationTests -v
```

Expected: failures because `evaluate_gate` is not yet defined.

- [ ] **Step 3: Implement deterministic evaluation**

Append to `scripts/reporting/laban_cross_asset_gate.py`:

```python
def _validate_references(shock: dict[str, Any]) -> None:
    facts = {str(row.get("fact_id")) for row in shock.get("facts") or []}
    inferences = {str(row.get("inference_id")) for row in shock.get("inferences") or []}
    _require(len(facts) == len(shock.get("facts") or []), "DUPLICATE_FACT_ID", str(shock.get("shock_id")))
    _require(
        len(inferences) == len(shock.get("inferences") or []),
        "DUPLICATE_INFERENCE_ID",
        str(shock.get("shock_id")),
    )
    for inference in shock.get("inferences") or []:
        for fact_id in inference.get("fact_ids") or []:
            _require(fact_id in facts, "UNKNOWN_FACT_REF", str(fact_id))
    linked_objects = [shock.get("main_vn_transmission") or {}] + list(shock.get("candidates") or [])
    for obj in linked_objects:
        for fact_id in obj.get("fact_ids") or []:
            _require(fact_id in facts, "UNKNOWN_FACT_REF", str(fact_id))
        for inference_id in obj.get("inference_ids") or []:
            _require(inference_id in inferences, "UNKNOWN_INFERENCE_REF", str(inference_id))


def _coverage_complete(scan: dict[str, Any]) -> bool:
    required = (
        "source",
        "method",
        "universe_as_of",
        "listed_total",
        "eligible_count",
        "scanned_count",
        "excluded_count",
        "excluded_symbols",
        "unmapped_symbols",
        "coverage_gaps",
    )
    if any(key not in scan for key in required):
        return False
    counts_hold = (
        int(scan["listed_total"]) == int(scan["eligible_count"]) + int(scan["excluded_count"])
        and int(scan["scanned_count"]) == int(scan["eligible_count"])
        and len(scan["excluded_symbols"]) == int(scan["excluded_count"])
    )
    return bool(
        scan["source"] == "FireAnt"
        and scan["universe_as_of"]
        and counts_hold
        and not scan["unmapped_symbols"]
        and not scan["coverage_gaps"]
    )


def _candidate_complete(candidate: dict[str, Any], active_mapping_ids: set[str]) -> bool:
    required = (
        "symbol",
        "mapping_ids",
        "exposure_type",
        "fact_ids",
        "inference_ids",
        "transmission_directness",
        "earnings_sensitivity",
        "timing",
        "persistence",
        "market_awareness",
        "technical",
        "liquidity",
        "valuation",
        "adverse_order_risk",
        "falsifier",
        "research_status",
    )
    if any(key not in candidate for key in required):
        return False
    if not candidate["mapping_ids"] or not set(candidate["mapping_ids"]).issubset(active_mapping_ids):
        return False
    for block in ("technical", "liquidity", "valuation"):
        item = candidate.get(block) or {}
        if not item.get("state") or not item.get("as_of") or not item.get("source"):
            return False
        if item.get("state") in {"UNKNOWN", "NOT_RUN", "INSUFFICIENT_DATA"}:
            return False
    return candidate["research_status"] in RESEARCH_STATUSES


def evaluate_gate(doc: dict[str, Any], registry: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    validate_gate_document(doc)
    validate_registry(registry)
    out = copy.deepcopy(doc)
    out["as_of"] = as_of or date.today().isoformat()
    shocks = out.get("active_shocks") or []
    if not shocks:
        out["status"] = "NOT_APPLICABLE"
        out["recommendation_gate"] = "NOT_APPLICABLE"
        return out

    active_mapping_ids = {
        str(entry["mapping_id"])
        for entry in registry["entries"]
        if entry.get("status") == "ACTIVE" and entry.get("staleness") == "FRESH"
    }
    fail_closed = False
    qualified_count = 0
    no_proxy_count = 0

    for shock in shocks:
        _validate_references(shock)
        if shock.get("is_stale") is not False:
            fail_closed = True
        transmission = shock.get("main_vn_transmission") or {}
        alternative = shock.get("alternative_transmission") or {}
        if transmission.get("status") == "BLOCKED":
            if (
                alternative.get("completed") is not True
                or not alternative.get("categories_checked")
                or alternative.get("missing_branches")
                or not alternative.get("confirm_or_falsify")
            ):
                fail_closed = True
        if not _coverage_complete(shock.get("universe_scan") or {}):
            fail_closed = True

        candidates = shock.get("candidates") or []
        for candidate in candidates:
            if (candidate.get("technical") or {}).get("state") == "EXTENDED":
                candidate["research_status"] = "EXTENDED — DO NOT CHASE"
                fail_closed = True
            elif not _candidate_complete(candidate, active_mapping_ids):
                candidate["research_status"] = "INSUFFICIENT DATA"
                fail_closed = True

        answer = shock.get("best_proxy_answer") or {}
        answer_status = answer.get("status")
        if answer_status == "QUALIFIED_PROXY":
            matching = [c for c in candidates if c.get("symbol") == answer.get("symbol")]
            if not matching or matching[0].get("research_status") != "RESEARCH-READY — HUMAN REVIEW REQUIRED":
                fail_closed = True
            else:
                qualified_count += 1
        elif answer_status == "NO_DEFENSIBLE_PROXY" and _coverage_complete(shock.get("universe_scan") or {}):
            no_proxy_count += 1
        else:
            fail_closed = True

    if fail_closed:
        out["status"] = "FAIL_CLOSED"
        out["recommendation_gate"] = "BLOCKED"
        if "COVERAGE GAP — further ticker scan required" not in out["warnings"]:
            out["warnings"].append("COVERAGE GAP — further ticker scan required")
    elif qualified_count:
        out["status"] = "COMPLETE_CANDIDATES"
        out["recommendation_gate"] = "OPEN"
    elif no_proxy_count == len(shocks):
        out["status"] = "COMPLETE_NO_DEFENSIBLE_PROXY"
        out["recommendation_gate"] = "BLOCKED"
    else:
        out["status"] = "FAIL_CLOSED"
        out["recommendation_gate"] = "BLOCKED"
    return out


def load_and_evaluate(gate_path: Path, registry_path: Path, as_of: str | None = None) -> dict[str, Any]:
    gate_doc = json.loads(gate_path.read_text(encoding="utf-8"))
    registry_doc = json.loads(registry_path.read_text(encoding="utf-8"))
    return evaluate_gate(gate_doc, registry_doc, as_of=as_of)
```

- [ ] **Step 4: Run all gate tests to verify GREEN**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py -v
```

Expected: `Ran 11 tests` and `OK`.

- [ ] **Step 5: Commit evaluator behavior**

Run:

```powershell
git add -- scripts/reporting/laban_cross_asset_gate.py tests/test_laban_cross_asset_gate.py
git diff --cached --name-status
git commit -m "feat(laban): enforce cross-asset fail-closed rules"
```

Expected staged paths: only the two files above.

## Task 3: Add operator sidecar and post-hoc-safe mapping registry

**Files:**

- Create: `data/decision/laban_cross_asset_gate.json`
- Create: `data/decision/laban_cross_asset_proxy_map.json`
- Modify: `tests/test_laban_cross_asset_gate.py`

- [ ] **Step 1: Add failing live-artifact contract test**

Add to `tests/test_laban_cross_asset_gate.py`:

```python
class LiveArtifactTests(unittest.TestCase):
    GATE_PATH = REPO / "data" / "decision" / "laban_cross_asset_gate.json"
    REGISTRY_PATH = REPO / "data" / "decision" / "laban_cross_asset_proxy_map.json"

    def test_live_artifacts_load_as_not_applicable(self):
        result = load_and_evaluate(self.GATE_PATH, self.REGISTRY_PATH, "2026-08-21")
        self.assertEqual(result["status"], "NOT_APPLICABLE")
        self.assertEqual(result["recommendation_gate"], "NOT_APPLICABLE")

    def test_pnj_gold_seed_is_post_hoc_not_active(self):
        registry = json.loads(self.REGISTRY_PATH.read_text(encoding="utf-8"))
        pnj = next(row for row in registry["entries"] if row["symbol"] == "PNJ")
        self.assertEqual(pnj["status"], "DRAFT_POST_HOC")
        self.assertEqual(pnj["company_exposure_fact"]["source_quality"], "UNKNOWN")
        self.assertIsNone(pnj["last_verified"])
```

- [ ] **Step 2: Run artifact tests to verify RED**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py LiveArtifactTests -v
```

Expected: `FileNotFoundError` for `laban_cross_asset_gate.json`.

- [ ] **Step 3: Create the initial sidecar**

Create `data/decision/laban_cross_asset_gate.json`:

```json
{
  "schema": "laban_cross_asset_gate",
  "version": "1.0",
  "as_of": "2026-08-21",
  "policy_constants": {
    "blocked_transmission": "Main transmission blocked → search harder, not stop.",
    "proxy_question": "What is moving that VNINDEX cannot currently express, and which listed Vietnamese company is the best proxy for that move?"
  },
  "effects": {
    "weights": "NONE",
    "state": "NONE",
    "coverage": "NONE",
    "confidence": "NONE",
    "universe": "NONE",
    "final_action": "NONE",
    "oms": "NONE"
  },
  "status": "NOT_APPLICABLE",
  "recommendation_gate": "NOT_APPLICABLE",
  "active_shocks": [],
  "coverage_summary": {
    "source": "FireAnt",
    "method": "REST API or web-side endpoint",
    "universe_as_of": null,
    "listed_total": 0,
    "eligible_count": 0,
    "scanned_count": 0,
    "excluded_count": 0,
    "coverage_gaps": []
  },
  "warnings": [
    "No active material shock registered as of 2026-08-21."
  ]
}
```

- [ ] **Step 4: Create the persistent mapping registry**

Create `data/decision/laban_cross_asset_proxy_map.json`:

```json
{
  "schema": "laban_cross_asset_proxy_map",
  "version": "1.0",
  "as_of": "2026-08-21",
  "entries": [
    {
      "mapping_id": "gold_pnj_post_hoc_hypothesis",
      "asset_id": "gold",
      "mechanism_id": "gold_move_driver_unverified",
      "symbol": "PNJ",
      "exposure_type": "STRONG_INDIRECT",
      "company_exposure_fact": {
        "statement": "Post-hoc hypothesis only: verify PNJ revenue, margin, inventory, demand and regulatory sensitivity to the identified gold mechanism before promotion.",
        "source": "Unknown",
        "as_of": null,
        "source_quality": "UNKNOWN"
      },
      "adverse_mechanism": "High gold prices may destroy jewelry volume, increase working-capital pressure, alter margin mix, or trigger regulatory intervention.",
      "falsifier": "Verified company evidence shows no material earnings or valuation sensitivity to the identified gold mechanism.",
      "status": "DRAFT_POST_HOC",
      "last_verified": null,
      "staleness": "UNVERIFIED"
    }
  ]
}
```

- [ ] **Step 5: Run artifact and full focused tests to verify GREEN**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py -v
```

Expected: `Ran 13 tests` and `OK`.

- [ ] **Step 6: Commit only the two data artifacts and focused test**

Run:

```powershell
git add -- data/decision/laban_cross_asset_gate.json data/decision/laban_cross_asset_proxy_map.json tests/test_laban_cross_asset_gate.py
git diff --cached --name-status
git commit -m "data(laban): seed cross-asset sidecar and proxy registry"
```

Expected staged paths: only the three files above.

## Task 4: Add isolated T1/T3 rendering

**Files:**

- Create: `scripts/reporting/laban_cross_asset_render.py`
- Modify: `tests/test_laban_cross_asset_gate.py`

- [ ] **Step 1: Add failing renderer tests**

Add imports:

```python
from laban_cross_asset_render import attach_cross_asset_tabs, render_cross_asset_card
```

Add tests:

```python
class RendererTests(unittest.TestCase):
    def test_fail_closed_renders_both_hard_gates_and_coverage_gap(self):
        doc = empty_gate()
        doc["status"] = "FAIL_CLOSED"
        doc["recommendation_gate"] = "BLOCKED"
        doc["warnings"] = ["COVERAGE GAP — further ticker scan required"]
        html = render_cross_asset_card(doc)
        self.assertIn(HARD_GATE_BLOCKED, html)
        self.assertIn(HARD_GATE_PROXY, html)
        self.assertIn("COVERAGE GAP — further ticker scan required", html)
        self.assertIn("CANDIDATE — NOT A BUY RECOMMENDATION", html)

    def test_attach_changes_only_t1_and_t3(self):
        tabs = {"T1": "one", "T2": "two", "T3": "three", "T4": "four", "T6": "six"}
        result = attach_cross_asset_tabs(tabs, empty_gate())
        self.assertNotEqual(result["T1"], tabs["T1"])
        self.assertNotEqual(result["T3"], tabs["T3"])
        self.assertEqual(result["T2"], tabs["T2"])
        self.assertEqual(result["T4"], tabs["T4"])
        self.assertEqual(result["T6"], tabs["T6"])

    def test_renderer_escapes_operator_text(self):
        doc = empty_gate()
        doc["warnings"] = ["<script>alert(1)</script>"]
        html = render_cross_asset_card(doc)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
```

- [ ] **Step 2: Run renderer tests to verify RED**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py RendererTests -v
```

Expected: import failure containing `No module named 'laban_cross_asset_render'`.

- [ ] **Step 3: Implement the pure renderer**

Create `scripts/reporting/laban_cross_asset_render.py`:

```python
"""Pure HTML composition for the non-scoring cross-asset gate."""
from __future__ import annotations

from html import escape
from typing import Any

from laban_cross_asset_gate import HARD_GATE_BLOCKED, HARD_GATE_PROXY


def _status_color(status: str) -> str:
    return {
        "COMPLETE_CANDIDATES": "var(--g)",
        "COMPLETE_NO_DEFENSIBLE_PROXY": "var(--a)",
        "FAIL_CLOSED": "var(--r)",
        "NOT_APPLICABLE": "var(--muted)",
    }.get(status, "var(--r)")


def render_cross_asset_status_strip(result: dict[str, Any]) -> str:
    status = str(result.get("status") or "FAIL_CLOSED")
    gate = str(result.get("recommendation_gate") or "BLOCKED")
    return (
        '<div class="card" data-cross-asset-gate="status" '
        f'style="border-color:{_status_color(status)}">'
        '<h3>CROSS-ASSET OPPORTUNITY GATE</h3>'
        f'<p><b>{escape(status)}</b> · recommendation gate: {escape(gate)}</p>'
        '</div>'
    )


def render_cross_asset_card(result: dict[str, Any]) -> str:
    shocks = result.get("active_shocks") or []
    warnings = result.get("warnings") or []
    shock_rows = []
    for shock in shocks:
        answer = shock.get("best_proxy_answer") or {}
        transmission = shock.get("main_vn_transmission") or {}
        candidates = shock.get("candidates") or []
        candidate_rows = "".join(
            "<tr>"
            f"<td>{escape(str(row.get('symbol') or 'Unknown'))}</td>"
            f"<td>{escape(str(row.get('exposure_type') or 'Unknown'))}</td>"
            f"<td>{escape(str(row.get('research_status') or 'INSUFFICIENT DATA'))}</td>"
            "</tr>"
            for row in candidates
        )
        shock_rows.append(
            '<div class="card">'
            f"<h3>{escape(str(shock.get('asset') or 'Unknown'))} · {escape(str(shock.get('direction') or 'Unknown'))}</h3>"
            f"<p>Main VN transmission: {escape(str(transmission.get('status') or 'UNKNOWN'))}</p>"
            f"<p>Best proxy answer: {escape(str(answer.get('symbol') or answer.get('status') or 'COVERAGE GAP'))}</p>"
            '<div class="tblwrap"><table><thead><tr><th>Candidate</th><th>Exposure</th><th>Research status</th></tr></thead>'
            f"<tbody>{candidate_rows or '<tr><td colspan=3>INSUFFICIENT DATA</td></tr>'}</tbody></table></div>"
            "</div>"
        )
    warning_html = "".join(f"<li>{escape(str(item))}</li>" for item in warnings)
    return (
        '<div id="cross-asset-opportunity-gate" class="card" style="border-color:var(--a)">'
        '<h3>MISSED-OPPORTUNITY PREVENTION</h3>'
        '<p style="color:var(--r);font-weight:700">CANDIDATE — NOT A BUY RECOMMENDATION</p>'
        f"<p><b>{escape(HARD_GATE_BLOCKED)}</b></p>"
        f"<p><b>{escape(HARD_GATE_PROXY)}</b></p>"
        f"<p>Status: {escape(str(result.get('status') or 'FAIL_CLOSED'))}</p>"
        f"<ul>{warning_html}</ul>"
        f"{''.join(shock_rows) if shock_rows else '<p>No active material shock registered.</p>'}"
        "</div>"
    )


def attach_cross_asset_tabs(tabs: dict[str, str], result: dict[str, Any]) -> dict[str, str]:
    out = dict(tabs)
    out["T1"] = render_cross_asset_status_strip(result) + out.get("T1", "")
    out["T3"] = out.get("T3", "") + render_cross_asset_card(result)
    return out
```

- [ ] **Step 4: Run renderer and all focused tests to verify GREEN**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py -v
```

Expected: `Ran 16 tests` and `OK`.

- [ ] **Step 5: Commit the isolated renderer**

Run:

```powershell
git add -- scripts/reporting/laban_cross_asset_render.py tests/test_laban_cross_asset_gate.py
git diff --cached --name-status
git commit -m "feat(laban): render cross-asset research gate"
```

Expected staged paths: only the two files above. `scripts/reporting/laban_render.py` remains unstaged and byte-unchanged from the preflight baseline.

## Task 5: Wire validation before writes without touching the frozen engine

**Files:**

- Modify: `scripts/reporting/build_vn_structural_signals.py`
- Modify: `tests/test_laban_cross_asset_gate.py`

- [ ] **Step 1: Add failing builder-order and invariance tests**

Add:

```python
class BuilderIntegrationTests(unittest.TestCase):
    BUILDER = REPO / "scripts" / "reporting" / "build_vn_structural_signals.py"
    FRAGMENT = REPO / "reports" / "vn_structural_signals_fragment.html"
    REGISTRY = REPO / "data" / "decision" / "laban_cross_asset_proxy_map.json"

    def test_invalid_sidecar_exits_before_fragment_write(self):
        before = self.FRAGMENT.read_bytes() if self.FRAGMENT.exists() else None
        with tempfile.TemporaryDirectory() as tmp:
            bad_gate = Path(tmp) / "bad_gate.json"
            bad_gate.write_text('{"schema":"wrong"}', encoding="utf-8")
            run = subprocess.run(
                [
                    sys.executable,
                    str(self.BUILDER),
                    "--cross-asset-gate",
                    str(bad_gate),
                    "--cross-asset-registry",
                    str(self.REGISTRY),
                ],
                cwd=REPO,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        after = self.FRAGMENT.read_bytes() if self.FRAGMENT.exists() else None
        self.assertEqual(run.returncode, 2)
        self.assertIn("CROSS_ASSET_INVALID", run.stderr)
        self.assertEqual(after, before)

    def test_builder_never_passes_sidecar_to_run_engine(self):
        source = self.BUILDER.read_text(encoding="utf-8")
        start = source.index("snapshot = run_engine(")
        end = source.index(")", start)
        call_text = source[start:end]
        self.assertNotIn("cross_asset", call_text)

    def test_real_renderer_file_keeps_tariff_watch_and_has_no_cross_asset_edit(self):
        source = (REPO / "scripts" / "reporting" / "laban_render.py").read_text(encoding="utf-8")
        self.assertIn("Tariff watch", source)
        self.assertNotIn("cross_asset", source)
```

- [ ] **Step 2: Run builder tests to verify RED**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py BuilderIntegrationTests -v
```

Expected: failure because the builder does not recognize `--cross-asset-gate` and stderr lacks `CROSS_ASSET_INVALID`.

- [ ] **Step 3: Add imports and default paths to the builder**

In `scripts/reporting/build_vn_structural_signals.py`, after the existing `laban_render` import add:

```python
from laban_cross_asset_gate import (  # noqa: E402
    CrossAssetGateError,
    load_and_evaluate as load_and_evaluate_cross_asset,
)
from laban_cross_asset_render import attach_cross_asset_tabs  # noqa: E402
```

After `ADVISORY_LINKS_PATH`, add:

```python
CROSS_ASSET_GATE_PATH = REPO / "data" / "decision" / "laban_cross_asset_gate.json"
CROSS_ASSET_REGISTRY_PATH = REPO / "data" / "decision" / "laban_cross_asset_proxy_map.json"
```

- [ ] **Step 4: Add CLI overrides**

After `--signals`, add:

```python
    ap.add_argument("--cross-asset-gate", default=str(CROSS_ASSET_GATE_PATH))
    ap.add_argument("--cross-asset-registry", default=str(CROSS_ASSET_REGISTRY_PATH))
```

- [ ] **Step 5: Validate before the first file write**

Immediately after the signal evaluation loop and before `fragment = render(signals, today)`, insert:

```python
    cross_asset_result = None
    if not args.skip_laban:
        try:
            cross_asset_result = load_and_evaluate_cross_asset(
                Path(args.cross_asset_gate),
                Path(args.cross_asset_registry),
                as_of=today.isoformat(),
            )
        except (OSError, json.JSONDecodeError, CrossAssetGateError) as exc:
            print(f"CROSS_ASSET_INVALID: {exc}", file=sys.stderr)
            return 2
```

Do not move or modify the `run_engine(...)` argument list.

- [ ] **Step 6: Compose only T1 and T3 after the existing renderer split**

Immediately after `laban_tabs = split_tabs(block)`, insert:

```python
        if cross_asset_result is not None:
            laban_tabs = attach_cross_asset_tabs(laban_tabs, cross_asset_result)
```

- [ ] **Step 7: Run builder integration and all focused tests to verify GREEN**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py -v
python -m py_compile scripts/reporting/laban_cross_asset_gate.py scripts/reporting/laban_cross_asset_render.py scripts/reporting/build_vn_structural_signals.py
```

Expected: `Ran 19 tests`, `OK`, and `py_compile` exit code 0 with no output.

- [ ] **Step 8: Verify no protected file is staged, then commit**

Run:

```powershell
git add -- scripts/reporting/build_vn_structural_signals.py tests/test_laban_cross_asset_gate.py
git diff --cached --name-status
git commit -m "feat(laban): wire cross-asset sidecar before publication"
```

Expected staged paths: only the two files above.

## Task 6: Document the mandatory workflow and safety boundary

**Files:**

- Modify: `docs/WORKFLOW_ENGINE_EXTRACT.md`
- Modify: `tests/test_laban_cross_asset_gate.py`

- [ ] **Step 1: Add a failing documentation contract test**

Add:

```python
class DocumentationTests(unittest.TestCase):
    def test_workflow_documents_both_hard_gates_and_non_scoring_boundary(self):
        text = (REPO / "docs" / "WORKFLOW_ENGINE_EXTRACT.md").read_text(encoding="utf-8")
        self.assertIn(HARD_GATE_BLOCKED, text)
        self.assertIn(HARD_GATE_PROXY, text)
        self.assertIn("COVERAGE GAP — further ticker scan required", text)
        self.assertIn("never enters `run_engine()`", text)
```

- [ ] **Step 2: Run documentation test to verify RED**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py DocumentationTests -v
```

Expected: failure because the hard-gate strings are not yet present.

- [ ] **Step 3: Add section 2.5 to the workflow reference**

After the existing Hormuz section, add:

```markdown
### 2.5 Cross-Asset Opportunity Transmission Gate (mandatory when a material shock is active)

Sequence:

`Event detection → Fact verification → Mechanism → Multi-order effects → Main VN transmission → Blocked-transmission test → Cross-asset substitution test → Vietnam listed-proxy universe scan → Fundamental sensitivity → Technical confirmation → Valuation → Risk/adverse-order check → Research ranking → Human review`

Hard gates, preserved verbatim:

> Main transmission blocked → search harder, not stop.

> What is moving that VNINDEX cannot currently express, and which listed Vietnamese company is the best proxy for that move?

The current-run artifact is `data/decision/laban_cross_asset_gate.json`; the persistent exposure-edge registry is `data/decision/laban_cross_asset_proxy_map.json`. Both are non-scoring. The builder validates them before any publication write, but the sidecar never enters `run_engine()` and never affects weights, axes, structural-signal coverage, `final_action`, universe selection, sizing, or OMS.

When evidence, alternative branches, or full FireAnt listed-universe coverage are incomplete, the required result is `FAIL_CLOSED` plus `COVERAGE GAP — further ticker scan required`. This blocks recommendation finalization only; macro/scenario publication continues with a visible warning. A complete scan may return `COMPLETE_NO_DEFENSIBLE_PROXY`; the question never forces a ticker.

Candidate statuses are research-only. `RESEARCH-READY — HUMAN REVIEW REQUIRED` is not a BUY instruction, and `EXTENDED` always becomes `EXTENDED — DO NOT CHASE`. Post-mortem mappings enter as `DRAFT_POST_HOC` and require independent evidence plus prospective confirmation before promotion.
```

- [ ] **Step 4: Run documentation and all focused tests to verify GREEN**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py -v
```

Expected: `Ran 20 tests` and `OK`.

- [ ] **Step 5: Commit documentation and its contract test**

Run:

```powershell
git add -- docs/WORKFLOW_ENGINE_EXTRACT.md tests/test_laban_cross_asset_gate.py
git diff --cached --name-status
git commit -m "docs(laban): document cross-asset opportunity gate"
```

Expected staged paths: only the two files above.

## Task 7: Run isolated regression and publication verification

**Files:**

- No source-file changes expected.
- Temporary verification copy: unique folder under the system temp directory.

- [ ] **Step 1: Run the focused suite in the real workspace**

Run:

```powershell
python tests/test_laban_cross_asset_gate.py -v
```

Expected: `Ran 20 tests` and `OK`.

- [ ] **Step 2: Create a unique temporary La Bàn verification copy**

Run from `D:\V\0. VN Agent System`:

```powershell
$trialRoot = Join-Path ([IO.Path]::GetTempPath()) ("laban-cross-asset-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $trialRoot | Out-Null
New-Item -ItemType Directory -Path (Join-Path $trialRoot "scripts\reporting") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $trialRoot "data\decision") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $trialRoot "reports") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $trialRoot "tests") -Force | Out-Null
Copy-Item -LiteralPath "scripts\reporting\build_vn_structural_signals.py","scripts\reporting\laban_engine.py","scripts\reporting\laban_render.py","scripts\reporting\laban_cross_asset_gate.py","scripts\reporting\laban_cross_asset_render.py" -Destination (Join-Path $trialRoot "scripts\reporting")
Copy-Item -LiteralPath (Get-ChildItem -LiteralPath "data\decision" -File -Filter "*.json").FullName -Destination (Join-Path $trialRoot "data\decision")
Copy-Item -LiteralPath "reports\tollbooth_tracker_latest.html","reports\vn_structural_signals_fragment.html" -Destination (Join-Path $trialRoot "reports")
Copy-Item -LiteralPath "tests\test_laban_engine.py","tests\test_laban_cross_asset_gate.py" -Destination (Join-Path $trialRoot "tests")
Write-Output $trialRoot
```

Expected: a unique absolute temp path; the real reports/data remain untouched by subsequent steps.

- [ ] **Step 3: Run the pre-existing La Bàn regression suite in the temporary copy**

Run:

```powershell
$legacyTest = Join-Path $trialRoot "tests\test_laban_engine.py"
python $legacyTest
```

Expected: exit code 0 and all existing La Bàn tests report `OK`. Record the observed test count; do not prestate it because the current untracked suite can evolve independently.

- [ ] **Step 4: Build and inject twice in the temporary copy**

Run:

```powershell
Push-Location $trialRoot
python scripts/reporting/build_vn_structural_signals.py --as-of 2026-08-21 --inject
$snapshotSha1 = (Get-FileHash -Algorithm SHA256 "data\decision\laban_engine_snapshot.json").Hash
$htmlSha1 = (Get-FileHash -Algorithm SHA256 "reports\tollbooth_tracker_latest.html").Hash
python scripts/reporting/build_vn_structural_signals.py --as-of 2026-08-21 --inject
$snapshotSha2 = (Get-FileHash -Algorithm SHA256 "data\decision\laban_engine_snapshot.json").Hash
$htmlSha2 = (Get-FileHash -Algorithm SHA256 "reports\tollbooth_tracker_latest.html").Hash
Pop-Location
if ($snapshotSha1 -ne $snapshotSha2 -or $htmlSha1 -ne $htmlSha2) { throw "IDEMPOTENCY_FAIL" }
```

Expected: both builds exit 0; snapshot and HTML hashes are identical across the two runs.

- [ ] **Step 5: Verify rendered hard gates, Tariff Watch, and no protected semantics in the temporary HTML**

Run:

```powershell
$trialHtml = Get-Content -LiteralPath (Join-Path $trialRoot "reports\tollbooth_tracker_latest.html") -Raw -Encoding utf8
if (-not $trialHtml.Contains("Main transmission blocked → search harder, not stop.")) { throw "MISSING_GATE_1" }
if (-not $trialHtml.Contains("What is moving that VNINDEX cannot currently express, and which listed Vietnamese company is the best proxy for that move?")) { throw "MISSING_GATE_2" }
if (-not $trialHtml.Contains("MISSED-OPPORTUNITY PREVENTION")) { throw "MISSING_CARD" }
if (-not $trialHtml.Contains("Tariff watch")) { throw "TARIFF_WATCH_LOST" }
if ($trialHtml.Contains("ACTIONABLE")) { throw "PROHIBITED_ACTIONABLE_STATUS" }
```

Expected: exit code 0 with no output.

- [ ] **Step 6: Verify the real protected files did not change during testing**

Run:

```powershell
git status --short -- scripts/reporting/laban_engine.py scripts/reporting/laban_render.py tests/test_laban_engine.py data/decision/vn_structural_signals.json data/decision/laban_scenarios.json data/decision/laban_axis_state.json data/decision/laban_frame_log.json reports/tollbooth_tracker_latest.html reports/vn_structural_signals_fragment.html
```

Expected: exactly the same pre-existing status captured before Task 1; no new modification to any protected path.

- [ ] **Step 7: Run final diff hygiene checks**

Run:

```powershell
git diff --check
git diff --cached --name-status
git log -6 --oneline
```

Expected: `git diff --check` exits 0; no staged files remain; recent commits correspond to Tasks 1–6 plus the approved design commit.

## Task 8: Final implementation report and handoff

**Files:**

- Create: `reports/2026-08-21_cross_asset_opportunity_gate_implementation_report.md`

- [ ] **Step 1: Write the dated implementation report using observed evidence**

Create the report with these exact sections and replace each evidence bullet with the literal output observed in Task 7; do not use placeholders:

```markdown
# Cross-Asset Opportunity Transmission Gate — Implementation Report

**Date:** 2026-08-21

## FACTS

- Files created and modified, listed explicitly.
- Focused test command, observed test count, and result.
- Isolated legacy regression command, observed test count, and result.
- Temporary build snapshot SHA and HTML SHA from both idempotency runs.
- Exact confirmation that both hard-gate strings and Tariff Watch rendered.

## ASSUMPTIONS

- V1 remains operator-maintained and has no automatic global-data ingestion.
- `best_proxy_answer` remains a research result requiring human review.

## RISKS

- Coverage quality depends on a current full FireAnt universe and verified company-exposure data.
- The initial PNJ/gold mapping remains `DRAFT_POST_HOC` and cannot qualify a proxy.
- Same-family council review was process-independent, not provider-independent.

## ACTIONS

- Run a shadow pilot on the next material shock.
- Keep all candidates outside ThemePack/backtest/trading universes.
- Require V approval before any Phase 2 automation or mapping promotion.

**Next action required from V:** choose the first material shock for the shadow pilot or leave the gate in `NOT_APPLICABLE` until one occurs.
```

- [ ] **Step 2: Verify the implementation report**

Run:

```powershell
Select-String -LiteralPath reports/2026-08-21_cross_asset_opportunity_gate_implementation_report.md -Pattern '\b(TBD|TODO|FIXME|XXX)\b' -CaseSensitive:$false
```

Expected: no output.

- [ ] **Step 3: Commit only the implementation report**

Run:

```powershell
git add -- reports/2026-08-21_cross_asset_opportunity_gate_implementation_report.md
git diff --cached --name-status
git commit -m "docs(laban): report cross-asset gate implementation"
```

Expected staged path: only the implementation report.

## Final acceptance checklist

- [ ] Both hard-gate strings are byte-exact constants, JSON values, documentation text, and rendered output.
- [ ] Missing branches, evidence, or full-universe coverage fail closed and block recommendation finalization.
- [ ] Complete coverage can return no defensible proxy without forcing a ticker.
- [ ] Extended candidates always render `EXTENDED — DO NOT CHASE`.
- [ ] Cross-asset artifacts never enter `run_engine()` or affect its snapshot/hash.
- [ ] No candidate reaches ThemePack, backtest, A3/S3, `final_action`, sizing, OMS, broker, or live paths.
- [ ] PNJ/gold remains a post-hoc hypothesis until independently verified and prospectively confirmed.
- [ ] Current Tariff Watch and all existing user changes are preserved.
- [ ] Focused tests pass in the real workspace; legacy regression and publication checks pass in a temporary copy.
- [ ] Final report contains observed evidence and a concrete next action.

**Execution stop condition:** if any protected path gains an unexpected status, any existing La Bàn regression fails, or the engine snapshot changes solely because the sidecar changes, stop and return `NEEDS_HUMAN` with the exact diff, failing command, and required decision.
