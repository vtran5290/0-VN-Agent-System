# minervini_backtest/scripts/deploy_gates_check.py — Deploy Gates D1/D2/D3 (khóa deploy, không tranh luận)
"""
D1 — Walk-forward stability: 2023 validate & 2024 holdout both expectancy_r > 0, not too different.
D2 — Concentration control: top10_pct_pnl < 60% on holdout.
D3 — Realism survives: fee=30 + min_hold=3 pass (or near: PF 1.05–1.10 with expectancy_r > 0.10).
If any fail → do not deploy, iterate.
Requires: walk_forward_results.csv (with --realism --versions M3 M4) and decision_matrix.csv.
Run: python minervini_backtest/scripts/deploy_gates_check.py [--wf-csv path] [--matrix-csv path]
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent

# Thresholds
EXP_R_MIN = 0.0       # D1: both val and holdout > 0
EXP_R_DRIFT_MAX = 0.5 # D1: abs(val - holdout) not huge (optional: ratio)
TOP10_MAX = 0.60     # D2: holdout top10_pct_pnl < 60%
PF_REALISM_MIN = 1.05 # D3: PF @ fee30 minhold3 at least 1.05
EXP_R_REALISM_MIN = 0.10  # D3: and expectancy_r > 0.10 to consider


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--wf-csv", "--walk-forward", dest="wf_csv", default=None, help="walk_forward_results.csv (with version, expectancy_r, top10_pct_pnl)")
    p.add_argument("--matrix-csv", "--matrix", dest="matrix_csv", default=None, help="decision_matrix.csv")
    args = p.parse_args()

    wf_path = Path(args.wf_csv) if args.wf_csv else ROOT / "walk_forward_results.csv"
    matrix_path = Path(args.matrix_csv) if args.matrix_csv else ROOT / "decision_matrix.csv"

    print("=== Deploy Gates (D1/D2/D3) ===\n")

    wf = None
    if wf_path.exists():
        wf = pd.read_csv(wf_path)

    # D1: Walk-forward stability
    if wf is None:
        print("D1: SKIP (no walk_forward_results.csv). Run: walk_forward.py --realism --versions M3 M4 [--fetch]")
        d1_ok = None
    elif "version" not in wf.columns or "expectancy_r" not in wf.columns:
        print("D1: SKIP (CSV missing version or expectancy_r). Re-run walk_forward with --realism --versions M3 M4.")
        d1_ok = None
    else:
        d1_ok = True
        for ver in wf["version"].unique():
            sub = wf[wf["version"] == ver]
            val = sub[sub["split"] == "validate"]
            hold = sub[sub["split"] == "holdout"]
            er_val = val["expectancy_r"].iloc[0] if len(val) and "expectancy_r" in val.columns else None
            er_hold = hold["expectancy_r"].iloc[0] if len(hold) and "expectancy_r" in hold.columns else None
            if er_val is not None and pd.notna(er_val):
                er_val = float(er_val)
            else:
                er_val = None
            if er_hold is not None and pd.notna(er_hold):
                er_hold = float(er_hold)
            else:
                er_hold = None
            both_positive = (er_val is not None and er_val > EXP_R_MIN) and (er_hold is not None and er_hold > EXP_R_MIN)
            if not both_positive:
                d1_ok = False
            print(f"  D1 {ver}: validate expectancy_r={er_val}  holdout expectancy_r={er_hold}  both>0={both_positive}")
        print(f"  D1 overall: {'PASS' if d1_ok else 'FAIL'}\n")

    # D2: Concentration on holdout
    if wf is None or "top10_pct_pnl" not in wf.columns:
        print("D2: SKIP (no top10_pct_pnl in walk_forward). Re-run walk_forward with --realism.")
        d2_ok = None
    else:
        holdout = wf[wf["split"] == "holdout"]
        d2_ok = True
        for ver in holdout["version"].unique() if "version" in holdout.columns else []:
            top10 = holdout[holdout["version"] == ver]["top10_pct_pnl"].iloc[0]
            if top10 is not None and top10 == top10 and top10 >= TOP10_MAX:
                d2_ok = False
            ok = top10 is None or (top10 != top10) or top10 < TOP10_MAX
            print(f"  D2 {ver} holdout top10_pct_pnl={top10}  <{TOP10_MAX}={ok}")
        print(f"  D2 overall: {'PASS' if d2_ok else 'FAIL'}\n")

    # D3: Realism survives
    if not matrix_path.exists():
        print("D3: SKIP (no decision_matrix.csv). Run decision_matrix.py [--fetch]")
        d3_ok = None
    else:
        dm = pd.read_csv(matrix_path)
        real = dm[(dm["realism"] == True) & (dm["setting"] == "fee30_minhold3")]
        # Consider pass if PF >= 1.05 and expectancy_r >= 0.10 for at least one candidate (M3/M4)
        candidates = real[real["version"].isin(["M3", "M4"])]
        d3_ok = False
        for _, row in candidates.iterrows():
            pf = row.get("profit_factor")
            er = row.get("expectancy_r")
            if pf is not None and pd.notna(pf) and er is not None and pd.notna(er):
                if float(pf) >= PF_REALISM_MIN and float(er) >= EXP_R_REALISM_MIN:
                    d3_ok = True
                    print(f"  D3 {row['version']}: PF={pf}  expectancy_r={er}  PASS (>= {PF_REALISM_MIN} & exp_r >= {EXP_R_REALISM_MIN})")
                else:
                    print(f"  D3 {row['version']}: PF={pf}  expectancy_r={er}  (below threshold)")
        if not d3_ok:
            print("  D3: No candidate (M3/M4) passes PF>=1.05 and expectancy_r>=0.10 @ fee30 minhold3.")
        print(f"  D3 overall: {'PASS' if d3_ok else 'FAIL'}\n")

    deploy_ok = (d1_ok is not False) and (d2_ok is not False) and (d3_ok is True)
    print("---")
    if deploy_ok and (d1_ok is True and d2_ok is True):
        print("DEPLOY GATES PASSED. Proceed to deploy candidate selection.")
    else:
        print("DO NOT DEPLOY (fail or skip). Iterate: I2 (M4+M10) / I1 (M9+M6) / I3 (M7 risk rescue).")
    return 0 if deploy_ok else 1


if __name__ == "__main__":
    sys.exit(main())
