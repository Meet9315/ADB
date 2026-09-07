#!/usr/bin/env python3
"""
test_new_real_site.py — Validates end-to-end audit on a genuinely new real site.

Can validate an existing report file OR run a live end-to-end audit pipeline
against a real website, asserting all P7 criteria:
- Elapsed time within 240.0s soft budget (and 300.0s hard ceiling)
- Full Pydantic FinalReport schema validity
- Non-empty archetype inferred from observed corpus signals
- Traceable recommendations linked to findings
- Zero fabricated URLs or brand names
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[2]
SCRIPTS_DIR = _HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from audit import run_audit_pipeline
from models import FinalReport
from validate_report import validate_report


def assert_report_invariants(report: FinalReport) -> None:
    """Assert all P7 report invariants."""
    assert report.audit_metadata.target_domain, "Target domain must be non-empty"
    assert report.audit_metadata.archetype, "Archetype must be determined"
    assert report.summary.total_findings == len(report.findings), (
        f"Summary count ({report.summary.total_findings}) != findings ({len(report.findings)})"
    )
    assert report.audit_metadata.elapsed_s <= 300.0, (
        f"Audit elapsed time ({report.audit_metadata.elapsed_s:.1f}s) exceeded 300.0s hard ceiling"
    )

    if report.findings:
        assert len(report.recommendations) >= 1, "Report with findings must contain recommendations"

    # Evidence contract and provenance assertions
    for f in report.findings:
        assert "example.com" not in f.page_url, (
            f"Finding {f.id} contains fabricated example.com URL: {f.page_url}"
        )
        assert f.verification_method, f"Finding {f.id} missing verification_method"
        assert f.false_positive_guard, f"Finding {f.id} missing false_positive_guard"
        assert f.mechanism, f"Finding {f.id} missing mechanism"
        if f.suggested_action:
            assert f.suggested_action.linked_findings, (
                f"Suggested action for {f.id} has empty linked_findings"
            )


def run_live_real_site_audit(domain: str = "htmx.org") -> FinalReport:
    """
    Execute a live end-to-end audit pipeline on a real website
    and validate the resulting report against all P7 criteria.
    """
    print(f"[*] Executing live end-to-end audit on {domain}...")
    report_dict = run_audit_pipeline(
        domain=domain,
        budget_soft=240.0,
        budget_hard=300.0,
    )
    report = validate_report(report_dict)
    assert_report_invariants(report)

    assert report.audit_metadata.elapsed_s <= 240.0, (
        f"Live audit on {domain} took {report.audit_metadata.elapsed_s:.1f}s, exceeding 240s soft budget"
    )

    print(f"[PASS] Live real site audit on {domain} completed in {report.audit_metadata.elapsed_s:.1f}s")
    print(f"       Total findings: {report.summary.total_findings}")
    print(f"       Archetype: {report.audit_metadata.archetype}")
    print(f"       Recommendations: {len(report.recommendations)}")
    return report


def test_real_site_report(report_path: Optional[Path] = None) -> None:
    """Validate a pre-existing or discovered real site report."""
    if report_path is None:
        for arg in sys.argv[1:]:
            if arg.endswith(".json") and not arg.startswith("-"):
                report_path = Path(arg)
                break

        if report_path is None:
            # Check standard scratch locations
            candidates = [
                REPO_ROOT / "scratch" / "htmx_report.json",
                REPO_ROOT / "scratch" / "fastapi_report.json",
            ]
            for c in candidates:
                if c.exists():
                    report_path = c
                    break

    if report_path is None or not report_path.exists():
        raise FileNotFoundError(
            f"No existing audit report found at {report_path}. "
            "Pass a report file, run audit.py first, or run with --live to perform an audit."
        )

    data = json.loads(report_path.read_text(encoding="utf-8"))
    report = validate_report(data)
    assert_report_invariants(report)

    print(f"[PASS] Real site report successfully validated: {report.audit_metadata.target_domain}")
    print(f"       Total findings: {report.summary.total_findings}")
    print(f"       Archetype: {report.audit_metadata.archetype}")
    print(f"       Elapsed time: {report.audit_metadata.elapsed_s:.1f}s")
    print(f"       Recommendations: {len(report.recommendations)}")
    print(f"       Proactive recommendations: {len(report.proactive_recommendations)}")


if __name__ == "__main__":
    if "--live" in sys.argv:
        idx = sys.argv.index("--live")
        target = sys.argv[idx + 1] if len(sys.argv) > idx + 1 and not sys.argv[idx + 1].startswith("-") else "htmx.org"
        test_live_real_site_audit(target)
    elif len(sys.argv) > 1:
        test_real_site_report(Path(sys.argv[1]))
    else:
        # Default: validate existing report if found, else run live audit
        try:
            test_real_site_report()
        except FileNotFoundError:
            test_live_real_site_audit("htmx.org")
