from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional


class FillTiming(str, Enum):
    """When a fill is assumed to occur relative to the signal bar."""

    NEXT_BAR_OPEN = "next_bar_open"
    SAME_BAR_CLOSE_OPTIMISTIC = "same_bar_close_optimistic"


@dataclass(frozen=True)
class ExecutionConfig:
    """Centralized execution assumptions for research integrity."""

    entry_timing: FillTiming = FillTiming.NEXT_BAR_OPEN
    exit_timing: FillTiming = FillTiming.NEXT_BAR_OPEN
    fee_bps_per_side: float = 15.0
    slippage_bps_per_side: float = 5.0
    # Portfolio-level capacity proxy. Engines may ignore if not applicable.
    liquidity_participation_cap: Optional[float] = None  # e.g. 0.05 means 5% of ADTV
    # Optional entry/exit degradation (used by robustness layer)
    entry_delay_bars: int = 0  # 0 = normal (t+1). 1 = t+2, etc.
    exit_delay_bars: int = 0

    def fee_mult(self) -> float:
        return float(self.fee_bps_per_side) / 10_000.0

    def slip_mult(self) -> float:
        return float(self.slippage_bps_per_side) / 10_000.0


def apply_costs(price: float, side: str, fee_mult: float, slip_mult: float) -> float:
    """Apply fee+slippage to a raw price for a buy/sell fill."""
    if price is None:
        return price
    px = float(price)
    if side.lower() == "buy":
        return px * (1.0 + fee_mult + slip_mult)
    if side.lower() == "sell":
        return px * (1.0 - fee_mult - slip_mult)
    raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")


@dataclass(frozen=True)
class ExecutionAudit:
    engine: str
    research_safe_default: bool
    entry_timing: str
    exit_timing: str
    entry_delay_bars: int
    exit_delay_bars: int
    fee_bps_per_side: float
    slippage_bps_per_side: float
    liquidity_participation_cap: Optional[float]
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_execution_audit(
    *,
    engine: str,
    cfg: ExecutionConfig,
    research_safe_default: bool,
    notes: str = "",
) -> ExecutionAudit:
    return ExecutionAudit(
        engine=engine,
        research_safe_default=bool(research_safe_default),
        entry_timing=str(cfg.entry_timing.value),
        exit_timing=str(cfg.exit_timing.value),
        entry_delay_bars=int(cfg.entry_delay_bars),
        exit_delay_bars=int(cfg.exit_delay_bars),
        fee_bps_per_side=float(cfg.fee_bps_per_side),
        slippage_bps_per_side=float(cfg.slippage_bps_per_side),
        liquidity_participation_cap=cfg.liquidity_participation_cap,
        notes=notes or "",
    )


def execution_mode_label(cfg: ExecutionConfig) -> str:
    """Human-readable label used in audit logs."""
    base = f"entry={cfg.entry_timing.value},exit={cfg.exit_timing.value}"
    if cfg.entry_delay_bars or cfg.exit_delay_bars:
        base += f",delay(entry={cfg.entry_delay_bars},exit={cfg.exit_delay_bars})"
    base += f",fee_bps={cfg.fee_bps_per_side},slip_bps={cfg.slippage_bps_per_side}"
    if cfg.liquidity_participation_cap is not None:
        base += f",liq_cap={cfg.liquidity_participation_cap}"
    return base


def assert_research_safe(cfg: ExecutionConfig) -> None:
    """Fail fast if config is not research-safe."""
    if cfg.entry_timing != FillTiming.NEXT_BAR_OPEN:
        raise ValueError(f"Research-safe default requires entry_timing=NEXT_BAR_OPEN, got {cfg.entry_timing}")
    if cfg.exit_timing != FillTiming.NEXT_BAR_OPEN:
        raise ValueError(f"Research-safe default requires exit_timing=NEXT_BAR_OPEN, got {cfg.exit_timing}")
    if cfg.entry_delay_bars < 0 or cfg.exit_delay_bars < 0:
        raise ValueError("Delays must be >= 0")

