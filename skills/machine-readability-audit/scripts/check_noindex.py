#!/usr/bin/env python3
"""
check_noindex.py — R4: Detect noindex directives on substantive pages.

Reads each page's meta.json (response headers) and raw.html (meta robots tag)
from the corpus directory. Emits candidate findings to stdout in the hardened
finding contract format.

Usage:
    python check_noindex.py <corpus_dir> [--manifest <crawl_manifest.json>]

DO NOT FIRE when:
- The page URL or <title> matches the hardcoded exclusion list of
  legitimately private/transient page types:
    /cart, /login, /signin, /sign-in, /checkout, /account, /register,
    /registration, /search, /results, /404, /500, /admin, /dashboard,
    /my-account, /wishlist, /basket, /order-confirmation,
    title contains: Login, Sign in, Cart, Checkout, Search Results,
                    Register, My Account, Order Confirmation
  This exclusion list is mechanism-based (pages that are legitimately excluded
  from search indexing everywhere) and must never be extended with site-specific
  carve-outs. If a page doesn't fit these categories, it is either a real
  finding or requires adding a new generic mechanism-based category.
- noindex appears only in a non-authoritative tag (e.g. inside a JavaScript
  string or HTML comment, not a real meta tag or header).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Exclusion list — mechanism-based, never site-specific
# ---------------------------------------------------------------------------

# URL path segments that indicate legitimately excluded page types
EXCLUDED_PATH_SEGMENTS = {
    "cart", "login", "signin", "sign-in", "checkout", "account",
    "register", "registration", "search", "results", "404", "500",
    "admin", "dashboard", "my-account", "wishlist", "basket",
    "order-confirmation", "logout", "sign-out", "forgot-password",
    "reset-password", "verify-email",
}

# Title keywords for legitimately excluded page types (case-insensitive)
EXCLUDED_TITLE_KEYWORDS = {
    "login", "sign in", "sign-in", "cart", "checkout", "search results",
    "register", "registration", "my account", "order confirmation",
    "sign up", "404", "page not found", "forbidden", "access denied",
    "reset password", "forgot password",
}

FINDING_ID_COUNTER: Dict[str, int] = {}


def _new_id(check_id: str) -> str:
    FINDING_ID_COUNTER[check_id] = FINDING_ID_COUNTER.get(check_id, 0) + 1
    return f"F-{check_id}-{FINDING_ID_COUNTER[check_id]:03d}"


def _is_excluded_page(url: str, title: str) -> Tuple[bool, str]:
    """Return (is_excluded, reason) for this page."""
    path = urlparse(url).path.lower().strip("/")
    path_parts = set(path.split("/"))

    matched_seg = path_parts & EXCLUDED_PATH_SEGMENTS
    if matched_seg:
        return True, f"URL path contains excluded segment: {sorted(matched_seg)}"

    title_lower = (title or "").lower()
    for kw in EXCLUDED_TITLE_KEYWORDS:
        if kw in title_lower:
            return True, f"Page title contains excluded keyword: '{kw}'"

    return False, ""


def _has_noindex_header(headers: Dict) -> Optional[str]:
    """Detect noindex in X-Robots-Tag response header."""
    for k, v in headers.items():
        if k.lower() == "x-robots-tag":
            if "noindex" in v.lower():
                return v
    return None


def _has_noindex_meta(html: str) -> Optional[str]:
    """Detect noindex in <meta name="robots" ...> tag (not in comments or JS)."""
    # Strip HTML comments to avoid false matches
    html_stripped = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    # Find meta robots tags
    for m in re.finditer(
        r'<meta\s[^>]*name=["\']robots["\'][^>]*content=["\']([^"\']*)["\'][^>]*/?>',
        html_stripped, re.IGNORECASE
    ):
        content = m.group(1)
        if "noindex" in content.lower():
            return content
    return None


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def check_r4(corpus_dir: Path, manifest: Optional[Dict] = None) -> List[Dict]:
    """Run R4 on all pages in corpus_dir."""
    FINDING_ID_COUNTER["R4"] = 0
    findings: List[Dict] = []

    for page_dir in sorted(corpus_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        meta_path = page_dir / "meta.json"
        html_path = page_dir / "raw.html"

        if not meta_path.exists():
            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        url = meta.get("final_url") or meta.get("url", "")
        headers = meta.get("response_headers", {})
        status = meta.get("status_code", 200)

        # Only check successful pages
        if status != 200:
            continue

        html = html_path.read_text(encoding="utf-8", errors="replace") if html_path.exists() else ""
        title = _extract_title(html) or (
            meta.get("headings", {}).get("h1", [""])[0] if meta.get("headings") else ""
        )

        # Exclusion check (Rule 3 — negative logic)
        excluded, exclusion_reason = _is_excluded_page(url, title)
        if excluded:
            continue

        # Detection
        header_noindex = _has_noindex_header(headers)
        meta_noindex = _has_noindex_meta(html)

        if header_noindex or meta_noindex:
            source = "X-Robots-Tag header" if header_noindex else "<meta name='robots'>"
            directive = header_noindex or meta_noindex

            findings.append({
                "id": _new_id("R4"),
                "check_id": "R4",
                "page_url": url,
                "root_cause": "orientation_cost",
                "evidence": {
                    "type": "noindex_directive",
                    "source": source,
                    "directive_value": directive,
                    "page_title": title,
                    "status_code": status,
                },
                "raw_severity_class": "high",
                "confidence": 0.92,
                "mechanism": (
                    f"Page '{url}' carries a noindex directive via {source} "
                    f"(value: '{directive}'). Search engines and AI indexing bots "
                    "that respect robots directives will exclude this page from their index. "
                    "An AI assistant querying for this page's content will receive no cached "
                    "or indexed version, forcing it to either fetch live (if allowed) or omit "
                    "the content entirely."
                ),
                "false_positive_guard": (
                    f"Exclusion list checked: URL path segments not in "
                    f"{sorted(EXCLUDED_PATH_SEGMENTS)[:6]}... "
                    f"Title keywords not in {sorted(EXCLUDED_TITLE_KEYWORDS)[:4]}... "
                    f"URL: '{url}', Title: '{title}'. "
                    "Page type not identified as legitimately private/transient. "
                    "noindex found in authoritative tag (not in HTML comment or JS string). "
                    "Exclusion reason: n/a (not excluded)."
                ),
                "verification_method": (
                    f"curl -sI {url} | grep -i x-robots ; "
                    f"curl -s {url} | grep -i 'name.*robots'"
                ),
            })

    return findings


def main() -> None:
    ap = argparse.ArgumentParser(description="R4 noindex check for machine-readability-audit")
    ap.add_argument("corpus_dir", help="Path to corpus pages directory")
    ap.add_argument("--manifest", default=None, help="Path to crawl_manifest.json (optional)")
    args = ap.parse_args()

    corpus_dir = Path(args.corpus_dir)
    if not corpus_dir.exists():
        print(f"[check_noindex] ERROR: corpus dir not found: {corpus_dir}", file=sys.stderr)
        sys.exit(1)

    manifest = None
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    findings = check_r4(corpus_dir, manifest)
    print(f"[check_noindex] R4: {len(findings)} finding(s)", file=sys.stderr)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
