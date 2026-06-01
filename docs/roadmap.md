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

**Definition of done:** Running `python backend/main.py` prints agent output in terminal with no errors.

### Steps

- [ ] Delete old Jarvis project locally and on GitHub
- [ ] Create new GitHub repo: `jarvis` (private)
- [ ] Clone repo to Mac: `git clone ...`
- [ ] Create full folder structure (all folders and placeholder files)
- [ ] Install base dependencies:
  - Python 3.11, pip, pipx, node, git
  - CrewAI + crewai-tools
  - openai, anthropic SDK
- [ ] Install scraping tools:
  - firecrawl-py, praw, pytrends, playwright, beautifulsoup4
  - npm: google-play-scraper, app-store-scraper
- [ ] Install automation tools:
  - open-interpreter, pyautogui, skyvern
- [ ] Create `.env` from `.env.example` — fill all API keys
- [ ] Run `env_validator.py` — confirms all keys present
- [ ] Set up logger — `logger.py` writes to `logs/jarvis.log`
- [ ] Run hello-world CrewAI crew — one agent, one task, prints output
- [ ] First git commit: `init: project structure and environment`

### Files created this phase
```
backend/utils/logger.py
backend/utils/env_validator.py
backend/main.py              ← minimal FastAPI stub
.env.example
.gitignore
scripts/setup.sh
```

---

## Phase 1 — Workflow 2: Research → Market Validation → PRD

**Goal:** Type one sentence about an app idea. Jarvis produces a scored market report and full PRD.

**Definition of done:** Running Workflow 2 end-to-end produces a real `.md` PRD file in `/backend/output/`.

**Priority: HIGHEST — this is the core value of the entire system.**

### Steps

- [ ] Write `config/agents.yaml` — all 8 agents for Workflow 2:
  - manager, pain_point_hunter, competitor_mapper, revenue_estimator, gap_finder, trend_validator, audience_sizer, synthesis_agent
- [ ] Write `config/tasks.yaml` — all tasks for Workflow 2
- [ ] Write `tools/store_scraper.py` — wraps google-play-scraper + app-store-scraper
- [ ] Write `tools/firecrawl_tool.py` — wraps Firecrawl API
- [ ] Write `tools/reddit_tool.py` — wraps PRAW for subreddit search
- [ ] Write `crews/research_crew.py` — assembles agents + tasks, runs parallel where possible
- [ ] Wire crew into `main.py` — callable via function
- [ ] Add cost_guard.py — log token usage per run
- [ ] Test with real app idea (e.g. "a habit tracker for Indian college students")
- [ ] Human gate working — crew pauses, prints score, asks for go/no-go
- [ ] PRD output saved as markdown to `/backend/output/`
- [ ] Memory: key findings written to Obsidian vault via `obsidian_sync.py`
- [ ] Git commit: `feat: workflow-2 research and PRD crew working`

### Files created this phase
```
backend/config/agents.yaml
backend/config/tasks.yaml
backend/tools/store_scraper.py
backend/tools/firecrawl_tool.py
backend/tools/reddit_tool.py
backend/crews/research_crew.py
backend/memory/obsidian_sync.py
backend/utils/cost_guard.py
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

- [ ] Add `app_store_analyst` agent to `agents.yaml`
- [ ] Add Workflow 4 tasks to `tasks.yaml`
- [ ] Write `crews/social_crew.py` — reuses store_scraper + firecrawl tools
- [ ] Output saved to `/backend/output/AppStore_report_date.md`
- [ ] Git commit: `feat: workflow-4 app store intelligence report`

### Files created this phase
```
backend/crews/content_crew.py    ← stub for later
```
*(Mostly config additions to existing files)*

---

## Phase 3 — Workflow 3: Social Media Content Engine

**Goal:** Trigger once → get platform-specific viral content briefs for YouTube, Instagram, Twitter, Reddit. Drop finished file → Skyvern posts it.

**Definition of done:** Brief generated for all 4 platforms + Skyvern successfully posts to at least one.

### Steps

- [ ] Add social agents to `agents.yaml`:
  - trend_scanner, trend_analyser, viral_idea_generator, community_angle_agent
- [ ] Add Workflow 3 tasks to `tasks.yaml`
- [ ] Write `crews/social_crew.py`
- [ ] Add pytrends integration to tools
- [ ] Add Instagram/Reddit/Twitter trend fetching
- [ ] Configure Skyvern for Instagram posting
- [ ] Configure Skyvern for Twitter posting
- [ ] Upload gate: Jarvis watches `/backend/upload/` folder, triggers Skyvern on new file
- [ ] ntfy.sh notification: "Your brief is ready" → phone
- [ ] Git commit: `feat: workflow-3 social content engine and skyvern posting`

### Files created this phase
```
backend/crews/social_crew.py
backend/tools/trend_tool.py
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

**Goal:** Say "Hey Jarvis, research [topic]" → crew runs. Jarvis speaks the result back.

**Definition of done:** Wake word detected, Whisper transcribes command, correct crew triggered, Kokoro speaks summary.

### Steps

- [ ] Install: faster-whisper, sounddevice, kokoro-onnx, pyaudio, pvporcupine
- [ ] Write `voice/listener.py`:
  - Porcupine listens for "Hey Jarvis"
  - Faster-Whisper transcribes what follows
  - Intent parser maps speech → crew function
  - Crew runs, output summarised
  - Kokoro TTS speaks the summary
- [ ] Test with Workflow 2: "Hey Jarvis, research a to-do app for students"
- [ ] Test with Workflow 7: "Hey Jarvis, give me my morning briefing"
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
| 1 — UI Design Loop | design_crew.py + Claude vision integration + upload watcher |
| 5 — Competitor Teardown | Extends research_crew with deeper scraping |
| 6 — Content Pipeline | content_crew.py — topic → platform post |
| 7 — Morning Briefing | Scheduled summary of App Store + Reddit + trends |
| 8 — Mac Automation | Open Interpreter integration with safety confirmation |
| 9 — App Store Listing Optimiser | ASO agent using store data + SerperDev |
| 10 — Reddit Monitor | PRAW monitor + keyword alerts |

- [ ] Git commit per workflow: `feat: workflow-N complete`

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

- [ ] Core feature works end-to-end without errors
- [ ] Output saved to correct folder
- [ ] Logged to `jarvis.log`
- [ ] Cost logged if API calls were made
- [ ] Git committed with correct message
- [ ] `README.md` updated with what's now working

---

## Current Status

| Phase | Status |
|-------|--------|
| 0 — Setup | ⬜ Not started |
| 1 — Workflow 2 (PRD) | ⬜ Not started |
| 2 — Workflow 4 (App Store) | ⬜ Not started |
| 3 — Workflow 3 (Social) | ⬜ Not started |
| 4 — Frontend | ⬜ Not started |
| 5 — Voice | ⬜ Not started |
| 6 — Remaining Workflows | ⬜ Not started |
| 7 — Scheduling + Docker | ⬜ Not started |

> Update this table as phases complete.

---

*End of Roadmap v1.0*
