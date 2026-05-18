"""Pytest fixtures for weekly report tests (repo + extracted review zip)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
REVIEW_SCAN_FIXTURE = REPO / "tests" / "fixtures" / "phase36_daily_scan_review_fixture.csv"


@pytest.fixture
def review_scan_path(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point phase36 scan SSOT at review-only CSV (not production latest)."""
    assert REVIEW_SCAN_FIXTURE.is_file(), f"Missing {REVIEW_SCAN_FIXTURE}"
    monkeypatch.setenv("PHASE36_DAILY_SCAN_PATH", str(REVIEW_SCAN_FIXTURE))
    return REVIEW_SCAN_FIXTURE
