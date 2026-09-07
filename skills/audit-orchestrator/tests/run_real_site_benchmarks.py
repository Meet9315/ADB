#!/usr/bin/env python3
"""
run_real_site_benchmarks.py — Multi-archetype real-site benchmark suite.

Fulfills Prompt 11, Requirements 1, 2, 6:
1. Assembles ~15 real sites across archetypes:
   - SPA SaaS (linear.app)
   - Schema-rich big ecommerce (books.toscrape.com)
   - Schema-poor small shop (shop.mercurial-scm.org)
   - Local restaurant (frenchlaundry.com)
   - Docs site (fastapi.tiangolo.com)
   - Static portfolio (danabra.mov)
   - News site (theguardian.com)
   - Corporate site (stripe.com)
   - Generic-brand-name site (box.com)
   - Site behind Cloudflare (cloudflare.com)
   - 3-page site (info.cern.ch)
   - Developer tool (astral.sh)
   - Minimal content/library (htmx.org)
   - Modern runtime (deno.com)
   - Framework (vuejs.org)
2. Runs the full pipeline on all of them.
3. Logs runtime, findings count, detailed findings for human reviewer inspection.
4. Computes p95 runtime (< 4 min budget assertion).
5. Outputs complete benchmark JSON report for false-positive auditing.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "skills/audit-orchestrator/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from audit import run_audit_pipeline  # noqa: E402
from validate_report import validate_report  # noqa: E402

BENCHMARK_SITES = [
    {"domain": "linear.app", "archetype": "SPA SaaS"},
    {"domain": "books.toscrape.com", "archetype": "Schema-rich big ecommerce"},
    {"domain": "shop.mercurial-scm.org", "archetype": "Schema-poor small shop"},
    {"domain": "frenchlaundry.com", "archetype": "Local restaurant"},
    {"domain": "fastapi.tiangolo.com", "archetype": "Docs site"},
    {"domain": "danabra.mov", "archetype": "Static portfolio"},
    {"domain": "theguardian.com", "archetype": "News site"},
    {"domain": "stripe.com", "archetype": "Corporate site"},
    {"domain": "box.com", "archetype": "Generic-brand-name site"},
    {"domain": "cloudflare.com", "archetype": "Site behind Cloudflare"},
    {"domain": "info.cern.ch", "archetype": "3-page minimal site"},
    {"domain": "astral.sh", "archetype": "Developer tool"},
    {"domain": "htmx.org", "archetype": "Minimal content / library"},
    {"domain": "deno.com", "archetype": "Modern runtime"},
    {"domain": "vuejs.org", "archetype": "Open-source framework"},
]


def run_benchmark_suite(budget_soft: float = 40.0, budget_hard: float = 60.0) -> Dict[str, Any]:
    print("=" * 80)
    print(f"RUNNING REAL-SITE BENCHMARK SUITE ({len(BENCHMARK_SITES)} SITES ACROSS ARCHETYPES)")
    print(f"Budget per site: soft={budget_soft}s, hard={budget_hard}s | Target p95 runtime < 240s")
    print("=" * 80)

    results: List[Dict[str, Any]] = []
    runtimes: List[float] = []

    for idx, target in enumerate(BENCHMARK_SITES, 1):
        domain = target["domain"]
        arch_label = target["archetype"]

        print(f"\n[{idx}/{len(BENCHMARK_SITES)}] Auditing {domain} ({arch_label})...")
        t0 = time.monotonic()
        out_dir = REPO_ROOT / "scratch" / "benchmarks" / domain.replace(":", "_")
        try:
            report_dict = run_audit_pipeline(
                domain=domain,
                output_dir=out_dir,
                budget_soft=budget_soft,
                budget_hard=budget_hard,
            )
            elapsed = time.monotonic() - t0
            runtimes.append(elapsed)

            # Validate report schema
            report = validate_report(report_dict)

            findings_summary = [
                {
                    "id": f.id,
                    "check_id": f.check_id,
                    "severity": f.final_severity,
                    "confidence": f.confidence,
                    "page_url": f.page_url,
                    "mechanism": f.mechanism,
                    "evidence": f.evidence,
                }
                for f in report.findings
            ]

            entry = {
                "domain": domain,
                "archetype_category": arch_label,
                "inferred_archetype": report.audit_metadata.archetype,
                "is_tiny_site": report.audit_metadata.is_tiny_site,
                "runtime_s": round(elapsed, 2),
                "partial_audit": report.audit_metadata.partial_audit,
                "partial_audit_reason": report.audit_metadata.partial_audit_reason,
                "total_findings": report.summary.total_findings,
                "by_severity": report.summary.by_severity,
                "by_check_id": report.summary.by_check_id,
                "findings": findings_summary,
                "error": None,
            }
            results.append(entry)

            print(f"    Done in {elapsed:.2f}s | Findings: {report.summary.total_findings} "
                  f"| Partial: {report.audit_metadata.partial_audit} | Inferred Arch: {report.audit_metadata.archetype}")
            for f in report.findings:
                print(f"      * [{f.check_id}] ({f.final_severity}, conf={f.confidence:.2f}): {f.mechanism[:85]}... [{f.page_url}]")

        except Exception as exc:
            elapsed = time.monotonic() - t0
            runtimes.append(elapsed)
            print(f"    ERROR running {domain}: {exc}", file=sys.stderr)
            results.append({
                "domain": domain,
                "archetype_category": arch_label,
                "runtime_s": round(elapsed, 2),
                "error": str(exc),
                "total_findings": 0,
                "findings": [],
            })

    # Compute runtime stats
    sorted_runtimes = sorted(runtimes)
    p50 = statistics.median(sorted_runtimes) if sorted_runtimes else 0.0
    p95_idx = int(len(sorted_runtimes) * 0.95)
    p95 = sorted_runtimes[min(p95_idx, len(sorted_runtimes) - 1)] if sorted_runtimes else 0.0
    max_runtime = max(sorted_runtimes) if sorted_runtimes else 0.0

    total_findings_all_sites = sum(r.get("total_findings", 0) for r in results)

    summary_data = {
        "benchmark_timestamp": time.time(),
        "total_sites": len(BENCHMARK_SITES),
        "total_findings_produced": total_findings_all_sites,
        "runtime_stats": {
            "p50_runtime_s": round(p50, 2),
            "p95_runtime_s": round(p95, 2),
            "max_runtime_s": round(max_runtime, 2),
            "target_p95_ceiling_s": 240.0,
            "p95_passed": p95 < 240.0,
        },
        "sites": results,
    }

    # Save to scratch
    out_file = REPO_ROOT / "scratch" / "real_site_benchmarks.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(summary_data, indent=2, default=str), encoding="utf-8")

    print("\n" + "=" * 80)
    print("REAL-SITE BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"Total Sites Audited: {len(BENCHMARK_SITES)}")
    print(f"Total Findings Produced: {total_findings_all_sites}")
    print(f"Runtime Median (p50): {p50:.2f}s")
    print(f"Runtime p95: {p95:.2f}s (Budget Ceiling: 240.0s -> {'PASS' if p95 < 240.0 else 'FAIL'})")
    print(f"Benchmark artifact saved to: {out_file}")
    print("=" * 80)

    return summary_data


def main() -> None:
    run_benchmark_suite()


if __name__ == "__main__":
    main()
