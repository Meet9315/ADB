---
name: site-acquisition
description: >
  Crawls and optionally renders a target website within strict time and page
  budgets, producing a normalized page corpus and a crawl manifest for downstream
  analysis skills. Use this skill at the start of any audit pipeline, before
  running any analysis. It is strictly read-only and respects robots.txt.
license: MIT
compatibility: Requires Python 3.10+, httpx[http2], selectolax. Optional: playwright.
metadata:
  tier: "0"
  role: data-acquisition
---

## When to use

Use `site-acquisition` at the beginning of any website audit pipeline before invoking any analysis skills (such as `machine-readability-audit`, `trust-signals-audit`, or `engagement-audit`). Downstream analysis skills operate solely on offline local files and do not issue external network requests. `site-acquisition` acquires, normalizes, and packages the target website into a local page corpus alongside an authoritative `crawl_manifest.json`.

Never invoke analysis skills directly against live web endpoints without first running `site-acquisition`.

## Inputs

The skill is executed via its scripts (`scripts/crawl.py` followed by `scripts/render.py`), accepting the following parameters:

### Crawler Inputs (`scripts/crawl.py`)

| Argument / Option | Type | Default | Description |
|---|---|---|---|
| `domain` | String | *(Required)* | Target domain (e.g. `example.com`) or root URL (e.g. `https://example.com`). Automatically normalizes scheme and host. |
| `--output-dir` | Path | `corpus/<domain_slug>/pages` | Directory where per-page folders and crawl manifest are created. |
| `--budget-soft` | Float | `240.0` | Soft wall-clock budget in seconds. When reached, the crawler halts enqueueing new URLs. |
| `--budget-hard` | Float | `300.0` | Hard wall-clock deadline in seconds. Absolute ceiling across the entire acquisition stage. |

### Renderer Inputs (`scripts/render.py`)

| Argument / Option | Type | Default | Description |
|---|---|---|---|
| `corpus_dir` | Path | *(Required)* | Path to the `corpus/<domain_slug>/pages` directory produced by `crawl.py`. |
| `crawl_manifest` | Path | *(Required)* | Path to `crawl_manifest.json` produced by `crawl.py`. |
| `--budget-soft` | Float | Manifest value / `240.0` | Soft wall-clock budget in seconds (inherited from manifest if omitted). |
| `--budget-hard` | Float | Manifest value / `300.0` | Hard wall-clock budget in seconds (inherited from manifest if omitted). |

## Procedure

Acquisition executes as a coordinated two-phase pipeline sharing a single wall-clock timeline:

### Phase 1: Bounded Crawler (`scripts/crawl.py`)

1. **Robots Compliance & AI Bot Audit**:
   - Fetches `/robots.txt` before issuing page requests.
   - Parses `Disallow` and `Allow` directives for `AuditBot/1.0` and wildcard `*`. Disallowed paths are never crawled; skipped URLs are recorded in the manifest skip registry.
   - Separately inspects and logs directive rules for known AI crawler user-agents (`GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`, `CCBot`, `Bingbot`).
2. **Sitemap Discovery**:
   - Inspects `Sitemap:` declarations inside `robots.txt` and checks conventional paths (`/sitemap.xml`, `/sitemap_index.xml`).
   - Parses sitemap XML and sitemap indexes, extracting candidate page URLs up to the priority limit.
3. **Bounded Priority Crawl**:
   - **Bounds**: Hard cap of $\le 25$ unique pages, concurrency 6, and a 10-second timeout per page fetch.
   - **Prioritization Queue**:
     - `Priority 0 (Homepage)`: Root `/` fetched first.
     - `Priority 1 (Sitemap)`: High-value URLs discovered in sitemaps.
     - `Priority 2 (Navigation)`: Links extracted from `<nav>` and header tags on the homepage.
     - `Priority 3 (Template Clustering)`: Groups URLs by path pattern (e.g. `/items/{id}`, `/blog/{uuid}`), crawling at most 1 exemplar per pattern to prevent crawler traps.
     - `Priority 4 (Explicit Paths)`: Targeted search for `/about`, `/about-us`, `/contact`, `/contact-us`, `/pricing`.
   - **Scope**: Strictly restricted to the target origin host (same domain).
4. **Corpus Persistence**:
   - For every successful page response, creates a deterministic slug directory `corpus/<slug>/pages/<name>_<hash>/`:
     - `raw.html`: Pristine HTTP response payload.
     - `text.txt`: Clean visible text extracted via `selectolax`, stripping `<script>`, `<style>`, `<nav>`, `<footer>`, `<svg>`, and `<noscript>`.
     - `meta.json`: Final URL, status code, response headers, elapsed fetch time, title, and heading hierarchy (`h1`–`h6`).
5. **Manifest Generation**:
   - Writes initial `crawl_manifest.json` containing the domain metadata, initial budget snapshot (with `started_at` epoch timestamp), robots rules, sitemap results, page catalog, and skip records.

### Phase 2: Dynamic Renderer (`scripts/render.py`)

1. **Playwright Availability Probe**:
   - Checks on startup whether Playwright and a Chromium browser binary can be launched.
   - If missing: writes `renderer.playwright_available = false` into `crawl_manifest.json`, logs a notice, and exits cleanly with code 0. Downstream analysis skills fall back to raw HTML heuristics without crashing.
2. **Shared Wall-Clock Budget Check**:
   - Resumes tracking via `BudgetTracker.from_manifest()`. If less than 15 seconds remain before the 300s hard ceiling, rendering is skipped immediately to guarantee total pipeline compliance.
   - If remaining soft budget is $< 60$s, reduces sample rendering to 1 page (homepage only).
3. **Headless Execution & Sample Selection**:
   - Selects 3–5 representative pages (homepage + one exemplar per major URL template).
   - Launches headless Chromium once, navigating to each sample with an 8-second timeout (`wait_until="networkidle"`).
   - Writes `rendered.html` (post-DOM hydration snapshot) into each corresponding page directory.
4. **Manifest Finalization**:
   - Updates `crawl_manifest.json` with render results, appends any render-stage skips, and records the final consolidated acquisition budget snapshot.

## Shared Wall-Clock Budget Behavior

Acquisition guarantees strict execution boundaries via `lib/budget.py`:
- **Single Continuous Timeline**: `crawl.py` logs `started_at` (epoch timestamp) in `crawl_manifest.json`. When `render.py` starts, it resumes from that timestamp. The timer does not restart between processes.
- **Soft Deadline (240s)**: Halts crawler queue expansion and reduces renderer sample size.
- **Hard Deadline (300s)**: Absolute pipeline ceiling. All operations immediately persist gathered data and exit.
- **Audit Logging**: Skipped URLs or reduced samples are never dropped silently; each is recorded in `manifest.skips` with reason and timestamp.

## Output

### Directory Structure

```
corpus/<domain_slug>/
├── crawl_manifest.json
└── pages/
    ├── home_<hash>/
    │   ├── raw.html          # Initial static HTTP response
    │   ├── rendered.html     # Post-hydration DOM (if rendered)
    │   ├── text.txt          # Extracted visible plain text
    │   └── meta.json         # Headers, status code, headings, timing
    ├── about_<hash>/
    │   ├── raw.html
    │   ├── text.txt
    │   └── meta.json
    └── ... (up to 25 pages)
```

### Crawl Manifest Schema (`crawl_manifest.json`)

```json
{
  "schema_version": "1.0",
  "tool": "site-acquisition",
  "domain": "example.com",
  "base_url": "https://example.com",
  "origin_host": "example.com",
  "pages_crawled": 15,
  "pages_attempted": 16,
  "budget": {
    "started_at": 1741234567.89,
    "elapsed_s": 28.45,
    "soft_deadline_s": 240.0,
    "hard_deadline_s": 300.0,
    "over_soft": false,
    "over_hard": false
  },
  "robots": {
    "has_robots_txt": true,
    "raw_length_bytes": 512,
    "ai_agent_rules": {
      "GPTBot": {"disallowed": false, "rules": []},
      "ClaudeBot": {"disallowed": true, "rules": ["/private/"]}
    }
  },
  "sitemap": {
    "found": true,
    "urls_discovered": 30,
    "sources": ["https://example.com/sitemap.xml"]
  },
  "crawled_pages": [
    {
      "url": "https://example.com",
      "final_url": "https://example.com/",
      "status_code": 200,
      "error": null,
      "elapsed_s": 0.35,
      "slug": "home_61c98d9e"
    }
  ],
  "renderer": {
    "playwright_available": true,
    "pages_rendered": 4,
    "render_results": [
      {
        "url": "https://example.com",
        "slug": "home_61c98d9e",
        "rendered": true,
        "elapsed_s": 1.45,
        "error": null
      }
    ]
  },
  "skips": [
    {
      "stage": "crawl",
      "url": "https://example.com/admin",
      "reason": "disallowed_by_robots",
      "elapsed_at_skip_s": 1.2
    }
  ]
}
```

## Safety Constraints

- **Strictly Read-Only**: Issues exclusively HTTP GET and HEAD requests. Never submits forms, executes destructive calls, or accesses authenticated endpoints.
- **Robots-Compliant**: Disallow directives for standard crawlers are strictly obeyed.
- **Sandboxed Execution**: Enforces a 25-page cap, maximum 6 concurrency, 10s page timeout, and a 300s absolute runtime ceiling.
