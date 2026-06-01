# ADR-0002 — Reshape research_dept_crew: parallel specialists, dedicated interpreter, no semantic memory

> Date: 2026-06-01 (grilling session 2)
> Resolves: Questions 6, 7, 13 from `docs/adr/0001-grilling-session-followups.md`
> Supersedes a paragraph in ADR-0000 Question 5 (noted inline)
> Status: Resolved (2026-06-01, grilling session 3)

---

## Context

ADR-0000 resolved Questions 1–5 of the first grilling session. A re-read of the resulting Workflow 2 spec surfaced three related issues against `research_dept_crew`:

1. **Specialists are not actually parallel.** The 15-minute PRD time estimate (workflow-2 spec, "Cost Estimate Per Run") and the architecture-doc diagram (architecture.md:148) both say the 6 research specialists run "in parallel". CrewAI's `Process.hierarchical` runs tasks sequentially in list order — parallel execution requires `async_execution: true` on each task explicitly. Without it, ~5 min of expected research wall-clock becomes ~8–12 min.

2. **`research_director` has three overlapping jobs.** After ADR-0000 Q5, the director is (a) `manager_agent` of the crew, (b) executor of `research_interpretation_task` (strict JSON), and (c) executor of `research_consolidation_task` (free-form synthesis). CrewAI's manager-agent system prompt is conditioned to call its `Delegate work to coworker` tool. When the same agent is asked to produce JSON directly, it sometimes routes the request through a worker, breaking the contract. This directly undermines the reproducibility guarantee that ADR-0000 Q5 was created to provide.

3. **Per-dept ChromaDB collections do not isolate runs.** ADR-0000 Q2 promised per-department memory isolation as a benefit of the per-dept-crew pattern. CrewAI's `Crew(memory=True)` auto-generates a collection name from crew composition (agents + tasks), so two `build_research_dept_crew()` calls share the same underlying ChromaDB collection. Run 2 of "to-do app" can semantic-retrieve fragments from run 1 of "habit tracker" — the exact bleeding ADR-0000 Q2 was meant to prevent.

The three issues are coupled. Fixing parallelism (1) makes the consolidation task's `context:` field the synchronisation point, which strengthens the case for treating consolidation as a dedicated, structured task (relates to 2). Fixing the director's role conflict (2) means inter-agent state flows entirely through explicit task `context:`, which removes the last consumer of ChromaDB inside the crew (relates to 3).

---

## Decision

Three coordinated changes, all confined to `agents.yaml`, `tasks.yaml`, and `dept_crews.py`:

### 1. Add `async_execution: true` to the 6 research specialist tasks

Applied to:

- `research_pain_point_task`
- `research_competitor_mapping_task`
- `research_revenue_estimation_task`
- `research_gap_finding_task`
- `research_trend_validation_task`
- `research_audience_sizing_task`

`research_interpretation_task` stays synchronous — the 6 list it as `context:` and depend on its output. `research_consolidation_task` stays synchronous — it lists all 6 specialists as `context:` and CrewAI blocks it until they all complete. The sync/async/sync sandwich is the natural shape.

A smoke test is mandatory before declaring Phase 1 complete: print `time.time()` at the start of each specialist's first tool call to `jarvis.log` and confirm overlapping windows.

If `async_execution: true` misbehaves under `Process.hierarchical` in the installed CrewAI version, the fallback is manual `asyncio.gather()` over six single-task mini-crews composed in `jarvis_ceo.py`. The fallback adds Python but removes library-behaviour uncertainty.

### 2. Add `research_interpreter` as a dedicated Level-3 specialist

```yaml
research_interpreter:
  dept: research_dept
  role: Idea Interpretation Specialist
  goal: >
    Convert the user's one-sentence app idea into a structured JSON
    interpretation document used by all 6 research specialists.
  backstory: >
    You produce structured output, never free-form prose. You never
    delegate. Your output is parsed downstream — if it is not valid
    JSON matching the schema, the entire workflow breaks.
  llm: deepseek/deepseek-chat
  tools: []                         # no tools — pure interpretation
  allow_delegation: false           # critical: never delegate
  memory: false
  verbose: true
```

`research_interpretation_task` is reassigned: `agent: research_interpreter`. A Pydantic model defines the JSON schema and is attached via `output_pydantic` as a framework-level enforcer (the model will retry on validation failure).

`research_director` keeps two responsibilities only:

- `manager_agent` of `research_dept_crew` (delegation behaviour)
- Executor of `research_consolidation_task` (free-form synthesis, naturally aligned with a manager's role)

This is consistent with CLAUDE.md line 142 ("adding a new agent touches exactly 2 files — `agents.yaml` and `tasks.yaml`").

### 3. Set `memory=False` on both dept_crews

`build_research_dept_crew()` and `build_product_dept_crew()` are constructed with `memory=False`. After changes 1 and 2:

- Specialists are parallel — they cannot semantic-retrieve each other's mid-flight outputs.
- Interpretation is consumed via explicit `context:`, not via semantic recall.
- Consolidation receives all 6 specialist outputs via explicit `context:`, not via semantic recall.

ChromaDB has no concrete consumer inside the crew. Removing it eliminates the per-run contamination failure mode entirely.

ADR-0000 Q2's per-department-isolation promise is stricter, not weaker: cross-dept isolation is now achieved by *separate crews* (still true), and within-dept state isolation is achieved by *no shared semantic store* (newly explicit). If a future workflow develops a concrete need for semantic recall within a dept, the upgrade path is an ephemeral (RAM-only) ChromaDB client per `Crew` instance — leaves no on-disk state to leak.

---

## Consequences

### Positive

- The "15-minute PRD" promise becomes honest. Research fan-out completes in ~5 min on wall-clock (assuming async behaves as documented in the installed CrewAI version).
- ADR-0000 Q5's JSON-output contract is no longer fighting a manager-agent system prompt. Two runs of the same idea now produce comparable interpretations.
- Zero ChromaDB cross-run contamination, by construction. No cleanup code needed. No disk leak from orphaned collections.
- The director's role becomes coherent — coordinator + synthesiser, not coordinator + synthesiser + JSON-formatter.

### Negative

- Adds one YAML stanza (`research_interpreter`).
- Reverses framing in `architecture.md` — the "Per-Department Memory Isolation" section needs rewriting as "Per-Department Crew Isolation; in-dept memory disabled by default".
- `async_execution` behaviour needs validation on the actual installed CrewAI version. If it misbehaves, the fallback (manual `asyncio.gather()`) adds Python complexity.

### Cost

Neutral. The new `research_interpreter` adds one tiny LLM call (already counted in the Q5 cost estimate of ~₹0.50/run). Removing `memory=True` shaves ChromaDB embedding calls (small saving).

---

## Cross-references

- **Supersedes ADR-0000 Question 5 paragraph** that argued *"the director is already the `manager_agent` — a cheap single-call task it executes is the lightest possible change"*. That sentence is wrong under CrewAI's actual manager-prompt behaviour. ADR-0000 needs a one-line correction note appended.
- `docs/architecture.md` — "Per-Department Memory Isolation" section needs rewriting (Q13).
- `docs/architecture.md` — "How the CEO Routes a Request" sample diagram already says "in parallel"; with this ADR that statement is finally true.
- `docs/workflows/workflow-2-research-prd.md` — apply: new `research_interpreter` agent stanza; `async_execution: true` on 6 specialist tasks; `agent: research_interpreter` on `research_interpretation_task`; `output_pydantic` attachment; `memory=False` in both `build_*_dept_crew()` snippets.
- `docs/roadmap.md` Phase 1 step list — add the new `research_interpreter` agent and the Pydantic model file as deliverables; add the parallelism smoke test as a Phase 1 acceptance item.

---

*End of ADR-0002.*

---

## Resolution — 2026-06-01 (grilling session 3)

The original ADR documented the three strategic decisions. Grilling session 3 walked the seven open tactical questions below, one at a time, and the captured decisions are recorded here as the durable source of truth for "what did session 3 decide?"

### Q1 — How do you prove parallelism works?
**Decision:** `tests/test_workflow_2_parallelism.py` with a mocked LLM (5s sleep per response). Wire `task_callback` (per-task boundary, not per-tool) into the crew. Asserts the 6 specialist `START` timestamps are within 1s of each other; asserts total wall-clock is < 30s. If the test fails, trigger the Q2 fallback matrix. **Phase 1 deliverable.**

### Q2 — What triggers the `asyncio.gather()` fallback?
**Decision:** Four-failure trigger matrix (F1–F4). F1 = async flag silently ignored; F2 = context race in consolidation; F3 = manager-agent interference; F4 = real-OpenRouter flakiness. F1 + F2 are testable — gate the release on `tests/test_workflow_2_parallelism.py` + a new `test_consolidation_has_all_6_contexts`. F3 + F4 are runtime symptoms — the dashboard gets a "switch to fallback?" prompt via `human_gate.ask_user()`. **Fallback architecture:** six (or seven) `Crew(process=Process.sequential)` instances gathered with `asyncio.gather` + `asyncio.to_thread`. Preserves CrewAI tool handling. Implemented in `backend/crews/research_runner.py` (Phase 1 deliverable, only built if a trigger fires).

### Q3 — Where does the Pydantic schema live, and what does "retry on validation failure" mean?
**Decision:** `backend/contracts/research.py` (new package `backend/contracts/`, one file per workflow contract). Schema is the strict Pydantic v2 model with `Literal` for `app_category` and `Field(min_length=…, max_length=…)` on every list. Retry policy: 3 retries; LLM sees the verbatim Pydantic `ValidationError` message; all 3 fail → raise `InterpretationValidationError` → CEO catches → `runs.json` status = `failed` → write transcript to `backend/output/failed_interpretation_{run_id}.md`. **Implemented this session:** `backend/contracts/__init__.py` and `backend/contracts/research.py`. `dept_crews.py` sanitiser + `jarvis_ceo.py` exception handler are Phase 1 deliverables (spec is in `research.py`'s docstring).

### Q4 — The `memory` field is now contradictory across three files
**Decision:** Three coordinated edits — `memory: false` on every agent in `agents.yaml`; no `memory` argument in any `Crew(...)` call in `dept_crews.py` (relies on CrewAI default of `False`); `architecture.md` "Per-Department Memory Isolation" section renamed to "Per-Department Crew Isolation; in-dept memory disabled by default" with the full policy paragraph. **Implemented this session:** all 11 `memory: true` → `memory: false` in `workflow-2 spec`; both `memory=True` lines removed from `Crew(...)` snippets; `architecture.md` rewritten. `dept_crews.py` edit is Phase 1.

### Q5 — Is `deepseek/deepseek-chat` the right LLM for `research_interpreter`?
**Decision:** DeepSeek primary, with a 5%-fail-rate escape hatch documented as a YAML comment on `research_interpreter.llm`. If 3-retry validation failures exceed 5% over the first 10 runs, switch to `minimax/minimax-m3` (coding/multimodal tier). Track failure rate in `backend/output/interpretation_failures.log`. **Implemented this session:** the YAML comment is in `workflow-2 spec`'s `research_interpreter` stanza.

### Q6 — Does `output_pydantic` actually retry?
**Decision:** Version-pin `crewai==0.86.2` + `pydantic==2.6.4` in `backend/requirements.txt`. Set `max_retries: 3` on `research_interpretation_task`. Add a manual retry fallback in `dept_crews.py` (~30 lines) that catches validation errors, re-injects the Pydantic error message into the next prompt, and only raises `InterpretationValidationError` if all 3 fail. **Implemented this session:** `backend/requirements.txt` created; `max_retries: 3` and `output_pydantic: contracts.research.ResearchInterpretation` added to the spec. `dept_crews.py` manual fallback is Phase 1.

### Q7 — When and how does this ADR move to Resolved?
**Decision:** Resolved = all decisions documented + all cross-references have a home (Phase Discipline enforced — no Phase 1 Python code is scaffolded in this session). **Implemented this session:** see the "Cross-reference status" table below.

### Cross-reference status

| File | Required change | Status this session |
| --- | --- | --- |
| `docs/adr/0000-grilling-session-2026-06-01.md` | Append correction note to Q5 paragraph | ✅ Done |
| `docs/architecture.md` | Rewrite "Per-Department Memory Isolation" section | ✅ Done (Q4) |
| `docs/architecture.md` | Layer 3 Memory section + Decision Log row | ✅ Done (Q4) |
| `docs/workflows/workflow-2-research-prd.md` | `research_interpreter` agent stanza | ✅ Done (Q5) |
| `docs/workflows/workflow-2-research-prd.md` | `output_pydantic` + `max_retries: 3` on `research_interpretation_task` | ✅ Done (Q6) |
| `docs/workflows/workflow-2-research-prd.md` | `agent: research_interpreter` (replacing `research_director`) | ✅ Done (Q6) |
| `docs/workflows/workflow-2-research-prd.md` | `async_execution: true` on 6 specialist tasks | ✅ Done (Q1) |
| `docs/workflows/workflow-2-research-prd.md` | All agents `memory: false`; `Crew(...)` has no `memory` arg | ✅ Done (Q4) |
| `docs/roadmap.md` | Phase 1 step list: `research_interpreter` agent, `backend/contracts/research.py` deliverable, parallelism smoke test acceptance item | ✅ Done (Q7) |
| `backend/requirements.txt` | Version pins: `crewai==0.86.2`, `pydantic==2.6.4` | ✅ Done (Q6) |
| `backend/contracts/__init__.py` | New package marker + docstring | ✅ Done (Q3) |
| `backend/contracts/research.py` | `ResearchInterpretation` + `InterpretationValidationError` | ✅ Done (Q3) |
| `CLAUDE.md` | One-line exception under "Adding a new specialist" rule | ✅ Done (Q3) |
| `backend/crews/dept_crews.py` | `r/` sanitiser + manual retry fallback | ⏳ Phase 1 deliverable |
| `backend/crews/jarvis_ceo.py` | Catch `InterpretationValidationError` + write transcript to `backend/output/failed_interpretation_{run_id}.md` | ⏳ Phase 1 deliverable |
| `backend/crews/research_runner.py` | Q2 fallback (asyncio.gather of single-task Crews) | ⏳ Phase 1 deliverable, only built if a trigger fires |
| `tests/test_workflow_2_parallelism.py` | Mocked-LLM parallelism smoke test | ⏳ Phase 1 deliverable |

### Memory upgrade path (reserved, not active)

If a future workflow develops a concrete need for in-dept semantic recall, the upgrade is an ephemeral (RAM-only) ChromaDB client per `Crew` instance — constructed inside `build_*_dept_crew()` and torn down when `kickoff()` returns. This leaves no on-disk state to leak between runs and requires no changes to `agents.yaml`. ADR-0002's "in-dept memory disabled by default" policy is the *default*, not a permanent ban.

### Outstanding grilling question

None. All 7 questions in this ADR are resolved. The next grilling session should pick up from `docs/adr/0001-grilling-session-followups.md`'s *Resolved* table to find the next batch of open questions — the punch list in that file is also fully resolved as of session 2.

---

*End of resolution.*
