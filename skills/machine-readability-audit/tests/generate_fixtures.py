#!/usr/bin/env python3
"""
generate_fixtures.py — Creates all test fixtures for Stage 3 checks.

Run once to generate the fixtures directory tree under
skills/machine-readability-audit/tests/fixtures/
"""

import json
import os
import sys
from pathlib import Path
import time

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def write_manifest(fixture_dir: Path, manifest: dict) -> None:
    (fixture_dir / "crawl_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def write_page(fixture_dir: Path, slug: str, html: str, meta: dict, rendered_html: str = None) -> None:
    d = fixture_dir / "pages" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "raw.html").write_text(html, encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if rendered_html is not None:
        (d / "rendered.html").write_text(rendered_html, encoding="utf-8")
    # Visible text: strip tags
    import re
    stripped = re.sub(r"<[^>]+>", " ", html)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    (d / "text.txt").write_text(stripped, encoding="utf-8")


BASE_MANIFEST = {
    "schema_version": "1.0",
    "tool": "site-acquisition/crawl.py",
    "domain": "example.com",
    "base_url": "https://example.com",
    "origin_host": "example.com",
    "pages_crawled": 1,
    "pages_attempted": 1,
    "budget": {
        "started_at": time.time() - 5.0,
        "elapsed_s": 5.0,
        "soft_deadline_s": 240.0,
        "hard_deadline_s": 300.0,
        "over_soft": False,
        "over_hard": False,
    },
    "skips": [],
}

HEALTHY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Acme Corp - The Best Widgets</title>
  <link rel="canonical" href="https://example.com/product">
  <meta property="og:url" content="https://example.com/product">
</head>
<body>
  <header>
    <img src="/logo.png" alt="Acme Corp logo" class="logo">
    <nav><a href="/">Home</a> <a href="/about">About</a></nav>
  </header>
  <section class="hero">
    <h1>World-Class Widgets for Everyone</h1>
    <p>Explore our full range of premium widgets. Prices start at $9.99 and include free shipping.</p>
    <img src="/hero-photo.jpg" alt="A selection of Acme widgets displayed on a shelf" class="hero-img">
  </section>
  <section>
    <h2>Featured Products</h2>
    <p>Our bestselling Widget Pro is now available in three colors. Read more on the product page.</p>
  </section>
  <footer><p>Contact us at info@example.com</p></footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Fixture: r1_blocked — R1 should fire (both training + assistant bots blocked)
# ---------------------------------------------------------------------------
def make_r1_blocked() -> None:
    d = FIXTURES_DIR / "r1_blocked"
    d.mkdir(parents=True, exist_ok=True)
    manifest = {**BASE_MANIFEST,
        "domain": "blocked.example.com",
        "base_url": "https://blocked.example.com",
        "origin_host": "blocked.example.com",
        "robots": {
            "has_robots_txt": True,
            "raw_length_bytes": 200,
            "ai_agent_rules": {
                "GPTBot": {"disallow": ["/"], "allow": [], "crawl_delay": None},
                "ClaudeBot": {"disallow": ["/"], "allow": [], "crawl_delay": None},
                "PerplexityBot": {"disallow": ["/"], "allow": [], "crawl_delay": None},
                "Google-Extended": {"disallow": ["/"], "allow": [], "crawl_delay": None},
                "CCBot": {"disallow": ["/"], "allow": [], "crawl_delay": None},
                "Bingbot": {"disallow": ["/"], "allow": [], "crawl_delay": None},
            },
        },
        "sitemap": {"found": True, "urls": ["https://blocked.example.com/"], "sitemap_urls_fetched": ["https://blocked.example.com/sitemap.xml"], "errors": [], "source_directives": []},
        "crawled_pages": [{"url": "https://blocked.example.com/", "final_url": "https://blocked.example.com/", "status_code": 200, "error": None, "elapsed_s": 0.5, "slug": "home_aabbccdd"}],
    }
    write_manifest(d, manifest)
    write_page(d, "home_aabbccdd", HEALTHY_HTML, {"url": "https://blocked.example.com/", "final_url": "https://blocked.example.com/", "status_code": 200, "response_headers": {}, "headings": {"h1": ["World-Class Widgets"], "h2": [], "h3": []}})


# ---------------------------------------------------------------------------
# Fixture: r1_training_only — R1 should fire at medium severity (training only)
# ---------------------------------------------------------------------------
def make_r1_training_only() -> None:
    d = FIXTURES_DIR / "r1_training_only"
    d.mkdir(parents=True, exist_ok=True)
    manifest = {**BASE_MANIFEST,
        "domain": "training-blocked.example.com",
        "base_url": "https://training-blocked.example.com",
        "origin_host": "training-blocked.example.com",
        "robots": {
            "has_robots_txt": True,
            "raw_length_bytes": 100,
            "ai_agent_rules": {
                "GPTBot": {"disallow": ["/"], "allow": [], "crawl_delay": None},
                "CCBot": {"disallow": ["/"], "allow": [], "crawl_delay": None},
                "Google-Extended": {"disallow": ["/"], "allow": [], "crawl_delay": None},
                "ClaudeBot": {"disallow": [], "allow": [], "crawl_delay": None},
                "PerplexityBot": {"disallow": [], "allow": [], "crawl_delay": None},
                "Bingbot": {"disallow": [], "allow": [], "crawl_delay": None},
            },
        },
        "sitemap": {"found": True, "urls": ["https://training-blocked.example.com/"], "sitemap_urls_fetched": [], "errors": [], "source_directives": []},
        "crawled_pages": [{"url": "https://training-blocked.example.com/", "final_url": "https://training-blocked.example.com/", "status_code": 200, "error": None, "elapsed_s": 0.5, "slug": "home_11223344"}],
    }
    write_manifest(d, manifest)
    write_page(d, "home_11223344", HEALTHY_HTML, {"url": "https://training-blocked.example.com/", "final_url": "https://training-blocked.example.com/", "status_code": 200, "response_headers": {}, "headings": {"h1": ["World-Class Widgets"], "h2": [], "h3": []}})


# ---------------------------------------------------------------------------
# Fixture: r3_no_sitemap — R3 should fire
# ---------------------------------------------------------------------------
def make_r3_no_sitemap() -> None:
    d = FIXTURES_DIR / "r3_no_sitemap"
    d.mkdir(parents=True, exist_ok=True)
    crawled = []
    for i in range(6):
        crawled.append({"url": f"https://nosit.example.com/page{i}", "final_url": f"https://nosit.example.com/page{i}", "status_code": 200, "error": None, "elapsed_s": 0.3, "slug": f"page{i}_aabb{i:04d}"})
    manifest = {**BASE_MANIFEST,
        "domain": "nosit.example.com",
        "base_url": "https://nosit.example.com",
        "origin_host": "nosit.example.com",
        "robots": {
            "has_robots_txt": True,
            "raw_length_bytes": 50,
            "ai_agent_rules": {a: {"disallow": [], "allow": [], "crawl_delay": None} for a in ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot", "Bingbot"]},
        },
        "sitemap": {"found": False, "urls": [], "sitemap_urls_fetched": [], "errors": ["https://nosit.example.com/sitemap.xml: HTTP 404"], "source_directives": []},
        "crawled_pages": crawled,
    }
    write_manifest(d, manifest)
    for pg in crawled:
        write_page(d, pg["slug"], HEALTHY_HTML, {"url": pg["url"], "final_url": pg["final_url"], "status_code": 200, "response_headers": {}, "headings": {"h1": ["Test Page"], "h2": [], "h3": []}})


# ---------------------------------------------------------------------------
# Fixture: r4_noindex — R4 should fire on product page, NOT on login page
# ---------------------------------------------------------------------------
def make_r4_noindex() -> None:
    d = FIXTURES_DIR / "r4_noindex"
    d.mkdir(parents=True, exist_ok=True)

    # Substantive product page with noindex
    product_html = """<!DOCTYPE html>
<html><head>
  <meta charset="UTF-8">
  <title>Widget Pro - Shop Now</title>
  <meta name="robots" content="noindex, follow">
</head>
<body>
  <h1>Widget Pro — $49.99</h1>
  <p>The Widget Pro is our best-selling product. Available in red, blue, and green.</p>
  <section class="pricing">
    <h2>Pricing</h2>
    <p>Standard: $49.99 | Premium: $79.99</p>
  </section>
</body></html>"""

    # Login page with noindex — should NOT fire
    login_html = """<!DOCTYPE html>
<html><head>
  <meta charset="UTF-8">
  <title>Login - Example Site</title>
  <meta name="robots" content="noindex, nofollow">
</head>
<body>
  <h1>Sign in to your account</h1>
  <form><input type="email"><input type="password"><button>Sign in</button></form>
</body></html>"""

    manifest = {**BASE_MANIFEST,
        "domain": "noindex.example.com",
        "base_url": "https://noindex.example.com",
        "origin_host": "noindex.example.com",
        "robots": {
            "has_robots_txt": True,
            "raw_length_bytes": 60,
            "ai_agent_rules": {a: {"disallow": [], "allow": [], "crawl_delay": None} for a in ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot", "Bingbot"]},
        },
        "sitemap": {"found": True, "urls": ["https://noindex.example.com/", "https://noindex.example.com/widget-pro"], "sitemap_urls_fetched": ["https://noindex.example.com/sitemap.xml"], "errors": [], "source_directives": []},
        "crawled_pages": [
            {"url": "https://noindex.example.com/widget-pro", "final_url": "https://noindex.example.com/widget-pro", "status_code": 200, "error": None, "elapsed_s": 0.4, "slug": "widget_pro_aabb1234"},
            {"url": "https://noindex.example.com/login", "final_url": "https://noindex.example.com/login", "status_code": 200, "error": None, "elapsed_s": 0.3, "slug": "login_aabb5678"},
        ],
    }
    write_manifest(d, manifest)
    write_page(d, "widget_pro_aabb1234", product_html, {
        "url": "https://noindex.example.com/widget-pro",
        "final_url": "https://noindex.example.com/widget-pro",
        "status_code": 200,
        "response_headers": {},
        "headings": {"h1": ["Widget Pro — $49.99"], "h2": ["Pricing"], "h3": []},
    })
    write_page(d, "login_aabb5678", login_html, {
        "url": "https://noindex.example.com/login",
        "final_url": "https://noindex.example.com/login",
        "status_code": 200,
        "response_headers": {},
        "headings": {"h1": ["Sign in to your account"], "h2": [], "h3": []},
    })


# ---------------------------------------------------------------------------
# Fixture: r4_header_noindex — R4 should fire via X-Robots-Tag header
# ---------------------------------------------------------------------------
def make_r4_header_noindex() -> None:
    d = FIXTURES_DIR / "r4_header_noindex"
    d.mkdir(parents=True, exist_ok=True)
    pricing_html = """<!DOCTYPE html>
<html><head><title>Pricing Plans - Example</title></head>
<body>
  <h1>Our Pricing</h1>
  <p>Basic: $10/mo. Pro: $49/mo. Enterprise: Contact us.</p>
</body></html>"""
    manifest = {**BASE_MANIFEST,
        "domain": "headernoindex.example.com",
        "base_url": "https://headernoindex.example.com",
        "origin_host": "headernoindex.example.com",
        "robots": {
            "has_robots_txt": True,
            "raw_length_bytes": 60,
            "ai_agent_rules": {a: {"disallow": [], "allow": [], "crawl_delay": None} for a in ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot", "Bingbot"]},
        },
        "sitemap": {"found": True, "urls": ["https://headernoindex.example.com/pricing"], "sitemap_urls_fetched": [], "errors": [], "source_directives": []},
        "crawled_pages": [{"url": "https://headernoindex.example.com/pricing", "final_url": "https://headernoindex.example.com/pricing", "status_code": 200, "error": None, "elapsed_s": 0.3, "slug": "pricing_ccdd1234"}],
    }
    write_manifest(d, manifest)
    write_page(d, "pricing_ccdd1234", pricing_html, {
        "url": "https://headernoindex.example.com/pricing",
        "final_url": "https://headernoindex.example.com/pricing",
        "status_code": 200,
        "response_headers": {"X-Robots-Tag": "noindex"},
        "headings": {"h1": ["Our Pricing"], "h2": [], "h3": []},
    })


# ---------------------------------------------------------------------------
# Fixture: r5_canonical_conflict — R5b should fire
# ---------------------------------------------------------------------------
def make_r5_canonical_conflict() -> None:
    d = FIXTURES_DIR / "r5_canonical_conflict"
    d.mkdir(parents=True, exist_ok=True)
    conflict_html = """<!DOCTYPE html>
<html><head>
  <title>Widget Blue</title>
  <link rel="canonical" href="https://example.com/products/widget-blue">
  <meta property="og:url" content="https://example.com/shop/items/widget-blue-v2">
</head>
<body>
  <h1>Widget Blue</h1>
  <p>The best blue widget available.</p>
</body></html>"""
    manifest = {**BASE_MANIFEST,
        "domain": "conflictcanon.example.com",
        "base_url": "https://conflictcanon.example.com",
        "origin_host": "conflictcanon.example.com",
        "robots": {
            "has_robots_txt": True,
            "raw_length_bytes": 50,
            "ai_agent_rules": {a: {"disallow": [], "allow": [], "crawl_delay": None} for a in ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot", "Bingbot"]},
        },
        "sitemap": {"found": True, "urls": ["https://conflictcanon.example.com/products/widget-blue"], "sitemap_urls_fetched": [], "errors": [], "source_directives": []},
        "crawled_pages": [{"url": "https://conflictcanon.example.com/products/widget-blue", "final_url": "https://conflictcanon.example.com/products/widget-blue", "status_code": 200, "error": None, "elapsed_s": 0.4, "slug": "products_widget_blue_aa112233"}],
    }
    write_manifest(d, manifest)
    write_page(d, "products_widget_blue_aa112233", conflict_html, {
        "url": "https://conflictcanon.example.com/products/widget-blue",
        "final_url": "https://conflictcanon.example.com/products/widget-blue",
        "status_code": 200,
        "response_headers": {},
        "headings": {"h1": ["Widget Blue"], "h2": [], "h3": []},
    })


# ---------------------------------------------------------------------------
# Fixture: r5_4xx_link — R5c should fire
# ---------------------------------------------------------------------------
def make_r5_4xx_link() -> None:
    d = FIXTURES_DIR / "r5_4xx_link"
    d.mkdir(parents=True, exist_ok=True)
    manifest = {**BASE_MANIFEST,
        "domain": "deadlinks.example.com",
        "base_url": "https://deadlinks.example.com",
        "origin_host": "deadlinks.example.com",
        "robots": {
            "has_robots_txt": True,
            "raw_length_bytes": 50,
            "ai_agent_rules": {a: {"disallow": [], "allow": [], "crawl_delay": None} for a in ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot", "Bingbot"]},
        },
        "sitemap": {"found": True, "urls": ["https://deadlinks.example.com/"], "sitemap_urls_fetched": [], "errors": [], "source_directives": []},
        "crawled_pages": [
            {"url": "https://deadlinks.example.com/", "final_url": "https://deadlinks.example.com/", "status_code": 200, "error": None, "elapsed_s": 0.3, "slug": "home_deadlinks_aa11"},
            {"url": "https://deadlinks.example.com/old-product", "final_url": "https://deadlinks.example.com/old-product", "status_code": 404, "error": None, "elapsed_s": 0.2, "slug": "old_product_bb22"},
        ],
    }
    write_manifest(d, manifest)
    write_page(d, "home_deadlinks_aa11", HEALTHY_HTML, {"url": "https://deadlinks.example.com/", "final_url": "https://deadlinks.example.com/", "status_code": 200, "response_headers": {}, "headings": {"h1": ["Home"], "h2": [], "h3": []}})
    write_page(d, "old_product_bb22", "<html><head><title>404 Not Found</title></head><body><h1>Not Found</h1></body></html>", {"url": "https://deadlinks.example.com/old-product", "final_url": "https://deadlinks.example.com/old-product", "status_code": 404, "response_headers": {}, "headings": {"h1": ["Not Found"], "h2": [], "h3": []}})


# ---------------------------------------------------------------------------
# Fixture: d2_images — D2 should fire on content image without alt
# ---------------------------------------------------------------------------
def make_d2_images() -> None:
    d = FIXTURES_DIR / "d2_images"
    d.mkdir(parents=True, exist_ok=True)

    # Hero image with no alt (should fire), logo with "logo" filename (should NOT fire)
    # Small 20x20 icon (should NOT fire), cart image with context text (should NOT fire for context)
    d2_html = """<!DOCTYPE html>
<html><head><title>Pricing - Best Deals</title></head>
<body>
  <header>
    <img src="/acme-logo.png" alt="Acme Inc" class="logo">
  </header>
  <section class="hero">
    <h1>Unbeatable Widget Deals</h1>
    <img src="/hero-pricing-banner.jpg" class="hero-banner">
    <img src="/icon-check.png" width="20" height="20">
    <img src="/spacer.gif" width="1" height="1">
  </section>
  <section class="pricing">
    <h2>Plans</h2>
    <img src="/pricing-table.png" alt="" class="pricing-image">
  </section>
</body></html>"""

    manifest = {**BASE_MANIFEST,
        "domain": "d2test.example.com",
        "base_url": "https://d2test.example.com",
        "origin_host": "d2test.example.com",
        "robots": {
            "has_robots_txt": True,
            "raw_length_bytes": 50,
            "ai_agent_rules": {a: {"disallow": [], "allow": [], "crawl_delay": None} for a in ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot", "Bingbot"]},
        },
        "sitemap": {"found": True, "urls": ["https://d2test.example.com/"], "sitemap_urls_fetched": [], "errors": [], "source_directives": []},
        "crawled_pages": [{"url": "https://d2test.example.com/", "final_url": "https://d2test.example.com/", "status_code": 200, "error": None, "elapsed_s": 0.5, "slug": "home_d2_aa1122"}],
    }
    write_manifest(d, manifest)
    write_page(d, "home_d2_aa1122", d2_html, {
        "url": "https://d2test.example.com/",
        "final_url": "https://d2test.example.com/",
        "status_code": 200,
        "response_headers": {},
        "headings": {"h1": ["Unbeatable Widget Deals"], "h2": ["Plans"], "h3": []},
    })


# ---------------------------------------------------------------------------
# Fixture: clean — all 6 checks must produce 0 findings
# ---------------------------------------------------------------------------
def make_clean() -> None:
    d = FIXTURES_DIR / "clean"
    d.mkdir(parents=True, exist_ok=True)

    clean_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Acme Corp - Premium Widgets</title>
  <link rel="canonical" href="https://clean.example.com/">
  <meta property="og:url" content="https://clean.example.com/">
</head>
<body>
  <header>
    <img src="/acme-logo.png" alt="Acme Corp logo" class="logo" width="200" height="50">
    <nav><a href="/about">About</a><a href="/pricing">Pricing</a></nav>
  </header>
  <section class="hero">
    <h1>World-Class Widgets</h1>
    <p>Discover our premium widget lineup. Each widget is handcrafted with care and comes with a 30-day money-back guarantee. Our team of engineers has spent years perfecting the design.</p>
    <img src="/hero-widgets.jpg" alt="A selection of premium Acme widgets in various colors" class="hero-img">
  </section>
  <section>
    <h2>Why Choose Acme?</h2>
    <p>Trusted by over 10,000 businesses worldwide. Our widgets integrate seamlessly with all major platforms and require no technical expertise to set up.</p>
  </section>
  <section>
    <h2>Pricing</h2>
    <p>Basic: $9.99/month | Pro: $29.99/month | Enterprise: custom pricing available on request.</p>
  </section>
  <footer><p>© 2026 Acme Corp | <a href="/contact">Contact</a></p></footer>
</body>
</html>"""

    manifest = {
        "schema_version": "1.0",
        "tool": "site-acquisition/crawl.py",
        "domain": "clean.example.com",
        "base_url": "https://clean.example.com",
        "origin_host": "clean.example.com",
        "pages_crawled": 1,
        "pages_attempted": 1,
        "budget": {
            "started_at": time.time() - 5.0,
            "elapsed_s": 5.0,
            "soft_deadline_s": 240.0,
            "hard_deadline_s": 300.0,
            "over_soft": False,
            "over_hard": False,
        },
        "robots": {
            "has_robots_txt": True,
            "raw_length_bytes": 80,
            "ai_agent_rules": {
                agent: {"disallow": [], "allow": [], "crawl_delay": None}
                for agent in ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot", "Bingbot"]
            },
        },
        "sitemap": {
            "found": True,
            "urls": ["https://clean.example.com/", "https://clean.example.com/about", "https://clean.example.com/pricing"],
            "sitemap_urls_fetched": ["https://clean.example.com/sitemap.xml"],
            "errors": [],
            "source_directives": [],
        },
        "crawled_pages": [
            {
                "url": "https://clean.example.com/",
                "final_url": "https://clean.example.com/",
                "status_code": 200,
                "error": None,
                "elapsed_s": 0.35,
                "slug": "home_clean_aabb1122",
                "redirect_count": 0,
            }
        ],
        "skips": [],
    }

    write_manifest(d, manifest)
    write_page(d, "home_clean_aabb1122", clean_html, {
        "url": "https://clean.example.com/",
        "final_url": "https://clean.example.com/",
        "status_code": 200,
        "response_headers": {},
        "headings": {"h1": ["World-Class Widgets"], "h2": ["Why Choose Acme?", "Pricing"], "h3": []},
        "redirect_count": 0,
    })


# ---------------------------------------------------------------------------
# Fixture: e2_wrong_price — JSON-LD price contradiction ($19.99 vs visible $49.99)
# ---------------------------------------------------------------------------
def make_e2_wrong_price() -> None:
    d = FIXTURES_DIR / "e2_wrong_price"
    d.mkdir(parents=True, exist_ok=True)
    manifest = {**BASE_MANIFEST, "domain": "wrongprice.example.com", "base_url": "https://wrongprice.example.com"}

    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Widget Pro - Acme Store</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Widget Pro",
    "offers": {
      "@type": "Offer",
      "price": "19.99",
      "priceCurrency": "USD",
      "availability": "https://schema.org/InStock"
    }
  }
  </script>
</head>
<body>
  <h1>Widget Pro</h1>
  <div class="pricing-box">
    <p class="current-price">Special Price: $49.99 (Free Express Delivery)</p>
    <p>Upgrade to Widget Pro today for only $49.99. Backed by our 30-day money-back guarantee.</p>
  </div>
</body>
</html>"""

    write_manifest(d, manifest)
    write_page(d, "product_wrong_price", html, {
        "url": "https://wrongprice.example.com/widget-pro",
        "status_code": 200,
    })


# ---------------------------------------------------------------------------
# Fixture: e2_microdata — Microdata product with valid properties and matching text
# ---------------------------------------------------------------------------
def make_e2_microdata() -> None:
    d = FIXTURES_DIR / "e2_microdata"
    d.mkdir(parents=True, exist_ok=True)
    manifest = {**BASE_MANIFEST, "domain": "microdata.example.com", "base_url": "https://microdata.example.com"}

    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Microdata Widget Store</title>
</head>
<body>
  <div itemscope itemtype="http://schema.org/Product">
    <h1 itemprop="name">Microdata Widget Deluxe</h1>
    <p>Premium quality microdata widget for all industrial uses.</p>
    <div itemprop="offers" itemscope itemtype="http://schema.org/Offer">
      <span itemprop="price">29.99</span>
      <span itemprop="priceCurrency">USD</span>
    </div>
    <p>Now in stock for $29.99 with fast doorstep shipping.</p>
  </div>
</body>
</html>"""

    write_manifest(d, manifest)
    write_page(d, "product_microdata", html, {
        "url": "https://microdata.example.com/product",
        "status_code": 200,
    })


# ---------------------------------------------------------------------------
# Fixture: e2_rdfa — RDFa product with valid properties and matching text
# ---------------------------------------------------------------------------
def make_e2_rdfa() -> None:
    d = FIXTURES_DIR / "e2_rdfa"
    d.mkdir(parents=True, exist_ok=True)
    manifest = {**BASE_MANIFEST, "domain": "rdfa.example.com", "base_url": "https://rdfa.example.com"}

    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>RDFa Gadget Store</title>
</head>
<body>
  <div vocab="http://schema.org/" typeof="Product">
    <h1 property="name">RDFa Gadget Extreme</h1>
    <p>High-performance engineering gadget built with modern standards.</p>
    <div property="offers" typeof="Offer">
      <span property="price">39.99</span>
      <span property="priceCurrency">USD</span>
    </div>
    <p>Buy the RDFa Gadget Extreme today for $39.99 with comprehensive warranty.</p>
  </div>
</body>
</html>"""

    write_manifest(d, manifest)
    write_page(d, "product_rdfa", html, {
        "url": "https://rdfa.example.com/gadget",
        "status_code": 200,
    })


# ---------------------------------------------------------------------------
# Fixture: e2_clean — Clean structured data with matching visible price ($89.99)
# ---------------------------------------------------------------------------
def make_e2_clean() -> None:
    d = FIXTURES_DIR / "e2_clean"
    d.mkdir(parents=True, exist_ok=True)
    manifest = {**BASE_MANIFEST, "domain": "clean-sd.example.com", "base_url": "https://clean-sd.example.com"}

    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Clean Electronics - Ultra Headphones</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Ultra Wireless Headphones",
    "description": "Studio grade wireless headphones with active noise cancellation.",
    "offers": {
      "@type": "Offer",
      "price": "89.99",
      "priceCurrency": "USD",
      "availability": "https://schema.org/InStock"
    }
  }
  </script>
</head>
<body>
  <h1>Ultra Wireless Headphones</h1>
  <p>Studio grade wireless headphones with active noise cancellation.</p>
  <p>Available now in our store for $89.99 with free 2-day delivery.</p>
</body>
</html>"""

    write_manifest(d, manifest)
    write_page(d, "product_clean", html, {
        "url": "https://clean-sd.example.com/headphones",
        "status_code": 200,
    })


# ---------------------------------------------------------------------------
# Fixture: d1_js_gap — Raw HTML is SPA shell, rendered DOM has rich text (>450 words)
# ---------------------------------------------------------------------------
def make_d1_js_gap() -> None:
    d = FIXTURES_DIR / "d1_js_gap"
    d.mkdir(parents=True, exist_ok=True)
    manifest = {**BASE_MANIFEST, "domain": "spa-app.example.com", "base_url": "https://spa-app.example.com"}

    raw_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Acme Cloud Dashboard</title>
  <script src="/static/js/main.7f89b1c2.js"></script>
</head>
<body>
  <div id="root"></div>
  <noscript>You need to enable JavaScript to run this app.</noscript>
</body>
</html>"""

    # Rendered DOM with >450 words of rich content
    paragraphs = [
        "Welcome to the Acme Cloud enterprise operations platform and cloud orchestration system.",
        "Our unified control plane allows development teams to manage microservices, configure automated continuous deployment pipelines, and inspect distributed trace telemetry with sub-millisecond precision across global regions.",
        "The Developer Tier is completely free for up to three projects and includes five hundred build minutes per month, standard community support, and GitHub integration with automated pull request status checks.",
        "The Professional Tier costs twenty-nine dollars per user monthly and provides unlimited deployment pipelines, custom domain routing, automated SSL certificate generation, role-based access controls, and twelve-hour turnaround email support.",
        "The Enterprise Organization Tier costs four hundred and ninety-nine dollars per month and includes dedicated technical account management, single sign-on via Okta and Azure Active Directory, SOC 2 Type II audit report access, ninety-nine point nine nine percent uptime service level agreements, and custom data residency regions across North America, Europe, and Asia Pacific.",
        "Getting started is straightforward. Install our command-line utility using npm install -g acme-cli, authenticate using your personal access token, run acme init in your repository directory, and deploy instantly with acme deploy --production.",
        "Our high-performance edge compute network spans over one hundred and twenty cities worldwide, ensuring your APIs and serverless functions execute within twenty milliseconds of your end users.",
        "Security is central to our architectural foundation. All customer payloads are encrypted in transit via TLS 1.3 and at rest utilizing AES-256 GCM encryption keys rotated automatically every ninety days.",
        "Comprehensive observability includes distributed tracing across all container clusters, live metric streaming, real-time alert routing to PagerDuty and Slack, and queryable audit logs retained for up to seven years in cold storage.",
        "Modern infrastructure teams choose Acme Cloud because it eliminates manual cloud configuration, reduces server provisioning latency from hours to seconds, and provides guaranteed compliance with ISO 27001 and FedRAMP standards.",
        "Contact our global solutions engineering team to schedule a technical architecture review or request custom proof-of-concept testing in your staging environment.",
    ]
    rendered_body = "\n".join(f"<p>{p}</p>" for p in paragraphs)
    rendered_html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Acme Cloud Dashboard</title></head>
<body>
  <div id="root">
    <h1>Acme Cloud Operations Platform</h1>
    {rendered_body}
  </div>
</body>
</html>"""

    write_manifest(d, manifest)
    write_page(d, "home_spa", raw_html, {
        "url": "https://spa-app.example.com/",
        "status_code": 200,
    }, rendered_html=rendered_html)


# ---------------------------------------------------------------------------
# Fixture: e3_quotability — SaaS site with vague evasive pricing (quotability gap)
# ---------------------------------------------------------------------------
def make_e3_quotability() -> None:
    d = FIXTURES_DIR / "e3_quotability"
    d.mkdir(parents=True, exist_ok=True)
    manifest = {
        **BASE_MANIFEST,
        "domain": "cloudsaas.example.com",
        "base_url": "https://cloudsaas.example.com",
        "crawled_pages": [
            {"url": "https://cloudsaas.example.com/", "slug": "home_page"},
            {"url": "https://cloudsaas.example.com/pricing", "slug": "pricing_page"},
        ]
    }

    home_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CloudSaaS - Enterprise Workflow Platform</title>
</head>
<body>
  <h1>CloudSaaS Workflow Automation</h1>
  <p>CloudSaaS helps enterprise teams automate complex multi-step workflows, manage cross-team tasks, and integrate APIs effortlessly.</p>
  <a href="/pricing">View Plans and Pricing</a>
</body>
</html>"""

    pricing_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Plans & Pricing - CloudSaaS</title>
</head>
<body>
  <h1>Flexible Plans for Teams of Every Size</h1>
  <p>We believe every business is unique. We offer flexible subscription plans tailored specifically to your organization's bespoke requirements.</p>
  <p>Contact our sales team for pricing details and to schedule an executive consultation today. Pricing is available upon request.</p>
  <p>Learn more about our enterprise platform capabilities by speaking with a specialist.</p>
</body>
</html>"""

    write_manifest(d, manifest)
    write_page(d, "home_page", home_html, {
        "url": "https://cloudsaas.example.com/",
        "status_code": 200,
    })
    write_page(d, "pricing_page", pricing_html, {
        "url": "https://cloudsaas.example.com/pricing",
        "status_code": 200,
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    make_r1_blocked()
    make_r1_training_only()
    make_r3_no_sitemap()
    make_r4_noindex()
    make_r4_header_noindex()
    make_r5_canonical_conflict()
    make_r5_4xx_link()
    make_d2_images()
    make_clean()
    # Stage 5 fixtures:
    make_e2_wrong_price()
    make_e2_microdata()
    make_e2_rdfa()
    make_e2_clean()
    make_d1_js_gap()
    make_e3_quotability()
    print("All fixtures generated successfully.")
