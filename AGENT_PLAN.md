# Maxisight — Project Memory File

> Last updated: June 2, 2026 — Day 2 (evening update)
> Owner: Viswa
> GitHub: github.com/viswayadeedya/maxisight (moves to github.com/maxisight org when ready)
> Domain: maxisight.app ($10/year — buy when Phase 1 code is working)
> PyPI: maxisight + maxisight[crawler] + maxisight[cli] + maxisight[all]
> CLI: pip install maxisight / maxisight init

---

## THE NAME — READ THIS FIRST

**Maxisight.**

A lot of people are broke, depressed, stressed, anxious. They can't see a way forward.
This tool gives them maximum sight — to look in a direction where there is hope.

That's not a feature. That's a mission.

The broke, depressed, anxious job seeker who has been rejected 50 times and can't see a way forward — Maxisight gives them the ability to see. Maximum sight. A direction. Hope.

This is the origin story. Remember it when you're debugging Playwright at 2am.

---

## THE VISION

This is NOT a personal job tool. This is **open source infrastructure** for job automation.

Like Crawlee is infrastructure for web scraping, Maxisight is infrastructure for job hunting.
Anyone can install it, use the packages they need, and build on top of it.

**The pain being solved:**

- People are paying $200-300/month for job tools that are just LLM prompts wrapped in a UI
- Influencers make videos about tools that don't work in real time — just for views
- ApplyPilot relies entirely on Claude Code CLI subprocess — 93% failure rate on apply
- No open source tool has Pipeline B (funded startup outreach)
- Broke, anxious job seekers deserve a free, honest, working tool

**The mission:** Free, honest, deterministic, composable job automation infrastructure.
**The business:** Open source framework (free) → hosted product on top (premium pricing for non-technical users)

---

## PRODUCT TYPE — CLI Tool

Terminal-first. Like Crawlee, Angular CLI, HyperFrames.

```bash
pip install maxisight
maxisight init
maxisight crawl --source greenhouse --companies companies.json
maxisight match --resume resume.pdf
maxisight apply --dry-run
maxisight outreach --pipeline funded-startups
```

Users install once, run commands, get results.
No UI needed for Phase 1.
No subscription. No paywall. Open source.

**Target user Phase 1:** Developers — comfortable with terminal, Python, API keys
**Target user Phase 2 (hosted product):** Non-technical job seekers — they pay premium, no terminal needed

---

## BUSINESS MODEL

**Layer 1 — Open source framework (free)**
CLI + packages on PyPI and GitHub. Developers use it free. Community grows it.
Builds reputation, stars, credibility, O-1 evidence.

**Layer 2 — Hosted product on top (paid, premium pricing)**
Non-technical users sign up, enter resume, set preferences, tool runs in cloud.
No terminal. No code. No setup. They pay for removal of friction.
Price is HIGH — not low. The value is a job, a career change, financial security.

**Pricing philosophy:**

- Technical users who can use LLMs to self-serve = free
- Users who can't or won't = premium price
- You're not charging for software — you're charging for removal of friction
- Myron Golden: paid in proportion to the problem you solve

**Model reference:** Crawlee (free) → Apify platform (paid). That's the exact playbook.

---

## COMPLETE PYTHON STACK

| Layer                    | Tool                                | Why                                                         |
| ------------------------ | ----------------------------------- | ----------------------------------------------------------- |
| Language                 | Python 3.10+                        | Everything in one language. No bridges.                     |
| Package manager          | uv                                  | Fast, modern, what Crawlee Python uses                      |
| CLI framework            | Typer                               | Wraps Click, type annotations define commands automatically |
| Interactive prompts      | Inquirer                            | Dropdowns, text input, confirmations for maxisight init     |
| Project scaffolding      | Cookiecutter                        | Generates project structure on maxisight init               |
| Terminal output          | Rich                                | Spinners, progress bars, colored output                     |
| HTTP client              | httpx                               | Async HTTP for MyGreenhouse API + Lever + Ashby             |
| Static page crawling     | ParselCrawler (Crawlee)             | CSS/XPath selectors, faster than BeautifulSoup              |
| JS-rendered crawling     | PlaywrightCrawler (Crawlee)         | Real browser, handles dynamic content                       |
| Unknown pages            | AdaptivePlaywrightCrawler (Crawlee) | Auto-switches HTTP↔browser, learns over time                |
| Form filling (known ATS) | Playwright (deterministic)          | Hardcoded selectors, zero LLM cost                          |
| Open-ended questions     | StagehandCrawler (Crawlee)          | AI fallback ONLY for Type 2 fields                          |
| LLM agent                | LangGraph                           | State machine for job scoring + resume tailoring            |
| LLM models               | Claude API + OpenAI                 | Scoring, tailoring, story matching                          |
| Email                    | SendGrid                            | Cold outreach delivery                                      |
| Scheduler                | Hetzner VPS + cron                  | Self-hosted, ~€5/month                                      |
| Backend (Layer 2 only)   | FastAPI                             | NOT in CLI — only in hosted product                         |

---

## PACKAGE ARCHITECTURE

Each package is independent. One package does not need to know how another works.
Only input and output contracts matter between packages.
End users use only the packages they need.
NO database in core packages — user decides what to do with output.
Storage is ./storage folder as JSON files — Crawlee's built-in file storage.

```
maxisight/
  packages/
    crawler/       → pulls jobs from ATS boards
    matcher/       → scores jobs against profile
    applicator/    → submits applications
    emailfinder/   → finds contact emails
    outreach/      → sends cold emails
  cli/             → command wiring only (Typer)
```

**pyproject.toml entry point:**

```toml
[project.scripts]
maxisight = "maxisight._cli:cli"

[project.optional-dependencies]
cli = ["typer", "inquirer", "cookiecutter", "rich"]
crawler = ["crawlee[playwright,parsel]", "httpx"]
matcher = ["langgraph", "anthropic", "openai"]
all = ["maxisight[cli,crawler,matcher]"]
```

**Unix philosophy:** each command pipes into the next. User decides persistence.

---

## GREENHOUSE CRAWLER — CRITICAL DISCOVERY (June 2, 2026)

### MyGreenhouse is the right approach — NOT per-company API calls

**The old approach (abandoned):**

- Call `boards-api.greenhouse.io/v1/boards/{slug}/jobs` per company
- Requires knowing company slugs upfront
- 7,500+ companies = 7,500 API calls
- No cross-company search possible

**The new approach (confirmed working):**

- Use `my.greenhouse.io` — Greenhouse's own candidate portal
- One search returns jobs across ALL opted-in companies simultaneously
- No slug list needed
- Built-in filters: date posted, work type, employment type, location, salary

### Greenhouse stats (verified June 2, 2026)

- Greenhouse official (March 2026): **7,500+ companies globally**
- ~5,700-6,000 US companies (77% US-based per 6Sense)
- MyGreenhouse search for "Software Engineer" returns **680+ results** across companies
- Coverage: all companies that have opted into MyGreenhouse

### MyGreenhouse JSON API — confirmed structure

Viswa discovered this by inspecting network requests. MyGreenhouse serves clean JSON:

```json
{
  "component": "job_search",
  "props": {
    "page": 3,
    "moreResultsAvailable": true,
    "jobPosts": [
      {
        "id": 5151565007,
        "title": "Senior Software Engineer",
        "companyName": "TransMarket Group",
        "logoUrl": "...",
        "publicUrl": "https://job-boards.greenhouse.io/transmarketgroup/jobs/5151565007",
        "firstPublished": "2026-06-02T15:18:06Z",
        "locations": [],
        "workType": "in_person",
        "payRanges": null,
        "viewed": false
      }
    ]
  }
}
```

**Key fields available:**

- `firstPublished` — exact ISO timestamp → enables 24-hour filter
- `title` — job title → enables role filter
- `companyName` — company name
- `publicUrl` — direct apply URL (includes company slug automatically)
- `workType` — remote/hybrid/in_person
- `payRanges` — salary if posted
- `moreResultsAvailable` — pagination signal
- `locations` — city/country

### MyGreenhouse URL structure (confirmed)

```
https://my.greenhouse.io/jobs
  ?query=Software%20Engineer
  &date_posted=past_hour          ← built-in time filter
  &work_type[]=remote
  &work_type[]=hybrid
  &work_type[]=in_person
  &employment_type[]=full_time
  &employment_type[]=contract
  &page=1
```

**date_posted options:** `past_hour`, `past_24_hours`, `past_week`, `past_month`

### MyGreenhouse filters available (confirmed from UI screenshot)

- Date posted dropdown ✅
- Salary dropdown ✅
- Work type dropdown ✅
- Employment type dropdown ✅
- Location field ✅

### Authentication status — NEEDS VERIFICATION

**TODO:** Test in incognito window whether `my.greenhouse.io/jobs` JSON is accessible without login.

- If public → no auth needed, pure httpx call
- If requires login → user logs in once via Playwright, session cookie saved, reused for all searches

### The Greenhouse fetcher code

```python
import httpx
from datetime import datetime, timezone

async def search_greenhouse_jobs(
    query: str = "Software Engineer",
    date_posted: str = "past_24_hours",
    work_types: list = ["remote", "hybrid", "in_person"],
    employment_types: list = ["full_time"]
) -> list[dict]:

    base_url = "https://my.greenhouse.io/jobs"
    all_jobs = []
    page = 1

    async with httpx.AsyncClient() as client:
        while True:
            params = {
                "query": query,
                "date_posted": date_posted,
                "work_type[]": work_types,
                "employment_type[]": employment_types,
                "page": page
            }

            response = await client.get(base_url, params=params)
            data = response.json()

            jobs = data["props"]["jobPosts"]
            all_jobs.extend(jobs)

            if not data["props"]["moreResultsAvailable"]:
                break

            page += 1

    return all_jobs
```

### Why MyGreenhouse beats per-slug API approach

|                       | Per-slug API                 | MyGreenhouse                       |
| --------------------- | ---------------------------- | ---------------------------------- |
| Company discovery     | Manual slug list needed      | Automatic — all opted-in companies |
| Cross-company search  | ❌ Not possible              | ✅ Native                          |
| Date filter           | Filter in Python after fetch | ✅ Built into URL params           |
| Role filter           | Filter in Python after fetch | ✅ Built into search query         |
| Number of API calls   | 1 per company (7,500+)       | 1 per page of results              |
| Slug list maintenance | Ongoing manual work          | ❌ Not needed                      |
| Auth required         | ❌ No                        | ⚠️ TBD — needs incognito test      |

### Still using per-slug API for

Companies NOT opted into MyGreenhouse. As a fallback only.
Per-slug endpoint: `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`

---

## ATS PRIORITY LIST

### Tier 1 — MyGreenhouse cross-company search (PRIMARY)

```
my.greenhouse.io/jobs?query=Software+Engineer&date_posted=past_24_hours
```

- Covers all MyGreenhouse opted-in companies (~7,500 globally)
- Returns structured JSON with firstPublished timestamp
- No slug list needed
- Auth status: TBD (test in incognito)

### Tier 1b — Per-company API fallback (for non-MyGreenhouse companies)

| ATS        | Endpoint                                                       | Notes                                        |
| ---------- | -------------------------------------------------------------- | -------------------------------------------- |
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | No rate limit. GET = no auth                 |
| Lever      | `api.lever.co/v0/postings/{company}?mode=json`                 | Crawl-delay: 1 second                        |
| Ashby      | `jobs.ashbyhq.com/api` (GraphQL)                               | Best salary data. `includeCompensation=true` |

### Tier 2 — API but more complex

Workable, SmartRecruiters, JazzHR, BambooHR

### Tier 3 — PlaywrightCrawler required (JS-rendered)

Workday, iCIMS, Pinpoint, Teamtailor, Breezy

---

## CRAWLER ARCHITECTURE

### Which crawler for which target:

```
MyGreenhouse search API          → plain httpx (JSON API, paginated)
Greenhouse per-slug fallback     → plain httpx
Lever / Ashby APIs               → plain httpx
Static career pages              → ParselCrawler
JS-rendered career pages         → PlaywrightCrawler
Unknown career pages (Pipeline B)→ AdaptivePlaywrightCrawler
Form submission (known ATS)      → Playwright deterministic
Open-ended questions (Type 2)    → StagehandCrawler (fallback only)
```

### Why StagehandCrawler is ONLY in applicator, not crawler:

StagehandCrawler is AI-powered browser automation. It uses LLMs (OpenAI/Anthropic/Google)
to understand pages via natural language. It does NOT belong in the crawler package.
It only lives in the applicator package, only triggered for Type 2 open-ended form fields.

---

## APPLICATOR ARCHITECTURE — CRITICAL DECISIONS

### Two types of form fields:

**Type 1 — Structured fields (deterministic, free, no LLM):**

- First name, last name, email, phone
- Resume PDF upload
- LinkedIn URL, location
- Known dropdowns (country, years of experience)

**Type 2 — Open-ended fields (StagehandCrawler fallback):**

- "Tell me about your best project"
- "Why do you want to work here?"
- "Describe a technical challenge you solved"
- Unknown dropdowns, salary expectations

### The hybrid flow:

```python
# Step 1 — Deterministic (free, zero LLM)
await page.fill('[name="first_name"]', profile.first_name)
await page.fill('[name="email"]', profile.email)
await page.set_input_files('[type="file"]', resume_path)

# Step 2 — Detect custom questions
questions = await page.query_selector_all('.custom-question')

if not questions:
    await page.click('[type="submit"]')
else:
    await page.act(f"Answer all open questions using: {profile.summary}")
    await page.click('[type="submit"]')
```

### Why NOT full LLM automation (ApplyPilot lesson):

- ApplyPilot delegates EVERYTHING to Claude Code CLI subprocess
- 93% failure rate — 1,503 discovered, only 112 applied
- LLM answers are detectable as AI-generated
- Unpredictable cost, zero debuggability

### The story bank approach (build AFTER Phase 3):

- Before applying, Maxisight interviews the user once
- Captures 20-30 real stories from their actual experience
- When Type 2 question appears, MATCH a real story — don't generate
- LLM adapts the story slightly for the specific company
- Result: answers sound human because they ARE human memories
- Build this AFTER seeing real failures in production — not before

---

## TWO PIPELINE ARCHITECTURE

```
PIPELINE A                          PIPELINE B
──────────────────────              ──────────────────────
1. MyGreenhouse search              1. Funded startup finder
   (httpx JSON API, paginated)         (source: TBD — Crunchbase/Apollo/Harmonic)
   + Lever + Ashby APIs
   + ParselCrawler (static pages)
   + PlaywrightCrawler (JS pages)
          │                                    │
2. LangGraph matcher                2. AdaptivePlaywrightCrawler
   (score fit, tailor resume)          (discover + crawl career pages)
          │                                    │
3. Playwright applicator            3. People finder
   (deterministic Type 1 fields)       (founder + employees by company size)
   StagehandCrawler fallback           Contact rule:
   (Type 2 open-ended only)            <20 → founder
          │                            20-50 → engineering lead
4. Email finder                        50+ → hiring manager
   (Hunter.io or Apollo)                        │
          │                         4. LLM-personalised cold email
5. SendGrid outreach                   (SendGrid)
   (cold email to hiring manager)
```

---

## KEY TECHNICAL DECISIONS

**Crawlee version:** Python v1.3.0 (January 2026) — production stable
**Python version:** 3.10+
**Why not Node.js:** Crawlee Python has everything needed. One language = no bridges.
**Why not Puppeteer:** Node.js only. No Python support. Playwright is Puppeteer v2.
**Why not FastAPI now:** CLI tool doesn't need a server. FastAPI is for Layer 2 hosted product.
**Why not database:** Output is JSON files. User decides persistence. SQLite only if needed later.
**Why not full LLM automation:** Story bank + deterministic first = better than ApplyPilot's approach.
**Why not LinkedIn:** Jobs appear 24-48hrs late. Direct ATS = first 10 applicants not 400.
**Why not per-slug Greenhouse API:** MyGreenhouse cross-company search is simpler, no slug list needed.
**Why not jobhive-py:** Still requires slugs upfront. Doesn't solve cross-company discovery problem.
**robots.txt:** `respectRobotsTxtFile: True` always on in all crawlers.
**Concurrency:** maxConcurrency: 2-3. Be polite to servers.
**Unique keys:** Always job_id from ATS. Never job title alone.

---

## CRAWLEE PYTHON CLI STACK (learned from reading Crawlee source)

```
Typer        → CLI framework (type annotations = commands)
Inquirer     → interactive prompts (dropdowns, text, yes/no)
Cookiecutter → project scaffolding (maxisight init generates project)
Rich         → terminal output (spinners, progress, colors)
```

---

## PIPELINE B OPEN DECISIONS

- Funded startup source: TBD (Crunchbase, Apollo, or Harmonic)
- Career page discovery: AdaptivePlaywrightCrawler finds /jobs, /careers, /work-with-us
- Contact size rule: <20 → founder. 20-50 → engineering lead. 50+ → hiring manager

---

## BUILD ORDER

### Phase 1 — crawler package (START HERE)

- [x] Set up Python monorepo with uv
- [x] Install Typer, Rich, Inquirer, Cookiecutter for CLI
- [ ] Build maxisight init command with Cookiecutter template
- [x] **TEST: Does my.greenhouse.io/jobs require login? YES — confirmed 401 in incognito**
- [x] Build MyGreenhouse httpx fetcher (paginated, Inertia.js XHR approach)
- [x] Add role filter (query param) + date filter (date_posted=past_24_hours)
- [x] Add pagination loop (moreResultsAvailable)
- [x] Normalize into unified job schema
- [x] Output to ./storage as JSON files
- [x] Test end to end — **4,494 Software Engineer jobs fetched, US only, June 5, 2026** ✓
- [ ] Build Lever httpx fetcher (fallback)
- [ ] Build Ashby httpx fetcher (GraphQL fallback)
- [ ] Add ParselCrawler for static career pages
- [ ] Add PlaywrightCrawler for JS-rendered pages
- [ ] Add AdaptivePlaywrightCrawler for unknown pages
- [x] Wire up maxisight crawl CLI command
- [ ] Add robots.txt respect
- [x] Add crawl delay (1s between pages) + graceful 429 handling

### Phase 1.5 — enricher package

- [x] `GreenhouseEnricher` — fetches full job descriptions from boards API
- [x] Three-strategy URL resolver (standard, EU, old boards, custom+board param, custom+HTML extract)
- [x] HTML stripping to plain text (unescape entities + strip tags)
- [x] `maxisight enrich` CLI command with `--limit` flag
- [x] `JobDataset.load()` method
- [x] Tested: 17/20 enriched (85% custom domain coverage)

### Phase 1.5 — scorer package ✓ COMPLETE

- [x] `ScoringProfile` model — loads from `storage/profiles/default.json`
- [x] `score_jobs()` — universal batch scorer, source-agnostic
- [x] Six signals: T (title keyword gate + fuzzy), S (seniority), F (freshness 2^(-t/halflife)), C (company), L (location), D (weighted skill matching)
- [x] Formula: Score = T² × (S+F+C+L+D)/5
- [x] Hard filters: blocklist keywords before scoring, deduplication by job ID
- [x] `ScoredJob` + `JobOutcome` models added to models.py
- [x] `JobDataset.save_scored()` + `load_enriched()` added
- [x] `--score` + `--profile` flags on `maxisight enrich` CLI command
- [x] `storage/profiles/default.json` — user edits this manually (Phase 1)
- [x] `storage/profiles/resume.txt` — placeholder for Phase 2 resume parsing
- [x] 36/36 tests passing (signals + formula + integration)
- [x] Live test: Support Engineer correctly scored 0.0

### Phase 2 — resume parsing + profile auto-population (NEXT)

**User currently edits `storage/profiles/default.json` manually.**
**Phase 2 removes that friction: upload resume → Claude parses → profile auto-populated.**

- [ ] Resume parser: `maxisight profile --resume resume.pdf` — Claude API extracts skills, titles, experience
- [ ] Writes parsed data to `storage/profiles/default.json` automatically
- [ ] User reviews/adjusts in JSON before scoring (or via hosted UI in Phase 3)
- [ ] LLM resume tailoring: for each qualified job, tailor resume bullet points to match JD
- [ ] Wire up `maxisight apply` — deterministic Playwright for Type 1 fields

### Phase 3 — applicator package

- [ ] Deterministic Playwright for Greenhouse web form (Type 1)
- [ ] Multi-step flow handling
- [ ] Resume PDF upload
- [ ] Extend to Lever, Ashby forms
- [ ] Detect Type 2 open-ended questions
- [ ] StagehandCrawler fallback for Type 2 only
- [ ] Wire up maxisight apply CLI command
- [ ] Run 100 real applications → document failures → then build story bank

### Phase 4 — emailfinder + outreach packages

- [ ] Hunter.io or Apollo integration
- [ ] SendGrid email sender
- [ ] LLM personalised email writer
- [ ] Wire up maxisight outreach CLI command

### Phase 5 — Pipeline B

- [ ] Decide funded startup source
- [ ] Startup discovery fetcher
- [ ] AdaptivePlaywrightCrawler for career page discovery
- [ ] People finder
- [ ] Personalised founder outreach
- [ ] Wire up maxisight outreach --pipeline funded-startups

### Phase 6 — Story bank (build AFTER Phase 3 real-world data)

- [ ] Maxisight interview flow (captures user's real stories)
- [ ] Story bank JSON structure
- [ ] Story-to-question matching engine
- [ ] LLM story adapter (adapts voice, not generates)
- [ ] Human review + approve flow before Type 2 submission

---

## COMPETITORS RESEARCHED

- **ApplyPilot** — Claude Code subprocess for apply, 93% failure rate, LLM-dependent
- **JobHuntr** — browser extension, paid
- **Simplify** — Chrome extension, copilot not agent
- **Jobright AI** — matching only, no auto-apply
- **Fantastic.jobs** — charges $200-4,000/month for cross-company Greenhouse search (what Maxisight does free)
- **jobhive-py** — open source but still requires slug upfront, doesn't solve discovery

---

## PROGRESS LOG

| Date        | What was done                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Jun 1, 2026 | Day 1 — Full vision locked. Name confirmed: Maxisight. Origin story written. Open source CLI confirmed. Architecture mapped. ATS priority list confirmed. Two pipeline architecture designed. Git repo initialized.                                                                                                                                                                                                                                                                   |
| Jun 1, 2026 | Day 2 (morning) — Built Node.js/TypeScript monorepo with Turborepo + citty. All 8 packages scaffolded. First commit made.                                                                                                                                                                                                                                                                                                                                                             |
| Jun 2, 2026 | Day 2 (pivot) — Pivoted to all-Python stack. Crawlee Python v1.3.0 confirmed production stable. Node.js/TypeScript abandoned. CLI stack confirmed: Typer + Inquirer + Cookiecutter + Rich. uv as package manager. StagehandCrawler architecture decided. Story bank approach conceived.                                                                                                                                                                                               |
| Jun 2, 2026 | Day 2 (evening) — Major Greenhouse discovery. MyGreenhouse (my.greenhouse.io) confirmed as cross-company search portal. JSON API structure reverse-engineered from network requests. firstPublished timestamp confirmed. date_posted=past_hour filter confirmed in URL. 680+ Software Engineer results confirmed. 7,500+ companies on Greenhouse (official March 2026 stat). Per-slug API approach abandoned in favor of MyGreenhouse search. Auth status TBD — needs incognito test. |
| Jun 5, 2026 | Day 4 — MyGreenhouse crawler working end-to-end. Reverse-engineered Inertia.js protocol (Rails + Inertia.js + React, not Next.js). Required 10 iterations: 406 → 200-no-data → 409 version mismatch → KeyError deferred props → 429 rate limit → working. Key fix: two-step fetch (plain GET for version, then Inertia XHR with X-Inertia-Partial-Data header). Fetched 4,430 jobs in one crawl. Full notes in docs/mygreenhouse-inertia-reverse-engineering.md. pytest suite added. |
| Jun 6, 2026 | Day 5 (morning) — Built enricher package. GreenhouseEnricher fetches full job descriptions from boards API. Three-strategy URL resolver covers all patterns: standard greenhouse subdomain (3,240), EU subdomain (233), old boards.greenhouse.io format (132), custom domain with board param (32), custom domain jid-only with HTML extraction (1,222). 17/20 test jobs enriched. Added JobDataset.load(). Architecture decision: matcher will be rubric-based not LLM per job — free, fast, explainable. Pipeline locked: crawl → enrich → match (rubric) → apply (LLM tailoring only). |
| Jun 8, 2026 | Day 7 — Identified D signal dilution flaw in scorer. Current D divides by sum of ALL skill weights (27.8) — no job ever scores high because no job lists all 35 skills. Plan: Top-K normalization (divide by sum of top-K weights, K=8). A 4-skill job goes from D=0.14 → D=0.50. Not yet implemented — fix before Phase 2. |
| Jun 6, 2026 | Day 5 (evening) — Built scorer package. Formula: Score = T² × (S+F+C+L+D)/5. Six signals: Title (keyword gate + fuzzy), Seniority (soft penalty), Freshness (2^(-t/halflife)), Company (blocklist/watchlist), Location (remote/hybrid/in_person), Description (weighted skill matching). Key: title keyword gate kills Support/MATLAB/Implementation Engineer without hardcoded blocklist — controlled by user's target_titles. Skill weights in JSON not Python. Profile must match crawl query. Phase 2: Claude auto-populates profile from resume upload. 36/36 tests passing. Live test: top 50 scored from enriched data, Support Engineer correctly absent. Added ScoredJob + JobOutcome models, JobDataset.save_scored(), --score flag on enrich CLI. |

---

## OPEN QUESTIONS

1. ~~**URGENT: Does my.greenhouse.io/jobs require login?**~~ **ANSWERED: Yes, 401 in incognito. Playwright auth + Inertia.js XHR approach working.**
2. Funded startup source — Crunchbase, Apollo, or Harmonic?
3. Resume storage — local file only or user can point to cloud?
4. LLM budget cap per day for scoring + tailoring?
5. SendGrid warm-up strategy for cold outreach?
6. Open source license — MIT or Apache 2.0?
7. Domain purchase — buy when Phase 1 is working

---

## SOURCES VERIFIED

- Greenhouse official company count (March 2026): 7,500+ companies
- 6Sense: ~15,000 tracked, 76% US-based
- MyGreenhouse JSON API structure: reverse-engineered by Viswa (June 2, 2026)
- MyGreenhouse tech stack: Rails + Inertia.js + React (confirmed June 5, 2026 via Playwright network intercept)
- MyGreenhouse Inertia.js fetch protocol: full notes in `docs/mygreenhouse-inertia-reverse-engineering.md`
- MyGreenhouse live crawl result: 4,430 jobs for "Software Engineer" past_24_hours (June 5, 2026)
- MyGreenhouse UI filters confirmed: Date posted, Salary, Work type, Employment type
- MyGreenhouse search results: 680+ for "Software Engineer" (June 2, 2026)
- Greenhouse API: `developers.greenhouse.io/job-board.html`
- Lever + Ashby live responses (April 2026): `cavuno.com/blog/ats-platforms-public-job-posting-apis`
- Crawlee Python v1.3.0 stable: `crawlee.dev/python`
- Crawlee Python crawlers: `crawlee.dev/python/docs/quick-start`
- AdaptivePlaywrightCrawler Python: `crawlee.dev/python/docs/guides/adaptive-playwright-crawler`
- StagehandCrawler: `crawlee.dev/python/docs/guides/playwright-crawler-stagehand`
- Crawlee CLI stack (read from source): Typer + Inquirer + Cookiecutter + Rich
- ApplyPilot issues live: `github.com/Pickle-Pixel/ApplyPilot/issues`
