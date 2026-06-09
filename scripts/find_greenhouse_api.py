"""One-time diagnostic: find the real JSON API endpoint my.greenhouse.io uses.

Run: uv run python scripts/find_greenhouse_api.py
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

SESSION_FILE = Path("storage/sessions/greenhouse.json")


async def main():
    session = json.loads(SESSION_FILE.read_text())
    cookies = session["cookies"]

    print("Opening my.greenhouse.io in headless browser with your session cookies...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_cookies(cookies)

        page = await context.new_page()
        found = []

        async def handle_response(response):
            ct = response.headers.get("content-type", "")
            if "application/json" in ct:
                try:
                    body = await response.text()
                    if "job" in body.lower():
                        print(f"\n>>> JSON endpoint found!")
                        print(f"    URL: {response.url}")
                        print(f"    Status: {response.status}")
                        print(f"    Body preview:\n{body[:500]}")
                        found.append(response.url)
                except Exception:
                    pass

        page.on("response", handle_response)

        await page.goto(
            "https://my.greenhouse.io/jobs?query=Software+Engineer&date_posted=past_24_hours",
            wait_until="networkidle",
            timeout=30000,
        )

        await browser.close()

    if not found:
        print("\nNo JSON endpoints found with job data.")
        print("The app may use a different mechanism (SSE, inline HTML data, etc.)")
    else:
        print(f"\n--- Summary: found {len(found)} JSON endpoint(s) ---")
        for url in found:
            print(f"  {url}")


asyncio.run(main())
