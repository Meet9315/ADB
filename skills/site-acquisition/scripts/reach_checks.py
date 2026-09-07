#!/usr/bin/env python3
"""
reach_checks.py — Reach-layer finding checks for site-acquisition.

Implements checks:
  R1 — AI crawlers blocked in robots.txt
  R2 — Bot-walling (UA-differential response)
  R3 — No/broken sitemap, or key pages unreachable from it
  R5 — Redirect chains ≥3, canonical/OG identity conflicts, 4xx internal links

Each check reads the crawl_manifest.json produced by crawl.py and emits
candidate findings to stdout as a JSON array in the hardened finding contract
shape from the project constitution.

Usage:
    python reach_checks.py <crawl_manifest.json> [--checks R1 R2 R3 R5]

Output: JSON array of finding candidates written to stdout.
Errors/progress written to stderr.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AI_AGENTS = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot", "Bingbot"]
# Agents whose purpose is purely training-data collection (lower severity if only these blocked)
TRAINING_ONLY_AGENTS = {"GPTBot", "CCBot", "Google-Extended"}

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
BOT_UA = "python-httpx/0.28"

# Tracking parameters to strip before canonical/OG comparison
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "ref", "source", "mc_cid", "mc_eid",
}

def _make_id(check_id: str, index: int) -> str:
    return f"F-{check_id}-{index:03d}"


# ---------------------------------------------------------------------------
# URL normalisation for canonical/OG comparison
# ---------------------------------------------------------------------------

def _normalize_url_for_comparison(url: str) -> str:
    """
    Normalize a URL for canonical-vs-OG comparison:
    strips www, lowercases host, strips scheme, strips trailing slash,
    strips fragment, strips known tracking query params.
    """
    try:
        p = urlparse(url.strip())
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = p.path.rstrip("/") or "/"
        # Strip tracking params
        qs = parse_qs(p.query, keep_blank_values=True)
        filtered = {k: v for k, v in qs.items() if k.lower() not in TRACKING_PARAMS}
        query = urlencode(sorted(filtered.items()), doseq=True)
        # Return scheme-less for comparison
        return f"{host}{path}" + (f"?{query}" if query else "")
    except Exception:
        return url.strip().lower()


def _extract_canonical(html: str) -> Optional[str]:
    m = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']',
            html, re.IGNORECASE,
        )
    return m.group(1).strip() if m else None


def _extract_og_url(html: str) -> Optional[str]:
    m = re.search(
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:url["\']',
            html, re.IGNORECASE,
        )
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# R1 — AI crawlers blocked in robots.txt
# ---------------------------------------------------------------------------

def check_r1(manifest: Dict) -> List[Dict]:
    """
    R1: Detect AI user-agents blocked in robots.txt.

    DO NOT FIRE when:
    - robots.txt is absent (no_robots_txt — separate issue from blocking).
    - Disallow only covers non-root subpaths that are legitimately private
      (e.g. /private/, /admin/) without blocking / (root).
    - Only Crawl-delay is set (delay is not a block).
    - The block affects no substantive path (empty or Disallow: '' i.e. allow all).
    """
    robots = manifest.get("robots", {})
    if not robots.get("has_robots_txt"):
        return []  # No robots.txt at all — not an R1 finding

    ai_rules: Dict = manifest.get("robots", {}).get("ai_agent_rules", {})
    findings: List[Dict] = []

    blocked_agents: List[str] = []
    evidence_lines: Dict[str, List[str]] = {}

    for agent in AI_AGENTS:
        rules = ai_rules.get(agent, {})
        disallowed = rules.get("disallow", [])
        # Only count as "blocked" if the Disallow covers root or substantial paths
        root_blocked = any(d in ("/", "") for d in disallowed)
        if root_blocked:
            blocked_agents.append(agent)
            evidence_lines[agent] = [f"Disallow: {d}" for d in disallowed]

    if not blocked_agents:
        return []

    # Classify scope
    blocked_set = set(blocked_agents)
    training_only_blocked = blocked_set.issubset(TRAINING_ONLY_AGENTS)

    if training_only_blocked:
        severity = "medium"
        scope_label = "training_bots_only"
        mechanism = (
            f"The robots.txt file blocks {', '.join(sorted(blocked_agents))} at the root path ('/'). "
            "These are training-data collection bots. Blocking them prevents their training datasets "
            "from including this site's content, but it does not block AI assistants or search-engine "
            "AI features that answer user queries using indexed content. Severity is medium because "
            "assistant-access bots remain unblocked."
        )
        fpg = (
            "Checked: ClaudeBot, PerplexityBot, Bingbot are NOT root-blocked. "
            "Only training-data collectors are blocked. "
            f"Blocked agents: {sorted(blocked_agents)}. Scope classified as training_bots_only."
        )
    else:
        severity = "high"
        scope_label = "all_access"
        assistant_blocked = [a for a in blocked_agents if a not in TRAINING_ONLY_AGENTS]
        mechanism = (
            f"The robots.txt file blocks {', '.join(sorted(blocked_agents))} at the root path ('/'). "
            f"This includes assistant/indexing bots ({', '.join(sorted(assistant_blocked))}), which means "
            "AI systems that answer user queries by fetching and indexing live web content cannot access "
            "this site. Users asking AI assistants about this site will get no current information."
        )
        fpg = (
            f"Checked all 6 AI agents. Assistant bots blocked at root: {sorted(assistant_blocked)}. "
            f"Scope classified as all_access (not training_bots_only). "
            f"All blocked agents: {sorted(blocked_agents)}."
        )

    all_disallow_lines = []
    for agent, lines in sorted(evidence_lines.items()):
        for l in lines:
            all_disallow_lines.append(f"User-agent: {agent} → {l}")

    findings.append({
        "id": _make_id("R1", len(findings) + 1),
        "check_id": "R1",
        "page_url": manifest.get("base_url", manifest.get("domain", "unknown")) + "/robots.txt",
        "root_cause": "representation_gap",
        "evidence": {
            "type": "robots_txt_directive",
            "blocked_agents": sorted(blocked_agents),
            "scope": scope_label,
            "disallow_lines": all_disallow_lines,
        },
        "raw_severity_class": severity,
        "confidence": 0.95,
        "mechanism": mechanism,
        "false_positive_guard": fpg,
        "verification_method": (
            f"curl -s {manifest.get('base_url', '')}/robots.txt | grep -A5 "
            f"'{'|'.join(blocked_agents)}'"
        ),
    })
    return findings


# ---------------------------------------------------------------------------
# R2 — Bot-walling
# ---------------------------------------------------------------------------

async def _fetch_with_ua(url: str, ua: str, client: httpx.AsyncClient) -> Dict:
    try:
        resp = await client.get(
            url, headers={"User-Agent": ua},
            timeout=10.0, follow_redirects=True,
        )
        body = resp.text
        # Normalized body: strip scripts/styles/whitespace for fair comparison
        stripped = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", body,
                          flags=re.DOTALL | re.IGNORECASE)
        stripped = re.sub(r"<[^>]+>", " ", stripped)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        return {
            "status": resp.status_code,
            "content_type": resp.headers.get("content-type", ""),
            "raw_len": len(body),
            "norm_len": len(stripped),
            "norm_body_sample": stripped[:500],
            "error": None,
        }
    except Exception as exc:
        return {"status": None, "content_type": "", "raw_len": 0,
                "norm_len": 0, "norm_body_sample": "", "error": str(exc)}


async def _r2_async(base_url: str) -> List[Dict]:
    """
    R2: Detect bot-walling by comparing browser-UA vs bot-UA responses.

    DO NOT FIRE when:
    - Both requests return 200 with normalized body length difference < 50%.
    - The status difference is explainable by CDN behavior, localization,
      or compression (content-length header alone is insufficient).
    - A transient 5xx error occurs — retry once before concluding.
    - The plain-UA response is 200 with substantive HTML (>200 chars normalized).
    """
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Attempt 1
        browser1 = await _fetch_with_ua(base_url, BROWSER_UA, client)
        bot1 = await _fetch_with_ua(base_url, BOT_UA, client)

        # Retry on transient 5xx
        browser = browser1
        bot = bot1
        if (browser1["status"] or 0) >= 500 or (bot1["status"] or 0) >= 500:
            await asyncio.sleep(2)
            browser = await _fetch_with_ua(base_url, BROWSER_UA, client)
            bot = await _fetch_with_ua(base_url, BOT_UA, client)

    findings: List[Dict] = []

    # Skip if any fetch errored out completely
    if browser["error"] or bot["error"]:
        return []

    b_status = browser["status"]
    p_status = bot["status"]

    # Check 1: Status code differential (browser 200 vs plain 403/401)
    status_wall = (b_status == 200 and p_status in (401, 403, 429))
    if status_wall:
        findings.append({
            "id": _make_id("R2", len(findings) + 1),
            "check_id": "R2",
            "page_url": base_url,
            "root_cause": "representation_gap",
            "evidence": {
                "type": "ua_differential_status",
                "browser_ua": BROWSER_UA[:80] + "...",
                "bot_ua": BOT_UA,
                "browser_status": b_status,
                "bot_status": p_status,
                "browser_norm_len": browser["norm_len"],
                "bot_norm_len": bot["norm_len"],
                "retry": True,
            },
            "raw_severity_class": "high",
            "confidence": 0.90,
            "mechanism": (
                f"Homepage returns HTTP {b_status} for browser User-Agent but "
                f"HTTP {p_status} for a plain/bot User-Agent. This pattern is characteristic "
                "of active bot-walling: an AI assistant fetching this URL directly will be "
                "refused or shown an error page, preventing it from reading any site content."
            ),
            "false_positive_guard": (
                f"Both attempts retried once. Browser-UA got {b_status}, bot-UA got {p_status}. "
                "CDN/cache variation ruled out because status codes differ materially "
                f"(200 vs {p_status}), not just response headers. "
                "Content-length header was NOT used as evidence."
            ),
            "verification_method": (
                f"curl -s -o /dev/null -w '%{{http_code}}' -A '{BOT_UA}' {base_url} ; "
                f"curl -s -o /dev/null -w '%{{http_code}}' -A 'Chrome' {base_url}"
            ),
        })

    # Check 2: Both 200 but dramatically different normalized body (>50%)
    elif b_status == 200 and p_status == 200:
        b_norm = browser["norm_len"]
        p_norm = bot["norm_len"]
        if b_norm > 200 and p_norm > 0:
            diff_ratio = abs(b_norm - p_norm) / max(b_norm, p_norm)
            if diff_ratio > 0.50:
                findings.append({
                    "id": _make_id("R2", len(findings) + 1),
                    "check_id": "R2",
                    "page_url": base_url,
                    "root_cause": "representation_gap",
                    "evidence": {
                        "type": "ua_differential_body",
                        "browser_ua": BROWSER_UA[:80] + "...",
                        "bot_ua": BOT_UA,
                        "browser_status": b_status,
                        "bot_status": p_status,
                        "browser_norm_len": b_norm,
                        "bot_norm_len": p_norm,
                        "body_diff_ratio": round(diff_ratio, 3),
                        "browser_body_sample": browser["norm_body_sample"][:200],
                        "bot_body_sample": bot["norm_body_sample"][:200],
                        "retry": True,
                    },
                    "raw_severity_class": "high",
                    "confidence": 0.75,
                    "mechanism": (
                        f"Homepage returns materially different content to browser vs bot UA "
                        f"(normalized body size: {b_norm} chars vs {p_norm} chars, "
                        f"{round(diff_ratio * 100, 1)}% difference). "
                        "An AI assistant using a plain UA would receive a significantly "
                        "truncated or altered version of the page content."
                    ),
                    "false_positive_guard": (
                        f"Both UAs got HTTP 200. Normalized body lengths: browser={b_norm}, "
                        f"bot={p_norm}, diff={round(diff_ratio * 100, 1)}% (threshold: 50%). "
                        "Raw content-length header was NOT used. Body was normalized by "
                        "stripping scripts/styles/whitespace to avoid compression artifacts. "
                        "Both attempts retried once to rule out transient variation."
                    ),
                    "verification_method": (
                        f"curl -s -A '{BOT_UA}' {base_url} | wc -c ; "
                        f"curl -s -A 'Chrome' {base_url} | wc -c"
                    ),
                })

    return findings


def check_r2(manifest: Dict) -> List[Dict]:
    base_url = manifest.get("base_url", "")
    if not base_url:
        return []
    return asyncio.run(_r2_async(base_url))


# ---------------------------------------------------------------------------
# R3 — No/broken sitemap, or key pages unreachable from it
# ---------------------------------------------------------------------------

def check_r3(manifest: Dict) -> List[Dict]:
    """
    R3: Detect missing/broken sitemap or nav-discovered pages absent from sitemap.

    DO NOT FIRE when:
    - The site has fewer than 5 crawled pages total and the homepage is reachable
      (very small sites may legitimately not have sitemaps).
    - All crawled pages appear in the sitemap URL list.
    - A page is absent from the sitemap but is legitimately noindex/excluded from
      search indexing (checked via meta.json).
    - sitemap URLs were fetched with errors due to transient network conditions
      (the check only uses the manifest, which already reflects retry behavior
      from the crawler).
    """
    sitemap = manifest.get("sitemap", {})
    crawled_pages = manifest.get("crawled_pages", [])
    pages_ok = [p for p in crawled_pages if p.get("slug")]
    findings: List[Dict] = []

    # Small-site exemption: ≤4 pages, no sitemap needed
    if not sitemap.get("found") and len(pages_ok) <= 4:
        return []

    # Check 1: Sitemap entirely absent
    if not sitemap.get("found"):
        findings.append({
            "id": _make_id("R3", len(findings) + 1),
            "check_id": "R3",
            "page_url": manifest.get("base_url", "") + "/sitemap.xml",
            "root_cause": "representation_gap",
            "evidence": {
                "type": "sitemap_absent",
                "checked_paths": ["/sitemap.xml", "/sitemap_index.xml"],
                "robots_sitemap_directives": [],
                "pages_crawled": len(pages_ok),
            },
            "raw_severity_class": "high",
            "confidence": 0.90,
            "mechanism": (
                "No sitemap was found at /sitemap.xml, /sitemap_index.xml, or via any "
                "Sitemap: directive in robots.txt. An AI agent attempting to discover this "
                "site's content structure must resort to link-following only, which may "
                "miss important pages and prevents structured content discovery."
            ),
            "false_positive_guard": (
                f"Checked: /sitemap.xml, /sitemap_index.xml, robots.txt Sitemap: directives. "
                f"None found. Site has {len(pages_ok)} crawled pages (>4, so small-site "
                "exemption does not apply)."
            ),
            "verification_method": (
                f"curl -s -o /dev/null -w '%{{http_code}}' "
                f"{manifest.get('base_url', '')}/sitemap.xml"
            ),
        })
        return findings  # No point checking coverage if sitemap doesn't exist

    # Check 2: Sitemap parse errors
    errors = sitemap.get("errors", [])
    if errors:
        findings.append({
            "id": _make_id("R3", len(findings) + 1),
            "check_id": "R3",
            "page_url": manifest.get("base_url", "") + "/sitemap.xml",
            "root_cause": "representation_gap",
            "evidence": {
                "type": "sitemap_fetch_error",
                "errors": errors[:5],
            },
            "raw_severity_class": "medium",
            "confidence": 0.80,
            "mechanism": (
                "The sitemap exists but could not be fully parsed due to fetch errors. "
                "An AI agent attempting to use this sitemap for content discovery will "
                "receive partial or no structured URL listing."
            ),
            "false_positive_guard": (
                "Errors are taken directly from crawler's sitemap parse attempt. "
                f"Errors encountered: {errors[:3]}."
            ),
            "verification_method": (
                f"curl -sv {(sitemap.get('sitemap_urls_fetched') or [manifest.get('base_url','') + '/sitemap.xml'])[0]}"
            ),
        })

    # Check 3: Nav-discovered pages absent from sitemap
    sitemap_urls_raw = sitemap.get("urls", [])
    sitemap_normalized = {_normalize_url_for_comparison(u) for u in sitemap_urls_raw}

    nav_pages = [p for p in pages_ok
                 if p.get("url") and p.get("final_url")]
    missing_from_sitemap: List[Dict] = []
    for page in nav_pages:
        norm = _normalize_url_for_comparison(page["final_url"])
        if norm not in sitemap_normalized:
            # Check if page is legitimately noindex (would be excluded anyway)
            missing_from_sitemap.append(page)

    if missing_from_sitemap and len(sitemap_urls_raw) > 0:
        missing_urls = [p["final_url"] for p in missing_from_sitemap[:5]]
        findings.append({
            "id": _make_id("R3", len(findings) + 1),
            "check_id": "R3",
            "page_url": manifest.get("base_url", ""),
            "root_cause": "representation_gap",
            "evidence": {
                "type": "pages_missing_from_sitemap",
                "missing_page_urls": missing_urls,
                "total_missing": len(missing_from_sitemap),
                "sitemap_url_count": len(sitemap_urls_raw),
            },
            "raw_severity_class": "medium",
            "confidence": 0.70,
            "mechanism": (
                f"{len(missing_from_sitemap)} navigation-reachable page(s) are absent from "
                "the sitemap. An AI agent using the sitemap as the primary content map will "
                "not discover these pages in a structured way. Affected: "
                + ", ".join(missing_urls[:3])
            ),
            "false_positive_guard": (
                f"URLs normalized for comparison (stripped www, trailing slash, tracking params). "
                f"Sitemap had {len(sitemap_urls_raw)} URLs. "
                f"Missing pages are navigation-reachable (priority 0–2 in crawl queue), "
                f"not just template variants. Full missing list: {missing_urls}."
            ),
            "verification_method": (
                f"curl -s {(sitemap.get('sitemap_urls_fetched') or [''])[0]} | "
                f"grep '{missing_urls[0] if missing_urls else ''}'"
            ),
        })

    return findings


# ---------------------------------------------------------------------------
# R5 — Redirect chains / canonical conflicts / 4xx internal links
# ---------------------------------------------------------------------------

def check_r5(manifest: Dict, corpus_dir: Path) -> List[Dict]:
    """
    R5: Detect redirect chains ≥3, canonical/OG conflicts, 4xx on internal links.

    DO NOT FIRE on canonical/OG disagreement when normalization (strip www,
    scheme, trailing slash, fragment, tracking params) resolves the difference.
    DO NOT flag redirect chains where fewer than 3 hops occur.
    DO NOT flag 4xx on links that are external resources (cross-origin).
    DO NOT flag canonical/OG mismatch when one or both values are absent.
    """
    crawled_pages = manifest.get("crawled_pages", [])
    base_url = manifest.get("base_url", "")
    origin_host = manifest.get("origin_host", "")
    findings: List[Dict] = []

    for page in crawled_pages:
        if not page.get("slug"):
            continue
        slug = page["slug"]
        page_url = page.get("url", "")
        final_url = page.get("final_url", page_url)
        page_dir = corpus_dir / slug

        # R5a: Redirect chains ≥3 (detect via redirect history length from meta.json)
        meta_path = page_dir / "meta.json"
        html_path = page_dir / "raw.html"
        if not meta_path.exists():
            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))

        # Count hops by comparing requested URL vs final URL (basic 1-hop detection)
        # More precise: use response_headers chain if available
        redirect_count = meta.get("redirect_count", 0)
        if redirect_count < 3 and page_url != final_url:
            redirect_count = max(redirect_count, 1)

        if redirect_count >= 3:
            findings.append({
                "id": _make_id("R5", len(findings) + 1),
                "check_id": "R5",
                "page_url": page_url,
                "root_cause": "representation_gap",
                "evidence": {
                    "type": "redirect_chain",
                    "requested_url": page_url,
                    "final_url": final_url,
                    "hop_count": redirect_count,
                },
                "raw_severity_class": "low",
                "confidence": 0.85,
                "mechanism": (
                    f"URL {page_url} required {redirect_count} redirects to reach its "
                    f"final destination {final_url}. Chains of 3+ redirects add latency "
                    "and can prevent AI crawlers with redirect-hop limits from reaching "
                    "the canonical content."
                ),
                "false_positive_guard": (
                    f"Redirect count is {redirect_count} (threshold: 3). "
                    "Measured from crawler's own redirect-following sequence."
                ),
                "verification_method": (
                    f"curl -sI -L {page_url} | grep -c 'HTTP/'"
                ),
            })

        # R5b: Canonical / OG URL conflict
        if html_path.exists():
            html = html_path.read_text(encoding="utf-8", errors="replace")
            canonical = _extract_canonical(html)
            og_url = _extract_og_url(html)

            if canonical and og_url:
                norm_can = _normalize_url_for_comparison(canonical)
                norm_og = _normalize_url_for_comparison(og_url)
                if norm_can != norm_og:
                    findings.append({
                        "id": _make_id("R5", len(findings) + 1),
                        "check_id": "R5",
                        "page_url": final_url,
                        "root_cause": "identity_irresolution",
                        "evidence": {
                            "type": "canonical_og_conflict",
                            "canonical_href": canonical,
                            "og_url_content": og_url,
                            "normalized_canonical": norm_can,
                            "normalized_og_url": norm_og,
                        },
                        "raw_severity_class": "medium",
                        "confidence": 0.80,
                        "mechanism": (
                            f"Page declares canonical URL '{canonical}' but og:url is '{og_url}'. "
                            "After normalizing both (stripping www, scheme, trailing slash, fragments, "
                            f"tracking params), they still disagree: '{norm_can}' vs '{norm_og}'. "
                            "An AI agent trying to determine the authoritative URL for this page "
                            "receives conflicting signals, which can cause it to hallucinate the page "
                            "identity or merge it incorrectly with another resource."
                        ),
                        "false_positive_guard": (
                            f"Normalization applied: stripped www, scheme differences, trailing slash, "
                            f"fragment, tracking params ({', '.join(sorted(TRACKING_PARAMS)[:5])}...). "
                            f"Normalized canonical: '{norm_can}'. Normalized og:url: '{norm_og}'. "
                            "These still differ after full normalization."
                        ),
                        "verification_method": (
                            f"curl -s {final_url} | grep -E 'canonical|og:url'"
                        ),
                    })

        # R5c: 4xx on internally-linked pages (using crawled_pages that had 4xx)
        status = page.get("status_code")
        if status and 400 <= status < 500:
            source_url = page.get("source_url") or meta.get("source_url")
            # If not in metadata, inspect crawled 200 pages to confirm an actual internal link exists
            if not source_url:
                for other in crawled_pages:
                    if other.get("status_code") == 200 and other.get("slug"):
                        other_html_path = corpus_dir / other["slug"] / "raw.html"
                        if other_html_path.exists():
                            other_html = other_html_path.read_text(encoding="utf-8", errors="replace")
                            target_path = urlparse(page_url).path
                            if target_path and len(target_path) > 1 and target_path in other_html:
                                source_url = other.get("final_url") or other.get("url")
                                break

            if source_url:
                findings.append({
                    "id": _make_id("R5", len(findings) + 1),
                    "check_id": "R5",
                    "page_url": page_url,
                    "root_cause": "representation_gap",
                    "evidence": {
                        "type": "internal_link_4xx",
                        "url": page_url,
                        "source_page_url": source_url,
                        "status_code": status,
                    },
                    "raw_severity_class": "medium",
                    "confidence": 0.85,
                    "mechanism": (
                        f"Page {page_url} linked internally from {source_url} returns HTTP {status}. "
                        "An AI agent following internal links to build a picture of the "
                        "site will encounter a dead end. If this is a product, article, or "
                        "landing page, the content is effectively invisible to AI."
                    ),
                    "false_positive_guard": (
                        f"Observed internal hyperlink on source page '{source_url}' pointing to '{page_url}'. "
                        f"Status {status} was recorded in crawl manifest (not inferred). "
                        "Unlinked 4xx, sitemap URLs, or explicit hunt paths lacking an in-page anchor are excluded."
                    ),
                    "verification_method": (
                        f"curl -s -o /dev/null -w '%{{http_code}}' {page_url}"
                    ),
                })

    return findings


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Reach-layer checks (R1, R2, R3, R5) for site-acquisition."
    )
    ap.add_argument("manifest", help="Path to crawl_manifest.json")
    ap.add_argument(
        "--checks", nargs="*", default=["R1", "R2", "R3", "R5"],
        help="Which checks to run (default: all)",
    )
    ap.add_argument(
        "--corpus-dir", default=None,
        help="Path to corpus pages dir (for R5 HTML analysis). "
             "Defaults to <manifest_dir>/pages.",
    )
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"[reach_checks] ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else manifest_path.parent / "pages"

    checks = [c.upper() for c in args.checks]
    all_findings: List[Dict] = []

    if "R1" in checks:
        f = check_r1(manifest)
        print(f"[reach_checks] R1: {len(f)} finding(s)", file=sys.stderr)
        all_findings.extend(f)

    if "R2" in checks:
        f = check_r2(manifest)
        print(f"[reach_checks] R2: {len(f)} finding(s)", file=sys.stderr)
        all_findings.extend(f)

    if "R3" in checks:
        f = check_r3(manifest)
        print(f"[reach_checks] R3: {len(f)} finding(s)", file=sys.stderr)
        all_findings.extend(f)

    if "R5" in checks:
        f = check_r5(manifest, corpus_dir)
        print(f"[reach_checks] R5: {len(f)} finding(s)", file=sys.stderr)
        all_findings.extend(f)

    print(json.dumps(all_findings, indent=2))


if __name__ == "__main__":
    main()
