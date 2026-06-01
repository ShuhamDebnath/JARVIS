# Workflow 2 — Research → Market Validation → PRD

> Version: 1.0  
> Status: Ready to Build — Phase 1  
> Priority: HIGHEST — this is the first workflow to build  
> Last Updated: June 2026

---

## What This Workflow Does

You give Jarvis one sentence describing an app idea.  
Jarvis researches the market, scores the opportunity, and — if you approve — writes a full Product Requirements Document.

**Input:** One sentence. Example: `"A habit tracker for Indian college students"`  
**Output:** Opportunity score (out of 50) + full PRD saved as a markdown file  
**Time:** ~15 minutes end to end  
**Human gates:** One — go/no-go decision after the score is presented

---

## Agent Hierarchy for This Workflow

```
Jarvis CEO
└── Research Director
    ├── Pain Point Hunter
    ├── Competitor Mapper
    ├── Revenue Estimator
    ├── Gap Finder
    ├── Trend Validator
    └── Audience Sizer
└── Product Director
    ├── Opportunity Scorer
    └── PRD Writer
```

**Flow:**
1. CEO receives idea → activates Research Director + Product Director
2. Research Director runs 6 specialists in parallel
3. Research Director consolidates findings → passes to Product Director
4. Opportunity Scorer scores → presents to user → waits for approval
5. PRD Writer runs only if user approves
6. CEO returns final output

---

## Full Pipeline — Step by Step

### Step 1 — CEO Receives Input
- User types app idea in plain English via frontend or terminal
- CEO validates input is not empty
- CEO logs the request: `"Workflow 2 triggered: {idea}"`
- CEO activates Research Director with the idea as context

### Step 2 — 6 Research Specialists Run in Parallel

All 6 agents fire simultaneously. Each has a specific job and specific tools.

#### Agent A — Pain Point Hunter
**Job:** Find real user frustrations that prove the problem exists  
**Sources:** Reddit threads, ProductHunt discussions, App Store 1-star reviews  
**Tools:** PRAW, app-store-scraper, SerperDev  
**Output:** Top 10 pain points with source URLs and quote evidence  

#### Agent B — Competitor Mapper
**Job:** Map every existing app that solves this problem  
**Sources:** App Store search, Play Store search, Google  
**Tools:** app-store-scraper, google-play-scraper, SerperDev  
**Output:** Table of top 10 competitors — name, rating, downloads estimate, last update, price  

#### Agent C — Revenue Estimator
**Job:** Estimate how much money exists in this market  
**Sources:** App Store charts, pricing pages, app revenue databases  
**Tools:** Firecrawl, SerperDev  
**Output:** Revenue range estimate, top 3 monetisation models used, estimated MRR for top apps  

#### Agent D — Gap Finder
**Job:** Find features that users repeatedly ask for but no app provides  
**Sources:** All competitor app reviews (1 and 2 star), Reddit complaints, feature request threads  
**Tools:** app-store-scraper, google-play-scraper, PRAW  
**Output:** Top 5 recurring missing features with evidence count per feature  

#### Agent E — Trend Validator
**Job:** Confirm the market is growing, not shrinking  
**Sources:** Google Trends, Reddit growth data, Twitter/X momentum  
**Tools:** pytrends, PRAW, SerperDev  
**Output:** Trend direction (growing / stable / declining), velocity score, India-specific trend data  

#### Agent F — Audience Sizer
**Job:** Estimate how many people have this problem  
**Sources:** Subreddit sizes, keyword search volumes, App Store category size  
**Tools:** PRAW, SerperDev, Firecrawl  
**Output:** TAM estimate, India-specific addressable market, primary demographic profile  

### Step 3 — Research Director Consolidates

Research Director receives all 6 outputs and produces a single unified research brief:

```
RESEARCH BRIEF
--------------
Problem confirmed: [yes/no] — [one sentence summary]
Market size: [TAM estimate]
Top pain points: [top 3]
Competitor landscape: [n apps found, avg rating X]
Biggest gap: [the single most important missing feature]
Trend: [growing/stable/declining] at [velocity]
India angle: [specific India market insight]
```

### Step 4 — Opportunity Scorer Runs

Scores the opportunity out of 50 across 5 dimensions:

| Dimension | Max Score | What it measures |
|-----------|-----------|-----------------|
| Market size | 10 | TAM — bigger market = higher score |
| Competition density | 10 | Inverted — fewer strong competitors = higher score |
| Revenue potential | 10 | Monetisation clarity and MRR ceiling |
| Trend momentum | 10 | Growing fast = high score, declining = low |
| Build effort vs reward | 10 | Can one developer build the MVP? Reward justifies effort? |

**Scoring rule:**
- Above 35 → worth building → present to user with recommendation to proceed
- 25–35 → borderline → present to user with specific risks highlighted
- Below 25 → skip → present to user with evidence for why

### Step 5 — Human Gate

Jarvis presents the score to the user:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JARVIS MARKET VALIDATION REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Idea: Habit tracker for Indian college students

OPPORTUNITY SCORE: 38 / 50 ✅ Worth Building

Market size:          8/10  — ₹340Cr addressable in India
Competition density:  7/10  — 12 apps exist, none rated above 3.8
Revenue potential:    8/10  — Freemium model dominant, ₹2–8L/month ceiling
Trend momentum:       9/10  — Growing 34% YoY in India, Reddit activity up
Build effort/reward:  6/10  — 3–4 month MVP, moderate complexity

TOP GAP FOUND:
No existing app has offline mode + vernacular language support.
This appears in 847 reviews across 6 competitor apps.

ESTIMATED REVENUE: ₹1.5–6L/month within 12 months

Generate full PRD? (yes / no)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

- If user says **yes** → proceed to Step 6
- If user says **no** → save the research brief to Obsidian vault, end workflow

### Step 6 — PRD Writer Runs

PRD Writer uses the full research brief + score to generate a complete PRD.

**PRD sections generated:**

```
1. Executive Summary
   - One paragraph: what the app is, who it is for, why now

2. Problem Statement
   - Primary problem with Reddit/review evidence and quote
   - Secondary problems ranked by frequency
   - Who experiences this problem (demographic from Audience Sizer)

3. Market Opportunity
   - TAM and India-specific SAM
   - Revenue model recommendation with reasoning
   - Competitive window (why build now)

4. User Personas
   - 2–3 personas built from real review data
   - Each: name, age, location, pain, current solution, frustration

5. Competitor Analysis Table
   - All mapped competitors
   - Columns: name, rating, downloads, price, key strength, key weakness

6. MVP Feature List
   - Features sorted by: must-have / should-have / nice-to-have
   - Each feature: description + user story + why included (evidence)

7. V2 Feature List
   - Features deferred from MVP
   - Each: why deferred, what signal would justify adding it

8. Differentiation Strategy
   - The one thing this app does that no competitor does
   - How to communicate it in App Store listing

9. Monetisation Plan
   - Recommended model with reasoning
   - Free tier limits
   - Paid tier price and features
   - India-specific pricing consideration

10. Technical Notes (Flutter/Swift)
    - Screen count estimate
    - Key technical challenges flagged
    - Third-party services needed

11. Screen List
    - Every screen the MVP needs
    - Feeds directly into Workflow 1 (UI Design Loop)

12. Success Metrics and KPIs
    - D1 / D7 / D30 retention targets
    - Rating target
    - Revenue target at 3 / 6 / 12 months
```

### Step 7 — Output Saved

- PRD saved to: `backend/output/PRD_{appname}_{date}.md`
- Key findings written to Obsidian vault:
  - `obsidian-vault/research/{appname}.md` — research brief
  - `obsidian-vault/prd/{appname}.md` — link to PRD
  - `obsidian-vault/competitors/{competitor}.md` — one note per competitor found
- Run cost logged to `backend/logs/jarvis.log`
- CEO notifies user: `"PRD saved. Want me to start generating screens? (Workflow 1)"`

---

## Files Involved

### Config files (YAML)
```yaml
# backend/config/agents.yaml — agents for this workflow
jarvis_ceo
research_director
pain_point_hunter
competitor_mapper
revenue_estimator
gap_finder
trend_validator
audience_sizer
product_director
opportunity_scorer
prd_writer
```

```yaml
# backend/config/tasks.yaml — tasks for this workflow
research_coordination_task
pain_point_research_task
competitor_mapping_task
revenue_estimation_task
gap_finding_task
trend_validation_task
audience_sizing_task
research_consolidation_task
opportunity_scoring_task
human_gate_task
prd_writing_task
output_saving_task
```

### Python files
```
backend/crews/research_crew.py      # assembles all agents + tasks, runs the workflow
backend/tools/store_scraper.py      # App Store + Play Store data
backend/tools/firecrawl_tool.py     # web scraping
backend/tools/reddit_tool.py        # Reddit research
backend/memory/obsidian_sync.py     # saves findings to Obsidian vault
backend/utils/cost_guard.py         # tracks token usage per run
backend/main.py                     # FastAPI route: POST /workflow/research
```

### Output files
```
backend/output/PRD_{appname}_{YYYY-MM-DD}.md
backend/logs/jarvis.log
obsidian-vault/research/{appname}.md
obsidian-vault/prd/{appname}.md
obsidian-vault/competitors/{competitor}.md
```

---

## agents.yaml — Full Config for This Workflow

```yaml
# ─────────────────────────────────────────
# LEVEL 1 — CEO
# ─────────────────────────────────────────
jarvis_ceo:
  role: Jarvis Chief Executive Officer
  goal: >
    Receive the user's app idea, activate the correct departments,
    synthesise all outputs, and present a clear final result to the user.
    Never do research or writing yourself — delegate everything.
  backstory: >
    You are Jarvis — a personal AI operating system for a solo mobile app developer.
    You think like a startup CEO. You decompose problems, delegate to specialists,
    and synthesise results into clear decisions. You are direct, efficient, and never waste words.
  llm: deepseek/deepseek-chat
  allow_delegation: true
  verbose: true

# ─────────────────────────────────────────
# LEVEL 2 — DEPARTMENT HEADS
# ─────────────────────────────────────────
research_director:
  role: Research Department Director
  goal: >
    Coordinate all 6 research specialists for {idea}.
    Ensure each specialist completes their task.
    Consolidate all findings into one unified research brief.
  backstory: >
    You are the head of a world-class market research department.
    You never do research yourself — you coordinate specialists and
    synthesise their findings into a clear, evidence-based brief.
  llm: deepseek/deepseek-chat
  allow_delegation: true
  memory: true
  verbose: true

product_director:
  role: Product Department Director
  goal: >
    Take the research brief for {idea} and produce:
    1. An opportunity score out of 50 with clear reasoning
    2. A complete PRD if the user approves
  backstory: >
    You are a senior product director who has launched 20+ mobile apps.
    You know what makes an app succeed in India. You score opportunities
    with evidence, not gut feeling, and write PRDs that developers can
    actually build from.
  llm: deepseek/deepseek-chat
  allow_delegation: true
  memory: true
  verbose: true

# ─────────────────────────────────────────
# LEVEL 3 — RESEARCH SPECIALISTS
# ─────────────────────────────────────────
pain_point_hunter:
  role: Pain Point Research Specialist
  goal: >
    Find real user frustrations that prove the problem exists for {idea}.
    Search Reddit, ProductHunt, and App Store 1-star reviews.
    Return the top 10 pain points with source URLs and direct evidence.
  backstory: >
    You are an obsessive researcher who finds what users actually complain about,
    not what founders assume they complain about. You only cite real sources.
    You never make up pain points.
  llm: deepseek/deepseek-chat
  tools: [RedditTool, AppStoreScraperTool, SerperDevTool]
  allow_delegation: false
  memory: true

competitor_mapper:
  role: Competitor Analysis Specialist
  goal: >
    Map every existing app that competes with {idea}.
    Find top 10 competitors on App Store and Play Store.
    Return: name, rating, estimated downloads, last update date, price, key strength, key weakness.
  backstory: >
    You are a competitive intelligence analyst. You find every player in a market,
    quantify their position, and surface their weaknesses with evidence from their reviews.
  llm: deepseek/deepseek-chat
  tools: [AppStoreScraperTool, PlayStoreScraperTool, SerperDevTool]
  allow_delegation: false
  memory: true

revenue_estimator:
  role: Revenue Estimation Specialist
  goal: >
    Estimate the revenue opportunity for {idea}.
    Find pricing models of top competitors, App Store chart positions,
    and estimate MRR for the top 3 apps. Return a revenue range and
    the top 3 monetisation models used in this category.
  backstory: >
    You are a mobile app revenue analyst. You estimate market size from
    public signals — chart positions, review counts, pricing pages.
    You give ranges, not false precision.
  llm: deepseek/deepseek-chat
  tools: [FirecrawlTool, SerperDevTool, AppStoreScraperTool]
  allow_delegation: false
  memory: true

gap_finder:
  role: Feature Gap Research Specialist
  goal: >
    Find the features that users of {idea} category apps repeatedly ask for
    but no existing app provides. Search 1 and 2-star reviews across all
    competitor apps and Reddit complaints. Return top 5 gaps with evidence count.
  backstory: >
    You read thousands of negative reviews to find the patterns others miss.
    You only report gaps that appear in multiple sources — never single anecdotes.
    Evidence count per gap is mandatory.
  llm: deepseek/deepseek-chat
  tools: [AppStoreScraperTool, PlayStoreScraperTool, RedditTool]
  allow_delegation: false
  memory: true

trend_validator:
  role: Market Trend Validation Specialist
  goal: >
    Validate whether the market for {idea} is growing, stable, or declining.
    Use Google Trends for search volume trajectory, Reddit for community growth,
    and web search for recent news. Include India-specific trend data.
  backstory: >
    You validate market timing. A great idea in a declining market is still a bad investment.
    You use data, not opinion, and you always include India-specific signals because
    that is the primary market for this developer.
  llm: deepseek/deepseek-chat
  tools: [PytrendsTool, RedditTool, SerperDevTool]
  allow_delegation: false
  memory: true

audience_sizer:
  role: Audience Sizing Specialist
  goal: >
    Estimate the total addressable market for {idea} in India and globally.
    Use subreddit sizes, keyword search volumes, and App Store category data.
    Return TAM estimate, India SAM, and primary demographic profile.
  backstory: >
    You size markets from public signals. You are conservative — you never
    inflate TAM. You always break out India-specific numbers because
    Indian pricing and behaviour differs significantly from global averages.
  llm: deepseek/deepseek-chat
  tools: [RedditTool, SerperDevTool, FirecrawlTool]
  allow_delegation: false
  memory: true

# ─────────────────────────────────────────
# LEVEL 3 — PRODUCT SPECIALISTS
# ─────────────────────────────────────────
opportunity_scorer:
  role: Opportunity Scoring Specialist
  goal: >
    Score the market opportunity for {idea} out of 50.
    Use the research brief from Research Director.
    Score 5 dimensions: market size, competition density (inverted),
    revenue potential, trend momentum, build effort vs reward.
    Present score with clear reasoning per dimension.
  backstory: >
    You are a ruthless opportunity evaluator. You score with evidence, not emotion.
    You have seen hundreds of app ideas fail because founders skipped validation.
    Your job is to save the developer time by being honest about what the data says.
  llm: deepseek/deepseek-chat
  allow_delegation: false
  memory: true

prd_writer:
  role: Product Requirements Document Writer
  goal: >
    Write a complete, developer-ready PRD for {idea} using the research brief
    and opportunity score. Include all 12 sections. Be specific — no vague requirements.
    Every feature must have a user story and evidence from research.
  backstory: >
    You are a senior product manager who writes PRDs that developers love.
    You are specific, structured, and evidence-driven. You know Flutter and Swift
    well enough to flag technical complexity. You always include a screen list
    because it feeds directly into the design workflow.
  llm: deepseek/deepseek-chat
  allow_delegation: false
  memory: true
```

---

## tasks.yaml — Full Config for This Workflow

```yaml
# Research tasks — run in parallel
pain_point_research_task:
  description: >
    Research pain points for this app idea: {idea}
    Search Reddit (relevant subreddits), ProductHunt discussions,
    and App Store 1-star reviews for apps in this category.
    Return the top 10 pain points. For each: the pain point,
    source URL, and a direct quote or evidence.
  expected_output: >
    A numbered list of 10 pain points with source URLs and evidence quotes.
  agent: pain_point_hunter

competitor_mapping_task:
  description: >
    Find all apps that compete with this idea: {idea}
    Search App Store and Play Store for the top 10 competitors.
    For each app return: name, rating, estimated downloads,
    last update date, price, key strength, key weakness.
  expected_output: >
    A markdown table with 10 competitors and all required columns filled.
  agent: competitor_mapper

revenue_estimation_task:
  description: >
    Estimate the revenue opportunity for this idea: {idea}
    Find pricing models of the top competitors.
    Estimate MRR for the top 3 apps based on chart position and review velocity.
    Return: revenue range, top 3 monetisation models used, India pricing context.
  expected_output: >
    Revenue range estimate, monetisation model breakdown, India-specific pricing note.
  agent: revenue_estimator

gap_finding_task:
  description: >
    Find the top 5 feature gaps in apps competing with: {idea}
    Read 1-star and 2-star reviews across all competitor apps and Reddit complaints.
    Only report gaps that appear in multiple sources.
    For each gap: description, evidence count, and example quotes.
  expected_output: >
    Top 5 feature gaps with evidence count and example quotes for each.
  agent: gap_finder

trend_validation_task:
  description: >
    Validate market trend for this app idea: {idea}
    Check Google Trends for 5-year trajectory.
    Check Reddit for subreddit growth in the last 12 months.
    Search for recent news about this market.
    Include India-specific signals.
  expected_output: >
    Trend direction (growing/stable/declining), velocity score,
    India-specific trend data, and 3 supporting data points.
  agent: trend_validator

audience_sizing_task:
  description: >
    Estimate the audience size for this app idea: {idea}
    Use subreddit subscriber counts, monthly keyword search volumes,
    and App Store category download estimates.
    Always break out India-specific numbers separately.
  expected_output: >
    Global TAM estimate, India SAM estimate, primary demographic profile
    (age range, occupation, device type).
  agent: audience_sizer

# Consolidation task — runs after all 6 parallel tasks complete
research_consolidation_task:
  description: >
    Consolidate all research findings for: {idea}
    You have received outputs from 6 specialists:
    pain points, competitors, revenue, gaps, trends, and audience.
    Synthesise into one unified research brief using this format:
    - Problem confirmed: yes/no + one sentence
    - Market size: TAM and India SAM
    - Top 3 pain points
    - Competitor landscape summary
    - Biggest gap found
    - Trend direction and velocity
    - India-specific insight
  expected_output: >
    A structured research brief in the exact format specified.
    No watered-down summaries — include the strongest evidence from each specialist.
  agent: research_director
  context: [pain_point_research_task, competitor_mapping_task, revenue_estimation_task,
            gap_finding_task, trend_validation_task, audience_sizing_task]

# Scoring task
opportunity_scoring_task:
  description: >
    Score the market opportunity for: {idea}
    Use the research brief from the consolidation task.
    Score each dimension out of 10 with reasoning:
    - Market size (bigger = higher)
    - Competition density (less competition = higher)
    - Revenue potential (clearer model = higher)
    - Trend momentum (faster growth = higher)
    - Build effort vs reward (easier build + higher reward = higher)
    Present in the standard Jarvis score format.
    End with: "Generate full PRD? (yes / no)"
  expected_output: >
    Formatted opportunity score report with dimension scores,
    reasoning, top gap, revenue estimate, and the human gate question.
  agent: opportunity_scorer
  context: [research_consolidation_task]
  human_input: true

# PRD task — only runs if user approved
prd_writing_task:
  description: >
    Write a complete PRD for: {idea}
    Use the research brief and opportunity score as your source material.
    Write all 12 sections:
    1. Executive Summary
    2. Problem Statement (with evidence)
    3. Market Opportunity
    4. User Personas (from real review data)
    5. Competitor Analysis Table
    6. MVP Feature List (with user stories)
    7. V2 Feature List
    8. Differentiation Strategy
    9. Monetisation Plan (India pricing)
    10. Technical Notes (Flutter/Swift)
    11. Screen List
    12. Success Metrics and KPIs
    Be specific. No vague requirements. Every feature needs a user story.
  expected_output: >
    A complete markdown PRD document with all 12 sections.
    Minimum 1500 words. Every feature has a user story.
    Screen list is complete and can feed into Workflow 1.
  agent: prd_writer
  context: [research_consolidation_task, opportunity_scoring_task]
```

---

## research_crew.py — Structure Reference

```python
# backend/crews/research_crew.py
# Do not write code until Phase 1 build session.
# This is the structural reference for Claude Code.

# What this file does:
# 1. Loads all agents from agents.yaml
# 2. Loads all tasks from tasks.yaml
# 3. Assembles the crew with Process.hierarchical
# 4. Sets manager_agent = jarvis_ceo
# 5. Runs the crew with kickoff(inputs={"idea": user_input})
# 6. On completion: saves output to /backend/output/
# 7. Calls obsidian_sync.py to write memory notes
# 8. Logs token usage and cost to jarvis.log

# FastAPI route in main.py:
# POST /workflow/research
# Body: { "idea": "string" }
# Returns: { "status": "running", "run_id": "uuid" }
# Frontend polls GET /workflow/status/{run_id} for updates
```

---

## Tools Required

| Tool file | What it wraps | API key needed |
|-----------|--------------|----------------|
| `store_scraper.py` | app-store-scraper + google-play-scraper (npm) | None |
| `firecrawl_tool.py` | Firecrawl API | FIRECRAWL_API_KEY |
| `reddit_tool.py` | PRAW | Set up via Reddit app (free) |
| `serper_tool.py` | SerperDev | SERPER_API_KEY |
| `pytrends_tool.py` | pytrends (Google Trends) | None |

---

## Cost Estimate Per Run

| Model | Calls per run | Est. tokens | Est. cost |
|-------|--------------|-------------|-----------|
| DeepSeek | ~15 agent calls | ~80,000 tokens | ~₹8–15 |
| MiniMax M3 | 0 (not used here) | — | — |
| Claude Vision | 0 (not used here) | — | — |

**Estimated cost per Workflow 2 run: ₹8–15**  
At 30 runs/month: ~₹300–450/month for this workflow alone.

---

## Testing Checklist

Before marking Phase 1 complete:

- [ ] Run with idea: `"A habit tracker for Indian college students"`
- [ ] All 6 parallel agents return outputs (check logs)
- [ ] Research consolidation produces a structured brief
- [ ] Opportunity score appears with correct format
- [ ] Human gate pauses — workflow does not auto-proceed
- [ ] Type "yes" → PRD writer runs and produces all 12 sections
- [ ] Type "no" → workflow ends gracefully, research saved to Obsidian
- [ ] PRD file saved to `backend/output/PRD_habittracker_{date}.md`
- [ ] Obsidian vault notes created (research + PRD + competitor files)
- [ ] Token usage logged in `jarvis.log`
- [ ] Run a second idea to confirm memory does not bleed between runs

---

## Common Errors and Fixes

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `PRAW 401 Unauthorized` | Reddit credentials wrong or expired | Re-generate Reddit app credentials at reddit.com/prefs/apps |
| `Firecrawl timeout` | Page too large or JS-heavy site | Increase timeout in `firecrawl_tool.py`, add retry |
| `app-store-scraper returns empty` | App Store rate limiting | Add 2-second delay between calls |
| `DeepSeek rate limit` | Too many parallel calls | Add `max_rpm` setting to CrewAI config |
| `Human gate not pausing` | `human_input: true` missing in tasks.yaml | Add it to `opportunity_scoring_task` |
| `Memory bleeding between runs` | ChromaDB collection not reset | Reset collection at start of each crew run |

---

## Next Workflow to Build After This

Once Workflow 2 is tested and committed → build **Workflow 4 (App Store Intelligence Report)**.  
It reuses `store_scraper.py` and `reddit_tool.py` built in this phase — minimal new code needed.

Workflow 4 spec: `docs/workflows/workflow-4-appstore-intelligence.md`

---

*End of Workflow 2 Spec v1.0*
