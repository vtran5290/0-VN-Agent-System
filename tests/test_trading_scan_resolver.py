"""Scan resolver: Phase36 latest alias, legacy sample name, stale date policy."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.trading.config import LiveTradingConfig
from src.trading.live.scan_resolver import (
    PHASE36_LATEST_NAME,
    PHASE36_LEGACY_PRODUCTION_NAME,
    resolve_scan,
)

REQUIRED = ["as_of_date", "final_action", "strategy_classification", "symbol"]


def _write_scan(path: Path, asof: str) -> None:
    df = pd.DataFrame(
        [
            {
                "as_of_date": asof,
                "symbol": "FPT",
                "final_action": "WATCH_ONLY",
                "strategy_classification": "A3_PRODUCTION",
            }
        ]
    )
    df.to_csv(path, index=False)


class TestPhase36ScanResolver(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.search = Path(self.tmp.name) / "missing_work"
        self.search.mkdir(parents=True)
        self.cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            allow_sample_scan=False,
            scan_csv_path=self.search / "nonexistent.csv",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_latest_preferred_over_legacy_sample_name(self):
        legacy = self.search / PHASE36_LEGACY_PRODUCTION_NAME
        latest = self.search / PHASE36_LATEST_NAME
        _write_scan(legacy, "2026-05-15")
        _write_scan(latest, "2026-05-18")
        r = resolve_scan(self.cfg, "2026-05-18", test_mode=True, search_dir=self.search)
        self.assertEqual(r.path.name, PHASE36_LATEST_NAME)
        self.assertFalse(r.blocked)

    def test_legacy_sample_blocked_without_allow_sample(self):
        legacy = self.search / PHASE36_LEGACY_PRODUCTION_NAME
        _write_scan(legacy, "2026-05-15")
        r = resolve_scan(
            self.cfg,
            "2026-05-15",
            cli_scan_path=legacy,
            test_mode=False,
            allow_sample=False,
            search_dir=self.search,
        )
        self.assertTrue(r.blocked)

    def test_legacy_sample_allowed_with_allow_sample(self):
        legacy = self.search / PHASE36_LEGACY_PRODUCTION_NAME
        _write_scan(legacy, "2026-05-15")
        r = resolve_scan(
            self.cfg,
            "2026-05-15",
            cli_scan_path=legacy,
            test_mode=False,
            allow_sample=True,
            search_dir=self.search,
        )
        self.assertFalse(r.blocked)
        self.assertFalse(r.is_sample)

    def test_arbitrary_sample_file_blocked(self):
        bad = self.search / "my_sample_fixture.csv"
        _write_scan(bad, "2026-05-15")
        r = resolve_scan(
            self.cfg,
            "2026-05-15",
            cli_scan_path=bad,
            test_mode=False,
            allow_sample=True,
            search_dir=self.search,
        )
        self.assertTrue(r.blocked)

    def test_stale_calendar_date_blocks_by_default(self):
        latest = self.search / PHASE36_LATEST_NAME
        _write_scan(latest, "2026-05-15")
        r = resolve_scan(
            self.cfg, "2026-05-18", cli_scan_path=latest, test_mode=False, allow_sample=False
        )
        self.assertTrue(r.is_stale)
        self.assertTrue(r.blocked)
        self.assertIn("stale_scan_requested", " ".join(r.warnings))

    def test_metadata_allow_sample_flag(self):
        latest = self.search / PHASE36_LATEST_NAME
        _write_scan(latest, "2026-05-15")
        r0 = resolve_scan(
            self.cfg, "2026-05-15", cli_scan_path=latest, test_mode=False, allow_sample=False
        )
        self.assertFalse(r0.metadata.get("allow_sample"))
        r1 = resolve_scan(
            self.cfg, "2026-05-15", cli_scan_path=latest, test_mode=False, allow_sample=True
        )
        self.assertTrue(r1.metadata.get("allow_sample"))

    def test_use_latest_scan_date_override(self):
        latest = self.search / PHASE36_LATEST_NAME
        _write_scan(latest, "2026-05-15")
        r = resolve_scan(
            self.cfg,
            "2026-05-18",
            cli_scan_path=latest,
            test_mode=False,
            use_latest_scan_date=True,
        )
        self.assertFalse(r.blocked)
        self.assertEqual(r.effective_date, "2026-05-15")

    def test_config_points_to_latest_not_phase34(self):
        from src.trading.config import load_live_trading_config, REPO_ROOT

        cfg = load_live_trading_config()
        p = str(cfg.scan_csv_path).replace("\\", "/")
        self.assertIn("phase36_daily_scan_latest", p)
        self.assertNotIn("phase34", p)


if __name__ == "__main__":
    unittest.main()
