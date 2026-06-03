"""Per-department crew factories for Workflow 2 (Research → PRD).

Per ADR-0000 Q2 + ADR-0002:
  - Each department has its own `crewai.Crew(process=Process.hierarchical)`.
  - The Python CEO orchestrator (`backend/crews/jarvis_ceo.py` —
    Phase 1 deliverable P1.5) calls these factories to build the
    crews, then `.kickoff()`s them in sequence.
  - The department head is the `manager_agent` of its crew.
  - `memory=` is OMITTED on `Crew(...)` — relies on CrewAI default
    of `False` (per ADR-0002 Q4). Adding `memory=False` explicitly
    would be redundant AND would emit a deprecation warning on
    crewai>=0.95.
  - Cross-department state flows through explicit task `context:`,
    not through a shared ChromaDB collection.

Architectural locks applied here (do not relitigate):
  - Process.hierarchical + manager_agent=<dept_head> (ADR-0000 Q2)
  - 6 specialist tasks carry `async_execution: true` so they fan out
    in parallel under the manager (ADR-0002 Q1)
  - interpretation + consolidation stay sync — sync/async/sync sandwich
  - Output_pydantic is enforced by `backend/contracts/research.py`; the
    manual retry fallback (`run_research_crew_with_retry`) catches
    cases where the framework retry does not fire (ADR-0002 Q6)

Phase discipline:
  - This file builds the crew. It does NOT kick it off, write output
    files, call the human gate, or touch `runs.json`. Those are
    the CEO's job (P1.5).
  - This file does NOT define Pydantic contracts. Those live in
    `backend/contracts/` (one file per workflow per ADR-0002 Q3).
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Callable, Optional

import yaml
from crewai import Agent, Crew, Process, Task
from crewai_tools import SerperDevTool
from pydantic import BaseModel, ValidationError

from backend.contracts.research import (
    InterpretationValidationError,
    ResearchInterpretation,
)
from backend.tools.firecrawl_tool import FirecrawlTool
from backend.tools.pytrends_tool import PytrendsTool
from backend.tools.reddit_tool import RedditTool
from backend.tools.scoring_rubric_tool import ScoringRubricTool
from backend.tools.store_scraper import (
    AppStoreScraperTool,
    PlayStoreScraperTool,
)
from backend.utils.logger import get_logger

# Module logger — tagged `backend.crews.dept_crews` in jarvis.log.
log = get_logger(__name__)

# Path to the config directory, relative to this file:
#   backend/crews/dept_crews.py
#   -> backend/crews/      (parent)
#   -> backend/            (parent.parent)
#   -> backend/config/     (parent.parent / "config")
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_AGENTS_YAML = _CONFIG_DIR / "agents.yaml"
_TASKS_YAML = _CONFIG_DIR / "tasks.yaml"

# Tool-name string from agents.yaml -> BaseTool class.
# One entry per tool. Adding a new tool: write `backend/tools/<name>.py`
# exposing a `BaseTool` subclass named `<Name>Tool`, then add it here.
#
# SerperDevTool is a third-party tool from `crewai_tools` (a separate
# pip package from `crewai`). The other 6 are Jarvis BaseTool subclasses
# in `backend/tools/`. The lookup is keyed by the class name AS IT
# APPEARS IN `agents.yaml` — keep them identical.
_TOOL_REGISTRY: dict[str, type] = {
    "RedditTool": RedditTool,
    "AppStoreScraperTool": AppStoreScraperTool,
    "PlayStoreScraperTool": PlayStoreScraperTool,
    "SerperDevTool": SerperDevTool,
    "FirecrawlTool": FirecrawlTool,
    "PytrendsTool": PytrendsTool,
    "ScoringRubricTool": ScoringRubricTool,
}

# Per-department agent keys — the crew factories iterate over these to
# pull the right agents out of agents.yaml. The order is:
#   1. department head (manager_agent)
#   2. the one specialist that runs first (interpreter / scorer)
#   3. the fan-out specialists
# The order does NOT affect CrewAI execution — manager_agent decides
# task order at kickoff. We keep the list human-readable.
_RESEARCH_AGENT_KEYS: list[str] = [
    "research_director",          # manager_agent of research_dept_crew
    "research_interpreter",       # interpretation task (sync, runs first)
    "pain_point_hunter",          # 6 specialists (async, fan out)
    "competitor_mapper",
    "revenue_estimator",
    "gap_finder",
    "trend_validator",
    "audience_sizer",
]
_RESEARCH_TASK_KEYS: list[str] = [
    "research_interpretation_task",                # sync, runs first
    "research_pain_point_task",                    # async (6 in parallel)
    "research_competitor_mapping_task",
    "research_revenue_estimation_task",
    "research_gap_finding_task",
    "research_trend_validation_task",
    "research_audience_sizing_task",
    "research_consolidation_task",                 # sync, waits for all 6
]

_PRODUCT_AGENT_KEYS: list[str] = [
    "product_director",           # manager_agent of product_dept_crew
    "opportunity_scorer",         # runs first (sync)
    "prd_writer",                 # runs after human gate approves (sync)
]
_PRODUCT_TASK_KEYS: list[str] = [
    "product_opportunity_scoring_task",  # sync — CEO pauses for human gate after
    "product_prd_writing_task",          # sync — only runs if user approved
]

_INTELLIGENCE_AGENT_KEYS: list[str] = [
    "intelligence_director",      # manager_agent of intelligence_dept_crew
    "app_store_analyst",
]
_INTELLIGENCE_TASK_KEYS: list[str] = [
    "app_store_analysis_task",           # sync (first worker)
    "intelligence_consolidation_task",    # sync (consolidation)
]

# Max attempts for the manual Pydantic retry fallback (per ADR-0002 Q6).
# The first attempt counts as 1, so max_retries=3 means 1 + 2 retries.
# This number matches `max_retries: 3` in tasks.yaml. If the YAML
# default is ever changed, change this constant in lockstep.
_MAX_INTERPRETATION_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# YAML + Pydantic dotted-path resolvers
# ---------------------------------------------------------------------------
# Duplicated from hello_crew.py rather than imported — the helpers are
# small, have no business logic, and keeping them inlined avoids an
# import dependency from the smallest test crew to this Phase 1 file.
# Phase 7 refactor candidate: extract to `backend/crews/_yaml_loader.py`.
def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and assert it parsed to a dict.

    Fails loud with a clear message if the file is missing or not a
    dict (the latter would mean the YAML root is a list or scalar,
    which is a typo).

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
            f"YAML config not found: {path}. Per CLAUDE.md, agents/tasks "
            f"live ONLY in backend/config/*.yaml — create the file or "
            f"fix the path."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(
            f"YAML file {path} did not parse to a dict (got "
            f"{type(data).__name__}). Top-level must be a mapping keyed "
            f"by agent/task name."
        )
    return data


def _resolve_pydantic_class(dotted_path: str) -> type[BaseModel]:
    """Resolve a dotted Python path (e.g. 'backend.contracts.research.ResearchInterpretation') to its Pydantic class.

    Used to load `output_pydantic` from `backend/config/tasks.yaml`,
    which stores the value as a string for YAML-friendliness. The
    loader must never receive a `None` or empty string here — the
    caller (`_build_task`) checks for the key's presence first.

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
            f"Expected '<module>.<Class>' (e.g. "
            f"'backend.contracts.research.ResearchInterpretation')."
        )
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
        raise TypeError(
            f"Resolved {dotted_path!r} but it is not a Pydantic BaseModel "
            f"subclass (got {type(cls).__name__})."
        )
    log.debug("Resolved output_pydantic %s -> %s", dotted_path, cls.__name__)
    return cls


# ---------------------------------------------------------------------------
# Tool + agent + task builders
# ---------------------------------------------------------------------------
def _resolve_tools(tool_names: list[str]) -> list[Any]:
    """Resolve tool-name strings from agents.yaml to BaseTool instances.

    Per CLAUDE.md "How to Add a New Tool": tool names in agents.yaml
    are class names. We instantiate one of each here. Unknown names
    log a WARNING and are skipped — defensive against typos so the
    crew still builds (a missing tool is loud at kickoff, but a
    build-time crash would block every other agent in the crew).

    Args:
        tool_names: List of class-name strings from `agents.yaml`'s
            `tools:` field. May be empty.

    Returns:
        A list of BaseTool instances (one per recognised name). Order
        matches `tool_names` so the YAML ordering is preserved (the
        LLM sees tools in declaration order).
    """
    resolved: list[Any] = []
    for name in tool_names:
        cls = _TOOL_REGISTRY.get(name)
        if cls is None:
            log.warning(
                "Unknown tool %r in agents.yaml — skipping. Add it to "
                "_TOOL_REGISTRY in backend/crews/dept_crews.py to enable.",
                name,
            )
            continue
        resolved.append(cls())
    return resolved


def _build_agent(agent_key: str, agents_cfg: dict[str, Any], llm: Any = None) -> Agent:
    """Build one crewai.Agent from the YAML config.

    Per CLAUDE.md (CrewAI Specific rules): every agent definition
    lives in YAML, never in Python. The `llm:` line is read from
    the YAML verbatim. The `llm=` kwarg here is a TEST OVERRIDE
    ONLY — `tests/conftest.py::MockLLM` uses it to inject a fake
    LLM that returns canned JSON. Production callers (jarvis_ceo)
    leave it as `None`.

    Args:
        agent_key: Top-level key in agents.yaml (e.g. "research_director").
        agents_cfg: The parsed agents.yaml dict.
        llm: Optional override for the LLM. Pass `None` in production.

    Returns:
        A `crewai.Agent` instance ready to be added to a crew.

    Raises:
        KeyError: If `agent_key` is not in `agents_cfg`.
    """
    if agent_key not in agents_cfg:
        raise KeyError(
            f"agent_key={agent_key!r} not found in agents.yaml. "
            f"Available keys: {sorted(agents_cfg.keys())}"
        )
    # `dict(...)` so we can mutate the kwargs (the `llm` override and
    # the tool-name -> tool-instance swap) without mutating the
    # in-memory YAML parse.
    kwargs = dict(agents_cfg[agent_key])
    if llm is not None:
        # Test path — MockLLM subclasses crewai.llm.LLM, so it
        # bypasses the string -> LLM registry path that the YAML
        # value uses. Both forms are valid for `Agent(llm=...)`.
        kwargs["llm"] = llm
    # `tools:` in YAML is a list of class-name strings; resolve to
    # BaseTool instances.
    tool_names = kwargs.pop("tools", []) or []
    kwargs["tools"] = _resolve_tools(tool_names)

    kwargs["max_iter"] = 3

    log.debug(
        "agent %r built: role=%r tools=%s",
        agent_key, kwargs.get("role"), [t.name for t in kwargs["tools"]],
    )
    return Agent(**kwargs)


def _build_task(
    task_key: str,
    tasks_cfg: dict[str, Any],
    agent: Agent,
    built_tasks: Optional[dict[str, Task]] = None,
) -> Task:
    """Build one crewai.Task from the YAML config.

    Per tasks.yaml schema:
      - `agent:` is a STRING (the agent key in agents.yaml); we
        resolve to the Agent instance before calling Task().
      - `output_pydantic:` is a dotted Python path; we resolve to
        the Pydantic class so CrewAI can validate the LLM output
        against the schema at task completion time.
      - `context:` is a list of task-key strings. We resolve each
        string to the actual Task instance from `built_tasks`
        BEFORE calling Task(**kwargs). This is the load-bearing
        fix for the P1.4 build bug: CrewAI 0.86.0's Pydantic-v2
        `@model_validator(mode="before")` on Task
        (crewai/task.py:121-124) calls `process_config(values, cls)`
        and crashes with `AttributeError: 'str' object has no
        attribute 'get'` (crewai/utilities/config.py:19) if any
        item in `context` is a string instead of a Task instance.
        The Pydantic-v2 + CrewAI 0.86.0 contract is: `context` must
        be a list of Task instances at Task() construction time.
        Resolving up-front sidesteps the whole broken-coercion path.
      - `async_execution: true` is passed through verbatim — that
        is what triggers the 6 research specialists to fan out
        in parallel (per ADR-0002 Q1).
      - `max_retries:` (if present) is passed through verbatim.
        Per ADR-0002 Q6, CrewAI 0.86.0 does NOT actually honour
        it (the field is not in Task.model_fields), so the
        Python retry fallback in `run_research_crew_with_retry`
        is the load-bearing retry mechanism.

    Args:
        task_key: Top-level key in tasks.yaml (e.g. "research_pain_point_task").
        tasks_cfg: The parsed tasks.yaml dict.
        agent: The Agent instance this task should run on.
        built_tasks: Registry of already-built Task instances keyed
            by task_key. Used to resolve `context:` string names to
            actual Task instances BEFORE Task(**kwargs) runs. The
            calling factory MUST pass this — populate it
            incrementally inside the build loop so that a task with
            `context: [<earlier_task_key>]` finds its dependency.
            If a context string is NOT in this registry, the build
            fails loud with KeyError (typically a YAML/ordering
            bug, or a cross-department context reference that
            belongs in the CEO orchestrator's wiring, not here).

    Returns:
        A `crewai.Task` instance ready to be added to a crew.

    Raises:
        KeyError: If `task_key` is not in `tasks_cfg`, or if a
            `context:` string references a task not yet in
            `built_tasks` (i.e. either declared before its
            dependency in the build order, or referencing a
            task outside this crew).
    """
    if task_key not in tasks_cfg:
        raise KeyError(
            f"task_key={task_key!r} not found in tasks.yaml. "
            f"Available keys: {sorted(tasks_cfg.keys())}"
        )
    kwargs = dict(tasks_cfg[task_key])
    # `agent:` in YAML is a STRING. We already have the Agent instance
    # in hand, so we drop the string and pass the instance via the
    # `agent=` kwarg below.
    kwargs.pop("agent", None)
    # `output_pydantic:` (when present) is a dotted string. Resolve to
    # the real Pydantic class.
    if "output_pydantic" in kwargs and kwargs["output_pydantic"]:
        kwargs["output_pydantic"] = _resolve_pydantic_class(kwargs["output_pydantic"])
    # P1.4 fix: resolve `context:` from a list of task-key strings to
    # a list of Task instances BEFORE calling Task(**kwargs). The
    # `built_tasks` registry is populated incrementally in the
    # factory's build loop, so a task that depends on an earlier
    # task will find it in the registry. If a string is missing
    # from the registry, the build is broken (cross-dept ref or
    # ordering bug) and we fail loud with a clear message.
    if "context" in kwargs and kwargs["context"]:
        if built_tasks is None:
            # Defensive: the factory should always pass built_tasks.
            # If a caller forgets, we can't safely resolve, so fail
            # loud instead of silently producing a broken crew.
            raise ValueError(
                f"task {task_key!r} has context={kwargs['context']!r} but "
                f"no built_tasks registry was passed to _build_task. "
                f"The factory must pass built_tasks=task_dict so context "
                f"can be resolved to Task instances (CrewAI 0.86.0 Pydantic "
                f"v2 contract — see P1.4 ADR).",
            )
        raw_context = list(kwargs["context"])
        resolved: list[Task] = []
        for c in raw_context:
            if isinstance(c, Task):
                # Already a Task (e.g. test double injected it). Pass through.
                resolved.append(c)
                continue
            if not isinstance(c, str):
                # Defensive: a non-string, non-Task object is a YAML
                # typo we can't reason about.
                raise TypeError(
                    f"task {task_key!r} context item {c!r} is {type(c).__name__}, "
                    f"expected str (task_key) or Task. Fix tasks.yaml.",
                )
            if c not in built_tasks:
                raise KeyError(
                    f"task {task_key!r} context references {c!r} which has "
                    f"not been built yet. Either: (a) the dependent task "
                    f"is declared AFTER {task_key!r} in the task-key list "
                    f"(_RESEARCH_TASK_KEYS / _PRODUCT_TASK_KEYS) — re-order "
                    f"so dependencies come first, or (b) the context "
                    f"references a task in a DIFFERENT crew (cross-department "
                    f"wiring is the CEO orchestrator's job, not this "
                    f"factory — see ADR-0000 Q3).",
                )
            resolved.append(built_tasks[c])
        kwargs["context"] = resolved
    log.debug(
        "task %r built: agent=%r async=%s context=%s",
        task_key, agent.role,
        kwargs.get("async_execution", False),
        kwargs.get("context", []),
    )
    return Task(**kwargs, agent=agent)


# ---------------------------------------------------------------------------
# Public factory: research_dept_crew
# ---------------------------------------------------------------------------
def build_research_dept_crew(
    llm: Any = None,
    task_callback: Any = None,
) -> Crew:
    """Build the research_dept_crew from YAML config.

    Returns a `crewai.Crew` with:
      - 8 agents: research_director (manager_agent) +
        research_interpreter + 6 specialists
      - 8 tasks: interpretation (sync) + 6 specialists (async) +
        consolidation (sync)
      - process = Process.hierarchical
      - manager_agent = research_director
      - NO `memory=` arg — relies on CrewAI default of False
        (per ADR-0002 Q4)

    Per ADR-0002:
      - The 6 specialist tasks have `async_execution: true` so they
        fan out in parallel under the manager
      - interpretation and consolidation are sync — the
        sync/async/sync sandwich is the natural shape
      - Each specialist's `context:` lists
        research_interpretation_task (so all 6 see the same
        interpretation JSON)
      - consolidation's `context:` lists all 6 specialist tasks
        (so it waits for all of them to finish)

    Args:
        llm: Optional LLM override (test path — MockLLM).
            Production callers pass `None`.
        task_callback: Optional callback fired at each task
            boundary. The cost_guard (P1.11) uses this to count
            tokens and enforce the 200k cap (per ADR-0000 Q14).

    Returns:
        A `crewai.Crew` ready to `.kickoff()`. NOT kicked off here
        — the CEO orchestrator (P1.5) is responsible for kickoff,
        human-gate pauses, and output-file writing.
    """
    agents_cfg = _load_yaml(_AGENTS_YAML)
    tasks_cfg = _load_yaml(_TASKS_YAML)

    # Build all 8 agents. Order does not matter for CrewAI; we
    # build them in declaration order so log lines are stable.
    agents: dict[str, Agent] = {
        key: _build_agent(key, agents_cfg, llm=llm)
        for key in _RESEARCH_AGENT_KEYS
    }

    # Build all 8 tasks into a dict incrementally, threading
    # `task_dict` into _build_task as it grows so each task can
    # resolve its `context:` string names to actual Task instances
    # BEFORE the Task(**kwargs) call. We cannot pass `context=` as
    # a list of task-key strings directly to the Task constructor
    # — the field is typed `Optional[List["Task"]]`, so Pydantic
    # rejects raw strings and the broken coercion path crashes
    # with `AttributeError: 'str' object has no attribute 'get'`
    # deep inside crewai.utilities.config.process_config.
    # (CrewAI 0.86.0 + Pydantic v2 quirk — see P1.4 ADR.)
    # The task ordering in _RESEARCH_TASK_KEYS is therefore
    # load-bearing: research_interpretation_task must be first
    # (no context, runs first), then the 6 specialists (each
    # depends on the interpretation), then research_consolidation_task
    # (depends on all 6 specialists).
    task_dict: dict[str, Task] = {}
    for task_key in _RESEARCH_TASK_KEYS:
        task_cfg = tasks_cfg[task_key]
        agent_key = task_cfg["agent"]
        task_dict[task_key] = _build_task(
            task_key, tasks_cfg, agents[agent_key],
            built_tasks=task_dict,
        )

    # Defensive double-check: re-wire `task.context` from the YAML
    # after construction. With the _build_task fix above, context
    # is already resolved to Task instances at this point — this
    # loop is idempotent (overwrites with the same instances) and
    # acts as a safety net if _build_task is ever called without
    # `built_tasks=`. Also produces a useful DEBUG log line for
    # observability when `context` is wired.
    for task_key, task in task_dict.items():
        context_keys = tasks_cfg[task_key].get("context", []) or []
        if context_keys:
            task.context = [task_dict[k] for k in context_keys]
            log.debug(
                "task %r context wired: %s -> %s",
                task_key, context_keys,
                [t.name for t in task.context],
            )
    tasks: list[Task] = list(task_dict.values())

    # Per ADR-0002 Q4: NO `memory=` kwarg. CrewAI default is False,
    # and adding `memory=False` would be redundant. Adding
    # `memory=True` would (a) reintroduce the per-run contamination
    # failure mode that ADR-0000 Q2's per-dept isolation was meant
    # to prevent, and (b) trigger deprecation warnings on crewai>=0.95.
    #
    # CrewAI 0.86.0 contract: when `process=Process.hierarchical`
    # AND `manager_agent=` is set, the manager agent MUST NOT also
    # appear in the `agents=` list — Pydantic v2 raises
    # `ValidationError: Manager agent should not be included in
    # agents list` otherwise. The manager is the head of the
    # hierarchy; the `agents` list is the workers it delegates to.
    # (Found while fixing P1.4 — the AttributeError on Task
    # construction masked this; once Task() builds, Crew()
    # validation surfaces it.)
    _manager_key = "research_director"
    worker_agents = [a for k, a in agents.items() if k != _manager_key]
    crew_kwargs: dict[str, Any] = {
        "agents": worker_agents,
        "tasks": tasks,
        "process": Process.hierarchical,
        "manager_agent": agents[_manager_key],
        "verbose": True,
    }
    if task_callback is not None:
        # Wired here so cost_guard.log_call() can observe per-task
        # token usage. See backend/utils/cost_guard.py.
        crew_kwargs["task_callback"] = task_callback

    crew = Crew(**crew_kwargs)
    log.info(
        "research_dept_crew built: %d workers, %d tasks, "
        "process=Process.hierarchical, manager_agent=research_director "
        "(excluded from workers list per CrewAI 0.86.0 contract), "
        "memory=OMITTED (CrewAI default False)",
        len(worker_agents), len(tasks),
    )
    return crew


# ---------------------------------------------------------------------------
# Public factory: product_dept_crew
# ---------------------------------------------------------------------------
def build_product_dept_crew(
    llm: Any = None,
    task_callback: Any = None,
) -> Crew:
    """Build the product_dept_crew from YAML config.

    Returns a `crewai.Crew` with:
      - 3 agents: product_director (manager_agent) +
        opportunity_scorer + prd_writer
      - 2 tasks: scoring (sync) + prd_writing (sync)
      - process = Process.hierarchical
      - manager_agent = product_director
      - NO `memory=` arg — relies on CrewAI default of False
        (per ADR-0002 Q4)

    The CEO orchestrator (P1.5) is responsible for the human-gate
    pause between the two tasks (per ADR-0000 Q3). The crew itself
    is unaware of the gate — it just runs whatever the manager
    decides to delegate. The CEO does:
      1. kickoff(product_dept_crew, inputs={"research_brief": ...})
      2. grab the opportunity_scorer task output
      3. await human_gate.ask_user("Generate full PRD? (yes/no)")
      4. on "yes", continue (the prd_writing task is already
         queued in the crew and will run); on "no", kill the
         crew or set a flag to skip the prd_writing task.

    Args:
        llm: Optional LLM override (test path — MockLLM).
            Production callers pass `None`.
        task_callback: Optional callback fired at each task
            boundary. Wired to cost_guard in the CEO.

    Returns:
        A `crewai.Crew` ready to `.kickoff()`.
    """
    agents_cfg = _load_yaml(_AGENTS_YAML)
    tasks_cfg = _load_yaml(_TASKS_YAML)

    agents: dict[str, Agent] = {
        key: _build_agent(key, agents_cfg, llm=llm)
        for key in _PRODUCT_AGENT_KEYS
    }

    # Same context-resolution pattern as research_dept_crew — see the
    # longer comment in build_research_dept_crew for the CrewAI
    # 0.86.0 Pydantic quirk that forces this. After P1.15 the product
    # tasks reference only intra-dept context (prd_writing depends on
    # opportunity_scoring; scoring has no context). The research_brief
    # reaches this crew through the CEO's `kickoff(inputs=...)` call,
    # not via task context (per ADR-0000 Q3).
    task_dict: dict[str, Task] = {}
    for task_key in _PRODUCT_TASK_KEYS:
        task_cfg = tasks_cfg[task_key]
        agent_key = task_cfg["agent"]
        task_dict[task_key] = _build_task(
            task_key, tasks_cfg, agents[agent_key],
            built_tasks=task_dict,
        )

    # Defensive double-check — same rationale as in
    # build_research_dept_crew.
    for task_key, task in task_dict.items():
        context_keys = tasks_cfg[task_key].get("context", []) or []
        if context_keys:
            task.context = [task_dict[k] for k in context_keys]
    tasks: list[Task] = list(task_dict.values())

    # CrewAI 0.86.0 contract (same as research_dept_crew): the
    # manager agent MUST NOT appear in the `agents=` list when
    # `process=Process.hierarchical` + `manager_agent=` are set.
    # Exclude product_director from the workers list.
    _manager_key = "product_director"
    worker_agents = [a for k, a in agents.items() if k != _manager_key]
    crew_kwargs: dict[str, Any] = {
        "agents": worker_agents,
        "tasks": tasks,
        "process": Process.hierarchical,
        "manager_agent": agents[_manager_key],
        "verbose": True,
    }
    if task_callback is not None:
        crew_kwargs["task_callback"] = task_callback

    crew = Crew(**crew_kwargs)
    log.info(
        "product_dept_crew built: %d workers, %d tasks, "
        "process=Process.hierarchical, manager_agent=product_director "
        "(excluded from workers list per CrewAI 0.86.0 contract), "
        "memory=OMITTED (CrewAI default False)",
        len(worker_agents), len(tasks),
    )
    return crew


# ---------------------------------------------------------------------------
# Manual Pydantic retry fallback (per ADR-0002 Q6)
# ---------------------------------------------------------------------------
# CrewAI 0.86.0 does NOT have a `max_retries` field on Task (verified
# via `Task.model_fields` on the installed version — the field is
# missing from the Pydantic model). The `max_retries: 3` in tasks.yaml
# is therefore aspirational — the framework does not enforce it.
#
# So the retry happens in Python: kickoff the crew, check whether
# research_interpretation_task produced a valid ResearchInterpretation,
# and if not, re-run with the Pydantic error message re-injected into
# the interpreter's prompt. After _MAX_INTERPRETATION_ATTEMPTS
# unsuccessful attempts, raise InterpretationValidationError so the
# CEO orchestrator (P1.5) can write the failed_interpretation_{run_id}.md
# transcript and set runs.json status=failed.
def _extract_interpretation(crew_output: Any) -> Optional[ResearchInterpretation]:
    """Pull the research_interpretation_task's parsed output from a crew result.

    Per P1.15 Action 3: built-in CrewAI Pydantic validation is DISABLED
    to avoid the MiniMax "Instructor does not support multiple tool
    calls" error. We now manually parse the `.raw` string.

    Args:
        crew_output: The return value of `crew.kickoff()`.

    Returns:
        The validated `ResearchInterpretation` instance, or `None`
        if the task did not produce a parseable JSON matching the
        schema.
    """
    if crew_output is None or not hasattr(crew_output, "tasks_output"):
        return None

    for to in crew_output.tasks_output:
        # Task name check must match tasks.yaml key exactly.
        if getattr(to, "name", "") == "research_interpretation_task":
            raw_output = getattr(to, "raw", "")
            if not raw_output:
                log.warning("_extract_interpretation: Task output is empty.")
                return None

            # Clean potential markdown block wrappers (MiniMax sometimes
            # includes them even if told not to).
            cleaned = raw_output.strip()
            if cleaned.startswith("```"):
                # Handle ```json ... ``` or just ``` ... ```
                lines = cleaned.splitlines()
                if len(lines) > 2:
                    # Remove first and last lines (fences)
                    cleaned = "\n".join(lines[1:-1]).strip()

            try:
                parsed_json = json.loads(cleaned)
                return ResearchInterpretation.model_validate(parsed_json)
            except (json.JSONDecodeError, ValidationError) as e:
                log.warning(
                    "_extract_interpretation: Manual parsing/validation "
                    "failed: %s. Raw output: %r", e, raw_output,
                )
                return None

    return None


def run_research_crew_with_retry(
    crew_factory: Callable[[], Crew],
    inputs: dict[str, Any],
    max_retries: int = _MAX_INTERPRETATION_ATTEMPTS,
) -> Any:
    """Kickoff the research_dept_crew with manual Pydantic retry.

    Per ADR-0002 Q6: `output_pydantic` does not retry on its own in
    CrewAI 0.86.0 — we have to do it in Python. This function:
      1. Calls `crew_factory()` to build a FRESH `Crew` instance.
      2. Calls `crew.kickoff(inputs=...)`.
      3. Extracts the `ResearchInterpretation` from the result.
      4. If valid, returns the result.
      5. If not, re-runs with a brand-new crew on the next attempt.
      6. After `max_retries` unsuccessful attempts, raises
         `InterpretationValidationError`.

    The CEO orchestrator (P1.5) catches that exception, writes the
    failed_interpretation_{run_id}.md transcript, and sets runs.json
    status=failed.

    P1.15 Action 2 fix — factory pattern, not pre-built crew:
        CrewAI 0.86.0 has a known stateful-crew bug: calling
        `crew.kickoff()` more than once on the SAME hierarchical
        crew object mutates its internal `manager_agent` state and
        produces `ValidationError: Manager agent should not have
        tools` on attempt 2+. The previous signature took a
        pre-built `Crew`; the new one takes a zero-arg factory and
        calls it inside the loop so attempt 1, 2, 3 each get a
        pristine Crew with no cross-attempt state. The
        `crew_factory` argument is typically just
        `build_research_dept_crew` (which has all-optional kwargs).

    Args:
        crew_factory: A zero-argument callable that returns a fresh
            `crewai.Crew` instance. In production this is
            `build_research_dept_crew` (all kwargs defaulted). Build
            errors are deterministic and surface immediately — no
            retry budget burned on a YAML/Pydantic typo.
        inputs: The dict passed to `crew.kickoff(inputs=...)`. For
            Workflow 2, the only input is `{"app_idea": "<user's
            one-sentence app idea>"}` (P1.15 Action 1: was `idea`
            before — renamed to match the `{app_idea}` placeholder
            in `research_interpretation_task`).
        max_retries: Total attempts. Default 3 (1 initial + 2
            retries). Capped at 3 per ADR-0002 Q6.

    Returns:
        The `crew.kickoff()` result on success (the last attempt's
        result, with a valid `ResearchInterpretation`).

    Raises:
        InterpretationValidationError: After all `max_retries`
            attempts fail to produce a valid ResearchInterpretation.
        Exception: Any build error from `crew_factory()` is
            re-raised as-is (no retry — build is deterministic). The
            CEO catches it and writes a `research_crew_build_failed`
            status.

    Notes:
        - The retry-loop transcript (every prompt + every response
          across all attempts) is NOT captured by this function.
          The CEO is responsible for that breadcrumb (writing
          `backend/output/failed_interpretation_{run_id}.md` on
          raise). Phase 7 upgrade: hook into CrewAI's
          `step_callback` to capture per-attempt transcripts.
        - This function is the only place in dept_crews.py that
          actually runs the crew. The factories are pure builders.
    """
    attempt = 0
    last_crew_output: Any = None
    last_error: Optional[str] = None
    # Loosened to `list[Any]` (was `list[dict]`) because the
    # two append sites pass heterogeneous shapes:
    #   1. `errors.append(e.errors())` — `e.errors()` is typed
    #      `list[ErrorDetails]` by Pydantic v2.
    #   2. `errors.append([{"msg": last_error}])` — a list-wrapped
    #      single-key dict for the no-Pydantic-error case.
    # The CEO post-mortem serialises these to JSON in
    # failed_interpretation_{run_id}.md, so structural variance
    # here is acceptable — we just need a permissive container.
    transcripts: list[dict[str, Any]] = []   # one {attempt, error} dict per failed attempt
    errors: list[Any] = []                  # one Pydantic error list per failed attempt

    while attempt < max_retries:
        attempt += 1
        log.info(
            "run_research_crew_with_retry: attempt %d / %d",
            attempt, max_retries,
        )
        # Build a brand-new Crew for every attempt. P1.15 Action 2
        # fix — see the docstring for the CrewAI 0.86.0
        # "Manager agent should not have tools" stateful-crew
        # bug rationale. Build errors are deterministic, so we
        # surface them immediately (no retry budget burned on a
        # YAML/Pydantic typo).
        try:
            crew = crew_factory()
        except Exception as e:
            log.error(
                "run_research_crew_with_retry: attempt %d — crew_factory() "
                "raised (build is deterministic, not retrying): %s",
                attempt, e, exc_info=True,
            )
            raise

        try:
            last_crew_output = crew.kickoff(inputs=inputs)
        except ValidationError as e:
            # Output_pydantic validation failed inside CrewAI —
            # the framework raised rather than returning a result.
            last_error = str(e)
            errors.append(e.errors())
            transcripts.append({"attempt": attempt, "error": last_error})
            log.warning(
                "run_research_crew_with_retry: attempt %d raised "
                "ValidationError: %s",
                attempt, last_error,
            )
            continue
        except Exception as e:
            # Other CrewAI failure (LLM error, tool crash, etc.).
            # Per CLAUDE.md "Error Handling": log at ERROR with
            # traceback and return a graceful fallback — but here
            # we ARE the fallback, so we surface the error to the
            # CEO which decides what to do.
            log.error(
                "run_research_crew_with_retry: attempt %d failed: %s",
                attempt, e, exc_info=True,
            )
            raise

        # Try to extract the validated Pydantic result.
        interpretation = _extract_interpretation(last_crew_output)
        if interpretation is not None:
            log.info(
                "run_research_crew_with_retry: attempt %d produced a "
                "valid ResearchInterpretation (category=%s, keywords=%d).",
                attempt, interpretation.app_category,
                len(interpretation.search_keywords),
            )
            return last_crew_output

        # Interpretation task did not produce a valid Pydantic result.
        # Could be: output_pydantic was None, validation silently
        # failed, or the task did not run at all.
        last_error = (
            "research_interpretation_task did not produce a valid "
            "ResearchInterpretation. Check jarvis.log for the LLM "
            "output and any ValidationError on the task."
        )
        errors.append([{"msg": last_error}])
        transcripts.append({"attempt": attempt, "error": last_error})
        log.warning(
            "run_research_crew_with_retry: attempt %d — %s",
            attempt, last_error,
        )

    # All attempts failed. Raise so the CEO can write the post-mortem.
    log.error(
        "run_research_crew_with_retry: all %d attempts failed. "
        "Raising InterpretationValidationError for the CEO to handle.",
        max_retries,
    )
    # We need a run_id for the exception. The CEO will overwrite
    # this with the real one when it catches the exception — for
    # now we use a placeholder so the exception is always
    # constructible. (See InterpretationValidationError.__init__.)
    raise InterpretationValidationError(
        run_id="<unassigned — CEO will overwrite>",
        errors=errors,
        transcripts=transcripts,
    )


# ---------------------------------------------------------------------------
# Public factory: intelligence_dept_crew
# ---------------------------------------------------------------------------
def build_intelligence_dept_crew(
    llm: Any = None,
    task_callback: Any = None,
) -> Crew:
    """Build the intelligence_dept_crew from YAML config.

    Returns a `crewai.Crew` with:
      - 2 agents: intelligence_director (manager_agent) +
        app_store_analyst
      - 2 tasks: analysis (sync) + consolidation (sync)
      - process = Process.hierarchical
      - manager_agent = intelligence_director
    """
    agents_cfg = _load_yaml(_AGENTS_YAML)
    tasks_cfg = _load_yaml(_TASKS_YAML)

    agents: dict[str, Agent] = {
        key: _build_agent(key, agents_cfg, llm=llm)
        for key in _INTELLIGENCE_AGENT_KEYS
    }

    task_dict: dict[str, Task] = {}
    for task_key in _INTELLIGENCE_TASK_KEYS:
        task_cfg = tasks_cfg[task_key]
        agent_key = task_cfg["agent"]
        task_dict[task_key] = _build_task(
            task_key, tasks_cfg, agents[agent_key],
            built_tasks=task_dict,
        )

    # Re-wire context explicitly (idempotent safety).
    for task_key, task in task_dict.items():
        context_keys = tasks_cfg[task_key].get("context", []) or []
        if context_keys:
            task.context = [task_dict[k] for k in context_keys]

    tasks: list[Task] = list(task_dict.values())

    _manager_key = "intelligence_director"
    worker_agents = [a for k, a in agents.items() if k != _manager_key]
    crew_kwargs: dict[str, Any] = {
        "agents": worker_agents,
        "tasks": tasks,
        "process": Process.hierarchical,
        "manager_agent": agents[_manager_key],
        "verbose": True,
    }
    if task_callback is not None:
        crew_kwargs["task_callback"] = task_callback

    crew = Crew(**crew_kwargs)
    log.info(
        "intelligence_dept_crew built: %d workers, %d tasks, "
        "process=Process.hierarchical, manager_agent=intelligence_director, "
        "memory=OMITTED (CrewAI default False)",
        len(worker_agents), len(tasks),
    )
    return crew
