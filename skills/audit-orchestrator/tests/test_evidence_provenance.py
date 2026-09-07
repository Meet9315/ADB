#!/usr/bin/env python3
"""
test_evidence_provenance.py — Evidence-fabrication compliance test for reasoning checks.

Enforces Rule 1: Every fact, quoted passage, brand candidate, and orientation answer
in evidence and mechanism fields must trace to literal values in the corpus, never
fabricated or inferred from assumptions about "typical websites".

Checks audited:
- E3: Canonical question quotability gap (best passage quotes)
- T3: Entity ambiguity (brand candidates and active ambiguity signals)
- G1: Above-the-fold orientation rubric (who, what, next quotes)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECK_E3 = REPO_ROOT / "skills/machine-readability-audit/scripts/check_e3.py"
CHECK_T3 = REPO_ROOT / "skills/trust-signals-audit/scripts/check_t3.py"
CHECK_G1 = REPO_ROOT / "skills/engagement-audit/scripts/check_g1.py"


def _extract_all_corpus_text(corpus_dir: Path) -> str:
    """Concatenate all visible text across corpus pages."""
    combined = []
    for p in corpus_dir.rglob("*"):
        if p.is_file() and p.suffix in (".html", ".txt", ".json"):
            raw = p.read_text(encoding="utf-8", errors="replace")
            clean = re.sub(r"<[^>]+>", " ", raw)
            combined.append(clean)
    return " ".join(combined)


def test_e3_evidence_provenance() -> None:
    """Audit E3 findings: best_passage_quoted must be a literal substring of corpus text."""
    print("--- Auditing E3 Evidence Provenance ---")
    fx_dir = REPO_ROOT / "skills/machine-readability-audit/tests/fixtures/e3_quotability"
    manifest_path = fx_dir / "crawl_manifest.json"
    pages_dir = fx_dir / "pages"

    res = subprocess.run(
        [sys.executable, str(CHECK_E3), str(pages_dir), "--manifest", str(manifest_path)],
        capture_output=True, text=True,
    )
    findings = json.loads(res.stdout) if res.stdout.strip() else []
    assert len(findings) >= 1, "E3 should produce findings on e3_quotability fixture"

    corpus_text = _extract_all_corpus_text(pages_dir)
    # Normalize whitespace for robust substring matching
    norm_corpus = re.sub(r"\s+", " ", corpus_text).lower()

    for f in findings:
        passage = f["evidence"].get("best_passage") or f["evidence"].get("best_passage_quoted")
        if passage:
            norm_passage = re.sub(r"\s+", " ", passage).lower()
            assert norm_passage in norm_corpus, (
                f"Rule 1 Violation in E3 {f['id']}: Quoted passage not found literally in corpus!\n"
                f"Passage: {passage[:100]}..."
            )
            print(f"  [PASS] E3 finding {f['id']} passage is literal corpus substring: '{passage[:60]}...'")


def test_t3_evidence_provenance() -> None:
    """Audit T3 findings: brand candidate must be literally present in corpus title/headings."""
    print("\n--- Auditing T3 Evidence Provenance ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        p_home = tmp_path / "pages" / "home"
        p_home.mkdir(parents=True)

        ambig_html = (
            "<!DOCTYPE html><html><head><title>Summit</title></head><body>"
            "<main><h1>Welcome to Summit</h1>"
            "<p>We empower next-generation synergy across seamless frontiers. Our unified solutions optimize your vision "
            "with end-to-end holistic paradigms for frictionless execution.</p>"
            "</main></body></html>"
        )
        (p_home / "raw.html").write_text(ambig_html, encoding="utf-8")
        (p_home / "text.txt").write_text("Welcome to Summit We empower next-generation synergy across seamless frontiers. Our unified solutions optimize your vision with end-to-end holistic paradigms for frictionless execution.", encoding="utf-8")
        (p_home / "meta.json").write_text(json.dumps({"url": "https://summit.example.com/", "status_code": 200, "title": "Summit"}), encoding="utf-8")

        m_dict = {
            "schema_version": "1.0",
            "domain": "summit.example.com",
            "base_url": "https://summit.example.com",
            "crawled_pages": [{"url": "https://summit.example.com/", "slug": "home", "status_code": 200}],
        }
        manifest_path = tmp_path / "crawl_manifest.json"
        manifest_path.write_text(json.dumps(m_dict), encoding="utf-8")

        res = subprocess.run(
            [sys.executable, str(CHECK_T3), str(tmp_path / "pages"), "--manifest", str(manifest_path)],
            capture_output=True, text=True,
        )
        findings = json.loads(res.stdout) if res.stdout.strip() else []
        assert len(findings) >= 1, "T3 should produce a finding on generic brand fixture"

        corpus_text = _extract_all_corpus_text(tmp_path / "pages")
        norm_corpus = re.sub(r"\s+", " ", corpus_text).lower()

        for f in findings:
            brand = f["evidence"].get("brand_name") or f["evidence"].get("brand_candidate")
            assert brand, f"T3 finding {f['id']} missing brand_name"
            assert brand.lower() in norm_corpus, (
                f"Rule 1 Violation in T3 {f['id']}: Brand candidate '{brand}' does not trace to literal corpus text!"
            )
            print(f"  [PASS] T3 finding {f['id']} brand candidate '{brand}' is grounded in corpus text.")


def test_g1_evidence_provenance() -> None:
    """Audit G1 findings: rubric quotes must be literal substrings of first-viewport text."""
    print("\n--- Auditing G1 Evidence Provenance ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        p_home = tmp_path / "pages" / "home"
        p_home.mkdir(parents=True)

        home_html = (
            "<!DOCTYPE html><html><head><title>Acme Global Holdings</title></head><body>"
            "<header>Acme Global</header>"
            "<main><h1>Unleashing Synergistic Potential</h1>"
            "<p>Harmonizing horizon vectors and empowering elevated paradigm dynamics.</p>"
            "<nav><a href='/explore'>Explore</a></nav>"
            "</main></body></html>"
        )
        (p_home / "raw.html").write_text(home_html, encoding="utf-8")
        (p_home / "text.txt").write_text("Acme Global Unleashing Synergistic Potential Harmonizing horizon vectors. Explore", encoding="utf-8")
        (p_home / "meta.json").write_text(json.dumps({"url": "https://acmeglobal.example.com/", "status_code": 200, "title": "Acme Global Holdings"}), encoding="utf-8")

        m_dict = {
            "schema_version": "1.0",
            "domain": "acmeglobal.example.com",
            "crawled_pages": [{"url": "https://acmeglobal.example.com/", "slug": "home", "status_code": 200}],
        }
        manifest_path = tmp_path / "crawl_manifest.json"
        manifest_path.write_text(json.dumps(m_dict), encoding="utf-8")

        res = subprocess.run(
            [sys.executable, str(CHECK_G1), str(tmp_path / "pages"), "--manifest", str(manifest_path)],
            capture_output=True, text=True,
        )
        findings = json.loads(res.stdout) if res.stdout.strip() else []
        assert len(findings) >= 1, "G1 should produce orientation finding on buzzword copy"

        corpus_text = _extract_all_corpus_text(tmp_path / "pages")
        norm_corpus = re.sub(r"\s+", " ", corpus_text).lower()

        for f in findings:
            ev = f["evidence"]
            sample = ev.get("first_viewport_text_sample", "")
            assert sample, "G1 must include first_viewport_text_sample"
            assert re.sub(r"\s+", " ", sample).lower() in norm_corpus, (
                f"Rule 1 Violation in G1: Viewport text sample not found literally in corpus: {sample}"
            )

            # Check answered quotes
            rubric = ev.get("rubric_answers", {})
            for q_name in ("who_is_this", "what_do_they_offer", "what_should_i_do_next"):
                q_data = rubric.get(q_name, {})
                if q_data.get("answered") and q_data.get("quote"):
                    q_str = re.sub(r"\s+", " ", q_data["quote"]).lower()
                    # Strip parenthetical annotations if title-based
                    clean_quote = q_str.split(" (from page")[0].strip()
                    assert clean_quote in norm_corpus, (
                        f"Rule 1 Violation in G1 {q_name}: Quote '{clean_quote}' not found literally in corpus!"
                    )
            print(f"  [PASS] G1 finding {f['id']} all answers strictly grounded in literal viewport quotes.")


def main() -> None:
    print("=" * 65)
    print("EVIDENCE FABRICATION COMPLIANCE AUDIT (RULE 1)")
    print("=" * 65)
    test_e3_evidence_provenance()
    test_t3_evidence_provenance()
    test_g1_evidence_provenance()
    print("\n" + "=" * 65)
    print("RULE 1 COMPLIANCE: 0 VIOLATIONS (100% LITERAL PROVENANCE)")
    print("=" * 65)


if __name__ == "__main__":
    main()
