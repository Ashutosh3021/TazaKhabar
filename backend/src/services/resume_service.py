"""
Resume analysis service for TazaKhabar.
Handles PDF/DOCX/TXT extraction, ATS scoring, and suggested keyword additions.
"""
import logging
import re
from typing import Any

import pymupdf

from src.services.llm_service import generate_with_retry
from src.services.trend_service import TECH_KEYWORDS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

async def extract_text_from_pdf(content: bytes) -> str:
    """
    Extract text from PDF bytes using PyMuPDF.

    Raises:
        ValueError: If PDF is encrypted, image-only, or otherwise unreadable.
    """
    doc = pymupdf.open(stream=content, filetype="pdf")
    try:
        if doc.is_encrypted:
            raise ValueError("PDF is password-protected. Please remove the password and re-upload.")

        text_parts = []
        for page in doc:
            page_text = page.get_text()
            if not page_text.strip():
                continue
            text_parts.append(page_text)

        if not text_parts:
            raise ValueError(
                "PDF contains no extractable text. "
                "If this is a scanned/image-based PDF, please convert it to text format first."
            )

        raw_text = "\n".join(text_parts)
        return clean_resume_text(raw_text)
    finally:
        doc.close()


async def extract_text_from_txt(content: bytes) -> str:
    """Extract text from TXT bytes."""
    return clean_resume_text(content.decode("utf-8", errors="ignore"))


async def extract_text(content: bytes, filename: str) -> str:
    """
    Extract text from file content based on file extension/type.

    Args:
        content: Raw file bytes.
        filename: Original filename.

    Returns:
        Extracted and cleaned text.

    Raises:
        ValueError: If format not supported or extraction fails.
    """
    filename_lower = filename.lower() if filename else ""

    if filename_lower.endswith(".pdf") or _is_pdf_magic_bytes(content):
        return await extract_text_from_pdf(content)
    elif filename_lower.endswith(".txt"):
        return await extract_text_from_txt(content)
    else:
        raise ValueError(
            f"Unsupported file format. Please upload a PDF or TXT file. "
            f"Got: {filename or 'unknown'}"
        )


def _is_pdf_magic_bytes(content: bytes) -> bool:
    """Check if content starts with PDF magic bytes."""
    return content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def clean_resume_text(text: str) -> str:
    """
    Clean resume text by removing noise and normalizing whitespace.

    Removes: page numbers, headers, footers, non-ASCII characters.
    """
    # Remove page numbers (standalone numbers on lines)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    # Remove common headers/footers
    text = re.sub(
        r"^(Page \d+ of \d+|©.*|\-{5,}|_{5,}|Contact:|Email:|Phone:.*)$",
        "",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    # Remove email addresses and phone numbers (too noisy for embedding)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "", text)
    text = re.sub(r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "", text)
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    # Remove non-ASCII
    text = text.encode("ascii", "ignore").decode("ascii")
    return text.strip()


# ---------------------------------------------------------------------------
# Resume section chunking
# ---------------------------------------------------------------------------

def chunk_resume_sections(text: str) -> dict[str, str]:
    """
    Parse resume text into named sections.

    Returns:
        Dict with keys: experience, education, skills, projects.
    """
    sections: dict[str, str] = {
        "experience": "",
        "education": "",
        "skills": "",
        "projects": "",
    }

    section_keywords: dict[str, list[str]] = {
        "experience": ["experience", "work history", "employment", "work experience"],
        "education": ["education", "academic", "university", "degree", "college"],
        "skills": ["skills", "technical skills", "technologies", "competencies", "expertise"],
        "projects": ["projects", "personal projects", "open source", "portfolio"],
    }

    current_section = "experience"  # Default
    lines = text.split("\n")
    section_texts: dict[str, list[str]] = {
        "experience": [], "education": [], "skills": [], "projects": []
    }

    for line in lines:
        line_lower = line.lower().strip()
        matched = False
        for section, keywords in section_keywords.items():
            if any(kw in line_lower for kw in keywords):
                if len(line.strip()) < 50:  # Short header line = section marker
                    current_section = section
                    matched = True
                    break

        if not matched:
            section_texts[current_section].append(line)

    for section in sections:
        sections[section] = "\n".join(section_texts[section]).strip()

    return sections


# ---------------------------------------------------------------------------
# ATS scoring
# ---------------------------------------------------------------------------

ATS_SYSTEM = (
    "You are an expert ATS resume analyst. "
    "Write clear, specific feedback a candidate can act on this week. "
    "Use plain English sentences for issues (not labels or JSON keys). "
    "Keywords must be single technologies or skills (e.g. React, PostgreSQL), not full sentences."
)

ATS_PROMPT = """Analyze this resume. Return ONLY valid JSON (no markdown):

{{
  "score": <0-100 integer>,
  "critical_issues": [
    "<One sentence: what is wrong and how to fix it, e.g. 'Add measurable outcomes to your last role (metrics, %, scale).'>",
    "<Second issue>",
    "<Third issue>"
  ],
  "missing_keywords": ["<tech/skill>", "... up to 8 items ATS scanners expect for the candidate's level"]
}}

Rules:
- critical_issues: exactly 3 short actionable sentences (max 120 chars each).
- missing_keywords: 5-8 items only; no duplicates; no generic words like 'experience' or 'teamwork'.

Resume text (first 8000 chars):
{resume_text}

JSON:"""


async def analyze_resume_ats(resume_text: str) -> dict[str, Any]:
    """
    Score a resume using Gemini LLM.

    Returns:
        Dict with score (0-100), critical_issues (list), missing_keywords (list).
    """
    import json

    prompt = ATS_PROMPT.format(resume_text=resume_text[:8000])

    try:
        result = await generate_with_retry(prompt, ATS_SYSTEM)
        result = result.strip()

        # Strip markdown code blocks
        result = re.sub(r"^```json\s*", "", result)
        result = re.sub(r"^```\s*", "", result)
        result = re.sub(r"\s*```$", "", result)

        parsed = json.loads(result)

        return {
            "score": max(0, min(100, int(parsed.get("score", 0)))),
            "critical_issues": _normalize_phrase_list(parsed.get("critical_issues", []), max_items=3),
            "missing_keywords": _normalize_keyword_list(parsed.get("missing_keywords", []), max_items=8),
        }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ATS response as JSON: {e}, result: {result[:200]}")
        return {
            "score": 0,
            "critical_issues": ["Failed to analyze resume. Please try again."],
            "missing_keywords": [],
        }
    except Exception as e:
        logger.error(f"ATS scoring failed: {e}")
        return {
            "score": 0,
            "critical_issues": [f"Analysis error: {str(e)}"],
            "missing_keywords": [],
        }


# ---------------------------------------------------------------------------
# Suggested additions
# ---------------------------------------------------------------------------

SUGGESTIONS_PROMPT = """You are a tech hiring market analyst.

Suggest 5-7 technologies or skills this candidate should ADD to their resume to match current job postings.
Do NOT repeat skills already on the resume. Prefer items from trending market keywords when relevant to their target roles.

Return ONLY a JSON array of strings (no markdown):
["React", "TypeScript", ...]

Already on resume: {resume_keywords}
Resume skills section: {skills_section}
Resume experience excerpt: {experience_excerpt}
Target roles: {user_roles}
Trending in market this week: {booming_keywords}

JSON:"""


async def generate_suggested_additions(
    resume_keywords: list[str],
    user_roles: list[str],
    booming_keywords: list[str],
    resume_sections: dict[str, str] | None = None,
) -> list[str]:
    """
    Generate keyword suggestions using resume sections and market trends.

    Args:
        resume_keywords: Already-present keywords in resume.
        user_roles: Target job roles.
        booming_keywords: Top trending tech keywords (lowercased list).
        resume_sections: Optional dict of parsed resume sections from chunk_resume_sections().

    Returns:
        List of 5-7 suggested keywords to add.
    """
    import json

    sections = resume_sections or {}
    skills_section = sections.get("skills", "")[:2000]
    experience_excerpt = sections.get("experience", "")[:2000]
    if not skills_section and not experience_excerpt:
        combined = sections.get("projects", "") or ""
        experience_excerpt = combined[:2000]

    prompt = SUGGESTIONS_PROMPT.format(
        skills_section=skills_section or "(not detected — infer from experience)",
        experience_excerpt=experience_excerpt or "(not detected)",
        resume_keywords=", ".join(resume_keywords[:50]) if resume_keywords else "(none detected)",
        user_roles=", ".join(user_roles) if user_roles else "software engineer",
        booming_keywords=", ".join(booming_keywords[:20]) if booming_keywords else "(no trend data)",
    )

    resume_lower = {kw.lower() for kw in resume_keywords}

    try:
        result = await generate_with_retry(prompt, None)
        result = result.strip()
        result = re.sub(r"^```\w*\s*", "", result)
        result = re.sub(r"\s*```$", "", result)
        suggestions = json.loads(result)

        filtered = _normalize_keyword_list(suggestions, max_items=7)
        filtered = [s for s in filtered if s.lower() not in resume_lower]
        if filtered:
            return filtered
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to generate suggestions: {e}")

    # Fallback: trending keywords not already on resume
    if booming_keywords:
        return [
            kw for kw in booming_keywords
            if kw and kw.lower() not in resume_lower
        ][:7]
    return []


def _normalize_phrase_list(items: list, max_items: int = 3) -> list[str]:
    """Clean LLM issue strings for UI display."""
    out: list[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        text = re.sub(r"\s+", " ", item.strip().strip('"').strip("'"))
        if not text or len(text) < 8:
            continue
        if text.lower() in {x.lower() for x in out}:
            continue
        out.append(text[:200])
        if len(out) >= max_items:
            break
    return out


def _normalize_keyword_list(items: list, max_items: int = 10) -> list[str]:
    """Normalize skill/keyword tokens from LLM output."""
    out: list[str] = []
    skip = {"experience", "teamwork", "communication", "leadership", "problem solving"}
    for item in items:
        if not isinstance(item, str):
            continue
        text = item.strip().strip('"').strip("'")
        if not text or len(text) > 40:
            continue
        if " " in text and len(text.split()) > 4:
            continue
        key = text.lower()
        if key in skip or key in {x.lower() for x in out}:
            continue
        out.append(text)
        if len(out) >= max_items:
            break
    return out


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

async def extract_keywords_from_resume(resume_text: str) -> list[str]:
    """
    Extract matching tech keywords from resume text.

    Uses the TECH_KEYWORDS list from trend_service.
    """
    text_lower = resume_text.lower()
    return [kw for kw in TECH_KEYWORDS if kw.lower() in text_lower]


# ---------------------------------------------------------------------------
# Module initialization print
# ---------------------------------------------------------------------------
print("[OK] resume_service.py loaded — PDF extraction, ATS scoring, suggestions ready")
