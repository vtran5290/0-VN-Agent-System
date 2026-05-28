from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ContextMode(str, Enum):
    OHLCV_ONLY = "OHLCV_ONLY"
    PIT_MONTHLY_CONTEXT = "PIT_MONTHLY_CONTEXT"
    SYNTHETIC_APR2026_CONTEXT_ONLY_NOT_EMPIRICAL = "SYNTHETIC_APR2026_CONTEXT_ONLY_NOT_EMPIRICAL"

    @classmethod
    def from_cli(cls, value: str) -> "ContextMode":
        key = (value or "").strip().lower()
        mapping = {
            "ohlcv_only": cls.OHLCV_ONLY,
            "pit_monthly_context": cls.PIT_MONTHLY_CONTEXT,
            "synthetic_apr2026_context_only_not_empirical": cls.SYNTHETIC_APR2026_CONTEXT_ONLY_NOT_EMPIRICAL,
            "synthetic": cls.SYNTHETIC_APR2026_CONTEXT_ONLY_NOT_EMPIRICAL,
        }
        if key not in mapping:
            raise ValueError(f"Unsupported context mode: {value}")
        return mapping[key]


@dataclass(frozen=True)
class VinPolicy:
    exclude_symbols: tuple[str, ...] = ("VIC", "VHM", "VRE")
    vpl_min_bars_required: int = 252
