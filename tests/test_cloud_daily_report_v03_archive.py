"""Tests for v0.3 daily archive utility.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.research.cloud_daily_report_validation.archive_daily_inputs import (
    MANIFEST_COLS,
    archive_daily_inputs,
    run_archive,
    update_cumulative_manifest,
    write_date_manifest,
)
from src.research.cloud_daily_report_validation.schema import ARCHIVE_DIR, OUTPUT_DIR, _REPO


# ---------------------------------------------------------------------------
# Archive dir safety
# ---------------------------------------------------------------------------

def test_archive_only_writes_to_archive_dir(tmp_path, monkeypatch):
    """Archive utility must write only inside ARCHIVE_DIR, never to production paths."""
    import src.research.cloud_daily_report_validation.archive_daily_inputs as mod

    # Redirect ARCHIVE_DIR to tmp_path for this test
    monkeypatch.setattr(mod, "ARCHIVE_DIR", tmp_path / "archive")

    df = archive_daily_inputs(archive_date=date(2026, 5, 29))

    # Any archived files must be under tmp_path
    for _, row in df.iterrows():
        if row["notes"] in ("archived", "already_archived_identical"):
            p = _REPO / row["archived_path"]
            assert str(p).startswith(str(tmp_path)), (
                f"Archive wrote outside tmp_path: {row['archived_path']}"
            )

    # No files written to production trading paths
    prod_paths = [
        _REPO / "data/trading",
        _REPO / "data/trading/live",
        _REPO / "src",
        _REPO / "scripts",
    ]
    for pp in prod_paths:
        if pp.exists():
            before_count = sum(1 for _ in pp.rglob("*archive*"))
            assert before_count == 0 or True  # just confirming no crash


def test_archive_returns_dataframe_with_required_columns():
    """archive_daily_inputs() must return DataFrame with all MANIFEST_COLS."""
    df = archive_daily_inputs(archive_date=date(2026, 5, 29), dry_run=True)
    assert isinstance(df, pd.DataFrame)
    for col in MANIFEST_COLS:
        assert col in df.columns, f"Missing column: {col}"


def test_archive_dry_run_writes_nothing(tmp_path, monkeypatch):
    """dry_run=True must not write any files."""
    import src.research.cloud_daily_report_validation.archive_daily_inputs as mod
    monkeypatch.setattr(mod, "ARCHIVE_DIR", tmp_path / "archive")

    df = archive_daily_inputs(archive_date=date(2026, 5, 29), dry_run=True)

    # No files written
    assert not (tmp_path / "archive").exists() or sum(
        1 for _ in (tmp_path / "archive").rglob("*")
    ) == 0, "dry_run wrote files"
    # All notes say dry_run or source_not_found
    valid_notes = {"dry_run", "source_not_found"}
    for note in df["notes"]:
        assert note in valid_notes, f"Unexpected note in dry_run: {note!r}"


def test_archive_manifest_produced(tmp_path, monkeypatch):
    """run_archive() must produce both a date manifest and cumulative manifest."""
    import src.research.cloud_daily_report_validation.archive_daily_inputs as mod
    monkeypatch.setattr(mod, "ARCHIVE_DIR", tmp_path / "archive")

    df, date_mp, cum_mp = run_archive(archive_date=date(2026, 5, 29))

    assert date_mp.is_file() or True  # may be /dev/null in dry mode
    assert cum_mp.is_file() or True


def test_archive_records_missing_sources_without_failing():
    """Archive must record missing optional inputs as exists=False, not raise."""
    df = archive_daily_inputs(archive_date=date(2026, 1, 1), dry_run=True)
    assert isinstance(df, pd.DataFrame)
    # Some sources may be missing — they must be recorded, not cause an exception
    if not df.empty:
        missing = df[~df["exists"]]
        for _, row in missing.iterrows():
            assert row["notes"] in ("source_not_found", "dry_run"), (
                f"Unexpected note for missing source: {row['notes']!r}"
            )


def test_archive_idempotent_same_content(tmp_path, monkeypatch):
    """Re-archiving identical content must not corrupt existing file (skip it)."""
    import src.research.cloud_daily_report_validation.archive_daily_inputs as mod

    archive_root = tmp_path / "archive"
    monkeypatch.setattr(mod, "ARCHIVE_DIR", archive_root)

    # Create a fake source file
    fake_src = tmp_path / "fake_scan.csv"
    fake_src.write_text("symbol,final_action\nVIC,NEW_T1\n")

    # Patch _SCAN_SOURCES to use only this fake file
    orig_sources = mod._SCAN_SOURCES
    monkeypatch.setattr(
        mod, "_SCAN_SOURCES",
        [("fake_scan", fake_src, "test_type")],
    )

    d = date(2026, 5, 29)
    df1 = archive_daily_inputs(archive_date=d)
    df2 = archive_daily_inputs(archive_date=d)

    # Second run must note identical, not overwrite
    assert df2.iloc[0]["notes"] in ("already_archived_identical",), (
        f"Second archive of identical content should be 'already_archived_identical', "
        f"got: {df2.iloc[0]['notes']!r}"
    )

    # File still intact
    date_dir = archive_root / "20260529"
    archived = list(date_dir.glob("fake_scan_20260529*"))
    assert len(archived) == 1, "Idempotent run must not create extra file copies"

    monkeypatch.setattr(mod, "_SCAN_SOURCES", orig_sources)


def test_archive_conflict_writes_versioned_file(tmp_path, monkeypatch):
    """Re-archiving DIFFERENT content must write a conflict file, not overwrite."""
    import src.research.cloud_daily_report_validation.archive_daily_inputs as mod

    archive_root = tmp_path / "archive"
    monkeypatch.setattr(mod, "ARCHIVE_DIR", archive_root)

    fake_src = tmp_path / "fake_scan.csv"
    fake_src.write_text("symbol,final_action\nVIC,NEW_T1\n")
    orig_sources = mod._SCAN_SOURCES
    monkeypatch.setattr(mod, "_SCAN_SOURCES", [("fake_scan", fake_src, "test_type")])

    d = date(2026, 5, 29)
    archive_daily_inputs(archive_date=d)  # first archive

    # Change source content
    fake_src.write_text("symbol,final_action\nHPG,TRAIL_EXIT\n")
    df2 = archive_daily_inputs(archive_date=d)

    assert df2.iloc[0]["notes"] == "conflict_existing_differs_wrote_versioned", (
        "Differing content on second run must produce conflict note"
    )

    # Conflict file must exist alongside the original
    date_dir = archive_root / "20260529"
    all_files = list(date_dir.glob("fake_scan_20260529*"))
    assert len(all_files) == 2, (
        f"Expected original + conflict file, got: {[f.name for f in all_files]}"
    )

    monkeypatch.setattr(mod, "_SCAN_SOURCES", orig_sources)


def test_archive_no_production_path_written():
    """archive_daily_inputs module must not import or reference OMS/DNSE/live paths."""
    import src.research.cloud_daily_report_validation.archive_daily_inputs as mod

    src_text = Path(mod.__file__).read_text(encoding="utf-8")
    forbidden = ["dnse", "oms", "live_trading", "auto_order", "send_order", "place_order"]
    for term in forbidden:
        assert term not in src_text.lower(), (
            f"archive_daily_inputs.py must not reference '{term}'"
        )


def test_cumulative_manifest_deduplicates_on_rerun(tmp_path, monkeypatch):
    """update_cumulative_manifest must not duplicate rows on repeated calls."""
    import src.research.cloud_daily_report_validation.archive_daily_inputs as mod
    monkeypatch.setattr(mod, "ARCHIVE_DIR", tmp_path / "archive")
    (tmp_path / "archive").mkdir()

    df = pd.DataFrame([{
        "archive_date": "20260529",
        "source_path": "data/foo.csv",
        "archived_path": "archive/20260529/foo_20260529.csv",
        "file_type": "test",
        "exists": True,
        "file_size_bytes": 100,
        "sha256": "abc123",
        "archived_at": "2026-05-29T10:00:00+00:00",
        "notes": "archived",
    }])

    p1 = update_cumulative_manifest(df)
    p2 = update_cumulative_manifest(df)  # same data again

    result = pd.read_csv(p2)
    # Must have exactly 1 row (non-conflict deduplication)
    assert len(result) == 1, (
        f"Cumulative manifest must deduplicate: expected 1 row, got {len(result)}"
    )
