# Recommendation Bank — Canonical Action Templates

This file defines actionable, evidence-derived remediation templates for all implemented check IDs
(`R1`, `R2`, `R3`, `R4`, `R5`, `D1`, `D2`, `E2`, `E3`).
Every suggested action is parameterized strictly by the finding's concrete evidence.

### Canonical Recommendation Contract & Traceability Guarantee

Every remediation recommendation conforms to the canonical `SuggestedAction` model:
- `id`: Unique recommendation ID (e.g. `REC-001`).
- `title`: Non-empty, non-placeholder descriptive title.
- `description`: Non-empty, evidence-parameterized explanation of the defect and remediation.
- `code_snippet`: Concrete copy-pasteable configuration or markup snippet (or `None`).
- `priority`: Severity class matching or calibrated from defect urgency (`critical`, `high`, `medium`, `low`).
- `linked_findings`: Non-empty list of finding IDs (`["FINDING-001", ...]`) that this recommendation remediates.
- `is_proactive`: Boolean indicating whether this is an archetype proactive suggestion (`True`) or defect remediation (`False`).

**Orphan Rejection Rule**:
Non-proactive recommendations (`is_proactive=False`) MUST specify at least one valid finding ID in `linked_findings`. Any recommendation with empty `linked_findings`, placeholder finding IDs, or referencing non-existent finding IDs is strictly rejected by Pydantic validation. Bidirectional traceability is verified at both `FinalFinding` level (`self.id in self.suggested_action.linked_findings`) and `FinalReport` level (`linked_findings ⊆ set(finding_ids)`).

---

## R1 — AI Crawlers Blocked in robots.txt

- **Check ID**: `R1`
- **Root Cause**: `orientation_cost`
- **Title**: Update `robots.txt` to Permit Discovery-Oriented AI User-Agents
- **Description**:
  The current `robots.txt` disallows AI agents from crawling the site:
  Blocked agents: `{blocked_agents}` via directive `{directive_sample}`.
  {training_bot_note}
  To allow AI search and assistant discovery without permitting model training on your proprietary data,
  configure granular user-agent rules permitting assistant bots (`GPTBot`, `ClaudeBot`, `PerplexityBot`)
  while optionally disallowing training-only harvesters (`Google-Extended`, `CCBot`).
- **Code Snippet**:
  ```text
  # robots.txt recommendation
  User-agent: GPTBot
  Allow: /

  User-agent: ClaudeBot
  Allow: /

  User-agent: PerplexityBot
  Allow: /
  ```

---

## R2 — Bot Challenges or Blocking

- **Check ID**: `R2`
- **Root Cause**: `orientation_cost`
- **Title**: Configure WAF Rules to Whitelist Legitimate Search & AI Crawlers
- **Description**:
  The site edge/WAF returned a blocking challenge or access denial (`status_code: {status_code}`,
  `challenge_type: {challenge_type}`) when fetched by standard crawlers.
  Automated assistant and search engines will be unable to index content behind interstitial challenges.
  Update your security gateway (e.g. Cloudflare, CloudFront, Fastly) to pass verified bot traffic.
- **Code Snippet**:
  ```text
  # Cloudflare WAF Custom Rule Example:
  # Action: Skip Challenge
  # Expression: (cf.client.bot or http.user_agent contains "GPTBot" or http.user_agent contains "ClaudeBot")
  ```

---

## R3 — Sitemap Missing or Inaccessible

- **Check ID**: `R3`
- **Root Cause**: `orientation_cost`
- **Title**: Generate XML Sitemap and Declare Location in `robots.txt`
- **Description**:
  No valid XML sitemap was discoverable in `robots.txt` directives or at standard paths (`/sitemap.xml`).
  Without a sitemap, crawlers cannot determine site hierarchy, last modification times, or newly published URLs.
  Generate an automated sitemap and declare its canonical URL in `robots.txt`.
- **Code Snippet**:
  ```text
  # Append to robots.txt:
  Sitemap: {base_url}/sitemap.xml
  ```

---

## R4 — noindex Directives on Substantive Pages

- **Check ID**: `R4`
- **Root Cause**: `orientation_cost`
- **Title**: Remove Accidental `noindex` Directive from Substantive Page
- **Description**:
  The substantive page `{page_url}` specifies a `noindex` directive via `{source}` (`{directive_value}`).
  This prevents search engines and AI assistants from indexing this key landing or product page.
  Remove the `noindex` directive unless this page is intentionally restricted from public discovery.
- **Code Snippet**:
  ```html
  <!-- Remove or update robots meta tag: -->
  <meta name="robots" content="index, follow">
  ```

---

## R5 — Canonical / OG Conflict or 4xx Internal Links

- **Check ID**: `R5`
- **Root Cause**: `identity_irresolution`
- **Title**: Resolve Canonical Link Mismatches or Broken Internal Hyperlinks
- **Description**:
  {r5_detail_description}
  Ensure that `<link rel="canonical">` points to the authoritative URL, matches `og:url`, and that all internal
  hyperlinks return HTTP 200 responses.
- **Code Snippet**:
  ```html
  <!-- Ensure canonical and og:url match: -->
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:url" content="{canonical_url}">
  ```

---

## D1 — JS-Render Gap

- **Check ID**: `D1`
- **Root Cause**: `representation_gap`
- **Title**: Implement Server-Side Rendering (SSR) or Prerendering for Dynamic Content
- **Description**:
  Visible text divergence between raw HTML ({raw_word_count} words) and rendered DOM ({rendered_word_count} words)
  is {missing_word_ratio}% ({missing_word_count} missing words).
  Critical post-render facts such as "{post_render_fact_preview}" are invisible to fetchers that do not execute client JS.
  Implement server-side rendering (SSR), incremental static regeneration (ISR), or edge prerendering for primary content.
- **Code Snippet**:
  ```javascript
  // For Next.js / Nuxt / SvelteKit: Ensure primary content renders on server
  export async function getServerSideProps() {
    // Fetch and return initial content for hydration
    return { props: { data } };
  }
  ```

---

## D2 — Content Locked in Non-Text Form

- **Check ID**: `D2`
- **Root Cause**: `representation_gap`
- **Title**: Add Descriptive `alt` Text to Prominent Visual Content
- **Description**:
  Image `{img_src}` located in `{container_tag}` lacks descriptive `alt` text.
  Because the image is placed in a prominent content section without nearby caption text, assistive devices
  and multi-modal LLM indexers cannot discern its factual contents.
  Add concise, descriptive `alt` text conveying the information depicted in the image.
- **Code Snippet**:
  ```html
  <!-- Update image element: -->
  <img src="{img_src}" alt="Descriptive explanation of the diagram, product, or showcase item">
  ```

---

## E2 — Invalid / Contradicting Structured Data

- **Check ID**: `E2`
- **Root Cause**: `corroboration_deficit`
- **Title**: Reconcile Structured Data Discrepancies with Visible Page Content
- **Description**:
  {e2_detail_description}
  Contradictions between structured markup and visible page content cause search assistants to distrust or misquote
  your site. Update the `{syntax}` `{schema_type}` record so that property `{field}` matches the visible value.
- **Code Snippet**:
  ```json
  // In your JSON-LD block:
  {
    "@context": "https://schema.org",
    "@type": "{schema_type}",
    "{field}": "{corrected_value}"
  }
  ```

---

## E3 — Quotability Gap

- **Check ID**: `E3`
- **Root Cause**: `statement_implicitness`
- **Title**: Provide Self-Contained, Quotable Answers to Canonical Questions
- **Description**:
  No single passage across the site self-containedly answers the canonical {archetype} question:
  "{canonical_question}".
  Failure reason: {failure_reason}
  When AI search engines and conversational assistants summarize your site, they require concise, factual
  paragraphs that can be quoted directly without requiring multi-page extrapolation.
  Add a dedicated, fact-dense section addressing this question directly.
- **Code Snippet**:
  ```html
  <!-- Add self-contained answer block to relevant page: -->
  <section class="faq-item">
    <h3>{canonical_question}</h3>
    <p>Direct, factual statement specifying exact terms, numbers, policies, or capabilities.</p>
  </section>
  ```

---

## D3 — Semantic Structure Absent

- **Check ID**: `D3`
- **Root Cause**: `representation_gap`
- **Title**: Structure Document Outlines with Semantic Landmarks and Heading Hierarchy
- **Description**:
  Substantive page content is missing core HTML5 landmarks (<main> or role="main"), lacks an <h1> heading,
  or exhibits broken heading hierarchy. Autonomous web agents and summarizers rely on semantic landmarks
  to isolate primary content from navigation boilerplate and to establish document entity hierarchy.
  Add an <h1> heading, wrap primary content inside <main>, and ensure headings descend sequentially without skipping levels.
- **Code Snippet**:
  ```html
  <main>
    <h1>Primary Page Topic</h1>
    <section>
      <h2>Section Overview</h2>
      <h3>Detailed Subsection</h3>
    </section>
  </main>
  ```

---

## E1 — Missing Structured Data for Inferred Archetype

- **Check ID**: `E1`
- **Root Cause**: `corroboration_deficit`
- **Title**: Add Schema.org Structured Data Matching Site Archetype
- **Description**:
  The site was classified under an established archetype, but diagnostic pages lack matching structured data markup.
  AI search engines and assistants rely on schema.org entities to extract products, articles, or services
  with high factual confidence. Add JSON-LD schema blocks to diagnostic pages to enable rich answers and knowledge panel retrieval.
- **Code Snippet**:
  ```html
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Product Name",
    "description": "Product summary for AI indexers"
  }
  </script>
  ```

---

## E4 — Duplicate or Missing Titles and Meta Descriptions

- **Check ID**: `E4`
- **Root Cause**: `representation_gap`
- **Title**: Provide Unique, Descriptive Titles and Meta Descriptions
- **Description**:
  Substantive pages lack unique <title> tags or <meta name="description"> attributes, or share duplicate
  metadata across distinct URLs. Search engines and AI retrieval agents use title tags and meta descriptions
  as primary identifiers for query matching, snippet generation, and vector clustering.
  Ensure every substantive URL has a distinct, descriptive title and informative meta description.
- **Code Snippet**:
  ```html
  <head>
    <title>Distinct Page Topic | Brand Name</title>
    <meta name="description" content="A concise, factual 150-160 character summary of the specific content on this page.">
  </head>
  ```

---

## T1 — Staleness and Undated Content

- **Check ID**: `T1`
- **Root Cause**: `temporal_decay`
- **Title**: Update Stale Time-Sensitive Content and Add Temporal Anchors
- **Description**:
  Time-sensitive pages reference outdated temporal markers (such as obsolete pricing years, expired roadmaps, or historical 'as of' claims), or substantive pages lack any publication or modification timestamps. AI search agents verify freshness before recommending commercial terms. Update time-sensitive claims to reflect current terms, and supply ISO timestamps via JSON-LD dateModified or visible last-updated dates.
- **Code Snippet**:
  ```html
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "datePublished": "2026-01-15T00:00:00Z",
    "dateModified": "2026-09-01T12:00:00Z"
  }
  </script>
  ```

---

## T2 — Internal Inconsistency

- **Check ID**: `T2`
- **Root Cause**: `corroboration_deficit`
- **Title**: Harmonize Contradictory Factual Assertions Across Pages
- **Description**:
  Different pages on the domain assert conflicting factual values for identical entity attributes (such as contradictory phone numbers, divergent physical addresses, or widely conflicting customer proof metrics). Autonomous agents verifying entity credibility encounter conflicting corroboration and penalize factual reliability. Audit and harmonize repeated facts into a single canonical source of truth across all templates.
- **Code Snippet**:
  ```html
  <footer>
    <p>Contact Support: <a href="tel:+15551234567">(555) 123-4567</a></p>
    <address>100 Canonical Blvd, Suite 200, San Francisco, CA</address>
  </footer>
  ```

---

## T3 — Entity Ambiguity

- **Check ID**: `T3`
- **Root Cause**: `identity_irresolution`
- **Title**: Disambiguate Brand Identity with Schema.org sameAs Links
- **Description**:
  The site's brand exhibits entity ambiguity caused by a common dictionary brand name, absence of authoritative Schema.org sameAs registry links, or lack of category and geographic context on the homepage. AI answer engines and knowledge graphs struggle to disambiguate common names. Declare Schema.org Organization markup with verified sameAs URLs pointing to authoritative registries (Wikidata, Crunchbase, LinkedIn, Wikipedia).
- **Code Snippet**:
  ```html
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Brand Name",
    "url": "https://example.com",
    "sameAs": [
      "https://www.wikidata.org/wiki/...",
      "https://www.linkedin.com/company/..."
    ]
  }
  </script>
  ```

---

## T4 — Missing About, Contact, or Authorship Presence

- **Check ID**: `T4`
- **Root Cause**: `corroboration_deficit`
- **Title**: Provide Discoverable About, Contact, and Authorship Attribution
- **Description**:
  The website lacks discoverable contact channels (no contact page, mailto link, or telephone contact), provides no organizational About overview, or publishes editorial articles without author attribution. Autonomous research agents and AI assistants verify business legitimacy and E-E-A-T credentials before recommending entities. Add an explicit /contact page with reachable communication channels, an /about company overview, and clear author bylines on editorial content.
- **Code Snippet**:
  ```html
  <!-- Canonical Contact & About Navigation -->
  <nav>
    <a href="/about">About Us</a>
    <a href="/contact">Contact Support</a>
  </nav>
  ```


