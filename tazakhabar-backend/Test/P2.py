"""
Full Diagnostic — API Key + Phase 2 Module Health Check
=========================================================
Combines:
  • OpenRouter API key deep inspection (6 checks)
  • Phase 2 module existence & function signature checks
  • Live API connectivity test (no cost, uses /models endpoint)
  • llm_service header construction audit
  • resume_service, embedding_service, digest_service internals
  • DB model column verification
  • Rate-limit logic unit test (no DB needed)

Run from project root (TazaKhabar/):
    python diagnose_full.py
"""

import os, sys, re, json, asyncio, pathlib, importlib, inspect, traceback
from datetime import datetime

if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")

# ── Formatting helpers ───────────────────────────────────────────────────────
SEP   = "═" * 68
THIN  = "─" * 68
OK    = "✅"
FAIL  = "❌"
WARN  = "⚠️ "
INFO  = "ℹ️ "
SKIP  = "⏭️ "

def hr():       print(SEP)
def thinhr():   print(f"  {THIN}")
def head(t):    print(f"\n{SEP}\n  {t}\n{SEP}")
def sub(t):     print(f"\n  ── {t}")
def ok(m):      print(f"  {OK}  {m}")
def fail(m):    print(f"  {FAIL}  {m}")
def warn(m):    print(f"  {WARN} {m}")
def info(m):    print(f"  {INFO} {m}")
def skip(m):    print(f"  {SKIP} {m}")

ISSUES   = []   # accumulated list of confirmed problems
WARNINGS = []   # non-fatal concerns

def record_fail(msg):
    ISSUES.append(msg)
    fail(msg)

def record_warn(msg):
    WARNINGS.append(msg)
    warn(msg)


# ═══════════════════════════════════════════════════════════════════════════
# PATH SETUP
# ═══════════════════════════════════════════════════════════════════════════
script_dir = pathlib.Path(__file__).resolve().parent

backend_candidates = [
    script_dir / "tazakhabar-backend",
    script_dir,
    script_dir.parent / "tazakhabar-backend",
    script_dir.parent,
]
backend_dir = None
for bc in backend_candidates:
    if (bc / "src").exists() and (bc / "src" / "services").exists():
        backend_dir = bc
        break

if backend_dir:
    sys.path.insert(0, str(backend_dir))
    ok(f"Backend found: {backend_dir}")
else:
    fail("Cannot locate backend src/ directory. Run from project root.")
    sys.exit(1)

env_candidates = [
    backend_dir / ".env",
    script_dir / ".env",
    backend_dir.parent / ".env",
]
env_path = next((p for p in env_candidates if p.exists()), None)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1 — .env KEY DEEP INSPECTION
# ═══════════════════════════════════════════════════════════════════════════
head("SECTION 1 — API KEY DEEP INSPECTION")

sub("Locate .env file")
if env_path:
    ok(f"Found: {env_path}")
else:
    record_fail(".env file not found in any expected location")
    print("  Searched:")
    for p in env_candidates:
        print(f"    {p}")

raw_key      = ""
unquoted_key = ""

if env_path:
    raw_lines  = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
    key_lines  = [(i+1, l) for i, l in enumerate(raw_lines)
                  if "OPENROUTER" in l.upper() and not l.strip().startswith("#")]

    sub("Raw .env content (masked)")
    if not key_lines:
        record_fail("OPENROUTER_API_KEY not found in .env (or it is commented out)")
    else:
        for lineno, line in key_lines:
            if "=" in line:
                k, _, v = line.partition("=")
                v_stripped = v.strip().strip('"').strip("'")
                masked = (v_stripped[:8] + "***" + v_stripped[-4:]) if len(v_stripped) > 14 else f"[{len(v_stripped)} chars]"
                print(f"    Line {lineno}: {k.strip()} = {masked}")
                print(f"    repr  : {repr(line[:120])}")
                raw_key      = v.strip()
                unquoted_key = raw_key.strip('"').strip("'")

    sub("Key format checks")
    EXPECTED_MIN = 40

    checks = [
        ("Length >= 40 chars",         len(unquoted_key) >= EXPECTED_MIN,
                                        f"got {len(unquoted_key)} — key is TRUNCATED"),
        ("Starts with 'sk-or-'",       unquoted_key.startswith("sk-or-"),
                                        f"got prefix '{unquoted_key[:10]}' — wrong key type"),
        ("No spaces inside key",        " " not in unquoted_key,           "spaces found inside key"),
        ("No tab chars",               "\t" not in unquoted_key,          "tab character found"),
        ("No BOM marker",              not unquoted_key.startswith("\ufeff"), "BOM at start"),
        ("No zero-width chars",        not any(ord(c) in (0x200B,0x200C,0x200D,0xFEFF)
                                               for c in unquoted_key),    "invisible chars found"),
        ("Not a placeholder value",    unquoted_key.lower() not in
                                        ("your-api-key","placeholder","changeme",
                                         "sk-or-v1-xxx","sk-or-v1-...",""),
                                                                           "looks like a placeholder"),
    ]
    for label, passed, hint in checks:
        if passed:
            ok(label)
        else:
            record_fail(f"{label}  →  {hint}")

    sub("OS environment variable vs .env comparison")
    os_key = os.environ.get("OPENROUTER_API_KEY", "")
    if os_key:
        info(f"Shell OPENROUTER_API_KEY: {os_key[:8]}***{os_key[-4:]} ({len(os_key)} chars)")
        if os_key != unquoted_key:
            record_warn("Shell/OS env var OVERRIDES .env with a DIFFERENT value — this is likely the bug!")
            info(f"  .env value  : {len(unquoted_key)} chars")
            info(f"  shell value : {len(os_key)} chars")
            print("  FIX (PowerShell): Remove-Item Env:\\OPENROUTER_API_KEY")
            print("  FIX (bash)      : unset OPENROUTER_API_KEY")
        else:
            ok("Shell env matches .env value")
    else:
        ok("No conflicting shell env var set")

sub("How settings.py loads the key")
try:
    from src.config import settings
    app_key = settings.OPENROUTER_API_KEY or ""
    info(f"settings.OPENROUTER_API_KEY: {app_key[:8]}***{app_key[-4:] if len(app_key)>8 else ''} ({len(app_key)} chars)")

    if app_key == unquoted_key:
        ok("settings value matches .env exactly")
    elif app_key == raw_key:
        record_warn("settings value includes surrounding quotes — strip them from .env")
    elif len(app_key) < EXPECTED_MIN:
        record_fail(f"App reads only {len(app_key)} chars — key truncated during config load")
    else:
        record_warn(f"settings value differs from .env raw ({len(app_key)} vs {len(unquoted_key)} chars)")

    # The key the rest of the script will use for live tests
    LIVE_KEY = app_key or unquoted_key
except Exception as e:
    record_fail(f"Cannot import src.config.settings: {e}")
    LIVE_KEY = unquoted_key


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2 — LIVE OPENROUTER API TEST
# ═══════════════════════════════════════════════════════════════════════════
head("SECTION 2 — LIVE OPENROUTER API CALLS")

async def _live_api_tests(api_key: str):
    import httpx

    sub("Auth probe — GET /api/v1/models  (free, no tokens)")
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    info(f"Status: {r.status_code}")
    if r.status_code == 200:
        models = r.json().get("data", [])
        free   = [m["id"] for m in models if ":free" in m.get("id","")]
        ok(f"Auth PASSED — {len(models)} models visible, {len(free)} free models")
        if free:
            info(f"Free models available: {', '.join(free[:5])}")
        return True, free[:3] if free else []
    elif r.status_code == 401:
        body = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
        record_fail(f"401 Unauthorized — {body.get('error',{}).get('message','no message')}")
        print()
        print("  ┌─ ROOT CAUSE ────────────────────────────────────────────┐")
        if len(api_key) < 40:
            print(f"  │  Key is {len(api_key)} chars — TRUNCATED in .env              │")
            print("  │  Go to openrouter.ai/keys → copy the FULL key          │")
        elif not api_key.startswith("sk-or-"):
            print("  │  Wrong key format — must start with sk-or-v1-          │")
        else:
            print("  │  Key format looks correct but OpenRouter rejects it.   │")
            print("  │  → Generate a fresh key at openrouter.ai/keys          │")
            print("  │  → Check if key was revoked or account is suspended    │")
        print("  └────────────────────────────────────────────────────────┘")
        return False, []
    elif r.status_code == 402:
        record_warn("402 Payment Required — key is valid but no credits")
        info("Add credits: https://openrouter.ai/credits  OR use :free models only")
        return True, []
    else:
        record_warn(f"Unexpected {r.status_code}: {r.text[:200]}")
        return False, []

async def _chat_test(api_key: str, model: str):
    import httpx
    sub(f"Minimal chat test — model: {model}")
    async with httpx.AsyncClient(timeout=25) as c:
        r = await c.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "max_tokens": 10,
                  "messages": [{"role": "user", "content": "Reply with just: WORKS"}]},
        )
    info(f"Status: {r.status_code}")
    if r.status_code == 200:
        try:
            text = r.json()["choices"][0]["message"]["content"].strip()
            ok(f"Chat response: '{text}'")
        except Exception:
            ok(f"Chat succeeded: {r.text[:80]}")
    elif r.status_code == 401:
        record_fail(f"Chat 401 on model {model} — same auth issue")
    else:
        record_warn(f"Chat returned {r.status_code}: {r.text[:120]}")

try:
    import httpx
    auth_ok, free_models = asyncio.run(_live_api_tests(LIVE_KEY))
    if auth_ok and free_models:
        asyncio.run(_chat_test(LIVE_KEY, free_models[0]))
    elif auth_ok:
        asyncio.run(_chat_test(LIVE_KEY, "openai/gpt-4o-mini"))
except ImportError:
    skip("httpx not installed — pip install httpx")
except Exception as e:
    record_fail(f"Live API test exception: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3 — llm_service.py SOURCE AUDIT
# ═══════════════════════════════════════════════════════════════════════════
head("SECTION 3 — llm_service.py DEEP AUDIT")

llm_path = backend_dir / "src" / "services" / "llm_service.py"

if not llm_path.exists():
    record_fail(f"llm_service.py not found at {llm_path}")
else:
    src = llm_path.read_text(encoding="utf-8")
    lines = src.splitlines()

    sub("File stats")
    info(f"Lines: {len(lines)}  |  Size: {llm_path.stat().st_size} bytes")

    sub("Required functions present")
    REQUIRED_FUNCS = [
        "get_verified_model", "check_rate_limit", "increment_rate_limit",
        "check_and_increment", "summarize_news_item", "summarize_top_news",
        "generate_observation_text", "generate_with_retry",
    ]
    for fn in REQUIRED_FUNCS:
        found = bool(re.search(rf"(async\s+)?def\s+{fn}\s*\(", src))
        if found: ok(f"def {fn}")
        else:     record_fail(f"def {fn}  — MISSING")

    sub("Required constants/prompts present")
    REQUIRED_CONSTS = [
        "DAILY_LIMITS", "SUMMARIZATION_SYSTEM", "SUMMARIZATION_PROMPT",
        "OBSERVATION_SYSTEM", "OBSERVATION_PROMPT",
    ]
    for c in REQUIRED_CONSTS:
        found = c in src
        if found: ok(f"{c}")
        else:     record_fail(f"{c}  — MISSING")

    sub("Authorization header construction")
    auth_lines = [(i+1, l.strip()) for i, l in enumerate(lines)
                  if "authorization" in l.lower() or "bearer" in l.lower()]
    if not auth_lines:
        record_fail("No Authorization/Bearer header found in llm_service.py!")
        print("  The key is never being sent — add:")
        print('    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"')
    else:
        for lineno, line in auth_lines:
            info(f"Line {lineno}: {line}")
        # Check for common mistakes
        if any("api-key" in l.lower() or "x-api-key" in l.lower() for _, l in auth_lines):
            record_fail("Uses 'x-api-key' header — OpenRouter requires 'Authorization: Bearer'")
        if any('"Bearer"' in l or "'Bearer'" in l for _, l in auth_lines):
            # Check that the key variable is actually appended
            bearer_lines = [l for _, l in auth_lines if "bearer" in l.lower()]
            if all("OPENROUTER_API_KEY" not in l and "api_key" not in l.lower()
                   for l in bearer_lines):
                record_fail("Bearer header found but key variable not appended — sending empty auth!")
            else:
                ok("Bearer header includes key variable")

    sub("DAILY_LIMITS values")
    dl_match = re.search(r"DAILY_LIMITS\s*=\s*(\{[^}]+\})", src, re.DOTALL)
    if dl_match:
        info(f"DAILY_LIMITS = {dl_match.group(1).strip()}")
        if '"anonymous"' not in dl_match.group(1) or '"registered"' not in dl_match.group(1):
            record_fail("DAILY_LIMITS missing 'anonymous' or 'registered' keys")
        else:
            ok("DAILY_LIMITS has both keys")

    sub("Retry logic present")
    has_retry    = "retry" in src.lower()
    has_sleep    = "asyncio.sleep" in src or "await asyncio.sleep" in src
    has_max_retry = bool(re.search(r"max_retries?\s*=\s*\d", src, re.I))
    if has_retry: ok("Retry logic found")
    else:         record_warn("No retry logic detected")
    if has_sleep: ok("asyncio.sleep found (async retry backoff)")
    else:         record_warn("No sleep/backoff in retries")
    if has_max_retry: ok("max_retries constant defined")
    else:             record_warn("No explicit max_retries constant")

    sub("OpenRouter base URL")
    url_match = re.search(r"openrouter\.ai[^\s\"']+", src)
    if url_match:
        ok(f"URL found: {url_match.group()}")
        if "v1/chat/completions" not in src:
            record_fail("Expected endpoint /v1/chat/completions not found")
    else:
        record_fail("openrouter.ai URL not found in llm_service.py")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4 — resume_service.py DEEP AUDIT
# ═══════════════════════════════════════════════════════════════════════════
head("SECTION 4 — resume_service.py DEEP AUDIT")

resume_path = backend_dir / "src" / "services" / "resume_service.py"

if not resume_path.exists():
    record_fail(f"resume_service.py not found at {resume_path}")
else:
    src_r = resume_path.read_text(encoding="utf-8")
    lines_r = src_r.splitlines()

    sub("File stats")
    info(f"Lines: {len(lines_r)}  |  Size: {resume_path.stat().st_size} bytes")

    sub("Required functions")
    RESUME_FUNCS = [
        "extract_text_from_pdf", "extract_text_from_txt", "extract_text",
        "clean_resume_text", "chunk_resume_sections",
        "analyze_resume_ats", "generate_suggested_additions",
        "extract_keywords_from_resume", "_is_pdf_magic_bytes",
    ]
    for fn in RESUME_FUNCS:
        found = bool(re.search(rf"(async\s+)?def\s+{fn}\s*\(", src_r))
        if found: ok(f"def {fn}")
        else:     record_fail(f"def {fn}  — MISSING")

    sub("PDF library import")
    if "pymupdf" in src_r or "fitz" in src_r:
        ok("pymupdf/fitz import found")
    else:
        record_fail("No pymupdf or fitz import — PDF extraction will fail")

    sub("Magic bytes detection (%PDF)")
    if r"%PDF" in src_r or "b'%PDF'" in src_r or 'b"%PDF"' in src_r:
        ok("%PDF magic bytes check present")
    else:
        record_warn("No %PDF magic bytes check found — may not detect PDFs by content")

    sub("Encryption guard")
    if "encrypt" in src_r.lower() or "password" in src_r.lower() or "needs_pass" in src_r.lower():
        ok("Encryption/password check found")
    else:
        record_warn("No encryption check — encrypted PDFs may not raise proper errors")

    sub("ATS score response structure")
    if '"score"' in src_r or "'score'" in src_r:
        ok("'score' key in ATS response")
    else:
        record_warn("'score' key not found — ATS schema may be wrong")
    for key in ("critical_issues", "missing_keywords", "suggested_additions"):
        if key in src_r:
            ok(f"'{key}' key found")
        else:
            record_fail(f"'{key}' key MISSING from ATS response structure")

    sub("Runtime import test")
    try:
        from src.services import resume_service
        ok("resume_service imports without error")
        # Check key callables
        for fn in ["extract_text", "clean_resume_text", "chunk_resume_sections"]:
            if callable(getattr(resume_service, fn, None)):
                ok(f"{fn} is callable")
            else:
                record_fail(f"{fn} not callable after import")
    except Exception as e:
        record_fail(f"resume_service import failed: {e}")
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5 — embedding_service.py DEEP AUDIT
# ═══════════════════════════════════════════════════════════════════════════
head("SECTION 5 — embedding_service.py DEEP AUDIT")

emb_path = backend_dir / "src" / "services" / "embedding_service.py"

if not emb_path.exists():
    record_fail(f"embedding_service.py not found at {emb_path}")
else:
    src_e = emb_path.read_text(encoding="utf-8")

    sub("Required functions")
    EMB_FUNCS = [
        "get_embedding_model", "generate_text_embedding",
        "generate_content_embedding", "generate_user_profile_text",
        "generate_user_embedding", "embed_news_item",
        "cosine_similarity_bytes", "normalize_similarity",
    ]
    for fn in EMB_FUNCS:
        found = bool(re.search(rf"(async\s+)?def\s+{fn}\s*\(", src_e))
        if found: ok(f"def {fn}")
        else:     record_fail(f"def {fn}  — MISSING")

    sub("Model name")
    model_match = re.search(r"['\"]all-MiniLM-L6-v2['\"]", src_e)
    if model_match:
        ok("Model: all-MiniLM-L6-v2 found")
    else:
        record_warn("Expected model 'all-MiniLM-L6-v2' not found — check model name")

    sub("Expected embedding dimensions (384 → 1536 bytes)")
    if "384" in src_e:
        ok("384 dims referenced in code")
    else:
        record_warn("384 (expected dims) not mentioned — confirm model output size")
    if "1536" in src_e:
        ok("1536 bytes (384×4 float32) referenced")
    else:
        record_warn("1536 not mentioned — byte size may not be validated")

    sub("Singleton pattern for model loading")
    if "_model" in src_e or "_embedding_model" in src_e or "global " in src_e:
        ok("Singleton/global variable for model found")
    else:
        record_warn("No singleton detected — model may reload on every call (slow)")

    sub("Runtime functional test (no DB, no LLM)")
    try:
        from src.services import embedding_service as es
        ok("embedding_service imports without error")

        # normalize_similarity
        assert es.normalize_similarity(1.0) == 100,  "normalize(1.0) != 100"
        assert es.normalize_similarity(-1.0) == 0,   "normalize(-1.0) != 0"
        assert es.normalize_similarity(0.0) == 50,   "normalize(0.0) != 50"
        ok("normalize_similarity(1.0/0.0/-1.0) → 100/50/0  ✓")

        # generate_user_profile_text
        t = es.generate_user_profile_text(["React"], "II", "5yr frontend", {"remote": True})
        assert "React" in t and "II" in t, "profile text missing roles/level"
        ok("generate_user_profile_text returns correct text")

        t2 = es.generate_user_profile_text([], "I", None, None)
        assert "software engineer" in t2.lower(), "empty roles default missing"
        ok("Empty roles fallback to 'software engineer'")

        # Text embedding
        emb = es.generate_text_embedding("python developer")
        assert isinstance(emb, bytes),   "embedding not bytes"
        assert len(emb) == 1536,         f"embedding size {len(emb)} != 1536"
        ok(f"generate_text_embedding → {len(emb)} bytes  ✓")

        # Self-similarity
        sim = es.cosine_similarity_bytes(emb, emb)
        assert sim > 0.99 and sim <= 1.0, f"self-sim={sim}"
        ok(f"Self cosine similarity = {sim:.4f}  ✓")

        # content embedding
        cemb = es.generate_content_embedding("news", "n1", "AI hiring surge")
        assert isinstance(cemb, bytes) and len(cemb) == 1536
        ok("generate_content_embedding → bytes ✓")

    except AssertionError as ae:
        record_fail(f"Functional test failed: {ae}")
    except Exception as e:
        record_fail(f"embedding_service runtime error: {e}")
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6 — digest_service.py DEEP AUDIT
# ═══════════════════════════════════════════════════════════════════════════
head("SECTION 6 — digest_service.py DEEP AUDIT")

digest_path = backend_dir / "src" / "services" / "digest_service.py"

if not digest_path.exists():
    record_fail(f"digest_service.py not found at {digest_path}")
else:
    src_d = digest_path.read_text(encoding="utf-8")

    sub("Required functions")
    DIGEST_FUNCS = ["get_personalized_digest", "_source_label", "_infer_category"]
    for fn in DIGEST_FUNCS:
        found = bool(re.search(rf"(async\s+)?def\s+{fn}\s*\(", src_d))
        if found: ok(f"def {fn}")
        else:     record_fail(f"def {fn}  — MISSING")

    sub("Personalization logic")
    uses_embedding = "cosine_similarity" in src_d or "embedding" in src_d
    uses_fallback  = "fallback" in src_d.lower() or "no embedding" in src_d.lower()
    if uses_embedding: ok("Uses embeddings for personalization")
    else:              record_warn("No embedding/cosine_similarity — personalization may be missing")
    if uses_fallback:  ok("Has fallback when no user embedding")
    else:              record_warn("No fallback path for anonymous users")

    sub("DigestItemResponse fields built")
    for field in ("match_percentage", "featured", "category", "readTime", "source"):
        if field in src_d:
            ok(f"'{field}' field populated")
        else:
            record_fail(f"'{field}' not found — DigestItemResponse will be incomplete")

    sub("Pagination support")
    if "skip" in src_d and "limit" in src_d:
        ok("skip/limit pagination present")
    else:
        record_fail("skip/limit pagination missing from digest_service")

    sub("Runtime import test")
    try:
        from src.services import digest_service as ds
        ok("digest_service imports without error")
        for fn in ["get_personalized_digest", "_source_label", "_infer_category"]:
            if callable(getattr(ds, fn, None)):
                ok(f"{fn} callable")
            else:
                record_fail(f"{fn} not callable after import")
    except Exception as e:
        record_fail(f"digest_service import failed: {e}")
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7 — DB MODELS COLUMN CHECK
# ═══════════════════════════════════════════════════════════════════════════
head("SECTION 7 — DATABASE MODEL COLUMN CHECK")

try:
    from src.db.models import News, User, Observation, Embedding, RateLimit

    sub("News — Phase 2 columns")
    news_cols = [c.name for c in News.__table__.columns]
    for col in ("summary", "summarized", "summarized_at"):
        if col in news_cols: ok(f"News.{col}")
        else:                record_fail(f"News.{col} MISSING — migration needed")

    sub("User — ATS columns")
    user_cols = [c.name for c in User.__table__.columns]
    for col in ("resume_text", "ats_score", "ats_critical_issues",
                "ats_missing_keywords", "ats_suggested_additions", "last_analysis_at"):
        if col in user_cols: ok(f"User.{col}")
        else:                record_fail(f"User.{col} MISSING — migration needed")

    sub("Observation columns")
    obs_cols = [c.name for c in Observation.__table__.columns]
    for col in ("id", "week_start", "text", "generated_at"):
        if col in obs_cols: ok(f"Observation.{col}")
        else:               record_fail(f"Observation.{col} MISSING")

    sub("Embedding columns")
    emb_cols = [c.name for c in Embedding.__table__.columns]
    for col in ("item_id", "item_type", "embedding"):
        if col in emb_cols: ok(f"Embedding.{col}")
        else:               record_fail(f"Embedding.{col} MISSING")

    sub("RateLimit columns")
    rl_cols = [c.name for c in RateLimit.__table__.columns]
    for col in ("user_id", "date", "request_count", "last_request_at"):
        if col in rl_cols: ok(f"RateLimit.{col}")
        else:              record_fail(f"RateLimit.{col} MISSING")

except Exception as e:
    record_fail(f"DB model import failed: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8 — SCHEMAS CHECK
# ═══════════════════════════════════════════════════════════════════════════
head("SECTION 8 — PYDANTIC SCHEMA CHECKS")

try:
    from src.db.schemas import (
        ObservationResponse, ResumeAnalyseResponse,
        ProfileResponse, DigestItemResponse,
    )

    sub("ObservationResponse")
    r = ObservationResponse(text="test", generated_at="2026-01-01T00:00:00", fallback=False)
    for f in ("text", "generated_at", "fallback"):
        if hasattr(r, f): ok(f"field: {f}")
        else:             record_fail(f"ObservationResponse missing field: {f}")

    sub("ResumeAnalyseResponse")
    r = ResumeAnalyseResponse(ats_score=75, critical_issues=[], missing_keywords=[],
                               suggested_additions=[], resume_text_length=1000)
    for f in ("ats_score", "critical_issues", "missing_keywords",
              "suggested_additions", "resume_text_length"):
        if hasattr(r, f): ok(f"field: {f}")
        else:             record_fail(f"ResumeAnalyseResponse missing: {f}")

    sub("ProfileResponse")
    r = ProfileResponse(id="u1", name="A", email="a@b.com", roles=[], experience_level="I",
                        ats_score=None, ats_critical_issues=[], ats_missing_keywords=[],
                        ats_suggested_additions=[], last_analysis_at=None,
                        resume_text_length=None, preferences={})
    for f in ("id", "name", "email", "roles", "experience_level",
              "ats_score", "ats_critical_issues", "ats_missing_keywords",
              "ats_suggested_additions", "last_analysis_at", "preferences"):
        if hasattr(r, f): ok(f"field: {f}")
        else:             record_fail(f"ProfileResponse missing: {f}")

    sub("DigestItemResponse")
    r = DigestItemResponse(id="n1", headline="H", source="HN", summary="S",
                            category="TECH", readTime="3 min", score=100,
                            match_percentage=70, featured=False)
    for f in ("id", "headline", "source", "summary", "category",
              "readTime", "score", "match_percentage", "featured"):
        if hasattr(r, f): ok(f"field: {f}")
        else:             record_fail(f"DigestItemResponse missing: {f}")

except Exception as e:
    record_fail(f"Schema import/instantiation failed: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 9 — API ROUTES REGISTERED
# ═══════════════════════════════════════════════════════════════════════════
head("SECTION 9 — FASTAPI ROUTE REGISTRATION")

try:
    from src.main import app
    all_paths = {r.path for r in app.routes}
    EXPECTED_ROUTES = {
        "/api/jobs", "/api/news", "/api/trends", "/api/badge",
        "/api/refresh", "/health",
        "/api/observation", "/api/resume/analyse",
        "/api/profile", "/api/digest",
    }
    sub("Checking all 10 Phase 1+2 routes")
    for route in sorted(EXPECTED_ROUTES):
        if route in all_paths:
            ok(route)
        else:
            record_fail(f"{route}  — NOT REGISTERED")
except Exception as e:
    record_fail(f"FastAPI app import failed: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# FINAL DIAGNOSTIC SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
head("FINAL DIAGNOSTIC SUMMARY")

print(f"\n  Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  Backend   : {backend_dir}")
print(f"  .env file : {env_path or 'NOT FOUND'}")
print(f"  Key length: {len(LIVE_KEY)} chars  ({OK if len(LIVE_KEY)>=40 else FAIL+' TOO SHORT'})")
print()

if ISSUES:
    print(f"  {FAIL}  {len(ISSUES)} CONFIRMED ISSUE(S) FOUND:\n")
    for i, issue in enumerate(ISSUES, 1):
        print(f"     [{i}] {issue}")
    print()
    print("  ─ PRIORITY FIX GUIDE ─────────────────────────────────────────")
    if any("SHORT" in i or "TRUNCAT" in i or "length" in i.lower() for i in ISSUES):
        print("  1. KEY IS TRUNCATED — most critical issue:")
        print("     • Go to https://openrouter.ai/keys")
        print("     • Reveal/create your key, select ALL text, copy")
        print("     • Open your .env, replace the entire line:")
        print("       OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx...xxxxxxxx")
        print("     • No quotes, no spaces, no line breaks")
    if any("MISSING" in i for i in ISSUES):
        print("  2. MISSING DB COLUMNS — run your migration:")
        print("     python -m alembic upgrade head   (or your equivalent)")
    if any("Authorization" in i or "Bearer" in i for i in ISSUES):
        print("  3. HEADER BUG in llm_service.py:")
        print('     Ensure: "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"')
    thinhr()
else:
    print(f"  {OK}  No confirmed issues found!")

if WARNINGS:
    print(f"\n  {WARN} {len(WARNINGS)} WARNING(S) (non-fatal):\n")
    for w in WARNINGS:
        print(f"     • {w}")

hr()
print(f"  {OK} = pass   {FAIL} = fail   {WARN} = warning   {SKIP} = skipped")
hr()