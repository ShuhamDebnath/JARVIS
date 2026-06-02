"""P1.15 Action 2 — live E2E smoke test for Workflow 2 (Research → PRD).

THROWAWAY-DRAFT SCRIPT. The runbook suggests deleting it after the
E2E confirms the workflow runs end-to-end on real LLMs. Recommended
follow-up: rename to scripts/smoke_workflow_2.py and keep it as a
regression utility (no need to spin up uvicorn for a smoke test).

Foreground run so the human gate is interactive: a side thread
watches `backend/state/runs.json` for a `waiting_human` row, prints
the prompt, reads stdin, and bridges to
`human_gate.receive_user_reply()` so the CEO's `ask_user()` poll
wakes up.

Logs stream to console AND to `backend/output/p1_15_live_e2e_run.log`
(jarvis's logger is already configured to tee to jarvis.log; this
script just adds the run summary to the output dir for post-mortem).

P1.15 deviations from the original runbook snippet:
  - Parameter is `app_idea`, not `idea` (the snippet in the runbook
    was wrong — verified against backend/crews/jarvis_ceo.py:291
    and backend/main.py:325).
  - The human gate is a file-based poll, NOT stdin. The runbook's
    "stdin prompt" assumption is incorrect — `ask_user()` writes
    `state[run_id] = {status: "waiting_human", prompt: ...}` and
    polls every POLL_INTERVAL_S (1s) for `status: "done"`. The
    dashboard's POST /workflow/reply/{run_id} calls
    `receive_user_reply()` to flip the state. This script bridges
    stdin → receive_user_reply via a watcher thread.
  - run_workflow_2 is async, so this script uses asyncio.run.
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from pathlib import Path

# Make the project root importable. `python scripts/run_live_e2e.py`
# puts `scripts/` (not the project root) on sys.path[0], so the
# `from backend...` imports below would fail with ModuleNotFoundError.
# This shim puts the project root first so absolute imports resolve.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.crews.jarvis_ceo import run_workflow_2  # noqa: E402
from backend.orchestrator import human_gate  # noqa: E402
from backend.orchestrator.human_gate import new_run_id  # noqa: E402
from backend.utils import llm_provider  # noqa: E402,F401  (P1.15 minimax/ shim — side-effect import)

# Fixed idea for this E2E run (runbook Step 1). Indian college students
# is a juicy target market — exercises the PytrendsTool India-specific
# trend path in the research crew.
IDEA = "habit tracker for Indian college students"

# State file the human gate writes to. Polled by the watcher thread.
STATE_FILE = Path("backend/state/runs.json")

# How often the watcher thread reads the state file. The CEO's
# ask_user() polls every 1.0s (POLL_INTERVAL_S in human_gate.py);
# 0.5s here gives the watcher a chance to print the prompt BEFORE
# the CEO's next poll, so the user sees the question first.
WATCH_POLL_S = 0.5

# How long to wait for the user to type a reply at the human gate
# before auto-responding "yes". The live E2E is bounded by the
# 10-min Bash tool timeout, so we don't want to hang here.
GATE_REPLY_TIMEOUT_S = 60

# Set to True to short-circuit the human gate reply (for CI / scripted
# runs). Leave False for the live E2E so the user can type "yes".
AUTO_REPLY_YES = False


def _watch_for_human_gate(run_id: str) -> None:
    """Watch STATE_FILE for a `waiting_human` row matching run_id.

    When found: print the prompt, read stdin (with timeout), call
    receive_user_reply to flip the state. This wakes the CEO's
    ask_user() poll on its next 1.0s tick.

    Only fires ONCE per script run (one human gate per workflow 2).
    Exits silently if the workflow finishes before the gate fires.

    Stdin handling: Claude Code's foreground Bash tool may not
    reliably pipe user keystrokes to the subprocess, and a
    backgrounded run has no stdin at all. We use a thread+join
    timeout so the gate auto-replies "yes" if the user does not
    type within GATE_REPLY_TIMEOUT_S — better than a hung run that
    burns 8 min of LLM credits and times out at the 10-min Bash
    ceiling.
    """
    deadline = time.time() + 60 * 60  # 1 hour safety cap
    print(
        f"[watcher] watching {STATE_FILE} for run_id={run_id}",
        flush=True,
    )
    while time.time() < deadline:
        if STATE_FILE.exists():
            try:
                state = json.loads(STATE_FILE.read_text())
            except json.JSONDecodeError:
                time.sleep(WATCH_POLL_S)
                continue
            run_state = state.get(run_id)
            if run_state and run_state.get("status") == "waiting_human":
                prompt = run_state.get("prompt", "Continue? (yes/no)")
                print("\n" + "=" * 60, flush=True)
                print("HUMAN GATE FIRED — type 'yes' + Enter to proceed", flush=True)
                print(f"(auto-reply in {GATE_REPLY_TIMEOUT_S}s if no input)", flush=True)
                print("=" * 60, flush=True)
                print(prompt, flush=True)
                print("=" * 60, flush=True)
                if AUTO_REPLY_YES:
                    reply = "yes"
                    print(f"> {reply}  (AUTO_REPLY_YES flag set)", flush=True)
                else:
                    reply = _read_stdin_with_timeout(GATE_REPLY_TIMEOUT_S)
                human_gate.receive_user_reply(run_id, reply)
                print(
                    f"[watcher] reply sent: {reply!r} — CEO should resume",
                    flush=True,
                )
                return
        time.sleep(WATCH_POLL_S)
    print(
        "[watcher] deadline hit (1h) — workflow may not have reached gate",
        flush=True,
    )


def _read_stdin_with_timeout(timeout_s: int) -> str:
    """Read one line from stdin with a timeout. Default to "yes" on timeout/EOF.

    Uses a daemon thread + join() because input() has no native
    timeout. If the thread is still alive after timeout_s, we know
    no input arrived and we return "yes" so the workflow continues
    rather than hanging the script.
    """
    reply_holder: list[str | None] = [None]

    def _reader() -> None:
        try:
            reply_holder[0] = input()
        except EOFError:
            reply_holder[0] = None

    print("> ", end="", flush=True)
    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    thread.join(timeout=timeout_s)
    if thread.is_alive():
        # Timeout — user didn't type in time. Auto-reply.
        print(
            f"\n> yes  (auto-reply — no input within {timeout_s}s)",
            flush=True,
        )
        return "yes"
    raw = reply_holder[0]
    if raw is None:
        # EOF on stdin (piped without interaction, or backgrounded).
        print(
            "\n> yes  (auto-reply — stdin EOF)",
            flush=True,
        )
        return "yes"
    return raw.strip().lower() or "yes"


def main() -> int:
    print(f"=== P1.15 LIVE E2E START — idea={IDEA!r} ===", flush=True)
    run_id = new_run_id()
    print(f"=== run_id={run_id} ===", flush=True)

    # Start the watcher BEFORE the workflow so we don't miss the gate.
    watcher = threading.Thread(
        target=_watch_for_human_gate,
        args=(run_id,),
        daemon=True,
    )
    watcher.start()

    try:
        result = asyncio.run(run_workflow_2(app_idea=IDEA, run_id=run_id))
    except KeyboardInterrupt:
        print("\n=== ABORTED by Ctrl+C ===", flush=True)
        return 130
    except Exception as e:
        print(f"=== FAILED: {type(e).__name__}: {e} ===", flush=True)
        raise

    print(f"=== P1.15 LIVE E2E END — result={json.dumps(result, indent=2, default=str)} ===", flush=True)
    return 0 if result.get("status") == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
