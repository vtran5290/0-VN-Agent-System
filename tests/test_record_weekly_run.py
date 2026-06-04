"""Tests for append-only weekly evidence logging."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
import yaml

from src.review.record_weekly_run import DEFAULT_LOG, record_weekly_run


def _tracker(tmp_path: Path) -> Path:
    src = Path(__file__).resolve().parents[1] / "data" / "roadmap" / "stage_tracker.yaml"
    p = tmp_path / "stage_tracker.yaml"
    p.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return p


def test_appends_jsonl_history(tmp_path):
    tracker = _tracker(tmp_path)
    log = tmp_path / "weekly_review_log.jsonl"
    record_weekly_run(
        date="2026-05-22",
        weekly_reviewed=True,
        tracker_path=tracker,
        log_path=log,
    )
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["date"] == "2026-05-22"
    assert row["weekly_reviewed"] is True


def test_increments_clean_weekly_only_with_review_and_zero_incidents(tmp_path):
    tracker = _tracker(tmp_path)
    log = tmp_path / "log.jsonl"
    record_weekly_run(
        date="2026-05-22",
        weekly_reviewed=True,
        tracker_path=tracker,
        log_path=log,
    )
    data = yaml.safe_load(tracker.read_text(encoding="utf-8"))
    assert data["evidence"]["clean_weekly_cycles"] == 1
    assert data["last_reviews"]["last_weekly_run_date"] == "2026-05-22"


def test_increments_clean_order_intent_only_with_review_and_zero_incidents(tmp_path):
    tracker = _tracker(tmp_path)
    log = tmp_path / "log.jsonl"
    record_weekly_run(
        date="2026-05-22",
        order_intent_reviewed=True,
        order_intent_rows_reviewed=5,
        tracker_path=tracker,
        log_path=log,
    )
    data = yaml.safe_load(tracker.read_text(encoding="utf-8"))
    assert data["evidence"]["clean_order_intent_cycles"] == 1
    assert data["evidence"]["order_intent_rows_reviewed"] == 5
    assert data["last_reviews"]["last_order_intent_date"] == "2026-05-22"


def test_no_clean_weekly_when_stale_incidents(tmp_path):
    tracker = _tracker(tmp_path)
    log = tmp_path / "log.jsonl"
    record_weekly_run(
        date="2026-05-22",
        weekly_reviewed=True,
        stale_data_incidents=1,
        tracker_path=tracker,
        log_path=log,
    )
    data = yaml.safe_load(tracker.read_text(encoding="utf-8"))
    assert data["evidence"]["clean_weekly_cycles"] == 0
    assert data["evidence"]["stale_data_incidents"] == 1
    row = json.loads(log.read_text(encoding="utf-8").strip())
    assert row["clean_weekly_incremented"] is False


def test_no_clean_order_intent_when_unintended_incidents(tmp_path):
    tracker = _tracker(tmp_path)
    log = tmp_path / "log.jsonl"
    record_weekly_run(
        date="2026-05-22",
        order_intent_reviewed=True,
        unintended_order_incidents=1,
        tracker_path=tracker,
        log_path=log,
    )
    data = yaml.safe_load(tracker.read_text(encoding="utf-8"))
    assert data["evidence"]["clean_order_intent_cycles"] == 0
    assert data["evidence"]["unintended_order_incidents"] == 1


def test_no_increment_without_human_review_flags(tmp_path):
    tracker = _tracker(tmp_path)
    log = tmp_path / "log.jsonl"
    record_weekly_run(date="2026-05-22", tracker_path=tracker, log_path=log)
    data = yaml.safe_load(tracker.read_text(encoding="utf-8"))
    assert data["evidence"]["clean_weekly_cycles"] == 0
    assert data["evidence"]["clean_order_intent_cycles"] == 0


def test_fails_cleanly_if_tracker_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="Stage tracker not found"):
        record_weekly_run(
            date="2026-05-22",
            weekly_reviewed=True,
            tracker_path=tmp_path / "missing.yaml",
            log_path=tmp_path / "log.jsonl",
        )


def test_no_broker_live_trading_imports():
    path = Path(__file__).resolve().parents[1] / "src" / "review" / "record_weekly_run.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    banned_substrings = ("broker", "live_workflow", "order_intent_dry_run", "src.trading")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for bad in banned_substrings:
                    assert bad not in alias.name
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for bad in banned_substrings:
                assert bad not in mod


def test_default_log_path_under_data_roadmap():
    assert DEFAULT_LOG.name == "weekly_review_log.jsonl"
    assert "roadmap" in str(DEFAULT_LOG)
