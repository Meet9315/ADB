#!/usr/bin/env python3
"""
structured_data.py — Format-agnostic structured data extraction interface.

Extracts JSON-LD, Microdata, and RDFa using `extruct` and normalizes records into
uniform NormalizedRecord objects so downstream checks (E1, E2) consume clean,
format-independent properties without depending on extruct-specific dict structures.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Try importing extruct; report clearly if unavailable
try:
    import extruct
    EXTRUCT_AVAILABLE = True
except ImportError:
    EXTRUCT_AVAILABLE = False
    logger.warning("extruct is not installed. Fallback parser will be used.")


@dataclass
class NormalizedRecord:
    """A normalized structured data record independent of syntax format."""
    syntax: str  # 'json-ld' | 'microdata' | 'rdfa'
    schema_type: str  # Bare schema.org type, e.g. 'Product', 'Offer', 'LocalBusiness'
    properties: Dict[str, Any] = field(default_factory=dict)
    raw: Any = field(default=None)

    def get(self, key: str, default: Any = None) -> Any:
        return self.properties.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "syntax": self.syntax,
            "schema_type": self.schema_type,
            "properties": self.properties,
        }


def _clean_schema_type(type_val: Any) -> str:
    """Normalize a schema type to a simple type name (e.g. 'Product')."""
    if not type_val:
        return ""
    if isinstance(type_val, list):
        # Pick first non-empty type, preferring schema.org types
        candidates = [_clean_schema_type(t) for t in type_val if t]
        # Prefer specific types over generic Thing/WebPage
        for c in candidates:
            if c not in ("Thing", "WebPage", "WebSite"):
                return c
        return candidates[0] if candidates else ""
    s = str(type_val).strip()
    s = re.sub(r"^https?://schema\.org/?", "", s)
    s = re.sub(r"^schema:", "", s)
    # Split on slash or hash if still present
    if "/" in s:
        s = s.rsplit("/", 1)[-1]
    if "#" in s:
        s = s.rsplit("#", 1)[-1]
    return s.strip()


def _clean_property_key(key: str) -> str:
    """Strip schema.org namespaces from property names."""
    k = str(key).strip()
    k = re.sub(r"^https?://schema\.org/?", "", k)
    k = re.sub(r"^https?://www\.w3\.org/1999/02/22-rdf-syntax-ns#", "", k)
    k = re.sub(r"^schema:", "", k)
    if "/" in k and not k.startswith("http"):
        k = k.rsplit("/", 1)[-1]
    if "#" in k:
        k = k.rsplit("#", 1)[-1]
    return k.strip()


def _clean_rdfa_value(val: Any) -> Any:
    """Unpack RDFa value structures like [{'@value': 'text'}] or [{'@id': '...'}]"""
    if isinstance(val, list):
        if len(val) == 1:
            return _clean_rdfa_value(val[0])
        return [_clean_rdfa_value(v) for v in val]
    if isinstance(val, dict):
        if "@value" in val:
            return val["@value"]
        if "@id" in val and len(val) == 1:
            return val["@id"]
        # Recursively clean nested dict
        return {
            _clean_property_key(k): _clean_rdfa_value(v)
            for k, v in val.items()
            if not k.startswith("http://www.w3.org/ns/rdfa#")
        }
    return val


def _normalize_jsonld_item(item: Dict[str, Any]) -> List[NormalizedRecord]:
    """Normalize a JSON-LD item, expanding @graph and nested entities."""
    records: List[NormalizedRecord] = []
    if not isinstance(item, dict):
        return records

    # Handle @graph wrapper
    if "@graph" in item and isinstance(item["@graph"], list):
        for sub in item["@graph"]:
            records.extend(_normalize_jsonld_item(sub))
        return records

    raw_type = item.get("@type")
    schema_type = _clean_schema_type(raw_type)
    if not schema_type:
        return records

    props: Dict[str, Any] = {}
    for k, v in item.items():
        if k in ("@context", "@type"):
            continue
        clean_k = _clean_property_key(k)
        if isinstance(v, dict) and "@type" in v:
            # Nested record (e.g. offers: Offer)
            nested = _normalize_jsonld_item(v)
            records.extend(nested)
            props[clean_k] = v
        elif isinstance(v, list):
            props[clean_k] = v
            for elem in v:
                if isinstance(elem, dict) and "@type" in elem:
                    records.extend(_normalize_jsonld_item(elem))
        else:
            props[clean_k] = v

    records.append(NormalizedRecord(
        syntax="json-ld",
        schema_type=schema_type,
        properties=props,
        raw=item,
    ))
    return records


def _normalize_microdata_item(item: Dict[str, Any]) -> List[NormalizedRecord]:
    """Normalize a microdata item, handling nested properties."""
    records: List[NormalizedRecord] = []
    if not isinstance(item, dict):
        return records

    schema_type = _clean_schema_type(item.get("type", ""))
    raw_props = item.get("properties", {})
    props: Dict[str, Any] = {}

    for k, v in raw_props.items():
        clean_k = _clean_property_key(k)
        if isinstance(v, dict) and ("type" in v or "properties" in v):
            nested = _normalize_microdata_item(v)
            records.extend(nested)
            props[clean_k] = v
        elif isinstance(v, list):
            cleaned_list = []
            for elem in v:
                if isinstance(elem, dict) and ("type" in elem or "properties" in elem):
                    nested = _normalize_microdata_item(elem)
                    records.extend(nested)
                    cleaned_list.append(elem)
                else:
                    cleaned_list.append(elem)
            # If single-element list of primitive, unwrap
            if len(cleaned_list) == 1 and not isinstance(cleaned_list[0], (dict, list)):
                props[clean_k] = cleaned_list[0]
            else:
                props[clean_k] = cleaned_list
        else:
            props[clean_k] = v

    if schema_type:
        records.append(NormalizedRecord(
            syntax="microdata",
            schema_type=schema_type,
            properties=props,
            raw=item,
        ))
    return records


def _normalize_rdfa_item(item: Dict[str, Any]) -> List[NormalizedRecord]:
    """Normalize an RDFa item produced by extruct."""
    records: List[NormalizedRecord] = []
    if not isinstance(item, dict):
        return records

    raw_type = item.get("@type", [])
    schema_type = _clean_schema_type(raw_type)
    if not schema_type:
        return records

    props: Dict[str, Any] = {}
    for k, v in item.items():
        if k in ("@id", "@type") or k.startswith("http://www.w3.org/ns/rdfa#"):
            continue
        clean_k = _clean_property_key(k)
        cleaned_v = _clean_rdfa_value(v)
        props[clean_k] = cleaned_v

    records.append(NormalizedRecord(
        syntax="rdfa",
        schema_type=schema_type,
        properties=props,
        raw=item,
    ))
    return records


# ── Fallback extraction (when extruct is unavailable or errors) ───────────

def _fallback_extract_jsonld(html: str) -> List[NormalizedRecord]:
    """Pure-Python fallback for extracting JSON-LD scripts."""
    records: List[NormalizedRecord] = []
    script_re = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for m in script_re.finditer(html):
        content = m.group(1).strip()
        if not content:
            continue
        try:
            data = json.loads(content)
            if isinstance(data, list):
                for item in data:
                    records.extend(_normalize_jsonld_item(item))
            elif isinstance(data, dict):
                records.extend(_normalize_jsonld_item(data))
        except Exception as exc:
            logger.debug("Fallback JSON-LD parse failed: %s", exc)
    return records


def _fallback_extract_microdata(html: str) -> List[NormalizedRecord]:
    """Lightweight regex-based fallback for simple microdata."""
    records: List[NormalizedRecord] = []
    item_re = re.compile(
        r'<[^>]+itemscope[^>]*itemtype=["\']([^"\']+)["\'][^>]*>(.*?)(?=<(?:div|section|article)[^>]*itemscope|\Z)',
        re.DOTALL | re.IGNORECASE,
    )
    prop_re = re.compile(
        r'<[^>]+itemprop=["\']([^"\']+)["\'][^>]*(?:content=["\']([^"\']+)["\']|>([^<]*)</)',
        re.IGNORECASE,
    )
    for m in item_re.finditer(html):
        itype = _clean_schema_type(m.group(1))
        body = m.group(2)
        props: Dict[str, Any] = {}
        for pm in prop_re.finditer(body):
            name = _clean_property_key(pm.group(1))
            val = pm.group(2) if pm.group(2) is not None else pm.group(3)
            props[name] = val.strip() if val else ""
        if itype:
            records.append(NormalizedRecord(
                syntax="microdata",
                schema_type=itype,
                properties=props,
                raw={"type": itype, "properties": props},
            ))
    return records


# ── Public API ───────────────────────────────────────────────────────────

def extract_structured_data(
    html: str,
    base_url: str = "",
    use_fallback_only: bool = False,
) -> List[NormalizedRecord]:
    """
    Extract and normalize JSON-LD, Microdata, and RDFa structured data from HTML.

    Args:
        html: Raw or rendered HTML content string.
        base_url: Optional base URL for resolving relative URIs.
        use_fallback_only: Force fallback extraction for testing.

    Returns:
        List of NormalizedRecord instances.
    """
    if not html or not html.strip():
        return []

    if EXTRUCT_AVAILABLE and not use_fallback_only:
        try:
            data = extruct.extract(
                html,
                base_url=base_url or None,
                syntaxes=["json-ld", "microdata", "rdfa"],
                errors="log",
            )
            records: List[NormalizedRecord] = []

            # 1. JSON-LD
            for item in data.get("json-ld", []):
                records.extend(_normalize_jsonld_item(item))

            # 2. Microdata
            for item in data.get("microdata", []):
                records.extend(_normalize_microdata_item(item))

            # 3. RDFa
            for item in data.get("rdfa", []):
                records.extend(_normalize_rdfa_item(item))

            return records
        except Exception as exc:
            logger.warning("extruct.extract raised %s: %s; using fallback", type(exc).__name__, exc)

    # Fallback path
    records = []
    records.extend(_fallback_extract_jsonld(html))
    records.extend(_fallback_extract_microdata(html))
    return records
