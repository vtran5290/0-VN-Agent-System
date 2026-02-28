"""
Merge fetch_global, fetch_vietnam_market, compute_distribution_days into data/raw/manual_inputs.json.
Never overwrite overrides.* or vietnam.omo_net/interbank_on/credit_growth_yoy unless --force-vn-liquidity.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.safe_json_io import atomic_write_json, safe_read_json, safe_update_nested
from scripts.fetch_global import fetch_global
from scripts.fetch_vietnam_market import fetch_vietnam_market
from scripts.compute_distribution_days import compute_distribution_days

logger = logging.getLogger(__name__)

MANUAL_INPUTS_PATH = REPO_ROOT / "data" / "raw" / "manual_inputs.json"
DRIFT_GUARD = {"interpretation_detected": False, "decision_layer_leak": False}
EXTRACTION_MODE = "macro_market_auto_v1"


def run(asof: str | None, force_vn_liquidity: bool = False) -> None:
    from datetime import date
    if asof is None:
        asof = date.today().isoformat()
    global_data = fetch_global(asof)
    vn_market_data = fetch_vietnam_market(asof)
    dist_data = compute_distribution_days(asof)
    data = safe_read_json(MANUAL_INPUTS_PATH)
    if not data:
        data = {"asof_date": asof, "global": {}, "vietnam": {}, "market": {}, "overrides": {}}
    saved_vietnam = dict(data.get("vietnam", {}))
    saved_overrides = dict(data.get("overrides", {}))
    data["asof_date"] = asof
    data["extraction_mode"] = EXTRACTION_MODE
    data["drift_guard"] = DRIFT_GUARD.copy()
    safe_update_nested(data, global_data)
    safe_update_nested(data, vn_market_data)
    safe_update_nested(data, dist_data)
    if not force_vn_liquidity:
        for key in ("omo_net", "interbank_on", "credit_growth_yoy"):
            if key in saved_vietnam and saved_vietnam[key] is not None:
                data.setdefault("vietnam", {})[key] = saved_vietnam[key]
        data["overrides"] = saved_overrides
    atomic_write_json(MANUAL_INPUTS_PATH, data)
    logger.info("Updated %s", MANUAL_INPUTS_PATH)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=None, help="Date YYYY-MM-DD")
    ap.add_argument("--force-vn-liquidity", action="store_true", help="Allow overwrite of vietnam OMO/interbank/credit")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.asof, getattr(args, "force_vn_liquidity", False))
