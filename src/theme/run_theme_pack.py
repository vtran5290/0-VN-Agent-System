# src/theme/run_theme_pack.py — CLI for ThemePack ranker
"""
Run ThemePack pre-filter. Produces:
  1) data/raw/candidates/ai_energy_overspill_candidates.csv (symbol,tier,total_score,lane,flags)
  2) data/features/theme_scores/ai_energy_overspill_scores_YYYYMMDD.csv (full scored table)
Backtest consumes via: --candidates data/raw/candidates/ai_energy_overspill_candidates.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .loaders import load_fundamentals, load_pack_config, load_watchlist
from .features import build_component_df
from .scorer import score_and_flag
from .export import write_candidates_csv, write_scores_csv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="ThemePack ranker: AI_Energy_Overspill_VN")
    parser.add_argument("--pack", default="config/theme_packs/ai_energy_theme_pack_v1.json", help="Path to theme pack JSON")
    parser.add_argument("--asof", required=True, metavar="YYYY-MM-DD", help="As-of date for output filenames")
    parser.add_argument("--watchlist", default=None, help="Optional watchlist path (else config/watchlist.txt)")
    parser.add_argument("--fundamentals", default=None, help="Fundamentals CSV (default data/sources/company/fundamentals_snapshot.csv)")
    parser.add_argument("--topk", type=int, default=None, help="Optional: keep only top K by total_score (before writing)")
    parser.add_argument("--pack-id", default="ai_energy_overspill", help="Output file prefix")
    args = parser.parse_args()

    pack_path = Path(args.pack) if Path(args.pack).is_absolute() else REPO_ROOT / args.pack
    if not pack_path.exists():
        print(f"[theme] Pack not found: {pack_path}")
        return
    cfg = load_pack_config(pack_path)

    fundamentals_path = Path(args.fundamentals) if args.fundamentals else REPO_ROOT / "data" / "sources" / "company" / "fundamentals_snapshot.csv"
    df = load_fundamentals(fundamentals_path)
    if df.empty:
        print("[theme] No fundamentals loaded; empty output.")
        return

    if args.watchlist:
        wl_path = Path(args.watchlist) if Path(args.watchlist).is_absolute() else REPO_ROOT / args.watchlist
        symbols = load_watchlist(wl_path, REPO_ROOT)
        if symbols:
            df = df[df["symbol"].str.upper().isin(symbols)].copy()
    if df.empty:
        print("[theme] No rows after watchlist filter.")
        return

    df = build_component_df(df, cfg)
    df = score_and_flag(df, cfg, lane_per_symbol=None)

    if args.topk is not None and args.topk > 0:
        df = df.nlargest(args.topk, "total_score").copy()

    path_candidates = write_candidates_csv(df, args.asof, args.pack_id)
    path_scores = write_scores_csv(df, args.asof, args.pack_id)

    n = len(df)
    top10 = df.nlargest(10, "total_score")[["symbol", "tier", "total_score", "lane"]].to_string(index=False)
    exploded = df["flags"].str.split("|").explode()
    flag_counts = exploded[exploded.str.len() > 0].value_counts()
    flag_str = flag_counts.to_string() if not flag_counts.empty else "none"

    print(f"[theme] n_symbols={n}")
    print(f"[theme] top10:\n{top10}")
    print(f"[theme] flag counts:\n{flag_str}")
    print(f"[theme] Wrote: {path_candidates}")
    print(f"[theme] Wrote: {path_scores}")


if __name__ == "__main__":
    main()
