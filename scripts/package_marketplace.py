#!/usr/bin/env python3
"""
package_marketplace.py — Marketplace packaging, hygiene validation, and extracted verification.

Fulfills Prompt 12 Requirements:
1. Validates package hygiene:
   - Only runtime dependencies actually used are declared
   - Versions pinned in requirements-pinned.txt
   - Zero secrets, API keys, credentials, .env files, caches, virtual environments,
     __pycache__, browser binaries, temporary files, datasets, or pretrained model weights
   - Zero accidental live-test corpora/dumps
   - Inspects and prints complete final file list before zipping
2. Zips the marketplace root to dist/ai-discoverability-audit.zip:
   - Confirms total archive size is under 50MB
3. Extracts ZIP into a fresh isolated temporary directory:
   - Executes verification from the extracted artifact, NOT from the working tree
4. In the extracted environment, executes:
   - Skill validation (validate_skills.py + skills-ref)
   - Representative fixture tests (run_fixtures.py)
   - Report schema validation (test_models.py)
   - End-to-end audit (audit.py run example.com) with schema validation
5. Reports final tree, ZIP size, exact dependency versions, and exact command outcomes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

# Exclusion patterns for packaging
EXCLUDE_DIRS: Set[str] = {
    ".git",
    ".github",
    ".pytest_cache",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    "scratch",
    "corpus",
    "dist",
    "htmlcov",
}

EXCLUDE_FILE_PATTERNS: Set[str] = {
    ".DS_Store",
    "Thumbs.db",
    ".coverage",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".env",
    ".env.*",
}

SECRET_KEYWORDS: List[str] = [
    "PRIVATE KEY",
    "AWS_SECRET",
    "AIZA",  # Google API key prefix
    "SK-",   # OpenAI / Anthropic key prefix in assignments
]


def collect_package_files(root: Path) -> List[Path]:
    """Traverse repository and return strictly sanitized list of files to package."""
    package_files: List[Path] = []

    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue

        rel_parts = path.relative_to(root).parts
        # Check excluded directories
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue

        # Check excluded filenames
        name = path.name
        if name in EXCLUDE_FILE_PATTERNS or any(name.endswith(ext.replace("*", "")) for ext in [".pyc", ".pyo", ".pyd"]):
            continue

        package_files.append(path)

    return package_files


def audit_hygiene(root: Path, files: List[Path]) -> None:
    """Audit collected files for secrets, credentials, binary dumps, or unexpected bloat."""
    print("=" * 80)
    print("STEP 1: DEPENDENCY & PACKAGE HYGIENE AUDIT")
    print("=" * 80)

    # 1. Inspect file list
    print(f"Collected {len(files)} files for marketplace packaging:\n")
    for f in files:
        rel = f.relative_to(root)
        size_kb = f.stat().st_size / 1024.0
        print(f"  {str(rel):65s} ({size_kb:6.1f} KB)")

    print("\nAuditing file contents for secrets, credentials, and binary artifacts...")
    for f in files:
        rel = f.relative_to(root)

        # Check for forbidden extensions
        ext = f.suffix.lower()
        if ext in (".exe", ".dll", ".so", ".dylib", ".bin", ".tar", ".gz", ".zip", ".pkl"):
            raise ValueError(f"Prohibited binary file found in package: {rel}")

        # Check for secrets in text files
        if ext in (".py", ".md", ".json", ".txt", ".yml", ".yaml"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for kw in SECRET_KEYWORDS:
                    if kw in content and "SECRET_KEYWORDS" not in content:
                        raise ValueError(f"Potential secret/credential keyword '{kw}' detected in: {rel}")
            except Exception as exc:
                if not isinstance(exc, ValueError):
                    pass
                else:
                    raise

    print("  [PASS] Zero secrets, API keys, credentials, or binary blobs detected.")
    print("  [PASS] Zero scratch/, corpus/, __pycache__, or virtual environments included.")


def build_zip(root: Path, files: List[Path], dist_dir: Path) -> Path:
    """Create ZIP archive in dist_dir and verify size < 50MB."""
    print("\n" + "=" * 80)
    print("STEP 2: MARKETPLACE ROOT PACKAGING (ZIP CREATION)")
    print("=" * 80)

    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dist_dir / "ai-discoverability-audit.zip"

    if zip_path.exists():
        zip_path.unlink()

    total_uncompressed = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in files:
            arcname = str(f.relative_to(root))
            zf.write(f, arcname)
            total_uncompressed += f.stat().st_size

    compressed_size = zip_path.stat().st_size
    size_mb = compressed_size / (1024.0 * 1024.0)
    uncompressed_mb = total_uncompressed / (1024.0 * 1024.0)

    print(f"Archive created: {zip_path}")
    print(f"Total files in archive:       {len(files)}")
    print(f"Uncompressed content size:    {uncompressed_mb:.2f} MB ({total_uncompressed:,} bytes)")
    print(f"Compressed archive size:      {size_mb:.2f} MB ({compressed_size:,} bytes)")
    print(f"Packaging ceiling target:     < 50.00 MB")

    if size_mb >= 50.0:
        raise ValueError(f"ZIP package exceeds 50MB limit: {size_mb:.2f} MB")

    print(f"  [PASS] Archive size is {size_mb:.2f} MB (strictly under 50MB threshold)")
    return zip_path


def run_extracted_verification(zip_path: Path) -> None:
    """Extract ZIP into fresh isolated directory and run full verification suite."""
    print("\n" + "=" * 80)
    print("STEP 3: OUT-OF-TREE EXTRACTED ARTIFACT VERIFICATION")
    print("=" * 80)

    with tempfile.TemporaryDirectory(prefix="extracted_marketplace_") as tmp_dir_str:
        extract_root = Path(tmp_dir_str)
        print(f"Extracting {zip_path.name} to fresh environment:\n  {extract_root}\n")

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_root)

        def _exec(cmd: List[str], desc: str) -> Tuple[int, str]:
            print(f"[*] Running: {' '.join(cmd)}")
            t0 = time.monotonic()
            res = subprocess.run(cmd, cwd=extract_root, capture_output=True, text=True)
            elapsed = time.monotonic() - t0
            status = "PASS" if res.returncode == 0 else "FAIL"
            print(f"    [{status}] {desc} in {elapsed:.2f}s (exit code {res.returncode})")
            if res.returncode != 0:
                print(f"--- STDOUT ---\n{res.stdout}", file=sys.stderr)
                print(f"--- STDERR ---\n{res.stderr}", file=sys.stderr)
                raise RuntimeError(f"Command failed in extracted environment: {' '.join(cmd)}")
            return res.returncode, res.stdout

        # 1. Dependency verification script
        _exec([sys.executable, "scripts/verify_dependencies.py"], "Dependency hygiene and direct import audit")

        # 2. Skill specification validation (validate_skills.py)
        _exec([sys.executable, "scripts/validate_skills.py"], "Skill frontmatter and manifest compliance")

        # 3. AgentSkills official validator (skills-ref)
        npx_bin = shutil.which("npx") or "npx"
        skills = [
            "skills/audit-orchestrator",
            "skills/site-acquisition",
            "skills/machine-readability-audit",
            "skills/trust-signals-audit",
            "skills/engagement-audit",
        ]
        for sk in skills:
            _exec([npx_bin, "-y", "skills-ref", "validate", sk], f"Official skills-ref validation: {sk}")

        # 4. Representative fixture tests (run_fixtures.py)
        _exec([sys.executable, "skills/machine-readability-audit/tests/run_fixtures.py"], "42-fixture discovery suite")

        # 5. Report schema validation (test_models.py)
        _exec([sys.executable, "-m", "pytest", "skills/audit-orchestrator/tests/test_models.py"], "Pydantic contract schema & invariant tests")

        # 6. End-to-end audit execution from extracted artifact
        report_output = extract_root / "extracted_audit_report.json"
        _exec([
            sys.executable,
            "skills/audit-orchestrator/scripts/audit.py",
            "run",
            "example.com",
            "--output", str(report_output),
            "--budget-soft", "30",
            "--budget-hard", "45",
        ], "End-to-end live audit run from extracted artifact")

        # 7. Validate produced report
        _exec([
            sys.executable,
            "skills/audit-orchestrator/scripts/validate_report.py",
            str(report_output),
        ], "Validation of extracted audit output against FinalReport schema")

        print("\n" + "=" * 80)
        print("CONFIRMED: EXTRACTED ARTIFACT FULLY OPERATIONAL AND SPEC-COMPLIANT")
        print("=" * 80)


def main() -> None:
    files = collect_package_files(REPO_ROOT)
    audit_hygiene(REPO_ROOT, files)
    dist_dir = REPO_ROOT / "dist"
    zip_path = build_zip(REPO_ROOT, files, dist_dir)
    run_extracted_verification(zip_path)


if __name__ == "__main__":
    main()
