"""Unit tests for each signal function. Fast. No network. No files."""
from datetime import datetime, timedelta, timezone

import pytest

from maxisight.scorer.profile import ScoringProfile
from maxisight.scorer.scorer import (
    has_blocklist_keyword,
    score_company,
    score_description,
    score_freshness,
    score_location,
    score_seniority,
    score_title,
)


def make_profile(**kwargs):
    defaults = dict(
        target_titles=[
            "software engineer",
            "backend engineer",
            "full stack engineer",
            "senior software engineer",
        ]
    )
    defaults.update(kwargs)
    return ScoringProfile(**defaults)


# ── Title ─────────────────────────────────────────────────────────────────────

def test_title_exact_match():
    assert score_title("Software Engineer", make_profile()) >= 0.95

def test_title_senior_variant():
    assert score_title("Senior Backend Engineer", make_profile()) >= 0.80

def test_title_developer_synonym():
    assert score_title("Full Stack Developer", make_profile()) >= 0.70

def test_title_support_engineer_killed():
    assert score_title("Support Engineer", make_profile()) == 0.0

def test_title_matlab_engineer_killed():
    assert score_title("MATLAB Engineer", make_profile()) == 0.0

def test_title_implementation_engineer_killed():
    assert score_title("Implementation Engineer", make_profile()) == 0.0

def test_title_unrelated_role_killed():
    assert score_title("Marketing Manager", make_profile()) == 0.0

def test_title_support_engineer_passes_if_targeted():
    p = make_profile(target_titles=["support engineer", "technical support engineer"])
    assert score_title("Support Engineer", p) >= 0.90


# ── Seniority ─────────────────────────────────────────────────────────────────

def test_seniority_match():
    assert score_seniority("Senior Software Engineer", "senior") == 1.0

def test_seniority_junior_penalized_for_senior_user():
    s = score_seniority("Junior Software Engineer", "senior")
    assert 0.3 <= s <= 0.5

def test_seniority_never_zero():
    assert score_seniority("Junior Software Engineer", "senior") > 0

def test_seniority_mid_open_to_all():
    assert score_seniority("Junior Software Engineer", "mid") == 1.0
    assert score_seniority("Staff Engineer", "mid") == 1.0


# ── Freshness ─────────────────────────────────────────────────────────────────

def test_freshness_just_posted():
    assert score_freshness(datetime.now(timezone.utc), 24.0) >= 0.99

def test_freshness_halflife():
    posted = datetime.now(timezone.utc) - timedelta(hours=24)
    s = score_freshness(posted, 24.0)
    assert 0.48 <= s <= 0.52  # should be ~0.5 at halflife

def test_freshness_never_zero():
    old = datetime.now(timezone.utc) - timedelta(hours=500)
    assert score_freshness(old, 24.0) > 0  # floor prevents exact zero


# ── Company ───────────────────────────────────────────────────────────────────

def test_company_blocklist_zeroes():
    p = make_profile(blocklist_companies=["Evil Corp"])
    assert score_company("Evil Corp", p) == 0.0

def test_company_watchlist_boosts():
    p = make_profile(watchlist_companies=["Stripe"])
    assert score_company("Stripe", p) == 1.2

def test_company_neutral():
    assert score_company("Unknown Startup", make_profile()) == 1.0


# ── Location ──────────────────────────────────────────────────────────────────

def test_location_remote():
    assert score_location("remote") == 1.0

def test_location_hybrid():
    assert score_location("hybrid") == 1.0

def test_location_in_person_penalized_not_zero():
    assert score_location("in_person") == 0.7

def test_location_unknown_neutral():
    assert score_location(None) == 1.0


# ── Description ───────────────────────────────────────────────────────────────

def test_description_empty_neutral():
    assert score_description("", {"python": 1.0}) == 0.5

def test_description_skill_match():
    desc = "We need a Python developer with FastAPI and PostgreSQL experience"
    weights = {"python": 1.0, "fastapi": 1.0, "postgresql": 1.0}
    assert score_description(desc, weights) >= 0.8

def test_description_no_match():
    desc = "Excel spreadsheet analyst PowerPoint marketing campaigns"
    weights = {"python": 1.0, "fastapi": 1.0, "langgraph": 1.0}
    assert score_description(desc, weights) < 0.1

def test_description_partial_match():
    desc = "Python backend engineer with AWS experience"
    weights = {"python": 1.0, "fastapi": 1.0, "aws": 1.0, "react": 1.0}
    score = score_description(desc, weights)
    assert 0.2 < score < 0.8


# ── Blocklist keywords ────────────────────────────────────────────────────────

def test_blocklist_clearance_detected():
    from maxisight.models import Job
    job = Job(
        id="test_001", source="greenhouse", company_slug="test",
        company_name="Test", title="Software Engineer",
        location="VA", url="https://test.com",
        posted_at=datetime.now(timezone.utc).isoformat(),
        work_type="in_person", raw={"content": "requires ts/sci clearance and polygraph"},
    )
    assert has_blocklist_keyword(job, ["ts/sci", "polygraph"]) is True

def test_blocklist_clean_job_passes():
    from maxisight.models import Job
    job = Job(
        id="test_002", source="greenhouse", company_slug="test",
        company_name="Test", title="Software Engineer",
        location="NY", url="https://test.com",
        posted_at=datetime.now(timezone.utc).isoformat(),
        work_type="remote", raw={"content": "Python FastAPI AWS microservices"},
    )
    assert has_blocklist_keyword(job, ["ts/sci", "polygraph"]) is False
