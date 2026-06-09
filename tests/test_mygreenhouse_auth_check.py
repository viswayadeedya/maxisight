"""Tests whether my.greenhouse.io/jobs requires login.

Run this test to answer the most critical open question:
Does MyGreenhouse need auth or can we hit it directly with httpx?
"""

import json
import re
from pathlib import Path

import httpx
import pytest

from maxisight._consts import MY_GREENHOUSE_URL, SESSION_DIR, USER_AGENT


@pytest.mark.asyncio
async def test_mygreenhouse_without_auth():
    """Hits my.greenhouse.io with no cookies. Prints exactly what we get back."""
    params = {
        "query": "Software Engineer",
        "date_posted": "past_24_hours",
        "page": 1,
    }
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(MY_GREENHOUSE_URL, params=params, headers=headers)

    print(f"\nStatus: {response.status_code}")
    print(f"Final URL: {response.url}")
    print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
    print(f"Body preview: {response.text[:500]}")

    # This test always passes — it's a diagnostic. Read the output above.
    assert response.status_code in (200, 302, 401, 403), (
        f"Unexpected status {response.status_code}"
    )

    if response.status_code == 200 and "application/json" in response.headers.get("content-type", ""):
        data = response.json()
        props = data.get("props", {})
        jobs = props.get("jobPosts", [])
        print(f"\nRESULT: No auth needed. Got {len(jobs)} jobs on page 1.")
    elif "sign_in" in str(response.url) or response.status_code in (401, 403):
        print("\nRESULT: Auth required. Run 'maxisight auth greenhouse' first.")
    else:
        print("\nRESULT: Got HTML (not JSON). MyGreenhouse may serve JSON via XHR only.")


@pytest.mark.asyncio
async def test_mygreenhouse_next_data_structure():
    """Hits my.greenhouse.io with real cookies and prints the __NEXT_DATA__ key structure.

    Run this after 'maxisight auth greenhouse' to confirm the exact JSON path for jobPosts.
    """
    session_file = Path(SESSION_DIR) / "greenhouse.json"
    if not session_file.exists():
        pytest.skip("No greenhouse session. Run 'maxisight auth greenhouse' first.")

    session = json.loads(session_file.read_text())
    cookies = {c["name"]: c["value"] for c in session["cookies"]}

    params = {"query": "Software Engineer", "date_posted": "past_24_hours", "page": 1}
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(MY_GREENHOUSE_URL, params=params, headers=headers, cookies=cookies, timeout=30.0)

    print(f"\nStatus: {response.status_code}")
    print(f"Final URL: {response.url}")
    print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")

    if "sign_in" in str(response.url) or response.status_code in (401, 403):
        pytest.skip("Session expired. Run 'maxisight auth greenhouse' to re-authenticate.")

    html = response.text
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)

    if not match:
        print(f"\n[DIAGNOSTIC] __NEXT_DATA__ NOT found. HTML preview:\n{html[:500]}")
        pytest.fail("Could not find __NEXT_DATA__ in the response HTML.")

    next_data = json.loads(match.group(1))
    page_props = next_data.get("props", {}).get("pageProps", {})
    nested_props = page_props.get("props", {})

    print(f"\n[DIAGNOSTIC] pageProps keys: {list(page_props.keys())}")
    if nested_props:
        print(f"[DIAGNOSTIC] pageProps.props keys: {list(nested_props.keys())}")

    direct_jobs = page_props.get("jobPosts", [])
    nested_jobs = nested_props.get("jobPosts", [])
    print(f"\n[DIAGNOSTIC] Jobs at pageProps.jobPosts: {len(direct_jobs)}")
    print(f"[DIAGNOSTIC] Jobs at pageProps.props.jobPosts: {len(nested_jobs)}")

    assert response.status_code == 200
