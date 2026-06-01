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
- `memory` is **omitted** from every `Crew(...)` call in `dept_crews.py` — CrewAI's default is `memory=False`, so no `memory` argument means no ChromaDB inside the crew. All agents in all depts also have `memory: false` in `agents.yaml` (the two settings are belt-and-braces; either alone suffices in current CrewAI). Inter-agent state is threaded explicitly via task `context:`.

---

## Agent Hierarchy — The Jarvis Command Structure

Jarvis uses a three-level hierarchy. You always talk to Jarvis (CEO). Jarvis routes internally. You never address individual agents directly.

**Important — the CEO is a Python orchestrator, not a CrewAI agent.** CrewAI's `Process.hierarchical` is a two-level construct: a single `manager_agent` plus a pool of workers. There is no native 3-level delegation tree. To enforce the three-level rule from the docs, the CEO is implemented as a **Python function** in `backend/crews/jarvis_ceo.py` that calls **per-department sub-crews** (one CrewAI `Crew` per department, each with `Process.hierarchical`) and threads their outputs into the next department's input. The 3-level diagram is therefore real, but only the bottom two levels are CrewAI crews — the top level is plain Python.

```
JARVIS CEO  (Python orchestrator — backend/crews/jarvis_ceo.py)
│   Role: Receives all user input, decides which departments to activate,
│         calls each department's crew in sequence or parallel,
│         threads outputs into the next department's input.
│   Rule: Never does research or writing itself — only orchestrates Python
│         calls to per-department crews. No LLM call at the CEO level.
│
├── research_dept_crew  (CrewAI Crew, process=Process.hierarchical)
│   │   manager_agent: research_director  (LLM: DeepSeek)
│   ├── Pain Point Hunter        — Reddit, ProductHunt, 1-star App Store reviews
│   ├── Competitor Mapper        — existing apps, ratings, download estimates
│   ├── Revenue Estimator        — pricing models, MRR estimates, App Store charts
│   ├── Gap Finder               — missing features across all competitor reviews
│   ├── Trend Validator          — Google Trends, Reddit growth, Twitter momentum
│   ├── Audience Sizer           — TAM from keyword volumes, subreddit sizes
│   └── (consolidation task is a worker too, owned by research_director)
│
├── product_dept_crew   (CrewAI Crew, process=Process.hierarchical)
│   │   manager_agent: product_director  (LLM: DeepSeek)
│   ├── Opportunity Scorer       — scores ideas out of 50, go/no-go recommendation
│   ├── PRD Writer               — full product requirements document from research
│   └── App Store Optimiser      — ASO copy, keywords, screenshots strategy
│
├── content_dept_crew   (CrewAI Crew, process=Process.hierarchical)
│   │   manager_agent: content_director  (LLM: MiniMax M3)
│   ├── Trend Scanner            — Reddit, Google Trends, Twitter, Instagram hashtags
│   ├── Viral Idea Generator     — platform-specific content briefs
│   ├── Copywriter               — captions, thread copy, post text
│   └── Community Angle Agent    — cross-post targets, best posting times IST
│
├── design_dept_crew    (CrewAI Crew, process=Process.hierarchical)
│   │   manager_agent: design_director  (LLM: Claude — vision tasks)
│   ├── UI Validator             — analyses screens for usability and consistency
│   ├── Design Feedback Agent    — structured feedback with specific suggestions
│   └── Iteration Suggester      — proposes concrete design improvements
│
├── intelligence_dept_crew  (CrewAI Crew, process=Process.hierarchical)
│   │   manager_agent: intelligence_director  (LLM: DeepSeek)
│   ├── App Store Analyst        — trending apps, bad reviews, missing features
│   ├── Reddit Monitor           — keyword alerts, community sentiment
│   └── Morning Briefing Agent   — daily summary of what matters today
│
└── automation_dept_crew (CrewAI Crew, process=Process.hierarchical)
    │   manager_agent: automation_director  (LLM: DeepSeek)
    ├── Mac Automation Agent     — natural language → terminal (Open Interpreter)
    ├── Social Poster            — uploads content to platforms (Skyvern)
    └── Upload Watcher           — detects new files in /upload/, triggers posting
```

### How the CEO Orchestrator Routes a Request

The CEO is **plain Python** in `backend/crews/jarvis_ceo.py`. Example for Workflow 2:

```python
# backend/crews/jarvis_ceo.py
from crews.dept_crews import build_research_dept_crew, build_product_dept_crew

def run_workflow_2(idea: str) -> dict:
    # 1. Research dept runs — 6 specialists + consolidation
    research_crew = build_research_dept_crew()
    research_brief = research_crew.kickoff(inputs={"idea": idea})

    # 2. Human gate — opportunity score is presented, user says yes/no
    score_report = research_brief["opportunity_score"]
    if not ask_user_go_no_go(score_report):           # <-- blocks on HTTP / frontend
        return {"status": "declined", "brief": research_brief}

    # 3. Product dept runs — PRD writer uses the research brief as input
    product_crew = build_product_dept_crew()
    prd = product_crew.kickoff(inputs={
        "idea": idea,
        "research_brief": research_brief,
    })

    return {"status": "completed", "prd": prd}
```

The CEO orchestrator handles:
- Which departments to activate per workflow
- The order of execution (parallel where possible, sequential where output depends on prior output)
- The human-gate pause/resume handshake with the FastAPI layer
- Saving outputs to disk and Obsidian
- Logging token usage and cost per run

It does **not** call an LLM itself. It does **not** synthesise or rewrite any text. Synthesis happens inside each dept crew's `manager_agent` (the department head).

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
2. **CEO is a Python orchestrator, not an LLM** — it calls `dept_crew.kickoff()` and threads outputs, never does research or writing itself
3. **Each department head is a `manager_agent` inside its own `dept_crew`** — the dept head is a CrewAI manager, not a free-floating agent
4. **Department heads never skip specialists** — they delegate down through their dept crew's `Process.hierarchical`, not across
5. **Specialists never talk to other departments** — cross-department communication is routed by the Python CEO orchestrator passing outputs as inputs
6. **New agents always slot into an existing department's crew** — never create a free-floating agent
7. **Engineering is outside Jarvis** — code writing/review is handled by Claude Code, not by agents

### Per-Department Crew Isolation; in-dept memory disabled by default

**Policy (per ADR-0002, grilling session 3, 2026-06-01):** All agents in all `dept_crews` run with `memory=False`. The `Crew(...)` constructor in `backend/crews/dept_crews.py` is called with **no `memory` argument** — CrewAI's default is `False` in 0.86+ and that default is the future-proof choice (passing `memory=False` explicitly raises a deprecation warning in 0.95+). Cross-crew state is threaded **exclusively** via task `context:`. ChromaDB is not used inside any `dept_crew`. The Python CEO orchestrator passes outputs as inputs to the next department — it does not share memory across departments.

Consequences:

- **No cross-run contamination, by construction.** Two `kickoff()` calls on the same `research_dept_crew` cannot leak semantic fragments between ideas, because there is no shared vector store to leak from. (Pre-ADR-0002, CrewAI's `memory=True` auto-generated a collection name from crew composition — the same name across runs — so run 2 of "to-do app" could semantic-retrieve fragments from run 1 of "habit tracker".)
- **No orphaned collections on disk.** Disabling ChromaDB eliminates the need for cleanup code, collection-name rotation, or per-run reset hooks.
- **Cross-department state is explicit text inputs.** Easier to debug (`cat` the research brief and read it), easier to log, easier to version-control. The cost is that long context (>100k tokens) doesn't fit in a single LLM call without summarisation — but no current Jarvis workflow hits that limit.
- **Director's role is coherent.** `research_director` and `product_director` are `manager_agent` + consolidator only. They don't have a side-job of "remember what the last specialist said" via ChromaDB.

**Reserved upgrade path:** If a future workflow develops a concrete need for semantic recall within a `dept_crew` (e.g., "the gap-finder should semantic-retrieve the last 10 competitor analyses we did for similar apps"), the upgrade is an ephemeral (RAM-only) ChromaDB client per `Crew` instance — constructed inside `build_*_dept_crew()` and torn down when the crew's `kickoff()` returns. This leaves no on-disk state to leak between runs and requires no changes to `agents.yaml`. ADR-0002's policy is the *default*, not a permanent ban.

### Adding New Agents

The hierarchy is designed to grow. The agent-key convention (resolved in grilling session 2, Q8 — see ADR-0001 follow-ups) is:

- **Agents use flat keys with a `dept:` field** in `backend/config/agents.yaml`. NOT departments-as-top-level-YAML-keys. Example:

  ```yaml
  # canonical pattern
  research_director:
    dept: research_dept
    role: Research Department Director
    ...
  product_director:
    dept: product_dept
    role: Product Department Director
    ...
  ```

- **Tasks use department-name prefixes** in `backend/config/tasks.yaml` so the loader can filter without ambiguity. Example: `research_pain_point_task`, `product_prd_writing_task`. The prefix is the disambiguator; do not put a `dept:` field on tasks.

- **The loader** in `backend/crews/dept_crews.py` uses `load_agents_for("research_dept")` to filter the flat agent list by `dept:` field, and `load_tasks_for("research_dept")` to filter the task list by the `research_` prefix.

To add a new specialist:

1. Decide which department it belongs to
2. Add a flat-keyed entry to `backend/config/agents.yaml` with `dept: <dept_name>`
3. Add its tasks to `backend/config/tasks.yaml` using the department's task prefix (`research_*`, `product_*`, `content_*`, etc.)
4. Reference it in `backend/crews/dept_crews.py` under the appropriate `build_<dept>_dept_crew()` factory
5. The Python CEO orchestrator automatically routes work to the right dept — no orchestrator change needed

This is the modularity guarantee: adding a new agent touches exactly 2 files (`agents.yaml` + `tasks.yaml`) and one entry in `dept_crews.py`. Nothing else breaks.

**Exception (ADR-0002, grilling session 3, 2026-06-01):** A task with `output_pydantic` (i.e., a strict-JSON contract) touches a 3rd file — `backend/contracts/<workflow>.py` — for the Pydantic model class. The agent + task YAML files still define *behaviour*; the contract file defines *shape*. This exception is recorded in CLAUDE.md so the rule stays consistent across docs.

### Tool Registration — Built-in vs Project-Local

CrewAI's `crewai-tools` pip package ships a fixed set of tools (`SerperDevTool`, `FirecrawlTool`, etc.). The rest of Jarvis's toolset is project-local — wrapped as `BaseTool` subclasses in `backend/tools/`. `agents.yaml` references both by class-name string in the agent's `tools:` list. The convention is:

- **Built-in tools (`crewai-tools`):** import directly from `crewai_tools`. The loader in `dept_crews.py` does not need to register them — CrewAI resolves the name.
- **Project-local tools:** import + register in `backend/crews/dept_crews.py` before `Crew(...)` is instantiated. The `BaseTool` subclass defines a `name` attribute; `agents.yaml` references the tool by that `name`. Example: `tools: [RedditTool, AppStoreScraperTool, PytrendsTool, ScoringRubricTool, SkyvernTool, VisionTool]`.
- **Tool files needed (per grilling session 2, Q10 — see ADR-0001 follow-ups):**
  - `tools/store_scraper.py` — wraps `google-play-scraper` and `app-store-scraper` npm packages. Shells out to Node via `subprocess.run` (single long-lived Node process is a Phase 7 optimisation).
  - `tools/firecrawl_tool.py` — wraps Firecrawl API.
  - `tools/reddit_tool.py` — wraps PRAW.
  - `tools/pytrends_tool.py` — wraps pytrends.
  - `tools/scoring_rubric_tool.py` — wraps the hardcoded rubric table from ADR-0000 Q1.
  - `tools/vision_tool.py` — wraps Claude Vision (Phase 6 / Workflow 1).
  - `tools/skyvern_tool.py` — Phase 3a: `BaseTool` stub that raises `NotImplementedError` (per ADR-0003); Phase 3b: real Skyvern-backed implementation.

Adding a new tool is one new file under `backend/tools/` + one entry in the relevant agent's `tools:` list in `agents.yaml`. No Python change to crew assembly unless the tool needs custom registration.

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

## Layer 3 — Memory

Jarvis uses one long-term memory layer (Obsidian). ChromaDB is **available in CrewAI** but **disabled by default in all `dept_crews`** per the policy above. There is no "two-layer memory" in active use — the Obsidian vault is the only layer; ChromaDB is a reserved upgrade path.

### ChromaDB — Available, disabled by default
- **Status:** Built into CrewAI, but `memory` argument is **omitted** from every `Crew(...)` call in `backend/crews/dept_crews.py`. CrewAI's default is `memory=False`, so no `memory` argument means no ChromaDB.
- **Why disabled:** ADR-0002 (grilling session 3, 2026-06-01) decided that all inter-agent state flows through explicit task `context:`. No semantic recall is needed inside the crew — and disabling ChromaDB eliminates the cross-run contamination failure mode (Q13 of grilling session 2) by construction.
- **Reserved upgrade path:** If a future workflow needs in-dept semantic recall, the upgrade is an ephemeral (RAM-only) ChromaDB client per `Crew` instance. No on-disk state, no per-run reset hooks. See "Per-Department Crew Isolation" section above for the full policy.

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
│   │   ├── jarvis_ceo.py          # Python orchestrator over all workflows
│   │   ├── dept_crews.py          # build_research_dept_crew() + build_product_dept_crew() etc.
│   │   ├── research_crew.py       # Workflow 2 — Research + PRD
│   │   ├── content_crew.py        # Workflow 6 — Content pipeline
│   │   ├── design_crew.py         # Workflow 1 — UI validation
│   │   └── social_crew.py         # Workflow 3 + 4 — Social + App Store
│   ├── orchestrator/
│   │   └── human_gate.py          # ask_user / receive_user_reply handshake
│   ├── state/                     # JSON-file run state (gitignored)
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
   └── Receives request → validates input → calls the Python CEO orchestrator
       for the matching workflow

3. Python CEO Orchestrator (backend/crews/jarvis_ceo.py)
   └── Decides which dept_crews to activate and in what order
   └── Calls the first dept_crew via crew.kickoff(inputs={...})
   └── No LLM call at the CEO level — pure Python routing

4. dept_crew (CrewAI Crew, process=Process.hierarchical)
   └── manager_agent = department head (LLM: DeepSeek / MiniMax M3 / Claude)
   └── Manager reads the task → decomposes → delegates to specialist agents
   └── Each specialist agent: reads tools → queries external APIs → returns findings
   └── Tools used: Firecrawl, PRAW, SerperDev, store_scraper, pytrends

5. ChromaDB (one collection per dept_crew)
   └── Stores intermediate results within this department only
   └── Cross-department data is passed as explicit text inputs by the CEO

6. Department head synthesises its dept's outputs into a final dept result
   └── Returns the dept result to the Python CEO orchestrator

7. CEO orchestrator threads the dept result into the next dept_crew's inputs
   └── OR presents the dept result to the user (human gate)

8. Human Gate (where applicable)
   └── CEO orchestrator pauses → returns the report to FastAPI
   └── FastAPI sends the report to the frontend → waits for user reply
   └── User replies via the dashboard → CEO orchestrator resumes the workflow
   └── All human-gate state is held in the orchestrator (not inside the crew),
       so the dept_crew finishes cleanly and the next dept_crew starts fresh.

9. Output saved (per workflow completion)
   └── Markdown file → /backend/output/
   └── Key findings → Obsidian vault via obsidian_sync.py
   └── Run summary → jarvis.log

10. Frontend
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
| Jun 2026 | In-dept memory disabled (ChromaDB off, Obsidian only) | Inter-agent state flows via explicit task `context:`. ChromaDB available as a future upgrade path if a workflow develops a concrete semantic-recall need. Cross-run contamination eliminated by construction. ADR-0002. |
| Jun 2026 | No Docker until Phase 7 | Hides errors during learning phase — costs debugging time |
| Jun 2026 | Manual triggers before scheduling | Validate workflows work before automating them |
| Jun 2026 | Next.js frontend over Open WebUI | Long-term customisability — Open WebUI is fallback only |
| Jun 2026 | Hermes Agent deferred | Compelling self-improvement loop but community too small at this stage |
| Jun 2026 | Three-level CEO hierarchy from day one | Flat crews require full rewrite to add hierarchy later — cheaper to design correctly once |
| Jun 2026 | CEO is a Python orchestrator over per-dept CrewAI crews | CrewAI `Process.hierarchical` is 2 levels natively. A Python CEO + per-dept sub-crews gives the 3-level model the docs describe, while keeping the "specialists never cross departments" rule enforceable. |
| Jun 2026 | Engineering department excluded from Jarvis | Claude Code is purpose-built for coding — CrewAI agents are poor at long code generation, no overlap needed |
| Jun 2026 | Phase 3 split into 3a (briefs, manual post) and 3b (Skyvern auto-post) | Skyvern is the single biggest install risk in the project. Splitting the go/no-go boundary lets the creative half ship independently if Skyvern install fails. ADR-0003. |
| Jun 2026 | Cost guard: 200k-token hard cap per run, fail-loud on exceed | Buggy infinite-loop crew would otherwise blow the ₹2,000/month budget. Daily cap and automatic model fallback deferred to Phase 7. ADR-0001 Q14. |
| Jun 2026 | Save research brief before the human gate; expose PRD-only recovery path | The 6-specialist research brief is the most expensive output. Losing it on a PRD-write crash would force a full re-run. Brief is durable from the moment research_dept_crew.kickoff() returns. ADR-0001 Q15. |

---

*End of Architecture v1.0*
