"""Central BUY-exposure and stale-input gate policy for MCP enforcement.

Used by enforce_portfolio_constraints_impl (and indirectly by propose_order_intent /
simulate_paper_order via that enforcer). Keeps stale-pack / council rules in one place.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def is_new_buy_exposure(
    order_intent: Optional[Dict[str, Any]] = None,
    ticker: str = "",
    proposed_size_pct: float = 0.0,
) -> bool:
    """True when the call represents adding new long exposure (BUY intent or legacy ticker add)."""
    if order_intent and str(order_intent.get("side", "")).upper() == "BUY":
        return True
    if ticker and proposed_size_pct > 0:
        return True
    return False


def council_blocks_new_exposure(council: Dict[str, Any]) -> bool:
    stance = str(council.get("decision_stance", "")).lower()
    return "no new" in stance or "no_new" in stance


def collect_stale_manual_buy_blocks(
    *,
    new_buy: bool,
    council: Dict[str, Any],
    manual: Dict[str, Any],
    checks: List[Dict[str, Any]],
) -> List[str]:
    """Return hard-block reason codes for stale council / manual packs on new BUY only."""
    hard_blocks: List[str] = []

    if council.get("stale"):
        checks.append({"check": "council_output", "passed": False, "warn": "stale"})
        if new_buy:
            hard_blocks.append("stale_council_output")

    if council_blocks_new_exposure(council):
        hard_blocks.append("council_blocks_new_exposure")

    if manual.get("manual_inputs", {}).get("stale"):
        hard_blocks.append("stale_manual_inputs")

    consensus = manual.get("consensus_pack", {})
    if consensus.get("stale"):
        checks.append({"check": "consensus_pack", "passed": False, "warn": "stale_or_missing"})
        if new_buy and consensus.get("required_for_council"):
            hard_blocks.append("stale_or_missing_consensus_pack")

    research = manual.get("research_engine_pack", {})
    if research.get("stale"):
        checks.append({"check": "research_engine_pack", "passed": False, "warn": "stale_or_missing"})
        if new_buy and research.get("required_for_council"):
            hard_blocks.append("stale_or_missing_research_pack")

    return hard_blocks


def evaluate_manual_buy_gates(
    *,
    order_intent: Optional[Dict[str, Any]] = None,
    ticker: str = "",
    proposed_size_pct: float = 0.0,
    council: Dict[str, Any],
    manual: Dict[str, Any],
    checks: List[Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    """Convenience: compute new_buy flag and return (new_buy, hard_block_reasons)."""
    new_buy = is_new_buy_exposure(order_intent, ticker, proposed_size_pct)
    blocks = collect_stale_manual_buy_blocks(
        new_buy=new_buy,
        council=council,
        manual=manual,
        checks=checks,
    )
    return new_buy, blocks
