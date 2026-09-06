#!/usr/bin/env python3
"""
crawl.py — Bounded, robots-compliant website crawler for site-acquisition.

Usage:
    python crawl.py <domain> [--output-dir <path>] [--budget-soft 240] [--budget-hard 300]

Behaviour:
  - Respects robots.txt (honours Disallow for our user-agent and *).
    Separately records rules for AI agents: GPTBot, ClaudeBot,
    PerplexityBot, Google-Extended, CCBot, Bingbot.
  - Bounded crawl: ≤25 pages, concurrency 6, 10 s timeout per page.
  - Priority queue: homepage → robots.txt/sitemap → nav links → one
    exemplar per URL-path template → explicit /about /contact /pricing.
  - Writes per-page: raw.html, text.txt, meta.json to corpus/<slug>/.
  - Writes crawl_manifest.json with robots rules, sitemap results,
    budget snapshot, and skip log.

Safety:
  Read-only.  No authenticated/destructive/rate-abusing actions.
  Rate-limited by 10 s timeout + max 6 concurrent connections.
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
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from selectolax.parser import HTMLParser

# -- resolve lib/ (sibling of scripts/) ------------------------------------
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "lib"))
from budget import BudgetTracker  # noqa: E402

# -- constants -------------------------------------------------------------
MAX_PAGES = 25
CONCURRENCY = 6
PAGE_TIMEOUT_S = 10.0
USER_AGENT = "AuditBot/1.0 (+https://agentskills.io)"

AI_AGENTS = ["GPTBot", "ClaudeBot", "PerplexityBot",
             "Google-Extended", "CCBot", "Bingbot"]

# Priority levels (lower = fetched first)
PRI_HOME = 0
PRI_SITEMAP = 1
PRI_NAV = 2
PRI_TEMPLATE = 3
PRI_EXPLICIT = 4

EXPLICIT_PATHS = ["/about", "/about-us", "/contact", "/contact-us", "/pricing"]

# Stop enqueueing when less than this many seconds remain before soft deadline.
SOFT_MARGIN_S = 30.0


# ── URL utilities ─────────────────────────────────────────────────────────

def normalise_url(href: str, base: str) -> Optional[str]:
    """Resolve *href* against *base*, normalise, drop non-http(s)."""
    try:
        parsed = urlparse(urljoin(base, href))
    except Exception:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def same_domain(url: str, origin_host: str) -> bool:
    host = urlparse(url).netloc.lower()
    o = origin_host.lower()
    return host == o or host == f"www.{o}" or f"www.{host}" == o


def url_path_template(url: str) -> str:
    """Collapse numeric / uuid segments to produce a path template."""
    path = urlparse(url).path
    path = re.sub(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{uuid}", path)
    path = re.sub(r"/\d+", "/{id}", path)
    return path


# ── Robots handling ───────────────────────────────────────────────────────

def _parse_robots_txt(raw: str) -> Dict:
    """Parse robots.txt into {agent: {disallow: [], allow: [], crawl_delay: N}}."""
    rules: Dict = {}
    current_agents: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key == "user-agent":
            current_agents = [val]
            if val not in rules:
                rules[val] = {"disallow": [], "allow": [], "crawl_delay": None}
        elif key == "disallow" and val:
            for a in current_agents:
                rules.setdefault(a, {"disallow": [], "allow": [], "crawl_delay": None})
                rules[a]["disallow"].append(val)
        elif key == "allow" and val:
            for a in current_agents:
                rules.setdefault(a, {"disallow": [], "allow": [], "crawl_delay": None})
                rules[a]["allow"].append(val)
        elif key == "crawl-delay":
            for a in current_agents:
                rules.setdefault(a, {"disallow": [], "allow": [], "crawl_delay": None})
                try:
                    rules[a]["crawl_delay"] = float(val)
                except ValueError:
                    pass
    return rules


def _is_path_disallowed(path: str, rules_for_agent: Dict) -> bool:
    """Check if *path* is disallowed by the parsed rules for a single agent."""
    # Allow rules take precedence over Disallow for the same prefix (simple model).
    for allowed in rules_for_agent.get("allow", []):
        if path.startswith(allowed):
            return False
    for disallowed in rules_for_agent.get("disallow", []):
        if path.startswith(disallowed):
            return True
    return False


def is_url_allowed(url: str, all_rules: Dict) -> bool:
    """Return True if our user-agent may fetch *url*."""
    path = urlparse(url).path or "/"
    # Check agent-specific rules first, then wildcard
    for agent_key in (USER_AGENT, "AuditBot", "*"):
        if agent_key in all_rules:
            if _is_path_disallowed(path, all_rules[agent_key]):
                return False
    return True


async def fetch_robots_txt(
    base_url: str, client: httpx.AsyncClient, budget: BudgetTracker,
) -> Tuple[str, Dict]:
    """Fetch robots.txt asynchronously, bounded by hard budget remaining."""
    robots_url = base_url.rstrip("/") + "/robots.txt"
    raw = ""
    timeout = min(PAGE_TIMEOUT_S, max(1.0, budget.remaining_hard()))
    try:
        r = await client.get(robots_url, timeout=timeout, follow_redirects=True)
        if r.status_code == 200:
            raw = r.text
    except Exception:
        pass
    return raw, _parse_robots_txt(raw)


# ── Sitemap parsing ──────────────────────────────────────────────────────

async def parse_sitemaps(
    base_url: str, robots_raw: str, client: httpx.AsyncClient,
) -> Dict:
    """Discover and parse sitemaps.  Returns structured results."""
    result: Dict = {
        "found": False, "urls": [], "sitemap_urls_fetched": [],
        "errors": [], "source_directives": [],
    }
    candidates: List[str] = []

    # From robots.txt Sitemap: directives
    for line in robots_raw.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            sm_url = stripped.split(":", 1)[1].strip()
            if sm_url:
                candidates.append(sm_url)
                result["source_directives"].append(sm_url)

    # Fallback conventional paths
    for p in ("/sitemap.xml", "/sitemap_index.xml"):
        candidates.append(base_url.rstrip("/") + p)

    seen: Set[str] = set()
    page_urls: Set[str] = set()

    async def _fetch_sm(sm_url: str, depth: int = 0) -> None:
        if sm_url in seen or depth > 2:
            return
        seen.add(sm_url)
        try:
            resp = await client.get(sm_url, timeout=10)
            if resp.status_code != 200:
                result["errors"].append(f"{sm_url}: HTTP {resp.status_code}")
                return
            result["found"] = True
            result["sitemap_urls_fetched"].append(sm_url)
            text = resp.text
            if "<sitemapindex" in text.lower():
                for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", text, re.S):
                    if depth < 1:
                        await _fetch_sm(loc.strip(), depth + 1)
            else:
                for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", text, re.S):
                    page_urls.add(loc.strip())
                    if len(page_urls) >= 500:
                        return
        except Exception as exc:
            result["errors"].append(f"{sm_url}: {type(exc).__name__}: {exc}")

    for sm in candidates:
        if len(page_urls) >= 500:
            break
        await _fetch_sm(sm)

    result["urls"] = list(page_urls)
    return result


# ── HTML extraction ──────────────────────────────────────────────────────

def extract_nav_links(html: str, base_url: str) -> List[str]:
    """Extract hrefs from nav/header regions, falling back to all <a> tags."""
    tree = HTMLParser(html)
    links: List[str] = []
    for sel in ("nav a", "header a", '[role="navigation"] a',
                '[class*="nav"] a', '[class*="menu"] a'):
        for node in tree.css(sel):
            href = node.attributes.get("href", "")
            if href:
                n = normalise_url(href, base_url)
                if n:
                    links.append(n)
    if not links:
        for node in tree.css("a"):
            href = node.attributes.get("href", "")
            if href:
                n = normalise_url(href, base_url)
                if n:
                    links.append(n)
    return links


def extract_text(html: str) -> str:
    tree = HTMLParser(html)
    for tag in tree.css("script, style, noscript, svg"):
        tag.decompose()
    raw = tree.body.text(separator="\n") if tree.body else ""
    return re.sub(r"\n{3,}", "\n\n", raw).strip()


def extract_headings(html: str) -> Dict:
    tree = HTMLParser(html)
    return {
        level: [n.text(strip=True) for n in tree.css(level)]
        for level in ("h1", "h2", "h3")
    }


# ── Page fetch ───────────────────────────────────────────────────────────

async def fetch_page(
    url: str, client: httpx.AsyncClient, sem: asyncio.Semaphore,
) -> Dict:
    async with sem:
        t0 = time.monotonic()
        try:
            resp = await client.get(url, timeout=PAGE_TIMEOUT_S,
                                    follow_redirects=True)
            elapsed = round(time.monotonic() - t0, 3)
            ct = resp.headers.get("content-type", "")
            html = resp.text if "html" in ct.lower() else ""
            return {
                "url": url, "final_url": str(resp.url),
                "status_code": resp.status_code, "content_type": ct,
                "html": html, "headers": dict(resp.headers),
                "elapsed_s": elapsed, "error": None,
            }
        except Exception as exc:
            return {
                "url": url, "final_url": url,
                "status_code": None, "content_type": "",
                "html": "", "headers": {},
                "elapsed_s": round(time.monotonic() - t0, 3),
                "error": f"{type(exc).__name__}: {exc}",
            }


# ── Corpus persistence ───────────────────────────────────────────────────

def _page_slug(url: str) -> str:
    digest = hashlib.md5(url.encode()).hexdigest()[:8]
    path = urlparse(url).path.strip("/").replace("/", "_") or "home"
    slug = re.sub(r"[^\w\-]", "_", path)[:40]
    return f"{slug}_{digest}"


def save_page(corpus_dir: Path, result: Dict) -> Optional[str]:
    """Write raw HTML, text, and meta for one page.  Returns slug or None."""
    if not result["html"]:
        return None
    slug = _page_slug(result["url"])
    d = corpus_dir / slug
    d.mkdir(parents=True, exist_ok=True)

    (d / "raw.html").write_text(result["html"], encoding="utf-8", errors="replace")

    text = extract_text(result["html"])
    (d / "text.txt").write_text(text, encoding="utf-8", errors="replace")

    headings = extract_headings(result["html"])
    meta = {
        "url": result["url"],
        "final_url": result["final_url"],
        "status_code": result["status_code"],
        "content_type": result["content_type"],
        "elapsed_s": result["elapsed_s"],
        "error": result["error"],
        "headings": headings,
        "response_headers": result["headers"],
    }
    (d / "meta.json").write_text(json.dumps(meta, indent=2, default=str),
                                 encoding="utf-8")
    return slug


# ── Priority queue ───────────────────────────────────────────────────────

class CrawlQueue:
    def __init__(self) -> None:
        self._items: List[Tuple[int, str]] = []
        self._seen: Set[str] = set()

    def push(self, url: str, priority: int) -> bool:
        if url in self._seen:
            return False
        self._seen.add(url)
        self._items.append((priority, url))
        self._items.sort(key=lambda x: x[0])
        return True

    def pop(self) -> Optional[Tuple[int, str]]:
        return self._items.pop(0) if self._items else None

    def drain_all(self) -> List[Tuple[int, str]]:
        items = list(self._items)
        self._items.clear()
        return items

    def __len__(self) -> int:
        return len(self._items)


# ── Main crawl loop ─────────────────────────────────────────────────────

async def crawl(domain: str, corpus_dir: Path, budget: BudgetTracker) -> Dict:
    """Execute the bounded priority crawl.  Returns manifest-ready dict."""
    # Normalise origin
    if "://" not in domain:
        domain = "https://" + domain
    p = urlparse(domain)
    origin_host = p.netloc or p.path.split("/")[0]
    base_url = f"{p.scheme}://{origin_host}"

    corpus_dir.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(CONCURRENCY)
    limits = httpx.Limits(max_connections=CONCURRENCY + 2,
                          max_keepalive_connections=CONCURRENCY)
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(headers=headers, limits=limits,
                                 http2=True) as client:
        # 1. Robots.txt (async, bounded by budget)
        print(f"[crawl] Fetching robots.txt for {base_url}")
        robots_raw, all_rules = await fetch_robots_txt(base_url, client, budget)
        ai_rules = {a: all_rules.get(a, {}) for a in AI_AGENTS}
        ai_rules["*"] = all_rules.get("*", {})

        # 2. Sitemaps
        print("[crawl] Parsing sitemaps")
        sitemap_data = await parse_sitemaps(base_url, robots_raw, client)

        # 3. Seed the queue
        queue = CrawlQueue()
        queue.push(base_url + "/", PRI_HOME)

        # Sitemap URLs — one exemplar per path template
        template_enqueued: Set[str] = set()
        sm_origin = [u for u in sitemap_data["urls"]
                     if same_domain(u, origin_host)]
        for u in sm_origin[:200]:
            tmpl = url_path_template(u)
            if tmpl not in template_enqueued:
                template_enqueued.add(tmpl)
                queue.push(u, PRI_SITEMAP)

        # Explicit hunt paths
        for ep in EXPLICIT_PATHS:
            queue.push(base_url + ep, PRI_EXPLICIT)

        crawled: List[Dict] = []
        templates_crawled: Set[str] = set()
        nav_seeded = False

        while queue and len(crawled) < MAX_PAGES:
            # Hard ceiling check — halt immediately if over hard deadline
            if budget.over_hard():
                for _pri, skip_url in queue.drain_all():
                    budget.record_skip(skip_url,
                                       "hard_deadline_exceeded", "crawl")
                break

            # Budget gate — stop enqueueing when near soft deadline
            if budget.remaining_soft() < SOFT_MARGIN_S:
                for _pri, skip_url in queue.drain_all():
                    budget.record_skip(skip_url,
                                       "soft_deadline_approaching", "crawl")
                break

            # Pop a batch (up to CONCURRENCY, but never exceed MAX_PAGES total)
            remaining_slots = MAX_PAGES - len(crawled)
            batch_limit = min(CONCURRENCY, remaining_slots)
            batch: List[Tuple[int, str]] = []
            while len(batch) < batch_limit and queue:
                item = queue.pop()
                if item is None:
                    break
                pri, url = item
                # Robots check
                if not is_url_allowed(url, all_rules):
                    budget.record_skip(url, "robots_disallow", "crawl")
                    continue
                # Template dedup for lower-priority items
                tmpl = url_path_template(url)
                if pri >= PRI_TEMPLATE and tmpl in templates_crawled:
                    budget.record_skip(url, "template_already_crawled", "crawl")
                    continue
                batch.append((pri, url))

            if not batch:
                break

            # Fetch concurrently
            results = await asyncio.gather(
                *(fetch_page(u, client, sem) for _, u in batch)
            )

            for (pri, url), result in zip(batch, results):
                tmpl = url_path_template(url)
                slug = save_page(corpus_dir, result)
                crawled.append({
                    "url": url,
                    "final_url": result["final_url"],
                    "status_code": result["status_code"],
                    "error": result["error"],
                    "elapsed_s": result["elapsed_s"],
                    "slug": slug,
                })
                if slug:
                    templates_crawled.add(tmpl)

                # Seed nav links from the homepage
                if not nav_seeded and pri == PRI_HOME and result["html"]:
                    nav_seeded = True
                    for link in extract_nav_links(result["html"],
                                                  result["final_url"]):
                        if same_domain(link, origin_host):
                            queue.push(link, PRI_NAV)

                # Discover same-domain links from high-priority pages
                if pri <= PRI_NAV and result["html"]:
                    tree = HTMLParser(result["html"])
                    for node in tree.css("a"):
                        href = node.attributes.get("href", "")
                        n = normalise_url(href, result["final_url"])
                        if n and same_domain(n, origin_host):
                            lt = url_path_template(n)
                            if lt not in templates_crawled:
                                queue.push(n, PRI_TEMPLATE)

    pages_ok = [c for c in crawled if c["slug"]]
    return {
        "base_url": base_url,
        "origin_host": origin_host,
        "pages_crawled": len(pages_ok),
        "pages_attempted": len(crawled),
        "crawled_pages": crawled,
        "robots": {
            "raw_length_bytes": len(robots_raw.encode()),
            "has_robots_txt": len(robots_raw) > 0,
            "ai_agent_rules": ai_rules,
        },
        "sitemap": sitemap_data,
    }


# ── Entry point ──────────────────────────────────────────────────────────

async def main_async(domain: str, output_dir: Path,
                     soft: float, hard: float) -> Path:
    budget = BudgetTracker(soft_s=soft, hard_s=hard)
    print(f"[crawl] Starting: domain={domain}, output={output_dir}")

    try:
        data = await asyncio.wait_for(
            crawl(domain, output_dir, budget),
            timeout=max(1.0, budget.remaining_hard()),
        )
    except asyncio.TimeoutError:
        print(f"[crawl] Hard budget ceiling ({hard}s) reached! Halting crawl.")
        budget.record_skip("all", "crawl_hard_deadline_exceeded", "crawl")
        crawled_pages = []
        if output_dir.exists():
            for pdir in output_dir.iterdir():
                meta_file = pdir / "meta.json"
                if meta_file.exists():
                    try:
                        m = json.loads(meta_file.read_text(encoding="utf-8"))
                        crawled_pages.append({
                            "url": m.get("url"),
                            "final_url": m.get("final_url"),
                            "status_code": m.get("status_code"),
                            "error": m.get("error"),
                            "elapsed_s": m.get("elapsed_s"),
                            "slug": pdir.name,
                        })
                    except Exception:
                        pass
        data = {
            "base_url": domain,
            "origin_host": domain,
            "pages_crawled": len(crawled_pages),
            "pages_attempted": len(crawled_pages),
            "crawled_pages": crawled_pages,
            "robots": {"has_robots_txt": False, "raw_length_bytes": 0, "ai_agent_rules": {}},
            "sitemap": {"found": False, "urls": [], "sitemap_urls_fetched": [], "errors": [], "source_directives": []},
        }

    manifest = {
        "schema_version": "1.0",
        "tool": "site-acquisition/crawl.py",
        "domain": domain,
        "budget": budget.snapshot(),
        "skips": budget.skips(),
        **data,
    }
    manifest_path = output_dir.parent / "crawl_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str),
                             encoding="utf-8")
    e = budget.elapsed()
    print(f"[crawl] Done in {e:.1f}s — {data['pages_crawled']} pages, "
          f"{len(budget.skips())} skipped.  Manifest: {manifest_path}")
    return manifest_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Site-acquisition crawler")
    ap.add_argument("domain", help="Domain or URL to crawl")
    ap.add_argument("--output-dir", default=None,
                    help="Corpus output directory (default: corpus/<domain>/pages)")
    ap.add_argument("--budget-soft", type=float, default=240.0)
    ap.add_argument("--budget-hard", type=float, default=300.0)
    args = ap.parse_args()

    if args.output_dir:
        out = Path(args.output_dir)
    else:
        safe = re.sub(r"[^\w\-]", "_",
                      args.domain.replace("https://", "").replace("http://", ""))
        out = Path("corpus") / safe / "pages"

    asyncio.run(main_async(args.domain, out, args.budget_soft, args.budget_hard))


if __name__ == "__main__":
    main()
