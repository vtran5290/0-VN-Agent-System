from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
BASE_DIR = REPO / "data" / "smart_money"
EXTRACTED_DIR = BASE_DIR / "extracted"
MONTHLY_DIR = BASE_DIR / "monthly"


@dataclass
class FundRecord:
    fund_name: str
    fund_code: Optional[str]
    report_month: str
    raw: Dict[str, Any]
    path: Path


def _safe_read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def load_funds_for_month(month: str) -> List[FundRecord]:
    """
    Load all per-fund JSON files for a target month (YYYY-MM).

    Expected pattern: data/smart_money/extracted/*_<YYYY-MM>.json
    """
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    pattern = f"*_{month}.json"
    records: List[FundRecord] = []
    for path in sorted(EXTRACTED_DIR.glob(pattern)):
        data = _safe_read_json(path)
        if not data:
            continue
        report_month = str(data.get("report_month") or month)
        fund_name = str(data.get("fund_name") or path.stem)
        fund_code_val = data.get("fund_code")
        fund_code = str(fund_code_val) if fund_code_val is not None else None
        records.append(FundRecord(fund_name=fund_name, fund_code=fund_code, report_month=report_month, raw=data, path=path))
    return records


def load_monthly_consensus(month: str) -> Optional[Dict[str, Any]]:
    """
    Load previously computed monthly consensus JSON, if available.
    """
    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    path = MONTHLY_DIR / f"smart_money_{month}.json"
    if not path.exists():
        return None
    return _safe_read_json(path)


def write_monthly_consensus(month: str, payload: Dict[str, Any]) -> Path:
    """
    Persist monthly consensus JSON to data/smart_money/monthly/.
    """
    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    path = MONTHLY_DIR / f"smart_money_{month}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def infer_prev_month(month: str) -> Optional[str]:
    """
    Best-effort YYYY-MM → previous month (same format).
    Returns None if parsing fails.
    """
    try:
        year_str, mon_str = month.split("-")
        year = int(year_str)
        mon = int(mon_str)
        if mon == 1:
            return f"{year - 1}-12"
        return f"{year}-{mon - 1:02d}"
    except Exception:
        return None

