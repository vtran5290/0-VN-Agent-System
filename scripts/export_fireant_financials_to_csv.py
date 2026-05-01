#!/usr/bin/env python3
"""
Export FireAnt financials Parquet → CSV (để mở Excel / xem data cũ).
Không xóa file Parquet. Chạy từ repo root: python scripts/export_fireant_financials_to_csv.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORTS = REPO_ROOT / "data" / "fireant_exports"
SUMMARY_PATH = EXPORTS / "summary.json"


def main() -> int:
    if not SUMMARY_PATH.exists():
        print("summary.json not found.")
        return 1
    try:
        import pandas as pd
    except ImportError:
        print("pandas required.")
        return 1

    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    financials = summary.get("financials") or {}
    q_rel = (financials.get("quarterly_file") or "").replace("\\", "/")
    a_rel = (financials.get("annual_file") or "").replace("\\", "/")
    if not q_rel or not a_rel:
        print("summary.json thiếu quarterly_file / annual_file.")
        return 1

    q_path = REPO_ROOT / q_rel
    a_path = REPO_ROOT / a_rel
    out_dir = REPO_ROOT / "data" / "fireant_exports" / "financials"
    out_dir.mkdir(parents=True, exist_ok=True)

    if q_path.exists():
        q_csv = out_dir / q_path.name.replace(".parquet", ".csv")
        print("Export quarterly →", q_csv.name)
        pd.read_parquet(q_path).to_csv(q_csv, index=False)
    else:
        print("Không tìm thấy file quarterly parquet:", q_path)

    if a_path.exists():
        a_csv = out_dir / a_path.name.replace(".parquet", ".csv")
        print("Export annual →", a_csv.name)
        pd.read_parquet(a_path).to_csv(a_csv, index=False)
    else:
        print("Không tìm thấy file annual parquet:", a_path)

    print("Xong. File CSV nằm trong data/fireant_exports/financials/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
