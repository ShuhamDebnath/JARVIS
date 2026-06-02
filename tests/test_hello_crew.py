"""End-to-end test for the hello-world crew (Phase 0a).

This is the single most important test in Phase 0a: it proves the
plumbing that every real workflow will depend on is wired correctly
end-to-end.

What it exercises:
    1. `backend/config/agents.yaml` and `backend/config/tasks.yaml`
       are well-formed (parse without errors, have the expected
       top-level keys).
    2. `build_hello_crew()` instantiates one `crewai.Agent` + one
       `crewai.Task` + one `crewai.Crew` without errors.
    3. The task's `output_pydantic` (a dotted-path string in YAML)
       is resolved to the real `HelloOutput` Pydantic class via
       `importlib.import_module` + `getattr`.
    4. The crew runs end-to-end with a MockLLM (no real API call).
    5. CrewAI parses the LLM's `Final Answer:` content against
       `output_pydantic` and exposes the parsed Pydantic model on
       `result.pydantic`.
    6. The canned message survives the full pipeline unchanged.

Per Phase 0a "no real LLM calls" rule (env_valid: false), this test
MUST NOT hit DeepSeek / OpenRouter. The MockLLM fixture from
`tests/conftest.py` substitutes for the real LLM.
"""

from __future__ import annotations

from backend.contracts.hello import HelloOutput
from backend.crews.hello_crew import build_hello_crew


def test_crew_kickoff_with_mock_llm(mock_llm) -> None:
    """Build the hello crew with a MockLLM, kick it off, and assert
    the result is a HelloOutput with the canned message.
    """
    # --- Build --------------------------------------------------------------
    # build_hello_crew(llm=mock_llm) overrides the YAML `llm:` string
    # with the test double. The crew assembly (Agent + Task + Crew)
    # happens synchronously here — no LLM call until kickoff().
    crew = build_hello_crew(llm=mock_llm)

    # Sanity: the assembly is well-formed.
    assert len(crew.agents) == 1, "hello_crew must have exactly 1 agent"
    assert len(crew.tasks) == 1, "hello_crew must have exactly 1 task"

    # --- Kickoff -------------------------------------------------------------
    # The single async-style ReAct loop runs. MockLLM returns its
    # canned response on the first call, so this completes without
    # the retry storm we would see with a wrong-shaped mock.
    result = crew.kickoff()

    # --- Assert --------------------------------------------------------------
    # CrewAI parses the LLM's `Final Answer:` content (the JSON
    # string) against the task's `output_pydantic` (HelloOutput) and
    # exposes the parsed model on `result.pydantic`. This is the
    # contract that real workflows (Phase 1+) will rely on.
    assert result.pydantic is not None, (
        "CrewAI should have parsed the LLM output into result.pydantic. "
        "If this is None, check the mock's `Final Answer:` matches "
        "the output_pydantic schema."
    )
    assert isinstance(result.pydantic, HelloOutput), (
        f"result.pydantic should be a HelloOutput, got {type(result.pydantic).__name__}"
    )
    assert result.pydantic.message == "Hello from Jarvis", (
        f"Expected canned message, got {result.pydantic.message!r}"
    )
