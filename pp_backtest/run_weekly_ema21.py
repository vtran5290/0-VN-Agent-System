from __future__ import annotations
"""
Weekly backtest variant:
- Entry: Gil weekly Pocket Pivot, gated by EMA21_week > MA50_week (trend-on filter).
- Exit: close < EMA21_week OR close < MA50_week OR EMA21_week cross down MA50_week.
- Market regime: same as run_weekly (VN30 FTD/no_new_positions), configurable via market_mode.
- Outputs: standard aggregate stats + sub-horizon slices for last 13/26/52 weeks (by entry date).
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
    from pp_backtest.data import fetch_ohlcv_fireant, fetch_ohlcv_vnstock
    from pp_backtest.weekly_bars import daily_to_weekly
    from pp_backtest.signals_weekly import (
        weekly_pocket_pivot_signal,
        weekly_exit_ema21_ma50,
        ema,
        sma,
    )
    from pp_backtest.market_regime import add_book_regime_columns, weekly_regime_from_daily
    from pp_backtest.run_weekly import (
        run_weekly_backtest,
        load_tickers,
        MARKET_MODE_BOOK,
        MARKET_MODE_OFF,
        MARKET_MODE_TREND_ONLY,
    )
except ImportError:
    from config import BacktestConfig
    from data import fetch_ohlcv_fireant, fetch_ohlcv_vnstock
    from weekly_bars import daily_to_weekly
    from signals_weekly import (
        weekly_pocket_pivot_signal,
        weekly_exit_ema21_ma50,
        ema,
        sma,
    )
    from market_regime import add_book_regime_columns, weekly_regime_from_daily
    from run_weekly import (
        run_weekly_backtest,
        load_tickers,
        MARKET_MODE_BOOK,
        MARKET_MODE_OFF,
        MARKET_MODE_TREND_ONLY,
    )


FEE_BPS_DEFAULT = 30


def _compute_ema21_ma50_gate(wdf: pd.DataFrame) -> pd.Series:
    c = wdf["close"].astype(float)
    ema21 = ema(c, 21)
    ma50 = sma(c, 50)
    return (ema21 > ma50).fillna(False)


def summarize_by_horizon(ledger: pd.DataFrame, weeks: int) -> dict:
    if ledger.empty:
        return {
            "weeks": weeks,
            "n_trades": 0,
            "pf": np.nan,
            "tail5": np.nan,
            "mdd": np.nan,
            "avg_ret": np.nan,
            "win_rate": np.nan,
        }
    df = ledger.copy()
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    max_dt = df["entry_date"].max()
    cutoff = max_dt - pd.Timedelta(days=7 * weeks)
    sub = df[df["entry_date"] >= cutoff]
    if sub.empty:
        return {
            "weeks": weeks,
            "n_trades": 0,
            "pf": np.nan,
            "tail5": np.nan,
            "mdd": np.nan,
            "avg_ret": np.nan,
            "win_rate": np.nan,
        }
    ret = sub["ret"].astype(float).values
    wins = ret[ret > 0]
    losses = ret[ret <= 0]
    pf = (wins.sum() / (-losses.sum())) if len(losses) and losses.sum() < 0 and len(wins) else np.nan
    cum = np.cumprod(1.0 + ret) - 1.0
    peak = np.maximum.accumulate(1.0 + cum)
    mdd = float((((1.0 + cum) / peak) - 1.0).min()) if len(cum) else np.nan
    tail5 = float(np.nanpercentile(ret, 5))
    return {
        "weeks": weeks,
        "n_trades": len(sub),
        "pf": pf,
        "tail5": tail5,
        "mdd": mdd,
        "avg_ret": float(ret.mean()),
        "win_rate": float((ret > 0).mean()),
    }


def main(args: object = None):
    cfg = BacktestConfig()
    if args and getattr(args, "start", None):
        cfg.start = args.start
    if args and getattr(args, "end", None):
        cfg.end = args.end
    use_vnstock = getattr(args, "vnstock", False) if args else False
    watchlist_path = Path(getattr(args, "watchlist", None)) if args and getattr(args, "watchlist", None) else None
    tickers = load_tickers(watchlist_path)
    if args and getattr(args, "symbols", None):
        wanted = {s.strip().upper() for s in args.symbols if s.strip()}
        tickers = [t for t in tickers if t.strip().upper() in wanted] or list(wanted)
    fee_bps = float(getattr(args, "fee_bps", FEE_BPS_DEFAULT)) if args else FEE_BPS_DEFAULT
    market_mode = int(getattr(args, "market_mode", MARKET_MODE_BOOK)) if args else MARKET_MODE_BOOK
    fetch = fetch_ohlcv_vnstock if use_vnstock else fetch_ohlcv_fireant
    mode_label = {
        MARKET_MODE_OFF: "m0_no_filter",
        MARKET_MODE_TREND_ONLY: "m1_trend_only",
        MARKET_MODE_BOOK: "m2_book",
    }.get(market_mode, f"m{market_mode}")

    print(
        f"[run_weekly_ema21] start={cfg.start} end={cfg.end} symbols={len(tickers)} "
        f"fee_bps={fee_bps} market_mode={market_mode} ({mode_label})"
    )

    # Market: VN30 daily → book regime → weekly regime
    try:
        market_daily = fetch("VN30", cfg.start, cfg.end)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception as e:
        print(f"[market] VN30 failed: {e}. Proceeding without regime (all entries allowed).")
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])

    weekly_dfs: dict[str, pd.DataFrame] = {}
    for sym in tickers:
        try:
            daily_df = fetch(sym, cfg.start, cfg.end)
        except Exception as e:
            print(f"[skip] {sym}: {e}")
            continue
        wdf = daily_to_weekly(daily_df)
        if wdf.empty or len(wdf) < 11:
            continue

        # Base pocket pivot condition (weekly, Gil/Kacher).
        wdf["weekly_pp"] = weekly_pocket_pivot_signal(wdf)

        # Trend gate: EMA21_week > MA50_week (after cross up, condition remains true).
        ema21_gt_ma50 = _compute_ema21_ma50_gate(wdf)
        wdf["weekly_pp"] = wdf["weekly_pp"] & ema21_gt_ma50

        # Exit: EMA21/MA50 violation or EMA21 cross down MA50.
        wdf["exit_ma10"] = weekly_exit_ema21_ma50(wdf)

        # Market distribution weeks + regime merge (same as baseline).
        wdf = wdf.merge(market_weekly_regime, on="date", how="left")
        wdf["regime_ftd"] = wdf["regime_ftd"].fillna(False)
        wdf["no_new_positions"] = wdf["no_new_positions"].fillna(False)
        weekly_dfs[sym] = wdf

    if not weekly_dfs:
        print("No weekly data. Check date range and watchlist.")
        return

    ledger, agg = run_weekly_backtest(
        weekly_dfs,
        market_weekly_regime,
        entry_weekly_pp=True,
        entry_3wt=False,
        fee_bps=fee_bps,
        market_mode=market_mode,
    )
    print(
        "[aggregate_all] trades={n_trades} PF={pf:.4f} tail5={tail5:.2%} "
        "max_drawdown={mdd:.2%} avg_ret={avg_ret:.2%} win_rate={win_rate:.2%}".format(**agg)
    )

    # Horizon slices by entry date: last 13/26/52 weeks
    for w in (13, 26, 52):
        sub_stats = summarize_by_horizon(ledger, weeks=w)
        print(
            "[horizon_{weeks}w] trades={n_trades} PF={pf:.4f} tail5={tail5:.2%} "
            "max_drawdown={mdd:.2%} avg_ret={avg_ret:.2%} win_rate={win_rate:.2%}".format(**sub_stats)
        )

    ledger_path = _PP / "pp_weekly_ema21_ledger.csv"
    ledger.to_csv(ledger_path, index=False)
    print(f"Wrote: {ledger_path}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--vnstock", action="store_true")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--watchlist", default=None, help="e.g. config/watchlist_80.txt")
    p.add_argument("--fee-bps", type=float, default=FEE_BPS_DEFAULT)
    p.add_argument(
        "--market-mode",
        type=int,
        default=MARKET_MODE_BOOK,
        choices=(MARKET_MODE_OFF, MARKET_MODE_TREND_ONLY, MARKET_MODE_BOOK),
        help="0=no filter, 1=trend only (FTD-style), 2=trend+dist stop-buy (Book).",
    )
    p.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Optional: only these symbols (subset of watchlist or exact list)",
    )
    args = p.parse_args()
    main(args=args)

