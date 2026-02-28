from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

import pandas as pd

from fa_cohort.fa_filters import FaFilterConfig, fa_pass


def load_fa_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "report_date" not in df.columns or "symbol" not in df.columns:
        raise ValueError("FA CSV must contain 'symbol' and 'report_date' columns.")
    df["report_date"] = pd.to_datetime(df["report_date"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return df


def _load_price_data() -> Dict[str, pd.DataFrame]:
    """
    Use existing curated loader from minervini_backtest/run.py.
    """
    from run import load_curated_data  # type: ignore

    data = load_curated_data(None)
    out: Dict[str, pd.DataFrame] = {}
    for sym, df in data.items():
        if df is None or df.empty:
            continue
        d = df.copy()
        d["date"] = pd.to_datetime(d["date"])
        d = d.sort_values("date").drop_duplicates(subset=["date"], keep="last")
        out[sym.upper()] = d
    return out


def _next_trading_day_close(price_df: pd.DataFrame, dt: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
    sub = price_df[price_df["date"] >= dt].head(1)
    if sub.empty:
        return None
    row = sub.iloc[0]
    return row["date"], float(row["close"])


def _horizon_exit(price_df: pd.DataFrame, entry_dt: pd.Timestamp, weeks: int) -> tuple[pd.Timestamp, float] | None:
    # approx N weeks = N*5 trading days
    target_days = weeks * 5
    sub = price_df[price_df["date"] > entry_dt]
    if len(sub) < target_days:
        # use last available bar
        if sub.empty:
            return None
        row = sub.iloc[-1]
        return row["date"], float(row["close"])
    row = sub.iloc[target_days - 1]
    return row["date"], float(row["close"])


def _cohort_for_quarter(fa_df: pd.DataFrame, cfg: FaFilterConfig) -> pd.DataFrame:
    fa_df = fa_df.copy()
    fa_df["year"] = fa_df["report_date"].dt.year
    fa_df["quarter"] = fa_df["report_date"].dt.to_period("Q")
    fa_df = fa_df.sort_values(["report_date", "symbol"])
    rows = []
    for (qtr,), grp in fa_df.groupby(["quarter"]):
        for _, row in grp.iterrows():
            if fa_pass(row, cfg):
                rows.append(
                    {
                        "symbol": row["symbol"],
                        "report_date": row["report_date"],
                        "year": row["year"],
                        "quarter": str(qtr),
                        "eps_yoy": row.get("eps_yoy"),
                        "sales_yoy": row.get("sales_yoy"),
                        "roe": row.get("roe"),
                    }
                )
    return pd.DataFrame(rows)


def run_cohort_backtest(
    fa_csv: str | Path,
    horizons: List[int],
    bench_symbol: str = "VNINDEX",
    start: str | None = None,
    end: str | None = None,
    cfg: FaFilterConfig | None = None,
    out_dir: str | Path = "minervini_backtest/outputs/fa_cohort",
) -> None:
    cfg = cfg or FaFilterConfig(eps_yoy_min=20.0, sales_yoy_min=15.0, roe_min=15.0, margin_yoy_min=0.0)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fa_df = load_fa_csv(fa_csv)
    if start:
        fa_df = fa_df[fa_df["report_date"] >= start]
    if end:
        fa_df = fa_df[fa_df["report_date"] <= end]
    if fa_df.empty:
        raise ValueError("No FA rows after applying start/end filter.")

    cohort_df = _cohort_for_quarter(fa_df, cfg)
    if cohort_df.empty:
        print("No symbols pass FA filter; nothing to backtest.")
        return

    # Annual cohort stats
    annual = (
        cohort_df.groupby("year")
        .agg(
            n_pass=("symbol", "nunique"),
            median_eps_yoy=("eps_yoy", "median"),
            median_sales_yoy=("sales_yoy", "median"),
            median_roe=("roe", "median"),
        )
        .reset_index()
    )
    annual.to_csv(out_dir / "annual_cohort_counts.csv", index=False)

    # Load prices for all symbols + benchmark
    price_data = _load_price_data()
    bench_df = price_data.get(bench_symbol.upper())
    if bench_df is None or bench_df.empty:
        raise ValueError(f"Benchmark symbol {bench_symbol} not found in curated data.")

    records = []
    for _, row in cohort_df.iterrows():
        sym = row["symbol"]
        px = price_data.get(sym)
        if px is None or px.empty:
            continue
        rep_dt = row["report_date"]
        # entry at next trading day
        ent = _next_trading_day_close(px, rep_dt)
        if ent is None:
            continue
        entry_dt, entry_px = ent
        # align benchmark entry
        bench_ent = _next_trading_day_close(bench_df, entry_dt)
        if bench_ent is None:
            continue
        bench_entry_dt, bench_entry_px = bench_ent

        for weeks in horizons:
            exit_pair = _horizon_exit(px, entry_dt, weeks)
            bench_exit_pair = _horizon_exit(bench_df, bench_entry_dt, weeks)
            if exit_pair is None or bench_exit_pair is None:
                continue
            exit_dt, exit_px = exit_pair
            bench_exit_dt, bench_exit_px = bench_exit_pair
            ret = (exit_px / entry_px) - 1.0
            bench_ret = (bench_exit_px / bench_entry_px) - 1.0
            records.append(
                {
                    "cohort_date": entry_dt.date(),
                    "symbol": sym,
                    "horizon_weeks": weeks,
                    "ret": ret,
                    "bench_ret": bench_ret,
                    "alpha": ret - bench_ret,
                    "year": entry_dt.year,
                }
            )

    if not records:
        print("No valid symbol/horizon pairs for cohort backtest.")
        return

    rec_df = pd.DataFrame(records)
    # equal-weight per cohort_date/horizon
    grp_cols = ["cohort_date", "horizon_weeks"]
    cohort_ret = (
        rec_df.groupby(grp_cols)
        .agg(
            n_symbols=("symbol", "nunique"),
            cohort_ret=("ret", "mean"),
            bench_ret=("bench_ret", "mean"),
        )
        .reset_index()
    )
    cohort_ret["alpha"] = cohort_ret["cohort_ret"] - cohort_ret["bench_ret"]
    cohort_ret.to_csv(out_dir / "cohort_returns.csv", index=False)

    # Simple summary verdict
    horizons_unique = sorted(set(horizons))
    # yearly alpha medians by horizon
    yearly_alpha = (
        rec_df.groupby(["year", "horizon_weeks"])["alpha"].median().reset_index()
    )
    yearly_alpha.to_csv(out_dir / "yearly_alpha.csv", index=False)

    # PASS if median alpha > 0 across horizons AND at least 3 distinct years with positive median alpha
    median_alpha_by_h = yearly_alpha.groupby("horizon_weeks")["alpha"].median()
    all_h_pos = (median_alpha_by_h > 0).all()
    years_pos = (
        yearly_alpha.groupby("year")["alpha"].median() > 0
    )
    n_years_pos = years_pos.sum()
    verdict = "PASS" if all_h_pos and n_years_pos >= 3 else "FAIL"

    summary_lines: List[str] = []
    summary_lines.append("# FA Cohort Study — Summary\n\n")
    summary_lines.append(f"- FA CSV: `{fa_csv}`\n")
    summary_lines.append(f"- Horizons (weeks): {horizons_unique}\n")
    summary_lines.append(f"- Benchmark: {bench_symbol}\n")
    summary_lines.append(f"- FA filter config: `{asdict(cfg)}`\n\n")
    summary_lines.append("## Annual cohort counts\n\n")
    summary_lines.append(annual.to_string(index=False))
    summary_lines.append("\n\n## Median yearly alpha by horizon\n\n")
    summary_lines.append(yearly_alpha.to_string(index=False))
    summary_lines.append(f"\n\n## Verdict\n\n**{verdict}**\n")

    (Path(out_dir) / "summary.md").write_text("".join(summary_lines), encoding="utf-8")

