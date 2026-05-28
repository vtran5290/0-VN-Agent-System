from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack-suffix", default="", help="optional suffix (e.g. p02)")
    args = ap.parse_args()

    today = datetime.now().strftime("%Y%m%d")
    root = Path(".")
    out_dir = root / "outputs" / "review_packages"
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.pack_suffix.strip()}" if args.pack_suffix and args.pack_suffix.strip() else ""
    pkg = out_dir / f"institutional_accumulation_backtest_review_pack_{today}{suffix}.zip"
    impl = root / "implementation_report.md"
    testlog = root / "test_log.txt"
    limits = root / "known_limitations.md"
    openq = root / "open_questions_for_chatgpt.md"
    if not impl.is_file():
        _write(
            impl,
            "# Institutional Accumulation Backtest Implementation Report\n\n## Executive summary\nResearch-only backtest framework generated.\n",
        )
    if not testlog.is_file():
        _write(testlog, "No tests logged yet.\n")
    if not limits.is_file():
        _write(limits, "- PIT monthly context unavailable in current repo snapshot.\n")
    if not openq.is_file():
        _write(openq, "- Should PIT fund context be built from weekly consensus snapshots?\n")

    src_inventory = root / "source_file_inventory.csv"
    patch_file = root / "implementation_diff.patch"
    snapshots_dir = root / "source_snapshots"
    _write_source_inventory(root, src_inventory)
    _write_diff_patch(root, patch_file, snapshots_dir)
    snapshot_files = _write_source_snapshots(root, snapshots_dir)

    include = _review_pack_allowlist(root, src_inventory, patch_file, impl, testlog, limits, openq)
    include += snapshot_files
    seen: set[str] = set()
    with zipfile.ZipFile(pkg, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in include:
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            zf.write(p, rel)
    print(f"Wrote {pkg}")


def _review_pack_allowlist(
    root: Path,
    src_inventory: Path,
    patch_file: Path,
    impl: Path,
    testlog: Path,
    limits: Path,
    openq: Path,
) -> list[Path]:
    base = root / "data/research/institutional_accumulation"
    return [
        impl,
        testlog,
        limits,
        openq,
        src_inventory,
        patch_file,
        base / "run_coverage_audit.csv",
        base / "benchmark_validation.csv",
        base / "vin_ticker_audit.csv",
        base / "portfolio_metrics_summary.csv",
        base / "component_ablation_oos.csv",
        base / "yearly_validation.csv",
        base / "regime_validation.csv",
        base / "score_decile_calibration.csv",
        base / "risk_penalty_calibration.csv",
        base / "distribution_flag_validation.csv",
        base / "warning_validation.csv",
        base / "changes_event_study.csv",
        base / "vin_sensitivity_summary.csv",
        root / "reports/research/institutional_accumulation/institutional_accumulation_backtest_summary.html",
    ]


def _write_source_inventory(root: Path, out: Path) -> None:
    targets = []
    targets += list((root / "src/research/institutional_accumulation_backtest").glob("*.py"))
    targets += list((root / "scripts/research/institutional_accumulation_backtest").glob("*.py"))
    targets += list((root / "tests").glob("test_institutional_accumulation_backtest_*.py"))
    targets += [root / "Makefile"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "sha256", "line_count", "purpose"])
        for p in sorted({t for t in targets if t.is_file()}):
            rel = p.relative_to(root).as_posix()
            txt = p.read_text(encoding="utf-8", errors="ignore")
            sha = hashlib.sha256(txt.encode("utf-8")).hexdigest()
            lines = txt.count("\n") + 1 if txt else 0
            purpose = "backtest_source"
            if rel.startswith("tests/"):
                purpose = "backtest_tests"
            elif rel == "Makefile":
                purpose = "commands"
            w.writerow([rel, sha, lines, purpose])


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


def _source_snapshot_targets(root: Path) -> list[Path]:
    targets: list[Path] = []
    targets += sorted((root / "src/research/institutional_accumulation_backtest").glob("*.py"))
    targets += sorted((root / "scripts/research/institutional_accumulation_backtest").glob("*.py"))
    targets += sorted((root / "tests").glob("test_institutional_accumulation_backtest_*.py"))
    mk = root / "Makefile"
    if mk.is_file():
        targets.append(mk)
    return [p for p in targets if p.is_file()]


def _write_source_snapshots(root: Path, snapshots_dir: Path) -> list[Path]:
    if snapshots_dir.exists():
        shutil.rmtree(snapshots_dir)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for src in _source_snapshot_targets(root):
        rel = src.relative_to(root)
        dst = snapshots_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        written.append(dst)
    return written


if __name__ == "__main__":
    main()
