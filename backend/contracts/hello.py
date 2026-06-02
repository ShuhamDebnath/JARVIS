"""Contract: hello_task output.

The hello-world crew's single task (`hello_task`, executed by
`hello_agent`) MUST return a JSON object that parses cleanly into
`HelloOutput`. The contract is intentionally trivial: a single
`message` field. Its only job is to prove the contract plumbing works
end-to-end (YAML → Agent → Task → output_pydantic → Pydantic parse).

This file is the "shape" file referenced by `backend/config/tasks.yaml`
via the dotted path `backend.contracts.hello.HelloOutput`. Keep the
import path stable — the YAML loader in `backend/crews/hello_crew.py`
resolves that string to a class with `importlib.import_module`.

Phase 0a only. Real workflow contracts (research_interpretation,
prd_draft, etc.) live in their own files alongside this one. Adding
fields to HelloOutput is a trivial change for the hello crew but a
breaking change for any downstream that imports this contract — there
is no downstream today, so be conservative until Phase 1.
"""

# NOTE: Do NOT add `from __future__ import annotations` to this file.
# `crewai.utilities.converter.generate_model_description` (called every
# time a task with `output_pydantic=` kicks off) reads
# `model.__annotations__` and assumes each value is an actual type
# object — it then calls `.upper()` / `.__name__` on it. With PEP 563
# (future annotations) the values are STRINGS and CrewAI 0.86.0 crashes
# with `AttributeError: 'str' object has no attribute '__name__'`.
# Keeping the annotations as live types is the simplest workaround for
# this upstream bug. If we ever migrate to a CrewAI version that
# understands Pydantic v2 `model_fields`, this comment can go.

from pydantic import BaseModel, Field


class HelloOutput(BaseModel):
    """The shape the hello-world crew promises to return.

    Produced by `hello_agent` (a single-agent test crew in Phase 0a).
    No downstream consumers — this contract exists to prove the
    `output_pydantic` plumbing in CrewAI works against a strict schema.

    Fields:
        message: Free-form greeting string the LLM is instructed to
            generate. Kept short (max_length=500) so a runaway LLM
            cannot blow up the dashboard with a 50KB hello.
    """

    message: str = Field(
        min_length=1,
        max_length=500,
        description="A short greeting from Jarvis. Phase 0a expects the "
        "mocked LLM to return 'Hello from Jarvis' verbatim. Real LLM "
        "mode (Phase 1+) will return a generated greeting.",
    )
