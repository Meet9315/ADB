---
name: machine-readability-audit
description: >
  Audits a page corpus for structured-data gaps, robots-directive problems, and
  metadata deficiencies that degrade AI agent discoverability. Implements checks
  R1–R5 (robots and crawlability), D1–D2 (structured data), and E2–E3 (engagement
  signals). Emits finding candidates in the hardened finding contract format for
  the orchestrator to deduplicate and score. Use this skill after site-acquisition
  has produced a corpus and crawl_manifest.json.
license: MIT
compatibility: Requires Python 3.10+. No network access needed (operates on local corpus).
metadata:
  tier: "0"
  role: analysis
---

## When to use

Use `machine-readability-audit` after `site-acquisition` has written its corpus
and `crawl_manifest.json`. Pass the corpus directory to the analysis script.

Do **not** invoke this skill before site-acquisition completes — it has no
network access and requires a local corpus to operate on.

Do **not** run this skill against a corpus produced by a different domain than
the one being audited in the current session.

## Inputs

| Parameter | Required | Description |
|---|---|---|
| `corpus_dir` | Yes | Path to the corpus directory written by site-acquisition |
| `crawl_manifest` | Yes | Path to `crawl_manifest.json` |
| `output_file` | No | Where to write finding candidates JSON (default: `<corpus_dir>/../findings_machine_readability.json`) |

## Procedure

For each check below, the script reads the relevant corpus files, applies the
detection logic, and emits zero or more finding candidates. It never modifies
corpus files. Detection logic is implemented in later tasks — this is the scaffold.

### Checks (Tier 0 core)

| Check ID | Area | What it detects |
|---|---|---|
| R1 | Robots | `robots.txt` missing or unreachable |
| R2 | Robots | Known AI agent blocked by robots.txt |
| R3 | Robots | `X-Robots-Tag: noindex` or `<meta name="robots" content="noindex">` |
| R4 | Robots | `Disallow: /` for wildcard agent |
| R5 | Robots | No `Sitemap:` directive in robots.txt |
| D1 | Structured data | No JSON-LD or Microdata on pages where it is expected |
| D2 | Structured data | JSON-LD present but unparseable or missing required fields |
| E2 | Engagement | No canonical `<link rel="canonical">` tag |
| E3 | Engagement | Missing or empty `<meta name="description">` |

For each check, the script must:
- State the specific condition(s) under which the check must **not** fire
  (false-positive guard, as data in the finding candidate)
- Provide a `verification_method` executable by a stranger in under 2 minutes
- Include concrete `evidence` traceable to corpus file values

## Output

`findings_machine_readability.json` — a JSON array of finding candidates:

```json
[
  {
    "id": "F-001",
    "check_id": "R1",
    "page_url": "https://example.com/robots.txt",
    "root_cause": "representation_gap",
    "evidence": { "type": "http_status", "status_code": 404 },
    "raw_severity_class": "high",
    "confidence": 0.95,
    "mechanism": "robots.txt absent means AI crawlers receive no Disallow/Allow directives and may crawl or skip pages unpredictably",
    "false_positive_guard": "HTTP GET to /robots.txt returned 404 (not a redirect to a valid file)",
    "verification_method": "curl -I https://example.com/robots.txt — expect 200 for compliant site"
  }
]
```

All fields in the hardened finding contract are required. The orchestrator will
reject any candidate missing a required field.
