"""Tests for GreenhouseSlugCrawler — hits the real public API, no auth needed."""

import pytest
from maxisight.crawler.greenhouse import GreenhouseSlugCrawler
from maxisight.models import Job


@pytest.mark.asyncio
async def test_fetch_returns_jobs():
    crawler = GreenhouseSlugCrawler()
    jobs = await crawler.fetch("stripe")
    assert len(jobs) > 0, "Expected at least one job for Stripe"


@pytest.mark.asyncio
async def test_fetch_job_fields():
    crawler = GreenhouseSlugCrawler()
    jobs = await crawler.fetch("stripe")
    job = jobs[0]

    assert isinstance(job, Job)
    assert job.id.startswith("greenhouse_stripe_")
    assert job.source == "greenhouse"
    assert job.company_slug == "stripe"
    assert job.title != ""
    assert job.url.startswith("http")


@pytest.mark.asyncio
async def test_fetch_invalid_slug_raises():
    from maxisight.errors import CrawlerError
    crawler = GreenhouseSlugCrawler()
    with pytest.raises(CrawlerError):
        await crawler.fetch("this-company-does-not-exist-xyz-123")
