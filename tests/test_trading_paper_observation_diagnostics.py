"""Paper-observation diagnostics: bool parse, scan basis, capacity attribution, valid day, operator pack."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from src.trading.config import REPO_ROOT, load_live_trading_config
from src.trading.live.account_dashboard import _intent_stats, write_compare_report
from src.trading.live.csv_parse import parse_csv_bool
from src.trading.live.paper_accounts import (
    build_live_config_for_account,
    get_paper_account,
    initialize_paper_account,
    scan_size_basis_metadata,
)
from src.trading.live.paper_observation import (
    evaluate_valid_paper_day,
    finalize_paper_observation,
    write_daily_operator_pack,
)
from src.trading.live.path_safety import is_under_paper_trade
from src.trading.live.sizing_policy import apply_execution_sizing


class TestCsvBoolParse(unittest.TestCase):
    def test_false_string_not_true(self):
        self.assertFalse(parse_csv_bool("False"))
        self.assertFalse(parse_csv_bool("FALSE"))
        self.assertFalse(parse_csv_bool("false"))

    def test_true_variants(self):
        self.assertTrue(parse_csv_bool("true"))
        self.assertTrue(parse_csv_bool("True"))
        self.assertTrue(parse_csv_bool(1))
        self.assertTrue(parse_csv_bool("yes"))

    def test_empty_nan_false(self):
        self.assertFalse(parse_csv_bool(""))
        self.assertFalse(parse_csv_bool(None))
        self.assertFalse(parse_csv_bool(float("nan")))

    def test_manual_review_count_not_inflated(self):
        intents = pd.DataFrame([
            {"action": "BUY_T1", "requires_manual_review": "False"},
            {"action": "BUY_T1", "requires_manual_review": "true"},
            {"action": "SKIP", "requires_manual_review": False},
        ])
        st = _intent_stats(intents)
        self.assertEqual(st["manual_review"], 1)


class TestScanSizeBasisMetadata(unittest.TestCase):
    def test_10b_20b_metadata_and_warning(self):
        a10 = get_paper_account("A3_SCALE_PAPER_10B")
        a20 = get_paper_account("A3_SCALE_PAPER_20B")
        m10 = scan_size_basis_metadata(a10)
        m20 = scan_size_basis_metadata(a20)
        self.assertEqual(m10["scan_size_basis"], "5B_reference_scan_not_scaled")
        self.assertEqual(m20["scan_size_basis"], "5B_reference_scan_liquidity_capped")
        self.assertEqual(m10["scan_reference_nav_VND"], 5_000_000_000.0)
        self.assertTrue(m10["reference_sizing_warning"])
        self.assertTrue(m20["reference_sizing_warning"])

    def test_compare_shows_basis(self):
        with TemporaryDirectory() as tmp:
            for aid in ("A3_PROD_PAPER_5B", "A3_SCALE_PAPER_20B"):
                root = Path(tmp) / aid
                initialize_paper_account(aid, ledger_root_override=root)
            path = write_compare_report("2099-05-01", ["A3_PROD_PAPER_5B", "A3_SCALE_PAPER_20B"])
            text = path.read_text(encoding="utf-8")
            self.assertIn("Scan size basis", text)
            self.assertIn("5B_reference_scan_liquidity_capped", text)
            self.assertIn("ref nav", text.lower())


class TestCapacityAttribution(unittest.TestCase):
    def test_adv_and_max_order_caps(self):
        cfg, _ = build_live_config_for_account("A3_SCALE_PAPER_20B")
        row = pd.Series({"adv50_B_VND": 1.0})
        ev, qty, pol, reason, attr = apply_execution_sizing(
            cfg, 2_000_000_000.0, 50_000.0, "BUY", row
        )
        self.assertGreater(qty, 0)
        self.assertTrue(
            attr["capped_by_adv_liquidity"] or attr["capped_by_max_order_value"] or reason
        )

    def test_intent_stats_counts_caps(self):
        intents = pd.DataFrame([
            {
                "action": "BUY_T1",
                "requires_manual_review": "False",
                "sizing_adjustment_reason": "liquidity_cap_hit",
                "capped_by_adv_liquidity": "True",
                "capped_by_max_order_value": "False",
                "capped_by_cash": "False",
            },
            {
                "action": "SKIP_BELOW_MIN",
                "requires_manual_review": False,
                "sizing_adjustment_reason": "below_min_trade_value",
                "capped_by_max_order_value": False,
            },
        ])
        st = _intent_stats(intents)
        self.assertEqual(st["capped_by_adv_liquidity"], 1)
        self.assertEqual(st["below_min_trade"], 1)


class TestValidPaperDay(unittest.TestCase):
    def _row(self, aid: str, light: str = "GREEN", recon: str = "OK") -> dict:
        return {
            "account_id": aid,
            "traffic_light_status": light,
            "reconciliation_status": recon,
            "manifest_status": "COMPLETED",
            "ledger_contaminated": False,
            "manual_review": 0,
            "reference_sizing_warning": False,
        }

    def test_all_green_valid(self):
        rows = [self._row(a) for a in (
            "A3_DSE_PILOT_PAPER_SMALL", "A3_PROD_PAPER_5B",
            "A3_SCALE_PAPER_10B", "A3_SCALE_PAPER_20B",
        )]
        v = evaluate_valid_paper_day(
            "2099-05-02",
            scan_meta={"is_stale": False, "is_sample": False},
            account_rows=rows,
            test_mode=True,
        )
        self.assertTrue(v["valid_paper_day"])

    def test_red_invalid(self):
        rows = [self._row("A3_PROD_PAPER_5B", "RED")]
        v = evaluate_valid_paper_day(
            "2099-05-02",
            scan_meta={"is_stale": False, "is_sample": False},
            account_rows=rows,
            test_mode=True,
        )
        self.assertFalse(v["valid_paper_day"])
        self.assertTrue(any("traffic_light_red" in x for x in v["invalid_reasons"]))

    def test_yellow_manual_review_still_valid_with_warning(self):
        rows = [
            self._row("A3_DSE_PILOT_PAPER_SMALL"),
            self._row("A3_PROD_PAPER_5B", "YELLOW"),
            self._row("A3_SCALE_PAPER_10B"),
            self._row("A3_SCALE_PAPER_20B"),
        ]
        rows[1]["manual_review"] = 2
        v = evaluate_valid_paper_day(
            "2099-05-02",
            scan_meta={"is_stale": False, "is_sample": False},
            account_rows=rows,
            test_mode=True,
        )
        self.assertTrue(v["valid_paper_day"])
        self.assertTrue(any("manual_review" in w for w in v["warnings"]))


class TestOperatorPackAndRunAll(unittest.TestCase):
    def test_operator_pack_sections(self):
        rows = [
            {
                "account_id": aid,
                "traffic_light_status": "GREEN",
                "cash_vnd": 1e9,
                "equity": 1e9,
                "return_pct": 0,
                "cash_drag_pct": 50,
                "gross_exposure_pct": 50,
                "new_fills_today": 0,
                "exits_today": 0,
                "manual_review": 0,
                "risk_rejection_count": 0,
                "reconciliation_status": "OK",
                "scan_size_basis": "x",
                "scan_reference_nav_VND": 5e9,
                "reference_sizing_warning": aid.startswith("A3_SCALE"),
                "reference_sizing_warning_text": "warn" if aid.startswith("A3_SCALE") else "",
                "capped_by_max_order_value": 0,
                "capped_by_adv_liquidity": 0,
                "capped_by_cash": 0,
                "below_min_trade": 0,
                "skip_count": 0,
                "capped_orders": 0,
            }
            for aid in (
                "A3_DSE_PILOT_PAPER_SMALL", "A3_PROD_PAPER_5B",
                "A3_SCALE_PAPER_10B", "A3_SCALE_PAPER_20B",
            )
        ]
        valid = evaluate_valid_paper_day(
            "2099-05-03", scan_meta={"path": "/x.csv", "scan_hash": "h"}, account_rows=rows, test_mode=True
        )
        p = write_daily_operator_pack(
            "2099-05-03",
            scan_meta={"path": "/x.csv", "scan_hash": "h", "is_stale": False, "is_sample": False},
            account_rows=rows,
            valid_day=valid,
            s3_shadow={"recorded": 1, "skipped": 0, "blocked_count": 0},
        )
        text = p.read_text(encoding="utf-8")
        for sec in ("## A.", "## B.", "## C.", "## D.", "## E.", "## F.", "## G.", "## H."):
            self.assertIn(sec, text)
        for aid in (
            "A3_DSE_PILOT_PAPER_SMALL", "A3_PROD_PAPER_5B",
            "A3_SCALE_PAPER_10B", "A3_SCALE_PAPER_20B",
        ):
            self.assertIn(aid, text)
        self.assertIn("S3 shadow", text)

    def test_finalize_writes_outputs(self):
        with TemporaryDirectory() as tmp:
            for aid in (
                "A3_DSE_PILOT_PAPER_SMALL", "A3_PROD_PAPER_5B",
                "A3_SCALE_PAPER_10B", "A3_SCALE_PAPER_20B",
            ):
                initialize_paper_account(aid, ledger_root_override=Path(tmp) / aid)
            paths = finalize_paper_observation(
                "2099-05-04",
                scan_meta={"path": str(Path(tmp) / "s.csv"), "scan_hash": "h", "is_stale": False, "is_sample": False},
                account_results=[],
                test_mode=True,
            )
            self.assertTrue(Path(paths["daily_operator_pack"]).exists())
            self.assertTrue(Path(paths["valid_paper_day"]).exists())
            self.assertTrue(Path(paths["compare_report"]).exists())
            valid = json.loads(Path(paths["valid_paper_day"]).read_text(encoding="utf-8"))
            self.assertIn("valid_paper_day", valid)

    def test_no_paper_trade_writes(self):
        out = REPO_ROOT / "data" / "trading" / "live" / "accounts"
        self.assertFalse(is_under_paper_trade(out))


class TestLiveSafety(unittest.TestCase):
    def test_live_auto_off(self):
        self.assertFalse(load_live_trading_config().live_trading)


if __name__ == "__main__":
    unittest.main()
