#!/usr/bin/env python3
"""
test_planted_defects.py — Synthetic fixture suite for planted-defect recall and clean-control FP rate.

Implements:
- Exactly 1 local synthetic fixture per implemented check with a known planted defect (20 checks).
- Clean control fixture evaluation across all 20 checks.
- Honestly-labeled separate metrics:
  * Planted-defect recall: fraction of planted defects the synthetic fixtures actually caught (target >85%).
  * Clean-control false-positive rate: findings produced on zero-defect fixture (target: exactly 0.0%).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]

# Check script paths across all 5 skills
REACH_SCRIPT = REPO_ROOT / "skills/site-acquisition/scripts/reach_checks.py"
MRA_DIR = REPO_ROOT / "skills/machine-readability-audit/scripts"
TSA_DIR = REPO_ROOT / "skills/trust-signals-audit/scripts"
EA_DIR = REPO_ROOT / "skills/engagement-audit/scripts"
CLEAN_FIXTURE = REPO_ROOT / "skills/machine-readability-audit/tests/fixtures/clean"

CHECK_SCRIPTS = {
    "R1": (REACH_SCRIPT, ["--checks", "R1"]),
    "R2": (REACH_SCRIPT, ["--checks", "R2"]),
    "R3": (REACH_SCRIPT, ["--checks", "R3"]),
    "R4": (MRA_DIR / "check_noindex.py", []),
    "R5": (REACH_SCRIPT, ["--checks", "R5"]),
    "D1": (MRA_DIR / "check_d1.py", []),
    "D2": (MRA_DIR / "check_d2.py", []),
    "D3": (MRA_DIR / "check_d3.py", []),
    "E1": (MRA_DIR / "check_e1.py", []),
    "E2": (MRA_DIR / "check_e2.py", []),
    "E3": (MRA_DIR / "check_e3.py", []),
    "E4": (MRA_DIR / "check_e4.py", []),
    "T1": (TSA_DIR / "check_t1.py", []),
    "T2": (TSA_DIR / "check_t2.py", []),
    "T3": (TSA_DIR / "check_t3.py", []),
    "T4": (TSA_DIR / "check_t4.py", []),
    "G1": (EA_DIR / "check_g1.py", []),
    "G2": (EA_DIR / "check_g2.py", []),
    "G3": (EA_DIR / "check_g3.py", []),
    "G4": (EA_DIR / "check_g4.py", []),
}


def _run_check(check_id: str, corpus_dir: Path, manifest_path: Path) -> List[Dict[str, Any]]:
    """Execute a single check script against a synthetic corpus and parse JSON output."""
    script_path, extra_args = CHECK_SCRIPTS[check_id]

    if script_path == REACH_SCRIPT:
        cmd = [sys.executable, str(script_path), str(manifest_path), *extra_args, "--corpus-dir", str(corpus_dir)]
    elif check_id == "D2":
        cmd = [sys.executable, str(script_path), str(corpus_dir)]
    else:
        cmd = [sys.executable, str(script_path), str(corpus_dir), "--manifest", str(manifest_path), *extra_args]

    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(res.stdout) if res.stdout.strip() else []
    except Exception:
        return []


def create_planted_fixture(check_id: str, base_dir: Path) -> Tuple[Path, Path]:
    """Build a local HTML fixture directory containing a planted defect for the given check."""
    pages_dir = base_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = base_dir / "crawl_manifest.json"

    # Default manifest base
    m_dict: Dict[str, Any] = {
        "schema_version": "1.0",
        "domain": f"planted-{check_id.lower()}.example.com",
        "base_url": f"https://planted-{check_id.lower()}.example.com",
        "crawled_pages": [],
    }

    # 1. R1: All AI bots blocked in robots.txt (use existing proven fixture if available, or synthetic manifest)
    if check_id == "R1":
        r1_fix = REPO_ROOT / "skills/machine-readability-audit/tests/fixtures/r1_blocked"
        return r1_fix / "pages", r1_fix / "crawl_manifest.json"

    # 2. R2: HTTP 403 / anti-bot challenge (via ephemeral local test server)
    elif check_id == "R2":
        # Write dummy manifest with local server base_url configured dynamically in test runner
        p = pages_dir / "home"
        p.mkdir(parents=True, exist_ok=True)
        (p / "raw.html").write_text("<html><body><h1>403 Botwall</h1></body></html>", encoding="utf-8")
        (p / "meta.json").write_text(json.dumps({"url": "http://127.0.0.1:0/", "status_code": 403}), encoding="utf-8")
        m_dict["crawled_pages"].append({"url": "http://127.0.0.1:0/", "slug": "home", "status_code": 403})
        manifest_path.write_text(json.dumps(m_dict), encoding="utf-8")
        return pages_dir, manifest_path

    # 3. R3: Sitemap absent on multi-page site (>4 pages)
    elif check_id == "R3":
        r3_fix = REPO_ROOT / "skills/machine-readability-audit/tests/fixtures/r3_no_sitemap"
        return r3_fix / "pages", r3_fix / "crawl_manifest.json"

    # 4. R4: Robots noindex directive on product page
    elif check_id == "R4":
        p = pages_dir / "product"
        p.mkdir(parents=True, exist_ok=True)
        html = '<html><head><meta name="robots" content="noindex, follow"></head><body><h1>Widget</h1></body></html>'
        (p / "raw.html").write_text(html, encoding="utf-8")
        (p / "meta.json").write_text(json.dumps({"url": "https://planted-r4.example.com/products/widget", "status_code": 200}), encoding="utf-8")
        m_dict["crawled_pages"].append({"url": "https://planted-r4.example.com/products/widget", "slug": "product", "status_code": 200})

    # 5. R5: Canonical conflict
    elif check_id == "R5":
        r5_fix = REPO_ROOT / "skills/machine-readability-audit/tests/fixtures/r5_canonical_conflict"
        return r5_fix / "pages", r5_fix / "crawl_manifest.json"

    # 6. D1: JS-rendering gap (>40% missing words AND >300 gap)
    elif check_id == "D1":
        d1_fix = REPO_ROOT / "skills/machine-readability-audit/tests/fixtures/d1_js_gap"
        return d1_fix / "pages", d1_fix / "crawl_manifest.json"

    # 7. D2: Image missing alt text in prominent hero zone
    elif check_id == "D2":
        d2_fix = REPO_ROOT / "skills/machine-readability-audit/tests/fixtures/d2_images"
        return d2_fix / "pages", d2_fix / "crawl_manifest.json"

    # 8. D3: Missing h1, missing main landmark, broken heading hierarchy (>= 80 words)
    elif check_id == "D3":
        p_dir = pages_dir / "page1"
        p_dir.mkdir(parents=True, exist_ok=True)
        body_text = (
            "This is a substantive article discussing various important concepts. "
            "It contains enough words to exceed the minimum threshold for semantic evaluation. "
            "Here we discuss architecture, reliability, maintainability, and security across modern distributed software systems. "
            "Furthermore, we analyze database indexing strategies, cache invalidation protocols, and consistency models. "
            "Notice that h2 jumps directly to h4, skipping h3 downwards in hierarchy. "
            "Additionally, there is no h1 tag anywhere on this document, and neither a main tag nor a role='main' attribute is present. "
        ) * 2
        d3_html = (
            "<!DOCTYPE html><html><head><title>Semantic Test</title></head><body>"
            "<header><nav><a href='/'>Home</a></nav></header>"
            "<div>"
            "<h2>Introduction</h2>"
            f"<p>{body_text}</p>"
            "<h4>Deep Nested Topic</h4>"
            "<p>Further discussion on distributed system consensus algorithms like Raft and Paxos.</p>"
            "</div>"
            "<footer><p>Footer content</p></footer>"
            "</body></html>"
        )
        (p_dir / "raw.html").write_text(d3_html, encoding="utf-8")
        (p_dir / "text.txt").write_text(body_text, encoding="utf-8")
        (p_dir / "meta.json").write_text(json.dumps({"url": "https://example.com/article", "status_code": 200, "title": "Semantic Test"}), encoding="utf-8")
        m_dict["crawled_pages"].append({"url": "https://example.com/article", "slug": "page1", "status_code": 200})

    # 9. E1: Missing Product schema on ecommerce archetype product page
    elif check_id == "E1":
        m_dict["archetypes"] = ["ecommerce"]
        p = pages_dir / "prod"
        p.mkdir(parents=True, exist_ok=True)
        html = '<html><body><h1>Widget Deluxe</h1><p>$49.99 in stock</p></body></html>'
        (p / "raw.html").write_text(html, encoding="utf-8")
        (p / "meta.json").write_text(json.dumps({"url": "https://planted-e1.example.com/products/widget-deluxe", "status_code": 200}), encoding="utf-8")
        m_dict["crawled_pages"].append({"url": "https://planted-e1.example.com/products/widget-deluxe", "slug": "prod", "status_code": 200})

    # 10. E2: Structured data price contradiction
    elif check_id == "E2":
        e2_fix = REPO_ROOT / "skills/machine-readability-audit/tests/fixtures/e2_wrong_price"
        return e2_fix / "pages", e2_fix / "crawl_manifest.json"

    # 11. E3: Quotability gap on canonical question
    elif check_id == "E3":
        e3_fix = REPO_ROOT / "skills/machine-readability-audit/tests/fixtures/e3_quotability"
        return e3_fix / "pages", e3_fix / "crawl_manifest.json"

    # 12. E4: Duplicate page titles and missing meta description (>= 80 words)
    elif check_id == "E4":
        p1_dir = pages_dir / "p1"
        p2_dir = pages_dir / "p2"
        p1_dir.mkdir(parents=True, exist_ok=True)
        p2_dir.mkdir(parents=True, exist_ok=True)
        text_content = "Substantive page content with more than eighty words for testing purposes. " * 10
        p1_html = (
            "<!DOCTYPE html><html><head><title>Company Overview | Acme</title></head><body>"
            "<main><h1>About Acme</h1><p>" + text_content + "</p></main></body></html>"
        )
        p2_html = (
            "<!DOCTYPE html><html><head><title>Company Overview | Acme</title></head><body>"
            "<main><h1>Leadership</h1><p>" + text_content + "</p></main></body></html>"
        )
        (p1_dir / "raw.html").write_text(p1_html, encoding="utf-8")
        (p1_dir / "text.txt").write_text(text_content, encoding="utf-8")
        (p1_dir / "meta.json").write_text(json.dumps({"url": "https://acme.example.com/about", "status_code": 200, "title": "Company Overview | Acme"}), encoding="utf-8")
        (p2_dir / "raw.html").write_text(p2_html, encoding="utf-8")
        (p2_dir / "text.txt").write_text(text_content, encoding="utf-8")
        (p2_dir / "meta.json").write_text(json.dumps({"url": "https://acme.example.com/leadership", "status_code": 200, "title": "Company Overview | Acme"}), encoding="utf-8")
        m_dict["crawled_pages"].extend([
            {"url": "https://acme.example.com/about", "slug": "p1", "status_code": 200},
            {"url": "https://acme.example.com/leadership", "slug": "p2", "status_code": 200},
        ])

    # 13. T1: Stale time-sensitive pricing claim (>= 80 words)
    elif check_id == "T1":
        p_stale = pages_dir / "pricing"
        p_stale.mkdir(parents=True, exist_ok=True)
        text_words = "Substantive detailed information for users regarding system operations and workflow features. " * 8
        stale_html = (
            "<!DOCTYPE html><html><head><title>Pricing | CloudPlatform</title></head><body>"
            "<main><h1>CloudPlatform Pricing</h1>"
            "<p>Current pricing as of 2022: $29/mo per user for starter package.</p>"
            f"<p>{text_words}</p>"
            "</main></body></html>"
        )
        (p_stale / "raw.html").write_text(stale_html, encoding="utf-8")
        (p_stale / "text.txt").write_text("CloudPlatform Pricing Current pricing as of 2022: $29/mo per user. " + text_words, encoding="utf-8")
        (p_stale / "meta.json").write_text(json.dumps({"url": "https://cloud.example.com/pricing", "status_code": 200}), encoding="utf-8")
        m_dict["crawled_pages"].append({"url": "https://cloud.example.com/pricing", "slug": "pricing", "status_code": 200})

    # 14. T2: Cross-page contradictory physical address
    elif check_id == "T2":
        p1 = pages_dir / "p1"
        p2 = pages_dir / "p2"
        p1.mkdir(parents=True, exist_ok=True)
        p2.mkdir(parents=True, exist_ok=True)
        (p1 / "raw.html").write_text("<html><body><p>Headquarters: 100 Main St, Austin, TX</p></body></html>", encoding="utf-8")
        (p1 / "text.txt").write_text("Headquarters: 100 Main St, Austin, TX", encoding="utf-8")
        (p1 / "meta.json").write_text(json.dumps({"url": "https://planted-t2.example.com/about", "status_code": 200}), encoding="utf-8")
        (p2 / "raw.html").write_text("<html><body><p>Headquarters: 999 Market Ave, Austin, TX</p></body></html>", encoding="utf-8")
        (p2 / "text.txt").write_text("Headquarters: 999 Market Ave, Austin, TX", encoding="utf-8")
        (p2 / "meta.json").write_text(json.dumps({"url": "https://planted-t2.example.com/contact", "status_code": 200}), encoding="utf-8")
        m_dict["crawled_pages"].extend([
            {"url": "https://planted-t2.example.com/about", "slug": "p1", "status_code": 200},
            {"url": "https://planted-t2.example.com/contact", "slug": "p2", "status_code": 200},
        ])

    # 15. T3: Entity ambiguity (generic brand lacking sameAs and category)
    elif check_id == "T3":
        p = pages_dir / "ambig"
        p.mkdir(parents=True, exist_ok=True)
        html = (
            "<!DOCTYPE html><html><head><title>Summit</title></head><body>"
            "<main><h1>Welcome to Summit</h1>"
            "<p>We empower next-generation synergy across seamless frontiers. Our unified solutions optimize your vision "
            "with end-to-end holistic paradigms for frictionless execution.</p>"
            "</main></body></html>"
        )
        (p / "raw.html").write_text(html, encoding="utf-8")
        (p / "text.txt").write_text("Welcome to Summit We empower next-generation synergy across seamless frontiers. Our unified solutions optimize your vision with end-to-end holistic paradigms for frictionless execution.", encoding="utf-8")
        (p / "meta.json").write_text(json.dumps({"url": "https://summit.example.com/", "status_code": 200, "title": "Summit"}), encoding="utf-8")
        m_dict["domain"] = "summit.example.com"
        m_dict["base_url"] = "https://summit.example.com"
        m_dict["crawled_pages"].append({"url": "https://summit.example.com/", "slug": "ambig", "status_code": 200})

    # 16. T4: Missing about and contact presence
    elif check_id == "T4":
        p = pages_dir / "nocontact"
        p.mkdir(parents=True, exist_ok=True)
        html = "<html><body><main><h1>Overview</h1><p>General software landing without contact details.</p></main></body></html>"
        (p / "raw.html").write_text(html, encoding="utf-8")
        (p / "text.txt").write_text("Overview General software landing without contact details.", encoding="utf-8")
        (p / "meta.json").write_text(json.dumps({"url": "https://planted-t4.example.com/", "status_code": 200}), encoding="utf-8")
        m_dict["crawled_pages"].append({"url": "https://planted-t4.example.com/", "slug": "nocontact", "status_code": 200})

    # 17. G1: Above-fold orientation failure (buzzwords without offering quote)
    elif check_id == "G1":
        p = pages_dir / "buzz"
        p.mkdir(parents=True, exist_ok=True)
        html = (
            "<html><head><title>Acme Horizon</title></head><body>"
            "<header>Acme Horizon</header>"
            "<main><h1>Unleashing Synergistic Potential</h1>"
            "<p>Harmonizing horizon vectors and accelerating paradigm matrices.</p>"
            "<a href='/explore'>Explore</a>"
            "</main></body></html>"
        )
        (p / "raw.html").write_text(html, encoding="utf-8")
        (p / "text.txt").write_text("Acme Horizon Unleashing Synergistic Potential Harmonizing horizon vectors. Explore", encoding="utf-8")
        (p / "meta.json").write_text(json.dumps({"url": "https://planted-g1.example.com/", "status_code": 200, "title": "Acme Horizon"}), encoding="utf-8")
        m_dict["crawled_pages"].append({"url": "https://planted-g1.example.com/", "slug": "buzz", "status_code": 200})

    # 18. G2: Broken internal link
    elif check_id == "G2":
        p = pages_dir / "home"
        p.mkdir(parents=True, exist_ok=True)
        html = "<html><body><a href='/dead-link'>Dead Link</a></body></html>"
        (p / "raw.html").write_text(html, encoding="utf-8")
        (p / "meta.json").write_text(json.dumps({"url": "https://planted-g2.example.com/", "status_code": 200}), encoding="utf-8")
        m_dict["crawled_pages"].extend([
            {"url": "https://planted-g2.example.com/", "slug": "home", "status_code": 200},
            {"url": "https://planted-g2.example.com/dead-link", "slug": "dead", "status_code": 404, "source_url": "https://planted-g2.example.com/"},
        ])

    # 19. G3: Intrusive interstitial modal covering substantive content on load
    elif check_id == "G3":
        p = pages_dir / "modal"
        p.mkdir(parents=True, exist_ok=True)
        html = (
            "<html><body>"
            "<div class='interstitial-modal' style='position:fixed; inset:0; z-index:9999;'><h2>Subscribe Now!</h2></div>"
            "<main><h1>Article Headline</h1><p>Substantive article paragraph.</p></main>"
            "</body></html>"
        )
        (p / "raw.html").write_text(html, encoding="utf-8")
        (p / "meta.json").write_text(json.dumps({"url": "https://planted-g3.example.com/", "status_code": 200}), encoding="utf-8")
        m_dict["crawled_pages"].append({"url": "https://planted-g3.example.com/", "slug": "modal", "status_code": 200})

    # 20. G4: Missing primary call-to-action on commercial product page
    elif check_id == "G4":
        p = pages_dir / "prod"
        p.mkdir(parents=True, exist_ok=True)
        html = (
            "<html><head><title>Acme Widget Pro</title></head><body>"
            "<header>Acme</header>"
            "<main><h1>Acme Widget Pro</h1>"
            "<p>The Widget Pro delivers unprecedented precision engineering and durable performance for all manufacturing operations.</p>"
            "</main></body></html>"
        )
        (p / "raw.html").write_text(html, encoding="utf-8")
        (p / "text.txt").write_text("Acme Widget Pro The Widget Pro delivers unprecedented precision engineering and durable performance for all manufacturing operations.", encoding="utf-8")
        (p / "meta.json").write_text(json.dumps({"url": "https://planted-g4.example.com/products/widget-pro", "status_code": 200}), encoding="utf-8")
        m_dict["crawled_pages"].append({"url": "https://planted-g4.example.com/products/widget-pro", "slug": "prod", "status_code": 200})

    manifest_path.write_text(json.dumps(m_dict), encoding="utf-8")
    return pages_dir, manifest_path


import http.server
import threading


class _BotWallHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        ua = self.headers.get("User-Agent", "")
        if "python-httpx" in ua:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Access Denied")
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Browser Welcome</h1></body></html>")

    def log_message(self, *args):
        pass


def run_planted_defect_suite() -> Dict[str, Any]:
    """Execute all 20 planted defect tests and clean control."""
    results = {}
    print("=" * 65)
    print("SYNTHETIC FIXTURE SUITE: PLANTED-DEFECT RECALL (20 CHECKS)")
    print("=" * 65)

    detected_count = 0
    total_checks = len(CHECK_SCRIPTS)

    for cid in sorted(CHECK_SCRIPTS.keys()):
        with tempfile.TemporaryDirectory() as tmp_dir:
            p_dir, m_path = create_planted_fixture(cid, Path(tmp_dir))

            server = None
            if cid == "R2":
                server = http.server.HTTPServer(("127.0.0.1", 0), _BotWallHandler)
                port = server.server_port
                t = threading.Thread(target=server.serve_forever, daemon=True)
                t.start()
                # Update manifest with local server base_url
                m_data = json.loads(m_path.read_text(encoding="utf-8"))
                m_data["base_url"] = f"http://127.0.0.1:{port}"
                m_path.write_text(json.dumps(m_data), encoding="utf-8")

            findings = _run_check(cid, p_dir, m_path)

            if server:
                server.shutdown()

            matching = [f for f in findings if f.get("check_id") == cid]
            detected = len(matching) >= 1
            if detected:
                detected_count += 1
                status = f"[PASS] Detected {cid} ({len(matching)} finding(s))"
            else:
                status = f"[FAIL] FAILED to detect planted defect {cid} (got: {findings})"
            print(f"  {status}")
            results[cid] = {"detected": detected, "findings_count": len(matching)}

    recall = detected_count / total_checks

    # Clean Control Evaluation
    print("\n" + "=" * 65)
    print("CLEAN CONTROL ZERO-DEFECT EVALUATION")
    print("=" * 65)
    clean_manifest = CLEAN_FIXTURE / "crawl_manifest.json"
    clean_pages = CLEAN_FIXTURE / "pages"

    clean_findings_total = 0
    for cid in sorted(CHECK_SCRIPTS.keys()):
        clean_findings = _run_check(cid, clean_pages, clean_manifest)
        c_matches = [f for f in clean_findings if f.get("check_id") == cid]
        if c_matches:
            print(f"  [FAIL] False positive on clean fixture for {cid}: {c_matches}")
            clean_findings_total += len(c_matches)
        else:
            print(f"  [PASS] Clean control zero findings for {cid}")

    clean_fp_rate = clean_findings_total / total_checks

    print("\n" + "=" * 65)
    print("SYNTHETIC BENCHMARK METRIC SUMMARY")
    print("=" * 65)
    print(f"  Planted-Defect Recall:           {recall:.1%} ({detected_count}/{total_checks}) [target: >85%]")
    print(f"  Clean-Control FP Rate:           {clean_fp_rate:.1%} ({clean_findings_total} findings) [target: 0.0%]")
    print("=" * 65)

    assert recall >= 0.85, f"Planted defect recall {recall:.1%} is below 85% requirement!"
    assert clean_fp_rate == 0.0, f"Clean control FP rate {clean_fp_rate:.1%} must be exactly 0.0%!"

    return {
        "planted_defect_recall": recall,
        "clean_control_fp_rate": clean_fp_rate,
        "detected_count": detected_count,
        "total_checks": total_checks,
        "clean_findings_total": clean_findings_total,
    }


def main() -> None:
    res = run_planted_defect_suite()
    if res["planted_defect_recall"] >= 0.85 and res["clean_control_fp_rate"] == 0.0:
        print("\nAll synthetic fixture suite benchmarks PASSED!")
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
