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

# Legal entity indicators (corporate suffixes anchoring entity identity)
LEGAL_ENTITY_RE = re.compile(
    r"\b(?:inc(?:\.|\b)|llc|ltd(?:\.|\b)|corp(?:\.|\b)|corporation|co(?:\.|\b)|gmbh|ag|pty|b\.v\.|s\.a\.)",
    re.IGNORECASE,
)

# Registered trademark / service mark symbols anchoring entity identity
TRADEMARK_RE = re.compile(r"(?:™|®|&trade;|&reg;|&#8482;|&#174;)")

# Coined tech and brand affixes indicating a distinctive coined name
COINED_SUFFIX_RE = re.compile(
    r"(?:ify|ly|able|tech|hub|labs?|stack|base|flow|ware|gen|ops|scale)$",
    re.IGNORECASE,
)

# Common generic single-word dictionary vocabulary prone to entity collisions
COMMON_GENERIC_WORDS: Set[str] = {
    "summit", "apex", "nova", "beacon", "pulse", "elevate", "velocity",
    "echo", "canvas", "prism", "horizon", "nexus", "vanguard", "catalyst",
    "orbit", "stride", "spark", "forge", "crest", "stream", "flow",
    "haven", "anchor", "clarity", "zenith", "titan", "matrix", "surge",
    "craft", "bridge", "venture", "arc", "origin", "pivot", "beacon",
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


def _is_ambiguous_brand_corpus(
    brand: str,
    title: str,
    body_text: str,
    html: str,
) -> Tuple[bool, List[str]]:
    """
    Determine whether a brand name suffers from entity ambiguity using observable corpus signals:
    1. Single-word morphology without legal suffix or distinctive coined structure.
    2. Lack of trademark / service mark symbols in corpus HTML.
    3. Bare / unqualified usage in page title (no category modifier or descriptive subtitle).
    4. Observable generic usage: word appears in lowercase in ordinary sentences within corpus text,
       or matches common generic dictionary vocabulary.
    """
    brand_clean = brand.strip()
    words = brand_clean.split()

    # Multi-word brands (e.g. 'Summit Data Systems', 'FastScale Engine') provide natural disambiguation
    if len(words) > 1:
        return False, ["multi_word_brand"]

    # Legal entity suffix present (e.g. 'Acme Corp', 'Summit LLC')
    if LEGAL_ENTITY_RE.search(brand_clean) or LEGAL_ENTITY_RE.search(title):
        return False, ["has_legal_entity_suffix"]

    # Registered trademark / service mark symbols in HTML
    if TRADEMARK_RE.search(html):
        return False, ["has_trademark_symbol"]

    # CamelCase coined terms (e.g. 'CloudFlare', 'FastScale', 'DataDog')
    if re.search(r"[a-z][A-Z]", brand_clean):
        return False, ["camel_case_coined_term"]

    # Alphanumeric or hyphenated names (e.g. 'Web3', 'E-Trade')
    if re.search(r"[\d\-]", brand_clean):
        return False, ["alphanumeric_or_hyphenated"]

    # Coined tech suffix (e.g. '-ify', '-ly', '-scale', '-base')
    if COINED_SUFFIX_RE.search(brand_clean):
        return False, ["coined_morpheme_suffix"]

    # Check title qualification: is the title bare/unqualified?
    title_parts = [p.strip() for p in re.split(r"[-|–—:]", title) if p.strip()]
    bare_title = False
    if len(title_parts) <= 1:
        bare_title = True
    elif len(title_parts) == 2 and any(tp.lower() in ("home", "welcome", "index", "official site") for tp in title_parts):
        bare_title = True

    brand_lower = brand_clean.lower()
    # Observable generic usage: token appears in lowercase in body text as a common noun/verb
    in_text_lowercase = bool(re.search(rf"\b{re.escape(brand_lower)}\b", body_text))

    is_generic_vocab = (
        brand_lower in COMMON_GENERIC_WORDS
        or (len(brand_lower) <= 8 and in_text_lowercase)
    )

    signals: List[str] = []
    if bare_title:
        signals.append("bare_unqualified_title")
    if is_generic_vocab:
        signals.append("generic_dictionary_vocabulary")
    if in_text_lowercase:
        signals.append("lowercase_in_corpus_text")

    # Ambiguous brand requires generic vocabulary plus bare/unqualified title or short common word
    if is_generic_vocab and (bare_title or len(brand_lower) <= 6):
        return True, signals

    return False, signals


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

    # 1. Observable Corpus Signal 1: Ambiguous generic brand name
    is_ambiguous_brand, brand_signals = _is_ambiguous_brand_corpus(brand, title, text, html)

    # 2. Observable Corpus Signal 2: Absence of Organization JSON-LD with sameAs links
    has_same_as = _check_organization_same_as(html)
    lacks_same_as = not has_same_as

    # 3. Observable Corpus Signal 3: Homepage text never disambiguates category / geography
    text_lower = text.lower()
    has_category = any(cat in text_lower for cat in CATEGORY_KEYWORDS)
    has_geography = bool(GEOGRAPHY_RE.search(text))
    lacks_disambiguation = not has_category and not has_geography

    active_signals: List[str] = []
    if is_ambiguous_brand:
        active_signals.append("common_brand_name")
    if lacks_same_as:
        active_signals.append("missing_organization_same_as")
    if lacks_disambiguation:
        active_signals.append("lacks_category_or_geography_disambiguation")

    signal_count = len(active_signals)

    # FALSE-POSITIVE GUARD & STRICT PREREQUISITE RULE:
    # A DEFECT FINDING strictly requires:
    #   1. The brand itself is ambiguous (is_ambiguous_brand == True)
    #   2. Compounded by at least one missing disambiguator (lacks_same_as or lacks_disambiguation),
    #      yielding signal_count >= 2.
    # If the brand is NOT ambiguous (e.g. distinctive, coined, legally suffixed, or trademarked),
    # then missing sameAs or sparse category copy NEVER produces a defect finding. It routes
    # exclusively as a proactive suggestion.
    if is_ambiguous_brand and signal_count >= 2:
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
                "is_common_brand": True,
                "brand_signals": brand_signals,
                "lacks_same_as": lacks_same_as,
                "lacks_disambiguation": lacks_disambiguation,
            },
            "raw_severity_class": "medium",
            "confidence": 0.88,
            "mechanism": (
                f"Entity identity for generic brand '{brand}' suffers from multiple co-occurring ambiguity signals: "
                f"{', '.join(active_signals)}. Autonomous agents performing entity resolution cannot disambiguate "
                "this site from generic counterparts without explicit sameAs authority links or category disambiguation, "
                "leading to omitted entity citations or mistaken identity."
            ),
            "false_positive_guard": (
                "Brand ambiguity prerequisite and signal stacking guard: verified that the brand is a bare single-word "
                "generic term lacking legal entity suffix or trademark, combined with missing sameAs or lack of "
                "category disambiguation (>= 2 signals). Distinctive, compound, or trademarked brands never trigger a defect."
            ),
            "verification_method": f"curl -sL {home_url} | grep -iE 'sameas|organization'",
        })

    # If signals are present but criteria for a defect finding are not met, route as PROACTIVE SUGGESTION
    elif lacks_same_as or is_ambiguous_brand:
        single_signal = active_signals[0] if active_signals else "missing_organization_same_as"
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
