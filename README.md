# swiggy-product-check

Tools to check where a specific product — *"Natch Thai Dry Mango Slices: Chili"* —
is in stock on **Swiggy Instamart** across 30 areas of Hyderabad.

Swiggy's Instamart API is protected by AWS WAF, whose anti-bot token is generated
by JavaScript that a plain HTTP client can't run. This repo therefore includes both
a lightweight `requests`-based checker and a more robust browser-driven version that
passes the WAF naturally.

## Scripts

| Script | What it does |
| --- | --- |
| `check_availability.py` | Lightweight checker using `requests` + your real Swiggy session cookies. Fastest, but may hit `403`s from the WAF. |
| `check_availability_browser.py` | Robust checker that drives a real Chromium browser via Playwright, then calls Swiggy's search API from inside the page so every request carries a valid WAF token. |
| `discover_api.py` | Diagnostic that records all Instamart API calls the page makes — used to find the search and store-resolution endpoints. |
| `probe_store.py` | Experiment to test whether passing `lat/lng` to the launch endpoint resolves a different store. |

## Getting your Swiggy cookies

Swiggy's API blocks unauthenticated requests, so you need your own session cookies:

1. Open [swiggy.com](https://www.swiggy.com) in Chrome and browse Instamart a little.
2. Press **F12** → **Network** tab.
3. Click any request to `www.swiggy.com` → **Headers** → **Request Headers**.
4. Copy the entire value of the `cookie` row.

Paste that string into a file named `cookies.txt` (it's git-ignored).

## Usage

### Lightweight (`requests`)

```bash
# Option 1 — cookie file (most reliable)
python check_availability.py --cookies-file cookies.txt

# Option 2 — paste directly (use SINGLE quotes)
python check_availability.py --cookies 'deviceId=...; tid=...; ...'

# Option 3 — env var
export SWIGGY_COOKIES='deviceId=...; tid=...; ...'
python check_availability.py

# Option 4 — auto-load from Chrome
pip install browser-cookie3
python check_availability.py
```

### Browser-driven (Playwright)

```bash
# One-time setup
pip install playwright browser-cookie3
playwright install chromium

# Run (add --headed to watch)
python check_availability_browser.py --cookies-file cookies.txt
```

## Requirements

- Python 3
- `requests` (for the lightweight checker)
- `playwright` and `browser-cookie3` (for the browser-driven checker)

## Notes

- `cookies.txt` and `__pycache__/` are git-ignored — never commit your session cookies.
- These scripts hit Swiggy's private endpoints for personal use; be mindful of rate limits.
