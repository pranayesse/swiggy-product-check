#!/usr/bin/env python3
"""
discover_api.py
---------------
Diagnostic: opens Swiggy Instamart in a real browser and records ALL Instamart
API calls the page makes, focusing on:
  (a) the search endpoint, and
  (b) any endpoint that resolves a STORE ID from a location (lat/lng),
which we need in order to check availability across different areas.

RUN:
    python3 discover_api.py --cookies-file cookies.txt
    # add --headed to watch
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

STORE_KEYS = {"storeid", "primarystoreid", "secondarystoreid", "store_id",
              "primary_store_id", "merchantid", "merchant_id"}


def load_cookies(args) -> dict:
    if args.cookies_file:
        return parse_cookie_string(open(args.cookies_file).read().strip(),
                                   f"file {args.cookies_file}")
    if args.cookies:
        return parse_cookie_string(args.cookies, "--cookies flag")
    return load_cookies_from_browser() or load_cookies_from_env()


def find_store_ids(obj, found: dict, depth=0):
    """Recursively collect any store-id-like key/value pairs."""
    if depth > 12 or len(found) > 20:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in STORE_KEYS and isinstance(v, (str, int)) and str(v) not in ("", "0"):
                found[k] = v
            find_store_ids(v, found, depth + 1)
    elif isinstance(obj, list):
        for e in obj[:20]:
            find_store_ids(e, found, depth + 1)


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

    calls = []  # dicts with method,url,post,status,store_ids,has_product

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
            if "swiggy.com" not in url or ("/api/instamart" not in url and "/dapi/instamart" not in url):
                return
            store_ids, has_product = {}, False
            try:
                if "json" in resp.headers.get("content-type", ""):
                    text = resp.text()
                    has_product = all(k in text.lower() for k in PRODUCT_KEYWORDS)
                    try:
                        find_store_ids(json.loads(text), store_ids)
                    except Exception:
                        pass
            except Exception:
                pass
            req = resp.request
            post = None
            try:
                post = req.post_data
            except Exception:
                pass
            calls.append({"method": req.method, "url": url, "post": post,
                          "status": resp.status, "store_ids": store_ids,
                          "has_product": has_product})

        page.on("response", on_response)

        print("Loading Instamart (this resolves your store) …")
        page.goto("https://www.swiggy.com/instamart",
                  wait_until="domcontentloaded", timeout=45000)
        time.sleep(6)

        print(f"Searching for '{PRODUCT_SEARCH_TERM}' …")
        page.goto(
            f"https://www.swiggy.com/instamart/search?custom_back=true&query={PRODUCT_SEARCH_TERM.replace(' ', '+')}",
            wait_until="domcontentloaded", timeout=45000)
        time.sleep(6)

        browser.close()

    # ── Report ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 74)
    print("  ALL INSTAMART API CALLS")
    print("=" * 74)
    for c in calls:
        path = c["url"].split("?")[0].replace("https://www.swiggy.com", "")
        qkeys = ""
        if "?" in c["url"]:
            qkeys = " ?" + "&".join(kv.split("=")[0] for kv in c["url"].split("?", 1)[1].split("&"))
        flags = []
        if c["has_product"]:
            flags.append("HAS_PRODUCT")
        if c["store_ids"]:
            flags.append(f"STORE_IDS={c['store_ids']}")
        flag_str = ("  <<< " + " | ".join(flags)) if flags else ""
        print(f"\n  [{c['method']}] {c['status']}  {path}{qkeys}{flag_str}")
        if c["post"]:
            print(f"      body: {c['post'][:200]}")

    print("\n" + "=" * 74)
    print("  STORE-ID-BEARING ENDPOINTS (these tell us how location maps to a store)")
    print("=" * 74)
    any_store = False
    for c in calls:
        if c["store_ids"]:
            any_store = True
            path = c["url"].split("?")[0].replace("https://www.swiggy.com", "")
            print(f"  [{c['method']}] {path}  ->  {c['store_ids']}")
    if not any_store:
        print("  (none found — tell me and I'll widen the search)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
