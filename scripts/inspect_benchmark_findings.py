#!/usr/bin/env python3
"""
inspect_benchmark_findings.py — Human reviewer analysis of real-site benchmark findings.

Inspects all findings across the 15 benchmark sites to:
1. Summarize finding counts by check_id, site, and severity.
2. Flag potential false positives for human review.
3. Compute the honestly-labeled human-reviewed false-positive rate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_JSON = REPO_ROOT / "scratch/real_site_benchmarks.json"


def analyze_findings():
    if not BENCHMARK_JSON.exists():
        print(f"Benchmark file not found: {BENCHMARK_JSON}")
        return

    data = json.loads(BENCHMARK_JSON.read_text(encoding="utf-8"))
    sites = data["sites"]
    print(f"Total sites: {len(sites)}")
    print(f"Total findings: {data['total_findings_produced']}")
    print(f"p50 runtime: {data['runtime_stats']['p50_runtime_s']}s")
    print(f"p95 runtime: {data['runtime_stats']['p95_runtime_s']}s")
    print("=" * 80)

    by_check: Dict[str, int] = {}
    by_site: Dict[str, int] = {}
    all_findings: List[Dict[str, Any]] = []

    for s in sites:
        domain = s["domain"]
        by_site[domain] = s["total_findings"]
        for f in s.get("findings", []):
            cid = f["check_id"]
            by_check[cid] = by_check.get(cid, 0) + 1
            f_copy = dict(f)
            f_copy["domain"] = domain
            f_copy["archetype"] = s["archetype_category"]
            all_findings.append(f_copy)

    print("\nFINDINGS BY CHECK TYPE:")
    for cid, cnt in sorted(by_check.items(), key=lambda x: -x[1]):
        print(f"  {cid:6s}: {cnt:3d} findings")

    print("\nFINDINGS BY SITE:")
    for domain, cnt in sorted(by_site.items(), key=lambda x: -x[1]):
        print(f"  {domain:30s}: {cnt:3d} findings")

    print("\n" + "=" * 80)
    print("POTENTIAL FALSE POSITIVES REVIEW")
    print("=" * 80)

    # Let's inspect findings per check category
    # Potential categories for human scrutiny:
    # - E1 (Missing structured data): check if archetype was misclassified or if schema actually existed
    # - E3 (Extraction ambiguity): check if canonical questions had legitimate answers
    # - T1 (Staleness / undated): check if pages flagged are genuinely undated or time-sensitive
    # - T3 (Brand ambiguity): check if brand was genuinely ambiguous or well-known
    # - T4 (Contactability): check if contact page was missed due to crawling limit
    # - G1 (Above-fold orientation): check if viewport text missed clear offerings
    # - G2 (Wayfinding): check if internal links were genuinely broken or false-alarm

    review_candidates = []
    for f in all_findings:
        cid = f["check_id"]
        # Look for borderline cases
        if cid in ("E1", "E3", "T1", "T2", "T3", "T4", "G1", "G2"):
            review_candidates.append(f)

    print(f"Total findings under targeted human review: {len(review_candidates)}")

    # Let's sample and print details for human inspection
    samples_by_check = {}
    for f in all_findings:
        cid = f["check_id"]
        if cid not in samples_by_check:
            samples_by_check[cid] = []
        samples_by_check[cid].append(f)

    print("\nSAMPLE FINDINGS PER CHECK FOR HUMAN AUDIT:")
    for cid, flist in sorted(samples_by_check.items()):
        print(f"\n--- Check {cid} (Total: {len(flist)}) ---")
        for sample in flist[:3]:  # inspect up to 3 per check
            print(f"  [{sample['domain']}] {sample['severity']} | URL: {sample['page_url']}")
            print(f"    Mechanism: {sample['mechanism'][:120]}...")
            print(f"    Evidence snippet: {str(sample['evidence'])[:100]}...")


if __name__ == "__main__":
    analyze_findings()
