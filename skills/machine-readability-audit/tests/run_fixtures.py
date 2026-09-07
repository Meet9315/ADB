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
CHECK_T1 = REPO_ROOT / "skills/trust-signals-audit/scripts/check_t1.py"
CHECK_T2 = REPO_ROOT / "skills/trust-signals-audit/scripts/check_t2.py"
CHECK_T3 = REPO_ROOT / "skills/trust-signals-audit/scripts/check_t3.py"
CHECK_T4 = REPO_ROOT / "skills/trust-signals-audit/scripts/check_t4.py"
CHECK_G1 = REPO_ROOT / "skills/engagement-audit/scripts/check_g1.py"
CHECK_G2 = REPO_ROOT / "skills/engagement-audit/scripts/check_g2.py"
CHECK_G3 = REPO_ROOT / "skills/engagement-audit/scripts/check_g3.py"
CHECK_G4 = REPO_ROOT / "skills/engagement-audit/scripts/check_g4.py"
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


def run_t1(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_T1), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_t2(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_T2), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_t3(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_T3), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_t4(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_T4), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_g1(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_G1), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_g2(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_G2), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_g3(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_G3), str(corpus_dir), "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def run_g4(fixture: Path) -> list[dict]:
    corpus_dir = fixture / "pages"
    manifest = fixture / "crawl_manifest.json"
    result = subprocess.run(
        [sys.executable, str(CHECK_G4), str(corpus_dir), "--manifest", str(manifest)],
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

# --- T1: Staleness on time-sensitive pricing vs evergreen essay ---
print("\n[T1-staleness] Time-sensitive pricing with old date vs evergreen essay")
with tempfile.TemporaryDirectory() as tmp_t1:
    tmp_t1_path = Path(tmp_t1)
    p_stale = tmp_t1_path / "pages" / "pricing"
    p_evergreen = tmp_t1_path / "pages" / "blog"
    p_stale.mkdir(parents=True)
    p_evergreen.mkdir(parents=True)

    text_words = "Substantive detailed information for users regarding system operations and workflow features. " * 8
    stale_html = (
        "<!DOCTYPE html><html><head><title>Pricing | CloudPlatform</title></head><body>"
        "<main><h1>CloudPlatform Pricing</h1>"
        "<p>Current pricing as of 2022: $29/mo per user for starter package.</p>"
        f"<p>{text_words}</p>"
        "</main></body></html>"
    )
    evergreen_html = (
        "<!DOCTYPE html><html><head><title>Reflections on Distributed Architecture</title></head><body>"
        "<article><h1>Reflections on Architecture</h1>"
        "<p>Published on March 14, 2019 by Engineering Team.</p>"
        f"<p>{text_words}</p>"
        "</article></body></html>"
    )
    (p_stale / "raw.html").write_text(stale_html, encoding="utf-8")
    (p_stale / "text.txt").write_text("CloudPlatform Pricing Current pricing as of 2022: $29/mo per user. " + text_words, encoding="utf-8")
    (p_stale / "meta.json").write_text(json.dumps({"url": "https://cloud.example.com/pricing", "status_code": 200}), encoding="utf-8")

    (p_evergreen / "raw.html").write_text(evergreen_html, encoding="utf-8")
    (p_evergreen / "text.txt").write_text("Reflections on Architecture Published on March 14, 2019. " + text_words, encoding="utf-8")
    (p_evergreen / "meta.json").write_text(json.dumps({"url": "https://cloud.example.com/blog/architecture", "status_code": 200}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "cloud.example.com",
        "base_url": "https://cloud.example.com",
        "crawled_pages": [
            {"url": "https://cloud.example.com/pricing", "slug": "pricing", "status_code": 200},
            {"url": "https://cloud.example.com/blog/architecture", "slug": "blog", "status_code": 200},
        ],
    }
    (tmp_t1_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    t1_findings = run_t1(tmp_t1_path)
    # Stale pricing MUST trigger; evergreen blog post MUST NOT trigger
    stale_flagged = any(f["page_url"] == "https://cloud.example.com/pricing" and f["evidence"]["type"] == "stale_time_sensitive_claim" for f in t1_findings)
    evergreen_flagged = any(f["page_url"] == "https://cloud.example.com/blog/architecture" and "stale" in f["evidence"].get("type", "") for f in t1_findings)

    t1_ok = stale_flagged and not evergreen_flagged
    if not t1_ok:
        print(f"  FAIL [T1] Expected stale pricing flagged and evergreen blog unflagged, got: {t1_findings}")
    test("T1 flags stale pricing claims while correctly guarding evergreen essays against staleness", t1_ok)

# --- T2: Internal Inconsistency across 3 pages with phone normalization guard ---
print("\n[T2-inconsistency] Conflicting phone numbers with format normalization guard")
with tempfile.TemporaryDirectory() as tmp_t2:
    tmp_t2_path = Path(tmp_t2)
    p1 = tmp_t2_path / "pages" / "contact"
    p2 = tmp_t2_path / "pages" / "about"
    p3 = tmp_t2_path / "pages" / "pricing"
    p1.mkdir(parents=True)
    p2.mkdir(parents=True)
    p3.mkdir(parents=True)

    text_words = "Corporate customer overview and operational details for enterprise clients. " * 8
    # Page 1: (555) 100-2000
    (p1 / "raw.html").write_text(f"<html><body><h1>Contact</h1><p>General inquiries: (555) 100-2000</p><p>{text_words}</p></body></html>", encoding="utf-8")
    (p1 / "text.txt").write_text(f"Contact\nGeneral inquiries: (555) 100-2000\n{text_words}", encoding="utf-8")
    (p1 / "meta.json").write_text(json.dumps({"url": "https://corp.example.com/contact", "status_code": 200}), encoding="utf-8")

    # Page 2: Conflicting phone (555) 999-8888
    (p2 / "raw.html").write_text(f"<html><body><h1>About</h1><p>General inquiries: (555) 999-8888</p><p>{text_words}</p></body></html>", encoding="utf-8")
    (p2 / "text.txt").write_text(f"About\nGeneral inquiries: (555) 999-8888\n{text_words}", encoding="utf-8")
    (p2 / "meta.json").write_text(json.dumps({"url": "https://corp.example.com/about", "status_code": 200}), encoding="utf-8")

    # Page 3: Phone with different punctuation: +1-555-100-2000 (normalizes to 5551002000, identical to Page 1)
    (p3 / "raw.html").write_text(f"<html><body><h1>Pricing</h1><p>General inquiries: +1-555-100-2000</p><p>{text_words}</p></body></html>", encoding="utf-8")
    (p3 / "text.txt").write_text(f"Pricing\nGeneral inquiries: +1-555-100-2000\n{text_words}", encoding="utf-8")
    (p3 / "meta.json").write_text(json.dumps({"url": "https://corp.example.com/pricing", "status_code": 200}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "corp.example.com",
        "base_url": "https://corp.example.com",
        "crawled_pages": [
            {"url": "https://corp.example.com/contact", "slug": "contact", "status_code": 200},
            {"url": "https://corp.example.com/about", "slug": "about", "status_code": 200},
            {"url": "https://corp.example.com/pricing", "slug": "pricing", "status_code": 200},
        ],
    }
    (tmp_t2_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    t2_findings = run_t2(tmp_t2_path)
    # Must flag conflict between 5551002000 and 5559998888, but NOT between (555) 100-2000 and +1-555-100-2000
    t2_ok = len(t2_findings) == 1 and t2_findings[0]["check_id"] == "T2"
    if t2_ok:
        ev = t2_findings[0]["evidence"]
        t2_ok = (
            ev.get("fact_type") == "telephone_number"
            and ev.get("normalized_value_a") == "5551002000"
            and ev.get("normalized_value_b") == "5559998888"
        )
    if not t2_ok:
        print(f"  FAIL [T2] Expected 1 phone conflict between normalized numbers, got: {t2_findings}")
    test("T2 diffs phone numbers across 3 pages while normalizing punctuation to prevent false conflicts", t2_ok)

# --- T2: Physical Address Conflict across pages ---
print("\n[T2-address-conflict] Conflicting street addresses across pages")
with tempfile.TemporaryDirectory() as tmp_t2_addr:
    tmp_t2_path = Path(tmp_t2_addr)
    p1 = tmp_t2_path / "pages" / "contact"
    p2 = tmp_t2_path / "pages" / "about"
    p1.mkdir(parents=True)
    p2.mkdir(parents=True)

    (p1 / "raw.html").write_text("<html><body><h1>Contact Us</h1><p>Our headquarters: 100 Main Street, Austin, TX 78701</p></body></html>", encoding="utf-8")
    (p1 / "text.txt").write_text("Contact Us\nOur headquarters: 100 Main Street, Austin, TX 78701", encoding="utf-8")
    (p1 / "meta.json").write_text(json.dumps({"url": "https://corp.example.com/contact", "status_code": 200}), encoding="utf-8")

    (p2 / "raw.html").write_text("<html><body><h1>About Us</h1><p>Visit our corporate office at 500 Market Boulevard, San Francisco, CA 94105</p></body></html>", encoding="utf-8")
    (p2 / "text.txt").write_text("About Us\nVisit our corporate office at 500 Market Boulevard, San Francisco, CA 94105", encoding="utf-8")
    (p2 / "meta.json").write_text(json.dumps({"url": "https://corp.example.com/about", "status_code": 200}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "corp.example.com",
        "base_url": "https://corp.example.com",
        "crawled_pages": [
            {"url": "https://corp.example.com/contact", "slug": "contact", "status_code": 200},
            {"url": "https://corp.example.com/about", "slug": "about", "status_code": 200},
        ],
    }
    (tmp_t2_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    t2_addr_findings = run_t2(tmp_t2_path)
    t2_addr_ok = len(t2_addr_findings) == 1 and t2_addr_findings[0]["evidence"].get("fact_type") == "physical_address"
    if not t2_addr_ok:
        print(f"  FAIL [T2-address-conflict] Expected 1 physical_address conflict, got: {t2_addr_findings}")
    test("T2 detects contradictory physical street addresses asserted across pages", t2_addr_ok)

# --- T2: Address Normalization & Unit Extension Guard ---
print("\n[T2-address-guard] Address normalization (St vs Street) and Suite addition guard")
with tempfile.TemporaryDirectory() as tmp_t2_guard:
    tmp_t2_path = Path(tmp_t2_guard)
    p1 = tmp_t2_path / "pages" / "contact"
    p2 = tmp_t2_path / "pages" / "about"
    p1.mkdir(parents=True)
    p2.mkdir(parents=True)

    # Page 1: 100 Main St, Suite 400, Austin, TX
    (p1 / "raw.html").write_text("<html><body><h1>Contact</h1><p>Office: 100 Main St, Suite 400, Austin, TX 78701</p></body></html>", encoding="utf-8")
    (p1 / "text.txt").write_text("Contact\nOffice: 100 Main St, Suite 400, Austin, TX 78701", encoding="utf-8")
    (p1 / "meta.json").write_text(json.dumps({"url": "https://corp.example.com/contact", "status_code": 200}), encoding="utf-8")

    # Page 2: 100 Main Street, Austin, TX (different abbreviation, no suite -> same physical building)
    (p2 / "raw.html").write_text("<html><body><h1>About</h1><p>HQ: 100 Main Street, Austin, TX 78701</p></body></html>", encoding="utf-8")
    (p2 / "text.txt").write_text("About\nHQ: 100 Main Street, Austin, TX 78701", encoding="utf-8")
    (p2 / "meta.json").write_text(json.dumps({"url": "https://corp.example.com/about", "status_code": 200}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "corp.example.com",
        "base_url": "https://corp.example.com",
        "crawled_pages": [
            {"url": "https://corp.example.com/contact", "slug": "contact", "status_code": 200},
            {"url": "https://corp.example.com/about", "slug": "about", "status_code": 200},
        ],
    }
    (tmp_t2_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    t2_guard_findings = run_t2(tmp_t2_path)
    t2_guard_ok = len(t2_guard_findings) == 0
    if not t2_guard_ok:
        print(f"  FAIL [T2-address-guard] Expected 0 findings for normalized address/suite extension, got: {t2_guard_findings}")
    test("T2 address guard normalizes abbreviations and excludes unit extensions from false conflicts", t2_guard_ok)

# --- T2: Department Phone Role Separation Guard ---
print("\n[T2-department-guard] Distinct phone numbers for different departments do not conflict")
with tempfile.TemporaryDirectory() as tmp_t2_dept:
    tmp_t2_path = Path(tmp_t2_dept)
    p1 = tmp_t2_path / "pages" / "sales"
    p2 = tmp_t2_path / "pages" / "support"
    p1.mkdir(parents=True)
    p2.mkdir(parents=True)

    # Page 1: Sales department phone
    (p1 / "raw.html").write_text("<html><body><h1>Sales</h1><p>Sales: (555) 111-2222</p></body></html>", encoding="utf-8")
    (p1 / "text.txt").write_text("Sales\nSales: (555) 111-2222", encoding="utf-8")
    (p1 / "meta.json").write_text(json.dumps({"url": "https://corp.example.com/sales", "status_code": 200}), encoding="utf-8")

    # Page 2: Support department phone (different number, but different department)
    (p2 / "raw.html").write_text("<html><body><h1>Support</h1><p>Support: (555) 333-4444</p></body></html>", encoding="utf-8")
    (p2 / "text.txt").write_text("Support\nSupport: (555) 333-4444", encoding="utf-8")
    (p2 / "meta.json").write_text(json.dumps({"url": "https://corp.example.com/support", "status_code": 200}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "corp.example.com",
        "base_url": "https://corp.example.com",
        "crawled_pages": [
            {"url": "https://corp.example.com/sales", "slug": "sales", "status_code": 200},
            {"url": "https://corp.example.com/support", "slug": "support", "status_code": 200},
        ],
    }
    (tmp_t2_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    t2_dept_findings = run_t2(tmp_t2_path)
    t2_dept_ok = len(t2_dept_findings) == 0
    if not t2_dept_ok:
        print(f"  FAIL [T2-department-guard] Expected 0 findings for different departments, got: {t2_dept_findings}")
    test("T2 department guard permits distinct phone numbers for different departments without false conflict", t2_dept_ok)

# --- T3: Entity Ambiguity (signal stacking vs proactive suggestion split) ---
print("\n[T3-ambiguity] Generic brand name with stacked signals vs single weak signal")
with tempfile.TemporaryDirectory() as tmp_t3_multi:
    tmp_t3_path = Path(tmp_t3_multi)
    p_home = tmp_t3_path / "pages" / "home"
    p_home.mkdir(parents=True)

    # Generic one-word brand name ("Summit"), no Organization sameAs, and generic buzzwords without category/geography
    ambig_html = (
        "<!DOCTYPE html><html><head><title>Summit</title></head><body>"
        "<main><h1>Welcome to Summit</h1>"
        "<p>We empower next-generation synergy across seamless frontiers. Our unified solutions optimize your vision "
        "with end-to-end holistic paradigms for frictionless execution.</p>"
        "</main></body></html>"
    )
    (p_home / "raw.html").write_text(ambig_html, encoding="utf-8")
    (p_home / "text.txt").write_text("Welcome to Summit We empower next-generation synergy across seamless frontiers. Our unified solutions optimize your vision with end-to-end holistic paradigms for frictionless execution.", encoding="utf-8")
    (p_home / "meta.json").write_text(json.dumps({"url": "https://summit.example.com/", "status_code": 200, "title": "Summit"}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "summit.example.com",
        "base_url": "https://summit.example.com",
        "crawled_pages": [{"url": "https://summit.example.com/", "slug": "home", "status_code": 200}],
    }
    (tmp_t3_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    t3_multi_findings = run_t3(tmp_t3_path)
    # Stacked signals (common brand + no sameAs + no category/geo) MUST trigger finding
    t3_multi_ok = len(t3_multi_findings) == 1 and t3_multi_findings[0]["check_id"] == "T3"
    if t3_multi_ok:
        ev = t3_multi_findings[0]["evidence"]
        t3_multi_ok = ev.get("signal_count", 0) >= 2 and ev.get("is_common_brand") is True
    if not t3_multi_ok:
        print(f"  FAIL [T3-multi] Expected T3 finding for stacked signals, got: {t3_multi_findings}")
    test("T3 reports high-confidence defect finding when multiple ambiguity signals stack together", t3_multi_ok)

with tempfile.TemporaryDirectory() as tmp_t3_single:
    tmp_t3_path = Path(tmp_t3_single)
    p_home = tmp_t3_path / "pages" / "home"
    p_home.mkdir(parents=True)

    # Distinctive multi-word brand with clear software category, but lacks sameAs (single weak signal)
    single_html = (
        "<!DOCTYPE html><html><head><title>FastScaleEngine - Cloud Orchestration Platform</title></head><body>"
        "<main><h1>FastScaleEngine Software</h1>"
        "<p>FastScaleEngine is a B2B SaaS platform for Kubernetes cluster deployment and automated scaling in Austin, Texas.</p>"
        "</main></body></html>"
    )
    (p_home / "raw.html").write_text(single_html, encoding="utf-8")
    (p_home / "text.txt").write_text("FastScaleEngine Software FastScaleEngine is a B2B SaaS platform for Kubernetes cluster deployment and automated scaling in Austin, Texas.", encoding="utf-8")
    (p_home / "meta.json").write_text(json.dumps({"url": "https://fastscale.example.com/", "status_code": 200, "title": "FastScaleEngine"}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "fastscale.example.com",
        "base_url": "https://fastscale.example.com",
        "crawled_pages": [{"url": "https://fastscale.example.com/", "slug": "home", "status_code": 200}],
    }
    (tmp_t3_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    t3_single_findings = run_t3(tmp_t3_path)
    # Single weak signal MUST NOT trigger a defect finding
    t3_single_ok = len(t3_single_findings) == 0
    if not t3_single_ok:
        print(f"  FAIL [T3-single] Expected 0 findings for single weak signal, got: {t3_single_findings}")
    test("T3 false-positive guard suppresses defect finding when only one weak signal is present", t3_single_ok)

# --- T3: Unambiguous Brand Guard ---
print("\n[T3-unambiguous-brand] Distinctive brand lacking sameAs and category produces 0 defect findings")
with tempfile.TemporaryDirectory() as tmp_t3_unambig:
    tmp_t3_path = Path(tmp_t3_unambig)
    p_home = tmp_t3_path / "pages" / "home"
    p_home.mkdir(parents=True)

    # Distinctive legal entity ("Acme Corp"), lacks sameAs and category keywords
    unambig_html = (
        "<!DOCTYPE html><html><head><title>Acme Corp</title></head><body>"
        "<main><h1>Welcome to Acme Corp</h1>"
        "<p>Empowering forward-thinking visionaries with unprecedented capability across all paradigms.</p>"
        "</main></body></html>"
    )
    (p_home / "raw.html").write_text(unambig_html, encoding="utf-8")
    (p_home / "text.txt").write_text("Welcome to Acme Corp Empowering forward-thinking visionaries with unprecedented capability across all paradigms.", encoding="utf-8")
    (p_home / "meta.json").write_text(json.dumps({"url": "https://acmecorp.example.com/", "status_code": 200, "title": "Acme Corp"}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "acmecorp.example.com",
        "base_url": "https://acmecorp.example.com",
        "crawled_pages": [{"url": "https://acmecorp.example.com/", "slug": "home", "status_code": 200}],
    }
    (tmp_t3_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    t3_unambig_findings = run_t3(tmp_t3_path)
    t3_unambig_ok = len(t3_unambig_findings) == 0
    if not t3_unambig_ok:
        print(f"  FAIL [T3-unambiguous-brand] Expected 0 defect findings for distinctive brand, got: {t3_unambig_findings}")
    test("T3 suppresses defect finding when brand is unambiguous, even if sameAs and category are absent", t3_unambig_ok)

# --- T4: Missing About/Contact Presence ---
print("\n[T4-presence] Absence of contact and about presence")
with tempfile.TemporaryDirectory() as tmp_t4:
    tmp_t4_path = Path(tmp_t4)
    p_landing = tmp_t4_path / "pages" / "landing"
    p_landing.mkdir(parents=True)

    landing_html = (
        "<!DOCTYPE html><html><head><title>Generic Landing Page</title></head><body>"
        "<main><h1>Landing Overview</h1>"
        "<p>Generic page content that completely omits contact channels, telephone numbers, "
        "email addresses, and about company descriptions.</p>"
        "</main></body></html>"
    )
    (p_landing / "raw.html").write_text(landing_html, encoding="utf-8")
    (p_landing / "text.txt").write_text("Landing Overview Generic page content that completely omits contact channels.", encoding="utf-8")
    (p_landing / "meta.json").write_text(json.dumps({"url": "https://landing.example.com/", "status_code": 200}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "landing.example.com",
        "base_url": "https://landing.example.com",
        "crawled_pages": [{"url": "https://landing.example.com/", "slug": "landing", "status_code": 200}],
    }
    (tmp_t4_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    t4_findings = run_t4(tmp_t4_path)
    t4_types = [f["evidence"]["type"] for f in t4_findings]
    t4_ok = "missing_contact_presence" in t4_types and "missing_about_presence" in t4_types
    if not t4_ok:
        print(f"  FAIL [T4] Expected missing_contact_presence and missing_about_presence, got: {t4_findings}")
    test("T4 detects missing contact and about presence mechanisms", t4_ok)

# --- T4: Editorial Authorship Attribution Ratio on News Archetype ---
print("\n[T4-authorship-ratio] News site with 4 of 5 articles unattributed triggers T4 finding")
with tempfile.TemporaryDirectory() as tmp_t4_auth:
    tmp_t4_path = Path(tmp_t4_auth)
    pages_dir = tmp_t4_path / "pages"
    pages_dir.mkdir(parents=True)

    # 1 attributed article, 4 unattributed articles
    crawled = []
    for idx in range(1, 6):
        slug = f"post-{idx}"
        p_dir = pages_dir / slug
        p_dir.mkdir(parents=True)
        byline = "<p class='byline'>By Jane Doe</p>" if idx == 1 else ""
        text_byline = "By Jane Doe" if idx == 1 else ""
        html = f"<html><body><article><h1>News Article {idx}</h1>{byline}<p>Reporting on economic developments.</p></article></body></html>"
        (p_dir / "raw.html").write_text(html, encoding="utf-8")
        (p_dir / "text.txt").write_text(f"News Article {idx} {text_byline} Reporting on economic developments.", encoding="utf-8")
        (p_dir / "meta.json").write_text(json.dumps({"url": f"https://news.example.com/news/{slug}", "status_code": 200}), encoding="utf-8")
        crawled.append({"url": f"https://news.example.com/news/{slug}", "slug": slug, "status_code": 200})

    m_dict = {
        "schema_version": "1.0",
        "domain": "news.example.com",
        "base_url": "https://news.example.com",
        "archetypes": ["news"],
        "crawled_pages": crawled,
    }
    (tmp_t4_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    t4_auth_findings = run_t4(tmp_t4_path)
    t4_auth_ok = any(f["evidence"].get("type") == "missing_authorship_attribution" and f["evidence"].get("unattributed_ratio") == 0.8 for f in t4_auth_findings)
    if not t4_auth_ok:
        print(f"  FAIL [T4-authorship-ratio] Expected missing_authorship_attribution with 0.8 ratio, got: {t4_auth_findings}")
    test("T4 flags systemic anonymous publishing when >= 50% of articles on news archetype lack attribution", t4_auth_ok)


# ===========================================================================
# G-Series Synthetic Tests (Tier 2: Engagement Audit)
# ===========================================================================

# --- G1: Above-Fold Orientation Failure ---
print("\n[G1-orientation] Above-fold orientation rubric tests")
# Case A: Buzzword homepage failing "what do they offer?"
with tempfile.TemporaryDirectory() as tmp_g1_fail:
    tmp_g1_path = Path(tmp_g1_fail)
    p_home = tmp_g1_path / "pages" / "home"
    p_home.mkdir(parents=True)

    html_fail = (
        "<!DOCTYPE html><html><head><title>Acme Global Holdings</title></head><body>"
        "<header>Acme Global</header>"
        "<main><h1>Unleashing Synergistic Potential</h1>"
        "<p>Harmonizing horizon vectors and empowering elevated paradigm dynamics.</p>"
        "<nav><a href='/explore'>Explore</a></nav>"
        "</main></body></html>"
    )
    (p_home / "raw.html").write_text(html_fail, encoding="utf-8")
    (p_home / "text.txt").write_text("Acme Global Unleashing Synergistic Potential Harmonizing horizon vectors. Explore", encoding="utf-8")
    (p_home / "meta.json").write_text(json.dumps({"url": "https://acmeglobal.example.com/", "status_code": 200, "title": "Acme Global Holdings"}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "acmeglobal.example.com",
        "base_url": "https://acmeglobal.example.com",
        "crawled_pages": [{"url": "https://acmeglobal.example.com/", "slug": "home", "status_code": 200}],
    }
    (tmp_g1_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    g1_fail_findings = run_g1(tmp_g1_path)
    g1_fail_ok = len(g1_fail_findings) >= 1 and "what_do_they_offer" in g1_fail_findings[0]["evidence"]["unanswered_questions"]
    if not g1_fail_ok:
        print(f"  FAIL [G1-fail] Expected G1 finding for uninformative buzzwords, got: {g1_fail_findings}")
    test("G1 flags above-fold orientation failure when first-viewport text lacks grounded offering quote", g1_fail_ok)

# Case B: Clear orientation homepage
with tempfile.TemporaryDirectory() as tmp_g1_pass:
    tmp_g1_path = Path(tmp_g1_pass)
    p_home = tmp_g1_path / "pages" / "home"
    p_home.mkdir(parents=True)

    html_pass = (
        "<!DOCTYPE html><html><head><title>Acme Analytics - Cloud Monitoring</title></head><body>"
        "<header>Acme Analytics</header>"
        "<main><h1>Cloud Monitoring Platform</h1>"
        "<p>We provide real-time server monitoring software for DevOps engineering teams.</p>"
        "<p><a href='/signup' class='btn'>Start Free Trial</a></p>"
        "</main></body></html>"
    )
    (p_home / "raw.html").write_text(html_pass, encoding="utf-8")
    (p_home / "text.txt").write_text("Acme Analytics Cloud Monitoring Platform We provide real-time server monitoring software for DevOps engineering teams. Start Free Trial", encoding="utf-8")
    (p_home / "meta.json").write_text(json.dumps({"url": "https://analytics.example.com/", "status_code": 200, "title": "Acme Analytics - Cloud Monitoring"}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "analytics.example.com",
        "base_url": "https://analytics.example.com",
        "crawled_pages": [{"url": "https://analytics.example.com/", "slug": "home", "status_code": 200}],
    }
    (tmp_g1_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    g1_pass_findings = run_g1(tmp_g1_path)
    g1_pass_ok = len(g1_pass_findings) == 0
    if not g1_pass_ok:
        print(f"  FAIL [G1-pass] Expected 0 findings for clear orientation homepage, got: {g1_pass_findings}")
    test("G1 cleanly passes when who, what, and next action are quoted from first viewport", g1_pass_ok)

# Case C: Ambiguity guard (Rule 1: never guess or assume what the company probably does)
with tempfile.TemporaryDirectory() as tmp_g1_ambig:
    tmp_g1_path = Path(tmp_g1_ambig)
    p_home = tmp_g1_path / "pages" / "home"
    p_home.mkdir(parents=True)

    html_ambig = (
        "<!DOCTYPE html><html><head><title>Acme Systems</title></head><body>"
        "<header>Acme Systems</header>"
        "<main><h1>Modern Cloud Infrastructure</h1>"
        "<p>Unifying enterprise scale and telemetry pipelines across all regions.</p>"
        "<p><a href='/explore'>Explore</a></p>"
        "</main></body></html>"
    )
    (p_home / "raw.html").write_text(html_ambig, encoding="utf-8")
    (p_home / "text.txt").write_text("Acme Systems Modern Cloud Infrastructure Unifying enterprise scale and telemetry pipelines across all regions. Explore", encoding="utf-8")
    (p_home / "meta.json").write_text(json.dumps({"url": "https://systems.example.com/", "status_code": 200, "title": "Acme Systems"}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "systems.example.com",
        "base_url": "https://systems.example.com",
        "crawled_pages": [{"url": "https://systems.example.com/", "slug": "home", "status_code": 200}],
    }
    (tmp_g1_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    g1_ambig_findings = run_g1(tmp_g1_path)
    g1_ambig_ok = len(g1_ambig_findings) == 0
    if not g1_ambig_ok:
        print(f"  FAIL [G1-ambig] Expected 0 findings due to Rule 1 ambiguity guard, got: {g1_ambig_findings}")
    test("G1 suppresses findings when offering judgment is ambiguous per Rule 1 negative logic", g1_ambig_ok)


# --- G2: Wayfinding Defects ---
print("\n[G2-wayfinding] Broken internal links, utility navigation, and substantive orphans")
with tempfile.TemporaryDirectory() as tmp_g2:
    tmp_g2_path = Path(tmp_g2)
    p_home = tmp_g2_path / "pages" / "home"
    p_home.mkdir(parents=True)
    p_orphan = tmp_g2_path / "pages" / "orphan"
    p_orphan.mkdir(parents=True)

    # Home has no link to pricing or orphan
    (p_home / "raw.html").write_text("<html><body><header>Acme</header><main><p>Welcome to Acme.</p></main></body></html>", encoding="utf-8")
    (p_home / "text.txt").write_text("Welcome to Acme.", encoding="utf-8")
    (p_home / "meta.json").write_text(json.dumps({"url": "https://wayfinding.example.com/", "status_code": 200}), encoding="utf-8")

    # Substantive orphan (> 80 words)
    orphan_text = "Detailed documentation guide explaining the architecture of our platform. " * 10
    (p_orphan / "raw.html").write_text(f"<html><body><h1>Guide</h1><p>{orphan_text}</p></body></html>", encoding="utf-8")
    (p_orphan / "text.txt").write_text(orphan_text, encoding="utf-8")
    (p_orphan / "meta.json").write_text(json.dumps({"url": "https://wayfinding.example.com/docs/guide", "status_code": 200}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "wayfinding.example.com",
        "base_url": "https://wayfinding.example.com",
        "crawled_pages": [
            {"url": "https://wayfinding.example.com/", "slug": "home", "status_code": 200},
            {"url": "https://wayfinding.example.com/broken-page", "slug": "broken", "status_code": 404, "source_url": "https://wayfinding.example.com/"},
            {"url": "https://wayfinding.example.com/pricing", "slug": "pricing", "status_code": 200, "depth": 3},
            {"url": "https://wayfinding.example.com/docs/guide", "slug": "orphan", "status_code": 200},
        ],
    }
    (tmp_g2_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    g2_findings = run_g2(tmp_g2_path)
    g2_types = [f["evidence"]["type"] for f in g2_findings]
    g2_ok = (
        "broken_internal_link" in g2_types
        and "excessive_utility_click_depth" in g2_types
        and "substantive_orphan_page" in g2_types
    )
    if not g2_ok:
        print(f"  FAIL [G2] Expected broken_internal_link, excessive_utility_click_depth, and substantive_orphan_page, got: {g2_types}")
    test("G2 flags broken internal links, excessive utility click depth, and substantive orphan pages", g2_ok)

# Intentional Nav Path Guard for G2: Depth alone is not a defect when linked in home nav
with tempfile.TemporaryDirectory() as tmp_g2_guard:
    tmp_g2_path = Path(tmp_g2_guard)
    p_home = tmp_g2_path / "pages" / "home"
    p_home.mkdir(parents=True)

    # Home directly links to /pricing in navigation
    (p_home / "raw.html").write_text("<html><body><header><nav><a href='/pricing'>Pricing</a></nav></header></body></html>", encoding="utf-8")
    (p_home / "text.txt").write_text("Pricing", encoding="utf-8")
    (p_home / "meta.json").write_text(json.dumps({"url": "https://guard.example.com/", "status_code": 200}), encoding="utf-8")

    m_dict = {
        "schema_version": "1.0",
        "domain": "guard.example.com",
        "base_url": "https://guard.example.com",
        "crawled_pages": [
            {"url": "https://guard.example.com/", "slug": "home", "status_code": 200},
            {"url": "https://guard.example.com/pricing", "slug": "pricing", "status_code": 200, "depth": 3, "source_url": "https://guard.example.com/"},
        ],
    }
    (tmp_g2_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    g2_guard_findings = run_g2(tmp_g2_path)
    g2_guard_ok = len(g2_guard_findings) == 0
    if not g2_guard_ok:
        print(f"  FAIL [G2-guard] Expected 0 findings due to intentional nav path guard, got: {g2_guard_findings}")
    test("G2 suppresses depth defect when utility page has an intentional home navigation path", g2_guard_ok)


# --- G3: Friction & Intrusive Obstructions ---
print("\n[G3-friction] Interstitials, payload ceilings, and media displacement")
# Case A: Intrusive modal covering content on load
with tempfile.TemporaryDirectory() as tmp_g3_modal:
    tmp_g3_path = Path(tmp_g3_modal)
    p_home = tmp_g3_path / "pages" / "home"
    p_home.mkdir(parents=True)

    html_modal = (
        "<!DOCTYPE html><html><head><title>Acme Blog</title></head><body>"
        "<div class='interstitial-modal' style='position:fixed; inset:0; z-index:9999;'><h2>Join Our Newsletter!</h2></div>"
        "<main><h1>Article Headline</h1><p>Substantive article paragraphs describing technological trends.</p></main>"
        "</body></html>"
    )
    (p_home / "raw.html").write_text(html_modal, encoding="utf-8")
    (p_home / "meta.json").write_text(json.dumps({"url": "https://modal.example.com/", "status_code": 200}), encoding="utf-8")
    m_dict = {"schema_version": "1.0", "domain": "modal.example.com", "crawled_pages": [{"url": "https://modal.example.com/", "slug": "home"}]}
    (tmp_g3_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    g3_modal_findings = run_g3(tmp_g3_path)
    g3_modal_ok = any(f["evidence"].get("type") == "intrusive_interstitial_modal" for f in g3_modal_findings)
    if not g3_modal_ok:
        print(f"  FAIL [G3-modal] Expected intrusive_interstitial_modal, got: {g3_modal_findings}")
    test("G3 flags intrusive interstitial modals obscuring substantive content on load", g3_modal_ok)

# Case B: Cookie / GDPR banner strictly exempted (NEVER flag legal consent dialogs)
with tempfile.TemporaryDirectory() as tmp_g3_cookie:
    tmp_g3_path = Path(tmp_g3_cookie)
    p_home = tmp_g3_path / "pages" / "home"
    p_home.mkdir(parents=True)

    html_cookie = (
        "<!DOCTYPE html><html><head><title>Acme Portal</title></head><body>"
        "<div id='cookie-consent-banner' class='cookie-notice' style='position:fixed; inset:0; z-index:9999;'>"
        "<p>We use cookies and similar technologies to provide privacy compliance and ensure optimal experience. Accept all cookies.</p>"
        "<button>Accept All</button>"
        "</div>"
        "<main><h1>Portal Home</h1><p>Substantive portal content.</p></main>"
        "</body></html>"
    )
    (p_home / "raw.html").write_text(html_cookie, encoding="utf-8")
    (p_home / "meta.json").write_text(json.dumps({"url": "https://cookie.example.com/", "status_code": 200}), encoding="utf-8")
    m_dict = {"schema_version": "1.0", "domain": "cookie.example.com", "crawled_pages": [{"url": "https://cookie.example.com/", "slug": "home"}]}
    (tmp_g3_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    g3_cookie_findings = run_g3(tmp_g3_path)
    g3_cookie_ok = len(g3_cookie_findings) == 0
    if not g3_cookie_ok:
        print(f"  FAIL [G3-cookie] Expected 0 findings for cookie/GDPR consent dialog, got: {g3_cookie_findings}")
    test("G3 strictly excludes cookie banners, GDPR dialogs, and legal notices from friction findings", g3_cookie_ok)

# Case C: Excessive page payload (> 5MB)
with tempfile.TemporaryDirectory() as tmp_g3_heavy:
    tmp_g3_path = Path(tmp_g3_heavy)
    p_home = tmp_g3_path / "pages" / "home"
    p_home.mkdir(parents=True)

    (p_home / "raw.html").write_text("<html><body><h1>Heavy Page</h1></body></html>", encoding="utf-8")
    (p_home / "meta.json").write_text(json.dumps({
        "url": "https://heavy.example.com/",
        "status_code": 200,
        "response_headers": {"content-length": "6291456"},  # 6 MB
    }), encoding="utf-8")
    m_dict = {"schema_version": "1.0", "domain": "heavy.example.com", "crawled_pages": [{"url": "https://heavy.example.com/", "slug": "home"}]}
    (tmp_g3_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    g3_heavy_findings = run_g3(tmp_g3_path)
    g3_heavy_ok = any(f["evidence"].get("type") == "excessive_page_payload" and f["evidence"].get("payload_mb") == 6.0 for f in g3_heavy_findings)
    if not g3_heavy_ok:
        print(f"  FAIL [G3-heavy] Expected excessive_page_payload with 6.0MB, got: {g3_heavy_findings}")
    test("G3 flags transferred page payload exceeding 5MB explicit deterministic ceiling", g3_heavy_ok)


# --- G4: No Discernible Primary Action ---
print("\n[G4-action] Primary call-to-action intent presence on commercial pages")
# Case A: Commercial product page lacking primary CTA
with tempfile.TemporaryDirectory() as tmp_g4_fail:
    tmp_g4_path = Path(tmp_g4_fail)
    p_prod = tmp_g4_path / "pages" / "product"
    p_prod.mkdir(parents=True)

    html_no_cta = (
        "<!DOCTYPE html><html><head><title>Acme Widget Pro</title></head><body>"
        "<header>Acme</header>"
        "<main><h1>Acme Widget Pro</h1>"
        "<p>The Widget Pro delivers unprecedented precision engineering and durable performance for all manufacturing operations.</p>"
        "</main></body></html>"
    )
    (p_prod / "raw.html").write_text(html_no_cta, encoding="utf-8")
    (p_prod / "text.txt").write_text("Acme Widget Pro The Widget Pro delivers unprecedented precision engineering and durable performance for all manufacturing and industrial assembly operations worldwide.", encoding="utf-8")
    (p_prod / "meta.json").write_text(json.dumps({"url": "https://shop.example.com/products/widget-pro", "status_code": 200}), encoding="utf-8")
    m_dict = {
        "schema_version": "1.0",
        "domain": "shop.example.com",
        "crawled_pages": [{"url": "https://shop.example.com/products/widget-pro", "slug": "product", "status_code": 200}],
    }
    (tmp_g4_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    g4_fail_findings = run_g4(tmp_g4_path)
    g4_fail_ok = any(f["evidence"].get("type") == "missing_primary_action" for f in g4_fail_findings)
    if not g4_fail_ok:
        print(f"  FAIL [G4-fail] Expected missing_primary_action on product page, got: {g4_fail_findings}")
    test("G4 flags commercial product/landing pages with no detectable primary action", g4_fail_ok)

# Case B: Non-commercial page exemption (privacy policy / blog article)
with tempfile.TemporaryDirectory() as tmp_g4_exempt:
    tmp_g4_path = Path(tmp_g4_exempt)
    p_legal = tmp_g4_path / "pages" / "privacy"
    p_legal.mkdir(parents=True)

    html_legal = (
        "<!DOCTYPE html><html><head><title>Privacy Policy</title></head><body>"
        "<header>Acme Legal</header>"
        "<main><h1>Privacy Policy</h1>"
        "<p>This privacy policy outlines how Acme collects, uses, and safeguards information.</p>"
        "</main></body></html>"
    )
    (p_legal / "raw.html").write_text(html_legal, encoding="utf-8")
    (p_legal / "text.txt").write_text("Privacy Policy This privacy policy outlines how Acme collects, uses, and safeguards information.", encoding="utf-8")
    (p_legal / "meta.json").write_text(json.dumps({"url": "https://shop.example.com/privacy", "status_code": 200}), encoding="utf-8")
    m_dict = {
        "schema_version": "1.0",
        "domain": "shop.example.com",
        "crawled_pages": [{"url": "https://shop.example.com/privacy", "slug": "privacy", "status_code": 200}],
    }
    (tmp_g4_path / "crawl_manifest.json").write_text(json.dumps(m_dict), encoding="utf-8")

    g4_exempt_findings = run_g4(tmp_g4_path)
    g4_exempt_ok = len(g4_exempt_findings) == 0
    if not g4_exempt_ok:
        print(f"  FAIL [G4-exempt] Expected 0 findings for non-commercial page, got: {g4_exempt_findings}")
    test("G4 exempts non-commercial pages (legal, editorial, documentation) from action requirements", g4_exempt_ok)


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
all_clean_findings.extend(run_t1(fx))
all_clean_findings.extend(run_t2(fx))
all_clean_findings.extend(run_t3(fx))
all_clean_findings.extend(run_t4(fx))
all_clean_findings.extend(run_g1(fx))
all_clean_findings.extend(run_g2(fx))
all_clean_findings.extend(run_g3(fx))
all_clean_findings.extend(run_g4(fx))

clean_ok = assert_zero("clean", all_clean_findings)
test("CLEAN fixture produces 0 findings across all 20 deterministic checks (R1-R5, D1-D3, E1-E4, T1-T4, G1-G4)", clean_ok)

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
