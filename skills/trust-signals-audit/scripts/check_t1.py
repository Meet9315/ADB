#!/usr/bin/env python3
"""
check_t1.py — T1 Staleness and Undated Content Check (Tier 1: Trust Signals Audit).

Audits the local corpus for temporal decay:
1. Staleness: Detects outdated temporal markers on TIME-SENSITIVE content
   (pricing, plans, status, "current" claims).
2. Undated content: Detects substantive pages lacking any temporal anchors
   (emitted as a separate, lower-severity finding; never bucketed with staleness).

Negative-Logic Rules:
- Evergreen essays, articles, and general blog posts are NOT flagged for staleness
  even if their publication date is old.
- Only time-sensitive content (pricing, current status, active roadmaps, 'as of' claims)
  with stale dates (<= 2024, given 2026 reference) triggers staleness findings.
- Undated content is strictly separated from staleness with lower severity ('low').
- Substantive threshold: pages with visible words < 80 are excluded.

Usage:
    python check_t1.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

# Reference year for freshness audits (2026)
REFERENCE_YEAR = 2026
STALE_THRESHOLD_YEAR = REFERENCE_YEAR - 2  # <= 2024 is stale for time-sensitive claims

PRICING_PATH_RE = re.compile(r"/(?:pricing|plans?|rates?|costs?|fees?|packages?)(?:/|$|\?)", re.IGNORECASE)
TIME_SENSITIVE_PHRASES = [
    re.compile(r"\bcurrent\s+(?:pricing|rates?|plans?|costs?|status|offerings?)\b", re.IGNORECASE),
    re.compile(r"\bas\s+of\s+(?:january|february|march|april|may|june|july|august|september|october|november|december\s+)?(20[0-9]{2})\b", re.IGNORECASE),
    re.compile(r"\beffective\s+(?:date\s*:?\s*)?(?:january|february|march|april|may|june|july|august|september|october|november|december\s+)?(20[0-9]{2})\b", re.IGNORECASE),
    re.compile(r"\blast\s+updated\s*:?\s*(?:[a-z]+\s+\d{1,2},\s*)?(20[0-9]{2})\b", re.IGNORECASE),
]
YEAR_RE = re.compile(r"\b(19\d\d|20\d\d)\b")
COPYRIGHT_RE = re.compile(r"(?:©|&copy;|copyright)\s*(?:20\d\d(?:\s*[-–—]\s*(20\d\d))?|(20\d\d))", re.IGNORECASE)


def _extract_dates_from_page(html: str, text: str) -> Dict[str, Any]:
    """Extract temporal markers from visible text and structured metadata."""
    found_years: Set[int] = set()
    as_of_claims: List[Tuple[str, int]] = []
    copyright_year: Optional[int] = None

    # 1. Check copyright
    for m in COPYRIGHT_RE.finditer(html):
        yr_str = m.group(1) or m.group(2)
        if yr_str and yr_str.isdigit():
            yr = int(yr_str)
            copyright_year = yr
            found_years.add(yr)

    # 2. Check JSON-LD dateModified and datePublished
    jsonld_re = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
    for m in jsonld_re.finditer(html):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else [data]
            for it in items:
                if isinstance(it, dict):
                    for k in ("dateModified", "datePublished", "copyrightYear"):
                        v = str(it.get(k, ""))
                        ym = YEAR_RE.search(v)
                        if ym:
                            found_years.add(int(ym.group(1)))
        except Exception:
            pass

    # 3. Check time-sensitive phrases in visible text
    for phrase_re in TIME_SENSITIVE_PHRASES:
        for m in phrase_re.finditer(text):
            matched_text = m.group(0).strip()
            # If regex captured a year in group 1
            if m.lastindex and m.group(1) and m.group(1).isdigit():
                yr = int(m.group(1))
                found_years.add(yr)
                as_of_claims.append((matched_text, yr))
            else:
                # Look for year in vicinity (next 20 chars)
                start, end = m.span()
                vicinity = text[start:min(len(text), end + 25)]
                ym = YEAR_RE.search(vicinity)
                if ym:
                    yr = int(ym.group(1))
                    found_years.add(yr)
                    as_of_claims.append((vicinity.strip(), yr))

    # All general years in text
    for ym in YEAR_RE.finditer(text):
        found_years.add(int(ym.group(1)))

    return {
        "found_years": sorted(found_years),
        "as_of_claims": as_of_claims,
        "copyright_year": copyright_year,
    }


def _is_time_sensitive_page(url: str, html: str, text: str) -> Tuple[bool, str]:
    """Determine if page represents time-sensitive content requiring freshness."""
    path = urlparse(url).path.lower()

    if PRICING_PATH_RE.search(path):
        return True, "pricing_page"

    # Page contains pricing structures with price indicators
    has_prices = bool(re.search(r"[$€£]\s*\d+(?:\.\d{2})?(?:/(?:mo|month|yr|year|seat|user))?", text, re.IGNORECASE))
    has_pricing_words = bool(re.search(r"\b(?:tier|plan|subscription|pricing|per month|billed monthly)\b", text, re.IGNORECASE))
    if has_prices and has_pricing_words:
        return True, "pricing_table"

    # Explicit current claims
    if re.search(r"\b(?:current\s+(?:pricing|rates?|plans?|status)|active\s+roadmap)\b", text, re.IGNORECASE):
        return True, "explicit_current_claim"

    return False, "evergreen"


def run_check_t1(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute T1 check across all crawled pages."""
    findings: List[Dict[str, Any]] = []
    finding_idx = 1

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

        html = raw_path.read_text(encoding="utf-8", errors="replace")
        text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
        word_count = len(text.split())

        # Negative logic guard: skip non-substantive pages
        if word_count < 80:
            continue

        temporal_data = _extract_dates_from_page(html, text)
        found_years = [y for y in temporal_data["found_years"] if 1990 <= y <= REFERENCE_YEAR + 1]

        is_time_sensitive, context_type = _is_time_sensitive_page(url, html, text)

        # 1. Staleness check: ONLY fires on time-sensitive content with stale markers
        if is_time_sensitive:
            stale_claims = [c for c in temporal_data["as_of_claims"] if c[1] <= STALE_THRESHOLD_YEAR]
            stale_copyright = temporal_data["copyright_year"] is not None and temporal_data["copyright_year"] <= STALE_THRESHOLD_YEAR
            
            # If the page explicitly makes an 'as of [old_year]' claim or is a pricing page with only old dates
            if stale_claims:
                claim_text, claim_year = stale_claims[0]
                findings.append({
                    "id": f"F-T1-{finding_idx:03d}",
                    "check_id": "T1",
                    "page_url": url,
                    "root_cause": "temporal_decay",
                    "evidence": {
                        "type": "stale_time_sensitive_claim",
                        "context_type": context_type,
                        "stale_marker": claim_text,
                        "marker_year": claim_year,
                        "reference_year": REFERENCE_YEAR,
                        "age_years": REFERENCE_YEAR - claim_year,
                        "all_detected_years": found_years,
                    },
                    "raw_severity_class": "medium",
                    "confidence": 0.90,
                    "mechanism": (
                        f"Page '{url}' contains time-sensitive {context_type.replace('_', ' ')} with an outdated "
                        f"temporal marker ('{claim_text}'). AI search assistants verify factual freshness before "
                        "recommending commercial or operational terms. Stale dates degrade model trust and cause "
                        "assistants to flag pricing terms as unverified."
                    ),
                    "false_positive_guard": (
                        f"Time-sensitive gate: evaluated strictly for {context_type}; evergreen articles excluded. "
                        f"Detected claim year {claim_year} is older than freshness threshold {STALE_THRESHOLD_YEAR}."
                    ),
                    "verification_method": f"curl -sL {url} | grep -iE 'as of|pricing|effective|updated'",
                })
                finding_idx += 1
            elif context_type == "pricing_page" and found_years and max(found_years) <= STALE_THRESHOLD_YEAR:
                max_year = max(found_years)
                findings.append({
                    "id": f"F-T1-{finding_idx:03d}",
                    "check_id": "T1",
                    "page_url": url,
                    "root_cause": "temporal_decay",
                    "evidence": {
                        "type": "stale_pricing_page",
                        "context_type": "pricing_page",
                        "latest_detected_year": max_year,
                        "reference_year": REFERENCE_YEAR,
                        "age_years": REFERENCE_YEAR - max_year,
                        "all_detected_years": found_years,
                    },
                    "raw_severity_class": "medium",
                    "confidence": 0.85,
                    "mechanism": (
                        f"Pricing page '{url}' references temporal markers no newer than {max_year} "
                        f"(threshold: {STALE_THRESHOLD_YEAR}). AI shopping and quote agents may distrust pricing terms "
                        "lacking recent corroboration."
                    ),
                    "false_positive_guard": (
                        f"Verified page path is pricing-diagnostic and newest temporal anchor {max_year} <= {STALE_THRESHOLD_YEAR}."
                    ),
                    "verification_method": f"curl -sL {url} | grep -iE '20[0-9]{{2}}'",
                })
                finding_idx += 1

        # 2. Undated content check: separate, lower-severity finding, never bucketed with staleness
        elif not found_years:
            # Substantive page lacking any temporal anchors
            findings.append({
                "id": f"F-T1-{finding_idx:03d}",
                "check_id": "T1",
                "page_url": url,
                "root_cause": "temporal_decay",
                "evidence": {
                    "type": "undated_content",
                    "word_count": word_count,
                    "temporal_markers_found": 0,
                },
                "raw_severity_class": "low",
                "confidence": 0.80,
                "mechanism": (
                    f"Substantive page '{url}' ({word_count} words) lacks any temporal anchors (publication date, "
                    "last-updated timestamp, copyright notice, or JSON-LD dateModified). Autonomous agents "
                    "down-weight unanchored content due to freshness uncertainty."
                ),
                "false_positive_guard": (
                    f"Checked visible text, copyright strings, and JSON-LD for temporal markers. "
                    f"Only substantive pages (word_count={word_count} >= 80) lacking all dates are flagged."
                ),
                "verification_method": f"curl -sL {url} | grep -iE 'date|updated|published|copyright|20[0-9]{{2}}'",
            })
            finding_idx += 1

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="T1 — Staleness and Undated Content Check")
    parser.add_argument("corpus_dir", type=Path, help="Directory containing crawled page subdirectories")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to crawl_manifest.json")
    args = parser.parse_args()

    manifest_data: Optional[Dict[str, Any]] = None
    if args.manifest and args.manifest.exists():
        try:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception:
            pass

    findings = run_check_t1(args.corpus_dir, manifest=manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
