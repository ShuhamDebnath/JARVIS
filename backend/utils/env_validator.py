# backend/utils/env_validator.py
# ─────────────────────────────────────────────────────────────────────────────
# Validates that all required API keys are present in the environment on
# FastAPI startup (and as a stand-alone CLI: `python -m utils.env_validator`).
#
# Required keys (per Phase 0a + your Step 4 instruction):
#     DEEPSEEK_API_KEY   — primary LLM for research/writing agents
#     OPENROUTER_API_KEY — routes MiniMax M3 / M2.7 calls
#     SERPER_API_KEY     — SerperDev web search tool
#
# Warn-only (not strictly required for Phase 0a, but used later in Phase 1):
#     ANTHROPIC_API_KEY  — Claude Vision (Phase 6 / Workflow 1)
#     FIRECRAWL_API_KEY  — Web scraper (Phase 1, revenue_estimator etc.)
#
# Optional (deferred to Phase 5+):
#     (none — Phase 5 MLX voice stack runs entirely local, no API keys)
#
# Per AI-RULES.md Rule 2: human-readable error messages; fail loud with
# what to do, not silent.
# Per ADR-0002 Q6: don't silently change required/optional lists.
# ─────────────────────────────────────────────────────────────────────────────

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Phase 5: Import the shared Jarvis logger so the validator can
# emit a structured warning that lands in backend/logs/jarvis.log
# (in addition to the print()-based report above). We import the
# logger lazily here to avoid a circular import with main.py during
# early startup.
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Placeholder strings the .env.example uses. If a key holds one of these,
# it's effectively missing — the user copied .env.example without filling in.
_PLACEHOLDERS = {
    "",
    "your_api_key_here",
    "replace_me_with_real_deepseek_key",
    "replace_me_with_real_openrouter_key",
    "replace_me_with_real_anthropic_key",
    "replace_me_with_real_serper_key",
    "replace_me_with_real_firecrawl_key",
}

# Required for Phase 0a + Phase 1 (your Step 4 instruction).
# P1.15: MINIMAX_API_KEY added as REQUIRED because the live-routing target
# is now the direct MiniMax API (per user's MiniMax token plan). The
# DEEPSEEK and OPENROUTER keys stay in REQUIRED as a fallback — flipping
# the YAML back to `deepseek/deepseek-chat` is a one-liner if MiniMax
# rate-limits mid-run.
REQUIRED_KEYS = [
    "MINIMAX_API_KEY",   # primary — direct MiniMax API (P1.15 routing)
    "DEEPSEEK_API_KEY",  # fallback — kept populated as a safety net
    "OPENROUTER_API_KEY",  # fallback — kept populated as a safety net
    "SERPER_API_KEY",
]

# Warn-only — not strictly required for Phase 0a, but used in later phases.
# We surface a warning so the user knows what's coming, but we do NOT block
# startup if they're missing.
WARN_KEYS = [
    "ANTHROPIC_API_KEY",   # needed Phase 6 / Workflow 1 (vision)
    "FIRECRAWL_API_KEY",   # needed Phase 1 / Workflow 2 (revenue_estimator)
]

# Optional — Phase 5+ (voice layer).
# Phase 5 pivoted to a 100% local MLX voice stack (mlx-whisper +
# mlx-audio + Silero-VAD via torch). No external API keys are
# required, so the OPTIONAL list is intentionally empty for the
# voice layer. Keep this list present so future optional keys have
# a home without a code change.
OPTIONAL_KEYS: list[str] = []


def _is_placeholder(value: str | None) -> bool:
    """Return True if the value is empty or a known .env.example placeholder.

    Why this matters: the user's `.env` is shipped with `replace_me_with_real_*`
    text. A naive `os.environ.get("DEEPSEEK_API_KEY")` returns the placeholder
    string, not None, so the key looks "present" but is unusable.
    """
    if value is None:
        return True
    return value.strip() in _PLACEHOLDERS


def _load_dotenv() -> None:
    """Load .env from the project root if present.

    Looks for `<repo_root>/.env` — works whether the validator is run as
    `python -m utils.env_validator` (from repo root) or as a stand-alone
    script. We do NOT fail if .env is missing — the env vars might be
    supplied another way (shell, Docker, etc.).
    """
    # backend/utils/env_validator.py → repo root is 3 levels up
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / ".env"
    load_dotenv(env_path, override=False)  # override=False: real env wins


def validate_env() -> bool:
    """Check all required keys are present and non-placeholder.

    Returns True if every REQUIRED key has a real value, False otherwise.
    WARN and OPTIONAL keys are reported but do not affect the return value.

    Prints a one-line-per-key report to stdout. Used by:
    - backend/main.py on FastAPI startup (via the `lifespan` handler)
    - the `__main__` block below for CLI smoke-test
    """
    _load_dotenv()

    all_ok = True
    print("=" * 60)
    print("JARVIS — Environment validation")
    print("=" * 60)

    # Required keys — fail the validation if any are missing/placeholder.
    for key in REQUIRED_KEYS:
        value = os.environ.get(key)
        if value is None or _is_placeholder(value):
            print(f"  [MISSING]  {key:<22}  — required for Phase 0a")
            all_ok = False
        else:
            # Show only the first 4 chars to avoid leaking the key to logs.
            print(f"  [OK]       {key:<22}  — {value[:4]}***")

    # Warn keys — present a warning but do not fail the validation.
    for key in WARN_KEYS:
        value = os.environ.get(key)
        if value is None or _is_placeholder(value):
            print(f"  [WARN]     {key:<22}  — not required now, needed later")
        else:
            print(f"  [OK]       {key:<22}  — {value[:4]}***")

    # Optional keys — only report; never fail.
    # Phase 5 MLX pivot: no optional API keys are required for the
    # voice layer (mlx-whisper + mlx-audio + Silero-VAD all run
    # locally). The loop is preserved so future optional keys have
    # a stable home.
    for key in OPTIONAL_KEYS:
        value = os.environ.get(key)
        if value is None or _is_placeholder(value):
            print(f"  [SKIP]     {key:<22}  — optional")
        else:
            print(f"  [OK]       {key:<22}  — {value[:4]}***")

    # Phase 5 MLX stack is fully local. No Voice-Layer warning needed.

    print("-" * 60)
    if all_ok:
        print("RESULT: PASS — all required keys present.")
    else:
        print("RESULT: FAIL — one or more required keys are missing.")
        print()
        print("To fix: copy .env.example to .env and fill in the values.")
        print("    cp .env.example .env")
        print("    # then edit .env and replace the placeholders with real keys")
    print("=" * 60)
    return all_ok


# CLI entry point — `python -m utils.env_validator` or direct script run.
if __name__ == "__main__":
    sys.exit(0 if validate_env() else 1)
