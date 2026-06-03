"""Per-department crew factories for Workflow 3 (Social Media Content Engine).

Per ADR-0003:
  - Phase 3a: `content_dept_crew` produces platform-specific viral content
    briefs. `automation_dept_crew` is NOT invoked. Skyvern is not installed.
  - Phase 3b: `automation_dept_crew` handles Skyvern auto-posting.

Architectural locks applied here:
  - Process.hierarchical + manager_agent=<dept_head> (ADR-0000 Q2)
  - 4 specialist tasks carry `async_execution: true` so they fan out
    in parallel under the manager
  - Brief consolidation task is sync — waits for all 4 to complete
  - NO `memory=` kwarg on `Crew(...)` — relies on CrewAI default of False
    (per ADR-0002 Q4)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, Crew, Process, Task

from backend.utils.logger import get_logger

log = get_logger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_AGENTS_YAML = _CONFIG_DIR / "agents.yaml"
_TASKS_YAML = _CONFIG_DIR / "tasks.yaml"

_CONTENT_AGENT_KEYS = [
    "content_director",      # manager_agent of content_dept_crew
    "trend_scanner",         # 4 specialists (async, fan out)
    "trend_analyser",
    "viral_idea_generator",
    "community_angle_agent",
]
_CONTENT_TASK_KEYS = [
    "trend_scanning_task",           # sync (runs first)
    "trend_analysis_task",           # async (4 in parallel)
    "viral_idea_generation_task",    # async
    "community_angle_task",          # async
    "brief_consolidation_task",      # sync (waits for all 4)
]

_AUTOMATION_AGENT_KEYS = [
    "automation_director",  # manager_agent (not yet in agents.yaml — stub)
    "social_poster",         # Phase 3b only
]
_AUTOMATION_TASK_KEYS = [
    "social_posting_task",   # Phase 3b only
]


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and assert it parsed to a dict."""
    if not path.exists():
        raise FileNotFoundError(f"YAML config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML file {path} did not parse to a dict")
    return data


def _resolve_tools(tool_names: list[str]) -> list[Any]:
    """Resolve tool-name strings from agents.yaml to BaseTool instances."""
    from crewai_tools import SerperDevTool
    from backend.tools.firecrawl_tool import FirecrawlTool
    from backend.tools.pytrends_tool import PytrendsTool
    from backend.tools.reddit_tool import RedditTool
    from backend.tools.scoring_rubric_tool import ScoringRubricTool
    from backend.tools.store_scraper import AppStoreScraperTool, PlayStoreScraperTool
    from backend.tools.skyvern_tool import SkyvernTool

    _TOOL_REGISTRY = {
        "RedditTool": RedditTool,
        "AppStoreScraperTool": AppStoreScraperTool,
        "PlayStoreScraperTool": PlayStoreScraperTool,
        "SerperDevTool": SerperDevTool,
        "FirecrawlTool": FirecrawlTool,
        "PytrendsTool": PytrendsTool,
        "ScoringRubricTool": ScoringRubricTool,
        "SkyvernTool": SkyvernTool,
    }
    resolved = []
    for name in tool_names:
        cls = _TOOL_REGISTRY.get(name)
        if cls is None:
            log.warning("Unknown tool %r in agents.yaml — skipping", name)
            continue
        resolved.append(cls())
    return resolved


def _build_agent(agent_key: str, agents_cfg: dict[str, Any], llm: Any = None) -> Agent:
    """Build one crewai.Agent from the YAML config."""
    if agent_key not in agents_cfg:
        raise KeyError(f"agent_key={agent_key!r} not found in agents.yaml")
    kwargs = dict(agents_cfg[agent_key])
    if llm is not None:
        kwargs["llm"] = llm
    tool_names = kwargs.pop("tools", []) or []
    kwargs["tools"] = _resolve_tools(tool_names)
    kwargs["max_iter"] = 3
    return Agent(**kwargs)


def _build_task(
    task_key: str,
    tasks_cfg: dict[str, Any],
    agent: Agent,
    built_tasks: dict[str, Task] | None = None,
) -> Task:
    """Build one crewai.Task from the YAML config."""
    if task_key not in tasks_cfg:
        raise KeyError(f"task_key={task_key!r} not found in tasks.yaml")
    kwargs = dict(tasks_cfg[task_key])
    kwargs.pop("agent", None)

    if "context" in kwargs and kwargs["context"] and built_tasks is not None:
        raw_context = list(kwargs["context"])
        resolved = []
        for c in raw_context:
            if isinstance(c, Task):
                resolved.append(c)
            elif isinstance(c, str):
                if c not in built_tasks:
                    raise KeyError(
                        f"task {task_key!r} context references {c!r} which "
                        f"has not been built yet"
                    )
                resolved.append(built_tasks[c])
        kwargs["context"] = resolved

    return Task(**kwargs, agent=agent)


def build_content_dept_crew(llm: Any = None, task_callback: Any = None) -> Crew:
    """Build the content_dept_crew from YAML config.

    Returns a `crewai.Crew` with:
      - 5 agents: content_director (manager_agent) + 4 specialists
      - 5 tasks: scanning (sync) + 4 specialists (async) + consolidation (sync)
      - process = Process.hierarchical
      - manager_agent = content_director
      - NO `memory=` kwarg

    Phase 3a definition of done: brief produced for all 4 platforms
    (YouTube, Instagram, Twitter, Reddit).
    """
    agents_cfg = _load_yaml(_AGENTS_YAML)
    tasks_cfg = _load_yaml(_TASKS_YAML)

    agents = {
        key: _build_agent(key, agents_cfg, llm=llm)
        for key in _CONTENT_AGENT_KEYS
    }

    task_dict: dict[str, Task] = {}
    for task_key in _CONTENT_TASK_KEYS:
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

    tasks = list(task_dict.values())
    _manager_key = "content_director"
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
        "content_dept_crew built: %d workers, %d tasks, "
        "process=Process.hierarchical, manager_agent=content_director, "
        "memory=OMITTED (CrewAI default False)",
        len(worker_agents), len(tasks),
    )
    return crew


def build_automation_dept_crew(llm: Any = None, task_callback: Any = None) -> Crew:
    """Build the automation_dept_crew for Phase 3b Skyvern auto-posting.

    Uses:
      - manager_agent: automation_director (dept head)
      - worker agent: social_poster (specialist that calls SkyvernTool)
      - task: social_posting_task
      - process: Process.hierarchical (per ADR-0000 Q2)

    The social_poster agent carries `max_iter=3` (via _build_agent) so
    transient Skyvern errors are retried before the crew fails.

    Args:
        llm: Optional LLM override (e.g. in tests). Production: None.
        task_callback: Optional task callback for crew callbacks.

    Returns:
        A `crewai.Crew` with 1 manager + 1 specialist + 1 task,
        process=Process.hierarchical, no memory kwarg.
    """
    agents_cfg = _load_yaml(_AGENTS_YAML)
    tasks_cfg = _load_yaml(_TASKS_YAML)

    # Build both agents via the factory
    agents = {
        key: _build_agent(key, agents_cfg, llm=llm)
        for key in _AUTOMATION_AGENT_KEYS
    }

    # Build the single task
    task_dict: dict[str, Task] = {}
    for task_key in _AUTOMATION_TASK_KEYS:
        task_cfg = tasks_cfg[task_key]
        agent_key = task_cfg["agent"]
        task_dict[task_key] = _build_task(
            task_key, tasks_cfg, agents[agent_key],
            built_tasks=task_dict,
        )

    tasks = list(task_dict.values())
    _manager_key = "automation_director"
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
        "automation_dept_crew built: %d workers, %d tasks, "
        "process=Process.hierarchical, manager_agent=automation_director, "
        "memory=OMITTED (CrewAI default False)",
        len(worker_agents), len(tasks),
    )
    return crew