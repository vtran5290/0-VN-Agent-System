"""
S16 Reopen — Momentum Seasonality Observational Analysis
Pre-reg: 2026-07-09_S15reopen_FIP_S2pool_prereg.md (§ Observational Side Task)

Stratifies A3_RS closed-trade returns by calendar month and Tet-relative timing.
OBSERVATIONAL ONLY — no gate, no intervention, describe only.

Data requirements:
  Primary: data/paper_trade/closed_trades.csv (entry_date, net_return columns)
  Extended: AFL OOS export (2020-2026) with entry_date + net_return — preferred
  Note: paper_trade/ starts 2026-03-03 (~4 months). If N < 36 months of data,
        output is flagged [DATA-INSUFFICIENT] and cannot support any intervention claim.

Usage:
  python scripts/s16_seasonality_observational.py
  python scripts/s16_seasonality_observational.py --data path/to/extended_oos.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import warnings
warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VN_AGENT_ROOT = Path(__file__).parent.parent
DEFAULT_DATA = VN_AGENT_ROOT / "data" / "paper_trade" / "closed_trades.csv"

# Tet (Lunar New Year) approximate Gregorian dates for VN (2020-2026)
# Source: official VN public holidays — week containing LNY + ±2 weeks window
LNY_DATES = {
    2020: "2020-01-25",
    2021: "2021-02-12",
    2022: "2022-02-01",
    2023: "2023-01-22",
    2024: "2024-02-10",
    2025: "2025-01-29",
    2026: "2026-02-17",
}
TET_WINDOW_DAYS = 14  # ±14 calendar days around LNY date


def load_trades(data_path: Path) -> pd.DataFrame:
    df = pd.read_csv(data_path, parse_dates=["entry_date"])
    required = {"entry_date", "net_return"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}. Available: {list(df.columns)}")
    df = df.dropna(subset=["entry_date", "net_return"])
    df["entry_month"] = df["entry_date"].dt.month
    df["entry_year"] = df["entry_date"].dt.year
    df["entry_month_name"] = df["entry_date"].dt.strftime("%b")
    df["is_quarter_end_month"] = df["entry_month"].isin([3, 6, 9, 12])
    df["is_january"] = df["entry_month"] == 1
    return df


def add_tet_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Flag trades within TET_WINDOW_DAYS of Lunar New Year."""
    tet_flags = []
    for _, row in df.iterrows():
        d = row["entry_date"]
        year = d.year
        lny = LNY_DATES.get(year)
        if lny is None:
            tet_flags.append(False)
            continue
        lny_dt = pd.Timestamp(lny)
        delta = abs((d - lny_dt).days)
        tet_flags.append(delta <= TET_WINDOW_DAYS)
    df["near_tet"] = tet_flags
    return df


def check_data_sufficiency(df: pd.DataFrame) -> dict:
    months_covered = df["entry_date"].dt.to_period("M").nunique()
    years_covered = df["entry_year"].nunique()
    jan_count = len(df[df["is_january"]])
    min_sample_gate = months_covered >= 36  # 3 years minimum for any pattern claim
    return {
        "n_trades": len(df),
        "months_covered": months_covered,
        "years_covered": years_covered,
        "jan_observations": jan_count,
        "min_sample_gate_pass": min_sample_gate,
        "data_flag": "OK" if min_sample_gate else "[DATA-INSUFFICIENT]",
    }


def monthly_analysis(df: pd.DataFrame) -> pd.DataFrame:
    MONTH_ORDER = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    results = []
    for m in MONTH_ORDER:
        subset = df[df["entry_month"] == m]["net_return"]
        if len(subset) == 0:
            results.append({
                "month": m, "month_name": pd.Timestamp(f"2000-{m:02d}-01").strftime("%b"),
                "n": 0, "mean_return": None, "median_return": None,
                "win_rate": None, "quarter_end": m in [3, 6, 9, 12],
            })
            continue
        results.append({
            "month": m,
            "month_name": pd.Timestamp(f"2000-{m:02d}-01").strftime("%b"),
            "n": len(subset),
            "mean_return": subset.mean(),
            "median_return": subset.median(),
            "win_rate": (subset > 0).mean(),
            "quarter_end": m in [3, 6, 9, 12],
        })
    return pd.DataFrame(results)


def segment_analysis(df: pd.DataFrame) -> dict:
    """Compare: January vs rest, quarter-end vs non-quarter-end-ex-jan."""
    jan = df[df["is_january"]]["net_return"]
    qend = df[df["is_quarter_end_month"] & ~df["is_january"]]["net_return"]
    non_qend_ex_jan = df[~df["is_quarter_end_month"] & ~df["is_january"]]["net_return"]
    tet = df[df["near_tet"]]["net_return"]
    non_tet = df[~df["near_tet"]]["net_return"]

    def stats(s, label):
        if len(s) == 0:
            return {"label": label, "n": 0, "mean": None, "median": None, "win_rate": None}
        return {
            "label": label, "n": len(s),
            "mean": s.mean(), "median": s.median(),
            "win_rate": (s > 0).mean(),
        }

    return {
        "january": stats(jan, "January"),
        "quarter_end_ex_jan": stats(qend, "Quarter-end months (Mar/Jun/Sep/Dec) ex Jan"),
        "non_quarter_end_ex_jan": stats(non_qend_ex_jan, "Non-quarter-end, non-January"),
        "tet_window": stats(tet, f"Near-Tet (±{TET_WINDOW_DAYS}d of LNY)"),
        "non_tet": stats(non_tet, f"Non-Tet window"),
    }


def print_report(sufficiency: dict, monthly: pd.DataFrame, segments: dict, data_path: Path):
    print("\n" + "=" * 70)
    print("S16 REOPEN — Momentum Seasonality Observational Analysis")
    print("Date: 2026-07-09 | Pre-reg: 2026-07-09_S15reopen_FIP_S2pool_prereg.md")
    print("OBSERVATIONAL ONLY — describe only, no intervention")
    print("=" * 70)
    print(f"\nData source: {data_path}")
    print(f"N trades: {sufficiency['n_trades']}")
    print(f"Months covered: {sufficiency['months_covered']} | Years: {sufficiency['years_covered']}")
    print(f"January observations: {sufficiency['jan_observations']}")
    print(f"Minimum-sample gate (≥36 months): {'PASS' if sufficiency['min_sample_gate_pass'] else 'FAIL'}")
    print(f"Data flag: {sufficiency['data_flag']}")

    if not sufficiency["min_sample_gate_pass"]:
        print("\n⚠️  [DATA-INSUFFICIENT]: <36 months of data.")
        print("   Results below are DESCRIPTIVE ONLY and cannot support any claim.")
        print("   Re-run with AFL OOS export (2020-2026) for meaningful analysis.")
        print()

    print("\n--- Monthly Return Distribution (by entry month) ---")
    print(f"{'Month':<10} {'N':>5} {'Mean Ret':>10} {'Median Ret':>12} {'Win Rate':>10} {'Qtr End':>8}")
    print("-" * 60)
    for _, row in monthly.iterrows():
        if row["n"] == 0:
            print(f"{row['month_name']:<10} {'0':>5} {'N/A':>10} {'N/A':>12} {'N/A':>10} {str(row['quarter_end']):>8}")
        else:
            qe_flag = "★" if row["quarter_end"] else " "
            jan_flag = "▼" if row["month"] == 1 else " "
            print(
                f"{row['month_name']:<10}{jan_flag}{qe_flag}"
                f" {row['n']:>4} "
                f"{row['mean_return']:>+9.2%} "
                f"{row['median_return']:>+11.2%} "
                f"{row['win_rate']:>9.1%}"
            )
    print("  ★ = quarter-end month (window-dressing thesis)  ▼ = January (reversal thesis)")

    print("\n--- Segment Comparison ---")
    for seg in segments.values():
        if seg["n"] == 0:
            print(f"  {seg['label']}: N=0 (no data)")
        else:
            print(
                f"  {seg['label']}:"
                f" N={seg['n']}, mean={seg['mean']:+.2%}, "
                f"median={seg['median']:+.2%}, win={seg['win_rate']:.1%}"
            )

    print("\n--- US Reference (Gray & Vogel 1927-2014) ---")
    print("  January: H-L spread = -1.72%/month (reversal)")
    print("  Quarter-end avg: 3.10%/month vs non-quarter-end ex Jan: 0.59%/month (5× ratio)")
    print("  December: 5.52%/month (strongest)")

    print("\n--- Observational Verdict ---")
    n_jan = sufficiency["jan_observations"]
    if not sufficiency["min_sample_gate_pass"]:
        print("  [DATA-INSUFFICIENT] — cannot confirm or refute S16 pattern.")
        print("  Required action: extract AFL OOS 2020-2026 trades → re-run.")
    else:
        jan_mean = monthly.loc[monthly["month"] == 1, "mean_return"].values
        qend_means = monthly.loc[monthly["quarter_end"], "mean_return"].dropna()
        non_qend_means = monthly.loc[~monthly["quarter_end"] & (monthly["month"] != 1), "mean_return"].dropna()
        if len(jan_mean) > 0 and not pd.isna(jan_mean[0]) and len(qend_means) > 0:
            qend_avg = qend_means.mean()
            non_qend_avg = non_qend_means.mean() if len(non_qend_means) > 0 else float("nan")
            jan_vs_qend = jan_mean[0] < qend_avg
            qend_vs_non = qend_avg > non_qend_avg if not pd.isna(non_qend_avg) else None
            pattern_consistent = jan_vs_qend and (qend_vs_non if qend_vs_non is not None else False)
            print(f"  Jan mean ({jan_mean[0]:+.2%}) < Qtr-end avg ({qend_avg:+.2%}): {'YES' if jan_vs_qend else 'NO'}")
            if not pd.isna(non_qend_avg):
                print(f"  Qtr-end avg ({qend_avg:+.2%}) > Non-qtr ex-Jan ({non_qend_avg:+.2%}): {'YES' if qend_vs_non else 'NO'}")
            verdict = "[OBSERVED-CONSISTENT]" if pattern_consistent else "[OBSERVED-INCONSISTENT]"
            print(f"  Verdict: {verdict}")
            print("  Next step: if OBSERVED-CONSISTENT → register formal pre-reg with minimum-sample gate.")
            print("             if OBSERVED-INCONSISTENT → S16 remains DEGRADING-REJECT.")
        else:
            print("  Insufficient data to compute verdict.")

    print("\n" + "=" * 70)
    print("Tet reference dates used:", LNY_DATES)
    print("=" * 70 + "\n")


def main():
    data_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA
    if not data_path.exists():
        print(f"ERROR: Data file not found: {data_path}")
        print("Provide AFL OOS export with columns: entry_date, net_return")
        sys.exit(1)

    df = load_trades(data_path)
    df = add_tet_flag(df)
    sufficiency = check_data_sufficiency(df)
    monthly = monthly_analysis(df)
    segments = segment_analysis(df)
    print_report(sufficiency, monthly, segments, data_path)

    # Save CSV for further analysis
    out_path = data_path.parent / "s16_seasonality_monthly.csv"
    monthly.to_csv(out_path, index=False)
    print(f"Monthly table saved: {out_path}")


if __name__ == "__main__":
    main()
