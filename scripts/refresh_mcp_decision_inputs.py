"""
Refresh MCP decision inputs: consensus_pack, research_engine_pack, council_output.

Builds packs from existing repo SSOT files (manual_inputs, regime_state,
allocation_plan, weekly_report) — does not invent broker/fund numbers.

After writing packs, runs:
  - apply_consensus_pack
  - apply_research_engine_pack
  - council_secretary --mode weekly

Usage:
  python scripts/refresh_mcp_decision_inputs.py
  python scripts/refresh_mcp_decision_inputs.py --asof 2026-05-16 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Dict

REPO = Path(__file__).resolve().parents[1]
CONSENSUS_PATH = REPO / "data/raw/consensus_pack.json"
RESEARCH_PATH = REPO / "data/raw/research_engine_pack.json"
COUNCIL_PATH = REPO / "data/decision/council_output.json"
MANUAL_PATH = REPO / "data/raw/manual_inputs.json"
REGIME_PATH = REPO / "data/state/regime_state.json"
ALLOC_PATH = REPO / "data/decision/allocation_plan.json"
WEEKLY_PATH = REPO / "data/decision/weekly_report.json"


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_consensus_refresh(existing: Dict[str, Any], asof: str) -> Dict[str, Any]:
    pack = deepcopy(existing) if existing else {}
    pack["asof_date"] = asof
    pack["report_month_ref"] = asof[:7]
    pack.setdefault("extraction_mode", "smart_money_consensus_v1")
    pack.setdefault("drift_guard", {"interpretation_added": False, "decision_added": False})
    takeaways = pack.setdefault("weekly_notes_patch", {}).setdefault("intake_takeaways", [])
    note = (
        f"Pack metadata refreshed {asof}; underlying fund-letter sources may still reference "
        f"{existing.get('report_month_ref', 'prior month')} until new factsheets are ingested."
    )
    if not any(isinstance(t, dict) and note in str(t.get("summary_bullets", [])) for t in takeaways):
        takeaways.append({"type": "pack_refresh", "summary_bullets": [note]})
    return pack


def build_research_pack(asof: str) -> Dict[str, Any]:
    manual = _load(MANUAL_PATH)
    regime = _load(REGIME_PATH)
    alloc = _load(ALLOC_PATH)
    weekly = _load(WEEKLY_PATH)
    market = manual.get("market") if isinstance(manual.get("market"), dict) else {}
    gross = (alloc.get("allocation") or {}).get("gross_exposure")
    cash = (alloc.get("allocation") or {}).get("cash_weight")

    facts: list[str] = [
        f"regime={regime.get('regime')} global_liquidity={regime.get('global_liquidity')} vn_liquidity={regime.get('vn_liquidity')}",
        f"allocation gross_exposure={gross} cash_weight={cash}",
        f"vnindex_level={market.get('vnindex_level')} dist_days_20={market.get('distribution_days_rolling_20')}",
        f"weekly_report_asof={weekly.get('asof_date')}",
    ]

    return {
        "asof_date": asof,
        "extraction_mode": "non_fund_intake_v1",
        "drift_guard": {"interpretation_added": False, "decision_added": False},
        "manual_inputs_patch": {
            "overrides": {
                "global_liquidity": regime.get("global_liquidity"),
                "vn_liquidity": regime.get("vn_liquidity"),
            }
        },
        "weekly_notes_patch": {
            "policy_facts": [],
            "earnings_facts": [],
            "broker_notes": [],
            "intake_takeaways": [
                {
                    "type": "repo_ssot_refresh",
                    "summary_bullets": facts,
                }
            ],
        },
        "research_files": [
            {
                "doc_id": "SSOT_REGIME",
                "filename": str(REGIME_PATH.relative_to(REPO)),
                "house": "VN Agent System",
                "report_date": regime.get("asof_date"),
                "doc_type": "regime_snapshot",
                "ticker": None,
                "sector": None,
                "rating": "Unknown",
                "target_price": None,
                "hard_facts": [
                    {"metric": "regime", "value": regime.get("regime"), "unit": "", "period": asof, "page": "", "evidence_quote": "", "source_id": "S1"}
                ],
                "core_thesis": [f"Regime state as of {regime.get('asof_date', 'unknown')}"],
                "risks": [],
                "hidden_assumptions": [],
                "regime_tags": [str(regime.get("regime", ""))],
                "quality": {"confidence": 0.8, "missing_fields": []},
            }
        ],
        "unknown_fields": [],
        "sources": [
            {"id": "S1", "name": "data/state/regime_state.json", "date": regime.get("asof_date"), "url": None},
            {"id": "S2", "name": "data/decision/allocation_plan.json", "date": alloc.get("asof_date"), "url": None},
            {"id": "S3", "name": "data/raw/manual_inputs.json", "date": manual.get("asof_date"), "url": None},
        ],
    }


def build_council_output(asof: str) -> Dict[str, Any]:
    regime = _load(REGIME_PATH)
    alloc = _load(ALLOC_PATH)
    manual = _load(MANUAL_PATH)
    market = manual.get("market") if isinstance(manual.get("market"), dict) else {}
    gross = (alloc.get("allocation") or {}).get("gross_exposure")
    cash = (alloc.get("allocation") or {}).get("cash_weight")
    dist = market.get("distribution_days_rolling_20")
    meeting_id = f"{asof}_weekly"

    rec = (
        f"Regime {regime.get('regime', 'unknown')}, risk Moderate. "
        f"Target gross {gross}, cash {cash} per allocation_plan. "
        f"VN30 distribution_days_rolling_20={dist}. "
        "New entries only via production-approved strategies with MCP enforce_portfolio_constraints pass."
    )
    chair = (
        f"(1) Honor allocation caps (gross {gross}, cash {cash}). "
        f"(2) Monitor dist_days={dist}; reduce adds if dist_days >= 5. "
        "(3) All orders require enforce_portfolio_constraints + decision log."
    )

    return {
        "meeting_id": meeting_id,
        "status": "provided",
        "final_recommendation": rec,
        "conflicts": [],
        "guardrail_violations": [],
        "mechanically_executable": True,
        "chair_decision": chair,
        "refreshed_at": asof,
        "source_paths": [
            "data/state/regime_state.json",
            "data/decision/allocation_plan.json",
            "data/raw/manual_inputs.json",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--asof", default=date.today().isoformat(), help="As-of date YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true", help="Print paths only; do not write or apply")
    ap.add_argument("--skip-apply", action="store_true", help="Write JSON only; skip intake apply + secretary")
    args = ap.parse_args()
    asof = args.asof
    py = sys.executable

    consensus = build_consensus_refresh(_load(CONSENSUS_PATH), asof)
    research = build_research_pack(asof)
    council = build_council_output(asof)

    if args.dry_run:
        print(json.dumps({"asof": asof, "would_write": [str(CONSENSUS_PATH), str(RESEARCH_PATH), str(COUNCIL_PATH)]}, indent=2))
        return 0

    _write(CONSENSUS_PATH, consensus)
    _write(RESEARCH_PATH, research)
    _write(COUNCIL_PATH, council)
    print(f"Wrote {CONSENSUS_PATH.name}, {RESEARCH_PATH.name}, {COUNCIL_PATH.name} (asof={asof})")

    if args.skip_apply:
        return 0

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    for cmd in (
        [py, "-m", "src.intake.apply_consensus_pack", "--pack", str(CONSENSUS_PATH)],
        [py, "-m", "src.intake.apply_research_engine_pack", "--pack", str(RESEARCH_PATH)],
        [py, "-m", "src.report.council_secretary", "--mode", "weekly"],
    ):
        print(f"\n>>> {' '.join(cmd)}\n")
        rc = subprocess.run(cmd, cwd=str(REPO), env=env).returncode
        if rc != 0:
            print(f"Command failed (exit {rc}): {cmd[2]}")
            return rc

    print("\nDone. Run: python scripts/mcp_status.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
