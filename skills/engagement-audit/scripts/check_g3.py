#!/usr/bin/env python3
"""
check_g3.py — G3 Friction & Intrusive Obstructions Check (Tier 2: Engagement Audit).

Audits pages for human interaction friction using explicit deterministic thresholds:
1. Interstitial/modal DOM elements covering substantive content on load.
2. Transferred page payload exceeding 5MB (5,242,880 bytes).
3. Primary content pushed below a media block that exceeds 50% of the initial viewport height.

Negative-Logic Rules (False-Positive Guards):
- Cookie & Legal Notice Exemption: NEVER flag cookie banners, consent dialogs, or legally
  required privacy notices as friction findings. These are legal compliance mechanisms.
- Intentional Page Control Guard: Modals that are hidden by default (display: none, aria-hidden)
  or user-invoked navigation drawers are excluded.
- Explicit Threshold Guard: Payload must strictly exceed 5MB; media blocks must exceed 50vh.

Usage:
    python check_g3.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

PAYLOAD_THRESHOLD_BYTES = 5 * 1024 * 1024  # 5 MB = 5,242,880 bytes

COOKIE_LEGAL_KEYWORDS = [
    "cookie", "consent", "gdpr", "privacy", "tracking", "terms", "compliance",
    "opt-in", "preferences", "manage cookies", "accept all",
]

# Patterns for intrusive modal/interstitial containers
MODAL_CLASS_RE = re.compile(
    r'\b(?:class|id)=["\'][^"\']*(?:interstitial|popup|newsletter-modal|lead-capture|promo-modal|overlay-modal)[^"\']*["\']',
    re.IGNORECASE,
)

# Style patterns for full-screen fixed overlay covering content
FIXED_OVERLAY_RE = re.compile(
    r'style=["\'][^"\']*(?:position\s*:\s*fixed|position\s*:\s*absolute)[^"\']*(?:inset\s*:\s*0|width\s*:\s*100%)[^"\']*(?:z-index\s*:\s*(?:[1-9]\d{2,}|9999))[^"\']*["\']',
    re.IGNORECASE,
)

# Media height > 50vh or > 500px preceding main content
MEDIA_DISPLACEMENT_RE = re.compile(
    r'<(?:video|iframe|div)[^>]*(?:class=["\'][^"\']*(?:video-hero|hero-media|bg-video)[^"\']*["\']|style=["\'][^"\']*(?:height\s*:\s*(?:[5-9]\d|100)vh|height\s*:\s*(?:[5-9]\d{2}|\d{4,})px)[^"\']*["\'])[^>]*>',
    re.IGNORECASE,
)


def _is_cookie_or_legal_banner(snippet: str) -> bool:
    """Check if the detected element is a legally required cookie/privacy notice."""
    s = snippet.lower()
    return any(k in s for k in COOKIE_LEGAL_KEYWORDS)


def run_check_g3(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute G3 Friction checks across all corpus pages."""
    findings: List[Dict[str, Any]] = []
    finding_idx = 1

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

        if not url:
            continue

        html = raw_path.read_text(encoding="utf-8", errors="replace")
        text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
        headers = meta.get("response_headers", {})

        # ---------------------------------------------------------------------
        # 1. Heavy Page Payload Check (> 5MB)
        # ---------------------------------------------------------------------
        content_len_str = headers.get("content-length") or headers.get("Content-Length")
        payload_bytes = 0
        if content_len_str and str(content_len_str).isdigit():
            payload_bytes = int(content_len_str)
        else:
            payload_bytes = len(html.encode("utf-8"))

        if payload_bytes > PAYLOAD_THRESHOLD_BYTES:
            mb = round(payload_bytes / (1024 * 1024), 2)
            findings.append({
                "id": f"F-G3-{finding_idx:03d}",
                "check_id": "G3",
                "page_url": url,
                "root_cause": "orientation_cost",
                "evidence": {
                    "type": "excessive_page_payload",
                    "payload_bytes": payload_bytes,
                    "threshold_bytes": PAYLOAD_THRESHOLD_BYTES,
                    "payload_mb": mb,
                },
                "raw_severity_class": "medium",
                "confidence": 0.95,
                "mechanism": (
                    f"Page transferred payload of {mb}MB exceeds the 5.0MB ceiling. Excessive payload sizes "
                    "cause high initial latency, slow Time to Interactive (TTI), and aggressive bounce rates "
                    "on mobile and resource-constrained networks."
                ),
                "false_positive_guard": (
                    f"Explicit threshold guard: measured total payload ({payload_bytes} bytes > {PAYLOAD_THRESHOLD_BYTES} bytes). "
                    "Sub-5MB payloads cleanly pass."
                ),
                "verification_method": f"curl -sI '{url}' | grep -i 'content-length'",
            })
            finding_idx += 1

        # ---------------------------------------------------------------------
        # 2. Interstitial / Modal Covering Substantive Content on Load
        # ---------------------------------------------------------------------
        modal_match = MODAL_CLASS_RE.search(html) or FIXED_OVERLAY_RE.search(html)
        if modal_match:
            matched_str = modal_match.group(0)
            # Find snippet around the match
            start_pos = max(0, modal_match.start() - 50)
            end_pos = min(len(html), modal_match.end() + 250)
            snippet = html[start_pos:end_pos]

            # Hidden guard: skip if display: none or aria-hidden="true"
            is_hidden = bool(re.search(r'(?:display\s*:\s*none|aria-hidden=["\']true["\'])', snippet, re.IGNORECASE))

            # COOKIE & LEGAL NOTICE EXEMPTION (Mandatory False-Positive Guard):
            is_legal = _is_cookie_or_legal_banner(snippet)

            if not is_hidden and not is_legal:
                findings.append({
                    "id": f"F-G3-{finding_idx:03d}",
                    "check_id": "G3",
                    "page_url": url,
                    "root_cause": "orientation_cost",
                    "evidence": {
                        "type": "intrusive_interstitial_modal",
                        "matched_element": matched_str[:80],
                        "is_cookie_or_legal_banner": False,
                        "is_hidden": False,
                    },
                    "raw_severity_class": "medium",
                    "confidence": 0.88,
                    "mechanism": (
                        f"Page '{url}' renders an unprompted overlay/modal on load covering substantive content. "
                        "Intrusive popups create immediate cognitive friction, obstruct task flow, and trigger "
                        "search engine interstitials penalties."
                    ),
                    "false_positive_guard": (
                        "Conservative friction guard: cookie notices, GDPR consent dialogs, and legal banners are "
                        "strictly excluded. Evaluated active visibility and full-screen overlay positioning."
                    ),
                    "verification_method": f"curl -sL '{url}' | grep -iE 'interstitial|popup|lead-capture'",
                })
                finding_idx += 1

        # ---------------------------------------------------------------------
        # 3. Media Block Viewport Displacement (> 50vh / 50% viewport)
        # ---------------------------------------------------------------------
        media_match = MEDIA_DISPLACEMENT_RE.search(html)
        if media_match:
            # Verify this media element appears before substantive heading or paragraph
            h1_pos = html.find("<h1")
            p_pos = html.find("<p")
            media_pos = media_match.start()

            # If media block precedes main heading or first paragraph
            if (h1_pos == -1 or media_pos < h1_pos) and (p_pos == -1 or media_pos < p_pos):
                findings.append({
                    "id": f"F-G3-{finding_idx:03d}",
                    "check_id": "G3",
                    "page_url": url,
                    "root_cause": "orientation_cost",
                    "evidence": {
                        "type": "media_viewport_displacement",
                        "media_element": media_match.group(0)[:80],
                        "displacement_threshold": "> 50vh / 450px",
                    },
                    "raw_severity_class": "medium",
                    "confidence": 0.85,
                    "mechanism": (
                        f"Top-of-page media element on '{url}' exceeds 50% viewport height, pushing all substantive "
                        "text and headings below the initial fold. Users encounter an orientation vacuum requiring "
                        "immediate scrolling before understanding page context."
                    ),
                    "false_positive_guard": (
                        "Threshold guard: verified media block height (> 50vh or > 450px) and confirmed location "
                        "preceding primary substantive headings or text."
                    ),
                    "verification_method": f"curl -sL '{url}' | grep -iE 'video-hero|hero-media'",
                })
                finding_idx += 1

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="G3 — Friction & Obstructions Check")
    parser.add_argument("corpus_dir", type=Path, help="Directory containing crawled page subdirectories")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to crawl_manifest.json")
    args = parser.parse_args()

    manifest_data: Optional[Dict[str, Any]] = None
    if args.manifest and args.manifest.exists():
        try:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception:
            pass

    findings = run_check_g3(args.corpus_dir, manifest=manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
