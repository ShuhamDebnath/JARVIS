"""Hello-world crew assembly (Phase 0a).

This is the smallest possible CrewAI crew that exercises the full
plumbing we will rely on in Phase 1+:

  YAML config (agents.yaml + tasks.yaml)
    -> resolve output_pydantic dotted path to a Pydantic class
    -> build one crewai.Agent
    -> build one crewai.Task with output_pydantic=<class>
    -> assemble into a crewai.Crew
    -> return the crew

The single-agent test crew uses `Process.sequential` rather than the
mandatory `Process.hierarchical` for multi-agent crews (see CLAUDE.md
"Agent Hierarchy"). The exception is documented inline below — the
moment a second agent lands in this file, the process must flip back
to hierarchical.

Per CLAUDE.md (CrewAI Specific): no LLM string is hardcoded in
Python — `llm:` is read from `backend/config/agents.yaml`. The
`llm=` kwarg on `build_hello_crew` is a TEST OVERRIDE ONLY (used by
`tests/conftest.py::MockLLM`); production code never calls this with
a custom llm.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Optional

import yaml
from crewai import Agent, Crew, Process, Task
from pydantic import BaseModel

from backend.contracts.hello import HelloOutput
from backend.utils.logger import get_logger

# Module logger — tagged `backend.crews.hello_crew` in jarvis.log.
log = get_logger(__name__)

# Path to the config directory, relative to this file:
#   backend/crews/hello_crew.py
#   -> backend/crews/      (parent)
#   -> backend/            (parent.parent)
#   -> backend/config/     (parent.parent / "config")
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_AGENTS_YAML = _CONFIG_DIR / "agents.yaml"
_TASKS_YAML = _CONFIG_DIR / "tasks.yaml"


def _resolve_pydantic_class(dotted_path: str) -> type[BaseModel]:
    """Resolve a dotted Python path (e.g. 'backend.contracts.hello.HelloOutput') to its Pydantic class.

    Used to load `output_pydantic` from `backend/config/tasks.yaml`,
    which stores the value as a string for YAML-friendliness. The
    loader must never receive a `None` or empty string here — the
    caller (build_hello_crew) pops the key from the YAML dict and
    raises KeyError if it is missing.

    Args:
        dotted_path: A fully-qualified Python path in `<module>.<Class>`
            form. Module must be importable from sys.path.

    Returns:
        The resolved Pydantic BaseModel subclass.

    Raises:
        ValueError: If `dotted_path` is not in `<module>.<class>` form.
        ImportError: If the module cannot be imported.
        AttributeError: If the class name is not in the module.
        TypeError: If the resolved object is not a BaseModel subclass.
    """
    module_path, _, class_name = dotted_path.rpartition(".")
    if not module_path or not class_name:
        raise ValueError(
            f"Invalid dotted path for output_pydantic: {dotted_path!r}. "
            f"Expected '<module>.<Class>' (e.g. 'backend.contracts.hello.HelloOutput')."
        )
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
        raise TypeError(
            f"Resolved {dotted_path!r} but it is not a Pydantic BaseModel subclass "
            f"(got {type(cls).__name__})."
        )
    log.debug("Resolved output_pydantic %s -> %s", dotted_path, cls.__name__)
    return cls


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and assert it parsed to a dict.

    Helper for loading `agents.yaml` and `tasks.yaml`. Fails loud with
    a clear message if the file is missing or not a dict (the latter
    would mean the YAML root is a list or scalar, which is a typo).

    Args:
        path: Absolute path to the YAML file.

    Returns:
        The parsed dict (top-level mapping).

    Raises:
        FileNotFoundError: If `path` does not exist.
        yaml.YAMLError: If the file is malformed.
        ValueError: If the parsed YAML is not a dict.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"YAML config not found: {path}. "
            f"Per CLAUDE.md, agents/tasks live ONLY in backend/config/*.yaml — "
            f"create the file or fix the path."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(
            f"YAML file {path} did not parse to a dict (got {type(data).__name__}). "
            f"Top-level must be a mapping keyed by agent/task name."
        )
    return data


def build_hello_crew(llm: Any = None) -> Crew:
    """Build the hello-world crew from YAML config.

    Loads `backend/config/agents.yaml` and `backend/config/tasks.yaml`,
    instantiates one Agent + one Task, and returns a Crew wired with
    `Process.sequential` (single-agent exception to the
    `Process.hierarchical` rule — see inline comment in the function
    body).

    Args:
        llm: Optional override for the LLM. Used by tests
            (`tests/conftest.py::MockLLM`) to inject a fake LLM that
            returns canned JSON. Production callers leave this as
            `None` so the LLM string from `agents.yaml` flows through
            unchanged.

    Returns:
        A `crewai.Crew` ready to `.kickoff()`. The kickoff result for
        this crew will have a `.pydantic` attribute of type
        `HelloOutput` (CrewAI parses the LLM string output against
        the task's `output_pydantic` automatically).
    """
    agents_cfg = _load_yaml(_AGENTS_YAML)
    tasks_cfg = _load_yaml(_TASKS_YAML)

    # --- Agent -------------------------------------------------------------
    # `dict(...)` so we can mutate the kwargs (the `llm` override) without
    # mutating the in-memory YAML parse (defensive — same dict may be
    # passed to multiple builds if we ever cache it).
    agent_kwargs = dict(agents_cfg["hello_agent"])
    if llm is not None:
        # Test path — MockLLM is a crewai.llm.BaseLLM subclass, so it
        # bypasses the string->LLM registry path that the YAML value
        # uses. Both forms are valid for `Agent(llm=...)`.
        agent_kwargs["llm"] = llm
    agent = Agent(**agent_kwargs)
    log.info(
        "hello_agent built: role=%r llm=%r allow_delegation=%s",
        agent.role, agent_kwargs.get("llm"), agent_kwargs.get("allow_delegation"),
    )

    # --- Task --------------------------------------------------------------
    # `agent:` in tasks.yaml is a STRING (the agent KEY in agents.yaml)
    # — kept as a string for YAML-friendliness and to make the agent
    # wiring human-readable in the config. The Task constructor wants
    # the Agent INSTANCE, not the key, so we pop the key and pass the
    # instance explicitly via the `agent=` kwarg below.
    # `output_pydantic` is also a dotted string in YAML; resolve it
    # to a real Pydantic class so CrewAI can validate the LLM output
    # against the schema at task completion time.
    task_kwargs = dict(tasks_cfg["hello_task"])
    agent_ref: str = task_kwargs.pop("agent")
    pydantic_path: str = task_kwargs.pop("output_pydantic")
    pydantic_cls = _resolve_pydantic_class(pydantic_path)
    task = Task(**task_kwargs, output_pydantic=pydantic_cls, agent=agent)
    log.info(
        "hello_task built: agent_key=%r -> %r, output_pydantic=%s",
        agent_ref, agent.role, pydantic_path,
    )

    # --- Crew --------------------------------------------------------------
    # CLAUDE.md "Agent Hierarchy" mandates Process.hierarchical for any
    # multi-agent crew. The hello-world crew has exactly ONE agent, so
    # Process.sequential is the documented exception. If a second agent
    # is ever added here, flip process=Process.hierarchical AND add a
    # manager_llm= line. Workflows 1+ (Phase 1) use hierarchical from
    # day one.
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,  # single-agent exception — see comment above
        verbose=True,
    )
    log.info("hello_crew built: 1 agent, 1 task, process=Process.sequential (single-agent exception)")
    return crew
