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

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.crews.jarvis_ceo import run_workflow_2
from backend.orchestrator.human_gate import new_run_id
from backend.utils import llm_provider  # noqa: F401  (P1.15 minimax/ shim — side-effect import)
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


# ---------------------------------------------------------------------------
# POST /crews/hello — hello-world crew endpoint (Phase 0a)
# ---------------------------------------------------------------------------
#
# Per ADR-0002 Q2 (grilling session 3, 2026-06-01): this endpoint is a
# smoke-test for the crew assembly + contract plumbing. It has two
# paths:
#
#   ?mock=true  → 200 with a canned HelloOutput JSON. This is the only
#                 way to call the endpoint in Phase 0a (env_valid: false
#                 means no real LLM call is possible). The frontend
#                 dashboard uses this path to render a "hello" tile
#                 without burning any API quota.
#
#   (no mock)   → 503 with a clear message. Real crew runs unblock in
#                 Phase 1 once env validation passes AND the
#                 hello_crew is wired to call the real LLM (it isn't
#                 yet — see Finding 1 in the Phase 0a handoff report:
#                 we never wired a real LLM call here, only a
#                 hardcoded response).
#
# We deliberately do NOT instantiate `build_hello_crew()` here — that
# would require a `MockLLM` instance, which lives in tests/. The 200
# path returns a hardcoded response that matches the HelloOutput
# schema exactly; the actual crew execution is exercised by
# `tests/test_hello_crew.py`, not by this HTTP endpoint.


@app.post("/crews/hello")
def run_hello_crew(mock: bool = False) -> JSONResponse:
    """Hello-world crew endpoint. See module-level comment for the
    full behavioural contract.

    Args:
        mock: Query-param flag. When true, returns a canned
            `HelloOutput` response (Phase 0a "hello" tile for the
            dashboard). When false, returns 503 — the real crew is
            Phase 1 work.

    Returns:
        200 with `{"status": "ok", "phase": "0a", "mock": true, ...}`
        on the mock path; 503 with a structured error envelope on
        the real-crew path.
    """
    if mock:
        logger.info("POST /crews/hello: mock path — returning canned HelloOutput")
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "phase": "0a",
                "mock": True,
                "message": "Hello from Jarvis",
            },
        )

    # Real-crew path is Phase 1. The 503 envelope mirrors the
    # /health error shape so the dashboard can render both with the
    # same component.
    env_ok = getattr(app.state, "env_ok", False)
    logger.warning(
        "POST /crews/hello: real-crew path blocked (env_valid=%s, phase=%s) — "
        "caller must use ?mock=true in Phase 0a",
        env_ok, getattr(app.state, "phase", "unknown"),
    )
    return JSONResponse(
        status_code=503,
        content={
            "status": "error",
            "code": 503,
            "phase": getattr(app.state, "phase", "unknown"),
            "env_valid": env_ok,
            "message": (
                "Hello-world crew is in mock-only mode during Phase 0a. "
                "Real crew runs require env validation to pass (Phase 1)."
            ),
            "fix": "Pass ?mock=true to get a canned response. Example: "
                   "POST /crews/hello?mock=true",
        },
    )


# ---------------------------------------------------------------------------
# POST /workflows/research-prd — kick off Workflow 2 (Research → PRD) (Phase 1)
# ---------------------------------------------------------------------------
#
# Phase 1 counterpart of the /crews/hello endpoint above. Kicks
# off `run_workflow_2` (the Python CEO orchestrator in
# backend/crews/jarvis_ceo.py) as a BACKGROUND task and returns
# the new run_id immediately so the dashboard can poll
# `GET /workflow/status/{run_id}` (in human_gate) for progress.
#
# Why background, not synchronous:
#   `run_workflow_2` includes a human gate (ADR-0000 Q3) that can
#   block for up to 24h waiting for the user to reply. A sync
#   endpoint would tie up a FastAPI worker for that whole time.
#   Background tasks free the worker; the dashboard polls.
#
# Why no `?mock=true` knob:
#   Unlike `/crews/hello`, Workflow 2 has no canned response —
#   its value comes from the LLM reasoning over real research.
#   The degraded-env path (env_valid=false) returns 503 with the
#   same envelope as /crews/hello so the dashboard can render
#   both with the same component.


class ResearchPRDRequest(BaseModel):
    """Request body for `POST /workflows/research-prd`.

    Attributes:
        app_idea: The user's one-sentence app idea (e.g. "a habit
            tracker for Indian college students"). Forwarded to
            `run_workflow_2()` as the crew's primary input.
    """
    app_idea: str


@app.post("/workflows/research-prd")
async def start_research_prd(
    req: ResearchPRDRequest,
    background: BackgroundTasks,
) -> JSONResponse:
    """Kick off Workflow 2 (Research → PRD) as a background task.

    Behaviour:
      - Degraded env (env_valid=false) → 503 with the structured
        error envelope (mirrors /crews/hello). The workflow needs
        real API keys; without them we don't even queue the run.
      - Valid env → 202 with a fresh UUID `run_id`. The crew runs
        in a background task. The dashboard polls
        `GET /workflow/status/{run_id}` for progress and posts
        replies to `POST /workflow/reply/{run_id}` to unblock the
        human gate.

    Args:
        req: Pydantic-validated body with `app_idea`.
        background: FastAPI's BackgroundTasks injection — the crew
            is queued on this and runs AFTER the 202 is sent.

    Returns:
        202 envelope on the happy path; 503 envelope on degraded env.
    """
    env_ok = getattr(app.state, "env_ok", False)
    if not env_ok:
        logger.warning(
            "POST /workflows/research-prd: blocked (env_valid=%s, phase=%s) — "
            "caller must set up .env with real API keys",
            env_ok, getattr(app.state, "phase", "unknown"),
        )
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "code": 503,
                "phase": getattr(app.state, "phase", "unknown"),
                "env_valid": env_ok,
                "message": (
                    "Workflow runs require env validation to pass. "
                    "The research crew and product crew both need real "
                    "API keys (OpenRouter, etc.) to function."
                ),
                "fix": (
                    "cp .env.example .env  # then fill in real API keys. "
                    "Run `python -m utils.env_validator` for a full report."
                ),
            },
        )

    # Happy path — queue the crew as a background task. The run_id
    # is generated here (not inside run_workflow_2) so the HTTP
    # response can include it before the task starts.
    run_id = new_run_id()
    background.add_task(run_workflow_2, req.app_idea, run_id)
    logger.info(
        "POST /workflows/research-prd: queued run %s for app_idea=%r",
        run_id, req.app_idea,
    )
    return JSONResponse(
        status_code=202,
        content={
            "run_id": run_id,
            "status": "started",
            "phase": getattr(app.state, "phase", "unknown"),
            "app_idea": req.app_idea,
        },
    )
