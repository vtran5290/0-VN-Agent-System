"""Legacy dist_session monitor — non-SSOT deprecation markers."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MONITOR = REPO / "scripts" / "monitor_vnindex_distribution_session.py"
DIST_DOC = REPO / "docs" / "DIST_SESSION_MONITOR.md"


def test_legacy_monitor_script_docstring_warns_non_ssot():
    text = MONITOR.read_text(encoding="utf-8")
    assert "LEGACY" in text
    assert "distribution-risk" in text
    assert "not SSOT" in text or "not SSOT" in text.replace("'", "'")


def test_dist_session_monitor_doc_marks_legacy_outputs():
    text = DIST_DOC.read_text(encoding="utf-8")
    assert "DISTRIBUTION_RISK_OPERATOR_INTEGRATION" in text
    assert "final_action" in text
    assert "not SSOT" in text
