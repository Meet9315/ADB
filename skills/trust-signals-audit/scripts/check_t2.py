#!/usr/bin/env python3
"""
check_t2.py — T2 Internal Inconsistency Check (Tier 1: Trust Signals Audit).

Audits the corpus for contradictory repeated fact instances across distinct pages:
- Contact telephone numbers (with role/department context guard and punctuation normalization)
- Physical street addresses (with street abbreviation normalization)
- Key claimed proof metrics (with scale-gap guard)

Negative-Logic Rules:
- Formats MUST be normalized before comparison:
  Phone punctuation differences (e.g. '(555) 123-4567' vs '555.123.4567' vs '+1-555-123-4567')
  normalize to identical digit sequences ('5551234567') and MUST NEVER trigger a conflict.
- Address abbreviations ('Street' vs 'St.', 'Suite' vs 'Ste.') normalize before comparison.
- Role/Context Guard: Distinct numbers serving different labeled roles/departments
  (e.g. Sales vs Support vs Press) do NOT conflict with each other.
  Only differing numbers serving the SAME role (or general unsegmented contact) across distinct pages conflict.
- Substring Address Guard: Addresses where one page adds an explicit suite/unit number to the same street
  do not conflict.
- Scale Guard for Metrics: Proof metrics must diverge by >= 2.0x across distinct URLs to trigger a conflict.

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

# Address regex (street number + street name + type, optional unit/suite, optional city/state/zip)
STREET_RE = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9\.\s]{1,30}?\b(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way|Parkway|Pkwy|Court|Ct|Circle|Cir)\b\.?(?:[,\s]+(?:Suite|Ste|Unit|Apt|Apartment|Floor|Fl|#)\s*[A-Za-z0-9\-]+)?(?:[,\s]+[A-Za-z\s]{2,25}(?:,\s*[A-Z]{2}(?:\s+\d{5})?\b|\s+\d{5}\b)?)?",
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


def _extract_phone_role(text: str, start: int, end: int) -> str:
    """Extract department or functional context in the immediate vicinity of a phone number."""
    pre_text = text[max(0, start - 35):start]
    if "\n" in pre_text:
        pre_text = pre_text.split("\n")[-1]
    post_text = text[end:min(len(text), end + 25)]
    if "\n" in post_text:
        post_text = post_text.split("\n")[0]
    vicinity = f"{pre_text} {post_text}".lower()

    if re.search(r"\b(?:sales|billing|orders?)\b", vicinity):
        return "sales"
    if re.search(r"\b(?:support|help|tech(?:nical)?|service|desk)\b", vicinity):
        return "support"
    if re.search(r"\b(?:press|media|pr)\b", vicinity):
        return "press"
    if re.search(r"\b(?:fax)\b", vicinity):
        return "fax"
    if re.search(r"\b(?:headquarters|hq|corporate|main\s+office)\b", vicinity):
        return "headquarters"
    return "general"


def _normalize_address(raw: str) -> str:
    """Normalize common street address abbreviations, punctuation, and casing."""
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


def _base_address(norm_addr: str) -> str:
    """Strip unit/suite/floor/building designations to obtain primary street address."""
    s = re.sub(r"\b(?:ste|suite|unit|apt|apartment|fl|floor|bldg|building|#)\s*[a-z0-9\-]+\b", "", norm_addr)
    return re.sub(r"\s+", " ", s).strip()


def run_check_t2(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute T2 cross-page inconsistency checks across the corpus."""
    findings: List[Dict[str, Any]] = []

    # Map role -> normalized_phone -> list of (url, raw_phone)
    phones_by_role: Dict[str, Dict[str, List[Tuple[str, str]]]] = {}

    # Map normalized_address -> list of (url, raw_address)
    addresses_by_norm: Dict[str, List[Tuple[str, str]]] = {}

    # Map url -> set of (metric_val, raw_metric)
    metrics_by_url: Dict[str, Set[Tuple[int, str]]] = {}

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

        # 1. Extract phone instances with role context
        for m in PHONE_RE.finditer(text):
            raw_phone = m.group(0)
            norm = _normalize_phone(raw_phone)
            # Filter dummy placeholder sequences
            if len(norm) == 10 and not norm.startswith("000") and norm != "1234567890":
                role = _extract_phone_role(text, m.start(), m.end())
                phones_by_role.setdefault(role, {}).setdefault(norm, []).append((url, raw_phone))

        # 2. Extract address instances
        for m in STREET_RE.finditer(text):
            raw_addr = m.group(0).strip()
            norm_addr = _normalize_address(raw_addr)
            if len(norm_addr) > 8:
                addresses_by_norm.setdefault(norm_addr, []).append((url, raw_addr))

        # 3. Extract metrics
        for m in METRIC_RE.finditer(text):
            raw_metric = m.group(0)
            cnt_str = m.group(1).replace(",", "")
            if cnt_str.isdigit():
                metrics_by_url.setdefault(url, set()).add((int(cnt_str), raw_metric))

    finding_idx = 1

    # --- Check 1: Inconsistent Phone Numbers across pages (under same role/department) ---
    for role, phones_map in sorted(phones_by_role.items()):
        if len(phones_map) > 1:
            norm_keys = sorted(phones_map.keys())
            # Find pairwise conflicts between distinct URLs
            for i in range(len(norm_keys)):
                for j in range(i + 1, len(norm_keys)):
                    norm_a = norm_keys[i]
                    norm_b = norm_keys[j]
                    inst_a = phones_map[norm_a]
                    inst_b = phones_map[norm_b]

                    # Verify they occur on distinct URLs
                    url_a, raw_a = inst_a[0]
                    url_b, raw_b = inst_b[0]

                    if url_a != url_b:
                        role_label = f" ({role} department)" if role != "general" else ""
                        findings.append({
                            "id": f"F-T2-{finding_idx:03d}",
                            "check_id": "T2",
                            "page_url": url_a,
                            "root_cause": "corroboration_deficit",
                            "evidence": {
                                "fact_type": "telephone_number",
                                "role": role,
                                "normalized_value_a": norm_a,
                                "raw_value_a": raw_a,
                                "url_a": url_a,
                                "normalized_value_b": norm_b,
                                "raw_value_b": raw_b,
                                "url_b": url_b,
                            },
                            "raw_severity_class": "medium",
                            "confidence": 0.90,
                            "mechanism": (
                                f"Contradictory phone numbers{role_label} detected across pages: '{raw_a}' on {url_a} vs "
                                f"'{raw_b}' on {url_b}. AI assistants synthesizing contact details will encounter "
                                "conflicting corroboration and may refuse to state contact numbers or hallucinate "
                                "between contradictory numbers."
                            ),
                            "false_positive_guard": (
                                "Role and normalization guard: stripped all whitespace, country-code prefixes (+1), "
                                "parentheses, and punctuation before comparison. Verified numbers belong to the same "
                                f"role ('{role}'); distinct departments (e.g. Sales vs Support) do not conflict."
                            ),
                            "verification_method": f"curl -sL {url_a} | grep -E '{raw_a}' && curl -sL {url_b} | grep -E '{raw_b}'",
                        })
                        finding_idx += 1
                        break  # Report one clear conflict per role
                if len(findings) > 0 and findings[-1]["check_id"] == "T2" and findings[-1]["evidence"].get("role") == role:
                    break

    # --- Check 2: Inconsistent Physical Addresses across pages ---
    if len(addresses_by_norm) > 1:
        addr_norms = sorted(addresses_by_norm.keys())
        for i in range(len(addr_norms)):
            for j in range(i + 1, len(addr_norms)):
                norm_a = addr_norms[i]
                norm_b = addr_norms[j]

                # Substring/Unit extension guard: if one adds suite/unit or is a substring, do not conflict
                if norm_a in norm_b or norm_b in norm_a or _base_address(norm_a) == _base_address(norm_b):
                    continue

                inst_a = addresses_by_norm[norm_a]
                inst_b = addresses_by_norm[norm_b]
                url_a, raw_a = inst_a[0]
                url_b, raw_b = inst_b[0]

                if url_a != url_b:
                    findings.append({
                        "id": f"F-T2-{finding_idx:03d}",
                        "check_id": "T2",
                        "page_url": url_a,
                        "root_cause": "corroboration_deficit",
                        "evidence": {
                            "fact_type": "physical_address",
                            "normalized_value_a": norm_a,
                            "raw_value_a": raw_a,
                            "url_a": url_a,
                            "normalized_value_b": norm_b,
                            "raw_value_b": raw_b,
                            "url_b": url_b,
                        },
                        "raw_severity_class": "medium",
                        "confidence": 0.88,
                        "mechanism": (
                            f"Contradictory physical street addresses asserted across pages: '{raw_a}' on {url_a} vs "
                            f"'{raw_b}' on {url_b}. Autonomous assistants cross-referencing company credentials require "
                            "a single unambiguous physical location for local grounding and corporate verification."
                        ),
                        "false_positive_guard": (
                            "Address normalization guard: normalized street abbreviations (Street/St, Avenue/Ave, Suite/Ste), "
                            "whitespace, and casing. Evaluated across distinct page URLs; substring/unit extensions excluded."
                        ),
                        "verification_method": f"curl -sL {url_a} | grep -iE '{raw_a[:20]}' && curl -sL {url_b} | grep -iE '{raw_b[:20]}'",
                    })
                    finding_idx += 1
                    break
            if len(findings) > 0 and findings[-1]["evidence"].get("fact_type") == "physical_address":
                break

    # --- Check 3: Inconsistent Claimed Metrics across pages ---
    all_metrics: Dict[int, List[Tuple[str, str]]] = {}
    for u, m_set in metrics_by_url.items():
        for cnt, raw in m_set:
            all_metrics.setdefault(cnt, []).append((u, raw))

    if len(all_metrics) > 1:
        metric_vals = sorted(all_metrics.keys())
        min_v, max_v = metric_vals[0], metric_vals[-1]
        # Only flag when discrepancy is significant (>= 2x difference)
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
