#!/usr/bin/env python3
"""
check_e1.py — E1 Missing structured data for inferred archetype check.

Uses Prompt 4's validated archetype classifier to detect the site's primary archetype,
identifies archetype-diagnostic pages (e.g. product pages, articles, location pages),
and checks for the presence of matching schema.org structured data (JSON-LD, Microdata, RDFa).

Following the project constitution:
- The archetype gate IS the false-positive guard: never demands Product schema for blog/docs.
- Only fires when confidence in archetype is high and diagnostic page patterns are present.
- Skips sites classified as 'unknown'.
- Evidence: e.g. "X product-pattern pages crawled; 0 contain Product/Offer structured data."
- Output: JSON list of candidate findings conforming to CandidateFinding schema.

Usage:
    python check_e1.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import archetype  # noqa: E402
from structured_data import extract_structured_data  # noqa: E402

# Expected schema.org types by archetype
ARCHETYPE_EXPECTED_SCHEMAS: Dict[str, Set[str]] = {
    "ecommerce": {"Product", "Offer", "AggregateOffer", "ItemList", "IndividualProduct"},
    "saas": {"SoftwareApplication", "WebApplication", "Organization", "TechArticle"},
    "content": {"Article", "BlogPosting", "BlogPost", "TechArticle"},
    "news": {"NewsArticle", "ReportageNewsArticle", "Article"},
    "local_business": {
        "LocalBusiness", "Restaurant", "Store", "MedicalBusiness", "Dentist",
        "Hotel", "FoodEstablishment", "LodgingBusiness", "AutoDealer", "CleaningService",
    },
    "corporate": {"Organization", "Corporation"},
}

PRODUCT_PATH_RE = re.compile(r"/(?:products?|items?|goods|shop|catalog|p)/[^/]+", re.IGNORECASE)
ARTICLE_PATH_RE = re.compile(r"/(?:blog|posts?|articles?|stories|news|insights)/[^/]+", re.IGNORECASE)


def _is_diagnostic_page_for_archetype(url: str, html: str, archetype_name: str) -> bool:
    """
    Check if a page exhibits concrete diagnostic patterns for the archetype
    (e.g. product detail pattern, article pattern).
    """
    path = urlparse(url).path.lower()

    if archetype_name == "ecommerce":
        # Specific product detail page pattern
        if PRODUCT_PATH_RE.search(path):
            return True
        # Or page has buy/cart buttons alongside price pattern
        has_price = bool(re.search(r"[$€£]\s*\d+(?:\.\d{2})?", html))
        has_buy_button = bool(re.search(r'(?:add\s+to\s+cart|buy\s+now|checkout)', html, re.IGNORECASE))
        return has_price and has_buy_button

    elif archetype_name in ("content", "news"):
        if ARTICLE_PATH_RE.search(path):
            return True
        # Or has clear byline and publication date in document
        has_byline = bool(re.search(r'class=["\'][^"\']*(?:byline|author)[^"\']*["\']', html, re.IGNORECASE))
        has_pubdate = bool(re.search(r'class=["\'][^"\']*(?:pubdate|date|publish)[^"\']*["\']', html, re.IGNORECASE))
        return has_byline and has_pubdate

    elif archetype_name == "saas":
        # Homepage or pricing page of a confirmed SaaS site
        return path in ("/", "", "/index.html", "/pricing", "/features")

    elif archetype_name == "local_business":
        return path in ("/", "", "/contact", "/location", "/about", "/visit")

    elif archetype_name == "corporate":
        return path in ("/", "", "/about", "/company")

    return False


def run_check_e1(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute E1 check across all crawled pages in corpus_dir."""
    findings: List[Dict[str, Any]] = []

    # 1. Infer archetype using the validated classifier
    primary_archetype = "unknown"
    if manifest:
        try:
            sig = archetype.extract_signals(manifest, corpus_dir)
            scores = archetype.score_archetypes(sig)
            archs, _ = archetype.select_archetypes(scores, sig)
            if archs and archs[0] != "unknown":
                primary_archetype = archs[0]
        except Exception:
            pass

    # Archetype Gate: Never demand structured data if site archetype is unknown
    if primary_archetype == "unknown" or primary_archetype not in ARCHETYPE_EXPECTED_SCHEMAS:
        return []

    expected_types = ARCHETYPE_EXPECTED_SCHEMAS[primary_archetype]

    diagnostic_pages: List[Tuple[str, str, Path]] = []  # (url, html, page_dir)

    for page_dir in sorted(corpus_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        meta_path = page_dir / "meta.json"
        html_path = page_dir / "raw.html"

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

        html = html_path.read_text(encoding="utf-8", errors="replace")
        if _is_diagnostic_page_for_archetype(url, html, primary_archetype):
            diagnostic_pages.append((url, html, page_dir))

    # If no diagnostic pages observed, do not fire
    if not diagnostic_pages:
        return []

    # Check structured data on diagnostic pages
    pages_lacking_schema: List[str] = []
    for url, html, page_dir in diagnostic_pages:
        records = extract_structured_data(html)
        found_types = {r.type for r in records}
        if not (found_types & expected_types):
            pages_lacking_schema.append(url)

    # Flag when structured data is missing on diagnostic pages
    if pages_lacking_schema:
        primary_url = pages_lacking_schema[0]
        expected_str = "/".join(sorted(expected_types)[:3])
        evidence_msg = (
            f"{len(diagnostic_pages)} {primary_archetype}-pattern pages crawled; "
            f"{len(pages_lacking_schema)} lack {expected_str} structured data."
        )

        findings.append({
            "id": f"F-E1-{len(findings) + 1:03d}",
            "check_id": "E1",
            "page_url": primary_url,
            "root_cause": "corroboration_deficit",
            "evidence": {
                "type": "missing_archetype_structured_data",
                "inferred_archetype": primary_archetype,
                "diagnostic_pages_count": len(diagnostic_pages),
                "unannotated_pages_count": len(pages_lacking_schema),
                "unannotated_urls": pages_lacking_schema[:5],
                "expected_schema_types": sorted(expected_types),
                "evidence_summary": evidence_msg,
            },
            "raw_severity_class": "medium",
            "confidence": 0.88,
            "mechanism": (
                f"Site was classified as '{primary_archetype}', but {len(pages_lacking_schema)} of "
                f"{len(diagnostic_pages)} diagnostic pages lack {expected_str} structured data markup. "
                "AI search engines and assistants rely on schema.org entities to extract products, articles, "
                "or business identities with high factual confidence. Lacking schema, assistants may fail to "
                "surface these entities in answer cards or direct answers."
            ),
            "false_positive_guard": (
                f"Archetype gate: evaluated strictly for '{primary_archetype}' schemas ({expected_str}). "
                f"Evaluated {len(diagnostic_pages)} diagnostic pages matching verified {primary_archetype} patterns. "
                "Extracted JSON-LD, Microdata, and RDFa before declaring schema absent."
            ),
            "verification_method": f"curl -s {primary_url} | grep -i 'application/ld+json'",
        })

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check E1: Missing structured data for inferred archetype")
    parser.add_argument("corpus_dir", type=Path, help="Directory containing crawled page subdirectories")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to crawl_manifest.json")
    args = parser.parse_args()

    manifest_data: Optional[Dict[str, Any]] = None
    if args.manifest and args.manifest.exists():
        try:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception:
            pass

    findings = run_check_e1(args.corpus_dir, manifest=manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
