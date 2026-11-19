# Market Lens

Market Lens is a small Python stock-research project with three interfaces:

- `web_app.py` serves a browser UI at `http://127.0.0.1:8000`.
- `stock_trend.py` reports price trends, moving averages, and Indian-market fundamentals.
- `stock_chatbot.py` combines market data and news with an optional Gemini or Groq chat model.
- `company_info.py` provides a lightweight company snapshot in the terminal.

The project uses live data from Yahoo Finance and, for Indian listings, best-effort HTML parsing from Screener.in. Data can be delayed, incomplete, or unavailable. This project is for education and research only and is **not financial advice**.

## Setup

Python 3.10 or newer is recommended.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your own `GEMINI_API_KEY` or `GROQ_API_KEY` to `.env` only when using the chatbot. Never commit `.env`.

## Usage

Start the browser app:

```powershell
py web_app.py
```

Run a trend report:

```powershell
py stock_trend.py Infosys
```

Run the chatbot:

```powershell
py stock_chatbot.py Infosys
py stock_chatbot.py Infosys --ask "What changed over the last year?"
py stock_chatbot.py Infosys --dry-run
```

Run the terminal snapshot:

```powershell
py company_info.py Infosys
```

The chatbot supports `/news`, `/report`, `/company <name>`, and `/quit` during an interactive session.

## Testing

```powershell
py -m unittest discover -s tests -v
```

Tests use mocked responses and do not require market-network requests.

## Limitations

- Yahoo Finance and Screener.in are third-party services and may change or rate-limit requests.
- Search results may map a company to a listing that is not the user's preferred exchange.
- Fundamentals are only scraped for `.NS` and `.BO` listings.
- AI answers are constrained to the collected data and headlines, but should still be independently verified.
