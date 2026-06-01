# Jarvis

> Personal AI operating system for a solo mobile app developer.  
> Automates market research, competitor analysis, content creation, UI validation, and social posting.  
> Private. Single-user. Runs on macOS.

---

## What Jarvis Does

| Workflow | What it automates | Time saved |
|----------|------------------|------------|
| Research → PRD | One sentence → full market validation + PRD | 3–5 hrs → 15 min |
| App Store Intelligence | Category → ranked competitor report | 2 hrs → 10 min |
| Social Content Engine | Trigger → viral briefs for 4 platforms | 2 hrs → 20 min |
| UI Design Loop | Upload screen → structured feedback + iteration | Manual → automated |
| Competitor Teardown | App name → full intelligence dossier | 1–2 hrs → 12 min |
| Morning Briefing | Daily → what changed in your market overnight | 30 min → 5 min |
| Mac Automation | Natural language → Mac terminal commands | On demand |
| ASO Optimiser | App name → optimised App Store listing copy | 1 hr → 15 min |
| Reddit Monitor | Scheduled → flagged posts to reply to or act on | Daily checking → automatic |

---

## Architecture

Three-level hierarchy:

```
Jarvis CEO (Python orchestrator)
├── Research Department   — market research, competitor analysis, trend validation
├── Product Department    — PRD writing, opportunity scoring, ASO
├── Content Department    — social briefs, copywriting, trend scanning
├── Design Department     — UI validation, design feedback (Claude Vision)
├── Intelligence Dept     — App Store reports, Reddit monitor, morning briefing
└── Automation Department — Mac terminal, Skyvern posting, upload watcher
```

**Stack:** CrewAI + DeepSeek + MiniMax M3 + Claude Vision + FastAPI + Next.js  
**Memory:** ChromaDB (short-term) + Obsidian vault (long-term)  
**Cost:** ~₹700–1,400/month at normal usage

Full architecture decisions: `docs/architecture.md`

---

## Project Status

| Phase | Focus | Status |
|-------|-------|--------|
| 0a | Hello-world crew | ⬜ Not started |
| 0b | Workflow 2 tool installs | ⬜ Not started |
| 1 | Workflow 2 — Research → PRD | ⬜ Not started |
| 2 | Workflow 4 — App Store Intel | ⬜ Not started |
| 3a | Workflow 3 — Content briefs | ⬜ Not started |
| 3b | Workflow 3 — Skyvern auto-post | ⬜ Not started |
| 4 | Frontend Dashboard (Next.js) | ⬜ Not started |
| 5 | Voice Layer | ⬜ Not started |
| 6 | Remaining Workflows (1,5,6,7,8,9,10) | ⬜ Not started |
| 7 | Scheduling + Docker | ⬜ Not started |

> Update this table as phases complete.

---

## Documentation

| File | Purpose |
|------|---------|
| `docs/prd.md` | What Jarvis is, what it must do, success criteria |
| `docs/roadmap.md` | Phase-by-phase build plan with checklists |
| `docs/architecture.md` | Every tool decision and why — read before touching code |
| `docs/api-keys.md` | Which keys, where to get them, cost estimates |
| `docs/workflows/` | Detailed spec per workflow — agents, tasks, expected output |
| `docs/adr/` | Architecture Decision Records — why key decisions were made |
| `CLAUDE.md` | Instructions for Claude Code — read automatically on every session |
| `AI-RULES.md` | Universal AI rules — paste at the top of any AI session |

---

## Quick Start (Phase 0a)

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/jarvis.git
cd jarvis

# 2. Install base dependencies
pip install crewai crewai-tools anthropic openai python-dotenv fastapi uvicorn

# 3. Copy env template and fill in your keys
cp .env.example .env
# Edit .env — add OPENROUTER_API_KEY and ANTHROPIC_API_KEY at minimum

# 4. Validate environment
python backend/utils/env_validator.py

# 5. Start the server
python backend/main.py

# 6. Test the health endpoint
curl http://localhost:8000/health
```

Full setup instructions: `docs/roadmap.md` → Phase 0a

---

## Working With AI on This Project

**Claude Code sessions:** `CLAUDE.md` is read automatically. No extra context needed.

**Any other AI session:** Paste the contents of `AI-RULES.md` at the top of your first message. Then paste relevant sections from `docs/prd.md` and `docs/roadmap.md`.

**When something breaks:** Paste the full error traceback. Do not summarise it.

---

## Cost

Target: under ₹2,000/month.  
Estimated at normal usage: ₹700–1,400/month.  
Primary LLM: DeepSeek via OpenRouter — 10x cheaper than GPT-4 for the same research tasks.  
Full cost breakdown: `docs/api-keys.md`

---

*This is a private project. Not for distribution.*
