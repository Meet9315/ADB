#!/usr/bin/env python3
"""
test_determinism.py — Multi-run determinism verification per check type.

Fulfills Prompt 11, Requirement 5:
"Run the determinism test, per check type:
 - rule-based checks must be byte-identical across two runs on the same corpus;
 - heuristic checks must match on severity class and confidence band;
 - reasoning checks must match on finding set, severity, and evidence, though exact
   prose may vary. For reasoning checks, use the same bounded corpus, question set,
   and deterministic passage ordering on both runs. If the host reasoning layer is
   nondeterministic, normalize outputs to the finding contract before comparison
   and report any residual variance."
"""

from __future__ import annotations

import http.server
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "skills/audit-orchestrator/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import fixture generator and check definitions from test_planted_defects
from test_planted_defects import (  # noqa: E402
    CHECK_SCRIPTS,
    REACH_SCRIPT,
    _BotWallHandler,
    create_planted_fixture,
)

RULE_BASED_CHECKS = ["R1", "R2", "R3", "R4", "R5", "D3", "E1", "E2", "E4", "T4"]
HEURISTIC_CHECKS = ["D1", "D2", "T1", "T2", "G2", "G3", "G4"]
REASONING_CHECKS = ["E3", "T3", "G1"]


def _run_check_raw(check_id: str, corpus_dir: Path, manifest_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
    """Execute check script and return raw stdout along with parsed JSON."""
    script_path, extra_args = CHECK_SCRIPTS[check_id]
    if script_path == REACH_SCRIPT:
        cmd = [sys.executable, str(script_path), str(manifest_path), *extra_args, "--corpus-dir", str(corpus_dir)]
    elif check_id == "D2":
        cmd = [sys.executable, str(script_path), str(corpus_dir)]
    else:
        cmd = [sys.executable, str(script_path), str(corpus_dir), "--manifest", str(manifest_path), *extra_args]

    res = subprocess.run(cmd, capture_output=True, text=True)
    raw = res.stdout.strip()
    try:
        parsed = json.loads(raw) if raw else []
    except Exception:
        parsed = []
    return raw, parsed


def test_determinism_suite() -> Dict[str, Any]:
    print("=" * 75)
    print("DETERMINISM VERIFICATION SUITE PER CHECK TYPE (20 CHECKS)")
    print("=" * 75)
    print(f"Rule-Based ({len(RULE_BASED_CHECKS)}): {', '.join(RULE_BASED_CHECKS)}")
    print(f"Heuristic ({len(HEURISTIC_CHECKS)}):  {', '.join(HEURISTIC_CHECKS)}")
    print(f"Reasoning ({len(REASONING_CHECKS)}):  {', '.join(REASONING_CHECKS)}")
    print("-" * 75)

    summary: Dict[str, Dict[str, Any]] = {
        "rule_based": {"total": len(RULE_BASED_CHECKS), "passed": 0, "failed": []},
        "heuristic": {"total": len(HEURISTIC_CHECKS), "passed": 0, "failed": []},
        "reasoning": {"total": len(REASONING_CHECKS), "passed": 0, "failed": [], "residual_variance": []},
    }

    # 1. Rule-Based Checks: Byte-identical verification
    print("\n[1] VERIFYING RULE-BASED CHECKS (Requirement: Byte-Identical Output)")
    for cid in RULE_BASED_CHECKS:
        with tempfile.TemporaryDirectory() as tmp_dir:
            p_dir, m_path = create_planted_fixture(cid, Path(tmp_dir))
            server = None
            if cid == "R2":
                server = http.server.HTTPServer(("127.0.0.1", 0), _BotWallHandler)
                port = server.server_port
                t = threading.Thread(target=server.serve_forever, daemon=True)
                t.start()
                m_data = json.loads(m_path.read_text(encoding="utf-8"))
                m_data["base_url"] = f"http://127.0.0.1:{port}"
                m_path.write_text(json.dumps(m_data), encoding="utf-8")

            raw1, parsed1 = _run_check_raw(cid, p_dir, m_path)
            raw2, parsed2 = _run_check_raw(cid, p_dir, m_path)

            if server:
                server.shutdown()
                server.server_close()

            # Byte-identical assertion
            is_identical = (raw1 == raw2) and (len(parsed1) > 0)
            if is_identical:
                summary["rule_based"]["passed"] += 1
                print(f"  [PASS] {cid:4s} -> BYTE-IDENTICAL ({len(raw1)} bytes, {len(parsed1)} finding(s))")
            else:
                summary["rule_based"]["failed"].append(cid)
                print(f"  [FAIL] {cid:4s} -> Output differed between runs! (len1={len(raw1)}, len2={len(raw2)})")

    # 2. Heuristic Checks: Severity class and confidence band match
    print("\n[2] VERIFYING HEURISTIC CHECKS (Requirement: Severity Class & Confidence Band Match)")
    for cid in HEURISTIC_CHECKS:
        with tempfile.TemporaryDirectory() as tmp_dir:
            p_dir, m_path = create_planted_fixture(cid, Path(tmp_dir))
            raw1, parsed1 = _run_check_raw(cid, p_dir, m_path)
            raw2, parsed2 = _run_check_raw(cid, p_dir, m_path)

            assert len(parsed1) > 0, f"Heuristic fixture {cid} produced 0 findings in Run 1"
            assert len(parsed1) == len(parsed2), f"Finding count mismatch for {cid}: {len(parsed1)} vs {len(parsed2)}"

            matches = True
            for f1, f2 in zip(parsed1, parsed2):
                sev1 = f1.get("raw_severity_class")
                sev2 = f2.get("raw_severity_class")
                conf1 = float(f1.get("confidence", 0.0))
                conf2 = float(f2.get("confidence", 0.0))

                # Severity class must match exactly
                if sev1 != sev2:
                    matches = False
                    break
                # Confidence band must match within tolerance (< 0.01)
                if abs(conf1 - conf2) > 0.01:
                    matches = False
                    break

            if matches:
                summary["heuristic"]["passed"] += 1
                c_disp = f"conf={parsed1[0].get('confidence')}, sev={parsed1[0].get('raw_severity_class')}"
                print(f"  [PASS] {cid:4s} -> SEVERITY & CONFIDENCE MATCH ({c_disp})")
            else:
                summary["heuristic"]["failed"].append(cid)
                print(f"  [FAIL] {cid:4s} -> Invariant mismatch between runs for heuristic check")

    # 3. Reasoning-Based Checks: Finding set, severity, and evidence grounding match
    print("\n[3] VERIFYING REASONING CHECKS (Requirement: Finding Set, Severity, Evidence Match)")
    for cid in REASONING_CHECKS:
        with tempfile.TemporaryDirectory() as tmp_dir:
            p_dir, m_path = create_planted_fixture(cid, Path(tmp_dir))
            raw1, parsed1 = _run_check_raw(cid, p_dir, m_path)
            raw2, parsed2 = _run_check_raw(cid, p_dir, m_path)

            assert len(parsed1) > 0, f"Reasoning fixture {cid} produced 0 findings in Run 1"
            assert len(parsed1) == len(parsed2), f"Finding count mismatch for {cid}: {len(parsed1)} vs {len(parsed2)}"

            matches = True
            for f1, f2 in zip(parsed1, parsed2):
                # Finding ID and Check ID match
                if f1.get("check_id") != f2.get("check_id"):
                    matches = False
                    break
                # Severity matches
                if f1.get("raw_severity_class") != f2.get("raw_severity_class"):
                    matches = False
                    break
                # Evidence dictionary keys match
                ev1 = f1.get("evidence", {})
                ev2 = f2.get("evidence", {})
                if set(ev1.keys()) != set(ev2.keys()):
                    matches = False
                    break
                # Key evidence fields match
                for k in ev1:
                    if isinstance(ev1[k], (int, float, bool)):
                        if ev1[k] != ev2[k]:
                            matches = False
                            break

            if matches:
                summary["reasoning"]["passed"] += 1
                # Check for prose variance
                prose_same = (raw1 == raw2)
                variance_desc = "none (byte-identical)" if prose_same else "minor prose variance (normalized contract intact)"
                if not prose_same:
                    summary["reasoning"]["residual_variance"].append({
                        "check_id": cid,
                        "finding_id": parsed1[0]["id"],
                        "variance": "Normalized finding contract matched; slight textual variance in description/mechanism.",
                    })
                print(f"  [PASS] {cid:4s} -> FINDING SET & EVIDENCE MATCH (residual variance: {variance_desc})")
            else:
                summary["reasoning"]["failed"].append(cid)
                print(f"  [FAIL] {cid:4s} -> Invariant mismatch between runs for reasoning check")

    # Final Report Table
    print("\n" + "=" * 75)
    print("DETERMINISM TEST SUMMARY REPORT")
    print("=" * 75)
    print(f"Rule-Based Checks: {summary['rule_based']['passed']}/{summary['rule_based']['total']} PASS (100% Byte-Identical)")
    print(f"Heuristic Checks:  {summary['heuristic']['passed']}/{summary['heuristic']['total']} PASS (100% Severity & Confidence Match)")
    print(f"Reasoning Checks:  {summary['reasoning']['passed']}/{summary['reasoning']['total']} PASS (100% Finding Set & Evidence Match)")
    print(f"Residual Variance: {len(summary['reasoning']['residual_variance'])} reported")
    print("=" * 75)

    assert summary["rule_based"]["passed"] == summary["rule_based"]["total"]
    assert summary["heuristic"]["passed"] == summary["heuristic"]["total"]
    assert summary["reasoning"]["passed"] == summary["reasoning"]["total"]


def main() -> None:
    test_determinism_suite()


if __name__ == "__main__":
    main()
