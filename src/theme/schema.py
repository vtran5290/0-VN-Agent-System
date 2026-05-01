# src/theme/schema.py — Strict schema and enums for ThemePack config
from __future__ import annotations

from typing import Literal

# Lane enums (must match config)
LANE_GRID_EPC = "GRID_EPC"
LANE_GRID_EQUIP = "GRID_EQUIP"
LANE_POWER_GEN = "POWER_GEN"
LANE_INDUSTRIAL_PARK = "INDUSTRIAL_PARK"
LANE_DATA_CENTER_REAL = "DATA_CENTER_REAL"
LANE_MATERIALS = "MATERIALS"

LANES: tuple[str, ...] = (
    LANE_GRID_EPC,
    LANE_GRID_EQUIP,
    LANE_POWER_GEN,
    LANE_INDUSTRIAL_PARK,
    LANE_DATA_CENTER_REAL,
    LANE_MATERIALS,
)

MISSING_POLICY_NEUTRAL = "neutral"
MISSING_POLICY_STRICT = "strict"
MissingPolicy = Literal["neutral", "strict"]

COMPONENT_Q = "Q"
COMPONENT_R = "R"
COMPONENT_T = "T"
COMPONENT_V = "V"
COMPONENT_M = "M"
COMPONENTS: tuple[str, ...] = ("Q", "R", "T", "V", "M")

TIER1 = "tier1"
TIER2 = "tier2"
TIER3 = "tier3"
TIERS: tuple[str, ...] = (TIER1, TIER2, TIER3)

FLAG_WEAK_INTEREST_COVER = "weak_interest_cover"
FLAG_HIGH_LEVERAGE = "high_leverage"
FLAG_WC_TRAP = "wc_trap"


def validate_lane(lane: str) -> str:
    if lane not in LANES:
        raise ValueError(f"Invalid lane: {lane}. Must be one of {LANES}")
    return lane


def validate_missing_policy(policy: str) -> str:
    if policy not in (MISSING_POLICY_NEUTRAL, MISSING_POLICY_STRICT):
        raise ValueError(f"Invalid missing_policy: {policy}")
    return policy
