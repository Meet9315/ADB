#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_archetype_fixtures.py — Generates synthetic test fixtures for archetype classifier:
  1. Major archetypes (8): ecommerce, saas, content, news, docs, portfolio, local_business, corporate
  2. Ambiguous case: SaaS with deep documentation
  3. Unknown case: minimal/generic landing without signals
  4. Mixed case: Ecommerce + SaaS
  5. False-positive guard for local_business: corporate tech site with HQ address in footer but no hours/schema
  6. False-positive guard for corporate: personal blog with Organization/WebSite schema but no Corporation
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def write_manifest(fixture_dir: Path, manifest: dict) -> None:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "crawl_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def write_page(fixture_dir: Path, slug: str, html: str, meta: dict) -> None:
    d = fixture_dir / "pages" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "raw.html").write_text(html, encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    stripped = re.sub(r"<[^>]+>", " ", html)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    (d / "text.txt").write_text(stripped, encoding="utf-8")


def base_manifest(domain: str, pages: list[dict]) -> dict:
    return {
        "schema_version": "1.0",
        "tool": "site-acquisition/crawl.py",
        "domain": domain,
        "base_url": f"https://{domain}",
        "origin_host": domain,
        "pages_crawled": len(pages),
        "pages_attempted": len(pages),
        "budget": {
            "started_at": time.time() - 5.0,
            "elapsed_s": 5.0,
            "soft_deadline_s": 240.0,
            "hard_deadline_s": 300.0,
            "over_soft": False,
            "over_hard": False,
        },
        "crawled_pages": pages,
        "skips": [],
    }


# ===========================================================================
# 1. Major Archetype: Ecommerce
# ===========================================================================
def make_ecommerce() -> None:
    d = FIXTURES_DIR / "archetype_ecommerce"
    p1 = {
        "url": "https://shop.example.com/",
        "final_url": "https://shop.example.com/",
        "status_code": 200, "slug": "home", "elapsed_s": 0.1, "redirect_count": 0, "error": None
    }
    p2 = {
        "url": "https://shop.example.com/products/classic-tee",
        "final_url": "https://shop.example.com/products/classic-tee",
        "status_code": 200, "slug": "product_tee", "elapsed_s": 0.1, "redirect_count": 0, "error": None
    }
    p3 = {
        "url": "https://shop.example.com/cart",
        "final_url": "https://shop.example.com/cart",
        "status_code": 200, "slug": "cart", "elapsed_s": 0.1, "redirect_count": 0, "error": None
    }
    write_manifest(d, base_manifest("shop.example.com", [p1, p2, p3]))

    html_home = """<!DOCTYPE html><html><head><title>Urban Threads Store</title></head><body>
    <nav><a href="/products/classic-tee">Shop</a><a href="/cart">Cart (0)</a></nav>
    <h1>Urban Threads Online Store</h1><p>Check out our seasonal collection.</p>
    </body></html>"""

    html_prod = """<!DOCTYPE html><html><head><title>Classic Cotton Tee - Urban Threads</title>
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "Product", "name": "Classic Cotton Tee",
     "offers": {"@type": "Offer", "price": "29.99", "priceCurrency": "USD"}}
    </script></head><body>
    <h1>Classic Cotton Tee</h1>
    <p>Price: $29.99 USD</p>
    <form action="/cart/add" method="post">
      <button type="submit" class="btn add-to-cart">Add to Cart</button>
    </form>
    </body></html>"""

    html_cart = """<!DOCTYPE html><html><head><title>Shopping Cart</title></head><body>
    <h1>Your Shopping Bag</h1>
    <form action="/checkout" method="post">
      <button type="submit" class="btn buy-now">Proceed to Checkout</button>
    </form>
    </body></html>"""

    write_page(d, "home", html_home, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "product_tee", html_prod, {"url": p2["url"], "final_url": p2["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "cart", html_cart, {"url": p3["url"], "final_url": p3["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 2. Major Archetype: SaaS
# ===========================================================================
def make_saas() -> None:
    d = FIXTURES_DIR / "archetype_saas"
    p1 = {"url": "https://saastool.io/", "final_url": "https://saastool.io/", "status_code": 200, "slug": "home", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p2 = {"url": "https://saastool.io/pricing", "final_url": "https://saastool.io/pricing", "status_code": 200, "slug": "pricing", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p3 = {"url": "https://saastool.io/features", "final_url": "https://saastool.io/features", "status_code": 200, "slug": "features", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    write_manifest(d, base_manifest("saastool.io", [p1, p2, p3]))

    html_home = """<!DOCTYPE html><html><head><title>DataFlow — Modern Cloud Workflow Automation</title>
    <script type="application/ld+json">{"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "DataFlow"}</script>
    </head><body>
    <h1>Automate Your Cloud Pipelines with Real-time Analytics</h1>
    <p>Manage your team's workflow and integration dashboards with ease.</p>
    <a href="/pricing" class="btn">Start a free trial</a>
    <a href="/demo" class="btn">Request a demo</a>
    </body></html>"""

    html_pricing = """<!DOCTYPE html><html><head><title>Plans & Pricing - DataFlow</title></head><body>
    <h1>Choose Your Plan</h1>
    <div class="tier"><h2>Starter</h2><p>$19 per user per month</p><a href="/signup">Try free trial</a></div>
    <div class="tier"><h2>Enterprise Plan</h2><p>Custom SSO, SAML, and API webhooks.</p><a href="/demo">Book a consultation</a></div>
    </body></html>"""

    html_features = """<!DOCTYPE html><html><head><title>Platform Features - DataFlow</title></head><body>
    <h1>API, Webhooks & Enterprise Automation</h1>
    <p>Build custom integrations with our unified dashboard and automated analytics engine.</p>
    </body></html>"""

    write_page(d, "home", html_home, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "pricing", html_pricing, {"url": p2["url"], "final_url": p2["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "features", html_features, {"url": p3["url"], "final_url": p3["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 3. Major Archetype: Content / Blog
# ===========================================================================
def make_content() -> None:
    d = FIXTURES_DIR / "archetype_content"
    p1 = {"url": "https://deeptechblog.org/", "final_url": "https://deeptechblog.org/", "status_code": 200, "slug": "home", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p2 = {"url": "https://deeptechblog.org/blog/future-of-compilers", "final_url": "https://deeptechblog.org/blog/future-of-compilers", "status_code": 200, "slug": "post1", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p3 = {"url": "https://deeptechblog.org/blog/garbage-collection-notes", "final_url": "https://deeptechblog.org/blog/garbage-collection-notes", "status_code": 200, "slug": "post2", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    write_manifest(d, base_manifest("deeptechblog.org", [p1, p2, p3]))

    html_home = """<!DOCTYPE html><html><head><title>Deep Tech Blog</title></head><body>
    <h1>Essays on Systems Engineering</h1>
    <nav><a href="/blog/future-of-compilers">Compilers</a><a href="/blog/garbage-collection-notes">Memory</a></nav>
    </body></html>"""

    html_p1 = """<!DOCTYPE html><html><head><title>The Future of Optimizing Compilers</title>
    <script type="application/ld+json">{"@context": "https://schema.org", "@type": "BlogPosting", "headline": "The Future of Optimizing Compilers"}</script>
    </head><body>
    <h1>The Future of Optimizing Compilers</h1>
    <div class="byline">Written by Dr. Aris Thorne</div>
    <time datetime="2025-11-10">Published November 10, 2025</time>
    <article><p>Compilers have transformed modern software performance through multi-stage optimizations...</p></article>
    </body></html>"""

    html_p2 = """<!DOCTYPE html><html><head><title>Garbage Collection Architecture Notes</title>
    <script type="application/ld+json">{"@context": "https://schema.org", "@type": "Article", "headline": "Garbage Collection Architecture Notes"}</script>
    </head><body>
    <h1>Garbage Collection Architecture Notes</h1>
    <p class="author">By Elena Rostova</p>
    <span class="date">Posted on December 02, 2025</span>
    <article><p>Generational hypothesis remains central to low-latency runtimes...</p></article>
    </body></html>"""

    write_page(d, "home", html_home, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "post1", html_p1, {"url": p2["url"], "final_url": p2["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "post2", html_p2, {"url": p3["url"], "final_url": p3["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 4. Major Archetype: News
# ===========================================================================
def make_news() -> None:
    d = FIXTURES_DIR / "archetype_news"
    p1 = {"url": "https://chronicle-times.com/", "final_url": "https://chronicle-times.com/", "status_code": 200, "slug": "home", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p2 = {"url": "https://chronicle-times.com/news/climate-accord-signed", "final_url": "https://chronicle-times.com/news/climate-accord-signed", "status_code": 200, "slug": "news1", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p3 = {"url": "https://chronicle-times.com/news/tech-antitrust-ruling", "final_url": "https://chronicle-times.com/news/tech-antitrust-ruling", "status_code": 200, "slug": "news2", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    write_manifest(d, base_manifest("chronicle-times.com", [p1, p2, p3]))

    html_home = """<!DOCTYPE html><html><head><title>The Chronicle Times — Breaking News</title></head><body>
    <h1>The Chronicle Times</h1><p>Top national and world news updates.</p>
    <nav><a href="/news/climate-accord-signed">World</a><a href="/news/tech-antitrust-ruling">Business</a></nav>
    </body></html>"""

    html_n1 = """<!DOCTYPE html><html><head><title>International Climate Accord Finalized</title>
    <script type="application/ld+json">{"@context": "https://schema.org", "@type": "NewsArticle", "headline": "International Climate Accord Finalized"}</script>
    </head><body>
    <h1>International Climate Accord Finalized</h1>
    <div class="byline">By Sarah Jenkins, Senior Diplomatic Correspondent</div>
    <p class="date">Published March 15, 2026</p>
    <p>Delegates gathered in Geneva to ratify the landmark treaty...</p>
    </body></html>"""

    html_n2 = """<!DOCTYPE html><html><head><title>Court Issues Decisive Antitrust Ruling</title>
    <script type="application/ld+json">{"@context": "https://schema.org", "@type": "NewsArticle", "headline": "Court Issues Decisive Antitrust Ruling"}</script>
    </head><body>
    <h1>Court Issues Decisive Antitrust Ruling</h1>
    <div class="byline">By Michael Chang, Technology Reporter</div>
    <span class="published">Published March 16, 2026</span>
    <p>The federal appeals court affirmed regulatory authority in digital distribution...</p>
    </body></html>"""

    write_page(d, "home", html_home, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "news1", html_n1, {"url": p2["url"], "final_url": p2["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "news2", html_n2, {"url": p3["url"], "final_url": p3["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 5. Major Archetype: Docs
# ===========================================================================
def make_docs() -> None:
    d = FIXTURES_DIR / "archetype_docs"
    p1 = {"url": "https://libdoc.dev/docs/getting-started", "final_url": "https://libdoc.dev/docs/getting-started", "status_code": 200, "slug": "start", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p2 = {"url": "https://libdoc.dev/docs/v2.1/api-reference", "final_url": "https://libdoc.dev/docs/v2.1/api-reference", "status_code": 200, "slug": "api", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p3 = {"url": "https://libdoc.dev/docs/guide/architecture", "final_url": "https://libdoc.dev/docs/guide/architecture", "status_code": 200, "slug": "arch", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    write_manifest(d, base_manifest("libdoc.dev", [p1, p2, p3]))

    html_p1 = """<!DOCTYPE html><html><head><title>Getting Started - LibDoc Documentation</title></head><body>
    <h1>Installation and Quickstart</h1>
    <pre><code class="language-bash">npm install @libdoc/core</code></pre>
    <p>Initialize the client as shown below:</p>
    <pre><code>const client = new LibDoc({ apiKey: "..." });</code></pre>
    </body></html>"""

    html_p2 = """<!DOCTYPE html><html><head><title>v2.1 API Reference - LibDoc</title></head><body>
    <h1>API Endpoints Reference v2.1</h1>
    <pre><code>GET /v2.1/sessions/verify</code></pre>
    <pre><code>POST /v2.1/events/dispatch</code></pre>
    </body></html>"""

    html_p3 = """<!DOCTYPE html><html><head><title>Architecture Guide - LibDoc</title></head><body>
    <h1>Core Architecture & Runtime Model</h1>
    <pre><code>class WorkerPool { constructor(size) { ... } }</code></pre>
    </body></html>"""

    write_page(d, "start", html_p1, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "api", html_p2, {"url": p2["url"], "final_url": p2["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "arch", html_p3, {"url": p3["url"], "final_url": p3["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 6. Major Archetype: Portfolio
# ===========================================================================
def make_portfolio() -> None:
    d = FIXTURES_DIR / "archetype_portfolio"
    p1 = {"url": "https://maya-design.com/", "final_url": "https://maya-design.com/", "status_code": 200, "slug": "home", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p2 = {"url": "https://maya-design.com/portfolio/brand-identity-craft", "final_url": "https://maya-design.com/portfolio/brand-identity-craft", "status_code": 200, "slug": "work1", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    write_manifest(d, base_manifest("maya-design.com", [p1, p2]))

    html_home = """<!DOCTYPE html><html><head><title>Maya Lin — Independent Art Director & Designer</title>
    <script type="application/ld+json">{"@context": "https://schema.org", "@type": "Person", "name": "Maya Lin", "jobTitle": "Art Director"}</script>
    </head><body>
    <h1>Selected Works & Design Portfolio</h1>
    <p>A showcase of editorial, visual design, and brand identity projects.</p>
    <nav><a href="/portfolio/brand-identity-craft">View Case Study</a></nav>
    </body></html>"""

    html_p2 = """<!DOCTYPE html><html><head><title>Brand Identity Case Study - Maya Lin</title>
    <script type="application/ld+json">{"@context": "https://schema.org", "@type": "CreativeWork", "name": "Brand Identity Craft"}</script>
    </head><body>
    <h1>Brand Identity Craft — Case Study</h1>
    <p>Comprehensive visual identity system and gallery showcase for artisan studio.</p>
    </body></html>"""

    write_page(d, "home", html_home, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "work1", html_p2, {"url": p2["url"], "final_url": p2["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 7. Major Archetype: Local Business
# ===========================================================================
def make_local_business() -> None:
    d = FIXTURES_DIR / "archetype_local_business"
    p1 = {"url": "https://baydentalcare.com/", "final_url": "https://baydentalcare.com/", "status_code": 200, "slug": "home", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p2 = {"url": "https://baydentalcare.com/contact", "final_url": "https://baydentalcare.com/contact", "status_code": 200, "slug": "contact", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    write_manifest(d, base_manifest("baydentalcare.com", [p1, p2]))

    html_home = """<!DOCTYPE html><html><head><title>Bay Dental Care — Family Dentistry</title>
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "Dentist", "name": "Bay Dental Care",
     "telephone": "(415) 555-0199", "address": "742 Evergreen Terrace, Springfield, OR"}
    </script></head><body>
    <h1>Welcome to Bay Dental Care</h1>
    <p>Compassionate dental health services in your neighborhood.</p>
    <a href="/contact">Visit Our Clinic</a>
    </body></html>"""

    html_contact = """<!DOCTYPE html><html><head><title>Location & Hours - Bay Dental Care</title></head><body>
    <h1>Clinic Hours & Location</h1>
    <p>Address: 742 Evergreen Terrace, Springfield, OR</p>
    <p>Phone: (415) 555-0199</p>
    <p>Hours: Mon - Fri 8:00am - 5:00pm</p>
    <p>Sat: 9:00am - 1:00pm | Sun: Closed</p>
    </body></html>"""

    write_page(d, "home", html_home, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "contact", html_contact, {"url": p2["url"], "final_url": p2["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 8. Major Archetype: Corporate
# ===========================================================================
def make_corporate() -> None:
    d = FIXTURES_DIR / "archetype_corporate"
    pages = []
    for i in range(1, 6):
        pages.append({
            "url": f"https://nextera-holdings.com/page{i}",
            "final_url": f"https://nextera-holdings.com/page{i}",
            "status_code": 200, "slug": f"page{i}", "elapsed_s": 0.1, "redirect_count": 0, "error": None
        })
    write_manifest(d, base_manifest("nextera-holdings.com", pages))

    # Dense institutional navigation links
    nav_links = "".join([f'<a href="/dept/{j}">Division {j}</a>' for j in range(15)])

    html_corp = f"""<!DOCTYPE html><html><head><title>Nextera Holdings Inc. — Global Enterprise</title>
    <script type="application/ld+json">{{"@context": "https://schema.org", "@type": "Corporation", "name": "Nextera Holdings Inc."}}</script>
    </head><body>
    <header><nav>{nav_links}</nav></header>
    <h1>Nextera Holdings Enterprise Overview</h1>
    <p>Corporate governance, investor relations, board disclosures, and annual ESG reports.</p>
    <footer><nav>{nav_links}</nav></footer>
    </body></html>"""

    for i in range(1, 6):
        write_page(d, f"page{i}", html_corp, {"url": pages[i-1]["url"], "final_url": pages[i-1]["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 9. Ambiguous Site: Developer Tool with balanced SaaS + Docs signals
# ===========================================================================
def make_ambiguous() -> None:
    d = FIXTURES_DIR / "archetype_ambiguous"
    p1 = {"url": "https://devcloud.io/", "final_url": "https://devcloud.io/", "status_code": 200, "slug": "home", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p2 = {"url": "https://devcloud.io/pricing", "final_url": "https://devcloud.io/pricing", "status_code": 200, "slug": "pricing", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p3 = {"url": "https://devcloud.io/docs/quickstart", "final_url": "https://devcloud.io/docs/quickstart", "status_code": 200, "slug": "docs_quickstart", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p4 = {"url": "https://devcloud.io/docs/v2.1/api-reference", "final_url": "https://devcloud.io/docs/v2.1/api-reference", "status_code": 200, "slug": "docs_api", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p5 = {"url": "https://devcloud.io/docs/v2.1/cli-guide", "final_url": "https://devcloud.io/docs/v2.1/cli-guide", "status_code": 200, "slug": "docs_cli", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    write_manifest(d, base_manifest("devcloud.io", [p1, p2, p3, p4, p5]))

    html_home = """<!DOCTYPE html><html><head><title>DevCloud — Cloud Infrastructure Platform</title></head><body>
    <h1>Serverless Infrastructure Automation</h1>
    <a href="/demo" class="btn">Request a demo</a>
    <a href="/docs/quickstart">Read the documentation</a>
    </body></html>"""

    html_pricing = """<!DOCTYPE html><html><head><title>Pricing Plans - DevCloud</title></head><body>
    <h1>Flexible Cloud Plans</h1>
    <p>$49 per user per month. Includes API integration, webhook endpoints, and automated workflows.</p>
    <a href="/trial">Start free trial</a>
    </body></html>"""

    html_doc1 = """<!DOCTYPE html><html><head><title>Quickstart - DevCloud Docs</title></head><body>
    <h1>Getting Started with DevCloud</h1>
    <pre><code class="bash">curl -s https://devcloud.io/install.sh | bash</code></pre>
    <pre><code>devcloud init --cluster production</code></pre>
    </body></html>"""

    html_doc2 = """<!DOCTYPE html><html><head><title>API Reference - DevCloud Docs</title></head><body>
    <h1>DevCloud REST API Reference</h1>
    <pre><code>POST /v2.1/clusters/deploy</code></pre>
    </body></html>"""

    html_doc3 = """<!DOCTYPE html><html><head><title>CLI Reference - DevCloud Docs</title></head><body>
    <h1>Command Line Tool v2.1</h1>
    <pre><code>devcloud clusters list --format json</code></pre>
    </body></html>"""

    write_page(d, "home", html_home, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "pricing", html_pricing, {"url": p2["url"], "final_url": p2["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "docs_quickstart", html_doc1, {"url": p3["url"], "final_url": p3["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "docs_api", html_doc2, {"url": p4["url"], "final_url": p4["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "docs_cli", html_doc3, {"url": p5["url"], "final_url": p5["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 10. Unknown Case: Minimal / Generic Landing Page with No Diagnostic Signals
# ===========================================================================
def make_unknown() -> None:
    d = FIXTURES_DIR / "archetype_unknown"
    p1 = {"url": "https://mystery-project.org/", "final_url": "https://mystery-project.org/", "status_code": 200, "slug": "home", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    write_manifest(d, base_manifest("mystery-project.org", [p1]))

    html = """<!DOCTYPE html><html><head><title>Project Mystery</title></head><body>
    <h1>Project Mystery</h1>
    <p>Welcome to our interim landing page. We are currently working quietly in stealth mode.</p>
    <p>Check back later for future updates. Inquiries: contact@mystery-project.org</p>
    </body></html>"""

    write_page(d, "home", html, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 11. Mixed Case: Storefront + SaaS Subscription Platform (e.g. Shopify model)
# ===========================================================================
def make_mixed() -> None:
    d = FIXTURES_DIR / "archetype_mixed"
    p1 = {"url": "https://commercecloud.net/", "final_url": "https://commercecloud.net/", "status_code": 200, "slug": "home", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p2 = {"url": "https://commercecloud.net/products/pos-terminal-pro", "final_url": "https://commercecloud.net/products/pos-terminal-pro", "status_code": 200, "slug": "product", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p3 = {"url": "https://commercecloud.net/pricing", "final_url": "https://commercecloud.net/pricing", "status_code": 200, "slug": "pricing", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p4 = {"url": "https://commercecloud.net/cart", "final_url": "https://commercecloud.net/cart", "status_code": 200, "slug": "cart", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    write_manifest(d, base_manifest("commercecloud.net", [p1, p2, p3, p4]))

    html_home = """<!DOCTYPE html><html><head><title>CommerceCloud — Omnichannel Retail Platform</title></head><body>
    <h1>Run Your Entire Retail Business</h1>
    <nav><a href="/products/pos-terminal-pro">Hardware Store</a><a href="/pricing">Software Plans</a><a href="/cart">Cart</a></nav>
    </body></html>"""

    html_prod = """<!DOCTYPE html><html><head><title>POS Terminal Pro - Hardware</title>
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "Product", "name": "POS Terminal Pro",
     "offers": {"@type": "Offer", "price": "299.00", "priceCurrency": "USD"}}
    </script></head><body>
    <h1>POS Terminal Pro</h1>
    <p>Price: $299.00 USD</p>
    <form action="/cart/add" method="post"><button type="submit" class="btn add-to-cart">Add to Cart</button></form>
    </body></html>"""

    html_pricing = """<!DOCTYPE html><html><head><title>Software Subscription Plans - CommerceCloud</title>
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "CommerceCloud Platform"}
    </script></head><body>
    <h1>Monthly Cloud Plans</h1>
    <p>Software subscriptions starting at $79 per month. Includes inventory API, analytics dashboard, and automated workflows.</p>
    <a href="/demo">Request a demo</a>
    <a href="/trial">Start free trial</a>
    </body></html>"""

    html_cart = """<!DOCTYPE html><html><head><title>Cart</title></head><body>
    <h1>Cart</h1>
    <form action="/checkout"><button type="submit" class="buy-now">Checkout</button></form>
    </body></html>"""

    write_page(d, "home", html_home, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "product", html_prod, {"url": p2["url"], "final_url": p2["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "pricing", html_pricing, {"url": p3["url"], "final_url": p3["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "cart", html_cart, {"url": p4["url"], "final_url": p4["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 12. False-Positive Guard: Local Business (HQ Address only, no hours/schema)
# ===========================================================================
def make_fp_local_business() -> None:
    d = FIXTURES_DIR / "archetype_fp_local_business"
    p1 = {"url": "https://globalscale-ai.com/", "final_url": "https://globalscale-ai.com/", "status_code": 200, "slug": "home", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p2 = {"url": "https://globalscale-ai.com/contact", "final_url": "https://globalscale-ai.com/contact", "status_code": 200, "slug": "contact", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p3 = {"url": "https://globalscale-ai.com/pricing", "final_url": "https://globalscale-ai.com/pricing", "status_code": 200, "slug": "pricing", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    write_manifest(d, base_manifest("globalscale-ai.com", [p1, p2, p3]))

    html_home = """<!DOCTYPE html><html><head><title>GlobalScale AI — Distributed Machine Learning</title>
    <script type="application/ld+json">{"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "GlobalScale"}</script>
    </head><body>
    <h1>Distributed ML Infrastructure</h1>
    <a href="/demo">Request a demo</a>
    </body></html>"""

    html_contact = """<!DOCTYPE html><html><head><title>Contact GlobalScale</title></head><body>
    <h1>Corporate Contact Information</h1>
    <p>Mailing Address: 500 Howard Street, Suite 800, San Francisco, CA</p>
    <p>Press inquiries: press@globalscale-ai.com</p>
    </body></html>"""

    html_pricing = """<!DOCTYPE html><html><head><title>Pricing - GlobalScale</title></head><body>
    <h1>Enterprise Pricing</h1>
    <p>Per-seat licenses with dedicated support.</p>
    <a href="/demo">Schedule a demo</a>
    </body></html>"""

    write_page(d, "home", html_home, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "contact", html_contact, {"url": p2["url"], "final_url": p2["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "pricing", html_pricing, {"url": p3["url"], "final_url": p3["final_url"], "status_code": 200, "response_headers": {}})


# ===========================================================================
# 13. False-Positive Guard: Corporate (Yoast/WordPress Organization & WebSite schema)
# ===========================================================================
def make_fp_corporate() -> None:
    d = FIXTURES_DIR / "archetype_fp_corporate"
    p1 = {"url": "https://sam-writes-code.com/", "final_url": "https://sam-writes-code.com/", "status_code": 200, "slug": "home", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    p2 = {"url": "https://sam-writes-code.com/blog/my-favorite-python-features", "final_url": "https://sam-writes-code.com/blog/my-favorite-python-features", "status_code": 200, "slug": "post1", "elapsed_s": 0.1, "redirect_count": 0, "error": None}
    write_manifest(d, base_manifest("sam-writes-code.com", [p1, p2]))

    # Standard WordPress / Yoast SEO boilerplate injected into every personal blog
    html_home = """<!DOCTYPE html><html><head><title>Sam Writes Code — Personal Engineering Log</title>
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@graph": [
      {"@type": "WebSite", "name": "Sam Writes Code", "url": "https://sam-writes-code.com/"},
      {"@type": "Organization", "name": "Sam Writes Code", "url": "https://sam-writes-code.com/"}
    ]}
    </script></head><body>
    <h1>Sam Writes Code</h1>
    <p>Personal thoughts on programming languages and developer tooling.</p>
    <nav><a href="/blog/my-favorite-python-features">Latest Post</a></nav>
    </body></html>"""

    html_p1 = """<!DOCTYPE html><html><head><title>My Favorite Python 3.12 Features</title>
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "BlogPosting", "headline": "My Favorite Python 3.12 Features"}
    </script></head><body>
    <h1>My Favorite Python 3.12 Features</h1>
    <div class="byline">Written by Sam Peterson</div>
    <span class="date">Published January 14, 2026</span>
    <article><p>Type parameter syntax and improved error messages have significantly improved ergonomics...</p></article>
    </body></html>"""

    write_page(d, "home", html_home, {"url": p1["url"], "final_url": p1["final_url"], "status_code": 200, "response_headers": {}})
    write_page(d, "post1", html_p1, {"url": p2["url"], "final_url": p2["final_url"], "status_code": 200, "response_headers": {}})


def generate_all() -> None:
    make_ecommerce()
    make_saas()
    make_content()
    make_news()
    make_docs()
    make_portfolio()
    make_local_business()
    make_corporate()
    make_ambiguous()
    make_unknown()
    make_mixed()
    make_fp_local_business()
    make_fp_corporate()
    print("All archetype fixtures generated successfully.")


if __name__ == "__main__":
    generate_all()
