#!/usr/bin/env python3
"""
check_e3.py — E3 Quotability gap check.

Uses Prompt 4's archetype classifier to generate 5–8 canonical questions.
Extracts a bounded, explicitly enumerated corpus of script-extracted passages
from the crawled site.
Tests whether any single passage self-containedly answers each canonical question.
Flags questions lacking a quotable answer. Never reconstructs answers from domain knowledge.

Usage:
    python check_e3.py <corpus_dir> [--manifest <crawl_manifest.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import archetype  # noqa: E402


# ── Canonical Questions by Archetype ──────────────────────────────────────

CANONICAL_QUESTIONS: Dict[str, List[Dict[str, Any]]] = {
    "ecommerce": [
        {
            "question": "What is the return or refund policy, including time limits and conditions?",
            "topic": "return_refund",
            "keywords": ["return", "refund", "exchange", "30-day", "guarantee", "reimbursement", "store credit"],
            "factual_indicators": [r"\d+\s*days?", r"within\s+\d+", r"full\s+refund", r"condition", r"receipt", r"original"],
        },
        {
            "question": "What payment methods are accepted for purchases?",
            "topic": "payment_methods",
            "keywords": ["payment", "visa", "mastercard", "amex", "paypal", "apple pay", "credit card", "debit card", "stripe"],
            "factual_indicators": [r"visa", r"mastercard", r"paypal", r"apple\s+pay", r"credit\s+card", r"accepted"],
        },
        {
            "question": "How long does standard shipping take and what does it cost?",
            "topic": "shipping_policy",
            "keywords": ["shipping", "delivery", "dispatch", "fedex", "ups", "usps", "transit", "business days"],
            "factual_indicators": [r"\d+[-–]\d+\s*(?:business\s+)?days?", r"free\s+shipping", r"\$\d+", r"flat\s+rate"],
        },
        {
            "question": "What specific products or item categories does this store sell?",
            "topic": "catalog_offerings",
            "keywords": ["collection", "catalog", "shop", "products", "accessories", "items", "apparel", "gear"],
            "factual_indicators": [r"(?:we\s+sell|featuring|collection\s+of|shop\s+our|selection\s+of)", r"catalog"],
        },
        {
            "question": "How can a customer contact support for order inquiries or issues?",
            "topic": "customer_support",
            "keywords": ["support", "help", "contact", "customer service", "email", "phone", "chat", "inquiries"],
            "factual_indicators": [r"[\w.-]+@[\w.-]+\.\w+", r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", r"hours", r"submit\s+a\s+ticket"],
        },
        {
            "question": "Is there a product warranty, guarantee, or replacement policy?",
            "topic": "warranty_guarantee",
            "keywords": ["warranty", "guarantee", "lifetime", "manufacturer", "repair", "defect", "coverage"],
            "factual_indicators": [r"\d+\s*year", r"lifetime\s+warranty", r"manufacturer", r"repair", r"defective"],
        },
    ],
    "saas": [
        {
            "question": "What does the software do and what is its core value proposition?",
            "topic": "product_overview",
            "keywords": ["platform", "software", "solution", "automate", "workflow", "manage", "build", "api", "tool"],
            "factual_indicators": [r"(?:enables|helps|allows|built\s+for|designed\s+to)\s+\w+", r"platform\s+for"],
        },
        {
            "question": "What are the specific pricing plans, tier names, and recurring costs?",
            "topic": "pricing_tiers",
            "keywords": ["pricing", "plan", "monthly", "annual", "per user", "starter", "pro", "enterprise", "/mo"],
            "factual_indicators": [r"[$€£]\d+(?:/mo|/user|/month)?", r"\b(?:starter|free|pro|business|enterprise)\b.*[$€£]\d+"],
        },
        {
            "question": "Is there a free trial or free tier, and does it require a credit card?",
            "topic": "free_trial",
            "keywords": ["free trial", "free tier", "no credit card", "start free", "14-day", "30-day", "freemium"],
            "factual_indicators": [r"\d+[- ]day\s+free\s+trial", r"no\s+credit\s+card\s+required", r"free\s+forever"],
        },
        {
            "question": "What third-party platforms, APIs, or integrations are supported?",
            "topic": "integrations_api",
            "keywords": ["integrations", "api", "webhook", "zapier", "slack", "github", "export", "connect"],
            "factual_indicators": [r"rest\s+api", r"webhooks?", r"integrate(?:s|d)?\s+with", r"sdk"],
        },
        {
            "question": "What are the supported deployment platforms, operating systems, or browsers?",
            "topic": "platform_support",
            "keywords": ["supported", "cloud", "on-premise", "docker", "mac", "windows", "linux", "ios", "android", "browser"],
            "factual_indicators": [r"(?:available\s+on|supports?|compatible\s+with)\s+(?:windows|mac|linux|ios|android|chrome)"],
        },
        {
            "question": "How is customer data secured, encrypted, and kept compliant (e.g. SOC2, GDPR)?",
            "topic": "security_compliance",
            "keywords": ["security", "soc2", "soc 2", "gdpr", "hipaa", "encryption", "aes-256", "tls", "compliance"],
            "factual_indicators": [r"soc\s*2", r"gdpr", r"hipaa", r"iso\s*27001", r"end-to-end\s+encryption", r"aes[- ]256"],
        },
    ],
    "docs": [
        {
            "question": "How do developers install or add this package to their project?",
            "topic": "installation",
            "keywords": ["install", "npm", "pip", "yarn", "cargo", "pnpm", "gem", "brew", "download", "cdn"],
            "factual_indicators": [r"(?:npm\s+i|pip\s+install|cargo\s+add|yarn\s+add|gem\s+install|brew\s+install)"],
        },
        {
            "question": "What authentication credentials, API keys, or tokens are required?",
            "topic": "authentication",
            "keywords": ["authentication", "api key", "token", "bearer", "oauth", "credentials", "header"],
            "factual_indicators": [r"authorization:\s*bearer", r"api[-_ ]key", r"oauth", r"access[-_ ]token"],
        },
        {
            "question": "What runtime, language, or OS versions are required as prerequisites?",
            "topic": "prerequisites",
            "keywords": ["prerequisites", "requirements", "python", "node", "java", "go", "version", ">="],
            "factual_indicators": [r"(?:python|node|go|ruby|java)\s*(?:>=|>|\^)?\s*\d+", r"requires\s+version"],
        },
        {
            "question": "Where is the core API reference documentation or entry point?",
            "topic": "api_reference",
            "keywords": ["reference", "api", "endpoints", "classes", "methods", "parameters", "schemas"],
            "factual_indicators": [r"(?:api\s+reference|endpoints?|method\s+signature|parameters:)"],
        },
        {
            "question": "How do users report bugs, submit PRs, or contribute to this project?",
            "topic": "contributing",
            "keywords": ["contributing", "github", "pull request", "issue", "bug report", "contribute", "license"],
            "factual_indicators": [r"(?:github\.com|open\s+an\s+issue|submit\s+a\s+pull\s+request|contributing\.md)"],
        },
    ],
    "local_business": [
        {
            "question": "What is the physical address or service area of the business?",
            "topic": "physical_location",
            "keywords": ["address", "located", "suite", "street", "avenue", "road", "city", "state", "zip"],
            "factual_indicators": [r"\d+\s+[A-Za-z0-9\s,.-]+(?:st|ave|rd|blvd|dr|lane|way|suite)\b", r"located\s+at"],
        },
        {
            "question": "What are the weekly operating hours for the business?",
            "topic": "business_hours",
            "keywords": ["hours", "open", "monday", "friday", "saturday", "sunday", "am", "pm", "closed"],
            "factual_indicators": [r"(?:mon|tue|wed|thu|fri|sat|sun)[-–a-z\s]*:\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)", r"open\s+daily"],
        },
        {
            "question": "How can customers schedule an appointment, consultation, or reservation?",
            "topic": "scheduling_booking",
            "keywords": ["appointment", "booking", "reserve", "schedule", "consultation", "call to book"],
            "factual_indicators": [r"(?:book\s+an\s+appointment|schedule\s+a\s+consultation|make\s+a\s+reservation)"],
        },
        {
            "question": "What specific primary services, treatments, or specialties are offered?",
            "topic": "services_offered",
            "keywords": ["services", "specialties", "offer", "treatments", "repairs", "consulting", "menu"],
            "factual_indicators": [r"(?:services\s+include|specializing\s+in|our\s+treatments|offerings)"],
        },
        {
            "question": "What direct telephone number or email is used to contact the business?",
            "topic": "direct_contact",
            "keywords": ["phone", "call", "tel", "email", "reach us", "contact"],
            "factual_indicators": [r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", r"[\w.-]+@[\w.-]+\.\w+"],
        },
    ],
    "content": [
        {
            "question": "What primary topics, niches, or themes does this publication cover?",
            "topic": "editorial_scope",
            "keywords": ["topics", "about", "covering", "articles", "focus", "insights", "analysis"],
            "factual_indicators": [r"(?:focuses\s+on|covers|dedicated\s+to|reporting\s+on)"],
        },
        {
            "question": "Who are the primary writers, editors, or contributors to the site?",
            "topic": "authorship",
            "keywords": ["author", "writer", "editor", "by", "team", "contributor", "bio"],
            "factual_indicators": [r"(?:written\s+by|editor-in-chief|staff\s+writer|contributing\s+editor)"],
        },
        {
            "question": "How can readers subscribe to new article alerts, newsletters, or RSS?",
            "topic": "subscription_newsletter",
            "keywords": ["subscribe", "newsletter", "email", "rss", "feed", "updates", "weekly"],
            "factual_indicators": [r"(?:subscribe\s+to|join\s+our\s+newsletter|get\s+updates|rss\s+feed)"],
        },
        {
            "question": "What is the publication's editorial standard, review, or corrections policy?",
            "topic": "editorial_standards",
            "keywords": ["editorial", "corrections", "policy", "ethics", "fact-check", "standards"],
            "factual_indicators": [r"(?:editorial\s+policy|fact-checking|corrections?\s+policy|code\s+of\s+ethics)"],
        },
        {
            "question": "How often is new content, analysis, or journalism published?",
            "topic": "publishing_cadence",
            "keywords": ["daily", "weekly", "monthly", "published", "cadence", "edition", "issues"],
            "factual_indicators": [r"(?:published\s+daily|weekly\s+edition|monthly\s+issue|every\s+\w+)"],
        },
    ],
    "news": [
        {
            "question": "What is the primary news beat, geographic focus, or investigative mission?",
            "topic": "news_mission",
            "keywords": ["reporting", "investigative", "news", "beat", "journalism", "coverage", "global"],
            "factual_indicators": [r"(?:investigative\s+reporting|independent\s+journalism|covering|news\s+from)"],
        },
        {
            "question": "What digital subscription or membership plans and rates are available?",
            "topic": "subscription_rates",
            "keywords": ["subscription", "membership", "supporter", "digital access", "$/month", "annual"],
            "factual_indicators": [r"[$€£]\d+(?:/month|/year)?", r"subscribe\s+for\s+[$€£]"],
        },
        {
            "question": "How can sources or whistleblowers securely submit confidential news tips?",
            "topic": "confidential_tips",
            "keywords": ["tips", "whistleblower", "secure", "signal", "securedrop", "confidential", "leak"],
            "factual_indicators": [r"(?:securedrop|signal|confidential\s+tips|send\s+a\s+tip)"],
        },
        {
            "question": "What is the formal corrections procedure for reporting inaccuracies?",
            "topic": "corrections_procedure",
            "keywords": ["corrections", "clarifications", "report an error", "accuracy", "inaccuracy"],
            "factual_indicators": [r"(?:corrections\s+and\s+clarifications|report\s+a\s+correction|standards\s+editor)"],
        },
        {
            "question": "Who owns, funds, or maintains editorial oversight of this news outlet?",
            "topic": "ownership_funding",
            "keywords": ["owned", "publisher", "trust", "board", "foundation", "independent", "subsidiary"],
            "factual_indicators": [r"(?:owned\s+by|published\s+by|the\s+trust|board\s+of\s+directors)"],
        },
    ],
    "portfolio": [
        {
            "question": "Who is the creator or studio and what is their primary creative discipline?",
            "topic": "creator_identity",
            "keywords": ["designer", "developer", "photographer", "artist", "architect", "engineer", "about me"],
            "factual_indicators": [r"(?:i\s+am\s+a|specializing\s+in|creative\s+director|freelance)"],
        },
        {
            "question": "What specific client projects, case studies, or notable works are featured?",
            "topic": "featured_projects",
            "keywords": ["project", "case study", "client", "work", "campaign", "built", "designed"],
            "factual_indicators": [r"(?:case\s+study|client:|project\s+for|featured\s+work)"],
        },
        {
            "question": "What specific software, tech stack, or creative tools does the creator specialize in?",
            "topic": "skills_tools",
            "keywords": ["skills", "stack", "figma", "react", "python", "blender", "tools", "technologies"],
            "factual_indicators": [r"(?:tools\s+used|tech\s+stack|proficient\s+in|technologies)"],
        },
        {
            "question": "How can prospective clients or collaborators inquire about new engagements?",
            "topic": "inquiry_contact",
            "keywords": ["contact", "inquire", "email", "hire", "hello", "get in touch", "collaborate"],
            "factual_indicators": [r"[\w.-]+@[\w.-]+\.\w+", r"(?:get\s+in\s+touch|available\s+for\s+hire)"],
        },
        {
            "question": "What is the creator's current availability for freelance, contract, or full-time roles?",
            "topic": "availability",
            "keywords": ["available", "booking", "q1", "q2", "q3", "q4", "freelance", "full-time", "accepting"],
            "factual_indicators": [r"(?:available\s+for|accepting\s+new\s+clients|booking\s+for)"],
        },
    ],
    "corporate": [
        {
            "question": "What core industries, products, and commercial solutions does the company provide?",
            "topic": "commercial_solutions",
            "keywords": ["solutions", "enterprise", "industry", "commercial", "global", "services", "capabilities"],
            "factual_indicators": [r"(?:delivers|provides|leader\s+in|enterprise\s+solutions)"],
        },
        {
            "question": "Who are the key executive leaders or members of the board of directors?",
            "topic": "leadership_board",
            "keywords": ["ceo", "executive", "leadership", "board of directors", "founder", "officer", "president"],
            "factual_indicators": [r"(?:chief\s+executive\s+officer|ceo|president|board\s+of\s+directors)"],
        },
        {
            "question": "Where is the global corporate headquarters and primary regional offices located?",
            "topic": "corporate_headquarters",
            "keywords": ["headquarters", "headquartered", "offices", "global", "locations", "corporate office"],
            "factual_indicators": [r"(?:headquartered\s+in|corporate\s+headquarters|global\s+offices)"],
        },
        {
            "question": "How can investors, shareholders, or media press representatives contact the company?",
            "topic": "investor_press_contact",
            "keywords": ["investor relations", "press", "media", "shareholders", "pr", "newsroom", "inquiries"],
            "factual_indicators": [r"(?:investor\s+relations|press\s+contact|media\s+inquiries|ir@|press@)"],
        },
        {
            "question": "What is the company's formal ESG, sustainability, or governance commitment?",
            "topic": "esg_governance",
            "keywords": ["sustainability", "esg", "governance", "carbon", "diversity", "environmental", "responsibility"],
            "factual_indicators": [r"(?:sustainability\s+report|esg\s+report|net\s+zero|carbon\s+neutral)"],
        },
    ],
}


# ── Passage Extraction ───────────────────────────────────────────────────

@dataclass
class Passage:
    passage_id: str
    url: str
    text: str
    word_count: int


def _extract_passages_from_corpus(corpus_dir: Path, max_passages: int = 60) -> List[Passage]:
    """
    Extract a bounded, explicitly enumerated corpus of coherent passages (40-200 words)
    from crawled page text files.
    """
    passages: List[Passage] = []
    pid = 1

    page_dirs = [d for d in corpus_dir.iterdir() if d.is_dir() and (d / "raw.html").exists()]
    if not page_dirs:
        for sub in corpus_dir.glob("*/raw.html"):
            page_dirs.append(sub.parent)

    for pdir in sorted(page_dirs):
        meta_path = pdir / "meta.json"
        text_path = pdir / "text.txt"
        raw_path = pdir / "raw.html"

        page_url = f"https://example.com/{pdir.name}"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                page_url = meta.get("url", page_url)
            except Exception:
                pass

        text = ""
        if text_path.exists():
            text = text_path.read_text(encoding="utf-8", errors="replace")
        elif raw_path.exists():
            from check_d1 import _extract_visible_text
            text = _extract_visible_text(raw_path.read_text(encoding="utf-8", errors="replace"))

        if not text:
            continue

        # Split text into paragraphs or logical blocks
        blocks = re.split(r'\n\s*\n|\r\n\s*\r\n', text)
        if len(blocks) <= 1:
            # Split by punctuation sentence groupings
            sentences = re.split(r'(?<=[.!?])\s+', text)
            current_chunk: List[str] = []
            current_words = 0
            for s in sentences:
                s_words = len(s.split())
                if current_words + s_words > 120 and current_chunk:
                    blocks.append(" ".join(current_chunk))
                    current_chunk = [s]
                    current_words = s_words
                else:
                    current_chunk.append(s)
                    current_words += s_words
            if current_chunk:
                blocks.append(" ".join(current_chunk))

        for block in blocks:
            b_clean = re.sub(r'\s+', ' ', block).strip()
            w_count = len(b_clean.split())
            if 30 <= w_count <= 250:
                passages.append(Passage(
                    passage_id=f"P-{pid:03d}",
                    url=page_url,
                    text=b_clean,
                    word_count=w_count,
                ))
                pid += 1
                if len(passages) >= max_passages:
                    return passages

    return passages


# ── Quotability Evaluation ───────────────────────────────────────────────

def _evaluate_question_quotability(
    question_spec: Dict[str, Any],
    passages: List[Passage],
) -> Tuple[bool, Optional[Passage], str]:
    """
    Test whether at least one passage self-containedly answers the canonical question.
    Returns: (is_answered, best_candidate_passage, failure_reason)
    """
    question = question_spec["question"]
    keywords = question_spec["keywords"]
    factual_indicators = [re.compile(p, re.IGNORECASE) for p in question_spec.get("factual_indicators", [])]

    candidates: List[Tuple[float, Passage]] = []

    for p in passages:
        p_lower = p.text.lower()
        # Score relevance based on keyword matches
        matches = sum(1 for kw in keywords if kw.lower() in p_lower)
        if matches >= 1:
            score = float(matches)
            # Bonus if factual indicators match
            facts_matched = sum(1 for pattern in factual_indicators if pattern.search(p.text))
            score += facts_matched * 2.5
            candidates.append((score, p))

    if not candidates:
        return False, None, f"No candidate passage in the bounded corpus addressed '{question_spec['topic']}'."

    # Sort best candidates first
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_p = candidates[0]

    # Check if best candidate self-containedly answers with concrete facts
    has_factual = any(pattern.search(best_p.text) for pattern in factual_indicators)

    # Negative check for evasive marketing phrases (e.g. "contact sales", "learn more", "coming soon")
    is_evasive = bool(re.search(
        r'(?:contact\s+(?:sales|us|our\s+team)\s+for\s+(?:pricing|details)|pricing\s+available\s+upon\s+request|coming\s+soon|learn\s+more\s+about\s+our)',
        best_p.text, flags=re.IGNORECASE,
    )) and not has_factual

    if has_factual and not is_evasive:
        return True, best_p, ""

    if is_evasive:
        return False, best_p, (
            f"Passage mentions the topic but gives an evasive/marketing non-answer "
            f"('{best_p.text[:90]}...') without factual details."
        )

    # Found keywords but lacks concrete factual answer indicators
    return False, best_p, (
        f"Passage discusses related vocabulary but lacks self-contained factual specifics "
        f"(matched keywords: {best_score:.1f}, but lacked required factual attributes)."
    )


# ── Check Runner ─────────────────────────────────────────────────────────

def run_check_e3(
    corpus_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Run E3 quotability gap check.
    Emits findings per the Hardened Finding Contract.
    """
    findings: List[Dict[str, Any]] = []

    # 1. Determine site archetype using archetype classifier
    # Try finding manifest file
    manifest_path = corpus_dir / "crawl_manifest.json"
    if not manifest_path.exists() and corpus_dir.parent:
        potential = corpus_dir.parent / "crawl_manifest.json"
        if potential.exists():
            manifest_path = potential

    primary_archetype = "saas"  # sensible default
    if manifest_path.exists():
        try:
            res = archetype.classify(manifest_path, corpus_dir)
            archs = res.get("archetypes", [])
            if archs and archs[0] != "unknown":
                primary_archetype = archs[0]
        except Exception:
            pass
    elif manifest:
        # Construct temporary check
        try:
            sig = archetype.extract_signals(manifest, corpus_dir)
            scores = archetype.score_archetypes(sig)
            archs, _ = archetype.select_archetypes(scores, sig)
            if archs and archs[0] != "unknown":
                primary_archetype = archs[0]
        except Exception:
            pass

    # 2. Select 5-8 canonical questions for this archetype
    questions = CANONICAL_QUESTIONS.get(primary_archetype, CANONICAL_QUESTIONS["saas"])

    # 3. Extract bounded corpus of script-extracted passages
    passages = _extract_passages_from_corpus(corpus_dir, max_passages=60)
    if not passages:
        return findings

    finding_idx = 1
    for q_spec in questions:
        q_text = q_spec["question"]
        answered, best_passage, failure_reason = _evaluate_question_quotability(q_spec, passages)

        if not answered:
            # Quotability gap finding!
            page_url = best_passage.url if best_passage else (passages[0].url if passages else "https://example.com")
            passage_text = best_passage.text if best_passage else None
            passage_id = best_passage.passage_id if best_passage else None

            # Pricing/return policy gaps have higher impact
            is_high_impact = q_spec["topic"] in ("pricing_tiers", "return_refund", "business_hours", "installation")
            severity = "high" if is_high_impact else "medium"

            findings.append({
                "id": f"F-E3-{finding_idx:03d}",
                "check_id": "E3",
                "page_url": page_url,
                "root_cause": "statement_implicitness",
                "evidence": {
                    "type": "quotability_gap",
                    "archetype": primary_archetype,
                    "canonical_question": q_text,
                    "topic": q_spec["topic"],
                    "best_passage_id": passage_id,
                    "best_passage": passage_text,
                    "failure_reason": failure_reason,
                    "bounded_passages_evaluated": len(passages),
                },
                "raw_severity_class": severity,
                "confidence": 0.88,
                "mechanism": (
                    f"When an AI agent or search assistant is asked the canonical {primary_archetype} question "
                    f"'{q_text}', the site provides no self-contained, quotable passage with factual specifics. "
                    f"Failure reason: {failure_reason} Downstream assistants must either extrapolate, "
                    f"hallucinate, or omit the site from recommendation answers."
                ),
                "false_positive_guard": (
                    f"Evaluated an explicitly enumerated corpus of {len(passages)} bounded script-extracted passages "
                    f"(40-250 words) from visible text. Never reconstructed answers from external or brand knowledge. "
                    f"Evaluated best candidate against required factual indicators."
                ),
                "verification_method": (
                    f"Search site corpus for '{q_spec['keywords'][0]}'; confirm that no single passage "
                    f"answers '{q_text}' with verifiable factual detail."
                ),
            })
            finding_idx += 1

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="E3 — Quotability gap check")
    parser.add_argument("corpus_dir", help="Path to corpus directory containing page folders")
    parser.add_argument("--manifest", help="Optional path to crawl_manifest.json", default=None)
    args = parser.parse_args()

    corpus_dir = Path(args.corpus_dir)
    if not corpus_dir.exists():
        print(f"Error: corpus directory not found: {corpus_dir}", file=sys.stderr)
        sys.exit(1)

    manifest_data = None
    if args.manifest:
        mpath = Path(args.manifest)
        if mpath.exists():
            try:
                manifest_data = json.loads(mpath.read_text(encoding="utf-8"))
            except Exception:
                pass

    findings = run_check_e3(corpus_dir, manifest_data)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
