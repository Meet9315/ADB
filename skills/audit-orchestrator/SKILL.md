---
name: audit-orchestrator
description: >
  Orchestrates an end-to-end AI-discoverability audit of any website. Coordinates site-acquisition
  (crawl & render), runs analysis checks, infers archetype, deduplicates findings, scores severities,
  and compiles a validated final report. Emits deterministic, Pydantic-validated audit reports.
license: MIT
compatibility: Requires Python 3.10+. Coordinates local and network tasks.
metadata:
  tier: "0"
  role: entrypoint
---

## When to use

Run `audit-orchestrator` as the primary entrypoint for auditing any website for AI discoverability
and engagement problems. It coordinates:
1. **Acquisition**: `site-acquisition/crawl.py` (robots-compliant crawler) and `render.py` (Playwright renderer).
2. **Archetype Inference**: `machine-readability-audit/archetype.py`.
3. **Analysis Checks**:
   - Reach layer: `reach_checks.py` (R1, R2, R3, R5).
   - Machine readability layer: `check_noindex.py` (R4), `check_d1.py` (D1), `check_d2.py` (D2),
     `check_e2.py` (E2), and `check_e3.py` (E3).
4. **Synthesis**: Deterministic deduplication, root-cause clustering, recommendation generation,
   and final report validation via Pydantic.

---

## Inputs & CLI Commands

The orchestrator exposes a thin **Typer CLI** in `scripts/audit.py`:

```bash
# Run a full end-to-end audit on a domain:
python scripts/audit.py run example.com --output report.json

# Merge and deduplicate raw candidate finding JSON files:
python scripts/audit.py merge candidates.json --output merged.json

# Validate a candidate finding or final report against Pydantic models:
python scripts/audit.py validate report.json
```

---

## Procedure & Architecture

### 1. Canonical Finding & Report Models (`scripts/models.py`)

Backed by **Pydantic v2** (`pydantic==2.12.5`):
- `CandidateFinding`: Strictly enforces the Hardened Finding Contract (all 10 fields required).
- `SuggestedAction`: Structured recommendation (`id`, `title`, `description`, `code_snippet`, `priority`, `linked_findings`, `is_proactive`). Non-proactive recommendations MUST link to at least one finding ID; orphan recommendations are rejected.
- `FinalFinding`: Enriched finding with `final_severity`, `suggested_action` (validated bidirectional link: finding ID must be in `suggested_action.linked_findings`), `deduped_occurrences`, and `affected_urls`.
- `SummaryCounts`: Invariant-checked summary metrics (`total_findings`, `by_severity`, `by_root_cause`, `by_check_id`).
- `AuditMetadata`: Target domain, base URL, inferred archetype, timestamps, and budget tracking flags.
- `FinalReport`: Complete validated audit schema including consolidated `recommendations` and `proactive_recommendations` with deterministic JSON serialization (`to_deterministic_json()`).

### 2. Strict Contract Linting

Pydantic validators strictly reject incomplete candidates:
- Rejects missing, empty, or whitespace-only strings for `root_cause`, `mechanism`, `false_positive_guard`,
  `verification_method`, and `id`.
- Rejects case-insensitive placeholder values (`"TBD"`, `"TODO"`, `"N/A"`, `"not available"`, `"none"`, `"placeholder"`)
  in all top-level contract fields AND recursively inside any string-valued sub-fields of `evidence` (e.g. `snippet`, `value`).
- Rejects empty `evidence` dictionaries.
- **Never silently repairs or fabricates missing evidence**: invalid candidates raise validation errors immediately.

### 3. Finding Deduplication & Severity Scoring (`scripts/merge_findings.py`)

- **Deduplication**: Clusters candidate findings sharing a deterministic signature:
  - Consolidates duplicate issues occurring across multiple pages into a single `FinalFinding`.
  - Records all affected page paths in `affected_urls` and tracks `deduped_occurrences`.
- **Severity Scoring**:
  - Calibrates final severity from `raw_severity_class`, `confidence`, and cluster occurrence frequency.
  - Escalate high-frequency defects (e.g. site-wide missing alt text or repeated noindex headers).
  - Demotes severity if confidence is under 0.60.
- **Action Instantiation**: Links each finding to an actionable recommendation from `references/recommendation-bank.md`,
  parameterized strictly using the finding's concrete evidence.

### 4. Recommendation Banks & Bidirectional Traceability

- **`references/recommendation-bank.md`**: Contains deterministic remediation templates for all implemented check IDs
  (`R1`, `R2`, `R3`, `R4`, `R5`, `D1`, `D2`, `E2`, `E3`).
  - **Traceability**: Every remediation recommendation explicitly stores `linked_findings: List[str]` pointing to the findings it fixes.
  - **Orphan Rejection**: Non-proactive recommendations with empty `linked_findings`, placeholder IDs, or referencing non-existent finding IDs are strictly rejected.
- **`references/proactive-bank.md`**: Provides archetype-conditioned proactive improvements
  (e.g., `/llms.txt`, structured return policies, OpenAPI specs) flagged with `is_proactive=True` and added *only* when the topic is not already covered by an existing audit finding.

### 5. Report Assembly & Invariant Verification (`scripts/validate_report.py`)

Validates report-level invariants:
- Zero duplicate finding IDs in the final report.
- `summary.total_findings == len(findings) == sum(summary.by_severity.values()) == sum(summary.by_root_cause.values())`.
- Full traceability across all recommendations in `report.recommendations`: all referenced finding IDs must exist in `report.findings`.
- Serializes deterministically (sorted keys, stable indentation, UTF-8 encoding) ensuring byte-identical outputs.

### 6. Budget Tracking & Partial Audits

- The orchestrator inherits the wall-clock budget tracker from site-acquisition.
- If the remaining time approaches the hard deadline (5 minutes / 300s):
  - Sets `partial_audit = true` in `AuditMetadata`.
  - Records a human-readable `partial_audit_reason`.
  - Halts optional deep rendering or additional checks to guarantee safe termination under budget.

---

## Negative Logic & Guardrails

The orchestrator enforces the following explicit non-goals:
- **Never invent or repair missing evidence**: If an analysis skill emits a candidate with empty evidence or a placeholder
  like `"TBD"`, the orchestrator rejects the finding rather than guessing or inserting defaults.
- **No duplicate proactive suggestions**: If an `E3` finding flags missing return policy details, the proactive
  return policy recommendation is omitted to prevent redundant advice.
- **No nondeterminism**: Iterating over clusters, dictionary keys, and JSON serialization uses sorted keys.
  Two runs on the same input produce identical byte sequences.
- **No destructive actions**: All network interactions remain strictly read-only and respect `robots.txt`.

---

## Output Contract

The orchestrator produces a `FinalReport` JSON matching the schema below:

```json
{
  "schema_version": "1.0",
  "audit_metadata": {
    "target_domain": "example.com",
    "base_url": "https://example.com",
    "archetype": "saas",
    "is_tiny_site": false,
    "started_at": "2026-09-07T00:00:00Z",
    "completed_at": "2026-09-07T00:01:45Z",
    "elapsed_s": 105.2,
    "partial_audit": false,
    "partial_audit_reason": null
  },
  "summary": {
    "total_findings": 3,
    "by_severity": { "critical": 1, "high": 1, "medium": 1, "low": 0 },
    "by_root_cause": {
      "representation_gap": 1,
      "statement_implicitness": 1,
      "corroboration_deficit": 1
    },
    "by_check_id": { "D1": 1, "E2": 1, "E3": 1 }
  },
  "findings": [
    {
      "id": "FINDING-001",
      "check_id": "D1",
      "page_url": "https://example.com/",
      "root_cause": "representation_gap",
      "evidence": { "raw_word_count": 12, "rendered_word_count": 450, "missing_word_count": 438 },
      "raw_severity_class": "critical",
      "final_severity": "critical",
      "confidence": 0.92,
      "mechanism": "...",
      "false_positive_guard": "...",
      "verification_method": "...",
      "suggested_action": {
        "id": "REC-001",
        "title": "Implement Server-Side Rendering (SSR)",
        "description": "...",
        "code_snippet": "...",
        "priority": "critical",
        "linked_findings": ["FINDING-001"],
        "is_proactive": false
      },
      "deduped_occurrences": 1,
      "affected_urls": ["https://example.com/"]
    }
  ],
  "recommendations": [
    {
      "id": "REC-001",
      "title": "Implement Server-Side Rendering (SSR)",
      "description": "...",
      "code_snippet": "...",
      "priority": "critical",
      "linked_findings": ["FINDING-001"],
      "is_proactive": false
    }
  ],
  "proactive_recommendations": [
    {
      "id": "PROACT-001",
      "title": "Deploy an /llms.txt Machine-Readable Context File",
      "description": "...",
      "code_snippet": "...",
      "priority": "medium",
      "linked_findings": [],
      "is_proactive": true
    }
  ]
}
```
