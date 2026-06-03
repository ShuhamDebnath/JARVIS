"""Python CEO orchestrator for Workflow 2 (Research → PRD).

Per ADR-0000 Q2: the CEO is plain Python, NOT a CrewAI agent. It
builds the per-department sub-crews via `backend.crews.dept_crews`,
calls them in sequence, handles the human gate, and writes the
output files. The three-level hierarchy is:

    Level 1 — this file (Python, no LLM)
    Level 2 — research_director, product_director (CrewAI manager_agents)
    Level 3 — specialists (CrewAI agents that do the work)

This file is the only place in Jarvis that:
  1. Calls multiple sub-crews in sequence
  2. Pauses for human input via `human_gate.ask_user`
  3. Writes the final PRD to `backend/output/`
  4. Catches `InterpretationValidationError` and writes the
     `failed_interpretation_{run_id}.md` post-mortem

Per ADR-0000 Q3, the human gate is `human_gate.ask_user()` — never
`human_input: true` (that flag only works in CLI mode and is detached
from the FastAPI + browser dashboard topology).

The entry point is `run_workflow_2(app_idea)` — async because the
human gate is async. Phase 1 P1.13 wires this into FastAPI.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Optional

from crewai import Crew, Process

from backend.contracts.research import InterpretationValidationError
from backend.crews.dept_crews import (
    _build_agent,
    _build_task,
    _load_yaml,
    _AGENTS_YAML,
    _TASKS_YAML,
    build_product_dept_crew,
    build_research_dept_crew,
    build_intelligence_dept_crew,
    run_research_crew_with_retry,
)
from backend.crews.content_crew import build_content_dept_crew
from backend.orchestrator.human_gate import (
    ask_user,
    new_run_id,
)
from backend.utils.cost_guard import (
    BudgetExceeded,
    DEFAULT_MAX_TOKENS_PER_RUN,
    end_run,
    start_run,
)
from backend.memory import RunStatus, write_run_status
from backend.utils.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Output file paths (per CLAUDE.md "Output Files")
# ---------------------------------------------------------------------------
# backend/crews/jarvis_ceo.py -> backend/output/
_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

# Default 35/50 scoring threshold (per ADR-0000 Q1). Logged at the top
# of every scoring report per the workflow-2 spec.
DEFAULT_THRESHOLD = 35


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _slugify_topic(idea: str) -> str:
    """Turn a one-sentence app idea into a filename-safe slug.

    Examples:
        "habit tracker for Indian college students" -> "habittrackerforindiancollegestudents"
        "A simple to-do app"                         -> "asimpletodoapp"

    Truncates to 40 chars to keep filenames readable. Returns
    "untitled" for inputs that slugify to the empty string (e.g.
    a string of only non-alphanumeric characters).
    """
    slug = re.sub(r"[^a-z0-9]+", "", idea.lower())[:40]
    return slug or "untitled"


def _write_failed_interpretation(
    run_id: str,
    transcripts: list[dict],
) -> Path:
    """Write the failed-interpretation post-mortem to backend/output/.

    Called when `run_research_crew_with_retry` raises
    `InterpretationValidationError` after 3 attempts. Per
    `backend/contracts/research.py`, the CEO is responsible for
    persisting the LLM transcript so the developer can diagnose the
    "the interpretation won't validate" failure mode.

    Args:
        run_id: The workflow run id (UUID).
        transcripts: One `{attempt, error}` dict per failed attempt,
            captured by `run_research_crew_with_retry`.

    Returns:
        The path of the written file. The CEO returns this path in
        its failure dict so the dashboard can show a "see post-mortem"
        link.
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _OUTPUT_DIR / f"failed_interpretation_{run_id}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Failed interpretation — run {run_id}\n\n")
        f.write(
            "`research_interpretation_task` failed Pydantic validation "
            "after 3 attempts. The LLM's raw output is below. The most "
            "common cause is the LLM emitting prose or a markdown fence "
            "around the JSON; the second is omitting a required field. "
            "If this becomes frequent, switch the `research_interpreter` "
            "agent to `minimax/minimax-m3` per ADR-0002 Q5.\n\n"
        )
        f.write(f"**Total attempts:** {len(transcripts)}\n\n")
        for i, t in enumerate(transcripts, 1):
            f.write(f"## Attempt {i}\n\n")
            f.write("```json\n")
            f.write(json.dumps(t, indent=2, ensure_ascii=False))
            f.write("\n```\n\n")
    log.error(
        "jarvis_ceo: wrote failed-interpretation post-mortem to %s "
        "(run %s, %d attempts)",
        path, run_id, len(transcripts),
    )
    return path


def _write_prd(topic_slug: str, prd_markdown: str) -> Path:
    """Write the PRD to backend/output/PRD_{topic}_{YYYY-MM-DD}.md.

    Per CLAUDE.md "Output Files": always APPEND, never OVERWRITE.
    If the file already exists, append `-1`, `-2`, etc. to the
    stem until we find a free name. (The expected cadence is one
    run per day, so collisions are rare — but the contract is
    "never overwrite" so we honour it.)

    Args:
        topic_slug: The slugified app idea (see `_slugify_topic`).
        prd_markdown: The full PRD text (12 sections, 1500+ words).

    Returns:
        The path the PRD was written to.
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    base = _OUTPUT_DIR / f"PRD_{topic_slug}_{today}.md"
    path = base
    n = 1
    while path.exists():
        path = base.with_name(f"{base.stem}-{n}{base.suffix}")
        n += 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(prd_markdown)
    log.info("jarvis_ceo: wrote PRD to %s (%d chars)", path, len(prd_markdown))
    return path


def _write_intelligence_report(topic_slug: str, report_markdown: str) -> Path:
    """Write the Intelligence Report to backend/output/AppStore_{topic}_{YYYY-MM-DD}.md.

    Per CLAUDE.md "Output Files": always APPEND, never OVERWRITE.
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    base = _OUTPUT_DIR / f"AppStore_{topic_slug}_{today}.md"
    path = base
    n = 1
    while path.exists():
        path = base.with_name(f"{base.stem}-{n}{base.suffix}")
        n += 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(report_markdown)
    log.info("jarvis_ceo: wrote Intelligence Report to %s (%d chars)", path, len(report_markdown))
    return path


def _extract_research_brief(crew_output: Any) -> str:
    """Pull the research brief (consolidation task's output) from a crew result.

    The brief is the free-form synthesis produced by
    `research_consolidation_task` (executed by `research_director`
    in his role as coordinator). It is the input to
    `product_opportunity_scoring_task` in the product_dept_crew.

    Falls back to `str(crew_output)` if the expected structure is
    not present — the LLM can be a moving target.
    """
    if crew_output is None:
        return ""
    if hasattr(crew_output, "tasks_output"):
        for to in crew_output.tasks_output:
            if getattr(to, "name", "") == "research_consolidation_task":
                # TaskOutput has `.raw` (the LLM text) on success.
                raw = getattr(to, "raw", None)
                if raw:
                    return str(raw)
                # Fallback: stringify the whole task output.
                return str(to)
    # Last-resort fallback — better to have something than nothing.
    return str(crew_output)


def _extract_opportunity_score(scoring_output: Any) -> Optional[int]:
    """Pull the opportunity score (out of 50) from the scoring task output.

    Tries to find a number preceded by `/50` or `out of 50` in the
    raw LLM text. Returns None if no number is found — the user
    gate then asks "did the score run? please paste it manually" as
    a fallback. (Phase 1 keeps the parser dumb; Phase 7 can swap
    to a stricter Pydantic model on `product_opportunity_scoring_task`
    once we have 10+ real runs to validate the schema against.)
    """
    if scoring_output is None:
        return None
    text = ""
    if hasattr(scoring_output, "tasks_output"):
        for to in scoring_output.tasks_output:
            if getattr(to, "name", "") == "product_opportunity_scoring_task":
                text = str(getattr(to, "raw", "") or to)
                break
    if not text:
        text = str(scoring_output)
    # Look for "/50" or "out of 50" within ~30 chars of a number.
    match = re.search(r"(\d{1,2})\s*(?:/50|out of 50)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _build_single_task_crew(
    task_key: str,
    manager_agent_role: str,
    llm: Any = None,
) -> Crew:
    """Build a single-task Crew (used for "scoring only" and "PRD only").

    The default `build_product_dept_crew()` returns a Crew bears BOTH
    the scoring and prd_writing tasks. The CEO needs to pause
    between them for the human gate (per ADR-0000 Q3), so it builds
    two single-task crews instead — one per phase.

    This helper is the smallest possible CrewAI crew: 1 manager
    agent + 1 specialist agent + 1 task. Process.hierarchical is
    still used (the manager_agent is the dept head so the workflow
    shape is consistent across the system).

    Args:
        task_key: The key in tasks.yaml for the task to run
            (e.g. "product_opportunity_scoring_task").
        manager_agent_role: The role of the manager_agent — must
            be the dept head that "owns" this task. Today only
            "Product Department Director" (product_director) is
            supported.
        llm: Optional LLM override (test path). Production: None.

    Returns:
        A `crewai.Crew` with 1 manager + 1 specialist + 1 task,
        process=Process.hierarchical, no memory kwarg.
    """
    agents_cfg = _load_yaml(_AGENTS_YAML)
    tasks_cfg = _load_yaml(_TASKS_YAML)

    # Map manager role -> manager agent key.
    manager_key_map = {
        "Product Department Director": "product_director",
        "Research Department Director": "research_director",
        "Intelligence Department Director": "intelligence_director",
    }
    manager_key = manager_key_map.get(manager_agent_role)
    if manager_key is None:
        raise ValueError(
            f"_build_single_task_crew: unknown manager_agent_role "
            f"{manager_agent_role!r}. Valid: {sorted(manager_key_map.keys())}"
        )

    manager_agent = _build_agent(manager_key, agents_cfg, llm=llm)
    task_cfg = tasks_cfg[task_key]
    specialist_key = task_cfg["agent"]
    specialist_agent = _build_agent(specialist_key, agents_cfg, llm=llm)
    task = _build_task(task_key, tasks_cfg, specialist_agent)

    crew = Crew(
        agents=[specialist_agent],
        tasks=[task],
        process=Process.hierarchical,
        manager_agent=manager_agent,
        verbose=True,
    )
    log.info(
        "single-task crew built: manager=%r specialist=%r task=%r",
        manager_agent.role, specialist_agent.role, task_key,
    )
    return crew


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def run_workflow_2(
    app_idea: str,
    run_id: Optional[str] = None,
) -> dict:
    """Run the full Research → PRD workflow for one app idea.

    This is the only public entry point of the CEO orchestrator.
    It:
      1. Opens a cost-guard budget window (200k tokens per ADR-0000 Q14).
      2. Runs the research_dept_crew with manual Pydantic retry
         (per ADR-0002 Q6). On interpretation failure: writes the
         post-mortem and returns a "failed" dict.
      3. Extracts the research brief and feeds it to the
         product_dept_crew.
      4. Runs the scoring task only. Pauses for the human gate
         ("Score is X/50. Generate full PRD? (yes/no)").
      5. If the user approves, runs the prd_writing task and writes
         the PRD to `backend/output/PRD_{topic}_{YYYY-MM-DD}.md`.
      6. Closes the cost-guard window in a `finally:` block.

    Args:
        app_idea: The user's one-sentence app idea (e.g. "a habit
            tracker for Indian college students").
        run_id: Optional pre-existing run id. If None, a new UUID
            is generated. Useful for retries — pass the same
            `run_id` and the cost-guard `start_run()` will reset
            the budget (idempotent by design).

    Returns:
        A status dict with at least:
          - run_id: str
          - status: "complete" | "failed" | "cancelled"
          - prd_path: str (only on complete)
          - transcript_path: str (only on interpretation failure)
          - reason: str (only on failed / cancelled)
    """
    run_id = run_id or new_run_id()
    log.info("run_workflow_2 START — run_id=%s idea=%r", run_id, app_idea)
    # Mirror STARTED to the Obsidian vault so the dev sees the run
    # in their vault the moment it kicks off. write_run_status is
    # already defensive against OSError — the workflow run is not
    # affected if the vault can't be written.
    write_run_status(
        run_id, RunStatus.STARTED,
        note=f"app_idea={app_idea!r}",
        meta={"app_idea": app_idea},
    )

    # Open the cost-guard budget window. start_run() is idempotent
    # (a retry resets the counter to zero). 200k cap is hardcoded
    # per ADR-0000 Q14; re-validating the parallelism test is
    # required before raising it.
    start_run(run_id, max_tokens=DEFAULT_MAX_TOKENS_PER_RUN)
    try:
        # ---- Step 1: Research dept crew ----------------------------------
        # Per P1.15 Action 2: we pass the FACTORY (not a pre-built
        # crew) into run_research_crew_with_retry so a fresh Crew
        # instance is built on every retry attempt. Re-kicking off
        # the same hierarchical crew object mutates its
        # manager_agent state and produces "Manager agent should
        # not have tools" on attempt 2+ (a known CrewAI 0.86.0
        # stateful-crew quirk). Build errors are deterministic so
        # we surface them once at the top — no retry budget burned
        # on a YAML/Pydantic typo.
        try:
            build_research_dept_crew()  # build-once smoke check
        except Exception as e:
            log.error("run_workflow_2: failed to build research_dept_crew: %s", e, exc_info=True)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"research_crew_build_failed: {e}",
                meta={"reason": "research_crew_build_failed", "error": str(e)},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "research_crew_build_failed",
                "error": str(e),
            }

        try:
            research_output = run_research_crew_with_retry(
                build_research_dept_crew,
                inputs={"app_idea": app_idea},
            )
        except InterpretationValidationError as e:
            # Update the exception's run_id to the real one (the
            # retry helper used a placeholder because it doesn't
            # know the run_id).
            e.run_id = run_id
            transcript_path = _write_failed_interpretation(run_id, e.transcripts)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"interpretation_validation_failed after {len(e.transcripts)} attempts",
                meta={
                    "reason": "interpretation_validation_failed",
                    "attempts": len(e.transcripts),
                    "transcript_path": str(transcript_path),
                },
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "interpretation_validation_failed",
                "transcript_path": str(transcript_path),
                "attempts": len(e.transcripts),
            }
        except BudgetExceeded as e:
            log.error("run_workflow_2: budget exceeded on research crew: %s", e)
            write_run_status(
                run_id, RunStatus.FAILED,
                note="budget_exceeded on research crew",
                meta={"reason": "budget_exceeded", "phase": "research"},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "budget_exceeded",
                "post_mortem": f"backend/output/cost_exceeded_{run_id}.txt",
            }
        except Exception as e:
            log.error("run_workflow_2: research crew crashed: %s", e, exc_info=True)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"research_crew_crashed: {e}",
                meta={"reason": "research_crew_crashed", "error": str(e)},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "research_crew_crashed",
                "error": str(e),
            }

        research_brief = _extract_research_brief(research_output)
        log.info(
            "run_workflow_2: research complete — brief is %d chars",
            len(research_brief),
        )
        write_run_status(
            run_id, RunStatus.RESEARCH_COMPLETE,
            note=f"research brief is {len(research_brief)} chars",
            meta={"research_brief_chars": len(research_brief)},
        )

        # ---- Step 2: Product scoring only (human gate comes after) -----
        try:
            scoring_crew = _build_single_task_crew(
                task_key="product_opportunity_scoring_task",
                manager_agent_role="Product Department Director",
            )
        except Exception as e:
            log.error("run_workflow_2: failed to build scoring_crew: %s", e, exc_info=True)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"scoring_crew_build_failed: {e}",
                meta={
                    "reason": "scoring_crew_build_failed",
                    "error": str(e),
                    "research_brief_chars": len(research_brief),
                },
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "scoring_crew_build_failed",
                "error": str(e),
                "research_brief_chars": len(research_brief),
            }

        try:
            scoring_output = scoring_crew.kickoff(
                inputs={"research_brief": research_brief},
            )
        except BudgetExceeded as e:
            log.error("run_workflow_2: budget exceeded on scoring: %s", e)
            write_run_status(
                run_id, RunStatus.FAILED,
                note="budget_exceeded on scoring",
                meta={"reason": "budget_exceeded", "phase": "scoring"},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "budget_exceeded",
                "post_mortem": f"backend/output/cost_exceeded_{run_id}.txt",
            }
        except Exception as e:
            log.error("run_workflow_2: scoring crew crashed: %s", e, exc_info=True)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"scoring_crew_crashed: {e}",
                meta={"reason": "scoring_crew_crashed", "error": str(e)},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "scoring_crew_crashed",
                "error": str(e),
            }

        # ---- Step 3: Human gate ------------------------------------------
        score = _extract_opportunity_score(scoring_output)
        score_line = f"Opportunity score: {score}/50" if score is not None else "Opportunity score: (could not parse)"
        prompt = (
            f"Threshold used: {DEFAULT_THRESHOLD}/50 (DEFAULT — to be "
            f"re-validated after 10+ runs).\n\n"
            f"{score_line}\n\n"
            f"Generate the full PRD? (yes / no)"
        )
        # Log SCORING_COMPLETE (decision made) and AWAITING_HUMAN
        # (gate reached) as two separate writes — gives the dev a
        # clear "scoring done, waiting for human" timeline.
        write_run_status(
            run_id, RunStatus.SCORING_COMPLETE,
            note=score_line,
            meta={"score": score, "threshold": DEFAULT_THRESHOLD},
        )
        write_run_status(
            run_id, RunStatus.AWAITING_HUMAN,
            note="paused at human gate",
            meta={"score": score, "threshold": DEFAULT_THRESHOLD, "prompt": prompt},
        )
        log.info("run_workflow_2: pausing at human gate — %s", score_line)
        reply = await ask_user(run_id, prompt, timeout_s=86_400)

        if reply is None:
            # Timeout — mark cancelled and return.
            log.warning("run_workflow_2: human gate timed out for run %s", run_id)
            write_run_status(
                run_id, RunStatus.CANCELLED,
                note="human gate timed out (24h deadline)",
                meta={"reason": "human_gate_timeout", "score": score},
            )
            return {
                "run_id": run_id,
                "status": "cancelled",
                "reason": "human_gate_timeout",
                "score": score,
            }
        if not reply.strip().lower().startswith("y"):
            log.info("run_workflow_2: user declined PRD for run %s (reply=%r)", run_id, reply)
            write_run_status(
                run_id, RunStatus.HUMAN_DECLINED,
                note=f"user declined PRD: {reply!r}",
                meta={"reason": "user_declined_prd", "score": score, "user_reply": reply},
            )
            return {
                "run_id": run_id,
                "status": "cancelled",
                "reason": "user_declined_prd",
                "score": score,
                "user_reply": reply,
            }
        # User approved — log it so the timeline shows the yes/no.
        write_run_status(
            run_id, RunStatus.HUMAN_APPROVED,
            note=f"user approved PRD: {reply!r}",
            meta={"score": score, "user_reply": reply},
        )

        # ---- Step 4: PRD writing -----------------------------------------
        try:
            prd_crew = _build_single_task_crew(
                task_key="product_prd_writing_task",
                manager_agent_role="Product Department Director",
            )
        except Exception as e:
            log.error("run_workflow_2: failed to build prd_crew: %s", e, exc_info=True)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"prd_crew_build_failed: {e}",
                meta={"reason": "prd_crew_build_failed", "error": str(e), "score": score},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "prd_crew_build_failed",
                "error": str(e),
                "score": score,
            }

        try:
            prd_output = prd_crew.kickoff(
                inputs={
                    "research_brief": research_brief,
                    "opportunity_score": score,
                },
            )
        except BudgetExceeded as e:
            log.error("run_workflow_2: budget exceeded on PRD writing: %s", e)
            write_run_status(
                run_id, RunStatus.FAILED,
                note="budget_exceeded on PRD writing",
                meta={"reason": "budget_exceeded", "phase": "prd_writing"},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "budget_exceeded",
                "post_mortem": f"backend/output/cost_exceeded_{run_id}.txt",
            }
        except Exception as e:
            log.error("run_workflow_2: PRD crew crashed: %s", e, exc_info=True)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"prd_crew_crashed: {e}",
                meta={"reason": "prd_crew_crashed", "error": str(e)},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "prd_crew_crashed",
                "error": str(e),
            }

        prd_markdown = str(prd_output)
        topic_slug = _slugify_topic(app_idea)
        prd_path = _write_prd(topic_slug, prd_markdown)

        log.info(
            "run_workflow_2 COMPLETE — run_id=%s prd=%s",
            run_id, prd_path,
        )
        write_run_status(
            run_id, RunStatus.COMPLETE,
            note=f"PRD written to {prd_path.name}",
            meta={
                "prd_path": str(prd_path),
                "prd_chars": len(prd_markdown),
                "score": score,
                "research_brief_chars": len(research_brief),
            },
        )
        return {
            "run_id": run_id,
            "status": "complete",
            "prd_path": str(prd_path),
            "score": score,
            "research_brief_chars": len(research_brief),
            "prd_chars": len(prd_markdown),
        }

    finally:
        # Always close the cost-guard window — success, failure,
        # or cancellation. end_run() is a no-op if the run_id is
        # unknown (defensive).
        end_run(run_id)


async def run_workflow_4(
    category: str,
    run_id: Optional[str] = None,
) -> dict:
    """Run the App Store Intelligence workflow for one category.

    Entry point for Phase 2 Workflow 4.
    """
    run_id = run_id or new_run_id()
    log.info("run_workflow_4 START — run_id=%s category=%r", run_id, category)
    
    write_run_status(
        run_id, RunStatus.STARTED,
        note=f"category={category!r}",
        meta={"category": category},
    )

    start_run(run_id, max_tokens=DEFAULT_MAX_TOKENS_PER_RUN)
    try:
        # Build crew
        try:
            crew = build_intelligence_dept_crew()
        except Exception as e:
            log.error("run_workflow_4: failed to build intelligence_dept_crew: %s", e, exc_info=True)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"intelligence_crew_build_failed: {e}",
                meta={"reason": "intelligence_crew_build_failed", "error": str(e)},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "intelligence_crew_build_failed",
                "error": str(e),
            }

        # Kickoff
        try:
            output = crew.kickoff(inputs={"category": category})
        except BudgetExceeded as e:
            log.error("run_workflow_4: budget exceeded: %s", e)
            write_run_status(
                run_id, RunStatus.FAILED,
                note="budget_exceeded",
                meta={"reason": "budget_exceeded"},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "budget_exceeded",
            }
        except Exception as e:
            log.error("run_workflow_4: intelligence crew crashed: %s", e, exc_info=True)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"intelligence_crew_crashed: {e}",
                meta={"reason": "intelligence_crew_crashed", "error": str(e)},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "intelligence_crew_crashed",
                "error": str(e),
            }

        # Save output
        report_markdown = str(output)
        topic_slug = _slugify_topic(category)
        report_path = _write_intelligence_report(topic_slug, report_markdown)
        
        write_run_status(
            run_id, RunStatus.INTELLIGENCE_COMPLETE,
            note=f"Intelligence report written to {report_path.name}",
            meta={
                "report_path": str(report_path),
                "report_chars": len(report_markdown),
            },
        )
        write_run_status(
            run_id, RunStatus.COMPLETE,
            note="Workflow 4 finished successfully",
        )
        
        return {
            "run_id": run_id,
            "status": "complete",
            "report_path": str(report_path),
            "report_chars": len(report_markdown),
        }
    finally:
        end_run(run_id)


def _write_brief(topic_slug: str, brief_markdown: str) -> Path:
    """Write the Content Brief to backend/output/Brief_{topic}_{YYYY-MM-DD}.md.

    Per CLAUDE.md "Output Files": always APPEND, never OVERWRITE.
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    base = _OUTPUT_DIR / f"Brief_{topic_slug}_{today}.md"
    path = base
    n = 1
    while path.exists():
        path = base.with_name(f"{base.stem}-{n}{base.suffix}")
        n += 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(brief_markdown)
    log.info("jarvis_ceo: wrote Brief to %s (%d chars)", path, len(brief_markdown))
    return path


async def run_workflow_3_briefs(
    topic: str,
    run_id: Optional[str] = None,
) -> dict:
    """Run the Social Content Brief workflow for one topic.

    Entry point for Phase 3a (Workflow 3 — brief generation, manual posting).

    Per ADR-0003:
      - Only `content_dept_crew` is invoked (not automation_dept_crew)
      - Skyvern is NOT used — developer copy-pastes from the brief
      - Brief is saved to `backend/output/Brief_{topic}_{date}.md`
      - ntfy.sh notification fires when brief is ready

    Args:
        topic: The topic to generate viral content briefs for.
        run_id: Optional pre-existing run id.

    Returns:
        A status dict with at least:
          - run_id: str
          - status: "complete" | "failed" | "cancelled"
          - brief_path: str (only on complete)
    """
    run_id = run_id or new_run_id()
    log.info("run_workflow_3_briefs START — run_id=%s topic=%r", run_id, topic)

    write_run_status(
        run_id, RunStatus.STARTED,
        note=f"topic={topic!r}",
        meta={"topic": topic},
    )

    start_run(run_id, max_tokens=DEFAULT_MAX_TOKENS_PER_RUN)
    try:
        try:
            crew = build_content_dept_crew()
        except Exception as e:
            log.error("run_workflow_3_briefs: failed to build content_dept_crew: %s", e, exc_info=True)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"content_crew_build_failed: {e}",
                meta={"reason": "content_crew_build_failed", "error": str(e)},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "content_crew_build_failed",
                "error": str(e),
            }

        try:
            output = crew.kickoff(inputs={"topic": topic})
        except BudgetExceeded as e:
            log.error("run_workflow_3_briefs: budget exceeded: %s", e)
            write_run_status(
                run_id, RunStatus.FAILED,
                note="budget_exceeded",
                meta={"reason": "budget_exceeded"},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "budget_exceeded",
            }
        except Exception as e:
            log.error("run_workflow_3_briefs: content crew crashed: %s", e, exc_info=True)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"content_crew_crashed: {e}",
                meta={"reason": "content_crew_crashed", "error": str(e)},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "content_crew_crashed",
                "error": str(e),
            }

        brief_markdown = str(output)
        topic_slug = _slugify_topic(topic)
        brief_path = _write_brief(topic_slug, brief_markdown)

        log.info(
            "run_workflow_3_briefs COMPLETE — run_id=%s brief=%s",
            run_id, brief_path,
        )
        write_run_status(
            run_id, RunStatus.COMPLETE,
            note=f"Brief written to {brief_path.name}",
            meta={
                "brief_path": str(brief_path),
                "brief_chars": len(brief_markdown),
            },
        )
        return {
            "run_id": run_id,
            "status": "complete",
            "brief_path": str(brief_path),
            "brief_chars": len(brief_markdown),
        }
    finally:
        end_run(run_id)


async def run_workflow_3_post(
    brief_path: str,
    platform: str,
    run_id: Optional[str] = None,
) -> dict:
    """Run the Auto-Post workflow (Workflow 3b) — Skyvern automation.

    Entry point for Phase 3b. Acts as the "Upload Gate":
      1. Validates the brief file exists
      2. Opens a cost-guard budget window
      3. Kicks off automation_dept_crew with inputs
      4. Closes the budget and returns a status dict

    Args:
        brief_path: Absolute path to the brief Markdown file produced
            by run_workflow_3_briefs (Phase 3a).
        platform: Target social platform (Twitter, Instagram, Reddit, YouTube).
        run_id: Optional pre-existing run id.

    Returns:
        A status dict with at least:
          - run_id: str
          - status: "complete" | "failed" | "cancelled"
          - post_confirmation: str (only on complete)
    """
    from backend.crews.content_crew import build_automation_dept_crew

    run_id = run_id or new_run_id()
    log.info(
        "run_workflow_3_post START — run_id=%s brief=%s platform=%s",
        run_id, brief_path, platform,
    )

    write_run_status(
        run_id, RunStatus.STARTED,
        note=f"brief_path={brief_path!r} platform={platform!r}",
        meta={"brief_path": brief_path, "platform": platform},
    )

    start_run(run_id, max_tokens=DEFAULT_MAX_TOKENS_PER_RUN)
    try:
        # Validate brief file exists
        path = Path(brief_path)
        if not path.exists():
            log.error("run_workflow_3_post: brief not found at %s", brief_path)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"brief_not_found: {brief_path}",
                meta={"reason": "brief_not_found"},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "brief_not_found",
                "brief_path": brief_path,
            }

        try:
            crew = build_automation_dept_crew()
        except Exception as e:
            log.error(
                "run_workflow_3_post: failed to build automation_dept_crew: %s",
                e, exc_info=True,
            )
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"automation_crew_build_failed: {e}",
                meta={"reason": "automation_crew_build_failed", "error": str(e)},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "automation_crew_build_failed",
                "error": str(e),
            }

        try:
            output = crew.kickoff(
                inputs={"brief_path": str(path.resolve()), "platform": platform},
            )
        except BudgetExceeded as e:
            log.error("run_workflow_3_post: budget exceeded: %s", e)
            write_run_status(
                run_id, RunStatus.FAILED,
                note="budget_exceeded",
                meta={"reason": "budget_exceeded"},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "budget_exceeded",
            }
        except Exception as e:
            log.error("run_workflow_3_post: automation crew crashed: %s", e, exc_info=True)
            write_run_status(
                run_id, RunStatus.FAILED,
                note=f"automation_crew_crashed: {e}",
                meta={"reason": "automation_crew_crashed", "error": str(e)},
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "automation_crew_crashed",
                "error": str(e),
            }

        post_confirmation = str(output)
        log.info(
            "run_workflow_3_post COMPLETE — run_id=%s confirmation=%s",
            run_id, post_confirmation,
        )
        write_run_status(
            run_id, RunStatus.COMPLETE,
            note=f"Post confirmed: {post_confirmation[:60]}",
            meta={
                "post_confirmation": post_confirmation,
                "brief_path": brief_path,
                "platform": platform,
            },
        )
        return {
            "run_id": run_id,
            "status": "complete",
            "post_confirmation": post_confirmation,
            "brief_path": str(path.resolve()),
            "platform": platform,
        }
    finally:
        end_run(run_id)
