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

