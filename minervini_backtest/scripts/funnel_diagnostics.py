# minervini_backtest/scripts/funnel_diagnostics.py -- Funnel counts by gate (TT / setup / trigger / retest / entries / exits)
"""
Output: per version, per universe, counts TT_pass, setup_pass, trigger_pass, retest_pass, entries, exits
so we can see where trades are killed (realism: fee=30, min_hold=3).
Run: python minervini_backtest/scripts/funnel_diagnostics.py [--versions M4 M9] [--universe A|B|both] [--fetch] [--out]
"""
from __future__ import annotations
import sys
from pathlib import Path
import argparse
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run import load_config, load_curated_data, fetch_fireant, _merge_regime
from engine import run_single_symbol

DEFAULT_VERSIONS = ["M4", "M9"]
REALISM_OVERRIDE = {"fee_bps": 30, "min_hold_bars": 3}


def run_funnel_one_version(
    data: dict[str, pd.DataFrame],
    version: str,
    cfg_override: dict,
) -> dict:
    """Run backtest with collect_funnel=True; aggregate funnel counts across symbols."""
    cfg = load_config(version)
    cfg.update(cfg_override)
    data = _merge_regime(data, cfg)
    agg = {"tt_pass": 0, "setup_pass": 0, "trigger_pass": 0, "retest_pass": 0, "entries": 0, "exits": 0}
    for sym, df in data.items():
        try:
            result = run_single_symbol(df, cfg, symbol=sym, collect_funnel=True)
            if len(result) == 3:
                _, _, funnel = result
                for k in agg:
                    agg[k] += funnel.get(k, 0)
        except Exception:
            continue
    return agg


def main():
    p = argparse.ArgumentParser(description="Funnel diagnostics: TT / setup / trigger / retest / entries / exits")
    p.add_argument("--versions", nargs="+", default=DEFAULT_VERSIONS, help="Configs e.g. M4 M9")
    p.add_argument("--universe", choices=["A", "B", "both"], default="A", help="A=VN30/top liquidity, B=broad")
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--out", "-o", default=None, help="Output CSV path")
    p.add_argument("--fee-bps", type=float, default=30, help="Override fee_bps (default 30)")
    p.add_argument("--min-hold", type=int, default=3, help="Override min_hold_bars (default 3)")
    args = p.parse_args()

    all_data = load_curated_data(None)
    if not all_data and args.fetch:
        start = args.start or "2018-01-01"
        end = args.end or "2026-12-31"
        watchlist_path = ROOT.parent / "config" / "watchlist.txt"
        tickers = []
        if watchlist_path.exists():
            tickers = [ln.strip() for ln in watchlist_path.read_text(encoding="utf-8").strip().splitlines() if ln.strip()]
        if not tickers:
            tickers = ["VN30", "MBB", "SSI", "VCI", "TCB", "FPT", "MWG", "VPB", "STB", "ACB", "CTG", "BID", "VNM", "VHM", "HPG", "MSN", "VIC"]
        for sym in tickers[:50]:
            try:
                all_data[sym.upper()] = fetch_fireant(sym, start, end)
            except Exception:
                pass
    if not all_data:
        print("No data. Use data/curated or --fetch.")
        return 1

    if args.start or args.end:
        for sym in list(all_data):
            all_data[sym] = all_data[sym].copy().set_index("date")
            if args.start:
                all_data[sym] = all_data[sym].loc[args.start:]
            if args.end:
                all_data[sym] = all_data[sym].loc[:args.end]
            all_data[sym] = all_data[sym].reset_index()

    override = {"fee_bps": args.fee_bps, "min_hold_bars": args.min_hold}
    syms = list(all_data.keys())
    n_a = min(15, len(syms))
    data_a = {s: all_data[s] for s in syms[:n_a]}
    data_b = all_data

    rows = []
    for version in args.versions:
        try:
            _ = load_config(version)
        except FileNotFoundError:
            print(f"[skip] Config not found: {version}")
            continue
        for label, data in [("A_VN30_top_liquidity", data_a), ("B_broad", data_b)]:
            if args.universe == "A" and "B_" in label:
                continue
            if args.universe == "B" and "A_" in label:
                continue
            agg = run_funnel_one_version(data, version, override)
            rows.append({
                "version": version,
                "universe": label,
                "tt_pass": agg["tt_pass"],
                "setup_pass": agg["setup_pass"],
                "trigger_pass": agg["trigger_pass"],
                "retest_pass": agg["retest_pass"],
                "entries": agg["entries"],
                "exits": agg["exits"],
            })

    df = pd.DataFrame(rows)
    print("Funnel (fee=%s bps, min_hold=%s):" % (override["fee_bps"], override["min_hold_bars"]))
    print(df.to_string(index=False))

    out_path = Path(args.out) if args.out else ROOT / "funnel_diagnostics.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print("\nWrote: %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
