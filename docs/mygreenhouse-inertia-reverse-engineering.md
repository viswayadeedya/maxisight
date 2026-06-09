# How my.greenhouse.io Works — Reverse Engineered (June 2026)

This document records the full discovery process for `my.greenhouse.io`. Nothing here was publicly documented. We found it by watching network requests in a real browser.

---

## What the site is

`my.greenhouse.io` is built with **Rails + Inertia.js + React**.

- **Rails** — the server (Ruby on Rails, Greenhouse's core stack)
- **Inertia.js** — a bridge between Rails and React. It lets Rails serve a React frontend without building a separate API. Not Next.js. Not a REST API.
- **React** — the frontend rendered in the browser

This matters because:
- The URL `my.greenhouse.io/jobs` does NOT return JSON to a plain HTTP request
- It returns HTML to browsers and JSON only to requests that look like Inertia XHR calls
- If you send `Accept: application/json` you get **406 Not Acceptable**

---

## The errors we hit and why

| Error | What we sent | Why it happened |
|-------|-------------|-----------------|
| `406 Not Acceptable` | `Accept: application/json` | Server only serves `text/html` for that URL. Rails rejects explicit JSON requests. |
| `200 OK` but no jobs | `Accept: text/html`, no Inertia headers | Server returns HTML shell. No `__NEXT_DATA__` (it's not Next.js). Data loads via JS. |
| `409 Conflict` | `X-Inertia: true` + wrong version | Inertia version mismatch. Server says "your app is out of date, reload." |
| `200 OK` but `KeyError: jobPosts` | `X-Inertia: true` + correct version | Server returned Inertia response but WITHOUT job data — deferred props not requested. |
| `429 Too Many Requests` | Everything correct, no delay | We were fetching 28 pages with no pause between requests. |

---

## How Inertia.js works (what we learned)

### Initial page load

Browser visits `my.greenhouse.io/jobs` → Rails returns HTML:

```html
<div id="app" data-page="{&quot;component&quot;:&quot;job_search&quot;,&quot;props&quot;:{...},&quot;version&quot;:&quot;feea613c...&quot;}"></div>
```

The `data-page` attribute is HTML-entity-encoded JSON. It contains:
- `component` — the React component name (`"job_search"`)
- `props` — initial props for the page (user info, settings — NOT job results)
- `version` — a hash of the current app version (critical for subsequent requests)

**Important:** The initial HTML does NOT contain job search results. Jobs load via a second XHR request.

### Subsequent navigation (XHR)

Every click/search in the browser triggers a fetch request with these headers:

```
X-Inertia: true
X-Inertia-Version: feea613c8cb5171fccbad5d95e15e2fc69579876
X-Inertia-Partial-Component: job_search
X-Inertia-Partial-Data: browsing,page,moreResultsAvailable,jobPosts
X-CSRF-Token: <value from MYGREENHOUSE-XSRF-TOKEN cookie>
X-Requested-With: XMLHttpRequest
Accept: text/html, application/xhtml+xml
Referer: https://my.greenhouse.io/jobs
```

Rails sees `X-Inertia: true` and returns JSON instead of HTML:

```json
{
  "component": "job_search",
  "props": {
    "browsing": false,
    "page": 1,
    "moreResultsAvailable": true,
    "jobPosts": [
      {
        "id": 4259746009,
        "title": "Support Engineer",
        "companyName": "Redwood Software",
        "logoUrl": null,
        "publicUrl": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4259746009?gh_src=my.greenhouse.search",
        "firstPublished": "2026-06-05T15:28:48Z",
        "locations": ["Houten, UT", "Utrecht, UT"],
        "workType": "hybrid",
        "payRanges": null,
        "viewed": false
      }
    ]
  },
  "url": "/jobs?query=Software+Engineer...",
  "version": "feea613c8cb5171fccbad5d95e15e2fc69579876"
}
```

### Deferred props

Inertia has a "deferred props" feature. Some props are not included in the initial XHR response — they load separately. Without `X-Inertia-Partial-Data`, the server returns only base props (user info, settings). You must request the job props explicitly.

`X-Inertia-Partial-Data: browsing,page,moreResultsAvailable,jobPosts` tells the server: only return these four props.

### Version checking

If `X-Inertia-Version` doesn't match the server's current version → **409 Conflict**.

The correct version must be extracted from the `data-page` attribute in the initial HTML load. It changes when Greenhouse deploys a new version of the app.

---

## The working fetch flow (httpx, Python)

```python
# Step 1 — plain GET to extract the current Inertia version
init = await client.get("https://my.greenhouse.io/jobs")
dp_match = re.search(r'data-page="([^"]+)"', init.text)
inertia_version = json.loads(html.unescape(dp_match.group(1))).get("version", "")

# Step 2 — all search pages as Inertia XHR
inertia_headers = {
    "X-Inertia": "true",
    "X-Inertia-Version": inertia_version,
    "X-Inertia-Partial-Component": "job_search",
    "X-Inertia-Partial-Data": "browsing,page,moreResultsAvailable,jobPosts",
    "X-CSRF-Token": cookies["MYGREENHOUSE-XSRF-TOKEN"],
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "text/html, application/xhtml+xml",
    "Referer": "https://my.greenhouse.io/jobs",
}

# paginate until moreResultsAvailable is False or 429
while True:
    response = await client.get(url, params=params, headers=inertia_headers)
    if response.status_code == 429:
        break  # rate limited — save what we have
    data = response.json()
    props = data["props"]
    jobs.extend(props["jobPosts"])
    if not props.get("moreResultsAvailable"):
        break
    page += 1
    await asyncio.sleep(1.0)  # be polite
```

---

## JSON field notes

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Greenhouse job ID |
| `title` | string | Job title |
| `companyName` | string | Company display name |
| `publicUrl` | string | Direct apply URL. Contains company slug: `job-boards.greenhouse.io/{slug}/jobs/{id}` |
| `firstPublished` | ISO 8601 string | When the job was first posted |
| `locations` | list of strings | e.g. `["San Francisco, CA", "Remote"]`. NOT a list of dicts. |
| `workType` | string | `"remote"`, `"hybrid"`, `"in_person"` |
| `payRanges` | null or list | Often null. When present, check if dict before calling `.get("min")` |
| `viewed` | bool | Whether the logged-in user has viewed this job |
| `moreResultsAvailable` | bool | Pagination signal — False means last page |

---

## URL parameters for search

```
https://my.greenhouse.io/jobs
  ?query=Software+Engineer
  &date_posted=past_24_hours       ← past_hour | past_24_hours | past_week | past_month
  &work_type[]=remote
  &work_type[]=hybrid
  &work_type[]=in_person
  &employment_type[]=full_time
  &page=1
```

---

## Session / cookies required

`maxisight auth greenhouse` opens a browser, waits for the user to log in, then saves these cookies:

| Cookie | Purpose |
|--------|---------|
| `_session_id` | Rails session — proves you are logged in |
| `MYGREENHOUSE-XSRF-TOKEN` | CSRF protection — must be sent as `X-CSRF-Token` header in XHR requests |
| `_dd_s` | Datadog monitoring (not required for auth) |
| PostHog cookie | Analytics (not required for auth) |

The session was saved at a timestamp in `storage/sessions/greenhouse.json`. Sessions appear to last at least several days.

---

## How we found all of this

1. Tried `Accept: application/json` → got 406. Realized it's not a JSON API.
2. Assumed Next.js, looked for `__NEXT_DATA__` script tag → not found. It's Rails.
3. Ran a Playwright script that loaded the page and intercepted all network requests.
4. Playwright showed a second request with `X-Inertia: true` headers returning JSON.
5. Captured the exact request headers Playwright sent.
6. Reproduced those headers in httpx one by one until it worked.
7. Got 409 → fixed by extracting version from `data-page` HTML attribute.
8. Got `KeyError: jobPosts` → fixed by adding `X-Inertia-Partial-Data` header.
9. Got 429 → fixed by adding 1 second delay between pages + graceful stop.

Total attempts to get this working: ~10 iterations.

---

## Rate limiting

Greenhouse rate limits requests at the page level. At ~1 request/second we hit 429 around page 28-30. Adding `asyncio.sleep(1.0)` between pages is sufficient for normal use. If 429 is hit mid-crawl, we stop and save what we have rather than crashing.

---

## Is this documented anywhere publicly?

No. Inertia.js itself is documented at [inertiajs.com](https://inertiajs.com), but how Greenhouse specifically implements it (deferred props, which component names, which partial data keys) was found only by inspecting network requests.

The `X-Inertia-Partial-Data: browsing,page,moreResultsAvailable,jobPosts` list is specific to Greenhouse's implementation — if they add or rename props, this may need updating.
