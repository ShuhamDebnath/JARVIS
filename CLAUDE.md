# CLAUDE.md — Jarvis Project Instructions for Claude Code

> This file is read automatically by Claude Code at the start of every session.
> Do not delete or rename this file.
> Last Updated: June 2026

---

## What This Project Is

Jarvis is a personal AI operating system for a solo mobile app developer based in Bengaluru, India. It automates market research, competitor analysis, content creation, social posting, and UI validation using a multi-agent CrewAI framework.

This is a private single-user system. It is not a SaaS product. There is no auth, no multi-user support, no billing.

**Read these before touching any code:**
- `docs/prd.md` — what Jarvis is and what it must do
- `docs/roadmap.md` — what phase we are in and what is being built right now
- `docs/architecture.md` — every tool decision and why it was made

---

## Owner Profile

- Mobile app developer (iOS / Android / Flutter)
- Bengaluru, India — IST timezone
- Beginner-to-intermediate Python — prefers YAML config over writing Python from scratch
- Gets stuck when code has too much boilerplate or unexplained magic
- Preferred workflow: paste errors → get fixed code → move on

**How to write code for this owner:**
- Prefer simple and explicit over clever and compact
- Always add inline comments explaining what each block does
- Never use advanced Python patterns without explaining them in a comment
- YAML config first — if something can be configured in YAML instead of Python, do it in YAML
- When something might fail, add a clear error message that says what went wrong and what to do

---

## Current Phase

> **Update this section every time a phase completes.**

**Active phase:** 🚀 **Phase 5 — Voice Layer.** Phase 4 (Frontend Dashboard) is fully shipped. Next.js dashboard running at `http://localhost:3000` with `WorkflowCard`, `AgentStatus`, and `OutputViewer` components.

**Completed phases:**
- ✅ **Phase 0c (June 2026)** — Automation Setup: skyvern + pyautogui installed, requirements.txt pinned, .env.example updated with SKYVERN_BROWSER_API_KEY.
- ✅ **Phase 3b (June 2026)** — Workflow 3b Auto-Post: build_automation_dept_crew() implemented, run_workflow_3_post() added to jarvis_ceo.py, POST /workflows/auto-post endpoint wired in FastAPI.
- ✅ **Phase 1 — COMPLETE.** Phase 1 (Research → PRD Infrastructure and Integration) is fully shipped and verified. All 25 core unit tests pass. Structural fixes for MiniMax reliability (circuit breakers, manual JSON validation, tool formatting rules) are permanently integrated. Phase 1 Workflow 2 (Research → PRD) is now operational with high-reliability Python shims.
- ✅ **Phase 2 — COMPLETE.** Phase 2 (Intelligence Layer) is fully shipped. Workflow 4 (App Store Intelligence) is operational.
- ✅ **Phase 3 — COMPLETE.** Phase 3 (Social Content Engine) is fully shipped. Workflow 3a (briefs) and Workflow 3b (auto-post) operational with content_dept_crew and automation_dept_crew.
- ✅ **Phase 4 — COMPLETE.** Phase 4 (Frontend Dashboard) is fully shipped. Next.js App Router dashboard at `frontend/` with WorkflowCard, AgentStatus (5s polling), OutputViewer (react-markdown with manual dark-theme component overrides). Communication via `frontend/lib/api.ts` typed fetch client → FastAPI on port 8000.

**Currently building:** 🚀 **Phase 5 — Voice Layer.** Faster-Whisper STT, Kokoro TTS, Porcupine wake word "Hey Jarvis". Native `portaudio` required on Apple Silicon (via Homebrew) before Python audio libs can be installed.

**Next phase:** Phase 5 — Voice Layer
**Note on the Frontend WorkflowCard rule:** The "How to Add a New Workflow" rule that says "Add a `WorkflowCard` in the frontend dashboard" only applies **starting from Workflow 2** (Phase 1 onward). The Next.js dashboard itself is built in Phase 4, so Phase 0a and Phase 0b do not add `WorkflowCard`s and do not need `ComingSoon` placeholders. The dashboard-facing surface for Phase 0a (`?mock=true` on `/crews/hello`) is the only such contract until Phase 1 lands.

Refer to `docs/roadmap.md` for the full phase breakdown and completion checklist.

---

## Tech Stack — Quick Reference

| Layer | Tool | Notes |
|-------|------|-------|
| Agent framework | CrewAI | YAML config in `backend/config/` |
| Primary LLM | DeepSeek | `deepseek/deepseek-chat` via OpenRouter |
| Coding / multimodal | MiniMax M3 | `minimax/minimax-m3` via OpenRouter |
| Fallback LLM | MiniMax M2.7 | `minimax/minimax-m2.7` via OpenRouter |
| Vision LLM | Claude | `claude-sonnet-4-5` via Anthropic SDK |
| Short-term memory | ChromaDB | Built into CrewAI, auto-managed |
| Long-term memory | Obsidian vault | `/obsidian-vault/`, written by `obsidian_sync.py` |
| Web scraping | Firecrawl | Cloud API key in Phase 1, self-hosted Phase 7 |
| Web search | SerperDev | 2,500 free queries/month |
| App Store data | app-store-scraper + google-play-scraper | npm packages |
| Reddit | PRAW | Official API |
| Mac automation | Open Interpreter | Natural language → terminal |
| Browser automation | Skyvern | Social posting, App Store Connect |
| STT | Faster-Whisper | Local, Phase 5 |
| TTS | Kokoro TTS | Local, Phase 5 |
| Wake word | Porcupine | "Hey Jarvis", Phase 5 |
| Notifications | ntfy.sh | Push to phone |
| Backend API | FastAPI | `backend/main.py` |
| Frontend | Next.js App Router | `frontend/` |

Full reasoning for every decision is in `docs/architecture.md`.

---

## Folder Structure

```
jarvis/
├── backend/
│   ├── crews/          # One file per workflow crew
│   ├── orchestrator/   # jarvis_ceo.py + human_gate.py (Python CEO layer)
│   ├── state/          # JSON-file run state (gitignored except .gitkeep)
│   ├── config/         # agents.yaml and tasks.yaml ONLY
│   ├── tools/          # Reusable tool wrappers
│   ├── voice/          # Voice layer (Phase 5)
│   ├── memory/         # ChromaDB (auto) + obsidian_sync.py
│   ├── scheduler/      # APScheduler jobs (Phase 7)
│   ├── logs/           # jarvis.log lives here
│   ├── output/         # All workflow output files saved here
│   ├── upload/         # Drop files here for Skyvern to pick up
│   ├── utils/          # logger.py, env_validator.py, cost_guard.py
│   └── main.py         # FastAPI entry point
├── frontend/           # Next.js App Router
├── obsidian-vault/     # Long-term memory (Markdown notes)
├── docs/               # All project documentation
├── scripts/            # setup.sh and utility scripts
├── tests/              # One test file per crew/tool
├── CLAUDE.md           # This file
├── AI-RULES.md         # Universal AI rules
├── README.md
├── .env.example
└── .gitignore
```

---

## Coding Rules

### General
- Python 3.11 only
- All secrets come from `.env` via `python-dotenv` — never hardcode keys
- Run `backend/utils/env_validator.py` first if adding new env variables
- Every function must have a docstring explaining what it does, its inputs, and what it returns
- No function longer than 50 lines — split into smaller functions if needed

### CrewAI Specific
- Agent definitions go in `backend/config/agents.yaml` — not in Python files
- Task definitions go in `backend/config/tasks.yaml` — not in Python files
- Crew assembly (combining agents + tasks) goes in `backend/crews/*.py`
- Tools are defined in `backend/tools/*.py` and referenced by name in `agents.yaml`
- Never hardcode the LLM model string in Python — it must come from `agents.yaml`

### Agent Hierarchy — Never Break These Rules
Jarvis uses a strict three-level hierarchy. Every agent must fit into it.

```
Level 1 — Jarvis CEO         (one, always present, routes everything)
Level 2 — Department Heads   (Research / Product / Content / Design / Intelligence / Automation)
Level 3 — Specialist Agents  (do the actual work, use tools, report to their head)
```

- Always use `process=Process.hierarchical` in every crew — never `Process.sequential` for multi-agent crews
- CEO never does work itself — its only job is to delegate and synthesise
- New agents always belong to a department — never create a free-floating agent outside the tree
- Specialists do not communicate across departments — cross-department output flows via CEO
- Engineering is outside Jarvis — no coding agents inside CrewAI; Claude Code handles all code tasks
- Adding a new specialist touches exactly 2 config files — `agents.yaml` and `tasks.yaml` — nothing else
- **Exception (ADR-0002, grilling session 3, 2026-06-01):** A task with `output_pydantic` (i.e., a strict-JSON contract) touches a 3rd file — `backend/contracts/<workflow>.py` — for the Pydantic model class. The agent + task YAML files are still the only files that define *behaviour*; the contract file defines *shape*.

The six departments:
| Department | What it owns |
|------------|--------------|
| Research | Market research, competitor analysis, trend validation |
| Product | PRD writing, opportunity scoring, ASO |
| Content | Social briefs, copywriting, trend scanning |
| Design | UI validation, design feedback (uses Claude Vision) |
| Intelligence | App Store reports, Reddit monitor, morning briefing |
| Automation | Mac terminal, Skyvern posting, upload watcher |

### Logging
- Use `backend/utils/logger.py` for all logging — never use `print()` in production code
- Log every agent action at INFO level
- Log every error with full traceback at ERROR level
- Log token usage and estimated cost at the end of every crew run

### Error Handling
- Every tool call must be wrapped in try/except
- Error messages must be human-readable: say what failed and what the user should check
- On tool failure, log the error and return a graceful fallback — do not crash the crew
- Example of a good error message:
  ```python
  except Exception as e:
      logger.error(f"Firecrawl failed for URL {url}: {e}")
      return "Firecrawl unavailable. Check FIRECRAWL_API_KEY in .env or try again."
  ```

### Output Files
- All workflow outputs saved to `backend/output/`
- Filename format: `WorkflowName_topic_YYYY-MM-DD.md`
- Example: `PRD_habittracker_2026-06-01.md`
- Always append, never overwrite existing output files

### Frontend
- Next.js App Router — use `app/` directory structure
- No pages router
- Fetch backend via `lib/api.ts` — never call FastAPI directly from components
- Unbuilt workflow buttons must use the `ComingSoon` component — never delete or hide them
- TypeScript strict mode on

---

## How to Add a New Workflow

1. Add agents to `backend/config/agents.yaml`
2. Add tasks to `backend/config/tasks.yaml`
3. Create `backend/crews/new_crew.py`
4. Add a FastAPI route in `backend/main.py`
5. Add a `WorkflowCard` in the frontend dashboard
6. Add a test in `tests/`
7. Update `docs/roadmap.md` — mark the workflow as complete
8. Commit: `feat: workflow-N complete`

---

## How to Add a New Tool

1. Create `backend/tools/tool_name.py`
2. Wrap the tool as a CrewAI `BaseTool` subclass
3. Add the tool name to the relevant agent's `tools:` list in `agents.yaml`
4. Test the tool independently before adding it to a crew
5. Document what the tool does and what API key it needs

---

## How to Swap an LLM

Edit one line in `backend/config/agents.yaml`:

```yaml
agent_name:
  llm: deepseek/deepseek-chat   # change this to any OpenRouter model string
```

No Python changes needed.

---

## Git Commit Convention

```
type: short description

Types:
init     — project setup
feat     — new feature or workflow
fix      — bug fix
config   — yaml or env changes
docs     — documentation only
refactor — code cleanup, no behaviour change
```

Examples:
```
init: project structure and environment
feat: workflow-2 research and PRD crew working
fix: firecrawl timeout on large pages
config: switch market_researcher to minimax-m3
docs: update roadmap phase 1 complete
```

---

## What Is Out of Scope — Do Not Build These

- Docker / containerisation → Phase 7 only
- Scheduled / automated triggers → Phase 7 only
- Telegram interface → future, not planned
- Multi-user support → never
- Mobile app for Jarvis → future, not planned
- Auth system → never needed

If asked to build any of the above before Phase 7, refuse and explain that it is deferred intentionally.

---

## When You Are Unsure

If instructions in this file conflict with what the user asks in the session:

1. Flag the conflict clearly
2. Ask which takes priority before writing any code
3. Do not silently pick one over the other

If a library is not in the stack listed above:

1. Ask before installing it
2. Explain what it does and why it is needed
3. If it duplicates an existing tool, flag the overlap

---

## Debugging Protocol

When the user pastes an error:

1. Read the full traceback — identify the exact line and file
2. Explain what the error means in plain English (one sentence)
3. Give the fixed code — not a suggestion, actual working code
4. Explain what was wrong and what the fix does (two sentences max)
5. If the fix requires an `.env` change or install, state it explicitly

---

## Session Start Checklist

At the start of every Claude Code session, confirm:

- [ ] Read `docs/roadmap.md` — know the current phase
- [ ] Know what was last committed — ask the user if unsure
- [ ] Check `.env.example` — know which keys are required for current phase
- [ ] Ask the user: "What are we building today?" if not already stated

---

*End of CLAUDE.md*
