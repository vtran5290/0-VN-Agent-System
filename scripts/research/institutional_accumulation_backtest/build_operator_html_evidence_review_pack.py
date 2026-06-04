from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd


class OperatorHtmlPackBuildError(RuntimeError):
    pass


def _targets(root: Path) -> list[Path]:
    t: list[Path] = []
    t += sorted((root / "src/scans/institutional_accumulation").glob("operator_*.py"))
    t += [root / "scripts/research/institutional_accumulation_backtest/build_operator_html_evidence_review_pack.py"]
    t += [root / "tests/test_institutional_accumulation_operator_evidence.py"]
    t += [root / "data/research/institutional_accumulation_full_history/ia_dashboard_evidence_config.json"]
    return [p for p in t if p.is_file()]


def _write_source_inventory(root: Path, out: Path) -> None:
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "sha256", "line_count", "purpose"])
        for p in _targets(root):
            txt = p.read_text(encoding="utf-8", errors="ignore")
            w.writerow([p.relative_to(root).as_posix(), hashlib.sha256(txt.encode()).hexdigest(), txt.count("\n") + 1, "operator_html_evidence"])


def _write_diff_patch(root: Path, out: Path) -> None:
    diff = ""
    for cmd in (["git", "diff"], ["git", "diff", "--cached"], ["git", "diff", "HEAD"]):
        try:
            candidate = subprocess.check_output(cmd, text=True, cwd=str(root))
        except Exception:
            candidate = ""
        if candidate.strip():
            diff = candidate
            break
    if not diff.strip():
        diff = "# No git diff available\n"
    out.write_text(diff, encoding="utf-8")


def _validate_pack(*, root: Path, html_path: Path, report_path: Path) -> None:
    if not html_path.is_file() or len(html_path.read_text(encoding="utf-8")) < 1000:
        raise OperatorHtmlPackBuildError("BLOCKED_FIXTURE_CONTAMINATION")
    html_txt = html_path.read_text(encoding="utf-8")
    if "Full-History" not in html_txt:
        raise OperatorHtmlPackBuildError("BLOCKED_FIXTURE_CONTAMINATION")
    if "RESEARCH_ONLY_NOT_PRODUCTION" not in html_txt:
        raise OperatorHtmlPackBuildError("BLOCKED_FIXTURE_CONTAMINATION")
    if "full_history_accumulation_validation.html" not in html_txt:
        raise OperatorHtmlPackBuildError("BLOCKED_FIXTURE_CONTAMINATION")
    safety = "This dashboard does not set final_action, OMS orders, DNSE routing, sizing, or live execution."
    if safety not in html_txt:
        raise OperatorHtmlPackBuildError("BLOCKED_FIXTURE_CONTAMINATION")

    outcomes = root / "data/research/institutional_accumulation/forward_outcomes_panel.parquet"
    if outcomes.is_file():
        n = len(pd.read_parquet(outcomes))
        if n < 10000:
            raise OperatorHtmlPackBuildError("BLOCKED_FIXTURE_CONTAMINATION")

    report_txt = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    if "Full-History" not in report_txt and "Operator HTML" not in report_txt:
        raise OperatorHtmlPackBuildError("BLOCKED_STALE_REPORT")


def build_operator_html_evidence_review_pack(
    root: Path = Path("."),
    pack_date: str | None = None,
    output_zip: Path | None = None,
) -> Path:
    root = Path(root)
    today = pack_date or datetime.now().strftime("%Y%m%d")
    out_zip = output_zip or (
        root / "outputs" / "review_packages" / f"institutional_accumulation_operator_html_evidence_update_{today}.zip"
    )
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    inv = root / "source_file_inventory.csv"
    patch = root / "implementation_diff.patch"
    _write_source_inventory(root, inv)
    _write_diff_patch(root, patch)

    html = root / "outputs/scans/institutional_accumulation_operator_summary_latest.html"
    report = root / "implementation_report.md"
    _validate_pack(root=root, html_path=html, report_path=report)

    include = [
        report,
        root / "test_log.txt",
        root / "open_questions_for_chatgpt.md",
        inv,
        patch,
        html,
        root / "data/research/institutional_accumulation_full_history/ia_dashboard_evidence_config.json",
    ]
    include += _targets(root)

    seen: set[str] = set()
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in include:
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            zf.write(p, rel)
    return out_zip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--pack-date", default=None)
    ap.add_argument("--output-zip", default=None)
    args = ap.parse_args()
    try:
        out = build_operator_html_evidence_review_pack(
            root=Path(args.root),
            pack_date=args.pack_date,
            output_zip=Path(args.output_zip) if args.output_zip else None,
        )
    except OperatorHtmlPackBuildError as e:
        raise SystemExit(str(e))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
