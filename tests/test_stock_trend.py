import unittest
from unittest.mock import patch

import pandas as pd

from stock_trend import price_trend


class StockTrendTests(unittest.TestCase):
    @patch("yfinance.Ticker")
    def test_price_trend_calculates_change_and_verdict(self, ticker_class):
        closes = pd.Series(
            range(1, 151),
            index=pd.date_range("2025-01-01", periods=150, freq="D"),
            name="Close",
            dtype=float,
        )
        ticker_class.return_value.history.return_value = pd.DataFrame({"Close": closes})

        result = price_trend("TEST")

        self.assertEqual(result["verdict"], "Insufficient data")
        self.assertAlmostEqual(result["changes_percent"]["5_trading_days"], 3.45, places=2)
        self.assertIsNone(result["ma200"])

    @patch("yfinance.Ticker")
    def test_price_trend_rejects_empty_history(self, ticker_class):
        ticker_class.return_value.history.return_value = pd.DataFrame()

        with self.assertRaises(RuntimeError):
            price_trend("TEST")


if __name__ == "__main__":
    unittest.main()
