# minervini_backtest/scripts/gate_attribution.py — Waterfall: delta expectancy_r / PF / trades per gate (2 universes)
"""
Layers: G0 TT+breakout → G1 +VDU → G2 +CS → G3 +VCP → G4 +close_strength → G5 +retest.
Universe A: VN30 / top liquidity (small list). Universe B: broad (80–200 symbols).
Output: waterfall with delta expectancy_r, delta PF, delta trades per gate.
Run: python minervini_backtest/scripts/gate_attribution.py [--universe A|B|both] [--fetch] [--out-dir]
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run import load_config, load_curated_data, fetch_fireant
from engine import run_backtest
from metrics import minervini_r_metrics

GATES = [
    ("G0_TT_breakout", {"setup": "none", "close_strength": False, "use_retest": False}),
    ("G1_+VDU", {"setup": "vdu_only", "close_strength": False, "use_retest": False}),
    ("G2_+CS", {"setup": "cs_only", "close_strength": False, "use_retest": False}),
    ("G3_+VCP", {"setup": "vcp", "close_strength": False, "use_retest": False}),
    ("G4_+close_strength", {"setup": "vcp", "close_strength": True, "use_retest": False}),
    ("G5_+retest", {"setup": "vcp", "close_strength": True, "use_retest": True}),
]


def _pf(ledger: pd.DataFrame) -> float | None:
    if ledger is None or ledger.empty:
        return None
    ret = ledger["ret"].astype(float)
    wins, losses = ret[ret > 0], ret[ret <= 0]
    if len(losses) and losses.sum() < 0 and len(wins):
        return float(wins.sum() / (-losses.sum()))
    return None


def run_waterfall(data: dict, base_cfg: dict, label: str = "") -> pd.DataFrame:
    rows = []
    prev_exp = prev_exp_r = prev_pf = prev_trades = None
    for name, overrides in GATES:
        cfg = {**base_cfg, **overrides}
        try:
            _, ledger = run_backtest(data, cfg)
        except Exception as e:
            rows.append({"gate": name, "trades": 0, "expectancy": None, "expectancy_r": None, "profit_factor": None,
                         "delta_exp": None, "delta_exp_r": None, "delta_pf": None, "delta_trades": None})
            continue
        if ledger.empty:
            rows.append({"gate": name, "trades": 0, "expectancy": None, "expectancy_r": None, "profit_factor": None,
                         "delta_exp": None, "delta_exp_r": None, "delta_pf": None, "delta_trades": None})
            prev_exp = prev_exp_r = prev_pf = None
            prev_trades = 0
            continue
        ret = ledger["ret"].astype(float)
        exp = round(ret.mean(), 4)
        r_metrics = minervini_r_metrics(ledger)
        exp_r = r_metrics.get("expectancy_r")
        pf = _pf(ledger)
        n = len(ledger)
        delta_exp = round(exp - prev_exp, 4) if prev_exp is not None else None
        if prev_exp_r is not None and exp_r == exp_r:
            delta_exp_r = round(float(exp_r) - float(prev_exp_r), 4)
        else:
            delta_exp_r = None
        delta_pf = round(pf - prev_pf, 4) if (pf is not None and prev_pf is not None) else None
        delta_trades = n - prev_trades if prev_trades is not None else None
        rows.append({
            "gate": name,
            "trades": n,
            "expectancy": exp,
            "expectancy_r": round(exp_r, 4) if exp_r == exp_r else None,
            "profit_factor": round(pf, 4) if pf is not None else None,
            "delta_exp": delta_exp,
            "delta_exp_r": delta_exp_r,
            "delta_pf": delta_pf,
            "delta_trades": delta_trades,
        })
        prev_exp = exp
        prev_exp_r = float(exp_r) if exp_r == exp_r else prev_exp_r
        prev_pf = pf
        prev_trades = n
    df = pd.DataFrame(rows)
    df["universe"] = label
    return df


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--universe", choices=["A", "B", "both"], default="both", help="A=VN30/top liquidity, B=broad")
    p.add_argument("--symbols", nargs="*", default=None, help="Override: use these symbols (no A/B split)")
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--out", "-o", default=None, help="Single CSV path (both universes concatenated)")
    p.add_argument("--out-dir", default=None, help="Directory for gate_attribution_A.csv, gate_attribution_B.csv")
    p.add_argument("--fee-bps", type=float, default=None, help="Realism: fee bps (e.g. 30); same as decision_matrix")
    p.add_argument("--min-hold", type=int, default=None, help="Realism: min_hold_bars (e.g. 3)")
    args = p.parse_args()

    all_data = load_curated_data(None)
    if not all_data and args.fetch:
        start = args.start or "2018-01-01"
        end = args.end or "2024-12-31"
        # Fetch a larger set for B; we'll split by list
        symbols_broad = args.symbols or ["MBB", "SSI", "VCI", "TCB", "FPT", "MWG", "VPB", "STB", "TCB", "ACB", "CTG", "BID", "VNM", "VHM", "GAS", "PLX", "POW", "SAB", "VNM", "HPG", "MSN", "VIC", "VRE", "NLG", "PDR", "VPB", "TPB", "OCB", "LPB", "HCM", "VND", "VCI", "SHS", "FTS", "VIX", "VND", "VOS", "VFS", "VGS", "VIB", "KLB", "DXS", "VOS"]
        for sym in symbols_broad[:50]:  # cap for fetch
            try:
                all_data[sym.upper()] = fetch_fireant(sym, start, end)
            except Exception as e:
                pass
    if not all_data:
        print("No data. Use --fetch or data/curated.")
        return 1

    if args.start or args.end:
        for sym in list(all_data):
            all_data[sym] = all_data[sym].copy().set_index("date")
            if args.start:
                all_data[sym] = all_data[sym].loc[args.start:]
            if args.end:
                all_data[sym] = all_data[sym].loc[:args.end]
            all_data[sym] = all_data[sym].reset_index()

    # Universe A: top liquidity (first N symbols or VN30-style list). B: rest / all.
    if args.symbols:
        data_a = {k: all_data[k] for k in args.symbols if k in all_data}
        data_b = data_a
    else:
        syms = list(all_data.keys())
        # A = first 10–15 (proxy for "VN30/top liquidity"); B = all
        n_a = min(15, len(syms))
        data_a = {s: all_data[s] for s in syms[:n_a]}
        data_b = all_data

    base_cfg = load_config("M1")
    if getattr(args, "fee_bps", None) is not None:
        base_cfg["fee_bps"] = args.fee_bps
    if getattr(args, "min_hold", None) is not None:
        base_cfg["min_hold_bars"] = args.min_hold
    out_dir = Path(args.out_dir) if args.out_dir else ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []

    if args.universe in ("A", "both") and data_a:
        df_a = run_waterfall(data_a, base_cfg, label="A_VN30_top_liquidity")
        frames.append(df_a)
        print("=== Universe A (VN30 / top liquidity) ===\n")
        print(df_a.to_string(index=False))
        if args.out_dir or args.universe == "A":
            df_a.to_csv(out_dir / "gate_attribution_A.csv", index=False)
            print(f"Wrote: {out_dir / 'gate_attribution_A.csv'}\n")

    if args.universe in ("B", "both") and data_b:
        df_b = run_waterfall(data_b, base_cfg, label="B_broad")
        frames.append(df_b)
        print("=== Universe B (broad) ===\n")
        print(df_b.to_string(index=False))
        if args.out_dir or args.universe == "B":
            df_b.to_csv(out_dir / "gate_attribution_B.csv", index=False)
            print(f"Wrote: {out_dir / 'gate_attribution_B.csv'}\n")

    if frames:
        combined = pd.concat(frames, ignore_index=True)
        out_path = Path(args.out) if args.out else ROOT / "gate_attribution_waterfall.csv"
        combined.to_csv(out_path, index=False)
        print(f"Combined: {out_path}")
    print("\nInterpretation: largest delta_exp_r / delta_pf = gate that adds edge. TT-only (G0) vs retest (G5) vs VCP (G3).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
