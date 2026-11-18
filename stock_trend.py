import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
import yfinance as yf
from bs4 import BeautifulSoup
from dotenv import load_dotenv


load_dotenv()
API_KEY = os.getenv("API_KEY")


def find_stock(company_name):
    """Find an equity, preferring its NSE listing when available."""
    quotes = yf.Search(company_name, max_results=10).quotes
    equities = [item for item in quotes if item.get("quoteType") == "EQUITY"]
    if not equities:
        raise LookupError(f"No company found for '{company_name}'.")
    quote = next((item for item in equities if item.get("symbol", "").endswith(".NS")), equities[0])
    if not quote.get("symbol"):
        raise LookupError("The search result did not include a stock symbol.")
    return quote


def number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def percentage(start, end):
    return (end - start) / start * 100 if start else None


def price_trend(symbol):
    """Calculate trend figures from one year of daily prices."""
    history = yf.Ticker(symbol).history(period="1y")
    if history.empty or "Close" not in history:
        raise RuntimeError("No price history is available for this stock.")
    closes = history["Close"].dropna()
    if closes.empty:
        raise RuntimeError("No closing prices are available for this stock.")

    latest = number(closes.iloc[-1])
    changes = {}
    for days in (5, 21, 126):
        changes[f"{days}_trading_days"] = percentage(number(closes.iloc[-days - 1]), latest) if len(closes) > days else None
    changes["one_year"] = percentage(number(closes.iloc[0]), latest) if len(closes) > 1 else None
    ma50 = number(closes.rolling(50).mean().iloc[-1]) if len(closes) >= 50 else None
    ma200 = number(closes.rolling(200).mean().iloc[-1]) if len(closes) >= 200 else None
    if ma50 is not None and ma200 is not None:
        verdict = "Uptrend" if latest > ma50 > ma200 else "Downtrend" if latest < ma50 < ma200 else "Sideways / mixed"
    else:
        verdict = "Insufficient data"
    latest_date = closes.index[-1]
    return {"latest_close": latest, "latest_date": str(latest_date.date()), "changes_percent": changes,
            "ma50": ma50, "ma200": ma200, "one_year_high": number(closes.max()),
            "one_year_low": number(closes.min()), "verdict": verdict}


def table_rows(table):
    return [[cell.get_text(" ", strip=True) for cell in row.select("th, td")]
            for row in table.select("tr") if row.select("th, td")]


def scrape_fundamentals(symbol):
    """Make one best-effort Screener request for Indian listings."""
    if not symbol.endswith((".NS", ".BO")):
        return {"available": False, "reason": "Fundamentals are only scraped for .NS and .BO listings."}
    base_symbol = symbol.rsplit(".", 1)[0]
    url = f"https://www.screener.in/company/{base_symbol}/"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        about = soup.select_one(".company-profile .about p")
        ratios = []
        for item in soup.select("#top-ratios li"):
            name = item.select_one(".name")
            value = item.select_one(".nowrap")
            if name and value:
                ratios.append({"name": name.get_text(" ", strip=True), "value": value.get_text(" ", strip=True)})
        growth_table = soup.select_one("table.ranges-table")
        growth = table_rows(growth_table) if growth_table else []
        quarter_table = soup.select_one("section#quarters table")
        quarters = []
        if quarter_table:
            rows = table_rows(quarter_table)
            headers = rows[0][1:] if rows else []
            sales_row = next((row for row in rows[1:] if row and row[0].strip().lower().startswith("sales")), [])
            profit_row = next((row for row in rows[1:] if row and "net profit" in row[0].strip().lower()), [])
            for index, quarter in list(enumerate(headers))[-4:]:
                quarters.append({"quarter": quarter, "sales": sales_row[index + 1] if index + 1 < len(sales_row) else None,
                                 "net_profit": profit_row[index + 1] if index + 1 < len(profit_row) else None})
        pros = [item.get_text(" ", strip=True) for item in soup.select(".pros li")]
        cons = [item.get_text(" ", strip=True) for item in soup.select(".cons li")]
        return {"available": True, "source_url": url, "about": about.get_text(" ", strip=True) if about else None,
                "ratios": ratios, "growth": growth, "quarters": quarters, "pros": pros, "cons": cons}
    except requests.RequestException as error:
        return {"available": False, "source_url": url, "reason": f"Screener request failed: {error}"}
    except Exception as error:
        return {"available": False, "source_url": url, "reason": f"Could not parse Screener data: {error}"}


def collect(company_name):
    quote = find_stock(company_name)
    symbol = quote["symbol"]
    trend = price_trend(symbol)
    fundamentals = scrape_fundamentals(symbol)
    return {"company_name": quote.get("longname") or quote.get("shortname") or company_name,
            "symbol": symbol, "exchange": quote.get("exchange"), "trend": trend,
            "fundamentals": fundamentals, "source_url": fundamentals.get("source_url"),
            "checked": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")}


def display(value):
    return "N/A" if value is None else f"{value:,.2f}" if isinstance(value, float) else str(value)


def print_report(data):
    trend = data["trend"]
    print(f"\n{data['company_name']} ({data['symbol']})")
    print("=" * 60)
    print("PRICE TREND")
    print(f"Latest close ({trend['latest_date']}): {display(trend['latest_close'])}")
    for period, change in trend["changes_percent"].items():
        print(f"Change over {period.replace('_', ' ')}: {display(change)}%")
    print(f"MA50: {display(trend['ma50'])} | MA200: {display(trend['ma200'])}")
    print(f"One-year high / low: {display(trend['one_year_high'])} / {display(trend['one_year_low'])}")
    print(f"Verdict: {trend['verdict']}")
    fundamentals = data["fundamentals"]
    print("\nABOUT")
    print(fundamentals.get("about") or fundamentals.get("reason", "N/A"))
    print("\nKEY RATIOS")
    print("\n".join(f"{item['name']}: {item['value']}" for item in fundamentals.get("ratios", [])) or "N/A")
    print("\nLONG-TERM GROWTH")
    print("\n".join(" | ".join(row) for row in fundamentals.get("growth", [])) or "N/A")
    print("\nLAST 4 QUARTERS")
    print("\n".join(f"{item['quarter']}: Sales {item.get('sales') or 'N/A'}, Net Profit {item.get('net_profit') or 'N/A'}" for item in fundamentals.get("quarters", [])) or "N/A")
    print("\nPROS / CONS")
    print("Pros: " + "; ".join(fundamentals.get("pros", [])) if fundamentals.get("pros") else "Pros: N/A")
    print("Cons: " + "; ".join(fundamentals.get("cons", [])) if fundamentals.get("cons") else "Cons: N/A")
    print(f"\nSource URL: {data.get('source_url') or 'Yahoo Finance price history only'}")


def main():
    company_name = " ".join(sys.argv[1:]).strip() or input("Company name: ").strip()
    if not company_name:
        print("Please provide a company name.")
        return
    try:
        data = collect(company_name)
        filename = f"{data['symbol'].replace('.', '_')}_trend.json"
        Path(filename).write_text(json.dumps(data, indent=2), encoding="utf-8")
        print_report(data)
        print(f"\nSaved data to {filename}")
    except LookupError as error:
        print(error)
    except Exception as error:
        print(f"Could not collect stock data: {error}")


if __name__ == "__main__":
    main()