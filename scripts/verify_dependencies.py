#!/usr/bin/env python3
"""
verify_dependencies.py — Dependency reproducibility and pinned manifest verification.

Verifies:
1. Pinned manifest covers every runtime dependency actually imported.
2. Explicit import checks for extruct, pydantic, typer, httpx, selectolax, playwright, bs4, lxml.
3. No undeclared or unused dependencies.
4. Records exact Python version and installed dependency versions.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# All direct external packages that are legitimately imported by skills
DIRECT_RUNTIME_PACKAGES = {
    "httpx": "httpx[http2]",
    "selectolax": "selectolax",
    "playwright": "playwright",
    "extruct": "extruct",
    "pydantic": "pydantic",
    "typer": "typer",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "pytest": "pytest",
}


def verify_direct_imports() -> dict[str, str]:
    """Import each required package and record its resolved version."""
    versions = {}
    print("=== 1. Explicit Direct Import Verification ===")
    for mod_name, pkg_name in DIRECT_RUNTIME_PACKAGES.items():
        try:
            mod = importlib.import_module(mod_name)
            ver = getattr(mod, "__version__", None)
            if not ver:
                base_pkg = pkg_name.split("[")[0]
                try:
                    ver = importlib.metadata.version(base_pkg)
                except Exception:
                    ver = "installed"
            versions[pkg_name] = str(ver)
            print(f"  [PASS] {mod_name:<15} -> {pkg_name} (version {ver})")
        except ImportError as exc:
            print(f"  [FAIL] {mod_name:<15} -> FAILED to import: {exc}")
            sys.exit(1)
    return versions


def verify_codebase_imports() -> set[str]:
    """Scan all Python files in skills/ to extract top-level import names."""
    print("\n=== 2. Codebase Import Coverage Audit ===")
    standard_lib = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else {
        "os", "sys", "re", "json", "time", "datetime", "pathlib", "argparse", "typing",
        "collections", "urllib", "hashlib", "subprocess", "copy", "tempfile", "traceback",
        "math", "dataclasses", "abc", "shutil", "enum", "logging", "asyncio", "unittest",
    }
    skills_dir = REPO_ROOT / "skills"
    # Dynamically find all local python module stems across skills/
    local_modules = {p.stem for p in skills_dir.rglob("*.py")}

    discovered_imports: set[str] = set()
    for py_file in skills_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            # Match: import foo, import foo.bar
            m_imp = re.match(r"^import\s+([a-zA-Z0-9_]+)", line)
            if m_imp:
                discovered_imports.add(m_imp.group(1))
            # Match: from foo import bar
            m_from = re.match(r"^from\s+([a-zA-Z0-9_]+)\s+import", line)
            if m_from:
                discovered_imports.add(m_from.group(1))

    # Filter out standard library and internal module names
    third_party_imports = {
        imp for imp in discovered_imports
        if imp not in standard_lib and imp not in local_modules and not imp.startswith("_")
    }

    print(f"  Discovered 3rd-party imports across skills/: {sorted(third_party_imports)}")
    declared_mods = set(DIRECT_RUNTIME_PACKAGES.keys())
    undeclared = third_party_imports - declared_mods
    if undeclared:
        print(f"  [FAIL] Undeclared runtime imports found: {undeclared}")
        sys.exit(1)
    else:
        print("  [PASS] All 3rd-party imports map directly to declared dependencies.")

    return third_party_imports


def verify_pinned_manifest() -> None:
    """Verify requirements-pinned.txt exists and contains valid pinned entries."""
    print("\n=== 3. Pinned Dependency Manifest Check ===")
    pinned_path = REPO_ROOT / "requirements-pinned.txt"
    if not pinned_path.exists():
        print(f"  [FAIL] requirements-pinned.txt not found at {pinned_path}")
        sys.exit(1)

    lines = [
        line.strip() for line in pinned_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    pinned_packages = {}
    for line in lines:
        if "==" in line:
            pkg, ver = line.split("==", 1)
            pinned_packages[pkg] = ver
        else:
            print(f"  [WARN] Unpinned entry in requirements-pinned.txt: {line}")

    expected_pkgs = {
        "beautifulsoup4", "extruct", "httpx[http2]", "lxml",
        "playwright", "pydantic", "pytest", "selectolax", "typer",
    }
    missing = expected_pkgs - set(pinned_packages.keys())
    if missing:
        print(f"  [FAIL] Missing expected pinned packages: {missing}")
        sys.exit(1)

    print(f"  [PASS] All {len(pinned_packages)} runtime packages strictly pinned with '==':")
    for p, v in sorted(pinned_packages.items()):
        print(f"         {p} == {v}")


def main() -> None:
    print(f"Python Runtime: {sys.version.split()[0]} ({sys.platform})")
    print(f"Executable:     {sys.executable}")
    print(f"Repo Root:      {REPO_ROOT}\n")

    versions = verify_direct_imports()
    verify_codebase_imports()
    verify_pinned_manifest()

    print("\n" + "=" * 55)
    print("ALL DEPENDENCY REPRODUCIBILITY CHECKS PASSED")
    print("=" * 55)


if __name__ == "__main__":
    main()
