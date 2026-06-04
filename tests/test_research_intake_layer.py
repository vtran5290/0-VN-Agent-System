"""Lightweight tests for Research Intake Layer (Stage 0 — no trading logic)."""

from __future__ import annotations

import ast
import csv
import importlib.util
from pathlib import Path

import pytest

from src.research.intake.schema import (
    INDEX_COLUMNS,
    INDEX_PATH,
    SAFETY_PHRASE,
    SOURCE_TYPES,
    STATUSES,
    THESIS_IMPACTS,
    WATCHLIST_ACTIONS,
)
from src.research.intake.summarize_index import summarize

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = REPO / "templates" / "research"
WORKFLOW_DOC = REPO / "docs" / "research" / "RESEARCH_INTAKE_WORKFLOW.md"
SUMMARIZE_PY = REPO / "src" / "research" / "intake" / "summarize_index.py"
WRAPPER_PY = REPO / "scripts" / "research" / "research_intake_summary.py"

FORBIDDEN_IMPORT_PREFIXES = (
    "src.trading",
    "src.oms",
    "src.execution",
    "src.broker",
    "dnse",
)


def test_research_index_schema_file_exists():
    assert INDEX_PATH.is_file(), f"missing {INDEX_PATH}"


def test_research_index_header_columns():
    with INDEX_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
    assert tuple(header) == INDEX_COLUMNS


def test_allowed_enums_documented_in_schema():
    assert "equity_research" in SOURCE_TYPES
    assert "RAW_EXTRACTED" in STATUSES
    assert "IMPROVED" in THESIS_IMPACTS
    assert "UPGRADE" in WATCHLIST_ACTIONS
    assert len(SOURCE_TYPES) == 8
    assert len(STATUSES) == 5
    assert len(THESIS_IMPACTS) == 5
    assert len(WATCHLIST_ACTIONS) == 6


@pytest.mark.parametrize(
    "name",
    [
        "research_card_template.md",
        "weekly_research_digest_template.md",
        "sector_thesis_dashboard_template.md",
    ],
)
def test_templates_contain_safety_wording(name: str):
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    assert SAFETY_PHRASE in text
    assert "final_action" in text


def test_workflow_doc_states_research_cannot_override_final_action():
    text = WORKFLOW_DOC.read_text(encoding="utf-8")
    assert SAFETY_PHRASE in text
    assert "does not set or override" in text.lower() or "does **not** set or override" in text
    assert "Override `final_action`" in text or "override `final_action`" in text
    assert "Create `final_action`" in text or "create `final_action`" in text


def _imports_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_summary_script_no_trading_execution_imports():
    for path in (SUMMARIZE_PY, WRAPPER_PY):
        imports = _imports_in_file(path)
        for imp in imports:
            for forbidden in FORBIDDEN_IMPORT_PREFIXES:
                assert not imp.startswith(forbidden), f"{path.name} imports {imp}"


def test_summarize_index_empty_index():
    out = summarize(INDEX_PATH)
    assert "Research intake index summary" in out
    assert SAFETY_PHRASE.replace(".", "") in out.replace(".", "") or SAFETY_PHRASE in out


def test_intake_package_importable():
    spec = importlib.util.find_spec("src.research.intake")
    assert spec is not None


def test_stage0_research_index_latest_has_batch_rows():
    latest = REPO / "data" / "research" / "stage0" / "research_index_latest.csv"
    if not latest.is_file():
        pytest.skip("stage0 index not bootstrapped yet")
    with latest.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 80
    assert tuple(rows[0].keys()) == INDEX_COLUMNS
