---
name: project-architecture
description: Maxisight tech stack, crawler strategy, MyGreenhouse discovery, key technical decisions
metadata:
  type: project
---

**Stack:** Python 3.10+, uv, Typer + Rich (CLI), httpx (HTTP), Pydantic (models), Playwright (auth), Crawlee Python v1.3.0 (future: ParselCrawler / PlaywrightCrawler / AdaptivePlaywrightCrawler), LangGraph + Claude API + OpenAI (Phase 2 matcher), SendGrid (outreach).

**File structure follows domain modules, NOT Crawlee's internal framework structure:**
```
src/maxisight/
  _cli.py, models.py, config.py, errors.py, _consts.py
  crawler/   enricher/   scorer/   matcher/   applicator/   outreach/   auth/   storage/

storage/
  sessions/greenhouse.json          ← saved login cookies
  datasets/mygreenhouse/*.json      ← raw crawl output
  datasets/mygreenhouse/enriched_*  ← enriched with descriptions
  datasets/scored/*.json            ← scorer shortlist output
  profiles/default.json             ← user's scoring config (edit this manually)
  profiles/resume.txt               ← resume text (placeholder for Phase 2)
```

**MyGreenhouse discovery (June 2, 2026 — CRITICAL):**
- `my.greenhouse.io/jobs` is Greenhouse's own candidate portal — cross-company search
- Covers all 7,500+ opted-in companies. One paginated search, no slug list needed.
- Requires login. Auth: Playwright headed browser saves cookies once; httpx reuses for all searches.
- Per-slug API (`boards-api.greenhouse.io/v1/boards/{slug}/jobs`) kept as fallback for non-opted companies.

**MyGreenhouse tech stack (June 5, 2026 — confirmed by reverse engineering):**
- Built with **Rails + Inertia.js + React** — NOT Next.js, NOT a REST API
- `my.greenhouse.io/jobs` returns HTML to plain requests. JSON only comes via Inertia XHR.
- Sending `Accept: application/json` returns **406**. Must use `Accept: text/html, application/xhtml+xml`.
- Full working approach documented in `docs/mygreenhouse-inertia-reverse-engineering.md`

**Inertia.js fetch flow (two steps):**
1. Plain GET `my.greenhouse.io/jobs` → parse `data-page` HTML attribute → extract `version` hash
2. All search pages: GET with Inertia XHR headers:
   - `X-Inertia: true`
   - `X-Inertia-Version: <from step 1>`
   - `X-Inertia-Partial-Component: job_search`
   - `X-Inertia-Partial-Data: browsing,page,moreResultsAvailable,jobPosts`
   - `X-CSRF-Token: <value of MYGREENHOUSE-XSRF-TOKEN cookie>`
   - `X-Requested-With: XMLHttpRequest`

**JSON field types (confirmed from live data):**
- `locations` — list of **strings** (e.g. `["San Francisco, CA"]`), NOT list of dicts
- `payRanges` — null or a **string** (e.g. `"$186,200 - $223,400"`), NOT a dict with min/max
- `props.jobPosts[]` with `id`, `title`, `companyName`, `publicUrl`, `firstPublished`, `workType`, `payRanges`, `locations`, `moreResultsAvailable`
- URL params: `query`, `date_posted` (past_hour/past_24_hours/past_week/past_month), `work_type[]`, `employment_type[]`, `page`

**Location filtering (confirmed June 5, 2026 — from DevTools inspection):**
- Default: US only. Params hardcoded from what Greenhouse sends when you type "United States":
  - `location=United States`, `lat=39.71614`, `lon=-96.999246`, `location_type=country`, `country_short_name=US`
- CLI: `--worldwide` flag removes location filter for global results
- Location is resolved via Pelias geocoding API (`api-geocode-earth-proxy.greenhouse.io`) — lat/lon hardcoded per country, no live geocoding needed for common cases

**Rate limiting:** 429 hits around page 28-30 at 1 req/sec. On 429: stop and save what we have. Sleep 1s between pages.

**Enricher — Greenhouse URL patterns (June 6, 2026):**
`GreenhouseEnricher` in `src/maxisight/enricher/greenhouse.py` uses three strategies:

| Strategy | Pattern | Count in dataset | How to resolve |
|---|---|---|---|
| 1 | `(job-boards|boards)(.eu)?.greenhouse.io/{slug}/jobs/{id}` | 3,240 | Extract from URL path |
| 2 | Custom domain + `?board=SLUG&gh_jid=ID` | 32 | Extract from query params |
| 3 | Custom domain + `?gh_jid=ID` only | 1,222 | Fetch page HTML, extract `for=SLUG` from Greenhouse embed script |

Strategy 3 confirmed: `boards.greenhouse.io/embed/job_board/js?for=nexhealth` found in HTML.
Test result: 17/20 enriched (3 skipped — custom pages that don't embed Greenhouse script detectably).

**Pipeline architecture (agreed June 6):**
```
crawl  → job cards (title, company, url, salary, location)
enrich → full job description added per job (boards API, free)
match  → rubric-based scorer (rules, free, instant) → qualified/ + rejections/
apply  → LLM tailors resume per qualified job (small volume, paid)
```

**Matcher design decision — rubric-based, NOT LLM per job:**
- Profile/config defines rules once: required skills, seniority, salary min, work type
- Matcher applies rules deterministically — free, fast, always explainable
- Rejection reason always explicit ("requires Go, not in your skills")
- LLM only for resume tailoring on final qualified set (~10-20 jobs)
- Cost: LLM per application × 10-20, NOT LLM per job × 4,000
- Rejection data saved with reason → feeds back into rubric refinement over time

**Rejection data schema:**
- `storage/datasets/qualified/` — jobs that passed matching
- `storage/datasets/rejections/` — jobs that failed + rejection reason + resume_version

**Scorer package (`src/maxisight/scorer/`) — built June 6:**

Formula: `Score = T² × (S + F + C + L + D) / 5`

| Signal | What it measures | Hard zero? |
|---|---|---|
| T — Title | Keyword gate + fuzzy match vs target_titles | Yes — unrelated roles score 0 |
| S — Seniority | Soft penalty for level mismatch | No — 0.4 minimum |
| F — Freshness | `2^(-hours/halflife)`, = 0.5 at halflife | No — floor at 1e-6 |
| C — Company | Blocklist=0, watchlist=1.2, neutral=1.0 | Yes — if blocklisted |
| L — Location | remote/hybrid=1.0, in_person=0.7 | No |
| D — Description | Weighted skill matching vs skill_weights dict | No — 0.5 if no description |

**Title keyword gate (how Support Engineer is eliminated):**
- Extracts meaningful words from `target_titles` (strips generic words: engineer, developer, senior...)
- If job title shares ZERO of these keywords → T=0.0 → score=0.0
- No hardcoded blocklist — controlled entirely by user's `target_titles`
- "Support Engineer" has no overlap with ["software", "backend", "platform", "full", "stack"] → killed

**Scoring profile (`storage/profiles/default.json`):**
- User edits this JSON file manually — Phase 1 (developer audience)
- Fields: `target_titles` (list), `skill_weights` (dict of skill→weight 0-1), `level`, `freshness_halflife_hours`, `score_threshold`, `top_n`, `blocklist_companies`, `watchlist_companies`, `blocklist_keywords`
- **Profile must match the crawl query.** If you crawl "Data Analyst" but profile targets "software engineer", data analyst jobs all score 0.
- Different roles = different profile file. CLI: `--profile storage/profiles/data_analyst.json`
- Phase 2 hosted product: resume upload → Claude parses → auto-populates this profile. Same scorer underneath, no code change.

**Skill weights design (why NOT TF-IDF):**
- TF-IDF penalizes common words — "Python" is so common in job postings it'd get LOW weight
- Weighted matching means ONLY the user's skills matter, regardless of market frequency
- Weights in JSON not Python — user tunes them, community can submit PRs for different roles

**D signal flaw identified (June 8, 2026) — PLAN TO FIX:**

Current formula: `D = matched_weight / sum(ALL weights)` — denominator = 27.8

Problem: no real job post will ever list all 35 skills. A job listing python + fastapi + aws + react scores only D=0.14. That's recall-oriented scoring against an impossible ceiling. The signal is compressed into the bottom 20% of its range by design. Rated 4/10.

Root cause: the denominator assumes a "perfect job" mentions every skill you know. Reality: a great job mentions 6-10 skills.

Planned fix — **Top-K normalization:**
- Divide matched weight by sum of **top-K weights** instead of all weights
- K represents "what a great job realistically lists" — proposed default K=8
- New denominator (K=8, all top-8 are weight 1.0): 8.0 instead of 27.8
- Same 4-skill job: D = 4.0/8.0 = 0.50 — honest and meaningful
- A job matching all 8 top skills: D = 8.0/8.0 = 1.0 (capped with min(1.0, ...))
- K configurable in `default.json` as `skill_top_k: 8`
- This is precision-oriented: rewards skills found, doesn't punish for skills not listed
- Not yet implemented — implement before Phase 2 resume parsing

**Applicator philosophy (ApplyPilot lesson):**
- Type 1 fields (name, email, resume upload): deterministic Playwright, zero LLM cost
- Type 2 fields (open-ended questions): StagehandCrawler fallback ONLY
- Story bank (Phase 6): interview user once, capture 20-30 real stories, MATCH don't generate

**ATS priority:** MyGreenhouse (primary) → Lever → Ashby → ParselCrawler (static) → PlaywrightCrawler (JS) → AdaptivePlaywrightCrawler (unknown)

**Rules:** robots.txt always on. maxConcurrency: 2-3. Unique job ID = source + job_id. Never job title alone.
