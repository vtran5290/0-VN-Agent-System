# src/macro/run_us_fiscal_stress.py — CLI: load inputs, score, write dashboard state
"""
Run US Fiscal Stress pack. Outputs engine-facing dashboard state for Fed Dashboard / rotation.
Usage:
  python -m src.macro.run_us_fiscal_stress --pack config/macro_packs/us_fiscal_stress_pack_v1.json --input data/raw/us_fiscal_stress_inputs.json --out data/state/us_fiscal_stress.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .us_fiscal_stress import load_pack, load_inputs, score, REPO_ROOT

DEFAULT_OUT = REPO_ROOT / "data" / "state" / "us_fiscal_stress.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="US Fiscal Stress Regime Pack — score and write dashboard state")
    parser.add_argument("--pack", default="config/macro_packs/us_fiscal_stress_pack_v1.json", help="Pack config JSON")
    parser.add_argument("--input", default="data/raw/us_fiscal_stress_inputs.json", help="Inputs JSON (inputs key or root)")
    parser.add_argument("--asof", default=None, metavar="YYYY-MM-DD", help="As-of date (optional, for output)")
    parser.add_argument("--out", default=None, help="Output dashboard state JSON path")
    args = parser.parse_args()

    pack_path = Path(args.pack) if Path(args.pack).is_absolute() else REPO_ROOT / args.pack
    if not pack_path.exists():
        print(f"[us_fiscal_stress] Pack not found: {pack_path}")
        return

    inp_path = Path(args.input) if Path(args.input).is_absolute() else REPO_ROOT / args.input
    inputs = load_inputs(inp_path)
    pack = load_pack(pack_path)

    # If input file has full pack structure, use its inputs; else use root as inputs
    if not inputs and inp_path.exists():
        with open(inp_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        inputs = raw.get("inputs", raw)

    result = score(inputs, pack)

    out_path = Path(args.out) if args.out and Path(args.out).is_absolute() else (REPO_ROOT / args.out if args.out else DEFAULT_OUT)
    out_path = out_path or DEFAULT_OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "asof_date": args.asof or pack.get("asof_date", ""),
        "pack_name": pack.get("pack_name", "US_FISCAL_STRESS"),
        "us_fiscal_stress_score": result["us_fiscal_stress_score"],
        "us_fiscal_stress_regime": result["us_fiscal_stress_regime"],
        "risk_flag": result["risk_flag"],
        "drivers_top3": result["drivers_top3"],
        "flags": result["flags"],
        "subscores": result["subscores"],
        "subscores_breakdown": result["subscores_breakdown"],
        "missing_fields": result["missing_fields"],
        "signal_quality": result["signal_quality"],
        "duration_risk_mode": result["duration_risk_mode"],
        "preferred_equity_style": result["preferred_equity_style"],
        "policy_stance": result.get("policy_stance"),
        "policy_delta_3m_bps": result.get("policy_delta_3m_bps"),
        "policy_stance_source": result.get("policy_stance_source"),
        "days_gap_actual": result.get("days_gap_actual"),
        "policy_stance_confidence": result.get("policy_stance_confidence"),
        "policy_stance_effective": result.get("policy_stance_effective"),
        "coverage_weight_final": result.get("coverage_weight_final"),
        "measured_components_count": result.get("measured_components_count"),
        "equity_factor_tilt": result.get("equity_factor_tilt"),
        "vn_sector_tilt_hint": result.get("vn_sector_tilt_hint"),
        "us_fiscal_stress": result["us_fiscal_stress"],
        "implications": result["implications"],
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"[us_fiscal_stress] score={result['us_fiscal_stress_score']} regime={result['us_fiscal_stress_regime']} risk_flag={result['risk_flag']}")
    print(f"[us_fiscal_stress] drivers_top3={result['drivers_top3']} flags={result['flags']}")
    print(f"[us_fiscal_stress] signal_quality={result['signal_quality']} duration_risk_mode={result['duration_risk_mode']} preferred_equity_style={result['preferred_equity_style']}")
    print(f"[us_fiscal_stress] coverage_weight_final={result.get('coverage_weight_final')} measured_components_count={result.get('measured_components_count')}")
    print(f"[us_fiscal_stress] policy_stance={result.get('policy_stance')} policy_stance_effective={result.get('policy_stance_effective')} policy_stance_confidence={result.get('policy_stance_confidence')} policy_delta_3m_bps={result.get('policy_delta_3m_bps')} policy_stance_source={result.get('policy_stance_source')} days_gap_actual={result.get('days_gap_actual')}")
    print(f"[us_fiscal_stress] equity_factor_tilt={result.get('equity_factor_tilt')} vn_sector_tilt_hint={result.get('vn_sector_tilt_hint')}")
    print(f"[us_fiscal_stress] implications={result['implications']}")
    print(f"[us_fiscal_stress] Wrote: {out_path}")


if __name__ == "__main__":
    main()
