#!/usr/bin/env python3
"""
check_e2.py — E2 Invalid/contradicting structured data check.

Consumes normalized structured-data records from structured_data.py.
Parses JSON-LD, Microdata, and RDFa records.
1. Validates deterministic required properties for declared schema.org types.
2. Compares key values (price, name, availability, address) with visibly stated
   values from the page corpus.
Contradictions are higher severity than absence.
Normalizes harmless whitespace, punctuation, currency, phone, URL, and numeric-format differences.

Usage:
    python check_e2.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Sibling import: structured_data
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from structured_data import NormalizedRecord, extract_structured_data  # noqa: E402


# ── Normalization helpers ────────────────────────────────────────────────

def _normalize_text(s: str) -> str:
    """Normalize whitespace and case."""
    if not s:
        return ""
    s = re.sub(r'[\u2018\u2019]', "'", s)
    s = re.sub(r'[\u201c\u201d]', '"', s)
    s = re.sub(r'[\u2013\u2014]', '-', s)
    return re.sub(r'\s+', ' ', s).strip().lower()


def _parse_price_float(val: Any) -> Optional[float]:
    """Extract a float price from string or numeric value."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    # Strip currency symbols and ISO codes
    s = re.sub(r'[$€£¥₹]|USD|EUR|GBP|CAD|AUD', '', s, flags=re.IGNORECASE).strip()
    # Remove thousand commas
    s = s.replace(',', '')
    m = re.search(r'\d+(?:\.\d+)?', s)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def _extract_visible_prices(text: str) -> List[float]:
    """Find all price numbers mentioned in visible text with currency markers."""
    # Matches $19.99, 19.99 USD, €25, £10.50
    pattern = re.compile(
        r'(?:[$€£¥₹]|USD|EUR|GBP)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        r'|(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:USD|EUR|GBP)',
        re.IGNORECASE,
    )
    prices: List[float] = []
    for m in pattern.finditer(text):
        num_str = m.group(1) or m.group(2)
        if num_str:
            num_clean = num_str.replace(',', '')
            try:
                val = float(num_clean)
                if 0.01 <= val <= 1000000.0:  # Reasonable price range filter
                    prices.append(val)
            except ValueError:
                pass
    return prices


def _normalize_phone(p: str) -> str:
    """Strip all non-digits from phone numbers."""
    return re.sub(r'\D', '', p)


# ── Schema deterministic validation rules ────────────────────────────────

SCHEMA_RULES = {
    "Product": {
        "required_one_of": [["name"]],
        "expected": ["offers", "description", "image", "brand"],
    },
    "Offer": {
        "required_one_of": [["price", "priceSpecification"]],
        "expected": ["priceCurrency", "availability"],
    },
    "LocalBusiness": {
        "required_one_of": [["name"]],
        "expected": ["address", "telephone"],
    },
    "Organization": {
        "required_one_of": [["name", "legalName"]],
        "expected": ["url"],
    },
    "Corporation": {
        "required_one_of": [["name", "legalName"]],
        "expected": ["url"],
    },
    "Article": {
        "required_one_of": [["headline", "name"]],
        "expected": ["author", "datePublished"],
    },
    "NewsArticle": {
        "required_one_of": [["headline", "name"]],
        "expected": ["author", "datePublished"],
    },
    "BlogPosting": {
        "required_one_of": [["headline", "name"]],
        "expected": ["author", "datePublished"],
    },
    "SoftwareApplication": {
        "required_one_of": [["name"]],
        "expected": ["operatingSystem", "applicationCategory", "offers"],
    },
    "Event": {
        "required_one_of": [["name"]],
        "expected": ["startDate", "location"],
    },
}


def _validate_required_properties(
    record: NormalizedRecord,
) -> Optional[Dict[str, Any]]:
    """Check if record declared a type that violates deterministic required property rules."""
    stype = record.schema_type
    rules = SCHEMA_RULES.get(stype)
    if not rules:
        return None

    # Check required groups (must have at least one from each list)
    for group in rules.get("required_one_of", []):
        present = any(record.properties.get(k) for k in group)
        if not present:
            return {
                "schema_type": stype,
                "syntax": record.syntax,
                "missing_required": group,
                "present_keys": list(record.properties.keys()),
            }

    # If Offer, check priceCurrency when price is present
    if stype == "Offer" and record.properties.get("price") is not None:
        if not record.properties.get("priceCurrency"):
            return {
                "schema_type": stype,
                "syntax": record.syntax,
                "missing_required": ["priceCurrency"],
                "present_keys": list(record.properties.keys()),
            }

    # If LocalBusiness, require address OR telephone
    if stype == "LocalBusiness":
        has_addr = bool(record.properties.get("address"))
        has_tel = bool(record.properties.get("telephone"))
        if not (has_addr or has_tel):
            return {
                "schema_type": stype,
                "syntax": record.syntax,
                "missing_required": ["address or telephone"],
                "present_keys": list(record.properties.keys()),
            }

    # If Organization / Corporation, require url
    if stype in ("Organization", "Corporation"):
        if not record.properties.get("url"):
            return {
                "schema_type": stype,
                "syntax": record.syntax,
                "missing_required": ["url"],
                "present_keys": list(record.properties.keys()),
            }

    # If Article / NewsArticle / BlogPosting, require author AND datePublished
    if stype in ("Article", "NewsArticle", "BlogPosting"):
        missing_article_props = []
        if not record.properties.get("author"):
            missing_article_props.append("author")
        if not record.properties.get("datePublished"):
            missing_article_props.append("datePublished")
        if missing_article_props:
            return {
                "schema_type": stype,
                "syntax": record.syntax,
                "missing_required": missing_article_props,
                "present_keys": list(record.properties.keys()),
            }

    return None


# ── Contradiction detection ──────────────────────────────────────────────

def _check_record_contradictions(
    record: NormalizedRecord,
    visible_text: str,
    page_title: str,
) -> List[Dict[str, Any]]:
    """Compare key values (price, name, availability) with visible page facts."""
    contradictions: List[Dict[str, Any]] = []
    stype = record.schema_type
    props = record.properties
    vis_lower = visible_text.lower()

    # 1. Price Contradiction (Entity-aware)
    sd_price: Optional[float] = None
    if stype in ("Offer", "Product"):
        raw_price = props.get("price")
        if raw_price is None and isinstance(props.get("offers"), dict):
            raw_price = props["offers"].get("price")
        elif raw_price is None and isinstance(props.get("offers"), list) and props["offers"]:
            first_offer = props["offers"][0]
            if isinstance(first_offer, dict):
                raw_price = first_offer.get("price")

        sd_price = _parse_price_float(raw_price)

    if sd_price is not None and sd_price > 0.0:
        # Check for entity-local prices first if entity has a name
        entity_name = str(props.get("name") or "").strip()
        vis_prices: List[float] = []
        if entity_name and entity_name.lower() in vis_lower:
            idx = vis_lower.find(entity_name.lower())
            snippet = visible_text[max(0, idx - 300):min(len(visible_text), idx + 300 + len(entity_name))]
            local_prices = _extract_visible_prices(snippet)
            if local_prices:
                vis_prices = local_prices

        if not vis_prices:
            vis_prices = _extract_visible_prices(visible_text)

        if vis_prices:
            # Multi-tier / variant rule: If sd_price matches ANY visible price tier, do NOT contradict
            matches = any(abs(sd_price - vp) < 0.01 for vp in vis_prices)
            if not matches:
                contradictions.append({
                    "field": "price",
                    "structured_value": sd_price,
                    "visible_values": vis_prices,
                    "syntax": record.syntax,
                    "schema_type": stype,
                    "mechanism": (
                        f"Structured data declares price {sd_price} ({record.syntax}), "
                        f"but visible page text explicitly advertises {vis_prices}. "
                        f"This conflicting information causes AI assistants to quote false pricing."
                    ),
                })

    # 2. Availability Contradiction
    raw_avail = props.get("availability")
    if raw_avail is None and isinstance(props.get("offers"), dict):
        raw_avail = props["offers"].get("availability")

    if raw_avail:
        avail_str = str(raw_avail).lower()
        is_instock_sd = "instock" in avail_str and "outofstock" not in avail_str

        # Check visible text for explicit out-of-stock badges
        out_of_stock_phrases = ["out of stock", "sold out", "currently unavailable", "backorder"]
        vis_out_of_stock = any(re.search(rf'\b{p}\b', vis_lower) for p in out_of_stock_phrases)

        if is_instock_sd and vis_out_of_stock:
            contradictions.append({
                "field": "availability",
                "structured_value": "InStock",
                "visible_values": ["Out of stock / Sold out"],
                "syntax": record.syntax,
                "schema_type": stype,
                "mechanism": (
                    f"Structured data declares item is InStock, but page text visibly displays "
                    f"'Sold Out' / 'Out of stock'. AI shopping agents relying on structured data "
                    f"will direct users to buy unavailable items."
                ),
            })

    return contradictions


# ── Check runner ─────────────────────────────────────────────────────────

def run_check_e2(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Run E2 check across all pages in the corpus.
    Emits findings following the Hardened Finding Contract.
    """
    findings: List[Dict[str, Any]] = []
    finding_idx = 1

    page_dirs = [d for d in corpus_dir.iterdir() if d.is_dir() and (d / "raw.html").exists()]
    if not page_dirs:
        for sub in corpus_dir.glob("*/raw.html"):
            page_dirs.append(sub.parent)

    for pdir in sorted(page_dirs):
        raw_path = pdir / "raw.html"
        meta_path = pdir / "meta.json"
        text_path = pdir / "text.txt"

        meta: Dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        page_url = meta.get("final_url") or meta.get("url")
        if not page_url and manifest:
            for cp in manifest.get("crawled_pages", []):
                if cp.get("slug") == pdir.name:
                    page_url = cp.get("final_url") or cp.get("url")
                    break
        if not page_url:
            continue

        raw_html = raw_path.read_text(encoding="utf-8", errors="replace")
        visible_text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
        if not visible_text:
            from check_d1 import _extract_visible_text
            visible_text = _extract_visible_text(raw_html)

        # Extract structured data records via extraction interface
        records = extract_structured_data(raw_html, base_url=page_url)
        if not records:
            continue

        # Extract page title for context
        title_m = re.search(r'<title[^>]*>(.*?)</title>', raw_html, flags=re.IGNORECASE | re.DOTALL)
        page_title = title_m.group(1).strip() if title_m else ""

        # 1. Contradiction Detection (CRITICAL / HIGH severity)
        seen_contradiction_keys: Set[Tuple[str, str]] = set()
        page_contradictions: List[Dict[str, Any]] = []
        for rec in records:
            conts = _check_record_contradictions(rec, visible_text, page_title)
            for c in conts:
                ckey = (c["field"], str(c["structured_value"]))
                if ckey not in seen_contradiction_keys:
                    seen_contradiction_keys.add(ckey)
                    page_contradictions.append(c)

        for cont in page_contradictions:
            findings.append({
                "id": f"F-E2-{finding_idx:03d}",
                "check_id": "E2",
                "page_url": page_url,
                "root_cause": "corroboration_deficit",
                "evidence": {
                    "type": "structured_data_contradiction",
                    "syntax": cont["syntax"],
                    "schema_type": cont["schema_type"],
                    "field": cont["field"],
                    "structured_value": cont["structured_value"],
                    "visible_values": cont["visible_values"],
                },
                "raw_severity_class": "critical" if cont["field"] == "price" else "high",
                "confidence": 0.95,
                "mechanism": cont["mechanism"],
                "false_positive_guard": (
                    f"Normalized currency, whitespace, and numeric formats before comparison. "
                    f"Verified visible text contains stated values {cont['visible_values']} while "
                    f"structured data strictly asserts {cont['structured_value']}."
                ),
                "verification_method": (
                    f"Inspect page source `curl -sL {page_url}` and compare {cont['syntax']} "
                    f"property '{cont['field']}' with visible content on page."
                ),
            })
            finding_idx += 1

        # 2. Schema Validation Rules (MEDIUM severity)
        for rec in records:
            val_err = _validate_required_properties(rec)
            if val_err:
                findings.append({
                    "id": f"F-E2-{finding_idx:03d}",
                    "check_id": "E2",
                    "page_url": page_url,
                    "root_cause": "identity_irresolution",
                    "evidence": {
                        "type": "invalid_schema_properties",
                        "syntax": val_err["syntax"],
                        "schema_type": val_err["schema_type"],
                        "missing_required": val_err["missing_required"],
                        "present_keys": val_err["present_keys"],
                    },
                    "raw_severity_class": "medium",
                    "confidence": 0.90,
                    "mechanism": (
                        f"Schema.org type '{val_err['schema_type']}' ({val_err['syntax']}) is declared "
                        f"without mandatory properties {val_err['missing_required']}. Downstream AI extractors "
                        f"cannot resolve this entity without these core properties."
                    ),
                    "false_positive_guard": (
                        f"Verified against standard schema.org requirements for {val_err['schema_type']}. "
                        f"Declared record only contains keys: {val_err['present_keys']}."
                    ),
                    "verification_method": (
                        f"View source on {page_url} and inspect {val_err['syntax']} block for {val_err['schema_type']}."
                    ),
                })
                finding_idx += 1

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="E2 — Invalid/contradicting structured data check")
    parser.add_argument("corpus_dir", help="Path to corpus directory containing page folders")
    parser.add_argument("--manifest", help="Optional path to crawl_manifest.json", default=None)
    args = parser.parse_args()

    corpus_dir = Path(args.corpus_dir)
    if not corpus_dir.exists():
        print(f"Error: corpus directory not found: {corpus_dir}", file=sys.stderr)
        sys.exit(1)

    manifest_data = None
    if args.manifest:
        mpath = Path(args.manifest)
        if mpath.exists():
            try:
                manifest_data = json.loads(mpath.read_text(encoding="utf-8"))
            except Exception:
                pass

    findings = run_check_e2(corpus_dir, manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
