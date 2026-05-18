"""Order intent adapter tests."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.trading.config import LiveTradingConfig
from src.trading.live.order_intent import build_order_intents


class TestOrderIntent(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            scan_csv_path=Path(__file__).parent / "fixtures" / "trading" / "sample_scan.csv",
            allow_sample_scan=True,
        )
        self.cfg.ensure_dirs()

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_t1_maps(self):
        intents = build_order_intents(self.cfg, "2099-01-01", {"BLOCK_ORDER_GENERATION": False}, test_mode=True)
        tradeable = intents[intents["action"].isin(["BUY_T1", "BUY_T1_MANUAL_REVIEW"])]
        self.assertTrue((tradeable["symbol"] == "FPT").any())

    def test_skip_liquidity(self):
        intents = build_order_intents(self.cfg, "2099-01-01", {"BLOCK_ORDER_GENERATION": False}, test_mode=True)
        aaa = intents[intents["symbol"] == "AAA"]
        self.assertEqual(aaa.iloc[0]["action"], "SKIP_LIQUIDITY")

    def test_s3_watch_only(self):
        intents = build_order_intents(self.cfg, "2099-01-01", {"BLOCK_ORDER_GENERATION": False}, test_mode=True)
        ssi = intents[intents["symbol"] == "SSI"]
        self.assertNotIn(ssi.iloc[0]["action"], ["BUY_T1", "BUY_T2"])


if __name__ == "__main__":
    unittest.main()
