from __future__ import annotations

"""
Adapter: convert "smart_money_monthly_v1" production.v4 JSON
into per-fund extracted JSON files under data/smart_money/extracted/.

Usage (from repo root):

    python -m src.smart_money.adapter_v4 --input data/smart_money/raw/smart_money_2025-12.production.v4.json

This is a thin, facts-first transformer:
- Does NOT infer missing tickers or sectors.
- Only maps what is present in the v4 JSON.
"""

import argparse
import json
from pathlib import Path
from typing import List, Optional

from .io import EXTRACTED_DIR


def convert_v4_file(input_path: Path, month_override: Optional[str] = None) -> List[Path]:
    """
    Convert a smart_money_monthly_v1 JSON into per-fund extracted JSONs.

    - input_path: path to *.production.v4.json
    - month_override: if provided, use this YYYY-MM instead of report_month_ref
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input JSON not found: {input_path}")

    raw = json.load(input_path.open(encoding="utf-8"))
    mode = raw.get("extraction_mode")
    if mode != "smart_money_monthly_v1":
        raise ValueError(f"Unexpected extraction_mode={mode!r}; expected 'smart_money_monthly_v1'.")

    month = month_override or raw.get("report_month_ref")
    if not isinstance(month, str):
        raise ValueError("report_month_ref missing or not a string; please pass --month explicitly.")

    asof_date = raw.get("asof_date")
    funds = raw.get("funds") or []

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    out_paths: List[Path] = []

    for f in funds:
        fund_id = f.get("fund_id") or "UNKNOWN_FUND"
        fund_id_str = str(fund_id)

        top_holdings_v4 = f.get("top_holdings") or []
        top_holdings = []
        for h in top_holdings_v4:
            ticker = h.get("ticker")
            # Facts-first: skip entries without explicit ticker (do not infer from name).
            if ticker is None:
                continue
            rank = h.get("rank")
            weight_val = h.get("weight_pct")
            try:
                weight = float(weight_val) if weight_val is not None else None
            except (TypeError, ValueError):
                weight = None

            holding = {
                "rank": rank,
                "ticker": ticker,
                "weight": weight,
                "source_section": "Top holdings",
            }
            sector = h.get("sector")
            if sector is not None:
                holding["sector"] = sector
            top_holdings.append(holding)

        missing_data = ["equity_weight", "cash_weight", "sector_weights", "manager_themes"]
        payload = {
            "fund_name": fund_id_str,
            "fund_code": fund_id_str,
            "report_month": month,
            "as_of_date": asof_date,
            "equity_weight": None,
            "cash_weight": None,
            "top_holdings": top_holdings,
            "sector_weights": [],
            "manager_themes": [],
            "missing_data": missing_data,
            "confidence": {
                "holdings": 1.0 if top_holdings else 0.0,
                "themes": 0.0,
            },
        }
        note = f.get("note")
        if note:
            payload["diagnostics_note"] = str(note)

        out_path = EXTRACTED_DIR / f"{fund_id_str}_{month}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        out_paths.append(out_path)

    return out_paths


def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(description="Convert smart_money_monthly_v1 production.v4 JSON into per-fund extracted JSONs.")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to smart_money_YYYY-MM.production.v4.json (relative to repo or absolute).",
    )
    parser.add_argument(
        "--month",
        help="Override month (YYYY-MM). If omitted, use report_month_ref from the JSON.",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    out_paths = convert_v4_file(input_path, month_override=args.month)
    print(f"Converted {len(out_paths)} funds from {input_path}:")
    for p in out_paths:
        print(f"  - {p}")


if __name__ == "__main__":
    main()

