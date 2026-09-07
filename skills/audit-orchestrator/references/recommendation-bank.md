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
