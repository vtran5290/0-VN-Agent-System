"""Tests for order-intent dry run (no broker, no OMS execution)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.trading.order_intent_dry_run import (
    OrderIntentDryRunError,
    generate_order_intent_dry_run,
    resolve_effective_scan_date,
    validate_order_intent_csv,
)


class TestOrderIntentDryRun(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.positions = self.root / "positions.json"
        self.scan = self.root / "scan.csv"
        self.out = self.root / "order_intent.csv"

    def tearDown(self):
        self.tmp.cleanup()

    def _write_positions(self, tickers: list[str]) -> None:
        rows = [{"ticker": t, "lots": 1000, "entry_price": 10000.0} for t in tickers]
        self.positions.write_text(json.dumps(rows), encoding="utf-8")

    def _write_scan(self, rows: list[dict]) -> None:
        pd.DataFrame(rows).to_csv(self.scan, index=False)

    def test_order_sent_always_no(self):
        self._write_positions(["FPT"])
        self._write_scan([
            {
                "as_of_date": "2026-01-15",
                "symbol": "FPT",
                "final_action": "NEW_T1",
                "strategy_classification": "A3_PRODUCTION",
            },
        ])
        generate_order_intent_dry_run(
            "2026-01-15", self.scan, self.positions, self.out
        )
        df = pd.read_csv(self.out)
        self.assertTrue((df["order_sent"] == "NO").all())
        self.assertTrue((df["manual_approval_required"] == "YES").all())
        self.assertNotIn("2099", df["date"].iloc[0])

    def test_maps_final_action_only(self):
        self._write_positions(["FPT"])
        self._write_scan([
            {
                "as_of_date": "2026-01-15",
                "symbol": "FPT",
                "final_action": "TRAIL_EXIT",
                "strategy_classification": "A3_PRODUCTION",
            },
        ])
        generate_order_intent_dry_run(
            "2026-01-15", self.scan, self.positions, self.out
        )
        row = pd.read_csv(self.out).iloc[0]
        self.assertEqual(row["phase36_final_action"], "TRAIL_EXIT")
        self.assertEqual(row["suggested_action"], "REVIEW_EXIT")
        self.assertEqual(row["holding_classification"], "A3_PRODUCTION_MATCHED")

    def test_notes_include_requested_and_effective_dates(self):
        self._write_positions(["FPT"])
        self._write_scan([
            {
                "as_of_date": "2026-01-10",
                "symbol": "FPT",
                "final_action": "NEW_T1",
                "strategy_classification": "A3_PRODUCTION",
            },
        ])
        generate_order_intent_dry_run(
            "2026-01-15", self.scan, self.positions, self.out
        )
        row = pd.read_csv(self.out).iloc[0]
        self.assertEqual(row["date"], "2026-01-10")
        self.assertIn("requested_date=2026-01-15", row["notes"])
        self.assertIn("effective_scan_date=2026-01-10", row["notes"])

    def test_rejects_placeholder_only_scan_without_test_flag(self):
        with self.assertRaises(OrderIntentDryRunError):
            resolve_effective_scan_date(
                ["2099-01-01"],
                "2099-01-01",
                allow_test_sample=False,
            )

    def test_placeholder_allowed_with_test_flag(self):
        eff, _ = resolve_effective_scan_date(
            ["2099-01-01"],
            "2099-01-01",
            allow_test_sample=True,
        )
        self.assertEqual(eff, "2099-01-01")

    def test_mixed_scan_rejects_placeholder_for_production(self):
        self._write_positions(["FPT"])
        self._write_scan([
            {
                "as_of_date": "2099-01-01",
                "symbol": "FPT",
                "final_action": "NEW_T1",
                "strategy_classification": "A3_PRODUCTION",
            },
            {
                "as_of_date": "2026-01-15",
                "symbol": "FPT",
                "final_action": "NEW_T1",
                "strategy_classification": "A3_PRODUCTION",
            },
        ])
        generate_order_intent_dry_run(
            "2026-01-20", self.scan, self.positions, self.out
        )
        row = pd.read_csv(self.out).iloc[0]
        self.assertEqual(row["date"], "2026-01-15")
        self.assertFalse(str(row["date"]).startswith("2099"))

    def test_missing_scan_fail_closed(self):
        self._write_positions(["FPT"])
        with self.assertRaises(OrderIntentDryRunError):
            generate_order_intent_dry_run(
                "2026-01-15", self.root / "missing.csv", self.positions, self.out
            )

    def test_missing_positions_fail_closed(self):
        self._write_scan([
            {
                "as_of_date": "2026-01-15",
                "symbol": "FPT",
                "final_action": "NEW_T1",
                "strategy_classification": "A3_PRODUCTION",
            },
        ])
        with self.assertRaises(OrderIntentDryRunError):
            generate_order_intent_dry_run(
                "2026-01-15", self.scan, self.root / "missing.json", self.out
            )

    def test_no_scan_match_outside_a3(self):
        self._write_positions(["ZZZ"])
        self._write_scan([
            {
                "as_of_date": "2026-01-15",
                "symbol": "FPT",
                "final_action": "NEW_T1",
                "strategy_classification": "A3_PRODUCTION",
            },
        ])
        generate_order_intent_dry_run(
            "2026-01-15", self.scan, self.positions, self.out
        )
        row = pd.read_csv(self.out).iloc[0]
        self.assertEqual(row["risk_flag"], "OUTSIDE_A3_OR_NO_SCAN_MATCH")
        self.assertEqual(row["holding_classification"], "DISCRETIONARY_OUTSIDE_A3")

    def test_s3_row_not_used_for_production_match(self):
        self._write_positions(["SSI"])
        self._write_scan([
            {
                "as_of_date": "2026-01-15",
                "symbol": "SSI",
                "final_action": "NEW_T1",
                "strategy_classification": "S3_RESEARCH_ONLY",
            },
        ])
        generate_order_intent_dry_run(
            "2026-01-15", self.scan, self.positions, self.out
        )
        row = pd.read_csv(self.out).iloc[0]
        self.assertEqual(row["risk_flag"], "OUTSIDE_A3_OR_NO_SCAN_MATCH")

    def test_fixture_output_requires_test_filename(self):
        self._write_positions(["FPT"])
        self._write_scan([
            {
                "as_of_date": "2099-01-01",
                "symbol": "FPT",
                "final_action": "NEW_T1",
                "strategy_classification": "A3_PRODUCTION",
            },
        ])
        with self.assertRaises(OrderIntentDryRunError):
            generate_order_intent_dry_run(
                "2099-01-01",
                self.scan,
                self.positions,
                self.root / "order_intent_2026-05-17.csv",
                allow_test_sample=True,
            )

    def test_no_broker_imports_in_module(self):
        mod = sys.modules["src.trading.order_intent_dry_run"]
        src = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("order_manager", src.lower())
        self.assertNotIn("get_broker", src)
        self.assertNotIn("live.workflow", src)

    def test_a3_rank_score_not_in_mapping(self):
        from src.trading import order_intent_dry_run as m

        self.assertNotIn("a3_rank_score", m.SUGGESTED_FROM_FINAL_ACTION)

    def test_validate_rejects_placeholder_date_column(self):
        self._write_positions(["FPT"])
        self._write_scan([
            {
                "as_of_date": "2026-01-15",
                "symbol": "FPT",
                "final_action": "NEW_T1",
                "strategy_classification": "A3_PRODUCTION",
            },
        ])
        bad = self.root / "order_intent_2026-01-15.csv"
        bad.write_text(
            "date,ticker,order_sent\n2099-01-01,FPT,NO\n",
            encoding="utf-8",
        )
        with self.assertRaises(OrderIntentDryRunError):
            validate_order_intent_csv(bad)

    def test_validate_allows_test_filename_with_flag(self):
        test_path = self.root / "order_intent_test_sample.csv"
        test_path.write_text(
            "date,ticker,order_sent\n2099-01-01,FPT,NO\n",
            encoding="utf-8",
        )
        validate_order_intent_csv(test_path, allow_test_sample=True)

    def test_validate_rejects_order_sent_not_no(self):
        bad = self.root / "order_intent_2026-01-15.csv"
        bad.write_text(
            "date,ticker,order_sent\n2026-01-15,FPT,YES\n",
            encoding="utf-8",
        )
        with self.assertRaises(OrderIntentDryRunError):
            validate_order_intent_csv(bad)


if __name__ == "__main__":
    unittest.main()
