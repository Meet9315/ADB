# AI Discoverability Audit — Agent Skill Marketplace

[![Skills Specification](https://img.shields.io/badge/AgentSkills-Compliant-brightgreen)](https://agentskills.io)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 122 passed](https://img.shields.io/badge/tests-122%20passed-success)](skills/audit-orchestrator/tests)

An open-source agent skill marketplace package that audits websites for **AI Discoverability**, **Machine Readability**, **Trust Signals**, and **Human Cognitive Usability**. 

Autonomous agents, LLM answer engines (Perplexity, ChatGPT Search, Claude), and semantic crawlers evaluate web content through fundamentally different mechanisms than traditional web crawlers. This package evaluates websites across three analytical tiers and 20 distinct checks, emitting structured, actionable audit reports conforming to the **Hardened Finding Contract**.

---

## 1. Skill Responsibilities & Composition

The marketplace is composed of five modular, composable skills declared in `marketplace.json`, with `audit-orchestrator` acting as the single primary entrypoint:

```
                          ┌──────────────────────────┐
                          │    audit-orchestrator    │  (Entrypoint)
                          │   CLI: audit.py run      │
                          └─────────────┬────────────┘
                                        │ (1. Crawl & Render)
                                        ▼
                          ┌──────────────────────────┐
                          │     site-acquisition     │  (Tier 0: Reach)
                          │  crawl.py  |  render.py  │  (R1, R2, R3, R5)
                          └─────────────┬────────────┘
                                        │ Normalized Corpus & crawl_manifest.json
         ┌──────────────────────────────┼──────────────────────────────┐
         │ (2. Extractability)          │ (3. Corroboration)           │ (4. Usability)
         ▼                              ▼                              ▼
┌──────────────────────────┐ ┌──────────────────────────┐ ┌──────────────────────────┐
│ machine-readability-audit│ │   trust-signals-audit    │ │     engagement-audit     │
│       (Tier 0: MRA)      │ │      (Tier 1: TSA)       │ │       (Tier 2: EA)       │
│ R4, D1-D3, E1-E4         │ │         T1 - T4          │ │         G1 - G4          │
└────────┬─────────────────┘ └──────────┬───────────────┘ └────────────┬─────────────┘
         │ Candidate Findings           │ Candidate Findings           │ Candidate Findings
         └──────────────────────────────┼──────────────────────────────┘
                                        │
                                        ▼
                          ┌──────────────────────────┐
                          │    audit-orchestrator    │  (Merge & Score Engine)
                          │ merge_findings.py        │  - Deduplication
                          │ build_report.py          │  - Traceable Recommendations
                          └─────────────┬────────────┘  - Pydantic Schema Validation
                                        │
                                        ▼
                          ┌──────────────────────────┐
                          │   Final Audit Report     │
                          │   (FinalReport JSON)     │
                          └──────────────────────────┘
```

### Skill Breakdown

| Skill | Role | Entrypoint | Key Responsibilities & Checks |
| :--- | :--- | :---: | :--- |
| **`audit-orchestrator`** | Top-Level Orchestrator | **`true`** | Coordinates execution across skills, enforces global runtime budgets, merges and deduplicates findings, links actionable recommendations, and emits validated `FinalReport` artifacts. |
| **`site-acquisition`** | Data Acquisition | `false` | Bounded crawler respecting RFC 9309 `robots.txt`, concurrency limit of 6, 10s page timeout, Playwright headless DOM rendering fallback, and reach checks (**R1, R2, R3, R5**). |
| **`machine-readability-audit`** | Tier 0 Analysis | `false` | Read-only analysis of DOM extractability, semantic landmarks, structured data coverage, and schema validity (**R4, D1, D2, D3, E1, E2, E3, E4**). |
| **`trust-signals-audit`** | Tier 1 Analysis | `false` | Evaluates temporal freshness, cross-page factual consistency, brand disambiguation, and organizational presence (**T1, T2, T3, T4**). |
| **`engagement-audit`** | Tier 2 Analysis | `false` | Evaluates human cognitive flow, first-viewport orientation, internal wayfinding, intrusive friction, and primary actions (**G1, G2, G3, G4**). |

---

## 2. Implemented Checks (20 Total)

### Tier 0: Reachability & Machine Readability
- **R1 — AI Crawler Access**: Detects blocking of AI user-agents (`GPTBot`, `ClaudeBot`, `PerplexityBot`, etc.) in `robots.txt`.
- **R2 — Anti-Bot Wall Verification**: Identifies edge firewalls (Cloudflare, Akamai) returning 403/429 to headless HTTP clients while allowing standard browsers.
- **R3 — Sitemap Completeness**: Verifies presence, HTTP 200 response, XML validity, and navigation page coverage of `sitemap.xml`.
- **R4 — Noindex Directives**: Detects `noindex` robots meta tags or HTTP headers on key non-utility pages.
- **R5 — Canonical Conflict & Dead Links**: Detects `og:url` vs canonical mismatches and 4xx status codes on internal links.
- **D1 — JS-Rendering Divergence**: Detects thin SSR content where raw HTML lacks >40% and >300 words compared to rendered DOM.
- **D2 — Prominent Image Alt Text**: Identifies content-bearing hero images lacking descriptive `alt` attributes.
- **D3 — Semantic HTML Structure**: Flags missing `<h1>` headings, broken heading hierarchy jumps, and missing `<main>` landmarks.
- **E1 — Archetype Structured Data**: Validates presence of expected Schema.org entities conditioned on inferred site archetype (e.g. `Product` on Ecommerce).
- **E2 — Schema Price Contradiction**: Detects numerical price mismatches between JSON-LD markup and visible text.
- **E3 — Quotability Gap**: Uses deterministic canonical questions to assess whether key topics provide direct, quotable answer passages.
- **E4 — Schema Syntax Errors**: Identifies malformed JSON-LD syntax, unclosed braces, or missing mandatory entity properties.

### Tier 1: Trust Signals & Corroboration
- **T1 — Staleness & Undated Content**: Detects stale temporal markers on time-sensitive claims (pricing, roadmaps) while guarding evergreen essays.
- **T2 — Internal Fact Inconsistency**: Normalizes and cross-references phone numbers, physical addresses, and corporate metrics across pages to identify conflicting assertions.
- **T3 — Brand Entity Ambiguity**: Identifies generic brand names lacking `Organization` `sameAs` Wikidata/social links and clear categorizations.
- **T4 — Contact & About Presence**: Flags missing contact channels, missing company background overviews, and unattributed news publishing.

### Tier 2: Human Cognitive Flow & Engagement
- **G1 — Above-the-Fold Orientation**: Evaluates first-viewport text against a 3-question rubric (*Who is this? What do they offer? What should I do next?*).
- **G2 — Wayfinding Defects**: Detects broken navigation paths, excessive utility click depth (>3), and substantive orphan pages.
- **G3 — Friction & Interstitials**: Detects unprompted full-screen modal overlays covering content on load and payloads exceeding 5MB.
- **G4 — Primary Action Intent**: Flags commercial pages lacking a discernible primary call-to-action or conversion path.

---

## 3. Quick Start & Installation

### Prerequisites
- Python 3.10 or 3.11
- Node.js (for running `skills-ref` specification validator, optional)

### Step 1: Install Dependencies
```bash
# Clone the repository
git clone https://github.com/Meet9315/ADB.git
cd ADB

# Install pinned dependencies
pip install -r requirements-pinned.txt

# Install Playwright browser engine for headless rendering
playwright install chromium
```

### Step 2: Run an Audit
Execute an end-to-end audit directly against any target domain:

```bash
# Run full audit pipeline
python skills/audit-orchestrator/scripts/audit.py run example.com

# Save report to a custom file with custom budgets
python skills/audit-orchestrator/scripts/audit.py run stripe.com \
  --output scratch/stripe_report.json \
  --budget-soft 60 \
  --budget-hard 90
```

### Step 3: Inspect the Output
The pipeline produces a JSON audit report adhering to the Pydantic `FinalReport` model:
```json
{
  "schema_version": "1.0",
  "audit_metadata": {
    "target_domain": "example.com",
    "base_url": "https://example.com",
    "archetype": "corporate",
    "is_tiny_site": false,
    "elapsed_s": 24.5,
    "partial_audit": false
  },
  "summary": {
    "total_findings": 3,
    "by_severity": { "critical": 0, "high": 0, "medium": 1, "low": 2 }
  },
  "findings": [ ... ],
  "recommendations": [ ... ]
}
```

---

## 4. Verification & Testing

The repository features comprehensive automated test suites validating contract compliance, synthetic recall, determinism, and budget boundaries:

```bash
# 1. Official AgentSkills Specification Validator (skills-ref)
npx -y skills-ref validate skills/audit-orchestrator
npx -y skills-ref validate skills/site-acquisition
npx -y skills-ref validate skills/machine-readability-audit
npx -y skills-ref validate skills/trust-signals-audit
npx -y skills-ref validate skills/engagement-audit

# 2. Python Skill Manifest & Frontmatter Validator
python scripts/validate_skills.py

# 3. Complete Pytest Suite (122 unit tests)
pytest

# 4. Planted-Defect Recall & Clean Control Suite (20 checks)
python skills/audit-orchestrator/tests/test_planted_defects.py

# 5. Multi-Run Determinism Suite
python skills/audit-orchestrator/tests/test_determinism.py

# 6. Early-Termination & Budget Degradation Suite
python skills/audit-orchestrator/tests/test_early_termination.py

# 7. Rule 1 Evidence-Fabrication Provenance Audit
python skills/audit-orchestrator/tests/test_evidence_provenance.py

# 8. Dependency Manifest & Import Audit
python scripts/verify_dependencies.py
```

---

## 5. Pinned Dependencies & Reproducibility

The project runtime strictly pins all direct third-party dependencies in `requirements-pinned.txt`:

| Package | Version | Purpose |
| :--- | :--- | :--- |
| `httpx[http2]` | `0.28.1` | Asynchronous HTTP client with HTTP/2 support |
| `selectolax` | `0.4.11` | High-performance Modest C-engine HTML parser |
| `playwright` | `1.62.0` | Headless Chromium automation for dynamic DOM rendering |
| `extruct` | `0.18.0` | Extraction of JSON-LD, Microdata, and RDFa metadata |
| `pydantic` | `2.12.5` | Strict contract validation and report schema invariants |
| `typer` | `0.27.2` | CLI framework for orchestrator commands |
| `beautifulsoup4` | `4.14.3` | Robust markup traversal and DOM manipulation |
| `lxml` | `6.1.1` | XML/HTML document tree parsing |
| `pytest` | `9.1.1` | Unit test execution and assertion framework |

All dependencies are verified by `scripts/verify_dependencies.py`, ensuring zero undeclared or unused dependencies.

---

## 6. Honest Limitations & Operational Boundaries

To ensure reliable, ethical, and bounded operation, the audit pipeline is built with deliberate operational constraints:

1. **Bounded Crawl Scope (25-page ceiling)**: The crawler acquires up to 25 representative pages (homepage, sitemap, navigation links, and URL templates). This enforces the strict p95 runtime target (< 4 minutes) and avoids crawling traps. Large multi-thousand page sites are sampled, not exhaustively mapped.
2. **Read-Only Non-Destructive Safety**: The pipeline performs strictly safe HTTP GET requests. It never submits forms, executes state-changing POST requests, attempts authentication, or bypasses anti-bot measures through credential stuffing or proxy cycling.
3. **Anti-Hallucination & Rule 1 Provenance**: Findings never invent or hypothesize unseen facts. All evidence values must be literal substrings extracted directly from the page corpus. If a heuristic or reasoning step is ambiguous, the finding is suppressed.
4. **False-Positive Edge Cases (3.3% Empirical Rate)**: Human review of 182 benchmark findings across 15 real-world sites identified a 3.3% false-positive rate, primarily in edge cases:
   - *News Headlines*: Headlines containing street terms (e.g. *"road"*) can occasionally trigger address conflict heuristics (T2).
   - *Mega-Menus*: Desktop CSS classes named `megamenu-popup` can trigger modal overlay heuristics (G3).
   - *Personal/Historical Sites*: Historical archives or personal portfolios may be flagged for missing commercial call-to-action buttons (G4).
5. **Headless Execution Requirements**: Playwright requires a valid browser engine (`playwright install chromium`). In environments where browser binaries cannot run, the crawler gracefully degrades to raw HTML heuristic fallback mode with calibrated lower confidence.

---

## 7. License

MIT License. See [LICENSE](LICENSE) for details.
