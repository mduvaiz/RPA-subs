import unittest
from unittest.mock import patch

from market_data import find_stock, money, snapshot, value_range


class MarketDataTests(unittest.TestCase):
    def test_money_and_ranges_handle_missing_values(self):
        self.assertEqual(money(None, "USD"), "N/A")
        self.assertEqual(value_range(None, 10, "USD"), "N/A")
        self.assertEqual(value_range(1, 10, "USD"), "USD 1.00 - USD 10.00")

    @patch("market_data.yf.Ticker")
    @patch("market_data.yf.Search")
    def test_snapshot_uses_details_and_safe_missing_ranges(self, search, ticker_class):
        search.return_value.quotes = [{
            "quoteType": "EQUITY",
            "symbol": "TEST.NS",
            "longname": "Test Limited",
            "exchange": "NSI",
        }]
        ticker_class.return_value.fast_info = {
            "lastPrice": 100,
            "previousClose": 90,
            "currency": "INR",
            "dayLow": None,
            "dayHigh": 105,
            "yearLow": 70,
            "yearHigh": 120,
            "marketCap": 100000000,
        }
        ticker_class.return_value.info = {
            "sector": "Technology",
            "industry": "Software",
            "dividendYield": None,
        }

        data = snapshot("Test")

        self.assertEqual(data["sector"], "Technology")
        self.assertEqual(data["industry"], "Software")
        self.assertEqual(data["day_range"], "N/A")
        self.assertEqual(data["change_percent"], "+11.11%")

    @patch("market_data.yf.Search")
    def test_find_stock_rejects_non_equity_search_results(self, search):
        search.return_value.quotes = [{"quoteType": "ETF", "symbol": "TEST"}]

        with self.assertRaises(LookupError):
            find_stock("Test")


if __name__ == "__main__":
    unittest.main()
