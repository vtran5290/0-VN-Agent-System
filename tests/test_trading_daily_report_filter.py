"""Daily report date filter tests."""
import unittest
from src.trading.models import ManagedOrder, OrderProposal, OrderSide, OrderState, Signal
from src.trading.monitoring.daily_report import filter_orders_by_date


class TestDailyReportFilter(unittest.TestCase):
    def test_filters_by_date(self):
        o1 = ManagedOrder(
            proposal=OrderProposal(Signal("A3_DP", "FPT", OrderSide.BUY.value, "2099-01-01", 1, 1)),
            state=OrderState.FILLED,
        )
        o2 = ManagedOrder(
            proposal=OrderProposal(Signal("A3_DP", "HPG", OrderSide.BUY.value, "2099-01-02", 1, 1)),
            state=OrderState.FILLED,
        )
        daily = filter_orders_by_date([o1, o2], "2099-01-02")
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0].proposal.signal.symbol, "HPG")


if __name__ == "__main__":
    unittest.main()
