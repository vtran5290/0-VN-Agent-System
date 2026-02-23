# minervini_backtest/scripts/deploy_candidate_selection.py — Pick core deploy: M4 vs M3 @ fee=30 & min_hold=3
"""
Logic: If M4 survives fee=30 & min_hold=3 better than M3 → M4 core. Else M3 core, M4 as confirmation.
Reads decision_matrix.csv (or runs decision_matrix) and prints recommendation.
Run: python minervini_backtest/scripts/deploy_candidate_selection.py [--matrix-csv path] [--fetch]
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--matrix-csv", default=None, help="Path to decision_matrix.csv (else run decision_matrix)")
    p.add_argument("--fetch", action="store_true", help="Run decision_matrix with --fetch first")
    args = p.parse_args()

    csv_path = Path(args.matrix_csv) if args.matrix_csv else ROOT / "decision_matrix.csv"
    if not csv_path.exists() or args.fetch:
        import subprocess
        cmd = [sys.executable, str(ROOT / "scripts" / "decision_matrix.py")]
        if args.fetch:
            cmd.append("--fetch")
        subprocess.run(cmd, cwd=str(ROOT.parent), timeout=300)
        csv_path = ROOT / "decision_matrix.csv"

    if not csv_path.exists():
        print("Run decision_matrix.py first (or use --fetch).")
        return 1

    df = pd.read_csv(csv_path)
    real = df[(df["realism"] == True) & (df["setting"] == "fee30_minhold3")]
    m3 = real[real["version"] == "M3"]
    m4 = real[real["version"] == "M4"]

    def _exp_r(r):
        if r.empty:
            return None
        v = r["expectancy_r"].iloc[0]
        return float(v) if v == v else None

    def _pf(r):
        if r.empty:
            return None
        v = r["profit_factor"].iloc[0]
        return float(v) if v is not None and v == v else None

    def _pass(r):
        if r.empty:
            return False
        return bool(r["pass_realism"].iloc[0])

    exp3, exp4 = _exp_r(m3), _exp_r(m4)
    pf3, pf4 = _pf(m3), _pf(m4)
    pass3, pass4 = _pass(m3), _pass(m4)

    print("=== Deploy candidate (fee=30 bps, min_hold=3) ===\n")
    print(f"M3: expectancy_r={exp3}  PF={pf3}  pass_realism={pass3}")
    print(f"M4: expectancy_r={exp4}  PF={pf4}  pass_realism={pass4}\n")

    if pass4 and (not pass3 or (exp4 is not None and exp3 is not None and exp4 >= exp3)):
        print("→ M4 as CORE (retest reduces false breakout; survives realism).")
        print("  Use M3 as optional confirmation or for burst-heavy regimes.")
    elif pass3:
        print("→ M3 as CORE (3WT + partial + trail survives realism).")
        print("  Use M4 as confirmation filter when break-fail is frequent.")
    else:
        print("→ Neither M3 nor M4 passes realism. Check Gross-only / Noise; tune or add regime gate (M11).")

    print("\nNext: run deploy_gates_check.py for D1/D2/D3 before final deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
