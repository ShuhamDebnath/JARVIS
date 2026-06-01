# backend/main.py
# ─────────────────────────────────────────────────────────────────────────────
# Jarvis FastAPI entry point.
#
# Phase 0a — Minimum viable server:
#   1. On startup, validate that every required API key is present in .env
#      (delegated to `utils.env_validator`). We log the result loudly and
#      remember it in `app.state.env_ok` so /health can report it.
#   2. Expose a single GET /health endpoint that returns the app's status.
#
# Future phases (per docs/roadmap.md) will mount:
#   - Workflow routers        (Phase 1+)
#   - Upload watcher          (Phase 3a)
#   - Voice layer             (Phase 5)
#
# Run it from the project root with the conventional uvicorn module form:
#
#     cd /path/to/jarvis
#     source .venv/bin/activate
#     uvicorn backend.main:app --reload
#
# The `backend/__init__.py` file makes `backend` a real Python package, so
# the `from backend.utils ...` imports below resolve cleanly.
# ─────────────────────────────────────────────────────────────────────────────

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.utils.env_validator import validate_env
from backend.utils.logger import get_logger

# Logger for this module. Using `__name__` means log lines will be tagged
# `backend.main` — easy to grep for when debugging the server.
logger = get_logger(__name__)

# Origins that the Next.js frontend (frontend/, Phase 0d+) will hit us from
# during local dev. Tightening this further (e.g. removing 3000 when no
# frontend is wired) is fine; locking it to a production domain is out of
# scope for Phase 0a (single-user local app).
_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan hook — runs ONCE at startup and ONCE at shutdown.

    Why a lifespan (not the old `@app.on_event("startup")`)?
    - Lifespan is the modern FastAPI pattern (replaces deprecated startup/
      shutdown events). Same semantics, cleaner code.
    - One block of code instead of two decorators.

    On startup we run the environment validator. Per AI-RULES.md Rule 2
    ("fail loud, not silent"), if any required API key is missing we log
    at CRITICAL level and STILL start the app — that way the user can
    hit /health and see exactly what's wrong instead of staring at a
    crashed server with no diagnostics. The app is "degraded" but alive.
    """
    logger.info("Jarvis backend starting up (Phase 0a) ...")

    # Run the env check. The validator prints its own report to stdout
    # (intentional — it's also runnable as a stand-alone CLI), and
    # returns True/False.
    env_ok = validate_env()

    if env_ok:
        logger.info("Environment validation: PASS — all required API keys present.")
    else:
        # CRITICAL (not ERROR) because the app is technically running, but
        # the user is about to have a bad time. We make sure the log line
        # points them at the fix.
        logger.critical(
            "Environment validation: FAIL — one or more required API keys "
            "are missing or still hold .env.example placeholders. "
            "Fix with:  cp .env.example .env  # then fill in real keys. "
            "Run `python -m utils.env_validator` for a full report."
        )

    # Stash the result on app.state so the /health route can read it
    # without re-running the validator on every request.
    app.state.env_ok = env_ok
    app.state.phase = "0a"

    yield  # ← FastAPI serves requests from here until shutdown.

    logger.info("Jarvis backend shutting down.")


# Build the FastAPI app. `lifespan=lifespan` wires our startup/shutdown
# handler above. `title` and `version` show up in the auto-generated
# /docs Swagger UI (handy for poking the API by hand during dev).
app = FastAPI(
    title="Jarvis API",
    version="0.0.1",
    description="Personal AI operating system for a solo mobile dev. Phase 0a stub.",
    lifespan=lifespan,
)

# CORS middleware — let the Next.js dev server call us from a different
# port. We allow credentials so cookie-based sessions (Phase 3a Skyvern
# uploads) work; for Phase 0a there are no cookies yet, but it's harmless
# to enable now and saves a config change later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Smoke-test endpoint.

    Used by:
    - The dev (manual curl) to confirm the server is up.
    - The frontend (Phase 0d+) to render a green/red status dot.
    - Future uptime monitors.

    Returns a JSON object describing app state. We intentionally return
    200 OK even when env validation failed — the user wanted to KNOW, not
    to get a generic 500. The `env_valid` field carries the actual status.
    """
    # `getattr` with a default protects against the (impossible-today)
    # case where /health is somehow hit before lifespan startup runs.
    env_ok = getattr(app.state, "env_ok", False)

    return {
        "status": "ok" if env_ok else "degraded",
        "env_valid": env_ok,
        # Human-readable so the dev can read /health and immediately know
        # what to do without also opening the server log.
        "env_message": (
            "All required API keys present."
            if env_ok
            else "Required API keys missing or still hold .env.example "
                 "placeholders. Check server logs or run: "
                 "python -m utils.env_validator"
        ),
        "phase": getattr(app.state, "phase", "unknown"),
    }
