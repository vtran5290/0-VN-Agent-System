from __future__ import annotations

from pathlib import Path

from scripts.research.institutional_accumulation_backtest.build_review_pack import (
    _write_diff_patch,
    _write_source_inventory,
    _write_source_snapshots,
)


def test_source_audit_artifacts_created(tmp_path) -> None:
    root = Path.cwd()
    inv = tmp_path / "source_file_inventory.csv"
    patch = tmp_path / "implementation_diff.patch"
    snapshots = tmp_path / "source_snapshots"
    _write_source_inventory(root, inv)
    _write_diff_patch(root, patch, snapshots)
    snap_files = _write_source_snapshots(root, snapshots)
    assert inv.is_file()
    assert patch.is_file()
    assert patch.read_text(encoding="utf-8").strip() != ""
    assert any(p.suffix == ".py" for p in snap_files)
