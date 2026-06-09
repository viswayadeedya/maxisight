from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class Job(BaseModel):
    id: str
    source: str
    company_slug: str
    title: str
    location: str | None = None
    url: str
    posted_at: str | None = None
    description: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    company_name: str | None = None
    work_type: str | None = None
    raw: dict


class ScoredJob(BaseModel):
    job: Job
    score: float
    title_score: float
    seniority_score: float
    freshness_score: float
    company_score: float
    location_score: float
    description_score: float
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobOutcome(BaseModel):
    job_id: str
    company_name: str
    job_title: str
    score_at_apply: float
    applied_at: datetime
    outcome: Literal["interview", "rejected", "ghosted", "offer", "withdrew"]
    days_to_response: int | None = None
    notes: str = ""
