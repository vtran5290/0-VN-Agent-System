"""Paper ledger live module tests."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.trading.config import LiveTradingConfig
from src.trading.live.paper_ledger import PaperLedger


class TestPaperLedgerLive(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(data_root=Path(self.tmp.name) / "trading")
        self.cfg.ensure_dirs()
        self.ledger = PaperLedger(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_open_t1_and_t2(self):
        tid = self.ledger.open_T1("FPT", "2099-01-01", 100_000, 250_000_000, 2500)
        self.ledger.add_T2(tid, "2099-01-08", 96_000, 250_000_000, 2600)
        trades = self.ledger._load_trades()
        row = trades[trades["trade_id"] == tid].iloc[0]
        self.assertEqual(row["state"], "T2_ADDED")
        pos = self.ledger.reconcile_open_positions()
        self.assertEqual(len(pos), 1)


if __name__ == "__main__":
    unittest.main()
