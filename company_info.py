import sys

from market_data import snapshot


def main():
    company_name = " ".join(sys.argv[1:]).strip() or input("Company name: ").strip()
    if not company_name:
        print("Please provide a company name.")
        return

    try:
        data = snapshot(company_name)
    except (LookupError, RuntimeError) as error:
        print(error)
        return

    quote = data["quote"]
    details = data["details"]
    change = data["change"]
    arrow = "▲" if change >= 0 else "▼"

    print("\n" + "=" * 48)
    print(f"{data['name']} ({data['symbol']})")
    print("=" * 48)
    print(f"Exchange: {quote.get('exchange', 'N/A')}")
    print(f"Sector: {data['sector']}")
    print(f"Industry: {data['industry']}")
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
    print(f"Current price: {data['current_price']}")
    print(f"Day change: {arrow} {data['change_amount']} ({data['change_percent']})")
    print(f"Day range: {data['day_range']}")
    print(f"52-week range: {data['year_range']}")
    print(f"Market cap: {data['market_cap']}")
    print(f"Checked: {data['checked']}")


if __name__ == "__main__":
    main()