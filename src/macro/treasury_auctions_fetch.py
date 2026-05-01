# src/macro/treasury_auctions_fetch.py — US Treasury FiscalData API: auction bid-to-cover & indirect
"""
Fetch latest 10Y note and 30Y bond auctions; write snapshot and map to US_FISCAL_STRESS inputs.auctions.
Source: https://api.fiscaldata.treasury.gov/services/api/fiscal_service/
Dataset: Treasury Securities Auctions (auctions_query). No API key required.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT_PATH = REPO_ROOT / "data" / "sources" / "macro" / "treasury_auctions_snapshot.json"
BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"


def _safe_float(v: Any) -> float | None:
    if v is None or v == "null" or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _exclude_tips_frn(records: list[dict]) -> list[dict]:
    """Exclude TIPS, FRN, and inflation-protected so we use regular Note/Bond only."""
    out = []
    for rec in records:
        st = (rec.get("security_type") or "").upper()
        if st in ("TIPS", "FRN"):
            continue
        if "INFLATION" in st or "FLOATING" in st:
            continue
        out.append(rec)
    return out


def fetch_auctions(security_type: str | None = None, page_size: int = 100) -> list[dict]:
    """Fetch auction records. security_type: 'Note' | 'Bond' | None (all). Excludes TIPS and FRN."""
    params: dict[str, Any] = {
        "sort": "-auction_date",
        "page[size]": page_size,
        "format": "json",
    }
    if security_type:
        params["filter"] = f"security_type:eq:{security_type}"
    r = requests.get(BASE_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return _exclude_tips_frn(data.get("data", []))


def latest_with_btc(records: list[dict], term_hint: str) -> dict | None:
    """First record (by auction_date desc) with non-null bid_to_cover_ratio matching term.
    term_hint: '10Y' -> security_term contains 10-Year; '30Y' -> 30-Year.
    """
    for rec in records:
        btc = _safe_float(rec.get("bid_to_cover_ratio"))
        if btc is None:
            continue
        st = (rec.get("security_term") or "").lower()
        if term_hint == "10Y" and ("10-year" in st or "10 year" in st):
            return rec
        if term_hint == "30Y" and ("30-year" in st or "30 year" in st):
            return rec
    return None


def indirect_pct(rec: dict) -> float | None:
    """indirect_bidder_accepted / total_accepted * 100 if both present."""
    ind = _safe_float(rec.get("indirect_bidder_accepted"))
    tot = _safe_float(rec.get("total_accepted"))
    if ind is not None and tot is not None and tot > 0:
        return round(100.0 * ind / tot, 2)
    return None


def run_fetch() -> dict:
    """Fetch Notes and Bonds (excl. TIPS/FRN), pick latest 10Y and 30Y with BTC, build snapshot. Audit: cusip, security_type, auction_date, issue_date."""
    asof_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"
    all_notes = fetch_auctions("Note")
    all_bonds = fetch_auctions("Bond")
    combined = all_notes + all_bonds
    rec_10y = latest_with_btc(combined, "10Y")
    rec_30y = latest_with_btc(combined, "30Y")

    def _row(rec: dict | None, tenor: str) -> dict:
        if not rec:
            return {
                "tenor": tenor,
                "auction_date": None,
                "issue_date": None,
                "cusip": None,
                "bid_to_cover_ratio": None,
                "indirect_bidder_pct": None,
                "security_type": None,
                "security_term": None,
                "status": "missing",
            }
        btc = _safe_float(rec.get("bid_to_cover_ratio"))
        ind_pct = indirect_pct(rec)
        return {
            "tenor": tenor,
            "auction_date": rec.get("auction_date"),
            "issue_date": rec.get("issue_date"),
            "cusip": rec.get("cusip"),
            "bid_to_cover_ratio": btc,
            "indirect_bidder_pct": ind_pct,
            "security_type": rec.get("security_type"),
            "security_term": rec.get("security_term"),
            "status": "ok",
        }

    snapshot = {
        "asof_date": asof_iso,
        "source": "fiscaldata.treasury.gov",
        "endpoint": BASE_URL,
        "auctions": [
            _row(rec_10y, "10Y"),
            _row(rec_30y, "30Y"),
        ],
    }
    return snapshot


def map_to_us_fiscal_stress_auctions(snapshot: dict) -> dict:
    """Map snapshot to US_FISCAL_STRESS pack inputs.auctions.*"""
    auctions = snapshot.get("auctions", [])
    by_tenor = {a["tenor"]: a for a in auctions}
    a10 = by_tenor.get("10Y", {})
    a30 = by_tenor.get("30Y", {})
    return {
        "ust_10y_bid_to_cover": a10.get("bid_to_cover_ratio"),
        "ust_10y_indirect_pct": a10.get("indirect_bidder_pct"),
        "ust_30y_bid_to_cover": a30.get("bid_to_cover_ratio"),
        "ust_30y_indirect_pct": a30.get("indirect_bidder_pct"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Treasury auction data (bid-to-cover, indirect) for US fiscal stress pack.")
    parser.add_argument("--out", type=str, default=None, help=f"Snapshot path (default: {SNAPSHOT_PATH})")
    parser.add_argument("--print-mapping", action="store_true", help="Print mapping to inputs.auctions")
    args = parser.parse_args()

    snapshot = run_fetch()
    out_path = Path(args.out) if args.out else SNAPSHOT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)

    print(f"Wrote {out_path}")
    print(f"asof_date={snapshot['asof_date']}")
    for a in snapshot.get("auctions", []):
        print(f"  {a['tenor']}: btc={a.get('bid_to_cover_ratio')} indirect_pct={a.get('indirect_bidder_pct')} date={a.get('auction_date')}")

    if args.print_mapping:
        mapping = map_to_us_fiscal_stress_auctions(snapshot)
        print("Mapping to inputs.auctions:", json.dumps(mapping, indent=2))


if __name__ == "__main__":
    main()
