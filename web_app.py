import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from market_data import LookupSuggestionError, NoPublicEquityError, snapshot


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Lens</title>
  <style>
    :root { --ink:#183238; --muted:#627479; --paper:#f5f0e8; --card:#fffdf8;
      --line:#d9ddd5; --teal:#0d7770; --coral:#e16d52; }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); font:16px Georgia, serif; background:
      radial-gradient(circle at 10% 10%, #e6eee5 0 20%, transparent 45%), var(--paper); }
    main { width:min(1080px, calc(100% - 36px)); margin:auto; padding:54px 0 70px; }
    header { display:flex; justify-content:space-between; align-items:end; gap:24px; margin-bottom:34px; }
    .eyebrow { color:var(--coral); font:700 12px Arial, sans-serif; letter-spacing:2px; text-transform:uppercase; }
    h1 { font-size:clamp(42px, 7vw, 76px); line-height:.95; margin:10px 0 0; font-weight:500; }
    .intro { color:var(--muted); font:15px Arial, sans-serif; max-width:300px; line-height:1.5; }
    form { display:flex; gap:10px; margin-bottom:28px; }
    input { flex:1; min-width:0; padding:17px 18px; border:1px solid var(--line); border-radius:4px;
      background:var(--card); color:var(--ink); font:18px Arial, sans-serif; outline:none; }
    input:focus { border-color:var(--teal); box-shadow:0 0 0 3px #0d777022; }
    button { border:0; border-radius:4px; padding:0 24px; background:var(--teal); color:white;
      font:700 15px Arial, sans-serif; cursor:pointer; }
    button:hover { background:#095e59; } button:disabled { opacity:.6; cursor:wait; }
    #status { min-height:24px; color:var(--muted); font:14px Arial, sans-serif; }
    #status button { margin-left:8px; padding:7px 12px; font-size:13px; }
    .hero, .panel { background:var(--card); border:1px solid var(--line); border-radius:6px; }
    .hero { padding:28px; display:flex; justify-content:space-between; gap:20px; align-items:start; }
    .hero h2 { margin:6px 0 5px; font-size:34px; font-weight:500; }
    .symbol { color:var(--teal); font:700 14px Arial, sans-serif; letter-spacing:1px; }
    .price { text-align:right; white-space:nowrap; }
    .price strong { display:block; font:700 36px Arial, sans-serif; }
    .change { font:700 15px Arial, sans-serif; } .up { color:#16845b; } .down { color:#c65343; }
    .grid { display:grid; grid-template-columns:repeat(3, 1fr); gap:14px; margin-top:14px; }
    .panel { padding:20px; } .panel h3 { margin:0 0 16px; font-size:18px; font-weight:500; }
    dl { display:grid; grid-template-columns:1fr auto; gap:11px 16px; margin:0; font:14px Arial, sans-serif; }
    dt { color:var(--muted); } dd { margin:0; text-align:right; font-weight:700; }
    .summary { grid-column:1 / -1; line-height:1.6; color:#40565a; font:15px Arial, sans-serif; }
    .summary h3 { color:var(--ink); font:18px Georgia, serif; }
    .empty { padding:52px 20px; text-align:center; color:var(--muted); }
    footer { margin-top:26px; color:var(--muted); font:12px Arial, sans-serif; }
    @media (max-width:700px) { main { padding-top:30px; } header, .hero { display:block; }
      .intro { margin-top:18px; } .price { text-align:left; margin-top:24px; } .grid { grid-template-columns:1fr; }
      .summary { grid-column:auto; } button { padding:0 16px; } }
  </style>
</head>
<body>
  <main>
    <header><div><div class="eyebrow">Live market brief</div><h1>Market Lens</h1></div>
      <div class="intro">Search a company to see its latest market snapshot and business profile.</div></header>
    <form id="search"><input id="company" placeholder="Try Infosys, Tata Motors, or Apple" autocomplete="off"><button>Search</button></form>
    <div id="status">Enter a company name to begin.</div>
    <section id="result" hidden></section>
    <footer>Data from Yahoo Finance via yfinance. Prices may be delayed. For research only, not financial advice.</footer>
  </main>
  <script>
    const form = document.querySelector('#search'), input = document.querySelector('#company');
    const status = document.querySelector('#status'), result = document.querySelector('#result');
    const esc = value => String(value ?? 'N/A').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const row = (label, value) => `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`;
    form.addEventListener('submit', async event => {
      event.preventDefault(); const name = input.value.trim(); if (!name) return;
      const button = form.querySelector('button'); window.marketLensSuggestion = null;
      button.disabled = true; status.textContent = 'Looking up live data...'; result.hidden = true;
      try {
        const response = await fetch(`/api/company?name=${encodeURIComponent(name)}`), data = await response.json();
        if (!response.ok) {
          window.marketLensSuggestion = data.suggestion || null;
          throw new Error(data.error || 'Could not load company data.');
        }
        const direction = data.change >= 0 ? 'up' : 'down', arrow = data.change >= 0 ? '▲' : '▼';
        result.innerHTML = `<div class="hero"><div><div class="symbol">${esc(data.symbol)} · ${esc(data.exchange)}</div><h2>${esc(data.name)}</h2><div>${esc(data.sector)} · ${esc(data.industry)}</div></div>
          <div class="price"><strong>${esc(data.current_price)}</strong><span class="change ${direction}">${arrow} ${esc(data.change_amount)} (${esc(data.change_percent)})</span></div></div>
          <div class="grid"><div class="panel"><h3>Trading range</h3><dl>${row('Today', data.day_range)}${row('52 weeks', data.year_range)}${row('Currency', data.currency)}</dl></div>
          <div class="panel"><h3>Company profile</h3><dl>${row('Country', data.country)}${row('Employees', data.employees)}${row('Website', data.website)}</dl></div>
          <div class="panel"><h3>Valuation</h3><dl>${row('Market cap', data.market_cap)}${row('P/E ratio', data.pe_ratio)}${row('Forward P/E', data.forward_pe)}${row('Dividend yield', data.dividend_yield)}</dl></div>
          <div class="panel summary"><h3>Business summary</h3>${esc(data.summary)}</div></div>`;
        result.hidden = false; status.textContent = `Checked ${data.checked}`;
      } catch (error) {
        status.textContent = error.message;
        if (window.marketLensSuggestion) {
          const suggestion = window.marketLensSuggestion;
          const suggestionButton = document.createElement('button');
          suggestionButton.type = 'button';
          suggestionButton.textContent = `Search ${suggestion}`;
          suggestionButton.addEventListener('click', () => {
            input.value = suggestion;
            form.requestSubmit();
          });
          status.appendChild(document.createTextNode(' '));
          status.appendChild(suggestionButton);
        }
        window.marketLensSuggestion = null;
        result.hidden = true;
      }
      button.disabled = false;
    });
  </script>
</body>
</html>"""


def lookup(company_name):
    return snapshot(company_name)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body, content_type = HTML.encode(), "text/html; charset=utf-8"
        elif parsed.path == "/api/company":
            name = parse_qs(parsed.query).get("name", [""])[0].strip()
            try:
                if not name:
                    raise ValueError("Enter a company name.")
                body, content_type = json.dumps(lookup(name)).encode(), "application/json"
            except LookupSuggestionError as error:
                body, content_type = json.dumps({
                    "error": str(error),
                    "kind": "suggestion",
                    "suggestion": error.suggestion,
                }).encode(), "application/json"
                self.send_response(404)
                self.send_header("Content-Type", content_type)
                self.end_headers()
                self.wfile.write(body)
                return
            except NoPublicEquityError as error:
                body, content_type = json.dumps({
                    "error": str(error),
                    "kind": "private_or_unlisted",
                }).encode(), "application/json"
                self.send_response(404)
                self.send_header("Content-Type", content_type)
                self.end_headers()
                self.wfile.write(body)
                return
            except (ValueError, LookupError, RuntimeError) as error:
                body, content_type = json.dumps({
                    "error": str(error),
                    "kind": "lookup_error" if isinstance(error, LookupError) else "invalid_request",
                }).encode(), "application/json"
                self.send_response(404 if isinstance(error, LookupError) else 400)
                self.send_header("Content-Type", content_type)
                self.end_headers()
                self.wfile.write(body)
                return
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        del args


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Market Lens is running at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()