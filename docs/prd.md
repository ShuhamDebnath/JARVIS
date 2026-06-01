# Jarvis — Product Requirements Document

> Version: 1.0  
> Status: Approved — Ready to Build  
> Owner: Mobile App Developer, Bengaluru, India  
> Last Updated: June 2026

---

## 1. Executive Summary

Jarvis is a personal AI operating system built for an independent mobile app developer. It handles the non-coding work — market research, competitor analysis, content creation, social posting, and UI validation — so the developer can stay focused on building apps.

It is not a SaaS product. It is not for other users. It is a private productivity system that runs locally on macOS, costs near-zero to operate, and gets smarter over time through a two-layer memory system.

The system is built in phases. Each phase delivers immediate value before the next begins.

---

## 2. Problem Statement

An independent mobile app developer working alone faces a recurring set of time drains:

- **Market research** before building a new app takes 3–5 hours manually
- **Competitor analysis** (App Store + Play Store reviews) is tedious and ignored in practice
- **Content creation** for social media (Twitter, Instagram, Reddit) takes 2+ hours per post when done properly
- **UI design validation** requires back-and-forth with tools and has no automated feedback loop
- **Morning briefings** — knowing what is trending right now in mobile dev — require manual checking of 5+ sources

The result: the developer spends more time on research and marketing than on building. Jarvis eliminates this.

---

## 3. Goals

| Goal | Measure of success |
|------|-------------------|
| Reduce market research time from 3–5 hrs to 15 min | Workflow 2 produces a full PRD from one sentence |
| Automate daily content briefing | Workflow 3 delivers ready-to-use briefs every morning |
| Enable voice-controlled Mac automation | Say a command, Mac executes it |
| Build a memory system that improves over time | Jarvis remembers past research, preferences, decisions |
| Keep monthly API cost under ₹2,000 | DeepSeek as primary LLM + cost guardrails |

---

## 4. Non-Goals

- This is NOT a SaaS product — no multi-user support, no auth system, no billing
- This is NOT a coding assistant — Claude Code handles that separately
- This is NOT a replacement for human judgment — every major output has a human approval gate
- No mobile app for Jarvis itself in Phase 1–3 (Telegram interface is a future phase)

---

## 5. Users

**Single user: the developer himself.**

Profile:
- Mobile app developer (iOS / Android / Flutter)
- Based in Bengaluru, India — IST timezone, Indian English
- Beginner-to-intermediate Python skills
- Prefers YAML config and low-code approaches over writing Python from scratch
- Has API keys for: DeepSeek, MiniMax via OpenRouter, Anthropic Claude
- Running macOS

---

## 6. Tech Stack

### Orchestration (Brain)
| Component | Tool | Why |
|-----------|------|-----|
| Agent framework | CrewAI | YAML config, hierarchical agents, built-in memory, beginner-friendly |
| Primary LLM | DeepSeek | 10x cheaper than GPT-4, strong reasoning |
| Coding / multimodal LLM | MiniMax M3 (via OpenRouter) | Multimodal, good at code, cost-effective |
| Fallback LLM | MiniMax M2.7 (via OpenRouter) | Long context fallback |
| Vision LLM | Claude (Anthropic) | Best for UI design validation tasks |

### Memory (Two-Layer)
| Layer | Tool | Purpose |
|-------|------|---------|
| Short-term / semantic search | ChromaDB (built into CrewAI) | Task context, recent research |
| Long-term / structured knowledge | Obsidian vault (Markdown + links) | Preferences, decisions, past PRDs, app ideas |

### Research & Scraping (Eyes)
| Tool | Purpose |
|------|---------|
| Firecrawl (self-hosted) | Web scraping — handles JS sites, outputs LLM-ready markdown |
| google-play-scraper (npm) | Play Store reviews, rankings, competitor data |
| app-store-scraper (npm) | App Store same |
| PRAW | Reddit API — official, free, reliable |
| pytrends | Google Trends — free, no API key |
| SerperDev | Web search for agents — 2,500 free queries/month |
| Instagrapi | Instagram data — use with burner account |

### Automation (Hands)
| Tool | Purpose |
|------|---------|
| Open Interpreter | Natural language → Mac terminal commands |
| Skyvern | AI browser agent — posts to social, manages App Store Connect |
| PyAutoGUI | Fallback mouse/keyboard control |

### Voice Layer
| Tool | Purpose |
|------|---------|
| Faster-Whisper | Speech-to-text, local, handles Indian English |
| Kokoro TTS | Text-to-speech, local, natural voice, free |
| Porcupine (Picovoice) | Wake word detection — "Hey Jarvis" |
| ntfy.sh | Push notifications to phone |

### Frontend & UI
| Tool | Purpose |
|------|---------|
| Next.js (App Router) | Custom dashboard — simple now, upgradeable |
| FastAPI | Backend API server |
| Open WebUI | Fallback chat interface via Docker |

---

## 7. System Architecture

```
User (voice / text / frontend)
         ↓
    FastAPI (main.py)
         ↓
    Jarvis CEO  (Python orchestrator — backend/crews/jarvis_ceo.py)
    │  No LLM call. Pure Python routing. Decides which dept_crews
    │  to activate, in what order, threads outputs as inputs.
    ↓
    ┌────────────── Per-department sub-crews (one CrewAI Crew per dept) ─────────────┐
    │  research_dept_crew   (Process.hierarchical, manager_agent: research_director)   │
    │  product_dept_crew    (Process.hierarchical, manager_agent: product_director)    │
    │  content_dept_crew    (Process.hierarchical, manager_agent: content_director)    │
    │  design_dept_crew     (Process.hierarchical, manager_agent: design_director)     │
    │  intelligence_dept_crew (Process.hierarchical, manager_agent: intelligence_director) │
    │  automation_dept_crew (Process.hierarchical, manager_agent: automation_director) │
    │                                                                                  │
    │  Each crew: memory=False (per ADR-0002). Specialist agents never call across    │
    │  depts — the CEO threads the output of one dept into the next dept's input.    │
    └──────────────────────────────────────────────────────────────────────────────────┘
         ↓                                            ↓
    Tools Layer                                   Memory Layer
    (Firecrawl, PRAW, Serper,                      (Obsidian vault — single
     store scrapers, pytrends,                      long-term layer. ChromaDB
     Skyvern, Claude Vision)                        disabled in dept_crews by
                                                   default per ADR-0002)
         ↓
    Output Layer (PRDs, briefs, reports, logs)
         ↓
    Frontend Dashboard (Next.js)
```

> Per ADR-0000 Q2 and ADR-0002: the CEO is **plain Python**, not a CrewAI agent.
> CrewAI's `Process.hierarchical` is natively 2-level (manager + workers); a Python
> CEO on top of per-department sub-crews gives the 3-level hierarchy this PRD
> describes, while keeping the "specialists never cross departments" rule
> mechanically enforceable.

---

## 8. Workflows

### Overview

| # | Workflow | Trigger | Approx. Time | Human Gate |
|---|----------|---------|--------------|------------|
| 1 | UI Design → Validation → Iteration | Manual upload | ~20 min/screen | End approval |
| 2 | Research → Market Validation → PRD | Manual — one sentence | ~15 min | Go/no-go at scoring |
| 3 | Social Trend → Viral Brief → Post | Manual trigger (schedule later) | ~10 min | Upload approval |
| 4 | App Store Intelligence Report | Manual trigger | ~10 min | None |
| 5 | Competitor Deep Teardown | Manual — name a competitor | ~12 min | Read report |
| 6 | Content Pipeline — Topic to Post | Manual — give topic | ~8 min | Review before post |
| 7 | Daily Morning Briefing (Voice) | Manual trigger | ~5 min | None |
| 8 | Mac Desktop Automation | Voice or text | On demand | Confirm risky actions |
| 9 | App Store Listing Optimiser | Manual trigger | ~15 min | Review new copy |
| 10 | Reddit Community Monitor | Manual trigger | ~5 min | None |

> **Note:** All workflows are manually triggered in Phase 1–3. Scheduling is added in Phase 4.

---

### Workflow 2 — Research → PRD (Highest Priority)

**Input:** One sentence from the user describing an app idea  
**Output:** Scored market validation report + full PRD document

Pipeline:
1. User types app idea in plain English
2. 6 agents run in parallel (~5 min):
   - Pain point hunter — Reddit, ProductHunt, 1-star App Store reviews
   - Competitor mapper — all existing apps, ratings, download estimates
   - Revenue estimator — App Store charts, pricing models, MRR estimates
   - Gap finder — recurring missing features across all competitor reviews
   - Trend validator — Google Trends, Reddit growth, Twitter momentum
   - Audience sizer — TAM from keyword volumes and subreddit sizes
3. Synthesis agent consolidates all 6 outputs
4. App Store validator — downloads competitor screenshots, Claude vision analyses UI patterns
5. Opportunity scorer — scores out of 50 across 5 dimensions. Above 35 = worth building.
6. Human gate — Jarvis presents score and asks: "Generate PRD?"
7. PRD generator writes full document if approved
8. Output saved to `/backend/output/PRD_appname_date.md`

---

### Workflow 1 — UI Design Validation Loop (Second Priority)

**Input:** Screen design document or Figma export  
**Output:** Validated design with AI feedback + iteration suggestions

Pipeline:
1. User uploads screen doc to `/backend/upload/`
2. Claude vision agent analyses UI patterns, usability, consistency
3. Feedback report generated with specific suggestions
4. User iterates → re-uploads → loop continues
5. Final approval saves validated design to `/backend/output/`

---

### Workflow 3 — Social Media Engine (Third Priority)

**Input:** Manual trigger  
**Output:** Platform-specific viral content briefs

Pipeline:
1. Trend scanner checks Reddit, Google Trends, Twitter, Instagram hashtags
2. Trend analyser ranks by velocity, niche relevance, India-specific reach
3. Viral idea generator creates briefs for YouTube, Instagram Reels, Twitter, Reddit
4. Community angle agent adds cross-post targets and best posting times (IST)
5. Brief delivered as text output in dashboard
6. User creates content using brief
7. User drops finished file in `/backend/upload/` → Skyvern posts with captions

---

## 9. Memory System

### ChromaDB (Short-term)
- **Status:** Built into CrewAI, but **disabled by default** in all `dept_crews` (per ADR-0002). `Crew(...)` calls in `backend/crews/dept_crews.py` are constructed with no `memory` argument — CrewAI's default is `False`. All agents in `agents.yaml` are also `memory: false`. Belt-and-braces; either alone suffices in current CrewAI.
- **Why disabled:** Inter-agent state flows through explicit task `context:`. ChromaDB inside a crew has no concrete consumer left, and removing it eliminates the cross-run contamination failure mode (run 2 of "to-do app" semantic-retrieving fragments from run 1 of "habit tracker") by construction.
- **Reserved upgrade path:** If a future workflow develops a concrete in-dept semantic-recall need, the upgrade is an ephemeral (RAM-only) ChromaDB client per `Crew` instance — leaves no on-disk state to leak between runs. See ADR-0002 for the full policy.

### Obsidian Vault (Long-term — active memory layer)
- Stored as Markdown files with bidirectional links
- Written to by: `obsidian_sync.py` after every significant workflow completion
- Stores: PRDs, market research summaries, competitor notes, user preferences, past decisions
- Queryable by: agents via file read tools, and by the user directly in Obsidian app
- Location: `/obsidian-vault/` in project root

---

## 10. Logging & Debugging

- All agent actions logged to `/backend/logs/jarvis.log`
- Log format: timestamp, crew name, agent name, action, status, duration
- Log levels: INFO (normal), WARNING (retried), ERROR (failed)
- Errors include full traceback for AI-assisted debugging
- Cost per run logged separately for budget tracking

---

## 11. Cost Guardrails

> Per ADR-0001 Q14: `backend/utils/cost_guard.py` ships in Phase 1 with a minimal viable implementation. The full automatic-fallback + daily-cap table is deferred to Phase 7 (per "manual before automated" principle).

| Guard | Behaviour | When |
|-------|-----------|------|
| Per-run token limit | Hard cap of 200,000 tokens per crew run. Exceeding raises `BudgetExceeded`, which the CEO orchestrator catches, sets run status to `failed`, and writes `backend/output/cost_exceeded_{run_id}.txt`. | Phase 1 |
| Daily spend cap | Total daily API spend tracked. Alert sent via ntfy.sh if exceeded. | Phase 7 |
| Model fallback | If DeepSeek is slow or unavailable, falls back to MiniMax M2.7 automatically. | Phase 7 |

**Phase 1 cost_guard.py API:** `start_run(run_id, max_tokens)`, `log_call(run_id, model, in_tok, out_tok)` (hooked into CrewAI `step_callback` / `task_callback`), `end_run(run_id)`, `check_budget(run_id)`. Hardcoded $/token table per model.

Target: under ₹2,000/month total API cost.

---

## 12. Frontend Dashboard

### Phase 1 (Build now — simple)
- Single page dashboard
- List of 10 workflow cards — each with a trigger button
- "Coming Soon" badge on workflows not yet built
- Output viewer panel — shows latest output from any workflow
- Agent status panel — shows which agents are running
- Log viewer — last 50 lines of `jarvis.log`

### Phase 2 (Later)
- Workflow history and output archive
- Memory browser (Obsidian vault viewer)
- Cost tracker chart
- Settings page (API keys, model selection, schedule config)

### Phase 3 (Future)
- Full custom Jarvis personality UI
- Voice interface in browser
- Mobile-optimised view

---

## 13. Environment Variables Required

```
DEEPSEEK_API_KEY=
OPENROUTER_API_KEY=        # For MiniMax M3 / M2.7
ANTHROPIC_API_KEY=         # For Claude vision tasks
SERPER_API_KEY=            # Web search for agents
FIRECRAWL_API_KEY=         # If using cloud version
PORCUPINE_ACCESS_KEY=      # Wake word detection
```

---

## 14. What Is Explicitly Out of Scope (Phase 1–6)

- Docker / containerisation (added in Phase 7, per ADR-0003 split)
- Scheduled / automated triggers (added in Phase 7)
- Telegram interface (future)
- Multi-user support (never)
- Mobile app for Jarvis (future)
- AutoGen Studio visual builder (optional later)

---

## 15. Success Criteria

| Milestone | Definition of done |
|-----------|-------------------|
| Phase 1 complete | Workflow 2 runs end-to-end and produces a real PRD from one sentence |
| Phase 2 complete | Workflow 3 produces content briefs and Skyvern posts to at least one platform |
| Phase 3 complete | Voice layer works — "Hey Jarvis, research [topic]" triggers a crew |
| Phase 4 complete | All 10 workflows built, scheduler running, full dashboard live |
| System mature | Obsidian memory has 30+ linked notes written by Jarvis from real usage |

---

*End of PRD v1.0*
