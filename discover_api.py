#!/usr/bin/env python3
"""
discover_api.py
---------------
Diagnostic: opens Swiggy Instamart in a real browser, performs a search the
normal way (by navigating the site), and records the ACTUAL network requests
the page makes — so we can see the real search-API endpoint, method, params
and response shape instead of guessing.

RUN:
    python3 discover_api.py --cookies-file cookies.txt
    # add --headed to watch the browser

It prints every JSON/API response whose URL or body looks related to search,
including the request method, full URL, any POST body, and whether the product
name shows up in the response.
"""

import argparse
import json
import sys
import time

from check_availability import (
    PRODUCT_SEARCH_TERM,
    PRODUCT_KEYWORDS,
    parse_cookie_string,
    load_cookies_from_browser,
    load_cookies_from_env,
)


def load_cookies(args) -> dict:
    if args.cookies_file:
        return parse_cookie_string(open(args.cookies_file).read().strip(),
                                   f"file {args.cookies_file}")
    if args.cookies:
        return parse_cookie_string(args.cookies, "--cookies flag")
    return load_cookies_from_browser() or load_cookies_from_env()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookies-file")
    parser.add_argument("--cookies")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    cookies = load_cookies(args)
    if not cookies:
        print("No cookies. Use --cookies-file cookies.txt")
        return 1

    captured = []  # (method, url, post_data, status, has_product, snippet)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 9) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/149.0.0.0 Mobile Safari/537.36"),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        context.add_cookies(
            [{"name": k, "value": v, "domain": ".swiggy.com", "path": "/"}
             for k, v in cookies.items()]
        )
        page = context.new_page()

        def on_response(resp):
            url = resp.url
            if "swiggy.com" not in url:
                return
            # Only care about API-ish calls
            if "/api/" not in url and "/dapi/" not in url:
                return
            try:
                ctype = resp.headers.get("content-type", "")
            except Exception:
                ctype = ""
            body_snippet, has_product = "", False
            if "json" in ctype:
                try:
                    text = resp.text()
                    low = text.lower()
                    has_product = all(k in low for k in PRODUCT_KEYWORDS)
                    # flag anything that looks like search/product results
                    if has_product or "search" in url.lower() or "instamart" in url.lower():
                        body_snippet = text[:200]
                except Exception:
                    pass
            req = resp.request
            post = None
            try:
                post = req.post_data
            except Exception:
                pass
            # Record search/product-related calls only
            if has_product or "search" in url.lower():
                captured.append((req.method, url, post, resp.status, has_product,
                                 body_snippet))

        page.on("response", on_response)

        print("Loading Instamart …")
        page.goto("https://www.swiggy.com/instamart",
                  wait_until="domcontentloaded", timeout=45000)
        time.sleep(5)

        print(f"Navigating to search for '{PRODUCT_SEARCH_TERM}' …")
        page.goto(
            f"https://www.swiggy.com/instamart/search?custom_back=true&query={PRODUCT_SEARCH_TERM.replace(' ', '+')}",
            wait_until="domcontentloaded", timeout=45000)
        time.sleep(6)

        # Also try typing into the search box, in case results load via XHR
        try:
            box = page.query_selector("input[type='text'], input[type='search']")
            if box:
                box.click()
                box.fill(PRODUCT_SEARCH_TERM)
                time.sleep(1)
                page.keyboard.press("Enter")
                time.sleep(6)
        except Exception as e:
            print(f"  (search box interaction skipped: {e})")

        browser.close()

    print("\n" + "=" * 70)
    print("  CAPTURED SEARCH-RELATED API CALLS")
    print("=" * 70)
    if not captured:
        print("\n  None captured. The results may load from a differently-named "
              "endpoint.\n  Re-run with --headed and watch the Network tab, or tell me.")
        return 1

    seen = set()
    for method, url, post, status, has_product, snippet in captured:
        key = (method, url.split("?")[0])
        flag = "  <-- CONTAINS PRODUCT" if has_product else ""
        print(f"\n  [{method}] {status}  {url}{flag}")
        if post:
            print(f"      POST body: {post[:300]}")
        if snippet:
            print(f"      Response:  {snippet}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
