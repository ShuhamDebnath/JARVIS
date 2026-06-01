# Jarvis — Architecture & Stack Decisions

> Version: 1.0  
> Status: Finalised  
> Last Updated: June 2026  
> Purpose: Every tool decision is recorded here with the reason. Any AI working in this repo must read this first.

---

## Guiding Principles

1. **Cheapest tool that does the job** — no over-engineering
2. **YAML over Python where possible** — owner is beginner-intermediate, config is easier to read and change
3. **One tool per category** — no duplication, no overlap
4. **Local first** — prefer tools that run locally over cloud APIs to reduce cost and latency
5. **Manual before automated** — get it working by hand, then schedule it
6. **Modular** — every crew, tool, and agent is independently replaceable

---

## Layer 1 — Orchestration (Brain)

### CrewAI
**Decision: Primary agent framework**

CrewAI manages all agent workflows. It handles agent creation, task assignment, delegation, memory, and parallel execution.

Why CrewAI won over alternatives:

| Framework | Verdict | Reason |
|-----------|---------|--------|
| CrewAI | ✅ Chosen | YAML config, hierarchical agents, built-in ChromaDB memory, large community, beginner-friendly |
| AutoGen | ⚠️ Alternative | Good framework, has visual Studio GUI — consider if YAML approach ever feels limiting |
| Hermes Agent | 🔮 Future | Self-improving agent with learning loop — compelling but smaller community, steeper curve |
| Agent Zero | ❌ Skip | Self-modifying agents, unstable, not for beginners |
| OpenHands | ❌ Skip | Built for software engineering teams in Docker sandboxes — overkill |
| Goose | ❌ Too limited | Good UX but single-agent only — cannot orchestrate multi-agent workflows |
| Open Interpreter | ✅ Hands layer only | Not an orchestrator — used specifically for Mac terminal automation |

**Key CrewAI concepts used:**
- `agents.yaml` — defines every agent (role, goal, backstory, LLM, tools)
- `tasks.yaml` — defines every task (description, expected output, assigned agent)
- `Crew(process=Process.hierarchical)` — manager agent delegates to specialist agents
- `memory=True` — ChromaDB auto-handles short-term memory per crew

---

## Agent Hierarchy — The Jarvis Command Structure

Jarvis uses a three-level hierarchy. You always talk to Jarvis (CEO). Jarvis routes internally. You never address individual agents directly.

```
JARVIS (CEO Agent)
│   Role: Receives all user input, decides which departments to activate,
│         synthesises all department outputs into a final response.
│   LLM:  DeepSeek
│   Rule: Never does research or writing itself — only delegates and synthesises.
│
├── Research Director
│   │   Role: Orchestrates all market research tasks
│   │   LLM:  DeepSeek
│   ├── Pain Point Hunter        — Reddit, ProductHunt, 1-star App Store reviews
│   ├── Competitor Mapper        — existing apps, ratings, download estimates
│   ├── Revenue Estimator        — pricing models, MRR estimates, App Store charts
│   ├── Gap Finder               — missing features across all competitor reviews
│   ├── Trend Validator          — Google Trends, Reddit growth, Twitter momentum
│   └── Audience Sizer           — TAM from keyword volumes, subreddit sizes
│
├── Product Director
│   │   Role: Turns research into actionable product documents
│   │   LLM:  DeepSeek
│   ├── Opportunity Scorer       — scores ideas out of 50, go/no-go recommendation
│   ├── PRD Writer               — full product requirements document from research
│   └── App Store Optimiser      — ASO copy, keywords, screenshots strategy
│
├── Content Director
│   │   Role: Generates platform-specific content briefs and manages posting
│   │   LLM:  MiniMax M3
│   ├── Trend Scanner            — Reddit, Google Trends, Twitter, Instagram hashtags
│   ├── Viral Idea Generator     — platform-specific content briefs
│   ├── Copywriter               — captions, thread copy, post text
│   └── Community Angle Agent    — cross-post targets, best posting times IST
│
├── Design Director
│   │   Role: Validates and iterates UI designs
│   │   LLM:  Claude (Anthropic) — vision tasks
│   ├── UI Validator             — analyses screens for usability and consistency
│   ├── Design Feedback Agent    — structured feedback with specific suggestions
│   └── Iteration Suggester      — proposes concrete design improvements
│
├── Intelligence Director
│   │   Role: Monitors markets and surfaces daily insights
│   │   LLM:  DeepSeek
│   ├── App Store Analyst        — trending apps, bad reviews, missing features
│   ├── Reddit Monitor           — keyword alerts, community sentiment
│   └── Morning Briefing Agent   — daily summary of what matters today
│
└── Automation Director
        Role: Executes actions on Mac and web on behalf of the user
        LLM:  DeepSeek
    ├── Mac Automation Agent     — natural language → terminal (Open Interpreter)
    ├── Social Poster            — uploads content to platforms (Skyvern)
    └── Upload Watcher           — detects new files in /upload/, triggers posting
```

### How the CEO Routes a Request

```
You:  "Research a habit tracker app for Indian students"
       ↓
Jarvis CEO receives input → decides: Research Director + Product Director needed
       ↓
Research Director activates 6 specialists in parallel (~5 min)
       ↓
Product Director receives findings → Opportunity Scorer → PRD Writer
       ↓
CEO synthesises both department outputs into one response
       ↓
You receive: opportunity score + full PRD
```

### Hierarchy Rules — Never Break These

1. **You always talk to Jarvis (CEO)** — never to individual agents directly
2. **CEO never does work itself** — it only delegates and synthesises
3. **Department heads never skip specialists** — they delegate down, not across
4. **Specialists never talk to other departments** — cross-department communication goes via the CEO
5. **New agents always slot into an existing department** — never create a free-floating agent
6. **Engineering is outside Jarvis** — code writing/review is handled by Claude Code, not by agents

### Adding New Agents

The hierarchy is designed to grow. To add a new specialist:

1. Decide which department it belongs to
2. Add the agent to `agents.yaml` under the correct department head
3. Add its tasks to `tasks.yaml`
4. Reference it in the relevant crew file
5. The CEO and department head automatically gain access — no other files change

This is the modularity guarantee: adding a new agent touches exactly 2 files (`agents.yaml` + `tasks.yaml`) and one crew file. Nothing else breaks.

---

## Layer 2 — LLM Allocation

Every agent in the system is assigned the most cost-effective LLM for its task type.

| Task Type | LLM | Why |
|-----------|-----|-----|
| Research, reasoning, writing | DeepSeek (`deepseek/deepseek-chat`) | 10x cheaper than GPT-4, strong reasoning, fast |
| Coding tasks, multimodal input | MiniMax M3 (`minimax/minimax-m3` via OpenRouter) | Multimodal (text + image + code), cost-effective |
| Long context fallback | MiniMax M2.7 (`minimax/minimax-m2.7` via OpenRouter) | Extended context window |
| Vision / UI analysis | Claude (`claude-sonnet-4-5` via Anthropic) | Best available vision LLM for design validation tasks |
| Manager / orchestration | DeepSeek | Strong at delegation and synthesis, no vision needed |

**LLM switching rule:** To change any agent's LLM, edit one line in `agents.yaml`:
```yaml
market_researcher:
  llm: deepseek/deepseek-chat   # change this line only
```

**Cost target:** Under ₹2,000/month total. DeepSeek as primary keeps this achievable even with 6 parallel agents.

---

## Layer 3 — Memory (Two-Layer System)

Jarvis uses two memory layers for different purposes. They work independently and complement each other.

### ChromaDB — Short-term / Semantic Memory
- **Built into CrewAI** — zero extra setup
- Stores: task context, research within a session, intermediate agent outputs
- Query method: semantic similarity (vector search)
- Scope: per crew run, configurable retention
- Use case: "What did the competitor mapper find 10 minutes ago?"

### Obsidian Vault — Long-term / Structured Memory
- **Location:** `/obsidian-vault/` in project root
- Stores: completed PRDs, market research summaries, competitor profiles, past decisions, app ideas, user preferences
- Format: Markdown files with bidirectional `[[links]]` between related notes
- Written by: `backend/memory/obsidian_sync.py` after every significant workflow completion
- Read by: agents via file read tools, and by the user directly in Obsidian app
- Query method: filename search + full text search in Obsidian

**Why not just one memory system:**

| Need | ChromaDB | Obsidian |
|------|----------|---------|
| Within-session agent context | ✅ | ❌ too slow |
| Cross-session knowledge | ❌ resets | ✅ permanent |
| Human-readable and editable | ❌ | ✅ |
| Semantic search | ✅ | ❌ |
| Relationship mapping (links) | ❌ | ✅ |
| Zero setup | ✅ | needs sync script |

**Why not VectorDB RAG for everything:**
VectorDB retrieves by similarity — it is a search engine, not a memory system. It cannot understand relationships between ideas, track how preferences evolved, or build a picture of who you are. Obsidian's link graph does this. Both layers together approximate how human memory actually works.

---

## Layer 4 — Research & Scraping (Eyes)

One tool per data source. No redundancy.

| Source | Tool | Why |
|--------|------|-----|
| General web | Firecrawl (self-hosted via Docker later) | Handles JS-rendered sites, outputs clean LLM-ready markdown, free when self-hosted |
| Web search | SerperDev | 2,500 free queries/month, fast, structured results |
| Play Store | google-play-scraper (npm) | Purpose-built, no API key, no rate bans |
| App Store | app-store-scraper (npm) | Same — purpose-built, free |
| Reddit | PRAW | Official Reddit API, free tier, reliable, no bans |
| Google Trends | pytrends | Free, no API key required |
| Instagram | Instagrapi | Unofficial — use with a dedicated burner account only |

**Firecrawl note:** Use the cloud API key in Phase 1 for simplicity. Self-host via Docker in Phase 7 for zero cost at scale.

---

## Layer 5 — Automation (Hands)

| Task | Tool | Why |
|------|------|-----|
| Mac terminal automation | Open Interpreter | Natural language → shell commands. Last updated 2024 but still functional for this use case. No clean replacement exists yet. |
| Browser automation / social posting | Skyvern | Visual AI browser agent — no brittle CSS selectors, handles dynamic pages, manages App Store Connect and social platforms |
| Fallback mouse/keyboard | PyAutoGUI | Emergency fallback only — use when Skyvern cannot handle a specific interaction |

**Open Interpreter status:** Not actively developed as of 2025. Functional for current needs. If it breaks or becomes incompatible, replace with a Claude computer-use integration or Skyvern extension.

---

## Layer 6 — Voice

All voice components run locally. Zero API cost.

| Component | Tool | Why |
|-----------|------|-----|
| Speech-to-text | Faster-Whisper | Local, free, 4x faster than base Whisper, handles Indian English accent reliably |
| Text-to-speech | Kokoro TTS | Best free local TTS available in 2025, natural voice quality |
| Wake word | Porcupine (Picovoice) | "Hey Jarvis" detection, free tier, low CPU usage, reliable |
| Phone notifications | ntfy.sh | Free, open source, no account required, push to any device |

**Voice layer placement:** Built in Phase 5, after the first 3 workflows are stable. Voice is a UX layer on top of already-working crews — it just transcribes and calls `crew.kickoff(inputs={...})`.

---

## Layer 7 — Frontend & API

| Component | Tool | Why |
|-----------|------|-----|
| Dashboard | Next.js (App Router) | Chosen for long-term customisability. Simple in Phase 4, upgradeable in Phase 6+. |
| Backend API | FastAPI | Lightweight, async, easy to add new routes per workflow |
| Fallback chat UI | Open WebUI (Docker) | Zero-code chat interface to test crews before dashboard is built |

**Frontend philosophy:** Build simple now. Each workflow gets a card with a trigger button. Unbuilt workflows show a "Coming Soon" badge. The UI is intentionally minimal in Phase 4 — design upgrades come in Phase 6.

---

## Folder Structure

```
jarvis/
├── backend/
│   ├── crews/
│   │   ├── research_crew.py       # Workflow 2 — Research + PRD
│   │   ├── content_crew.py        # Workflow 6 — Content pipeline
│   │   ├── design_crew.py         # Workflow 1 — UI validation
│   │   └── social_crew.py         # Workflow 3 + 4 — Social + App Store
│   ├── config/
│   │   ├── agents.yaml            # All agent definitions
│   │   └── tasks.yaml             # All task definitions
│   ├── tools/
│   │   ├── store_scraper.py       # App Store + Play Store
│   │   ├── firecrawl_tool.py      # Web scraper
│   │   └── reddit_tool.py         # Reddit monitor
│   ├── voice/
│   │   └── listener.py            # Wake word + STT + TTS
│   ├── memory/
│   │   ├── chromadb/              # Auto-managed by CrewAI
│   │   └── obsidian_sync.py       # Writes to Obsidian vault
│   ├── scheduler/
│   │   └── jobs.py                # APScheduler (Phase 7 only)
│   ├── logs/
│   │   └── jarvis.log
│   ├── output/                    # All workflow outputs saved here
│   ├── upload/                    # Drop files here → Skyvern picks up
│   ├── utils/
│   │   ├── logger.py              # Structured logging setup
│   │   ├── env_validator.py       # Checks all .env keys on startup
│   │   └── cost_guard.py          # Token budget tracking per run
│   └── main.py                    # FastAPI app entry point
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── layout.tsx
│   │   └── dashboard/
│   ├── components/
│   │   ├── WorkflowCard.tsx
│   │   ├── AgentStatus.tsx
│   │   ├── OutputViewer.tsx
│   │   └── ComingSoon.tsx
│   ├── lib/
│   │   └── api.ts
│   └── public/
├── obsidian-vault/
│   └── .obsidian/
├── docs/
│   ├── prd.md
│   ├── roadmap.md
│   ├── architecture.md            # This file
│   ├── api-keys.md
│   └── workflows/
│       ├── workflow-1-design.md
│       ├── workflow-2-research-prd.md
│       └── workflow-3-social.md
├── scripts/
│   └── setup.sh
├── tests/
├── CLAUDE.md
├── AI-RULES.md
├── README.md
├── .env.example
├── .gitignore
└── docker-compose.yml             # Phase 7 only
```

---

## Data Flow — How a Request Moves Through the System

```
1. User Input
   └── Via: frontend button / voice command / terminal

2. FastAPI (main.py)
   └── Receives request → validates input → calls correct crew

3. CrewAI Manager Agent (DeepSeek)
   └── Reads task → decomposes → delegates to specialist agents

4. Specialist Agents run in parallel
   └── Each agent: reads tools → queries external APIs → returns findings
   └── Tools used: Firecrawl, PRAW, SerperDev, store_scraper, pytrends

5. ChromaDB
   └── Stores intermediate results → agents query each other's findings

6. Synthesis Agent
   └── Consolidates all findings → produces final output

7. Human Gate (where applicable)
   └── FastAPI pauses crew → sends result to frontend → waits for approval

8. Output saved
   └── Markdown file → /backend/output/
   └── Key findings → Obsidian vault via obsidian_sync.py
   └── Run summary → jarvis.log

9. Frontend
   └── Polls FastAPI → displays output in OutputViewer component
```

---

## Environment Variables

Full list in `.env.example`. Summary:

| Variable | Used by | Required |
|----------|---------|----------|
| `DEEPSEEK_API_KEY` | All research/writing agents | ✅ Yes |
| `OPENROUTER_API_KEY` | MiniMax M3/M2.7 agents | ✅ Yes |
| `ANTHROPIC_API_KEY` | Claude vision tasks (Workflow 1) | ✅ Yes |
| `SERPER_API_KEY` | SerperDev web search tool | ✅ Yes |
| `FIRECRAWL_API_KEY` | Firecrawl cloud (Phase 1–6) | ✅ Yes |
| `PORCUPINE_ACCESS_KEY` | Wake word detection (Phase 5) | ⏳ Phase 5 |

---

## What Is Deliberately Not in This Stack

| Thing | Why excluded |
|-------|-------------|
| LangChain | Too much abstraction, slower updates, CrewAI is cleaner for this use case |
| OpenAI GPT-4 | 10x more expensive than DeepSeek for same quality on research tasks |
| Pinecone / Weaviate | Paid VectorDBs — ChromaDB is free and built into CrewAI |
| n8n / Zapier | Low-code automation platforms — adds another layer, CrewAI handles orchestration |
| Docker (Phase 1–6) | Hides errors from beginners — added in Phase 7 after everything works |
| Scheduling (Phase 1–6) | Manual triggers first — scheduling added in Phase 7 |
| Telegram bot | Future phase — ntfy.sh covers notifications for now |
| Multi-user auth | Never — this is a single-user personal system |

---

## Decision Log

Significant decisions made and why — for future reference.

| Date | Decision | Reason |
|------|----------|--------|
| Jun 2026 | CrewAI over AutoGen | YAML config more accessible for owner's skill level |
| Jun 2026 | DeepSeek as primary LLM | Cost — 10x cheaper, comparable performance for research tasks |
| Jun 2026 | MiniMax M3 for coding/multimodal | Better than DeepSeek for code generation and image+text tasks |
| Jun 2026 | Two-layer memory (ChromaDB + Obsidian) | VectorDB alone lacks relationship mapping and long-term cross-session knowledge |
| Jun 2026 | No Docker until Phase 7 | Hides errors during learning phase — costs debugging time |
| Jun 2026 | Manual triggers before scheduling | Validate workflows work before automating them |
| Jun 2026 | Next.js frontend over Open WebUI | Long-term customisability — Open WebUI is fallback only |
| Jun 2026 | Hermes Agent deferred | Compelling self-improvement loop but community too small at this stage |
| Jun 2026 | Three-level CEO hierarchy from day one | Flat crews require full rewrite to add hierarchy later — cheaper to design correctly once |
| Jun 2026 | Engineering department excluded from Jarvis | Claude Code is purpose-built for coding — CrewAI agents are poor at long code generation, no overlap needed |

---

*End of Architecture v1.0*
