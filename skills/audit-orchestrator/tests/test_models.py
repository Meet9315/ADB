#!/usr/bin/env python3
"""
test_models.py — Comprehensive unit tests for audit-orchestrator Pydantic models and CLI.

Tests:
1. Valid CandidateFinding and FinalReport models.
2. Missing, empty-string, and whitespace-only values across required contract fields.
3. Missing and empty evidence dictionary.
4. Obvious placeholder values ("TBD", "TODO", "N/A", "not available") in required contract
   fields (including case variants and surrounding whitespace).
5. Placeholder values in string-valued evidence sub-fields (e.g. snippet, value, details).
6. Invalid confidence values (<0, >1, non-float) and invalid severity classes.
7. Duplicate finding IDs in FinalReport.
8. Inconsistent summary counts.
9. Deterministic JSON serialization (byte-for-byte equality).
10. Typer CLI commands (run, merge, validate).
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
from pydantic import ValidationError

_HERE = Path(__file__).resolve().parent
SCRIPTS_DIR = _HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_report import build_final_report, serialize_report  # noqa: E402
from models import AuditMetadata, CandidateFinding, FinalFinding, FinalReport, SuggestedAction, SummaryCounts  # noqa: E402
from validate_report import validate_candidate, validate_report  # noqa: E402


VALID_CANDIDATE: Dict[str, Any] = {
    "id": "F-D1-001",
    "check_id": "D1",
    "page_url": "https://example.com/pricing",
    "root_cause": "representation_gap",
    "evidence": {
        "raw_word_count": 45,
        "rendered_word_count": 520,
        "missing_word_count": 475,
        "missing_word_ratio": 0.913,
        "post_render_fact": "Enterprise tier costs $499 monthly with custom SLA",
    },
    "raw_severity_class": "critical",
    "confidence": 0.92,
    "mechanism": "Page requires client-side JS rendering; raw HTML contains only 45 words omitting critical pricing facts.",
    "false_positive_guard": "Verified missing word ratio >40% (91.3%) and absolute gap >300 words (475 words).",
    "verification_method": "curl -sL https://example.com/pricing | wc -w",
}


# ── 1. Valid Model Tests ──────────────────────────────────────────────────

def test_valid_candidate_finding():
    """Verify that a compliant candidate finding parses successfully."""
    cand = CandidateFinding.model_validate(VALID_CANDIDATE)
    assert cand.id == "F-D1-001"
    assert cand.check_id == "D1"
    assert cand.root_cause == "representation_gap"
    assert cand.confidence == 0.92
    assert cand.evidence["raw_word_count"] == 45


def test_valid_final_report():
    """Verify that a compliant FinalReport parses successfully."""
    cand = CandidateFinding.model_validate(VALID_CANDIDATE)
    action = SuggestedAction(
        title="Implement Server-Side Rendering (SSR)",
        description="Render dynamic content on the server so crawlers receive full text.",
        code_snippet="export async function getServerSideProps() { ... }",
        priority="critical",
        linked_findings=[cand.id],
    )
    final_f = FinalFinding(
        **cand.model_dump(),
        final_severity="critical",
        suggested_action=action,
        deduped_occurrences=1,
        affected_urls=["https://example.com/pricing"],
    )
    report = build_final_report(
        target_domain="example.com",
        base_url="https://example.com",
        archetype="saas",
        is_tiny_site=False,
        started_at="2026-09-07T00:00:00Z",
        completed_at="2026-09-07T00:01:30Z",
        elapsed_s=90.0,
        findings=[final_f],
    )
    assert report.summary.total_findings == 1
    assert report.summary.by_severity["critical"] == 1
    assert len(report.findings) == 1


# ── 2. Missing, Empty-String, and Whitespace-Only Fields ───────────────────

@pytest.mark.parametrize("field", [
    "root_cause",
    "mechanism",
    "false_positive_guard",
    "verification_method",
])
def test_missing_required_contract_field(field: str):
    """Test that omitting a required contract field raises ValidationError."""
    data = copy.deepcopy(VALID_CANDIDATE)
    del data[field]
    with pytest.raises(ValidationError):
        CandidateFinding.model_validate(data)


@pytest.mark.parametrize("field", [
    "root_cause",
    "mechanism",
    "false_positive_guard",
    "verification_method",
])
@pytest.mark.parametrize("bad_value", [
    "",
    "   ",
    "\t",
    "\n\n",
])
def test_empty_or_whitespace_contract_field(field: str, bad_value: str):
    """Test that empty strings and whitespace-only values are strictly rejected."""
    data = copy.deepcopy(VALID_CANDIDATE)
    data[field] = bad_value
    with pytest.raises(ValidationError):
        CandidateFinding.model_validate(data)


# ── 3. Missing and Empty Evidence ─────────────────────────────────────────

def test_missing_evidence():
    """Test that missing evidence dictionary is rejected."""
    data = copy.deepcopy(VALID_CANDIDATE)
    del data["evidence"]
    with pytest.raises(ValidationError):
        CandidateFinding.model_validate(data)


def test_empty_evidence_dict():
    """Test that an empty evidence dictionary is rejected."""
    data = copy.deepcopy(VALID_CANDIDATE)
    data["evidence"] = {}
    with pytest.raises(ValidationError):
        CandidateFinding.model_validate(data)


# ── 4. Placeholder Values in Contract Fields ──────────────────────────────

@pytest.mark.parametrize("field", [
    "mechanism",
    "false_positive_guard",
    "verification_method",
])
@pytest.mark.parametrize("placeholder", [
    "TBD",
    "tbd",
    "  TBD  ",
    "TODO",
    "todo",
    "N/A",
    "n/a",
    "NA",
    "na",
    "not available",
    "NOT AVAILABLE",
    "  Not Available  ",
    "none",
    "NONE",
    "placeholder",
    "unknown",
])
def test_placeholder_values_in_contract_fields(field: str, placeholder: str):
    """Test case-insensitive rejection of placeholder values in top-level fields."""
    data = copy.deepcopy(VALID_CANDIDATE)
    data[field] = placeholder
    with pytest.raises(ValidationError):
        CandidateFinding.model_validate(data)


# ── 5. Placeholder Values in Evidence Sub-Fields ──────────────────────────

@pytest.mark.parametrize("placeholder", [
    "TBD",
    "TODO",
    "n/a",
    "not available",
    "none",
    "  TODO  ",
    "  N/A  ",
])
def test_placeholder_in_evidence_string_subfield(placeholder: str):
    """Test that string sub-fields inside evidence reject placeholders."""
    data = copy.deepcopy(VALID_CANDIDATE)
    data["evidence"]["post_render_fact"] = placeholder
    with pytest.raises(ValidationError):
        CandidateFinding.model_validate(data)


def test_placeholder_in_nested_evidence_subfield():
    """Test that nested dicts and lists inside evidence also reject placeholders."""
    # Nested dict
    data = copy.deepcopy(VALID_CANDIDATE)
    data["evidence"]["nested"] = {"details": "TODO"}
    with pytest.raises(ValidationError):
        CandidateFinding.model_validate(data)

    # Nested list
    data2 = copy.deepcopy(VALID_CANDIDATE)
    data2["evidence"]["samples"] = ["valid sample", "TBD"]
    with pytest.raises(ValidationError):
        CandidateFinding.model_validate(data2)


# ── 6. Invalid Confidence and Severity Values ─────────────────────────────

@pytest.mark.parametrize("bad_confidence", [-0.1, 1.05, 2.0, "high"])
def test_invalid_confidence_values(bad_confidence: Any):
    """Test confidence bounds (must be 0.0 <= confidence <= 1.0)."""
    data = copy.deepcopy(VALID_CANDIDATE)
    data["confidence"] = bad_confidence
    with pytest.raises(ValidationError):
        CandidateFinding.model_validate(data)


@pytest.mark.parametrize("bad_severity", ["urgent", "info", "warning", "catastrophic"])
def test_invalid_severity_class(bad_severity: str):
    """Test severity class enum constraints."""
    data = copy.deepcopy(VALID_CANDIDATE)
    data["raw_severity_class"] = bad_severity
    with pytest.raises(ValidationError):
        CandidateFinding.model_validate(data)


# ── 7. Duplicate Finding IDs in Report ────────────────────────────────────

def test_duplicate_finding_ids_in_report():
    """Test that a report containing duplicate finding IDs is rejected."""
    cand = CandidateFinding.model_validate(VALID_CANDIDATE)
    action = SuggestedAction(
        title="Action 1",
        description="Description 1",
        priority="critical",
        linked_findings=[cand.id],
    )
    f1 = FinalFinding(
        **cand.model_dump(),
        final_severity="critical",
        suggested_action=action,
        deduped_occurrences=1,
        affected_urls=["https://example.com/1"],
    )
    f2 = FinalFinding(
        **cand.model_dump(),  # same ID: F-D1-001
        final_severity="critical",
        suggested_action=action,
        deduped_occurrences=1,
        affected_urls=["https://example.com/2"],
    )
    with pytest.raises(ValidationError, match="Duplicate finding ID"):
        build_final_report(
            target_domain="example.com",
            base_url="https://example.com",
            archetype="saas",
            is_tiny_site=False,
            started_at="2026-09-07T00:00:00Z",
            completed_at="2026-09-07T00:01:00Z",
            elapsed_s=60.0,
            findings=[f1, f2],
        )


# ── 8. Inconsistent Summary Counts ────────────────────────────────────────

def test_inconsistent_summary_counts():
    """Test that manually tampering with SummaryCounts causes validation failure."""
    cand = CandidateFinding.model_validate(VALID_CANDIDATE)
    action = SuggestedAction(
        title="Action 1",
        description="Description 1",
        priority="critical",
        linked_findings=[cand.id],
    )
    f1 = FinalFinding(
        **cand.model_dump(),
        final_severity="critical",
        suggested_action=action,
        deduped_occurrences=1,
        affected_urls=["https://example.com/1"],
    )
    report = build_final_report(
        target_domain="example.com",
        base_url="https://example.com",
        archetype="saas",
        is_tiny_site=False,
        started_at="2026-09-07T00:00:00Z",
        completed_at="2026-09-07T00:01:00Z",
        elapsed_s=60.0,
        findings=[f1],
    )

    # Tamper with total_findings
    report_dict = report.model_dump()
    report_dict["summary"]["total_findings"] = 99  # Actual count is 1
    with pytest.raises(ValidationError, match="does not match actual findings count"):
        FinalReport.model_validate(report_dict)

    # Tamper with severity sum
    report_dict2 = report.model_dump()
    report_dict2["summary"]["by_severity"]["critical"] = 5
    with pytest.raises(ValidationError, match="Sum of by_severity"):
        FinalReport.model_validate(report_dict2)


# ── 9. Deterministic JSON Serialization ───────────────────────────────────

def test_deterministic_json_serialization():
    """Verify that serializing the same report multiple times produces identical bytes."""
    cand = CandidateFinding.model_validate(VALID_CANDIDATE)
    action = SuggestedAction(
        title="SSR Implementation",
        description="Ensure dynamic text is present in server HTML.",
        code_snippet="export async function getServerSideProps() { ... }",
        priority="critical",
        linked_findings=[cand.id],
    )
    f = FinalFinding(
        **cand.model_dump(),
        final_severity="critical",
        suggested_action=action,
        deduped_occurrences=1,
        affected_urls=["https://example.com/pricing"],
    )
    report = build_final_report(
        target_domain="example.com",
        base_url="https://example.com",
        archetype="saas",
        is_tiny_site=False,
        started_at="2026-09-07T00:00:00Z",
        completed_at="2026-09-07T00:01:00Z",
        elapsed_s=60.0,
        findings=[f],
    )

    json_run_1 = report.to_deterministic_json().encode("utf-8")
    json_run_2 = report.to_deterministic_json().encode("utf-8")
    json_run_3 = serialize_report(report).encode("utf-8")

    assert json_run_1 == json_run_2
    assert json_run_2 == json_run_3


# ── 10. Typer CLI Commands ────────────────────────────────────────────────

def test_typer_cli_help():
    """Verify that the Typer CLI responds to --help with code 0."""
    audit_script = SCRIPTS_DIR / "audit.py"
    res = subprocess.run([sys.executable, str(audit_script), "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "AI Discoverability Audit Orchestrator CLI" in res.stdout
    assert "run" in res.stdout
    assert "merge" in res.stdout
    assert "validate" in res.stdout


def test_typer_cli_merge_and_validate(tmp_path: Path):
    """Test merge and validate subcommands via Typer CLI."""
    audit_script = SCRIPTS_DIR / "audit.py"

    # Create temporary candidates JSON
    candidates_file = tmp_path / "test_candidates.json"
    candidates_file.write_text(json.dumps([VALID_CANDIDATE]), encoding="utf-8")

    # 1. Test CLI merge
    merged_file = tmp_path / "test_merged.json"
    res_merge = subprocess.run(
        [sys.executable, str(audit_script), "merge", str(candidates_file), "--output", str(merged_file)],
        capture_output=True, text=True,
    )
    assert res_merge.returncode == 0
    assert merged_file.exists()

    # 2. Test CLI validate on merged file
    res_val = subprocess.run(
        [sys.executable, str(audit_script), "validate", str(merged_file)],
        capture_output=True, text=True,
    )
    assert res_val.returncode == 0
    assert "VALID" in res_val.stdout


# ── 11. Traceability & Orphan Recommendation Rejection Tests ──────────────

def test_reject_orphan_recommendation_empty_linked_findings():
    """Verify that a non-proactive SuggestedAction with empty linked_findings is rejected."""
    with pytest.raises(ValidationError, match="Orphan recommendation"):
        SuggestedAction(
            title="Update robots.txt",
            description="Allow discovery crawlers in robots.txt.",
            priority="critical",
            linked_findings=[],
            is_proactive=False,
        )


@pytest.mark.parametrize("bad_fid", ["", "   ", "TBD", "N/A", "todo", "none"])
def test_reject_orphan_recommendation_placeholder_linked_findings(bad_fid: str):
    """Verify that placeholder or empty finding IDs in linked_findings are rejected."""
    with pytest.raises(ValidationError):
        SuggestedAction(
            title="Update robots.txt",
            description="Allow discovery crawlers in robots.txt.",
            priority="critical",
            linked_findings=[bad_fid],
            is_proactive=False,
        )


def test_accept_proactive_recommendation_without_linked_findings():
    """Verify that proactive recommendations (is_proactive=True) do not require linked findings."""
    action = SuggestedAction(
        title="Deploy an /llms.txt Machine-Readable Context File",
        description="Deploy an /llms.txt endpoint describing site APIs and docs.",
        code_snippet="# /llms.txt",
        priority="medium",
        linked_findings=[],
        is_proactive=True,
    )
    assert action.is_proactive is True
    assert action.linked_findings == []


def test_final_finding_rejects_mismatched_action_link():
    """Verify that FinalFinding enforces that its ID is in suggested_action.linked_findings."""
    cand = CandidateFinding.model_validate(VALID_CANDIDATE)
    action = SuggestedAction(
        title="SSR Implementation",
        description="Dynamic content on server.",
        priority="critical",
        linked_findings=["OTHER-FINDING-999"],  # Mismatched ID
        is_proactive=False,
    )
    with pytest.raises(ValidationError, match="does not link back to this finding's ID"):
        FinalFinding(
            **cand.model_dump(),
            final_severity="critical",
            suggested_action=action,
            deduped_occurrences=1,
            affected_urls=["https://example.com/pricing"],
        )


def test_final_report_rejects_orphan_recommendation_nonexistent_finding_id():
    """Verify that FinalReport rejects recommendations linking to non-existent finding IDs."""
    cand = CandidateFinding.model_validate(VALID_CANDIDATE)
    action = SuggestedAction(
        title="SSR Implementation",
        description="Dynamic content on server.",
        priority="critical",
        linked_findings=[cand.id],
    )
    f = FinalFinding(
        **cand.model_dump(),
        final_severity="critical",
        suggested_action=action,
        deduped_occurrences=1,
        affected_urls=["https://example.com/pricing"],
    )
    report = build_final_report(
        target_domain="example.com",
        base_url="https://example.com",
        archetype="saas",
        is_tiny_site=False,
        started_at="2026-09-07T00:00:00Z",
        completed_at="2026-09-07T00:01:00Z",
        elapsed_s=60.0,
        findings=[f],
    )
    report_dict = report.model_dump()
    # Inject an orphan recommendation referencing a non-existent finding
    report_dict["recommendations"].append({
        "id": "REC-999",
        "title": "Fix Broken Links",
        "description": "Remove dead links.",
        "code_snippet": None,
        "priority": "medium",
        "linked_findings": ["FINDING-NON-EXISTENT"],
        "is_proactive": False,
    })
    with pytest.raises(ValidationError, match="references non-existent finding ID"):
        FinalReport.model_validate(report_dict)


def test_final_report_consolidates_recommendations_and_preserves_traceability():
    """Verify that build_final_report populates report.recommendations with linked_findings."""
    cand = CandidateFinding.model_validate(VALID_CANDIDATE)
    action = SuggestedAction(
        title="SSR Implementation",
        description="Dynamic content on server.",
        priority="critical",
        linked_findings=[cand.id],
    )
    f = FinalFinding(
        **cand.model_dump(),
        final_severity="critical",
        suggested_action=action,
        deduped_occurrences=1,
        affected_urls=["https://example.com/pricing"],
    )
    report = build_final_report(
        target_domain="example.com",
        base_url="https://example.com",
        archetype="saas",
        is_tiny_site=False,
        started_at="2026-09-07T00:00:00Z",
        completed_at="2026-09-07T00:01:00Z",
        elapsed_s=60.0,
        findings=[f],
    )
    assert len(report.recommendations) >= 1
    rec = report.recommendations[0]
    assert rec.id == "REC-001"
    assert rec.linked_findings == [cand.id]
    assert rec.is_proactive is False
    # Verify proactive recommendations have is_proactive=True and empty linked_findings
    for pro in report.proactive_recommendations:
        assert pro.is_proactive is True
        assert pro.linked_findings == []


def test_final_report_rejects_missing_recommendations_when_findings_exist():
    """Verify that FinalReport rejects empty recommendations when findings are present, refusing silent repair."""
    cand = CandidateFinding.model_validate(VALID_CANDIDATE)
    action = SuggestedAction(
        title="SSR Implementation",
        description="Dynamic content on server.",
        priority="critical",
        linked_findings=[cand.id],
    )
    f = FinalFinding(
        **cand.model_dump(),
        final_severity="critical",
        suggested_action=action,
        deduped_occurrences=1,
        affected_urls=["https://example.com/pricing"],
    )
    report = build_final_report(
        target_domain="example.com",
        base_url="https://example.com",
        archetype="saas",
        is_tiny_site=False,
        started_at="2026-09-07T00:00:00Z",
        completed_at="2026-09-07T00:01:00Z",
        elapsed_s=60.0,
        findings=[f],
    )
    report_dict = report.model_dump()
    report_dict["recommendations"] = []  # Intentionally empty when findings exist
    with pytest.raises(ValidationError, match="recommendations' list is empty"):
        FinalReport.model_validate(report_dict)



