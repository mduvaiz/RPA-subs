import sys
from datetime import datetime

import yfinance as yf


def money(value, currency):
    if value is None:
        return "N/A"
    return f"{currency} {value:,.2f}"


def main():
    company_name = " ".join(sys.argv[1:]).strip() or input("Company name: ").strip()
    if not company_name:
        print("Please provide a company name.")
        return

    try:
        quotes = yf.Search(company_name, max_results=10).quotes
    except Exception:
        print("Could not search for that company. Please check your internet connection.")
        return

    equities = [quote for quote in quotes if quote.get("quoteType") == "EQUITY"]
    if not equities:
        print(f"No company found for '{company_name}'.")
        return

    quote = next((item for item in equities if item.get("symbol", "").endswith(".NS")), equities[0])
    symbol = quote.get("symbol")
    if not symbol:
        print("The search result did not include a stock symbol.")
        return

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        current = info.get("lastPrice")
        previous = info.get("previousClose")
        if current is None or previous is None:
            raise ValueError("missing price")
    except Exception:
        print("Price information is not available right now.")
        return

    try:
        details = ticker.info
    except Exception:
        details = {}

    currency = info.get("currency") or ""
    change = current - previous
    percent = change / previous * 100 if previous else 0
    arrow = "▲" if change >= 0 else "▼"
    market_cap = info.get("marketCap")
    market_cap_text = (f"INR {market_cap / 10_000_000:,.2f} crore"
                       if currency == "INR" and market_cap else money(market_cap, currency))
    display_name = quote.get("longname") or quote.get("shortname") or company_name

    print("\n" + "=" * 48)
    print(f"{display_name} ({symbol})")
    print("=" * 48)
    print(f"Exchange: {quote.get('exchange', 'N/A')}")
    print(f"Sector: {quote.get('sector', 'N/A')}")
    print(f"Industry: {quote.get('industry', 'N/A')}")
    fields = (
        ("Website", "website"),
        ("Country", "country"),
        ("Employees", "fullTimeEmployees"),
        ("Business summary", "longBusinessSummary"),
        ("P/E ratio", "trailingPE"),
        ("Forward P/E", "forwardPE"),
        ("Dividend yield", "dividendYield"),
        ("52-week change", "52WeekChange"),
    )
    for label, key in fields:
        value = details.get(key)
        if value not in (None, ""):
            if key == "dividendYield":
                value = f"{value:.2f}%"
            elif key == "52WeekChange":
                value = f"{value * 100:.2f}%"
            print(f"{label}: {value}")
    print(f"Current price: {money(current, currency)}")
    print(f"Day change: {arrow} {money(abs(change), currency)} ({percent:+.2f}%)")
    print(f"Day range: {money(info.get('dayLow'), currency)} - {money(info.get('dayHigh'), currency)}")
    print(f"52-week range: {money(info.get('yearLow'), currency)} - {money(info.get('yearHigh'), currency)}")
    print(f"Market cap: {market_cap_text}")
    print(f"Checked: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")


if __name__ == "__main__":
    main()