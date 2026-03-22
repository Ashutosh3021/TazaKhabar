"""
Phase 2 Comprehensive Test Script
=================================
Tests every function, model field, schema, and API endpoint for Phase 2.

Run from tazakhabar-backend/:
    python Test/P2.py

Requires .env with GEMINI_API_KEY for LLM-dependent tests.
"""
import asyncio
import io
import os
import sys
import pathlib
import tempfile

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")

from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import pymupdf
from pymupdf import FileDataError  # pymupdf 1.26 raises FileDataError (RuntimeError) for invalid PDFs
from fastapi.testclient import TestClient
from sqlalchemy import select, delete, or_

from src.db.database import engine, async_session, create_all_tables
from src.db.models import News, User, Observation, Embedding, RateLimit
from src.db.schemas import (
    ObservationResponse,
    ResumeAnalyseResponse,
    ProfileResponse,
    DigestItemResponse,
)
from src.services import llm_service, resume_service, embedding_service, digest_service
from src.main import app


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
PASS = "✅"
FAIL = "❌"
SKIP = "⌚"
SEP  = "─" * 70


def banner(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def section(name: str) -> None:
    print(f"\n  ## {name}")


def check(name: str, condition: bool, detail: str = "") -> None:
    emoji = PASS if condition else FAIL
    detail_str = f"  -> {detail}" if detail else ""
    print(f"  {emoji} {name}{detail_str}")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE IMPORT TESTS
# ─────────────────────────────────────────────────────────────────────────────
banner("PHASE 2 — MODULE IMPORT TESTS")

# ── llm_service ──
section("llm_service — imports")
try:
    from src.services.llm_service import (
        get_client, get_verified_model,
        check_rate_limit, increment_rate_limit, check_and_increment,
        summarize_news_item, summarize_top_news,
        generate_observation_text, generate_with_retry,
        DAILY_LIMITS,
        SUMMARIZATION_SYSTEM, SUMMARIZATION_PROMPT,
        OBSERVATION_SYSTEM, OBSERVATION_PROMPT,
    )
    check("get_client",              callable(get_client))
    check("get_verified_model",     callable(get_verified_model))
    check("check_rate_limit",      callable(check_rate_limit))
    check("increment_rate_limit",   callable(increment_rate_limit))
    check("check_and_increment",    callable(check_and_increment))
    check("summarize_news_item",   callable(summarize_news_item))
    check("summarize_top_news",    callable(summarize_top_news))
    check("generate_observation_text", callable(generate_observation_text))
    check("generate_with_retry",    callable(generate_with_retry))
    check("DAILY_LIMITS == {anonymous:5, registered:20}",
          DAILY_LIMITS == {"anonymous": 5, "registered": 20},
          f"got {DAILY_LIMITS}")
    check("SUMMARIZATION_SYSTEM prompt set",
          len(SUMMARIZATION_SYSTEM) > 10)
    check("OBSERVATION_SYSTEM prompt set",
          len(OBSERVATION_SYSTEM) > 10)
except ImportError as e:
    check(f"llm_service import FAILED: {e}", False)

# ── resume_service ──
section("resume_service — imports")
try:
    from src.services.resume_service import (
        extract_text_from_pdf, extract_text_from_txt, extract_text,
        clean_resume_text, chunk_resume_sections,
        analyze_resume_ats, generate_suggested_additions,
        extract_keywords_from_resume, _is_pdf_magic_bytes,
    )
    check("extract_text_from_pdf",    callable(extract_text_from_pdf))
    check("extract_text_from_txt",    callable(extract_text_from_txt))
    check("extract_text",             callable(extract_text))
    check("clean_resume_text",        callable(clean_resume_text))
    check("chunk_resume_sections",    callable(chunk_resume_sections))
    check("analyze_resume_ats",      callable(analyze_resume_ats))
    check("generate_suggested_additions", callable(generate_suggested_additions))
    check("extract_keywords_from_resume", callable(extract_keywords_from_resume))
    check("_is_pdf_magic_bytes",     callable(_is_pdf_magic_bytes))
except ImportError as e:
    check(f"resume_service import FAILED: {e}", False)

# ── embedding_service ──
section("embedding_service — imports")
try:
    from src.services.embedding_service import (
        get_embedding_model, generate_text_embedding,
        generate_content_embedding, generate_user_profile_text,
        generate_user_embedding, embed_news_item,
        cosine_similarity_bytes, normalize_similarity,
    )
    check("get_embedding_model",          callable(get_embedding_model))
    check("generate_text_embedding",      callable(generate_text_embedding))
    check("generate_content_embedding",   callable(generate_content_embedding))
    check("generate_user_profile_text",  callable(generate_user_profile_text))
    check("generate_user_embedding",      callable(generate_user_embedding))
    check("embed_news_item",            callable(embed_news_item))
    check("cosine_similarity_bytes",    callable(cosine_similarity_bytes))
    check("normalize_similarity",       callable(normalize_similarity))
except ImportError as e:
    check(f"embedding_service import FAILED: {e}", False)

# ── digest_service ──
section("digest_service — imports")
try:
    from src.services.digest_service import (
        get_personalized_digest, _source_label, _infer_category,
    )
    check("get_personalized_digest", callable(get_personalized_digest))
    check("_source_label",           callable(_source_label))
    check("_infer_category",         callable(_infer_category))
except ImportError as e:
    check(f"digest_service import FAILED: {e}", False)


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA TESTS
# ─────────────────────────────────────────────────────────────────────────────
banner("PHASE 2 — SCHEMA TESTS")

section("ObservationResponse")
try:
    r = ObservationResponse(text="AI jobs surge", generated_at="2026-03-21T00:00:00", fallback=False)
    check("fields: text, generated_at, fallback",
          all(hasattr(r, f) for f in ["text", "generated_at", "fallback"]))
    check("text == 'AI jobs surge'", r.text == "AI jobs surge")
    check("fallback == False",        r.fallback is False)
except Exception as e:
    check(f"ObservationResponse: {e}", False)

section("ResumeAnalyseResponse")
try:
    r = ResumeAnalyseResponse(
        ats_score=75,
        critical_issues=["No metrics", "Weak summary"],
        missing_keywords=["React", "TypeScript"],
        suggested_additions=["Kubernetes"],
        resume_text_length=5000,
    )
    check("ats_score == 75",           r.ats_score == 75)
    check("critical_issues list len",  len(r.critical_issues) == 2)
    check("missing_keywords includes React", "React" in r.missing_keywords)
    check("suggested_additions includes K8s", "Kubernetes" in r.suggested_additions)
    check("resume_text_length == 5000", r.resume_text_length == 5000)
except Exception as e:
    check(f"ResumeAnalyseResponse: {e}", False)

section("ProfileResponse")
try:
    r = ProfileResponse(
        id="u1", name="Ash", email="ash@test.com",
        roles=["Frontend Dev", "React"], experience_level="II",
        ats_score=82, ats_critical_issues=["No cover letter"],
        ats_missing_keywords=["GraphQL"], ats_suggested_additions=["Next.js"],
        last_analysis_at="2026-03-21T10:00:00",
        resume_text_length=3000, preferences={"remote": True},
    )
    check("id, name, email",      r.id == "u1" and r.name == "Ash")
    check("roles list len=2",     len(r.roles) == 2)
    check("ats_score == 82",     r.ats_score == 82)
    check("ats_critical_issues", len(r.ats_critical_issues) == 1)
    check("preferences remote=True", r.preferences.get("remote") is True)
except Exception as e:
    check(f"ProfileResponse: {e}", False)

section("DigestItemResponse")
try:
    r = DigestItemResponse(
        id="n1", headline="AI Jobs Surge", source="Ask HN",
        summary="AI postings up 40%...", category="HIRING",
        readTime="5 min read", score=150,
        match_percentage=87, featured=True,
    )
    check("all digest fields present",
          all(hasattr(r, f) for f in [
              "id", "headline", "source", "summary", "category",
              "readTime", "score", "match_percentage", "featured"
          ]))
    check("featured == True",        r.featured is True)
    check("match_percentage == 87", r.match_percentage == 87)
    check("category == HIRING",     r.category == "HIRING")
except Exception as e:
    check(f"DigestItemResponse: {e}", False)


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────
banner("PHASE 2 — DATABASE MODEL TESTS")

async def _test_models():
    await create_all_tables()
    async with async_session() as s:

        section("News — Phase 2 fields")
        cols = [c.name for c in News.__table__.columns]
        check("summarized field",    "summarized"    in cols, str(cols))
        check("summarized_at field", "summarized_at" in cols, str(cols))
        check("summary field",      "summary"       in cols, str(cols))

        section("User — ATS fields")
        cols = [c.name for c in User.__table__.columns]
        check("resume_text field",           "resume_text"           in cols)
        check("ats_score field",             "ats_score"             in cols)
        check("ats_critical_issues field",  "ats_critical_issues"  in cols)
        check("ats_missing_keywords field",  "ats_missing_keywords"  in cols)
        check("ats_suggested_additions",    "ats_suggested_additions" in cols)
        check("last_analysis_at field",     "last_analysis_at"      in cols)

        section("Observation model")
        cols = [c.name for c in Observation.__table__.columns]
        check("id field",           "id"           in cols)
        check("week_start field",   "week_start"   in cols)
        check("text field",         "text"         in cols)
        check("generated_at field", "generated_at" in cols)

        section("Embedding model (Phase 1+2)")
        cols = [c.name for c in Embedding.__table__.columns]
        check("item_id field",     "item_id"     in cols)
        check("item_type field",   "item_type"   in cols)
        check("embedding field",   "embedding"   in cols)

asyncio.run(_test_models())


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDING SERVICE — UNIT TESTS (no DB, no LLM)
# ─────────────────────────────────────────────────────────────────────────────
banner("PHASE 2 — EMBEDDING SERVICE UNIT TESTS")

section("get_embedding_model() — singleton load")
try:
    m = embedding_service.get_embedding_model()
    check("Returns SentenceTransformer", "SentenceTransformer" in type(m).__name__)
except Exception as e:
    check(f"get_embedding_model: {e}", False)

section("generate_text_embedding — size + roundtrip")
try:
    emb1 = embedding_service.generate_text_embedding("machine learning engineer")
    emb2 = embedding_service.generate_text_embedding("frontend react developer")
    emb3 = embedding_service.generate_text_embedding("machine learning engineer")
    check("Returns bytes",             isinstance(emb1, bytes))
    check("Size = 1536 bytes (384×4)", len(emb1) == 1536, f"got {len(emb1)}")
    check("Same text -> same bytes",    emb1 == emb3)
    sim_self = embedding_service.cosine_similarity_bytes(emb1, emb1)
    check(f"Self-similarity ≈ 1.0: {sim_self:.4f}", sim_self > 0.99 and sim_self <= 1.0)
    sim_cross = embedding_service.cosine_similarity_bytes(emb1, emb2)
    check(f"Cross-similarity < 1.0: {sim_cross:.4f}", 0.0 <= sim_cross < 1.0)
except Exception as e:
    check(f"Embedding generation: {e}", False)

section("normalize_similarity")
try:
    check("normalize(1.0)  = 100", embedding_service.normalize_similarity(1.0)  == 100)
    check("normalize(-1.0) =   0", embedding_service.normalize_similarity(-1.0) ==   0)
    check("normalize(0.0)  =  50", embedding_service.normalize_similarity(0.0)  ==  50)
except Exception as e:
    check(f"normalize_similarity: {e}", False)

section("generate_user_profile_text")
try:
    t = embedding_service.generate_user_profile_text(
        ["React", "TypeScript"], "II",
        "5 years frontend experience with React and Next.js",
        {"remote": True},
    )
    check("Contains roles",    "React" in t and "TypeScript" in t)
    check("Contains level",   "II" in t)
    check("Contains background", "Background:" in t)
    check("Contains prefs",    "Preferences:" in t)

    t2 = embedding_service.generate_user_profile_text([], "I", None, None)
    check("Empty roles -> default", "software engineer" in t2.lower())
except Exception as e:
    check(f"generate_user_profile_text: {e}", False)

section("generate_content_embedding")
try:
    emb = embedding_service.generate_content_embedding("news", "n123", "AI Jobs Surge 2026")
    check("Returns bytes",    isinstance(emb, bytes))
    check("Size = 1536",     len(emb) == 1536)
except Exception as e:
    check(f"generate_content_embedding: {e}", False)


# ─────────────────────────────────────────────────────────────────────────────
# RESUME SERVICE — UNIT TESTS (no DB, no LLM)
# ─────────────────────────────────────────────────────────────────────────────
banner("PHASE 2 — RESUME SERVICE UNIT TESTS")

section("_is_pdf_magic_bytes")
try:
    from src.services.resume_service import _is_pdf_magic_bytes
    check("Detects %PDF magic",    _is_pdf_magic_bytes(b"%PDF-1.4"))
    check("Rejects GIF",          not _is_pdf_magic_bytes(b"GIF89a"))
    check("Rejects plain text",   not _is_pdf_magic_bytes(b"Hello world"))
except Exception as e:
    check(f"_is_pdf_magic_bytes: {e}", False)

section("clean_resume_text")
try:
    dirty = (
        "John Doe\n"
        "Page 1 of 3\n"
        "john@example.com\n"
        "123-456-7890\n"
        "Contact:\n"
        "Email: jane@test.com\n"
        "___________________\n"
        "Experience\n"
        "5 years Python development\n"
    )
    cleaned = resume_service.clean_resume_text(dirty)
    check("Removes email addresses",  "@" not in cleaned)
    check("Removes phone numbers",    "123-456" not in cleaned)
    check("Removes page markers",     "Page 1 of 3" not in cleaned)
    check("Keeps experience text",   "Experience" in cleaned)
    check("Returns stripped",        cleaned == cleaned.strip())
except Exception as e:
    check(f"clean_resume_text: {e}", False)

section("chunk_resume_sections")
try:
    sample = (
        "John Doe\n"
        "Experience\n"
        "Senior Engineer at Acme\n"
        "Education\n"
        "BS CS at MIT\n"
        "Skills\n"
        "Python, React, SQL\n"
        "Projects\n"
        "Open source contributor\n"
    )
    chunks = resume_service.chunk_resume_sections(sample)
    check("Returns dict",         isinstance(chunks, dict))
    check("Has experience",      "experience" in chunks)
    check("Has education",       "education"  in chunks)
    check("Has skills",          "skills"      in chunks)
    check("Has projects",        "projects"    in chunks)
    check("All values are str",  all(isinstance(v, str) for v in chunks.values()))
except Exception as e:
    check(f"chunk_resume_sections: {e}", False)

section("extract_text_from_txt")
try:
    result = asyncio.run(resume_service.extract_text_from_txt(
        b"John Doe\nSoftware Engineer\nPython, React, TypeScript"
    ))
    check("Extracts text",    "John Doe" in result)
    check("Emails removed",  "@" not in result)
except Exception as e:
    check(f"extract_text_from_txt: {e}", False)

section("extract_text — format routing")
try:
    # .txt
    t = asyncio.run(resume_service.extract_text(b"Simple resume text here", "resume.txt"))
    check("Routes .txt",           "Simple resume" in t)

    # magic bytes (unknown ext but %PDF header — too short to parse, expect error)
    try:
        asyncio.run(resume_service.extract_text(b"%PDF-1.4 short", "unknown_ext"))
        check("Routes by magic bytes (too short -> error)", False, "Expected error for truncated PDF")
    except FileDataError:
        check("Routes by magic bytes (too short -> FileDataError)", True)
    except ValueError:
        check("Routes by magic bytes (too short -> ValueError)", True)

    # Unsupported format
    try:
        asyncio.run(resume_service.extract_text(b"hello", "resume.docx"))
        check("Rejects .docx", False)
    except ValueError as ve:
        check("Rejects .docx -> ValueError", True, str(ve)[:60])
except Exception as e:
    check(f"extract_text routing: {e}", False)

section("extract_text_from_pdf — encrypted PDF")
try:
    doc = pymupdf.open()
    doc.new_page()  # blank doc must have ≥1 page to save
    tmp = pathlib.Path(tempfile.gettempdir()) / "test_enc.pdf"
    doc.save(str(tmp), encryption=pymupdf.PDF_ENCRYPT_AES_128, owner_pw="owner", user_pw="user")
    doc.close()
    with open(tmp, "rb") as fh:
        encrypted_bytes = fh.read()
    tmp.unlink()
    try:
        asyncio.run(resume_service.extract_text_from_pdf(encrypted_bytes))
        check("Raises ValueError for encrypted PDF", False)
    except ValueError as ve:
        check("Encrypted PDF → ValueError", True, str(ve)[:60])
except Exception as e:
    check(f"Encrypted PDF test: {e}", False)


# ─────────────────────────────────────────────────────────────────────────────
# LLM SERVICE — RATE LIMIT TESTS (DB)
# ─────────────────────────────────────────────────────────────────────────────
banner("PHASE 2 — LLM SERVICE RATE LIMIT TESTS")

TEST_USER  = "rate-limit-test-user"
TEST_ANON  = None  # anonymous


async def _test_rl():
    # Bug 4 fix: clean up stale RateLimit rows before testing to avoid DB pollution
    # from previous test runs that may have saturated anonymous or test-user limits.
    async with async_session() as s:
        await s.execute(
            delete(RateLimit).where(
                or_(
                    RateLimit.user_id.is_(None),
                    RateLimit.user_id == "fresh-user-xyz",
                    RateLimit.user_id == "atomic-test-xyz",
                    RateLimit.user_id == TEST_USER,
                )
            )
        )
        await s.commit()

    section("check_rate_limit — first request (no record)")
    try:
        allowed, retry_after = await llm_service.check_rate_limit("fresh-user-xyz")
        check("New user allowed",           allowed is True)
        check("retry_after == 0",            retry_after == 0)
        allowed2, _ = await llm_service.check_rate_limit(None)
        check("New anonymous allowed",      allowed2 is True)
    except Exception as e:
        check(f"check_rate_limit (new): {e}", False)

    section("check_rate_limit — anonymous limit (5/day)")
    try:
        for _ in range(5):
            await llm_service.increment_rate_limit(None)
        allowed, retry_after = await llm_service.check_rate_limit(None)
        check("6th anonymous request BLOCKED", allowed is False)
        check(f"retry_after > 0 (got {retry_after}s)", retry_after > 0)
    except Exception as e:
        check(f"Rate limit anonymous: {e}", False)

    section("check_and_increment — atomic")
    try:
        uid = "atomic-test-xyz"
        a1, _ = await llm_service.check_and_increment(uid)
        a2, _ = await llm_service.check_and_increment(uid)
        check("1st call allowed", a1 is True)
        check("2nd call also allowed (2/20)", a2 is True)
    except Exception as e:
        check(f"check_and_increment: {e}", False)

asyncio.run(_test_rl())


# ─────────────────────────────────────────────────────────────────────────────
# LLM SERVICE — GEMINI TESTS (requires GEMINI_API_KEY)
# ─────────────────────────────────────────────────────────────────────────────
banner("PHASE 2 — GEMINI / LLM CALLS")

section("GEMINI_API_KEY — check")
try:
    from src.config import settings
    has_key = bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) > 10)
    check("GEMINI_API_KEY in .env", has_key,
          f"length={len(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else 0}")
    if not has_key:
        print(f"  ⌚ LLM tests SKIPPED - set GEMINI_API_KEY in .env")
except Exception as e:
    check(f"GEMINI_API_KEY check: {e}", False)
    print(f"  ⌚ LLM tests SKIPPED - {e}")

# Only run LLM tests if key is available
_lLM_KEY_AVAILABLE = False
try:
    from src.config import settings
    _lLM_KEY_AVAILABLE = bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) > 10)
except Exception:
    pass

if _lLM_KEY_AVAILABLE:

    section("get_client() — singleton")
    try:
        c = llm_service.get_client()
        check("Returns Client instance", "Client" in type(c).__name__)
        check("Has models.generate_content", hasattr(c.models, "generate_content"))
    except Exception as e:
        check(f"get_client: {e}", False)

    section("get_verified_model() — model detection")
    try:
        model = llm_service.get_verified_model()
        valid = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]
        check(f"Detected: {model}", model in valid)
    except Exception as e:
        check(f"get_verified_model: {e}", False)

    section("generate_observation_text — real API call")
    try:
        obs = asyncio.run(llm_service.generate_observation_text(
            booming_keywords=["AI", "machine learning", "LLM", "Python"],
            declining_keywords=["COBOL", "Flash"],
        ))
        check("Returns non-empty",       len(obs) > 10)
        check("Returns trimmed string",  obs == obs.strip())
        check("Is a paragraph (long)",   len(obs) > 50)
    except Exception as e:
        check(f"generate_observation_text: {e}", False)

    section("generate_with_retry — general Gemini call")
    try:
        result = asyncio.run(llm_service.generate_with_retry(
            prompt="Say exactly: Phase 2 Gemini test OK",
            system_instruction="You are a test assistant.",
        ))
        check("Returns non-empty",     len(result) > 0)
        check("Contains expected text", "Phase 2 Gemini test OK" in result)
    except Exception as e:
        check(f"generate_with_retry: {e}", False)

    section("analyze_resume_ats — real API call")
    try:
        resume = (
            "John Doe\n"
            "Experience: 5 years Python, 2 years React\n"
            "Education: BS Computer Science\n"
            "Skills: Python, React, JavaScript, SQL, Git\n"
        )
        result = asyncio.run(resume_service.analyze_resume_ats(resume))
        check("Returns dict",           isinstance(result, dict))
        check("Has 'score' key",      "score" in result)
        check("Has 'critical_issues'", "critical_issues" in result)
        check("Has 'missing_keywords'", "missing_keywords" in result)
        score = result.get("score", -1)
        check(f"score in 0-100: {score}", 0 <= score <= 100)
        check("critical_issues is list", isinstance(result.get("critical_issues"), list))
        check("missing_keywords is list", isinstance(result.get("missing_keywords"), list))
    except Exception as e:
        check(f"analyze_resume_ats: {e}", False)

    section("generate_suggested_additions — real API call")
    try:
        result = asyncio.run(resume_service.generate_suggested_additions(
            resume_keywords=["Python", "React"],
            user_roles=["Frontend Dev"],
            booming_keywords=["AI", "TypeScript", "Rust", "WebAssembly", "Go"],
        ))
        check("Returns list",           isinstance(result, list))
        check("Max 7 items",            len(result) <= 7)
        check("Filters present keywords", "Python" not in result and "React" not in result)
    except Exception as e:
        check(f"generate_suggested_additions: {e}", False)

    section("extract_keywords_from_resume — keyword matching")
    try:
        text = "I have 5 years experience with Python, React, TypeScript and SQL databases"
        keywords = asyncio.run(resume_service.extract_keywords_from_resume(text))
        check("Returns list",      isinstance(keywords, list))
        check("Finds python",     "python" in keywords)
        check("Finds react",      "react" in keywords)
        check("Finds typescript", "typescript" in keywords)
        check("No absent rust",   "rust" not in keywords)
    except Exception as e:
        check(f"extract_keywords_from_resume: {e}", False)

else:
    section("LLM API tests")
    print(f"  ⌚ SKIPPED — GEMINI_API_KEY not set in .env")


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE WRITE/READ TESTS
# ─────────────────────────────────────────────────────────────────────────────
banner("PHASE 2 — DATABASE WRITE/READ TESTS")

_TUSER  = "test-p2-user"
_TNEWS  = "test-p2-news"
_EMB_USR = "emb-test-user"


async def _test_db_writes():
    # Cleanup: delete test rows from previous runs BEFORE inserting.
    # Each cleanup uses its own committed session so failures stay isolated.
    async with async_session() as s:
        await s.execute(delete(User).where(User.id == _TUSER))
        await s.commit()
    async with async_session() as s:
        await s.execute(delete(News).where(News.id == _TNEWS))
        await s.commit()
    async with async_session() as s:
        await s.execute(delete(Embedding).where(Embedding.item_id == _EMB_USR))
        await s.commit()

    # ── User with ATS fields ──
    section("User - ATS fields write/read")
    try:
        async with async_session() as s:
            user = User(
                id=_TUSER, name="Test User", email="test@test.com",
                roles=["Frontend Dev", "React"], experience_level="II",
                resume_text="Experienced frontend developer with 5 years React...",
                ats_score=75,
                ats_critical_issues=["Weak bullets", "No metrics"],
                ats_missing_keywords=["TypeScript", "GraphQL"],
                ats_suggested_additions=["Next.js", "Tailwind"],
                last_analysis_at=datetime.utcnow(),
            )
            s.add(user)
            await s.commit()

            stmt = select(User).where(User.id == _TUSER)
            result = await s.execute(stmt)
            u = result.scalar_one()
            check("ats_score saved",         u.ats_score == 75)
            check("ats_critical_issues len", len(u.ats_critical_issues) == 2)
            check("ats_missing_keywords",    "TypeScript" in u.ats_missing_keywords)
            check("ats_suggested_additions","Next.js" in u.ats_suggested_additions)
            check("resume_text saved",       "Experienced" in u.resume_text)
            check("last_analysis_at saved",  u.last_analysis_at is not None)
    except Exception as e:
        check(f"User ATS fields: {e}", False)

    # ── News with summarized fields ──
    section("News - summarized fields write/read")
    try:
        async with async_session() as s:
            news = News(
                id=_TNEWS, hn_item_id="99999", type="ask_hn",
                title="What tech skills are most in demand in 2026?",
                score=250,
                summary="AI and ML skills dominate the 2026 job market...",
                summarized=True, summarized_at=datetime.utcnow(),
                report_version="1",
            )
            s.add(news)
            await s.commit()

            stmt = select(News).where(News.id == _TNEWS)
            result = await s.execute(stmt)
            n = result.scalar_one()
            check("summary saved",         "AI" in (n.summary or ""))
            check("summarized=True saved", n.summarized is True)
            check("summarized_at saved",   n.summarized_at is not None)
    except Exception as e:
        check(f"News summarized fields: {e}", False)

    # ── Observation ──
    section("Observation - write/read")
    try:
        async with async_session() as s:
            obs = Observation(
                week_start=datetime.utcnow(),
                text="Tech hiring remains strong with AI roles leading growth...",
                generated_at=datetime.utcnow(),
            )
            s.add(obs)
            await s.commit()

            stmt = select(Observation).order_by(Observation.generated_at.desc()).limit(1)
            result = await s.execute(stmt)
            o = result.scalar_one()
            check("text saved",           len(o.text) > 10)
            check("week_start saved",     o.week_start is not None)
            check("generated_at saved",   o.generated_at is not None)
    except Exception as e:
        check(f"Observation write/read: {e}", False)

    # ── Embedding BLOB roundtrip ──
    section("Embedding - BLOB write/read + cosine sim")
    try:
        emb_bytes = embedding_service.generate_text_embedding(
            "Software engineer with Python and React experience"
        )
        async with async_session() as s:
            emb = Embedding(
                item_id=_EMB_USR, item_type="user_profile", embedding=emb_bytes,
            )
            s.add(emb)
            await s.commit()

            stmt = select(Embedding).where(
                Embedding.item_id == _EMB_USR,
                Embedding.item_type == "user_profile",
            )
            result = await s.execute(stmt)
            stored = result.scalar_one()
            check("BLOB stored and retrieved", stored.embedding == emb_bytes)
            sim = embedding_service.cosine_similarity_bytes(stored.embedding, emb_bytes)
            check(f"Cosine sim on stored BLOB: {sim:.4f}", sim > 0.99)
    except Exception as e:
        check(f"Embedding BLOB roundtrip: {e}", False)

asyncio.run(_test_db_writes())


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINT TESTS
# ─────────────────────────────────────────────────────────────────────────────
banner("PHASE 2 — API ENDPOINT TESTS")

tc = TestClient(app)


section("GET /api/observation — returns data")
try:
    r = tc.get("/api/observation")
    check("Status 200",             r.status_code == 200)
    d = r.json()
    check("Has 'text' field",       "text"        in d)
    check("Has 'generated_at'",     "generated_at" in d)
    check("Has 'fallback'",         "fallback"     in d)
    check("fallback=False (has data)", d.get("fallback") is False)
except Exception as e:
    check(f"/api/observation: {e}", False)


section("GET /api/profile — no X-User-ID")
try:
    r = tc.get("/api/profile")
    check("Status 200",             r.status_code == 200)
    d = r.json()
    check("Returns empty profile", d.get("id") is None)
except Exception as e:
    check(f"/api/profile GET (empty): {e}", False)


section("GET /api/profile — with test user")
try:
    r = tc.get("/api/profile", headers={"X-User-ID": _TUSER})
    check("Status 200",            r.status_code == 200)
    d = r.json()
    check(f"id == {_TUSER}",       d.get("id") == _TUSER)
    check(f"ats_score={d.get('ats_score')}", d.get("ats_score") == 75)
    check("critical_issues len=2",  len(d.get("ats_critical_issues", [])) == 2)
    check("roles include React",    "React" in d.get("roles", []))
except Exception as e:
    check(f"/api/profile GET (with user): {e}", False)


section("POST /api/profile — create/update")
try:
    payload = {
        "name": "Updated Name",
        "email": "updated@test.com",
        "roles": ["Backend Dev", "Python"],
        "experience_level": "III",
    }
    r = tc.post("/api/profile", json=payload,
                headers={"X-User-ID": "update-test-p2"})
    check("Status 200",            r.status_code == 200)
    d = r.json()
    check("Name updated",         d.get("name") == "Updated Name")
    check("Roles updated",         "Backend Dev" in d.get("roles"))
    check("Level updated to III",  d.get("experience_level") == "III")
except Exception as e:
    check(f"/api/profile POST: {e}", False)


section("POST /api/profile — requires X-User-ID")
try:
    r = tc.post("/api/profile", json={"name": "No Header Test"})
    check("Status 400 without header", r.status_code == 400)
except Exception as e:
    check(f"/api/profile POST (no header): {e}", False)


section("POST /api/resume/analyse — TXT file (real LLM)")
try:
    files = {
        "file": (
            "resume.txt",
            b"John Doe\nSoftware Engineer\nPython, React, SQL\n5 years experience\nBS Computer Science",
            "text/plain",
        )
    }
    r = tc.post("/api/resume/analyse", files=files,
                headers={"X-User-ID": "resume-test-user-p2"})
    check(f"Status {r.status_code}", r.status_code == 200)
    if r.status_code == 200:
        d = r.json()
        check("Has ats_score",          "ats_score"          in d)
        check("Has critical_issues",    "critical_issues"    in d)
        check("Has missing_keywords",   "missing_keywords"   in d)
        check("Has suggested_additions","suggested_additions" in d)
        check("Has resume_text_length", "resume_text_length" in d)
        score = d.get("ats_score", -1)
        check(f"score in 0-100: {score}", 0 <= score <= 100)
    else:
        check("Upload failed", False, f"status: {r.status_code}")
except Exception as e:
    check(f"/api/resume/analyse TXT: {e}", False)


section("POST /api/resume/analyse — 429 on rate limit")
try:
    async def _saturate():
        today = datetime.utcnow().strftime("%Y-%m-%d")
        async with async_session() as s:
            # Delete all existing anonymous rows for today first to avoid duplicate-key errors
            await s.execute(
                delete(RateLimit).where(
                    RateLimit.user_id.is_(None),
                    RateLimit.date == today,
                )
            )
            await s.commit()
            # Insert exactly ONE row with count well above the 5/5 anonymous limit
            s.add(RateLimit(
                user_id=None,
                date=today,
                request_count=50,
                last_request_at=datetime.utcnow(),
            ))
            await s.commit()
    asyncio.run(_saturate())

    files = {"file": ("r.txt", b"Short resume text here for testing", "text/plain")}
    r = tc.post("/api/resume/analyse", files=files)
    check("429 on rate limit exceeded", r.status_code == 429)
    check("Retry-After header present",
          "retry-after" in {h.lower() for h in r.headers})
except Exception as e:
    check(f"/api/resume/analyse rate limit: {e}", False)


section("POST /api/resume/analyse — 400 on bad content type")
try:
    files = {"file": ("r.docx", b"fake docx", "application/msword")}
    r = tc.post("/api/resume/analyse", files=files,
                headers={"X-User-ID": "resume-test-user-p2"})
    check("400 on .docx", r.status_code == 400)
except Exception as e:
    check(f"/api/resume/analyse bad type: {e}", False)


section("POST /api/resume/analyse — 400 on empty file")
try:
    files = {"file": ("empty.txt", b"", "text/plain")}
    r = tc.post("/api/resume/analyse", files=files,
                headers={"X-User-ID": "resume-test-user-p2"})
    check("400 on empty file", r.status_code == 400)
except Exception as e:
    check(f"/api/resume/analyse empty: {e}", False)


section("POST /api/resume/analyse — 422 on short text (<50 chars)")
try:
    files = {"file": ("short.txt", b"Hi", "text/plain")}
    r = tc.post("/api/resume/analyse", files=files,
                headers={"X-User-ID": "resume-test-user-p2"})
    check("422 on <50 char text", r.status_code == 422)
except Exception as e:
    check(f"/api/resume/analyse short: {e}", False)


section("GET /api/digest — anonymous default")
try:
    r = tc.get("/api/digest")
    check("Status 200",                 r.status_code == 200)
    d = r.json()
    check("Has 'data' key",             "data" in d)
    check("Has 'meta' key",             "meta" in d)
    check("meta.total exists",          "total" in d["meta"])
    check("meta.skip=0",                d["meta"].get("skip") == 0)
    check("meta.limit=5",               d["meta"].get("limit") == 5)
    check("meta.has_more exists",        "has_more" in d["meta"])
except Exception as e:
    check(f"/api/digest GET: {e}", False)


section("GET /api/digest — pagination params")
try:
    r = tc.get("/api/digest?skip=0&limit=5")
    check("Status 200 with params",     r.status_code == 200)
    d = r.json()
    check("data is list",             isinstance(d.get("data"), list))
    check("limit respected (≤20)",     0 < d["meta"].get("limit", 0) <= 20)
except Exception as e:
    check(f"/api/digest pagination: {e}", False)


section("GET /api/digest — limit > 20 → 422")
try:
    r = tc.get("/api/digest?limit=100")
    check("422 on limit > 20", r.status_code == 422)
except Exception as e:
    check(f"/api/digest limit validation: {e}", False)


section("GET /api/digest — personalized with X-User-ID")
try:
    r = tc.get("/api/digest?skip=0&limit=5", headers={"X-User-ID": _TUSER})
    check("Status 200",            r.status_code == 200)
    items = r.json().get("data", [])
    if items:
        item = items[0]
        check("Item has match_percentage", "match_percentage" in item)
        check("Item has featured flag",    "featured" in item)
        check("Item has headline",         "headline" in item)
    else:
        check("Items returned (may be empty if no summarized news)", True)
except Exception as e:
    check(f"/api/digest personalized: {e}", False)


# ─────────────────────────────────────────────────────────────────────────────
# ALL ROUTES REGISTERED
# ─────────────────────────────────────────────────────────────────────────────
banner("PHASE 2 — ROUTER REGISTRATION")

all_paths = {r.path for r in app.routes}
expected = {
    "/api/jobs", "/api/news", "/api/trends", "/api/badge",
    "/api/refresh", "/health",
    "/api/observation", "/api/resume/analyse",
    "/api/profile", "/api/digest",
}
missing = expected - all_paths
check("All Phase 2 routes registered",
      len(missing) == 0,
      f"Missing: {missing}" if missing else "All 10 routes found ✅")


# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
banner("PHASE 2 — TEST COMPLETE")
print(f"\n  Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  Working dir: {BACKEND_DIR}")
print(f"  GEMINI_KEY : {'SET - LLM tests ran' if _lLM_KEY_AVAILABLE else 'NOT SET - LLM tests skipped ⌚'}")
print(SEP)
print(f"  Review ✅ = pass, ❌ = fail, ⌚ = skipped")
print(SEP)
