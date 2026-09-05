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
# Install dependencies
pip install -r skills/site-acquisition/requirements.txt

# Run an audit
# (Detailed instructions in skills/audit-orchestrator/SKILL.md)
```
