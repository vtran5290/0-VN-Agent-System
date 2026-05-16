"""Baseline reconciliation tests."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from src.trading.config import TradingConfig
from src.trading.reconciliation.baseline import baseline_positions_qty, load_latest_baseline


class TestBaselineRecon(unittest.TestCase):
    def test_baseline_qty_loaded(self):
        tmp = TemporaryDirectory()
        cfg = TradingConfig(data_root=Path(tmp.name) / "trading")
        cfg.baseline_positions_dir.mkdir(parents=True)
        payload = {"asof_date": "2099-01-01", "positions": [{"symbol": "FPT", "quantity": 100}]}
        (cfg.baseline_positions_dir / "baseline_2099-01-01.json").write_text(json.dumps(payload))
        b = load_latest_baseline(cfg, "2099-01-15")
        qty = baseline_positions_qty(b)
        self.assertEqual(qty["FPT"], 100)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
