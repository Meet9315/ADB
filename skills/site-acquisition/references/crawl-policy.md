# Crawl Policy — site-acquisition

## Robots compliance

The crawler identifies as `AuditBot/1.0 (+https://agentskills.io)`.

It fetches and parses `robots.txt` before any crawl activity.  Disallow
rules for `*` and for the `AuditBot` user-agent are honoured — URLs
matching any Disallow prefix (that is not overridden by a matching Allow
rule) are skipped and recorded in `crawl_manifest.json`.

Additionally, the crawler records (but does not necessarily obey) the
Disallow/Allow/Crawl-delay rules for six known AI user agents:
`GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`, `CCBot`,
`Bingbot`.  These are surfaced in `crawl_manifest.json` → `robots` →
`ai_agent_rules` for consumption by the machine-readability-audit skill.

## Crawl bounds

| Parameter | Value |
|---|---|
| Max pages | 25 |
| Concurrency | 6 |
| Per-page timeout | 10 s |
| Soft budget | 240 s (stop enqueueing new URLs) |
| Hard budget | 300 s (absolute ceiling) |

## Playwright-unavailable fallback

`render.py` probes Playwright and browser availability on startup.  If
either is missing:

1. The script sets `renderer.playwright_available = false` in
   `crawl_manifest.json`.
2. It exits cleanly with exit code 0 — **it does not crash**.
3. Downstream analysis skills check this flag.  When rendering was not
   available, any check that would have used rendered HTML falls back to
   raw HTML with a lower confidence score (typically −0.1 to −0.2 on
   the 0–1 scale).  The finding candidate records the fallback in its
   `false_positive_guard` field.

This means the full audit pipeline runs correctly in environments where
Playwright cannot be installed (CI containers, locked-down sandboxes,
etc.) — it just produces slightly less confident results for
JavaScript-dependent pages.

## Skip logging

Neither `crawl.py` nor `render.py` silently drops coverage.  Every URL
that was considered but not fetched/rendered is recorded in
`crawl_manifest.json` → `skips` with:

- `stage`: `"crawl"` or `"render"`
- `url`: the skipped URL
- `reason`: one of `robots_disallow`, `template_already_crawled`,
  `soft_deadline_approaching`, `render_budget_reduced`
- `elapsed_at_skip_s`: wall-clock time when the decision was made
