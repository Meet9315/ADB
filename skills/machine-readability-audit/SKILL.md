---
name: machine-readability-audit
description: >
  Audits a page corpus for structured-data gaps, robots-directive issues, metadata
  deficiencies, JS-rendering divergence, and content-accessibility problems that reduce
  AI agent discoverability. Emits finding candidates in the hardened finding contract format
  per the project constitution. Use this skill after site-acquisition has produced a corpus
  and crawl manifest. Implements Tier 0 core checks: R4, D1, D2, E2, E3 (reach-layer
  checks R1, R2, R3, R5 are in site-acquisition).
license: MIT
compatibility: Requires Python 3.10+. Operates on local corpus — no network access needed.
metadata:
  tier: "0"
  role: analysis
---

## When to use

Run `machine-readability-audit` **after** `site-acquisition` has completed and produced:
- A corpus directory with `raw.html`, `text.txt`, `meta.json`, and optional `rendered.html` per page.
- A `crawl_manifest.json` with robots rules, sitemap data, and page catalog.

This skill never issues network requests. It reads only from the local corpus.

## Inputs

| Script | Argument | Description |
|---|---|---|
| `scripts/archetype.py` | `crawl_manifest.json` | Path to manifest from site-acquisition |
| `scripts/archetype.py` | `--corpus-dir` | Pages directory (default: `<manifest_dir>/pages`) |
| `scripts/check_noindex.py` | `corpus_dir` | Path to corpus pages directory |
| `scripts/check_noindex.py` | `--manifest` | Path to `crawl_manifest.json` (optional) |
| `scripts/check_d1.py` | `corpus_dir` | Path to corpus pages directory |
| `scripts/check_d1.py` | `--manifest` | Path to `crawl_manifest.json` (optional) |
| `scripts/check_d2.py` | `corpus_dir` | Path to corpus pages directory |
| `scripts/check_e2.py` | `corpus_dir` | Path to corpus pages directory |
| `scripts/check_e2.py` | `--manifest` | Path to `crawl_manifest.json` (optional) |
| `scripts/check_e3.py` | `corpus_dir` | Path to corpus pages directory |
| `scripts/check_e3.py` | `--manifest` | Path to `crawl_manifest.json` (optional) |

---

## Structured Data Extraction Interface (`scripts/structured_data.py`)

All structured data extraction is encapsulated behind a unified interface:
`extract_structured_data(html: str, base_url: str = "") -> List[NormalizedRecord]`.

Downstream checks (`check_e2.py`, etc.) consume only `NormalizedRecord` objects and never
interact directly with parser-specific dict structures or formats.

### Supported Formats & Normalization
- **JSON-LD**: Extracted and flattened (including `@graph` arrays and nested entities).
- **Microdata**: Extracted from `itemscope`, `itemtype`, and `itemprop` structures.
- **RDFa**: Extracted from `vocab`, `typeof`, and `property` attributes.

Each `NormalizedRecord` contains:
- `syntax`: `'json-ld' | 'microdata' | 'rdfa'`
- `schema_type`: Bare schema.org type string (e.g. `'Product'`, `'Offer'`, `'LocalBusiness'`), stripped of URIs.
- `properties`: Dict of normalized property names mapped to cleaned values (RDFa values unpacked, URIs stripped).
- `raw`: Original parsed structure for diagnostic tracing.

### Dependency & Fallback Behavior
- Primary parser: `extruct==0.18.0` (pinned in `requirements.txt`).
- Fallback parser: When `extruct` is not installed or raises on malformed markup, a pure-Python fallback
  extracts JSON-LD script blocks and basic Microdata itemscopes. The fallback path logs explicitly and is tested.

---

## Procedures & Checks

### Archetype Inference (`scripts/archetype.py`)

Run **before** downstream checks to calibrate severity thresholds and select canonical questions.

1. Reads every page's `raw.html` and `meta.json` from `corpus_dir`.
2. Extracts observable signals: JSON-LD `@type` values, URL path patterns, HTML class
   attributes, form actions, link text, article dates, bylines, physical addresses
   (with code-block content stripped first), and business hours.
3. Scores each of 8 archetypes against those signals (`ecommerce`, `saas`, `news`, `content`,
   `docs`, `portfolio`, `local_business`, `corporate`).
4. Returns top-scoring archetype as primary; tags `is_tiny_site: true` if < 8 pages crawled.

**Negative Logic (Archetype):**
- Address alone is not `local_business` (capped at 0.5; requires hours or local schema).
- `Organization`/`WebSite` schema is near-universal (+0.3 weight only); `Corporation` is diagnostic.
- `/checkout` in arbitrary links is not a cart; cart requires specific CSS classes or form actions.
- Strip `<pre>` and `<code>` blocks before phone/address detection to avoid code examples.

---

### D1 — JS-Render Gap (`scripts/check_d1.py`)

Detects client-side JavaScript rendering divergence between the raw fetched HTML and the
fully executed DOM on sampled pages.

1. Identifies pages where `rendered.html` exists alongside `raw.html`.
2. Extracts visible text from both representations (stripping `<script>`, `<style>`, `<noscript>`, `<svg>`).
3. Computes `raw_word_count`, `rendered_word_count`, `gap = rendered - raw`, and `ratio = gap / rendered`.
4. Evaluates SSR / prerender escape hatches (`__NEXT_DATA__`, `<script type="application/json">`, `<noscript>`).
5. Finds a concrete post-render-only fact (substantive phrase present only in rendered DOM).

**DO NOT FIRE (Negative Logic — D1):**
- **Threshold guard**: Must NOT fire unless BOTH condition 1 AND condition 2 are met:
  1. `ratio > 0.40` (>40% of visible words are missing from raw HTML).
  2. `gap > 300` (absolute deficit is greater than 300 words).
- **Minor dynamic widgets**: Cookie banners, live chat popups, or footer widgets that add <300 words are ignored.
- **Semantically usable escape hatches**: If missing facts are extractable from framework JSON state or
  substantive `<noscript>` fallback, confidence is reduced (0.92 -> 0.65). Opaque minified hashes/state
  do NOT count as an escape hatch.
- **Bounded heuristic fallback**: If Playwright / `rendered.html` is absent, an SPA shell with <120 words
  and JS bundles is flagged at explicitly capped confidence (0.48). Never claim high confidence without DOM.

---

### R4 — noindex Directives (`scripts/check_noindex.py`)

1. Inspects `meta.json` response headers (`X-Robots-Tag`) and `raw.html` `<meta name="robots">`.
2. Detects `noindex` directives on indexable substantive pages.

**DO NOT FIRE (Negative Logic — R4):**
- Legitimately private/transient URL paths (`/cart`, `/checkout`, `/login`, `/admin`, `/search`, `/404`).
- Legitimately private page titles (`Sign in`, `Cart`, `Checkout`, `Page not found`).
- Directive found only inside an HTML comment or JS string literal.

---

### D2 — Content Locked in Non-Text Form (`scripts/check_d2.py`)

1. Parses `<img>` tags in prominent content zones (`<header>`, `<section>`, hero/pricing classes).
2. Flags images missing descriptive `alt` text.

**DO NOT FIRE (Negative Logic — D2):**
- Non-empty `alt` attribute.
- Decorative filenames (`icon`, `logo`, `divider`, `spacer`, `1x1`, `social`, `spinner`).
- Decorative CSS classes (`icon`, `avatar`, `badge`, `social`, `emoji`).
- Small dimensions (width and height both ≤50px).
- Content-specific restatement: text within ±80 chars is ≤12 words sharing ≥1 filename token, or shares ≥2 tokens.
- CSS `background-image` or footer/aside images.

---

### E2 — Invalid / Contradicting Structured Data (`scripts/check_e2.py`)

Consumes normalized records from `structured_data.py`. Covers JSON-LD, Microdata, and RDFa.

1. **Deterministic Schema Validation**:
   - `Product`: Requires `name`.
   - `Offer`: Requires `price` or `priceSpecification`. If `price` present, requires `priceCurrency`.
   - `LocalBusiness`: Requires `name` and (`address` or `telephone`).
   - `Organization` / `Corporation`: Requires `name` or `legalName`, and `url`.
   - `Article` / `NewsArticle` / `BlogPosting`: Requires `headline` or `name`, `author`, and `datePublished`.
2. **Contradiction Detection**:
   - Compares structured values (`price`, `availability`, `name`, `address`) with visibly stated page text.
   - Normalizes harmless differences: whitespace, currency symbols vs ISO codes (`$19.99` == `19.99 USD`),
     phone formatting, URL schemes/trailing slashes, and numeric formats before comparing.
   - Contradictions are flagged at **critical** or **high** severity because conflicting machine-readable
     and visible facts cause downstream AI systems to distrust or misquote the site.

**DO NOT FIRE (Negative Logic — E2):**
- **Harmonious formatting differences**: `$19.99`, `19.99 USD`, and `19.99` are identical; never flag.
- **Multiple variants/tiers**: If structured data price matches *any* stated price tier on the page, do not flag.
- **Partial availability overlap**: If visible text does not explicitly assert "Sold out" / "Out of stock",
  do not contradict `InStock`.
- **Deduplicated findings**: Multiple structured records for the same product on the same page only emit one
  contradiction finding per distinct field.

---

### E3 — Quotability Gap (`scripts/check_e3.py`)

Tests whether an AI search agent or assistant can extract self-contained, quotable factual answers
to canonical questions for the site's archetype.

1. Obtains primary site archetype from `archetype.py`.
2. Generates 5–8 canonical archetype-specific questions:
   - `ecommerce`: Return/refund policy, accepted payment methods, shipping times/costs, product catalog, support contact.
   - `saas`: Product value proposition, pricing tiers and recurring costs, free trial terms, supported integrations/APIs, platform support, security/compliance.
   - `local_business`: Physical address/service area, business hours, appointment booking, services offered, direct phone/contact.
   - `docs`: Installation command, authentication credentials, system prerequisites, API reference entry, bug report procedure.
   - `content` / `news`: Editorial scope, subscription rates, whistleblower tips, corrections policy, publisher/ownership.
   - `corporate`: Core commercial solutions, executive leadership, headquarters location, investor/press relations, ESG governance.
3. Extracts a bounded, explicitly enumerated corpus of coherent passages (30–250 words) from visible text across the crawled site.
4. Evaluates whether any single passage self-containedly answers each question with factual indicators.
5. Flags unanswered or evasive questions (e.g. "contact sales for pricing" without figures).

**DO NOT FIRE (Negative Logic — E3):**
- **Self-contained answer present**: If at least one passage provides verifiable, concrete facts answering the question, do not flag.
- **Never reconstruct from external knowledge**: Evaluation is strictly bounded to the script-extracted corpus.
- **Tiny-site calibration**: For sites tagged `is_tiny_site`, missing secondary questions do not inflate severity;
  orientation and primary purpose questions take precedence.

---

## Output Contract

All check scripts emit a JSON array to stdout adhering strictly to the Hardened Finding Contract:

```json
{
  "id": "F-E2-001",
  "check_id": "E2",
  "page_url": "https://example.com/product",
  "root_cause": "corroboration_deficit",
  "evidence": {
    "type": "structured_data_contradiction",
    "syntax": "json-ld",
    "schema_type": "Offer",
    "field": "price",
    "structured_value": 19.99,
    "visible_values": [49.99]
  },
  "raw_severity_class": "critical",
  "confidence": 0.95,
  "mechanism": "Structured data declares price 19.99 (json-ld), but visible page text explicitly advertises 49.99. Conflicting facts cause assistants to quote false pricing.",
  "false_positive_guard": "Normalized currency, whitespace, and numeric formats before comparison. Stated visible values strictly contradict structured data.",
  "verification_method": "Inspect page source `curl -sL https://example.com/product` and compare json-ld 'price' with visible content."
}
```

Progress and diagnostic messages are written to stderr. Clean JSON arrays are written to stdout.
