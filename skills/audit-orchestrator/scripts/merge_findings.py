#!/usr/bin/env python3
"""
merge_findings.py — Deterministic deduplication, root-cause merging, and severity scoring.

Pydantic validation strictly rejects incomplete or placeholder candidates rather than
inventing or repairing missing evidence.
Instantiates actionable remediation suggestions strictly from the finding's concrete evidence.

Usage:
    python merge_findings.py <candidates.json> [--output <merged.json>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from models import CandidateFinding, FinalFinding, SuggestedAction  # noqa: E402


def _make_signature(c: CandidateFinding) -> Tuple[str, ...]:
    """Derive a deterministic grouping signature for deduplication."""
    ev = c.evidence
    cid = c.check_id

    if cid == "R1":
        agents = str(sorted(ev.get("blocked_agents", [])))
        return (cid, agents)
    elif cid == "R2":
        return (cid, str(ev.get("status_code", "")), str(ev.get("challenge_type", "")))
    elif cid == "R3":
        return (cid, str(ev.get("type", "")))
    elif cid == "R4":
        return (cid, str(ev.get("source", "")), str(ev.get("directive_value", "")), c.page_url)
    elif cid == "R5":
        return (cid, str(ev.get("type", "")), str(ev.get("canonical_url", c.page_url)))
    elif cid == "D1":
        return (cid, c.page_url)
    elif cid == "D2":
        return (cid, str(ev.get("img_src", "")), c.page_url)
    elif cid == "E2":
        return (cid, c.page_url, str(ev.get("field", "")), str(ev.get("structured_value", "")))
    elif cid == "E3":
        return (cid, str(ev.get("canonical_question", "")))
    else:
        return (cid, c.root_cause, c.page_url)


def _compute_final_severity(raw_severity: str, confidence: float, occurrence_count: int) -> str:
    """Deterministic severity calibration based on confidence and frequency."""
    if confidence < 0.60:
        if raw_severity == "critical":
            return "high"
        elif raw_severity == "high":
            return "medium"
        return raw_severity

    # High frequency escalation
    if raw_severity == "high" and occurrence_count >= 5:
        return "critical"
    if raw_severity == "medium" and occurrence_count >= 10:
        return "high"

    return raw_severity


def _instantiate_recommendation(c: CandidateFinding, finding_id: str = "") -> SuggestedAction:
    """Instantiate a SuggestedAction strictly from the candidate's concrete evidence."""
    ev = c.evidence
    cid = c.check_id
    linked_findings = [finding_id] if finding_id else [c.id]

    if cid == "R1":
        blocked = ", ".join(ev.get("blocked_agents", ["AI Crawlers"]))
        directive = ev.get("directive_sample", "Disallow: /")
        is_training_only = ev.get("is_training_only", False)
        training_note = (
            "This rule blocks training-only scrapers, leaving assistant discovery intact."
            if is_training_only else
            "This rule blocks assistant crawlers, entirely preventing search discovery."
        )
        return SuggestedAction(
            title="Update robots.txt to Permit Discovery-Oriented AI Agents",
            description=(
                f"robots.txt disallows AI agents ({blocked}) via directive '{directive}'. {training_note} "
                "Permit discovery bots (GPTBot, ClaudeBot, PerplexityBot) while restricting training scrapers."
            ),
            code_snippet=(
                "# Recommended robots.txt configuration:\n"
                "User-agent: GPTBot\nAllow: /\n\n"
                "User-agent: ClaudeBot\nAllow: /\n\n"
                "User-agent: PerplexityBot\nAllow: /"
            ),
            priority="critical" if not is_training_only else "medium",
            linked_findings=linked_findings,
        )

    elif cid == "R2":
        code = ev.get("status_code", 403)
        ctype = ev.get("challenge_type", "WAF Block")
        return SuggestedAction(
            title="Configure Edge Security to Allow Verified Search and AI Crawlers",
            description=(
                f"Security gateway returned HTTP {code} ({ctype}) when accessed by crawlers. "
                "Configure WAF allowlists for verified search engine and AI agent user-agents."
            ),
            code_snippet=(
                "# WAF Bypass Rule Example:\n"
                "Action: Allow\n"
                "Expression: (cf.client.bot or http.user_agent contains 'GPTBot')"
            ),
            priority="critical",
            linked_findings=linked_findings,
        )

    elif cid == "R3":
        return SuggestedAction(
            title="Generate and Publish an XML Sitemap",
            description=(
                "No XML sitemap was discoverable in robots.txt or standard paths. "
                "Publish an XML sitemap listing canonical URLs and declare it in robots.txt."
            ),
            code_snippet=(
                "# Append to robots.txt:\n"
                f"Sitemap: {c.page_url.rstrip('/')}/sitemap.xml" if c.page_url.startswith("http") else "# Append to robots.txt:\nSitemap: <base_url>/sitemap.xml"
            ),
            priority="high",
            linked_findings=linked_findings,
        )

    elif cid == "R4":
        source = ev.get("source", "meta robots tag")
        dval = ev.get("directive_value", "noindex")
        return SuggestedAction(
            title="Remove noindex Directives from Substantive Public Pages",
            description=(
                f"Page {c.page_url} has a '{dval}' directive in {source}. "
                "Remove this directive to permit indexing by search engines and AI assistants."
            ),
            code_snippet='<meta name="robots" content="index, follow">',
            priority="high",
            linked_findings=linked_findings,
        )

    elif cid == "R5":
        etype = ev.get("type", "canonical_conflict")
        if etype == "canonical_og_conflict":
            canon = ev.get("canonical_url", "")
            og = ev.get("og_url", "")
            return SuggestedAction(
                title="Align rel=canonical with OpenGraph og:url",
                description=(
                    f"Page {c.page_url} specifies canonical '{canon}' which conflicts with og:url '{og}'. "
                    "Ensure both metadata tags point to the single authoritative URL."
                ),
                code_snippet=(
                    f'<link rel="canonical" href="{canon}">\n'
                    f'<meta property="og:url" content="{canon}">'
                ),
                priority="medium",
                linked_findings=linked_findings,
            )
        else:
            broken = ev.get("broken_url", "")
            status = ev.get("status_code", 404)
            return SuggestedAction(
                title="Fix Broken Internal Link Returning 4xx Status",
                description=(
                    f"Internal link to '{broken}' returned HTTP {status}. "
                    "Update or remove dead hyperlinks to preserve crawler budget."
                ),
                code_snippet=None,
                priority="medium",
                linked_findings=linked_findings,
            )

    elif cid == "D1":
        raw_words = ev.get("raw_word_count", 0)
        rend_words = ev.get("rendered_word_count", 0)
        missing = ev.get("missing_word_count", 0)
        ratio = ev.get("missing_word_ratio", 0.0)
        fact = ev.get("post_render_fact", "Primary content")
        return SuggestedAction(
            title="Implement Server-Side Rendering (SSR) for Dynamic Content",
            description=(
                f"Raw HTML contains only {raw_words} words, while rendered DOM contains {rend_words} words "
                f"({round(ratio * 100, 1)}% missing, {missing} words omitted), including facts like "
                f"'{fact[:80]}...'. Implement SSR or static prerendering so fetchers receive full text."
            ),
            code_snippet=(
                "// Ensure critical content is rendered on the server during build or request\n"
                "export async function getServerSideProps() {\n"
                "  return { props: { content } };\n"
                "}"
            ),
            priority="critical" if ratio > 0.70 else "high",
            linked_findings=linked_findings,
        )

    elif cid == "D2":
        img = ev.get("img_src", "image")
        tag = ev.get("container_tag", "section")
        return SuggestedAction(
            title="Provide Descriptive alt Text on Content-Bearing Images",
            description=(
                f"Content image '{img}' in <{tag}> lacks descriptive alt text. "
                "Add meaningful alt text describing the visual data, product, or diagram."
            ),
            code_snippet=f'<img src="{img}" alt="Detailed description of the content depicted in this image">',
            priority="high",
            linked_findings=linked_findings,
        )

    elif cid == "E2":
        field = ev.get("field", "property")
        sval = ev.get("structured_value", "")
        vvals = ev.get("visible_values", [])
        syntax = ev.get("syntax", "json-ld")
        stype = ev.get("schema_type", "Product")
        return SuggestedAction(
            title="Reconcile Structured Data Discrepancy with Visible Content",
            description=(
                f"{syntax} {stype} declares {field}='{sval}', but visible page text asserts {vvals}. "
                "Update the structured data so machine-readable values agree with visible facts."
            ),
            code_snippet=(
                f"// In {syntax} {stype} markup:\n"
                f'"{field}": "{vvals[0] if vvals else sval}"'
            ),
            priority="critical" if field == "price" else "high",
            linked_findings=linked_findings,
        )

    elif cid == "E3":
        q = ev.get("canonical_question", "Question")
        reason = ev.get("failure_reason", "No quotable passage")
        arch = ev.get("archetype", "site")
        return SuggestedAction(
            title="Publish a Self-Contained, Quotable Passage Answering Canonical Query",
            description=(
                f"No single passage on the site answers the canonical {arch} question '{q}'. "
                f"Failure reason: {reason}. Add a dedicated section with verifiable, factual details."
            ),
            code_snippet=(
                f'<section class="faq">\n'
                f'  <h3>{q}</h3>\n'
                f'  <p>Concrete factual statement providing exact terms, figures, or specifications.</p>\n'
                f'</section>'
            ),
            priority="high" if ev.get("topic") in ("pricing_tiers", "return_refund") else "medium",
            linked_findings=linked_findings,
        )

    else:
        return SuggestedAction(
            title=f"Resolve {c.root_cause.replace('_', ' ').title()} Issue ({cid})",
            description=c.mechanism,
            code_snippet=None,
            priority=c.raw_severity_class,
            linked_findings=linked_findings,
        )


def merge_candidate_findings(
    raw_candidates: List[Dict[str, Any]],
) -> List[FinalFinding]:
    """
    Validate candidates with Pydantic, deduplicate by signature,
    compute final severities, and attach instantiated recommendations.
    """
    if not raw_candidates:
        return []

    # 1. Pydantic Validation: strictly reject incomplete or placeholder candidates
    validated_candidates: List[CandidateFinding] = []
    for idx, raw in enumerate(raw_candidates):
        try:
            val = CandidateFinding.model_validate(raw)
            validated_candidates.append(val)
        except Exception as exc:
            raise ValueError(
                f"Candidate at index {idx} (id={raw.get('id', '?')}) failed contract validation: {exc}"
            ) from exc

    # 2. Deduplicate and group by deterministic signature
    groups: Dict[Tuple[str, ...], List[CandidateFinding]] = {}
    for c in validated_candidates:
        sig = _make_signature(c)
        groups.setdefault(sig, []).append(c)

    # 3. Build FinalFinding instances
    cluster_records = []
    # Sort signature keys deterministically
    for sig in sorted(groups.keys(), key=lambda s: str(s)):
        cluster = groups[sig]
        # Sort cluster by confidence descending, then page_url
        cluster.sort(key=lambda x: (-x.confidence, x.page_url))
        lead = cluster[0]

        affected_urls = sorted(list({item.page_url for item in cluster}))
        occurrences = len(cluster)

        final_sev = _compute_final_severity(lead.raw_severity_class, lead.confidence, occurrences)
        cluster_records.append((lead, final_sev, occurrences, affected_urls))

    # Sort clusters by severity rank (critical, high, medium, low), then confidence desc, then page_url
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    cluster_records.sort(
        key=lambda item: (severity_rank.get(item[1], 4), -item[0].confidence, item[0].page_url)
    )

    final_findings: List[FinalFinding] = []
    for idx, (lead, final_sev, occurrences, affected_urls) in enumerate(cluster_records, start=1):
        fid = f"FINDING-{idx:03d}"
        action = _instantiate_recommendation(lead, finding_id=fid)

        final_findings.append(FinalFinding(
            id=fid,
            check_id=lead.check_id,
            page_url=lead.page_url,
            root_cause=lead.root_cause,
            evidence=lead.evidence,
            raw_severity_class=lead.raw_severity_class,
            final_severity=final_sev,
            confidence=lead.confidence,
            mechanism=lead.mechanism,
            false_positive_guard=lead.false_positive_guard,
            verification_method=lead.verification_method,
            suggested_action=action,
            deduped_occurrences=occurrences,
            affected_urls=affected_urls,
        ))

    return final_findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic finding merger and severity scorer")
    parser.add_argument("candidates_file", help="Path to JSON file containing raw candidate findings")
    parser.add_argument("--output", "-o", help="Optional output path for merged findings JSON", default=None)
    args = parser.parse_args()

    cpath = Path(args.candidates_file)
    if not cpath.exists():
        print(f"Error: file not found: {cpath}", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(cpath.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print(f"Error: expected JSON array of findings in {cpath}", file=sys.stderr)
        sys.exit(1)

    merged = merge_candidate_findings(raw)
    out_json = json.dumps([f.model_dump(mode="json") for f in merged], indent=2, sort_keys=True)

    if args.output:
        Path(args.output).write_text(out_json, encoding="utf-8")
        print(f"Merged {len(raw)} candidates into {len(merged)} findings -> {args.output}")
    else:
        print(out_json)


if __name__ == "__main__":
    main()
