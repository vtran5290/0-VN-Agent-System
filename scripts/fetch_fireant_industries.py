from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def _get_client():
    import sys

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from src.data.fireant_client import get_client  # type: ignore

    return get_client()


def fetch_industries_master(out_dir: Path) -> Path:
    """
    Fetch the industry universe from FireAnt:
      GET /industries

    Saves:
      industries_master.json
      industries_master.csv
    """
    client = _get_client()
    # Reuse underlying session with a raw GET to /industries
    # by using the client's private session if needed; for now, call requests via client._get
    # to keep headers/token consistent.
    # We intentionally bypass type hints here; this is an internal helper.
    from src.data.fireant_client import RESTV2_BASE  # type: ignore

    raw = client._get(f"{RESTV2_BASE}/industries", params=None)  # type: ignore[attr-defined]
    items: List[Dict[str, Any]] = raw if isinstance(raw, list) else []

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "industries_master.json"
    csv_path = out_dir / "industries_master.csv"

    json_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    if items:
        df = pd.DataFrame(items)
        df.to_csv(csv_path, index=False)
    else:
        pd.DataFrame(columns=["industryCode", "level", "name", "description"]).to_csv(
            csv_path, index=False
        )

    logging.info("Industries master: %s records -> %s", len(items), csv_path)
    return csv_path


def fetch_industries_history(
    start: str,
    end: str,
    out_dir: Path,
    level_filter: int | None = 1,
) -> Path:
    """
    Fetch historical stats for all industries:
      GET /industries/{industryCode}/historical-stats?startDate=...&endDate=...

    If level_filter is set, only include industries with that level (e.g. 1 for top-level sectors).
    """
    client = _get_client()
    from src.data.fireant_client import RESTV2_BASE  # type: ignore

    master_path = fetch_industries_master(out_dir)
    master_df = pd.read_csv(master_path)
    if level_filter is not None and "level" in master_df.columns:
        codes = (
            master_df.loc[master_df["level"] == level_filter, "industryCode"]
            .dropna()
            .astype(str)
            .tolist()
        )
    else:
        codes = master_df["industryCode"].dropna().astype(str).tolist()

    records: List[Dict[str, Any]] = []
    for code in codes:
        url = f"{RESTV2_BASE}/industries/{code}/historical-stats"
        params = {"startDate": start, "endDate": end}
        try:
            data = client._get(url, params=params)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - network dependent
            logging.error("industries/%s historical fetch failed: %s", code, exc)
            continue

        if not isinstance(data, list):
            continue
        for row in data:
            idx = row or {}
            date_val = idx.get("date")
            if not date_val:
                continue
            records.append(
                {
                    "industryCode": code,
                    "date": str(date_val)[:10],
                    "indexOpen": idx.get("indexOpen"),
                    "indexHigh": idx.get("indexHigh"),
                    "indexLow": idx.get("indexLow"),
                    "indexClose": idx.get("indexClose"),
                    "totalVolume": idx.get("totalVolume"),
                    "totalValue": idx.get("totalValue"),
                    "buyForeignQuantity": idx.get("buyForeignQuantity"),
                    "sellForeignQuantity": idx.get("sellForeignQuantity"),
                    "pe": idx.get("pe"),
                    "pb": idx.get("pb"),
                    "ps": idx.get("ps"),
                    "marketCap": idx.get("marketCap"),
                }
            )

    if not records:
        out_path = out_dir / "industries_history_empty.csv"
        pd.DataFrame(
            columns=[
                "industryCode",
                "date",
                "indexOpen",
                "indexHigh",
                "indexLow",
                "indexClose",
                "totalVolume",
                "totalValue",
                "buyForeignQuantity",
                "sellForeignQuantity",
                "pe",
                "pb",
                "ps",
                "marketCap",
            ]
        ).to_csv(out_path, index=False)
        logging.warning("No industries history records; wrote empty CSV to %s", out_path)
        return out_path

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["industryCode", "date"]).reset_index(drop=True)

    out_name = f"industries_history_L{level_filter}_{start}_{end}.csv" if level_filter else f"industries_history_{start}_{end}.csv"
    out_path = out_dir / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    logging.info(
        "Industries history (level=%s): %s rows, %s industries -> %s",
        level_filter,
        len(df),
        df["industryCode"].nunique(),
        out_path,
    )
    return out_path


def main() -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(
        description="Fetch FireAnt /industries master list and historical stats."
    )
    parser.add_argument(
        "--start",
        default="2012-01-01",
        help="Start date (YYYY-MM-DD) for historical-stats.",
    )
    parser.add_argument(
        "--end",
        default=datetime.today().strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD) for historical-stats.",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=1,
        help="Industry level to include (default: 1 = top-level sectors).",
    )
    parser.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "data" / "fireant_exports" / "industries"),
        help="Output directory for industries master + history.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    fetch_industries_master(out_dir)
    fetch_industries_history(args.start, args.end, out_dir, level_filter=args.level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

