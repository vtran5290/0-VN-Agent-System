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
    if not _evidence_rows_valid(raw):
        return _unknown("malformed evidence row")
    if any(not _requirements_pass(raw, target) for target in range(2, state_id + 1)):
        return _unknown("claimed state lacks fresh confirmed prerequisite evidence")
    out = deepcopy(raw)
    out["integrity_status"] = "VALID"
    out["integrity_errors"] = []
    out["evidence_hash"] = compute_evidence_hash(out)
    return out


def promotion_allowed(contract: dict[str, Any], target_state: int) -> bool:
    current = (contract.get("current_state") or {}).get("id")
    if not isinstance(current, int) or target_state != current + 1:
        return False
    return _requirements_pass(contract, target_state)
