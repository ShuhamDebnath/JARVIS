"""End-to-end tests for the `POST /workflows/research-prd` FastAPI
route (P1.13).

The route kicks off Workflow 2 (Research → PRD) as a background
task and returns the new run_id immediately. The dashboard polls
`GET /workflow/status/{run_id}` (lives in `human_gate`) for
progress and replies.

Why two paths (degraded vs valid):
    The route is a real crew call — there is no `?mock=true` knob
    (unlike `/crews/hello`). So when env validation fails (no API
    keys in .env), the route returns 503 with the same structured
    error envelope `/crews/hello` uses. The dashboard renders both
    with the same component.

What this file covers:

  1. Degraded env (env_valid=false, the test default) → 503
     envelope — proves the route is registered and the env check
     is wired.
  2. Valid env (env_valid=True, run_workflow_2 monkey-patched to
     a no-op so the background task does nothing) → 202 with a
     fresh UUID `run_id` — proves the happy path works end-to-end
     without actually running the crew.

The real crew execution is exercised by `test_workflow_2_parallelism.py`
(P1.14). This file only tests the HTTP layer.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return a TestClient with the FastAPI lifespan already started.

    Mirrors the fixture in `test_phase0a_e2e.py` — the lifespan
    runs the env validator and stashes the result on `app.state`.
    The env in this checkout is invalid (no .env keys), so
    `app.state.env_ok` ends up False and the 503-path tests are
    the ones that fire by default.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def env_valid_true(monkeypatch):
    """Flip `app.state.env_ok` to True for the duration of one test.

    Used by the 202-path test. `monkeypatch.setattr` on a
    module-level attribute auto-restores on teardown, so other
    tests in the module still see the original (False) value.

    Note: the lifespan runs once per module (env_valid starts
    False). This fixture temporarily flips it True for the
    202-path test only.
    """
    monkeypatch.setattr(app.state, "env_ok", True)
    yield


@pytest.fixture
def mock_workflow_2(monkeypatch):
    """Replace `jarvis_ceo.run_workflow_2` with a no-op for one test.

    The 202-path test must NOT actually run the crew (it would
    either hit real APIs or surface the latent P1.4 kickoff
    bug). The background task adds the no-op instead. The
    202-path test asserts on the HTTP response shape only —
    P1.14 is where the actual crew path is exercised.
    """
    from backend.crews import jarvis_ceo

    async def _noop(app_idea: str, run_id: str | None = None) -> dict:
        return {"run_id": run_id or "noop", "status": "noop", "app_idea": app_idea}

    monkeypatch.setattr(jarvis_ceo, "run_workflow_2", _noop)
    yield


# ---------------------------------------------------------------------------
# 1. Degraded env → 503 with /crews/hello-shaped error envelope
# ---------------------------------------------------------------------------


def test_workflows_research_prd_degraded_env_returns_503_envelope(
    client: TestClient,
) -> None:
    """`POST /workflows/research-prd` in degraded env (env_valid=false,
    the test default) returns 503 with the structured error envelope
    that mirrors `/crews/hello`. Proves the route is registered AND
    that the env-check guard fires.
    """
    response = client.post(
        "/workflows/research-prd",
        json={"app_idea": "habit tracker for Indian college students"},
    )

    assert response.status_code == 503, (
        f"degraded-env path should return 503, got {response.status_code}: {response.text}"
    )

    body = response.json()

    # Error envelope shape — match what /crews/hello emits so the
    # dashboard can render both with the same component.
    assert set(body.keys()) >= {
        "status", "code", "phase", "env_valid", "message", "fix",
    }, f"unexpected 503 shape: {sorted(body.keys())}"

    assert body["status"] == "error", (
        f"status should be 'error', got {body['status']!r}"
    )
    assert body["code"] == 503, (
        f"code should mirror status 503, got {body['code']!r}"
    )
    assert body["env_valid"] is False, (
        f"env_valid should be false in test env, got {body['env_valid']!r}"
    )

    # The message must point the dev at the real fix (set up .env),
    # not just say "broken". If the wording changes, this test
    # catches it so the change is deliberate.
    msg = body["message"].lower()
    assert "env" in msg or "api keys" in msg, (
        f"message should mention env / API keys; got: {body['message']!r}"
    )

    # The fix field is the dashboard's contract — non-empty so
    # the UI has something to render.
    assert body["fix"], f"fix should be non-empty, got {body['fix']!r}"


# ---------------------------------------------------------------------------
# 2. Valid env + no-op crew → 202 with a fresh UUID run_id
# ---------------------------------------------------------------------------


def test_workflows_research_prd_valid_env_returns_202_with_run_id(
    client: TestClient,
    env_valid_true,
    mock_workflow_2,
) -> None:
    """`POST /workflows/research-prd` in valid env returns 202 with
    a fresh UUID `run_id`. The crew runs as a background task
    (mocked to a no-op here); the HTTP response is sent before
    the task starts.
    """
    response = client.post(
        "/workflows/research-prd",
        json={"app_idea": "habit tracker for Indian college students"},
    )

    assert response.status_code == 202, (
        f"valid-env path should return 202, got {response.status_code}: {response.text}"
    )

    body = response.json()

    # Envelope shape: run_id + status + phase, plus the echo of the
    # app_idea so the dashboard can render the run header
    # immediately.
    assert set(body.keys()) >= {"run_id", "status", "phase", "app_idea"}, (
        f"unexpected 202 shape: {sorted(body.keys())}"
    )

    # run_id is a real UUID — `uuid.UUID(...)` raises ValueError
    # on a malformed string, so this single line asserts BOTH
    # "key present" and "value is a UUID".
    parsed_id = uuid.UUID(body["run_id"])
    assert str(parsed_id) == body["run_id"], (
        f"run_id should round-trip through uuid.UUID; got {body['run_id']!r}"
    )

    # Status text reflects "accepted, started in background".
    assert body["status"] == "started", (
        f"status should be 'started', got {body['status']!r}"
    )

    # The app_idea is echoed back so the dashboard can show what
    # the user submitted without an extra round-trip.
    assert body["app_idea"] == "habit tracker for Indian college students", (
        f"app_idea should echo the request body; got {body['app_idea']!r}"
    )

    # Phase is whatever the lifespan set — keep the assertion loose
    # ("0a" today, will flip to "1" when the lifespan phase tag is
    # updated in the Phase 1 closeout commit).
    assert isinstance(body["phase"], str) and body["phase"], (
        f"phase should be a non-empty string, got {body['phase']!r}"
    )
