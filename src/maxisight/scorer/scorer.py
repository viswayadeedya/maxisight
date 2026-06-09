import math
from datetime import datetime, timezone

from rapidfuzz import fuzz

from maxisight.models import Job, ScoredJob
from maxisight.scorer.profile import ScoringProfile


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_posted_at(posted_at: str | None) -> datetime | None:
    """Parse ISO 8601 string to datetime. Returns None on failure."""
    if not posted_at:
        return None
    try:
        return datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
    except ValueError:
        return None


# ── Signal 1: Title (T) ───────────────────────────────────────────────────────

def score_title(job_title: str, profile: ScoringProfile) -> float:
    """
    Two-step title scoring.

    Step 1 — Keyword gate (hard filter):
      Extract meaningful keywords from user's target_titles.
      If job title shares ZERO meaningful keywords → return 0.0.
      Kills: "Support Engineer", "MATLAB Engineer", "Implementation Engineer"
      without a hardcoded blocklist. User controls this via target_titles.

    Step 2 — Fuzzy match (soft score):
      Only runs if keyword gate passes.
      Handles synonyms: "Developer" ≈ "Engineer", "Full Stack" variants.
    """
    SYNONYMS = {
        "developer": "engineer",
        "programmer": "engineer",
        "fullstack": "full",
        "full-stack": "full",
    }
    title_words = set(job_title.lower().split())
    normalized_words = {SYNONYMS.get(w, w) for w in title_words}
    target_keywords = profile.extract_title_keywords()

    if not (normalized_words & target_keywords):
        return 0.0

    return max(
        fuzz.token_sort_ratio(job_title.lower(), t.lower()) / 100
        for t in profile.target_titles
    )


# ── Signal 2: Seniority (S) ───────────────────────────────────────────────────

def score_seniority(job_title: str, user_level: str) -> float:
    """
    Soft penalty for seniority mismatch. Never hard zero.
    A junior title might have senior responsibilities — only penalize, never exclude.
    """
    title = job_title.lower()
    junior_signals = {"junior", "intern", "entry", "associate", "graduate",
                      "jr", "new grad", "early career"}
    senior_signals = {"senior", "staff", "principal", "lead", "sr",
                      "architect", "director"}

    if user_level == "senior":
        return 0.4 if any(w in title for w in junior_signals) else 1.0
    if user_level == "junior":
        return 0.4 if any(w in title for w in senior_signals) else 1.0
    return 1.0


# ── Signal 3: Freshness (F) ───────────────────────────────────────────────────

def score_freshness(posted_at: datetime, halflife_hours: float) -> float:
    """
    Exponential decay. Posted now = 1.0. At halflife = 0.5.
    Formula: e^(-hours_old / halflife). Never returns 0.
    """
    now = datetime.now(timezone.utc)
    hours_old = max((now - posted_at).total_seconds() / 3600, 0)
    # 2^(-t/halflife) so score = 0.5 exactly at t = halflife_hours
    raw = math.pow(2, -hours_old / halflife_hours)
    return max(round(raw, 6), 1e-6)  # floor prevents exact zero


# ── Signal 4: Company (C) ─────────────────────────────────────────────────────

def score_company(company_name: str, profile: ScoringProfile) -> float:
    """
    Blocklist = hard 0.0 (only hard zero from this signal).
    Watchlist = 1.2 boost.
    Unknown = 1.0 neutral.
    """
    name = (company_name or "").lower().strip()
    if name in [b.lower().strip() for b in profile.blocklist_companies]:
        return 0.0
    if name in [w.lower().strip() for w in profile.watchlist_companies]:
        return 1.2
    return 1.0


# ── Signal 5: Location (L) ────────────────────────────────────────────────────

def score_location(work_type: str | None) -> float:
    """
    Remote/hybrid = 1.0. In-person = 0.7 soft penalty.
    Never a hard filter — relocation is possible. Unknown = 1.0 neutral.
    """
    if work_type in ("remote", "hybrid"):
        return 1.0
    if work_type == "in_person":
        return 0.7
    return 1.0


# ── Signal 6: Description (D) ─────────────────────────────────────────────────

def score_description(job_description: str, skill_weights: dict[str, float]) -> float:
    """
    Weighted skill matching against job description.
    Returns 0.5 neutral if description is empty — missing data should not
    kill a job that passed title scoring.
    """
    if not job_description or not skill_weights:
        return 0.5

    desc = job_description.lower()
    max_possible = sum(skill_weights.values())
    if max_possible == 0:
        return 0.5

    total_weight = sum(
        weight for skill, weight in skill_weights.items() if skill in desc
    )
    return round(total_weight / max_possible, 4)


# ── Hard Filters ──────────────────────────────────────────────────────────────

def has_blocklist_keyword(job: Job, blocklist_keywords: list[str]) -> bool:
    """Check raw job text for hard blocklist keywords (visa, clearance, etc.)."""
    raw_text = ""
    if job.raw:
        raw_text = str(job.raw).lower()
    if job.description:
        raw_text += " " + job.description.lower()
    if job.title:
        raw_text += " " + job.title.lower()
    return any(kw.lower() in raw_text for kw in blocklist_keywords)


# ── Formula ───────────────────────────────────────────────────────────────────

def compute_score(job: Job, profile: ScoringProfile) -> ScoredJob:
    """
    Score = T² × (S + F + C + L + D) / 5

    T² amplifier:
      T=1.0 → multiplier 1.0  (full score)
      T=0.7 → multiplier 0.49 (meaningful penalty)
      T=0.0 → score 0.0       (eliminated: Support Engineer, MATLAB Engineer, etc.)
    """
    job_description = job.description or ""
    if not job_description and isinstance(job.raw, dict):
        job_description = job.raw.get("content", "") or job.raw.get("description", "") or ""

    T = score_title(job.title, profile)
    C = score_company(job.company_name or "", profile)

    if C == 0.0 or T == 0.0:
        return ScoredJob(
            job=job, score=0.0,
            title_score=T, seniority_score=0.0, freshness_score=0.0,
            company_score=C, location_score=0.0, description_score=0.0,
        )

    S = score_seniority(job.title, profile.level)
    parsed_dt = _parse_posted_at(job.posted_at)
    F = score_freshness(parsed_dt, profile.freshness_halflife_hours) if parsed_dt else 0.5
    L = score_location(job.work_type)
    D = score_description(job_description, profile.skill_weights)

    final_score = round(T ** 2 * (S + F + C + L + D) / 5, 4)

    return ScoredJob(
        job=job, score=final_score,
        title_score=T, seniority_score=S, freshness_score=F,
        company_score=C, location_score=L, description_score=D,
    )


# ── Batch Scorer ──────────────────────────────────────────────────────────────

def score_jobs(jobs: list[Job], profile: ScoringProfile) -> list[ScoredJob]:
    """
    Universal scorer. Works for jobs from ANY source.
    1. Hard filter: blocklist keywords
    2. Deduplicate by job ID
    3. Score each remaining job
    4. Filter by threshold
    5. Sort descending, return top N
    """
    seen_ids: set[str] = set()
    results: list[ScoredJob] = []

    for job in jobs:
        if job.id in seen_ids:
            continue
        seen_ids.add(job.id)

        if has_blocklist_keyword(job, profile.blocklist_keywords):
            continue

        scored = compute_score(job, profile)
        if scored.score >= profile.score_threshold:
            results.append(scored)

    results.sort(key=lambda x: x.score, reverse=True)
    return results[: profile.top_n]
