#!/usr/bin/env python3
"""
validate_skills.py — CI validator for agentskills.io SKILL.md compliance.

Checks every skill folder under skills/ against the agentskills.io specification:
  https://agentskills.io/specification

Rules enforced (from the official spec):
  1. Each skill directory must contain a SKILL.md file.
  2. SKILL.md must begin with YAML frontmatter (--- ... ---).
  3. Frontmatter must contain required fields: name, description.
  4. `name` field:
       - 1–64 characters
       - Only lowercase letters (a-z), digits (0-9), and hyphens (-)
       - Must not start or end with a hyphen
       - Must not contain consecutive hyphens (--)
       - Must match the parent directory name exactly
  5. `description` field:
       - 1–1024 characters, non-empty (not just whitespace)
  6. Optional field `compatibility`, if present: 1–500 characters
  7. SKILL.md must be ≤ 500 lines (project constitution limit).
  8. marketplace.json (if present at repo root) must list every skill directory
     found under skills/; names must match.

Exit code 0 = all skills pass.
Exit code 1 = one or more failures.

Usage:
    python scripts/validate_skills.py [--skills-dir <path>] [--marketplace <path>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple


# ---------------------------------------------------------------------------
# YAML frontmatter extraction (no external deps — stdlib only)
# ---------------------------------------------------------------------------

def extract_frontmatter(text: str) -> Tuple[dict, str]:
    """
    Extract YAML frontmatter from a SKILL.md string.
    Returns (fields_dict, body).  Raises ValueError on malformed frontmatter.
    Deliberately minimal — handles only the scalar/string fields in the spec.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md does not begin with '---' (no frontmatter)")

    fm_lines: List[str] = []
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
        fm_lines.append(line)

    if end_idx is None:
        raise ValueError("Frontmatter opening '---' has no closing '---'")

    body = "".join(lines[end_idx + 1:])

    # Parse the frontmatter lines into a dict
    # Supports: scalar values, block scalars (> and |), and nested maps (metadata:)
    fields: dict = {}
    current_key: str | None = None
    current_val_lines: List[str] = []
    block_scalar = False
    nested_map = False

    def flush_current() -> None:
        nonlocal current_key, current_val_lines, block_scalar, nested_map
        if current_key is None:
            return
        if block_scalar:
            val = " ".join(l.strip() for l in current_val_lines if l.strip())
            fields[current_key] = val
        elif nested_map:
            fields[current_key] = {}  # we don't need to parse nested maps deeply
        else:
            fields[current_key] = current_val_lines[0].strip() if current_val_lines else ""
        current_key = None
        current_val_lines = []
        block_scalar = False
        nested_map = False

    for line in fm_lines:
        stripped = line.rstrip("\n")
        if not stripped.strip():
            continue
        # Detect a new top-level key (no leading spaces)
        if stripped and not stripped[0].isspace():
            flush_current()
            if ":" in stripped:
                key, _, rest = stripped.partition(":")
                current_key = key.strip()
                rest = rest.strip()
                if rest in (">", "|"):
                    block_scalar = True
                    current_val_lines = []
                elif rest == "":
                    nested_map = True
                    current_val_lines = []
                else:
                    block_scalar = False
                    current_val_lines = [rest]
        else:
            # continuation / block scalar line
            if block_scalar or nested_map:
                current_val_lines.append(stripped)
    flush_current()

    return fields, body


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$")
CONSEC_HYPHENS = re.compile(r"--")


def validate_skill_dir(skill_dir: Path) -> List[str]:
    """
    Validate one skill directory.  Returns a list of error strings (empty = pass).
    """
    errors: List[str] = []
    dir_name = skill_dir.name

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"[{dir_name}] SKILL.md not found in {skill_dir}")
        return errors

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Rule 7: ≤ 500 lines
    if len(lines) > 500:
        errors.append(f"[{dir_name}] SKILL.md has {len(lines)} lines; max 500")

    # Extract frontmatter
    try:
        fields, _ = extract_frontmatter(text)
    except ValueError as exc:
        errors.append(f"[{dir_name}] Frontmatter error: {exc}")
        return errors

    # Rule 3: required fields
    for req in ("name", "description"):
        if req not in fields:
            errors.append(f"[{dir_name}] Missing required frontmatter field: '{req}'")

    if "name" in fields:
        name = fields["name"].strip()

        # Rule 4a: 1–64 chars
        if not (1 <= len(name) <= 64):
            errors.append(
                f"[{dir_name}] 'name' must be 1–64 chars; got {len(name)}"
            )

        # Rule 4b: only [a-z0-9-]
        if not re.fullmatch(r"[a-z0-9\-]+", name):
            errors.append(
                f"[{dir_name}] 'name' must contain only lowercase letters, digits, "
                f"and hyphens; got '{name}'"
            )

        # Rule 4c: no leading/trailing hyphen
        if name.startswith("-") or name.endswith("-"):
            errors.append(
                f"[{dir_name}] 'name' must not start or end with a hyphen; got '{name}'"
            )

        # Rule 4d: no consecutive hyphens
        if CONSEC_HYPHENS.search(name):
            errors.append(
                f"[{dir_name}] 'name' must not contain consecutive hyphens; got '{name}'"
            )

        # Rule 4e: must match directory name
        if name != dir_name:
            errors.append(
                f"[{dir_name}] 'name' field ('{name}') must match directory name ('{dir_name}')"
            )

    if "description" in fields:
        desc = fields["description"]
        desc_stripped = desc.strip()

        # Rule 5: 1–1024 chars, non-empty
        if not desc_stripped:
            errors.append(f"[{dir_name}] 'description' must not be empty")
        elif len(desc_stripped) > 1024:
            errors.append(
                f"[{dir_name}] 'description' must be ≤ 1024 chars; got {len(desc_stripped)}"
            )

    # Rule 6: optional compatibility field
    if "compatibility" in fields:
        compat = fields["compatibility"].strip()
        if not (1 <= len(compat) <= 500):
            errors.append(
                f"[{dir_name}] 'compatibility' must be 1–500 chars if present; "
                f"got {len(compat)}"
            )

    return errors


def validate_marketplace(marketplace_path: Path, skill_names: List[str]) -> List[str]:
    """
    Validate marketplace.json: every skill directory must be listed.
    Returns list of error strings.
    """
    errors: List[str] = []
    if not marketplace_path.exists():
        errors.append(f"marketplace.json not found at {marketplace_path}")
        return errors

    try:
        data = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"marketplace.json is invalid JSON: {exc}")
        return errors

    listed_names = {s.get("name", "") for s in data.get("skills", [])}
    for name in skill_names:
        if name not in listed_names:
            errors.append(
                f"Skill '{name}' found in skills/ but not listed in marketplace.json"
            )

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate agentskills.io SKILL.md files against the spec"
    )
    parser.add_argument(
        "--skills-dir",
        default="skills",
        help="Root directory containing skill subdirectories (default: skills/)",
    )
    parser.add_argument(
        "--marketplace",
        default="marketplace.json",
        help="Path to marketplace.json (default: marketplace.json)",
    )
    args = parser.parse_args()

    skills_root = Path(args.skills_dir)
    if not skills_root.is_dir():
        print(f"ERROR: skills directory '{skills_root}' not found", file=sys.stderr)
        sys.exit(1)

    skill_dirs = sorted(d for d in skills_root.iterdir() if d.is_dir())
    if not skill_dirs:
        print(f"WARNING: No subdirectories found in '{skills_root}'")
        sys.exit(0)

    all_errors: List[str] = []
    skill_names: List[str] = []

    for skill_dir in skill_dirs:
        errs = validate_skill_dir(skill_dir)
        all_errors.extend(errs)
        skill_names.append(skill_dir.name)

    # Validate marketplace.json
    marketplace_path = Path(args.marketplace)
    all_errors.extend(validate_marketplace(marketplace_path, skill_names))

    # Report
    print(f"\n=== Skill validation: {len(skill_dirs)} skill(s) checked ===\n")
    if all_errors:
        for err in all_errors:
            print(f"  FAIL  {err}")
        print(f"\n{len(all_errors)} error(s) found. Build FAILED.\n")
        sys.exit(1)
    else:
        for name in skill_names:
            print(f"  PASS  {name}")
        print(f"\nAll {len(skill_dirs)} skill(s) passed validation.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
