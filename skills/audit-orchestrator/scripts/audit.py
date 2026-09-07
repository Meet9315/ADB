#!/usr/bin/env python3
"""
audit.py — Thin Typer CLI orchestrator for end-to-end AI discoverability audits.

Coordinates:
1. Site acquisition (crawl.py & render.py)
2. Reach checks (reach_checks.py)
3. Machine readability checks (check_noindex.py, check_d1.py, check_d2.py, check_e2.py, check_e3.py)
4. Archetype classification (archetype.py)
5. Finding deduplication and scoring (merge_findings.py)
6. Final report assembly and validation (build_report.py & validate_report.py)
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[2]

sys.path.insert(0, str(_HERE))
from build_report import build_final_report, serialize_report  # noqa: E402
from merge_findings import merge_candidate_findings  # noqa: E402
from validate_report import validate_candidate, validate_report  # noqa: E402

app = typer.Typer(help="AI Discoverability Audit Orchestrator CLI")


def _run_cmd(cmd: List[str], timeout: Optional[float] = None) -> Tuple[int, str, str]:
    """Execute command synchronously and return returncode, stdout, stderr, respecting timeout."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired as exc:
        return -1, exc.stdout or "", exc.stderr or "Subprocess timed out exceeding hard budget ceiling"


def run_audit_pipeline(
    domain: str,
    output_dir: Optional[Path] = None,
    budget_soft: float = 240.0,
    budget_hard: float = 300.0,
) -> Dict[str, Any]:
    """
    Internal programmatic function executing the full audit pipeline.
    Reused identically by CLI and tests.
    """
    t0 = time.monotonic()
    started_iso = datetime.now(timezone.utc).isoformat()

    def _rem_timeout() -> float:
        return max(1.0, budget_hard - (time.monotonic() - t0))

    if output_dir is None:
        clean_domain = domain.replace("https://", "").replace("http://", "").split("/")[0].replace(":", "_")
        output_dir = REPO_ROOT / "scratch" / f"audit_{clean_domain}_{int(time.time())}"

    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_pages = output_dir / "pages"
    manifest_path = output_dir / "crawl_manifest.json"

    typer.echo(f"[*] Starting audit for {domain} (output: {output_dir})")

    # 1. Acquisition: crawl.py
    crawl_script = REPO_ROOT / "skills" / "site-acquisition" / "scripts" / "crawl.py"
    typer.echo("    [1/6] Crawling site pages...")
    code, stdout, stderr = _run_cmd([
        sys.executable, str(crawl_script),
        domain,
        "--output-dir", str(corpus_pages),
        "--budget-soft", str(budget_soft),
        "--budget-hard", str(budget_hard),
    ], timeout=_rem_timeout())
    if code != 0:
        typer.echo(f"    [!] Crawl returned non-zero code {code}: {stderr}", err=True)

    # 2. Rendering: render.py
    render_script = REPO_ROOT / "skills" / "site-acquisition" / "scripts" / "render.py"
    typer.echo("    [2/6] Rendering sampled pages with Playwright...")
    if manifest_path.exists() and corpus_pages.exists() and (time.monotonic() - t0) < (budget_hard - 10.0):
        _run_cmd([
            sys.executable, str(render_script),
            str(corpus_pages),
            str(manifest_path),
            "--budget-soft", str(budget_soft),
            "--budget-hard", str(budget_hard),
        ], timeout=_rem_timeout())

    # Check budget from manifest
    manifest_data: Dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    base_url = manifest_data.get("base_url", f"https://{domain}")
    elapsed_so_far = time.monotonic() - t0
    partial_audit = elapsed_so_far >= (budget_hard - 20.0)
    partial_reason = "Hard budget deadline approaching; remaining analysis bounded." if partial_audit else None

    # 3. Archetype classification
    archetype_script = REPO_ROOT / "skills" / "machine-readability-audit" / "scripts" / "archetype.py"
    typer.echo("    [3/6] Inferring site archetype...")
    arch_res: Dict[str, Any] = {}
    if manifest_path.exists() and (time.monotonic() - t0) < (budget_hard - 5.0):
        code, stdout, stderr = _run_cmd([
            sys.executable, str(archetype_script),
            str(manifest_path),
            "--corpus-dir", str(corpus_pages),
        ], timeout=_rem_timeout())
        if code == -1:
            partial_audit = True
            partial_reason = f"Stage timed out to enforce {budget_hard}s hard ceiling."
        else:
            try:
                arch_res = json.loads(stdout)
            except Exception:
                pass

    primary_archetype = arch_res.get("archetypes", ["unknown"])[0] if arch_res.get("archetypes") else "unknown"
    is_tiny = arch_res.get("is_tiny_site", False)

    # 4. Analysis checks
    typer.echo("    [4/6] Executing analysis checks (R-series, D-series, E-series, T-series)...")
    raw_candidates: List[Dict[str, Any]] = []

    # Reach checks (R1, R2, R3, R5)
    reach_script = REPO_ROOT / "skills" / "site-acquisition" / "scripts" / "reach_checks.py"
    if manifest_path.exists() and (time.monotonic() - t0) < (budget_hard - 5.0):
        code, stdout, _ = _run_cmd([
            sys.executable, str(reach_script),
            str(manifest_path),
            "--checks", "R1", "R2", "R3", "R5",
            "--corpus-dir", str(corpus_pages),
        ], timeout=_rem_timeout())
        if code == -1:
            partial_audit = True
            partial_reason = f"Stage timed out to enforce {budget_hard}s hard ceiling."
        else:
            try:
                raw_candidates.extend(json.loads(stdout))
            except Exception:
                pass

    # Machine readability and Trust signals checks
    mra_scripts = REPO_ROOT / "skills" / "machine-readability-audit" / "scripts"
    tsa_scripts = REPO_ROOT / "skills" / "trust-signals-audit" / "scripts"
    checks = [
        mra_scripts / "check_noindex.py",  # R4
        mra_scripts / "check_d1.py",       # D1
        mra_scripts / "check_d2.py",       # D2
        mra_scripts / "check_d3.py",       # D3
        mra_scripts / "check_e1.py",       # E1
        mra_scripts / "check_e2.py",       # E2
        mra_scripts / "check_e3.py",       # E3
        mra_scripts / "check_e4.py",       # E4
        tsa_scripts / "check_t1.py",       # T1
        tsa_scripts / "check_t2.py",       # T2
        tsa_scripts / "check_t3.py",       # T3
        tsa_scripts / "check_t4.py",       # T4
    ]

    for cscript in checks:
        if (time.monotonic() - t0) >= (budget_hard - 3.0):
            partial_audit = True
            partial_reason = f"Stage timed out to enforce {budget_hard}s hard ceiling."
            break
        if cscript.exists() and corpus_pages.exists():
            code, stdout, _ = _run_cmd([
                sys.executable, str(cscript),
                str(corpus_pages),
                "--manifest", str(manifest_path),
            ], timeout=_rem_timeout())
            if code == -1:
                partial_audit = True
                partial_reason = f"Stage timed out to enforce {budget_hard}s hard ceiling."
            else:
                try:
                    res = json.loads(stdout)
                    if isinstance(res, list):
                        raw_candidates.extend(res)
                except Exception:
                    pass

    # 5. Merging & Deduplication
    typer.echo(f"    [5/6] Merging and validating {len(raw_candidates)} candidate findings...")
    merged_findings = merge_candidate_findings(raw_candidates)

    # 6. Report generation
    total_elapsed = time.monotonic() - t0
    completed_iso = datetime.now(timezone.utc).isoformat()
    typer.echo("    [6/6] Assembling final audit report...")

    report = build_final_report(
        target_domain=domain,
        base_url=base_url,
        archetype=primary_archetype,
        is_tiny_site=is_tiny,
        started_at=started_iso,
        completed_at=completed_iso,
        elapsed_s=total_elapsed,
        findings=merged_findings,
        partial_audit=partial_audit,
        partial_audit_reason=partial_reason,
    )

    return report.model_dump(mode="json")


@app.command()
def run(
    domain: str = typer.Argument(..., help="Target website domain, e.g. example.com"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Path to write the report JSON"),
    budget_soft: float = typer.Option(240.0, "--budget-soft", help="Soft budget in seconds"),
    budget_hard: float = typer.Option(300.0, "--budget-hard", help="Hard budget in seconds"),
) -> None:
    """Run an end-to-end audit on a domain and produce a validated audit report."""
    report_dict = run_audit_pipeline(
        domain=domain,
        budget_soft=budget_soft,
        budget_hard=budget_hard,
    )
    validated = validate_report(report_dict)
    deterministic_json = validated.to_deterministic_json()

    if output:
        output.write_text(deterministic_json, encoding="utf-8")
        typer.echo(f"\n[+] Audit complete! Report saved to {output}")
    else:
        typer.echo(deterministic_json)


@app.command()
def merge(
    candidates_file: Path = typer.Argument(..., help="JSON file containing raw candidates array"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path for merged JSON"),
) -> None:
    """Validate and deduplicate a JSON list of candidate findings."""
    raw = json.loads(candidates_file.read_text(encoding="utf-8"))
    merged = merge_candidate_findings(raw)
    out_json = json.dumps([f.model_dump(mode="json") for f in merged], indent=2, sort_keys=True)
    if output:
        output.write_text(out_json, encoding="utf-8")
        typer.echo(f"Merged {len(raw)} candidates into {len(merged)} findings -> {output}")
    else:
        typer.echo(out_json)


@app.command()
def validate(
    target_file: Path = typer.Argument(..., help="JSON file to validate (CandidateFinding or FinalReport)"),
) -> None:
    """Validate a candidate finding, candidate list, or final report against Pydantic models."""
    raw = json.loads(target_file.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "audit_metadata" in raw:
        report = validate_report(raw)
        typer.echo(f"VALID FinalReport for '{report.audit_metadata.target_domain}' ({len(report.findings)} findings)")
    elif isinstance(raw, dict) and "check_id" in raw:
        cand = validate_candidate(raw)
        typer.echo(f"VALID CandidateFinding '{cand.id}' ({cand.check_id})")
    elif isinstance(raw, list):
        is_final = any("final_severity" in item for item in raw if isinstance(item, dict))
        for idx, item in enumerate(raw):
            if is_final:
                from models import FinalFinding
                FinalFinding.model_validate(item)
            else:
                validate_candidate(item)
        kind = "FinalFinding" if is_final else "CandidateFinding"
        typer.echo(f"VALID {kind} Array ({len(raw)} items)")
    else:
        typer.echo("Error: unrecognized format", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
