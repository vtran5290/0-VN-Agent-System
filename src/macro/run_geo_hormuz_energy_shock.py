from __future__ import annotations

"""
CLI entrypoint for geo_hormuz_energy_shock layer.

Usage:
  python -m src.macro.run_geo_hormuz_energy_shock --input data/raw/geo_hormuz_energy_shock_inputs.json --out data/state/geo_hormuz_energy_shock.json --asof YYYY-MM-DD

- Inputs: JSON with either { "asof_date": "...", "inputs": { ... } } or bare inputs dict
  matching geo_hormuz_energy_shock.inputs schema.
- Output: dashboard-style JSON layer used by Cursor engine and agents.
"""

import argparse
import json
from pathlib import Path

from .geo_hormuz_energy_shock import REPO_ROOT, load_inputs, score

DEFAULT_OUT = REPO_ROOT / "data" / "state" / "geo_hormuz_energy_shock.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hormuz energy shock layer — score and write dashboard state"
    )
    parser.add_argument(
        "--input",
        default="data/raw/geo_hormuz_energy_shock_inputs.json",
        help="Inputs JSON path (root or {asof_date, inputs})",
    )
    parser.add_argument(
        "--asof",
        default=None,
        metavar="YYYY-MM-DD",
        help="As-of date (optional, falls back to inputs.asof_date)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output dashboard state JSON path (default: data/state/geo_hormuz_energy_shock.json)",
    )
    args = parser.parse_args()

    inp_path = Path(args.input) if Path(args.input).is_absolute() else REPO_ROOT / args.input
    if not inp_path.exists():
        print(f"[geo_hormuz] Input not found: {inp_path}")
        return

    raw_inputs = load_inputs(inp_path)
    asof = args.asof or str(raw_inputs.get("asof_date") or "")
    result = score(raw_inputs, asof=asof)

    out_path = (
        Path(args.out)
        if args.out and Path(args.out).is_absolute()
        else (REPO_ROOT / args.out if args.out else DEFAULT_OUT)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    st = result.get("state") or {}
    print(
        f"[geo_hormuz] asof={result.get('asof')} "
        f"risk_state={st.get('risk_state')} shock_mode={st.get('shock_mode')} "
        f"vn_inflation={st.get('inflation_risk_vn')} vn_supply={st.get('supply_disruption_risk_vn')} "
        f"sbv_constraint={st.get('sbv_policy_constraint')} "
        f"checklist={st.get('real_cycle_checklist', {}).get('hits')}/{st.get('real_cycle_checklist', {}).get('total')}({st.get('real_cycle_checklist', {}).get('classification')})"
    )
    print(f"[geo_hormuz] Wrote: {out_path}")


if __name__ == "__main__":
    main()

