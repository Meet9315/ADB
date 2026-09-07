# AI-Discoverability Audit — Agent Skill Marketplace

> Audits any website for AI-discoverability and on-site engagement problems.
> Submission for the Adobe University Hackathon 2026, Round 3.

Full documentation will be added at packaging time (see `PROJECT_CONSTITUTION.md`).

## Skills

| Skill | Role |
|---|---|
| `audit-orchestrator` | Entrypoint — runs the full audit pipeline |
| `site-acquisition` | Crawls and renders the target website |
| `machine-readability-audit` | Checks structured data, robots directives, and metadata |

## Quick start

```bash
# Install dependencies across all skills
pip install -r requirements.txt

# Install Playwright browser engine for headless DOM rendering
playwright install chromium

# Run the full audit pipeline
python skills/audit-orchestrator/scripts/audit.py https://example.com

# Run the test suite
python skills/machine-readability-audit/tests/run_fixtures.py
python skills/machine-readability-audit/tests/test_archetype_fixtures.py
pytest skills/audit-orchestrator/tests/test_models.py
```

