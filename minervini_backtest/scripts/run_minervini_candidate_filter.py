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
    debug_fa_gate_snapshot,
)


CSV_COLUMNS = [
    "asof_date", "symbol",
    "fa_pass", "fa_fail_reasons",
    "sales_yoy", "earnings_yoy", "roe", "debt_to_equity", "margin_yoy", "eps_yoy", "earnings_accel_flag",
    "tech_breakout_20d", "tech_ma_stacked", "tech_both",
    "close", "ma5", "ma10", "ma20", "high20",
    "liquidity_adv20", "volume", "vol_med20",
    "rs_3m", "rs_6m", "rs_3m_pct", "rs_6m_pct", "pass_rs",
    "tier", "tag", "tier_mark",
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
    ap.add_argument(
        "--tier-mark",
        default="S",
        choices=["S", "A2", "A3", "A4"],
        help=(
            "FA Mark tier: 'S' (Mark-tight), 'A2' (loosened earnings_yoy floor), "
            "'A3' (ROE/debt/margin as soft flags), or 'A4' (soften debt_to_equity only)."
        ),
    )
    ap.add_argument(
        "--debug-fa",
        action="store_true",
        help="If set, write FA gate debug snapshot CSV and print diagnostics (no change to Tier logic).",
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

    # Universe: --watchlist override, else prefer universe_186.txt then watchlist_80.txt then watchlist.txt
    if args.watchlist:
        watchlist_path = Path(args.watchlist)
    else:
        watchlist_path = ROOT.parent / "config" / "universe_186.txt"
        if not watchlist_path.exists():
            watchlist_path = ROOT.parent / "config" / "watchlist_80.txt"
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
    df = run_candidate_screen(fa_latest, price_data, asof, tier_mark=args.tier_mark)

    # Counts: Tier A = actionable (FA + tech + RS), Tier W = watchlist (W1: FA pass only, no timing)
    n_universe = len(df)
    n_fa_pass = int(df["fa_pass"].sum())
    tier_a = df[df["tier"] == "A"]
    tier_w = df[df["tier"] == "W"]
    n_candidate = len(tier_a)
    n_watchlist = len(tier_w)
    candidates = tier_a
    n_fa_only = n_fa_pass - n_candidate - n_watchlist
    tech_only = df[~df["fa_pass"] & (df["tech_breakout_20d"] | df["tech_ma_stacked"])]
    n_tech_only = len(tech_only)

    # Price coverage: present / missing / insufficient history
    n_universe_total = n_universe
    n_price_present = sum(1 for s in df["symbol"] if s in price_data and price_data.get(s) is not None and not price_data[s].empty)
    n_price_missing = n_universe_total - n_price_present
    # Insufficient: has price but cannot compute features at asof (< 21 bars)
    n_price_insufficient_history = 0
    if "high20" in df.columns:
        for _, row in df.iterrows():
            sym = row["symbol"]
            if sym in price_data and price_data.get(sym) is not None and not price_data[sym].empty:
                if pd.isna(row.get("high20")):
                    n_price_insufficient_history += 1
    coverage = {
        "n_universe_total": int(n_universe_total),
        "n_price_present": int(n_price_present),
        "n_price_missing": int(n_price_missing),
        "n_price_insufficient_history": int(n_price_insufficient_history),
    }

    # CSV: exact column order, drop internal tech_fail_reason if present
    out_cols = [c for c in CSV_COLUMNS if c in df.columns]
    out_df = df[out_cols].copy()
    out_df.to_csv(out_dir / "candidates.csv", index=False)

    # Optional FA debug snapshot (facts-only; does not change Tier logic)
    if args.debug_fa:
        debug_df = debug_fa_gate_snapshot(
            fa_latest=load_fa_latest_per_symbol(fa_path),
            universe=universe,
            tier_mark_S="S",
            tier_mark_A2="A2",
        )
        debug_path = out_dir / f"debug_fa_snapshot_{asof.strftime('%Y%m%d')}.csv"
        debug_df.to_csv(debug_path, index=False)
        pass_S = int(debug_df["pass_S"].sum())
        pass_A2 = int(debug_df["pass_A2"].sum())
        only_earnings = int(debug_df["flag_only_earnings_floor"].sum())
        print(f"[FA Debug] pass_S={pass_S}  pass_A2={pass_A2}  pass_A2_only_earnings_floor={only_earnings}")
        # Top 10 fail reasons for S
        all_reasons = []
        for r in debug_df["fail_reasons_S"]:
            if not isinstance(r, str) or not r:
                continue
            all_reasons.extend([x.strip() for x in r.split(";") if x.strip()])
        if all_reasons:
            s = pd.Series(all_reasons).value_counts().head(10)
            print("[FA Debug] Top 10 fail reasons (Tier S):")
            for reason, cnt in s.items():
                print(f"  {reason}: {int(cnt)}")
        print(f"[FA Debug] Wrote snapshot to {debug_path}")

    # JSON
    config = {
        "sales_yoy_min": 15,
        "roe_min": 15,
        "earnings_yoy_min": 20,
        "debt_to_equity_max": 1.5,
        "margin_yoy_min": 0,
        "require_earnings_accel": True,
        "earnings_accel_2step_when_high": True,
        "profit_positive_guard": True,
        "tech_breakout_20d": True,
        "tech_ma_stacked": "ma5_gt_ma10_gt_ma20",
        "rs_3m_gate": "RS_3M > 0 or top 20%",
        "tier_mark": args.tier_mark,
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

    candidate_rows = out_df[out_df["tier"] == "A"]
    records = [_serialize(r) for r in candidate_rows.replace({pd.NA: None}).to_dict(orient="records")]
    payload = {
        "asof_date": asof.strftime("%Y-%m-%d"),
        "config": config,
        "counts": {
            "universe": n_universe,
            "fa_pass": n_fa_pass,
            "tier_a_actionable": n_candidate,
            "tier_w_watchlist": n_watchlist,
            "fa_only": n_fa_only,
            "tech_only": n_tech_only,
        },
        "coverage": coverage,
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
        "- **FA gate**: VN FA leadership (Mark-inspired): sales_yoy≥15, roe≥15, earnings_yoy≥20, debt≤1.5, earnings accel (2-step when high else 1-step), profit_positive.",
        "- **Tech gate**: breakout_20d OR ma5>ma10>ma20 (Phase 2 co-locked).",
        "- **RS gate**: RS_3M > 0 or top 20% (stock 63d return vs VNINDEX).",
        "- **RS percentile**: rs_3m_pct, rs_6m_pct = rank in universe (0–100, 100=strongest); use for watchlist strength.",
        "",
        "## Counts",
        f"- Passed FA: **{n_fa_pass}**",
        f"- **Tier A (actionable)**: FA + tech (tag non-empty) — **{n_candidate}**",
        f"- **Tier W (watchlist)**: FA pass only, no timing — **{n_watchlist}**",
        f"- FA-only (no tech): **{n_fa_only}**",
        f"- Tech-only (no FA): **{n_tech_only}**",
        "",
        "## Candidates by tag (Tier A only)",
        "",
    ]
    for tag, cnt in tag_counts.items():
        readme_lines.append(f"- {tag}: {int(cnt)}")
    if n_watchlist > 0:
        readme_lines.append("")
        readme_lines.append("## Tier W (watchlist) — FA pass only, chờ timing")
        w_cols = ["symbol", "rs_3m", "rs_3m_pct", "rs_6m_pct", "liquidity_adv20", "close"]
        w_cols = [c for c in w_cols if c in tier_w.columns]
        top_w = tier_w.nlargest(10, "liquidity_adv20")[w_cols]
        readme_lines.append("| symbol | rs_3m | rs_3m_pct | rs_6m_pct | liquidity_adv20 | close |")
        readme_lines.append("|--------|-------|-----------+-----------+-----------------|-------|")
        for _, r in top_w.iterrows():
            liq = r.get("liquidity_adv20")
            liq_str = f"{liq:,.0f}" if pd.notna(liq) else "—"
            rs = r.get("rs_3m")
            rs_str = f"{rs:.4f}" if pd.notna(rs) else "—"
            p3 = r.get("rs_3m_pct")
            p6 = r.get("rs_6m_pct")
            p3_str = f"{p3:.0f}" if pd.notna(p3) else "—"
            p6_str = f"{p6:.0f}" if pd.notna(p6) else "—"
            readme_lines.append(f"| {r['symbol']} | {rs_str} | {p3_str} | {p6_str} | {liq_str} | {r.get('close', '—')} |")
    readme_lines.extend([
        "",
        "## Top 10 Tier A (actionable) by liquidity_adv20 (VND)",
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
    print(f"  universe={n_universe}  fa_pass={n_fa_pass}  tier_A={n_candidate}  tier_W={n_watchlist}  fa_only={n_fa_only}  tech_only={n_tech_only}")
    print(f"  coverage: present={coverage['n_price_present']}  missing={coverage['n_price_missing']}  insufficient_history={coverage['n_price_insufficient_history']}")
    fa_pass_df = df[df["fa_pass"]]
    if len(fa_pass_df) > 0 and "rs_3m_pct" in df.columns and "rs_6m_pct" in df.columns:
        p3 = fa_pass_df["rs_3m_pct"].dropna()
        p6 = fa_pass_df["rs_6m_pct"].dropna()
        med_3 = float(p3.median()) if len(p3) > 0 else None
        med_6 = float(p6.median()) if len(p6) > 0 else None
        def _top_label(p: float | None) -> str:
            if p is None or pd.isna(p):
                return "—"
            if p >= 50:
                return f"top {100 - p:.0f}%"
            return f"bottom {100 - p:.0f}%"
        print(f"  FA-pass RS: 3m median pct={med_3:.1f} ({_top_label(med_3)}), 6m median pct={med_6:.1f} ({_top_label(med_6)})  [100=strongest]")
    tag_dict = {k: int(v) for k, v in tag_counts.to_dict().items()}
    print(f"  by tag: {tag_dict}")
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
