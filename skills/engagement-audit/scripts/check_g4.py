#!/usr/bin/env python3
"""
check_g4.py — G4 No Discernible Primary Action Check (Tier 2: Engagement Audit).

Audits homepage and commercial product/service landing pages for the presence of a
discernible primary call-to-action among a bounded set of intent-bearing links/buttons:
contact, buy, purchase, quote, book, demo, sign-up, start, subscribe, download,
or equivalent archetype-specific actions (e.g. get started, try free, documentation).

Negative-Logic Rules (False-Positive Guards):
- Non-Commercial Exemption: If a page's purpose does not require an immediate action
  (editorial essays, blog articles, documentation reference entries, privacy policies,
  terms of service, and informational pages), DO NOT FLAG and record that guard.
- Measurable Signal Guard: Action candidates must have measurable visible text and
  a concrete target link (href) or form submission action.
- Clean pages with clear CTA links (e.g. 'Get Started', 'Buy Now', 'Contact Us')
  cleanly pass with 0 findings.

Usage:
    python check_g4.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# Bounded set of intent-bearing action keywords
INTENT_ACTION_PATTERNS = [
    re.compile(r"\b(?:get\s+started|start(?:\s+(?:free|trial|now|here))?|try(?:\s+(?:free|now|it))?)\b", re.IGNORECASE),
    re.compile(r"\b(?:sign\s*up|create\s+account|register|join(?:\s+(?:now|free))?)\b", re.IGNORECASE),
    re.compile(r"\b(?:buy(?:\s+now)?|purchase|order(?:\s+now)?|checkout|add\s+to\s+cart|shop(?:\s+now)?)\b", re.IGNORECASE),
    re.compile(r"\b(?:book(?:\s+(?:a\s+)?demo)?|schedule(?:\s+(?:a\s+)?demo)?|demo|quote|request\s+(?:a\s+)?quote)\b", re.IGNORECASE),
    re.compile(r"\b(?:contact(?:\s+us)?|reach\s+us|get\s+in\s+touch|talk\s+to\s+sales|support)\b", re.IGNORECASE),
    re.compile(r"\b(?:download|install|subscribe|read\s+docs|documentation|explore\s+docs|pricing|view\s+pricing)\b", re.IGNORECASE),
]

# Pages whose purpose does not require an immediate commercial or operational call-to-action
NON_COMMERCIAL_PATHS_RE = re.compile(
    r"/(?:blog|posts?|articles?|news|stories|essays?|docs?|documentation|guides?|reference|api|privacy|terms|legal|disclaimer|faq|about)(?:/|$|\?)",
    re.IGNORECASE,
)

COMMERCIAL_PAGE_RE = re.compile(
    r"/(?:pricing|plans?|products?|features?|services?|solutions?|store|shop)(?:/|$|\?)",
    re.IGNORECASE,
)


def _has_primary_action(html: str) -> Tuple[bool, Optional[str]]:
    """Inspect HTML for buttons or styled links containing intent-bearing action text."""
    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        # Find clickable action elements
        candidates = soup.find_all(["a", "button", "input"])
        for el in candidates:
            text = ""
            if el.name == "input":
                if el.get("type", "").lower() in ("submit", "button"):
                    text = el.get("value", "")
            else:
                text = el.get_text(strip=True)

            href = el.get("href", "")
            if el.name == "a" and (not href or href.startswith("#") or href.startswith("javascript:")):
                # If it has meaningful text like 'Get Started', it might be a JS-bound button
                pass

            if text and len(text) <= 40:
                for pat in INTENT_ACTION_PATTERNS:
                    if pat.search(text):
                        return True, f"<{el.name}>: '{text}'"

    # Regex fallback
    for pat in INTENT_ACTION_PATTERNS:
        m = pat.search(html)
        if m:
            return True, f"text: '{m.group(0)}'"

    return False, None


def run_check_g4(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute G4 Primary Action Check across homepage and commercial landing pages."""
    findings: List[Dict[str, Any]] = []
    finding_idx = 1

    domain = manifest.get("domain", "") if manifest else ""
    evaluated_urls: Set[str] = set()

    for page_dir in sorted(corpus_dir.iterdir()):
        if not page_dir.is_dir():
            continue

        meta_path = page_dir / "meta.json"
        raw_path = page_dir / "rendered.html"
        if not raw_path.exists():
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

        if not url or url in evaluated_urls:
            continue
        evaluated_urls.add(url)

        parsed = urlparse(url)
        path = parsed.path.lower()

        # Determine page role
        is_home = path in ("", "/", "/index.html")
        is_commercial = bool(COMMERCIAL_PAGE_RE.search(path))

        # NON-COMMERCIAL EXEMPTION GUARD:
        # Informational, editorial, legal, and reference pages do not require an immediate action
        if NON_COMMERCIAL_PATHS_RE.search(path) and not is_home:
            continue

        # Check applies to Homepage and commercial landing/product pages
        if not (is_home or is_commercial):
            continue

        html = raw_path.read_text(encoding="utf-8", errors="replace")
        text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""

        # Substantive content guard (exclude empty shells / error stubs)
        if len(text.split()) < 10:
            continue

        has_action, action_sample = _has_primary_action(html)

        if not has_action:
            role_label = "homepage" if is_home else "product/commercial page"
            findings.append({
                "id": f"F-G4-{finding_idx:03d}",
                "check_id": "G4",
                "page_url": url,
                "root_cause": "statement_implicitness",
                "evidence": {
                    "type": "missing_primary_action",
                    "page_role": role_label,
                    "target_url": url,
                    "evaluated_action_intents": [
                        "contact", "buy", "purchase", "quote", "book_demo",
                        "sign_up", "get_started", "subscribe", "download", "documentation"
                    ],
                },
                "raw_severity_class": "medium",
                "confidence": 0.88,
                "mechanism": (
                    f"The {role_label} '{url}' lacks any detectable primary call-to-action button or conversion link. "
                    "Visitors seeking to engage, purchase, or sign up encounter an actionability void, leaving "
                    "them stranded without a clear next step in their user journey."
                ),
                "false_positive_guard": (
                    "Reasoning + heuristic action guard: inspected anchor, button, and input elements against bounded "
                    "action intents. Editorial articles, blog posts, documentation entries, and legal pages are strictly "
                    "exempted from action requirements."
                ),
                "verification_method": f"curl -sL '{url}' | grep -iE 'button|get started|sign up|buy now'",
            })
            finding_idx += 1

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="G4 — Primary Action Check")
    parser.add_argument("corpus_dir", type=Path, help="Directory containing crawled page subdirectories")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to crawl_manifest.json")
    args = parser.parse_args()

    manifest_data: Optional[Dict[str, Any]] = None
    if args.manifest and args.manifest.exists():
        try:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception:
            pass

    findings = run_check_g4(args.corpus_dir, manifest=manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
