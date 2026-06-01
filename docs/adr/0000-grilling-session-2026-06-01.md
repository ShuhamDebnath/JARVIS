# Grilling Session — 2026-06-01

> Captured live as Claude Code interrogates the Jarvis plan one decision at a time.
> Source files reviewed: `CLAUDE.md`, `AI-RULES.md`, `docs/prd.md`, `docs/architecture.md`, `docs/roadmap.md`, `docs/workflows/workflow-1-design-validation.md`, `docs/workflows/workflow-2-research-prd.md`, `docs/workflows/workflow-3-social-media-engine.md`.

---

## Open Questions (Pending Resolution)

(Filled in as we go — each question gets a recommended answer + your decision.)

---

## Question 1 — Opportunity Score Calibration (RESOLVED)

**Issue raised:** The opportunity score out of 50 is the load-bearing decision in Workflow 2 — the user builds or skips based on this number. The original spec was a single LLM doing holistic 5-dimension scoring with no calibration evidence, no rubric, and a placeholder threshold of 35.

**Decision: Hybrid rubric** — 4 hard sub-scores extracted from explicit data points via a strict rubric + 1 subjective sub-score for build effort.

**Reasoning (Shuham's architectural rationale):**
- LLMs are bad at arbitrary math — they hallucinate plausible-looking numbers that aren't grounded in reality
- The go/no-go decision needs to be explainable — hard sub-scores give the user a reason to trust the score
- Build effort is genuinely subjective — an LLM reading a feature list and estimating Flutter complexity is exactly what LLMs are good at
- 4 hard + 1 subjective gives the best of both worlds: data for the market, AI reasoning for engineering

**Implementation:** Spec updated in `docs/workflows/workflow-2-research-prd.md` — `opportunity_scorer` agent and `opportunity_scoring_task` task now require strict rubric-based extraction for 4 dimensions and explicit LLM-only estimation for build effort. The 35/50 threshold is explicitly marked as a default to be empirically validated after 10+ real runs.

---

## Question 2 — Three-Level Hierarchy vs CrewAI's Two-Level Process (RESOLVED)

**Issue raised:** Architecture mandates a 3-level CEO → Department Head → Specialist hierarchy, and rules say "always use `process=Process.hierarchical`". But CrewAI's hierarchical process is 2 levels natively (one `manager_agent` + a pool of workers). With `allow_delegation: true` everywhere, specialists can call any other agent — the "specialists never talk to other departments" rule becomes impossible to enforce.

**Decision: Per-department sub-crews composed by a Python CEO orchestrator.** The CEO is plain Python, not a CrewAI agent. Each department has its own `Crew(process=Process.hierarchical)` with the department head as `manager_agent`. The CEO calls each `dept_crew.kickoff()` in sequence or parallel and threads outputs as inputs to the next.

**Reasoning (Shuham's architectural rationale):**
- Per-department sub-crews make the 3-level diagram in the docs actually real, not aspirational
- Each `dept_crew` has its own ChromaDB collection → solves the "memory bleeding between runs" issue called out in the Workflow 2 spec
- Cross-department state is explicit text inputs, not implicit shared vector store — easier to debug
- "Specialists never talk to other departments" becomes mechanically enforced (they literally cannot, they're in different crews)
- Department-level reset is trivial — drop one ChromaDB collection, no risk to other departments

**Trade-off accepted:** Lose cross-department shared `memory=True`. Gain clean isolation, deterministic inter-dept data flow, and enforceable hierarchy rules.

**Implementation:** Specs updated in:
- `docs/architecture.md` — rewrote "Agent Hierarchy" section, CEO is now Python not LLM; added "Per-Department Memory Isolation" section; updated Data Flow; added new entry to Decision Log
- `docs/workflows/workflow-2-research-prd.md` — split into `research_dept_crew` + `product_dept_crew`; added `dept:` field to every agent; prefixed all tasks with `research_` or `product_` to prevent collisions; replaced `research_crew.py` with three files: `jarvis_ceo.py` + `dept_crews.py` + `orchestrator/human_gate.py`

---

## Question 3 — Human Gate Mechanism (RESOLVED)

**Issue raised:** Every workflow has at least one "human gate" but the docs never specify how the gate actually works. CrewAI's `human_input: true` only works in CLI mode (stdin prompt). In a FastAPI + browser dashboard, the crew runs on the server while the user is in a different process — there is no stdin. The new Python CEO orchestrator (from Question 2) is plain Python, so `human_input: true` is doubly detached from the actual decision point.

**Decision: Async pause/resume via `ask_user()` / `receive_user_reply()` + a JSON-file state store.**

**Implementation:** `backend/orchestrator/human_gate.py` is now written (out-of-phase, see note below). It exposes:
- `new_run_id()` — generates a uuid for each workflow run
- `get_run_status(run_id)` — read by FastAPI for the dashboard poll
- `async ask_user(run_id, prompt, timeout_s)` — blocks the CEO orchestrator until reply or timeout, polls the state file every 1 second
- `receive_user_reply(run_id, reply)` — flips the state row to "done", wakes the polling `ask_user`
- State stored in `backend/state/runs.json` via atomic tmp+rename writes
- 24h default timeout (user might trigger a run at 11pm and reply next morning)
- Module-level `logging` instead of `print()` per AI-RULES.md Rule 2 — comment notes it should be replaced with `backend/utils/logger.py` when that file exists
- `__main__` smoke test — verified passing on 2026-06-01

**Phase discipline deviation (noted):** This file is technically Phase 1 work, but the user explicitly overrode AI-RULES.md Rule 9 to write it now. Reason given: the FastAPI layer needs the architecture in place so Phase 0's hello-world can use the same pattern. All other Phase 1 work must wait for Phase 0 to finish. If two more out-of-phase files are written before Phase 0 closes, the deviation pattern should be re-discussed.

**Trade-off accepted:** JSON file is slower than in-memory, but debuggable (`cat runs.json` shows the state) and survives restarts. Phase 7 production swaps to SQLite WAL — same contract.

---

## Question 4 — Phase 0 Install Scope (RESOLVED)

**Issue raised:** Phase 0's definition of done is "hello-world crew runs" but its install list pulls in Skyvern, Open Interpreter, PyAutoGUI, Playwright, and both store-scraper npm packages — all of which are only used in Phase 3+ (Workflow 3, 6, 8). One failed install (Skyvern is the worst offender on macOS) blocks the entire Phase 0. Estimated 2–3 hours is unrealistic; reality is 4–6 hours with a high failure risk.

**Decision: Split Phase 0 into 0a / 0b / 0c / 0d. Install only what the next workflow needs.**

| Sub-phase | Install batch | Trigger |
|-----------|--------------|---------|
| **0a** (current) | Python, CrewAI, anthropic, openai SDK, python-dotenv | Already active |
| **0b** | firecrawl-py, praw, pytrends, playwright, beautifulsoup4, store scrapers (npm) | Before Phase 1 starts |
| **0c** | skyvern, pyautogui, instagrapi | Before Phase 3 starts |
| **0d** | open-interpreter, sounddevice, pvporcupine | Before Phase 6 starts |

**Reasoning (Shuham's rationale):**
- Each sub-phase has a small, scoped install — failure blocks one workflow, not the whole system
- "Working beats complete" is the roadmap's first principle — install the minimum needed to get the next thing working
- Manual install also exposes what's actually needed vs. what's nice-to-have

**Implementation:** Specs updated in:
- `docs/roadmap.md` — Phase 0 split into 0a/0b/0c/0d with per-sub-phase install batches, smoke tests, and definitions of done
- `CLAUDE.md` — Current Phase section now points to Phase 0a specifically
- `docs/roadmap.md` — Current Status table now lists the four sub-phases separately

**Trade-off accepted:** More install runs over the project's lifetime. Gained: each install is fast, scoped, and has a clear smoke test.

---

## Question 5 — Non-Deterministic Interpretation of One-Sentence Input (RESOLVED)

**Issue raised:** Workflow 2 starts with the user typing one sentence (e.g. "a habit tracker for Indian college students"). The CEO passes that string as `{"idea": "..."}` to `research_dept_crew.kickoff()`. Inside the crew, the `research_director` (manager_agent) decomposes it and delegates to 6 specialists. Each specialist independently re-interprets the same raw sentence before searching. Because LLM interpretation is non-deterministic, the same input can produce 6 different research directions across the 6 specialists — and across different runs of the same idea. Two runs of the same idea can produce two unrelated PRDs.

**Concrete example (input = "a habit tracker for Indian college students"):**

- Run 1: `pain_point_hunter` searches `r/getdisciplined`, `r/IndianHabits`; `competitor_mapper` searches App Store for "habit tracker"; `gap_finder` reads habit app reviews; `trend_validator` trends "habit tracker"; `revenue_estimator` looks at freemium habit apps; `audience_sizer` sizes `r/india`.
- Run 2: `pain_point_hunter` searches `r/meditation`, `r/study`; `competitor_mapper` searches "study planner"; `gap_finder` reads meditation app reviews; `trend_validator` trends "student productivity"; `revenue_estimator` looks at subscription study apps; `audience_sizer` sizes `r/IndianTeenagers`.

Different research, different data, different opportunity score, different PRD. The user runs the same idea twice and gets two different PRDs.

**Root cause:** The `research_director` decomposition is a single LLM call with no shared, structured output. Each specialist receives the raw sentence plus a brief role description and makes its own guess about scope. There is no canonical interpretation that all 6 share.

**Decision: Add `research_interpretation_task` as task 0 in Workflow 2 — a single LLM call that runs before the 6 specialists fan out and produces a structured JSON interpretation document that all 6 specialists consume as task context.**

**Task definition (new, runs first in `research_dept_crew`):**

```yaml
research_interpretation_task:
  description: >
    Interpret the user's one-sentence app idea into a structured brief.
    Output ONLY this JSON shape — no other text, no markdown fences.
    {
      "app_category": "productivity | health | education | finance | social | utility | other",
      "target_user": "<one-sentence demographic>",
      "core_problem": "<one-sentence problem statement>",
      "search_keywords": ["<5 keywords all specialists must use>"],
      "subreddits_to_monitor": ["<5 subreddit names>"],
      "app_store_categories": ["<2 iOS + 2 Google Play categories>"],
      "ambiguity_flag": "<if the idea is genuinely unclear, write 'AMBIGUOUS: <why>'. Otherwise null.>"
    }
  expected_output: >
    Valid JSON only. No prose, no markdown fences. The next task in this
    crew depends on this output being parseable.
  agent: research_director    # director does the interpretation, not a specialist
  output_json: true
```

**Each of the 6 specialist tasks gets:**

```yaml
context: [research_interpretation_task]
```

And gets a one-line note in its description: *"Use the interpretation document above. Do not re-interpret the idea. Use the search_keywords, subreddits, and app_store_categories from the document."*

**Why the director does the interpretation (not a new agent):** Adding a new agent would be a 6th file change (departments, hierarchy, etc.). The director is already the `manager_agent` — it owns the workflow. A cheap single-call task it executes is the lightest possible change. If interpretation quality turns out to be poor in early runs, the cheap fix is to give the director a stricter system prompt, not to spin up a new agent.

**Ambiguity flag handling:** If `ambiguity_flag` is non-null, the CEO orchestrator surfaces it to the user via the existing `human_gate.ask_user()` mechanism (per Question 3) with a "Did you mean X or Y?" question. If the user does not reply within the gate's 24h timeout, the workflow proceeds with the most likely interpretation and the flag is echoed into the final PRD's "Assumptions" section so the user sees what Jarvis assumed.

**Why this works (Shuham's architectural rationale):**
- The interpretation is **structured JSON, not free text** — parseable, debuggable, testable, loggable
- All 6 specialists now share one canonical interpretation — two runs of the same idea produce two very similar PRDs (same keywords, same subreddits, same App Store categories) instead of two unrelated ones
- Day-one trustworthiness: the user can re-run the same input and get a comparable result, which is the whole point of a research tool
- The interpretation is the natural place to add the "ask a clarifying question" human gate in the future — already structured, already JSON

**Cost:** +1 LLM call per Workflow 2 run (~5 seconds, ~₹0.50 with DeepSeek). Negligible against the 6 parallel specialist calls.

**Trade-off accepted:** Slightly slower Workflow 2 runs. Gained: reproducibility, debuggability, structured place for the "ask clarifying question" gate, and a single canonical interpretation to point at when the user says "the PRD is wrong."

**Implementation:** Spec updated in `docs/workflows/workflow-2-research-prd.md`:
- `tasks.yaml` block — new `research_interpretation_task` added as the first task; each of the 6 specialist tasks gets `context: [research_interpretation_task]`; the `expected_output` of each specialist task is tightened to reference the interpretation
- "Agent Hierarchy for This Workflow" — Flow steps expanded to make interpretation task 0 explicit
- "Full Pipeline — Step by Step" — Step 2 now begins with the interpretation step
- "Cost Estimate Per Run" — bumped to 7 specialist LLM calls + 1 interpretation call
- "Testing Checklist" — new test: run the same idea twice, confirm interpretation JSON is identical, confirm downstream specialist outputs use the same keywords/subreddits

`docs/architecture.md` and `docs/roadmap.md` — **not changed**. The interpretation task is a Workflow 2 internal design decision, not a system-wide architecture change. The 3-level hierarchy, the Python CEO orchestrator, the per-dept sub-crew pattern, the ChromaDB-per-dept isolation, and the Phase 1 effort estimate are all unaffected.

---

## Correction note — appended 2026-06-01 (per ADR-0002, grilling session 3)

**The paragraph above beginning "**Why the director does the interpretation (not a new agent):**" is superseded by ADR-0002 (Q7).** The argument that *"a cheap single-call task it executes is the lightest possible change"* was wrong under CrewAI's actual manager-prompt behaviour: the manager-agent system prompt is conditioned to call its `Delegate work to coworker` tool, and when the same agent is asked to produce JSON directly, the routing competes with the JSON contract and breaks the reproducibility guarantee that Q5 was created to provide.

**The correct decision (ADR-0002, grilling session 3, 2026-06-01):** The interpretation task is executed by a new dedicated Level-3 specialist, `research_interpreter` (in `agents.yaml`), with `allow_delegation: false` and `tools: []`. The director is now coordinator + consolidator only — manager_agent of `research_dept_crew` plus executor of `research_consolidation_task`. The interpretation schema is enforced by Pydantic v2 via `output_pydantic` (see `backend/contracts/research.py`) with `max_retries: 3` and a manual retry fallback.

This correction is purely architectural — the spirit of Q5 (reproducible interpretation, single canonical brief) is unchanged. The mechanism for achieving it is corrected.

---
