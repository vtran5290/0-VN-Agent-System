"""IA score firewall — production paths must not use IA score fields for sizing."""
import ast
import importlib
import importlib.util
import unittest
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
PRODUCTION_DIRS = [
    REPO / "src" / "trading" / "live",
    REPO / "src" / "trading" / "oms",
    REPO / "src" / "trading" / "risk",
    REPO / "src" / "trading" / "brokers",
]

IA_FIELD_NAMES = {
    "ia_score",
    "institutional_score",
    "accumulation_rank",
    "capital_footprint_score_raw",
    "big_individual_footprint_proxy",
    "cf_score",
    "cf_rank",
}

FORBIDDEN_IMPORT_PREFIXES = (
    "src.trading.research.capital_footprint",
    "src.scans.institutional_accumulation",
)


def _collect_py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if p.is_file()]


def _source_mentions_ia_field(source: str) -> set[str]:
    found = set()
    for name in IA_FIELD_NAMES:
        if name in source:
            found.add(name)
    return found


class TestIAScoreFirewall(unittest.TestCase):
    def test_no_ia_imports_in_production_dirs(self):
        violations = []
        for root in PRODUCTION_DIRS:
            for path in _collect_py_files(root):
                source = path.read_text(encoding="utf-8")
                for prefix in FORBIDDEN_IMPORT_PREFIXES:
                    if f"from {prefix}" in source or f"import {prefix}" in source:
                        violations.append(f"{path}: imports {prefix}")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_no_ia_field_names_in_production_source(self):
        violations = []
        for root in PRODUCTION_DIRS:
            for path in _collect_py_files(root):
                hits = _source_mentions_ia_field(path.read_text(encoding="utf-8"))
                if hits:
                    violations.append(f"{path}: mentions {sorted(hits)}")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_extreme_ia_columns_do_not_change_execution_sizing(self):
        from src.trading.config import LiveTradingConfig
        from src.trading.live.sizing_policy import apply_execution_sizing

        cfg = LiveTradingConfig(
            portfolio_size_vnd=1_000_000_000,
            max_order_value_vnd=600_000_000,
            adv_participation=0.10,
        )
        base_row = pd.Series(
            {
                "symbol": "FPT",
                "adv50_vnd": 2_000_000_000,
                "scan_value_vnd": 50_000_000,
            }
        )
        extreme_row = base_row.copy()
        for col in IA_FIELD_NAMES:
            extreme_row[col] = 9999
        extreme_row["ia_score"] = 9999
        extreme_row["institutional_score"] = -9999

        base_result = apply_execution_sizing(
            cfg, 50_000_000, 50_000, "BUY", base_row
        )
        extreme_result = apply_execution_sizing(
            cfg, 50_000_000, 50_000, "BUY", extreme_row
        )
        self.assertEqual(base_result[1], extreme_result[1], "qty must not depend on IA columns")
        self.assertAlmostEqual(base_result[0], extreme_result[0])

    def test_oms_sizing_path_has_no_ia_ast_references(self):
        om_path = REPO / "src" / "trading" / "oms" / "order_manager.py"
        tree = ast.parse(om_path.read_text(encoding="utf-8"))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        overlap = names & IA_FIELD_NAMES
        self.assertEqual(overlap, set(), f"order_manager references IA fields: {overlap}")

    def test_capital_footprint_not_importable_from_oms(self):
        oms_spec = importlib.util.find_spec("src.trading.oms.order_manager")
        self.assertIsNotNone(oms_spec)
        om = importlib.import_module("src.trading.oms.order_manager")
        self.assertFalse(
            hasattr(om, "capital_footprint"),
            "OMS must not bind capital_footprint module",
        )


if __name__ == "__main__":
    unittest.main()
