import unittest

import pandas as pd

from src.backtest.execution import ExecutionConfig, FillTiming
from pp_backtest.backtest import run_single_symbol_with_ledger
from pp_backtest.config import BacktestConfig


class TestExecutionSemantics(unittest.TestCase):
    def _toy_df(self) -> pd.DataFrame:
        # 4 bars, entry signal on bar 0, exit signal on bar 1 -> fills at bar 1 open and bar 2 open by default.
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06"]),
                "open": [10.0, 11.0, 12.0, 13.0],
                "high": [10.5, 11.5, 12.5, 13.5],
                "low": [9.5, 10.5, 11.5, 12.5],
                "close": [10.2, 11.2, 12.2, 13.2],
                "volume": [1000, 1000, 1000, 1000],
                "pp": [True, False, False, False],
                "sell_final": [False, True, False, False],
            }
        )

    def test_entry_fills_next_open_not_same_bar(self):
        df = self._toy_df()
        cfg = BacktestConfig()
        exec_cfg = ExecutionConfig(
            entry_timing=FillTiming.NEXT_BAR_OPEN,
            exit_timing=FillTiming.NEXT_BAR_OPEN,
            fee_bps_per_side=0.0,
            slippage_bps_per_side=0.0,
        )
        stats, ledger = run_single_symbol_with_ledger(df, cfg, exec_cfg=exec_cfg)
        self.assertEqual(len(ledger), 1)
        # Entry should be at bar 1 open (11.0), not bar 0 open/close.
        self.assertAlmostEqual(float(ledger.loc[0, "entry_open_raw"]), 11.0)
        # Exit should be at bar 2 open (12.0).
        self.assertAlmostEqual(float(ledger.loc[0, "exit_open_raw"]), 12.0)

    def test_meta_v1_shift_blocks_future_regime(self):
        # Meta-trending is True only on bar 0; entry at bar 1 open must use meta_trending.shift(1),
        # so meta must be True on bar -1 (which doesn't exist) => blocked.
        df = self._toy_df()
        df["meta_trending"] = [True, False, False, False]
        cfg = BacktestConfig()
        exec_cfg = ExecutionConfig(fee_bps_per_side=0.0, slippage_bps_per_side=0.0)
        stats, ledger = run_single_symbol_with_ledger(df, cfg, use_meta_v1=True, exec_cfg=exec_cfg)
        self.assertEqual(len(ledger), 0)


if __name__ == "__main__":
    unittest.main()

