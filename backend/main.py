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

from pathlib import Path
import json
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.crews.jarvis_ceo import run_workflow_2, run_workflow_3_briefs, run_workflow_3_post, run_workflow_4
from backend.orchestrator.human_gate import new_run_id
from backend.utils import llm_provider  # noqa: F401  (P1.15 minimax/ shim — side-effect import)
from backend.utils.env_validator import validate_env
from backend.utils.logger import get_logger
from backend.voice.listener import JarvisVoiceCore

# Logger for this module. Using `__name__` means log lines will be tagged
# `backend.main` — easy to grep for when debugging the server.
logger = get_logger(__name__)

# Phase 5 — single global voice controller. The instance is created
# here (not on first request) so its `__init__` runs once on import.
# `start_listening()` is NOT called automatically — the mic is off
# until the operator (or the dashboard) toggles `mic_enabled` to True
# via POST /api/voice/settings. This matches the safety default in
# `JarvisVoiceCore.__init__` (mic_enabled=False, tts_enabled=True,
# auto_execute=False).
voice_core = JarvisVoiceCore()

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
    logger.info("Jarvis backend starting up ...")

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
    app.state.phase = "2"

    yield  # ← FastAPI serves requests from here until shutdown.

    logger.info("Jarvis backend shutting down.")


# Build the FastAPI app. `lifespan=lifespan` wires our startup/shutdown
# handler above. `title` and `version` show up in the auto-generated
# /docs Swagger UI (handy for poking the API by hand during dev).
app = FastAPI(
    title="Jarvis API",
    version="0.0.1",
    description="Personal AI operating system for a solo mobile dev.",
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

@app.post("/crews/hello")
def run_hello_crew(mock: bool = False) -> JSONResponse:
    """Hello-world crew endpoint.
    """
    if mock:
        logger.info("POST /crews/hello: mock path — returning canned HelloOutput")
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "phase": getattr(app.state, "phase", "unknown"),
                "mock": True,
                "message": "Hello from Jarvis",
            },
        )

    env_ok = getattr(app.state, "env_ok", False)
    return JSONResponse(
        status_code=503,
        content={
            "status": "error",
            "code": 503,
            "phase": getattr(app.state, "phase", "unknown"),
            "env_valid": env_ok,
            "message": "Real crew runs require env validation to pass.",
        },
    )


# ---------------------------------------------------------------------------
# POST /workflows/research-prd — kick off Workflow 2 (Research → PRD) (Phase 1)
# ---------------------------------------------------------------------------

class ResearchPRDRequest(BaseModel):
    """Request body for `POST /workflows/research-prd`.
    """
    app_idea: str


@app.post("/workflows/research-prd")
async def start_research_prd(
    req: ResearchPRDRequest,
    background: BackgroundTasks,
) -> JSONResponse:
    """Kick off Workflow 2 (Research → PRD) as a background task.
    """
    env_ok = getattr(app.state, "env_ok", False)
    if not env_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "code": 503,
                "phase": getattr(app.state, "phase", "unknown"),
                "env_valid": env_ok,
                "message": "Workflow runs require env validation to pass.",
            },
        )

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


# ---------------------------------------------------------------------------
# POST /workflows/app-store-intelligence — Workflow 4 (Phase 2)
# ---------------------------------------------------------------------------

class AppStoreIntelligenceRequest(BaseModel):
    """Request body for `POST /workflows/app-store-intelligence`.

    Attributes:
        category: The app category to analyze (e.g. "finance", "health").
    """
    category: str


@app.post("/workflows/app-store-intelligence")
async def start_app_store_intelligence(
    req: AppStoreIntelligenceRequest,
    background: BackgroundTasks,
) -> JSONResponse:
    """Kick off Workflow 4 (App Store Intelligence) as a background task.
    """
    env_ok = getattr(app.state, "env_ok", False)
    if not env_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "code": 503,
                "phase": getattr(app.state, "phase", "unknown"),
                "env_valid": env_ok,
                "message": "Workflow runs require env validation to pass.",
            },
        )

    run_id = new_run_id()
    background.add_task(run_workflow_4, req.category, run_id)
    logger.info(
        "POST /workflows/app-store-intelligence: queued run %s for category=%r",
        run_id, req.category,
    )
    return JSONResponse(
        status_code=202,
        content={
            "run_id": run_id,
            "status": "started",
            "phase": getattr(app.state, "phase", "unknown"),
            "category": req.category,
        },
    )


# ---------------------------------------------------------------------------
# POST /workflows/content-briefs — Workflow 3a (Phase 3a)
# ---------------------------------------------------------------------------

class ContentBriefsRequest(BaseModel):
    """Request body for `POST /workflows/content-briefs`."""
    topic: str


@app.post("/workflows/content-briefs")
async def start_content_briefs(
    req: ContentBriefsRequest,
    background: BackgroundTasks,
) -> JSONResponse:
    """Kick off Workflow 3a (Social Content Briefs) as a background task.

    Per ADR-0003: Phase 3a is brief generation only. Skyvern is NOT used.
    Developer copy-pastes from the brief and posts manually.
    """
    env_ok = getattr(app.state, "env_ok", False)
    if not env_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "code": 503,
                "phase": getattr(app.state, "phase", "unknown"),
                "env_valid": env_ok,
                "message": "Workflow runs require env validation to pass.",
            },
        )

    run_id = new_run_id()
    background.add_task(run_workflow_3_briefs, req.topic, run_id)
    logger.info(
        "POST /workflows/content-briefs: queued run %s for topic=%r",
        run_id, req.topic,
    )
    return JSONResponse(
        status_code=202,
        content={
            "run_id": run_id,
            "status": "started",
            "phase": getattr(app.state, "phase", "unknown"),
            "topic": req.topic,
        },
    )


# ---------------------------------------------------------------------------
# POST /workflows/auto-post — Workflow 3b (Phase 3b)
# ---------------------------------------------------------------------------

class AutoPostRequest(BaseModel):
    """Request body for `POST /workflows/auto-post`."""
    brief_path: str
    platform: str


@app.post("/workflows/auto-post")
async def start_auto_post(
    req: AutoPostRequest,
    background: BackgroundTasks,
) -> JSONResponse:
    """Kick off Workflow 3b (Auto-Post) as a background task.

    Reads the brief at `brief_path` and uses Skyvern to post to `platform`.
    Falls back to logging-only mode if SKYVERN_BROWSER_API_KEY is not set.
    """
    env_ok = getattr(app.state, "env_ok", False)
    if not env_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "code": 503,
                "phase": getattr(app.state, "phase", "unknown"),
                "env_valid": env_ok,
                "message": "Workflow runs require env validation to pass.",
            },
        )

    run_id = new_run_id()
    background.add_task(run_workflow_3_post, req.brief_path, req.platform, run_id)
    logger.info(
        "POST /workflows/auto-post: queued run %s brief=%s platform=%s",
        run_id, req.brief_path, req.platform,
    )
    return JSONResponse(
        status_code=202,
        content={
            "run_id": run_id,
            "status": "started",
            "phase": getattr(app.state, "phase", "unknown"),
            "brief_path": req.brief_path,
            "platform": req.platform,
        },
    )


# ---------------------------------------------------------------------------
# GET /output/{filename} — Phase 4 output file serving (Next.js dashboard)
# ---------------------------------------------------------------------------

@app.get("/output/{filename}")
def get_output_file(filename: str) -> JSONResponse:
    """Serve a markdown file from backend/output/.

    Used by the Phase 4 Next.js OutputViewer to read generated reports
    and briefs directly in the browser.

    Security: filename is resolved against output_dir and must not escape it
    (no "../" traversal). Raises 404 if file does not exist.
    """
    output_dir = Path(__file__).parent.parent / "output"
    target = output_dir / filename

    # Resolve and validate — prevents path traversal attacks
    try:
        resolved = target.resolve()
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not resolved.is_relative_to(output_dir):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not resolved.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("GET /output/%s: failed to read — %s", filename, e)
        raise HTTPException(status_code=500, detail="Could not read file")

    return JSONResponse(content={"filename": filename, "content": text})


# ---------------------------------------------------------------------------
# GET /workflows/runs — Phase 4 status polling (Next.js dashboard)
# ---------------------------------------------------------------------------

@app.get("/workflows/runs")
def get_workflow_runs() -> JSONResponse:
    """Return the current contents of backend/state/runs.json.

    Used by the Phase 4 Next.js dashboard to poll active workflow runs.
    Gracefully returns {} if the file doesn't exist yet (first run, fresh state).
    """
    runs_path = Path(__file__).parent.parent / "state" / "runs.json"

    if not runs_path.exists():
        return JSONResponse(content={})

    try:
        with open(runs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except (json.JSONDecodeError, OSError) as e:  # type: ignore[reportPossiblyUnboundVariable]
        logger.warning("GET /workflows/runs: failed to read runs.json — %s", e)
        return JSONResponse(content={})


# ---------------------------------------------------------------------------
# Phase 5 — Voice Layer control endpoints
# ---------------------------------------------------------------------------
#
# Three hardware-aware toggles are exposed under /api/voice/settings:
#   - mic_enabled   : start/stop the background VAD + STT loop
#   - tts_enabled   : speak responses aloud (True) or stay silent (False)
#   - auto_execute  : run matched workflows immediately (True) or stage
#                     them on the dashboard for manual confirmation (False)
#
# The Next.js dashboard (frontend/components/VoiceControls.tsx) reads
# the current state on mount and POSTs deltas when the operator
# flips a switch. The mic toggle has a side-effect: start_listening()
# or stop_listening() on the global `voice_core` instance.

class VoiceSettingsUpdate(BaseModel):
    """Request body for `POST /api/voice/settings`.

    All fields are Optional so the operator can update one toggle
    without re-sending the other two. Touched fields are applied
    via `voice_core.update_settings(...)` which also handles the
    start/stop side-effect on a `mic_enabled` flip.
    """
    mic_enabled: Optional[bool] = None
    tts_enabled: Optional[bool] = None
    auto_execute: Optional[bool] = None


@app.get("/api/voice/settings")
def get_voice_settings() -> JSONResponse:
    """Return the current voice-toggle snapshot.

    Response shape (always the same 4 fields, JSON-serialisable):
        {
            "mic_enabled":   bool,
            "tts_enabled":   bool,
            "auto_execute":  bool,
            "is_listening":  bool,   # true if the background worker is alive
        }
    """
    return JSONResponse(content=voice_core.get_settings())


@app.post("/api/voice/settings")
def update_voice_settings(req: VoiceSettingsUpdate) -> JSONResponse:
    """Apply a partial update to the voice toggles.

    The mic toggle has a hardware side-effect:
        - False → True : spawns the background listener thread
        - True  → False: signals the listener to stop and joins it
    The other two toggles are pure state changes — no hardware touched.
    """
    new_settings = voice_core.update_settings(
        mic_enabled=req.mic_enabled,
        tts_enabled=req.tts_enabled,
        auto_execute=req.auto_execute,
    )
    logger.info(
        "POST /api/voice/settings: applied %r — new=%r",
        req.model_dump(exclude_none=True), new_settings,
    )
    return JSONResponse(content=new_settings)
