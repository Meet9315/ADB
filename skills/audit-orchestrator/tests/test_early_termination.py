#!/usr/bin/env python3
"""
test_early_termination.py — Validates early termination and graceful degradation under budget limits.

Fulfills Prompt 11, Requirement 4:
"Run the early-termination test: a deliberately slow/oversized synthetic site.
Confirm graceful degradation exactly as designed in Prompt 2/6, and confirm
the final report is schema-valid and marked partial_audit: true with a stated reason."
"""

from __future__ import annotations

import http.server
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "skills/audit-orchestrator/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from audit import run_audit_pipeline  # noqa: E402
from validate_report import validate_report  # noqa: E402


class SlowOversizedHandler(http.server.BaseHTTPRequestHandler):
    """Synthetic server handler that serves an oversized page tree with intentional latency."""

    def log_message(self, format: str, *args: object) -> None:
        pass  # Suppress request logging during tests

    def do_GET(self) -> None:
        # Deliberate per-request delay to simulate a slow / lagging target
        time.sleep(0.8)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        # Oversized link network: 100 pages linked from every page
        links = "".join(f'<li><a href="/page_{i}">Page {i}</a></li>' for i in range(100))
        html = f"""<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <title>Slow Oversized Synthetic Target - {self.path}</title>
        </head>
        <body>
            <main>
                <h1>Slow Oversized Synthetic Target</h1>
                <p>This synthetic site serves endless pages with intentional latency to verify budget boundaries.</p>
                <ul>{links}</ul>
            </main>
        </body>
        </html>"""
        self.wfile.write(html.encode("utf-8"))


def test_early_termination_synthetic_slow_site() -> None:
    print("=" * 70)
    print("EARLY TERMINATION TEST: DELIBERATELY SLOW / OVERSIZED SYNTHETIC SITE")
    print("=" * 70)

    # 1. Start local slow server on ephemeral port
    server = http.server.HTTPServer(("127.0.0.1", 0), SlowOversizedHandler)
    port = server.server_address[1]
    srv_thread = threading.Thread(target=server.serve_forever, daemon=True)
    srv_thread.start()

    target_domain = f"http://127.0.0.1:{port}"
    budget_soft = 2.0
    budget_hard = 4.0

    print(f"[*] Synthetic server listening at {target_domain}")
    print(f"[*] Running audit with tight budget: soft={budget_soft}s, hard={budget_hard}s")

    t0 = time.monotonic()
    try:
        report_dict = run_audit_pipeline(
            domain=target_domain,
            budget_soft=budget_soft,
            budget_hard=budget_hard,
        )
    finally:
        server.shutdown()
        server.server_close()

    elapsed = time.monotonic() - t0
    print(f"\nExecution elapsed time: {elapsed:.2f}s (hard ceiling={budget_hard}s)")

    # 2. Schema validity assertion
    report = validate_report(report_dict)
    print("  [PASS] Final report strictly validates against Pydantic FinalReport schema")

    # 3. Graceful degradation: bounded time
    assert elapsed <= (budget_hard + 6.0), (
        f"Pipeline failed to terminate gracefully within ceiling: {elapsed:.2f}s > {budget_hard + 6.0}s"
    )
    print(f"  [PASS] Pipeline gracefully degraded within ceiling window ({elapsed:.2f}s)")

    # 4. Partial audit assertion
    assert report.audit_metadata.partial_audit is True, (
        f"Expected partial_audit to be True, got {report.audit_metadata.partial_audit}"
    )
    print("  [PASS] report.audit_metadata.partial_audit is True")

    assert report.audit_metadata.partial_audit_reason, (
        "Expected stated non-empty partial_audit_reason"
    )
    print(f"  [PASS] report.audit_metadata.partial_audit_reason: '{report.audit_metadata.partial_audit_reason}'")

    print("\n" + "=" * 70)
    print("CONFIRMED: DELIBERATELY SLOW/OVERSIZED SITE TERMINATED WITH SCHEMA-VALID PARTIAL REPORT")
    print("=" * 70)


def main() -> None:
    test_early_termination_synthetic_slow_site()


if __name__ == "__main__":
    main()
