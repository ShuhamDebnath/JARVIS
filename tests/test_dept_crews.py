"""Tests for the Workflow 2 department crew factories (P1.4).

The P1.4 bug had three layers that surfaced end-to-end:

  1. `Task(**kwargs)` in `_build_task` crashed on string-list
     `context` (Pydantic v2 + CrewAI 0.86.0 contract violation).
     Fix: pass `built_tasks` into `_build_task` and resolve
     string names to Task instances before `Task(**kwargs)`.

  2. `Crew(**crew_kwargs)` in `build_research_dept_crew` /
     `build_product_dept_crew` crashed because the manager
     agent was included in the `agents=` list. CrewAI 0.86.0
     contract: hierarchical manager MUST NOT appear in workers.
     Fix: exclude the manager by key when building the workers
     list in both factories.

  3. (Fixed in P1.15) The product tasks previously referenced
     `research_consolidation_task` in their `context:` list, which
     was a cross-department reference the product factory could not
     resolve (it builds only the product tasks). P1.15 cleaned up
     tasks.yaml — the product tasks now reference only intra-dept
     context, and the CEO orchestrator passes the research brief
     via `kickoff(inputs={"research_brief": ...})` (per ADR-0000
     Q3). The test below pins the post-P1.15 behaviour: the product
     crew builds cleanly, the manager is excluded from workers,
     and the only context dep on the prd_writing task is the
     intra-dept scoring task.

These tests pin all three behaviours down:

  - `test_research_dept_crew_builds_without_crashing` — guards
    against regression of fixes (1) and (2) on the research
    crew. (The product crew is covered by a separate test
    below that documents the known cross-dept YAML issue.)

  - `test_research_manager_excluded_from_crew_agents` — pins
    the CrewAI 0.86.0 contract: research_director is the
    manager, NOT a worker. If a future refactor accidentally
    puts the manager back into `crew.agents`, this test fires.

  - `test_research_specialist_context_wired_as_task_instances` —
    pins fix (1): the 6 specialist tasks have their
    `context:` wired as actual `crewai.Task` objects (not
    strings), and the research_consolidation_task has all 6
    specialists as its context.

  - `test_product_dept_crew_builds_after_p115_yaml_cleanup` —
    pins the post-P1.15 product crew shape: 2 workers (manager
    excluded), 2 tasks, hierarchical process with
    product_director as manager, scoring task has empty context
    (brief arrives via kickoff inputs), prd_writing task has
    exactly the scoring task as its single intra-dept context.

  - `test_build_task_resolves_string_context` — unit-level
    regression test for `_build_task`: with a registry of
    already-built tasks, string context names must be
    resolved to Task instances BEFORE `Task(**kwargs)`. This
    is the load-bearing fix for bug (1).
"""

from __future__ import annotations

import pytest

from crewai import Task

from backend.crews.dept_crews import (
    _RESEARCH_AGENT_KEYS,
    _RESEARCH_TASK_KEYS,
    _build_task,
    build_product_dept_crew,
    build_research_dept_crew,
)


# Reuse the MockLLM from the project conftest so tests don't hit
# the real LLM (env_valid: false — see conftest.py for the rule).
from tests.conftest import MockLLM  # noqa: E402


# ---------------------------------------------------------------------------
# P1.4 fix verification — build_research_dept_crew end-to-end
# ---------------------------------------------------------------------------


def test_research_dept_crew_builds_without_crashing() -> None:
    """build_research_dept_crew must build a full crew (8 tasks, 7 workers).

    This is the top-level guard for P1.4: if either fix (1)
    [string context resolution] or fix (2) [manager excluded
    from agents list] regresses, this test fires because the
    `Crew(**crew_kwargs)` validation or the prior
    `Task(**kwargs)` call will raise.

    The crew is built with `MockLLM` so the test does not
    require a real OpenRouter key (env_valid: false per
    conftest.py).
    """
    crew = build_research_dept_crew(llm=MockLLM())
    # 8 agents declared in YAML (research_director + interpreter
    # + 6 specialists). 1 is the manager, so 7 end up in
    # `crew.agents`. See test_research_manager_excluded_from_crew_agents
    # for the manager-exclusion invariant.
    assert len(crew.agents) == len(_RESEARCH_AGENT_KEYS) - 1
    # 8 tasks (interpretation + 6 specialists + consolidation).
    assert len(crew.tasks) == len(_RESEARCH_TASK_KEYS)
    # Hierarchical process with the research_director as manager.
    assert crew.process.value == "hierarchical"
    # The manager agent on the crew object is the research_director.
    assert crew.manager_agent is not None
    assert crew.manager_agent.role == "Research Department Director"


def test_research_manager_excluded_from_crew_agents() -> None:
    """The hierarchical manager MUST NOT appear in `crew.agents`.

    CrewAI 0.86.0 Pydantic v2 contract: when
    `process=Process.hierarchical` and `manager_agent=` are
    both set, the manager cannot also be in `agents=` —
    otherwise `Crew(...)` raises
    `ValidationError: Manager agent should not be included
    in agents list`. This test pins the invariant so a
    future refactor that drops the manager-exclusion logic
    fails fast at test time.
    """
    crew = build_research_dept_crew(llm=MockLLM())
    # Every agent in crew.agents must NOT be the manager.
    assert crew.manager_agent is not None
    assert crew.manager_agent not in crew.agents
    # And the manager's role is exactly what we expect.
    assert crew.manager_agent.role == "Research Department Director"


def test_research_specialist_context_wired_as_task_instances() -> None:
    """The 6 specialist tasks and the consolidation task must have
    `context` populated with `crewai.Task` instances, not strings.

    This pins P1.4 fix (1): a string in `task.context` would
    crash `Task(**kwargs)` deep inside CrewAI's
    `process_config` Pydantic v2 before-validator with
    `AttributeError: 'str' object has no attribute 'get'`.
    Resolution happens in `_build_task` by looking up the
    task-key in the in-progress `built_tasks` registry.
    """
    crew = build_research_dept_crew(llm=MockLLM())

    # Build a name -> task map for assertion convenience. Note
    # that `task.name` is `None` in crewai 0.86.0 unless
    # explicitly set in `config`, so we use `description[:40]`
    # as a stable-enough key for the assertion. (The
    # load-bearing assertion is `isinstance(c, Task)`, not
    # the lookup key.)
    tasks_by_key = {
        "research_interpretation_task": crew.tasks[0],
        # Tasks 1..6 are the 6 specialists; index order
        # matches _RESEARCH_TASK_KEYS[1:7].
        "research_pain_point_task": crew.tasks[1],
        "research_competitor_mapping_task": crew.tasks[2],
        "research_revenue_estimation_task": crew.tasks[3],
        "research_gap_finding_task": crew.tasks[4],
        "research_trend_validation_task": crew.tasks[5],
        "research_audience_sizing_task": crew.tasks[6],
        "research_consolidation_task": crew.tasks[7],
    }

    # Each of the 6 specialists has the interpretation task in context.
    for spec_key in (
        "research_pain_point_task",
        "research_competitor_mapping_task",
        "research_revenue_estimation_task",
        "research_gap_finding_task",
        "research_trend_validation_task",
        "research_audience_sizing_task",
    ):
        spec = tasks_by_key[spec_key]
        ctx = getattr(spec, "context", None) or []
        assert len(ctx) == 1, (
            f"{spec_key} should have exactly 1 context dep "
            f"(the interpretation task); got {len(ctx)}"
        )
        assert isinstance(ctx[0], Task), (
            f"{spec_key}.context[0] must be a crewai.Task "
            f"instance (P1.4 fix); got {type(ctx[0]).__name__}"
        )
        assert ctx[0] is tasks_by_key["research_interpretation_task"], (
            f"{spec_key}.context[0] must be the interpretation "
            f"task instance, not a copy or string"
        )

    # Consolidation has all 6 specialists in its context.
    consolidation = tasks_by_key["research_consolidation_task"]
    ctx = getattr(consolidation, "context", None) or []
    assert len(ctx) == 6, (
        f"research_consolidation_task should have 6 context "
        f"deps (all 6 specialists); got {len(ctx)}"
    )
    assert all(isinstance(c, Task) for c in ctx), (
        "All items in research_consolidation_task.context must "
        "be crewai.Task instances (P1.4 fix); got at least one "
        "non-Task value"
    )
    # And the 6 context items are exactly the 6 specialists, in
    # the order declared in _RESEARCH_TASK_KEYS.
    spec_keys = [
        "research_pain_point_task",
        "research_competitor_mapping_task",
        "research_revenue_estimation_task",
        "research_gap_finding_task",
        "research_trend_validation_task",
        "research_audience_sizing_task",
    ]
    for c, expected_key in zip(ctx, spec_keys):
        assert c is tasks_by_key[expected_key], (
            f"research_consolidation_task.context contains an "
            f"unexpected task; expected {expected_key}"
        )

    # Interpretation is sync (no context — it's the root).
    interp = tasks_by_key["research_interpretation_task"]
    assert not getattr(interp, "context", None), (
        "research_interpretation_task must have empty context "
        "(it's the root; specialists depend ON it, not the other "
        "way around)"
    )


# ---------------------------------------------------------------------------
# P1.4 fix verification — _build_task unit-level
# ---------------------------------------------------------------------------


def test_build_task_resolves_string_context() -> None:
    """`_build_task` must resolve string context names to Task instances.

    P1.4 fix (1) at the unit level: with a registry of
    already-built tasks, a follow-up task that declares
    `context: [<earlier_task_key>]` must get a Task instance
    in `task.context`, not the raw string. If the resolution
    regresses, this test fires BEFORE the integration test
    above (faster feedback).
    """
    # Build a minimal registry by hand — we don't need a real
    # crew for this unit test, just enough to exercise the
    # resolution path.
    from backend.crews.dept_crews import (
        _AGENTS_YAML,
        _TASKS_YAML,
        _build_agent,
        _load_yaml,
    )

    agents_cfg = _load_yaml(_AGENTS_YAML)
    tasks_cfg = _load_yaml(_TASKS_YAML)

    # The 1st research task (no context) — build it first to
    # populate the registry.
    interp_agent = _build_agent("research_interpreter", agents_cfg, llm=MockLLM())
    interp_task = _build_task(
        "research_interpretation_task",
        tasks_cfg,
        interp_agent,
        built_tasks={},  # no deps — empty registry is fine
    )
    assert not getattr(interp_task, "context", None), (
        "interpretation task must build with no context"
    )

    # The 2nd research task has context: [research_interpretation_task].
    # Pass the just-built interpretation task in `built_tasks` —
    # _build_task must resolve the string to that instance.
    pain_agent = _build_agent("pain_point_hunter", agents_cfg, llm=MockLLM())
    pain_task = _build_task(
        "research_pain_point_task",
        tasks_cfg,
        pain_agent,
        built_tasks={"research_interpretation_task": interp_task},
    )
    ctx = getattr(pain_task, "context", None) or []
    assert len(ctx) == 1, (
        f"pain_point task should have 1 context dep after "
        f"resolution; got {len(ctx)}"
    )
    assert isinstance(ctx[0], Task), (
        "pain_point task context must be a Task instance, not "
        f"a string (P1.4 fix); got {type(ctx[0]).__name__}"
    )
    assert ctx[0] is interp_task, (
        "pain_point task context must be the SAME instance as "
        "the interpretation task we built (not a copy)"
    )


def test_build_task_raises_on_unresolvable_context() -> None:
    """`_build_task` must raise a clear KeyError on unresolvable context.

    Pin the strictness of fix (1): if a task's YAML `context:`
    references a task not in `built_tasks`, the build fails
    loud with a clear message — NOT silently with a string
    left in context. This catches two real failure modes:
      (a) task-ordering bugs (dependent task declared before
          its dependency in the build list)
      (b) cross-department context refs (the product crew's
          `context: [research_consolidation_task]`)
    Both should be surfaced immediately, not masked.
    """
    from backend.crews.dept_crews import (
        _AGENTS_YAML,
        _TASKS_YAML,
        _build_agent,
        _load_yaml,
    )

    agents_cfg = _load_yaml(_AGENTS_YAML)
    tasks_cfg = _load_yaml(_TASKS_YAML)
    pain_agent = _build_agent("pain_point_hunter", agents_cfg, llm=MockLLM())

    # Pass an EMPTY registry — `research_pain_point_task` wants
    # `context: [research_interpretation_task]`, which is not
    # in the registry. Expect a clear KeyError.
    with pytest.raises(KeyError) as excinfo:
        _build_task(
            "research_pain_point_task",
            tasks_cfg,
            pain_agent,
            built_tasks={},
        )
    # The error message must name the unresolvable task key
    # so the operator can grep for it.
    assert "research_interpretation_task" in str(excinfo.value), (
        f"KeyError message should name the unresolvable task "
        f"key 'research_interpretation_task'; got: {excinfo.value}"
    )


# ---------------------------------------------------------------------------
# P1.15 verification — product_dept_crew builds cleanly after YAML cleanup
# ---------------------------------------------------------------------------


def test_product_dept_crew_builds_after_p115_yaml_cleanup() -> None:
    """build_product_dept_crew must build cleanly after P1.15.

    Before P1.15, `backend/config/tasks.yaml` had the product
    tasks reference `research_consolidation_task` in their
    `context:` lists. That task lives in the RESEARCH crew, not
    the product crew, so the product factory could not resolve
    it and raised a clear KeyError. P1.15 cleaned up the YAML —
    product tasks now reference only intra-dept context, and the
    CEO orchestrator passes the research brief into this crew via
    `kickoff(inputs={"research_brief": ...})` (per ADR-0000 Q3).

    Invariants pinned now:
      - The product crew builds with 2 workers (product_director
        is the manager and is excluded from agents).
      - 2 tasks: opportunity_scoring + prd_writing.
      - product_director is the manager_agent (and NOT in agents).
      - product_opportunity_scoring_task has EMPTY context — the
        research_brief arrives via the CEO's kickoff inputs, not
        through task context wiring.
      - product_prd_writing_task has exactly 1 context dep:
        product_opportunity_scoring_task (intra-dept, the SAME
        instance that's in the crew's task list).
    """
    crew = build_product_dept_crew(llm=MockLLM())

    # 3 agents in YAML (product_director + opportunity_scorer +
    # prd_writer); 1 is the manager, so 2 end up in crew.agents.
    assert len(crew.agents) == 2, (
        f"product crew should have 2 workers (manager excluded); "
        f"got {len(crew.agents)}"
    )
    # 2 tasks: opportunity_scoring + prd_writing.
    assert len(crew.tasks) == 2, (
        f"product crew should have 2 tasks; got {len(crew.tasks)}"
    )
    # Hierarchical process with product_director as manager.
    assert crew.process.value == "hierarchical"
    assert crew.manager_agent is not None
    assert crew.manager_agent.role == "Product Department Director"
    # Manager-exclusion invariant (same as research crew).
    assert crew.manager_agent not in crew.agents, (
        "product_director (manager) must NOT appear in crew.agents — "
        "CrewAI 0.86.0 contract."
    )

    # Context wiring (intra-dept only after P1.15).
    tasks_by_key = {
        "product_opportunity_scoring_task": crew.tasks[0],
        "product_prd_writing_task": crew.tasks[1],
    }

    scoring = tasks_by_key["product_opportunity_scoring_task"]
    scoring_ctx = getattr(scoring, "context", None) or []
    assert scoring_ctx == [], (
        f"product_opportunity_scoring_task must have empty context "
        f"after P1.15 — the research_brief is passed via the CEO's "
        f"kickoff inputs, not via task context. Got: {scoring_ctx!r}"
    )

    prd = tasks_by_key["product_prd_writing_task"]
    prd_ctx = getattr(prd, "context", None) or []
    assert len(prd_ctx) == 1, (
        f"product_prd_writing_task should have exactly 1 context dep "
        f"(the scoring task); got {len(prd_ctx)}"
    )
    assert isinstance(prd_ctx[0], Task), (
        f"product_prd_writing_task.context[0] must be a crewai.Task "
        f"instance (P1.4 fix); got {type(prd_ctx[0]).__name__}"
    )
    assert prd_ctx[0] is tasks_by_key["product_opportunity_scoring_task"], (
        "product_prd_writing_task.context[0] must be the SAME instance "
        "as the scoring task in crew.tasks (not a copy or a string)."
    )
