"""Build artifacts/earnings_quality_flags.csv from weekly_notes.json earnings_facts (regime_tags / quality_flags)."""
from __future__ import annotations
import csv
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NOTES = REPO / "data" / "raw" / "weekly_notes.json"
OUT = REPO / "artifacts" / "earnings_quality_flags.csv"

QUALITY_FLAGS = {
    "one_off_gain", "provision_cleanup", "inventory_gain_loss",
    "fx_gain_loss", "disposal_gain", "accounting_reversal",
}


def main() -> None:
    rows: list[dict] = []
    if not NOTES.exists():
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["ticker", "flag", "source_id"])
            w.writeheader()
        print(f"No {NOTES}; wrote empty {OUT}")
        return
    notes = __import__("json").loads(NOTES.read_text(encoding="utf-8"))
    earnings = notes.get("earnings_facts") or []
    for e in earnings:
        ticker = (e.get("ticker") or "").strip()
        source_id = e.get("source") or e.get("source_id") or "weekly_notes"
        tags = e.get("regime_tags") or e.get("quality_flags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        for flag in tags:
            if flag:
                rows.append({"ticker": ticker, "flag": flag, "source_id": source_id})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "flag", "source_id"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()
