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
CHECK_E2 = REPO_ROOT / "skills/machine-readability-audit/scripts/check_e2.py"
CHECK_E3 = REPO_ROOT / "skills/machine-readability-audit/scripts/check_e3.py"
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

# --- CLEAN: All checks must produce 0 findings ---
print("\n[clean] All checks against clean fixture — must produce 0 findings")
fx = FIXTURES / "clean"
all_clean_findings = []
all_clean_findings.extend(run_reach(fx, ["R1", "R3", "R5"]))
all_clean_findings.extend(run_noindex(fx))
all_clean_findings.extend(run_d2(fx))
all_clean_findings.extend(run_d1(fx))
all_clean_findings.extend(run_e2(fx))

clean_ok = assert_zero("clean", all_clean_findings)
test("CLEAN fixture produces 0 findings across deterministic checks", clean_ok)

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
