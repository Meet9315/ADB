#!/usr/bin/env python3
"""
render.py — Headless-browser renderer for site-acquisition.

Renders 3–5 sampled pages (homepage + one exemplar per major URL template)
with Playwright, saving the post-JS HTML alongside raw.html in the corpus.

Shares a single wall-clock budget with crawl.py via BudgetTracker.from_manifest().

On startup, detects whether Playwright and a browser binary are available.
If not, sets `playwright_available: false` in the manifest and exits
cleanly — downstream checks use a lower-confidence heuristic fallback.

Usage:
    python render.py <corpus-dir> <crawl-manifest> [--budget-soft 240] [--budget-hard 300]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# -- resolve lib/ (sibling of scripts/) ------------------------------------
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "lib"))
from budget import BudgetTracker  # noqa: E402

RENDER_TIMEOUT_MS = 8_000       # 8 s per page
MAX_RENDER_PAGES = 5
MIN_RENDER_PAGES = 1            # always try at least the homepage


# ── Playwright availability probe ────────────────────────────────────────

def _probe_playwright() -> bool:
    """Return True if Playwright + a Chromium binary are usable."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F811
        pw = sync_playwright().start()
        try:
            browser = pw.chromium.launch(headless=True)
            browser.close()
            return True
        except Exception:
            return False
        finally:
            pw.stop()
    except Exception:
        return False


# ── Sample selection ─────────────────────────────────────────────────────

def _select_samples(manifest: Dict, max_pages: int) -> List[Dict]:
    """
    Pick homepage + one exemplar per unique URL-path template,
    capped at *max_pages*.
    """
    import re
    from urllib.parse import urlparse

    def _template(url: str) -> str:
        path = urlparse(url).path
        path = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/{uuid}", path)
        path = re.sub(r"/\d+", "/{id}", path)
        return path

    pages = [p for p in manifest.get("crawled_pages", []) if p.get("slug")]
    if not pages:
        return []

    # Homepage first
    home = [p for p in pages if urlparse(p["url"]).path in ("/", "")]
    rest = [p for p in pages if p not in home]

    selected: List[Dict] = []
    seen_templates: set = set()

    for p in home:
        t = _template(p["url"])
        if t not in seen_templates:
            seen_templates.add(t)
            selected.append(p)
        if len(selected) >= max_pages:
            return selected

    for p in rest:
        t = _template(p["url"])
        if t not in seen_templates:
            seen_templates.add(t)
            selected.append(p)
        if len(selected) >= max_pages:
            break

    return selected


# ── Rendering ────────────────────────────────────────────────────────────

def render_pages(
    corpus_dir: Path,
    samples: List[Dict],
    budget: BudgetTracker,
) -> List[Dict]:
    """
    Render each sample page with Playwright.
    Returns per-page result dicts.  Reuses a single browser instance.
    """
    from playwright.sync_api import sync_playwright

    results: List[Dict] = []
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)

    try:
        for idx, sample in enumerate(samples):
            # Budget check: halt if approaching hard ceiling
            if budget.remaining_hard() < 15.0:
                budget.record_skip(sample["url"],
                                   "render_hard_deadline_approaching", "render")
                break

            # Budget check: stop adding samples if remaining soft budget is tight
            if budget.remaining_soft() < 20.0 and len(results) >= MIN_RENDER_PAGES:
                budget.record_skip(sample["url"],
                                   "render_budget_reduced", "render")
                break

            slug = sample["slug"]
            url = sample["url"]
            page_dir = corpus_dir / slug
            t0 = time.monotonic()
            error: Optional[str] = None

            try:
                page = browser.new_page()
                page.goto(url, timeout=RENDER_TIMEOUT_MS,
                          wait_until="networkidle")
                rendered_html = page.content()
                page.close()
                (page_dir / "rendered.html").write_text(
                    rendered_html, encoding="utf-8", errors="replace")
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"

            elapsed = round(time.monotonic() - t0, 3)
            results.append({
                "url": url,
                "slug": slug,
                "rendered": error is None,
                "elapsed_s": elapsed,
                "error": error,
            })
            print(f"[render] {'OK' if not error else 'FAIL'} {url} "
                  f"({elapsed:.1f}s){'' if not error else ' — ' + error}")
    finally:
        browser.close()
        pw.stop()

    return results


# ── Entry point ──────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Site-acquisition renderer")
    ap.add_argument("corpus_dir", help="Path to corpus/pages directory")
    ap.add_argument("crawl_manifest", help="Path to crawl_manifest.json")
    ap.add_argument("--budget-soft", type=float, default=None,
                    help="Soft budget in seconds (default: inherit from manifest)")
    ap.add_argument("--budget-hard", type=float, default=None,
                    help="Hard budget in seconds (default: inherit from manifest)")
    args = ap.parse_args()

    corpus_dir = Path(args.corpus_dir)
    manifest_path = Path(args.crawl_manifest)

    if not manifest_path.exists():
        print(f"[render] ERROR: manifest not found: {manifest_path}",
              file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Shared budget tracker — continuous wall-clock time from crawl start
    budget = BudgetTracker.from_manifest(
        manifest, soft_s=args.budget_soft, hard_s=args.budget_hard
    )
    print(f"[render] Starting render phase. Acquisition elapsed so far: {budget.elapsed():.1f}s "
          f"(soft remaining: {budget.remaining_soft():.1f}s, hard remaining: {budget.remaining_hard():.1f}s)")

    # Hard ceiling safety check before doing any work
    if budget.remaining_hard() < 15.0:
        print("[render] Hard budget nearly exhausted before render phase — skipping rendering.")
        budget.record_skip("all", "acquisition_hard_budget_exhausted", "render")
        manifest["renderer"] = {
            "playwright_available": False,
            "note": "Skipped because acquisition hard budget was nearly exhausted.",
            "pages_rendered": 0,
            "render_results": [],
        }
        manifest["budget"] = budget.snapshot()
        manifest["skips"] = budget.skips()
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str),
                                 encoding="utf-8")
        return

    # Probe Playwright availability
    pw_available = _probe_playwright()
    print(f"[render] Playwright available: {pw_available}")

    if not pw_available:
        # Record and exit cleanly
        manifest["renderer"] = {
            "playwright_available": False,
            "note": "Playwright or browser binary not found; downstream "
                    "checks will use lower-confidence heuristic fallback.",
            "pages_rendered": 0,
            "render_results": [],
        }
        manifest["budget"] = budget.snapshot()
        manifest["skips"] = budget.skips()
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str),
                                 encoding="utf-8")
        print("[render] Skipped — Playwright unavailable.  "
              "Pipeline continues with heuristic fallback.")
        return

    # Select pages to render based on remaining budget
    max_pages = MAX_RENDER_PAGES
    if budget.over_soft() or budget.remaining_soft() < 60:
        max_pages = MIN_RENDER_PAGES
        print(f"[render] Budget tight ({budget.remaining_soft():.1f}s soft remaining) — "
              f"reducing to {MIN_RENDER_PAGES} sample page")

    samples = _select_samples(manifest, max_pages)
    if not samples:
        print("[render] No crawled pages with slugs — nothing to render.")
        manifest["renderer"] = {
            "playwright_available": True,
            "pages_rendered": 0,
            "render_results": [],
        }
        manifest["budget"] = budget.snapshot()
        manifest["skips"] = budget.skips()
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str),
                                 encoding="utf-8")
        return

    print(f"[render] Rendering {len(samples)} page(s)")
    render_results = render_pages(corpus_dir, samples, budget)

    # Update manifest with render results, final shared budget snapshot, and consolidated skips
    manifest["renderer"] = {
        "playwright_available": True,
        "pages_rendered": sum(1 for r in render_results if r["rendered"]),
        "render_results": render_results,
    }
    manifest["budget"] = budget.snapshot()
    manifest["skips"] = budget.skips()
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str),
                             encoding="utf-8")

    ok = sum(1 for r in render_results if r["rendered"])
    print(f"[render] Done in {budget.elapsed():.1f}s total acquisition time — "
          f"{ok}/{len(render_results)} pages rendered, {len(budget.skips())} total skips")


if __name__ == "__main__":
    main()
