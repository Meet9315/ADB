#!/usr/bin/env python3
"""
check_d3.py — D3 Semantic structure absent check.

Evaluates:
- Missing <h1> landmark on substantive pages
- Broken heading hierarchy (skipping heading levels downwards, e.g. h1 -> h3 without h2)
- Missing <main> landmark (neither <main> tag nor role="main" present)

Following the project constitution:
- Strictly minor/low severity regardless of findings (avoids SEO checker overweight trap).
- Evaluates only substantive pages (word count >= 80, HTTP 200).
- Excludes utility/login/checkout/404 pages.
- Output: JSON list of candidate findings conforming to the CandidateFinding schema.

Usage:
    python check_d3.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Utility/private pages to exclude from semantic structure requirements
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


def _check_heading_hierarchy(html: str) -> Tuple[bool, List[str]]:
    """
    Check if heading levels skip levels downwards (e.g. h1 directly to h3).
    Returns (has_broken_hierarchy, list_of_violations).
    """
    headings = re.findall(r"<h([1-6])\b[^>]*>", html, re.IGNORECASE)
    if not headings:
        return False, []

    levels = [int(h) for h in headings]
    violations: List[str] = []

    prev = levels[0]
    for lvl in levels[1:]:
        # Downward skip of 2 or more levels (e.g. h1 -> h3, h2 -> h4)
        if lvl - prev >= 2:
            violations.append(f"h{prev} jumped directly to h{lvl}")
        prev = lvl

    return bool(violations), violations


def _is_main_landmark_present(html: str) -> bool:
    """Check if page has a <main> tag, role='main', or landmark id within an HTML tag."""
    if re.search(r"<main\b[^>]*>", html, re.IGNORECASE):
        return True
    if re.search(r'<[a-z0-9]+\b[^>]*\brole=["\']main["\']', html, re.IGNORECASE):
        return True
    if re.search(r'<[a-z0-9]+\b[^>]*\bid=["\'](?:main|main-content|content|primary)["\']', html, re.IGNORECASE):
        return True
    return False


def run_check_d3(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute D3 check across all crawled pages in corpus_dir."""
    findings: List[Dict[str, Any]] = []

    for page_dir in sorted(corpus_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        meta_path = page_dir / "meta.json"
        html_path = page_dir / "raw.html"
        text_path = page_dir / "text.txt"

        if not meta_path.exists() or not html_path.exists():
            continue

        meta: Dict[str, Any] = {}
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        url = meta.get("final_url") or meta.get("url", "")
        if not url and manifest:
            for cp in manifest.get("crawled_pages", []):
                if cp.get("slug") == page_dir.name:
                    url = cp.get("final_url") or cp.get("url", "")
                    break

        if not url:
            continue

        status = meta.get("status_code", 200)
        if status != 200:
            continue

        html = html_path.read_text(encoding="utf-8", errors="replace")
        visible_text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
        word_count = len([w for w in visible_text.split() if len(w) > 2])

        # Guard: thin or utility pages should not be audited for semantic landmarks
        if word_count < 80:
            continue

        title = meta.get("title", "")
        if _is_excluded_page(url, title):
            continue

        has_h1 = bool(re.search(r"<h1\b[^>]*>", html, re.IGNORECASE))
        has_main = _is_main_landmark_present(html)
        has_broken_hierarchy, violations = _check_heading_hierarchy(html)

        # 1. Missing h1
        if not has_h1:
            findings.append({
                "id": f"F-D3-{len(findings) + 1:03d}",
                "check_id": "D3",
                "page_url": url,
                "root_cause": "representation_gap",
                "evidence": {
                    "type": "missing_h1",
                    "visible_word_count": word_count,
                    "headings_found": re.findall(r"<h([1-6])\b[^>]*>", html, re.IGNORECASE)[:10],
                },
                "raw_severity_class": "low",
                "confidence": 0.90,
                "mechanism": (
                    f"Page '{url}' contains {word_count} visible words but lacks an <h1> heading. "
                    "AI summarizers and document extractors rely on <h1> as the primary topic landmark "
                    "to anchor document outlines."
                ),
                "false_positive_guard": (
                    f"Page has {word_count} visible words (threshold >= 80). Verified that no <h1> tag "
                    "exists anywhere in the raw HTML. Excluded utility and auth paths."
                ),
                "verification_method": f"curl -s {url} | grep -i '<h1'",
            })

        # 2. Missing main landmark
        if not has_main:
            findings.append({
                "id": f"F-D3-{len(findings) + 1:03d}",
                "check_id": "D3",
                "page_url": url,
                "root_cause": "representation_gap",
                "evidence": {
                    "type": "missing_main_landmark",
                    "visible_word_count": word_count,
                    "has_main_tag": False,
                    "has_role_main": False,
                },
                "raw_severity_class": "low",
                "confidence": 0.85,
                "mechanism": (
                    f"Page '{url}' lacks a <main> element or role='main' landmark. "
                    "Autonomous web agents separating primary article/product content from boilerplate "
                    "navigation, headers, and footers must resort to heuristics, increasing parsing latency."
                ),
                "false_positive_guard": (
                    f"Page has {word_count} visible words. Verified absence of both <main> element "
                    "and role='main' attribute across DOM."
                ),
                "verification_method": f"curl -s {url} | grep -E -i '<main|role=[\"\\']main'",
            })

        # 3. Broken heading hierarchy
        if has_broken_hierarchy and len(violations) >= 1:
            findings.append({
                "id": f"F-D3-{len(findings) + 1:03d}",
                "check_id": "D3",
                "page_url": url,
                "root_cause": "representation_gap",
                "evidence": {
                    "type": "broken_heading_hierarchy",
                    "violations": violations[:5],
                    "total_violations": len(violations),
                },
                "raw_severity_class": "low",
                "confidence": 0.80,
                "mechanism": (
                    f"Page '{url}' skips heading levels downwards ({', '.join(violations[:2])}). "
                    "LLMs constructing hierarchical section outlines may misinterpret nested subsections "
                    "as parent entities or skip context."
                ),
                "false_positive_guard": (
                    f"Detected {len(violations)} downward level skip(s) >= 2 levels. Upward transitions "
                    "(closing subsections) were ignored. Verified in document source order."
                ),
                "verification_method": f"curl -s {url} | grep -o -E -i '<h[1-6]'",
            })

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check D3: Semantic structure absent")
    parser.add_argument("corpus_dir", type=Path, help="Directory containing crawled page subdirectories")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to crawl_manifest.json")
    args = parser.parse_args()

    manifest_data: Optional[Dict[str, Any]] = None
    if args.manifest and args.manifest.exists():
        try:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception:
            pass

    findings = run_check_d3(args.corpus_dir, manifest=manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
