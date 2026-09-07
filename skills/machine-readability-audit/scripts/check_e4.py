#!/usr/bin/env python3
"""
check_e4.py — E4 Duplicate/missing titles and meta descriptions check.

Evaluates:
- Missing <title> on substantive pages
- Missing meta description (<meta name="description">) on substantive pages
- Duplicate titles across distinct substantive pages
- Duplicate meta descriptions across distinct substantive pages

Following the project constitution:
- Strictly minor/low severity regardless of findings (avoids report inflation).
- Evaluates only substantive pages (word count >= 80, HTTP 200).
- Excludes utility, login, cart, checkout, search, and error pages.
- Strips brand suffixes before comparing titles for duplicates.
- Groups/aggregates issues to prevent consuming disproportionate report real estate.
- Output: JSON list of candidate findings conforming to CandidateFinding schema.

Usage:
    python check_e4.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

# Utility/private pages to exclude from title/description requirements
EXCLUDED_PATH_SEGMENTS = {
    "login", "signin", "sign-in", "auth", "oauth",
    "cart", "checkout", "basket",
    "register", "signup", "sign-up",
    "account", "settings", "preferences",
    "search", "404", "error",
}


def _is_excluded_page(url: str, title: str) -> bool:
    """Check if page is a utility, login, or error page that should be excluded."""
    path = urlparse(url).path.lower().strip("/")
    path_parts = set(path.split("/"))
    if path_parts & EXCLUDED_PATH_SEGMENTS:
        return True
    title_lower = (title or "").lower()
    for kw in ("login", "sign in", "cart", "checkout", "not found", "404"):
        if kw in title_lower:
            return True
    return False


def _extract_title(raw_html: str) -> Optional[str]:
    """Extract and decode <title> tag text."""
    m = re.search(r"<title\b[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    cleaned = re.sub(r"\s+", " ", m.group(1)).strip()
    return html.unescape(cleaned) if cleaned else None


def _extract_meta_description(raw_html: str) -> Optional[str]:
    """Extract content from <meta name="description" content="..."> tag."""
    # Handle name="description" before or after content="..."
    m = re.search(
        r'<meta\b[^>]*?\bname=["\']description["\'][^>]*?\bcontent=["\'](.*?)["\']',
        raw_html,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        m = re.search(
            r'<meta\b[^>]*?\bcontent=["\'](.*?)["\'][^>]*?\bname=["\']description["\']',
            raw_html,
            re.IGNORECASE | re.DOTALL,
        )
    if not m:
        return None
    cleaned = re.sub(r"\s+", " ", m.group(1)).strip()
    return html.unescape(cleaned) if cleaned else None


def _normalize_title_for_dedup(title: str) -> str:
    """
    Normalize title for duplicate comparison by removing common site/brand suffixes.
    e.g. 'Pricing | Acme Corp' -> 'pricing'
    """
    t = title.strip().lower()
    # Strip common suffixes like ' | Brand', ' - Brand', ' — Brand', ' · Brand'
    t = re.sub(r"\s*[-|—–·:]\s*[^-\|—–·:]+$", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _normalize_desc_for_dedup(desc: str) -> str:
    """Normalize description for duplicate comparison."""
    return re.sub(r"\s+", " ", desc.strip().lower())


def run_check_e4(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute E4 check across all crawled pages in corpus_dir."""
    findings: List[Dict[str, Any]] = []

    substantive_pages: List[Tuple[str, str, Optional[str], Optional[str]]] = []
    # (url, html, title, description)

    for page_dir in sorted(corpus_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        meta_path = page_dir / "meta.json"
        html_path = page_dir / "raw.html"
        text_path = page_dir / "text.txt"

        if not html_path.exists():
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

        if meta.get("status_code", 200) != 200:
            continue

        html_content = html_path.read_text(encoding="utf-8", errors="replace")
        visible_text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
        word_count = len([w for w in visible_text.split() if len(w) > 2])

        # Guard: skip thin or stub pages
        if word_count < 80:
            continue

        title = _extract_title(html_content) or meta.get("title")
        if _is_excluded_page(url, title or ""):
            continue

        desc = _extract_meta_description(html_content)
        substantive_pages.append((url, html_content, title, desc))

    if not substantive_pages:
        return []

    # 1. Missing Titles
    pages_lacking_title = [url for url, _, title, _ in substantive_pages if not title]
    if pages_lacking_title:
        primary_url = pages_lacking_title[0]
        findings.append({
            "id": f"F-E4-{len(findings) + 1:03d}",
            "check_id": "E4",
            "page_url": primary_url,
            "root_cause": "representation_gap",
            "evidence": {
                "type": "missing_titles",
                "unannotated_pages_count": len(pages_lacking_title),
                "total_substantive_pages": len(substantive_pages),
                "sample_urls": pages_lacking_title[:5],
            },
            "raw_severity_class": "low",
            "confidence": 0.90,
            "mechanism": (
                f"{len(pages_lacking_title)} substantive page(s) lack a <title> tag. "
                "AI search agents and retrieval engines use page titles as the primary anchor "
                "for tab indexing, search results, and knowledge synthesis."
            ),
            "false_positive_guard": (
                f"Evaluated {len(substantive_pages)} substantive page(s) (word count >= 80, HTTP 200). "
                "Excluded utility and auth endpoints. Confirmed complete absence of non-empty <title> tag."
            ),
            "verification_method": f"curl -sL {primary_url} | grep -i '<title>'",
        })

    # 2. Missing Meta Descriptions
    pages_lacking_desc = [url for url, _, _, desc in substantive_pages if not desc]
    if pages_lacking_desc:
        primary_url = pages_lacking_desc[0]
        findings.append({
            "id": f"F-E4-{len(findings) + 1:03d}",
            "check_id": "E4",
            "page_url": primary_url,
            "root_cause": "representation_gap",
            "evidence": {
                "type": "missing_meta_descriptions",
                "unannotated_pages_count": len(pages_lacking_desc),
                "total_substantive_pages": len(substantive_pages),
                "sample_urls": pages_lacking_desc[:5],
            },
            "raw_severity_class": "low",
            "confidence": 0.85,
            "mechanism": (
                f"{len(pages_lacking_desc)} substantive page(s) lack a meta description tag. "
                "Search crawlers and conversational extractors use meta descriptions to generate search "
                "snippets and assess document relevance before deep crawling."
            ),
            "false_positive_guard": (
                f"Evaluated {len(substantive_pages)} substantive page(s) (word count >= 80, HTTP 200). "
                "Excluded utility and auth endpoints. Confirmed absence of non-empty <meta name='description'>."
            ),
            "verification_method": f"curl -sL {primary_url} | grep -i 'meta.*name=[\"\\']description[\"\\']'",
        })

    # 3. Duplicate Titles across distinct pages
    title_groups: Dict[str, List[Tuple[str, str]]] = {}  # norm_title -> [(url, raw_title)]
    for url, _, title, _ in substantive_pages:
        if title:
            norm_t = _normalize_title_for_dedup(title)
            if len(norm_t) > 3:  # ignore extremely short/ambiguous strings
                title_groups.setdefault(norm_t, []).append((url, title))

    dup_titles = {t: items for t, items in title_groups.items() if len(items) >= 2}
    if dup_titles:
        first_group = next(iter(dup_titles.values()))
        primary_url = first_group[0][0]
        total_dup_pages = sum(len(items) for items in dup_titles.values())
        dup_summary = [
            f"'{items[0][1]}' shared by {len(items)} URLs"
            for items in list(dup_titles.values())[:3]
        ]
        findings.append({
            "id": f"F-E4-{len(findings) + 1:03d}",
            "check_id": "E4",
            "page_url": primary_url,
            "root_cause": "representation_gap",
            "evidence": {
                "type": "duplicate_titles",
                "duplicate_groups_count": len(dup_titles),
                "total_affected_pages": total_dup_pages,
                "summary": "; ".join(dup_summary),
                "sample_clusters": [
                    {"title": items[0][1], "urls": [u for u, _ in items[:4]]}
                    for items in list(dup_titles.values())[:5]
                ],
            },
            "raw_severity_class": "low",
            "confidence": 0.85,
            "mechanism": (
                f"Found {len(dup_titles)} cluster(s) of identical page titles across {total_dup_pages} "
                "distinct substantive URLs. Duplicate titles create entity ambiguity in search engine indexes "
                "and reduce the precision of RAG retrieval engines."
            ),
            "false_positive_guard": (
                "Stripped common brand suffixes before comparison. Evaluated only distinct substantive "
                "pages with word count >= 80."
            ),
            "verification_method": f"curl -sL {primary_url} | grep -i '<title>'",
        })

    # 4. Duplicate Meta Descriptions across distinct pages
    desc_groups: Dict[str, List[Tuple[str, str]]] = {}  # norm_desc -> [(url, raw_desc)]
    for url, _, _, desc in substantive_pages:
        if desc:
            norm_d = _normalize_desc_for_dedup(desc)
            if len(norm_d) > 15:  # ignore trivial descriptions
                desc_groups.setdefault(norm_d, []).append((url, desc))

    dup_descs = {d: items for d, items in desc_groups.items() if len(items) >= 2}
    if dup_descs:
        first_group = next(iter(dup_descs.values()))
        primary_url = first_group[0][0]
        total_dup_pages = sum(len(items) for items in dup_descs.values())
        findings.append({
            "id": f"F-E4-{len(findings) + 1:03d}",
            "check_id": "E4",
            "page_url": primary_url,
            "root_cause": "representation_gap",
            "evidence": {
                "type": "duplicate_meta_descriptions",
                "duplicate_groups_count": len(dup_descs),
                "total_affected_pages": total_dup_pages,
                "sample_clusters": [
                    {"description": items[0][1][:120], "urls": [u for u, _ in items[:4]]}
                    for items in list(dup_descs.values())[:5]
                ],
            },
            "raw_severity_class": "low",
            "confidence": 0.85,
            "mechanism": (
                f"Found {len(dup_descs)} duplicate meta description cluster(s) across {total_dup_pages} "
                "distinct substantive URLs. Boilerplate descriptions fail to differentiate individual page content "
                "for autonomous search summary cards."
            ),
            "false_positive_guard": (
                "Normalized whitespace and evaluated only distinct substantive pages with non-empty descriptions."
            ),
            "verification_method": f"curl -sL {primary_url} | grep -i 'meta.*name=[\"\\']description[\"\\']'",
        })

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check E4: Duplicate/missing titles and meta descriptions")
    parser.add_argument("corpus_dir", type=Path, help="Directory containing crawled page subdirectories")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to crawl_manifest.json")
    args = parser.parse_args()

    manifest_data: Optional[Dict[str, Any]] = None
    if args.manifest and args.manifest.exists():
        try:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception:
            pass

    findings = run_check_e4(args.corpus_dir, manifest=manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
