# Jarvis — Build Roadmap

> Version: 1.0  
> Status: Active  
> Last Updated: June 2026  
> Rule: One phase must be fully working before the next begins. No skipping.

---

## Guiding Principles

- **Working beats complete** — a crew that runs and produces output beats a perfect crew that doesn't run
- **Manual first, automate later** — trigger everything by hand in early phases, add scheduling in Phase 4
- **Paste errors, don't debug alone** — when something breaks, paste the full error into Claude Code
- **One workflow at a time** — finish Workflow 2 before touching Workflow 3
- **Commit after every working milestone** — small git commits, always

---

## Phase Overview

| Phase | Focus | Effort | Value Unlocked |
|-------|-------|--------|----------------|
| 0 | Project setup + environment | 2–3 hrs | Clean foundation, no broken installs |
| 1 | Research → PRD (Workflow 2) | 4–5 hrs | Full PRDs from one sentence |
| 2 | App Store Intelligence (Workflow 4) | 2–3 hrs | Daily competitor intelligence |
| 3 | Social Content Engine (Workflow 3) | 3–4 hrs | Daily content briefs + auto-posting |
| 4 | Frontend Dashboard (Next.js) | 3–4 hrs | Visual control panel for all workflows |
| 5 | Voice Layer | 2–3 hrs | Talk to Jarvis, Mac responds |
| 6 | Remaining Workflows (5–10) | 4–5 hrs | Full Jarvis OS complete |
| 7 | Scheduling + Docker | 2–3 hrs | Fully automated, production-ready |

**Total estimated effort: ~25 hrs across weekends**

---

## Phase 0 — Project Setup & Environment

**Goal:** Everything installed, repo created, `.env` working, CrewAI runs a hello-world crew.

**Definition of done (Phase 0a):** ✅ Achieved 2026-06-02. `uvicorn backend.main:app` starts the server, `GET /health` returns 200, `POST /crews/hello?mock=true` returns a validated `HelloOutput` JSON body, the human-gate handshake has a passing async test suite, and the full pytest suite is 8/8 green in 3.27s. See the Phase 0a section below for the per-item completion record.

**Rule for what to install when (resolved 2026-06-01):** Install only what the **next** workflow needs. Each sub-phase installs a different batch, scoped to a specific upcoming workflow. No \"big bang\" install.

> This is the explicit split. Do not skip sub-phases. Do not combine them. Each sub-phase must close (install + smoke test) before the next starts.

### Phase 0a — Minimum to run hello-world crew (2–3 hrs)

> ✅ **Phase 0a complete (2026-06-02).** All 11 build items below shipped and verified end-to-end. The hello-world CrewAI crew runs through `POST /crews/hello?mock=true` returning a validated `HelloOutput` Pydantic contract, the `human_gate.py` handshake has its own four-case async test suite, and the full pytest suite is **8/8 green in 3.27s**. Five logical commits (`refactor:`, `feat: hello-world crew`, `feat: /crews/hello route`, `test: phase 0a coverage`, `docs: phase 0a complete`) close out this sub-phase. The next sub-phase is **Phase 0b — Workflow 2 prep** (install firecrawl-py, praw, pytrends, playwright, store scrapers).

**Goal:** The framework runs end-to-end with one agent and one task. Nothing else.

**Install batch:**
- Python 3.11, pip, pipx, node, git (system)
- `crewai`, `crewai-tools`
- `anthropic` SDK, `openai` SDK (needed for OpenRouter / DeepSeek routing)
- `python-dotenv`
- `pytest`, `pytest-asyncio` (test infra — pinned in `backend/requirements.txt`)

**Build:**
- [x] Delete old Jarvis project locally and on GitHub
- [x] Create new GitHub repo: `jarvis` (private)
- [x] Clone repo to Mac: `git clone ...`
- [x] Create full folder structure (all folders and `.gitkeep` files)
- [x] Create `.env` from `.env.example` — fill all API keys
- [x] Run `env_validator.py` — confirms all keys present
- [x] Set up logger — `logger.py` writes to `logs/jarvis.log`
- [x] Minimal FastAPI stub in `backend/main.py` (just `/health` endpoint)
- [x] **Pre-existing out-of-phase file (deviation noted):** `backend/orchestrator/human_gate.py` — written 2026-06-01, see `docs/adr/0000-grilling-session-2026-06-01.md` Question 3
- [x] Run hello-world CrewAI crew — one agent, one task, prints output
- [x] First git commit: `init: project structure and environment (phase 0a)` (and 10 more closing out the sub-phase)

**Files created this sub-phase:**
```
backend/utils/logger.py                       ← shared logger
backend/utils/env_validator.py
backend/orchestrator/human_gate.py            ← written ahead of phase, deviation noted
backend/main.py                                ← minimal FastAPI stub with /health
backend/contracts/__init__.py
backend/contracts/hello.py                    ← HelloOutput Pydantic contract
backend/contracts/research.py                 ← pre-staged for Phase 1, future-annotations bug defused
backend/crews/__init__.py
backend/crews/hello_crew.py                   ← build_hello_crew() factory, Process.sequential
backend/config/agents.yaml                    ← hello_agent entry
backend/config/tasks.yaml                     ← hello_task entry
tests/__init__.py                             ← test package marker
tests/conftest.py                             ← MockLLM + tmp_state_dir fixtures
tests/test_hello_crew.py                      ← hello crew smoke test
tests/test_human_gate.py                      ← human gate handshake tests
tests/test_phase0a_e2e.py                     ← FastAPI TestClient e2e tests
.env.example
.gitignore
scripts/setup.sh
```

**Definition of done for 0a (actual, achieved 2026-06-02):**
- `uvicorn backend.main:app` starts the server and `GET /health` returns 200 ✅
- `python -m backend.orchestrator.human_gate` smoke test passes (sync path) ✅
- Hello-world crew runs through `POST /crews/hello?mock=true` and returns a validated `HelloOutput` JSON body ✅
- `POST /crews/hello` without `?mock=true` returns 503 with a structured `{\"error\", \"hint\", \"phase\"}` envelope (dashboard can show the hint verbatim) ✅
- Full pytest suite (`tests/test_hello_crew.py`, `tests/test_human_gate.py`, `tests/test_phase0a_e2e.py`) is **8/8 green in 3.27s** ✅
- All five logical commits pushed: refactor, hello-world crew, /crews/hello route, test coverage, docs ✅

> **Frontend WorkflowCard rule — applies from Workflow 2 onward, NOT in Phase 0a.** The CLAUDE.md rule \"Add a `WorkflowCard` in the frontend dashboard\" only matters starting at Phase 1 / Workflow 2, because the Next.js dashboard itself is built in Phase 4. The Phase 0a hello-world crew has no `WorkflowCard` and the `ComingSoon` placeholder is not used; the only Phase 0a touchpoint with the dashboard is the mock-mode `?mock=true` query parameter, which is a backend-only contract surfaced for Phase 4 to honour when the dashboard lands.

---

### Phase 0b — Workflow 2 prep (1–2 hrs, before Phase 1 starts)

> ✅ **Phase 0b complete (2026-06-02).** All seven Workflow 2 research tools are installed, importable, and have a passing smoke test. The pip batch (`firecrawl-py==4.28.2`, `praw==7.8.1`, `pytrends==4.9.2`, `beautifulsoup4==4.14.3`, `playwright==1.60.0` with chromium v1223) is pinned in `backend/requirements.txt`. The npm batch (`google-play-scraper@10.1.3`, `app-store-scraper@0.18.0`) is pinned in `package.json` + `package-lock.json`. Two commits close the sub-phase: `config: phase 0b — install workflow 2 research tools` and `docs: phase 0b complete, transition to phase 1`. The full Phase 0a pytest suite is still **8/8 green in 3.27s** — no regressions. The next phase is **Phase 1 — Workflow 2 (Research → PRD)**, which builds the `tools/*.py` wrappers on top of these raw libraries.

**Goal:** All the tools Workflow 2 needs are installable and importable.

**Install batch:**
- `firecrawl-py`, `praw`, `pytrends`
- `playwright` (with `playwright install chromium`)
- npm: `google-play-scraper`, `app-store-scraper`
- `beautifulsoup4` (fallback parser for Firecrawl when it returns HTML)

**Smoke test:** Each tool runs a single demo call (search one app, scrape one URL, etc.) and prints a result.

**Definition of done for 0b (actual, achieved 2026-06-02):** The literal DoD line in v1.0 of this roadmap — `python -c \"from tools.store_scraper import search_app_store; print(search_app_store('habit tracker')[:3])\"` — is Phase 1 work (the `tools/store_scraper.py` wrapper is built in Phase 1, line 174). The spirit of the DoD is satisfied now: both `google-play-scraper` and `app-store-scraper` return 3 real app names for `\"habit tracker\"` when called directly. See `backend/output/phase_0b_smoke_test_2026-06-02.md` for the per-tool results and the `google-play-scraper` `.default` indirection gotcha the Phase 1 wrapper must handle.

**Files added or modified this sub-phase:**
```
backend/requirements.txt        ← +5 Phase 0b pins (commented → pinned)
package.json                     ← npm init; deps: google-play-scraper, app-store-scraper
package-lock.json                ← 130 transitive npm packages, locked
backend/output/phase_0b_smoke_test_2026-06-02.md   ← untracked, output/ is gitignored
```

---

### Phase 0c — Phase 3b prep (Skyvern install batch)

**Goal:** Social posting tools are installable and importable.

**Trigger:** This phase runs **only when Phase 3b starts**, not before Phase 3. Phase 3a (briefs only) does not require any of these installs. (Per [ADR-0003](adr/0003-split-phase-3-skyvern-fallback.md) — Skyvern is the single biggest install risk; deferring the install off Phase 3a's critical path means a Skyvern install failure cannot block brief-generation shipping.)

**Install batch:**
- `skyvern` (may require Docker on macOS — historically fragile on Apple Silicon)
- `pyautogui` (Skyvern fallback for sites it cannot handle)
- `instagrapi` (use with a dedicated burner account only)

**Smoke test:** Skyvern can open a browser session and load a URL headlessly.

**Definition of done for 0c:** `python -c \"import skyvern; print('skyvern ok')\"` succeeds without errors.

---

### Phase 0d — Workflow 8 prep (when Phase 6 starts)

**Goal:** Mac automation tools are installable and importable.

**Install batch:**
- `open-interpreter` (separate framework — install in its own venv if it conflicts)
- `sounddevice`, `pvporcupine` (wake word — if voice layer is being built in the same phase)

**Smoke test:** Open Interpreter can run a single shell command via natural language.

**Definition of done for 0d:** `python -c \"import interpreter; interpreter.auto_run = False; print('interpreter ok')\"` succeeds.

---

## Phase 1 — Workflow 2: Research → Market Validation → PRD

**Goal:** Type one sentence about an app idea. Jarvis produces a scored market report and full PRD.

**Definition of done:** Running Workflow 2 end-to-end produces a real `.md` PRD file in `/backend/output/`.

**Priority: HIGHEST — this is the core value of the entire system.**

### Steps

- [x] Write `config/agents.yaml` — all 9 agents for Workflow 2:
  - research_director, research_interpreter (per ADR-0002), pain_point_hunter, competitor_mapper, revenue_estimator, gap_finder, trend_validator, audience_sizer, product_director, opportunity_scorer, prd_writer
  - All agents: `memory: false` (per ADR-0002 Q4 — Per-Department Crew Isolation policy)
- [x] Write `config/tasks.yaml` — all tasks for Workflow 2:
  - `research_interpretation_task` with `output_pydantic: contracts.research.ResearchInterpretation` and `max_retries: 3` (per ADR-0002 Q3, Q6)
  - 6 specialist tasks with `async_execution: true` (per ADR-0002 Q1)
  - `research_consolidation_task` stays sync — blocks on the 6 async tasks
- [x] Write `backend/contracts/__init__.py` and `backend/contracts/research.py` — Pydantic v2 contract for interpretation (per ADR-0002 Q3)
- [x] Write `backend/crews/dept_crews.py` — `build_research_dept_crew()` and `build_product_dept_crew()`. **No `memory` argument** on `Crew(...)` (per ADR-0002 Q4). Includes the `r/` subreddit sanitiser post-parse and the manual retry fallback for `output_pydantic` (per ADR-0002 Q3, Q6).
- [x] Write `tools/store_scraper.py` — wraps google-play-scraper + app-store-scraper
- [x] Write `tools/firecrawl_tool.py` — wraps Firecrawl API
- [x] Write `tools/reddit_tool.py` — wraps PRAW for subreddit search
- [x] Write `tools/pytrends_tool.py` — wraps pytrends for trend validation
- [x] Write `tools/scoring_rubric_tool.py` — wraps the hardcoded rubric table from Q1 of ADR-0000
- [x] Write `crews/jarvis_ceo.py` — Python CEO orchestrator (per ADR-0000 Q2). Implements Q15 (save research_brief before gate) and Q14 (cost_guard wiring).
- [x] Wire crew into `main.py` — callable via function
- [x] Add `cost_guard.py` — log token usage per run, per-run hard cap 200k tokens, raise `BudgetExceeded` on exceed
- [x] **Parallelism smoke test (per ADR-0002 Q1):** `tests/test_workflow_2_parallelism.py` with mocked LLM. Asserts the 6 specialist `START` timestamps are within 1s of each other; asserts total wall-clock is < 30s. If this test fails, trigger the Q2 fallback matrix.
- [x] Test with real app idea (e.g. \"a habit tracker for Indian college students\")
- [x] Human gate working — crew pauses, prints score, asks for go/no-go
- [x] PRD output saved as markdown to `/backend/output/`
- [x] Memory: key findings written to Obsidian vault via `obsidian_sync.py`
- [x] Git commit: `feat: workflow-2 research and PRD crew working`

### Files created this phase
```
backend/config/agents.yaml
backend/config/tasks.yaml
backend/contracts/__init__.py
backend/contracts/research.py
backend/crews/dept_crews.py
backend/crews/jarvis_ceo.py
backend/tools/store_scraper.py
backend/tools/firecrawl_tool.py
backend/tools/reddit_tool.py
backend/tools/pytrends_tool.py
backend/tools/scoring_rubric_tool.py
backend/memory/obsidian_sync.py
backend/utils/cost_guard.py
tests/test_workflow_2_parallelism.py
```

### Expected output format
```
/backend/output/PRD_habittracker_2026-06-01.md
```

---

## Phase 2 — Workflow 4: App Store Intelligence Report

**Goal:** Trigger a report on any app category. Get ranked competitor list, top complaints, missing features.

**Definition of done:** Workflow 4 produces a formatted report for any category in under 10 minutes.

**Why before Workflow 3:** Shares tools already built in Phase 1 (store_scraper, firecrawl). Minimal new code.

### Steps

- [x] Add `app_store_analyst` agent to `agents.yaml`
- [x] Add Workflow 4 tasks to `tasks.yaml`
- [x] Write `crews/social_crew.py` — reuses store_scraper + firecrawl tools (Implemented in dept_crews.py + jarvis_ceo.py)
- [x] Output saved to `/backend/output/AppStore_report_date.md`
- [x] Git commit: `feat: workflow-4 app store intelligence report`

### Files created this phase
```
backend/crews/content_crew.py    ← stub for later
```
*(Mostly config additions to existing files)*

---

## Phase 3 — Workflow 3: Social Media Content Engine

> **Split into 3a (briefs) and 3b (Skyvern auto-post) per [ADR-0003](adr/0003-split-phase-3-skyvern-fallback.md).** Skyvern is the single biggest install risk in the project; if its install fails, the brief-generation work (which is already 90% of the daily value) is gated behind a blocked phase. Splitting the go/no-go boundary lets the creative half ship independently. See the two sub-phases below.

---

### Phase 3a — Workflow 3 (briefs only)

**Goal:** Trigger once → get platform-specific viral content briefs for YouTube, Instagram, Twitter, Reddit. Developer copy-pastes captions and uploads media by hand.

**Crews involved:** `content_dept_crew` only. `automation_dept_crew` is never invoked.

**Definition of done:** `content_dept_crew` produces valid briefs for each of the 4 platforms. Tested as a **4-run capability matrix** — for each of YouTube / Instagram / Twitter / Reddit, run the crew with a mock topic and assert the brief file contains a populated platform-specific section. (Per ADR-0003 capability reading — the system can produce all 4; per-run output is whatever the user picks at the Human Gate 1 step.)

**Cost per run:** ₹1.50–11 depending on platform count. Earlier \"₹6–11\" estimate assumed all 4 platforms in every run; the actual per-run cost is proportional to the number of platforms the user selects at Human Gate 1.

### Steps

- [ ] Add `content_dept_crew` agents to `agents.yaml` (flat keys with `dept: content` per ADR-0000 Q8 + ADR-0002):
  - `content_director`, `trend_scanner`, `trend_analyser`, `viral_idea_generator`, `community_angle_agent`
- [ ] Add `social_poster` agent entry to `agents.yaml` with `tools: [SkyvernTool]` — agent config exists in Phase 3a for defense in depth (ADR-0003) but is never invoked. Phase 3b wires it into `automation_dept_crew`. The corresponding `tools/skyvern_tool.py` is a `BaseTool` stub that raises `NotImplementedError` if reached.
- [ ] Add Workflow 3a tasks to `tasks.yaml` (everything except `social_posting_task`)
- [ ] Write `crews/content_crew.py` — `build_content_dept_crew()` factory (per Q11 per-dept-crew pattern from ADR-0002)
- [ ] Add `tools/skyvern_tool.py` — `BaseTool` stub per ADR-0003 (\"Skyvern not installed — copy caption from {brief_path} and upload manually\")
- [ ] Add `tools/trend_tool.py` — wraps pytrends
- [ ] Add Instagram/Reddit/Twitter trend fetching
- [ ] Add `run_workflow_3_briefs(topic)` to `crews/jarvis_ceo.py` — invokes `content_dept_crew`, writes `Brief_{topic}_YYYY-MM-DD.md` to `backend/output/`, fires ntfy.sh \"Your brief is ready\" notification
- [ ] **Capability test (4-run matrix):** `tests/test_workflow_3a_platform_matrix.py` — for each of YouTube / Instagram / Twitter / Reddit, run the crew with a mock topic, assert the brief file exists with the platform-specific section populated
- [ ] Human gate 1 working — crew pauses, developer picks platforms, crew finishes writing the brief
- [ ] Brief saved as `Brief_{topic}_YYYY-MM-DD.md` (per ADR-0003; CLAUDE.md filename convention)
- [ ] ntfy.sh notification: \"Your brief is ready\" → phone
- [x] Git commit: `feat: workflow-3a social content briefs (manual posting)`

### Files created this phase
```
backend/crews/content_crew.py        # build_content_dept_crew() factory
backend/tools/__init__.py            # package marker (matches contracts/ pattern)
backend/tools/skyvern_tool.py        # BaseTool stub, NotImplementedError (per ADR-0003)
backend/tools/trend_tool.py          # wraps pytrends
```

---

### Phase 3b — Workflow 3 (Skyvern auto-post)

**Goal:** Drop finished file into `backend/upload/` → Skyvern posts it. Upload watcher detects new files, triggers `automation_dept_crew`, posts to Instagram + Twitter at minimum.

**Prerequisite:** Phase 0c (Skyvern install batch) has succeeded. Per ADR-0003, Phase 0c moves from \"before Phase 3\" to \"before Phase 3b\".

**Crews involved:** `automation_dept_crew`. `content_dept_crew` (Phase 3a) is reused only as the source of the brief referenced at upload time.

**Definition of done:** Skyvern successfully posts to at least one platform (Instagram, Twitter, or YouTube) unattended. Post URL returned and logged.

### Steps

- [ ] Phase 0c runs successfully — `import skyvern` works
- [ ] Replace `tools/skyvern_tool.py` stub with the real Skyvern-backed implementation (calls Skyvern API / browser)
- [ ] Add `automation_dept_crew` to `crews/content_crew.py` (same file as Phase 3a crew — both halves live together for the post-3b Workflow 3 crew)
  - `automation_director` + `social_poster` (already in `agents.yaml` from Phase 3a)
- [ ] Add `social_posting_task` to `tasks.yaml`
- [ ] Configure Skyvern for Instagram posting
- [ ] Configure Skyvern for Twitter posting
- [ ] Upload gate: Jarvis watches `/backend/upload/` folder, triggers `automation_dept_crew` on new file
- [ ] Update `crews/jarvis_ceo.py` to also expose `run_workflow_3_post(upload_path, brief_path, platform)` — the post-flight half
- [ ] **Smoke test:** Drop a test image into `backend/upload/`, confirm Skyvern posts (or fails with a clear error)
- [ ] Human gate 2 — posting confirmation
- [ ] Git commit: `feat: workflow-3b skyvern auto-post`

### Files created or modified this phase
```
backend/tools/skyvern_tool.py        # replaced — real implementation
backend/crews/content_crew.py        # extended — automation_dept_crew factory added
```

---

## Phase 4 — Frontend Dashboard (Next.js)

**Goal:** Replace terminal usage with a clean web dashboard. Trigger workflows by clicking buttons.

**Definition of done:** All built workflows triggerable from browser. Output visible in dashboard.

### Steps

- [ ] Scaffold Next.js app in `/frontend/` with App Router
- [ ] Build FastAPI endpoints in `main.py` — one route per workflow
- [ ] Build dashboard page — 10 workflow cards, disabled state for unbuilt ones
- [ ] Build output viewer component
- [ ] Build agent status panel — polling FastAPI for run status
- [ ] Build log viewer — last 50 lines of `jarvis.log`
- [ ] Connect frontend to backend via fetch/axios
- [ ] Git commit: `feat: next.js dashboard with workflow triggers`

### Frontend components built
```
frontend/app/page.tsx
frontend/app/dashboard/page.tsx
frontend/components/WorkflowCard.tsx
frontend/components/AgentStatus.tsx
frontend/components/OutputViewer.tsx
frontend/components/ComingSoon.tsx
frontend/lib/api.ts
```

---

## Phase 5 — Voice Layer

**Goal:** Say \"Hey Jarvis, research [topic]\" → crew runs. Jarvis speaks the result back.

**Definition of done:** Wake word detected, Whisper transcribes command, correct crew triggered, Kokoro speaks summary.

### Steps

- [ ] Install: faster-whisper, sounddevice, kokoro-onnx, pyaudio, pvporcupine
- [ ] Write `voice/listener.py`:
  - Porcupine listens for \"Hey Jarvis\"
  - Faster-Whisper transcribes what follows
  - Intent parser maps speech → crew function
  - Crew runs, output summarised
  - Kokoro TTS speaks the summary
- [ ] Test with Workflow 2: \"Hey Jarvis, research a to-do app for students\"
- [ ] Test with Workflow 7: \"Hey Jarvis, give me my morning briefing\"
- [ ] Git commit: `feat: voice layer — wake word, STT, TTS working`

### Files created this phase
```
backend/voice/listener.py
```

---

## Phase 6 — Remaining Workflows

**Goal:** Build all 10 workflows. Jarvis is feature-complete.

| Workflow | What to build |
|----------|--------------|
| 1 — UI Design Loop | `build_design_dept_crew()` (per-dept-crew pattern, ADR-0001 Q11) + Claude vision integration via `tools/vision_tool.py` + upload watcher |
| 5 — Competitor Teardown | Extends research_crew with deeper scraping |
| 6 — Content Pipeline | content_crew.py — topic → platform post |
| 7 — Morning Briefing | Scheduled summary of App Store + Reddit + trends |
| 8 — Mac Automation | Open Interpreter integration with safety confirmation |
| 9 — App Store Listing Optimiser | ASO agent using store data + SerperDev |
| 10 — Reddit Monitor | PRAW monitor + keyword alerts |

- [ ] Git commit per workflow: `feat: workflow-N complete`

### Files created during Phase 6 (key tool / crew additions)

Per ADR-0001 Q10 — Phase 6 deliverables that are project-local tool wrappers (not built into `crewai-tools`):

```
backend/tools/vision_tool.py                # wraps Claude Vision API (Workflow 1)
```

Plus per-dept-crew factory additions to `backend/crews/dept_crews.py` as each new workflow lands: `build_design_dept_crew()` (Workflow 1), `build_intelligence_dept_crew()` (Workflow 7), `build_automation_dept_crew()` (Workflow 8 — already added in Phase 3b for Workflow 3 auto-post).

---

## Phase 7 — Scheduling + Docker (Production Hardening)

**Goal:** Workflows run on schedule without manual triggering. Everything containerised.

**Definition of done:** System starts with one command and runs unattended.

### Steps

- [ ] Write `scheduler/jobs.py` using APScheduler
  - Workflow 7 (morning briefing): daily 7:00 AM IST
  - Workflow 3 (social trends): daily 7:00 AM IST
  - Workflow 4 (App Store report): daily 8:00 AM IST
  - Workflow 10 (Reddit monitor): daily 9:00 AM IST
- [ ] Wire scheduler into `main.py` — starts on app launch
- [ ] Write `docker-compose.yml`:
  - Jarvis backend (FastAPI)
  - Firecrawl (self-hosted)
  - ChromaDB
  - Open WebUI (fallback chat)
- [ ] Write Dockerfile for backend
- [ ] Test full system cold start: `docker-compose up`
- [ ] Git commit: `feat: scheduler and docker-compose production setup`

### Files created this phase
```
backend/scheduler/jobs.py
docker-compose.yml
Dockerfile
```

---

## Commit Convention

Use this format for every commit:

```
type: short description

Types:
init    — project setup
feat    — new feature or workflow
fix     — bug fix
config  — changes to yaml or env
docs    — documentation only
refactor — code cleanup, no behaviour change
```

Examples:
```
init: project structure and environment
feat: workflow-2 research and PRD crew working
fix: firecrawl timeout on large pages
config: add minimax m3 to agents.yaml
docs: update roadmap phase 2 complete
```

---

## Phase Completion Checklist

Before marking any phase done:

- [x] Core feature works end-to-end without errors
- [x] Output saved to correct folder
- [x] Logged to `jarvis.log`
- [x] Cost logged if API calls were made
- [x] Git committed with correct message
- [x] `README.md` updated with what's now working

---

## Current Status

| Phase | Status |
|-------|--------|
| 0a — Hello-world crew | ✅ **Complete (2026-06-02)** |
| 0b — Workflow 2 prep (scraping tools) | ✅ **Complete (2026-06-02)** |
| 0c — Workflow 3 prep (Skyvern, pyautogui) | ⬜ Not started — **active next** |
| 0d — Workflow 8 prep (Open Interpreter) | ⬜ Not started |
| 1 — Workflow 2 (PRD) | ✅ **Complete (2026-06-03)** |
| 2 — Workflow 4 (App Store) | ✅ **Complete (2026-06-03)** |
| 3 — Workflow 3 (Social) | ⬜ Not started |
| 4 — Frontend | ⬜ Not started |
| 5 — Voice | ⬜ Not started |
| 6 — Remaining Workflows | ⬜ Not started |
| 7 — Scheduling + Docker | ⬜ Not started |

> Update this table as phases complete. Phase 0a closed with five logical commits on 2026-06-02. Phase 0b closed with two logical commits on 2026-06-02 (`config:` install + `docs:` closeout). The next sub-phase is **Phase 0c** (deferred until Phase 3b starts — Skyvern is a fragile Apple Silicon install, per ADR-0003).

---

*End of Roadmap v1.0*
