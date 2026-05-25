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
    "You are an expert ATS (Applicant Tracking System) analyst. "
    "Score resumes 0-100 honestly. "
    "List the top 3 most critical issues that hurt the score. "
    "List the 5-10 missing keywords/technologies commonly expected in tech resumes."
)

ATS_PROMPT = """Analyze this resume and return ONLY valid JSON (no markdown, no explanation):

{{
  "score": <0-100 integer>,
  "critical_issues": ["<specific actionable issue 1>", "<specific actionable issue 2>", "<specific actionable issue 3>"],
  "missing_keywords": ["<keyword1>", "<keyword2>", ...]
}}

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

        # Validate structure
        return {
            "score": max(0, min(100, int(parsed.get("score", 0)))),
            "critical_issues": list(parsed.get("critical_issues", []))[:3],
            "missing_keywords": list(parsed.get("missing_keywords", []))[:10],
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

SUGGESTIONS_PROMPT = """Based on this resume and the current tech market, suggest 5-7 keywords or technologies to add.

Return ONLY a JSON array (no markdown, no explanation):
["keyword1", "keyword2", ...]

Resume keywords: {resume_keywords}
User target roles: {user_roles}
Top trending keywords in tech market: {booming_keywords}

JSON:"""


async def generate_suggested_additions(
    resume_keywords: list[str],
    user_roles: list[str],
    booming_keywords: list[str],
) -> list[str]:
    """
    Generate keyword suggestions based on resume, roles, and market trends.

    Args:
        resume_keywords: Already-present keywords in resume.
        user_roles: Target job roles.
        booming_keywords: Top trending tech keywords.

    Returns:
        List of 5-7 suggested keywords to add.
    """
    import json

    prompt = SUGGESTIONS_PROMPT.format(
        resume_keywords=", ".join(resume_keywords[:50]),
        user_roles=", ".join(user_roles) if user_roles else "software engineer",
        booming_keywords=", ".join(booming_keywords[:20]),
    )

    try:
        result = await generate_with_retry(prompt, None)
        result = result.strip()
        result = re.sub(r"^```\w*\s*", "", result)
        result = re.sub(r"\s*```$", "", result)
        suggestions = json.loads(result)

        # Filter out keywords already in resume
        resume_lower = {kw.lower() for kw in resume_keywords}
        filtered = [s for s in suggestions if s.lower() not in resume_lower]
        return filtered[:7]
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to generate suggestions: {e}")
        return []


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
