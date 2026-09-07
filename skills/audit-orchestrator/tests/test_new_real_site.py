#!/usr/bin/env python3
"""
test_new_real_site.py — Validates end-to-end audit on a genuinely new real site.
"""

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[2]
SCRIPTS_DIR = _HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_report import validate_report


def test_real_site_report(report_path: Path | None = None):
    if report_path is None:
        if len(sys.argv) > 1:
            report_path = Path(sys.argv[1])
        else:
            report_path = REPO_ROOT / "scratch" / "fastapi_report.json"

    if not report_path.exists():
        raise FileNotFoundError(
            f"Expected real site audit report at {report_path}. "
            "Run an end-to-end audit (e.g. via audit.py) before running this test."
        )

    data = json.loads(report_path.read_text(encoding="utf-8"))
    report = validate_report(data)

    print(f"[PASS] Real site report successfully validated: {report.audit_metadata.target_domain}")
    print(f"       Total findings: {report.summary.total_findings}")
    print(f"       Archetype: {report.audit_metadata.archetype}")
    print(f"       Elapsed time: {report.audit_metadata.elapsed_s:.1f}s")
    print(f"       Proactive recommendations: {len(report.proactive_recommendations)}")

    # Generic report invariant assertions
    assert report.audit_metadata.target_domain, "Target domain must be non-empty"
    assert report.audit_metadata.archetype, "Archetype must be determined"
    assert report.summary.total_findings == len(report.findings), "Summary count must match findings list"
    assert report.audit_metadata.elapsed_s <= 300.0, "Audit must complete within 300s ceiling"
    if report.findings:
        assert len(report.recommendations) >= 1, "Report with findings must contain recommendations"


if __name__ == "__main__":
    test_real_site_report()

