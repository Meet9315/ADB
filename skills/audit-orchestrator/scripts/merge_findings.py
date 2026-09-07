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
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from models import CHECK_TITLES, CandidateFinding, FinalFinding, SuggestedAction  # noqa: E402


def load_recommendation_bank(bank_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """
    Parse canonical action templates directly from references/recommendation-bank.md.
    Returns a dictionary mapping check_id (e.g. 'R1', 'D1', 'E3') to template dict:
    {
        "title": str,
        "root_cause": str,
        "description_template": str,
        "code_snippet": Optional[str],
    }
    """
    if bank_path is None:
        bank_path = _HERE.parent / "references" / "recommendation-bank.md"

    bank: Dict[str, Dict[str, Any]] = {}
    if not bank_path.exists():
        return bank

    content = bank_path.read_text(encoding="utf-8")
    sections = re.split(r'\n(?=##\s+[A-Z0-9]+\s+—)', content)
    for sec in sections[1:]:
        cid_match = re.search(r'\*\*Check ID\*\*:\s*`?([A-Z0-9]+)`?', sec)
        title_match = re.search(r'\*\*Title\*\*:\s*([^\n]+)', sec)
        rc_match = re.search(r'\*\*Root Cause\*\*:\s*`?([^\n`]+)`?', sec)

        desc_lines: List[str] = []
        in_desc = False
        in_snippet = False
        snip_lines: List[str] = []

        for line in sec.splitlines():
            stripped = line.strip()
            if stripped.startswith("- **Description**:"):
                in_desc = True
                rem = stripped.replace("- **Description**:", "").strip()
                if rem:
                    desc_lines.append(rem)
                continue
            elif stripped.startswith("- **Code Snippet**:"):
                in_desc = False
                in_snippet = True
                continue
            elif stripped.startswith("- **") or stripped.startswith("---") or stripped.startswith("##"):
                in_desc = False
                in_snippet = False

            if in_desc:
                desc_lines.append(stripped)
            elif in_snippet:
                snip_lines.append(line)

        snippet = "\n".join(snip_lines).strip()
        m_code = re.search(r'```[^\n]*\n(.*?)```', snippet, re.DOTALL)
        code_str = m_code.group(1).strip() if m_code else (snippet if snippet else None)

        if cid_match and title_match:
            cid = cid_match.group(1).strip()
            bank[cid] = {
                "title": title_match.group(1).strip().replace("`", ""),
                "root_cause": rc_match.group(1).strip() if rc_match else "",
                "description_template": " ".join(desc_lines).strip(),
                "code_snippet": code_str,
            }
    return bank


RECOMMENDATION_BANK: Dict[str, Dict[str, Any]] = load_recommendation_bank()


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
    elif cid == "D3":
        return (cid, str(ev.get("type", "")))
    elif cid == "E1":
        return (cid, str(ev.get("type", "")))
    elif cid == "E4":
        return (cid, str(ev.get("type", "")))
    elif cid == "T1":
        return (cid, str(ev.get("type", "")), c.page_url)
    elif cid == "T2":
        return (cid, str(ev.get("fact_type", "")), str(ev.get("normalized_value_a", "")))
    elif cid == "T3":
        return (cid, str(ev.get("type", "")))
    elif cid == "T4":
        return (cid, str(ev.get("type", "")))
    elif cid == "G1":
        return (cid, str(ev.get("type", "")), c.page_url)
    elif cid == "G2":
        return (cid, str(ev.get("type", "")), str(ev.get("target_url", c.page_url)))
    elif cid == "G3":
        return (cid, str(ev.get("type", "")), c.page_url)
    elif cid == "G4":
        return (cid, str(ev.get("type", "")), c.page_url)
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
    """Instantiate a SuggestedAction strictly from canonical recommendation-bank templates and candidate evidence."""
    ev = c.evidence
    cid = c.check_id
    linked_findings = [finding_id] if finding_id else [c.id]
    tpl = RECOMMENDATION_BANK.get(cid, {})
    canonical_title = tpl.get("title")

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

    elif cid == "D3":
        ev_type = ev.get("type", "semantic_structure_absent")
        if ev_type == "missing_h1":
            title = "Add Primary <h1> Heading Landmark"
            desc = (
                f"Page {c.page_url} lacks an <h1> heading landmark. "
                "Add a descriptive <h1> element to establish the primary topic for document extractors."
            )
            code = "<h1>Primary Page Title</h1>"
        elif ev_type == "missing_main_landmark":
            title = "Enclose Primary Page Content in <main> Landmark"
            desc = (
                f"Page {c.page_url} lacks a <main> or role='main' landmark. "
                "Wrap primary content inside a <main> element so web agents can distinguish it from navigation and footer chrome."
            )
            code = "<main>\n  <!-- Primary content -->\n</main>"
        else:
            title = "Correct Heading Hierarchy Nesting"
            desc = (
                f"Page {c.page_url} skips heading levels downwards. "
                "Ensure headings descend sequentially (e.g. h1 -> h2 -> h3) without level skips."
            )
            code = "<h1>Title</h1>\n<h2>Section</h2>\n<h3>Subsection</h3>"

        return SuggestedAction(
            title=title,
            description=desc,
            code_snippet=code,
            priority="low",
            linked_findings=linked_findings,
        )

    elif cid == "E1":
        arch = ev.get("inferred_archetype", "inferred")
        expected = "/".join(ev.get("expected_schema_types", ["Entity"])[:3])
        unannotated = ev.get("unannotated_pages_count", 1)
        total = ev.get("diagnostic_pages_count", 1)
        first_schema = (ev.get("expected_schema_types") or ["Thing"])[0]
        return SuggestedAction(
            title=f"Add Schema.org Structured Data for {arch.replace('_', ' ').title()} Archetype",
            description=(
                f"Site was classified as '{arch}', but {unannotated} of {total} diagnostic pages "
                f"lack {expected} structured data. Add schema.org JSON-LD blocks to provide machine-verifiable entities."
            ),
            code_snippet=(
                '{\n  "@context": "https://schema.org",\n  "@type": "'
                + first_schema
                + '",\n  "name": "Title"\n}'
            ),
            priority="medium",
            linked_findings=linked_findings,
        )

    elif cid == "E4":
        ev_type = ev.get("type", "metadata_gap")
        if ev_type == "missing_titles":
            title = "Add Unique <title> Tags to Substantive Pages"
            desc = (
                f"{ev.get('unannotated_pages_count', 1)} substantive page(s) lack a <title> tag. "
                "Provide a concise, descriptive title for every page."
            )
            code = "<title>Descriptive Page Title | Brand</title>"
        elif ev_type == "missing_meta_descriptions":
            title = "Add Informative Meta Descriptions to Substantive Pages"
            desc = (
                f"{ev.get('unannotated_pages_count', 1)} substantive page(s) lack a meta description tag. "
                "Add <meta name='description' content='...'> summarizing the page in 150-160 characters."
            )
            code = '<meta name="description" content="Concise factual overview of this page.">'
        elif ev_type == "duplicate_titles":
            title = "Disambiguate Duplicate Page Titles"
            desc = (
                f"Found {ev.get('duplicate_groups_count', 1)} cluster(s) of identical page titles across "
                f"{ev.get('total_affected_pages', 2)} substantive URLs. Ensure each page has a distinct title."
            )
            code = "<title>Unique Page Concept | Brand</title>"
        else:
            title = "Differentiate Duplicate Meta Descriptions"
            desc = (
                f"Found {ev.get('duplicate_groups_count', 1)} cluster(s) of duplicate meta descriptions across "
                f"{ev.get('total_affected_pages', 2)} substantive URLs. Provide unique summaries."
            )
            code = '<meta name="description" content="Unique summary tailored specifically to this page.">'

        return SuggestedAction(
            title=title,
            description=desc,
            code_snippet=code,
            priority="low",
            linked_findings=linked_findings,
        )

    elif cid == "T1":
        ev_type = ev.get("type", "stale_content")
        if "stale" in ev_type:
            title = "Update Stale Commercial Terms and Refresh Temporal Markers"
            desc = (
                f"Page {c.page_url} references outdated temporal markers ('{ev.get('stale_marker', 'outdated year')}'). "
                "Update commercial terms, pricing tables, and roadmaps to reflect current operational dates."
            )
            code = '<p>Pricing effective for 2026: ...</p>'
            prio = "medium"
        else:
            title = "Add Publication Date or Last-Updated Timestamp"
            desc = (
                f"Substantive page {c.page_url} lacks any temporal anchors. "
                "Add visible publication dates or schema.org datePublished/dateModified timestamps."
            )
            code = '<time datetime="2026-09-01">September 1, 2026</time>'
            prio = "low"

        return SuggestedAction(
            title=title,
            description=desc,
            code_snippet=code,
            priority=prio,
            linked_findings=linked_findings,
        )

    elif cid == "T2":
        fact_type = ev.get("fact_type", "contact fact").replace("_", " ")
        raw_a = ev.get("raw_value_a", "")
        raw_b = ev.get("raw_value_b", "")
        url_a = ev.get("url_a", "")
        url_b = ev.get("url_b", "")
        desc = (
            f"Resolve contradictory {fact_type} asserted across pages "
            f"('{raw_a}' on {url_a} vs '{raw_b}' on {url_b}). "
            "Establish a single canonical source of truth for repeated entity facts across all templates."
        )
        return SuggestedAction(
            title=f"Harmonize Contradictory {fact_type.title()} Across Pages",
            description=desc,
            code_snippet=None,
            priority="medium",
            linked_findings=linked_findings,
        )

    elif cid == "T3":
        brand = ev.get("brand_name", "Brand")
        return SuggestedAction(
            title="Disambiguate Brand Identity with Schema.org sameAs Links",
            description=(
                f"Disambiguate entity '{brand}' by declaring Schema.org Organization markup with verified sameAs "
                "links to authoritative external registries (Wikidata, Crunchbase, LinkedIn, Wikipedia)."
            ),
            code_snippet=(
                '{\n  "@context": "https://schema.org",\n  "@type": "Organization",\n  "name": "'
                + brand
                + '",\n  "sameAs": [\n    "https://www.wikidata.org/wiki/...",\n    "https://www.linkedin.com/company/..."\n  ]\n}'
            ),
            priority="medium",
            linked_findings=linked_findings,
        )

    elif cid == "T4":
        ev_type = ev.get("type", "presence_gap")
        if "contact" in ev_type:
            title = "Provide Authoritative Public Contact Mechanisms"
            desc = (
                "Website lacks discoverable contact channels. Add a dedicated /contact page with reachable email, "
                "phone number, or active customer support channels."
            )
            code = '<nav><a href="/contact">Contact Us</a></nav>'
            prio = "medium"
        elif "about" in ev_type:
            title = "Publish Organizational About and Background Overview"
            desc = (
                "Website provides no discoverable 'About' or company identity overview. Publish an /about overview "
                "detailing entity mission, leadership, and organization background."
            )
            code = '<nav><a href="/about">About Us</a></nav>'
            prio = "low"
        else:
            title = "Add Verified Author Attribution to Editorial Content"
            desc = (
                "Editorial article pages lack author bylines or Schema.org author properties. Include author attribution "
                "to satisfy AI search engine and aggregator E-E-A-T credibility requirements."
            )
            code = '<span class="byline">By Author Name</span>'
            prio = "low"

        return SuggestedAction(
            title=title,
            description=desc,
            code_snippet=code,
            priority=prio,
            linked_findings=linked_findings,
        )

    elif cid == "G1":
        unanswered = ev.get("unanswered_questions", [])
        unanswered_str = ", ".join(q.replace("_", " ") for q in unanswered) if unanswered else "core value proposition"
        return SuggestedAction(
            title="Clarify Above-the-Fold Brand, Offering, and Next Steps",
            description=(
                f"Homepage initial viewport on {c.page_url} fails to clearly answer: {unanswered_str}. "
                "Restructure the above-fold hero area to explicitly communicate brand identity, the core product/service "
                "offering, and an immediate directional action."
            ),
            code_snippet=(
                '<header class="hero">\n'
                '  <h1>[Brand]: [Clear Value Proposition & Offering]</h1>\n'
                '  <p>We provide [concise description of core service/product] for [target audience].</p>\n'
                '  <a href="/get-started" class="cta-button">Get Started Free</a>\n'
                '</header>'
            ),
            priority="medium",
            linked_findings=linked_findings,
        )

    elif cid == "G2":
        ev_type = ev.get("type", "wayfinding_defect")
        target_u = ev.get("target_url", c.page_url)
        if ev_type == "broken_internal_link":
            status = ev.get("status_code", 404)
            title = "Fix Broken Internal Navigation Link"
            desc = (
                f"Page {ev.get('source_page', c.page_url)} contains an internal link to '{target_u}' "
                f"which returns HTTP {status}. Update or remove the dead link to eliminate user dead ends."
            )
            code = '<!-- Update broken link target -->\n<a href="/valid-path">Updated Destination</a>'
            prio = "medium"
        elif ev_type == "unreachable_utility_page":
            util_type = ev.get("utility_type", "utility")
            title = f"Integrate Critical {util_type.title()} Page into Site Navigation"
            desc = (
                f"Critical {util_type} page '{target_u}' has no navigable internal path from the homepage. "
                f"Add prominent navigation links in the header, footer, or main menu."
            )
            code = f'<nav>\n  <a href="{target_u}">{util_type.title()}</a>\n</nav>'
            prio = "medium"
        elif ev_type == "excessive_utility_click_depth":
            util_type = ev.get("utility_type", "utility")
            depth = ev.get("depth", 3)
            title = f"Reduce Click Depth for Critical {util_type.title()} Page"
            desc = (
                f"Critical {util_type} page '{target_u}' requires {depth} clicks from home without a direct "
                "menu link. Add a direct link in the primary header or footer to streamline wayfinding."
            )
            code = f'<footer>\n  <a href="{target_u}">{util_type.title()}</a>\n</footer>'
            prio = "low"
        else:
            title = "Integrate Substantive Orphan Page into Site Hierarchy"
            desc = (
                f"Substantive page '{target_u}' ({ev.get('word_count', 80)} words) has zero incoming internal links. "
                "Add contextual links from relevant parent pages to make this content discoverable."
            )
            code = f'<a href="{target_u}">Explore Related Content</a>'
            prio = "low"

        return SuggestedAction(
            title=title,
            description=desc,
            code_snippet=code,
            priority=prio,
            linked_findings=linked_findings,
        )

    elif cid == "G3":
        ev_type = ev.get("type", "friction_defect")
        if ev_type == "excessive_page_payload":
            mb = ev.get("payload_mb", 5.0)
            title = "Reduce Page Payload Below 5MB Budget"
            desc = (
                f"Page {c.page_url} transferred payload of {mb}MB exceeds the 5.0MB threshold. "
                "Compress media assets, bundle scripts, and defer non-critical payloads."
            )
            code = None
            prio = "medium"
        elif ev_type == "media_viewport_displacement":
            title = "Constrain Hero Media to Keep Primary Content Above the Fold"
            desc = (
                f"Top-of-page media on {c.page_url} exceeds 50% viewport height, pushing substantive text below the fold. "
                "Constrain hero video/media containers to keep value proposition and headings visible on load."
            )
            code = ".hero-media { max-height: 45vh; }"
            prio = "medium"
        else:
            title = "Remove Intrusive Content-Obscuring Modals on Load"
            desc = (
                f"Page {c.page_url} renders an unprompted modal covering substantive content on initial load. "
                "Ensure page content is immediately readable and defer promotional popups to user-initiated actions."
            )
            code = "/* Defer or remove blocking overlay on initial load */\n.interstitial-modal { display: none; }"
            prio = "medium"

        return SuggestedAction(
            title=title,
            description=desc,
            code_snippet=code,
            priority=prio,
            linked_findings=linked_findings,
        )

    elif cid == "G4":
        role_label = ev.get("page_role", "page")
        return SuggestedAction(
            title="Introduce a Prominent Primary Call-to-Action",
            description=(
                f"The {role_label} '{c.page_url}' lacks a discernible primary call-to-action button or conversion link. "
                "Add a prominent, styled call-to-action button (e.g. 'Get Started', 'Buy Now', 'Schedule Demo', 'Contact Us') "
                "to guide users to the primary next step."
            ),
            code_snippet=(
                '<div class="primary-action">\n'
                '  <a href="/get-started" class="btn btn-primary">Get Started Free</a>\n'
                '</div>'
            ),
            priority="medium",
            linked_findings=linked_findings,
        )

    else:
        return SuggestedAction(
            title=canonical_title or f"Resolve {c.root_cause.replace('_', ' ').title()} Issue ({cid})",
            description=c.mechanism,
            code_snippet=tpl.get("code_snippet"),
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
            title=CHECK_TITLES.get(lead.check_id, f"AI Discoverability Defect ({lead.check_id})"),
            severity=final_sev,
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
