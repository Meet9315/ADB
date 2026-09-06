#!/usr/bin/env python3
"""
archetype.py — Corpus-signal-based site archetype classifier.

Classifies a crawled site into one or more archetypes using ONLY observed
signals from the local corpus (raw HTML, text, URLs, crawl manifest).

Archetypes: ecommerce | saas | content | news | docs | portfolio |
            local_business | corporate

Usage:
    python archetype.py <crawl_manifest.json> [--corpus-dir <pages/>]

Output: JSON object to stdout with keys:
  archetypes         list[str]  — ordered by confidence, highest first
  is_tiny_site       bool       — true if < 8 crawled pages
  signals            dict       — every signal measured, as raw counts/booleans
  archetype_scores   dict       — raw score per archetype (for auditability)
  confidence_notes   list[str]  — human-readable explanation of top classification

Rules:
  - No domain name lookup, no category list, no hardcoded site names.
  - Every signal must be a value directly observable in corpus files.
  - A site with insufficient signal returns archetypes=["unknown"] with an
    explanation in confidence_notes.
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
# Signal extraction
# ---------------------------------------------------------------------------

# Schema.org types that are diagnostic for each archetype
ECOMMERCE_SCHEMA = {"Product", "Offer", "AggregateOffer", "ShoppingCart",
                    "BuyAction", "Order", "ItemList"}
SAAS_SCHEMA = {"SoftwareApplication", "WebApplication", "SaaS"}
NEWS_SCHEMA = {"NewsArticle", "ReportageNewsArticle", "LiveBlogPosting"}
CONTENT_SCHEMA = {"Article", "BlogPosting", "BlogPost"}
LOCAL_SCHEMA = {"LocalBusiness", "Restaurant", "Store", "MedicalBusiness",
                "Dentist", "Hotel", "FoodEstablishment", "LodgingBusiness",
                "AutoDealer", "CleaningService", "HomeAndConstructionBusiness"}
# Organization and WebSite are near-universal on modern sites — only Corporation is diagnostic.
# Organization/WebSite still count but at a much lower weight (see scoring section).
CORPORATE_SCHEMA_STRONG = {"Corporation"}
CORPORATE_SCHEMA_WEAK   = {"Organization", "WebSite"}
EVENT_SCHEMA = {"Event", "EventSeries"}
PORTFOLIO_SCHEMA = {"ImageGallery", "CreativeWork", "Person"}

# URL path patterns
DOCS_PATH_RE = re.compile(
    r"/(?:docs?|documentation|api(?:-reference)?|reference|sdk|guide|manual"
    r"|handbook|v\d+(?:\.\d+)*)/",
    re.IGNORECASE,
)
VERSIONED_PATH_RE = re.compile(r"/v\d+(?:\.\d+)+/", re.IGNORECASE)
BLOG_PATH_RE = re.compile(r"/(?:blog|posts?|articles?|news|insights?)/", re.IGNORECASE)
PORTFOLIO_PATH_RE = re.compile(
    r"/(?:portfolio|gallery|work|projects?|case-studies?|showcase)/", re.IGNORECASE
)

# HTML content patterns (applied to raw.html after stripping code blocks)
#
# CART_RE: match only class attributes and form actions, not arbitrary hrefs.
# href-based matching is too broad — any page linking to a payment provider
# (Stripe, PayPal) or mentioning /checkout in a URL has false positives.
CART_RE = re.compile(
    r'class=["\'][^"\']*(?:\badd-to-cart\b|\bbuy-now\b|\bshopping-cart\b|\bbasket-icon\b)[^"\']*["\']'
    r'|<form[^>]+action=["\'][^"\']*(?:/cart|/checkout|/basket)[^"\']*["\']'
    r'|<(?:button|a)[^>]*>\s*(?:Add\s+to\s+(?:Cart|Bag|Basket)|Buy\s+Now)\s*</(?:button|a)>',
    re.IGNORECASE,
)
PRICE_RE = re.compile(
    r'(?:\$|€|£|¥|USD|EUR|GBP)\s*\d[\d,]*(?:\.\d{2})?'
    r'|\d[\d,]*(?:\.\d{2})?\s*(?:USD|EUR|GBP)',
    re.IGNORECASE,
)
PRICING_PAGE_TITLE_RE = re.compile(
    r'pricing|plans?\s+(?:and\s+pricing|&\s+pricing)|choose\s+(?:a\s+)?plan'
    r'|subscription|upgrade\s+plan',
    re.IGNORECASE,
)
BYLINE_RE = re.compile(
    r'<(?:span|div|p|address)[^>]*(?:author|byline|written[-\s]by|posted[-\s]by)[^>]*>'
    r'|by\s+<(?:a|span|strong)[^>]*>',
    re.IGNORECASE,
)
ARTICLE_DATE_RE = re.compile(
    r'<(?:time|span|p)[^>]*(?:datetime|published|date)[^>]*>'
    r'|\bpublished\b|\bposted\b',
    re.IGNORECASE,
)
DEMO_CTA_RE = re.compile(
    r'(?:request|book|schedule|get|try|start)\s+(?:a\s+)?(?:free\s+)?'
    r'(?:demo|trial|access|consultation)',
    re.IGNORECASE,
)
SAAS_FEATURE_RE = re.compile(
    r'(?:integrat(?:ion|e)|dashboard|analytics|automat(?:ion|e)|workflow'
    r'|API|webhook|SSO|SAML|enterprise\s+plan|per\s+(?:seat|user|month))',
    re.IGNORECASE,
)
ADDRESS_RE = re.compile(
    r'\b\d{1,5}\s+\w+(?:\s+\w+)?\s+(?:St(?:reet)?|Ave(?:nue)?|Rd|Road'
    r'|Blvd|Boulevard|Dr(?:ive)?|Ln|Lane|Way|Court|Ct|Place|Pl)\b',
    re.IGNORECASE,
)
HOURS_RE = re.compile(
    r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s*[-–]\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*'
    r'|\b(?:open|hours?|closes?|closing)\b.{0,40}\d{1,2}(?::\d{2})?\s*(?:am|pm)',
    re.IGNORECASE,
)
PHONE_RE = re.compile(
    r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    r'|tel:\+?[\d\s\-()]{7,}',
    re.IGNORECASE,
)
NAV_LINK_RE = re.compile(
    r'<a[^>]*href=["\']([^"\'#?][^"\']*)["\'][^>]*>',
    re.IGNORECASE,
)
PORTFOLIO_KEYWORD_RE = re.compile(
    r'\b(?:portfolio|my\s+work|case\s+stud(?:y|ies)|selected\s+works?'
    r'|creative\s+director|art\s+director|photographer|illustrator|designer)\b',
    re.IGNORECASE,
)
CODE_BLOCK_RE = re.compile(r'<(?:pre|code)[^>]*>', re.IGNORECASE)


def _extract_schema_types(html: str) -> List[str]:
    """Extract @type values from JSON-LD blocks in HTML."""
    types: List[str] = []
    for ld_match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(ld_match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        # Handle single object or @graph array
        items = data if isinstance(data, list) else [data]
        items += data.get("@graph", []) if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict):
                t = item.get("@type", "")
                if isinstance(t, list):
                    types.extend(t)
                elif t:
                    types.append(t)
    return types


def _extract_page_urls(manifest: Dict) -> List[str]:
    return [p.get("final_url") or p.get("url", "") for p in manifest.get("crawled_pages", [])]


def extract_signals(manifest: Dict, corpus_dir: Path) -> Dict:
    """
    Measure every observable signal from the corpus. Returns a flat dict of
    counts and booleans — every value is directly traceable to corpus content.
    """
    sig: Dict = {
        # Schema types
        "schema_types_found": [],
        # Ecommerce
        "pages_with_cart_link": 0,
        "pages_with_price": 0,
        "has_pricing_page": False,
        "pricing_page_url": None,
        # SaaS — pricing context is now independent of product schema
        "has_pricing_page_saas_context": False,   # pricing page + no cart/product schema
        "has_pricing_page_plus_demo": False,       # pricing page + demo CTA (works even with product schema)
        "pages_with_demo_cta": 0,
        "pages_with_saas_features": 0,
        # Content / news
        "pages_with_byline": 0,
        "pages_with_article_date": 0,
        "blog_path_pages": 0,
        "news_path_pages": 0,
        # Docs
        "docs_path_pages": 0,
        "versioned_path_pages": 0,
        "pages_with_code_blocks": 0,
        # Portfolio
        "portfolio_path_pages": 0,
        "pages_with_portfolio_keyword": 0,
        # Local business — checked on text with code blocks stripped
        "pages_with_address": 0,
        "pages_with_hours": 0,
        "pages_with_phone": 0,
        # Counts
        "total_crawled_pages": len(manifest.get("crawled_pages", [])),
        "total_nav_links": 0,
    }

    schema_types_seen: List[str] = []
    page_urls = _extract_page_urls(manifest)

    for page_dir in sorted(corpus_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        html_path = page_dir / "raw.html"
        meta_path = page_dir / "meta.json"
        if not html_path.exists() or not meta_path.exists():
            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("status_code") != 200:
            continue

        html = html_path.read_text(encoding="utf-8", errors="replace")
        url = meta.get("final_url") or meta.get("url", "")
        url_lower = url.lower()
        path = urlparse(url).path.lower()

        # Schema types
        schema_types_seen.extend(_extract_schema_types(html))

        # Cart / ecommerce signals
        if CART_RE.search(html):
            sig["pages_with_cart_link"] += 1
        if PRICE_RE.search(html):
            sig["pages_with_price"] += 1

        # Pricing page
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        page_title = title_match.group(1).strip() if title_match else ""
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        h1_text = re.sub(r"<[^>]+>", "", h1_match.group(1)).strip() if h1_match else ""

        is_pricing = (
            "/pricing" in path
            or PRICING_PAGE_TITLE_RE.search(page_title)
            or PRICING_PAGE_TITLE_RE.search(h1_text)
        )
        if is_pricing and not sig["has_pricing_page"]:
            sig["has_pricing_page"] = True
            sig["pricing_page_url"] = url

        # SaaS-specific
        if DEMO_CTA_RE.search(html):
            sig["pages_with_demo_cta"] += 1
        if SAAS_FEATURE_RE.search(html):
            sig["pages_with_saas_features"] += 1

        # Content / news signals
        if BYLINE_RE.search(html):
            sig["pages_with_byline"] += 1
        if ARTICLE_DATE_RE.search(html):
            sig["pages_with_article_date"] += 1
        if BLOG_PATH_RE.search(url):
            sig["blog_path_pages"] += 1
        if re.search(r"/news/", url, re.IGNORECASE):
            sig["news_path_pages"] += 1

        # Docs signals
        if DOCS_PATH_RE.search(url):
            sig["docs_path_pages"] += 1
        if VERSIONED_PATH_RE.search(url):
            sig["versioned_path_pages"] += 1
        if CODE_BLOCK_RE.search(html):
            sig["pages_with_code_blocks"] += 1

        # Portfolio signals
        if PORTFOLIO_PATH_RE.search(url):
            sig["portfolio_path_pages"] += 1
        if PORTFOLIO_KEYWORD_RE.search(html):
            sig["pages_with_portfolio_keyword"] += 1

        # Local business — strip <pre>/<code> blocks first to avoid matching
        # phone numbers and addresses that appear in code examples or article text.
        html_no_code = re.sub(r"<(?:pre|code)[^>]*>.*?</(?:pre|code)>", " ", html,
                              flags=re.DOTALL | re.IGNORECASE)
        if ADDRESS_RE.search(html_no_code):
            sig["pages_with_address"] += 1
        if HOURS_RE.search(html_no_code):
            sig["pages_with_hours"] += 1
        if PHONE_RE.search(html_no_code):
            sig["pages_with_phone"] += 1

        # Nav links count
        sig["total_nav_links"] += len(NAV_LINK_RE.findall(html))

    # Deduplicate and store schema types
    sig["schema_types_found"] = sorted(set(schema_types_seen))

    # Derived signals
    product_schema = bool(ECOMMERCE_SCHEMA & set(schema_types_seen))
    cart_heavy = sig["pages_with_cart_link"] >= 3   # many cart UI elements = ecommerce-first

    # SaaS pricing context: pricing page exists but site is not primarily a storefront
    if sig["has_pricing_page"] and not product_schema and not cart_heavy:
        sig["has_pricing_page_saas_context"] = True

    # SaaS pricing+demo: pricing page + demo CTA regardless of product schema.
    # Catches SaaS tools that happen to have Product schema (e.g. Shopify, Hubspot).
    if sig["has_pricing_page"] and sig["pages_with_demo_cta"] >= 1:
        sig["has_pricing_page_plus_demo"] = True

    return sig


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_archetypes(sig: Dict) -> Dict[str, float]:
    """
    Compute a raw score (0.0–∞) for each archetype from observed signals.
    Higher = stronger evidence. Scores are not probabilities; they are
    evidence weights designed to be compared against each other.

    Every addend is documented with the signal it rewards and why.
    """
    schema = set(sig.get("schema_types_found", []))
    pages = max(sig["total_crawled_pages"], 1)

    scores: Dict[str, float] = {
        "ecommerce": 0.0,
        "saas": 0.0,
        "content": 0.0,
        "news": 0.0,
        "docs": 0.0,
        "portfolio": 0.0,
        "local_business": 0.0,
        "corporate": 0.0,
    }

    # ----- ECOMMERCE -----
    # Schema types are strongest evidence
    scores["ecommerce"] += 4.0 * len(schema & ECOMMERCE_SCHEMA)
    # Cart links are definitive
    scores["ecommerce"] += 3.0 * min(sig["pages_with_cart_link"] / pages, 1.0)
    # Pricing with prices (not plans), especially if many pages have prices
    scores["ecommerce"] += 2.0 * min(sig["pages_with_price"] / pages, 1.0)
    # Pricing page with product schema = very likely ecommerce
    if sig["has_pricing_page"] and (schema & ECOMMERCE_SCHEMA):
        scores["ecommerce"] += 2.0

    # ----- SAAS -----
    scores["saas"] += 4.0 * len(schema & SAAS_SCHEMA)
    # Pricing page without cart/product schema = subscription-model (strong SaaS signal)
    if sig["has_pricing_page_saas_context"]:
        scores["saas"] += 3.0
    # Pricing page + demo CTA = SaaS regardless of schema (catches SaaS with Product schema)
    if sig["has_pricing_page_plus_demo"]:
        scores["saas"] += 2.5
    # Demo/trial CTAs are almost exclusively SaaS
    scores["saas"] += 2.0 * min(sig["pages_with_demo_cta"] / pages, 1.0)
    # SaaS feature vocabulary
    scores["saas"] += 1.5 * min(sig["pages_with_saas_features"] / pages, 1.0)
    # Prices on page (per-seat/per-user) — supporting signal, not definitive
    scores["saas"] += 0.5 * min(sig["pages_with_price"] / pages, 1.0)

    # ----- CONTENT/BLOG -----
    scores["content"] += 4.0 * len(schema & CONTENT_SCHEMA)
    # Bylines are the strongest non-schema signal for editorial content
    scores["content"] += 3.0 * min(sig["pages_with_byline"] / pages, 1.0)
    # Article dates
    scores["content"] += 2.0 * min(sig["pages_with_article_date"] / pages, 1.0)
    # Blog URL paths
    scores["content"] += 2.5 if sig["blog_path_pages"] >= 2 else (
        1.0 if sig["blog_path_pages"] == 1 else 0.0
    )

    # ----- NEWS -----
    scores["news"] += 5.0 * len(schema & NEWS_SCHEMA)  # NewsArticle is definitive
    scores["news"] += 3.0 * min(sig["pages_with_byline"] / pages, 1.0)
    scores["news"] += 2.0 * min(sig["pages_with_article_date"] / pages, 1.0)
    scores["news"] += 2.0 if sig["news_path_pages"] >= 2 else 0.0
    # News is high-velocity: many articles = many dates
    if sig["pages_with_article_date"] >= 5:
        scores["news"] += 1.5

    # ----- DOCS -----
    scores["docs"] += 4.0 if sig["docs_path_pages"] >= 3 else (
        2.0 if sig["docs_path_pages"] >= 1 else 0.0
    )
    scores["docs"] += 2.0 if sig["versioned_path_pages"] >= 1 else 0.0
    # Code blocks are common in docs
    scores["docs"] += 2.0 * min(sig["pages_with_code_blocks"] / pages, 1.0)
    # Docs rarely have cart UI elements (price strings are OK — docs often have pricing pages)
    if sig["pages_with_cart_link"] == 0:
        scores["docs"] += 0.5

    # ----- PORTFOLIO -----
    scores["portfolio"] += 4.0 * len(schema & PORTFOLIO_SCHEMA)
    scores["portfolio"] += 3.0 if sig["portfolio_path_pages"] >= 1 else 0.0
    scores["portfolio"] += 2.0 if sig["pages_with_portfolio_keyword"] >= 1 else 0.0
    # Portfolios are typically small, low nav-density
    if sig["total_crawled_pages"] <= 12 and sig["pages_with_cart_link"] == 0:
        scores["portfolio"] += 0.5

    # ----- LOCAL BUSINESS -----
    # LOCAL_SCHEMA types are strong (explicitly marked up as a local business)
    scores["local_business"] += 4.0 * len(schema & LOCAL_SCHEMA)
    # Business hours are the most diagnostic non-schema local signal
    scores["local_business"] += 4.0 if sig["pages_with_hours"] >= 1 else 0.0
    # Address: strong only when paired with hours or local schema; alone it just means
    # a contact page exists (nearly universal). Cap address-only contribution at 1.0.
    if sig["pages_with_hours"] >= 1 or (schema & LOCAL_SCHEMA):
        scores["local_business"] += 2.5 if sig["pages_with_address"] >= 2 else (
            1.5 if sig["pages_with_address"] >= 1 else 0.0
        )
    else:
        # Address without hours/schema = contact page; not diagnostic on its own
        scores["local_business"] += 0.5 if sig["pages_with_address"] >= 1 else 0.0
    # Phone: weak signal alone (many sites list support numbers)
    scores["local_business"] += 0.5 if sig["pages_with_phone"] >= 1 else 0.0
    # Local businesses tend to be small sites
    if sig["total_crawled_pages"] <= 15:
        scores["local_business"] += 0.5

    # ----- CORPORATE -----
    # Corporation schema is genuinely diagnostic; Organization/WebSite are near-universal
    # and carry much lower weight so they don't swamp other archetypes.
    scores["corporate"] += 2.0 * len(schema & CORPORATE_SCHEMA_STRONG)
    scores["corporate"] += 0.3 * len(schema & CORPORATE_SCHEMA_WEAK)  # was +2.0 each — too high
    # Large nav structure = institutional
    if sig["total_nav_links"] / pages >= 10:
        scores["corporate"] += 1.0
    # Corporate sites rarely have bylines or cart UI
    if sig["pages_with_byline"] == 0 and sig["pages_with_cart_link"] == 0:
        scores["corporate"] += 0.5

    return scores


# ---------------------------------------------------------------------------
# Archetype selection
# ---------------------------------------------------------------------------

def select_archetypes(scores: Dict[str, float], sig: Dict) -> Tuple[List[str], List[str]]:
    """
    Select one or more archetypes. A secondary archetype is included if its
    score is ≥50% of the primary's and ≥1.5 absolute (to avoid noise).

    Returns (archetypes_ordered, confidence_notes).
    """
    if not scores:
        return ["unknown"], ["No signals found"]

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_name, best_score = ranked[0]
    notes: List[str] = []

    if best_score < 1.5:
        # Insufficient evidence
        return ["unknown"], [
            f"Highest archetype score is {best_score:.2f} (threshold: 1.5). "
            "Not enough corpus signal to classify confidently. "
            "Possible causes: very small site, homepage-only crawl, or no schema markup."
        ]

    selected = [best_name]
    notes.append(
        f"Primary archetype '{best_name}' (score {best_score:.2f})"
    )

    for name, score in ranked[1:]:
        if score >= 1.5 and score >= 0.50 * best_score:
            selected.append(name)
            notes.append(
                f"Secondary archetype '{name}' (score {score:.2f}, "
                f"{score / best_score * 100:.0f}% of primary)"
            )
        else:
            break  # ranked list — once we fall below threshold, stop

    return selected, notes


def _signal_narrative(sig: Dict, archetypes: List[str]) -> List[str]:
    """Produce a list of human-readable signal statements for the top archetypes."""
    lines: List[str] = []
    schema = sig.get("schema_types_found", [])
    if schema:
        lines.append(f"Schema types found: {', '.join(schema[:10])}")
    if sig["pages_with_cart_link"]:
        lines.append(f"Cart/checkout links on {sig['pages_with_cart_link']} page(s)")
    if sig["pages_with_price"]:
        lines.append(f"Price strings found on {sig['pages_with_price']} page(s)")
    if sig["has_pricing_page"]:
        lines.append(f"Pricing page detected: {sig['pricing_page_url']}")
    if sig["pages_with_demo_cta"]:
        lines.append(f"Demo/trial CTA on {sig['pages_with_demo_cta']} page(s)")
    if sig["pages_with_saas_features"]:
        lines.append(f"SaaS feature vocabulary on {sig['pages_with_saas_features']} page(s)")
    if sig["pages_with_byline"]:
        lines.append(f"Bylines on {sig['pages_with_byline']} page(s)")
    if sig["pages_with_article_date"]:
        lines.append(f"Article dates on {sig['pages_with_article_date']} page(s)")
    if sig["blog_path_pages"]:
        lines.append(f"Blog URL paths: {sig['blog_path_pages']} page(s)")
    if sig["news_path_pages"]:
        lines.append(f"News URL paths: {sig['news_path_pages']} page(s)")
    if sig["docs_path_pages"]:
        lines.append(f"Docs URL paths: {sig['docs_path_pages']} page(s)")
    if sig["versioned_path_pages"]:
        lines.append(f"Versioned URL paths: {sig['versioned_path_pages']} page(s)")
    if sig["pages_with_code_blocks"]:
        lines.append(f"Code blocks on {sig['pages_with_code_blocks']} page(s)")
    if sig["portfolio_path_pages"]:
        lines.append(f"Portfolio URL paths: {sig['portfolio_path_pages']} page(s)")
    if sig["pages_with_portfolio_keyword"]:
        lines.append(f"Portfolio keywords on {sig['pages_with_portfolio_keyword']} page(s)")
    if sig["pages_with_address"]:
        lines.append(f"Physical address on {sig['pages_with_address']} page(s)")
    if sig["pages_with_hours"]:
        lines.append(f"Business hours on {sig['pages_with_hours']} page(s)")
    if sig["pages_with_phone"]:
        lines.append(f"Phone number on {sig['pages_with_phone']} page(s)")
    lines.append(f"Total pages crawled: {sig['total_crawled_pages']}")
    return lines


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def classify(manifest_path: Path, corpus_dir: Optional[Path] = None) -> Dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if corpus_dir is None:
        corpus_dir = manifest_path.parent / "pages"

    sig = extract_signals(manifest, corpus_dir)
    scores = score_archetypes(sig)
    archetypes, notes = select_archetypes(scores, sig)
    narrative = _signal_narrative(sig, archetypes)

    is_tiny = sig["total_crawled_pages"] < 8

    if is_tiny:
        notes.append(
            f"TINY SITE: only {sig['total_crawled_pages']} page(s) crawled. "
            "Downstream depth/orphan checks should be skipped; "
            "orientation and quotability checks should be weighted more heavily."
        )

    return {
        "archetypes": archetypes,
        "is_tiny_site": is_tiny,
        "signals": sig,
        "archetype_scores": {k: round(v, 3) for k, v in scores.items()},
        "confidence_notes": notes + narrative,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Corpus-signal-based site archetype classifier."
    )
    ap.add_argument("manifest", help="Path to crawl_manifest.json")
    ap.add_argument(
        "--corpus-dir", default=None,
        help="Path to corpus pages dir. Defaults to <manifest_dir>/pages.",
    )
    ap.add_argument(
        "--pretty", action="store_true",
        help="Pretty-print output (default: compact JSON).",
    )
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"[archetype] ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else None
    result = classify(manifest_path, corpus_dir)

    indent = 2 if args.pretty else None
    print(json.dumps(result, indent=indent))

    print(
        f"[archetype] {manifest_path.parent.name}: "
        f"{result['archetypes']} (tiny={result['is_tiny_site']})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
