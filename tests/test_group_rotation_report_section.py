"""Tests for group rotation dashboard report section (no production paths)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.research.group_rotation.report_section import render_group_rotation_context_md

REPO = Path(__file__).resolve().parents[1]
CSV = REPO / "data/research/group_rotation/group_rotation_latest.csv"


def test_render_section_contains_safety_disclaimer():
    text = render_group_rotation_context_md(CSV if CSV.is_file() else None)
    assert "DASHBOARD ONLY" in text
    assert "final_action" in text
    assert "execution_allowed_flag" in text


def test_render_section_validated_before_research_only(tmp_path: Path):
    df = pd.DataFrame([
        {
            "grouping_layer": "theme_tag",
            "group_name": "rubber",
            "tier": "D",
            "group_rotation_score": 1.15,
            "signal_badge": "GROUP_RESEARCH_ONLY",
            "breadth_equal_weight": 0.6,
            "a3_gate_status": "GATE_PASS",
            "operator_note": "Research-only",
            "snapshot_date": "2026-05-25",
            "execution_allowed_flag": False,
        },
        {
            "grouping_layer": "theme_tag",
            "group_name": "steel_a",
            "tier": "A",
            "group_rotation_score": 0.55,
            "signal_badge": "GROUP_WEAK_ROTATION",
            "breadth_equal_weight": 0.4,
            "a3_gate_status": "GATE_FAIL",
            "operator_note": "Broad-based",
            "snapshot_date": "2026-05-25",
            "execution_allowed_flag": False,
        },
    ])
    p = tmp_path / "gr.csv"
    df.to_csv(p, index=False)
    text = render_group_rotation_context_md(p)
    v_pos = text.find("### Validated groups")
    r_pos = text.find("### Research-only")
    assert v_pos != -1 and r_pos != -1 and v_pos < r_pos
    assert "steel_a" in text
    assert "rubber" in text
