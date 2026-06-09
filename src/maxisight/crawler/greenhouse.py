import asyncio
import html
import json
import re
from pathlib import Path

import httpx

from maxisight._consts import GREENHOUSE_API_BASE, MY_GREENHOUSE_URL, SESSION_DIR, USER_AGENT
from maxisight.auth.greenhouse import GreenhouseAuth
from maxisight.errors import AuthError, CrawlerError
from maxisight.models import Job


class GreenhouseSlugCrawler:
    """Fallback crawler for companies not opted into MyGreenhouse.

    Uses the per-company public API: boards-api.greenhouse.io/v1/boards/{slug}/jobs
    """

    def __init__(self, user_agent: str = USER_AGENT) -> None:
        self._user_agent = user_agent

    async def fetch(self, company_slug: str) -> list[Job]:
        url = f"{GREENHOUSE_API_BASE}/{company_slug}/jobs?content=true"
        headers = {"User-Agent": self._user_agent}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise CrawlerError(
                    f"Greenhouse API returned {e.response.status_code} for '{company_slug}'"
                ) from e
            except httpx.RequestError as e:
                raise CrawlerError(
                    f"Failed to reach Greenhouse API for '{company_slug}': {e}"
                ) from e

        data = response.json()
        raw_jobs = data.get("jobs", [])
        return [self._normalize(company_slug, job) for job in raw_jobs]

    def _normalize(self, company_slug: str, raw: dict) -> Job:
        job_id = str(raw.get("id", ""))
        location = raw.get("location", {})
        location_name = location.get("name") if isinstance(location, dict) else None

        return Job(
            id=f"greenhouse_{company_slug}_{job_id}",
            source="greenhouse",
            company_slug=company_slug,
            title=raw.get("title", ""),
            location=location_name,
            url=raw.get("absolute_url", ""),
            posted_at=raw.get("updated_at"),
            description=raw.get("content"),
            raw=raw,
        )

    def fetch_sync(self, company_slug: str) -> list[Job]:
        return asyncio.run(self.fetch(company_slug))


class MyGreenhouseCrawler:
    """Cross-company crawler using my.greenhouse.io search.

    Requires a saved Greenhouse session (run 'maxisight auth greenhouse' first).
    One paginated search covers all opted-in companies — no slug list needed.
    """

    def __init__(self, session_dir: Path = Path(SESSION_DIR), user_agent: str = USER_AGENT) -> None:
        self._auth = GreenhouseAuth(session_dir=session_dir)
        self._user_agent = user_agent

    async def fetch(
        self,
        query: str,
        date_posted: str = "past_24_hours",
        work_types: list[str] | None = None,
        employment_types: list[str] | None = None,
        location: str | None = "United States",
        lat: float | None = 39.71614,
        lon: float | None = -96.999246,
        location_type: str | None = "country",
        country_short_name: str | None = "US",
    ) -> list[Job]:
        cookies = self._auth.load_cookies()
        httpx_cookies = {c["name"]: c["value"] for c in cookies}

        if work_types is None:
            work_types = ["remote", "hybrid", "in_person"]
        if employment_types is None:
            employment_types = ["full_time"]

        all_jobs: list[Job] = []
        page = 1

        # my.greenhouse.io uses Inertia.js.
        # Step 1: plain GET to extract the Inertia version from the HTML data-page attribute.
        # Step 2: all search requests (pages 1+) as Inertia XHR to get JSON directly.
        csrf_token = httpx_cookies.get("MYGREENHOUSE-XSRF-TOKEN", "")

        async with httpx.AsyncClient(
            headers={
                "User-Agent": self._user_agent,
                "Accept": "text/html, application/xhtml+xml, */*",
            },
            cookies=httpx_cookies,
            follow_redirects=True,
        ) as client:
            # Step 1 — get Inertia version from the HTML shell (no search params)
            try:
                init = await client.get(MY_GREENHOUSE_URL, timeout=30.0)
            except httpx.RequestError as e:
                raise CrawlerError(f"Failed to reach MyGreenhouse: {e}") from e

            if "sign_in" in str(init.url) or init.status_code == 401:
                raise AuthError(
                    "Greenhouse session expired. Run 'maxisight auth greenhouse' to re-authenticate."
                )

            if init.status_code != 200:
                raise CrawlerError(f"MyGreenhouse returned {init.status_code} loading session")

            dp_match = re.search(r'data-page="([^"]+)"', init.text)
            if not dp_match:
                raise CrawlerError("Could not find Inertia data-page in MyGreenhouse HTML")

            try:
                inertia_version = json.loads(html.unescape(dp_match.group(1))).get("version", "")
            except (ValueError, json.JSONDecodeError) as e:
                raise CrawlerError(f"Failed to parse Inertia version: {e}") from e

            # Step 2 — all search pages as Inertia XHR.
            # Partial-Data/Partial-Component tell Inertia to load deferred props (jobPosts).
            inertia_headers = {
                "X-Inertia": "true",
                "X-Inertia-Version": inertia_version,
                "X-CSRF-Token": csrf_token,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "text/html, application/xhtml+xml",
                "Referer": MY_GREENHOUSE_URL,
                "X-Inertia-Partial-Component": "job_search",
                "X-Inertia-Partial-Data": "browsing,page,moreResultsAvailable,jobPosts",
            }

            while True:
                params: dict = {
                    "query": query,
                    "date_posted": date_posted,
                    "work_type[]": work_types,
                    "employment_type[]": employment_types,
                    "page": page,
                }
                if location:
                    params["location"] = location
                    params["lat"] = lat
                    params["lon"] = lon
                    params["location_type"] = location_type
                    params["country_short_name"] = country_short_name

                try:
                    response = await client.get(
                        MY_GREENHOUSE_URL, params=params, headers=inertia_headers, timeout=30.0
                    )
                except httpx.RequestError as e:
                    raise CrawlerError(f"Failed to reach MyGreenhouse: {e}") from e

                if "sign_in" in str(response.url) or response.status_code == 401:
                    raise AuthError(
                        "Greenhouse session expired. Run 'maxisight auth greenhouse' to re-authenticate."
                    )

                if response.status_code == 429:
                    break  # rate limited — save what we have
                if response.status_code != 200:
                    raise CrawlerError(
                        f"MyGreenhouse returned {response.status_code} on page {page}"
                    )

                try:
                    data = response.json()
                    props = data["props"]
                    raw_jobs = props["jobPosts"]
                except (KeyError, ValueError, json.JSONDecodeError) as e:
                    raise CrawlerError(
                        f"Unexpected MyGreenhouse response format on page {page}: {e}"
                    ) from e

                all_jobs.extend(self._normalize(job) for job in raw_jobs)

                if not props.get("moreResultsAvailable", False):
                    break

                page += 1
                await asyncio.sleep(1.0)

        return all_jobs

    def _normalize(self, raw: dict) -> Job:
        job_id = str(raw.get("id", ""))
        locations = raw.get("locations", [])
        location_name = locations[0] if locations else None

        pay_ranges = raw.get("payRanges") or []
        first_range = pay_ranges[0] if pay_ranges else None
        salary_min = first_range.get("min") if isinstance(first_range, dict) else None
        salary_max = first_range.get("max") if isinstance(first_range, dict) else None

        url = raw.get("publicUrl", "")
        # Extract company slug from publicUrl: https://job-boards.greenhouse.io/{slug}/jobs/{id}
        company_slug = ""
        if "greenhouse.io/" in url:
            parts = url.split("greenhouse.io/")
            if len(parts) > 1:
                company_slug = parts[1].split("/")[0]

        return Job(
            id=f"mygreenhouse_{job_id}",
            source="mygreenhouse",
            company_slug=company_slug,
            company_name=raw.get("companyName"),
            title=raw.get("title", ""),
            location=location_name,
            url=url,
            posted_at=raw.get("firstPublished"),
            work_type=raw.get("workType"),
            salary_min=salary_min,
            salary_max=salary_max,
            raw=raw,
        )

    def fetch_sync(
        self,
        query: str,
        date_posted: str = "past_24_hours",
        work_types: list[str] | None = None,
        employment_types: list[str] | None = None,
        location: str | None = "United States",
        lat: float | None = 39.71614,
        lon: float | None = -96.999246,
        location_type: str | None = "country",
        country_short_name: str | None = "US",
    ) -> list[Job]:
        return asyncio.run(self.fetch(
            query, date_posted, work_types, employment_types,
            location, lat, lon, location_type, country_short_name,
        ))
