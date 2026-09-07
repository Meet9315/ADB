#!/usr/bin/env python3
"""
test_robots.py — Unit tests for robots.txt parsing and RFC 9309 path matching.

Tests:
1. Specific User-agent vs '*' wildcard precedence
2. Multiple consecutive User-agent: lines sharing a directive block
3. Longest-match rule precedence (Allow vs Disallow)
4. Longer Allow rule overriding shorter Disallow rule
5. Longer Disallow rule overriding shorter Allow rule
6. Equal-length rule tie resolution (Allow takes precedence per RFC 9309)
7. Case-insensitive agent matching
8. Wildcard (*) path pattern semantics
9. Terminal end-of-path ($) marker semantics
10. Blank Disallow: directives (allow all)
"""

import sys
from pathlib import Path
import pytest

_HERE = Path(__file__).resolve().parent
SCRIPTS_DIR = _HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from crawl import _parse_robots_txt, is_url_allowed, _is_path_disallowed, _path_matches_rule


def test_consecutive_user_agents_share_directives():
    """Verify multiple consecutive User-agent lines associate with the subsequent rules."""
    raw = """
User-agent: Googlebot
User-agent: AuditBot
User-agent: ClaudeBot
Disallow: /private/
Allow: /private/public/
"""
    rules = _parse_robots_txt(raw)
    assert "googlebot" in rules
    assert "auditbot" in rules
    assert "claudebot" in rules
    assert rules["googlebot"]["disallow"] == ["/private/"]
    assert rules["auditbot"]["disallow"] == ["/private/"]
    assert rules["claudebot"]["disallow"] == ["/private/"]
    assert rules["auditbot"]["allow"] == ["/private/public/"]


def test_specific_agent_priority_over_wildcard():
    """Verify specific user agent rules take precedence over wildcard * rules."""
    raw = """
User-agent: *
Disallow: /

User-agent: AuditBot
Allow: /
"""
    rules = _parse_robots_txt(raw)
    # Target URL is disallowed for generic bot, but allowed for AuditBot
    assert is_url_allowed("https://example.com/page", rules) is True


def test_wildcard_fallback_when_no_specific_agent():
    """Verify wildcard * applies when no specific user agent is defined."""
    raw = """
User-agent: SomeOtherBot
Disallow: /

User-agent: *
Disallow: /secret
"""
    rules = _parse_robots_txt(raw)
    assert is_url_allowed("https://example.com/secret/doc", rules) is False
    assert is_url_allowed("https://example.com/public", rules) is True


def test_longest_match_allow_overrides_shorter_disallow():
    """RFC 9309: Longer Allow rule overrides shorter Disallow rule."""
    raw = """
User-agent: *
Disallow: /admin
Allow: /admin/public
"""
    rules = _parse_robots_txt(raw)
    # /admin/public/index.html matches Allow (len 13) and Disallow (len 6) -> Allow wins
    assert is_url_allowed("https://example.com/admin/public/index.html", rules) is True
    # /admin/private matches Disallow (len 6) only -> Disallowed
    assert is_url_allowed("https://example.com/admin/private", rules) is False


def test_longest_match_disallow_overrides_shorter_allow():
    """RFC 9309: Longer Disallow rule overrides shorter Allow rule."""
    raw = """
User-agent: *
Allow: /blog
Disallow: /blog/drafts/
"""
    rules = _parse_robots_txt(raw)
    # /blog/drafts/post-1 matches Disallow (len 13) and Allow (len 5) -> Disallow wins
    assert is_url_allowed("https://example.com/blog/drafts/post-1", rules) is False
    # /blog/news matches Allow (len 5) only -> Allowed
    assert is_url_allowed("https://example.com/blog/news", rules) is True


def test_equal_length_allow_wins_tie():
    """RFC 9309 §2.2.2: If Allow and Disallow patterns have equal length, Allow wins."""
    raw = """
User-agent: *
Disallow: /page
Allow: /page
"""
    rules = _parse_robots_txt(raw)
    assert is_url_allowed("https://example.com/page", rules) is True


def test_case_insensitive_agent_matching():
    """Verify User-agent declarations are matched case-insensitively."""
    raw = """
User-agent: AuDiTbOt
Disallow: /restricted/
"""
    rules = _parse_robots_txt(raw)
    assert is_url_allowed("https://example.com/restricted/data", rules) is False


def test_wildcard_path_patterns():
    """Verify wildcard (*) path patterns match per RFC 9309."""
    assert _path_matches_rule("/files/report.pdf", "/*.pdf") is True
    assert _path_matches_rule("/files/report.html", "/*.pdf") is False
    assert _path_matches_rule("/api/v1/users", "/api/*/users") is True
    assert _path_matches_rule("/api/v2/products", "/api/*/users") is False

    raw = """
User-agent: *
Disallow: /*.pdf
Allow: /public/*.pdf
"""
    rules = _parse_robots_txt(raw)
    assert is_url_allowed("https://example.com/private/doc.pdf", rules) is False
    assert is_url_allowed("https://example.com/public/doc.pdf", rules) is True


def test_end_anchor_path_patterns():
    """Verify terminal ($) marker enforces end-of-path match."""
    assert _path_matches_rule("/index.php", "/*.php$") is True
    assert _path_matches_rule("/index.php?foo=bar", "/*.php$") is False
    assert _path_matches_rule("/index.php/extra", "/*.php$") is False

    raw = """
User-agent: *
Disallow: /*.php$
"""
    rules = _parse_robots_txt(raw)
    assert is_url_allowed("https://example.com/index.php", rules) is False
    assert is_url_allowed("https://example.com/index.php/sub", rules) is True


def test_empty_disallow_allows_everything():
    """Verify empty Disallow: lines reset disallow rules / allow all."""
    raw = """
User-agent: *
Disallow:

User-agent: BadBot
Disallow: /
"""
    rules = _parse_robots_txt(raw)
    assert is_url_allowed("https://example.com/anywhere", rules) is True
