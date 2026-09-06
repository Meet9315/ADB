---
name: machine-readability-audit
description: >
  Audits a page corpus for structured-data gaps, robots-directive issues, metadata
  deficiencies, and content-accessibility problems that reduce AI agent discoverability.
  Emits finding candidates in the hardened finding contract format per the project
  constitution. Use this skill after site-acquisition has produced a corpus and
  crawl manifest. Implements Tier 0 core checks: R4, D2 (reach-layer checks R1,
  R2, R3, R5 are in site-acquisition).
license: MIT
compatibility: Requires Python 3.10+. Operates on local corpus — no network access needed.
metadata:
  tier: "0"
  role: analysis
---

## When to use

Run `machine-readability-audit` **after** `site-acquisition` has completed and produced:
- A corpus directory with `raw.html`, `text.txt`, `meta.json` per page.
- A `crawl_manifest.json` with robots rules, sitemap data, and page catalog.

This skill never issues network requests. It reads only from the local corpus.

## Inputs

| Script | Argument | Description |
|---|---|---|
| `scripts/check_noindex.py` | `corpus_dir` | Path to corpus pages directory (e.g. `corpus/example_com/pages`) |
| `scripts/check_noindex.py` | `--manifest` | Path to `crawl_manifest.json` (optional) |
| `scripts/check_d2.py` | `corpus_dir` | Path to corpus pages directory |

## Procedure

### R4 — noindex Directives on Substantive Pages (`scripts/check_noindex.py`)

1. Iterates over all page directories in `corpus_dir`.
2. Reads `meta.json` for the page's `response_headers` and `status_code`.
3. Reads `raw.html` for `<meta name="robots" content="...">` tags.
4. Detects `noindex` in either source.
5. Before filing a finding, applies the exclusion check (see Negative Logic below).

**DO NOT FIRE (Negative Logic — R4):**
- **Legitimately excluded URL paths**: Page URL path contains any of: `cart`, `login`, `signin`,
  `sign-in`, `checkout`, `account`, `register`, `registration`, `search`, `results`, `404`,
  `500`, `admin`, `dashboard`, `my-account`, `wishlist`, `basket`, `order-confirmation`,
  `logout`, `sign-out`, `forgot-password`, `reset-password`, `verify-email`.
- **Legitimately excluded page titles**: `<title>` or `<h1>` contains (case-insensitive) any of:
  `login`, `sign in`, `cart`, `checkout`, `search results`, `register`, `my account`,
  `order confirmation`, `sign up`, `404`, `page not found`, `forbidden`, `access denied`,
  `reset password`, `forgot password`.
- **Non-authoritative tag**: noindex found only inside an HTML comment (`<!-- -->`) or
  a JavaScript string — not in an actual parsed `<meta>` element or `X-Robots-Tag` header.
- **This exclusion list is mechanism-based** (page types legitimately excluded from search
  indexing everywhere). It must never be extended with site-specific carve-outs. If a page
  on a tested site doesn't match these categories, it is either a real finding or warrants a
  new generic mechanism-based category.

---

### D2 — Content Locked in Non-Text Form (`scripts/check_d2.py`)

1. For each page, extracts HTML from prominent zones: `<header>`, all `<section>` elements,
   and elements whose class contains `hero`, `banner`, `pricing`, `feature`, `cta`,
   `jumbotron`, or `showcase`.
2. Parses all `<img>` tags in those zones.
3. For each image: checks `alt` attribute (absent or empty string = candidate).
4. Applies decorative heuristics (see Negative Logic below).
5. Checks surrounding text (±300 chars) for context restatement (≥15 substantive words).
6. For text-light pages (<100 words), detects PDF/video embeds without transcript keywords.

**DO NOT FIRE (Negative Logic — D2):**
- **Non-empty alt text**: If `alt="..."` contains any non-whitespace content, do not flag.
- **Decorative filename keywords**: `src` contains `icon`, `logo`, `arrow`, `bullet`,
  `divider`, `bg`, `background`, `spacer`, `pixel`, `1x1`, `separator`, `pattern`,
  `texture`, `line`, `chevron`, `caret`, `social`, `spinner`, `loading`.
- **Decorative class keywords**: Image `class` attribute contains `icon`, `logo`, `avatar`,
  `badge`, `bullet`, `divider`, `separator`, `social`, `spinner`, `emoji`.
- **Decorative dimensions**: Both inline `width` and `height` attributes are ≤50px.
- **Sufficient surrounding text context** (strict signal — word count alone is not sufficient):
  A finding is suppressed only if the text within ±80 chars of the `<img>` tag satisfies
  ONE of the following two conditions:
  - **Caption-proximity**: The adjacent text is ≤12 words AND contains at least one token
    (length >3, not a generic stop-word) that also appears in the image's `src` filename.
    Example: `"Pricing table: monthly and annual plans"` adjacent to `/pricing-table.png`
    satisfies this because `pricing` and `table` appear in both.
  - **Alt-candidate overlap**: The adjacent text contains ≥2 src-filename tokens regardless
    of word count.
  Generic nearby paragraph text — even long paragraphs that happen to be near the image —
  does NOT qualify. The suppression must demonstrate that the adjacent text specifically
  describes *this image*, not just surrounds it. Each suppressed image records the exact
  signal that triggered suppression in `false_positive_guard`.
- **CSS background images**: Only `<img>` elements are checked. `background-image` CSS
  properties are excluded — they are decorative by convention.
- **Below-fold images**: Only images within `<header>`, `<section>` elements, or elements
  with prominent class keywords are checked. Images in `<footer>` or `<aside>` are excluded.

## Output

Both scripts emit a JSON array to stdout. Each element follows the hardened finding contract:

```json
{
  "id": "F-R4-001",
  "check_id": "R4",
  "page_url": "https://example.com/pricing",
  "root_cause": "orientation_cost",
  "evidence": {
    "type": "noindex_directive",
    "source": "X-Robots-Tag header",
    "directive_value": "noindex",
    "page_title": "Pricing Plans",
    "status_code": 200
  },
  "raw_severity_class": "high",
  "confidence": 0.92,
  "mechanism": "...",
  "false_positive_guard": "...",
  "verification_method": "curl -sI https://example.com/pricing | grep -i x-robots"
}
```

Progress/diagnostic messages are written to stderr. Findings array is written to stdout (suitable for piping to the orchestrator).
