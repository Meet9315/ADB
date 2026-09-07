#!/usr/bin/env python3
"""
validate_report.py — Independent validator for candidate findings and final audit reports.

Verifies:
- All required contract fields are present, non-empty, and non-placeholder.
- Invariant consistency (total_findings == len(findings) == sum(by_severity)).
- Finding ID uniqueness.
- Confidence range (0.0 <= c <= 1.0) and severity class validities.

Usage:
    python validate_report.py <report_or_candidate.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from models import CandidateFinding, FinalReport  # noqa: E402


def validate_candidate(data: Dict[str, Any]) -> CandidateFinding:
    """Validate a single candidate finding dictionary against CandidateFinding model."""
    return CandidateFinding.model_validate(data)


def validate_report(data: Dict[str, Any]) -> FinalReport:
    """Validate a final audit report dictionary against FinalReport model."""
    return FinalReport.model_validate(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit report and finding contract validator")
    parser.add_argument("file_path", help="Path to report or candidate JSON file")
    args = parser.parse_args()

    p = Path(args.file_path)
    if not p.exists():
        print(f"Error: file not found: {p}", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(p.read_text(encoding="utf-8"))

    if isinstance(raw, dict) and "audit_metadata" in raw:
        # Validate as FinalReport
        try:
            report = validate_report(raw)
            print(f"VALID FinalReport: domain='{report.audit_metadata.target_domain}', "
                  f"findings={len(report.findings)}, total={report.summary.total_findings}")
            sys.exit(0)
        except Exception as exc:
            print(f"INVALID FinalReport:\n{exc}", file=sys.stderr)
            sys.exit(1)
    elif isinstance(raw, dict) and "check_id" in raw:
        # Validate as CandidateFinding
        try:
            cand = validate_candidate(raw)
            print(f"VALID CandidateFinding: id='{cand.id}', check_id='{cand.check_id}'")
            sys.exit(0)
        except Exception as exc:
            print(f"INVALID CandidateFinding:\n{exc}", file=sys.stderr)
            sys.exit(1)
    elif isinstance(raw, list):
        # Validate list of findings
        errors = []
        is_final = any("final_severity" in item for item in raw if isinstance(item, dict))
        for idx, item in enumerate(raw):
            try:
                if is_final:
                    from models import FinalFinding
                    FinalFinding.model_validate(item)
                else:
                    validate_candidate(item)
            except Exception as exc:
                errors.append(f"Item #{idx} ({item.get('id', '?')}): {exc}")
        if errors:
            print(f"INVALID Findings Array ({len(errors)} errors):", file=sys.stderr)
            for err in errors[:10]:
                print(f"  - {err}", file=sys.stderr)
            sys.exit(1)
        else:
            kind = "FinalFinding" if is_final else "CandidateFinding"
            print(f"VALID {kind} Array: {len(raw)} findings verified successfully.")
            sys.exit(0)
    else:
        print("Error: unrecognized JSON structure. Must be a FinalReport, CandidateFinding, or candidate array.",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
