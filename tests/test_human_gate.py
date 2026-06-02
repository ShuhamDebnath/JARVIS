"""Tests for the async pause/resume handshake in
`backend/orchestrator/human_gate.py`.

What this file covers (per the Phase 0a Step 9 plan):

  1. Happy path          — `ask_user` returns the reply when
                           `receive_user_reply` is called within
                           the timeout.
  2. Timeout             — `ask_user` returns `None` after the
                           deadline and the state row is flipped
                           to `status="failed"`.
  3. KeyError            — `receive_user_reply` raises `KeyError`
                           for a run_id that was never started
                           through `ask_user`.
  4. ValueError          — `receive_user_reply` raises `ValueError`
                           when called twice on the same run
                           (the second call sees status="done"
                           which is not "waiting_human").

The `tmp_state_dir` fixture from `tests/conftest.py` is what makes
these tests safe: it monkeypatches `human_gate.STATE_DIR` and
`human_gate.STATE_FILE` to a tmp path so the tests cannot pollute
the real `backend/state/runs.json`.

Timing note:
    `ask_user` polls the state file every POLL_INTERVAL_S = 1.0
    second. The happy-path test therefore takes ~1-1.5s of wall
    time. The timeout test uses `timeout_s=1` and runs in ~1s.
    Total suite runtime is ~3-4s. We do NOT monkey-patch the poll
    interval — these tests intentionally exercise the real poll
    cadence so a future change to the loop (e.g. switch to Redis
    pub/sub) is caught here.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from backend.orchestrator import human_gate
from backend.orchestrator.human_gate import (
    ask_user,
    get_run_status,
    new_run_id,
    receive_user_reply,
)


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_user_happy_path_returns_reply(tmp_state_dir) -> None:
    """`ask_user` returns the reply when `receive_user_reply` is called
    inside the timeout window, and the state row is flipped to `done`.
    """
    run_id = new_run_id()

    async def _wait_for_reply() -> str:
        return await ask_user(
            run_id,
            "happy-path prompt — please reply yes",
            timeout_s=5,  # long enough that the test won't time out
        )

    # Kick off ask_user in a background task. It writes the
    # 'waiting_human' state row, then polls every POLL_INTERVAL_S.
    waiter = asyncio.create_task(_wait_for_reply())

    # Give ask_user a beat to write the initial state row before we
    # call receive_user_reply. 0.2s is plenty — _ensure_state_dir +
    # _write_state is ~ms.
    await asyncio.sleep(0.2)

    # Simulate the dashboard POST /workflow/reply/{run_id}.
    receive_user_reply(run_id, "yes — happy path")

    # The next poll iteration should see status="done" and return.
    # We bound the wait at 3s (1s poll + 2s headroom) so a broken
    # poll loop fails the test instead of hanging the suite forever.
    reply = await asyncio.wait_for(waiter, timeout=3.0)
    assert reply == "yes — happy path", (
        f"ask_user should have returned the reply, got {reply!r}"
    )

    # And the state file should reflect the resolved run.
    state = get_run_status(run_id)
    assert state is not None, "state row should still exist after reply"
    assert state["status"] == "done", (
        f"status should be 'done' after reply, got {state.get('status')!r}"
    )
    assert state["reply"] == "yes — happy path"


# ---------------------------------------------------------------------------
# 2. Timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_user_timeout_returns_none_and_marks_failed(tmp_state_dir) -> None:
    """`ask_user` returns `None` after the deadline elapses, and
    flips the state row to `status="failed"`.
    """
    run_id = new_run_id()

    # timeout_s=1 means ask_user returns after roughly 1 wall-second
    # (one poll cycle — see ask_user source).
    t0 = time.monotonic()
    reply = await ask_user(run_id, "timeout prompt — no reply", timeout_s=1)
    elapsed = time.monotonic() - t0

    assert reply is None, f"expected None on timeout, got {reply!r}"

    # Sanity on the timing — catches both "returned instantly"
    # (broken poll loop) and "waited forever" (hanging asyncio task).
    assert elapsed >= 0.9, f"ask_user returned too fast: {elapsed:.2f}s"
    assert elapsed < 3.0, f"ask_user returned too slow: {elapsed:.2f}s"

    # The state file should reflect the failed run.
    state = get_run_status(run_id)
    assert state is not None, "state row should exist after timeout"
    assert state["status"] == "failed", (
        f"status should be 'failed' after timeout, got {state.get('status')!r}"
    )


# ---------------------------------------------------------------------------
# 3. KeyError on unknown run_id (sync — receive_user_reply is sync)
# ---------------------------------------------------------------------------


def test_receive_user_reply_unknown_run_id_raises_keyerror(tmp_state_dir) -> None:
    """`receive_user_reply` raises `KeyError` for a run_id that was
    never registered with `ask_user` (i.e., not in the state file).
    """
    # A freshly generated id, never added to the state file.
    unknown = new_run_id()
    assert get_run_status(unknown) is None, (
        "precondition: this run_id should not exist in the state file"
    )

    with pytest.raises(KeyError) as exc_info:
        receive_user_reply(unknown, "this should never be stored")

    # The KeyError message should mention the offending run_id so
    # the caller can debug without re-reading the source.
    assert unknown in str(exc_info.value), (
        f"KeyError message should mention the unknown run_id; got: {exc_info.value!s}"
    )


# ---------------------------------------------------------------------------
# 4. ValueError on already-done run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_receive_user_reply_on_done_run_raises_valueerror(tmp_state_dir) -> None:
    """`receive_user_reply` raises `ValueError` when called a second
    time on a run that has already been resolved (status="done").
    """
    run_id = new_run_id()

    # --- First reply: walk the happy path so the run is "done". ---
    async def _wait_for_first_reply() -> str:
        return await ask_user(run_id, "done-twice prompt", timeout_s=5)

    first_waiter = asyncio.create_task(_wait_for_first_reply())
    await asyncio.sleep(0.2)
    receive_user_reply(run_id, "first reply")
    first_reply = await asyncio.wait_for(first_waiter, timeout=3.0)
    assert first_reply == "first reply", (
        f"first ask_user call should have returned the first reply, got {first_reply!r}"
    )
    assert get_run_status(run_id)["status"] == "done", (
        "precondition: state should be 'done' before the second reply attempt"
    )

    # --- Second reply: must raise. ---
    with pytest.raises(ValueError) as exc_info:
        receive_user_reply(run_id, "second reply — should fail")

    # The error message should explain WHY (status is not 'waiting_human').
    msg = str(exc_info.value).lower()
    assert "not waiting" in msg or "not waiting for human input" in msg, (
        f"ValueError should explain the state conflict; got: {exc_info.value!s}"
    )
    assert "done" in msg, (
        f"ValueError should mention the current status ('done'); got: {exc_info.value!s}"
    )
