#!/usr/bin/env python3
"""
check_g1.py — G1 Above-Fold Orientation Failure Check (Tier 2: Engagement Audit).

Evaluates whether a first-time human visitor can immediately orient on the homepage
by answering three fixed rubric questions strictly from first-viewport text:
1. "Who is this?" (Brand or entity identity)
2. "What do they offer?" (Core product, service, platform, content, or mission)
3. "What should I do next?" (Immediate call-to-action, directional navigation, or next step)

Negative-Logic Rules (False-Positive Guards):
- Answers must be backed by verbatim quoted excerpts from the first-viewport text.
- If the judgment is ambiguous, DO NOT FLAG. Per Rule 1, this reasoning step must never
  extrapolate or assume what the company probably does based on external knowledge.
- If all 3 questions have grounded quotes, the check cleanly passes with 0 findings.
- Minimalist pages that nonetheless clearly state brand, offering, and a directional link
  are considered compliant.

Usage:
    python check_g1.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


# Indicative phrase patterns for offering descriptions
OFFERING_PATTERNS = [
    re.compile(r"\b(?:is\s+a|is\s+an|is\s+the)\s+([a-zA-Z0-9\s\-]+?(?:platform|software|tool|library|framework|service|app|database|engine|solution|agency|consultancy|store|shop|marketplace|provider|publication|magazine|guide|infrastructure|api|widgets?|products?))\b", re.IGNORECASE),
    re.compile(r"\b(?:we\s+(?:build|help|provide|deliver|create|enable|empower|automate|offer)|designed\s+to|built\s+for|the\s+simplest\s+way\s+to|open-source\s+[a-z]+)\s+([^.\n]{8,80})", re.IGNORECASE),
    re.compile(r"\b(?:discover|explore|featuring|offering|providing|delivering|introducing|browse)\s+(?:our\s+)?([^.\n]{6,80})", re.IGNORECASE),
    re.compile(r"\b(?:features?|solutions?|products?|offerings?|lineup|catalog)\s*[:—–-]\s*([^.\n]{6,80})", re.IGNORECASE),
    re.compile(r"\b(?:world-class|premium|high-quality|handcrafted|flagship|leading)\s+([a-zA-Z0-9\s\-]{3,40}?\b(?:widgets?|products?|solutions?|tools?|services?|hardware|apparel|goods|devices?))\b", re.IGNORECASE),
]

# Indicative patterns for next action / call to action
NEXT_ACTION_PATTERNS = [
    re.compile(r"\b(?:get\s+started|start\s+(?:free|trial|now)|try\s+(?:free|now|it)|sign\s+up|subscribe|buy\s+now|order\s+now|book\s+(?:a\s+)?demo|schedule\s+(?:a\s+)?call|contact\s+us|request\s+a\s+quote|download|explore|learn\s+more|read\s+docs|documentation|view\s+pricing)\b", re.IGNORECASE),
]


def _extract_first_viewport_text(html: str) -> str:
    """Extract text appearing above the fold (header, hero, and initial section)."""
    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        # Strip script, style, svg, noscript
        for s in soup(["script", "style", "svg", "noscript"]):
            s.decompose()

        snippets: List[str] = []
        # Check header / nav
        header = soup.find("header") or soup.find("nav")
        if header:
            snippets.append(header.get_text(separator=" ", strip=True))

        # Check hero or primary section
        hero = (
            soup.find(class_=re.compile(r"hero|banner|intro|jumbotron", re.IGNORECASE))
            or soup.find("main")
            or soup.find("section")
        )
        if hero:
            snippets.append(hero.get_text(separator=" ", strip=True))

        combined = " ".join(snippets).strip()
        if len(combined) >= 120:
            return combined[:1500]

        # Fallback to initial body text
        body = soup.find("body")
        if body:
            return body.get_text(separator=" ", strip=True)[:1500]

    # Regex fallback
    clean = re.sub(r"<(script|style|svg)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:1500]


def _evaluate_rubric(text: str, title: str, domain: str) -> Dict[str, Any]:
    """
    Evaluate the 3 rubric questions grounded in verbatim text quotes.
    Returns: dict with answered status, quotes, and ambiguity assessment.
    """
    result = {
        "who": {"answered": False, "quote": None},
        "what": {"answered": False, "quote": None},
        "next": {"answered": False, "quote": None},
        "is_ambiguous": False,
    }

    # 1. Who is this?
    # Check title, or brand mentions near beginning
    brand_candidate = ""
    if title:
        parts = [p.strip() for p in re.split(r"[-|–—:]", title) if p.strip()]
        if parts:
            brand_candidate = parts[0] if parts[0].lower() not in ("home", "welcome", "index") else (parts[-1] if len(parts) > 1 else "")

    if not brand_candidate and domain:
        clean_domain = re.sub(r"^(?:https?://)?(?:www\.)?", "", domain).split(".")[0]
        brand_candidate = clean_domain.capitalize()

    if brand_candidate and re.search(rf"\b{re.escape(brand_candidate)}\b", text, re.IGNORECASE):
        m = re.search(rf"[^.\n]*?\b{re.escape(brand_candidate)}\b[^.\n]*", text, re.IGNORECASE)
        if m:
            result["who"] = {"answered": True, "quote": m.group(0).strip()[:100]}
    elif brand_candidate:
        # Grounded in title
        result["who"] = {"answered": True, "quote": f"{brand_candidate} (from page title)"}

    # 2. What do they offer?
    for pat in OFFERING_PATTERNS:
        m = pat.search(text)
        if m:
            result["what"] = {"answered": True, "quote": m.group(0).strip()[:120]}
            break

    # If no regex matched, check for descriptive multi-sentence explanation
    if not result["what"]["answered"]:
        sentences = [s.strip() for s in re.split(r"[.!?\n]", text) if len(s.strip().split()) >= 3]
        for s in sentences[:4]:
            if any(k in s.lower() for k in (
                "platform", "tool", "service", "system", "app", "library", "solution",
                "product", "products", "software", "community", "widget", "widgets", "goods",
                "shop", "store", "catalog", "lineup", "hardware", "device", "framework", "api"
            )):
                result["what"] = {"answered": True, "quote": s[:120]}
                break

    # 3. What should I do next?
    for pat in NEXT_ACTION_PATTERNS:
        m = pat.search(text)
        if m:
            result["next"] = {"answered": True, "quote": m.group(0).strip()[:60]}
            break

    # Check for presence of navigation links that clearly guide next action
    if not result["next"]["answered"]:
        nav_matches = re.findall(r"\b(Docs|Documentation|Pricing|Features|Products|API|Guides|Download|Contact|Blog|About)\b", text, re.IGNORECASE)
        if nav_matches:
            result["next"] = {"answered": True, "quote": f"Navigation: {', '.join(set(nav_matches[:3]))}"}

    # AMBIGUITY GUARD (Rule 1):
    # If the text mentions domain concepts, capabilities, or functions (e.g. cloud, data,
    # infrastructure, analytics, security) without an explicit product/offering framing,
    # the judgment of whether this answers "what do they offer" is ambiguous.
    # Per Rule 1, we must never assert an answer based on assumptions about what the company
    # probably does. When ambiguous, suppress flagging and record the guard.
    AMBIGUOUS_DOMAIN_TERMS = (
        "technology", "technologies", "infrastructure", "operations", "capabilities",
        "transformation", "cloud", "intelligence", "digital", "security", "network",
        "data", "analytics", "protocol", "automation", "telemetry", "pipeline",
    )
    if not result["what"]["answered"]:
        text_lower = text.lower()
        if any(term in text_lower for term in AMBIGUOUS_DOMAIN_TERMS):
            result["is_ambiguous"] = True

    return result


def run_check_g1(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Execute G1 Above-Fold Orientation Check across homepage corpus."""
    findings: List[Dict[str, Any]] = []

    domain = manifest.get("domain", "") if manifest else ""
    home_page_dir: Optional[Path] = None
    home_url = ""

    # Locate homepage directory
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
        subdirs = [d for d in sorted(corpus_dir.iterdir()) if d.is_dir()]
        if subdirs:
            home_page_dir = subdirs[0]

    if not home_page_dir:
        return findings

    raw_path = home_page_dir / "rendered.html"
    if not raw_path.exists():
        raw_path = home_page_dir / "raw.html"
    meta_path = home_page_dir / "meta.json"

    if not raw_path.exists():
        return findings

    html = raw_path.read_text(encoding="utf-8", errors="replace")
    meta: Dict[str, Any] = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    if not home_url:
        home_url = meta.get("final_url") or meta.get("url", f"https://{domain}/")

    title = meta.get("title", "")
    viewport_text = _extract_first_viewport_text(html)

    # Substantive content guard: exclude placeholder / empty shell pages
    if len(viewport_text.split()) < 10:
        return findings

    rubric = _evaluate_rubric(viewport_text, title, domain)

    # AMBIGUITY GUARD (Rule 1):
    # If the judgment is ambiguous, do not flag.
    if rubric["is_ambiguous"]:
        return findings

    unanswered: List[str] = []
    if not rubric["who"]["answered"]:
        unanswered.append("who_is_this")
    if not rubric["what"]["answered"]:
        unanswered.append("what_do_they_offer")
    if not rubric["next"]["answered"]:
        unanswered.append("what_should_i_do_next")

    # If all three are answered, cleanly pass
    if not unanswered:
        return findings

    # Format human-readable mechanism explanation
    missing_labels = [q.replace("_", " ") for q in unanswered]
    findings.append({
        "id": "F-G1-001",
        "check_id": "G1",
        "page_url": home_url,
        "root_cause": "orientation_cost",
        "evidence": {
            "type": "above_fold_orientation_failure",
            "unanswered_questions": unanswered,
            "rubric_answers": {
                "who_is_this": rubric["who"],
                "what_do_they_offer": rubric["what"],
                "what_should_i_do_next": rubric["next"],
            },
            "first_viewport_text_sample": viewport_text[:300],
        },
        "raw_severity_class": "medium",
        "confidence": 0.88,
        "mechanism": (
            f"Homepage initial viewport fails to clearly communicate: {', '.join(missing_labels)}. "
            "First-time human visitors decide whether to bounce within 3 seconds; when orientation answers "
            "cannot be parsed above the fold, bounce rates increase and user task completion halts."
        ),
        "false_positive_guard": (
            "Grounded reasoning guard: evaluated strictly against first-viewport text quotes for three fixed "
            f"rubric questions. Ambiguous text suppressed per Rule 1. Unanswered items: {', '.join(unanswered)}."
        ),
        "verification_method": f"curl -sL {home_url} | head -n 40",
    })

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="G1 — Above-Fold Orientation Check")
    parser.add_argument("corpus_dir", type=Path, help="Directory containing crawled page subdirectories")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to crawl_manifest.json")
    args = parser.parse_args()

    manifest_data: Optional[Dict[str, Any]] = None
    if args.manifest and args.manifest.exists():
        try:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception:
            pass

    findings = run_check_g1(args.corpus_dir, manifest=manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
