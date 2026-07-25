"""Round-trip cost helpers for B0_CLEAN."""

from __future__ import annotations

COST_BPS = (30, 45, 60)
PRIMARY_COST_BP = 45


def apply_round_trip_cost(gross: float, cost_bp: int) -> float:
    return float(gross) - float(cost_bp) / 10_000.0


def cost_grid(gross: float) -> dict[str, float]:
    return {f"net_{bp}bp": apply_round_trip_cost(gross, bp) for bp in COST_BPS}
