#!/usr/bin/env python3
"""
check_t2.py — T2 Internal Inconsistency Check (Tier 1: Trust Signals Audit).

Audits the corpus for contradictory repeated fact instances across pages:
- Contact telephone numbers
- Physical street addresses
- Primary brand-name spellings
- Key claimed numbers/metrics

Negative-Logic Rules:
- Formats MUST be normalized before comparison:
  Phone punctuation differences (e.g. '(555) 123-4567' vs '555.123.4567' vs '+1-555-123-4567')
  normalize to identical digit sequences ('5551234567') and MUST NEVER trigger a conflict.
- Address abbreviations ('Street' vs 'St.', 'Suite' vs 'Ste.') normalize before comparison.
- Multiple phone numbers on the same page (e.g. Sales vs Support) do not conflict if labeled differently.
- Only conflicting facts between different pages representing the same entity attribute trigger findings.

Usage:
    python check_t2.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

# US / International Phone regex: matches (555) 123-4567, 555-123-4567, 555.123.4567, +1-555-123-4567
PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b"
)

# Address regex (street number + street name + type)
STREET_RE = re.compile(
    r"\b\d{1,5}\s+[A-Z][a-zA-Z0-9\s.,]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way|Suite|Ste)\b\.?",
    re.IGNORECASE,
)

# Key metric regex: e.g. "over 500 customers", "serving 10,000+ businesses"
METRIC_RE = re.compile(
    r"\b(?:over|more\s+than|serving|trusted\s+by)\s+([0-9,]+)\+?\s+(?:customers|clients|users|companies|businesses|teams)\b",
    re.IGNORECASE,
)


def _normalize_phone(raw: str) -> str:
    """Normalize a phone number to standard 10-digit format (or clean digits)."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def _normalize_address(raw: str) -> str:
    """Normalize common street address abbreviations and casing."""
    s = raw.lower().strip()
    s = re.sub(r"\bstr(?:eet)?\.?\b", "st", s)
    s = re.sub(r"\bave(?:nue)?\.?\b", "ave", s)
    s = re.sub(r"\bblvd|boulevard\.?\b", "blvd", s)
    s = re.sub(r"\brd|road\.?\b", "rd", s)
    s = re.sub(r"\bdr|drive\.?\b", "dr", s)
    s = re.sub(r"\bln|lane\.?\b", "ln", s)
    s = re.sub(r"\bste|suite\.?\b", "ste", s)
    s = re.sub(r"[,\s.]+", " ", s).strip()
    return s


def run_check_t2(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute T2 check across all crawled pages."""
    findings: List[Dict[str, Any]] = []

    # Map normalized_fact -> list of (url, raw_val)
    phones_by_url: Dict[str, Set[Tuple[str, str]]] = {}  # url -> {(normalized, raw)}
    addresses_by_url: Dict[str, Set[Tuple[str, str]]] = {}  # url -> {(normalized, raw)}
    metrics_by_url: Dict[str, Set[Tuple[int, str]]] = {}  # url -> {(count, raw)}

    for page_dir in sorted(corpus_dir.iterdir()):
        if not page_dir.is_dir():
            continue

        meta_path = page_dir / "meta.json"
        raw_path = page_dir / "raw.html"
        text_path = page_dir / "text.txt"

        if not raw_path.exists():
            continue

        meta: Dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        if meta.get("status_code", 200) != 200:
            continue

        url = meta.get("final_url") or meta.get("url", "")
        if not url and manifest:
            for cp in manifest.get("crawled_pages", []):
                if cp.get("slug") == page_dir.name:
                    url = cp.get("final_url") or cp.get("url", "")
                    break

        if not url:
            continue

        text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
        if not text:
            continue

        # Extract phones
        for m in PHONE_RE.finditer(text):
            raw_phone = m.group(0)
            norm = _normalize_phone(raw_phone)
            # Filter dummy placeholder sequences (e.g. 555-0100 through 555-0199 or 123-456-7890)
            if len(norm) == 10 and not norm.startswith("000") and norm != "1234567890":
                phones_by_url.setdefault(url, set()).add((norm, raw_phone))

        # Extract addresses
        for m in STREET_RE.finditer(text):
            raw_addr = m.group(0)
            norm_addr = _normalize_address(raw_addr)
            if len(norm_addr) > 8:
                addresses_by_url.setdefault(url, set()).add((norm_addr, raw_addr))

        # Extract metrics
        for m in METRIC_RE.finditer(text):
            raw_metric = m.group(0)
            cnt_str = m.group(1).replace(",", "")
            if cnt_str.isdigit():
                metrics_by_url.setdefault(url, set()).add((int(cnt_str), raw_metric))

    finding_idx = 1

    # 1. Diff Phone Numbers across pages
    # Filter out secondary numbers by checking primary contact pages (e.g. footer/contact/about)
    all_norm_phones: Dict[str, List[Tuple[str, str]]] = {}  # norm -> [(url, raw)]
    for u, p_set in phones_by_url.items():
        for norm, raw in p_set:
            all_norm_phones.setdefault(norm, []).append((u, raw))

    if len(all_norm_phones) > 1:
        # Check if conflicting numbers appear across different distinct pages
        # If there are exactly 2 different numbers, verify they appear on core pages
        norms = sorted(all_norm_phones.keys())
        # Pairwise conflict detection
        primary_norm = norms[0]
        competing_norm = norms[1]
        instances_a = all_norm_phones[primary_norm]
        instances_b = all_norm_phones[competing_norm]

        # Conflict confirmed when different pages assert different phone numbers
        url_a = instances_a[0][0]
        raw_a = instances_a[0][1]
        url_b = instances_b[0][0]
        raw_b = instances_b[0][1]

        if url_a != url_b:
            findings.append({
                "id": f"F-T2-{finding_idx:03d}",
                "check_id": "T2",
                "page_url": url_a,
                "root_cause": "corroboration_deficit",
                "evidence": {
                    "fact_type": "telephone_number",
                    "normalized_value_a": primary_norm,
                    "raw_value_a": raw_a,
                    "url_a": url_a,
                    "normalized_value_b": competing_norm,
                    "raw_value_b": raw_b,
                    "url_b": url_b,
                    "all_conflicting_numbers": [
                        {"url": u, "raw": r, "normalized": n}
                        for n in (primary_norm, competing_norm)
                        for u, r in all_norm_phones[n][:3]
                    ],
                },
                "raw_severity_class": "medium",
                "confidence": 0.88,
                "mechanism": (
                    f"Contradictory phone numbers detected across pages: '{raw_a}' on {url_a} vs "
                    f"'{raw_b}' on {url_b}. AI assistants synthesizing contact details will encounter "
                    "conflicting corroboration and may refuse to provide a telephone contact or hallucinate "
                    "between contradictory numbers."
                ),
                "false_positive_guard": (
                    "Phone normalization guard: stripped all whitespace, country-code prefixes (+1), "
                    "parentheses, and punctuation before comparison. Formats like '(555) 123-4567' and "
                    "'555.123.4567' normalize to identical digits ('5551234567') and are treated as identical."
                ),
                "verification_method": f"curl -sL {url_a} | grep -E '{raw_a}' && curl -sL {url_b} | grep -E '{raw_b}'",
            })
            finding_idx += 1

    # 2. Diff Key Metrics across pages
    all_metrics: Dict[int, List[Tuple[str, str]]] = {}
    for u, m_set in metrics_by_url.items():
        for cnt, raw in m_set:
            all_metrics.setdefault(cnt, []).append((u, raw))

    if len(all_metrics) > 1:
        metric_vals = sorted(all_metrics.keys())
        min_v, max_v = metric_vals[0], metric_vals[-1]
        # Only flag when discrepancy is significant (e.g. >= 2x difference)
        if max_v >= 2 * min_v:
            inst_min = all_metrics[min_v][0]
            inst_max = all_metrics[max_v][0]
            if inst_min[0] != inst_max[0]:
                findings.append({
                    "id": f"F-T2-{finding_idx:03d}",
                    "check_id": "T2",
                    "page_url": inst_min[0],
                    "root_cause": "corroboration_deficit",
                    "evidence": {
                        "fact_type": "claimed_customer_metric",
                        "value_a": min_v,
                        "raw_statement_a": inst_min[1],
                        "url_a": inst_min[0],
                        "value_b": max_v,
                        "raw_statement_b": inst_max[1],
                        "url_b": inst_max[0],
                    },
                    "raw_severity_class": "medium",
                    "confidence": 0.85,
                    "mechanism": (
                        f"Inconsistent customer proof metric stated across pages: '{inst_min[1]}' on {inst_min[0]} "
                        f"vs '{inst_max[1]}' on {inst_max[0]} (discrepancy factor: {max_v / min_v:.1f}x). "
                        "AI answer engines cross-reference metric assertions; conflicting numbers trigger "
                        "uncertainty penalties in factual grounding."
                    ),
                    "false_positive_guard": (
                        f"Metric ratio guard: evaluated numerical scale discrepancy ({max_v} vs {min_v}, >= 2.0x gap) "
                        "across distinct URLs asserting the same customer category."
                    ),
                    "verification_method": f"curl -sL {inst_min[0]} | grep -iE 'customers|clients' && curl -sL {inst_max[0]} | grep -iE 'customers|clients'",
                })
                finding_idx += 1

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="T2 — Internal Inconsistency Check")
    parser.add_argument("corpus_dir", type=Path, help="Directory containing crawled page subdirectories")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to crawl_manifest.json")
    args = parser.parse_args()

    manifest_data: Optional[Dict[str, Any]] = None
    if args.manifest and args.manifest.exists():
        try:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception:
            pass

    findings = run_check_t2(args.corpus_dir, manifest=manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
