#!/usr/bin/env python3
"""
check_d2.py — D2: Detect content locked in non-text form.

Checks for:
1. Content-bearing <img> tags without alt text in prominent positions
   (hero, pricing, header, first section, or class~=hero/banner/pricing).
2. Text-light pages (< 100 words) whose main payload is a PDF embed or video
   embed without a transcript.

Reads raw.html and text.txt from each corpus page directory.

Usage:
    python check_d2.py <corpus_dir>

DO NOT FIRE when:
- Image has a non-empty alt attribute (any non-whitespace content).
- Image filename or class matches the decorative heuristic:
    filenames: icon, logo, arrow, bullet, divider, bg, background,
               spacer, pixel, 1x1, separator, pattern, texture, line
    classes:   icon, logo, avatar, badge, bullet, divider, separator
  The specific heuristic that ruled out each image is recorded in
  false_positive_guard.
- Image inline width/height attributes are both ≤ 50px (decorative dimensions).
- The surrounding text (within 300 characters of the <img> tag) already
  restates the informational content that the image conveys.
- CSS background images (not <img> elements) — only <img> tags are checked.
- The image is outside the prominent zones (below-the-fold indicators:
  not in <header>, not in first <section>, not in element with
  class containing hero/banner/pricing/feature).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Decorative image heuristics
# ---------------------------------------------------------------------------

DECORATIVE_FILENAME_KEYWORDS = {
    "icon", "logo", "arrow", "bullet", "divider", "bg", "background",
    "spacer", "pixel", "1x1", "separator", "pattern", "texture", "line",
    "chevron", "caret", "social", "spinner", "loading",
}

DECORATIVE_CLASS_KEYWORDS = {
    "icon", "logo", "avatar", "badge", "bullet", "divider", "separator",
    "social", "spinner", "emoji",
}

# Maximum image dimension (inline width/height) to consider decorative
MAX_DECORATIVE_PX = 50

# Minimum surrounding text length to consider "context restatement"
CONTEXT_WINDOW_CHARS = 300
MIN_RESTATEMENT_WORDS = 15  # Must be substantial paragraph text, not just nav/heading boilerplate

FINDING_ID_COUNTER: Dict[str, int] = {}


def _new_id(check_id: str) -> str:
    FINDING_ID_COUNTER[check_id] = FINDING_ID_COUNTER.get(check_id, 0) + 1
    return f"F-{check_id}-{FINDING_ID_COUNTER[check_id]:03d}"


# ---------------------------------------------------------------------------
# HTML parsing helpers
# ---------------------------------------------------------------------------

def _extract_prominent_html(html: str) -> str:
    """
    Extract HTML from prominent zones only:
    <header>, ALL <section> elements, and elements with class containing
    hero/banner/pricing/feature/cta.
    """
    zones = []

    # Header zone
    m = re.search(r"<header[^>]*>(.*?)</header>", html, re.DOTALL | re.IGNORECASE)
    if m:
        zones.append(m.group(1))

    # ALL sections (not just first — pricing section may be second or later)
    for m in re.finditer(r"<section[^>]*>(.*?)</section>", html, re.DOTALL | re.IGNORECASE):
        zones.append(m.group(1))

    # Elements with prominent class keywords (div/article too)
    prominent_classes = ("hero", "banner", "pricing", "feature", "cta", "jumbotron", "showcase")
    for cls_pattern in prominent_classes:
        for m in re.finditer(
            rf'<(?:div|article)[^>]+class=["\'][^"\']*{cls_pattern}[^"\']*["\'][^>]*>'
            rf'(.*?)</(?:div|article)>',
            html, re.DOTALL | re.IGNORECASE
        ):
            zones.append(m.group(1))

    return "\n".join(zones) if zones else html[:3000]  # Fallback: first 3000 chars


def _parse_img_tags(html_zone: str) -> List[Dict]:
    """
    Parse <img> tags and extract relevant attributes.
    Returns list of dicts with: src, alt, width, height, class, position.
    """
    imgs = []
    for m in re.finditer(r"<img\s([^>]*)>", html_zone, re.IGNORECASE):
        attrs_str = m.group(1)
        pos = m.start()

        def _attr(name: str) -> Optional[str]:
            a = re.search(
                rf'{name}\s*=\s*["\']([^"\']*)["\']', attrs_str, re.IGNORECASE
            )
            if a:
                return a.group(1)
            # Bare attribute (e.g. alt=word without quotes)
            b = re.search(rf'{name}\s*=\s*(\S+)', attrs_str, re.IGNORECASE)
            return b.group(1) if b else None

        imgs.append({
            "src": _attr("src") or "",
            "alt": _attr("alt"),          # None = absent; "" = empty
            "width": _attr("width"),
            "height": _attr("height"),
            "class": _attr("class") or "",
            "position": pos,
            "surrounding_text": _get_surrounding_text(html_zone, pos),
        })
    return imgs


def _get_surrounding_text(html: str, pos: int) -> str:
    """Extract visible text within ±CONTEXT_WINDOW_CHARS of position."""
    start = max(0, pos - CONTEXT_WINDOW_CHARS)
    end = min(len(html), pos + CONTEXT_WINDOW_CHARS)
    snippet = html[start:end]
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", snippet)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _px_value(val: Optional[str]) -> Optional[int]:
    if val is None:
        return None
    m = re.match(r"(\d+)", val.strip())
    return int(m.group(1)) if m else None


def _filename_from_src(src: str) -> str:
    """Extract bare filename without extension from a src URL."""
    fname = src.split("/")[-1].split("?")[0].split("#")[0]
    fname = re.sub(r"\.[^.]+$", "", fname)  # strip extension
    return fname.lower()


def _is_decorative(img: Dict) -> Tuple[bool, str]:
    """Return (is_decorative, reason)."""
    src = img["src"].lower()
    fname = _filename_from_src(src)
    classes = img["class"].lower()

    # Dimension heuristic
    w = _px_value(img["width"])
    h = _px_value(img["height"])
    if w is not None and h is not None and w <= MAX_DECORATIVE_PX and h <= MAX_DECORATIVE_PX:
        return True, f"inline dimensions {w}x{h}px ≤ {MAX_DECORATIVE_PX}px threshold"

    # Filename heuristic
    for kw in DECORATIVE_FILENAME_KEYWORDS:
        if kw in fname:
            return True, f"filename '{fname}' contains decorative keyword '{kw}'"

    # Class heuristic
    for kw in DECORATIVE_CLASS_KEYWORDS:
        if kw in classes:
            return True, f"class '{classes[:60]}' contains decorative keyword '{kw}'"

    return False, ""


def _context_restates_content(surrounding_text: str) -> Tuple[bool, str]:
    """
    Return (restates, reason). Heuristic: if surrounding text has ≥MIN_RESTATEMENT_WORDS
    substantive words, assume it provides context for the image.
    (A more precise implementation would compare image filename/alt candidate
    against the text, but without ML this is our conservative guard.)
    """
    words = [w for w in surrounding_text.split() if len(w) > 2]
    if len(words) >= MIN_RESTATEMENT_WORDS:
        sample = " ".join(words[:8])
        return True, f"surrounding text has {len(words)} words: '{sample}...'"
    return False, f"surrounding text has only {len(words)} word(s)"


# ---------------------------------------------------------------------------
# D2 check
# ---------------------------------------------------------------------------

def check_d2(corpus_dir: Path) -> List[Dict]:
    """Run D2 on all pages in corpus_dir."""
    findings: List[Dict] = []

    for page_dir in sorted(corpus_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        meta_path = page_dir / "meta.json"
        html_path = page_dir / "raw.html"
        text_path = page_dir / "text.txt"

        if not meta_path.exists() or not html_path.exists():
            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        url = meta.get("final_url") or meta.get("url", "")
        status = meta.get("status_code", 200)
        if status != 200:
            continue

        html = html_path.read_text(encoding="utf-8", errors="replace")
        visible_text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
        word_count = len([w for w in visible_text.split() if len(w) > 2])

        # D2a: Content-bearing images without alt in prominent positions
        prominent_html = _extract_prominent_html(html)
        imgs = _parse_img_tags(prominent_html)

        for img in imgs:
            # alt attribute is present and non-empty → skip
            if img["alt"] is not None and img["alt"].strip():
                continue

            # alt is absent or empty — check decorative heuristics
            is_dec, dec_reason = _is_decorative(img)
            if is_dec:
                continue

            # Check surrounding text context
            restates, restate_reason = _context_restates_content(img["surrounding_text"])
            if restates:
                continue

            alt_status = "absent" if img["alt"] is None else "empty string"
            findings.append({
                "id": _new_id("D2"),
                "check_id": "D2",
                "page_url": url,
                "root_cause": "representation_gap",
                "evidence": {
                    "type": "content_image_no_alt",
                    "img_src": img["src"],
                    "alt_status": alt_status,
                    "img_class": img["class"],
                    "surrounding_text_snippet": img["surrounding_text"][:150],
                },
                "raw_severity_class": "medium",
                "confidence": 0.75,
                "mechanism": (
                    f"Image '{img['src']}' in a prominent page zone (hero/header/pricing area) "
                    f"has {alt_status} alt text. An AI agent parsing this page's HTML cannot "
                    "extract any text representation of this image's content. If the image "
                    "conveys a price, product name, or key claim, the agent will omit or "
                    "hallucinate that fact."
                ),
                "false_positive_guard": (
                    f"alt is {alt_status}. "
                    f"Decorative filename check: PASS (no match in {sorted(DECORATIVE_FILENAME_KEYWORDS)[:5]}...). "
                    f"Decorative class check: PASS (no match). "
                    f"Dimension check: PASS (width={img['width']}, height={img['height']} — "
                    f"not both ≤{MAX_DECORATIVE_PX}px). "
                    f"Context restatement: FAIL — {restate_reason}."
                ),
                "verification_method": (
                    f"curl -s {url} | grep -oP '<img[^>]*>' | grep -v 'alt=\"[^\"]+\"'"
                ),
            })

        # D2b: Text-light pages with PDF/video embeds and no transcript
        is_text_light = word_count < 100
        if is_text_light:
            has_pdf = bool(re.search(
                r'<(?:embed|object|iframe)[^>]+(?:src|data)=["\'][^"\']*\.pdf["\']',
                html, re.IGNORECASE,
            ))
            has_video = bool(re.search(
                r'<(?:video|iframe)[^>]+(?:src|data)=["\'][^"\']*["\']',
                html, re.IGNORECASE,
            ))
            has_transcript = bool(re.search(
                r'(?:transcript|caption|subtitles?|closed.caption)',
                visible_text, re.IGNORECASE,
            ))

            if (has_pdf or has_video) and not has_transcript:
                embed_type = "PDF" if has_pdf else "video"
                findings.append({
                    "id": _new_id("D2"),
                    "check_id": "D2",
                    "page_url": url,
                    "root_cause": "representation_gap",
                    "evidence": {
                        "type": "text_light_page_with_embed",
                        "embed_type": embed_type,
                        "visible_word_count": word_count,
                        "has_transcript": has_transcript,
                    },
                    "raw_severity_class": "medium",
                    "confidence": 0.70,
                    "mechanism": (
                        f"Page has only {word_count} visible words but embeds a {embed_type} "
                        f"without a text transcript. An AI agent reading this page's text "
                        f"will find almost no content — the {embed_type}'s information is "
                        "entirely inaccessible without a text representation."
                    ),
                    "false_positive_guard": (
                        f"Word count: {word_count} (threshold: 100). "
                        f"{embed_type} embed detected in HTML. "
                        f"Transcript keywords ('transcript', 'caption', 'subtitles') "
                        f"not found in visible text ({word_count} words)."
                    ),
                    "verification_method": (
                        f"curl -s {url} | wc -w ; curl -s {url} | grep -i 'embed\\|video\\|pdf'"
                    ),
                })

    return findings


def main() -> None:
    ap = argparse.ArgumentParser(description="D2 check for machine-readability-audit")
    ap.add_argument("corpus_dir", help="Path to corpus pages directory")
    args = ap.parse_args()

    corpus_dir = Path(args.corpus_dir)
    if not corpus_dir.exists():
        print(f"[check_d2] ERROR: corpus dir not found: {corpus_dir}", file=sys.stderr)
        sys.exit(1)

    findings = check_d2(corpus_dir)
    print(f"[check_d2] D2: {len(findings)} finding(s)", file=sys.stderr)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
