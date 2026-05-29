"""Daily input archive utility for cloud daily report validation.

Archives current scan/report/portfolio files into immutable dated snapshots at:
  data/research/cloud_daily_report_validation/archive/YYYYMMDD/

Also maintains a cumulative manifest at:
  data/research/cloud_daily_report_validation/archive/archive_manifest.csv

RESEARCH_ONLY_NOT_PRODUCTION
Writes only to data/research/cloud_daily_report_validation/archive/.
Never writes to production trading paths.
"""
from __future__ import annotations

import hashlib
import logging
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from .schema import ARCHIVE_DIR, _REPO

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source file registry
# ---------------------------------------------------------------------------

_SCAN_SOURCES: list[tuple[str, Path, str]] = [
    # (archive_stem, source_path, file_type)
    (
        "phase36_daily_scan",
        _REPO / "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv",
        "phase36_scan_eod",
    ),
    (
        "phase36_intraday_scan",
        _REPO / "data/research/intraday/phase36_intraday_scan_latest.csv",
        "phase36_scan_intraday",
    ),
    (
        "phase36_intraday_scan_meta",
        _REPO / "data/research/intraday/phase36_intraday_scan_latest_meta.json",
        "phase36_scan_intraday_meta",
    ),
    (
        "cloud_daily_report",
        _REPO / "data/research/reports/cloud_daily_report_latest.html",
        "cloud_report_html",
    ),
    (
        "cloud_daily_report",
        _REPO / "data/research/reports/cloud_daily_report_latest.json",
        "cloud_report_json",
    ),
    (
        "portfolio_state",
        _REPO / "data/trading/live/portfolio_state.json",
        "portfolio_state",
    ),
    (
        "current_positions_derived",
        _REPO / "data/raw/current_positions_derived.json",
        "positions_derived",
    ),
]

MANIFEST_COLS: list[str] = [
    "archive_date",
    "source_path",
    "archived_path",
    "file_type",
    "exists",
    "file_size_bytes",
    "sha256",
    "archived_at",
    "notes",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _archived_name(stem: str, source_path: Path, date_str: str) -> str:
    """Return archive filename like `phase36_daily_scan_20260529.csv`."""
    suffix = source_path.suffix
    return f"{stem}_{date_str}{suffix}"


def _conflict_name(stem: str, source_path: Path, date_str: str, ts: str) -> str:
    suffix = source_path.suffix
    return f"{stem}_{date_str}_conflict_{ts}{suffix}"


# ---------------------------------------------------------------------------
# Core archive function
# ---------------------------------------------------------------------------

def archive_daily_inputs(
    archive_date: Optional[date] = None,
    dry_run: bool = False,
) -> pd.DataFrame:
    """Archive all available current input files into a dated snapshot folder.

    Parameters
    ----------
    archive_date:
        Date to archive under. Defaults to today.
    dry_run:
        If True, compute what would be archived but do not write any files.

    Returns
    -------
    DataFrame with MANIFEST_COLS describing what was archived (or would be).
    """
    if archive_date is None:
        archive_date = date.today()
    date_str = archive_date.strftime("%Y%m%d")
    now_utc = datetime.now(tz=timezone.utc).isoformat()
    date_dir = ARCHIVE_DIR / date_str

    if not dry_run:
        date_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []

    for stem, src, file_type in _SCAN_SOURCES:
        archived_name = _archived_name(stem, src, date_str)
        dst = date_dir / archived_name
        rel_src = str(src.relative_to(_REPO)) if src.is_relative_to(_REPO) else str(src)
        _dst_for_rel = dst if not dry_run else ARCHIVE_DIR / date_str / archived_name
        rel_dst = (
            str(_dst_for_rel.relative_to(_REPO))
            if _dst_for_rel.is_relative_to(_REPO)
            else str(_dst_for_rel)
        )

        if not src.exists():
            rows.append({
                "archive_date": date_str,
                "source_path": rel_src,
                "archived_path": rel_dst,
                "file_type": file_type,
                "exists": False,
                "file_size_bytes": 0,
                "sha256": "",
                "archived_at": now_utc,
                "notes": "source_not_found",
            })
            continue

        src_size = src.stat().st_size
        src_hash = _sha256(src)

        if not dry_run:
            if dst.exists():
                dst_hash = _sha256(dst)
                def _rel(p: Path) -> str:
                    return str(p.relative_to(_REPO)) if p.is_relative_to(_REPO) else str(p)

                if dst_hash == src_hash:
                    # Identical content — skip silently
                    rows.append({
                        "archive_date": date_str,
                        "source_path": rel_src,
                        "archived_path": _rel(dst),
                        "file_type": file_type,
                        "exists": True,
                        "file_size_bytes": src_size,
                        "sha256": src_hash,
                        "archived_at": now_utc,
                        "notes": "already_archived_identical",
                    })
                    continue
                else:
                    # Content differs — write conflict file, don't overwrite
                    ts_tag = datetime.now(tz=timezone.utc).strftime("%H%M%S")
                    conflict_name = _conflict_name(stem, src, date_str, ts_tag)
                    conflict_dst = date_dir / conflict_name
                    shutil.copy2(src, conflict_dst)
                    rows.append({
                        "archive_date": date_str,
                        "source_path": rel_src,
                        "archived_path": _rel(conflict_dst),
                        "file_type": file_type,
                        "exists": True,
                        "file_size_bytes": src_size,
                        "sha256": src_hash,
                        "archived_at": now_utc,
                        "notes": "conflict_existing_differs_wrote_versioned",
                    })
                    logger.warning(
                        "Archive conflict for %s — existing file differs. Wrote: %s",
                        archived_name, conflict_name,
                    )
                    continue
            shutil.copy2(src, dst)
        _ap = (dst if not dry_run else (_dst_for_rel))
        rows.append({
            "archive_date": date_str,
            "source_path": rel_src,
            "archived_path": str(_ap.relative_to(_REPO)) if _ap.is_relative_to(_REPO) else str(_ap),
            "file_type": file_type,
            "exists": True,
            "file_size_bytes": src_size,
            "sha256": src_hash,
            "archived_at": now_utc,
            "notes": "dry_run" if dry_run else "archived",
        })
        if not dry_run:
            logger.info("Archived %s → %s", rel_src, dst.name)

    df = pd.DataFrame(rows, columns=MANIFEST_COLS)
    return df


# ---------------------------------------------------------------------------
# Manifest writers
# ---------------------------------------------------------------------------

def write_date_manifest(df: pd.DataFrame, archive_date: date) -> Path:
    """Write per-date manifest CSV."""
    date_str = archive_date.strftime("%Y%m%d")
    date_dir = ARCHIVE_DIR / date_str
    date_dir.mkdir(parents=True, exist_ok=True)
    p = date_dir / f"archive_manifest_{date_str}.csv"
    df.to_csv(p, index=False)
    return p


def update_cumulative_manifest(df: pd.DataFrame) -> Path:
    """Append new rows to cumulative archive_manifest.csv (no duplicate key overwrite)."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    p = ARCHIVE_DIR / "archive_manifest.csv"

    if p.exists():
        existing = pd.read_csv(p, dtype=str)
        # De-duplicate: keep existing rows for same (archive_date, source_path, file_type)
        # unless the new row is a conflict/versioned write
        key_cols = ["archive_date", "source_path", "file_type"]
        non_conflict_new = df[~df["notes"].str.contains("conflict", na=False)]
        conflict_new = df[df["notes"].str.contains("conflict", na=False)]

        # For non-conflict rows: drop existing if same key
        if not non_conflict_new.empty:
            mask = existing[key_cols].apply(tuple, axis=1).isin(
                non_conflict_new[key_cols].apply(tuple, axis=1)
            )
            existing = existing[~mask]

        combined = pd.concat([existing, non_conflict_new, conflict_new], ignore_index=True)
    else:
        combined = df

    combined.to_csv(p, index=False)
    return p


def run_archive(archive_date: Optional[date] = None, dry_run: bool = False) -> tuple[pd.DataFrame, Path, Path]:
    """Run archive + write both manifests. Returns (df, date_manifest_path, cumulative_path)."""
    if archive_date is None:
        archive_date = date.today()
    df = archive_daily_inputs(archive_date=archive_date, dry_run=dry_run)
    if dry_run:
        logger.info("Dry run — no files written")
        return df, Path("/dev/null"), Path("/dev/null")
    date_mp = write_date_manifest(df, archive_date)
    cum_mp = update_cumulative_manifest(df)
    n_archived = (df["notes"] == "archived").sum()
    n_skipped = (df["notes"] == "already_archived_identical").sum()
    n_missing = (~df["exists"]).sum()
    logger.info(
        "Archive complete for %s: %d archived, %d skipped (identical), %d source missing",
        archive_date.strftime("%Y%m%d"), n_archived, n_skipped, n_missing,
    )
    return df, date_mp, cum_mp
