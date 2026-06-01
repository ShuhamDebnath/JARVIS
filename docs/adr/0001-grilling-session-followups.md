# Grilling Session — Follow-up Questions (Queued)

> Captured 2026-06-01 by Claude Code after reading every doc + the in-flight code.
> Continues from `0000-grilling-session-2026-06-01.md` (Questions 1–5 already resolved).
> These are unresolved. Each has a recommended answer to start the next session with.
>
> **How to use this file:** Start the next session with `/grill-with-docs` and point it here.
> Resolve one question at a time. Move resolved questions into a `0002-...` ADR or append
> to this file under a `Resolved` section.

---

## Source files reviewed before this list

- `CLAUDE.md`, `AI-RULES.md`, `README.md`, `.env.example`, `.gitignore`
- `docs/prd.md`, `docs/architecture.md`, `docs/roadmap.md`
- `docs/workflows/workflow-1-design-validation.md`
- `docs/workflows/workflow-2-research-prd.md`
- `docs/workflows/workflow-3-social-media-engine.md`
- `docs/adr/0000-grilling-session-2026-06-01.md`
- `backend/orchestrator/human_gate.py` (only real code so far)
- `backend/state/runs.json` (smoke-test artifact)
- `backend/main.py`, `backend/config/agents.yaml`, `backend/config/tasks.yaml`,
  `backend/utils/logger.py`, `backend/utils/env_validator.py`,
  `backend/utils/cost_guard.py` — **all confirmed empty** (0 bytes / 1-line stubs)

---

## Question 6 — Are the 6 research specialists actually parallel?

**Issue raised**
`workflow-2-research-prd.md` says *"6 agents fire simultaneously"* and the cost/time estimate
(~5 min, ~85k tokens) assumes parallel execution. But CrewAI's `Process.hierarchical` is a
**manager-delegation** pattern, not a parallel-task pattern: the `manager_agent` decides which
worker runs next, and tasks listed in `tasks.yaml` execute **sequentially in list order** unless
you explicitly opt into async execution per task (`async_execution: true` on the task).

**Why it matters**
- This is the load-bearing time estimate for the whole project's value prop (15-min PRDs).
- Sequentially, 6 specialists × ~30–60s each = 3–6 min just for specialist calls, plus
  manager overhead = closer to 8–12 min for research alone. PRD writing adds more.
- Cost stays the same; wall-clock doesn't.

**Recommended answer**
- Add `async_execution: true` to each of the 6 specialist tasks
  (`research_pain_point_task`, `research_competitor_mapping_task`, etc.) in `tasks.yaml`.
- `research_consolidation_task` already has `context: [...all 6...]` — CrewAI will block
  consolidation until all 6 async tasks complete, which is exactly the gate we want.
- `research_interpretation_task` must stay synchronous (the 6 depend on its output).
- Validate with a smoke test: print start/end timestamps per specialist and confirm
  overlap in `jarvis.log`.

**Files to update**
- `docs/workflows/workflow-2-research-prd.md` — tasks.yaml block, add `async_execution: true`
  to the 6 specialist tasks; add a one-paragraph note explaining why interpretation +
  consolidation are sync but the 6 in between are async.

---

## Question 7 — `research_director` has three overlapping jobs

**Issue raised**
After Question 5 was resolved, `research_director` is now responsible for:
1. Acting as `manager_agent` of `research_dept_crew` (CrewAI delegation behaviour)
2. Running `research_interpretation_task` (deterministic JSON output, no delegation)
3. Running `research_consolidation_task` (free-form synthesis of 6 specialist outputs)

Three jobs is too many for one system prompt. Specifically: a manager agent in CrewAI is
prompted to *delegate*, but the interpretation task tells it to *produce JSON itself*.
Mixed signals → unreliable JSON.

**Why it matters**
- Question 5's whole point was reproducibility via structured JSON. If the JSON breaks
  because the manager-agent prompt fights the interpretation-task prompt, Question 5's
  benefit evaporates.
- This is the single most likely reason Workflow 2 will misbehave in week 1.

**Recommended answer — option A (cheapest)**
- Keep `research_director` as `manager_agent` + consolidator.
- Move interpretation to a tiny new agent: `research_interpreter` (a Level-3 specialist
  in `research_dept`, no tools, single job, strict JSON output, `allow_delegation: false`).
- Adds one agent to `agents.yaml`. Solves the role conflict cleanly.

**Recommended answer — option B (cheapest YAML-only)**
- Keep one agent but split the system prompt: the agent's `goal` lists both responsibilities
  with explicit "when called for task X, behave as Y" branching. Cheaper config-wise, but
  brittle — depends on LLM reading the branch correctly.

**My recommendation: option A.** A new agent is one YAML stanza + one entry in
`build_research_dept_crew()`. The "adding a new agent touches exactly 2 files" rule
(CLAUDE.md line 142) is already designed for this.

**Files to update**
- `docs/workflows/workflow-2-research-prd.md`
- The Q5 resolution paragraph in ADR `0000` (note that interpreter is now its own agent)

---

## Question 8 — `product_director` is defined twice in workflow-2 spec

**Issue raised**
`docs/workflows/workflow-2-research-prd.md` lines **383–397** define `product_director`
**without** a `dept:` field, then lines **405–420** define `product_director` **again**
with `dept: product_dept`. Pure duplication — YAML parsers will silently keep the second
one and discard the first. Looks like a copy-paste leftover from Question 2's edits.

**Why it matters**
- Cosmetic but confusing. The first one will be silently dropped.
- Whoever writes `backend/config/agents.yaml` for real will copy both and get a parse
  error or a silent override.

**Recommended answer**
Delete lines 383–397. Keep only the second block with `dept: product_dept`.
Add a one-line comment above it: `# DEPARTMENT: product_dept`.

**Files to update**
- `docs/workflows/workflow-2-research-prd.md` only.

---

## Question 9 — `prd_writing_task` is defined twice in workflow-2 spec

**Issue raised**
`docs/workflows/workflow-2-research-prd.md`:
- Line 842 declares `product_prd_writing_task:` then has no body (just a comment line).
- Line 845 declares `prd_writing_task:` with the full body and `agent: prd_writer`.

So we have a stub named with the `product_` prefix (which Question 2 mandated) **and** the
real definition without the prefix. Real `tasks.yaml` will be ambiguous.

**Why it matters**
- The naming-prefix rule from Question 2 is what prevents cross-dept task collisions.
- The actual task that gets loaded has no prefix → if Workflow 6 ever adds a content
  `prd_writing_task` (unlikely but possible), they'll collide.
- More urgent: the *unfilled* `product_prd_writing_task:` stub is going to be copied
  verbatim into the real `tasks.yaml` and break `load_tasks_for("product_dept")`.

**Recommended answer**
- Delete the stub on line 842.
- Rename line 845 from `prd_writing_task:` to `product_prd_writing_task:`.
- Update `research_consolidation_task` and any `context:` references that point at the
  old name (none currently — but recheck after the rename).

**Files to update**
- `docs/workflows/workflow-2-research-prd.md` only.

---

## Question 10 — Tool names referenced in agents.yaml don't exist in `crewai-tools`

**Issue raised**
Workflow-2 spec lists these tools in agent configs:
`RedditTool`, `AppStoreScraperTool`, `PlayStoreScraperTool`, `SerperDevTool`,
`FirecrawlTool`, `PytrendsTool`, `ScoringRubricTool`, `VisionTool` (Workflow 1).

`crewai-tools` (the pip package) ships `SerperDevTool` and `FirecrawlTool` out of the box.
The other 6 do not exist — they need to be written in `backend/tools/` as `BaseTool`
subclasses (per CLAUDE.md "How to Add a New Tool").

**Why it matters**
- Phase 1 will fail at crew instantiation if any of these names are passed to an agent
  and the corresponding tool doesn't exist.
- The roadmap's Phase 1 step list mentions `store_scraper.py`, `firecrawl_tool.py`,
  `reddit_tool.py` — but **not** `pytrends_tool.py` or `scoring_rubric_tool.py`,
  which are also required.

**Recommended answer**
- Update Phase 1 step list in `docs/roadmap.md` to add:
  - `tools/pytrends_tool.py`
  - `tools/scoring_rubric_tool.py` (wraps the hardcoded rubric table from Q1)
- For Workflow 1 (Phase 6): add `tools/vision_tool.py` to the Phase 6 step list.
- Distinguish in `agents.yaml` between built-in `crewai-tools` tools and project-local
  ones (e.g., import + register custom tools in `crews/dept_crews.py` before
  `Crew(...)` instantiation).

**Files to update**
- `docs/roadmap.md` Phase 1 + Phase 6 step lists.
- `docs/workflows/workflow-2-research-prd.md` "Tools Required" table (add pytrends_tool,
  scoring_rubric_tool).
- `docs/workflows/workflow-1-design-validation.md` "Files Involved" section (already
  lists `vision_tool.py` — just confirm the agent reference matches).

---

## Question 11 — Workflow 1 still uses 2-level hierarchy

**Issue raised**
Question 2 resolved that every dept gets its own `Crew(process=Process.hierarchical)`
with the dept head as `manager_agent`. The Workflow-2 spec was rewritten accordingly.
Workflow-1 spec **was not**: `design_director` is listed as a regular agent
(`allow_delegation: true`), but there is no `design_dept_crew` builder, no
`backend/crews/dept_crews.py:build_design_dept_crew()`, and no department-level
isolation. Inconsistent with the architecture.

**Why it matters**
- Phase 6 will hit this inconsistency and have to redo Workflow 1 design.
- The cross-workflow consistency check from CLAUDE.md line 137 ("always use
  `Process.hierarchical`") will fail audit.

**Recommended answer**
- Update `docs/workflows/workflow-1-design-validation.md` to mirror Workflow 2's structure:
  - Add `dept: design_dept` to all 3 design agents.
  - Show the `Jarvis CEO (Python) → design_dept_crew → 3 specialists` diagram.
  - Prefix all design tasks with `design_` in `tasks.yaml`.
  - Add a `build_design_dept_crew()` stub to the spec's "Crew Assembly" section.
- Same edit applies to Workflow 3 (already names `Content Director` + `Automation Director`
  separately — make these `content_dept_crew` and `automation_dept_crew`).

**Files to update**
- `docs/workflows/workflow-1-design-validation.md`
- `docs/workflows/workflow-3-social-media-engine.md`

---

## Question 12 — Skyvern on macOS is the single biggest install risk

**Issue raised**
Phase 0c installs Skyvern. Skyvern requires Docker on macOS, has a heavy Python
dependency tree, and has historically been fragile on Apple Silicon. If install fails,
Workflow 3 (Phase 3) is blocked with no backup.

**Why it matters**
- AI-RULES.md Rule 8 forbids replacing Skyvern with Selenium/Puppeteer.
- "Working beats complete" (roadmap principle 1) means we should have a manual fallback.

**Recommended answer**
- Keep Skyvern as the Phase 3+ goal.
- Add an explicit Phase 3a milestone in `docs/roadmap.md`: **"Brief generation working,
  posting still manual."** Workflow 3 delivers value even without Skyvern — the developer
  copy-pastes captions and uploads by hand.
- Move Skyvern install to a Phase 3b sub-phase. If it fails, Phase 3a still ships.
- `tools/skyvern_tool.py` raises `NotImplementedError("Skyvern not installed — copy
  caption from {brief_path} and upload manually")` until install succeeds.

**Files to update**
- `docs/roadmap.md` Phase 3 split into 3a / 3b.
- `docs/workflows/workflow-3-social-media-engine.md` testing checklist — mark "Skyvern
  posts to at least one platform" as Phase 3b, not 3a.

---

## Question 13 — How do you actually reset ChromaDB between runs?

**Issue raised**
The Workflow-2 testing checklist (line 1024) says *"Run a second idea to confirm memory
does not bleed between runs."* The architecture promises per-dept ChromaDB collections
(`jarvis_research_dept`, `jarvis_product_dept`). But:
- CrewAI's `memory=True` creates a collection scoped to the **crew instance**, not the
  **run id**. Two `kickoff()` calls on the same crew object share memory.
- There is no specified hook for "reset memory at start of run".

**Why it matters**
- Without a reset, run 2 of "habit tracker" could pull research from run 1 of "to-do
  app" — exactly the bleeding the architecture promises to prevent.
- The whole Q2 trade-off (lose cross-dept memory to gain isolation) depends on per-run
  reset working.

**Recommended answer**
Two options:

- **A. Fresh crew per run.** `build_research_dept_crew()` is called inside `run_workflow_2`
  every time, so each call gets a new Crew object with a new ChromaDB collection name
  scoped by `run_id`. Simple, no manual reset. Cost: tiny — Crew construction is cheap.
- **B. Explicit `clear_memory()` call.** Call `crew.reset_memory()` (or equivalent —
  needs verification against current CrewAI version) at the top of `run_workflow_2`.

**My recommendation: A.** Matches the existing `build_research_dept_crew()` factory pattern
already in the spec. The collection name should incorporate `run_id` to be safe:
`f"jarvis_research_dept_{run_id}"`. Confirm against the latest `crewai-tools` docs
that this is supported.

**Files to update**
- `docs/architecture.md` "Per-Department Memory Isolation" section — note that collections
  are run-scoped, not just dept-scoped.
- `docs/workflows/workflow-2-research-prd.md` "Crew Assembly" code snippet — show
  the run_id parameter being threaded into the collection name.

---

## Question 14 — `cost_guard.py` is empty but PRD §11 promises real guardrails

**Issue raised**
`backend/utils/cost_guard.py` is 0 bytes / 1-line empty. PRD §11 says:
- Per-run token limit → cancel run + log warning
- Daily spend cap → ntfy.sh alert
- Model fallback → DeepSeek → MiniMax M2.7 automatic

None of this is built or specced beyond the PRD prose. The roadmap Phase 1 step list
mentions `cost_guard.py` as a deliverable but with no design.

**Why it matters**
- "Cost under ₹2,000/month" is one of the PRD goals (PRD §3 table). With no guardrails,
  one buggy infinite-loop crew could blow the whole month.
- The fallback rule is hard — automatic LLM switching has to happen at the agent level,
  not just at the crew level. CrewAI doesn't ship this natively.

**Recommended answer (minimal viable for Phase 1)**
- `cost_guard.py` exposes 3 functions: `start_run(run_id)`, `log_call(run_id, model, in_tok, out_tok)`,
  `end_run(run_id)`.
- Hook it into the CrewAI callbacks system (`step_callback` / `task_callback`) so every
  LLM call increments `log_call`.
- Per-run budget = hardcoded `MAX_TOKENS_PER_RUN = 200_000` for Phase 1. If exceeded,
  raise + log + write a `cost_exceeded.txt` to `backend/output/`.
- Daily cap and fallback model → defer to Phase 7 (matches "manual before automated").

**Files to update**
- `docs/workflows/workflow-2-research-prd.md` "Cost Estimate Per Run" — confirm 85k is
  well under the 200k budget.
- `docs/roadmap.md` Phase 1 step list — add explicit "wire cost_guard.start_run / end_run
  into jarvis_ceo.run_workflow_2".

---

## Question 15 — Obsidian sync on partial failure

**Issue raised**
`jarvis_ceo.run_workflow_2` (workflow-2 spec lines 888–912):
- On `declined` (user says no at the gate) → `sync_research(idea, research_brief)` only.
- On `completed` → `sync_research(...) + sync_prd(...)`.
- On crash mid-PRD-write → **nothing is saved**. The research brief is lost too.

**Why it matters**
- The research brief is the most expensive output (6 specialist calls). Losing it on a
  PRD-write crash means re-running the whole crew for free advice.

**Recommended answer**
- Call `sync_research(idea, research_brief)` immediately after `research_crew.kickoff()`
  returns, before the human gate. Then the brief is durable no matter what happens later.
- The `declined` branch becomes a no-op (already saved).
- Wrap `product_crew.kickoff()` in try/except. On crash, log + save a `PRD_PARTIAL_{idea}.md`
  with whatever the LLM produced before the failure.

**Files to update**
- `docs/workflows/workflow-2-research-prd.md` "Crew Assembly — File 1" code snippet.

---

## Summary table

| # | Area | Severity | One-line recommendation |
|---|------|----------|------------------------|
| 6  | Workflow 2 parallelism | **HIGH** | Add `async_execution: true` to 6 specialist tasks |
| 7  | Director role conflict | **HIGH** | Add `research_interpreter` as its own agent |
| 8  | Dup product_director   | LOW      | Delete the first definition |
| 9  | Dup prd_writing_task   | MEDIUM   | Delete stub, prefix the real one |
| 10 | Missing tool wrappers  | MEDIUM   | Add pytrends_tool + scoring_rubric_tool to Phase 1 |
| 11 | Workflow 1 + 3 hierarchy inconsistency | MEDIUM | Update both specs to dept_crew pattern |
| 12 | Skyvern install risk   | MEDIUM   | Split Phase 3 → 3a (briefs) + 3b (auto-post) |
| 13 | ChromaDB per-run reset | **HIGH** | Run-scoped collection names in `build_*_dept_crew()` |
| 14 | cost_guard.py empty    | MEDIUM   | Minimal token counter + per-run cap in Phase 1 |
| 15 | Crash during PRD write | LOW      | Save research brief before the human gate |

---

## Resolved — 2026-06-01 (grilling session 2)

All 10 follow-up questions resolved via `/grill-with-docs`. Where the
recommended answer was adopted unchanged, the row says *"Recommended"*.
Where the resolution refined the recommended answer, the row records the
shipped decision.

| # | Decision | Captured in |
|---|----------|-------------|
| 6  | Recommended. `async_execution: true` on 6 specialist tasks. Interpretation + consolidation stay sync. Smoke-test the parallelism via overlapping timestamps in `jarvis.log`. Fallback: manual `asyncio.gather()` in `jarvis_ceo.py` if CrewAI's async misbehaves under `Process.hierarchical`. | **ADR-0002** |
| 7  | Refined Recommendation A: add `research_interpreter` as a Level-3 specialist (no tools, `allow_delegation: false`) **plus** attach a Pydantic schema to `research_interpretation_task` via `output_pydantic` as a belt-and-braces enforcer. Director keeps `manager_agent` + consolidation only. ADR-0000 Q5 paragraph about "the director executes the interpretation task" is superseded. | **ADR-0002** |
| 8  | `agents.yaml` uses **flat agent keys with a `dept:` field** (Proposal Y) — confirmed as canonical. The "departments as top-level keys" alternative is rejected. Delete the first `product_director` stanza in workflow-2 spec (lines 383–397). Loader iterates and filters by `dept:`. | workflow-2 spec edit + `architecture.md` "Adding New Agents" note |
| 9  | Recommended. Delete the empty `product_prd_writing_task:` stub on line 842. Rename the body on line 845 from `prd_writing_task:` to `product_prd_writing_task:`. Q2's prefix convention is preserved. | workflow-2 spec edit |
| 10 | Recommended + scope additions. Add `tools/pytrends_tool.py` and `tools/scoring_rubric_tool.py` to roadmap Phase 1. Add `tools/vision_tool.py` to Phase 6. Update workflow-2 "Tools Required" table. `agents.yaml` references custom tools by class-name string; `dept_crews.py` imports and registers them. `store_scraper.py` shells out to Node via `subprocess.run` for the npm packages — single long-lived Node process is a Phase 7 optimisation. | roadmap + workflow-2 + architecture edits |
| 11 | Recommendation B (the stronger of the two): rewrite Workflow 1 and Workflow 3 specs to mirror Workflow 2's per-dept-crew structure. **Also pin Workflow 3 explicitly as `content_dept_crew → CEO threads brief into → automation_dept_crew`** (Q2's "specialists never talk across departments" rule forces a CEO-mediated handoff anyway — call it out now). Defer the "does the Q5 interpretation pattern generalise?" question to per-workflow planning. | workflow-1 + workflow-3 spec edits |
| 12 | Recommended. Split Phase 3 → 3a (briefs, manual posting) + 3b (Skyvern auto-post). `skyvern_tool.py` stub raises `NotImplementedError` in 3a with a clear "post manually" message. Phase 0c install batch trigger moves from "before Phase 3" to "before Phase 3b". | **ADR-0003** |
| 13 | Stronger than Recommended A. Adopt **`memory=False` on both dept_crews** instead of run-scoped collection names. Justification: after Q6 + Q7, all inter-agent state flows via explicit task `context:` — ChromaDB has no concrete consumer left inside the crew. Stricter than ADR-0000 Q2's per-dept isolation promise, not a violation of it. Upgrade path if needed later: ephemeral (RAM-only) ChromaDB client per `Crew` instance. | **ADR-0002** + `architecture.md` rewrite of "Per-Department Memory Isolation" section |
| 14 | Recommended. Minimal `cost_guard.py`: `start_run / log_call / end_run / check_budget`. Hooked into CrewAI `step_callback` / `task_callback`. 200k-token hard cap per run. On exceed: `BudgetExceeded` raised, caught by `jarvis_ceo.run_workflow_2`, `runs.json` status set to `failed`, `cost_exceeded.txt` written to `backend/output/`. Daily cap + automatic model fallback deferred to Phase 7. Hardcoded $/token table per model for Phase 1. | roadmap Phase 1 step list edit + workflow-2 spec |
| 15 | Refined Recommendation A. Save `research_brief` via `sync_research()` **immediately after `research_crew.kickoff()` returns, before the human gate** — brief is durable through any later crash. Treat `ask_user()` returning `None` (timeout) as decline (currently slips through as truthy). Add `run_workflow_2_prd_only(idea, brief_path)` for cheap recovery from a PRD-write crash. Skip the `PRD_PARTIAL` step_callback approach — too much code for too little payoff. | workflow-2 spec "Crew Assembly — File 1" snippet edit |

### ADRs added this session

- **ADR-0002** — *Reshape research_dept_crew: parallel specialists, dedicated interpreter, no semantic memory* (Q6 + Q7 + Q13)
- **ADR-0003** — *Split Phase 3 into 3a (briefs) and 3b (Skyvern auto-post)* (Q12)

### Punch list — spec edits to apply next session

The decisions above are durable. The following files still need their text updated to match. Work through them in this order:

1. `docs/adr/0000-grilling-session-2026-06-01.md` — append a correction note: ADR-0000 Q5 paragraph claiming *"the director is already the `manager_agent` — a cheap single-call task it executes is the lightest possible change"* is superseded by ADR-0002 (Q7).
2. `docs/architecture.md`
   - Rewrite "Per-Department Memory Isolation" section as "Per-Department Crew Isolation; in-dept memory disabled by default" (Q13).
   - "Adding New Agents" section — pin the flat-keys + `dept:` field convention (Q8). Add a "Tool registration" paragraph (Q10).
   - Decision Log table — append rows for Q11, Q12, Q13, Q14, Q15.
3. `docs/workflows/workflow-2-research-prd.md` — apply Q6 (async tasks), Q7 (`research_interpreter` stanza + Pydantic), Q8 (delete dup `product_director`, drop Proposal X example), Q9 (rename PRD task + delete stub), Q10 (Tools Required table additions), Q13 (`memory=False` in both `build_*_dept_crew()` snippets), Q14 (`cost_guard.start_run` / `end_run` wired into `run_workflow_2`), Q15 (save brief before gate + PRD-only shortcut + None-as-decline).
4. `docs/workflows/workflow-1-design-validation.md` — Q11 structural rewrite (per-dept-crew pattern).
5. `docs/workflows/workflow-3-social-media-engine.md` — Q11 structural rewrite + pin content → CEO → automation handoff + Q12 testing checklist annotations (3a vs 3b). — **APPLIED 2026-06-01 (Q12 portion; Q11 rewrite pending separate session).** Spec restructured into a Phase 3a / Phase 3b split per [ADR-0003](0003-split-phase-3-skyvern-fallback.md): the "What This Workflow Does" preamble now states the split, the agent hierarchy demotes `automation_dept_crew` to a "Phase 3b (DEFERRED)" callout, Steps 1–6 are under a `## Full Pipeline — Phase 3a: Briefs only` heading, Steps 7–9 are under `## Full Pipeline — Phase 3b: Skyvern auto-post (deferred)`, the testing checklist is split into two checklists (3a capability matrix + 3b auto-post), the brief filename is `Brief_{topic}_{YYYY-MM-DD}.md`, the `social_poster` agent entry is annotated as "Phase 3a: present in agents.yaml, never invoked", and the cost line is updated to "₹1.50–11 depending on platform count" (ADR-0003 capability reading). The Q11 per-dept-crew rewrite of the body and tasks.yaml (flat `dept: content` keys, `build_content_dept_crew()` factory) is partially applied (YAML preview uses `dept: content`; full Q11 alignment of all 3 workflows is a follow-up session).
6. `docs/roadmap.md` — Q10 tool additions to Phase 1 + Phase 6 step lists; Q12 Phase 3 split into 3a/3b; Q14 cost_guard wiring entry; Q12 Phase 0c trigger rewrite ("before Phase 3b"). — **Q12 portion APPLIED 2026-06-01.** Phase 3 is now split into `### Phase 3a — Workflow 3 (briefs only)` and `### Phase 3b — Workflow 3 (Skyvern auto-post)`, each with its own Steps, Definition of done, and Files created. Phase 0c header is now `### Phase 0c — Phase 3b prep (Skyvern install batch)` with a `**Trigger:** This phase runs only when Phase 3b starts, not before Phase 3. Phase 3a (briefs only) does not require any of these installs. (Per ADR-0003)` line. Q10 (Phase 1 `pytrends_tool.py` + `scoring_rubric_tool.py`, Phase 6 `vision_tool.py`) and Q14 (cost_guard wiring entry) are still pending — covered in a follow-up session.

No new ADRs needed beyond 0002 and 0003 — the remaining items are spec edits that derive from existing decisions.

---

*End of follow-up grilling notes — fully resolved.*
