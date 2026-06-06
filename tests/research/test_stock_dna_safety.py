"""
Tests 10-11, 16, 20: Production safety guardrails.
  Test 10: A3 baseline final_action is not modified
  Test 11: Overlay variants are research-only
  Test 16: Stock DNA score cannot create/block/size/route live orders
  Test 20: Import firewall CI check — no production modules import from research/stock_dna
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.overlay import (
    _verify_production_columns_intact,
    annotate_t2_support,
)
from src.trading.research.stock_dna.schema import (
    COL_DNA_CONTEXT_SCORE,
    COL_DNA_DANGER_ACTIVE,
    COL_DNA_T2_ACTIVE,
    DNA_ANNOTATION_COLS,
    PROTECTED_PRODUCTION_COLS,
    assert_output_path_safe,
)


def _make_mock_scan(n: int = 10) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "symbol":       [f"SYM{i:03d}" for i in range(n)],
        "final_action": ["HOLD"] * n,
        "a3_rank_score": rng.uniform(0, 1, n),
        "close":        rng.uniform(10, 100, n),
        "ema20":        rng.uniform(10, 100, n),
        "ema50":        rng.uniform(10, 100, n),
        "sma100":       rng.uniform(10, 100, n),
        "sma150":       rng.uniform(10, 100, n),
        "as_of_date":   "2026-01-15",
    })


def _make_mock_profiles(symbols: list) -> pd.DataFrame:
    rows = []
    for sym in symbols[:5]:
        rows.append({
            "symbol": sym,
            "primary_support_line": "ema20",
            "danger_line": "sma100",
            "confidence": "MEDIUM",
            "line_obedience_score_raw": 0.65,
        })
    return pd.DataFrame(rows)


# ── Test 10: A3 baseline final_action not modified ────────────────────────────

class TestFinalActionNotModified:

    def test_final_action_unchanged_after_annotation(self):
        scan = _make_mock_scan()
        original_actions = scan["final_action"].copy()
        profiles = _make_mock_profiles(scan["symbol"].tolist())

        annotated = annotate_t2_support(scan.copy(), profiles)

        assert (annotated["final_action"] == original_actions).all(), (
            "final_action was modified by Stock DNA annotation — safety violation!"
        )

    def test_a3_rank_score_unchanged_after_annotation(self):
        scan = _make_mock_scan()
        original_scores = scan["a3_rank_score"].copy()
        profiles = _make_mock_profiles(scan["symbol"].tolist())

        annotated = annotate_t2_support(scan.copy(), profiles)

        assert (annotated["a3_rank_score"].values == original_scores.values).all(), (
            "a3_rank_score was modified by Stock DNA annotation — safety violation!"
        )

    def test_verify_production_columns_raises_on_modification(self):
        original = _make_mock_scan()
        modified = original.copy()
        modified["final_action"] = "BUY"  # Simulate illegal modification

        with pytest.raises(AssertionError, match="final_action"):
            _verify_production_columns_intact(original, modified)


# ── Test 11: Overlay variants are research-only ───────────────────────────────

class TestOverlayResearchOnly:

    def test_annotation_only_adds_dna_columns(self):
        scan = _make_mock_scan()
        profiles = _make_mock_profiles(scan["symbol"].tolist())
        annotated = annotate_t2_support(scan.copy(), profiles)

        dna_cols_added = [c for c in DNA_ANNOTATION_COLS if c in annotated.columns]
        assert len(dna_cols_added) > 0, "No DNA annotation columns were added"

    def test_annotation_does_not_add_production_columns(self):
        scan = _make_mock_scan()
        profiles = _make_mock_profiles(scan["symbol"].tolist())
        original_cols = set(scan.columns)
        annotated = annotate_t2_support(scan.copy(), profiles)
        new_cols = set(annotated.columns) - original_cols

        # No new production columns should appear
        prod_col_overlap = new_cols & PROTECTED_PRODUCTION_COLS
        assert not prod_col_overlap, f"Annotation added production columns: {prod_col_overlap}"

    def test_output_path_safety_guard(self):
        """assert_output_path_safe must raise for production paths."""
        from pathlib import Path
        with pytest.raises(ValueError, match="production directory"):
            assert_output_path_safe(Path("data/decision"))
        with pytest.raises(ValueError, match="production directory"):
            assert_output_path_safe(Path("data/scan"))

    def test_output_path_allows_research(self):
        """data/research/stock_dna is a safe output path."""
        from pathlib import Path
        # Should not raise
        assert_output_path_safe(Path("data/research/stock_dna"))


# ── Test 16: DNA score cannot create/block/size/route live orders ─────────────

class TestNoDNAInLiveOrders:

    def test_dna_context_score_is_float_only(self):
        """Stock DNA context score must be a float for annotation, not a routing signal."""
        scan = _make_mock_scan()
        profiles = _make_mock_profiles(scan["symbol"].tolist())
        annotated = annotate_t2_support(scan.copy(), profiles)

        if COL_DNA_CONTEXT_SCORE in annotated.columns:
            vals = annotated[COL_DNA_CONTEXT_SCORE].dropna()
            if not vals.empty:
                assert vals.dtype in [float, "float64", "float32"], (
                    f"DNA context score should be float, got {vals.dtype}"
                )

    def test_t2_active_is_integer_flag_not_order(self):
        """stock_dna_t2_active must be 0 or 1 only — never a quantity or price."""
        scan = _make_mock_scan()
        profiles = _make_mock_profiles(scan["symbol"].tolist())
        annotated = annotate_t2_support(scan.copy(), profiles)

        if COL_DNA_T2_ACTIVE in annotated.columns:
            vals = annotated[COL_DNA_T2_ACTIVE].dropna()
            assert set(vals.unique()).issubset({0, 1}), (
                f"stock_dna_t2_active has values outside {{0,1}}: {vals.unique()}"
            )

    def test_danger_active_is_integer_flag_not_order(self):
        """stock_dna_danger_active must be 0 or 1 only."""
        scan = _make_mock_scan()
        profiles = _make_mock_profiles(scan["symbol"].tolist())
        annotated = annotate_t2_support(scan.copy(), profiles)

        if COL_DNA_DANGER_ACTIVE in annotated.columns:
            vals = annotated[COL_DNA_DANGER_ACTIVE].dropna()
            assert set(vals.unique()).issubset({0, 1}), (
                f"stock_dna_danger_active has values outside {{0,1}}: {vals.unique()}"
            )


# ── Test 20: Import firewall CI check ────────────────────────────────────────

class TestImportFirewall:

    def test_oms_does_not_import_stock_dna(self):
        """
        Production OMS modules must not import from research/stock_dna.
        Grep for 'stock_dna' in src/trading/oms/ and src/trading/live/.
        """
        oms_dir  = ROOT / "src" / "trading" / "oms"
        live_dir = ROOT / "src" / "trading" / "live"

        violations = []
        for search_dir in [oms_dir, live_dir]:
            if not search_dir.exists():
                continue
            for py_file in search_dir.rglob("*.py"):
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                if "stock_dna" in content:
                    violations.append(str(py_file))

        assert not violations, (
            f"[Import Firewall] Production OMS/live modules import from stock_dna: {violations}. "
            "Research module must not be imported by production code."
        )

    def test_scans_does_not_import_stock_dna(self):
        """Daily scan modules must not import from research/stock_dna."""
        scans_dir = ROOT / "src" / "scans"
        if not scans_dir.exists():
            pytest.skip("src/scans not found")

        violations = []
        for py_file in scans_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if "stock_dna" in content:
                violations.append(str(py_file))

        assert not violations, (
            f"[Import Firewall] Scan modules import from stock_dna: {violations}"
        )

    def test_trading_signals_does_not_import_stock_dna(self):
        """Trading signals modules must not import from research/stock_dna."""
        signals_dir = ROOT / "src" / "trading" / "signals"
        if not signals_dir.exists():
            pytest.skip("src/trading/signals not found")

        violations = []
        for py_file in signals_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if "stock_dna" in content:
                violations.append(str(py_file))

        assert not violations, (
            f"[Import Firewall] Trading signals import from stock_dna: {violations}"
        )

    def test_research_module_path_is_under_research(self):
        """Verify the module is correctly placed under research/ (not trading root)."""
        dna_init = ROOT / "src" / "trading" / "research" / "stock_dna" / "__init__.py"
        assert dna_init.exists(), "Stock DNA module not found at expected research path"

        # Not under src/trading directly (one level up)
        bad_path = ROOT / "src" / "trading" / "stock_dna"
        assert not bad_path.exists(), "stock_dna mistakenly placed in src/trading/ root"


# ── Test 21: New overlay columns must not appear in production paths (council Q4) ─

class TestNewOverlayColumnsNotInProduction:
    """
    Council amendment 5 (Q4): per_symbol_null_z and the v3 overlay columns are
    diagnostic readouts only. They must never appear in any file under
    data/scan, data/decision, data/state, or data/paper_trade.
    """
    _NEW_OVERLAY_COLS = frozenset({
        "per_symbol_null_z",
        "is_stock_dna_aligned",
        "primary_support_tolerance",
        "distance_to_support_pct",
        "sample_confidence",
        "edge_confidence",
        "v1_annotation",
        "danger_line_flag",
    })
    _PROTECTED_DIRS = ["data/scan", "data/decision", "data/state", "data/paper_trade"]

    def test_new_columns_absent_from_protected_dirs(self):
        """No CSV in production dirs should contain any v3 overlay column headers."""
        violations: list[str] = []
        for dir_rel in self._PROTECTED_DIRS:
            prod_dir = ROOT / dir_rel
            if not prod_dir.exists():
                continue
            for csv_file in prod_dir.rglob("*.csv"):
                try:
                    header = csv_file.read_text(encoding="utf-8", errors="ignore").split("\n")[0]
                except Exception:
                    continue
                found = self._NEW_OVERLAY_COLS & set(c.strip() for c in header.split(","))
                if found:
                    violations.append(f"{csv_file}: {found}")
        assert not violations, (
            f"[Guardrail] v3 overlay columns found in production paths: {violations}. "
            "per_symbol_null_z and overlay annotation columns must never be written to "
            "data/scan, data/decision, data/state, or data/paper_trade."
        )

    def test_assert_output_path_safe_blocks_all_protected(self):
        """assert_output_path_safe must raise for every protected dir."""
        for dir_rel in self._PROTECTED_DIRS:
            with pytest.raises(ValueError, match="production directory"):
                assert_output_path_safe(Path(dir_rel))
