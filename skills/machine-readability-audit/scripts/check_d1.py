#!/usr/bin/env python3
"""
check_d1.py — D1 JS-render gap check (flagship).

Compares visible text from raw HTML and rendered DOM on sampled pages in the corpus.
Flags only when BOTH:
  1. >40% of visible words are missing in raw HTML vs rendered DOM, AND
  2. The absolute gap is >300 words.

Checks SSR/prerender escape hatches (__NEXT_DATA__, JSON state, <noscript>).
Opaque application state is NOT an escape hatch. Semantic extractability reduces confidence.
If rendered.html is absent, uses a bounded heuristic fallback at explicitly reduced confidence.

Usage:
    python check_d1.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _extract_visible_text(html: str) -> str:
    """Extract visible text from HTML, stripping non-visible tags."""
    if not html:
        return ""
    # Remove non-visible elements
    cleaned = re.sub(
        r'<(script|style|noscript|svg|canvas|template)[^>]*>.*?</\1>',
        ' ', html, flags=re.DOTALL | re.IGNORECASE,
    )
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', cleaned)
    # Decode basic entities & normalize whitespace
    text = re.sub(r'&nbsp;', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'&amp;', '&', text, flags=re.IGNORECASE)
    text = re.sub(r'&[a-z]+;', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _words(text: str) -> List[str]:
    """Tokenize visible text into word tokens."""
    return [w for w in re.split(r'\s+', text) if w]


def _find_post_render_fact(raw_text: str, rendered_text: str) -> Optional[str]:
    """Find a concrete sentence or substantive phrase present in rendered DOM but missing from raw."""
    raw_lower = raw_text.lower()
    # Split rendered text into sentences or punctuation chunks
    sentences = re.split(r'[.!?\n]+', rendered_text)
    for s in sentences:
        s_clean = s.strip()
        tokens = s_clean.split()
        # Look for a substantive chunk: 6 to 25 words
        if 6 <= len(tokens) <= 25:
            # Check if this phrase is completely absent from raw HTML text
            phrase = " ".join(tokens)
            if phrase.lower() not in raw_lower:
                # Also check that most words don't appear together
                subset_matches = sum(1 for t in tokens if t.lower() in raw_lower)
                if subset_matches / len(tokens) < 0.6:
                    return phrase
    # Fallback: find any 8-token sequence
    rendered_tokens = _words(rendered_text)
    for i in range(0, len(rendered_tokens) - 8, 4):
        seq = " ".join(rendered_tokens[i:i + 8])
        if seq.lower() not in raw_lower:
            return seq
    return None


def _check_escape_hatches(raw_html: str, post_render_fact: Optional[str]) -> Tuple[bool, bool, str]:
    """
    Check if raw HTML provides an SSR / prerender escape hatch.
    Returns: (detected, usable, details)
    Framework JSON or <noscript> only reduces confidence when relevant missing facts
    are actually semantically extractable. Opaque application state is NOT an escape hatch.
    """
    detected = False
    usable = False
    details_parts = []

    # 1. Framework JSON (e.g. Next.js, Nuxt, SvelteKit, application/json)
    json_scripts = re.findall(
        r'<script[^>]+(?:id=["\'](?:__NEXT_DATA__|__NUXT_DATA__|svelte-data)["\']|type=["\']application/json["\'])[^>]*>(.*?)</script>',
        raw_html, flags=re.DOTALL | re.IGNORECASE,
    )
    if json_scripts:
        detected = True
        combined_json = " ".join(json_scripts)
        # Check if it contains human-readable semantic text or if it's opaque state
        if post_render_fact:
            fact_tokens = [t.lower() for t in post_render_fact.split() if len(t) > 3]
            matches = sum(1 for t in fact_tokens if t in combined_json.lower())
            if fact_tokens and (matches / len(fact_tokens) >= 0.7):
                usable = True
                details_parts.append("Framework JSON state contains matching semantic text for missing facts")
            else:
                details_parts.append("Framework JSON state present but missing facts are not extractable (opaque state)")
        else:
            # General heuristic on JSON content
            if len(combined_json) > 500 and not re.search(r'[a-zA-Z]{5,}\s+[a-zA-Z]{4,}', combined_json):
                details_parts.append("Framework JSON is minified opaque state/hashes")
            else:
                usable = True
                details_parts.append("Framework JSON state contains readable strings")

    # 2. <noscript> content
    noscript_blocks = re.findall(r'<noscript[^>]*>(.*?)</noscript>', raw_html, flags=re.DOTALL | re.IGNORECASE)
    if noscript_blocks:
        detected = True
        noscript_text = _extract_visible_text(" ".join(noscript_blocks))
        if len(noscript_text.split()) > 50:
            usable = True
            details_parts.append("Substantive <noscript> fallback text provided")
        else:
            details_parts.append("<noscript> contains only minimal browser warning")

    if not detected:
        return False, False, "No SSR escape hatches detected in raw HTML"

    return detected, usable, "; ".join(details_parts)


def _check_heuristic_fallback(raw_html: str, page_url: str) -> Optional[Dict[str, Any]]:
    """
    Bounded heuristic fallback when Playwright / rendered.html is unavailable.
    Never claims high confidence.
    """
    visible_text = _extract_visible_text(raw_html)
    raw_words = len(_words(visible_text))

    # Check for empty SPA mounting container
    spa_container_match = re.search(
        r'<div[^>]+id=["\'](root|app|__next|__nuxt|main-app)["\'][^>]*>\s*</div>',
        raw_html, flags=re.IGNORECASE,
    )
    # Check for heavy JS application bundle cues
    has_bundle = bool(re.search(
        r'<script[^>]+src=["\'][^"\']*(?:chunk|bundle|main\.[0-9a-f]+|app\.[0-9a-f]+|index\.[0-9a-f]+)\.js["\']',
        raw_html, flags=re.IGNORECASE,
    ))

    if spa_container_match and raw_words < 120 and has_bundle:
        container_id = spa_container_match.group(1)
        return {
            "raw_words": raw_words,
            "container_id": container_id,
            "has_bundle": True,
            "evidence_note": f"Client-side SPA shell detected (<div id='{container_id}'>) with only {raw_words} words of visible text in raw HTML",
        }
    return None


def run_check_d1(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Execute D1 check across sampled pages in corpus.
    Returns list of candidate findings satisfying the Hardened Finding Contract.
    """
    findings: List[Dict[str, Any]] = []

    # Identify page directories
    page_dirs = [d for d in corpus_dir.iterdir() if d.is_dir() and (d / "raw.html").exists()]
    if not page_dirs:
        # Check subdirectories if nested
        for sub in corpus_dir.glob("*/raw.html"):
            page_dirs.append(sub.parent)

    finding_idx = 1

    for pdir in sorted(page_dirs):
        raw_path = pdir / "raw.html"
        rendered_path = pdir / "rendered.html"
        meta_path = pdir / "meta.json"

        meta: Dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        page_url = meta.get("url", f"https://example.com/{pdir.name}")
        raw_html = raw_path.read_text(encoding="utf-8", errors="replace")

        # Primary Path: rendered.html exists
        if rendered_path.exists():
            rendered_html = rendered_path.read_text(encoding="utf-8", errors="replace")
            raw_text = _extract_visible_text(raw_html)
            rendered_text = _extract_visible_text(rendered_html)

            raw_word_count = len(_words(raw_text))
            rendered_word_count = len(_words(rendered_text))
            gap = rendered_word_count - raw_word_count
            ratio = (gap / rendered_word_count) if rendered_word_count > 0 else 0.0

            # FLAG RULE: BOTH >40% of words missing AND absolute gap > 300 words
            if ratio > 0.40 and gap > 300:
                post_render_fact = _find_post_render_fact(raw_text, rendered_text)
                fact_str = post_render_fact if post_render_fact else "Substantive rendered body content missing from raw HTML"

                hatch_detected, hatch_usable, hatch_details = _check_escape_hatches(raw_html, post_render_fact)

                # Confidence calculation
                if hatch_usable:
                    # Escape hatch is usable -> reduces confidence
                    confidence = 0.65
                else:
                    confidence = 0.92

                severity = "critical" if (ratio > 0.70 or gap > 800) else "high"

                findings.append({
                    "id": f"F-D1-{finding_idx:03d}",
                    "check_id": "D1",
                    "page_url": page_url,
                    "root_cause": "representation_gap",
                    "evidence": {
                        "type": "js_render_gap",
                        "raw_word_count": raw_word_count,
                        "rendered_word_count": rendered_word_count,
                        "missing_word_count": gap,
                        "missing_word_ratio": round(ratio, 3),
                        "post_render_fact": fact_str,
                        "escape_hatch_detected": hatch_detected,
                        "escape_hatch_usable": hatch_usable,
                        "escape_hatch_details": hatch_details,
                        "execution_mode": "rendered_dom",
                    },
                    "raw_severity_class": severity,
                    "confidence": confidence,
                    "mechanism": (
                        f"Page requires client-side JavaScript execution to render primary content. "
                        f"An agent fetching raw HTML sees only {raw_word_count} words ({round(ratio*100, 1)}% missing, "
                        f"{gap} words omitted), including post-render facts like '{fact_str[:80]}...'. "
                        f"Agents without headless browser execution receive an incomplete representation."
                    ),
                    "false_positive_guard": (
                        f"Verified BOTH >40% missing words ({round(ratio*100, 1)}%) AND absolute gap >300 words ({gap} words). "
                        f"Checked SSR escape hatches: {hatch_details}."
                    ),
                    "verification_method": (
                        f"Compare raw HTML word count `curl -sL {page_url} | wc -w` against browser DOM."
                    ),
                })
                finding_idx += 1

        else:
            # Fallback Path: rendered.html does not exist
            heuristic_result = _check_heuristic_fallback(raw_html, page_url)
            if heuristic_result:
                findings.append({
                    "id": f"F-D1-{finding_idx:03d}",
                    "check_id": "D1",
                    "page_url": page_url,
                    "root_cause": "representation_gap",
                    "evidence": {
                        "type": "js_render_gap_heuristic",
                        "raw_word_count": heuristic_result["raw_words"],
                        "spa_container": heuristic_result["container_id"],
                        "has_bundle": heuristic_result["has_bundle"],
                        "execution_mode": "heuristic_fallback",
                        "limitation_note": "Playwright rendered DOM was unavailable; classified via bounded SPA heuristics.",
                    },
                    "raw_severity_class": "high",
                    "confidence": 0.48,  # Bounded heuristic fallback: never claim high confidence
                    "mechanism": (
                        f"Page contains an empty SPA mounting point (<div id='{heuristic_result['container_id']}'>) "
                        f"and only {heuristic_result['raw_words']} visible words in raw HTML, requiring client-side JS "
                        f"to populate primary content."
                    ),
                    "false_positive_guard": (
                        f"Verified raw visible text is under 120 words ({heuristic_result['raw_words']} words) and "
                        f"empty client-side SPA root with JS bundle is present. Confidence strictly capped at 0.48."
                    ),
                    "verification_method": (
                        f"Fetch raw HTML `curl -sL {page_url}` and verify <div id='{heuristic_result['container_id']}'> is empty."
                    ),
                })
                finding_idx += 1

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="D1 — JS-render gap check")
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

    findings = run_check_d1(corpus_dir, manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
