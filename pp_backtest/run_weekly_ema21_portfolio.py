from __future__ import annotations

"""
Research harness:
- Build weekly Pocket Pivot + EMA21/MA50 signals.
- Apply monthly point-in-time eligibility.
- Log candidate signals (basic) for later analysis.
- Run overlapping portfolio backtest with risk-based sizing.

This is the entry point for the multi-phase optimization pipeline.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

try:
    from pp_backtest.config import BacktestConfig
    from pp_backtest.data import fetch_ohlcv_fireant
    from pp_backtest.weekly_bars import daily_to_weekly
    from pp_backtest.signals_weekly import (
        weekly_pocket_pivot_signal,
        weekly_exit_ema21_ma50,
        sma,
        ema,
    )
    from pp_backtest.market_regime import add_book_regime_columns, weekly_regime_from_daily
    from pp_backtest.eligibility import get_global_eligibility
    from pp_backtest.portfolio_sim import PortfolioConfig, run_portfolio_backtest, DEFAULT_INITIAL_EQUITY_VND
except ImportError:
    from config import BacktestConfig
    from data import fetch_ohlcv_fireant
    from weekly_bars import daily_to_weekly
    from signals_weekly import (
        weekly_pocket_pivot_signal,
        weekly_exit_ema21_ma50,
        sma,
        ema,
    )
    from market_regime import add_book_regime_columns, weekly_regime_from_daily
    from eligibility import get_global_eligibility
    from portfolio_sim import PortfolioConfig, run_portfolio_backtest, DEFAULT_INITIAL_EQUITY_VND

# Path A config registry: config_name -> (ranking_mode, max_positions)
# champion = active default; challenger = research; baseline_old = deprecated
PATH_A_CONFIGS = {
    "champion": ("extension_first", 8),
    "challenger": ("simple_composite", 12),
    "baseline_old": ("current", 8),
}


def get_path_a_config(config_name: str) -> tuple[str, int]:
    """Resolve config_name to (ranking_mode, max_positions). Default: champion."""
    key = (config_name or "champion").strip().lower()
    if key not in PATH_A_CONFIGS:
        key = "champion"
    return PATH_A_CONFIGS[key]


def load_universe(path: Path) -> list[str]:
    txt = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in txt if ln.strip() and not ln.strip().startswith("#")]


def build_weekly_dfs(cfg: BacktestConfig, symbols: list[str]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    fetch = fetch_ohlcv_fireant
    # Market regime (VN30)
    try:
        market_daily = fetch("VN30", cfg.start, cfg.end)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception:
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])

    weekly_dfs: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            daily_df = fetch(sym, cfg.start, cfg.end)
        except Exception:
            continue
        wdf = daily_to_weekly(daily_df)
        if wdf.empty or len(wdf) < 11:
            continue
        c = wdf["close"].astype(float)
        wdf["ma10"] = sma(c, 10)
        wdf["ema21"] = ema(c, 21)
        wdf["weekly_pp"] = weekly_pocket_pivot_signal(wdf)
        wdf["exit_ma10"] = weekly_exit_ema21_ma50(wdf)
        # Merge regime
        wdf = wdf.merge(market_weekly_regime, on="date", how="left")
        wdf["regime_ftd"] = wdf["regime_ftd"].fillna(False)
        wdf["no_new_positions"] = wdf["no_new_positions"].fillna(False)
        weekly_dfs[sym] = wdf
    return weekly_dfs, market_weekly_regime


def run_weekly_period(
    start: str,
    end: str,
    symbols: list[str] | None = None,
    config_name: str = "champion",
) -> tuple[pd.DataFrame, dict]:
    """Run Path A (weekly) backtest for one period; returns (trades_df, stats). For parallel runner.
    config_name: champion (default), challenger, or baseline_old (deprecated)."""
    ranking_mode, max_positions = get_path_a_config(config_name)
    cfg = BacktestConfig()
    cfg.start = start
    cfg.end = end
    if symbols is None:
        universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
        if not universe_path.exists():
            universe_path = _REPO / "config" / "watchlist.txt"
        symbols = load_universe(universe_path)
    if not symbols:
        return pd.DataFrame(), {}
    weekly_dfs, _ = build_weekly_dfs(cfg, symbols)
    if not weekly_dfs:
        return pd.DataFrame(), {}
    try:
        eligibility = get_global_eligibility()
    except FileNotFoundError:
        from pp_backtest.eligibility import EligibilityMap
        rows = []
        for sym, wdf in weekly_dfs.items():
            wdf = wdf.copy()
            wdf["value"] = wdf["close"].astype(float) * wdf["volume"].astype(float)
            wdf["date"] = pd.to_datetime(wdf["date"])
            for i in range(len(wdf)):
                if i < 50:
                    continue
                row = wdf.iloc[i]
                dt = row["date"]
                tail50 = wdf.iloc[i - 50 : i]
                tail20 = wdf.iloc[i - 20 : i]
                adtv50 = float(tail50["value"].mean())
                adtv20 = float(tail20["value"].mean())
                rows.append({
                    "symbol": sym,
                    "month_start": dt,
                    "adtv20": adtv20,
                    "adtv50": adtv50,
                    "eligible_flag": adtv20 >= 2e9 and adtv50 >= 4e9,
                })
        eligibility = EligibilityMap(df=pd.DataFrame(rows))
    pconfig = PortfolioConfig(
        risk_per_trade=0.005,
        max_heat=0.04,
        max_positions=max_positions,
        max_symbol_weight=0.10,
        liquidity_participation_cap=0.05,
        initial_equity=DEFAULT_INITIAL_EQUITY_VND,
        fee_bps_per_side=15.0,
    )
    trades_df, stats = run_portfolio_backtest(weekly_dfs, pconfig, eligibility=eligibility, ranking_mode=ranking_mode)
    # Add trades_per_month for comparison
    if not trades_df.empty and "entry_date" in trades_df.columns:
        period_days = (pd.to_datetime(end) - pd.to_datetime(start)).days
        period_months = max(1, period_days / 30.0)
        stats["trades_per_month"] = len(trades_df) / period_months
    else:
        stats["trades_per_month"] = np.nan
    return trades_df, stats


def main(args: object | None = None) -> None:
    cfg = BacktestConfig()
    if args and getattr(args, "start", None):
        cfg.start = args.start
    if args and getattr(args, "end", None):
        cfg.end = args.end

    universe_path = Path(
        getattr(args, "universe", "config/universe_adv4bn_from_user.txt")
        if args
        else "config/universe_adv4bn_from_user.txt"
    )
    if not universe_path.is_absolute():
        universe_path = _REPO / universe_path
    symbols = load_universe(universe_path)
    config_name = getattr(args, "config", "champion") if args else "champion"
    print(f"[run_weekly_ema21_portfolio] config={config_name} start={cfg.start} end={cfg.end} universe={len(symbols)}")

    weekly_dfs, _ = build_weekly_dfs(cfg, symbols)
    if not weekly_dfs:
        print("No weekly data; aborting.")
        return

    try:
        eligibility = get_global_eligibility()
    except FileNotFoundError:
        # Fallback: build eligibility from weekly_dfs (trailing 20/50w value, eligible if adtv50 >= 4e9)
        from pp_backtest.eligibility import EligibilityMap
        rows = []
        for sym, wdf in weekly_dfs.items():
            wdf = wdf.copy()
            wdf["value"] = wdf["close"].astype(float) * wdf["volume"].astype(float)
            wdf["date"] = pd.to_datetime(wdf["date"])
            for i in range(len(wdf)):
                if i < 50:
                    continue
                row = wdf.iloc[i]
                dt = row["date"]
                tail50 = wdf.iloc[i - 50:i]
                tail20 = wdf.iloc[i - 20:i]
                adtv50 = float(tail50["value"].mean())
                adtv20 = float(tail20["value"].mean())
                eligible = adtv20 >= 2e9 and adtv50 >= 4e9
                rows.append({
                    "symbol": sym,
                    "month_start": dt,
                    "adtv20": adtv20,
                    "adtv50": adtv50,
                    "listed_flag": True,
                    "min_history_flag": True,
                    "active_flag": True,
                    "eligible_flag": eligible,
                })
        if rows:
            elig_df = pd.DataFrame(rows)
            eligibility = EligibilityMap(elig_df)
            print("[eligibility] using fallback from weekly_dfs (no monthly_universe_eligibility.csv)")
        else:
            eligibility = get_global_eligibility()

    # Run portfolio backtest (VND, 5% liquidity cap, fees 15 bps/side, regime gate)
    config_name = getattr(args, "config", "champion") if args else "champion"
    ranking_mode, max_positions = get_path_a_config(config_name)
    if getattr(args, "max_positions", None) is not None:
        max_positions = args.max_positions
    pconfig = PortfolioConfig(
        risk_per_trade=getattr(args, "risk_per_trade", 0.005) if args else 0.005,
        max_heat=0.04,
        max_positions=max_positions,
        max_symbol_weight=0.10,
        liquidity_participation_cap=0.05,
        initial_equity=DEFAULT_INITIAL_EQUITY_VND,
        fee_bps_per_side=15.0,
    )
    trades_df, stats = run_portfolio_backtest(weekly_dfs, pconfig, eligibility=eligibility, ranking_mode=ranking_mode)
    trades_path = _PP / "pp_weekly_ema21_portfolio_trades.csv"
    trades_df.to_csv(trades_path, index=False)
    log_path = _PP / "pp_portfolio_signal_log.csv"

    # Portfolio stats
    print("[portfolio_stats]")
    print(f"  CAGR={stats.get('cagr', np.nan):.2%} MDD={stats.get('mdd', np.nan):.2%} MAR={stats.get('mar', np.nan):.2f}")
    print(f"  n_trades={stats.get('n_trades', 0)} final_equity={stats.get('final_equity', 0):,.0f} VND")
    print(f"  avg_heat={stats.get('avg_heat', np.nan):.4f} avg_gross_exposure={stats.get('avg_gross_exposure', np.nan):.4f}")
    print("[skipped]")
    print(f"  skipped_ineligible={stats.get('skipped_ineligible', 0)} skipped_heat={stats.get('skipped_heat', 0)}")
    print(f"  skipped_max_positions={stats.get('skipped_max_positions', 0)} skipped_liquidity={stats.get('skipped_liquidity', 0)}")
    print(f"  skipped_regime_off={stats.get('skipped_regime_off', 0)} skipped_no_new_positions={stats.get('skipped_no_new_positions', 0)}")

    if not trades_df.empty and "ret" in trades_df.columns:
        top20_winners = trades_df.nlargest(20, "ret")[["symbol", "entry_date", "exit_date", "ret", "pnl"]]
        top20_losers = trades_df.nsmallest(20, "ret")[["symbol", "entry_date", "exit_date", "ret", "pnl"]]
        print("[top_20_winners]")
        print(top20_winners.to_string(index=False))
        print("[top_20_losers]")
        print(top20_losers.to_string(index=False))

    print(f"[portfolio] wrote trades: {len(trades_df)} -> {trades_path}")
    non_empty_trades = trades_path.exists() and trades_path.stat().st_size > 0
    non_empty_log = log_path.exists() and log_path.stat().st_size > 0
    print(f"  pp_weekly_ema21_portfolio_trades.csv non-empty: {non_empty_trades}")
    print(f"  pp_portfolio_signal_log.csv non-empty: {non_empty_log}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Path A weekly PP portfolio. Default config: champion (extension_first, 8).")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--universe", default="config/universe_adv4bn_from_user.txt")
    p.add_argument("--config", default="champion", choices=["champion", "challenger", "baseline_old"],
                    help="champion (default), challenger, or baseline_old (deprecated)")
    p.add_argument("--risk-per-trade", dest="risk_per_trade", type=float, default=0.005)
    p.add_argument("--max-positions", dest="max_positions", type=int, default=None,
                    help="Override max_positions; if unset, uses value from --config")
    args = p.parse_args()
    main(args=args)

