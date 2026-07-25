"""SSOT certification guard — refuse family runs on a drifted panel."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PANEL = REPO / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
DEFAULT_MANIFEST = REPO / "data" / "fireant_ssot" / "manifest.json"


class PanelNotCertified(RuntimeError):
    """Raised when panel bytes do not match the certified manifest sha256."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_certified_sha(manifest_path: Path = DEFAULT_MANIFEST) -> str:
    if not manifest_path.exists():
        raise PanelNotCertified(f"manifest missing: {manifest_path}")
    data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    panel_meta = data.get("ta_ohlcv_panel") or {}
    sha = panel_meta.get("sha256")
    if not sha or not isinstance(sha, str):
        raise PanelNotCertified("manifest.ta_ohlcv_panel.sha256 missing")
    return sha


def assert_panel_certified(
    panel_path: Path = DEFAULT_PANEL,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> str:
    """
    Return the matching sha256, or raise PanelNotCertified on drift/missing files.
    """
    if not panel_path.exists():
        raise PanelNotCertified(f"panel missing: {panel_path}")
    expected = read_certified_sha(manifest_path)
    actual = sha256_file(panel_path)
    if actual != expected:
        raise PanelNotCertified(
            f"SSOT panel sha drift: file={actual[:16]}… manifest={expected[:16]}… "
            f"Refuse to run. Re-certify via scripts/build_fireant_ssot.py."
        )
    return actual
