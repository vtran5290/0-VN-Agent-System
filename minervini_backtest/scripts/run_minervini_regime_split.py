"""
Tier A regime split — Mark brain.

Classify VNINDEX into bull / bear / transition using MA200 and its slope,
then recompute Tier_A alpha metrics by regime (126/252d).
Uses trades.csv from monthly historical hit-rate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _classify_regime(index_csv: Path) -> dict[pd.Timestamp, str]:
    df = pd.read_csv(index_csv)
    if "date" not in df.columns or "close" not in df.columns:
        raise ValueError("Index CSV must contain 'date' and 'close'")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    df["ma200"] = df["close"].rolling(200, min_periods=200).mean()
    df["ma200_shift20"] = df["ma200"].shift(20)
    df["slope200"] = df["ma200"] - df["ma200_shift20"]
    regimes: dict[pd.Timestamp, str] = {}
    for _, r in df.iterrows():
        d = r["date"]
        close = r["close"]
        ma200 = r["ma200"]
        slope200 = r["slope200"]
        if pd.isna(ma200) or pd.isna(slope200):
            continue
        if close > ma200 and slope200 > 0:
            reg = "bull"
        elif close < ma200 and slope200 < 0:
            reg = "bear"
        else:
            reg = "transition"
        regimes[pd.Timestamp(d)] = reg
    return regimes


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Regime-split Tier_A alpha metrics by VNINDEX MA200 regime"
    )
    ap.add_argument(
        "--trades-csv",
        default="minervini_backtest/outputs/minervini_hit_rate_monthly/trades.csv",
        help="Path to trades.csv from monthly hit-rate",
    )
    ap.add_argument(
        "--index-csv",
        default="minervini_backtest/data/raw/VNINDEX.csv",
        help="Benchmark index CSV (date, close)",
    )
    ap.add_argument(
        "--out-dir",
        default="minervini_backtest/outputs/minervini_hit_rate_monthly",
        help="Output directory for regime_summary.json and regime_report.md",
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent.parent  # repo root
    trades_path = root / args.trades_csv
    index_path = root / args.index_csv
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not trades_path.exists():
        print(f"[ERROR] trades.csv not found: {trades_path}")
        return 1
    if not index_path.exists():
        print(f"[ERROR] index CSV not found: {index_path}")
        return 1

    trades = pd.read_csv(trades_path)
    if "tier" not in trades.columns or "asof_date" not in trades.columns:
        print("[ERROR] trades.csv missing 'tier' or 'asof_date'")
        return 1
    trades["asof_date"] = pd.to_datetime(trades["asof_date"])
    tier_a = trades[trades["tier"] == "A"].copy()
    if tier_a.empty:
        print("[WARN] No Tier_A trades for regime split")
        summary = {
            "trade_count": 0,
            "regimes": {},
            "robustness": {"bull": None, "transition": None, "bear_flag": None},
        }
        (out_dir / "regime_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        (out_dir / "regime_report.md").write_text(
            "# Tier A Regime Split\n\nNo Tier_A trades.\n", encoding="utf-8"
        )
        return 0

    regimes = _classify_regime(index_path)
    tier_a["regime"] = tier_a["asof_date"].map(lambda d: regimes.get(pd.Timestamp(d), "unknown"))
    tier_a = tier_a[tier_a["regime"].isin(["bull", "bear", "transition"])].copy()
    if tier_a.empty:
        print("[WARN] All Tier_A trades fell into unknown regime")
        return 0

    horizons = [126, 252]
    out: dict[str, dict[str, dict[str, float | int | None]]] = {}

    for regime in ["bull", "transition", "bear"]:
        reg_df = tier_a[tier_a["regime"] == regime]
        reg_entry: dict[str, dict[str, float | int | None]] = {}
        for fd in horizons:
            col = f"alpha_{fd}"
            if col not in reg_df.columns:
                continue
            alphas = reg_df[col].dropna()
            n = len(alphas)
            if n == 0:
                reg_entry[str(fd)] = {
                    "trade_count": 0,
                    "median_alpha": None,
                    "mean_alpha": None,
                    "hit_rate_alpha_pos": None,
                    "p25_alpha": None,
                    "p75_alpha": None,
                    "min_alpha": None,
                    "max_alpha": None,
                }
                continue
            reg_entry[str(fd)] = {
                "trade_count": int(n),
                "median_alpha": float(alphas.median()),
                "mean_alpha": float(alphas.mean()),
                "hit_rate_alpha_pos": float((alphas > 0).mean()),
                "p25_alpha": float(alphas.quantile(0.25)),
                "p75_alpha": float(alphas.quantile(0.75)),
                "min_alpha": float(alphas.min()),
                "max_alpha": float(alphas.max()),
            }
        out[regime] = reg_entry

    # Robustness rule (per user spec)
    def _pass_regime(reg: str) -> bool | None:
        m = out.get(reg, {}).get("126")
        if not m or m["trade_count"] == 0:
            return None
        med = m["median_alpha"]
        hr = m["hit_rate_alpha_pos"]
        if med is None or hr is None:
            return None
        return bool(med > 0 and hr >= 0.60)

    bull_pass = _pass_regime("bull")
    trans_pass = _pass_regime("transition")
    bear_med = out.get("bear", {}).get("126", {}).get("median_alpha")
    bear_flag = None
    if bear_med is not None:
        bear_flag = bool(bear_med < -0.05)

    robustness = {
        "bull_pass": bull_pass,
        "transition_pass": trans_pass,
        "bear_flag_median_126_lt_minus_0_05": bear_flag,
    }

    summary = {
        "trade_count": int(len(tier_a)),
        "regimes": out,
        "robustness": robustness,
    }
    (out_dir / "regime_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    # Markdown report
    lines: list[str] = [
        "# Tier A Regime Split — Mark brain",
        "",
        f"Index: {index_path}",
        "",
        "## Robustness summary",
        f"- Bull regime PASS (median_126>0 & hit_rate_126>=0.60): {bull_pass}",
        f"- Transition regime PASS (same rule): {trans_pass}",
        f"- Bear regime flag (median_126 < -0.05): {bear_flag}",
        "",
        "## Regime metrics (Tier_A)",
    ]
    for regime in ["bull", "transition", "bear"]:
        lines.append(f"### {regime.capitalize()}")
        reg = out.get(regime, {})
        if not reg:
            lines.append("No trades.")
            lines.append("")
            continue
        for fd in horizons:
            m = reg.get(str(fd))
            lines.append(f"- Horizon {fd}d:")
            if not m or m["trade_count"] == 0:
                lines.append("  - No trades.")
                continue
            lines.append(f"  - trade_count: {m['trade_count']}")
            lines.append(f"  - median_alpha: {m['median_alpha']}")
            lines.append(f"  - mean_alpha: {m['mean_alpha']}")
            lines.append(f"  - hit_rate_alpha_pos: {m['hit_rate_alpha_pos']}")
            lines.append(f"  - p25_alpha: {m['p25_alpha']}")
            lines.append(f"  - p75_alpha: {m['p75_alpha']}")
            lines.append(f"  - min_alpha: {m['min_alpha']}")
            lines.append(f"  - max_alpha: {m['max_alpha']}")
        lines.append("")

    (out_dir / "regime_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        f"[TierA Regime Split] Wrote {out_dir / 'regime_summary.json'} and {out_dir / 'regime_report.md'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

