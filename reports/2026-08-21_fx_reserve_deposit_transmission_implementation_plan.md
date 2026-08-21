# FX Reserve–Liquidity–Deposit Transmission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Run the Cursor `/verifier` after implementation because the approved design used architecture/judgment review.

**Goal:** Add a facts-first State 0–4 FX→reserve→VND-liquidity→deposit-rate transmission monitor to PM Regime, with a byte-safe non-scoring La Bàn T6 mirror.

**Architecture:** Extend the existing `rate_pivot_monitor.json` with one canonical `fx_reserve_deposit_transmission` object. A focused validator/normalizer computes one deterministic evidence hash; PM renders the full monitor, while La Bàn loads the normalized contract only after `run_engine()` and renders a compact T6 mirror. No signal, axis, scenario, weight, regime, A3/S3, OMS, or live path receives the contract.

**Tech Stack:** Python 3 stdlib, JSON, existing static HTML/CSS report generators, pytest/unittest, PowerShell verification.

**Approved design:** `reports/2026-08-21_fx_reserve_deposit_transmission_design.md`

---

## File map

### Create

- `scripts/reporting/rate_pivot_transmission.py` — shared schema validation, safe `UNKNOWN` fallback, promotion checks, and deterministic evidence hash.
- `tests/test_rate_pivot_transmission.py` — contract/state-machine unit tests.
- `tests/test_pm_dashboard_rate_pivot_transmission.py` — PM rendering and binding-gate tests.
- `tests/test_laban_transmission_mirror.py` — La Bàn mirror, ordering, parity, and non-scoring tests.

### Modify

- `data/research/rate_pivot_monitor.json` — add canonical contract; correct legacy C3/C6 evidence labels while preserving all unrelated content.
- `scripts/reporting/generate_pm_regime_dashboard.py` — full primary panel, Macro Pulse badge, and correct G2 binding callout.
- `scripts/reporting/build_vn_structural_signals.py` — load normalized contract only after engine computation and pass it to rendering only.
- `scripts/reporting/laban_render.py` — compact T6 mirror; no engine/scoring mutation.

### Regenerate

- `reports/pm_regime_dashboard_latest.html`
- `reports/tollbooth_tracker_latest.html`
- `reports/vn_structural_signals_fragment.html`

### Do not modify

- `scripts/reporting/laban_engine.py`
- `data/decision/laban_axis_state.json`
- `data/decision/vn_structural_signals.json`
- `data/decision/laban_scenarios.json`
- `data/decision/laban_frame_log.json`, except any pre-existing builder-owned idempotent behavior must be checked and reported
- A3/S3/OMS, `final_action`, signal math, backtests, DNSE, `live_auto`, or real-capital paths

The worktree is heavily dirty. Several listed files are modified or untracked already. Never replace a file wholesale, run a formatter across it, or stage unrelated changes.

## Task 1: Preflight and shared contract validator

**Files:**

- Create: `scripts/reporting/rate_pivot_transmission.py`
- Create: `tests/test_rate_pivot_transmission.py`

- [ ] **Step 1: Inspect and record the relevant dirty state**

Run:

```powershell
git status --short -- data/research/rate_pivot_monitor.json scripts/reporting/generate_pm_regime_dashboard.py scripts/reporting/build_vn_structural_signals.py scripts/reporting/laban_engine.py scripts/reporting/laban_render.py reports/pm_regime_dashboard_latest.html reports/tollbooth_tracker_latest.html tests
git diff -- scripts/reporting/generate_pm_regime_dashboard.py scripts/reporting/build_vn_structural_signals.py scripts/reporting/laban_render.py
```

Expected: inspectable output. Preserve every pre-existing hunk. `laban_engine.py` remains untouched.

- [ ] **Step 2: Load the three mandatory UI skills before any HTML/CSS edit**

Read completely:

```text
D:\V\.agents\skills\animation\SKILL.md
D:\V\.agents\skills\impeccable\SKILL.md
D:\V\.agents\skills\taste\SKILL.md
```

Apply the existing minimal enterprise palette and IBM Plex patterns. Add no decorative animation unless it improves state comprehension.

- [ ] **Step 3: Write failing validator tests**

Create `tests/test_rate_pivot_transmission.py` with these exact behavioral tests:

```python
from copy import deepcopy

from scripts.reporting.rate_pivot_transmission import (
    STATE_LABELS,
    compute_evidence_hash,
    normalize_transmission_contract,
    promotion_allowed,
)


def _contract(state_id: int = 1) -> dict:
    return {
        "schema": "fx_reserve_deposit_transmission_v1",
        "as_of": "2026-08-21",
        "headline": "FX PRESSURE EASING — POTENTIAL RESERVE-REBUILD SETUP",
        "current_state": {
            "id": state_id,
            "label": STATE_LABELS[state_id],
            "status": "SETUP / APPROACHING",
            "evidence_class": "OBSERVATION",
            "confirmation_status": "NOT_CONFIRMED",
        },
        "state_machine": [
            {"id": 2, "label": STATE_LABELS[2], "requirements": [
                {"id": "formal_usd_stable", "status": "UNKNOWN", "freshness": "UNKNOWN", "claim_class": "UNCONFIRMED", "source_quality": "UNCONFIRMED"},
                {"id": "actual_usd_available", "status": "UNKNOWN", "freshness": "UNKNOWN", "claim_class": "UNCONFIRMED", "source_quality": "UNCONFIRMED"},
                {"id": "bank_fx_surplus", "status": "UNKNOWN", "freshness": "UNKNOWN", "claim_class": "UNCONFIRMED", "source_quality": "UNCONFIRMED"},
            ]},
            {"id": 3, "label": STATE_LABELS[3], "requirements": [
                {"id": "sbv_purchase_or_reserve_rise", "status": "UNKNOWN", "freshness": "UNKNOWN", "claim_class": "UNCONFIRMED", "source_quality": "UNCONFIRMED"},
                {"id": "vnd_injection", "status": "UNKNOWN", "freshness": "UNKNOWN", "claim_class": "UNCONFIRMED", "source_quality": "UNCONFIRMED"},
                {"id": "vnd_interbank_easing", "status": "UNKNOWN", "freshness": "UNKNOWN", "claim_class": "UNCONFIRMED", "source_quality": "UNCONFIRMED"},
            ]},
            {"id": 4, "label": STATE_LABELS[4], "requirements": [
                {"id": "big4_6_12m_decline", "status": "UNKNOWN", "freshness": "UNKNOWN", "claim_class": "UNCONFIRMED", "source_quality": "UNCONFIRMED"},
                {"id": "tier2_follow", "status": "UNKNOWN", "freshness": "UNKNOWN", "claim_class": "UNCONFIRMED", "source_quality": "UNCONFIRMED"},
                {"id": "funding_stable_credit_strong", "status": "UNKNOWN", "freshness": "UNKNOWN", "claim_class": "UNCONFIRMED", "source_quality": "UNCONFIRMED"},
            ]},
        ],
        "evidence_ladder": {"observation": [], "inference": [], "confirmation": []},
        "channels": {"fx": [], "external_flows": [], "reserve_liquidity": [], "bank_funding": []},
        "regulatory_funding_relief": {},
        "confirmation_checklist": [],
        "falsifiers": [],
        "scoring_effect": {"pm_regime": "NONE", "laban_regime": "NONE"},
    }


def _pass(row: dict) -> None:
    row.update(status="PASS", freshness="FRESH", claim_class="FACT", source_quality="PRIMARY")


def test_missing_contract_is_unknown_not_empty():
    got = normalize_transmission_contract({})
    assert got["current_state"]["label"] == "UNKNOWN"
    assert got["current_state"]["confirmation_status"] == "NOT_CONFIRMED"
    assert got["integrity_status"] == "UNKNOWN"


def test_hash_is_deterministic_and_ignores_declared_hash():
    raw = _contract()
    first = compute_evidence_hash(raw)
    raw["evidence_hash"] = "sha256:stale"
    assert compute_evidence_hash(raw) == first


def test_no_state_skip():
    raw = _contract(1)
    assert promotion_allowed(raw, 3) is False


def test_missing_bank_fx_supply_blocks_state_2():
    raw = _contract(1)
    state2 = raw["state_machine"][0]
    _pass(state2["requirements"][0])
    _pass(state2["requirements"][1])
    assert promotion_allowed(raw, 2) is False


def test_missing_reserve_evidence_blocks_state_3():
    raw = _contract(2)
    state3 = raw["state_machine"][1]
    _pass(state3["requirements"][1])
    _pass(state3["requirements"][2])
    assert promotion_allowed(raw, 3) is False


def test_unchanged_deposits_block_state_4():
    raw = _contract(3)
    state4 = raw["state_machine"][2]
    _pass(state4["requirements"][1])
    _pass(state4["requirements"][2])
    assert promotion_allowed(raw, 4) is False


def test_regulatory_relief_never_satisfies_monetary_requirements():
    raw = _contract(1)
    raw["regulatory_funding_relief"] = {"status": "PASS", "claim_class": "FACT"}
    assert promotion_allowed(raw, 2) is False


def test_bad_state_label_fails_closed():
    raw = _contract(1)
    raw["current_state"]["label"] = "RESERVE REBUILD CONFIRMED"
    got = normalize_transmission_contract({"fx_reserve_deposit_transmission": raw})
    assert got["integrity_status"] == "UNKNOWN"
    assert got["current_state"]["label"] == "UNKNOWN"


def test_malformed_evidence_row_fails_closed():
    raw = _contract(1)
    raw["channels"]["fx"] = [{"variable_id": "parallel_usd_vnd"}]
    got = normalize_transmission_contract({"fx_reserve_deposit_transmission": raw})
    assert got["integrity_status"] == "UNKNOWN"


def test_claimed_state_3_without_required_evidence_fails_closed():
    raw = _contract(3)
    got = normalize_transmission_contract({"fx_reserve_deposit_transmission": raw})
    assert got["integrity_status"] == "UNKNOWN"
    assert got["current_state"]["label"] == "UNKNOWN"
```

- [ ] **Step 4: Run tests and confirm they fail for the missing module**

Run:

```powershell
python -m pytest tests/test_rate_pivot_transmission.py -q
```

Expected: FAIL during import because `scripts.reporting.rate_pivot_transmission` does not exist.

- [ ] **Step 5: Implement the minimal shared module**

Create `scripts/reporting/rate_pivot_transmission.py` with:

```python
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

SCHEMA = "fx_reserve_deposit_transmission_v1"
STATE_LABELS = {
    0: "FX PRESSURE",
    1: "FX PRESSURE EASING",
    2: "RESERVE-REBUILD SETUP",
    3: "RESERVE REBUILD / LIQUIDITY TRANSMISSION CONFIRMED",
    4: "DEPOSIT-RATE PIVOT CONFIRMED",
}
_RELIABLE = {"PRIMARY", "CREDIBLE_SECONDARY"}
_EVIDENCE_REQUIRED = {
    "variable_id", "label", "value", "unit", "as_of", "claim_class",
    "source_quality", "freshness", "status", "source_name",
    "source_url_or_path", "notes",
}
_CLAIM_CLASSES = {"FACT", "INFERENCE", "MARKET_CHATTER", "UNCONFIRMED"}
_SOURCE_QUALITIES = {"PRIMARY", "CREDIBLE_SECONDARY", "SOURCE_SECONDARY", "UNCONFIRMED"}
_FRESHNESS = {"FRESH", "STALE", "UNKNOWN"}
_ROW_STATUS = {"PASS", "PARTIAL", "UNKNOWN", "FAIL", "NOT_COMPARABLE"}


def compute_evidence_hash(contract: dict[str, Any]) -> str:
    payload = deepcopy(contract)
    payload.pop("evidence_hash", None)
    payload.pop("integrity_status", None)
    payload.pop("integrity_errors", None)
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _unknown(reason: str) -> dict[str, Any]:
    contract = {
        "schema": SCHEMA,
        "as_of": "Unknown",
        "headline": "FX–LIQUIDITY TRANSMISSION — UNKNOWN / STALE",
        "current_state": {
            "id": None,
            "label": "UNKNOWN",
            "status": "UNKNOWN / STALE",
            "evidence_class": "UNCONFIRMED",
            "confirmation_status": "NOT_CONFIRMED",
        },
        "state_machine": [],
        "evidence_ladder": {"observation": [], "inference": [], "confirmation": []},
        "channels": {"fx": [], "external_flows": [], "reserve_liquidity": [], "bank_funding": []},
        "regulatory_funding_relief": {},
        "confirmation_checklist": [],
        "falsifiers": [],
        "scoring_effect": {"pm_regime": "NONE", "laban_regime": "NONE"},
        "integrity_status": "UNKNOWN",
        "integrity_errors": [reason],
    }
    contract["evidence_hash"] = compute_evidence_hash(contract)
    return contract


def normalize_transmission_contract(monitor: dict[str, Any]) -> dict[str, Any]:
    raw = monitor.get("fx_reserve_deposit_transmission")
    if not isinstance(raw, dict):
        return _unknown("missing fx_reserve_deposit_transmission")
    if raw.get("schema") != SCHEMA:
        return _unknown("unsupported transmission schema")
    state = raw.get("current_state") or {}
    state_id = state.get("id")
    if state_id not in STATE_LABELS or state.get("label") != STATE_LABELS[state_id]:
        return _unknown("current_state id/label mismatch")
    out = deepcopy(raw)
    out["integrity_status"] = "VALID"
    out["integrity_errors"] = []
    out["evidence_hash"] = compute_evidence_hash(out)
    return out


def _requirements_for(contract: dict[str, Any], target_state: int) -> list[dict[str, Any]]:
    for state in contract.get("state_machine") or []:
        if state.get("id") == target_state:
            return list(state.get("requirements") or [])
    return []


def _requirements_pass(contract: dict[str, Any], target_state: int) -> bool:
    requirements = _requirements_for(contract, target_state)
    return bool(requirements) and all(
        row.get("status") == "PASS"
        and row.get("freshness") == "FRESH"
        and row.get("claim_class") == "FACT"
        and row.get("source_quality") in _RELIABLE
        for row in requirements
    )


def _evidence_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in (contract.get("evidence_ladder") or {}).values():
        rows.extend(group or [])
    for group in (contract.get("channels") or {}).values():
        rows.extend(group or [])
    rows.extend(contract.get("confirmation_checklist") or [])
    return rows


def _evidence_rows_valid(contract: dict[str, Any]) -> bool:
    for row in _evidence_rows(contract):
        if not isinstance(row, dict) or not _EVIDENCE_REQUIRED.issubset(row):
            return False
        if row["claim_class"] not in _CLAIM_CLASSES:
            return False
        if row["source_quality"] not in _SOURCE_QUALITIES:
            return False
        if row["freshness"] not in _FRESHNESS or row["status"] not in _ROW_STATUS:
            return False
    return True


def promotion_allowed(contract: dict[str, Any], target_state: int) -> bool:
    current = (contract.get("current_state") or {}).get("id")
    if not isinstance(current, int) or target_state != current + 1:
        return False
    return _requirements_pass(contract, target_state)
```

Before assigning `integrity_status = "VALID"` in `normalize_transmission_contract`, add:

```python
    if not _evidence_rows_valid(raw):
        return _unknown("malformed evidence row")
    if any(not _requirements_pass(raw, target) for target in range(2, state_id + 1)):
        return _unknown("claimed state lacks fresh confirmed prerequisite evidence")
```

- [ ] **Step 6: Run validator tests**

Run:

```powershell
python -m pytest tests/test_rate_pivot_transmission.py -q
```

Expected: `10 passed`.

- [ ] **Step 7: Commit the focused module and tests**

```powershell
git add -- scripts/reporting/rate_pivot_transmission.py tests/test_rate_pivot_transmission.py
git diff --cached --check
git commit -m "feat(macro): add FX transmission contract validator"
```

## Task 2: Add the canonical State 1 contract and correct legacy evidence labels

**Files:**

- Modify: `data/research/rate_pivot_monitor.json`
- Modify: `tests/test_rate_pivot_transmission.py`

- [ ] **Step 1: Add a failing current-data test**

Append:

```python
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_current_monitor_is_state_1_and_non_scoring():
    monitor = json.loads((REPO / "data/research/rate_pivot_monitor.json").read_text(encoding="utf-8"))
    got = normalize_transmission_contract(monitor)
    assert got["integrity_status"] == "VALID"
    assert got["current_state"] == {
        "id": 1,
        "label": "FX PRESSURE EASING",
        "status": "SETUP / APPROACHING",
        "evidence_class": "OBSERVATION",
        "confirmation_status": "NOT_CONFIRMED",
    }
    assert got["deposit_thesis"]["upgrade"] == "NONE"
    assert set(got["scoring_effect"].values()) == {"NONE"}


def test_legacy_c3_c6_are_not_overstated():
    monitor = json.loads((REPO / "data/research/rate_pivot_monitor.json").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in monitor["criteria"]}
    assert by_id["C3"]["status"] == "APPROACHING"
    assert by_id["C6"]["status"] == "WATCH"
    assert monitor["council_v2_framework"]["tier2_leading_signals"]["P2_deposit_rate_diffusion"]["current_status"] == "MIXED"
    assert monitor["council_v2_framework"]["current_v2_assessment"]["v2_score"] == 0
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
python -m pytest tests/test_rate_pivot_transmission.py -q
```

Expected: the two new tests FAIL because the contract is absent and C3/C6 are overstated.

- [ ] **Step 3: Patch the existing JSON without replacing it**

Apply a minimal structured patch:

- Add the exact canonical object specified in the approved design.
- Set `current_state` to State 1 and `confirmation_status` to `NOT_CONFIRMED`.
- Populate all 18 monitoring variables. Use `null`, `UNKNOWN`, and a source/date note wherever current comparable evidence is absent.
- Set checklist item 1 and item 6 to `PARTIAL`; set the remaining seven to `UNKNOWN` unless Cursor obtains fresh, directly comparable evidence from already-authorized local sources. Do not browse in order to promote the state.
- State 2, 3, and 4 requirements remain non-passing.
- Keep the 50% Treasury-deposit LDR item `SOURCE_SECONDARY / UNCONFIRMED_PRIMARY`; regulatory relief remains separate.
- Set legacy C3 `CONFIRMED → APPROACHING`; explain that current same-leg formal comparison is unavailable.
- Set legacy C6 `APPROACHING → WATCH`; explain that exact bank/product/tier evidence remains unresolved.
- Keep V2 P2 `MIXED`, V2 score `0`, and overall PM/La Bàn regime effects `NONE`.
- Append dated C3/C6 history rows; do not rewrite earlier history.

After patching, compute and store the hash printed by:

```powershell
python -c "import json; from pathlib import Path; from scripts.reporting.rate_pivot_transmission import compute_evidence_hash; p=Path('data/research/rate_pivot_monitor.json'); d=json.loads(p.read_text(encoding='utf-8')); print(compute_evidence_hash(d['fx_reserve_deposit_transmission']))"
```

The stored value is an audit field. Consumers recompute the deterministic value so both surfaces stay identical.

- [ ] **Step 4: Validate JSON and tests**

Run:

```powershell
python -m json.tool data/research/rate_pivot_monitor.json | Out-Null
python -m pytest tests/test_rate_pivot_transmission.py -q
```

Expected: valid JSON and `12 passed`.

- [ ] **Step 5: Commit only the monitor and focused test**

```powershell
git add -- data/research/rate_pivot_monitor.json tests/test_rate_pivot_transmission.py
git diff --cached --check
git commit -m "data(macro): add State 1 FX liquidity transmission monitor"
```

## Task 3: Render the full primary panel in PM Regime

**Files:**

- Create: `tests/test_pm_dashboard_rate_pivot_transmission.py`
- Modify: `scripts/reporting/generate_pm_regime_dashboard.py`
- Regenerate: `reports/pm_regime_dashboard_latest.html`

- [ ] **Step 1: Write failing PM tests**

Create:

```python
import json
from pathlib import Path

from scripts.reporting.generate_pm_regime_dashboard import (
    _render_rate_pivot_monitor,
    build_html,
)

REPO = Path(__file__).resolve().parents[1]


def _monitor() -> dict:
    return json.loads((REPO / "data/research/rate_pivot_monitor.json").read_text(encoding="utf-8"))


def test_pm_renders_full_transmission_panel():
    html = _render_rate_pivot_monitor(_monitor())
    for text in (
        "FX PRESSURE EASING",
        "POTENTIAL RESERVE-REBUILD SETUP",
        "STATE 1",
        "NOT CONFIRMED",
        "OBSERVATION",
        "INFERENCE",
        "CONFIRMATION",
        "Regulatory funding relief",
        "Actual monetary liquidity creation",
        "FALSIFIERS",
    ):
        assert text.lower() in html.lower()
    assert "2007 repeat" not in html.lower()
    assert "liquidity boom confirmed" not in html.lower()


def test_g2_is_binding_when_g1_passes_and_g2_fails():
    html = _render_rate_pivot_monitor(_monitor())
    assert "G2" in html and "binding" in html.lower()
    assert "G1 FX veto is binding" not in html


def test_macro_pulse_badge_is_advisory_only():
    data = json.loads((REPO / "data/raw/pm_dashboard_data.json").read_text(encoding="utf-8"))
    html = build_html(data)
    assert "FX → Liquidity: STATE 1 · NOT CONFIRMED" in html
    assert "SYSTEM ROUTING: Reporting only" in html
```

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests/test_pm_dashboard_rate_pivot_transmission.py -q
```

Expected: FAIL because the transmission panel and badge are not rendered and binding logic is incomplete.

- [ ] **Step 3: Patch the PM generator minimally**

In `generate_pm_regime_dashboard.py`:

1. Import `normalize_transmission_contract` from `scripts.reporting.rate_pivot_transmission`.
2. Normalize the full monitor inside `_render_rate_pivot_monitor`.
3. Add `_render_fx_transmission(contract: dict) -> str` that renders:
   - headline/status;
   - State 0–4 ladder;
   - Observation/Inference/Confirmation;
   - FX/external-flow/reserve-liquidity/bank-funding groups;
   - separate regulatory versus monetary-liquidity cards;
   - checklist, falsifiers, implications;
   - historical note inside collapsed `<details>`.
4. Prepend that HTML to the existing V2 panel; do not remove V2.
5. Add `FX → Liquidity: STATE 1 · NOT CONFIRMED` near Macro Pulse, with the existing reporting-only routing footer.
6. Replace the binding calculation with explicit gate parsing:

```python
g1_fails = "FAIL" in g1_raw.upper()
g2_fails = "FAIL" in g2_raw.upper()
if g1_fails:
    binding = "G1 FX permission is binding — V2 score remains gated."
elif g2_fails:
    binding = "G2 inflation permission is binding — V2 score remains gated despite G1 FX passing."
else:
    binding = ""
```

Use existing CSS variables and card patterns. Do not add stock recommendations, action verbs, a new regime score, or a second data source.

- [ ] **Step 4: Run PM tests**

```powershell
python -m pytest tests/test_pm_dashboard_rate_pivot_transmission.py tests/test_pm_dashboard_macro_semantics.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Regenerate and inspect PM HTML**

```powershell
python scripts/reporting/generate_pm_regime_dashboard.py
Select-String -LiteralPath reports/pm_regime_dashboard_latest.html -Pattern 'FX PRESSURE EASING','STATE 1','NOT CONFIRMED','G2 inflation permission is binding','Regulatory funding relief','FALSIFIERS'
```

Expected: generator exits `0`; every required phrase is found.

- [ ] **Step 6: Commit source, test, and intended generated report only**

```powershell
git add -- scripts/reporting/generate_pm_regime_dashboard.py tests/test_pm_dashboard_rate_pivot_transmission.py reports/pm_regime_dashboard_latest.html
git diff --cached --check
git commit -m "feat(reporting): render FX transmission in PM Regime"
```

## Task 4: Add the non-scoring La Bàn T6 mirror

**Files:**

- Create: `tests/test_laban_transmission_mirror.py`
- Modify: `scripts/reporting/build_vn_structural_signals.py`
- Modify: `scripts/reporting/laban_render.py`
- Regenerate: `reports/vn_structural_signals_fragment.html`
- Regenerate: `reports/tollbooth_tracker_latest.html`

- [ ] **Step 1: Write failing La Bàn tests**

Create:

```python
import json
from pathlib import Path

from scripts.reporting.rate_pivot_transmission import normalize_transmission_contract

REPO = Path(__file__).resolve().parents[1]


def _contract() -> dict:
    monitor = json.loads((REPO / "data/research/rate_pivot_monitor.json").read_text(encoding="utf-8"))
    return normalize_transmission_contract(monitor)


def test_laban_mirror_renders_state_asof_hash():
    from scripts.reporting.laban_render import render_fx_transmission_mirror
    contract = _contract()
    html = render_fx_transmission_mirror(contract)
    assert "State 1" in html
    assert "Not confirmed" in html
    assert contract["as_of"] in html
    assert contract["evidence_hash"] in html
    assert "GT1 impact: monitoring only" in html


def test_builder_loads_transmission_after_engine_call():
    source = (REPO / "scripts/reporting/build_vn_structural_signals.py").read_text(encoding="utf-8")
    assert source.index("snapshot = run_engine(") < source.index("normalize_transmission_contract(")


def test_contract_never_enters_engine_inputs_or_decision_files():
    source = (REPO / "scripts/reporting/build_vn_structural_signals.py").read_text(encoding="utf-8")
    call = source.split("snapshot = run_engine(", 1)[1].split(")", 1)[0]
    assert "transmission" not in call
    for name in (
        "data/decision/laban_axis_state.json",
        "data/decision/vn_structural_signals.json",
        "data/decision/laban_scenarios.json",
    ):
        assert "fx_reserve_deposit_transmission" not in (REPO / name).read_text(encoding="utf-8")
```

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests/test_laban_transmission_mirror.py -q
```

Expected: FAIL because the mirror function/wiring does not exist.

- [ ] **Step 3: Add render-only wiring**

In `build_vn_structural_signals.py`:

- Add `RATE_PIVOT_MONITOR_PATH` beside other read paths.
- Import the shared normalizer.
- Keep `snapshot = run_engine(...)` unchanged.
- Immediately after a successful engine result, load and normalize the monitor:

```python
transmission_contract = normalize_transmission_contract(
    load_json(RATE_PIVOT_MONITOR_PATH) if RATE_PIVOT_MONITOR_PATH.is_file() else {}
)
```

- Pass only `transmission_contract=transmission_contract` to `render_laban_block`.

In `laban_render.py`:

- Add `render_fx_transmission_mirror(contract)`.
- Extend `render_t6_assumptions(..., transmission_contract=None)` and prepend the mirror to the existing GT1/assumption content.
- Extend `render_laban_block(..., transmission_contract=None)` and pass it only to T6 rendering.
- Escape every external string.
- Render `UNKNOWN / STALE` visibly when normalization fails.
- Include `as_of` and full `evidence_hash` in collapsed audit detail.
- Do not mutate `snapshot`, axes, assumptions, or advisory-link documents.

- [ ] **Step 4: Run focused tests**

```powershell
python -m pytest tests/test_laban_transmission_mirror.py tests/test_rate_pivot_transmission.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Verify La Bàn engine invariance before injection**

Run this read-only comparison:

```powershell
python -c "import json,sys; from pathlib import Path; p=Path('.'); sys.path.insert(0,str(p/'scripts/reporting')); from laban_engine import run_engine; L=lambda n:json.loads((p/'data/decision'/n).read_text(encoding='utf-8')); s=run_engine(L('laban_scenarios.json'),L('laban_signatures.json'),L('vn_structural_signals.json'),L('laban_axis_state.json'),L('laban_frame_log.json'),as_of='2026-08-21',kill_doc=L('laban_kill_conditions.json'),assumptions_doc=L('laban_thesis_assumptions.json')); print(json.dumps({'weights':s['weights'],'axis_state':s['axis_state'],'hard':s.get('kill_conditions')},ensure_ascii=False,sort_keys=True))"
```

Expected: output matches the baseline captured before implementation for weights, axes, and hard-invalidation state.

- [ ] **Step 6: Inject and inspect La Bàn T6**

```powershell
python scripts/reporting/build_vn_structural_signals.py --as-of 2026-08-21 --inject
Select-String -LiteralPath reports/tollbooth_tracker_latest.html -Pattern 'FX–LIQUIDITY TRANSMISSION','State 1','Not confirmed','GT1 impact: monitoring only'
```

Expected: builder exits `0`; all four phrases appear in T6.

- [ ] **Step 7: Commit only intended La Bàn files**

```powershell
git add -- scripts/reporting/build_vn_structural_signals.py scripts/reporting/laban_render.py tests/test_laban_transmission_mirror.py reports/vn_structural_signals_fragment.html reports/tollbooth_tracker_latest.html
git diff --cached --check
git commit -m "feat(laban): mirror FX liquidity state in T6"
```

## Task 5: Full verification and institutional review pack

**Files:**

- Create: `reports/2026-08-21_fx_reserve_deposit_transmission_cursor_review.md`

- [ ] **Step 1: Run all targeted tests**

```powershell
python -m pytest tests/test_rate_pivot_transmission.py tests/test_pm_dashboard_rate_pivot_transmission.py tests/test_laban_transmission_mirror.py tests/test_pm_dashboard_macro_semantics.py tests/test_laban_engine.py -q
```

Expected: exit `0`, no failures.

- [ ] **Step 2: Rebuild both target reports again from current sources**

```powershell
python scripts/reporting/generate_pm_regime_dashboard.py
python scripts/reporting/build_vn_structural_signals.py --as-of 2026-08-21 --inject
```

Expected: both commands exit `0`.

- [ ] **Step 3: Verify cross-surface parity and forbidden labels**

Run:

```powershell
$pm = Get-Content -LiteralPath reports/pm_regime_dashboard_latest.html -Raw -Encoding UTF8
$lb = Get-Content -LiteralPath reports/tollbooth_tracker_latest.html -Raw -Encoding UTF8
$contract = python -c "import json; from pathlib import Path; from scripts.reporting.rate_pivot_transmission import normalize_transmission_contract; d=json.loads(Path('data/research/rate_pivot_monitor.json').read_text(encoding='utf-8')); c=normalize_transmission_contract(d); print(c['evidence_hash'])"
if (-not $pm.Contains($contract)) { throw 'PM evidence hash mismatch' }
if (-not $lb.Contains($contract)) { throw 'La Ban evidence hash mismatch' }
foreach ($forbidden in @('2007 repeat','liquidity boom confirmed','reserve accumulation confirmed','deposit rate downtrend confirmed')) {
  if ($pm.ToLowerInvariant().Contains($forbidden)) { throw "Forbidden PM label: $forbidden" }
  if ($lb.ToLowerInvariant().Contains($forbidden)) { throw "Forbidden La Ban label: $forbidden" }
}
```

Expected: no exception.

- [ ] **Step 4: Run a skeptical Cursor verifier**

Invoke `/verifier` with only:

- approved design;
- implementation plan;
- relevant git diff;
- targeted test output;
- before/after La Bàn weights/state summary.

The verifier must check evidence semantics, same-leg FX comparisons, exact-key deposit logic, stale/unknown failure behavior, non-scoring isolation, and dirty-worktree preservation. If implementation diverges from the approved architecture, stop and invoke `/architecture-advisor`; do not invent a new pathway.

- [ ] **Step 5: Write the dated review pack**

Create `reports/2026-08-21_fx_reserve_deposit_transmission_cursor_review.md` with these sections:

```text
Date
FACTS
FILES CHANGED
FILES NOT TOUCHED
SECTIONS/CARDS CHANGED
OLD STATE → NEW STATE
MONITORING VARIABLES ADDED
CHECKS RUN AND EXACT RESULTS
LA BÀN/PM SCORE INVARIANCE
DATA GAPS / UNKNOWN
RISKS
ACTIONS
```

Record exact test counts and command exits. Do not claim completion from visual inspection alone.

- [ ] **Step 6: Final scope and secret check**

```powershell
git status --short
git diff --check
git diff --name-only 38c121c4..HEAD
git grep -n -E '(api[_-]?key|password|bearer [A-Za-z0-9_-]{20,})' -- scripts/reporting tests reports/2026-08-21_fx_reserve_deposit_transmission_cursor_review.md
```

Expected: only intended task files in the three task commits; no new secret value; unrelated dirty files remain untouched.

- [ ] **Step 7: Commit the review pack**

```powershell
git add -- reports/2026-08-21_fx_reserve_deposit_transmission_cursor_review.md
git diff --cached --check
git commit -m "docs(macro): verify FX liquidity transmission rollout"
```

## Completion contract

Cursor returns:

- files changed and files not touched;
- exact test/build outputs;
- old→new state table;
- all 18 monitoring-variable statuses;
- unresolved `UNKNOWN` data;
- proof that PM V2 score, PM overall regime, La Bàn axes, weights, scenarios, and regime state did not change;
- verifier verdict;
- next decision required from the user.

No deployment, push, production action, live trading, broker action, or real-capital action is authorized.
