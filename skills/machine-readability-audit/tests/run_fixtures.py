#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_fixtures.py -- Runs all 6 checks against all test fixtures and reports results.

Usage:
    python run_fixtures.py

Exit code 0 = all assertions pass.
Exit code 1 = one or more assertions fail.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]  # ADB/
REACH_CHECKS = REPO_ROOT / "skills/site-acquisition/scripts/reach_checks.py"
CHECK_NOINDEX = REPO_ROOT / "skills/machine-readability-audit/scripts/check_noindex.py"
CHECK_D2 = REPO_ROOT / "skills/machine-readability-audit/scripts/check_d2.py"
CHECK_D1 = REPO_ROOT / "skills/machine-readability-audit/scripts/check_d1.py"
CHECK_D3 = REPO_ROOT / "skills/machine-readability-audit/scripts/check_d3.py"
CHECK_E1 = REPO_ROOT / "skills/machine-readability-audit/scripts/check_e1.py"
CHECK_E2 = REPO_ROOT / "skills/machine-readability-audit/scripts/check_e2.py"
CHECK_E3 = REPO_ROOT / "skills/machine-readability-audit/scripts/check_e3.py"
CHECK_E4 = REPO_ROOT / "skills/machine-readability-audit/scripts/check_e4.py"
FIXTURES = Path(__file__).parent / "fixtures"


def run_reach(fixture: Path, checks: list[str]) -> list[dict]:
    manifest = fixture / "crawl_manifest.json"
    corpus_dir = fixture / "pages"
    result = subprocess.run(
        [sys.executable, str(REACH_CHECKS),
         str(manifest),
         "--checks", *checks,
         "--corpus-dir", str(corpus_dir)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [STDERR] {result.stderr[:300]}", file=sys.stderr)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_noindex(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_NOINDEX), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_d2(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    result = subprocess.run(
        [sys.executable, str(CHECK_D2), str(corpus_dir)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_d1(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_D1), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_e2(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_E2), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_e3(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_E3), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_d3(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_D3), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_e1(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_E1), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_e4(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_E4), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []



def check_fields(findings: list[dict]) -> list[str]:
    """Verify all required contract fields are present in every finding."""
    required = {
        "id", "check_id", "page_url", "root_cause", "evidence",
        "raw_severity_class", "confidence", "mechanism",
        "false_positive_guard", "verification_method",
    }
    errors = []
    for f in findings:
        missing = required - f.keys()
        if missing:
            errors.append(f"  Finding {f.get('id', '?')} missing fields: {sorted(missing)}")
    return errors


def assert_findings(label: str, findings: list[dict], expected_check_ids: list[str], min_count: int = 1) -> bool:  # noqa: E501
    field_errors = check_fields(findings)
    if field_errors:
        print(f"  FAIL [{label}] Contract field errors:")
        for e in field_errors:
            print(e)
        return False

    found_ids = [f["check_id"] for f in findings]
    for cid in expected_check_ids:
        matching = [f for f in findings if f["check_id"] == cid]
        if len(matching) < min_count:
            print(f"  FAIL [{label}] Expected >={min_count} {cid} finding(s), got {len(matching)}")
            return False
    return True


def assert_zero(label: str, findings: list[dict]) -> bool:
    if findings:
        ids = [f.get("id") for f in findings]
        print(f"  FAIL [{label}] Expected 0 findings, got {len(findings)}: {ids}")
        return False
    return True


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

results: list[tuple[str, bool]] = []

def test(name: str, passed: bool) -> None:
    status = "PASS" if passed else "FAIL"
    print(f"  {status}  {name}")
    results.append((name, passed))


print("\n=== Stage 3 Fixture Tests ===\n")

# --- R1: All AI agents blocked (high severity) ---
print("[R1-blocked] All AI agents blocked at root")
fx = FIXTURES / "r1_blocked"
findings = run_reach(fx, ["R1"])
ok = assert_findings("R1-blocked", findings, ["R1"])
if ok:
    sev = findings[0]["raw_severity_class"]
    scope = findings[0]["evidence"]["scope"]
    ok = sev == "high" and scope == "all_access"
    if not ok:
        print(f"  FAIL [R1-blocked] Expected severity=high/scope=all_access, got {sev}/{scope}")
test("R1 fires with high severity when all AI bots blocked at root", ok)

# --- R1: Training-only bots blocked (medium severity) ---
print("\n[R1-training-only] Only training bots blocked")
fx = FIXTURES / "r1_training_only"
findings = run_reach(fx, ["R1"])
ok = assert_findings("R1-training-only", findings, ["R1"])
if ok:
    sev = findings[0]["raw_severity_class"]
    scope = findings[0]["evidence"]["scope"]
    ok = sev == "medium" and scope == "training_bots_only"
    if not ok:
        print(f"  FAIL [R1-training-only] Expected severity=medium/scope=training_bots_only, got {sev}/{scope}")
test("R1 fires with medium severity when only training bots blocked", ok)

# --- R3: No sitemap ---
print("\n[R3-no-sitemap] Sitemap absent")
fx = FIXTURES / "r3_no_sitemap"
findings = run_reach(fx, ["R3"])
ok = assert_findings("R3-no-sitemap", findings, ["R3"])
if ok:
    ev_type = findings[0]["evidence"]["type"]
    ok = ev_type == "sitemap_absent"
    if not ok:
        print(f"  FAIL [R3-no-sitemap] Expected evidence.type=sitemap_absent, got {ev_type}")
test("R3 fires with sitemap_absent evidence when sitemap missing", ok)

# --- R4: noindex on substantive page fires, login page excluded ---
print("\n[R4-noindex] noindex on product page (should fire), login page (should not)")
fx = FIXTURES / "r4_noindex"
findings = run_noindex(fx)
# Should have exactly 1 finding (product page), NOT the login page
ok = len(findings) == 1
if not ok:
    print(f"  FAIL [R4-noindex] Expected 1 finding, got {len(findings)}: {[f.get('page_url') for f in findings]}")
else:
    ok = assert_findings("R4-noindex", findings, ["R4"])
    if ok:
        ok = "login" not in findings[0]["page_url"]
        if not ok:
            print(f"  FAIL [R4-noindex] Finding was on login page, should not fire")
test("R4 fires on product page noindex, suppressed on login page", ok)

# --- R4: noindex via X-Robots-Tag header ---
print("\n[R4-header-noindex] noindex via HTTP header")
fx = FIXTURES / "r4_header_noindex"
findings = run_noindex(fx)
ok = assert_findings("R4-header-noindex", findings, ["R4"])
if ok:
    source = findings[0]["evidence"]["source"]
    ok = "X-Robots-Tag" in source
    if not ok:
        print(f"  FAIL [R4-header-noindex] Expected X-Robots-Tag source, got {source}")
test("R4 detects noindex via X-Robots-Tag header", ok)

# --- R5: Canonical/OG conflict ---
print("\n[R5-canonical-conflict] canonical vs og:url conflict")
fx = FIXTURES / "r5_canonical_conflict"
findings = run_reach(fx, ["R5"])
ok = assert_findings("R5-canonical-conflict", findings, ["R5"])
if ok:
    ev_type = findings[0]["evidence"]["type"]
    ok = ev_type == "canonical_og_conflict"
    if not ok:
        print(f"  FAIL [R5-canonical-conflict] Expected evidence.type=canonical_og_conflict, got {ev_type}")
test("R5 fires on canonical/og:url conflict (after normalization still different)", ok)

# --- R5: 4xx internal links ---
print("\n[R5-4xx-link] Internally-linked page returns 404")
fx = FIXTURES / "r5_4xx_link"
findings = run_reach(fx, ["R5"])
ok = assert_findings("R5-4xx-link", findings, ["R5"])
if ok:
    ev_type = findings[0]["evidence"]["type"]
    ok = ev_type == "internal_link_4xx"
    if not ok:
        print(f"  FAIL [R5-4xx-link] Expected evidence.type=internal_link_4xx, got {ev_type}")
test("R5 detects 4xx on internally-linked page", ok)

# --- D2: Content image without alt ---
print("\n[D2-images] Content-bearing image without alt text")
fx = FIXTURES / "d2_images"
findings = run_d2(fx)
ok = len(findings) >= 1
if not ok:
    print(f"  FAIL [D2-images] Expected >=1 finding, got {len(findings)}")
else:
    ok = assert_findings("D2-images", findings, ["D2"])
    if ok:
        # Verify logo image (has alt) did NOT fire, and spacer (1x1) did NOT fire
        fired_srcs = [f["evidence"].get("img_src", "") for f in findings]
        logo_fired = any("logo" in s for s in fired_srcs)
        spacer_fired = any("spacer" in s for s in fired_srcs)
        if logo_fired:
            print(f"  FAIL [D2-images] Logo image (has alt) incorrectly fired")
            ok = False
        if spacer_fired:
            print(f"  FAIL [D2-images] Spacer image (decorative) incorrectly fired")
            ok = False
test("D2 fires on content image without alt, suppresses logo/spacer/decorative", ok)

# --- D1: JS-render gap ---
print("\n[D1-js-gap] SPA shell in raw HTML vs full rendered DOM")
fx = FIXTURES / "d1_js_gap"
findings = run_d1(fx)
ok = assert_findings("D1-js-gap", findings, ["D1"])
if ok:
    ev = findings[0]["evidence"]
    ok = ev.get("missing_word_count", 0) > 300 and ev.get("missing_word_ratio", 0.0) > 0.40
    if not ok:
        print(f"  FAIL [D1-js-gap] Expected missing_words>300 and ratio>0.40, got {ev}")
test("D1 fires on JS-render gap (>40% missing words AND >300 gap)", ok)

# --- E2: JSON-LD wrong price contradiction ---
print("\n[E2-wrong-price] JSON-LD price ($19.99) vs visible price ($49.99)")
fx = FIXTURES / "e2_wrong_price"
findings = run_e2(fx)
ok = assert_findings("E2-wrong-price", findings, ["E2"])
if ok:
    ev = findings[0]["evidence"]
    ok = ev.get("type") == "structured_data_contradiction" and ev.get("field") == "price"
    if not ok:
        print(f"  FAIL [E2-wrong-price] Expected price contradiction, got {ev}")
test("E2 fires on JSON-LD price contradiction against visible text", ok)

# --- E2: Microdata valid & matching ---
print("\n[E2-microdata] Microdata product with matching visible price")
fx = FIXTURES / "e2_microdata"
findings = run_e2(fx)
ok = assert_zero("E2-microdata", findings)
test("E2 passes clean Microdata without false contradictions", ok)

# --- E2: RDFa valid & matching ---
print("\n[E2-rdfa] RDFa product with matching visible price")
fx = FIXTURES / "e2_rdfa"
findings = run_e2(fx)
ok = assert_zero("E2-rdfa", findings)
test("E2 passes clean RDFa without false contradictions", ok)

# --- E2: Clean structured data ---
print("\n[E2-clean] Clean JSON-LD product with matching visible price")
fx = FIXTURES / "e2_clean"
findings = run_e2(fx)
ok = assert_zero("E2-clean", findings)
test("E2 passes clean structured data without findings", ok)

# --- E3: Quotability gap ---
print("\n[E3-quotability] SaaS site with evasive marketing pricing text")
fx = FIXTURES / "e3_quotability"
findings = run_e3(fx)
ok = assert_findings("E3-quotability", findings, ["E3"])
if ok:
    ev = findings[0]["evidence"]
    ok = ev.get("type") == "quotability_gap"
    if not ok:
        print(f"  FAIL [E3-quotability] Expected quotability_gap evidence, got {ev}")
test("E3 fires on canonical question quotability gap with best passage and failure reason", ok)

# --- D3: Semantic structure absent ---
print("\n[D3-semantic-structure] Missing h1, broken heading hierarchy, missing main landmark")
import tempfile
with tempfile.TemporaryDirectory() as tmp_d3:
    tmp_d3_path = Path(tmp_d3)
    p_dir = tmp_d3_path / "pages" / "page1"
    p_dir.mkdir(parents=True)

    body_text = (
        "This is a substantive article discussing various important concepts. "
        "It contains enough words to exceed the minimum threshold for semantic evaluation. "
        "Here we discuss architecture, reliability, maintainability, and security across modern distributed software systems. "
        "Furthermore, we analyze database indexing strategies, cache invalidation protocols, and consistency models. "
        "Notice that h2 jumps directly to h4, skipping h3 downwards in hierarchy. "
        "Additionally, there is no h1 tag anywhere on this document, and neither a main tag nor a role='main' attribute is present. "
    ) * 2

    d3_html = (
        "<!DOCTYPE html><html><head><title>Semantic Test</title></head><body>"
        "<header><nav><a href='/'>Home</a></nav></header>"
        "<div>"
        "<h2>Introduction</h2>"
        f"<p>{body_text}</p>"
        "<h4>Deep Nested Topic</h4>"
        "<p>Further discussion on distributed system consensus algorithms like Raft and Paxos.</p>"
        "</div>"
        "<footer><p>Footer content</p></footer>"
        "</body></html>"
    )
    (p_dir / "raw.html").write_text(d3_html, encoding="utf-8")
    (p_dir / "text.txt").write_text(body_text, encoding="utf-8")
    (p_dir / "meta.json").write_text(json.dumps({"url": "https://example.com/article", "status_code": 200, "title": "Semantic Test"}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "example.com",
        "base_url": "https://example.com",
        "crawled_pages": [{"url": "https://example.com/article", "slug": "page1", "status_code": 200}],
    }
    (tmp_d3_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    d3_findings = run_d3(tmp_d3_path)
    d3_cids = [f["check_id"] for f in d3_findings]
    d3_types = [f["evidence"]["type"] for f in d3_findings]
    d3_sevs = [f["raw_severity_class"] for f in d3_findings]

    d3_ok = (
        len(d3_findings) == 3
        and all(cid == "D3" for cid in d3_cids)
        and "missing_h1" in d3_types
        and "missing_main_landmark" in d3_types
        and "broken_heading_hierarchy" in d3_types
        and all(s == "low" for s in d3_sevs)
    )
    if not d3_ok:
        print(f"  FAIL [D3] Expected 3 D3 low-severity findings, got {d3_findings}")
    test("D3 flags missing h1, missing main landmark, and broken heading hierarchy with minor/low severity", d3_ok)

# --- E1: Missing structured data for inferred archetype ---
print("\n[E1-structured-data-archetype] Inferred archetype diagnostic pages lacking schema")
with tempfile.TemporaryDirectory() as tmp_e1:
    tmp_e1_path = Path(tmp_e1)
    p_dir = tmp_e1_path / "pages" / "product_item"
    p_dir.mkdir(parents=True)

    e1_html = (
        "<!DOCTYPE html><html><head><title>Premium Widget | Store</title></head><body>"
        "<main><h1>Premium Widget</h1>"
        "<p>Price: $49.99</p>"
        "<button>Add to Cart</button>"
        "<p>High quality precision widget with extensive durability and lifetime replacement guarantee.</p>"
        "</main></body></html>"
    )
    (p_dir / "raw.html").write_text(e1_html, encoding="utf-8")
    (p_dir / "meta.json").write_text(json.dumps({"url": "https://store.example.com/products/widget-1", "status_code": 200, "title": "Premium Widget"}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "store.example.com",
        "base_url": "https://store.example.com",
        "crawled_pages": [{"url": "https://store.example.com/products/widget-1", "slug": "product_item", "status_code": 200}],
    }
    (tmp_e1_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    e1_findings = run_e1(tmp_e1_path)
    e1_ok = len(e1_findings) == 1 and e1_findings[0]["check_id"] == "E1"
    if e1_ok:
        ev = e1_findings[0]["evidence"]
        vm = e1_findings[0]["verification_method"]
        e1_ok = (
            "diagnostic pages crawled" in ev.get("evidence_summary", "")
            and ev.get("inferred_archetype") == "ecommerce"
            and "Product" in ev.get("expected_schema_types", [])
            and "application/ld\\+json" in vm
            and "itemtype" in vm
            and "typeof" in vm
        )
    if not e1_ok:
        print(f"  FAIL [E1] Expected 1 E1 finding for unannotated product page, got {e1_findings}")
    test("E1 detects missing Product schema on ecommerce product pages with multi-syntax verification", e1_ok)

# --- E1: Related-but-insufficient schema does NOT suppress finding ---
print("\n[E1-insufficient-schema] Related schema (Organization/ItemList) does not suppress Product requirement")
with tempfile.TemporaryDirectory() as tmp_e1_insuff:
    tmp_path = Path(tmp_e1_insuff)
    p_dir = tmp_path / "pages" / "prod"
    p_dir.mkdir(parents=True)

    # Page has Organization and ItemList schema, but lacks Product/IndividualProduct
    html_with_org = (
        "<!DOCTYPE html><html><head><title>Gadget | Store</title>"
        "<script type='application/ld+json'>{\"@context\": \"https://schema.org\", \"@type\": \"Organization\", \"name\": \"Store Corp\"}</script>"
        "<script type='application/ld+json'>{\"@context\": \"https://schema.org\", \"@type\": \"ItemList\", \"name\": \"Nav Menu\"}</script>"
        "</head><body>"
        "<main><h1>Super Gadget</h1><p>Price: $99.00</p><button>Add to Cart</button></main>"
        "</body></html>"
    )
    (p_dir / "raw.html").write_text(html_with_org, encoding="utf-8")
    (p_dir / "meta.json").write_text(json.dumps({"url": "https://store.example.com/products/gadget", "status_code": 200}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "store.example.com",
        "base_url": "https://store.example.com",
        "crawled_pages": [{"url": "https://store.example.com/products/gadget", "slug": "prod", "status_code": 200}],
    }
    (tmp_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    insuff_findings = run_e1(tmp_path)
    # Organization/ItemList MUST NOT suppress the product requirement
    insuff_ok = len(insuff_findings) == 1 and insuff_findings[0]["check_id"] == "E1"
    if not insuff_ok:
        print(f"  FAIL [E1-insufficient] Expected finding not suppressed by Organization/ItemList, got: {insuff_findings}")
    test("E1 does NOT suppress finding when related-but-insufficient schema is present", insuff_ok)

# --- E1: Compliant schema produces zero findings ---
print("\n[E1-compliant-schema] Compliant Product schema produces 0 findings")
with tempfile.TemporaryDirectory() as tmp_e1_comp:
    tmp_path = Path(tmp_e1_comp)
    p_dir = tmp_path / "pages" / "prod"
    p_dir.mkdir(parents=True)

    html_with_prod = (
        "<!DOCTYPE html><html><head><title>Gadget | Store</title>"
        "<script type='application/ld+json'>{\"@context\": \"https://schema.org\", \"@type\": \"Product\", \"name\": \"Super Gadget\"}</script>"
        "</head><body>"
        "<main><h1>Super Gadget</h1><p>Price: $99.00</p><button>Add to Cart</button></main>"
        "</body></html>"
    )
    (p_dir / "raw.html").write_text(html_with_prod, encoding="utf-8")
    (p_dir / "meta.json").write_text(json.dumps({"url": "https://store.example.com/products/gadget", "status_code": 200}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "store.example.com",
        "base_url": "https://store.example.com",
        "crawled_pages": [{"url": "https://store.example.com/products/gadget", "slug": "prod", "status_code": 200}],
    }
    (tmp_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    comp_findings = run_e1(tmp_path)
    comp_ok = len(comp_findings) == 0
    if not comp_ok:
        print(f"  FAIL [E1-compliant] Expected 0 findings with valid Product schema, got: {comp_findings}")
    test("E1 produces 0 findings when diagnostic page contains expected Product schema", comp_ok)

# --- E4: Duplicate/missing titles and meta descriptions ---
print("\n[E4-meta-descriptions-titles] Duplicate titles and missing meta descriptions")
with tempfile.TemporaryDirectory() as tmp_e4:
    tmp_e4_path = Path(tmp_e4)
    p1_dir = tmp_e4_path / "pages" / "p1"
    p2_dir = tmp_e4_path / "pages" / "p2"
    p1_dir.mkdir(parents=True)
    p2_dir.mkdir(parents=True)

    text_content = "Substantive page content with more than eighty words for testing purposes. " * 10

    p1_html = (
        "<!DOCTYPE html><html><head><title>Company Overview | Acme</title></head><body>"
        "<main><h1>About Acme</h1><p>" + text_content + "</p></main></body></html>"
    )
    p2_html = (
        "<!DOCTYPE html><html><head><title>Company Overview | Acme</title></head><body>"
        "<main><h1>Leadership</h1><p>" + text_content + "</p></main></body></html>"
    )
    (p1_dir / "raw.html").write_text(p1_html, encoding="utf-8")
    (p1_dir / "text.txt").write_text(text_content, encoding="utf-8")
    (p1_dir / "meta.json").write_text(json.dumps({"url": "https://acme.example.com/about", "status_code": 200, "title": "Company Overview | Acme"}), encoding="utf-8")

    (p2_dir / "raw.html").write_text(p2_html, encoding="utf-8")
    (p2_dir / "text.txt").write_text(text_content, encoding="utf-8")
    (p2_dir / "meta.json").write_text(json.dumps({"url": "https://acme.example.com/leadership", "status_code": 200, "title": "Company Overview | Acme"}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "acme.example.com",
        "base_url": "https://acme.example.com",
        "crawled_pages": [
            {"url": "https://acme.example.com/about", "slug": "p1", "status_code": 200},
            {"url": "https://acme.example.com/leadership", "slug": "p2", "status_code": 200},
        ],
    }
    (tmp_e4_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    e4_findings = run_e4(tmp_e4_path)
    e4_types = [f["evidence"]["type"] for f in e4_findings]
    e4_sevs = [f["raw_severity_class"] for f in e4_findings]

    e4_ok = (
        "duplicate_titles" in e4_types
        and "missing_meta_descriptions" in e4_types
        and all(s == "low" for s in e4_sevs)
    )
    if not e4_ok:
        print(f"  FAIL [E4] Expected duplicate_titles and missing_meta_descriptions low-severity findings, got {e4_findings}")
    test("E4 detects duplicate titles and missing meta descriptions with minor/low severity", e4_ok)


# --- CLEAN: All checks must produce 0 findings ---
print("\n[clean] All checks against clean fixture — must produce 0 findings")
fx = FIXTURES / "clean"
all_clean_findings = []
all_clean_findings.extend(run_reach(fx, ["R1", "R2", "R3", "R5"]))
all_clean_findings.extend(run_noindex(fx))
all_clean_findings.extend(run_d2(fx))
all_clean_findings.extend(run_d1(fx))
all_clean_findings.extend(run_d3(fx))
all_clean_findings.extend(run_e1(fx))
all_clean_findings.extend(run_e2(fx))
all_clean_findings.extend(run_e3(fx))
all_clean_findings.extend(run_e4(fx))

clean_ok = assert_zero("clean", all_clean_findings)
test("CLEAN fixture produces 0 findings across all 12 deterministic checks (R1, R2, R3, R4, R5, D1, D2, D3, E1, E2, E3, E4)", clean_ok)

# --- E3 Tiny-Site Regression Tests ---
print("\n[e3-tiny-site-regression] Case A: Tiny clean ecommerce site (multi-page policy topics suppressed)")
e3_clean_findings = run_e3(FIXTURES / "clean")
case_a_ok = len(e3_clean_findings) == 0
test("Case A: Tiny clean site with is_tiny_site=True produces 0 E3 findings", case_a_ok)

print("\n[e3-tiny-site-regression] Case B: Tiny site with actual canonical answer evaluated")
import tempfile
with tempfile.TemporaryDirectory() as tmp_reg:
    tmp_reg_path = Path(tmp_reg)
    p_dir = tmp_reg_path / "pages" / "home"
    p_dir.mkdir(parents=True)

    # Tiny SaaS page that has a concrete product overview, but omits pricing
    saas_html = (
        "<!DOCTYPE html><html><head><title>Cloud Orchestrator</title></head><body>"
        "<header><h1>Cloud Orchestrator Platform</h1></header>"
        "<section>"
        "<p>Cloud Orchestrator is an enterprise cloud management platform designed to automate "
        "multi-cloud container deployments across AWS, Google Cloud, and Azure with unified policies. "
        "Our software enables engineering teams to manage infrastructure as code with zero manual provisioning.</p>"
        "</section>"
        "<section class='pricing'>"
        "<p>Contact our enterprise sales team for pricing information and custom quotes.</p>"
        "</section>"
        "</body></html>"
    )
    (p_dir / "raw.html").write_text(saas_html, encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "orchestrator.example.com",
        "base_url": "https://orchestrator.example.com",
        "is_tiny_site": True,
        "crawled_pages": [{"url": "https://orchestrator.example.com/", "slug": "home", "status_code": 200}],
    }
    (tmp_reg_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    res_b = subprocess.run(
        [sys.executable, str(CHECK_E3), str(tmp_reg_path / "pages"), "--manifest", str(tmp_reg_path / "crawl_manifest.json")],
        capture_output=True, text=True,
    )
    b_findings = json.loads(res_b.stdout) if res_b.stdout.strip() else []

    answered_topics = [f["evidence"]["topic"] for f in b_findings]
    overview_not_flagged = "product_overview" not in answered_topics
    pricing_flagged = "pricing_tiers" in answered_topics

    case_b_ok = overview_not_flagged and pricing_flagged
    if not case_b_ok:
        print(f"  FAIL Case B: overview_not_flagged={overview_not_flagged}, pricing_flagged={pricing_flagged}, flagged={answered_topics}")
    test("Case B: Tiny site evaluates applicable questions (answered=no finding, absent=finding)", case_b_ok)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*50}")
passed = sum(1 for _, ok in results if ok)
failed = len(results) - passed
print(f"Results: {passed}/{len(results)} passed, {failed} failed")

if failed > 0:
    print("\nFailed tests:")
    for name, ok in results:
        if not ok:
            print(f"  FAIL: {name}")
    sys.exit(1)
else:
    print("\nAll tests passed!")
    sys.exit(0)
