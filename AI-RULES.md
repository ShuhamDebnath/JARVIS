# AI-RULES.md — Universal AI Rules for Jarvis Project

> Paste this at the top of any AI session (Claude, ChatGPT, Gemini, etc.) when working on this project.
> These rules apply to every AI tool used in this project, not just Claude Code.
> Last Updated: June 2026

---

## Who I Am

- Solo mobile app developer, Bengaluru, India
- Building a personal AI OS called Jarvis
- Beginner-to-intermediate Python — I understand logic but not advanced patterns
- I prefer YAML config over Python boilerplate
- I work in short focused sessions — context matters, do not waste my time re-explaining basics
- My primary language is English. I speak with Indian phrasing at times — understand intent, do not correct grammar.

---

## The Project

Jarvis is a multi-agent CrewAI system that automates research, content, design validation, and social posting for a solo mobile app developer.

Full context is in:
- `docs/prd.md` — what we are building
- `docs/roadmap.md` — what phase we are in
- `docs/architecture.md` — every tool decision and why

If you have not read these, ask me to paste the relevant section before giving advice.

---

## Rule 1 — Be Direct

- Give me the answer, then the explanation — not the other way around
- Do not start responses with "Great question!" or "Certainly!" or any filler phrase
- Do not summarise what I just said back to me before answering
- One question at a time maximum — if you need clarification, ask the single most important thing
- If you are confident, say so. If you are not, say that too.

---

## Rule 2 — Code Rules

### Always
- Python 3.11
- Add inline comments on every non-obvious line
- Use `.env` for all secrets — never hardcode API keys
- Wrap every external API call in try/except with a human-readable error message
- Use the logger from `backend/utils/logger.py` — never use `print()` in production code
- Keep functions under 50 lines — split if longer
- Add a docstring to every function

### Never
- Do not use advanced Python patterns (decorators, metaclasses, complex generators) without explaining them
- Do not install libraries not already in the stack without asking first
- Do not write code that only works in your head — test your logic before giving it to me
- Do not give me pseudocode when I asked for real code
- Do not give me code with `# TODO` placeholders — finish it or tell me you cannot

### YAML first
- If something can be configured in `agents.yaml` or `tasks.yaml` instead of Python, do it in YAML
- Agent definitions → `backend/config/agents.yaml`
- Task definitions → `backend/config/tasks.yaml`
- Never hardcode model names or agent configs in Python files

---

## Rule 3 — Error Handling Protocol

When I paste an error:

1. Tell me what the error means in plain English — one sentence
2. Show me the fixed code — not a suggestion, actual working code
3. Tell me what was wrong and what the fix does — two sentences max
4. If I need to change `.env` or install something, say it explicitly at the top

Format:
```
WHAT WENT WRONG: [one sentence]
WHAT TO DO: [install / env change if needed]
FIXED CODE: [actual code]
WHY: [two sentences]
```

---

## Rule 4 — Honesty Rules

- If you do not know something, say so — do not guess and present it as fact
- If a library is outdated or has a known issue, tell me before I use it
- If my approach has a flaw, tell me directly — do not build on a bad foundation to avoid conflict
- If two options exist, tell me both with the tradeoffs — do not pick for me without explaining why
- If something I am asking for is out of scope for the current phase, say so and refer me to the roadmap

---

## Rule 5 — Out of Scope — Do Not Build These (Phase 1–6)

These are deferred intentionally. Do not suggest or build them unless I specifically ask and confirm:

| Thing | When |
|-------|------|
| Docker / containerisation | Phase 7 only |
| Scheduled / automated triggers | Phase 7 only |
| Telegram bot interface | Future — not planned |
| Multi-user support | Never |
| Auth / login system | Never |
| Mobile app for Jarvis | Future — not planned |
| LangChain | Not in stack — use CrewAI |
| OpenAI GPT-4 | Not in stack — use DeepSeek or MiniMax |
| Pinecone / Weaviate | Not in stack — use ChromaDB |

If I ask for something on this list, flag it and ask if I want to override intentionally.

---

## Rule 5b — Frontend Architecture (Phase 4+)

The Next.js App Router frontend (`frontend/`) communicates with FastAPI (`backend/`) exclusively through `frontend/lib/api.ts`. Do not call FastAPI directly from React components.

Key integration points:
- `GET /workflows/runs` → AgentStatus polling panel (5s interval)
- `GET /output/{filename}` → OutputViewer markdown rendering
- `POST /workflows/research-prd`, `/app-store-intelligence`, `/content-briefs`, `/auto-post` → WorkflowCard triggers

Typography: `@tailwindcss/typography` is **not** loaded via postcss or CSS `@import` in Tailwind v4 (Next.js 16 / Turbopack). Use `ReactMarkdown components={}` for styled markdown output. See ADR-0004 for details.

---

## Rule 5c — Phase 5 Voice Layer Prerequisites

When Phase 5 starts, Apple Silicon Macs require Homebrew-installed `portaudio` before Python audio libraries can be installed:

```bash
brew install portaudio
```

This is required for: faster-whisper, Kokoro TTS, pyaudio, pvporcupine.

---

## Rule 6 — Response Format

- Use markdown — I read responses in tools that render it
- Use tables for comparisons
- Use code blocks with language tags for all code
- Use bullet points for lists of steps
- Use bold for the most important word or phrase in a paragraph — not for decoration
- Keep responses focused — if I asked for one thing, give me one thing
- If the answer is long, structure it with clear headings

---

## Rule 7 — Memory and Context

- I work in sessions — you do not remember previous sessions unless I paste context
- If I paste this file, you have full context. Do not ask me to re-explain the project.
- If something changed since last session, I will tell you — do not assume
- If you need to know the current phase, ask me or check `docs/roadmap.md`
- Do not make assumptions about what was built in previous sessions — ask

---

## Rule 8 — LLM and Tool Decisions Are Finalised

The tech stack is decided. Do not suggest replacing:

- CrewAI with LangChain, AutoGen, or any other framework
- DeepSeek with GPT-4 or Claude for general tasks
- ChromaDB with Pinecone or any paid VectorDB
- Firecrawl with Playwright or BeautifulSoup for primary scraping
- Skyvern with Selenium or Puppeteer

If you have a strong reason to suggest a change, state it once clearly. If I say no, drop it.

---

## Rule 9 — Phase Discipline

- We build one phase at a time
- Do not write code for Phase 3 when we are in Phase 1
- Do not suggest architecture improvements that belong to a later phase
- If I ask for something that belongs to a future phase, tell me which phase it is in and ask if I want to defer or override

---

## Rule 10 — Commits and Documentation

After every working milestone, remind me to:

1. Test the feature end-to-end
2. Commit with the correct format:
   ```
   type: short description
   ```
3. Update `docs/roadmap.md` — mark the step complete
4. Update the `Current Phase` section in `CLAUDE.md` if a phase completed

Do not let me move to the next step without committing the current one.

---

## What a Good Session Looks Like

1. I tell you what we are building today
2. You confirm you understand the phase and the goal
3. We build one thing at a time — working before moving on
4. When something breaks, I paste the error — you fix it with the error protocol
5. When the thing works, you remind me to commit
6. We move to the next step

---

## What a Bad Session Looks Like — Avoid These

- Writing 500 lines of code without testing any of it
- Giving me code that "should work" without being sure
- Moving to the next feature before the current one runs
- Suggesting tools not in the stack without flagging it
- Writing boilerplate I do not understand and cannot debug
- Giving me a wall of explanation when I need working code

---

## One Final Rule

If at any point you are about to do something that conflicts with this file, stop and tell me before doing it. Ask once. Then follow my decision.

---

*End of AI-RULES.md*
