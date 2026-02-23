# pp_backtest/config.py — Backtest params (Pocket Pivot + Sell v4)
from dataclasses import dataclass

@dataclass
class BacktestConfig:
    start: str = "2018-01-01"
    end: str = "2026-02-21"
    fee_bps: float = 15.0          # 0.15% per side
    slippage_bps: float = 5.0      # 0.05% per side
    allow_short: bool = False
    use_adjusted: bool = True
    # VN T+2.5 = trading days (bars), not calendar days. min_hold_bars=3 enforces realistic liquidity (pre-registered, no tune)
    min_hold_bars: int = 0         # 0 = current (US-style); 3 = baseline_vn_realistic (bar count)

@dataclass
class PocketPivotParams:
    vol_lookback: int = 10
    ma_touch_tol_pct: float = 0.30 / 100.0
    slope_bars: int = 3
    slope_tol_pct: float = 0.10 / 100.0

@dataclass
class SellParams:
    enable_ma20_tier: bool = True
    ugly_atr_mult: float = 1.20
    ugly_closepos: float = 0.25
    heavy_vol_x_ma50: float = 1.50
    ride_bars_10: int = 35
    ride_tol_10: float = 1.0 / 100.0
    ride_bars_20: int = 35
    ride_tol_20: float = 1.5 / 100.0
    linger_bars_50: int = 2
    porosity_50: float = 2.0 / 100.0
    # SOFT_SELL: require N consecutive closes below tier MA before exit (Day1/Day2 branch only)
    # confirmation_scope is always tier_ma (MA10 for tier3, MA20 for tier2, MA50 for tier1)
    confirmation_closes: int = 1  # 1 = baseline (current); 2 = SOFT_SELL preset
