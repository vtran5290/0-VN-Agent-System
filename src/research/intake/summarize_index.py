"""Print research_index.csv summary — index stats only, no LLM."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from src.research.intake.schema import (
    INDEX_COLUMNS,
    INDEX_PATH,
    SAFETY_PHRASE,
)

NEEDS_REVIEW_STATUSES = frozenset({"RAW_EXTRACTED", "CARD_CREATED"})

UPGRADE_IMPACTS = frozenset({"IMPROVED"})
DOWNGRADE_IMPACTS = frozenset({"WEAKENED"})
UPGRADE_ACTIONS = frozenset({"UPGRADE", "ADD_TO_WATCH"})
DOWNGRADE_ACTIONS = frozenset({"DOWNGRADE", "REMOVE"})


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return []
        return [dict(row) for row in reader if any(v.strip() for v in row.values() if v)]


def summarize(index_path: Path | None = None) -> str:
    path = index_path or INDEX_PATH
    rows = _load_rows(path)
    lines: list[str] = [
        "# Research intake index summary",
        "",
        f"- **Index:** `{path}`",
        f"- **Rows:** {len(rows)}",
        "",
    ]

    if not rows:
        lines.append("_No data rows yet. Add entries to research_index.csv after extraction._")
        lines.append("")
        lines.append(f"_{SAFETY_PHRASE}_")
        return "\n".join(lines)

    by_type = Counter(r.get("source_type", "").strip() or "(blank)" for r in rows)
    by_ticker = Counter(r.get("ticker", "").strip().upper() or "(blank)" for r in rows)
    by_status = Counter(r.get("status", "").strip() or "(blank)" for r in rows)

    lines.append("## By source_type")
    for k, v in sorted(by_type.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## By ticker (top 15)")
    for k, v in by_ticker.most_common(15):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## By status")
    for k, v in sorted(by_status.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- {k}: {v}")
    lines.append("")

    upgrades: list[dict[str, str]] = []
    downgrades: list[dict[str, str]] = []
    needs_review: list[dict[str, str]] = []

    for r in rows:
        status = r.get("status", "").strip()
        impact = r.get("thesis_impact", "").strip()
        action = r.get("watchlist_action", "").strip()
        if status in NEEDS_REVIEW_STATUSES:
            needs_review.append(r)
        if impact in UPGRADE_IMPACTS or action in UPGRADE_ACTIONS:
            upgrades.append(r)
        if impact in DOWNGRADE_IMPACTS or action in DOWNGRADE_ACTIONS:
            downgrades.append(r)

    lines.append("## Top thesis upgrades (max 10)")
    if not upgrades:
        lines.append("- (none flagged)")
    else:
        for r in upgrades[:10]:
            lines.append(
                f"- {r.get('ticker', '?')} | {r.get('source_id', '?')} | "
                f"impact={r.get('thesis_impact', '')} action={r.get('watchlist_action', '')}"
            )
    lines.append("")
    lines.append("## Top thesis downgrades (max 10)")
    if not downgrades:
        lines.append("- (none flagged)")
    else:
        for r in downgrades[:10]:
            lines.append(
                f"- {r.get('ticker', '?')} | {r.get('source_id', '?')} | "
                f"impact={r.get('thesis_impact', '')} action={r.get('watchlist_action', '')}"
            )
    lines.append("")
    lines.append("## Reports needing review")
    if not needs_review:
        lines.append("- (none)")
    else:
        for r in needs_review[:20]:
            lines.append(
                f"- {r.get('source_id', '?')} | status={r.get('status', '')} | "
                f"{r.get('file_name', '')[:60]}"
            )
        if len(needs_review) > 20:
            lines.append(f"- … and {len(needs_review) - 20} more")
    lines.append("")
    lines.append(
        "_Research is thesis/watchlist context only and does not set or override final_action._"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize research_index.csv")
    parser.add_argument(
        "--index",
        type=Path,
        default=INDEX_PATH,
        help="Path to research_index.csv",
    )
    args = parser.parse_args(argv)
    if args.index.is_file():
        with args.index.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames and tuple(reader.fieldnames) != INDEX_COLUMNS:
                print(
                    f"WARN: index columns mismatch. Expected {len(INDEX_COLUMNS)} columns.",
                    flush=True,
                )
    print(summarize(args.index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
