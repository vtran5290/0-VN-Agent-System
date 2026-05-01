"""
Merge fetch_global, fetch_vietnam_market, compute_distribution_days into data/raw/manual_inputs.json.
Never overwrite overrides.* or vietnam.omo_net/interbank_on/credit_growth_yoy unless --force-vn-liquidity.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.safe_json_io import atomic_write_json, safe_read_json, safe_update_nested
from scripts.fetch_global import fetch_global
from scripts.metric_audit_enrich import enrich_global_metrics_audit_rows
from scripts.fetch_vietnam_market import fetch_vietnam_market
from scripts.compute_distribution_days import compute_distribution_days
from scripts.fetch_vietnam_liquidity import fetch_vietnam_liquidity

from src.macro.vietnam_liquidity.orchestrator import get_vietnam_liquidity_with_provider

logger = logging.getLogger(__name__)

MANUAL_INPUTS_PATH = REPO_ROOT / "data" / "raw" / "manual_inputs.json"
DRIFT_GUARD = {"interpretation_detected": False, "decision_layer_leak": False}
EXTRACTION_MODE = "macro_market_auto_v1"


def run(asof: str | None, force_vn_liquidity: bool = False, skip_vn_market: bool = False) -> None:
    from datetime import date
    if asof is None:
        asof = date.today().isoformat()
    global_data = fetch_global(asof)
    vn_market_data = fetch_vietnam_market(asof) if not skip_vn_market else {}
    dist_data = compute_distribution_days(asof) if not skip_vn_market else {}
    data = safe_read_json(MANUAL_INPUTS_PATH)
    if not data:
        data = {"asof_date": asof, "global": {}, "vietnam": {}, "market": {}, "overrides": {}}
    saved_vietnam = dict(data.get("vietnam", {}))
    saved_overrides = dict(data.get("overrides", {}))
    data["asof_date"] = asof
    data["extraction_mode"] = EXTRACTION_MODE
    data["drift_guard"] = DRIFT_GUARD.copy()
    safe_update_nested(data, global_data)
    if not skip_vn_market:
        safe_update_nested(data, vn_market_data)
        safe_update_nested(data, dist_data)
    else:
        # Weekly report uses FireAnt macro snapshot for VN index / dist days; keep manual market empty.
        data["market"] = {}
    if force_vn_liquidity:
        provider = (os.getenv("VIETNAM_MACRO_PROVIDER") or "existing").strip().lower()
        sstock_shadow = (os.getenv("VIETNAM_MACRO_SSTOCK_SHADOW") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "y",
            "on",
        )

        # Tier policy (non-destructive):
        # - existing: use SBV only
        # - auto: use SBV as primary; fill missing with SStock if it parses
        # - sstock: experimental request, but we still apply non-destructive auto-merge
        provider_mode = "existing"
        enable_sstock = False
        if sstock_shadow:
            provider_mode = "shadow"
            enable_sstock = True
        elif provider in ("auto", "sstock"):
            provider_mode = "auto"
            enable_sstock = True

        chosen, compare = get_vietnam_liquidity_with_provider(
            asof=asof,
            provider_mode=provider_mode,
            enable_sstock=enable_sstock,
        )

        # Backward compatible: only vietnam.{field} is consumed by weekly report.
        safe_update_nested(data, {"vietnam": chosen.to_manual_inputs_vietnam()})
        # If current OMO net is missing, clear stale OMO detail fields from previous runs
        # so report does not show contradictory "OMO net=None" with old inject/withdraw/rate.
        if data.get("vietnam", {}).get("omo_net") is None:
            v = data.setdefault("vietnam", {})
            for k in ("omo_inject", "omo_withdraw", "omo_rate", "omo_value_date", "omo_note"):
                v[k] = None

        # Provenance lives alongside values for auditing/shadow compare.
        prov = {f: chosen.meta[f].to_dict() for f in chosen.meta}
        safe_update_nested(data, {"vietnam_provenance": prov})

        if sstock_shadow and compare:
            artifacts_dir = REPO_ROOT / "artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            json_path = artifacts_dir / "sstock_shadow_compare.json"
            md_path = artifacts_dir / "sstock_shadow_compare.md"

            # Write JSON (machine-readable).
            atomic_write_json(json_path, compare)

            # Write Markdown (human-readable).
            items = compare.get("items") or []
            lines = [
                f"# SStock shadow comparison",
                f"",
                f"- asof: {asof}",
                f"- existing source: sbv",
                f"- sstock source: sstock (experimental)",
                f"",
                "| field | existing_value | sstock_value | chosen_value | chosen_source | status |",
                "|---|---:|---:|---:|---|---|",
            ]
            for it in items:
                lines.append(
                    "| {field} | {existing} | {sstock} | {chosen} | {src} | {status} |".format(
                        field=it.get("field"),
                        existing=it.get("existing_value"),
                        sstock=it.get("sstock_value"),
                        chosen=it.get("chosen_value"),
                        src=it.get("chosen_source"),
                        status=it.get("status"),
                    )
                )
            md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        for key in ("omo_net", "interbank_on", "credit_growth_yoy", "fx_usd_vnd"):
            if key in saved_vietnam and saved_vietnam[key] is not None:
                data.setdefault("vietnam", {})[key] = saved_vietnam[key]
        data["overrides"] = saved_overrides
    enrich_global_metrics_audit_rows(data)
    atomic_write_json(MANUAL_INPUTS_PATH, data)
    logger.info("Updated %s", MANUAL_INPUTS_PATH)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=None, help="Date YYYY-MM-DD")
    ap.add_argument("--force-vn-liquidity", action="store_true", help="Allow overwrite of vietnam OMO/interbank/credit")
    ap.add_argument(
        "--skip-vn-market",
        action="store_true",
        help="Do not merge fetch_vietnam_market / compute_distribution_days; set market={} for FireAnt-driven weekly",
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.asof, getattr(args, "force_vn_liquidity", False), getattr(args, "skip_vn_market", False))
