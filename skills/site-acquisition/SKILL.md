---
name: site-acquisition
description: >
  Crawls and optionally renders a target website within strict time and page
  budgets, producing a normalized page corpus (raw HTML, extracted text, headers,
  status codes) and a crawl_manifest.json that records robots.txt rules for known
  AI user agents, sitemap parse results, timing, and any URLs skipped. Use this
  skill at the start of any audit pipeline before running analysis skills.
  Do not use this skill to modify any website resource — it is strictly read-only.
license: MIT
compatibility: Requires Python 3.10+, httpx[http2], selectolax. Optional: playwright for JS rendering.
metadata:
  tier: "0"
  role: data-acquisition
---

## When to use

Use `site-acquisition` at the beginning of an audit pipeline to build the page
corpus that analysis skills consume. Always run this skill before any analysis.

Do **not** use this skill to:
- Perform authenticated requests
- Submit forms or modify any external resource
- Crawl domains that are not the explicit audit target

## Inputs

| Parameter | Required | Description |
|---|---|---|
| `domain` | Yes | Domain or URL to crawl (e.g. `example.com`) |
| `output_dir` | No | Directory to write corpus pages (default: `./corpus/<domain>/pages`) |
| `budget_soft_s` | No | Soft deadline in seconds (default: 240) |
| `budget_hard_s` | No | Hard ceiling in seconds (default: 300) |

## Procedure

### crawl.py

1. Fetch and parse `robots.txt`. Record Disallow/Allow rules for `*`,
   `GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`, `CCBot`, `Bingbot`.
2. Parse sitemaps discovered from `robots.txt` Sitemap: directives and fallback
   paths (`/sitemap.xml`, `/sitemap_index.xml`).
3. Seed the crawl queue (priority order):
   - Priority 0: homepage
   - Priority 1: robots.txt / sitemap-listed URLs (one exemplar per path template)
   - Priority 2: nav-linked pages from the homepage
   - Priority 3: one exemplar per URL path-pattern cluster
   - Priority 4: explicit paths `/about`, `/contact`, `/pricing`
4. Crawl up to 25 pages, concurrency 6, 10 s timeout per page.
5. Stop enqueueing new URLs (not mid-fetch) when the soft budget is close.
   Record all skipped URLs and reasons in `crawl_manifest.json`.
6. For each fetched page: save `raw.html`, `text.txt`, `meta.json` under
   `corpus/<slug>/`.

### render.py

1. On startup, detect whether Playwright and a browser binary are available.
   If not, set `playwright_available: false` in the manifest and exit cleanly —
   do not crash. Downstream checks will use lower-confidence heuristics instead.
2. Sample 3–5 pages: homepage + one exemplar per major URL template.
3. Reduce the sample count rather than exceed the remaining budget.
4. Render each page with an 8 s timeout, reusing a single browser instance.
5. Write rendered HTML alongside the raw HTML in the corpus.

## Output

```
corpus/
  <slug>/
    raw.html          # HTTP response body
    rendered.html     # Playwright render (if available)
    text.txt          # Extracted text, scripts/styles stripped
    meta.json         # URL, status, headers, h1/h2/h3, timing, errors
crawl_manifest.json   # Robots rules, sitemap results, budget snapshot, skip log
```

`crawl_manifest.json` schema (key fields):

```json
{
  "schema_version": "1.0",
  "domain": "...",
  "budget": { "elapsed_s": 0, "soft_deadline_s": 240, "hard_deadline_s": 300 },
  "skips": [{ "stage": "crawl", "url": "...", "reason": "...", "elapsed_at_skip_s": 0 }],
  "robots": { "ai_agent_rules": { "GPTBot": { "disallow": [], "allow": [] } } },
  "sitemap": { "found": true, "urls": [], "errors": [] },
  "crawled_pages": [{ "url": "...", "status_code": 200, "slug": "..." }]
}
```
