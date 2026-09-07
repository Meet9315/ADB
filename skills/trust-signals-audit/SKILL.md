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
2. Dynamically determine the evaluation reference year via UTC clock (`datetime.now(timezone.utc).year`) with optional `--reference-year` CLI parameter.
3. Identify time-sensitive contexts (pricing tables/paths, active roadmaps, operational status, explicit `"as of 20XX"` or `"current"` phrases).
4. If a time-sensitive context references a temporal anchor older than the freshness threshold ($\le reference\_year - 2$), emit a `stale_time_sensitive_claim` finding (`medium` severity).
5. Substantive pages ($\ge 80$ words) lacking any temporal anchor are emitted as a separate `undated_content` finding (`low` severity).

#### Explicit Negative-Logic Rules
- **Evergreen Essay Guard**: General articles, essays, technical explainers, and blog posts with old publication dates are NOT flagged for staleness. Evergreen content is valid regardless of publication year.
- **Separation of Undated Content**: A page with no dates at all is NEVER bucketed together with staleness. It is reported under `undated_content` with strictly `low` severity.
- **Dynamic Reference Guard**: The reference date is dynamic UTC calendar year rather than hardcoded, accepting any temporal anchor within the trailing 2 years as fresh.

---

### Check T2 — Internal Inconsistency (`check_t2.py`)

#### Procedure
1. Extract repeated factual instances across all crawled pages:
   - Contact phone numbers with department/role context (`sales`, `support`, `press`, `fax`, `headquarters`, `general`).
   - Physical street addresses and postal locations.
   - Core customer proof metrics (e.g., claimed customer/client counts).
2. Normalize all extracted instances into canonical uniform formats:
   - Phones: strip punctuation and country codes into standard digit sequences.
   - Addresses: normalize street abbreviations (`st`, `ave`, `blvd`, `rd`, `dr`, `ln`, `ste`), whitespace, casing, and unit designations.
3. Diff normalized instances across distinct page URLs:
   - Phone conflict: flag only when differing numbers belong to the SAME department role (or general unsegmented contact) across distinct URLs.
   - Address conflict: compare normalized addresses across distinct URLs, excluding substring/unit extensions where one page simply adds a suite or floor number.
   - Metric conflict: flag when numerical claims diverge by $\ge 2.0\times$ across distinct URLs.

#### Explicit Negative-Logic Rules
- **Phone Formatting Normalization Guard**: Phone punctuation differences (`(555) 123-4567` vs `555.123.4567` vs `+1-555-123-4567`) normalize to identical digits (`5551234567`) and MUST NEVER trigger a conflict finding.
- **Department Role Context Guard**: Distinct phone numbers on a site do NOT conflict if they serve different labeled departments (e.g., Sales vs Support vs Press).
- **Address Substring & Unit Extension Guard**: Standard street abbreviations (`Street` vs `St.`, `Avenue` vs `Ave.`) normalize prior to comparison. Addresses sharing the same street location but differing in suite/unit additions do NOT conflict.
- **Scale Guard for Metrics**: Numerical proof metrics must diverge by at least a factor of $2.0\times$ across distinct URLs before triggering a conflict finding.

---

### Check T3 — Entity Ambiguity (`check_t3.py`)

#### Procedure
1. Evaluate entity ambiguity using observable corpus signals:
   - **Observable Corpus Signals**: Single-word morphology, lack of legal entity suffix (`Inc`, `LLC`, `Corp`), lack of trademark symbols (`™`, `®`), bare/unqualified `<title>` tag, and observable lowercase dictionary word usage in body text.
   - **Missing sameAs Links**: Absence of Schema.org `Organization` or `Corporation` JSON-LD containing authoritative `sameAs` registry links.
   - **Lacks Disambiguating Context**: Homepage text fails to disambiguate industry category or geographic headquarters.
2. Implement the **Strict Prerequisite & Finding-vs-Suggestion Split**:
   - Brand ambiguity (`is_ambiguous_brand == True`) is an absolute prerequisite for a defect finding.
   - When an ambiguous brand stacks with missing `sameAs` or missing category context ($\ge 2$ signals), emit a high-confidence defect finding (`F-T3-001`, `medium` severity).
   - If the brand is NOT ambiguous (distinctive, coined, compound, legally suffixed, or trademarked), missing `sameAs` or sparse category text routes strictly to a **proactive suggestion** (`PROACT-T3-001`), NEVER a defect finding.

#### Explicit Negative-Logic Rules
- **Brand Ambiguity Prerequisite**: A distinctive, compound, or trademarked brand lacking `sameAs` is NOT an entity defect; it only triggers a proactive recommendation.
- **Observable Corpus Grounding**: Brand ambiguity is determined by observable corpus properties (name structure, title qualification, body text usage) rather than static exclusion lists.
- **The Split IS the False-Positive Guard**: The requirement for multiple co-occurring signals with confirmed brand ambiguity prevents penalizing unique or early-stage brands.

---

### Check T4 — Missing About / Contact / Authorship Presence (`check_t4.py`)

#### Procedure
1. Check for About presence across crawled paths, in-page sections (`#about`, `<section id="about">`), and HTML anchor links.
2. Check for Contact presence across paths, `mailto:` links, `tel:` links, phone patterns, and in-page sections.
3. On `news` or `content` archetypes with $\ge 2$ article pages, evaluate editorial authorship attribution across all article pages.

#### Explicit Negative-Logic Rules
- **Authorship Archetype & Ratio Gate**: Evaluated strictly on `news` and `content` archetypes with $\ge 2$ article pages. Flags when $\ge 50\%$ of crawled articles lack author bylines or Schema.org author attribution (allowing occasional editorial briefs while penalizing systemic anonymous publishing).
- **Non-Editorial Archetype Exemption**: Never demand author bylines on SaaS, ecommerce, documentation, or utility pages.
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
