from datetime import datetime

import yfinance as yf


def number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def text(value, fallback="N/A"):
    return str(value) if value not in (None, "") else fallback


def money(value, currency):
    amount = number(value)
    if amount is None:
        return "N/A"
    return f"{currency} {amount:,.2f}".strip()


def value_range(low, high, currency):
    if number(low) is None or number(high) is None:
        return "N/A"
    return f"{money(low, currency)} - {money(high, currency)}"


def find_stock(company_name):
    """Find an equity, preferring its NSE listing when available."""
    try:
        quotes = yf.Search(company_name, max_results=10).quotes
    except Exception as error:
        raise RuntimeError("Could not search right now. Check your internet connection.") from error
    equities = [item for item in quotes if item.get("quoteType") == "EQUITY"]
    if not equities:
        raise LookupError(f"No company found for '{company_name}'.")
    quote = next((item for item in equities if item.get("symbol", "").endswith(".NS")), equities[0])
    if not quote.get("symbol"):
        raise LookupError("The search result did not include a stock symbol.")
    return quote


def snapshot(company_name):
    """Return one normalized company snapshot for the CLI and web interfaces."""
    quote = find_stock(company_name)
    symbol = quote["symbol"]
    ticker = yf.Ticker(symbol)
    try:
        fast = ticker.fast_info
        current = number(fast.get("lastPrice"))
        previous = number(fast.get("previousClose"))
        if current is None or previous is None:
            raise ValueError("missing price")
    except Exception as error:
        raise RuntimeError("Price information is not available right now.") from error
    try:
        details = ticker.info
    except Exception:
        details = {}

    currency = text(fast.get("currency"), "USD")
    change = current - previous
    market_cap = number(fast.get("marketCap"))
    market_cap_text = (
        f"INR {market_cap / 10_000_000:,.2f} crore"
        if currency == "INR" and market_cap
        else money(market_cap, currency)
    )
    return {
        "name": text(quote.get("longname") or quote.get("shortname"), company_name),
        "symbol": symbol,
        "exchange": text(quote.get("exchange")),
        "sector": text(details.get("sector") or quote.get("sector")),
        "industry": text(details.get("industry") or quote.get("industry")),
        "currency": currency,
        "current_price": money(current, currency),
        "change": change,
        "change_amount": money(abs(change), currency),
        "change_percent": f"{change / previous * 100:+.2f}%",
        "day_range": value_range(fast.get("dayLow"), fast.get("dayHigh"), currency),
        "year_range": value_range(fast.get("yearLow"), fast.get("yearHigh"), currency),
        "market_cap": market_cap_text,
        "country": text(details.get("country")),
        "employees": text(details.get("fullTimeEmployees")),
        "website": text(details.get("website")),
        "pe_ratio": text(details.get("trailingPE")),
        "forward_pe": text(details.get("forwardPE")),
        "dividend_yield": (
            f"{details['dividendYield']:.2f}%"
            if details.get("dividendYield") is not None
            else "N/A"
        ),
        "summary": text(details.get("longBusinessSummary")),
        "checked": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "quote": quote,
        "details": details,
        "fast_info": fast,
    }
