"""Contract: research_interpretation_task output.

Spec origin: ADR-0002 (grilling session 3, 2026-06-01) Question 3, which
refined ADR-0000 Question 5's JSON shape into a strict Pydantic v2 model.

The output of `research_interpretation_task` (executed by the
`research_interpreter` agent) MUST match this schema. The 6 downstream
research specialists consume this output as task `context:` — if the
shape drifts, every specialist's search call breaks.

Retry policy (per ADR-0002 Q3):
- 3 retries on Pydantic validation failure.
- LLM sees the verbatim Pydantic ValidationError message on each retry.
- All 3 retries failing raises `InterpretationValidationError`.
- The CEO orchestrator (`jarvis_ceo.run_workflow_2`) catches that
  exception, sets `runs.json` status to `failed`, and writes the full
  LLM transcript to `backend/output/failed_interpretation_{run_id}.md`.

Phase note (2026-06-01):
- This file is being written in Phase 0a, out of strict order, because
  ADR-0002 specifies the contract must exist before Phase 1's
  `dept_crews.py` is written.
- The post-parse subreddit sanitizer (strip `r/` prefix) is a Phase 1
  deliverable that lives in `backend/crews/dept_crews.py`, NOT here.
  This file holds the *contract*; the loader applies the sanitiser.
- The `InterpretationValidationError` exception is raised by the
  output-validation layer in `dept_crews.py` (Phase 1) and caught by
  `jarvis_ceo.run_workflow_2` (Phase 1). The exception class itself
  lives here so both files can import it without a circular dep.
"""

# NOTE: Do NOT add `from __future__ import annotations` to this file.
# Same upstream bug as `backend/contracts/hello.py` — see the comment
# there for the full root cause. In short: `crewai.utilities.converter
# .generate_model_description` reads `model.__annotations__` and
# assumes each value is a real type. With PEP 563 (future annotations)
# the values are STRINGS and CrewAI 0.86.0 crashes with
# `AttributeError: 'str' object has no attribute '__name__'`. This
# contract hasn't blown up yet because no crew consumes it (Phase 0a
# has no research crew) — but the first Phase 1 kickoff would have
# crashed silently. Defused 2026-06-02 when the same bug surfaced in
# the hello-world crew's end-to-end test. If we ever migrate to a
# CrewAI version that understands Pydantic v2 `model_fields`, this
# comment can go.

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------

# App category is a closed enum. The LLM must pick one of these 7 values
# verbatim — anything else is a validation failure and triggers a retry.
# Adding a new category is a contract change: update this Literal AND
# the scoring rubric in Q1 of ADR-0000 (which maps categories to
# market-size assumptions).
AppCategory = Literal[
    "productivity",
    "health",
    "education",
    "finance",
    "social",
    "utility",
    "other",
]


class ResearchInterpretation(BaseModel):
    """Structured interpretation of the user's one-sentence app idea.

    Produced by `research_interpreter` (Level-3 specialist) at the start
    of Workflow 2. Consumed by all 6 research specialists via task
    `context: [research_interpretation_task]`.

    Why strict constraints:
    - `search_keywords` with 0–2 items breaks the 6 specialists — they
      have nothing to search for. min_length=3 enforces usefulness.
    - `target_user` shorter than 10 characters is not a demographic,
      it's a noun. min_length=10 forces specificity.
    - `core_problem` shorter than 10 characters is not a problem, it's
      a label. min_length=10 forces the LLM to actually articulate it.
    - The Literal on `app_category` makes the LLM pick a known bucket
      instead of inventing a string the downstream scoring rubric
      doesn't know how to handle.
    """

    app_category: AppCategory
    target_user: str = Field(
        min_length=10,
        max_length=200,
        description="One-sentence demographic of the primary user. "
        "Example: 'Indian college students aged 18-24 with intermittent "
        "study habits and limited disposable income.'",
    )
    core_problem: str = Field(
        min_length=10,
        max_length=300,
        description="One-sentence problem statement. Example: "
        "'Students forget to review lecture notes within 24 hours, "
        "which is the scientifically validated retention window.'",
    )
    search_keywords: list[str] = Field(
        min_length=3,
        max_length=10,
        description="3–10 search keywords ALL 6 specialists must use. "
        "Example: ['habit tracker India', 'student productivity app', "
        "'exam preparation habit'].",
    )
    subreddits_to_monitor: list[str] = Field(
        min_length=1,
        max_length=8,
        description="1–8 subreddit NAMES (no `r/` prefix). The "
        "post-parse sanitiser in `dept_crews.py` strips `r/` if the "
        "LLM includes it. Example: ['getdisciplined', 'IndianHabits'].",
    )
    app_store_categories: list[str] = Field(
        min_length=2,
        max_length=6,
        description="2–6 App Store / Play Store category names. Mix of "
        "iOS and Android categories is fine. Example: ['Productivity', "
        "'Education'].",
    )
    ambiguity_flag: str = Field(
        default="",
        description="Empty string ('') when the idea is clear. A string "
        "starting with 'AMBIGUOUS: ' followed by a one-sentence reason "
        "when the idea is unclear. The CEO orchestrator surfaces this to "
        "the user via human_gate.ask_user() (per ADR-0000 Q5). "
        "Typed as plain `str` (not `Optional[str]` / `str | None`) to "
        "bypass a CrewAI 0.86.0 bug: `describe_field` in "
        "`crewai/utilities/converter.py:245` crashes with "
        "`AttributeError: 'types.UnionType' object has no attribute "
        "'__name__'` on `Optional[X]` fields under Python 3.11. The "
        "empty-string sentinel preserves the same semantics (empty == "
        "clear) without triggering the upstream crash.",
    )


# ---------------------------------------------------------------------------
# Exception raised on validation failure
# ---------------------------------------------------------------------------


class InterpretationValidationError(Exception):
    """Raised when `research_interpreter` output fails Pydantic validation
    after 3 retries.

    Caught by `jarvis_ceo.run_workflow_2`. The handler:
    1. Logs the full LLM transcript (every prompt + every response
       across all 3 retries) to
       `backend/output/failed_interpretation_{run_id}.md` for debugging.
    2. Sets the run's status in `backend/state/runs.json` to `failed`.
    3. Returns a clean failure to the user via the dashboard: "Idea
       could not be interpreted after 3 attempts — please rephrase
       and try again." (The exact user-facing copy is a Phase 1 UX
       decision; this file only defines the exception contract.)
    """

    def __init__(self, run_id: str, errors: list[dict], transcripts: list[dict]):
        self.run_id = run_id
        self.errors = errors  # one Pydantic error dict per failed retry
        self.transcripts = transcripts  # one {prompt, response} dict per retry
        super().__init__(
            f"research_interpretation_task failed validation after 3 "
            f"retries for run_id={run_id}. See "
            f"backend/output/failed_interpretation_{run_id}.md for the "
            f"full transcript."
        )
