#!/usr/bin/env python3
"""
check_t3.py — T3 Entity Ambiguity Check (Tier 1: Trust Signals Audit).

Audits the site for entity ambiguity signals:
1. Common/shared dictionary brand name (e.g. 'Summit', 'Apex', 'Pulse', 'Nova').
2. Absence of Organization JSON-LD with 'sameAs' authoritative registry links.
3. Homepage text that fails to disambiguate industry category or geography.

Negative-Logic Rules & Finding-vs-Suggestion Split (False-Positive Guard):
- This check is confidence-capped: only report as a high-confidence FINDING
  when MULTIPLE signals stack together (active_signals >= 2).
- If only one weak signal is present (active_signals == 1), it is routed as a
  PROACTIVE SUGGESTION instead of a finding.
- This finding-vs-suggestion split based on signal count is itself the false-positive guard.

Usage:
    python check_t3.py <corpus_dir> [--manifest <crawl_manifest.json>] [--proactive-out <path>]
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

# Common single-word dictionary brand names frequently suffering entity collisions
COMMON_BRAND_NAMES: Set[str] = {
    "summit", "apex", "nova", "beacon", "pulse", "elevate", "velocity",
    "echo", "canvas", "prism", "horizon", "nexus", "vanguard", "catalyst",
    "orbit", "stride", "spark", "forge", "crest", "stream", "flow",
    "haven", "anchor", "clarity", "zenith", "beacon", "titan", "matrix",
}

# Category and geographic indicators
CATEGORY_KEYWORDS: Set[str] = {
    "software", "platform", "saas", "ecommerce", "retail", "shop", "store",
    "consulting", "agency", "hospital", "clinic", "healthcare", "medical",
    "logistics", "supply chain", "manufacturing", "construction", "developer tools",
    "api", "infrastructure", "hotel", "restaurant", "law firm", "legal",
    "finance", "fintech", "insurance", "education", "academy", "media", "publishing",
}

GEOGRAPHY_RE = re.compile(
    r"\b(?:based\s+in|headquartered\s+in|serving|located\s+in)\s+[A-Z][a-zA-Z\s,]+|"
    r"\b[A-Z][a-zA-Z]+,\s*(?:[A-Z]{2}|USA|UK|Canada|Germany|France|India|Australia)\b",
    re.IGNORECASE,
)


def _extract_brand_name(domain: str, title: str, text: str) -> str:
    """Extract candidate brand name from domain or page title."""
    # First check title before pipe/hyphen
    if title:
        parts = re.split(r"[-|–—:]", title)
        cand = parts[0].strip()
        if cand and len(cand.split()) <= 2:
            return cand
        # Or last part if 'Home | Brand'
        if len(parts) > 1:
            cand_last = parts[-1].strip()
            if cand_last and len(cand_last.split()) <= 2:
                return cand_last

    # Fall back to domain base name
    clean_domain = re.sub(r"^(?:https?://)?(?:www\.)?", "", domain)
    base = clean_domain.split(".")[0]
    return base


def _check_organization_same_as(html: str) -> bool:
    """Check if page contains Organization/Corporation schema with non-empty sameAs."""
    # Search JSON-LD scripts
    jsonld_re = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for m in jsonld_re.finditer(html):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else [data]
            if isinstance(data, dict) and "@graph" in data and isinstance(data["@graph"], list):
                items = data["@graph"]

            for it in items:
                if not isinstance(it, dict):
                    continue
                stype = str(it.get("@type", "")).lower()
                if any(org in stype for org in ("organization", "corporation", "localbusiness")):
                    same_as = it.get("sameAs")
                    if same_as:
                        if isinstance(same_as, list) and len(same_as) > 0:
                            return True
                        elif isinstance(same_as, str) and len(same_as.strip()) > 0:
                            return True
        except Exception:
            pass

    # Check Microdata / RDFa sameAs
    if re.search(r'(?:itemprop|property)=["\']sameAs["\']', html, re.IGNORECASE):
        return True

    return False


def run_check_t3(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Execute T3 check across the corpus.
    Returns: (findings_list, proactive_suggestions_list).
    """
    findings: List[Dict[str, Any]] = []
    proactive_suggestions: List[Dict[str, Any]] = []

    domain = manifest.get("domain", "") if manifest else ""
    home_page_dir: Optional[Path] = None
    home_url = ""

    # Locate homepage
    for page_dir in sorted(corpus_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        meta_path = page_dir / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                p_url = meta.get("final_url") or meta.get("url", "")
                parsed = urlparse(p_url)
                if not domain and parsed.netloc:
                    domain = parsed.netloc
                if parsed.path in ("", "/", "/index.html"):
                    home_page_dir = page_dir
                    home_url = p_url
                    break
            except Exception:
                pass

    if not home_page_dir:
        # Fall back to first crawled directory
        subdirs = [d for d in sorted(corpus_dir.iterdir()) if d.is_dir()]
        if subdirs:
            home_page_dir = subdirs[0]

    if not home_page_dir:
        return findings, proactive_suggestions

    raw_html_path = home_page_dir / "raw.html"
    text_path = home_page_dir / "text.txt"
    meta_path = home_page_dir / "meta.json"

    if not raw_html_path.exists():
        return findings, proactive_suggestions

    html = raw_html_path.read_text(encoding="utf-8", errors="replace")
    text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
    meta: Dict[str, Any] = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    if not home_url:
        home_url = meta.get("final_url") or meta.get("url", f"https://{domain}/")

    title = meta.get("title", "")
    brand = _extract_brand_name(domain, title, text)
    brand_lower = brand.lower()

    # 1. Signal 1: Common / Shared generic single-word brand name
    is_common_brand = (
        brand_lower in COMMON_BRAND_NAMES
        or (len(brand.split()) == 1 and len(brand) <= 8 and brand_lower.isalpha() and brand_lower in COMMON_BRAND_NAMES)
    )

    # 2. Signal 2: Absence of Organization JSON-LD with sameAs links
    has_same_as = _check_organization_same_as(html)
    lacks_same_as = not has_same_as

    # 3. Signal 3: Homepage text never disambiguates category / geography
    text_lower = text.lower()
    has_category = any(cat in text_lower for cat in CATEGORY_KEYWORDS)
    has_geography = bool(GEOGRAPHY_RE.search(text))
    lacks_disambiguation = not has_category and not has_geography

    active_signals: List[str] = []
    if is_common_brand:
        active_signals.append("common_brand_name")
    if lacks_same_as:
        active_signals.append("missing_organization_same_as")
    if lacks_disambiguation:
        active_signals.append("lacks_category_or_geography_disambiguation")

    signal_count = len(active_signals)

    # FALSE-POSITIVE GUARD & SPLIT:
    # >= 2 signals: Escalate to high-confidence DEFECT FINDING
    if signal_count >= 2:
        findings.append({
            "id": "F-T3-001",
            "check_id": "T3",
            "page_url": home_url,
            "root_cause": "identity_irresolution",
            "evidence": {
                "type": "entity_ambiguity",
                "brand_name": brand,
                "active_signals": active_signals,
                "signal_count": signal_count,
                "is_common_brand": is_common_brand,
                "lacks_same_as": lacks_same_as,
                "lacks_disambiguation": lacks_disambiguation,
            },
            "raw_severity_class": "medium",
            "confidence": 0.85,
            "mechanism": (
                f"Entity identity for '{brand}' suffers from multiple co-occurring ambiguity signals: "
                f"{', '.join(active_signals)}. Autonomous agents performing entity resolution cannot disambiguate "
                "this site from generic counterparts without explicit sameAs authority links or category disambiguation, "
                "leading to omitted entity citations or mistaken identity."
            ),
            "false_positive_guard": (
                "Confidence-capped signal stacking guard: evaluated common brand name, absence of Organization sameAs, "
                f"and lack of category/geography. Requires >= 2 co-occurring signals (observed: {signal_count}). "
                "Single weak signals are routed as proactive suggestions rather than defect findings."
            ),
            "verification_method": f"curl -sL {home_url} | grep -iE 'sameas|organization'",
        })

    # == 1 signal: Emit as PROACTIVE SUGGESTION instead of a defect finding
    elif signal_count == 1:
        single_signal = active_signals[0]
        proactive_suggestions.append({
            "id": "PROACT-T3-001",
            "title": "Add Schema.org sameAs Authority Links to Disambiguate Brand Identity",
            "description": (
                f"While entity identity for '{brand}' is reasonably distinct, adding schema.org Organization markup "
                "with authoritative sameAs links (e.g. Wikidata, Crunchbase, LinkedIn, Wikipedia) helps AI search engines "
                "unambiguously resolve your business entity."
            ),
            "code_snippet": (
                '{\n  "@context": "https://schema.org",\n  "@type": "Organization",\n  "name": "'
                + brand
                + '",\n  "sameAs": [\n    "https://www.wikidata.org/wiki/...",\n    "https://www.linkedin.com/company/..."\n  ]\n}'
            ),
            "priority": "low",
            "linked_findings": [],
            "is_proactive": True,
            "weak_signal": single_signal,
        })

    return findings, proactive_suggestions


def main() -> None:
    parser = argparse.ArgumentParser(description="T3 — Entity Ambiguity Check")
    parser.add_argument("corpus_dir", type=Path, help="Directory containing crawled page subdirectories")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to crawl_manifest.json")
    parser.add_argument("--proactive-out", type=Path, default=None, help="Path to write proactive suggestions JSON")
    args = parser.parse_args()

    manifest_data: Optional[Dict[str, Any]] = None
    if args.manifest and args.manifest.exists():
        try:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception:
            pass

    findings, suggestions = run_check_t3(args.corpus_dir, manifest=manifest_data)

    if args.proactive_out and suggestions:
        try:
            args.proactive_out.write_text(json.dumps(suggestions, indent=2), encoding="utf-8")
        except Exception:
            pass

    # Findings emitted to stdout for candidate merger
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
