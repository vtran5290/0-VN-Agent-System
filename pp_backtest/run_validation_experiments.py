"""
Validation experiments: ranking ablation + capacity test only.
Single slice 2018-01-01 to 2021-12-31. Writes artifacts/validation_results.{md,csv,json}.
No filter optimization, no FA, no signal changes.
"""

from __future__ import annotations

import json
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
    from pp_backtest.eligibility import get_global_eligibility, EligibilityMap
    from pp_backtest.portfolio_sim import (
        PortfolioConfig,
        run_portfolio_backtest,
        DEFAULT_INITIAL_EQUITY_VND,
    )
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
    from eligibility import get_global_eligibility, EligibilityMap
    from portfolio_sim import (
        PortfolioConfig,
        run_portfolio_backtest,
        DEFAULT_INITIAL_EQUITY_VND,
    )


METRIC_KEYS = [
    "CAGR", "MDD", "MAR", "n_trades", "final_equity",
    "avg_heat", "avg_gross_exposure",
    "skipped_ineligible", "skipped_regime_off", "skipped_no_new_positions",
    "skipped_max_positions", "skipped_liquidity",
]


def load_universe(path: Path) -> list[str]:
    txt = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in txt if ln.strip() and not ln.strip().startswith("#")]


def build_weekly_dfs(cfg: BacktestConfig, symbols: list[str]) -> dict[str, pd.DataFrame]:
    try:
        market_daily = fetch_ohlcv_fireant("VN30", cfg.start, cfg.end)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception:
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])
    weekly_dfs: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            daily_df = fetch_ohlcv_fireant(sym, cfg.start, cfg.end)
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
        wdf = wdf.merge(market_weekly_regime, on="date", how="left")
        wdf["regime_ftd"] = wdf["regime_ftd"].fillna(False)
        wdf["no_new_positions"] = wdf["no_new_positions"].fillna(False)
        weekly_dfs[sym] = wdf
    return weekly_dfs


def get_eligibility(weekly_dfs: dict[str, pd.DataFrame]) -> EligibilityMap:
    try:
        return get_global_eligibility()
    except FileNotFoundError:
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
                    "symbol": sym, "month_start": dt, "adtv20": adtv20, "adtv50": adtv50,
                    "listed_flag": True, "min_history_flag": True, "active_flag": True, "eligible_flag": eligible,
                })
        if not rows:
            raise FileNotFoundError("No eligibility from weekly_dfs")
        return EligibilityMap(df=pd.DataFrame(rows))


def default_config(initial_equity_vnd: float = DEFAULT_INITIAL_EQUITY_VND) -> PortfolioConfig:
    return PortfolioConfig(
        risk_per_trade=0.005,
        max_heat=0.04,
        max_positions=8,
        max_symbol_weight=0.10,
        liquidity_participation_cap=0.05,
        initial_equity=initial_equity_vnd,
        fee_bps_per_side=15.0,
    )


def stats_row(stats: dict, label: str, experiment: str) -> dict:
    row = {"experiment": experiment, "label": label}
    row["CAGR"] = stats.get("cagr", np.nan)
    row["MDD"] = stats.get("mdd", np.nan)
    row["MAR"] = stats.get("mar", np.nan)
    row["n_trades"] = stats.get("n_trades", 0)
    row["final_equity"] = stats.get("final_equity", 0)
    row["avg_heat"] = stats.get("avg_heat", np.nan)
    row["avg_gross_exposure"] = stats.get("avg_gross_exposure", np.nan)
    row["skipped_ineligible"] = stats.get("skipped_ineligible", 0)
    row["skipped_regime_off"] = stats.get("skipped_regime_off", 0)
    row["skipped_no_new_positions"] = stats.get("skipped_no_new_positions", 0)
    row["skipped_max_positions"] = stats.get("skipped_max_positions", 0)
    row["skipped_liquidity"] = stats.get("skipped_liquidity", 0)
    return row


def main() -> None:
    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    symbols = load_universe(universe_path)
    cfg = BacktestConfig()
    cfg.start = "2018-01-01"
    cfg.end = "2021-12-31"

    print("[run_validation_experiments] Building weekly data 2018-01-01 to 2021-12-31...", flush=True)
    weekly_dfs = build_weekly_dfs(cfg, symbols)
    if not weekly_dfs:
        print("No weekly data; abort.")
        return
    print(f"  Symbols: {len(weekly_dfs)}", flush=True)
    eligibility = get_eligibility(weekly_dfs)

    # Engine mode names (portfolio_sim accepts current, adtv_only, etc. via aliases)
    RANKING_MODES = [
        ("current", "current"),
        ("adtv_only", "adtv_only"),
        ("tightness_only", "tightness_only"),
        ("extension_only", "extension_only"),
        ("random_seed_42", "random_seed_42"),
    ]

    # --- PART A: Ranking ablation (initial_equity = 1e9) ---
    ranking_rows = []
    nav_1e9 = 1_000_000_000
    config_1e9 = default_config(initial_equity_vnd=nav_1e9)
    for label, mode in RANKING_MODES:
        print(f"  Ranking ablation: {label}...", flush=True)
        trades_df, stats = run_portfolio_backtest(
            weekly_dfs, config_1e9, eligibility=eligibility, ranking_mode=mode,
        )
        ranking_rows.append(stats_row(stats, label, "ranking_ablation"))
        trades_path = artifacts_dir / f"trades_ranking_{label}.csv"
        if not trades_df.empty:
            trades_df.to_csv(trades_path, index=False)

    # --- PART B: Capacity test (ranking = current only) ---
    capacity_rows = []
    for nav_vnd, label in [
        (1_000_000_000, "1bn"),
        (5_000_000_000, "5bn"),
        (10_000_000_000, "10bn"),
    ]:
        print(f"  Capacity: {label}...", flush=True)
        config_nav = default_config(initial_equity_vnd=nav_vnd)
        trades_df, stats = run_portfolio_backtest(
            weekly_dfs, config_nav, eligibility=eligibility, ranking_mode="current",
        )
        capacity_rows.append(stats_row(stats, label, "capacity_test"))
        trades_path = artifacts_dir / f"trades_capacity_{label}.csv"
        if not trades_df.empty:
            trades_df.to_csv(trades_path, index=False)

    # --- Build tables ---
    df_ranking = pd.DataFrame(ranking_rows)
    df_capacity = pd.DataFrame(capacity_rows)

    # --- Section 3: notes ---
    def best_ranking_by_mar() -> str:
        if df_ranking.empty or "MAR" not in df_ranking.columns:
            return "N/A"
        valid = df_ranking.replace([np.inf, -np.inf], np.nan).dropna(subset=["MAR"])
        if valid.empty:
            return "N/A"
        return valid.loc[valid["MAR"].idxmax(), "label"]

    def random_mar() -> float:
        r = df_ranking[df_ranking["label"] == "random_seed_42"]
        if r.empty:
            return np.nan
        return float(r["MAR"].iloc[0])

    def current_mar() -> float:
        r = df_ranking[df_ranking["label"] == "current"]
        if r.empty:
            return np.nan
        return float(r["MAR"].iloc[0])

    def liquidity_binds_at_5bn_or_10bn() -> str:
        if df_capacity.empty:
            return "N/A"
        c5 = df_capacity[df_capacity["label"] == "5bn"]
        c10 = df_capacity[df_capacity["label"] == "10bn"]
        s5 = int(c5["skipped_liquidity"].iloc[0]) if not c5.empty else 0
        s10 = int(c10["skipped_liquidity"].iloc[0]) if not c10.empty else 0
        if s10 > 0 or s5 > 0:
            return f"skipped_liquidity: 5bn={s5}, 10bn={s10}"
        return "skipped_liquidity remains 0 at 5bn and 10bn (liquidity not binding)"

    def performance_vs_nav() -> str:
        if len(df_capacity) < 2:
            return "N/A"
        cagrs = df_capacity.set_index("label")["CAGR"].astype(float)
        mdds = df_capacity.set_index("label")["MDD"].astype(float)
        if cagrs.isna().all():
            return "Insufficient data"
        cagr_1 = cagrs.get("1bn", np.nan)
        cagr_5 = cagrs.get("5bn", np.nan)
        cagr_10 = cagrs.get("10bn", np.nan)
        if np.isnan(cagr_1):
            return "N/A"
        msg = f"CAGR 1bn={cagr_1:.2%}"
        if not np.isnan(cagr_5):
            msg += f", 5bn={cagr_5:.2%}"
        if not np.isnan(cagr_10):
            msg += f", 10bn={cagr_10:.2%}"
        if not (np.isnan(cagr_5) or np.isnan(cagr_10)):
            if cagr_10 < cagr_1 - 0.02 or cagr_5 < cagr_1 - 0.02:
                msg += ". Performance degrades materially at higher NAV."
            else:
                msg += ". No material degradation at higher NAV."
        return msg

    notes = {
        "best_ranking_by_MAR": best_ranking_by_mar(),
        "random_vs_current": f"random_seed_42 MAR={random_mar():.2f}, current MAR={current_mar():.2f}; random underperforms materially" if random_mar() < current_mar() - 0.1 else "random vs current MAR difference is small",
        "liquidity_binding": liquidity_binds_at_5bn_or_10bn(),
        "performance_vs_NAV": performance_vs_nav(),
    }

    # --- Write artifacts ---
    md_path = artifacts_dir / "validation_results.md"
    csv_rank_path = artifacts_dir / "validation_results_ranking.csv"
    csv_cap_path = artifacts_dir / "validation_results_capacity.csv"
    json_path = artifacts_dir / "validation_results.json"

    use_markdown = hasattr(pd.DataFrame(), "to_markdown")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Validation Results (2018-01-01 to 2021-12-31)\n\n")
        f.write("## 1. Ranking ablation (initial_equity = 1bn VND)\n\n")
        if use_markdown:
            f.write(df_ranking[METRIC_KEYS + ["label"]].to_markdown(index=False) + "\n\n")
        else:
            f.write("```\n" + df_ranking[METRIC_KEYS + ["label"]].to_string(index=False) + "\n```\n\n")
        f.write("## 2. Capacity test (ranking = current)\n\n")
        if use_markdown:
            f.write(df_capacity[METRIC_KEYS + ["label"]].to_markdown(index=False) + "\n\n")
        else:
            f.write("```\n" + df_capacity[METRIC_KEYS + ["label"]].to_string(index=False) + "\n```\n\n")
        f.write("## 3. Notes\n\n")
        f.write("- **Best ranking by MAR:** " + notes["best_ranking_by_MAR"] + "\n")
        f.write("- **Random vs current:** " + notes["random_vs_current"] + "\n")
        f.write("- **Liquidity at 5bn/10bn:** " + notes["liquidity_binding"] + "\n")
        f.write("- **Performance vs NAV:** " + notes["performance_vs_NAV"] + "\n")

    df_ranking.to_csv(csv_rank_path, index=False)
    df_capacity.to_csv(csv_cap_path, index=False)
    df_all = pd.concat([df_ranking, df_capacity], ignore_index=True)
    df_all.to_csv(artifacts_dir / "validation_results.csv", index=False)
    def _sanitize(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            if isinstance(v, (np.integer, np.int64)):
                out[k] = int(v)
            elif isinstance(v, (np.floating, np.float64, float)):
                out[k] = None if (v != v or v == float("inf") or v == float("-inf")) else float(v)
            elif isinstance(v, np.bool_):
                out[k] = bool(v)
            else:
                out[k] = v
        return out

    out_json = {
        "ranking_ablation": [_sanitize(r) for r in df_ranking.to_dict(orient="records")],
        "capacity_test": [_sanitize(r) for r in df_capacity.to_dict(orient="records")],
        "notes": notes,
    }
    with open(json_path, "w", encoding="utf-8") as j:
        json.dump(out_json, j, indent=2)

    print(f"\nWrote {md_path}", flush=True)
    print(f"Wrote {csv_rank_path}, {csv_cap_path}, {artifacts_dir / 'validation_results.csv'}", flush=True)
    print(f"Wrote {json_path}", flush=True)
    print("\n--- Ranking ablation ---")
    print(df_ranking[["label", "CAGR", "MDD", "MAR", "n_trades", "final_equity", "skipped_liquidity"]].to_string(index=False))
    print("\n--- Capacity test ---")
    print(df_capacity[["label", "CAGR", "MDD", "MAR", "n_trades", "final_equity", "skipped_liquidity"]].to_string(index=False))
    print("\n--- Notes ---")
    for k, v in notes.items():
        print(f"  {k}: {v}")
    best = notes["best_ranking_by_MAR"]
    if not df_ranking.empty and "MAR" in df_ranking.columns:
        mar_vals = pd.to_numeric(df_ranking["MAR"], errors="coerce")
        if mar_vals.notna().any():
            worst_label = df_ranking.loc[mar_vals.idxmin(), "label"]
        else:
            worst_label = "N/A"
    else:
        worst_label = "N/A"
    print(f"\nBest ranking by MAR: {best}; Worst: {worst_label}")


if __name__ == "__main__":
    main()
