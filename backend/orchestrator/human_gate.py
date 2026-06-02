"""Async pause/resume handshake between the CEO orchestrator and the user.

This is the only place in Jarvis that knows the difference between a crew
running in a CLI and a crew running behind FastAPI. The CEO orchestrator
(plain Python) calls `ask_user(run_id, prompt)` when it needs a human
decision. The function blocks (using asyncio.sleep in a loop, polling the
state file) until the user replies via the FastAPI dashboard OR the
timeout fires. State is persisted to backend/state/runs.json so the
handshake survives a process restart.

Contract:
- The CEO orchestrator and the FastAPI dashboard agree on a `run_id`.
- The CEO writes a state row with status="waiting_human" and a prompt.
- The dashboard polls GET /workflow/status/{run_id}, sees the prompt, and
  shows it to the user.
- The dashboard POSTs the reply to /workflow/reply/{run_id}.
- `receive_user_reply` flips the state row to status="done".
- The next `ask_user` poll iteration sees status="done" and returns the reply.

If the user never replies, `ask_user` returns None after the timeout.

Implementation notes:
- File-based state is intentional. It is easy to debug (cat the file),
  it survives restarts, and Phase 1 testing uses curl on a single machine.
- For Phase 7 production, swap the JSON file for SQLite with WAL mode
  (still in this file — only the storage backend changes).
- For multi-process deployment, replace the in-process polling with
  an OS-level pub/sub (e.g., Redis pub/sub). The ask_user / receive_user_reply
  contract stays the same.

Phase note (2026-06-01):
This file is being written before Phase 0 completes, on explicit owner
override of Rule 9 (Phase Discipline). It is the only Phase 1 file
written out of order. All other Phase 1 work must wait for Phase 0 to
finish.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Optional

from backend.utils.logger import get_logger

# ---------------------------------------------------------------------------
# Locations and constants
# ---------------------------------------------------------------------------

# State directory lives next to this file: backend/state/.
# All run state is in a single JSON file for now (runs.json).
# Phase 7: swap for SQLite with WAL mode — same contract.
BACKEND_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BACKEND_DIR / "state"
STATE_FILE = STATE_DIR / "runs.json"

# Default timeout — 24 hours. The user might trigger a workflow at 11pm
# and not reply until the next morning. If we time out sooner, the run dies.
DEFAULT_TIMEOUT_S = 86_400

# Poll interval — how often ask_user() re-reads the state file.
# 1 second is responsive enough for the dashboard without burning CPU.
POLL_INTERVAL_S = 1.0

# Module logger — uses the shared Jarvis logger from backend/utils/logger.py.
# That module wires a single FileHandler (backend/logs/jarvis.log) + stdout
# handler at import time, so we just ask for a named logger here and start
# logging. Per CLAUDE.md "Logging" rule: never use print() in production code.
log = get_logger(__name__)


# ---------------------------------------------------------------------------
# State file helpers — atomic writes, no partial files on crash
# ---------------------------------------------------------------------------

def _ensure_state_dir() -> None:
    """Create backend/state/ if it does not exist. Idempotent."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _read_state() -> dict:
    """Read all run states. Returns {run_id: state_dict}.

    Returns an empty dict if the file does not exist (fresh install).
    """
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # State file is corrupt. Log and start fresh — losing state is
        # better than crashing every workflow run.
        log.error("State file %s is corrupt — starting fresh", STATE_FILE)
        return {}


def _write_state(state: dict) -> None:
    """Write all run states atomically.

    Atomic write = write to .tmp, then rename. If the process crashes
    mid-write, the next read sees the OLD file, never a half-written one.
    """
    _ensure_state_dir()
    tmp = STATE_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    tmp.replace(STATE_FILE)  # atomic on POSIX


# ---------------------------------------------------------------------------
# Public API — used by the CEO orchestrator and the FastAPI layer
# ---------------------------------------------------------------------------

def new_run_id() -> str:
    """Generate a new unique run id. Used by the FastAPI route handler.

    UUID4 is overkill for a single-user system but standard. The id is
    the only key the CEO and the dashboard need to agree on.
    """
    return str(uuid.uuid4())


def get_run_status(run_id: str) -> Optional[dict]:
    """Read the current state of one run. Returns None if the run is unknown.

    Called by FastAPI GET /workflow/status/{run_id}. The dashboard polls
    this every second while the run is `waiting_human` so it can show the
    prompt and accept the reply.
    """
    state = _read_state()
    return state.get(run_id)


async def ask_user(
    run_id: str,
    prompt: str,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> Optional[str]:
    """Pause the CEO orchestrator until the user replies or times out.

    Args:
        run_id:    The unique id of this workflow run. Must be the same id
                   that the dashboard is polling.
        prompt:    Markdown text to show the user. Example:
                   "Opportunity score: 38/50. Generate full PRD? (yes / no)"
        timeout_s: How long to wait before giving up. Default 24h.

    Returns:
        The user's reply as a string, OR None if the timeout fired or
        the run was deleted while waiting.

    Side effects:
        Writes a state row with status="waiting_human" before blocking.
        Updates the row to status="done" or "failed" on exit.

    How it works:
        Polls the state file every POLL_INTERVAL_S. Each poll is cheap
        (one file read). When receive_user_reply() flips the status to
        "done", the next poll sees it and returns the reply text.
    """
    _ensure_state_dir()
    state = _read_state()
    state[run_id] = {
        "status": "waiting_human",
        "prompt": prompt,
        "reply": None,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    _write_state(state)
    log.info("ask_user: run_id=%s waiting for reply (timeout=%ds)", run_id, timeout_s)

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        await asyncio.sleep(POLL_INTERVAL_S)
        state = _read_state()
        run_state = state.get(run_id)
        if run_state is None:
            log.warning("ask_user: run_id=%s was deleted while waiting", run_id)
            return None
        if run_state.get("status") == "done":
            log.info("ask_user: run_id=%s got reply: %r", run_id, run_state.get("reply"))
            return run_state.get("reply")

    # Timeout — mark the run as failed so the dashboard can render an error.
    state = _read_state()
    if run_id in state:
        state[run_id]["status"] = "failed"
        state[run_id]["updated_at"] = time.time()
        _write_state(state)
    log.warning("ask_user: run_id=%s timed out after %ds", run_id, timeout_s)
    return None


def receive_user_reply(run_id: str, reply: str) -> dict:
    """Wake the waiting ask_user() call with the user's reply.

    Called by FastAPI POST /workflow/reply/{run_id} when the user clicks
    "Send" on the dashboard. Flips the state row from "waiting_human" to
    "done" and stores the reply text.

    Args:
        run_id: The run id from the URL path.
        reply:  The reply text. Can be short ("yes", "no") or long
                (free-form feedback if the UI allows it).

    Returns:
        The updated state dict for the run.

    Raises:
        KeyError:  If the run_id is unknown.
        ValueError: If the run is not currently waiting for human input
                    (e.g., it already finished, or it was never started
                    through this module).
    """
    state = _read_state()
    if run_id not in state:
        raise KeyError(f"Unknown run_id: {run_id}")
    run_state = state[run_id]
    if run_state.get("status") != "waiting_human":
        raise ValueError(
            f"Run {run_id} is not waiting for human input "
            f"(current status: {run_state.get('status')})"
        )

    run_state["status"] = "done"
    run_state["reply"] = reply
    run_state["updated_at"] = time.time()
    _write_state(state)
    log.info("receive_user_reply: run_id=%s reply stored", run_id)
    return run_state


# ---------------------------------------------------------------------------
# Smoke test — run this file directly to verify the contract end-to-end
#
# Usage:
#   cd backend
#   python -m orchestrator.human_gate
#
# It will:
#   1. Start an asyncio task that calls ask_user (waits 10s for reply).
#   2. After 1 second, call receive_user_reply with "yes".
#   3. Print the reply that ask_user returns.
#   4. Verify the state file was updated.
#
# No FastAPI needed — this proves the handshake works standalone.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    async def _smoke_test() -> int:
        test_run_id = new_run_id()
        log.info("SMOKE TEST — run_id=%s", test_run_id)

        async def wait_for_reply() -> None:
            reply = await ask_user(
                test_run_id,
                "Smoke test prompt — reply with anything",
                timeout_s=10,
            )
            log.info("SMOKE TEST — ask_user returned: %r", reply)

        waiter = asyncio.create_task(wait_for_reply())
        # Give ask_user a second to write the state file
        await asyncio.sleep(1)
        # Simulate the dashboard POSTing a reply
        receive_user_reply(test_run_id, "yes — smoke test passed")
        # Wait for ask_user to return
        await waiter

        # Verify final state
        final = get_run_status(test_run_id)
        log.info("SMOKE TEST — final state: %s", final)
        if final and final.get("status") == "done" and final.get("reply", "").startswith("yes"):
            log.info("SMOKE TEST — PASSED")
            return 0
        log.error("SMOKE TEST — FAILED")
        return 1

    sys.exit(asyncio.run(_smoke_test()))
