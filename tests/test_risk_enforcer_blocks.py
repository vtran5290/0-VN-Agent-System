"""Risk / Council Enforcer hard-block coverage.

Targets the canonical block paths required by `docs/RISK_ENFORCER_SPEC.md`:

- unknown / research / watchlist strategy → block on BUY
- stale council output → block on new BUY exposure
- stale / missing consensus_pack → block on new BUY exposure
- stale / missing research_engine_pack → block on new BUY exposure
- invalid order intent schema → block
- invalid stop distance → sizing blocks
"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from src.mcp_server import adapters as A


def _intent(**overrides) -> Dict[str, Any]:
    base = {
        "symbol": "FPT",
        "side": "BUY",
        "strategy_id": "A3_DP",
        "setup_type": "breakout",
        "entry_price": 100000,
        "stop_price": 90000,
        "account_equity": 1e9,
        "adv50_vnd": 5e9,
        "asof": "2099-01-01",
    }
    base.update(overrides)
    return base


def _patch_packs(monkeypatch, *, council=False, consensus=False, research=False, manual=False):
    monkeypatch.setattr(
        A,
        "manual_input_status",
        lambda: {
            "manual_inputs": {"stale": manual, "required_for_council": True},
            "consensus_pack": {"stale": consensus, "required_for_council": True},
            "research_engine_pack": {"stale": research, "required_for_council": True},
        },
    )
    monkeypatch.setattr(
        A,
        "council_snapshot",
        lambda asof="": {
            "stale": council,
            "decision_stance": "neutral",
            "top_actions": [],
            "top_risks": [],
            "constraints": {},
            "timestamp": None,
            "source_path": "",
            "source_hash": None,
        },
    )


# ── strategy-status blocks ────────────────────────────────────────────────

def test_unknown_strategy_blocks_buy():
    enf = A.enforce_portfolio_constraints_impl(order_intent=_intent(strategy_id="NOT_A_STRATEGY"))
    assert enf["allowed"] is False
    assert "strategy_status" in enf["hard_block_reason"]


def test_research_only_strategy_blocks_buy():
    enf = A.enforce_portfolio_constraints_impl(order_intent=_intent(strategy_id="S3_best_dp"))
    assert enf["allowed"] is False


def test_watchlist_only_strategy_blocks_buy():
    enf = A.enforce_portfolio_constraints_impl(order_intent=_intent(strategy_id="W2"))
    assert enf["allowed"] is False


# ── stale pack blocks ─────────────────────────────────────────────────────

def test_stale_council_hard_blocks_new_buy(monkeypatch):
    _patch_packs(monkeypatch, council=True)
    enf = A.enforce_portfolio_constraints_impl(order_intent=_intent())
    assert enf["allowed"] is False
    assert "stale_council_output" in enf["hard_block_reason"]


def test_stale_consensus_hard_blocks_new_buy(monkeypatch):
    _patch_packs(monkeypatch, consensus=True)
    enf = A.enforce_portfolio_constraints_impl(order_intent=_intent())
    assert enf["allowed"] is False
    assert "stale_or_missing_consensus_pack" in enf["hard_block_reason"]


def test_missing_research_pack_hard_blocks_new_buy(monkeypatch):
    _patch_packs(monkeypatch, research=True)
    enf = A.enforce_portfolio_constraints_impl(order_intent=_intent())
    assert enf["allowed"] is False
    assert "stale_or_missing_research_pack" in enf["hard_block_reason"]


def test_stale_manual_inputs_blocks(monkeypatch):
    _patch_packs(monkeypatch, manual=True)
    enf = A.enforce_portfolio_constraints_impl(order_intent=_intent())
    assert enf["allowed"] is False
    assert "stale_manual_inputs" in enf["hard_block_reason"]


def test_sell_intent_not_blocked_by_stale_packs(monkeypatch):
    _patch_packs(monkeypatch, council=True, consensus=True, research=True)
    sell = _intent(side="SELL", stop_price=110000)
    enf = A.enforce_portfolio_constraints_impl(order_intent=sell)
    r = enf.get("hard_block_reason", "") or ""
    assert "stale_council_output" not in r
    assert "stale_or_missing_consensus_pack" not in r
    assert "stale_or_missing_research_pack" not in r


# ── schema / sizing blocks ────────────────────────────────────────────────

def test_invalid_stop_distance_blocks_sizing():
    sizing = A.calculate_position_size(_intent(stop_price=110000))
    assert sizing["allowed"] is False
    assert sizing["invalid_reason"] in {"invalid_stop_distance"}


def test_adv_missing_blocks_sizing():
    sizing = A.calculate_position_size(_intent(adv50_vnd=0))
    assert sizing["allowed"] is False
    assert sizing["invalid_reason"] == "adv50_missing"


def test_invalid_account_equity_in_schema():
    from src.mcp_server.schemas import validate_order_intent

    valid, _, errs = validate_order_intent(_intent(account_equity=0))
    assert valid is False
    assert any("account_equity" in e for e in errs)
