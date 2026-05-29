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


class P3PackBuildError(RuntimeError):
    pass


def _write_diff_patch(root: Path, out: Path, snapshots_dir: Path) -> None:
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
        diff = f"# No git diff available; source snapshots generated at {snapshots_dir.as_posix()}\n"
    out.write_text(diff, encoding="utf-8")


def _targets(root: Path) -> list[Path]:
    t: list[Path] = []
    t += sorted((root / "src/research/institutional_accumulation_backtest").glob("*.py"))
    t += sorted((root / "scripts/research/institutional_accumulation_backtest").glob("*.py"))
    t += sorted((root / "tests").glob("test_institutional_accumulation_backtest_*.py"))
    t += sorted((root / "tests").glob("test_institutional_accumulation_p1_*.py"))
    t += sorted((root / "tests").glob("test_institutional_accumulation_p2_*.py"))
    t += sorted((root / "tests").glob("test_institutional_accumulation_p3_*.py"))
    mk = root / "Makefile"
    if mk.is_file():
        t.append(mk)
    return [p for p in t if p.is_file()]


def _write_source_inventory(root: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "sha256", "line_count", "purpose"])
        for p in _targets(root):
            rel = p.relative_to(root).as_posix()
            txt = p.read_text(encoding="utf-8", errors="ignore")
            w.writerow([rel, hashlib.sha256(txt.encode("utf-8")).hexdigest(), txt.count("\n") + 1, "p3_portfolio_source"])


def _write_source_snapshots(root: Path, snapshots_dir: Path) -> list[Path]:
    if snapshots_dir.exists():
        shutil.rmtree(snapshots_dir)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for src in _targets(root):
        rel = src.relative_to(root)
        dst = snapshots_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        out.append(dst)
    return out


def _validate_p3_pack(
    *,
    root: Path,
    data_dir: Path,
    html_path: Path,
    report_path: Path,
) -> None:
    outcomes_path = data_dir / "forward_outcomes_panel.parquet"
    if not outcomes_path.is_file():
        raise P3PackBuildError("BLOCKED_MISSING_SOURCE")

    outcomes = pd.read_parquet(outcomes_path)
    if len(outcomes) < 10000:
        raise P3PackBuildError("BLOCKED_FIXTURE_CONTAMINATION")

    if "ticker" in outcomes.columns:
        uniq = set(str(t) for t in outcomes["ticker"].dropna().unique().tolist())
        if uniq.issubset({"AAA", "BBB"}):
            raise P3PackBuildError("BLOCKED_FIXTURE_CONTAMINATION")

    eq_path = data_dir / "p3_portfolio_equity_curves.csv"
    if not eq_path.is_file() or len(pd.read_csv(eq_path)) == 0:
        raise P3PackBuildError("BLOCKED_MISSING_EQUITY_CURVES")

    report_txt = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    if "P3" not in report_txt or "Portfolio Simulation" not in report_txt:
        raise P3PackBuildError("BLOCKED_STALE_REPORT")

    html_txt = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    if len(html_txt.encode("utf-8")) <= 1000:
        raise P3PackBuildError("BLOCKED_FIXTURE_CONTAMINATION")
    if "P3 Portfolio Simulation" not in html_txt:
        raise P3PackBuildError("BLOCKED_FIXTURE_CONTAMINATION")
    if "Research-only" not in html_txt or "RESEARCH_ONLY_NOT_PRODUCTION" not in html_txt:
        raise P3PackBuildError("BLOCKED_FIXTURE_CONTAMINATION")


def build_p3_review_pack(
    root: Path = Path("."),
    out_dir: Path | None = None,
    pack_date: str | None = None,
    pack_suffix: str | None = None,
    output_zip: Path | None = None,
) -> Path:
    root = Path(root)
    today = pack_date or datetime.now().strftime("%Y%m%d")
    if output_zip is None:
        out_base = out_dir if out_dir is not None else (root / "outputs" / "review_packages")
        suffix = f"_{pack_suffix.strip()}" if pack_suffix and pack_suffix.strip() else ""
        out_zip = Path(out_base) / f"institutional_accumulation_p3_portfolio_review_pack_{today}{suffix}.zip"
    else:
        out_zip = Path(output_zip)
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    inv = root / "source_file_inventory.csv"
    patch = root / "implementation_diff.patch"
    snaps = root / "source_snapshots"
    _write_source_inventory(root, inv)
    _write_diff_patch(root, patch, snaps)
    snap_files = _write_source_snapshots(root, snaps)

    p3 = root / "data" / "research" / "institutional_accumulation"
    report = root / "implementation_report.md"
    html = root / "reports" / "research" / "institutional_accumulation" / "p3_portfolio_simulation.html"
    _validate_p3_pack(root=root, data_dir=p3, html_path=html, report_path=report)

    include = [
        report,
        root / "test_log.txt",
        root / "open_questions_for_chatgpt.md",
        inv,
        patch,
        p3 / "p3_portfolio_equity_curves.csv",
        p3 / "p3_portfolio_metrics.csv",
        p3 / "p3_turnover_capacity.csv",
        p3 / "p3_yearly_returns.csv",
        p3 / "p3_regime_returns.csv",
        p3 / "p3_diagnostic_summary.csv",
        html,
    ]
    include += snap_files
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
    ap.add_argument("--pack-suffix", default=None)
    ap.add_argument("--output-zip", default=None)
    args = ap.parse_args()
    try:
        out = build_p3_review_pack(
            root=Path(args.root),
            pack_date=args.pack_date,
            pack_suffix=args.pack_suffix,
            output_zip=Path(args.output_zip) if args.output_zip else None,
        )
    except P3PackBuildError as e:
        raise SystemExit(str(e))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
