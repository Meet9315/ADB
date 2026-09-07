#!/usr/bin/env python3
"""
check_e1.py — E1 Missing structured data for inferred archetype check.

Uses Prompt 4's validated archetype classifier to detect the site's primary archetype,
identifies archetype-diagnostic pages (e.g. product pages, articles, location pages),
and checks for the presence of matching schema.org structured data (JSON-LD, Microdata, RDFa).

Following the project constitution:
- The archetype gate IS the false-positive guard: never demands Product schema for blog/docs.
- Expected schema requirements are archetype/diagnostic-pattern specific rather than treating
  all related types as interchangeable (e.g. ecommerce product pages specifically require Product
  rather than being satisfied by ItemList or generic Organization).
- Verification command corresponds to all supported syntaxes (JSON-LD, Microdata, RDFa).
- Only fires when confidence in archetype is high and diagnostic page patterns are present.
- Skips sites classified as 'unknown'.
- Evidence: e.g. "X product-pattern pages crawled; Y lack Product/IndividualProduct structured data."
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

PRODUCT_DETAIL_PATH_RE = re.compile(r"/(?:products?|items?|goods|p)/[^/]+", re.IGNORECASE)
CATALOG_PATH_RE = re.compile(r"/(?:catalog|collections?|shop|categories?)/?[^/]*$", re.IGNORECASE)
ARTICLE_PATH_RE = re.compile(r"/(?:blog|posts?|articles?|stories|news|insights)/[^/]+", re.IGNORECASE)


def _get_diagnostic_page_expected_schemas(
    url: str, html: str, archetype_name: str
) -> Optional[Tuple[str, Set[str]]]:
    """
    Determine if a page is diagnostic for the given archetype and return
    (diagnostic_pattern_name, expected_schema_set).
    Enforces archetype- and diagnostic-pattern-specific schema requirements rather
    than treating broad related schema types as interchangeable.
    """
    path = urlparse(url).path.lower().rstrip("/")
    if not path:
        path = "/"

    if archetype_name == "ecommerce":
        # 1. Product detail page: requires primary Product entity (not generic ItemList or Organization)
        has_price = bool(re.search(r"[$€£]\s*\d+(?:\.\d{2})?", html))
        has_buy_button = bool(re.search(r'(?:add\s+to\s+cart|buy\s+now|checkout)', html, re.IGNORECASE))
        if PRODUCT_DETAIL_PATH_RE.search(path) or (has_price and has_buy_button):
            return "product_detail", {"Product", "IndividualProduct"}
        # 2. Product catalog / collection listing
        if CATALOG_PATH_RE.search(path):
            return "catalog_listing", {"ItemList", "Product"}

    elif archetype_name == "saas":
        # Core software offering: requires actual software/application entity,
        # not generic Organization/WebSite which creates false negatives
        if path in ("/", "/pricing", "/features", "/product", "/platform"):
            return "software_offering", {"SoftwareApplication", "WebApplication", "SaaS", "Product"}

    elif archetype_name == "news":
        # News article pages: requires NewsArticle or Article
        has_byline = bool(re.search(r'class=["\'][^"\']*(?:byline|author)[^"\']*["\']', html, re.IGNORECASE))
        has_pubdate = bool(re.search(r'class=["\'][^"\']*(?:pubdate|date|publish)[^"\']*["\']', html, re.IGNORECASE))
        if ARTICLE_PATH_RE.search(path) or (has_byline and has_pubdate):
            return "news_article", {"NewsArticle", "ReportageNewsArticle", "Article"}

    elif archetype_name == "content":
        # Content / blog article pages: requires Article or BlogPosting
        has_byline = bool(re.search(r'class=["\'][^"\']*(?:byline|author)[^"\']*["\']', html, re.IGNORECASE))
        has_pubdate = bool(re.search(r'class=["\'][^"\']*(?:pubdate|date|publish)[^"\']*["\']', html, re.IGNORECASE))
        if ARTICLE_PATH_RE.search(path) or (has_byline and has_pubdate):
            return "article", {"Article", "BlogPosting", "BlogPost"}

    elif archetype_name == "local_business":
        if path in ("/", "/contact", "/location", "/locations", "/about", "/visit"):
            return "local_business", {
                "LocalBusiness", "Restaurant", "Store", "MedicalBusiness", "Dentist",
                "Hotel", "FoodEstablishment", "LodgingBusiness", "AutoDealer", "CleaningService",
            }

    elif archetype_name == "corporate":
        if path in ("/", "/about", "/company"):
            return "corporate_identity", {"Organization", "Corporation"}

    return None


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

    # Archetype Gate: Never demand structured data if site archetype is unknown or unsupported
    supported_archetypes = {"ecommerce", "saas", "content", "news", "local_business", "corporate"}
    if primary_archetype == "unknown" or primary_archetype not in supported_archetypes:
        return []

    # (url, html, pattern_name, expected_schemas)
    diagnostic_pages: List[Tuple[str, str, str, Set[str]]] = []

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
        diag_info = _get_diagnostic_page_expected_schemas(url, html, primary_archetype)
        if diag_info is not None:
            pattern_name, expected_types = diag_info
            diagnostic_pages.append((url, html, pattern_name, expected_types))

    # If no diagnostic pages observed, do not fire
    if not diagnostic_pages:
        return []

    # Group diagnostic pages by pattern for precise defect reporting
    grouped_pages: Dict[str, List[Tuple[str, str, Set[str]]]] = {}
    for url, html, pattern_name, expected_types in diagnostic_pages:
        grouped_pages.setdefault(pattern_name, []).append((url, html, expected_types))

    for pattern_name, p_list in sorted(grouped_pages.items()):
        expected_types = p_list[0][2]
        pages_lacking_schema: List[str] = []

        for url, html, exp in p_list:
            records = extract_structured_data(html)
            found_types = {r.schema_type for r in records}
            if not (found_types & exp):
                pages_lacking_schema.append(url)

        if pages_lacking_schema:
            primary_url = pages_lacking_schema[0]
            expected_str = "/".join(sorted(expected_types)[:3])
            evidence_msg = (
                f"{len(p_list)} {primary_archetype} ({pattern_name}) diagnostic pages crawled; "
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
                    "diagnostic_pattern": pattern_name,
                    "diagnostic_pages_count": len(p_list),
                    "unannotated_pages_count": len(pages_lacking_schema),
                    "unannotated_urls": pages_lacking_schema[:5],
                    "expected_schema_types": sorted(expected_types),
                    "evidence_summary": evidence_msg,
                },
                "raw_severity_class": "medium",
                "confidence": 0.88,
                "mechanism": (
                    f"Site was classified as '{primary_archetype}', but {len(pages_lacking_schema)} of "
                    f"{len(p_list)} {pattern_name} diagnostic pages lack {expected_str} structured data markup. "
                    "AI search engines and assistants rely on schema.org entities to extract products, articles, "
                    "or software identities with high factual confidence. Lacking schema, assistants may fail to "
                    "surface these entities in direct answers."
                ),
                "false_positive_guard": (
                    f"Archetype gate: evaluated strictly for '{primary_archetype}' {pattern_name} schemas ({expected_str}). "
                    f"Evaluated {len(p_list)} diagnostic pages matching verified {primary_archetype} patterns. "
                    "Extracted JSON-LD, Microdata, and RDFa across DOM before declaring schema absent."
                ),
                "verification_method": f"curl -sL {primary_url} | grep -E -i 'application/ld\\+json|itemtype=[\"\\']https?://schema\\.org/|typeof='",
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
