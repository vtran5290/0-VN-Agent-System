"""ICE-style DXY reconstruction from 6 FX rates (derived, not licensed ICE print)."""
from __future__ import annotations

import pytest

from src.intake.dxy_reconstructed import ICE_DXY_CONSTANT, compute_dxy_from_fx_rates


def test_ice_constant_matches_public_methodology() -> None:
    assert ICE_DXY_CONSTANT == 50.14348112


def test_compute_dxy_positive_and_order_of_magnitude() -> None:
    # Illustrative spot snapshot (not a claim vs official ICE close)
    v = compute_dxy_from_fx_rates(
        eurusd=1.08,
        usdjpy=150.0,
        gbpusd=1.27,
        usdcad=1.35,
        usdsek=10.5,
        usdchf=0.88,
    )
    assert 80 < v < 130


def test_compute_dxy_rejects_non_positive() -> None:
    with pytest.raises(ValueError, match="invalid_fx_rate"):
        compute_dxy_from_fx_rates(
            eurusd=0.0,
            usdjpy=150.0,
            gbpusd=1.27,
            usdcad=1.35,
            usdsek=10.5,
            usdchf=0.88,
        )
