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


def test_real_site_report():
    report_file = REPO_ROOT / "scratch" / "fastapi_report.json"
    if not report_file.exists():
        print(f"Report not yet generated at {report_file}; skipping check.")
        return

    data = json.loads(report_file.read_text(encoding="utf-8"))
    report = validate_report(data)

    print(f"[PASS] Real site report successfully validated: {report.audit_metadata.target_domain}")
    print(f"       Total findings: {report.summary.total_findings}")
    print(f"       Archetype: {report.audit_metadata.archetype}")
    print(f"       Elapsed time: {report.audit_metadata.elapsed_s:.1f}s")
    print(f"       Proactive recommendations: {len(report.proactive_recommendations)}")
    assert report.audit_metadata.target_domain == "fastapi.tiangolo.com"
    assert report.summary.total_findings == len(report.findings)


if __name__ == "__main__":
    test_real_site_report()
