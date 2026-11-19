import json
import os
import sys
from urllib.parse import quote

import feedparser
import requests
import yfinance as yf
from dotenv import load_dotenv
from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError

from stock_trend import collect


load_dotenv()


def text(value, fallback="N/A"):
    return fallback if value in (None, "") else str(value)


def today_snapshot(symbol):
    """Read the current snapshot separately from the one-year trend data."""
    info = yf.Ticker(symbol).fast_info
    price = info.get("lastPrice")
    previous = info.get("previousClose")
    change = (price - previous) / previous * 100 if price is not None and previous else None
    return {"price": price, "day_change_percent": change, "year_high": info.get("yearHigh"),
            "year_low": info.get("yearLow"), "market_cap": info.get("marketCap"),
            "currency": text(info.get("currency"))}


def get_news(company_name):
    """Download RSS first, then parse the downloaded bytes locally."""
    query = quote(f'"{company_name}" share OR stock')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        headlines = []
        for entry in feed.entries[:8]:
            raw_title = text(entry.get("title"), "Untitled")
            title, separator, suffix = raw_title.rpartition(" - ")
            source = text(entry.get("source", {}).get("title") if entry.get("source") else None,
                          suffix if separator else "Unknown source")
            headlines.append({"title": title if separator else raw_title, "source": source,
                              "date": text(entry.get("published") or entry.get("updated")),
                              "link": text(entry.get("link"))})
        return headlines, None
    except (requests.RequestException, ValueError) as error:
        return [], f"News unavailable: {error}"
    except Exception as error:
        return [], f"News could not be parsed: {error}"


def load_company(company_name):
    data = collect(company_name)
    symbol = data["symbol"]
    data["today"] = today_snapshot(symbol)
    data["news"], data["news_note"] = get_news(company_name)
    return data


def settings():
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider not in ("gemini", "groq"):
        provider = "gemini"
    if provider == "groq":
        return provider, os.getenv("GROQ_API_KEY"), os.getenv("LLM_MODEL") or "openai/gpt-oss-20b", "https://api.groq.com/openai/v1"
    return provider, os.getenv("GEMINI_API_KEY"), os.getenv("LLM_MODEL") or "gemini-2.5-flash", "https://generativelanguage.googleapis.com/v1beta/openai/"


def system_message(data):
    rules = (
        "You answer only from DATA and NEWS below. If an answer is not there, say exactly: "
        "That is not in my data. Name the source and date when using a headline. Explain finance words. "
        "Never tell the user to buy, sell, or hold. Use simple English and at most 120 words."
    )
    payload = json.dumps({"DATA": data, "NEWS": data.get("news", [])}, ensure_ascii=False, default=str)
    return rules + "\n\nDATA AND NEWS JSON:\n" + payload


def client_for(provider, key, base_url):
    if not key:
        raise RuntimeError(f"Missing {provider.upper()} API key; add it to .env.")
    return OpenAI(api_key=key, base_url=base_url, timeout=45.0, max_retries=0)


def error_detail(error):
    """Keep the provider's useful message while avoiding a traceback."""
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        provider_error = body.get("error")
        if isinstance(provider_error, dict) and provider_error.get("message"):
            return str(provider_error["message"])
        if body.get("message"):
            return str(body["message"])
    return str(error).splitlines()[0][:240]


def friendly_error(error, provider):
    status = getattr(error, "status_code", None)
    message = str(error).lower()
    detail = error_detail(error)
    if isinstance(error, APITimeoutError):
        return "AI request timed out after 45 seconds; try a shorter question or another model."
    if isinstance(error, APIConnectionError):
        return "Could not connect to the AI service; check your internet connection."
    if status == 429 or "429" in message:
        return "Free limit reached: wait a minute or switch LLM_PROVIDER in .env."
    if isinstance(error, AuthenticationError) or status == 401 or "api key" in message:
        key_name = "GROQ_API_KEY" if provider == "groq" else "GEMINI_API_KEY"
        return f"Invalid {provider.title()} key: update {key_name} in .env."
    if status == 400 and "api key" in message:
        return f"Invalid {provider.title()} key: update {('GROQ_API_KEY' if provider == 'groq' else 'GEMINI_API_KEY')} in .env."
    if isinstance(error, RateLimitError):
        return "Free limit reached: wait a minute or switch LLM_PROVIDER in .env."
    if status == 404:
        return f"{provider.title()} rejected the model/request (404): {detail}. Set LLM_MODEL in .env."
    if isinstance(error, APIError):
        return f"{provider.title()} API error ({status or 'unknown'}): {detail}"
    return f"AI request failed: {detail}"


def ask(client, model, system, history, question, provider):
    messages = [{"role": "system", "content": system}, *history[-16:], {"role": "user", "content": question}]
    try:
        result = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
        return result.choices[0].message.content.strip(), model
    except Exception as error:
        return friendly_error(error, provider), model


def print_header(data):
    today = data["today"]
    trend = data["trend"]
    print(f"\n{data['company_name']} ({data['symbol']})")
    print(f"Price: {text(today.get('price'))} {today.get('currency', '')} | 1-year change: {text(trend['changes_percent'].get('one_year'))}% | Headlines: {len(data['news'])}")
    if data.get("news_note"):
        print(data["news_note"])
    print("Data may be delayed. This tool is for research only, not financial advice.")


def print_news(data):
    if not data["news"]:
        print(data.get("news_note", "No headlines available."))
        return
    for index, item in enumerate(data["news"], 1):
        print(f"{index}. {item['title']} ({item['source']}, {item['date']})\n   {item['link']}")


def report_prompt():
    return ("Write a report with exactly these five sections, in this order: Company in one line; "
            "Recent price trend; Business health; In the news; One-line summary. Use only the supplied data and news.")


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    ask_index = args.index("--ask") if "--ask" in args else -1
    question = args[ask_index + 1] if ask_index >= 0 and ask_index + 1 < len(args) else None
    names = [arg for arg in args if not arg.startswith("--") and (ask_index < 0 or arg != question)]
    company_name = " ".join(names).strip() or input("Company name: ").strip()
    if not company_name:
        print("Please provide a company name.")
        return
    try:
        data = load_company(company_name)
    except Exception as error:
        print(f"Could not load company data: {str(error).splitlines()[0]}")
        return
    system = system_message(data)
    if dry_run:
        print(system)
        print(f"\nSystem message size: {len(system)} characters")
        return
    provider, key, model, base_url = settings()
    try:
        client = client_for(provider, key, base_url)
    except RuntimeError as error:
        print(error)
        if not question:
            print("Data loaded. AI questions will work after the key is added to .env.")
    print_header(data)
    history = []
    if question:
        if "client" not in locals():
            return
        answer, model = ask(client, model, system, history, question, provider)
        print(f"Bot: {answer}")
        return
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return
        if user_input == "/quit":
            print("Goodbye.")
            return
        if user_input == "/news":
            print_news(data)
            continue
        if user_input.startswith("/company "):
            try:
                company_name = user_input[9:].strip()
                data = load_company(company_name)
                system, history = system_message(data), []
                print_header(data)
            except Exception as error:
                print(f"Could not load company data: {str(error).splitlines()[0]}")
            continue
        if user_input == "/report":
            if "client" not in locals():
                print(f"Missing {provider.upper()} API key; add it to .env.")
                continue
            answer, model = ask(client, model, system, history, report_prompt(), provider)
            report_file = f"{data['symbol'].replace('.', '_')}_report.md"
            with open(report_file, "w", encoding="utf-8") as file:
                file.write(answer + "\n")
            print(f"Bot: {answer}\nSaved report to {report_file}")
            continue
        if not user_input:
            continue
        if "client" not in locals():
            print(f"Missing {provider.upper()} API key; add it to .env.")
            continue
        answer, model = ask(client, model, system, history, user_input, provider)
        print(f"Bot: {answer}")
        history.extend([{"role": "user", "content": user_input}, {"role": "assistant", "content": answer}])


if __name__ == "__main__":
    main()