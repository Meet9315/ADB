---
name: engagement-audit
description: Audits web corpora for cognitive flow, user orientation, wayfinding, interface friction, and actionability failure mechanisms (G1, G2, G3, G4).
---

# Engagement Audit Skill Specification (`engagement-audit`)

This skill audits a crawled website corpus for human cognitive orientation, navigation wayfinding, interaction friction, and clear actionability.

## 1. Separateness Justification: Human Usability vs Machine Parsing

The AI Discoverability audit pipeline evaluates a website across three distinct analytical tiers:

1. **Tier 0 (Machine Readability & Reachability — `machine-readability-audit`, `site-acquisition`)**:
   Addresses whether automated scrapers and headless parsers can access, render, and extract structured data from the site (robots directives, semantic landmarks, schema.org markup, JS rendering parity).
2. **Tier 1 (Trust Signals & Identity Corroboration — `trust-signals-audit`)**:
   Addresses whether autonomous answer engines can corroborate factual claims, resolve entity identity, and verify temporal freshness (staleness, internal consistency, brand collisions, organizational presence).
3. **Tier 2 (Cognitive Flow & Human Usability — `engagement-audit`)**:
   Addresses **human behavior and interaction flow**. An AI assistant synthesizing a recommendation or guiding an end-user to execute a real-world task must evaluate whether a human visitor will be able to orient immediately, navigate without dead ends, interact without obstructing friction, and identify the primary action. A site that is technically indexable and factually corroboratable can still fail completely if a human user bounces within 3 seconds due to cognitive disorientation, broken navigation, or intrusive overlays.

`engagement-audit` is strictly read-only and operates directly on the acquired corpus and crawl manifest.

---

## 2. Overview & Checks Implemented

| Check ID | Check Name | Target Issue | Default Severity | Root Cause |
|---|---|---|---|---|
| **G1** | Above-Fold Orientation Failure | Inability of a user to answer *who is this*, *what do they offer*, or *what should I do next* from initial viewport text | `medium` | `orientation_cost` |
| **G2** | Wayfinding Defects | Broken internal links, critical utility pages > 2 clicks from home without intentional navigation, or substantive orphan pages | `medium` (links/utility) / `low` (orphans) | `orientation_cost` |
| **G3** | Friction & Intrusive Obstructions | Modals/interstitials covering substantive content on load, transferred payload > 5MB, or media pushing content > 50% viewport | `medium` | `orientation_cost` |
| **G4** | No Discernible Primary Action | Absence of visible intent-bearing primary call-to-action on homepage or commercial product/service pages | `medium` | `statement_implicitness` |

---

## 3. Inputs and Operational Constraints

### Inputs
| Parameter | Type | Required | Description |
|---|---|---|---|
| `corpus_dir` | Directory Path | Yes | Path to crawled page subdirectories containing `raw.html`, `rendered.html` (if available), `text.txt`, and `meta.json`. |
| `--manifest` | File Path | No | Optional path to `crawl_manifest.json` containing site metadata, crawl graph, and depth metrics. |

### Operational Constraints
- **Read-Only**: Consumes local files; never initiates external network requests.
- **Strict Evidence Grounding**: Reasoning steps (G1, G4) must quote exact visible text strings and cannot invent inferences.
- **Deterministic Candidate Finding IDs**: Sequential candidate IDs (`F-G1-001`, `F-G2-001`, etc.).

---

## 4. Detailed Check Procedures & Negative-Logic Rules

### Check G1 — Above-Fold Orientation Failure (`check_g1.py`)

#### Procedure
1. Extract first-viewport text from the rendered homepage (header, hero section, and initial viewport elements before the primary fold, capped at first 1,500 characters or initial hero container).
2. Execute a structured rubric evaluation answering three fixed questions strictly from that extracted text:
   - **Q1 (Who is this?)**: Does the text identify the brand or entity name?
   - **Q2 (What do they offer?)**: Does the text define the specific product, service, platform, content, or mission provided?
   - **Q3 (What should I do next?)**: Does the text present a next step, directional prompt, or primary navigation entrypoint?
3. Require each answered question to cite the verbatim text excerpt it is based on.
4. If any question lacks a quote-grounded answer in the first-viewport text, emit a `G1` candidate finding.

#### Explicit Negative-Logic Rules
- **Ambiguity Guard (Rule 1)**: If the judgment is ambiguous, do NOT flag. The check must never guess or extrapolate an answer based on external assumptions about what the company probably does.
- **Verbatim Quote Requirement**: If concrete verbatim quotes answer all three questions, the check passes with 0 findings.
- **Minimalist Brand Exemption**: Sites with minimal text that nonetheless explicitly state brand, core offering, and a directional action in the first viewport are compliant.

---

### Check G2 — Wayfinding Defects (`check_g2.py`)

#### Procedure
1. **Broken Internal Links**: Scan crawled pages and manifest for internal links returning HTTP $4\text{xx}$ or $5\text{xx}$ status codes originating from crawled pages.
2. **Critical Utility Page Navigation**: Locate utility pages (`pricing`, `contact`, `about`). Evaluate their shortest navigational click-distance (`depth`) from the homepage.
3. **Substantive Orphan Pages**: Identify pages present in the crawl inventory with 0 incoming internal links from other crawled HTML documents.

#### Explicit Negative-Logic Rules
- **Intentional Navigational Path Guard**: Do not treat depth $> 2$ alone as a defect when a page has a clear, intentional navigational path (e.g. linked directly in the site header, primary navigation menu, or footer).
- **Substantive Orphan Guard**: Orphan pages discovered via sitemap are flagged ONLY when they are substantive pages ($\ge 80$ visible words), strictly excluding feeds, search endpoints, paginated archives (`/page/2`), tag filters, or utility artifacts.
- **External Links Exemption**: External out-links returning errors are not internal wayfinding defects.

---

### Check G3 — Friction & Intrusive Obstructions (`check_g3.py`)

#### Procedure
1. **Modals Covering Content**: Inspect the DOM for overlay, popup, interstitial, or dialog elements positioned with full-screen coverage (`fixed`/`absolute`, `z-index >= 100`, obscuring substantive content on load).
2. **Heavy Page Payload**: Check total transferred page byte payload against the $5\text{MB}$ ($5,242,880$ bytes) ceiling.
3. **Media Block Viewport Displacement**: Inspect top-of-page hero banners, background video containers, or media blocks exceeding $50\%$ of the initial viewport height ($> 450\text{px}$ or $> 50\text{vh}$) that push primary text content below the fold.

#### Explicit Negative-Logic Rules
- **Cookie & Consent Notice Exemption**: NEVER flag cookie banners, GDPR consent dialogs, terms notices, or legally required privacy prompts as friction findings. These are legal compliance mechanisms, not defect friction.
- **Intentional Page Control Guard**: A modal or dropdown is only a finding when it actively obscures substantive page content on initial load without user invocation.

---

### Check G4 — No Discernible Primary Action (`check_g4.py`)

#### Procedure
1. Inspect the homepage and commercial product/service/pricing pages for intent-bearing primary actions.
2. Evaluate presence of action elements (`<a>`, `<button>`, `<input type="submit">`) matching a bounded set of intent keywords:
   `contact`, `buy`, `purchase`, `quote`, `book`, `demo`, `sign-up`, `start`, `subscribe`, `download`, `get started`, `try free`, `add to cart`, `order`, `schedule`, `read docs`.
3. Verify that the action candidate has measurable text, visible styling, and a concrete target URL or submit action.

#### Explicit Negative-Logic Rules
- **Non-Commercial Exemption**: If the page's purpose does not require an immediate commercial or operational action (e.g., editorial articles, blog essays, documentation reference entries, privacy policies, legal disclaimers), do NOT flag and record that guard.
- **Bounded Action Intent**: Do not demand ecommerce purchase buttons on SaaS sites, or booking widgets on documentation sites. The action must align with the page context.

---

## 5. Hardened Candidate Finding Contract

All findings emitted conform strictly to the Pydantic `CandidateFinding` model:

```json
{
  "id": "F-G1-001",
  "check_id": "G1",
  "page_url": "https://example.com/",
  "root_cause": "orientation_cost",
  "evidence": {
    "type": "above_fold_orientation_failure",
    "unanswered_questions": ["what_do_they_offer"],
    "rubric_answers": {
      "who_is_this": {"answered": true, "quote": "Apex Systems"},
      "what_do_they_offer": {"answered": false, "quote": null},
      "what_should_i_do_next": {"answered": true, "quote": "Explore Solutions"}
    },
    "first_viewport_text_sample": "Apex Systems. Empowering next-generation synergies. Explore Solutions."
  },
  "raw_severity_class": "medium",
  "confidence": 0.88,
  "mechanism": "Initial viewport text fails to state the core offering. Human visitors bounce when value proposition is cryptic.",
  "false_positive_guard": "Grounded reasoning guard: evaluated strictly against first-viewport text quotes; ambiguous text suppressed.",
  "verification_method": "curl -sL https://example.com/ | head -n 40"
}
```
