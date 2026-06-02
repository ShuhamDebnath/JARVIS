"""Shared pytest fixtures and test doubles for the Jarvis test suite.

Anything reusable across multiple test files lives here. The two
big-ticket items for Phase 0a are:

  1. `MockLLM` — a `crewai.llm.LLM` subclass that returns a canned
     ReAct-style response without making a real API call. Required
     because Phase 0a is "env_valid: false" — no API keys are set
     in CI or on a fresh checkout, and tests that hit the real LLM
     would fail immediately.

  2. `tmp_state_dir` — monkeypatches `human_gate.STATE_DIR` /
     `STATE_FILE` to a `tmp_path` for the test's lifetime so the
     human_gate tests do not pollute the real
     `backend/state/runs.json`. Used by Step 9 (test_human_gate.py).

Why MockLLM subclasses LLM and not a hypothetical `BaseLLM`:
    The Phase 0a plan referenced "crewai.llm.BaseLLM" as the
    subclassing target, but crewai 0.86.0 does NOT export a
    `BaseLLM` class — only the concrete `LLM` class (which is just
    a regular Python class, not even a Pydantic model in this
    version's MRO). We subclass `LLM` directly. This is a finding
    worth noting: the Q1 locked decision in the plan referenced a
    class name that does not exist in the locked crewai version.

Why MockLLM returns a ReAct-formatted response:
    CrewAI's agent loop parses the LLM output as ReAct
    (`Thought:` / `Action:` / `Final Answer:`). The agent also
    expects the `Final Answer:` content to be parseable against the
    task's `output_pydantic` (here, `HelloOutput`). So the canned
    response is:

        Thought: I now can give a great answer
        Final Answer: {"message": "Hello from Jarvis"}

    and CrewAI extracts the JSON, validates it against HelloOutput,
    and stores the parsed model on `result.pydantic`.

Why we need a ReAct wrapper but NOT `from __future__ import annotations`:
    The `crewai.utilities.converter.generate_model_description`
    helper (called when a task with `output_pydantic=` kicks off)
    reads `model.__annotations__` and assumes each value is a real
    type. With `from __future__ import annotations` (PEP 563) the
    values are strings and the helper crashes with
    `AttributeError: 'str' object has no attribute '__name__'`. The
    hello contract deliberately omits the future-annotations import
    for this reason. See the comment in `backend/contracts/hello.py`.
"""

from __future__ import annotations

import pytest

from crewai.llm import LLM


# ---------------------------------------------------------------------------
# Test double: MockLLM
# ---------------------------------------------------------------------------

# The canned message the test asserts on. Centralised so the test and
# the mock agree on a single source of truth.
MOCK_LLM_MESSAGE: str = "Hello from Jarvis"


class MockLLM(LLM):
    """A `crewai.llm.LLM` subclass that returns a canned ReAct response.

    Used by `test_hello_crew.py` to exercise the hello-world crew
    WITHOUT making a real LLM API call. The Phase 0a rule is "no real
    LLM calls" (env_valid: false), and CI / fresh checkouts have no
    API keys set, so a real LLM would either fail to authenticate or
    blow through rate limits.

    The class:
        - subclasses the concrete `LLM` (no `BaseLLM` exists in
          crewai 0.86.0 — see conftest.py docstring),
        - calls `super().__init__(model="mock")` to pick up all the
          attributes CrewAI internals read (`stop`, `callbacks`,
          `temperature`, etc.) — see `CrewAgentExecutor.__init__`
          which reads `self.llm.stop`,
        - overrides `call()` to return a hard-coded ReAct response
          whose `Final Answer:` is the canned JSON,
        - overrides `supports_function_calling()` and
          `supports_stop_words()` to False / True respectively so
          CrewAI does not try a tool-calling code path (hello_agent
          has no tools).

    Args:
        message: The text to embed in the `Final Answer:` JSON.
            Defaults to `MOCK_LLM_MESSAGE`.
    """

    def __init__(self, message: str = MOCK_LLM_MESSAGE) -> None:
        # super().__init__ sets self.model, self.stop, self.callbacks,
        # self.temperature, etc. — the attributes CrewAI's
        # CrewAgentExecutor reads in its __init__.
        super().__init__(model="mock")
        self._message = message

    def call(self, messages, callbacks=None) -> str:  # type: ignore[override]
        """Return the canned ReAct response. Ignores `messages`."""
        # The ReAct format is what CrewAI parses. The agent expects:
        #   Thought: <reasoning>
        #   Final Answer: <final output>
        # Since hello_agent has no tools, it never tries to emit an
        # `Action:` line. The Final Answer content must be the JSON
        # that output_pydantic=HelloOutput expects.
        return (
            "Thought: I now can give a great answer\n"
            f'Final Answer: {{"message": "{self._message}"}}'
        )

    def supports_function_calling(self) -> bool:  # type: ignore[override]
        """hello_agent has no tools — never ask for function calling."""
        return False

    def supports_stop_words(self) -> bool:  # type: ignore[override]
        """Default behavior — matches crewai.llm.LLM default."""
        return True


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm() -> MockLLM:
    """Return a fresh MockLLM instance for the test.

    Use this fixture (not direct MockLLM()) when you need the
    test double and want pytest to show the dependency in the test
    signature for readability.
    """
    return MockLLM()


@pytest.fixture
def tmp_state_dir(tmp_path, monkeypatch):
    """Override `human_gate.STATE_DIR` and `STATE_FILE` to a temp path.

    Prevents human_gate tests (Step 9) from polluting the real
    `backend/state/runs.json` with test data. Mirrors the pattern
    recommended by pytest docs for module-level constants that
    point at filesystem locations.

    Returns:
        The `pathlib.Path` of the temp state dir (the same value as
        `tmp_path`, but typed for readability in the test).

    Note:
        The human_gate module is imported LAZILY inside the fixture
        so importing `conftest.py` does not eagerly import the
        entire backend package at pytest collection time. This keeps
        `pytest --collect-only` fast and avoids triggering
        `logger.basicConfig` during test discovery.
    """
    from backend.orchestrator import human_gate

    monkeypatch.setattr(human_gate, "STATE_DIR", tmp_path)
    monkeypatch.setattr(human_gate, "STATE_FILE", tmp_path / "runs.json")
    return tmp_path
