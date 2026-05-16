"""Unit tests for src.mcp_server.decision_gates policy helpers."""
from __future__ import annotations

from src.mcp_server.decision_gates import (
    collect_stale_manual_buy_blocks,
    council_blocks_new_exposure,
    evaluate_manual_buy_gates,
    is_new_buy_exposure,
)


def test_is_new_buy_exposure_order_intent():
    assert is_new_buy_exposure(order_intent={"side": "BUY"}) is True
    assert is_new_buy_exposure(order_intent={"side": "SELL"}) is False


def test_is_new_buy_exposure_legacy_ticker():
    assert is_new_buy_exposure(ticker="FPT", proposed_size_pct=1.0) is True
    assert is_new_buy_exposure(ticker="FPT", proposed_size_pct=0.0) is False


def test_council_blocks_new_exposure_phrase():
    assert council_blocks_new_exposure({"decision_stance": "no new buys this week"}) is True
    assert council_blocks_new_exposure({"decision_stance": "selective adds allowed"}) is False


def test_stale_packs_block_buy_only():
    checks: list = []
    blocks = collect_stale_manual_buy_blocks(
        new_buy=True,
        council={"stale": True, "decision_stance": "neutral"},
        manual={
            "manual_inputs": {"stale": False},
            "consensus_pack": {"stale": True, "required_for_council": True},
            "research_engine_pack": {"stale": True, "required_for_council": True},
        },
        checks=checks,
    )
    assert "stale_council_output" in blocks
    assert "stale_or_missing_consensus_pack" in blocks
    assert "stale_or_missing_research_pack" in blocks


def test_stale_packs_do_not_block_when_not_new_buy():
    checks: list = []
    blocks = collect_stale_manual_buy_blocks(
        new_buy=False,
        council={"stale": True, "decision_stance": "neutral"},
        manual={
            "consensus_pack": {"stale": True, "required_for_council": True},
            "research_engine_pack": {"stale": True, "required_for_council": True},
        },
        checks=checks,
    )
    assert blocks == []


def test_evaluate_manual_buy_gates_tuple():
    checks: list = []
    new_buy, blocks = evaluate_manual_buy_gates(
        order_intent={"side": "BUY"},
        council={"stale": False, "decision_stance": "ok"},
        manual={"consensus_pack": {"stale": False, "required_for_council": True}},
        checks=checks,
    )
    assert new_buy is True
    assert blocks == []
