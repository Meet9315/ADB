#!/usr/bin/env python3
"""
check_t4.py — T4 Missing About/Contact/Authorship Presence Check (Tier 1: Trust Signals Audit).

Deterministic presence checks for core trust mechanisms:
1. About Presence: Absence of about/company page, section, or navigational link.
2. Contact Presence: Absence of contact mechanism (page, mailto link, phone, or address).
3. Authorship Presence: Absence of author attribution on news/content articles.

Negative-Logic Rules:
- Authorship presence is ONLY evaluated on 'news' and 'content' archetypes with article pages;
  never demanded on SaaS, ecommerce, documentation, or utility pages.
- Uncrawled links in crawled HTML anchors (<a href="...">) satisfy presence (guards against
  false positives caused by crawl depth/budget limits).
- Single-page sites with in-page '#about' or '#contact' sections are considered compliant.

Usage:
    python check_t4.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

ABOUT_PATH_RE = re.compile(r"/(?:about(?:-us)?|company|who-we-are|our-story|team|leadership)(?:/|$|\?)", re.IGNORECASE)
CONTACT_PATH_RE = re.compile(r"/(?:contact(?:-us)?|support|get-in-touch|reach-us)(?:/|$|\?)", re.IGNORECASE)
ARTICLE_PATH_RE = re.compile(r"/(?:blog|posts?|articles?|news|stories|insights)/[^/]+", re.IGNORECASE)

ABOUT_SECTION_RE = re.compile(r'(?:id|class)=["\'][^"\']*(?:about|who-we-are)[^"\']*["\']|<h[1-3][^>]*>\s*About\s+(?:Us|Company)?', re.IGNORECASE)
CONTACT_SECTION_RE = re.compile(r'(?:id|class)=["\'][^"\']*(?:contact|support)[^"\']*["\']|<h[1-3][^>]*>\s*Contact\s+(?:Us)?', re.IGNORECASE)

MAILTO_RE = re.compile(r'href=["\']mailto:[^"\']+["\']', re.IGNORECASE)
TEL_RE = re.compile(r'href=["\']tel:[^"\']+["\']', re.IGNORECASE)
PHONE_TEXT_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b")
AUTHOR_BYLINE_RE = re.compile(r'class=["\'][^"\']*(?:byline|author|written-by)[^"\']*["\']|\bby\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b', re.IGNORECASE)


def run_check_t4(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute T4 presence checks across the corpus."""
    findings: List[Dict[str, Any]] = []

    has_about = False
    has_contact = False
    article_pages_count = 0
    article_pages_with_author = 0

    base_url = manifest.get("base_url", "") if manifest else ""
    archetype_name = "unknown"

    # Infer or extract archetype
    if manifest:
        arch_list = manifest.get("archetypes") or [manifest.get("archetype")]
        if arch_list and arch_list[0]:
            archetype_name = arch_list[0]

    all_anchor_hrefs: Set[str] = set()
    pages_examined: List[Tuple[str, Path]] = []

    for page_dir in sorted(corpus_dir.iterdir()):
        if not page_dir.is_dir():
            continue

        raw_path = page_dir / "raw.html"
        meta_path = page_dir / "meta.json"
        text_path = page_dir / "text.txt"

        if not raw_path.exists():
            continue

        meta: Dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        url = meta.get("final_url") or meta.get("url", "")
        if not url and manifest:
            for cp in manifest.get("crawled_pages", []):
                if cp.get("slug") == page_dir.name:
                    url = cp.get("final_url") or cp.get("url", "")
                    break

        if not url:
            continue

        if not base_url:
            p = urlparse(url)
            base_url = f"{p.scheme}://{p.netloc}"

        html = raw_path.read_text(encoding="utf-8", errors="replace")
        text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""

        path = urlparse(url).path.lower()

        # 1. Check About Presence
        if ABOUT_PATH_RE.search(path) or ABOUT_SECTION_RE.search(html):
            has_about = True

        # 2. Check Contact Presence
        if (
            CONTACT_PATH_RE.search(path)
            or CONTACT_SECTION_RE.search(html)
            or MAILTO_RE.search(html)
            or TEL_RE.search(html)
            or PHONE_TEXT_RE.search(text)
        ):
            has_contact = True

        # Extract anchor links for uncrawled presence check
        for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE):
            all_anchor_hrefs.add(m.group(1).lower())

        # 3. Check Article Authorship
        if ARTICLE_PATH_RE.search(path):
            article_pages_count += 1
            has_author = (
                bool(AUTHOR_BYLINE_RE.search(html))
                or '"author"' in html
                or '"creator"' in html
                or 'itemprop="author"' in html
            )
            if has_author:
                article_pages_with_author += 1

    # Check uncrawled anchor links (negative logic: prevents FP on uncrawled pages)
    if not has_about:
        for href in all_anchor_hrefs:
            if ABOUT_PATH_RE.search(href) or href.rstrip("/").endswith(("/about", "/about-us", "/company")):
                has_about = True
                break

    if not has_contact:
        for href in all_anchor_hrefs:
            if CONTACT_PATH_RE.search(href) or href.startswith("mailto:") or href.startswith("tel:"):
                has_contact = True
                break

    finding_idx = 1
    target_url = base_url or "https://example.com"

    # Flag missing Contact presence
    if not has_contact:
        findings.append({
            "id": f"F-T4-{finding_idx:03d}",
            "check_id": "T4",
            "page_url": target_url,
            "root_cause": "corroboration_deficit",
            "evidence": {
                "type": "missing_contact_presence",
                "evaluated_pages_count": len(list(corpus_dir.iterdir())),
                "has_contact_page": False,
                "has_mailto_link": False,
                "has_phone_number": False,
            },
            "raw_severity_class": "medium",
            "confidence": 0.90,
            "mechanism": (
                f"Website '{target_url}' lacks discoverable contact mechanisms (no contact page, mailto link, "
                "telephone link, or in-page support channel). AI agents verifying business authenticity and "
                "consumer support capabilities heavily penalize or omit sites lacking reachable contact channels."
            ),
            "false_positive_guard": (
                "Verified absence of contact routes (/contact, /support), in-page contact sections, mailto links, "
                "tel links, and anchors across all crawled HTML documents."
            ),
            "verification_method": f"curl -sL {target_url} | grep -iE 'contact|support|mailto:'",
        })
        finding_idx += 1

    # Flag missing About presence
    if not has_about:
        findings.append({
            "id": f"F-T4-{finding_idx:03d}",
            "check_id": "T4",
            "page_url": target_url,
            "root_cause": "identity_irresolution",
            "evidence": {
                "type": "missing_about_presence",
                "evaluated_pages_count": len(list(corpus_dir.iterdir())),
                "has_about_page": False,
                "has_about_section": False,
            },
            "raw_severity_class": "low",
            "confidence": 0.85,
            "mechanism": (
                f"Website '{target_url}' provides no discoverable 'About' or company identity overview. "
                "Autonomous research agents look for organizational background and mission context to "
                "corroborate corporate entity legitimacy."
            ),
            "false_positive_guard": (
                "Checked page URLs, HTML anchors, and in-page sections for 'about', 'company', or 'who-we-are' keywords."
            ),
            "verification_method": f"curl -sL {target_url} | grep -iE 'about|company|who-we-are'",
        })
        finding_idx += 1

    # Flag missing Authorship on news / content sites
    if archetype_name in ("news", "content") and article_pages_count >= 2:
        if article_pages_with_author == 0:
            findings.append({
                "id": f"F-T4-{finding_idx:03d}",
                "check_id": "T4",
                "page_url": target_url,
                "root_cause": "corroboration_deficit",
                "evidence": {
                    "type": "missing_authorship_attribution",
                    "archetype": archetype_name,
                    "article_pages_count": article_pages_count,
                    "attributed_pages_count": article_pages_with_author,
                },
                "raw_severity_class": "low",
                "confidence": 0.85,
                "mechanism": (
                    f"Site was classified as '{archetype_name}', but {article_pages_count} article pages lack author "
                    "bylines or schema.org author attribution. Answer engines and news aggregators enforce E-E-A-T "
                    "author credibility checks and deprioritize anonymous editorial content."
                ),
                "false_positive_guard": (
                    f"Archetype gate: evaluated strictly for '{archetype_name}' with {article_pages_count} article pages. "
                    "Excluded utility, marketing, and commercial pages."
                ),
                "verification_method": f"curl -sL {target_url} | grep -iE 'byline|author|written-by'",
            })
            finding_idx += 1

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="T4 — Missing About/Contact/Authorship Presence Check")
    parser.add_argument("corpus_dir", type=Path, help="Directory containing crawled page subdirectories")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to crawl_manifest.json")
    args = parser.parse_args()

    manifest_data: Optional[Dict[str, Any]] = None
    if args.manifest and args.manifest.exists():
        try:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception:
            pass

    findings = run_check_t4(args.corpus_dir, manifest=manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
