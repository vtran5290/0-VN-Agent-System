# minervini_backtest/scripts/decision_layer_from_outputs.py — Decision layer từ decision_matrix + gate waterfall
"""
Đọc decision_matrix.csv và gate_attribution_A/B (waterfall) → in bản nháp Decision layer:
  Survivors (1 core + 1 backup + 1 experimental)
  Top 3 actions (deploy / sweep / refactor)
  Top 3 risks (edge source, concentration, regime dependency)
  Watchlist update (version dùng cho scan hàng tuần)
Run: python minervini_backtest/scripts/decision_layer_from_outputs.py [--matrix path] [--gate-a path] [--gate-b path]
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def _first_available(*paths: Path) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def infer_thesis(gate_a: pd.DataFrame, gate_b: pd.DataFrame) -> str:
    """T1=TT/regime, T2=retest, T3=VCP. Dựa vào gate có |delta_exp_r| hoặc |delta_pf| lớn nhất."""
    if gate_a is None or gate_a.empty:
        return "T? (no gate data)"
    df = gate_a.copy()
    if "delta_exp_r" not in df.columns and "delta_pf" not in df.columns:
        return "T? (no delta columns)"
    if "delta_exp_r" in df.columns:
        df["_abs_dr"] = pd.to_numeric(df["delta_exp_r"], errors="coerce").abs()
    else:
        df["_abs_dr"] = pd.to_numeric(df["delta_pf"], errors="coerce").abs()
    df = df.dropna(subset=["_abs_dr"])
    if df.empty:
        return "T? (no deltas)"
    idx = df["_abs_dr"].idxmax()
    if pd.isna(idx):
        return "T?"
    gate_name = df.loc[idx, "gate"] if "gate" in df.columns else ""
    g = str(gate_name)
    if "G0" in g or "TT_breakout" in g:
        return "T1 (edge from TT/regime)"
    if "G5" in g or "retest" in g.lower():
        return "T2 (edge from retest)"
    if "G3" in g or "G4" in g or "VCP" in g:
        return "T3 (edge from VCP/close strength)"
    return "T? (check waterfall manually)"


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--matrix", "-m", default=None)
    p.add_argument("--gate-a", default=None)
    p.add_argument("--gate-b", default=None)
    args = p.parse_args()

    matrix_path = _first_available(
        Path(args.matrix) if args.matrix else None,
        ROOT / "decision_matrix.csv",
    )
    gate_a_path = _first_available(
        Path(args.gate_a) if args.gate_a else None,
        ROOT / "gate_attribution_A.csv",
    )
    gate_b_path = _first_available(
        Path(args.gate_b) if args.gate_b else None,
        ROOT / "gate_attribution_B.csv",
    )

    real = None
    survivors = []
    if matrix_path and matrix_path.exists():
        dm = pd.read_csv(matrix_path)
        real = dm[(dm["realism"] == True) & (dm["setting"] == "fee30_minhold3")]
        if not real.empty:
            for _, row in real.iterrows():
                if row.get("pass_realism") == True or (row.get("group") == "Survivors"):
                    survivors.append(row["version"])
            # Dedupe, keep order
            seen = set()
            survivors = [x for x in survivors if not (x in seen or seen.add(x))]
        if not survivors and "group" in dm.columns:
            survivors = list(dm[dm["group"] == "Survivors"]["version"].unique())

    gate_a_df = pd.read_csv(gate_a_path) if gate_a_path and gate_a_path.exists() else None
    gate_b_df = pd.read_csv(gate_b_path) if gate_b_path and gate_b_path.exists() else None
    gate_a = gate_a_df if gate_a_df is not None and not gate_a_df.empty else pd.DataFrame()
    gate_b = gate_b_df if gate_b_df is not None and not gate_b_df.empty else pd.DataFrame()
    thesis = infer_thesis(gate_a, gate_b)

    # Build decision layer text
    lines = [
        "# Decision layer (from decision_matrix + gate waterfall)",
        "",
        "## Core thesis (from gate waterfall)",
        thesis,
        "",
        "## Survivors (fee=30, min_hold=3)",
        "- **Core:** " + (survivors[0] if survivors else "[chọn 1 từ Survivors]"),
        "- **Backup:** " + (survivors[1] if len(survivors) > 1 else "[chọn 1 backup]"),
        "- **Experimental:** " + (survivors[2] if len(survivors) > 2 else "M9/M10/M11 tùy thesis"),
        "",
        "## Top 3 actions",
        "1. [ ] Deploy: run scanner (Tier A) với core version; Tier B checklist 5 phút/mã",
        "2. [ ] Sweep: (nếu chưa survivor) I1 M9+M6 / I2 M4+M10 / I3 M7+M4",
        "3. [ ] Refactor: (nếu T1) simplify VCP to soft filter; (nếu T2) tune retest window",
        "",
        "## Top 3 risks",
        "1. **Edge source:** " + ("confirm from waterfall (see thesis above)" if thesis.startswith("T") else "run gate_attribution to confirm"),
        "2. **Concentration:** top10_pct_pnl < 60% on holdout (run deploy_gates_check D2)",
        "3. **Regime dependency:** val/holdout both exp_r>0 (run deploy_gates_check D1); consider M11",
        "",
        "## Watchlist update",
        "Scan hàng tuần: version **" + (survivors[0] if survivors else "M4 or M3") + "** (core). Backup for confirmation: " + (survivors[1] if len(survivors) > 1 else "M4 or M3") + ".",
        "",
    ]

    out = "\n".join(lines)
    out_path = ROOT / "decision_layer_draft.md"
    Path(out_path).write_text(out, encoding="utf-8")
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
