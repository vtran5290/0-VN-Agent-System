# pp_backtest/run_weekly.py — Weekly backtest: Weekly PP, 3WT, market regime always on (Gil/Kacher)
from __future__ import annotations
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
        three_weeks_tight_breakout_signal,
        weekly_exit_ma10,
        weekly_market_dd_series,
    )
    from pp_backtest.market_regime import add_book_regime_columns, weekly_regime_from_daily
except ImportError:
    from config import BacktestConfig
    from data import fetch_ohlcv_fireant, fetch_ohlcv_vnstock
    from weekly_bars import daily_to_weekly
    from signals_weekly import (
        weekly_pocket_pivot_signal,
        three_weeks_tight_breakout_signal,
        weekly_exit_ma10,
        weekly_market_dd_series,
    )
    from market_regime import add_book_regime_columns, weekly_regime_from_daily


def load_tickers(watchlist_path: Path | None = None) -> list[str]:
    if watchlist_path is not None:
        p = watchlist_path if watchlist_path.is_absolute() else _REPO / watchlist_path
        if p.exists():
            lines = p.read_text(encoding="utf-8").strip().splitlines()
            return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    p = _REPO / "config" / "watchlist_80.txt"
    if p.exists():
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    p = _REPO / "config" / "watchlist.txt"
    if p.exists():
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    return ["SSI", "VCI", "MBB", "STB", "VNM"]


FEE_BPS = 30
MARKET_DD_WEEKS_THRESHOLD = 3
MARKET_DD_LB_WEEKS = 10


# Market regime modes for ablation (pre-registered, no curve-fit)
# 0 = no filter (alpha tự thân); 1 = trend only (FTD-style); 2 = trend + dist stop-buy (Book)
MARKET_MODE_OFF = 0
MARKET_MODE_TREND_ONLY = 1
MARKET_MODE_BOOK = 2


def run_weekly_backtest(
    weekly_dfs: dict[str, pd.DataFrame],
    market_weekly_regime: pd.DataFrame,
    entry_weekly_pp: bool = True,
    entry_3wt: bool = False,
    fee_bps: float = FEE_BPS,
    market_mode: int = MARKET_MODE_BOOK,
) -> tuple[pd.DataFrame, dict]:
    """
    weekly_dfs: symbol -> weekly DataFrame with date, open, high, low, close, volume,
      weekly_pp, [three_weeks_tight_breakout], exit_ma10, mkt_dd_weeks, regime_ftd, no_new_positions.
    market_weekly_regime: date, regime_ftd, no_new_positions (from weekly_regime_from_daily).
    market_mode: 0 = no filter, 1 = regime_ftd only, 2 = regime_ftd + no_new_positions (Book).
    Max 1 trade per symbol per week; entry at next week open, exit at week close when exit signal.
    """
    all_dates = sorted(set().union(*(set(w["date"].astype(str)) for w in weekly_dfs.values())))
    if not all_dates:
        return pd.DataFrame(), {"n_trades": 0, "pf": np.nan, "tail5": np.nan, "mdd": np.nan}
    ledger_rows = []
    positions = {}  # symbol -> {entry_week_idx, entry_date, entry_open, entry_week_close}

    for i, dt in enumerate(all_dates):
        # Merge regime for this week
        regime_row = market_weekly_regime[market_weekly_regime["date"].astype(str) == dt]
        regime_ftd = regime_row["regime_ftd"].iloc[0] if len(regime_row) and regime_row["regime_ftd"].iloc[0] else False
        no_new = regime_row["no_new_positions"].iloc[0] if len(regime_row) and regime_row["no_new_positions"].iloc[0] else False
        skip_for_no_new = (market_mode == MARKET_MODE_BOOK) and no_new
        skip_for_trend = (market_mode >= MARKET_MODE_TREND_ONLY) and (not regime_ftd)

        # Exit first: check each position for exit signal this week
        for sym in list(positions.keys()):
            wdf = weekly_dfs.get(sym)
            if wdf is None:
                continue
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]
            exit_ma10 = row.get("exit_ma10", False)
            mkt_dd = row.get("mkt_dd_weeks", 0) >= MARKET_DD_WEEKS_THRESHOLD
            if exit_ma10 or mkt_dd:
                pos = positions.pop(sym)
                exit_close = float(row["close"])
                entry_open = pos["entry_open"]
                ret = (exit_close - entry_open) / entry_open - 2 * (fee_bps / 1e4)
                ledger_rows.append({
                    "symbol": sym, "entry_date": pos["entry_date"], "exit_date": dt,
                    "hold_weeks": i - pos["entry_week_idx"], "ret": ret,
                    "exit_reason": "MA10" if exit_ma10 else "MARKET_DD",
                })

        # Entry: at most one new position per symbol per week when regime allows; fill at next week open
        if skip_for_no_new:
            continue
        next_dt = all_dates[i + 1] if i + 1 < len(all_dates) else None
        for sym, wdf in weekly_dfs.items():
            if sym in positions:
                continue
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]
            if skip_for_trend:
                continue
            entry_sig = False
            if entry_weekly_pp and row.get("weekly_pp", False):
                entry_sig = True
            if entry_3wt and row.get("three_weeks_tight_breakout", False):
                entry_sig = True
            if not entry_sig:
                continue
            if next_dt is None:
                continue
            next_row = wdf[wdf["date"].astype(str) == next_dt]
            if next_row.empty:
                continue
            next_open = float(next_row["open"].iloc[0])
            positions[sym] = {"entry_week_idx": i + 1, "entry_date": next_dt, "entry_open": next_open}

    # Force exit remaining at last date
    last_dt = all_dates[-1]
    for sym, pos in list(positions.items()):
        wdf = weekly_dfs.get(sym)
        if wdf is not None and not wdf.empty:
            last_row = wdf[wdf["date"].astype(str) == last_dt]
            exit_close = float(last_row["close"].iloc[0]) if not last_row.empty else float(wdf.iloc[-1]["close"])
        else:
            exit_close = pos["entry_open"]
        ret = (exit_close - pos["entry_open"]) / pos["entry_open"] - 2 * (fee_bps / 1e4)
        ledger_rows.append({
            "symbol": sym, "entry_date": pos["entry_date"], "exit_date": last_dt,
            "hold_weeks": len(all_dates) - 1 - pos["entry_week_idx"], "ret": ret, "exit_reason": "EOD",
        })

    ledger = pd.DataFrame(ledger_rows)
    if ledger.empty:
        return ledger, {"n_trades": 0, "pf": np.nan, "tail5": np.nan, "mdd": np.nan, "avg_ret": np.nan, "win_rate": np.nan}
    ret = ledger["ret"].astype(float).values
    wins = ret[ret > 0]
    losses = ret[ret <= 0]
    pf = (wins.sum() / (-losses.sum())) if len(losses) and losses.sum() < 0 and len(wins) else np.nan
    cum = np.cumprod(1.0 + ret) - 1.0
    peak = np.maximum.accumulate(1.0 + cum)
    mdd = float((((1.0 + cum) / peak) - 1.0).min()) if len(cum) else np.nan
    tail5 = float(np.nanpercentile(ret, 5))
    return ledger, {
        "n_trades": len(ledger),
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
    entry_weekly_pp = getattr(args, "entry_weekly_pp", True) if args else True
    entry_3wt = getattr(args, "entry_3wt", False) if args else False
    fee_bps = float(getattr(args, "fee_bps", FEE_BPS)) if args else FEE_BPS
    market_mode = int(getattr(args, "market_mode", MARKET_MODE_BOOK)) if args else MARKET_MODE_BOOK
    fetch = fetch_ohlcv_vnstock if use_vnstock else fetch_ohlcv_fireant
    mode_label = {0: "m0_no_filter", 1: "m1_trend_only", 2: "m2_book"}.get(market_mode, f"m{market_mode}")

    print(f"[run_weekly] start={cfg.start} end={cfg.end} symbols={len(tickers)} entry_weekly_pp={entry_weekly_pp} entry_3wt={entry_3wt} fee_bps={fee_bps} market_mode={market_mode} ({mode_label})")

    # Market: VN30 daily → book regime → weekly regime
    market_daily = None
    try:
        market_daily = fetch("VN30", cfg.start, cfg.end)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception as e:
        print(f"[market] VN30 failed: {e}. Proceeding without regime (all entries allowed).")
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])

    weekly_dfs = {}
    for sym in tickers:
        try:
            daily_df = fetch(sym, cfg.start, cfg.end)
        except Exception as e:
            print(f"[skip] {sym}: {e}")
            continue
        wdf = daily_to_weekly(daily_df)
        if wdf.empty or len(wdf) < 11:
            continue
        wdf["weekly_pp"] = weekly_pocket_pivot_signal(wdf)
        wdf["three_weeks_tight_breakout"] = three_weeks_tight_breakout_signal(wdf, max_range_pct=0.03)
        wdf["exit_ma10"] = weekly_exit_ma10(wdf)
        wdf["mkt_dd_weeks"] = weekly_market_dd_series(wdf, lb_weeks=MARKET_DD_LB_WEEKS)
        # Merge regime by date
        wdf = wdf.merge(market_weekly_regime, on="date", how="left")
        wdf["regime_ftd"] = wdf["regime_ftd"].fillna(False)
        wdf["no_new_positions"] = wdf["no_new_positions"].fillna(False)
        weekly_dfs[sym] = wdf

    if not weekly_dfs:
        print("No weekly data. Check date range and watchlist.")
        return

    ledger, agg = run_weekly_backtest(weekly_dfs, market_weekly_regime, entry_weekly_pp=entry_weekly_pp, entry_3wt=entry_3wt, fee_bps=fee_bps, market_mode=market_mode)
    print(f"[aggregate] trades={agg['n_trades']} PF={agg['pf']:.4f} tail5={agg['tail5']:.2%} max_drawdown={agg['mdd']:.2%} avg_ret={agg['avg_ret']:.2%} win_rate={agg['win_rate']:.2%}")

    ledger_path = _PP / "pp_weekly_ledger.csv"
    ledger.to_csv(ledger_path, index=False)
    print(f"Wrote: {ledger_path}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--vnstock", action="store_true")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--watchlist", default=None, help="e.g. config/watchlist_80.txt")
    p.add_argument("--entry-weekly-pp", action="store_true", default=True, help="Entry = Weekly Pocket Pivot (default on)")
    p.add_argument("--no-entry-weekly-pp", action="store_false", dest="entry_weekly_pp")
    p.add_argument("--entry-3wt", action="store_true", help="Also entry on 3-weeks-tight breakout")
    p.add_argument("--fee-bps", type=float, default=FEE_BPS)
    p.add_argument("--market-mode", type=int, default=MARKET_MODE_BOOK, choices=(0, 1, 2), help="0=no filter, 1=trend only (FTD-style), 2=trend+dist stop-buy (Book). Ablation: run C1/C2 with m0/m1/m2.")
    p.add_argument("--symbols", nargs="+", default=None, help="Optional: only these symbols (subset of watchlist or exact list)")
    args = p.parse_args()
    main(args=args)
