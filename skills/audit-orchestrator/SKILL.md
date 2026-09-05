---
name: audit-orchestrator
description: >
  Orchestrates a full AI-discoverability audit of any website. Accepts a domain
  name, runs site-acquisition to build a page corpus, dispatches analysis skills
  (machine-readability-audit, and later trust-signals-audit and engagement-audit),
  deduplicates findings by root cause, applies severity scoring, and emits a
  structured audit report. Use this skill whenever a user asks to audit a website
  for AI-discoverability, AI-readiness, structured-data coverage, or on-site
  engagement problems.
license: MIT
compatibility: Requires Python 3.10+, httpx, selectolax. Network access required.
metadata:
  tier: "0"
  role: entrypoint
---

## When to use

Use `audit-orchestrator` when the user wants a full end-to-end AI-discoverability
audit of a website. This is the only entrypoint skill; all other skills in this
marketplace are invoked by the orchestrator, not directly.

Do **not** invoke `site-acquisition` or `machine-readability-audit` directly
unless you are developing or testing an individual skill in isolation.

## Inputs

| Parameter | Required | Description |
|---|---|---|
| `domain` | Yes | The domain or URL to audit (e.g. `example.com` or `https://example.com`) |
| `output_dir` | No | Directory to write the corpus and report (default: `./audit-output/<domain>`) |
| `budget_soft_s` | No | Soft time budget in seconds (default: 240) |
| `budget_hard_s` | No | Hard time ceiling in seconds (default: 300) |

## Procedure

1. **Validate inputs.** Normalise the domain to a `https://` URL. Reject clearly
   invalid inputs (no TLD, localhost, IP addresses) before making any network call.
2. **Run `site-acquisition`.** Call `skills/site-acquisition/scripts/crawl.py`
   and, if a headless browser is available, `scripts/render.py`. Both scripts
   share a `BudgetTracker` instance. On completion, read `crawl_manifest.json`.
3. **Run analysis skills.** For each analysis skill available in this tier,
   invoke its entry script against the corpus directory. Collect the emitted
   finding candidates (JSON arrays).
4. **Deduplicate.** Group candidates by `(check_id, page_url, root_cause)`.
   Retain the highest-confidence candidate per group.
5. **Score.** Apply the severity matrix: `critical` findings suppress lower
   severity findings on the same page for the same root cause.
6. **Emit report.** Write `audit_report.json` containing the final finding list,
   a summary section (counts by severity), the budget snapshot, and the crawl
   manifest reference.
7. **Surface to user.** Print a human-readable summary: total findings by
   severity, top 3 critical/high findings with their verification methods.

## Output

`audit_report.json` at `<output_dir>/audit_report.json`:

```json
{
  "schema_version": "1.0",
  "domain": "...",
  "audited_at": "ISO-8601 timestamp",
  "budget": { "elapsed_s": 0, "over_soft": false, "over_hard": false },
  "summary": { "critical": 0, "high": 0, "medium": 0, "low": 0 },
  "findings": [ /* hardened finding contract objects */ ],
  "crawl_manifest_path": "..."
}
```

Each finding in `findings` conforms exactly to the hardened finding contract
defined in `PROJECT_CONSTITUTION.md`. The orchestrator never adds findings that
were not emitted by an analysis skill.
