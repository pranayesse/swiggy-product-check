#!/usr/bin/env python3
"""
probe_store.py
--------------
Make-or-break experiment: can we get Swiggy to resolve a DIFFERENT store by
passing lat/lng to /api/instamart/launch (and friends), instead of relying on
the signed location cookies?

It calls the launch endpoint from inside a real (WAF-cleared) browser for two
very different Hyderabad coordinates and prints any store-id-like fields, so we
can see whether the store actually changes with the coordinates.

RUN:
    python3 probe_store.py --cookies-file cookies.txt
"""

import argparse
import json
import sys
import time

from check_availability import (
    parse_cookie_string,
    load_cookies_from_browser,
    load_cookies_from_env,
)

# Two far-apart Hyderabad points — if the store id differs between them when we
# pass lat/lng, then param-based location works.
PROBE_POINTS = [
    {"name": "Hitech City (west)", "lat": 17.4435, "lng": 78.3772},
    {"name": "LB Nagar (east)",    "lat": 17.3484, "lng": 78.5466},
]

# Endpoint/param variants to try. We test several common shapes at once.
JS_PROBE = """
async ({ points }) => {
    const out = [];
    const variants = (lat, lng) => ([
        `/api/instamart/launch?lat=${lat}&lng=${lng}`,
        `/api/instamart/launch?userLat=${lat}&userLng=${lng}`,
        `/api/instamart/home?lat=${lat}&lng=${lng}`,
        `/api/instamart/home/v2?lat=${lat}&lng=${lng}`,
    ]);

    // Pull any store-id-like values out of an object tree.
    const findStores = (obj, acc, depth=0) => {
        if (depth > 10 || !obj || typeof obj !== "object") return;
        for (const k in obj) {
            const v = obj[k];
            if (/store.?id|merchant.?id/i.test(k) && (typeof v === "string" || typeof v === "number")) {
                if (String(v) && String(v) !== "0") acc[k] = v;
            }
            if (v && typeof v === "object") findStores(v, acc, depth+1);
        }
    };

    for (const pt of points) {
        for (const path of variants(pt.lat, pt.lng)) {
            try {
                const r = await fetch(path, {
                    method: "GET", credentials: "include",
                    headers: { "Accept": "application/json", "x-requested-with": "XMLHttpRequest" },
                });
                let stores = {}, snippet = "";
                let body = "";
                try { body = await r.text(); } catch(e) {}
                try { findStores(JSON.parse(body), stores); } catch(e) {}
                snippet = body.slice(0, 160);
                out.push({ point: pt.name, path, status: r.status, stores, snippet });
            } catch (e) {
                out.push({ point: pt.name, path, error: e.toString() });
            }
            await new Promise(r => setTimeout(r, 400));
        }
    }
    return out;
};
"""


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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 9) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/149.0.0.0 Mobile Safari/537.36"),
            locale="en-IN", timezone_id="Asia/Kolkata",
        )
        context.add_cookies(
            [{"name": k, "value": v, "domain": ".swiggy.com", "path": "/"}
             for k, v in cookies.items()]
        )
        page = context.new_page()
        print("Warming up …")
        page.goto("https://www.swiggy.com/instamart",
                  wait_until="domcontentloaded", timeout=45000)
        time.sleep(6)

        print("Probing launch/home with two different coordinates …\n")
        results = page.evaluate(JS_PROBE, {"points": PROBE_POINTS})
        browser.close()

    print("=" * 74)
    for r in results:
        if "error" in r:
            print(f"  [{r['point']}] {r['path']}\n      ERROR: {r['error']}")
            continue
        stores = r.get("stores") or {}
        flag = f"  STORES={stores}" if stores else ""
        print(f"  [{r['point']}] {r['status']}  {r['path']}{flag}")
        if not stores and r.get("snippet"):
            print(f"      snippet: {r['snippet']}")
    print("=" * 74)
    print("\n  >>> If STORES differ between the two points for the same endpoint,")
    print("      param-based location works and I can check all 30 areas.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
