#!/usr/bin/env python3
"""
VN Weekly Report: fetch SBV OMO + Yahoo DXY (third-party). Prints one JSON object (stdout).

Task order: (1) Vietnam OMO from SBV HTML, (2) DXY from Yahoo quote page DX-Y.NYB.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.intake.sbv_omo_scrape import fetch_sbv_omo_parsed  # noqa: E402
from src.intake.yahoo_dxy_quote import fetch_dxy_yahoo_quote_page  # noqa: E402


def main() -> None:
    logs: list[str] = []
    errors: list[str] = []

    # --- Task 1: SBV OMO ---
    omo_raw, omo_logs = fetch_sbv_omo_parsed()
    logs.extend(omo_logs)
    vietnam: dict = {
        "omo_net": None,
        "omo_inject": None,
        "omo_withdraw": None,
        "omo_rate": None,
        "omo_value_date": None,
        "omo_breakdown": [],
    }
    if omo_raw:
        vietnam["omo_net"] = omo_raw.get("omo_net")
        vietnam["omo_inject"] = omo_raw.get("omo_inject")
        vietnam["omo_withdraw"] = omo_raw.get("omo_withdraw")
        vietnam["omo_rate"] = omo_raw.get("omo_rate")
        vietnam["omo_value_date"] = omo_raw.get("omo_value_date")
        vietnam["omo_breakdown"] = omo_raw.get("omo_breakdown") or []
        for e in omo_raw.get("errors") or []:
            errors.append(f"omo:{e}")
    else:
        errors.append("omo_fetch_failed")

    # --- Task 2: Yahoo DXY ---
    price, prev_close, vd, dxy_logs = fetch_dxy_yahoo_quote_page()
    logs.extend(dxy_logs)
    dxy_block = {
        "dxy_third_party": price,
        "dxy_third_party_prev_close": prev_close,
        "dxy_third_party_source": "Yahoo Finance DX-Y.NYB",
        "dxy_third_party_date": vd,
        "dxy_ice_official": None,
    }
    if price is None and prev_close is None:
        errors.append("dxy_third_party_unavailable")

    out = {
        "vietnam": vietnam,
        "dxy": dxy_block,
        "errors": errors,
        "logs": logs,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
