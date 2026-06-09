import asyncio
import html
import re
from urllib.parse import parse_qs, urlparse

import httpx

from maxisight._consts import GREENHOUSE_API_BASE, USER_AGENT
from maxisight.models import Job


def _strip_html(raw: str) -> str:
    unescaped = html.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", unescaped)
    return " ".join(text.split())


def _parse_url(public_url: str) -> tuple[str | None, str | None]:
    """Return (slug, job_id) for any Greenhouse-powered URL.

    Strategy 1 — standard greenhouse subdomain:
        job-boards.greenhouse.io, job-boards.eu.greenhouse.io, boards.greenhouse.io
    Strategy 2 — custom domain with board= + gh_jid= query params
    Strategy 3 — custom domain with gh_jid= only (slug requires HTML fetch)
        returns (None, job_id) as signal to caller
    Returns (None, None) if URL cannot be enriched.
    """
    # Strategy 1
    match = re.search(
        r"(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/([^/?]+)/jobs/(\d+)",
        public_url,
    )
    if match:
        return match.group(1), match.group(2)

    # Strategy 2 + 3
    params = parse_qs(urlparse(public_url).query)
    slug = (params.get("board") or [None])[0]
    job_id = (params.get("gh_jid") or [None])[0]

    if job_id:
        return slug, job_id  # slug may be None (Strategy 3)

    return None, None


async def _fetch_slug_from_html(url: str, client: httpx.AsyncClient) -> str | None:
    """Fetch a custom career page and extract the Greenhouse board slug from the embed script."""
    try:
        r = await client.get(url, timeout=15.0)
        match = re.search(
            r"boards\.greenhouse\.io/embed/[^?]+\?for=([^&\"'\s>]+)", r.text
        )
        return match.group(1) if match else None
    except Exception:
        return None


class GreenhouseEnricher:
    """Fetches full job descriptions from the Greenhouse boards API.

    Covers all Greenhouse URL patterns — standard subdomains, EU subdomain,
    custom career domains with board/gh_jid params, and custom domains requiring
    an HTML slug extraction step.
    """

    def __init__(self, user_agent: str = USER_AGENT) -> None:
        self._user_agent = user_agent

    async def enrich(self, jobs: list[Job], limit: int | None = None) -> list[Job]:
        targets = jobs[:limit] if limit else jobs
        enriched = 0
        skipped = 0

        async with httpx.AsyncClient(
            headers={"User-Agent": self._user_agent},
            follow_redirects=True,
        ) as client:
            for i, job in enumerate(targets, 1):
                slug, job_id = _parse_url(job.url)

                if not job_id:
                    skipped += 1
                    continue

                if slug is None:
                    # Strategy 3: fetch HTML to find slug
                    slug = await _fetch_slug_from_html(job.url, client)
                    await asyncio.sleep(0.5)
                    if not slug:
                        skipped += 1
                        if i % 50 == 0 or i == len(targets):
                            print(f"  Progress: {i}/{len(targets)} — enriched {enriched}, skipped {skipped}")
                        continue

                api_url = f"{GREENHOUSE_API_BASE}/{slug}/jobs/{job_id}?content=true"
                try:
                    r = await client.get(api_url, timeout=15.0)
                    if r.status_code == 200:
                        raw_content = r.json().get("content") or ""
                        job.description = _strip_html(raw_content) if raw_content else None
                        enriched += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1

                if i % 50 == 0 or i == len(targets):
                    print(f"  Progress: {i}/{len(targets)} — enriched {enriched}, skipped {skipped}")

                if i < len(targets):
                    await asyncio.sleep(0.5)

        return jobs

    def enrich_sync(self, jobs: list[Job], limit: int | None = None) -> list[Job]:
        return asyncio.run(self.enrich(jobs, limit))
