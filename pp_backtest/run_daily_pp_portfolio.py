"""
Path B: true DAILY Pocket Pivot portfolio backtest.

- Daily FireAnt OHLCV -> daily PP signal (signals.pocket_pivot).
- Trend gate: EMA21_daily > MA50_daily.
- Exit: close < EMA21 or close < MA50 or EMA21 crosses below MA50 (next day open).
- Entry: PP + trend gate + regime_ftd, at next day open.
- Same risk framework as Path A: VND, fees 15 bps/side, max_heat, max_positions,
  liquidity cap, PIT eligibility, regime gate.
"""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

try:
    from pp_backtest.config import BacktestConfig, PocketPivotParams
    from pp_backtest.data import fetch_ohlcv_fireant
    from pp_backtest.signals import pocket_pivot, sma
    from pp_backtest.signals_weekly import ema
    from pp_backtest.market_regime import add_book_regime_columns
    from pp_backtest.eligibility import get_global_eligibility, EligibilityMap
except ImportError:
    from config import BacktestConfig, PocketPivotParams
    from data import fetch_ohlcv_fireant
    from signals import pocket_pivot, sma
    from signals_weekly import ema
    from market_regime import add_book_regime_columns
    from eligibility import get_global_eligibility, EligibilityMap

DEFAULT_INITIAL_EQUITY_VND = 1_000_000_000


@dataclass
class DailyPortfolioConfig:
    risk_per_trade: float = 0.005
    max_heat: float = 0.04
    max_positions: int = 8
    max_symbol_weight: float = 0.10
    liquidity_participation_cap: float = 0.05
    initial_equity: float = DEFAULT_INITIAL_EQUITY_VND
    fee_bps_per_side: float = 15.0


def _daily_exit_signal(df: pd.DataFrame) -> pd.Series:
    """Exit when close < EMA21 or close < MA50 or EMA21 crosses below MA50."""
    c = df["close"].astype(float)
    ema21 = df["ema21"] if "ema21" in df.columns else ema(c, 21)
    ma50 = df["ma50"] if "ma50" in df.columns else sma(c, 50)
    violate_ema21 = c < ema21
    violate_ma50 = c < ma50
    ema21_below = ema21 < ma50
    ema21_was_above = ema21.shift(1) >= ma50.shift(1)
    cross_down = ema21_below & ema21_was_above
    return (violate_ema21 | violate_ma50 | cross_down).fillna(False)


def _load_universe(path: Path) -> list[str]:
    txt = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in txt if ln.strip() and not ln.strip().startswith("#")]


def build_daily_dfs(
    start: str,
    end: str,
    symbols: list[str],
    market_daily: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Build per-symbol daily DataFrames with pp, ema21, ma50, exit_signal, regime."""
    regime = market_daily[["date", "regime_ftd", "no_new_positions"]].copy()
    regime["date"] = pd.to_datetime(regime["date"]).dt.normalize()

    daily_dfs: dict[str, pd.DataFrame] = {}
    pp_params = PocketPivotParams()
    for sym in symbols:
        try:
            df = fetch_ohlcv_fireant(sym, start, end)
        except Exception:
            continue
        if df is None or df.empty or len(df) < 51:
            continue
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df = pocket_pivot(df, pp_params)
        c = df["close"].astype(float)
        df["ema21"] = ema(c, 21)
        df["exit_signal"] = _daily_exit_signal(df)
        df = df.merge(regime, on="date", how="left")
        df["regime_ftd"] = df["regime_ftd"].fillna(False)
        df["no_new_positions"] = df["no_new_positions"].fillna(False)
        daily_dfs[sym] = df
    return daily_dfs


def _compute_stop_daily(row: pd.Series) -> float:
    close = float(row["close"])
    low = float(row["low"])
    ma10 = float(row.get("ma10", np.nan))
    ema21 = float(row.get("ema21", np.nan))
    stop_pp = low
    stop_ma10 = ma10 * 0.99 if not np.isnan(ma10) and ma10 > 0 else close * 0.92
    stop_ema21 = ema21 * 0.99 if not np.isnan(ema21) and ema21 > 0 else close * 0.92
    return max(stop_pp, stop_ma10, stop_ema21)


def run_daily_backtest(
    daily_dfs: dict[str, pd.DataFrame],
    config: DailyPortfolioConfig,
    eligibility: EligibilityMap,
) -> tuple[pd.DataFrame, dict]:
    """Daily portfolio sim: exit at next day open, entry at next day open. VND, fees, regime."""
    fee_mult = config.fee_bps_per_side / 10_000.0
    cash_vnd = config.initial_equity
    all_dates = sorted(
        set().union(*(set(d["date"].astype(str)) for d in daily_dfs.values()))
    )
    if not all_dates:
        return pd.DataFrame(), {}

    positions: dict[str, dict] = {}
    equity_path = [config.initial_equity]
    heat_path = [0.0]
    gross_exposure_path = [0.0]
    dates_path = [pd.to_datetime(all_dates[0])]
    trades: list[dict] = []

    skipped_ineligible = 0
    skipped_heat = 0
    skipped_max_positions = 0
    skipped_liquidity = 0
    skipped_regime_off = 0
    skipped_no_new_positions = 0

    for i, dt in enumerate(all_dates):
        cur_date = pd.to_datetime(dt)

        # 1) Exits at next day open
        to_close: list[str] = []
        for sym, pos in list(positions.items()):
            ddf = daily_dfs.get(sym)
            if ddf is None:
                continue
            row = ddf[ddf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]
            if not bool(row.get("exit_signal", False)):
                continue
            next_dt = all_dates[i + 1] if i + 1 < len(all_dates) else None
            if next_dt is not None:
                next_row = ddf[ddf["date"].astype(str) == next_dt]
                if not next_row.empty:
                    exit_price = float(next_row["open"].iloc[0])
                    exit_date = pd.to_datetime(next_dt)
                else:
                    exit_price = float(row["close"])
                    exit_date = cur_date
            else:
                exit_price = float(row["close"])
                exit_date = cur_date
            size = pos["shares"]
            entry_price = pos["entry_price"]
            exit_value_vnd = exit_price * size
            entry_value_vnd = entry_price * size
            entry_fee = entry_value_vnd * fee_mult
            exit_fee = exit_value_vnd * fee_mult
            pnl_vnd = exit_value_vnd - entry_value_vnd - entry_fee - exit_fee
            cash_vnd += exit_value_vnd - exit_fee
            to_close.append(sym)
            ret_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else np.nan
            trades.append({
                "symbol": sym,
                "entry_date": pos["entry_date"],
                "exit_date": exit_date,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "shares": size,
                "pnl": pnl_vnd,
                "ret": ret_pct,
                "risk_budget": pos["risk_budget"],
            })
        for sym in to_close:
            positions.pop(sym, None)

        # 2) Mark-to-market
        position_value_vnd = 0.0
        for sym, pos in positions.items():
            ddf = daily_dfs.get(sym)
            if ddf is None or ddf.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
                continue
            row = ddf[ddf["date"].astype(str) == dt]
            if row.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
            else:
                position_value_vnd += float(row.iloc[0]["close"]) * pos["shares"]
        equity_vnd = cash_vnd + position_value_vnd
        open_risk_vnd = sum(p["risk_budget"] for p in positions.values())
        free_heat_vnd = max(0.0, config.max_heat * equity_vnd - open_risk_vnd)

        # 3) Regime for this day
        regime_ftd = False
        no_new_positions = True
        for ddf in daily_dfs.values():
            r = ddf[ddf["date"].astype(str) == dt]
            if not r.empty:
                regime_ftd = bool(r.iloc[0].get("regime_ftd", False))
                no_new_positions = bool(r.iloc[0].get("no_new_positions", True))
                break

        # 4) Candidates: pp True, ema21 > ma50
        candidates: list[dict] = []
        for sym, ddf in daily_dfs.items():
            row = ddf[ddf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]
            if not bool(row.get("pp", False)):
                continue
            ema21 = float(row.get("ema21", np.nan))
            ma50 = float(row.get("ma50", np.nan))
            if np.isnan(ema21) or np.isnan(ma50) or not (ema21 > ma50):
                continue
            adtv20, adtv50 = eligibility.adtv(sym, cur_date)
            eligible_flag = eligibility.is_eligible(sym, cur_date)
            candidates.append({
                "symbol": sym,
                "row": row,
                "adtv20": adtv20,
                "adtv50": adtv50,
                "eligible_flag": eligible_flag,
            })

        # Rank by ADTV20 desc (simple)
        candidates_sorted = sorted(
            candidates,
            key=lambda c: -(c["adtv20"] or 0.0),
        )

        # 5) Entries at next day open
        for c in candidates_sorted:
            sym = c["symbol"]
            row = c["row"]
            adtv20 = c["adtv20"]
            adtv50 = c["adtv50"]
            eligible_flag = c["eligible_flag"]

            if sym in positions:
                continue
            if not regime_ftd:
                skipped_regime_off += 1
                continue
            if no_new_positions:
                skipped_no_new_positions += 1
                continue
            if not eligible_flag or adtv20 is None or adtv50 is None:
                skipped_ineligible += 1
                continue
            if len(positions) >= config.max_positions:
                skipped_max_positions += 1
                continue
            if free_heat_vnd <= 0:
                skipped_heat += 1
                continue

            next_dt = all_dates[i + 1] if i + 1 < len(all_dates) else None
            if next_dt is None:
                continue
            ddf = daily_dfs[sym]
            next_row = ddf[ddf["date"].astype(str) == next_dt]
            if next_row.empty:
                continue
            entry_price = float(next_row["open"].iloc[0])
            if entry_price <= 0:
                continue
            stop_price = _compute_stop_daily(row)
            stop_dist = (entry_price - stop_price) / entry_price
            if stop_dist <= 0:
                continue
            stop_dist = min(stop_dist, 0.10)
            risk_budget_vnd = min(config.risk_per_trade * equity_vnd, free_heat_vnd)
            if risk_budget_vnd <= 0:
                skipped_heat += 1
                continue
            nominal_value_vnd = risk_budget_vnd / stop_dist
            nominal_value_vnd = min(nominal_value_vnd, config.max_symbol_weight * equity_vnd)
            max_by_liq_vnd = config.liquidity_participation_cap * adtv20 if adtv20 else 0.0
            if max_by_liq_vnd <= 0:
                skipped_liquidity += 1
                continue
            nominal_value_vnd = min(nominal_value_vnd, max_by_liq_vnd)
            shares = int(nominal_value_vnd / entry_price)
            if shares <= 0:
                skipped_liquidity += 1
                continue
            entry_value_vnd = shares * entry_price
            entry_fee_vnd = entry_value_vnd * fee_mult
            if cash_vnd < entry_value_vnd + entry_fee_vnd:
                continue
            cash_vnd -= entry_value_vnd + entry_fee_vnd
            positions[sym] = {
                "entry_date": pd.to_datetime(next_dt),
                "entry_price": entry_price,
                "shares": shares,
                "risk_budget": risk_budget_vnd,
            }
            free_heat_vnd -= risk_budget_vnd

        # 6) Equity series
        position_value_vnd = 0.0
        for sym, pos in positions.items():
            ddf = daily_dfs.get(sym)
            if ddf is None or ddf.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
            else:
                row = ddf[ddf["date"].astype(str) == dt]
                if row.empty:
                    position_value_vnd += pos["entry_price"] * pos["shares"]
                else:
                    position_value_vnd += float(row.iloc[0]["close"]) * pos["shares"]
        equity_vnd = cash_vnd + position_value_vnd
        equity_path.append(equity_vnd)
        heat_path.append(sum(p["risk_budget"] for p in positions.values()))
        gross_exposure_path.append(
            position_value_vnd / equity_vnd if equity_vnd > 0 else 0.0
        )
        dates_path.append(cur_date)

    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        return trades_df, {}

    eq = np.array(equity_path, dtype=float)
    dates_arr = np.array(dates_path)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    mdd = float(dd.min())
    years = (dates_arr[-1] - dates_arr[0]).days / 365.25
    cagr = (eq[-1] / eq[0]) ** (1.0 / years) - 1.0 if years > 0 and eq[0] > 0 else np.nan
    mar = cagr / abs(mdd) if mdd < 0 else np.nan
    mean_equity = float(np.mean(eq)) if np.mean(eq) > 0 else 1.0
    period_months = max(1, (pd.to_datetime(all_dates[-1]) - pd.to_datetime(all_dates[0])).days / 30.0)
    trades_per_month = len(trades_df) / period_months

    stats = {
        "cagr": cagr,
        "mdd": mdd,
        "mar": mar,
        "n_trades": len(trades_df),
        "final_equity": float(eq[-1]),
        "avg_heat": float(np.mean(heat_path)) / mean_equity,
        "avg_gross_exposure": float(np.mean(gross_exposure_path)),
        "skipped_ineligible": skipped_ineligible,
        "skipped_regime_off": skipped_regime_off,
        "skipped_no_new_positions": skipped_no_new_positions,
        "skipped_max_positions": skipped_max_positions,
        "skipped_liquidity": skipped_liquidity,
        "trades_per_month": trades_per_month,
    }
    return trades_df, stats


def run_period(
    start: str,
    end: str,
    symbols: list[str] | None = None,
    eligibility: EligibilityMap | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Run Path B backtest for one period; returns (trades_df, stats). Used by parallel runner."""
    if symbols is None:
        universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
        if not universe_path.exists():
            universe_path = _REPO / "config" / "watchlist.txt"
        symbols = _load_universe(universe_path)
    if not symbols:
        return pd.DataFrame(), {}

    try:
        market_daily = fetch_ohlcv_fireant("VN30", start, end)
        market_daily = add_book_regime_columns(market_daily)
    except Exception:
        market_daily = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])
        market_daily["date"] = pd.to_datetime(market_daily["date"])

    daily_dfs = build_daily_dfs(start, end, symbols, market_daily)
    if not daily_dfs:
        return pd.DataFrame(), {}

    if eligibility is None:
        try:
            eligibility = get_global_eligibility()
        except FileNotFoundError:
            rows = []
            for sym, ddf in daily_dfs.items():
                ddf = ddf.copy()
                ddf["value"] = ddf["close"].astype(float) * ddf["volume"].astype(float)
                ddf["date"] = pd.to_datetime(ddf["date"])
                for i in range(50, len(ddf)):
                    dt = ddf.iloc[i]["date"]
                    tail50 = ddf.iloc[i - 50 : i]
                    tail20 = ddf.iloc[i - 20 : i]
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

    config = DailyPortfolioConfig()
    return run_daily_backtest(daily_dfs, config, eligibility)


def main(args: object | None = None) -> None:
    start = getattr(args, "start", None) or "2018-01-01"
    end = getattr(args, "end", None) or "2021-12-31"

    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = _load_universe(universe_path)
    if not symbols:
        print("[path_b] No symbols; aborting.")
        return

    print(f"[path_b] building daily data {start} -> {end} symbols={len(symbols)}", flush=True)
    trades_df, stats = run_period(start, end, symbols=symbols)

    if stats:
        artifacts_dir = _REPO / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        period_label = f"{start[:4]}_{end[:4]}"
        trades_path = artifacts_dir / f"trades_path_b_{period_label}.csv"
        if not trades_df.empty:
            trades_df.to_csv(trades_path, index=False)

        # Update single-period baseline artifacts for convenience
        import pandas as pd  # local import to avoid top-level dependency here
        row = {"period": period_label, "start": start, "end": end}
        for k, v in stats.items():
            row[k] = v
        df = pd.DataFrame([row])
        pb_csv = artifacts_dir / "path_b_daily_baseline.csv"
        pb_md = artifacts_dir / "path_b_daily_baseline.md"
        df.to_csv(pb_csv, index=False)
        cols = [c for c in ["period", "cagr", "mdd", "mar", "n_trades", "trades_per_month", "final_equity", "avg_heat", "avg_gross_exposure"] if c in df.columns]
        with open(pb_md, "w", encoding="utf-8") as f:
            f.write("# Path B – Daily Pocket Pivot Baseline (single period)\n\n")
            f.write(df[cols].to_string(index=False))

        print(f"[path_b] n_trades={stats.get('n_trades', 0)} CAGR={stats.get('cagr')} MDD={stats.get('mdd')} MAR={stats.get('mar')}")
        print(f"[path_b] trades_per_month={stats.get('trades_per_month')}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2021-12-31")
    ns = p.parse_args()
    main(ns)
