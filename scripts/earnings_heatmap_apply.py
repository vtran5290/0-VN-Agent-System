"""Apply earnings heatmap pack: archive to data/intake/earnings/heatmap/<asof>.json, render artifacts/."""
from __future__ import annotations
import json
import csv
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "data" / "raw" / "earnings_heatmap_pack.json"
HEATMAP_ARCHIVE = REPO / "data" / "intake" / "earnings" / "heatmap"
ARTIFACTS = REPO / "artifacts"


def main() -> None:
    if not PACK.exists():
        print(f"Missing {PACK}")
        return
    data = json.loads(PACK.read_text(encoding="utf-8"))
    asof = data.get("asof_date", "unknown")
    heatmap = data.get("heatmap", [])

    HEATMAP_ARCHIVE.mkdir(parents=True, exist_ok=True)
    archive_path = HEATMAP_ARCHIVE / f"{asof}.json"
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Archived: {archive_path}")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    md_lines = [f"# Earnings Heatmap — {asof}", ""]
    for row in heatmap:
        sector = row.get("sector", "")
        score = row.get("score", "")
        evidence = row.get("evidence", [])
        watch = row.get("watch", [])
        md_lines.append(f"## {sector} (score {score})")
        md_lines.append("- Evidence: " + "; ".join(evidence))
        md_lines.append("- Watch: " + "; ".join(watch))
        md_lines.append("")
    (ARTIFACTS / "earnings_heatmap.md").write_text("\n".join(md_lines), encoding="utf-8")

    csv_path = ARTIFACTS / "earnings_heatmap.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sector", "score", "evidence", "watch"])
        for row in heatmap:
            w.writerow([
                row.get("sector", ""),
                row.get("score", ""),
                "; ".join(row.get("evidence", [])),
                "; ".join(row.get("watch", [])),
            ])
    print(f"Rendered: {ARTIFACTS / 'earnings_heatmap.md'}, {csv_path}")


if __name__ == "__main__":
    main()
