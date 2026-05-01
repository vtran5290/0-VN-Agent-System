from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "sstock_general_data_series_sample.json"


def test_extract_latest_point_filters_by_asof_date():
    from src.macro.vietnam_liquidity.providers import sstock_provider as sp

    asof = _dt.date(2026, 3, 25)
    item = {
        "name": "OMO net",
        "data": [
            {"date": "2026-03-25", "value": None},
            {"date": "2026-03-24", "value": 900},
            {"date": "2026-03-23", "value": 800},
            {"date": "2026-03-25", "value": "1100"},
        ],
    }
    latest = sp._extract_latest_point_from_series_item(item, asof=asof)
    assert latest == ("2026-03-25", 1100.0)


def test_extract_fields_from_response_and_normalize_types():
    from src.macro.vietnam_liquidity.providers import sstock_provider as sp

    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    facts, used_labels = sp._extract_fields_from_response(payload, asof=_dt.date(2026, 3, 25))

    assert facts["omo_net"] == 1100  # normalized to int
    assert facts["fx_usd_vnd"] == 25104  # normalized to int
    assert facts["interbank_on"] == 8.05  # rounded to 2 decimals
    assert facts["credit_growth_yoy"] == 1.0  # rounded to 2 decimals

    # Ensure labels were used (best-effort matching).
    assert used_labels["omo_net"] is not None
    assert used_labels["fx_usd_vnd"] is not None


def test_auth_missing_returns_null_facts_and_errors():
    from src.macro.vietnam_liquidity.providers.sstock_provider import fetch_vietnam_liquidity_sstock

    # No SStock cookie/token env vars are expected in test environment.
    facts = fetch_vietnam_liquidity_sstock(asof="2026-03-25", session_cookie=None, session_token=None, timeout_s=1)
    assert all(facts.values[f] is None for f in facts.values)
    assert any("auth" in e.lower() for e in facts.errors)


def test_merge_auto_fills_missing_from_sstock():
    from src.macro.vietnam_liquidity.adapter import merge_vietnam_liquidity

    existing = {"omo_net": None, "interbank_on": 8.0, "credit_growth_yoy": None, "fx_usd_vnd": 25000}
    sstock = {"omo_net": 1100, "interbank_on": 8.05, "credit_growth_yoy": 1.0, "fx_usd_vnd": 25104}

    chosen = merge_vietnam_liquidity(
        existing=existing,
        sstock=sstock,
        provider_mode="auto",
        existing_source_name="sbv",
        sstock_source_name="sstock",
        existing_meta={},
        sstock_meta={},
    )

    assert chosen.values["interbank_on"] == 8.0  # existing wins when present
    assert chosen.values["omo_net"] == 1100  # fill missing
    assert chosen.values["credit_growth_yoy"] == 1.0  # fill missing
    assert chosen.values["fx_usd_vnd"] == 25000  # existing wins when present


def test_compare_output_status_and_chosen_source():
    from src.macro.vietnam_liquidity.orchestrator import compare_vietnam_liquidity
    from src.macro.vietnam_liquidity.models import VietnamFieldProvenance, VietnamLiquidityFacts

    asof = "2026-03-25"
    existing = VietnamLiquidityFacts(
        values={"omo_net": 1100, "interbank_on": 8.05, "credit_growth_yoy": 1.0, "fx_usd_vnd": 25104},
        meta={},
        errors=[],
    )
    sstock = VietnamLiquidityFacts(
        values={"omo_net": 1100, "interbank_on": 8.06, "credit_growth_yoy": None, "fx_usd_vnd": 25104},
        meta={},
        errors=[],
    )
    chosen = VietnamLiquidityFacts(
        values={"omo_net": 1100, "interbank_on": 8.05, "credit_growth_yoy": None, "fx_usd_vnd": 25104},
        meta={},
        errors=[],
    )

    # compare_vietnam_liquidity reads chosen.meta[field].chosen_source
    for f in ["omo_net", "interbank_on", "credit_growth_yoy", "fx_usd_vnd"]:
        chosen.meta[f] = VietnamFieldProvenance(
            field=f,
            chosen_source="sbv",
            existing_source="sbv",
            sstock_source="sstock",
            series_name=None,
            as_of=asof,
            fetched_at=None,
            verification_status="parsed",
            confidence=None,
        )

    compare = compare_vietnam_liquidity(asof=asof, existing=existing, sstock=sstock, chosen=chosen)
    items = {it["field"]: it for it in compare["items"]}
    assert items["omo_net"]["status"] == "match"
    assert items["fx_usd_vnd"]["status"] == "match"
    assert items["credit_growth_yoy"]["status"] in ("missing_sstock", "mismatch", "missing")  # chosen_value is None and sstock missing

