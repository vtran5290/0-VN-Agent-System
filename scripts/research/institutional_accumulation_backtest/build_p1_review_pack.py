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


class P1PackBuildError(RuntimeError):
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
            w.writerow([rel, hashlib.sha256(txt.encode("utf-8")).hexdigest(), txt.count("\n") + 1, "p1_research_source"])


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


def _safe_read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.is_file() else pd.DataFrame()


def _build_p1_output_audit(
    *,
    root: Path,
    data_dir: Path,
    html_path: Path,
    report_path: Path,
) -> tuple[pd.DataFrame, str]:
    outcomes_path = data_dir / "forward_outcomes_panel.parquet"
    measurement_path = data_dir / "p1_measurement_integrity.csv"
    autopsy_path = data_dir / "p1_score_decile_autopsy.csv"
    audit_path = data_dir / "p1_output_audit.csv"

    rows: list[dict[str, object]] = []
    final_status = "OK"

    if not outcomes_path.is_file():
        final_status = "BLOCKED_MISSING_SOURCE"
        rows.append({"metric": "source_outcomes_rows", "value": "", "status": "BLOCKED_MISSING_SOURCE", "note": "forward_outcomes_panel.parquet not found"})
    else:
        outcomes = pd.read_parquet(outcomes_path)
        ticker_n = int(outcomes["ticker"].nunique()) if "ticker" in outcomes.columns else 0
        date_min = str(pd.to_datetime(outcomes["scan_date"], errors="coerce").min().date()) if "scan_date" in outcomes.columns else ""
        date_max = str(pd.to_datetime(outcomes["scan_date"], errors="coerce").max().date()) if "scan_date" in outcomes.columns else ""
        rows += [
            {"metric": "source_outcomes_rows", "value": int(len(outcomes)), "status": "OK", "note": ""},
            {"metric": "source_ticker_count", "value": ticker_n, "status": "OK", "note": ""},
            {"metric": "source_scan_date_min", "value": date_min, "status": "OK", "note": ""},
            {"metric": "source_scan_date_max", "value": date_max, "status": "OK", "note": ""},
        ]
        if len(outcomes) < 10000 or ticker_n < 100:
            final_status = "BLOCKED_FIXTURE_CONTAMINATION"

    m = _safe_read_csv(measurement_path)
    full = m[m.get("subset", pd.Series(dtype=str)) == "full_sample"] if not m.empty else pd.DataFrame()
    full_n = int(full["n"].iloc[0]) if not full.empty and "n" in full.columns else 0
    full_t = int(full["ticker_n"].iloc[0]) if not full.empty and "ticker_n" in full.columns else 0
    full_ok = full_n >= 10000 and full_t >= 100
    if not full_ok:
        final_status = "BLOCKED_FIXTURE_CONTAMINATION"
    rows += [
        {"metric": "p1_measurement_full_sample_n", "value": full_n, "status": "OK" if full_ok else "BLOCKED_FIXTURE_CONTAMINATION", "note": "expect >=10000"},
        {"metric": "p1_measurement_full_sample_ticker_n", "value": full_t, "status": "OK" if full_ok else "BLOCKED_FIXTURE_CONTAMINATION", "note": "expect >=100"},
    ]

    aut = _safe_read_csv(autopsy_path)
    aut_n = int(pd.to_numeric(aut.get("n", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not aut.empty else 0
    aut_ok = aut_n >= 10000
    if not aut_ok:
        final_status = "BLOCKED_FIXTURE_CONTAMINATION"
    rows.append({"metric": "p1_autopsy_total_n", "value": aut_n, "status": "OK" if aut_ok else "BLOCKED_FIXTURE_CONTAMINATION", "note": "expect >=10000"})

    fixture_only = False
    if outcomes_path.is_file():
        outcomes = pd.read_parquet(outcomes_path)
        if "ticker" in outcomes.columns:
            uniq = set(str(t) for t in outcomes["ticker"].dropna().unique().tolist())
            fixture_only = uniq.issubset({"AAA", "BBB"})
            if fixture_only:
                final_status = "BLOCKED_FIXTURE_CONTAMINATION"

    html_txt = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    html_size = len(html_txt.encode("utf-8"))
    has_title = "P1 Institutional Accumulation Score Inversion Diagnostic" in html_txt
    if html_size <= 1000 or not has_title:
        final_status = "BLOCKED_FIXTURE_CONTAMINATION"
    rows += [
        {"metric": "p1_html_report_size_bytes", "value": html_size, "status": "OK" if html_size > 1000 else "BLOCKED_FIXTURE_CONTAMINATION", "note": "expect >1000"},
        {"metric": "p1_html_has_required_title", "value": bool(has_title), "status": "OK" if has_title else "BLOCKED_FIXTURE_CONTAMINATION", "note": "expect required title string"},
    ]

    report_txt = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    is_p1 = (
        "P1 Score Inversion Diagnostic Implementation Report" in report_txt
        or "P1.1 Score Inversion Diagnostic Cleanup Implementation Report" in report_txt
    )
    report_status = "OK" if is_p1 else "BLOCKED_STALE_REPORT"
    if not is_p1 and final_status == "OK":
        final_status = "BLOCKED_STALE_REPORT"
    rows.append({"metric": "implementation_report_is_p1", "value": bool(is_p1), "status": report_status, "note": "must be P1-specific report"})
    rows.append(
        {
            "metric": "fixture_contamination_check",
            "value": "PASS" if final_status == "OK" and not fixture_only else "FAIL",
            "status": final_status if final_status != "OK" else "OK",
            "note": "guards: scale, html quality, ticker set, report freshness",
        }
    )
    audit = pd.DataFrame(rows, columns=["metric", "value", "status", "note"])
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_path, index=False)
    return audit, final_status


def build_p1_review_pack(
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
        out_zip = Path(out_base) / f"institutional_accumulation_p1_score_diagnostic_review_pack_{today}{suffix}.zip"
    else:
        out_zip = Path(output_zip)
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    inv = root / "source_file_inventory.csv"
    patch = root / "implementation_diff.patch"
    snaps = root / "source_snapshots"
    _write_source_inventory(root, inv)
    _write_diff_patch(root, patch, snaps)
    snap_files = _write_source_snapshots(root, snaps)

    p1 = root / "data" / "research" / "institutional_accumulation"
    report = root / "implementation_report.md"
    html = root / "reports" / "research" / "institutional_accumulation" / "p1_score_inversion_diagnostic.html"
    _audit, status = _build_p1_output_audit(root=root, data_dir=p1, html_path=html, report_path=report)
    if status != "OK":
        raise P1PackBuildError(status)

    include = [
        report,
        root / "test_log.txt",
        root / "open_questions_for_chatgpt.md",
        inv,
        patch,
        p1 / "p1_measurement_integrity.csv",
        p1 / "p1_score_decile_autopsy.csv",
        p1 / "p1_component_diagnostics.csv",
        p1 / "p1_feature_lead_lag.csv",
        p1 / "p1_accumulation_vs_exhaustion.csv",
        p1 / "p1_unit_audit.csv",
        p1 / "p1_distribution_flag_diagnostic.csv",
        p1 / "p1_regime_dependency.csv",
        p1 / "p1_horizon_dependency.csv",
        p1 / "p1_tier_threshold_diagnostics.csv",
        p1 / "p1_diagnostic_summary.csv",
        p1 / "p1_output_audit.csv",
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
        out = build_p1_review_pack(
            root=Path(args.root),
            pack_date=args.pack_date,
            pack_suffix=args.pack_suffix,
            output_zip=Path(args.output_zip) if args.output_zip else None,
        )
    except P1PackBuildError as e:
        raise SystemExit(str(e))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

