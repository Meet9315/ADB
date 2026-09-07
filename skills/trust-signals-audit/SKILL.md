---
name: trust-signals-audit
description: Audits web corpora for trust, temporal freshness, internal consistency, entity ambiguity, and corroboration presence signals (T1, T2, T3, T4).
---

# Trust Signals Audit Skill Specification (`trust-signals-audit`)

This skill audits a crawled website corpus and Tier-0 audit findings for trust, freshness, and identity-corroboration signals. It is strictly read-only and does not fetch or crawl external resources.

## 1. Overview & Checks Implemented

| Check ID | Check Name | Target Issue | Default Severity | Root Cause |
|---|---|---|---|---|
| **T1** | Staleness & Undated Content | Outdated temporal markers on time-sensitive claims (pricing, roadmaps, status) or substantive unanchored content | `medium` (stale) / `low` (undated) | `temporal_decay` |
| **T2** | Internal Inconsistency | Contradictory factual assertions (phone numbers, addresses, metrics) across distinct pages | `medium` | `corroboration_deficit` |
| **T3** | Entity Ambiguity | Indistinguishable brand name lacking `Organization` `sameAs` links and category/geographic context | `medium` (finding) / proactive suggestion | `identity_irresolution` |
| **T4** | Missing Presence | Absence of discoverable About, Contact, or article Authorship corroboration | `medium` (contact) / `low` (about/author) | `corroboration_deficit` |

---

## 2. Inputs and Operational Constraints

### Inputs
| Parameter | Type | Required | Description |
|---|---|---|---|
| `corpus_dir` | Directory Path | Yes | Path to crawled page subdirectories containing `raw.html`, `text.txt`, and `meta.json`. |
| `--manifest` | File Path | No | Optional path to `crawl_manifest.json` containing site metadata and crawl inventory. |

### Operational Constraints
- **Read-Only**: The skill never issues network requests. It operates strictly over local files produced during acquisition.
- **Substantive Content Threshold**: Pages with visible word count $< 80$ are excluded from text and temporal checks.
- **Deterministic Finding IDs**: Local candidate IDs follow sequential naming (`F-T1-001`, `F-T2-001`, etc.).

---

## 3. Detailed Check Procedures & Negative-Logic Rules

### Check T1 — Staleness & Undated Content (`check_t1.py`)

#### Procedure
1. Inspect page URLs, HTML metadata, JSON-LD (`dateModified`, `datePublished`), copyright notices, and visible text for temporal markers.
2. Identify time-sensitive contexts (pricing tables/paths, active roadmaps, operational status, explicit `"as of 20XX"` or `"current"` phrases).
3. If a time-sensitive context references a temporal anchor older than the freshness threshold ($\le 2024$, given reference year $2026$), emit a `stale_time_sensitive_claim` finding (`medium` severity).
4. Substantive pages ($\ge 80$ words) lacking any temporal anchor are emitted as a separate `undated_content` finding (`low` severity).

#### Explicit Negative-Logic Rules
- **Evergreen Essay Guard**: General articles, essays, technical explainers, and blog posts with old publication dates are NOT flagged for staleness. Evergreen content is valid regardless of publication year.
- **Separation of Undated Content**: A page with no dates at all is NEVER bucketed together with staleness. It is reported under `undated_content` with strictly `low` severity.
- **Recent Reference Guard**: Any temporal anchor within the last two years ($> 2024$) is accepted as fresh.

---

### Check T2 — Internal Inconsistency (`check_t2.py`)

#### Procedure
1. Extract repeated factual instances across all crawled pages:
   - Contact phone numbers (US and international formats).
   - Physical street addresses and postal locations.
   - Core customer proof metrics (e.g., claimed customer/client counts).
2. Normalize all extracted instances into canonical uniform formats before comparison.
3. Compare normalized values across distinct page URLs. If two distinct pages assert irreconcilable facts for the same entity property, emit a `T2` finding.

#### Explicit Negative-Logic Rules
- **Phone Formatting Normalization Guard**: Phone punctuation differences (`(555) 123-4567` vs `555.123.4567` vs `+1-555-123-4567`) normalize to identical digits (`5551234567`) and MUST NEVER trigger a conflict finding.
- **Address Normalization Guard**: Standard street abbreviations (`Street` vs `St.`, `Avenue` vs `Ave.`, `Suite` vs `Ste.`) and casing variations normalize prior to comparison.
- **Different Contexts Guard**: Multiple distinct phone numbers on a site do NOT conflict if they serve different departments or distinct branch locations.
- **Scale Guard for Metrics**: Numerical proof metrics must diverge by at least a factor of $2.0\times$ across distinct URLs before triggering a conflict finding.

---

### Check T3 — Entity Ambiguity (`check_t3.py`)

#### Procedure
1. Evaluate three independent ambiguity signals on the homepage and site corpus:
   - **Signal 1 (Common Brand Name)**: Single-word dictionary brand name (e.g., *Summit*, *Apex*, *Pulse*, *Nova*) prone to entity collisions.
   - **Signal 2 (Missing sameAs Links)**: Absence of Schema.org `Organization` or `Corporation` JSON-LD containing authoritative `sameAs` registry links (Wikidata, Crunchbase, LinkedIn, Wikipedia).
   - **Signal 3 (Lacks Context)**: Homepage text fails to disambiguate the industry category or geographic headquarters.
2. Implement the **Finding-vs-Suggestion Split**:
   - If $\ge 2$ signals stack together: Emit a high-confidence defect finding (`confidence: 0.85`, `medium` severity).
   - If only $1$ signal is present: Route as a **proactive suggestion**, NOT a defect finding.

#### Explicit Negative-Logic Rules
- **Signal Stacking Requirement**: Never report entity ambiguity as a defect finding based on a single weak signal (e.g. distinctive brand name that merely lacks `sameAs`).
- **The Split IS the False-Positive Guard**: The requirement for multiple co-occurring signals prevents penalizing unique or early-stage brands that have clear homepage context.

---

### Check T4 — Missing About / Contact / Authorship Presence (`check_t4.py`)

#### Procedure
1. Check for About presence across crawled paths, in-page sections (`#about`, `<section id="about">`), and HTML anchor links.
2. Check for Contact presence across paths, `mailto:` links, `tel:` links, phone patterns, and in-page sections.
3. On `news` or `content` archetypes with article pages, check for author bylines and Schema.org `author` properties.

#### Explicit Negative-Logic Rules
- **Authorship Archetype Gate**: Never demand author bylines on SaaS, ecommerce, documentation, or utility pages.
- **Uncrawled Anchor Guard**: If an `/about` or `/contact` link exists in crawled HTML anchors (`<a href="...">`), presence is considered satisfied even if crawl budget prevented downloading the target page.
- **Single-Page Site Guard**: Single-page sites with in-page `#about` or `#contact` sections satisfy presence requirements.

---

## 4. Hardened Candidate Finding Contract

All findings emitted by this skill conform strictly to the project's Pydantic `CandidateFinding` contract:

```json
{
  "id": "F-T1-001",
  "check_id": "T1",
  "page_url": "https://example.com/pricing",
  "root_cause": "temporal_decay",
  "evidence": {
    "type": "stale_time_sensitive_claim",
    "context_type": "pricing_page",
    "stale_marker": "as of 2022",
    "marker_year": 2022,
    "reference_year": 2026,
    "age_years": 4
  },
  "raw_severity_class": "medium",
  "confidence": 0.90,
  "mechanism": "Pricing page references outdated temporal markers ('as of 2022'). AI shopping assistants distrust stale pricing.",
  "false_positive_guard": "Time-sensitive gate: evaluated strictly for pricing; evergreen articles excluded.",
  "verification_method": "curl -sL https://example.com/pricing | grep -iE 'as of|pricing'"
}
```
