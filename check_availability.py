#!/usr/bin/env python3
"""
check_availability.py
---------------------
Checks where "Natch Thai Dry Mango Slices: Chili" is in stock on
Swiggy Instamart across 30 Hyderabad areas.

Requires your real Swiggy session cookies (Swiggy's API blocks plain requests).

HOW TO GET COOKIES:
  1. Open swiggy.com in Chrome, browse Instamart a little.
  2. Press F12 → Network tab.
  3. Click any request to www.swiggy.com → Headers → Request Headers.
  4. Find the "cookie" row and copy its entire value.

OPTION 1 — cookie file (most reliable, avoids shell quoting issues):
    Paste the cookie string into a file called cookies.txt, then:
    python check_availability.py --cookies-file cookies.txt

OPTION 2 — paste directly (use SINGLE quotes to prevent shell expansion):
    python check_availability.py --cookies 'deviceId=...; tid=...; ...'
    *** IMPORTANT: use single quotes ' not double quotes " ***
    (double quotes cause $ signs in GA values to be eaten by the shell)

OPTION 3 — env var:
    export SWIGGY_COOKIES='deviceId=...; tid=...; ...'
    python check_availability.py

OPTION 4 — auto-load from Chrome:
    pip install browser-cookie3
    python check_availability.py
"""

import argparse
import json
import os
import sys
import time

import requests

PRODUCT_SEARCH_TERM = "natch thai mango"
PRODUCT_KEYWORDS    = ["natch", "mango"]

HYDERABAD_LOCATIONS = [
    {"name": "Hitech City",      "lat": 17.4435, "lng": 78.3772},
    {"name": "Madhapur",         "lat": 17.4481, "lng": 78.3915},
    {"name": "Kondapur",         "lat": 17.4602, "lng": 78.3541},
    {"name": "Gachibowli",       "lat": 17.4401, "lng": 78.3489},
    {"name": "Banjara Hills",    "lat": 17.4126, "lng": 78.4482},
    {"name": "Jubilee Hills",    "lat": 17.4314, "lng": 78.4097},
    {"name": "Ameerpet",         "lat": 17.4374, "lng": 78.4487},
    {"name": "Begumpet",         "lat": 17.4396, "lng": 78.4637},
    {"name": "Mehdipatnam",      "lat": 17.3958, "lng": 78.4386},
    {"name": "Attapur",          "lat": 17.3765, "lng": 78.4335},
    {"name": "Manikonda",        "lat": 17.3941, "lng": 78.3920},
    {"name": "Narsingi",         "lat": 17.3750, "lng": 78.3508},
    {"name": "Kukatpally",       "lat": 17.4849, "lng": 78.3993},
    {"name": "KPHB",             "lat": 17.4939, "lng": 78.3908},
    {"name": "Miyapur",          "lat": 17.4980, "lng": 78.3515},
    {"name": "Nizampet",         "lat": 17.5168, "lng": 78.3847},
    {"name": "Kompally",         "lat": 17.5498, "lng": 78.4745},
    {"name": "Secunderabad",     "lat": 17.4399, "lng": 78.4983},
    {"name": "Bowenpally",       "lat": 17.4818, "lng": 78.4844},
    {"name": "Alwal",            "lat": 17.5097, "lng": 78.5027},
    {"name": "Malkajgiri",       "lat": 17.4486, "lng": 78.5266},
    {"name": "AS Rao Nagar",     "lat": 17.4682, "lng": 78.5568},
    {"name": "Sainikpuri",       "lat": 17.4961, "lng": 78.5548},
    {"name": "Uppal",            "lat": 17.4013, "lng": 78.5593},
    {"name": "Nagole",           "lat": 17.3789, "lng": 78.5671},
    {"name": "Dilsukhnagar",     "lat": 17.3688, "lng": 78.5246},
    {"name": "LB Nagar",         "lat": 17.3484, "lng": 78.5466},
    {"name": "Vanasthalipuram",  "lat": 17.3256, "lng": 78.5586},
    {"name": "Hayathnagar",      "lat": 17.3273, "lng": 78.6046},
    {"name": "Shamshabad",       "lat": 17.2403, "lng": 78.4294},
]

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept":           "application/json, text/plain, */*",
    "Accept-Language":  "en-IN,en;q=0.9",
    "Accept-Encoding":  "gzip, deflate, br",
    "Referer":          "https://www.swiggy.com/instamart",
    "Origin":           "https://www.swiggy.com",
    "x-requested-with": "XMLHttpRequest",
}


# ── Cookie loading ────────────────────────────────────────────────────────────

def load_cookies_from_browser() -> dict:
    """Try to read Swiggy cookies from Chrome then Firefox via browser_cookie3."""
    try:
        import browser_cookie3
    except ImportError:
        return {}

    for loader, name in [
        (browser_cookie3.chrome,  "Chrome"),
        (browser_cookie3.firefox, "Firefox"),
    ]:
        try:
            jar = loader(domain_name=".swiggy.com")
            cookies = {c.name: c.value for c in jar}
            if cookies:
                print(f"  Loaded {len(cookies)} cookies from {name}: {list(cookies.keys())}")
                return cookies
        except Exception as exc:
            print(f"  {name} cookie load failed: {exc}")

    return {}


def parse_cookie_string(raw: str, source: str) -> dict:
    """Parse a semicolon-separated cookie string into a dict."""
    cookies = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            cookies[k.strip()] = v.strip()
    if cookies:
        print(f"  Loaded {len(cookies)} cookies from {source}")
    return cookies


def load_cookies_from_env() -> dict:
    raw = os.environ.get("SWIGGY_COOKIES", "").strip()
    if not raw:
        return {}
    return parse_cookie_string(raw, "SWIGGY_COOKIES env var")


def create_session(cookies: dict) -> requests.Session:
    s = requests.Session()
    s.headers.update(BASE_HEADERS)
    for name, value in cookies.items():
        s.cookies.set(name, value, domain=".swiggy.com")
    return s


# ── API calls ─────────────────────────────────────────────────────────────────

def verify_session(s: requests.Session) -> bool:
    """Quick check that the session works before we loop over all locations."""
    try:
        r = s.get("https://www.swiggy.com/", timeout=10)
        print(f"  Homepage: HTTP {r.status_code}")
        return r.ok
    except requests.RequestException as e:
        print(f"  Warning: {e}")
        return False


def search(s: requests.Session, loc: dict) -> dict:
    url = "https://www.swiggy.com/api/instamart/search"
    params = {
        "query":          PRODUCT_SEARCH_TERM,
        "pageNumber":     0,
        "layoutId":       3128,
        "pageType":       "INSTAMART_SEARCH",
        "isPreSearchTag": "false",
        "queryUniqueId":  "",
        "lat":            loc["lat"],
        "lng":            loc["lng"],
        "storeType":      "INSTAMART",
    }
    try:
        r = s.get(url, params=params, timeout=20)
        if r.ok:
            return r.json()
        return {"_http_error": r.status_code, "_text": r.text[:300]}
    except requests.RequestException as exc:
        return {"_exception": str(exc)}


# ── Response parsing ──────────────────────────────────────────────────────────

def collect_items(obj, depth: int = 0) -> list:
    if depth > 14:
        return []
    out = []
    if isinstance(obj, dict):
        if "name" in obj and ("price" in obj or "defaultPrice" in obj):
            out.append(obj)
        for v in obj.values():
            out.extend(collect_items(v, depth + 1))
    elif isinstance(obj, list):
        for elem in obj:
            out.extend(collect_items(elem, depth + 1))
    return out


def find_product(data: dict) -> dict | None:
    for item in collect_items(data):
        if all(kw in item.get("name", "").lower() for kw in PRODUCT_KEYWORDS):
            return item
    return None


def is_in_stock(item: dict) -> bool:
    val = item.get("inStock", item.get("isInStock", 1))
    return bool(val) if isinstance(val, bool) else int(val) != 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Check Swiggy Instamart availability across Hyderabad")
    parser.add_argument(
        "--cookies",
        metavar="COOKIE_STRING",
        help="Cookie string from Chrome DevTools. Use SINGLE quotes to avoid shell expansion of $ signs.",
    )
    parser.add_argument(
        "--cookies-file",
        metavar="FILE",
        help="Path to a file containing the cookie string (avoids all shell quoting issues).",
    )
    args = parser.parse_args()

    print("=" * 64)
    print("  Natch Thai Dry Mango Slices: Chili — Hyderabad Availability")
    print("=" * 64)

    # Load cookies: --cookies-file > --cookies > browser > env var
    print("\nLoading Swiggy session cookies …")
    if args.cookies_file:
        try:
            raw = open(args.cookies_file).read().strip()
            cookies = parse_cookie_string(raw, f"file {args.cookies_file}")
        except OSError as e:
            print(f"  ERROR reading {args.cookies_file}: {e}")
            return 1
    elif args.cookies:
        cookies = parse_cookie_string(args.cookies, "--cookies flag")
    else:
        cookies = load_cookies_from_browser() or load_cookies_from_env()

    if cookies and len(cookies) < 5:
        print(
            f"\n  WARNING: Only {len(cookies)} cookie(s) loaded — expected 20+.\n"
            "  The shell probably ate the rest due to $ expansion.\n"
            "  FIX: Save the cookie string to cookies.txt and run:\n"
            "       python check_availability.py --cookies-file cookies.txt\n"
            "  OR use single quotes:  --cookies 'deviceId=...; ...'\n"
        )
        return 1

    if not cookies:
        print(
            "\n  ERROR: No Swiggy cookies found.\n"
            "  Swiggy blocks requests without a real browser session.\n\n"
            "  EASIEST FIX:\n"
            "    1. Open swiggy.com in Chrome and browse Instamart a little.\n"
            "    2. Press F12 → Network tab.\n"
            "    3. Click any request to www.swiggy.com → Headers → Request Headers.\n"
            "    4. Find the 'cookie' row and copy its entire value.\n"
            "    5. Run:\n"
            '       python check_availability.py --cookies "paste_the_cookie_value_here"\n'
        )
        return 1

    s = create_session(cookies)

    print("\nVerifying session …")
    verify_session(s)
    time.sleep(0.5)

    available, out_of_stock, not_listed, errors = [], [], [], []

    print(f"\nChecking {len(HYDERABAD_LOCATIONS)} Hyderabad areas …\n")
    for i, loc in enumerate(HYDERABAD_LOCATIONS, 1):
        name = loc["name"]
        print(f"  [{i:02d}/{len(HYDERABAD_LOCATIONS)}] {name:<22}", end=" ", flush=True)

        data = search(s, loc)

        if "_http_error" in data or "_exception" in data:
            err = data.get("_http_error") or data.get("_exception")
            body = data.get("_text", "")
            print(f"ERROR ({err})")
            if body:
                print(f"              Response: {body[:120]}")
            errors.append((name, str(err)))
        else:
            item = find_product(data)
            if item is None:
                raw = json.dumps(data).lower()
                if "not_serviceable" in raw or "not serviceable" in raw:
                    print("Instamart not serviceable here")
                else:
                    print("Product not listed in search results")
                not_listed.append(name)
            elif is_in_stock(item):
                print(f"IN STOCK  ✓  [{item.get('name')}]")
                available.append(name)
            else:
                print(f"OUT OF STOCK  [{item.get('name')}]")
                out_of_stock.append(name)

        time.sleep(1.2)

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 64)
    print("  RESULTS SUMMARY")
    print("=" * 64)

    if available:
        print(f"\n  ✓  IN STOCK at {len(available)} location(s):")
        for loc in available:
            print(f"       {loc}")
    else:
        print("\n  Product not found in stock at any checked location.")

    if out_of_stock:
        print(f"\n  –  OUT OF STOCK at {len(out_of_stock)} location(s):")
        for loc in out_of_stock:
            print(f"       {loc}")

    if not_listed:
        print(f"\n  ?  Not listed / Instamart unavailable ({len(not_listed)}):")
        for loc in not_listed:
            print(f"       {loc}")

    if errors:
        print(f"\n  !  API errors ({len(errors)}):")
        for loc, err in errors:
            print(f"       {loc}: {err}")

    print()
    return 0 if available else 1


if __name__ == "__main__":
    sys.exit(main())
