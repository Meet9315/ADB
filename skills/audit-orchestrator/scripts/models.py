#!/usr/bin/env python3
"""
models.py — Canonical Pydantic validation models for audit-orchestrator.

Enforces the Hardened Finding Contract, validates candidate findings and final reports,
and implements strict contract linting (rejecting missing, empty, whitespace-only,
and placeholder values across contract fields and evidence sub-fields).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional, Set
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Obvious placeholder values that must be rejected case-insensitively
PLACEHOLDER_VALUES: Set[str] = {
    "tbd",
    "todo",
    "n/a",
    "na",
    "not available",
    "none",
    "placeholder",
    "unknown",
    "null",
    "nil",
}

RootCauseType = Literal[
    "representation_gap",
    "statement_implicitness",
    "identity_irresolution",
    "corroboration_deficit",
    "temporal_decay",
    "orientation_cost",
]

SeverityClassType = Literal["critical", "high", "medium", "low"]

CheckIdType = Literal[
    "R1", "R2", "R3", "R4", "R5",
    "D1", "D2", "D3",
    "E1", "E2", "E3", "E4",
    "T1", "T2", "T3", "T4",
    "G1", "G2", "G3", "G4",
]


def _validate_non_empty_non_placeholder(field_name: str, value: Any) -> str:
    """Validate that a string value is not empty, not whitespace, and not a placeholder."""
    if not isinstance(value, str):
        raise ValueError(f"Field '{field_name}' must be a string, got {type(value).__name__}")

    stripped = value.strip()
    if not stripped:
        raise ValueError(f"Field '{field_name}' cannot be empty or whitespace-only")

    if stripped.lower() in PLACEHOLDER_VALUES:
        raise ValueError(
            f"Field '{field_name}' contains prohibited placeholder value '{value}'"
        )

    return stripped


def _recursively_validate_evidence(path: str, val: Any) -> None:
    """Check that all string values inside evidence are non-empty and not placeholders."""
    if isinstance(val, str):
        stripped = val.strip()
        if not stripped:
            raise ValueError(f"Evidence string at '{path}' cannot be empty or whitespace-only")
        if stripped.lower() in PLACEHOLDER_VALUES:
            raise ValueError(f"Evidence field '{path}' contains prohibited placeholder value '{val}'")
    elif isinstance(val, dict):
        for k, v in val.items():
            _recursively_validate_evidence(f"{path}.{k}" if path else k, v)
    elif isinstance(val, (list, tuple)):
        for idx, item in enumerate(val):
            _recursively_validate_evidence(f"{path}[{idx}]", item)


class CandidateFinding(BaseModel):
    """
    Hardened candidate finding contract.
    Analysis skills emit findings in this exact shape.
    Every field is strictly required; none optional; none placeholder.
    """
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Unique finding ID, e.g. F-D1-001")
    check_id: CheckIdType = Field(..., description="Check identifier, e.g. D1")
    page_url: str = Field(..., description="URL of the page where the issue was observed")
    root_cause: RootCauseType = Field(..., description="Diagnostic root cause classification")
    evidence: Dict[str, Any] = Field(..., description="Concrete extracted evidence values")
    raw_severity_class: SeverityClassType = Field(..., description="Severity class")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    mechanism: str = Field(..., description="Diagnostic mechanism explaining why this is an issue")
    false_positive_guard: str = Field(..., description="Data verifying false-positive check passed")
    verification_method: str = Field(..., description="Concrete command to verify in < 2 minutes")

    @field_validator("id", "page_url", "root_cause", "mechanism", "false_positive_guard", "verification_method", mode="before")
    @classmethod
    def validate_strings(cls, v: Any, info: Any) -> str:
        return _validate_non_empty_non_placeholder(info.field_name, v)

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence(cls, v: Any) -> Dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError(f"Evidence must be a dictionary, got {type(v).__name__}")
        if not v:
            raise ValueError("Evidence dictionary cannot be empty")
        _recursively_validate_evidence("evidence", v)
        return v


class SuggestedAction(BaseModel):
    """Actionable remediation or proactive recommendation."""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    code_snippet: Optional[str] = None
    priority: SeverityClassType = Field(...)


class FinalFinding(BaseModel):
    """
    Deduplicated, scored, and recommendation-enriched finding for the final audit report.
    """
    model_config = ConfigDict(extra="forbid")

    id: str = Field(...)
    check_id: CheckIdType = Field(...)
    page_url: str = Field(...)
    root_cause: RootCauseType = Field(...)
    evidence: Dict[str, Any] = Field(...)
    raw_severity_class: SeverityClassType = Field(...)
    final_severity: SeverityClassType = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)
    mechanism: str = Field(...)
    false_positive_guard: str = Field(...)
    verification_method: str = Field(...)
    suggested_action: SuggestedAction = Field(...)
    deduped_occurrences: int = Field(default=1, ge=1)
    affected_urls: List[str] = Field(default_factory=list)

    @field_validator("id", "page_url", "mechanism", "false_positive_guard", "verification_method", mode="before")
    @classmethod
    def validate_strings(cls, v: Any, info: Any) -> str:
        return _validate_non_empty_non_placeholder(info.field_name, v)

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence(cls, v: Any) -> Dict[str, Any]:
        if not isinstance(v, dict) or not v:
            raise ValueError("Evidence must be a non-empty dictionary")
        _recursively_validate_evidence("evidence", v)
        return v


class SummaryCounts(BaseModel):
    """Summary metrics of audit findings."""
    model_config = ConfigDict(extra="forbid")

    total_findings: int = Field(..., ge=0)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_root_cause: Dict[str, int] = Field(default_factory=dict)
    by_check_id: Dict[str, int] = Field(default_factory=dict)


class AuditMetadata(BaseModel):
    """Metadata describing the target site, timing, and budget state."""
    model_config = ConfigDict(extra="forbid")

    target_domain: str = Field(..., min_length=1)
    base_url: str = Field(..., min_length=1)
    archetype: str = Field(..., min_length=1)
    is_tiny_site: bool = Field(default=False)
    started_at: str = Field(..., min_length=1)
    completed_at: str = Field(..., min_length=1)
    elapsed_s: float = Field(..., ge=0.0)
    partial_audit: bool = Field(default=False)
    partial_audit_reason: Optional[str] = None


class FinalReport(BaseModel):
    """
    Canonical audit report schema.
    Emitted by build_report.py and verified by validate_report.py.
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0")
    audit_metadata: AuditMetadata = Field(...)
    summary: SummaryCounts = Field(...)
    findings: List[FinalFinding] = Field(default_factory=list)
    proactive_recommendations: List[SuggestedAction] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_report_invariants(self) -> FinalReport:
        # 1. Verify no duplicate finding IDs
        seen_ids: Set[str] = set()
        for f in self.findings:
            if f.id in seen_ids:
                raise ValueError(f"Duplicate finding ID found in report: '{f.id}'")
            seen_ids.add(f.id)

        # 2. Verify summary count consistency
        if self.summary.total_findings != len(self.findings):
            raise ValueError(
                f"Summary total_findings ({self.summary.total_findings}) does not match "
                f"actual findings count ({len(self.findings)})"
            )

        severity_sum = sum(self.summary.by_severity.values())
        if severity_sum != len(self.findings):
            raise ValueError(
                f"Sum of by_severity ({severity_sum}) does not match findings count ({len(self.findings)})"
            )

        root_cause_sum = sum(self.summary.by_root_cause.values())
        if root_cause_sum != len(self.findings):
            raise ValueError(
                f"Sum of by_root_cause ({root_cause_sum}) does not match findings count ({len(self.findings)})"
            )

        return self

    def to_deterministic_json(self) -> str:
        """
        Serialize report to JSON deterministically.
        Uses sorted keys, uniform 2-space indentation, and UTF-8 encoding.
        """
        data = self.model_dump(mode="json")
        return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
