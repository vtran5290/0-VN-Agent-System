from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import win32com.client as win32


def main() -> None:
    repo = Path(r"c:\Users\LOLII\Documents\V\0. VN Agent System")
    xl_path = Path(r"C:\Users\LOLII\Documents\V\Port Analysis\Analysis - FQuery - 20260504.xlsx")
    asof = datetime.now().strftime("%Y-%m-%d")

    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Open(str(xl_path))
    ws = wb.Worksheets("Open")
    vals = ws.Range("U9:AN17").Value
    wb.Close(False)
    xl.Quit()

    rows = list(vals) if isinstance(vals, tuple) else [vals]
    out = []
    for r in rows:
        if not r:
            continue
        ticker_raw = r[0]
        if ticker_raw is None:
            continue
        ticker = str(ticker_raw).strip()
        if ":" in ticker:
            ticker = ticker.split(":", 1)[1]
        ticker = ticker.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{2,10}", ticker):
            continue

        reason = (str(r[1]).strip() if r[1] is not None else "unknown") or "unknown"
        try:
            entry_price = abs(float(r[2])) if r[2] is not None else None
        except Exception:
            entry_price = None
        try:
            lots = int(round(float(r[3]))) if r[3] is not None else None
        except Exception:
            lots = None
        if lots is None or lots <= 0:
            continue

        out.append(
            {
                "ticker": ticker,
                "entry_date": None,
                "entry_price": entry_price,
                "lots": lots,
                "stop_price_at_entry": None,
                "reason_tag": reason,
                "holding_days": None,
            }
        )

    raw = repo / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "current_positions_derived.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    prov = {
        "source": "current_positions_excel",
        "source_file": str(xl_path),
        "source_file_mtime": datetime.fromtimestamp(xl_path.stat().st_mtime).isoformat() + "Z",
        "row_count": len(out),
        "row_count_raw": len(rows),
        "row_count_skipped": len(rows) - len(out),
    }
    (raw / "current_positions_provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (raw / "current_positions_skip_report.json").write_text(
        json.dumps({"skip_counts": {}, "examples": {}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (raw / "current_positions_warnings.json").write_text("[]", encoding="utf-8")

    lines = [
        "# Current Positions (Auto-derived)",
        "",
        f"As of: {asof}",
        "",
        f"Total positions: {len(out)}",
        "",
        "| Symbol | Lots | Entry Date | Entry Price | Holding Days | Reason Tag |",
        "|--------|------|------------|-------------|--------------|------------|",
    ]
    for p in out:
        ep = "" if p["entry_price"] is None else str(int(round(float(p["entry_price"]))))
        lines.append(f"| {p['ticker']} | {p['lots']} |  | {ep} |  | {p['reason_tag']} |")
    lines.extend(
        [
            "",
            "---",
            "**Sanity check:**",
            f"- Open positions count = {len(out)}",
            f"- Source: Current positions.xlsx ({xl_path.name})",
        ]
    )
    (raw / "current_positions_digest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"updated_positions={len(out)}")


if __name__ == "__main__":
    main()
