"""
Minervini Candidate Filter — production screener.

FA gate: Mark-tight + earnings acceleration (same thresholds as Phase 2).
Tech gate: breakout_20d OR ma5_gt_ma10_gt_ma20 (co-locked engines).
Candidate = PASS_FA and (PASS_TECH_BREAKOUT or PASS_TECH_MA).

Outputs: candidates.csv, candidates.json, README.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

# Run from repo root; minervini_backtest on path for imports
import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minervini_candidates.utils import (
    load_fa_latest_per_symbol,
    load_price_data,
    get_asof_date,
    run_candidate_screen,
)


CSV_COLUMNS = [
    "asof_date", "symbol",
    "fa_pass", "fa_fail_reasons",
    "sales_yoy", "earnings_yoy", "roe", "debt_to_equity", "margin_yoy", "eps_yoy", "earnings_accel_flag",
    "tech_breakout_20d", "tech_ma_stacked", "tech_both",
    "close", "ma5", "ma10", "ma20", "high20",
    "liquidity_adv20", "volume", "vol_med20",
    "tag",
]


def _load_universe(watchlist_path: Path | None, fa_symbols: list[str]) -> list[str]:
    """Prefer watchlist file; else use unique symbols from FA."""
    if watchlist_path and watchlist_path.exists():
        lines = watchlist_path.read_text(encoding="utf-8").strip().splitlines()
        return [ln.strip().upper() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    return list(fa_symbols)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Minervini Candidate Filter: FA + timing (breakout_20d / MA stacked)"
    )
    ap.add_argument(
        "--asof",
        default=None,
        help="Screening date YYYY-MM-DD (default: latest trading date from price data)",
    )
    ap.add_argument(
        "--fa-csv",
        default="data/fa_minervini.csv",
        help="Path to FA CSV (default: data/fa_minervini.csv)",
    )
    ap.add_argument(
        "--price-dir",
        default="minervini_backtest/data/raw",
        help="Directory of OHLCV CSVs (default: minervini_backtest/data/raw)",
    )
    ap.add_argument(
        "--out-dir",
        default="minervini_backtest/outputs/minervini_candidates",
        help="Output directory for candidates.csv, candidates.json, README.md",
    )
    ap.add_argument(
        "--watchlist",
        default=None,
        help="Universe: path to watchlist (one symbol per line). Else use FA symbols.",
    )
    args = ap.parse_args()

    fa_path = Path(args.fa_csv)
    if not fa_path.exists():
        print(f"[ERROR] FA CSV not found: {fa_path}")
        return 1

    price_dir = Path(args.price_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load FA latest per symbol
    fa_latest = load_fa_latest_per_symbol(fa_path)
    if fa_latest.empty:
        print("[ERROR] No rows in FA CSV.")
        return 1

    # Universe: watchlist or FA symbols
    watchlist_path = Path(args.watchlist) if args.watchlist else (ROOT.parent / "config" / "watchlist_80.txt")
    if not watchlist_path.exists():
        watchlist_path = ROOT.parent / "config" / "watchlist.txt"
    universe = _load_universe(watchlist_path, fa_latest["symbol"].unique().tolist())
    if universe:
        fa_latest = fa_latest[fa_latest["symbol"].isin(universe)].copy()
    if fa_latest.empty:
        print("[ERROR] No FA rows after universe filter.")
        return 1

    # Load price data
    price_data = load_price_data(price_dir)
    if not price_data:
        print(f"[ERROR] No price data in {price_dir}")
        return 1

    # Asof date
    if args.asof:
        try:
            asof = pd.Timestamp(args.asof)
        except Exception:
            print(f"[ERROR] Invalid --asof {args.asof}")
            return 1
    else:
        asof = get_asof_date(price_data)
        if asof is None:
            print("[ERROR] Could not determine asof date from price data.")
            return 1

    # Screen
    df = run_candidate_screen(fa_latest, price_data, asof)

    # Counts
    n_universe = len(df)
    n_fa_pass = int(df["fa_pass"].sum())
    candidates = df[df["tag"].str.len() > 0]
    n_candidate = len(candidates)
    n_fa_only = n_fa_pass - n_candidate
    tech_only = df[~df["fa_pass"] & (df["tech_breakout_20d"] | df["tech_ma_stacked"])]
    n_tech_only = len(tech_only)

    # CSV: exact column order, drop internal tech_fail_reason if present
    out_cols = [c for c in CSV_COLUMNS if c in df.columns]
    out_df = df[out_cols].copy()
    out_df.to_csv(out_dir / "candidates.csv", index=False)

    # JSON
    config = {
        "sales_yoy_min": 15,
        "roe_min": 15,
        "earnings_yoy_min": 20,
        "debt_to_equity_max": 1.5,
        "margin_yoy_min": 0,
        "require_earnings_accel": True,
        "tech_breakout_20d": True,
        "tech_ma_stacked": "ma5_gt_ma10_gt_ma20",
    }
    def _serialize(r: dict) -> dict:
        out = {}
        for k, v in r.items():
            if v is None or (isinstance(v, float) and (v != v)):
                out[k] = None
            elif isinstance(v, (pd.Timestamp,)):
                out[k] = str(v)[:10]
            elif isinstance(v, (float,)):
                out[k] = float(v)
            else:
                out[k] = v
        return out

    candidate_rows = out_df[out_df["tag"].str.len() > 0]
    records = [_serialize(r) for r in candidate_rows.replace({pd.NA: None}).to_dict(orient="records")]
    payload = {
        "asof_date": asof.strftime("%Y-%m-%d"),
        "config": config,
        "counts": {
            "universe": n_universe,
            "fa_pass": n_fa_pass,
            "candidate": n_candidate,
            "fa_only": n_fa_only,
            "tech_only": n_tech_only,
        },
        "candidates": records,
    }
    with (out_dir / "candidates.json").open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    # README
    tag_counts = candidates["tag"].value_counts()
    top10 = candidates.nlargest(10, "liquidity_adv20")[["symbol", "tag", "liquidity_adv20", "close", "fa_pass"]]
    readme_lines = [
        "# Minervini Candidate Filter — Report",
        "",
        "## What was screened",
        f"- **Universe**: {n_universe} symbols (watchlist or FA latest).",
        f"- **As-of date**: {asof.strftime('%Y-%m-%d')}.",
        "- **FA gate**: Mark-tight + earnings acceleration (sales_yoy≥15, roe≥15, earnings_yoy≥20, debt_to_equity≤1.5, earnings_accel).",
        "- **Tech gate**: breakout_20d OR ma5>ma10>ma20 (Phase 2 co-locked engines).",
        "",
        "## Counts",
        f"- Passed FA: **{n_fa_pass}**",
        f"- Candidates (FA + tech): **{n_candidate}**",
        f"- FA-only (no tech): **{n_fa_only}**",
        f"- Tech-only (no FA): **{n_tech_only}**",
        "",
        "## Candidates by tag",
        "",
    ]
    for tag, cnt in tag_counts.items():
        readme_lines.append(f"- {tag}: {int(cnt)}")
    readme_lines.extend([
        "",
        "## Top 10 candidates by liquidity_adv20 (VND)",
        "",
        "| symbol | tag | liquidity_adv20 | close |",
        "|--------|-----|-----------------|-------|",
    ])
    for _, r in top10.iterrows():
        liq = r.get("liquidity_adv20")
        liq_str = f"{liq:,.0f}" if pd.notna(liq) else "—"
        readme_lines.append(f"| {r['symbol']} | {r['tag']} | {liq_str} | {r.get('close', '—')} |")
    readme_lines.extend([
        "",
        "## Caveat",
        "Universe is watchlist_80 (or FA symbols) as of 2024; survivorship bias may apply.",
        "",
    ])
    (out_dir / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")

    # Console summary
    print(f"[Minervini Candidate Filter] asof={asof.strftime('%Y-%m-%d')}")
    print(f"  universe={n_universe}  fa_pass={n_fa_pass}  candidate={n_candidate}  fa_only={n_fa_only}  tech_only={n_tech_only}")
    print(f"  by tag: {tag_counts.to_dict()}")
    print(f"  Wrote: {out_dir / 'candidates.csv'}, candidates.json, README.md")
    if n_candidate > 0:
        print("  Top 10 candidates by liquidity_adv20:")
        for i, (_, r) in enumerate(top10.iterrows(), 1):
            liq = r.get("liquidity_adv20")
            liq_str = f"{liq:,.0f}" if pd.notna(liq) else "—"
            print(f"    {i}. {r['symbol']}  {r['tag']}  liquidity_adv20={liq_str}  close={r.get('close', '—')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
