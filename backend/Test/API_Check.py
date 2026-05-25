"""
OpenRouter API Key Diagnostic Script
=====================================
Runs targeted checks to find the EXACT reason your API key isn't working.
No test suite noise — just the real problem, plainly stated.

Run from your project root (TazaKhabar/):
    python diagnose_openrouter.py

Or from the backend dir:
    python ../diagnose_openrouter.py
"""

import os
import sys
import re
import json
import asyncio
import pathlib

# ── Force UTF-8 on Windows ──────────────────────────────────────────────────
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")

SEP  = "═" * 65
THIN = "─" * 65
OK   = "✅"
FAIL = "❌"
WARN = "⚠️ "
INFO = "ℹ️ "


def hr(char="═"):   print(char * 65)
def head(t):        print(f"\n{SEP}\n  {t}\n{SEP}")
def sub(t):         print(f"\n  ── {t}")
def ok(msg):        print(f"  {OK}  {msg}")
def fail(msg):      print(f"  {FAIL}  {msg}")
def warn(msg):      print(f"  {WARN} {msg}")
def info(msg):      print(f"  {INFO} {msg}")
def verdict(v, msg):
    if v:   ok(msg)
    else:   fail(msg)


# ═══════════════════════════════════════════════════════════════════════════
# 1. LOCATE THE .env FILE
# ═══════════════════════════════════════════════════════════════════════════
head("STEP 1 — LOCATE .env FILE")

script_dir  = pathlib.Path(__file__).resolve().parent
candidates  = [
    script_dir / ".env",
    script_dir / "tazakhabar-backend" / ".env",
    script_dir.parent / ".env",
    script_dir.parent / "tazakhabar-backend" / ".env",
]

env_path = None
for p in candidates:
    if p.exists():
        env_path = p
        ok(f"Found .env at: {p}")
        break

if env_path is None:
    fail("No .env file found in any expected location.")
    fail(f"Searched:\n" + "\n".join(f"    {p}" for p in candidates))
    print("\n  FIX: Create a .env file in your backend directory with:")
    print("       OPENROUTER_API_KEY=sk-or-v1-<your-full-key-here>")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# 2. RAW .env CONTENT INSPECTION
# ═══════════════════════════════════════════════════════════════════════════
head("STEP 2 — RAW .env CONTENT (key lines only)")

raw_lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
key_lines = [(i+1, line) for i, line in enumerate(raw_lines)
             if "OPENROUTER" in line.upper()]

if not key_lines:
    fail("No line containing 'OPENROUTER' found in .env at all!")
    print("\n  FIX: Add this line to your .env file:")
    print("       OPENROUTER_API_KEY=sk-or-v1-<your-full-key-here>")
    sys.exit(1)

for lineno, line in key_lines:
    # Mask middle of key for safe display
    if "=" in line:
        k, _, v = line.partition("=")
        v_stripped = v.strip().strip('"').strip("'")
        masked = (v_stripped[:6] + "***" + v_stripped[-4:]) if len(v_stripped) > 12 else f"[{len(v_stripped)} chars — TOO SHORT]"
        print(f"\n  Line {lineno}: {k}={masked}")
        print(f"  Raw repr : {repr(line[:120])}")
    else:
        print(f"\n  Line {lineno}: {repr(line[:120])}")


# ═══════════════════════════════════════════════════════════════════════════
# 3. KEY EXTRACTION & FORMAT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════
head("STEP 3 — KEY EXTRACTION & FORMAT CHECKS")

raw_key = None
for _, line in key_lines:
    if "=" in line and not line.strip().startswith("#"):
        _, _, val = line.partition("=")
        raw_key = val.strip()
        break

if raw_key is None:
    fail("Could not extract key value (line may be commented out or malformed).")
    sys.exit(1)

# Strip surrounding quotes
unquoted_key = raw_key.strip('"').strip("'")

sub("Length check")
info(f"Raw value length    : {len(raw_key)} chars")
info(f"After strip quotes  : {len(unquoted_key)} chars")

EXPECTED_MIN = 40
verdict(len(unquoted_key) >= EXPECTED_MIN,
        f"Length >= {EXPECTED_MIN} (got {len(unquoted_key)})")

if len(unquoted_key) < EXPECTED_MIN:
    fail(f"KEY IS TOO SHORT — this is almost certainly the root cause.")
    print(f"\n  Your key is only {len(unquoted_key)} characters.")
    print("  A valid OpenRouter key looks like:")
    print("    sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    print("  (~56 characters total)\n")
    print("  COMMON CAUSES:")
    print("    1. Copy-paste cut off the key (select all → copy again)")
    print("    2. Shell variable expansion truncated it (wrap in quotes)")
    print("    3. You pasted a placeholder, not the real key")
    print("    4. Newline mid-key split it across two lines in .env\n")

sub("Prefix / format check")
VALID_PREFIXES = ("sk-or-v1-", "sk-or-")
has_prefix = any(unquoted_key.startswith(p) for p in VALID_PREFIXES)
verdict(has_prefix, f"Starts with 'sk-or-' prefix (got: '{unquoted_key[:10]}...')")

if not has_prefix:
    warn("Key doesn't start with 'sk-or-'. Might be wrong key type.")
    print("   OpenRouter keys always begin with 'sk-or-v1-'")
    print("   Make sure you're copying from: https://openrouter.ai/keys")

sub("Whitespace / invisible character check")
has_spaces      = " " in unquoted_key
has_tabs        = "\t" in unquoted_key
has_newlines    = "\n" in unquoted_key or "\r" in unquoted_key
has_bom         = unquoted_key.startswith("\ufeff")
has_zero_width  = any(ord(c) in (0x200B, 0x200C, 0x200D, 0xFEFF) for c in unquoted_key)

verdict(not has_spaces,     "No spaces inside key")
verdict(not has_tabs,       "No tab characters inside key")
verdict(not has_newlines,   "No newlines inside key")
verdict(not has_bom,        "No BOM (byte order mark) at start")
verdict(not has_zero_width, "No zero-width / invisible characters")

sub("Multi-line split check")
all_key_lines = [line for _, line in key_lines]
if len(all_key_lines) > 1:
    warn(f"Found {len(all_key_lines)} lines with 'OPENROUTER' — possible key split!")
    for _, l in key_lines:
        print(f"     {repr(l)}")
else:
    ok("Only one OPENROUTER line — no split detected")


# ═══════════════════════════════════════════════════════════════════════════
# 4. PYTHON ENVIRONMENT — HOW settings.py READS THE KEY
# ═══════════════════════════════════════════════════════════════════════════
head("STEP 4 — HOW YOUR APP READS THE KEY")

# Try to add backend to path
backend_candidates = [
    script_dir / "tazakhabar-backend",
    script_dir,
    script_dir.parent / "tazakhabar-backend",
]
backend_dir = None
for bc in backend_candidates:
    if (bc / "src").exists():
        backend_dir = bc
        sys.path.insert(0, str(bc))
        break

sub("Backend src import")
if backend_dir:
    ok(f"Backend found at: {backend_dir}")
else:
    warn("Could not locate backend src/ directory — skipping settings import test")

settings_key = None
if backend_dir:
    try:
        from src.config import settings
        settings_key = settings.OPENROUTER_API_KEY
        info(f"settings.OPENROUTER_API_KEY length : {len(settings_key) if settings_key else 0}")
        info(f"First 10 chars                     : {repr(settings_key[:10]) if settings_key else 'None'}")

        verdict(bool(settings_key), "settings.OPENROUTER_API_KEY is not empty")
        verdict(len(settings_key or '') >= EXPECTED_MIN,
                f"settings key length >= {EXPECTED_MIN} (got {len(settings_key or '')})")

        if settings_key != unquoted_key:
            warn("settings.OPENROUTER_API_KEY differs from raw .env value!")
            info(f"  .env raw    : {len(unquoted_key)} chars")
            info(f"  settings    : {len(settings_key)} chars")
            print("\n  This means pydantic-settings / python-dotenv is transforming")
            print("  your key. Check for extra quotes in .env or a conflicting")
            print("  environment variable set in your shell/system.\n")
        else:
            ok("settings value matches raw .env value exactly")

    except Exception as e:
        fail(f"Could not import settings: {e}")
        warn("Falling back to raw .env value for API test")
        settings_key = unquoted_key

sub("OS environment variable check")
os_key = os.environ.get("OPENROUTER_API_KEY", "")
if os_key:
    info(f"OS env OPENROUTER_API_KEY length: {len(os_key)}")
    if os_key != unquoted_key:
        warn("OS env variable DIFFERS from .env file!")
        warn("Your shell has OPENROUTER_API_KEY set separately — it may OVERRIDE .env!")
        info(f"  Shell/OS env: {len(os_key)} chars, starts with '{os_key[:8]}...'")
        info(f"  .env file   : {len(unquoted_key)} chars, starts with '{unquoted_key[:8]}...'")
        print("\n  FIX: Either unset the shell variable:")
        print("       $Env:OPENROUTER_API_KEY = $null   # PowerShell")
        print("       unset OPENROUTER_API_KEY           # bash")
        print("  Or make sure both values match.\n")
    else:
        ok("OS env matches .env file")
else:
    info("OPENROUTER_API_KEY not set in OS environment (loaded from .env only)")


# ═══════════════════════════════════════════════════════════════════════════
# 5. LIVE API TEST — ACTUAL HTTP REQUEST
# ═══════════════════════════════════════════════════════════════════════════
head("STEP 5 — LIVE API CALL TO OPENROUTER")

# Use best available key
test_key = settings_key or unquoted_key

sub(f"Testing with key: {test_key[:8]}***{test_key[-4:]} ({len(test_key)} chars)")

try:
    import httpx

    async def _test_api(api_key: str):
        results = {}

        # ── Test 1: Models endpoint (no cost, just auth check) ──
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            results["models_status"] = r.status_code
            results["models_body"]   = r.text[:300]

        # ── Test 2: Minimal chat completion ──
        async with httpx.AsyncClient(timeout=20) as client:
            payload = {
                "model": "openai/gpt-4o-mini",  # widely available fallback
                "max_tokens": 5,
                "messages": [{"role": "user", "content": "Say: OK"}],
            }
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            results["chat_status"] = r.status_code
            results["chat_body"]   = r.text[:400]

        return results

    res = asyncio.run(_test_api(test_key))

    sub("GET /api/v1/models — auth probe (free, no tokens used)")
    info(f"HTTP status: {res['models_status']}")
    if res["models_status"] == 200:
        ok("Auth PASSED — key is valid and accepted by OpenRouter!")
    elif res["models_status"] == 401:
        fail("Auth FAILED — 401 Unauthorized on models endpoint")
        body = json.loads(res["models_body"]) if res["models_body"].startswith("{") else {}
        info(f"Error message: {body.get('error', {}).get('message', res['models_body'])}")
    else:
        warn(f"Unexpected status {res['models_status']}: {res['models_body'][:100]}")

    sub("POST /api/v1/chat/completions — minimal chat test")
    info(f"HTTP status: {res['chat_status']}")

    if res["chat_status"] == 200:
        ok("Chat API call SUCCEEDED — key works end-to-end!")
        try:
            body = json.loads(res["chat_body"])
            text = body["choices"][0]["message"]["content"]
            ok(f"Model replied: '{text.strip()}'")
        except Exception:
            ok(f"Raw response: {res['chat_body'][:100]}")

    elif res["chat_status"] == 401:
        fail("401 Unauthorized — key is INVALID or NOT SENT correctly")
        try:
            body = json.loads(res["chat_body"])
            info(f"OpenRouter says: {body.get('error', {}).get('message', '?')}")
        except Exception:
            info(f"Raw: {res['chat_body'][:200]}")
        print()
        print("  ┌─ ROOT CAUSE ANALYSIS ──────────────────────────────────┐")
        print(f" │  Key length  : {len(test_key)} chars (need ≥40)              │")
        print(f" │  Key preview : {test_key[:8]}...{test_key[-4:]}                     │")
        print("  ├─ MOST LIKELY CAUSE ────────────────────────────────────┤")
        if len(test_key) < EXPECTED_MIN:
            print("  │  ❌ KEY IS TRUNCATED in your .env file                 │")
            print("  │     Go to openrouter.ai/keys → copy the FULL key       │")
            print("  │     Paste it in .env — no quotes needed:               │")
            print("  │     OPENROUTER_API_KEY=sk-or-v1-xxxx...                │")
        elif not has_prefix:
            print("  │  ❌ KEY HAS WRONG FORMAT (missing sk-or-v1- prefix)    │")
            print("  │     Make sure you're using an OpenRouter key,          │")
            print("  │     not an OpenAI or other provider key                │")
        else:
            print("  │  ❌ KEY MAY BE REVOKED OR FROM WRONG ACCOUNT           │")
            print("  │     Go to openrouter.ai/keys and generate a fresh key  │")
        print("  └────────────────────────────────────────────────────────┘")

    elif res["chat_status"] == 402:
        warn("402 Payment Required — key is VALID but no credits!")
        info("Add credits at: https://openrouter.ai/credits")
        info("Or use :free models only (nvidia/nemotron, etc.)")

    elif res["chat_status"] == 429:
        warn("429 Rate Limited — key is valid but you're hitting limits")
        info("Wait a few minutes and try again")

    else:
        warn(f"Unexpected {res['chat_status']}: {res['chat_body'][:200]}")

except ImportError:
    fail("httpx not installed — cannot run live API test")
    print("  Run: pip install httpx")
except Exception as e:
    fail(f"Live API test failed with exception: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 6. HOW YOUR llm_service BUILDS THE AUTH HEADER
# ═══════════════════════════════════════════════════════════════════════════
head("STEP 6 — HOW llm_service.py SENDS THE KEY")

if backend_dir:
    try:
        llm_path = backend_dir / "src" / "services" / "llm_service.py"
        if llm_path.exists():
            src = llm_path.read_text(encoding="utf-8")

            sub("Searching for Authorization header construction")
            auth_patterns = [
                (r'Authorization.*Bearer.*OPENROUTER_API_KEY', "Bearer + settings.OPENROUTER_API_KEY"),
                (r'Authorization.*Bearer.*api_key',            "Bearer + api_key variable"),
                (r'"api-key"',                                  '"api-key" header (wrong for OpenRouter)'),
                (r'x-api-key',                                  'x-api-key header (wrong for OpenRouter)'),
            ]
            for pattern, label in auth_patterns:
                if re.search(pattern, src, re.IGNORECASE):
                    info(f"Found pattern: {label}")

            # Find exact header construction lines
            for i, line in enumerate(src.splitlines()):
                if "authorization" in line.lower() or "bearer" in line.lower():
                    print(f"    Line {i+1}: {line.strip()}")

            sub("Checking if key is passed correctly to httpx/requests")
            # Look for where the client is created
            client_lines = [(i+1, l.strip()) for i, l in enumerate(src.splitlines())
                            if "httpx" in l.lower() or "AsyncClient" in l or "headers" in l.lower()]
            for lineno, line in client_lines[:10]:
                print(f"    Line {lineno}: {line}")

        else:
            warn(f"llm_service.py not found at {llm_path}")
    except Exception as e:
        warn(f"Could not inspect llm_service.py: {e}")
else:
    warn("Skipped — backend not found")


# ═══════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
head("DIAGNOSTIC SUMMARY")

issues = []
if len(unquoted_key) < EXPECTED_MIN:
    issues.append(f"KEY TOO SHORT: {len(unquoted_key)} chars (need ≥40). Truncated in .env.")
if not has_prefix:
    issues.append("KEY FORMAT WRONG: doesn't start with 'sk-or-'")
if has_spaces or has_tabs or has_zero_width:
    issues.append("KEY HAS WHITESPACE/INVISIBLE CHARS embedded")
if os_key and os_key != unquoted_key:
    issues.append("SHELL ENV VAR overrides .env with a different value")

if issues:
    print(f"\n  Found {len(issues)} issue(s):\n")
    for i, issue in enumerate(issues, 1):
        fail(f"  [{i}] {issue}")
    print()
    print("  ─ RECOMMENDED FIX ─────────────────────────────────────────")
    print("  1. Go to https://openrouter.ai/keys")
    print("  2. Create or reveal your API key")
    print("  3. Select ALL text of the key → copy")
    print("  4. Open tazakhabar-backend/.env")
    print("  5. Replace the entire line (no spaces, no quotes):")
    print("     OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx...xxxxxxxx")
    print("  6. Save the file and re-run the tests")
    print()
else:
    ok("No obvious issues found with the key itself")
    ok("If the API still returns 401, generate a fresh key at openrouter.ai/keys")

hr()