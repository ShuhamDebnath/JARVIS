"""Per-run token budget guard for Workflow 2 (per ADR-0000 Q14).

The PRD promises "Cost under ₹2,000/month" (PRD §3). With no
guardrails, one buggy infinite-loop crew could blow the whole month
in a single run. This module provides:

  - start_run(run_id, max_tokens)     — open a budget window
  - log_call(run_id, model, in, out)  — record one LLM call
  - check_budget(run_id)              — raise BudgetExceeded if over cap
  - end_run(run_id)                   — close the window (call from finally:)

Storage is in-memory (per-process dict). State is lost on restart —
Phase 7 production swaps to SQLite WAL.

Wired into the crew via CrewAI's `task_callback` (per-task boundary)
in `backend/crews/dept_crews.py`. The callback sees the task's LLM
output (which has a `.usage` field on newer models) and we increment
the run's token counter from there. If the field is missing we fall
back to a string-length estimate (very rough — better than nothing).

Hardcoded per-model $/token table for Phase 1 — Phase 7 will load
this from a config file.

Why a hard 200k cap, not configurable:
    ADR-0000 Q14 locked the number at 200k. Workflow 2 cost
    estimate is ~85k tokens/run. 200k gives ~2x headroom for
    retries. Any increase requires re-running the parallelism
    smoke test (P1.14) to confirm a 200k-cap run still finishes
    in < 30s.

Why we raise + log + write a file, not silently abort:
    The user MUST see the cost run-away, not have a crew that
    silently returns nothing. The cost_exceeded_{run_id}.txt
    artifact in backend/output/ is the post-mortem breadcrumb.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.utils.logger import get_logger

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Hardcoded cost table (per ADR-0000 Q14: "Hardcoded $/token table per
# model for Phase 1"). Phase 7 loads this from a config file.
# Prices are USD per 1k tokens (input + output averaged for simplicity).
# Update both this table AND any dashboard that surfaces the values.
# ─────────────────────────────────────────────────────────────────────────────
COST_PER_1K_TOKENS_USD: dict[str, float] = {
    "deepseek/deepseek-chat": 0.00027,    # DeepSeek V3 list price
    "minimax/minimax-m3":     0.00015,    # MiniMax M3 estimate
    "minimax/minimax-m2.7":   0.00010,    # MiniMax M2.7 estimate
    "claude-sonnet-4-5":      0.00300,    # Claude Sonnet 4.5 list
}

# Phase 1 hard cap. Per ADR-0000 Q14, "200k tokens per run, raise
# BudgetExceeded on exceed". Don't change silently — re-run P1.14.
DEFAULT_MAX_TOKENS_PER_RUN = 200_000

# Path for cost-runaway post-mortems. backend/output/ is gitignored
# per commit a34e2e6 (runtime artifacts only). The file is the
# post-mortem breadcrumb the developer reads after the fact —
# jarvis.log has the live trace.
_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"


# ─────────────────────────────────────────────────────────────────────────────
# Exception
# ─────────────────────────────────────────────────────────────────────────────
class BudgetExceeded(Exception):
    """Raised by check_budget() when a run's token total exceeds its cap.

    The CEO orchestrator (`backend/crews/jarvis_ceo.py`) catches this:
        1. The full LLM transcript is already in jarvis.log (per-call
           logger wrote it).
        2. Sets the run's status in `backend/state/runs.json` to
           "failed" with reason="budget_exceeded".
        3. The cost_exceeded_{run_id}.txt post-mortem is written
           by `_write_post_mortem()` BEFORE this exception is raised.
        4. Returns a clean failure dict to the dashboard.

    Attributes:
        run_id: The workflow run that breached the budget.
        total_tokens: Tokens consumed at the time of breach.
        max_tokens: The cap that was set by start_run().
    """

    def __init__(self, run_id: str, total_tokens: int, max_tokens: int) -> None:
        self.run_id = run_id
        self.total_tokens = total_tokens
        self.max_tokens = max_tokens
        super().__init__(
            f"Run {run_id} exceeded token budget: "
            f"{total_tokens} / {max_tokens} tokens. "
            f"See backend/output/cost_exceeded_{run_id}.txt for the post-mortem."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Per-run state
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class _RunState:
    """In-memory record of one running workflow's token consumption.

    Created by start_run(); mutated by log_call(); checked by
    check_budget(); torn down by end_run(). Never persisted — a
    process restart drops the state. Phase 7 swaps to SQLite WAL.

    Attributes:
        run_id: Workflow run identifier (UUID from human_gate).
        max_tokens: Hard cap set by start_run(). The cost guard
            raises BudgetExceeded when total_tokens >= this value.
        total_tokens: Running sum of input + output tokens across
            all log_call() invocations for this run.
        calls: A list of {model, in_tok, out_tok, ts_iso} dicts, one
            per log_call. Kept for the cost_exceeded post-mortem and
            for the per-run cost log line at end_run().
        start_ts: Unix epoch (float) when start_run was called. Used
            by end_run to log the total wall-clock of the run.
    """

    run_id: str
    max_tokens: int
    total_tokens: int = 0
    calls: list[dict[str, Any]] = field(default_factory=list)
    start_ts: float = field(default_factory=time.time)


# Module-level state — one entry per active run. Single-process
# only; if Jarvis ever multi-processes, this needs a lock or a
# server (Phase 7 problem).
_RUN_STATE: dict[str, _RunState] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def start_run(run_id: str, max_tokens: int = DEFAULT_MAX_TOKENS_PER_RUN) -> None:
    """Open a budget window for `run_id`.

    Idempotent: calling start_run() twice for the same run_id resets
    the state to zero. This is intentional — `jarvis_ceo.run_workflow_2`
    may be retried on transient failures, and a retry should start
    fresh, not inherit the previous attempt's tokens.

    Args:
        run_id: Workflow run identifier. Typically the UUID returned
            by `human_gate.new_run_id()`.
        max_tokens: Hard cap. Defaults to 200,000 per ADR-0000 Q14.

    Raises:
        ValueError: If `max_tokens` is non-positive (a 0 or negative
            cap would raise on the first log_call).
    """
    if max_tokens <= 0:
        raise ValueError(
            f"start_run(run_id={run_id!r}) called with max_tokens={max_tokens}. "
            f"Must be a positive integer."
        )
    _RUN_STATE[run_id] = _RunState(run_id=run_id, max_tokens=max_tokens)
    log.info("cost_guard: run %s started, max_tokens=%d", run_id, max_tokens)


def log_call(run_id: str, model: str, in_tok: int, out_tok: int) -> None:
    """Record one LLM call against `run_id`'s budget.

    Increments the run's total tokens and appends a per-call record
    to the call log. If the new total meets or exceeds the cap, raises
    `BudgetExceeded` so the calling code can abort the crew.

    If `run_id` is not in `_RUN_STATE` (e.g. log_call fires after
    end_run, or before start_run), the call is logged at WARNING
    and silently dropped — defensive against hook ordering bugs.

    Args:
        run_id: Workflow run identifier (must have been start_run'd).
        model: The LLM model string (e.g. "deepseek/deepseek-chat").
            Used for the per-model cost in the end-of-run log line.
        in_tok: Input / prompt tokens for this call.
        out_tok: Output / completion tokens for this call.

    Raises:
        BudgetExceeded: If the new total_tokens >= max_tokens for
            this run. The exception is raised AFTER the call is
            logged, so the cost_exceeded post-mortem shows the
            call that caused the breach.
    """
    state = _RUN_STATE.get(run_id)
    if state is None:
        log.warning(
            "cost_guard: log_call(run_id=%r, ...) called but run is not active. "
            "Dropping call (in=%d out=%d). Check start_run/end_run ordering.",
            run_id, in_tok, out_tok,
        )
        return

    call_total = in_tok + out_tok
    state.total_tokens += call_total
    state.calls.append({
        "model": model,
        "in_tok": in_tok,
        "out_tok": out_tok,
        "ts_iso": datetime.now(timezone.utc).isoformat(),
    })
    log.debug(
        "cost_guard: run %s call #%d model=%s in=%d out=%d total=%d/%d",
        run_id, len(state.calls), model, in_tok, out_tok,
        state.total_tokens, state.max_tokens,
    )

    check_budget(run_id)


def check_budget(run_id: str) -> None:
    """Raise `BudgetExceeded` if `run_id` is at or over its cap.

    Called by log_call() automatically after every recorded call.
    Exposed publicly so the CEO orchestrator can call it before
    kicking off an expensive task as a pre-flight check.

    Args:
        run_id: Workflow run identifier.

    Raises:
        BudgetExceeded: If state.total_tokens >= state.max_tokens.
        KeyError: If `run_id` was never start_run'd.
    """
    state = _RUN_STATE[run_id]   # KeyError is the right signal here
    if state.total_tokens >= state.max_tokens:
        _write_post_mortem(state)
        raise BudgetExceeded(run_id, state.total_tokens, state.max_tokens)


def end_run(run_id: str) -> None:
    """Close the budget window for `run_id` and log a final cost line.

    Always callable from a `finally:` block — never raises on a
    missing run_id (treats it as a no-op and logs WARNING). The
    final log line is the per-run cost roll-up: total tokens,
    wall-clock seconds, estimated USD, and which models were used.

    Args:
        run_id: Workflow run identifier.
    """
    state = _RUN_STATE.pop(run_id, None)
    if state is None:
        log.warning("cost_guard: end_run(run_id=%r) called but run was not active.", run_id)
        return

    # Aggregate per-model cost for the end-of-run log line.
    per_model: dict[str, int] = {}
    for call in state.calls:
        per_model[call["model"]] = per_model.get(call["model"], 0) + call["in_tok"] + call["out_tok"]
    cost_usd = sum(
        (toks / 1000.0) * COST_PER_1K_TOKENS_USD.get(model, 0.0)
        for model, toks in per_model.items()
    )
    wall_s = time.time() - state.start_ts
    log.info(
        "cost_guard: run %s ended, total_tokens=%d/%d, wall_s=%.1f, "
        "cost_usd=~$%.4f, models=%s",
        run_id, state.total_tokens, state.max_tokens, wall_s, cost_usd,
        per_model,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Post-mortem writer
# ─────────────────────────────────────────────────────────────────────────────
def _write_post_mortem(state: _RunState) -> None:
    """Write cost_exceeded_{run_id}.txt to backend/output/.

    Called by check_budget() immediately before raising
    BudgetExceeded. The file is the breadcrumb the developer reads
    after the fact — it lists every LLM call (model, in/out tokens,
    timestamp) so the runaway can be diagnosed.

    The directory is created if missing (a fresh checkout may not
    have backend/output/ yet — gitignored per commit a34e2e6).
    """
    try:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = _OUTPUT_DIR / f"cost_exceeded_{state.run_id}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Run {state.run_id} exceeded token budget.\n")
            f.write(f"  total_tokens: {state.total_tokens}\n")
            f.write(f"  max_tokens:   {state.max_tokens}\n")
            f.write(f"  start_ts:     {state.start_ts}\n")
            f.write(f"  breach_ts:    {time.time()}\n")
            f.write(f"\nPer-call breakdown ({len(state.calls)} calls):\n")
            for i, call in enumerate(state.calls, 1):
                f.write(
                    f"  {i:3d}. {call['ts_iso']}  {call['model']:30s}  "
                    f"in={call['in_tok']:6d}  out={call['out_tok']:6d}\n"
                )
        log.error(
            "cost_guard: wrote post-mortem to %s (run %s, %d calls)",
            path, state.run_id, len(state.calls),
        )
    except OSError as e:
        # Never let the post-mortem writer crash the run — it is
        # diagnostic, not load-bearing. Log and continue.
        log.error("cost_guard: failed to write post-mortem for run %s: %s", state.run_id, e)
