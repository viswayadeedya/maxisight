---
name: project-progress
description: What has been built in Maxisight, what phase we are in, what is next
metadata:
  type: project
---

**Current phase:** Phase 1.5 (scorer built) — Day 5 (evening)

**Built (as of June 6, 2026):**

**Infrastructure:**
- Python project with uv + hatchling, rapidfuzz added
- Full CLI: `maxisight version / auth / crawl / enrich` (Typer + Rich)
- `enrich` command now has `--score` and `--profile` flags

**Models (`src/maxisight/models.py`):**
- `Job` — id, source, company_slug, company_name, title, location (str), url, posted_at (str ISO), work_type, salary_min/max, description, raw
- `ScoredJob` — wraps Job + score, title_score, seniority_score, freshness_score, company_score, location_score, description_score, scored_at
- `JobOutcome` — tracks what happened after applying (interview/rejected/ghosted/offer/withdrew)

**Crawler (`src/maxisight/crawler/`):**
- `GreenhouseSlugCrawler` — per-slug API fallback, tested: 469 Stripe jobs ✓
- `MyGreenhouseCrawler` — cross-company search via my.greenhouse.io ✓
  - Inertia.js two-step fetch, 4,494 jobs in one crawl
  - US only by default, `--worldwide` flag available

**Enricher (`src/maxisight/enricher/`):**
- `GreenhouseEnricher` — fetches full job descriptions from boards API ✓
  - Three-strategy URL resolver (standard greenhouse, EU, old boards, custom domain)
  - 17/20 test jobs enriched (85% custom domain coverage)
  - HTML stripped to plain text

**Scorer (`src/maxisight/scorer/`) — BUILT TODAY ✓:**
- `ScoringProfile` — loads from `storage/profiles/default.json`
  - Fields: target_titles, skill_weights (weighted dict), level, freshness_halflife_hours, score_threshold, top_n, blocklist_companies, watchlist_companies, blocklist_keywords
  - **User edits this JSON file manually (Phase 1 / developer audience)**
  - **Phase 2 hosted product: resume upload → Claude auto-populates this profile**
- `score_jobs(jobs, profile)` — universal batch scorer, works for ANY ATS source
- Six signals: T (title), S (seniority), F (freshness), C (company), L (location), D (description)
- Formula: `Score = T² × (S + F + C + L + D) / 5`
- T² amplifier: Support Engineer, MATLAB Engineer, Implementation Engineer → T=0.0 → score=0.0
- Freshness: exponential decay `2^(-hours/halflife)`, score=0.5 exactly at halflife
- Hard filters: blocklist keywords (visa/clearance) eliminated before scoring
- Deduplication by job ID built in
- 36/36 unit + formula + integration tests passing

**Storage (`src/maxisight/storage/`):**
- `JobDataset.save()`, `load()`, `load_enriched()`, `save_scored()` ✓
- Scored output → `storage/datasets/scored/`
- Raw jobs NEVER overwritten — always preserved

**Profile files:**
- `storage/profiles/default.json` — user's scoring config (titles, skill weights, blocklists)
- `storage/profiles/resume.txt` — placeholder for Phase 2 resume parsing

**Tests:** 36 passing across signals, formula, and integration

**Pipeline confirmed working end-to-end:**
```
maxisight crawl   → 4,494 job cards saved to storage/datasets/mygreenhouse/
maxisight enrich  → full descriptions added, saved to enriched_*.json
maxisight enrich --score → scorer runs, top 50 jobs saved to storage/datasets/scored/
```

**Live result:** 50 jobs passed threshold from 50 enriched — top: D2L (Software Developer), Encora (Backend Engineer), Checkr (Senior Software Engineer)

---

**Key design decisions locked:**

1. **Scorer is source-agnostic** — works for Greenhouse, Lever, Ashby, any future ATS. Only knows about the `Job` model.
2. **Profile is user-editable JSON** — not hardcoded in Python. User changes their targets/weights by editing `default.json`. Different roles = different profile file.
3. **Profile must match the crawl query** — if you crawl "Data Analyst" but profile still says "software engineer" targets, all data analyst jobs will score 0. User is responsible for keeping them aligned.
4. **LLM nowhere in the scorer** — entirely free, instant, deterministic. LLM only enters at apply time for resume tailoring.
5. **Phase 2 hosted product** wraps this: resume upload → Claude parses → auto-populates profile JSON → user sees UI sliders. Same scorer underneath, no code change needed.

---

**Still TODO in Phase 1:**
- Lever httpx fetcher
- Ashby GraphQL fetcher
- `maxisight init` with Cookiecutter template
- robots.txt respect

**Phase 2:** Resume parsing (Claude API), profile auto-population, LLM resume tailoring per qualified job
**Phase 3+:** Playwright applicator, emailfinder, outreach, Pipeline B, story bank
