from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def _read_trades(dir_path: Path) -> pd.DataFrame:
    trades_path = dir_path / "trades.csv"
    if not trades_path.exists():
        raise FileNotFoundError(f"Expected trades.csv in {dir_path}, not found.")
    df = pd.read_csv(trades_path)
    required = [
        "symbol",
        "report_date",
        "horizon_weeks",
        "entry_date",
        "exit_date",
        "entry_price",
        "exit_price",
        "ret",
        "bench_ret",
        "alpha",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{trades_path} missing columns: {missing}")
    # Parse dates
    for col in ["report_date", "entry_date", "exit_date"]:
        df[col] = pd.to_datetime(df[col])
    # Drop duplicates by identity key
    key_cols = ["symbol", "report_date", "horizon_weeks", "entry_date"]
    before = len(df)
    df = df.drop_duplicates(subset=key_cols)
    dropped = before - len(df)
    if dropped > 0:
        print(f"[WARN] {dir_path}: dropped {dropped} duplicate trades by {key_cols}")
    return df


def _match_trades_with_tolerance(
    b: pd.DataFrame, m: pd.DataFrame, tolerance_days: int
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Return three DataFrames: both, breakout_only, ma_only.
    Matching by (symbol, report_date, horizon_weeks) and |entry_date_diff| <= tolerance_days.
    """
    key_cols = ["symbol", "report_date", "horizon_weeks"]
    b = b.copy()
    m = m.copy()
    b["__bid"] = range(len(b))
    m["__mid"] = range(len(m))

    if tolerance_days == 0:
        merged = b.merge(
            m,
            on=key_cols + ["entry_date"],
            how="inner",
            suffixes=("_b", "_m"),
        )
    else:
        merged = b.merge(m, on=key_cols, how="inner", suffixes=("_b", "_m"))
        if merged.empty:
            both_b = b.iloc[0:0]
            breakout_only = b.drop(columns="__bid")
            ma_only = m.drop(columns="__mid")
            return both_b, breakout_only, ma_only
        merged["entry_diff_days"] = (
            (merged["entry_date_b"] - merged["entry_date_m"]).dt.days.abs()
        )
        merged = merged[merged["entry_diff_days"] <= tolerance_days]
        if merged.empty:
            both_b = b.iloc[0:0]
            breakout_only = b.drop(columns="__bid")
            ma_only = m.drop(columns="__mid")
            return both_b, breakout_only, ma_only
        merged = merged.sort_values(
            ["symbol", "report_date", "horizon_weeks", "entry_diff_days"]
        )
        merged = merged.drop_duplicates(subset="__bid", keep="first")
        merged = merged.drop_duplicates(subset="__mid", keep="first")

    b_ids = merged["__bid"].to_numpy()
    m_ids = merged["__mid"].to_numpy()

    both_b = b.set_index("__bid").loc[b_ids].reset_index(drop=True)
    both_m = m.set_index("__mid").loc[m_ids].reset_index(drop=True)

    breakout_only = b[~b["__bid"].isin(b_ids)].drop(columns="__bid")
    ma_only = m[~m["__mid"].isin(m_ids)].drop(columns="__mid")
    both_b = both_b.drop(columns="__bid", errors="ignore")
    both_m = both_m.drop(columns="__mid", errors="ignore")

    both = both_b.copy()
    both["alpha_ma"] = both_m["alpha"].to_numpy()
    return both, breakout_only, ma_only


def _group_metrics(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {
            "trade_count": 0,
            "median_alpha": float("nan"),
            "mean_alpha": float("nan"),
            "sharpe_like": float("nan"),
        }
    a = df["alpha"].to_numpy()
    tc = int(len(a))
    med = float(np.nanmedian(a))
    mean = float(np.nanmean(a))
    std = float(np.nanstd(a))
    sharpe = mean / std if std > 0 else float("nan")
    return {
        "trade_count": tc,
        "median_alpha": med,
        "mean_alpha": mean,
        "sharpe_like": sharpe,
    }


def _correlation(alpha_b: pd.Series, alpha_ma: pd.Series, min_n: int = 20) -> float:
    mask = alpha_b.notna() & alpha_ma.notna()
    a = alpha_b[mask].to_numpy()
    b = alpha_ma[mask].to_numpy()
    if len(a) < min_n:
        return float("nan")
    if np.nanstd(a) == 0 or np.nanstd(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def main() -> int:
    ap = argparse.ArgumentParser(description="E5 Overlap Matrix for Hybrid breakout vs MA timing")
    ap.add_argument(
        "--breakout-dir",
        required=True,
        help="Directory for breakout_20d engine (expects trades.csv)",
    )
    ap.add_argument(
        "--ma-dir",
        required=True,
        help="Directory for ma5_gt_ma10_gt_ma20 engine (expects trades.csv)",
    )
    ap.add_argument(
        "--out-dir",
        required=True,
        help="Output directory for overlap report",
    )
    ap.add_argument(
        "--tolerance-days",
        type=int,
        default=0,
        help="Tolerance on entry_date matching (days, default 0)",
    )
    args = ap.parse_args()

    breakout_dir = Path(args.breakout_dir)
    ma_dir = Path(args.ma_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    b_trades = _read_trades(breakout_dir)
    m_trades = _read_trades(ma_dir)

    horizons = sorted(set(b_trades["horizon_weeks"].unique()) | set(m_trades["horizon_weeks"].unique()))

    both, breakout_only, ma_only = _match_trades_with_tolerance(
        b_trades, m_trades, args.tolerance_days
    )

    if not both.empty:
        diff = both["alpha"] - both["alpha_ma"]
        same_mask = diff.abs() <= 1e-9
        frac_same = float(same_mask.mean())
        print(
            f"[INFO] BOTH group: {frac_same:.3%} of trades have identical alpha between "
            "breakout and MA engines."
        )
        if args.tolerance_days == 0 and frac_same > 0.999:
            print(
                "[WARN] tolerance_days=0 and alpha_breakout ≈ alpha_ma for ~100% of BOTH trades; "
                "pooled correlation will be ~1.0 and is not informative about timing differences."
            )

    n_b = len(b_trades)
    n_m = len(m_trades)
    n_int = len(both)
    n_union = n_b + n_m - n_int
    overlap_rate = float(n_int / n_union) if n_union > 0 else float("nan")

    rows: List[Dict[str, float]] = []
    groups = {
        "BOTH": both,
        "BREAKOUT_ONLY": breakout_only,
        "MA_ONLY": ma_only,
    }
    for name, df in groups.items():
        for h in horizons:
            sub = df[df["horizon_weeks"] == h]
            m = _group_metrics(sub)
            rows.append(
                {
                    "group": name,
                    "horizon": int(h),
                    **m,
                }
            )
        m_all = _group_metrics(df)
        rows.append({"group": name, "horizon": -1, **m_all})

    overlap_groups = pd.DataFrame(rows)
    overlap_groups.to_csv(out_dir / "overlap_groups.csv", index=False)

    corr_rows: List[Dict[str, float]] = []
    for h in horizons:
        sub = both[both["horizon_weeks"] == h]
        c = _correlation(sub["alpha"], sub["alpha_ma"])
        corr_rows.append({"horizon": int(h), "corr_alpha": c, "trade_count": int(len(sub))})
    c_pooled = _correlation(both["alpha"], both["alpha_ma"])
    corr_rows.append({"horizon": -1, "corr_alpha": c_pooled, "trade_count": int(len(both))})
    corr_df = pd.DataFrame(corr_rows)

    def _only_positive(group_name: str, hs: List[int]) -> bool:
        g = overlap_groups[
            (overlap_groups["group"] == group_name) & (overlap_groups["horizon"].isin(hs))
        ]
        if g.empty:
            return False
        meds = g["median_alpha"].to_numpy()
        return np.all(np.isfinite(meds)) and np.all(meds > 0)

    cond_overlap = overlap_rate < 0.70 if not np.isnan(overlap_rate) else False
    main_horizons = [h for h in [10, 13] if h in horizons] or horizons[:2]
    cond_only = _only_positive("BREAKOUT_ONLY", main_horizons) or _only_positive(
        "MA_ONLY", main_horizons
    )

    pooled_row = corr_df[corr_df["horizon"] == -1]
    pooled_corr = float(pooled_row["corr_alpha"].iloc[0]) if not pooled_row.empty else float("nan")
    if np.isfinite(pooled_corr):
        cond_corr = pooled_corr < 0.75
    else:
        valid = corr_df[(corr_df["horizon"] != -1) & corr_df["corr_alpha"].notna()]
        cond_corr = (valid["corr_alpha"] < 0.75).sum() >= 2

    promote_or = bool(cond_overlap and cond_only and cond_corr)

    summary = {
        "inputs": {
            "breakout_dir": str(breakout_dir),
            "ma_dir": str(ma_dir),
            "out_dir": str(out_dir),
            "tolerance_days": int(args.tolerance_days),
        },
        "counts": {
            "n_breakout": int(n_b),
            "n_ma": int(n_m),
            "n_intersection": int(n_int),
            "n_union": int(n_union),
            "overlap_rate": float(overlap_rate) if np.isfinite(overlap_rate) else None,
        },
        "conditions": {
            "overlap_rate_lt_0_70": bool(cond_overlap),
            "only_group_positive": bool(cond_only),
            "corr_lt_0_75": bool(cond_corr),
        },
        "pooled_correlation": float(pooled_corr) if np.isfinite(pooled_corr) else None,
        "verdict": "PROMOTE_OR" if promote_or else "NO_OR",
    }

    with (out_dir / "overlap_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    lines: List[str] = []
    lines.append("# E5 Overlap Matrix Report\n")
    lines.append("## Inputs\n")
    lines.append(f"- **breakout_dir**: `{breakout_dir}`")
    lines.append(f"- **ma_dir**: `{ma_dir}`")
    lines.append(f"- **out_dir**: `{out_dir}`")
    lines.append(f"- **tolerance_days**: {args.tolerance_days}\n")

    lines.append("## Overlap rate\n")
    lines.append(f"- **n_breakout**: {n_b}")
    lines.append(f"- **n_ma**: {n_m}")
    lines.append(f"- **n_intersection**: {n_int}")
    lines.append(f"- **n_union**: {n_union}")
    if np.isfinite(overlap_rate):
        lines.append(f"- **overlap_rate**: {overlap_rate:.4f}\n")
    else:
        lines.append("- **overlap_rate**: NaN\n")

    lines.append("## Group metrics (by horizon)\n")
    lines.append(overlap_groups.to_string(index=False))
    lines.append("\n\n## Correlations (BOTH group)\n")
    lines.append(corr_df.to_string(index=False))

    lines.append("\n\n## Verdict\n")
    lines.append(f"**Verdict**: `{summary['verdict']}`\n")
    reasons = []
    ov_val = f"{overlap_rate:.4f}" if np.isfinite(overlap_rate) else "NaN"
    reasons.append(f"- overlap_rate < 0.70: {cond_overlap} (value={ov_val})")
    reasons.append(f"- ONLY group median_alpha > 0 on main horizons {main_horizons}: {cond_only}")
    corr_val = f"{pooled_corr:.4f}" if np.isfinite(pooled_corr) else "NaN"
    reasons.append(
        f"- pooled corr < 0.75 (or >=2 horizons corr<0.75): {cond_corr} (pooled={corr_val})"
    )
    lines.extend(reasons)

    (out_dir / "overlap_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote overlap_summary.json, overlap_report.md and overlap_groups.csv to {out_dir}")
    print(f"Final verdict: {summary['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

