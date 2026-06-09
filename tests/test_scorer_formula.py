"""Tests for the combined formula with known inputs."""
from datetime import datetime, timezone

import pytest

from maxisight.models import Job
from maxisight.scorer.profile import ScoringProfile
from maxisight.scorer.scorer import compute_score


def make_job(**kwargs):
    defaults = dict(
        id="test_001", source="greenhouse", company_slug="testco",
        company_name="TestCo", title="Software Engineer",
        location="San Francisco, CA", url="https://example.com/job/1",
        posted_at=datetime.now(timezone.utc).isoformat(),
        work_type="remote",
        description="Python FastAPI AWS microservices distributed systems",
        raw={},
    )
    defaults.update(kwargs)
    return Job(**defaults)


def make_profile(**kwargs):
    defaults = dict(
        target_titles=["software engineer", "backend engineer"],
        skill_weights={"python": 1.0, "fastapi": 1.0, "aws": 1.0},
    )
    defaults.update(kwargs)
    return ScoringProfile(**defaults)


def test_support_engineer_scores_zero():
    job = make_job(title="Support Engineer")
    result = compute_score(job, make_profile())
    assert result.score == 0.0
    assert result.title_score == 0.0


def test_blocklisted_company_scores_zero():
    job = make_job(company_name="Evil Corp")
    result = compute_score(job, make_profile(blocklist_companies=["Evil Corp"]))
    assert result.score == 0.0


def test_relevant_job_scores_above_threshold():
    job = make_job(title="Senior Software Engineer", work_type="remote")
    result = compute_score(job, make_profile())
    assert result.score >= 0.25


def test_watchlist_company_boosts_score():
    job_normal = make_job(company_name="Unknown Co")
    job_watch = make_job(company_name="Stripe")
    profile = make_profile(watchlist_companies=["Stripe"])
    assert compute_score(job_watch, profile).score > compute_score(job_normal, profile).score


def test_full_stack_developer_passes_threshold():
    """Developer synonym passes the filter — doesn't score identically to Engineer.
    T² amplification intentionally creates score differences by design."""
    job_dev = make_job(title="Full Stack Developer")
    profile = make_profile(target_titles=["full stack engineer", "software engineer"])
    result = compute_score(job_dev, profile)
    assert result.score >= profile.score_threshold
    assert result.title_score > 0  # keyword gate passed


def test_remote_scores_higher_than_in_person():
    job_remote = make_job(work_type="remote")
    job_office = make_job(work_type="in_person")
    profile = make_profile()
    assert compute_score(job_remote, profile).score > compute_score(job_office, profile).score


def test_scored_job_has_all_components():
    result = compute_score(make_job(), make_profile())
    assert 0.0 <= result.title_score <= 1.0
    assert 0.0 <= result.seniority_score <= 1.0
    assert 0.0 <= result.freshness_score <= 1.0
    assert result.company_score in (0.0, 1.0, 1.2)
    assert result.location_score in (0.7, 1.0)
    assert 0.0 <= result.description_score <= 1.0
