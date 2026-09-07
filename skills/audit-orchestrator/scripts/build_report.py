#!/usr/bin/env python3
"""
build_report.py — Final audit report builder and deterministic JSON serializer.

Assembles metadata, summary statistics, merged findings, and archetype-conditioned
proactive recommendations into a validated FinalReport schema.
Guarantees deterministic byte-for-byte JSON serialization.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from models import AuditMetadata, FinalFinding, FinalReport, SuggestedAction, SummaryCounts  # noqa: E402


# ── Proactive recommendations catalog ─────────────────────────────────────

PROACTIVE_CATALOG: Dict[str, List[Dict[str, Any]]] = {
    "ecommerce": [
        {
            "topic": "return_refund",
            "title": "Add Schema.org MerchantReturnPolicy Structured Markup",
            "description": (
                "Add structured MerchantReturnPolicy schema linked via hasMerchantReturnPolicy. "
                "This enables AI shopping agents to quote exact return windows and refund policies."
            ),
            "code_snippet": '{\n  "@type": "MerchantReturnPolicy",\n  "merchantReturnDays": "<actual_return_days_e.g._30>"\n}',
            "priority": "medium",
        },
        {
            "topic": "shipping_policy",
            "title": "Declare Structured OfferShippingDetails on Products",
            "description": (
                "Add shippingDetails to Offer schemas to specify delivery transit times and rates "
                "for conversational shopping comparisons."
            ),
            "code_snippet": '{\n  "@type": "OfferShippingDetails",\n  "shippingRate": { "@type": "MonetaryAmount", "value": "<shipping_rate>", "currency": "<currency_code>" }\n}',
            "priority": "medium",
        },
    ],
    "saas": [
        {
            "topic": "llms_txt",
            "title": "Deploy an /llms.txt Machine-Readable Context File",
            "description": (
                "Deploy a standard /llms.txt endpoint giving AI assistants and code agents "
                "an authoritative summary of product APIs, pricing tiers, and capabilities."
            ),
            "code_snippet": "# /llms.txt\n> <Brief product value proposition statement>\n- [Docs](/docs)",
            "priority": "medium",
        },
        {
            "topic": "pricing_tiers",
            "title": "Publish Structured SoftwareApplication and Offer Tiers",
            "description": (
                "Add SoftwareApplication schema detailing pricing tiers, applicationCategory, and feature lists."
            ),
            "code_snippet": '{\n  "@type": "SoftwareApplication",\n  "name": "<Application Name>",\n  "applicationCategory": "BusinessApplication"\n}',
            "priority": "low",
        },
    ],
    "docs": [
        {
            "topic": "llms_txt",
            "title": "Provide Curated Markdown Endpoints for AI Developer Tools",
            "description": (
                "Provide an /llms.txt index linking to clean raw markdown endpoints for all API guides."
            ),
            "code_snippet": "# /llms.txt\n- [API Reference](/docs/api.md)",
            "priority": "medium",
        },
        {
            "topic": "installation",
            "title": "Tag All Code Blocks with Explicit Language Identifiers",
            "description": (
                "Ensure every <pre><code> block has a language class for automated AI extraction."
            ),
            "code_snippet": '<pre><code class="language-bash">npm install <package-name></code></pre>',
            "priority": "low",
        },
    ],
    "news": [
        {
            "topic": "authorship",
            "title": "Enrich Article Authors with Person Schema and Verified Links",
            "description": (
                "Markup authors with Person schema including sameAs links to verified journalism profiles."
            ),
            "code_snippet": '{\n  "@type": "Person",\n  "name": "<author_name>"\n}',
            "priority": "medium",
        },
    ],
    "local_business": [
        {
            "topic": "business_hours",
            "title": "Add Detailed OpeningHoursSpecification and GeoCoordinates",
            "description": (
                "Provide ISO opening hours and latitude/longitude in LocalBusiness schema."
            ),
            "code_snippet": '{\n  "@type": "LocalBusiness",\n  "geo": { "@type": "GeoCoordinates", "latitude": "<business_latitude>", "longitude": "<business_longitude>" }\n}',
            "priority": "medium",
        },
    ],
    "corporate": [
        {
            "topic": "commercial_solutions",
            "title": "Implement Canonical Corporation Schema with Official Identifiers",
            "description": (
                "Declare Corporation schema with legalName, contactPoint for press, and investor relations."
            ),
            "code_snippet": '{\n  "@type": "Corporation",\n  "legalName": "<legal_corporate_name>"\n}',
            "priority": "low",
        },
    ],
}


def build_final_report(
    target_domain: str,
    base_url: str,
    archetype: str,
    is_tiny_site: bool,
    started_at: str,
    completed_at: str,
    elapsed_s: float,
    findings: List[FinalFinding],
    partial_audit: bool = False,
    partial_audit_reason: Optional[str] = None,
) -> FinalReport:
    """
    Construct, validate, and return the canonical FinalReport object.
    """
    # 1. Compute summary counts
    by_severity: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_root_cause: Dict[str, int] = {
        "representation_gap": 0,
        "statement_implicitness": 0,
        "identity_irresolution": 0,
        "corroboration_deficit": 0,
        "temporal_decay": 0,
        "orientation_cost": 0,
    }
    by_check_id: Dict[str, int] = {}

    for f in findings:
        by_severity[f.final_severity] = by_severity.get(f.final_severity, 0) + 1
        by_root_cause[f.root_cause] = by_root_cause.get(f.root_cause, 0) + 1
        by_check_id[f.check_id] = by_check_id.get(f.check_id, 0) + 1

    summary = SummaryCounts(
        total_findings=len(findings),
        by_severity=by_severity,
        by_root_cause=by_root_cause,
        by_check_id=by_check_id,
    )

    metadata = AuditMetadata(
        target_domain=target_domain,
        base_url=base_url,
        archetype=archetype,
        is_tiny_site=is_tiny_site,
        started_at=started_at,
        completed_at=completed_at,
        elapsed_s=round(elapsed_s, 2),
        partial_audit=partial_audit,
        partial_audit_reason=partial_audit_reason,
    )

    # 2. Add archetype proactive suggestions — only when not already covered by findings
    covered_topics: Set[str] = set()
    for f in findings:
        if f.check_id == "E3" and "topic" in f.evidence:
            covered_topics.add(f.evidence["topic"])
        if f.check_id == "E2" and "field" in f.evidence:
            covered_topics.add(f.evidence["field"])

    proactive_recs: List[SuggestedAction] = []
    candidates = PROACTIVE_CATALOG.get(archetype, [])
    for p in candidates:
        if p["topic"] not in covered_topics:
            proactive_recs.append(SuggestedAction(
                id=f"PROACT-{len(proactive_recs) + 1:03d}",
                title=p["title"],
                description=p["description"],
                code_snippet=p.get("code_snippet"),
                priority=p["priority"],
                linked_findings=[],
                is_proactive=True,
            ))

    # 3. Consolidate remediation recommendations with linked_findings
    recs_map: Dict[Any, SuggestedAction] = {}
    for f in findings:
        act = f.suggested_action
        key = (act.title, act.code_snippet)
        if key in recs_map:
            for fid in act.linked_findings:
                if fid not in recs_map[key].linked_findings:
                    recs_map[key].linked_findings.append(fid)
        else:
            recs_map[key] = SuggestedAction(
                id=f"REC-{len(recs_map) + 1:03d}",
                title=act.title,
                description=act.description,
                code_snippet=act.code_snippet,
                priority=act.priority,
                linked_findings=list(act.linked_findings),
                is_proactive=False,
            )
    consolidated_recs = list(recs_map.values())

    # 4. Assemble and validate FinalReport model
    report = FinalReport(
        schema_version="1.0",
        audit_metadata=metadata,
        summary=summary,
        findings=findings,
        recommendations=consolidated_recs,
        proactive_recommendations=proactive_recs,
    )

    return report


def serialize_report(report: FinalReport) -> str:
    """Serialize report to deterministic JSON."""
    return report.to_deterministic_json()
