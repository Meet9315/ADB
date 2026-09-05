# PROJECT CONSTITUTION — Agent Skill Marketplace (Adobe University Hackathon 2026, Round 3)

> **This file is build guidance, not a required marketplace skill and does not replace the agentskills.io artifact requirements.**
> Every Antigravity task must read this file first and treat it as authoritative.

---

We are building a submission for the Adobe University Hackathon 2026, Round 3: an
Agent Skill Marketplace that audits any website for AI-discoverability and
on-site-engagement problems, in the agentskills.io SKILL.md format.

CRITICAL CONTEXT: the judges evaluate the marketplace artifact itself — the SKILL.md
instructions, scripts, and composition — not a single demo report. Every design
decision must optimize for a judge reading the skill files as a technical
specification, not just for a report looking good on one test run.

## HARD RULES — apply to every skill, every script, every finding, with no exceptions:

**Rule 1 — Evidence is never invented.** Every fact in a finding must originate from a
script's output (a count, URL, snippet, diff, or parsed value). Any LLM/agent
reasoning step may interpret that evidence but must never assert a fact about the
site that isn't traceable to a literal value a script produced.

**Rule 2 — Every finding must state a mechanism, not just a verdict.** "No JSON-LD" is
not a finding. "No JSON-LD on product pages, therefore an assistant fetching this
page cannot extract price/availability as a structured fact and will omit or
hallucinate it" is a finding.

**Rule 3 — Every check must state, in its own SKILL.md text, the specific condition(s)
under which it must NOT fire.** Negative logic is required content, not optional
caution.

**Rule 4 — Every finding must be falsifiable:** it must include a verification method
(e.g. an exact curl command, a URL to view-source on, a specific field to inspect)
that a stranger could execute in under two minutes.

## THE HARDENED FINDING CONTRACT

Every analysis skill emits candidates in exactly this shape (add fields if useful, never remove required ones):

```json
{
  "id": "F-XXX",
  "check_id": "<e.g. D1>",
  "page_url": "...",
  "root_cause": "<one of: representation_gap | statement_implicitness |
                  identity_irresolution | corroboration_deficit |
                  temporal_decay | orientation_cost>",
  "evidence": { "type": "...", "...concrete values/snippets..." : "..." },
  "raw_severity_class": "critical|high|medium|low",
  "confidence": 0.0-1.0,
  "mechanism": "<diagnostic mechanism: why this evidence indicates a real problem>",
  "false_positive_guard": "<what was checked to rule out a false positive here, as data, not just a comment>",
  "verification_method": "<the exact, concrete way a stranger verifies this in <2 minutes>"
}
```

Only the orchestrator turns candidates into final report findings (dedupe,
root-cause merge, severity scoring). Analysis skills never do this themselves.

## SCOPE / GUARDRAILS (from the official rules, non-negotiable)

- **Recommend-only.** No skill ever modifies a live website, ever performs a
  destructive, authenticated, or rate-abusing action. Read-only, sandboxed.
- **Respect robots.txt.**
- **Runtime target:** p95 under 4 minutes; 5 minutes is the absolute hard ceiling.
  Design toward 4 minutes, treat 5 as a wall you never want to approach.
- **Submission zip** must stay under 50 MB, no pre-trained model weights bundled.
- **Provider-neutral** (agentskills.io spec) — never depend on a feature specific to
  whatever tool we're using to build it right now.

## BUILD ORDER — strict, tiered implementation plan

Do not build anything outside the current tier unless explicitly told to in the
session's prompt.

### Tier 0 core (build first, must be fully solid before anything else)

- **Checks:** R1, R2, R3, R4, R5, D1, D2, E2, E3 (9 checks total)
- **Plus:** basic archetype inference, the orchestrator, the recommendation engine
- **Skills:** `audit-orchestrator`, `site-acquisition`, `machine-readability-audit`

### Tier 0 stretch (optional, only after Tier 0 core passes its checkpoint)

- **Checks:** D3, E1, E4

### Tier 1 (only after the checkpoint passes)

- **Checks:** T1, T2, T3, T4
- **Skill:** `trust-signals-audit`

### Tier 2 (only after Tier 1 is stable)

- **Checks:** G1, G2, G3, G4
- **Skill:** `engagement-audit`

### Explicitly out of scope — do not build even if it seems easy

- Live-querying ChatGPT/Perplexity for "AI visibility"
- Backlink/domain-authority analysis
- Web-wide external corroboration crawling
- Full Lighthouse runs
- Keyword/ranking analysis

## ANTIGRAVITY EXECUTION PROTOCOL — apply to every subsequent prompt

- Read `PROJECT_CONSTITUTION.md` and the current repository state before editing.
- Work ONLY on the scope of the current prompt. Do not opportunistically add later-tier
  checks, architecture, dependencies, or speculative features.
- Preserve working behavior unless the current task explicitly requires changing it.
- Before declaring completion, run the tests/validation required by the prompt and
  report the actual commands, pass/fail result, timing, and important stderr/output.
- Never claim a file, test, benchmark, or integration exists unless it was actually
  created or executed in the current repository.
- Do not leave placeholder detection logic, TODO-based acceptance criteria, fake
  fixtures, or fabricated metrics in a claimed-complete deliverable.
- If blocked, stop at the blocker, explain the exact cause, preserve the current
  working state, and state the smallest fix required. Do not silently weaken a
  safety, accuracy, or scope constraint.
- At the end of each task, report: files changed, tests run, measured results,
  known limitations, and whether the next prompt is safe to start.
