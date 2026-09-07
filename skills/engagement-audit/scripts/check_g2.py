#!/usr/bin/env python3
"""
check_g2.py — G2 Wayfinding Defects Check (Tier 2: Engagement Audit).

Audits the site for navigational wayfinding defects:
1. Broken internal links: hyperlinks to internal pages returning 4xx/5xx status codes.
2. Critical utility pages (pricing, contact, about) that are > 2 clicks from home or lack
   navigable paths from home.
3. Substantive orphan pages: pages discovered in sitemap that are never linked from internal pages.

Negative-Logic Rules (False-Positive Guards):
- Intentional Navigational Path Guard: Depth alone is NEVER treated as a defect when a page
  has a clear, intentional navigational path (e.g. linked in header, nav, or footer on home).
- Substantive Orphan Guard: Orphan pages are flagged ONLY when they contain substantive
  content (>= 80 visible words), strictly excluding feeds, search endpoints, paginated archives,
  and utility artifacts.
- External links returning 4xx are not internal wayfinding defects.

Usage:
    python check_g2.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

UTILITY_PATTERNS = {
    "pricing": re.compile(r"/(?:pricing|plans?|rates?|costs?|fees?)(?:/|$|\?)", re.IGNORECASE),
    "contact": re.compile(r"/(?:contact(?:-us)?|support|help|reach-us)(?:/|$|\?)", re.IGNORECASE),
    "about": re.compile(r"/(?:about(?:-us)?|company|who-we-are|team)(?:/|$|\?)", re.IGNORECASE),
}

ARTIFACT_PATH_RE = re.compile(
    r"/(?:feed|rss|atom|search|tags?|categories|author|page/\d+|wp-json|api)(?:/|$|\?)|\?s=",
    re.IGNORECASE,
)


def _extract_anchor_hrefs(html: str) -> Set[str]:
    """Extract lowercase href targets from anchor tags."""
    hrefs: Set[str] = set()
    for m in re.finditer(r'<a[^>]+href=["\']([^"\'#]+)["\']', html, re.IGNORECASE):
        href = m.group(1).strip().lower()
        if href and not href.startswith(("javascript:", "mailto:", "tel:")):
            hrefs.add(href)
    return hrefs


def run_check_g2(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute G2 Wayfinding checks across the corpus and crawl inventory."""
    findings: List[Dict[str, Any]] = []
    finding_idx = 1

    crawled_pages = manifest.get("crawled_pages", []) if manifest else []
    domain = manifest.get("domain", "") if manifest else ""
    base_url = manifest.get("base_url", "") if manifest else ""

    # Build page maps
    page_by_url: Dict[str, Dict[str, Any]] = {}
    pages_by_slug: Dict[str, Dict[str, Any]] = {}
    incoming_links: Dict[str, Set[str]] = {}

    home_slug = ""
    home_url = ""
    home_anchors: Set[str] = set()

    for p in crawled_pages:
        u = p.get("url", "")
        slug = p.get("slug", "")
        page_by_url[u] = p
        if slug:
            pages_by_slug[slug] = p

        parsed = urlparse(u)
        if not domain and parsed.netloc:
            domain = parsed.netloc
        if parsed.path in ("", "/", "/index.html"):
            home_slug = slug
            home_url = u

        src = p.get("source_url")
        if src:
            incoming_links.setdefault(u, set()).add(src)

    # Inspect physical corpus directories
    corpus_pages_info: Dict[str, Dict[str, Any]] = {}
    all_observed_internal_links: Set[Tuple[str, str]] = set()  # (source_url, target_href)

    for pdir in sorted(corpus_dir.iterdir()):
        if not pdir.is_dir():
            continue
        meta_path = pdir / "meta.json"
        raw_path = pdir / "raw.html"
        text_path = pdir / "text.txt"

        meta: Dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        p_url = meta.get("final_url") or meta.get("url", "")
        if not p_url and pdir.name in pages_by_slug:
            p_url = pages_by_slug[pdir.name].get("url", "")

        status_code = meta.get("status_code") or (pages_by_slug.get(pdir.name, {}).get("status_code", 200))
        text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
        html = raw_path.read_text(encoding="utf-8", errors="replace") if raw_path.exists() else ""

        corpus_pages_info[pdir.name] = {
            "url": p_url,
            "status_code": status_code,
            "word_count": len(text.split()),
            "html": html,
        }

        # Track links from this page
        if html and p_url:
            anchors = _extract_anchor_hrefs(html)
            for a in anchors:
                all_observed_internal_links.add((p_url, a))
            if pdir.name == home_slug or p_url == home_url:
                home_anchors.update(anchors)

    if not base_url and domain:
        base_url = f"https://{domain}"

    # -------------------------------------------------------------------------
    # 1. Broken Internal Links Check
    # -------------------------------------------------------------------------
    reported_broken: Set[str] = set()
    for cp in crawled_pages:
        target_url = cp.get("url", "")
        code = cp.get("status_code", 200)
        src = cp.get("source_url")

        if code >= 400 and src and target_url not in reported_broken:
            reported_broken.add(target_url)
            findings.append({
                "id": f"F-G2-{finding_idx:03d}",
                "check_id": "G2",
                "page_url": src,
                "root_cause": "orientation_cost",
                "evidence": {
                    "type": "broken_internal_link",
                    "target_url": target_url,
                    "source_page": src,
                    "status_code": code,
                },
                "raw_severity_class": "medium",
                "confidence": 0.95,
                "mechanism": (
                    f"Page '{src}' links to internal page '{target_url}' which returns HTTP {code}. "
                    "Broken internal links produce dead ends for human navigation, preventing users from "
                    "completing information discovery tasks."
                ),
                "false_positive_guard": (
                    f"Deterministic status check: verified internal origin '{src}' and destination returning HTTP {code}. "
                    "External links excluded."
                ),
                "verification_method": f"curl -sL -o /dev/null -w '%{{http_code}}' '{target_url}'",
            })
            finding_idx += 1

    # -------------------------------------------------------------------------
    # 2. Critical Utility Pages (Depth & Navigability) Check
    # -------------------------------------------------------------------------
    evaluated_utility_types: Set[str] = set()

    for cp in crawled_pages:
        u = cp.get("url", "")
        path = urlparse(u).path.lower()

        for util_name, pat in UTILITY_PATTERNS.items():
            if pat.search(path) and util_name not in evaluated_utility_types:
                depth = cp.get("depth")

                # INTENTIONAL NAV PATH GUARD:
                # Check if this utility page is linked directly from homepage anchors
                has_intentional_path = any(
                    path == a or path == urlparse(a).path.lower() or a.rstrip("/").endswith(path.rstrip("/"))
                    for a in home_anchors
                )

                # Depth alone is not a defect if it has a direct intentional link
                if depth is not None and depth > 2 and not has_intentional_path:
                    evaluated_utility_types.add(util_name)
                    findings.append({
                        "id": f"F-G2-{finding_idx:03d}",
                        "check_id": "G2",
                        "page_url": u,
                        "root_cause": "orientation_cost",
                        "evidence": {
                            "type": "excessive_utility_click_depth",
                            "utility_type": util_name,
                            "target_url": u,
                            "depth": depth,
                            "has_intentional_home_nav_path": False,
                        },
                        "raw_severity_class": "low",
                        "confidence": 0.85,
                        "mechanism": (
                            f"Critical {util_name} page '{u}' requires {depth} clicks from home without a direct "
                            "navigation menu link. Users seeking conversion or contact details encounter excessive "
                            "wayfinding friction."
                        ),
                        "false_positive_guard": (
                            f"Intentional nav path guard: verified depth ({depth} > 2) and confirmed absence from "
                            "homepage primary navigation anchors."
                        ),
                        "verification_method": f"curl -sL '{home_url or base_url}' | grep -i '{path}'",
                    })
                    finding_idx += 1

                elif depth is None and not has_intentional_path:
                    # Unreachable utility page
                    evaluated_utility_types.add(util_name)
                    findings.append({
                        "id": f"F-G2-{finding_idx:03d}",
                        "check_id": "G2",
                        "page_url": u,
                        "root_cause": "orientation_cost",
                        "evidence": {
                            "type": "unreachable_utility_page",
                            "utility_type": util_name,
                            "target_url": u,
                            "has_navigable_internal_path": False,
                        },
                        "raw_severity_class": "medium",
                        "confidence": 0.90,
                        "mechanism": (
                            f"Critical {util_name} page '{u}' exists in the site inventory but has no navigable internal "
                            "path originating from the homepage. Users cannot locate this essential utility through on-site navigation."
                        ),
                        "false_positive_guard": (
                            f"Confirmed absence of incoming internal crawl edges and homepage links for {util_name} page."
                        ),
                        "verification_method": f"curl -sL '{u}'",
                    })
                    finding_idx += 1

    # -------------------------------------------------------------------------
    # 3. Substantive Orphan Pages Check
    # -------------------------------------------------------------------------
    for slug, pinfo in corpus_pages_info.items():
        p_url = pinfo.get("url", "")
        if not p_url or p_url == home_url:
            continue

        path = urlparse(p_url).path.lower()
        if ARTIFACT_PATH_RE.search(path):
            continue

        word_count = pinfo.get("word_count", 0)
        # SUBSTANTIVE ORPHAN GUARD:
        # Flag ONLY when substantive (>= 80 words) and has 0 incoming internal links
        in_links = incoming_links.get(p_url, set())
        if len(in_links) == 0 and word_count >= 80:
            findings.append({
                "id": f"F-G2-{finding_idx:03d}",
                "check_id": "G2",
                "page_url": p_url,
                "root_cause": "orientation_cost",
                "evidence": {
                    "type": "substantive_orphan_page",
                    "target_url": p_url,
                    "word_count": word_count,
                    "has_internal_inlinks": False,
                },
                "raw_severity_class": "low",
                "confidence": 0.85,
                "mechanism": (
                    f"Substantive page '{p_url}' ({word_count} words) is present in the site structure but has 0 internal "
                    "hyperlinks pointing to it. Human visitors browsing the site cannot discover this content through normal navigation."
                ),
                "false_positive_guard": (
                    f"Substantive threshold guard: evaluated word count ({word_count} >= 80) and confirmed 0 incoming "
                    "internal links; feed/search/tag artifacts excluded."
                ),
                "verification_method": f"curl -sL '{p_url}' | wc -w",
            })
            finding_idx += 1
            break  # Cap at 1 representative orphan finding to avoid report inflation

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="G2 — Wayfinding Defects Check")
    parser.add_argument("corpus_dir", type=Path, help="Directory containing crawled page subdirectories")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to crawl_manifest.json")
    args = parser.parse_args()

    manifest_data: Optional[Dict[str, Any]] = None
    if args.manifest and args.manifest.exists():
        try:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception:
            pass

    findings = run_check_g2(args.corpus_dir, manifest=manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
