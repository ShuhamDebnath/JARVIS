"""End-to-end tests for the Phase 0a FastAPI surface.

These tests exercise the full HTTP stack (FastAPI routing, the
lifespan startup hook, middleware, JSON serialization) without
spinning up a real uvicorn process. FastAPI's `TestClient` (httpx
under the hood) handles the request/response cycle in-process.

What this file covers (per the Phase 0a Step 10 plan):

  1. `GET /health`                      — 200, `env_valid: false`
  2. `POST /crews/hello?mock=true`      — 200, `HelloOutput` shape
  3. `POST /crews/hello` (no mock)      — 503, structured error envelope

The `client` fixture is module-scoped so the FastAPI lifespan
(validator + state setup) runs exactly once for the three tests.
Running the lifespan per-test would be wasteful and would also
emit a CRITICAL log line on every test run (since env_valid: false
in Phase 0a).

Phase 0a is in "env_valid: false" state — no API keys in .env, so
the validator will report the env as invalid. The /health test
asserts `env_valid: false` explicitly. This is the truth for
Phase 0a; if you wire real .env keys and re-run, /health will flip
to `env_valid: true` and this assertion will need updating.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return a TestClient with the FastAPI lifespan already started.

    Using `with TestClient(app) as client:` triggers the lifespan
    startup hook, which runs the env validator and stashes the
    result on `app.state.env_ok`. The `with` block ensures the
    shutdown hook also runs after the module's last test finishes.

    Module-scoped because the lifespan is expensive-ish (it sets
    up logging handlers + reads .env) and the result is shared
    read-only state on `app.state`.
    """
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. GET /health
# ---------------------------------------------------------------------------


def test_health_endpoint_returns_200_with_env_valid_false(client: TestClient) -> None:
    """`GET /health` returns 200 with the env-validity envelope.

    Phase 0a has no .env keys, so `env_valid` is `false`. The HTTP
    status is still 200 (not 503) — the /health route is a
    smoke-test that always succeeds, even in a degraded state. The
    `env_valid` field carries the actual truth.
    """
    response = client.get("/health")

    assert response.status_code == 200, (
        f"/health should return 200 in degraded state, got {response.status_code}"
    )

    body = response.json()
    # Shape contract: every documented key is present.
    assert set(body.keys()) >= {"status", "env_valid", "env_message", "phase"}, (
        f"unexpected /health shape: {sorted(body.keys())}"
    )

    # Phase 0a truth — update this assertion if you ever wire real
    # .env keys (it should flip to True).
    assert body["env_valid"] is False, (
        f"Phase 0a has no API keys — env_valid should be false, got {body['env_valid']!r}"
    )

    # The human-readable message should be actionable — point the
    # dev at the fix, not just say "broken".
    assert "API keys" in body["env_message"] or "env" in body["env_message"].lower(), (
        f"env_message should mention the API keys fix; got: {body['env_message']!r}"
    )

    # Phase tag is set by lifespan.
    assert body["phase"] == "0a", (
        f"phase should be '0a', got {body['phase']!r}"
    )

    # Status text reflects env state but is still 'ok'-ish in HTTP
    # terms. (We accept both "ok" and "degraded" for forward-compat.)
    assert body["status"] in {"ok", "degraded"}, (
        f"unexpected status text: {body['status']!r}"
    )


# ---------------------------------------------------------------------------
# 2. POST /crews/hello?mock=true
# ---------------------------------------------------------------------------


def test_crews_hello_mock_returns_200_with_hello_output_shape(
    client: TestClient,
) -> None:
    """`POST /crews/hello?mock=true` returns 200 with the HelloOutput
    shape embedded in the wrapper envelope.
    """
    response = client.post("/crews/hello?mock=true")

    assert response.status_code == 200, (
        f"mock path should return 200, got {response.status_code}: {response.text}"
    )

    body = response.json()

    # Envelope shape — match what backend/main.py emits.
    assert set(body.keys()) >= {"status", "phase", "mock", "message"}, (
        f"unexpected /crews/hello mock shape: {sorted(body.keys())}"
    )

    # The HelloOutput contract: exactly one `message` field, string,
    # 1-500 chars (per backend/contracts/hello.py).
    assert isinstance(body["message"], str), (
        f"message must be a str, got {type(body['message']).__name__}"
    )
    assert 1 <= len(body["message"]) <= 500, (
        f"message length {len(body['message'])} out of HelloOutput bounds"
    )
    assert body["message"] == "Hello from Jarvis", (
        f"canned message mismatch, got {body['message']!r}"
    )

    # Envelope metadata.
    assert body["status"] == "ok", f"status should be 'ok', got {body['status']!r}"
    assert body["phase"] == "0a", f"phase should be '0a', got {body['phase']!r}"
    assert body["mock"] is True, f"mock should be True on the mock path, got {body['mock']!r}"


# ---------------------------------------------------------------------------
# 3. POST /crews/hello (no mock)
# ---------------------------------------------------------------------------


def test_crews_hello_no_mock_returns_503_with_error_envelope(
    client: TestClient,
) -> None:
    """`POST /crews/hello` (without `?mock=true`) returns 503 with a
    structured error envelope explaining the state and the fix.
    """
    # Send the request with no query string — FastAPI will treat
    # `mock` as `False` (its default). We also explicitly hit
    # `?mock=false` to be defensive against any future "truthy"
    # parsing in the route.
    for query in ("", "?mock=false"):
        response = client.post(f"/crews/hello{query}")

        assert response.status_code == 503, (
            f"non-mock path should return 503, got {response.status_code}: {response.text}"
        )

        body = response.json()

        # Error envelope shape — match what backend/main.py emits.
        assert set(body.keys()) >= {
            "status", "code", "phase", "env_valid", "message", "fix",
        }, f"unexpected 503 shape: {sorted(body.keys())}"

        assert body["status"] == "error", f"status should be 'error', got {body['status']!r}"
        assert body["code"] == 503, f"code should mirror status 503, got {body['code']!r}"
        assert body["phase"] == "0a", f"phase should be '0a', got {body['phase']!r}"

        # Phase 0a truth: env_valid is false because no .env keys.
        assert body["env_valid"] is False, (
            f"env_valid should be false in Phase 0a, got {body['env_valid']!r}"
        )

        # The `fix` field is the contract for the dashboard — it
        # tells the user (and the dashboard UI) exactly how to
        # recover. If the wording changes, this test will catch it
        # so the change is deliberate.
        assert "mock=true" in body["fix"], (
            f"fix should mention ?mock=true; got: {body['fix']!r}"
        )

        # The human-readable message should mention Phase 0a so
        # the dev / future user knows this is a phase-gated
        # restriction, not a generic server error.
        assert "Phase 0a" in body["message"] or "phase 0a" in body["message"].lower(), (
            f"message should mention Phase 0a; got: {body['message']!r}"
        )
