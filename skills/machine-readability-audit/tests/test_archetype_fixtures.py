#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_archetype_fixtures.py — Comprehensive test suite for site archetype classifier.

Validates the full checklist:
  1. Major archetypes (8): ecommerce, saas, content, news, docs, portfolio, local_business, corporate
  2. Ambiguous case: SaaS developer tool with deep docs
  3. Unknown case: minimal/generic landing page without diagnostic signals
  4. Mixed case: Ecommerce + SaaS
  5. False-positive guard for local_business: corporate tech company with HQ address in footer
  6. False-positive guard for corporate: personal blog with Organization/WebSite schema
  7. Determinism: 10 repeated runs per fixture yielding byte-identical JSON outputs

Usage:
    python test_archetype_fixtures.py
Exit code 0 on all PASS, 1 on any failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]  # ADB/
ARCHETYPE_SCRIPT = REPO_ROOT / "skills/machine-readability-audit/scripts/archetype.py"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def run_archetype(fixture_name: str) -> dict:
    fixture_dir = FIXTURES_DIR / fixture_name
    manifest = fixture_dir / "crawl_manifest.json"
    corpus_dir = fixture_dir / "pages"
    res = subprocess.run(
        [sys.executable, str(ARCHETYPE_SCRIPT), str(manifest), "--corpus-dir", str(corpus_dir)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"archetype.py failed on {fixture_name}:\n{res.stderr}")
    return json.loads(res.stdout)


def run_archetype_raw(fixture_name: str) -> str:
    fixture_dir = FIXTURES_DIR / fixture_name
    manifest = fixture_dir / "crawl_manifest.json"
    corpus_dir = fixture_dir / "pages"
    res = subprocess.run(
        [sys.executable, str(ARCHETYPE_SCRIPT), str(manifest), "--corpus-dir", str(corpus_dir)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"archetype.py failed on {fixture_name}:\n{res.stderr}")
    return res.stdout


def main() -> int:
    failures = 0
    total_tests = 0

    print("================================================================")
    print("ARCHETYPE CLASSIFIER FIXTURE BENCHMARK")
    print("================================================================")

    # 1. Major Archetypes
    major_archetypes = [
        ("archetype_ecommerce", "ecommerce"),
        ("archetype_saas", "saas"),
        ("archetype_content", "content"),
        ("archetype_news", "news"),
        ("archetype_docs", "docs"),
        ("archetype_portfolio", "portfolio"),
        ("archetype_local_business", "local_business"),
        ("archetype_corporate", "corporate"),
    ]

    print("\n--- 1. Major Archetypes (8 tests) ---")
    for fixture_name, expected_primary in major_archetypes:
        total_tests += 1
        data = run_archetype(fixture_name)
        primary = data["archetypes"][0] if data["archetypes"] else None
        score = data["archetype_scores"].get(expected_primary, 0.0)
        if primary == expected_primary:
            print(f"  [PASS] {fixture_name:<28} -> primary: {primary} (score: {score:.2f})")
        else:
            failures += 1
            print(f"  [FAIL] {fixture_name:<28} -> expected {expected_primary}, got {primary} (scores: {data['archetype_scores']})")

    # 2. Ambiguous case
    print("\n--- 2. Ambiguous Case (SaaS + Docs) ---")
    total_tests += 1
    data_ambig = run_archetype("archetype_ambiguous")
    archetypes_ambig = data_ambig["archetypes"]
    if len(archetypes_ambig) >= 2 and "saas" in archetypes_ambig and "docs" in archetypes_ambig:
        print(f"  [PASS] archetype_ambiguous           -> multi-classified: {archetypes_ambig} (scores: saas={data_ambig['archetype_scores']['saas']:.2f}, docs={data_ambig['archetype_scores']['docs']:.2f})")
    else:
        failures += 1
        print(f"  [FAIL] archetype_ambiguous           -> expected multi-classification with saas & docs, got: {archetypes_ambig}")

    # 3. Unknown case
    print("\n--- 3. Unknown Case (Generic landing, insufficient signals) ---")
    total_tests += 1
    data_unknown = run_archetype("archetype_unknown")
    if data_unknown["archetypes"] == ["unknown"]:
        top_score = max(data_unknown["archetype_scores"].values())
        print(f"  [PASS] archetype_unknown             -> classified: ['unknown'] (top score: {top_score:.2f} < 1.5 threshold)")
    else:
        failures += 1
        print(f"  [FAIL] archetype_unknown             -> expected ['unknown'], got: {data_unknown['archetypes']}")

    # 4. Mixed site
    print("\n--- 4. Mixed Site (Ecommerce + SaaS) ---")
    total_tests += 1
    data_mixed = run_archetype("archetype_mixed")
    archetypes_mixed = data_mixed["archetypes"]
    if len(archetypes_mixed) >= 2 and ("ecommerce" in archetypes_mixed and "saas" in archetypes_mixed):
        print(f"  [PASS] archetype_mixed               -> multi-classified: {archetypes_mixed} (ecommerce={data_mixed['archetype_scores']['ecommerce']:.2f}, saas={data_mixed['archetype_scores']['saas']:.2f})")
    else:
        failures += 1
        print(f"  [FAIL] archetype_mixed               -> expected dual ecommerce + saas, got: {archetypes_mixed}")

    # 5. False-positive guard for local_business
    print("\n--- 5. False-Positive Guard: local_business ---")
    total_tests += 1
    data_fp_local = run_archetype("archetype_fp_local_business")
    local_score = data_fp_local["archetype_scores"]["local_business"]
    if "local_business" not in data_fp_local["archetypes"] and local_score < 1.5:
        print(f"  [PASS] archetype_fp_local_business   -> correctly rejected local_business (score: {local_score:.2f} < 1.5; classified: {data_fp_local['archetypes']})")
    else:
        failures += 1
        print(f"  [FAIL] archetype_fp_local_business   -> falsely classified as local_business! (score: {local_score:.2f}, archetypes: {data_fp_local['archetypes']})")

    # 6. False-positive guard for corporate
    print("\n--- 6. False-Positive Guard: corporate ---")
    total_tests += 1
    data_fp_corp = run_archetype("archetype_fp_corporate")
    corp_score = data_fp_corp["archetype_scores"]["corporate"]
    if "corporate" not in data_fp_corp["archetypes"] and data_fp_corp["archetypes"][0] == "content":
        print(f"  [PASS] archetype_fp_corporate        -> correctly rejected corporate (score: {corp_score:.2f}; classified: {data_fp_corp['archetypes']})")
    else:
        failures += 1
        print(f"  [FAIL] archetype_fp_corporate        -> falsely classified as corporate! (score: {corp_score:.2f}, archetypes: {data_fp_corp['archetypes']})")

    # 7. Deterministic repeated output (10 runs per fixture)
    print("\n--- 7. Determinism Assertion (10 repeated runs per fixture) ---")
    all_fixtures = [name for name, _ in major_archetypes] + [
        "archetype_ambiguous",
        "archetype_unknown",
        "archetype_mixed",
        "archetype_fp_local_business",
        "archetype_fp_corporate",
    ]
    det_failures = 0
    for fix in all_fixtures:
        first_output = run_archetype_raw(fix)
        for iteration in range(9):
            repeat_output = run_archetype_raw(fix)
            if repeat_output != first_output:
                det_failures += 1
                print(f"  [FAIL] Determinism broken on {fix} at iteration {iteration+2}")
                break

    total_tests += len(all_fixtures)
    if det_failures == 0:
        print(f"  [PASS] Determinism verified: 10/10 identical runs across all {len(all_fixtures)} fixtures.")
    else:
        failures += det_failures

    print("================================================================")
    print(f"TOTAL: {total_tests} assertions, {total_tests - failures} passed, {failures} failed.")
    print("================================================================")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
