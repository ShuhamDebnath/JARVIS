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
Jarvis CEO  (Python orchestrator — backend/crews/jarvis_ceo.py)
│
├── research_dept_crew  (CrewAI Crew, process=Process.hierarchical)
│   │   manager_agent: research_director
│   ├── Pain Point Hunter
│   ├── Competitor Mapper
│   ├── Revenue Estimator
│   ├── Gap Finder
│   ├── Trend Validator
│   ├── Audience Sizer
│   └── (consolidation task owned by research_director)
│
└── product_dept_crew   (CrewAI Crew, process=Process.hierarchical)
    │   manager_agent: product_director
    ├── Opportunity Scorer
    └── PRD Writer
```

**Flow:**
1. User types idea in plain English via frontend or terminal
2. FastAPI route `POST /workflow/research` calls `run_workflow_2(idea)` in the CEO orchestrator
3. CEO orchestrator calls `research_dept_crew.kickoff(inputs={"idea": idea})`
4. research_director (manager_agent) runs `research_interpretation_task` first — produces a structured JSON interpretation brief (app_category, target_user, core_problem, search_keywords, subreddits_to_monitor, app_store_categories, ambiguity_flag). All 6 specialist tasks receive this as context.
5. If `ambiguity_flag` is non-null, the CEO orchestrator can either (a) ask the user a clarifying question via `human_gate.ask_user()`, or (b) proceed with the most likely interpretation and echo the flag into the final PRD's "Assumptions" section
6. research_director delegates 6 specialist tasks in parallel — each uses the interpretation JSON as its shared scope (same keywords, same subreddits, same App Store categories)
7. research_director consolidates 6 outputs into the unified research brief
8. research_dept_crew returns the brief to the CEO orchestrator
9. CEO orchestrator presents the opportunity score to the user (human gate)
10. User replies "yes" or "no" via the dashboard
11. If "yes", CEO calls `product_dept_crew.kickoff(inputs={"idea": idea, "research_brief": brief})`
12. product_director (manager_agent) delegates to opportunity_scorer and prd_writer
13. product_dept_crew returns the PRD to the CEO orchestrator
14. CEO saves the PRD to `backend/output/PRD_{appname}_{date}.md` and writes Obsidian notes
15. CEO returns the final result to FastAPI

The two dept_crews never share memory. The CEO orchestrator passes the research brief to the product dept as an explicit text input. This is what solves the "memory bleeding between runs" issue — each dept_crew can be reset cleanly and independently.

---

## Full Pipeline — Step by Step

### Step 1 — CEO Receives Input
- User types app idea in plain English via frontend or terminal
- CEO validates input is not empty
- CEO logs the request: `"Workflow 2 triggered: {idea}"`
- CEO activates Research Director with the idea as context

### Step 2 — 6 Research Specialists Run in Parallel

**Before the 6 specialists fire, `research_director` runs `research_interpretation_task` once (see tasks.yaml below).** That single LLM call converts the raw one-sentence idea into a structured JSON interpretation document containing:
- `app_category` (one of productivity / health / education / finance / social / utility / other)
- `target_user` (one-sentence demographic)
- `core_problem` (one-sentence problem statement)
- `search_keywords` (5 keywords all specialists must use)
- `subreddits_to_monitor` (5 subreddit names)
- `app_store_categories` (2 iOS + 2 Google Play categories)
- `ambiguity_flag` (string starting with `AMBIGUOUS:` if the idea is genuinely unclear, else `null`)

All 6 specialist tasks below receive this JSON as `context: [research_interpretation_task]` and are explicitly told in their description: *"Use the interpretation document above. Do not re-interpret the idea. Use the search_keywords, subreddits, and app_store_categories from the document."* This is what eliminates the "6 different research directions from the same input" failure mode — all specialists share one canonical interpretation.

**Why the director does the interpretation, not a new specialist agent:** adding a new agent would be a cross-cutting change (departments, hierarchy, agent files). The director is already the `manager_agent` — it owns the workflow. A cheap single-call task it executes is the lightest possible change. If interpretation quality is poor in early runs, the cheap fix is to tighten the director's system prompt, not spin up a new agent.

**Ambiguity flag handling:** If `ambiguity_flag` is non-null, the CEO orchestrator surfaces it to the user via the existing `human_gate.ask_user()` mechanism with a "Did you mean X or Y?" question. If the user does not reply within the gate's 24h timeout, the workflow proceeds with the most likely interpretation and the flag is echoed into the final PRD's "Assumptions" section so the user sees what Jarvis assumed.

All 6 agents fire simultaneously after the interpretation step completes. Each has a specific job and specific tools.

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

> **Scoring implementation — HYBRID RUBRIC (resolved 2026-06-01).**
> The first 4 dimensions are **hard sub-scores**: the LLM extracts a specific
> data point from the research brief, looks it up in the published rubric
> table (`scoring_rubric:` below), and reports the score from the table.
> The LLM is NOT allowed to assign a hard sub-score without showing both
> the data point and the rubric row. The 5th dimension (build effort) is
> the only **subjective** sub-score and is explicitly labelled "(subjective)".

**Scoring rule:**
- Above 35 → worth building → present to user with recommendation to proceed
- 25–35 → borderline → present to user with specific risks highlighted
- Below 25 → skip → present to user with evidence for why

> **Threshold calibration note:** The 35/50 threshold is a **default placeholder**.
> It must be empirically re-validated after 10+ real runs of Workflow 2.
> Until then, every scoring report logs the threshold it used at the top.
> Do NOT silently change the threshold.

### Step 5 — Human Gate

Jarvis presents the score to the user:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JARVIS MARKET VALIDATION REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Threshold used: 35/50 (DEFAULT — to be re-validated after 10+ runs)
Idea: Habit tracker for Indian college students

OPPORTUNITY SCORE: 38 / 50 ✅ Worth Building

  Market size:          8/10  — 540k subs across r/IndianHabits r/india + 1.2M
                                monthly searches (rubric row: 500k–2M)
  Competition density:  7/10  — 2 apps with rating ≥ 4.0 in category
                                (rubric row: 0–2 strong apps)
  Revenue potential:    8/10  — top app MRR ~$15k, subscription proven
                                (rubric row: $5k–$50k)
  Trend momentum:       9/10  — pytrends +34% YoY, Reddit +28% YoY
                                (rubric row: positive + >20% YoY)
  Build effort/reward:  6/10 (subjective) — 3–4 month MVP, push notifs +
                                offline sync + vernacular (LLM estimate)

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
# (top-level keys are departments, not individuals)
research_dept:
  research_director        # manager_agent of research_dept_crew
  pain_point_hunter
  competitor_mapper
  revenue_estimator
  gap_finder
  trend_validator
  audience_sizer
product_dept:
  product_director         # manager_agent of product_dept_crew
  opportunity_scorer
  prd_writer
```

```yaml
# backend/config/tasks.yaml — tasks for this workflow
# All task names are prefixed with their department to avoid collisions
# when the two dept_crews are assembled from the same tasks.yaml.

research_pain_point_task
research_competitor_mapping_task
research_revenue_estimation_task
research_gap_finding_task
research_trend_validation_task
research_audience_sizing_task
research_consolidation_task

product_opportunity_scoring_task
product_human_gate_task
product_prd_writing_task
product_output_saving_task
```

### Python files
```
backend/crews/jarvis_ceo.py         # Python orchestrator — run_workflow_2(idea)
backend/crews/dept_crews.py         # build_research_dept_crew() + build_product_dept_crew()
backend/tools/store_scraper.py      # App Store + Play Store data
backend/tools/firecrawl_tool.py     # web scraping
backend/tools/reddit_tool.py        # Reddit research
backend/memory/obsidian_sync.py     # saves findings to Obsidian vault
backend/utils/cost_guard.py         # tracks token usage per run
backend/main.py                     # FastAPI route: POST /workflow/research
backend/orchestrator/human_gate.py  # pause/resume handshake with FastAPI
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
# CEO NOTE — The CEO is NOT an agent. It is the Python function
# `run_workflow_2(idea)` in backend/crews/jarvis_ceo.py.
# See architecture.md, "Agent Hierarchy" section, for the full rationale.
# ─────────────────────────────────────────

# ─────────────────────────────────────────
# DEPARTMENT: research_dept
# Members of this department are loaded by build_research_dept_crew()
# in backend/crews/dept_crews.py. The dept head (research_director)
# becomes the manager_agent of the dept_crew.
# ─────────────────────────────────────────
research_director:
  dept: research_dept
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
  memory: false
  verbose: true

# ─────────────────────────────────────────
# LEVEL 3 — INTERPRETER (added per ADR-0002, grilling session 3, 2026-06-01)
# Dedicated specialist for converting the user's one-sentence app idea
# into a structured JSON interpretation. Separated from research_director
# so the manager-agent system prompt (which says "delegate") does not
# fight the interpretation task (which says "produce JSON yourself").
# The director is now coordinator + consolidator only.
# ─────────────────────────────────────────
research_interpreter:
  dept: research_dept
  role: Idea Interpretation Specialist
  goal: >
    Convert the user's one-sentence app idea into a structured JSON
    interpretation document used by all 6 research specialists.
  backstory: >
    You produce structured output, never free-form prose. You never
    delegate. Your output is parsed downstream — if it is not valid
    JSON matching the schema, the entire workflow breaks.
  llm: deepseek/deepseek-chat
    # ESCAPE HATCH (ADR-0002 Q5, grilling session 3, 2026-06-01):
    # If 3-retry validation failures exceed 5% over the first 10 runs,
    # switch to minimax/minimax-m3 (the coding/multimodal tier) — it's
    # better at strict structured output. Track the failure rate in
    # backend/output/interpretation_failures.log and re-evaluate.
  tools: []
  allow_delegation: false
  memory: false
  verbose: true

# ─────────────────────────────────────────
# DEPARTMENT: product_dept
# Members of this department are loaded by build_product_dept_crew()
# in backend/crews/dept_crews.py. The dept head (product_director)
# becomes the manager_agent of the dept_crew.
# ─────────────────────────────────────────
product_director:
  dept: product_dept
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
  memory: false
  verbose: true

# ─────────────────────────────────────────
# RESEARCH SPECIALISTS (Level 3 of research_dept)
# ─────────────────────────────────────────
pain_point_hunter:
  dept: research_dept
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
  memory: false

competitor_mapper:
  dept: research_dept
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
  memory: false

revenue_estimator:
  dept: research_dept
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
  memory: false

gap_finder:
  dept: research_dept
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
  memory: false

trend_validator:
  dept: research_dept
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
  memory: false

audience_sizer:
  dept: research_dept
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
  memory: false

# ─────────────────────────────────────────
# LEVEL 3 — PRODUCT SPECIALISTS
# ─────────────────────────────────────────
opportunity_scorer:
  dept: product_dept
  role: Opportunity Scoring Specialist
  goal: >
    Score the market opportunity for {idea} out of 50 using a HYBRID rubric:
    4 hard sub-scores extracted from explicit data points via a strict rubric,
    and 1 subjective sub-score (build effort) estimated from the feature list.

    The 4 hard sub-scores are:
    - Market size          (rubric-based, data-extracted)
    - Competition density  (rubric-based, data-extracted)
    - Revenue potential    (rubric-based, data-extracted)
    - Trend momentum       (rubric-based, data-extracted)

    The 1 subjective sub-score is:
    - Build effort vs reward (LLM judgement from feature complexity)

    You MUST extract the underlying numbers first, then map them to 1-10
    using the published rubric below. You are NOT allowed to assign a
    sub-score without showing the extracted data point that produced it.

    Default go/no-go threshold is 35/50. This is a placeholder — it
    must be empirically re-validated after 10+ real runs of Workflow 2.
    Do NOT change the threshold silently. Log the threshold used at the
    top of every scoring report.
  backstory: >
    You are a ruthless opportunity evaluator. You score with evidence, not emotion.
    You have seen hundreds of app ideas fail because founders skipped validation.
    Your job is to save the developer time by being honest about what the data says.

    You do NOT trust your own gut. For 4 of 5 dimensions, you extract a
    hard number from the research brief and look up the score in a fixed
    rubric table. You are a calculator, not a critic, for those dimensions.

    For build effort, you ARE allowed to use judgement — LLMs are good
    at reading a feature list and estimating engineering complexity.
    You mark that sub-score with "(subjective)" so the user knows.
  llm: deepseek/deepseek-chat
  tools: [ScoringRubricTool]   # wraps the hardcoded rubric table below
  allow_delegation: false
  memory: false

# Rubric table — the LLM looks up scores in this, not invents them.
# Stored in a tool so the LLM cannot hallucinate it.
# Calibration note: these brackets are placeholders. Adjust after 10+ runs.
scoring_rubric:
  market_size:
    inputs_from: audience_sizer
    rubric:
      1: "Total addressable subreddit + keyword volume < 10,000"
      3: "10,000 – 100,000"
      5: "100,000 – 500,000"
      7: "500,000 – 2,000,000"
      10: "> 2,000,000"
  competition_density:
    inputs_from: competitor_mapper
    invert: true
    rubric:
      10: "0–2 apps with rating ≥ 4.0 in category"
      7:  "3–5 apps with rating ≥ 4.0"
      4:  "6–10 apps with rating ≥ 4.0"
      1:  "10+ apps with rating ≥ 4.0"
  revenue_potential:
    inputs_from: revenue_estimator
    rubric:
      1: "No monetisation model exists in the category"
      3: "Ads only — eCPM < $1"
      5: "Freemium present — top app MRR < $5k"
      7: "Top app MRR $5k–$50k, subscription model proven"
      10: "Top app MRR > $50k, multiple proven monetisation models"
  trend_momentum:
    inputs_from: trend_validator
    rubric:
      1:  "pytrends 12-month slope negative, Reddit activity flat"
      4:  "pytrends flat, Reddit activity growing"
      7:  "pytrends positive slope, Reddit growth > 20% YoY"
      10: "pytrends steep positive slope, Reddit growth > 50% YoY"
  build_effort_vs_reward:
    inputs_from: LLM judgement on feature list from gap_finder
    subjective: true
    rubric:
      1:  "MVP requires ML, real-time infra, payments, > 6 months solo"
      4:  "MVP requires 1–2 hard integrations (auth, payments), 3–4 months"
      7:  "MVP is mostly CRUD + polish, 1–2 months"
      10: "MVP is a weekend build, near-zero risk"

prd_writer:
  dept: product_dept
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
  memory: false
```

---

## tasks.yaml — Full Config for This Workflow

```yaml
# Research tasks — interpretation runs first, then 6 specialists fan out in parallel
# All names are prefixed with `research_` so they cannot collide with
# product_dept tasks loaded by build_product_dept_crew().

# ─────────────────────────────────────────
# TASK 0 — Interpretation (revised 2026-06-01 per ADR-0002, grilling session 3)
# Single LLM call. Produces a structured JSON interpretation that all 6
# specialists consume as context. Prevents 6-different-research-directions
# failure mode where the same input produced 6 different research threads.
#
# Originally owned by research_director (ADR-0000 Q5). Reassigned to
# research_interpreter per ADR-0002 Q7 because the manager-agent system
# prompt ("delegate") was fighting the interpretation prompt ("produce
# JSON yourself"). The director is now coordinator + consolidator only.
#
# Schema is enforced by Pydantic v2 via `output_pydantic` — see
# backend/contracts/research.py. Retry policy: max_retries=3; on all
# retries failing, contracts.research.InterpretationValidationError is
# raised. CEO orchestrator catches it and writes the LLM transcript to
# backend/output/failed_interpretation_{run_id}.md.
# ─────────────────────────────────────────
research_interpretation_task:
  description: >
    Interpret the user's one-sentence app idea into a structured brief.
    Output ONLY this JSON shape — no other text, no markdown fences:
    {
      "app_category": "<one of: productivity | health | education | finance | social | utility | other>",
      "target_user": "<one-sentence demographic, 10-200 chars>",
      "core_problem": "<one-sentence problem statement, 10-300 chars>",
      "search_keywords": ["<3-10 keywords all specialists must use>"],
      "subreddits_to_monitor": ["<1-8 subreddit names, NO 'r/' prefix>"],
      "app_store_categories": ["<2-6 App Store / Play Store category names>"],
      "ambiguity_flag": "<null when clear, or 'AMBIGUOUS: <why>' when unclear>"
    }
  expected_output: >
    Valid JSON matching the schema above. No prose, no markdown fences.
    The next task in this crew depends on this output being parseable.
  agent: research_interpreter
  output_pydantic: contracts.research.ResearchInterpretation
  max_retries: 3

# All 6 specialist tasks below share the interpretation JSON as context.
# The "Use the interpretation document above" line in each description is
# the explicit instruction that prevents specialists from re-interpreting.

research_pain_point_task:
  description: >
    Research pain points for this app idea: {idea}

    Use the interpretation document from research_interpretation_task
    (shared as context). Do not re-interpret the idea. Use the
    search_keywords and subreddits_to_monitor from the interpretation
    document — do not invent your own.

    Search Reddit (the subreddits listed in the interpretation),
    ProductHunt discussions, and App Store 1-star reviews for apps
    in the interpretation's app_category.
    Return the top 10 pain points. For each: the pain point,
    source URL, and a direct quote or evidence.
  expected_output: >
    A numbered list of 10 pain points with source URLs and evidence quotes.
    Search keywords and subreddits used MUST match the interpretation document.
  agent: pain_point_hunter
  async_execution: true
  context: [research_interpretation_task]

research_competitor_mapping_task:
  description: >
    Find all apps that compete with this idea: {idea}

    Use the interpretation document from research_interpretation_task
    (shared as context). Do not re-interpret the idea. Use the
    app_store_categories and search_keywords from the interpretation
    document — do not invent your own.

    Search App Store and Play Store (in the app_store_categories from
    the interpretation) for the top 10 competitors.
    For each app return: name, rating, estimated downloads,
    last update date, price, key strength, key weakness.
  expected_output: >
    A markdown table with 10 competitors and all required columns filled.
    App store categories searched MUST match the interpretation document.
  agent: competitor_mapper
  async_execution: true
  context: [research_interpretation_task]

research_revenue_estimation_task:
  description: >
    Estimate the revenue opportunity for this idea: {idea}

    Use the interpretation document from research_interpretation_task
    (shared as context). Do not re-interpret the idea. Use the
    app_category and search_keywords from the interpretation document.

    Find pricing models of the top competitors.
    Estimate MRR for the top 3 apps based on chart position and review velocity.
    Return: revenue range, top 3 monetisation models used, India pricing context.
  expected_output: >
    Revenue range estimate, monetisation model breakdown, India-specific pricing note.
  agent: revenue_estimator
  async_execution: true
  context: [research_interpretation_task]

research_gap_finding_task:
  description: >
    Find the top 5 feature gaps in apps competing with: {idea}

    Use the interpretation document from research_interpretation_task
    (shared as context). Do not re-interpret the idea. Use the
    app_category and search_keywords from the interpretation document.

    Read 1-star and 2-star reviews across all competitor apps and Reddit complaints.
    Only report gaps that appear in multiple sources.
    For each gap: description, evidence count, and example quotes.
  expected_output: >
    Top 5 feature gaps with evidence count and example quotes for each.
  agent: gap_finder
  async_execution: true
  context: [research_interpretation_task]

research_trend_validation_task:
  description: >
    Validate market trend for this app idea: {idea}

    Use the interpretation document from research_interpretation_task
    (shared as context). Do not re-interpret the idea. Use the
    search_keywords and target_user from the interpretation document.

    Check Google Trends for 5-year trajectory of the search_keywords.
    Check Reddit for subreddit growth (use subreddits_to_monitor) in the last 12 months.
    Search for recent news about this market.
    Include India-specific signals.
  expected_output: >
    Trend direction (growing/stable/declining), velocity score,
    India-specific trend data, and 3 supporting data points.
    Search keywords and subreddits used MUST match the interpretation document.
  agent: trend_validator
  async_execution: true
  context: [research_interpretation_task]

research_audience_sizing_task:
  description: >
    Estimate the audience size for this app idea: {idea}

    Use the interpretation document from research_interpretation_task
    (shared as context). Do not re-interpret the idea. Use the
    target_user, subreddits_to_monitor, and search_keywords from the
    interpretation document.

    Use subreddit subscriber counts, monthly keyword search volumes,
    and App Store category download estimates.
    Always break out India-specific numbers separately.
  expected_output: >
    Global TAM estimate, India SAM estimate, primary demographic profile
    (age range, occupation, device type). Subreddits and keywords used
    MUST match the interpretation document.
  agent: audience_sizer
  async_execution: true
  context: [research_interpretation_task]

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
  context: [research_pain_point_task, research_competitor_mapping_task, research_revenue_estimation_task,
            research_gap_finding_task, research_trend_validation_task, research_audience_sizing_task]

# Scoring task — owned by product_dept
product_opportunity_scoring_task:
  description: >
    Score the market opportunity for: {idea}
    Use the research brief from the consolidation task.

    STEP 1 — For each of the 4 hard dimensions, you MUST:
      (a) Extract the specific data point from the research brief
          (e.g. "subreddit size = 47,000 subscribers",
                 "competitors with rating ≥ 4.0 = 8 apps",
                 "top app MRR = $12k",
                 "pytrends 12-month slope = +18%").
      (b) Look up the matching bracket in the ScoringRubricTool
          and report the score from the rubric.
      (c) Show the data point AND the rubric lookup in the output.
      (d) You are NOT allowed to assign a hard sub-score without
          showing both the extracted data and the rubric row that
          produced it.

    STEP 2 — For the 1 subjective dimension (build effort vs reward):
      (a) Read the top 3 gaps from the Gap Finder and the top 3
          pain points from Pain Point Hunter.
      (b) Estimate Flutter/Swift MVP complexity in weeks of solo work.
      (c) Score 1–10 with the explicit label "(subjective)" so the
          user knows this sub-score is LLM judgement, not a rubric.

    STEP 3 — At the TOP of the report, log:
      "Threshold used: 35/50 (DEFAULT — to be re-validated after 10+ runs)"
      The user must see this every time so they know the threshold
      has not been empirically calibrated yet.

    STEP 4 — Present the standard Jarvis score format with the
    4 hard sub-scores and 1 subjective sub-score, total out of 50.

    STEP 5 — End with: "Generate full PRD? (yes / no)"
  expected_output: >
    Formatted opportunity score report. Must contain:
    - Threshold-used line at the top
    - For each of 4 hard sub-scores: the extracted data point, the
      rubric row it mapped to, and the score
    - For build effort: explicit "(subjective)" label
    - Total out of 50 and the human gate question
  agent: opportunity_scorer
  context: [research_consolidation_task]
  human_input: true

# PRD task — only runs if user approved
product_prd_writing_task:
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
  context: [research_consolidation_task, product_opportunity_scoring_task]
```

---

## Crew Assembly — Three Files, Three Jobs

This workflow is split across three files. The split matches the 3-level hierarchy from `docs/architecture.md`: a Python CEO on top, then per-department CrewAI crews, then specialist agents inside each crew.

### File 1 — `backend/crews/jarvis_ceo.py` (the Python orchestrator)

```python
# backend/crews/jarvis_ceo.py
# Pure Python — no LLM call. Calls dept_crews and threads their outputs.
# Implements ADR-0001 Q14 (cost_guard wiring) and Q15 (save brief before
# the gate; PRD-only recovery path; None-as-decline for ask_user()).

from crews.dept_crews import build_research_dept_crew, build_product_dept_crew
from orchestrator.human_gate import ask_user_go_no_go
from memory.obsidian_sync import sync_research, sync_prd
from utils.cost_guard import start_run, end_run, BudgetExceeded
from utils.logger import get_logger

logger = get_logger(__name__)

# Per-run hard cap. Configurable later; Phase 1 ships hardcoded.
MAX_TOKENS_PER_RUN = 200_000


def run_workflow_2(idea: str, run_id: str) -> dict:
    """Top-level Workflow 2 entry point. Returns a status dict."""
    # 0. Cost guard — start token tracking for this run
    start_run(run_id, max_tokens=MAX_TOKENS_PER_RUN)

    try:
        # 1. Research dept runs — 6 specialists + consolidation task
        research_crew = build_research_dept_crew()
        research_brief = research_crew.kickoff(inputs={"idea": idea})

        # 2. Save the brief to Obsidian IMMEDIATELY (ADR-0001 Q15).
        # The brief is the most expensive output (6 specialist calls).
        # If the human gate or anything after this fails, the brief
        # is still durable.
        sync_research(idea, research_brief)

        # 3. Human gate — opportunity score is inside the brief.
        # ask_user_go_no_go returns None on timeout (24h default per
        # human_gate.py); treat None as decline (Q15 refined rec).
        decision = ask_user_go_no_go(run_id, research_brief["opportunity_score"])
        if not decision:                              # False OR None → decline
            logger.info(f"Run {run_id} declined at human gate")
            return {"status": "declined", "brief": research_brief}

        # 4. Product dept runs — only if user said yes
        product_crew = build_product_dept_crew()
        prd = product_crew.kickoff(inputs={
            "idea": idea,
            "research_brief": research_brief,
        })

        # 5. Save PRD to disk + Obsidian
        sync_prd(idea, prd)

        return {"status": "completed", "prd": prd}

    except BudgetExceeded as e:
        # Q14: per-run token cap exceeded. Log + write evidence + mark failed.
        logger.error(f"Run {run_id} exceeded token budget: {e}")
        with open(f"backend/output/cost_exceeded_{run_id}.txt", "w") as f:
            f.write(f"Run {run_id} exceeded {MAX_TOKENS_PER_RUN} tokens.\n{e}\n")
        return {"status": "failed", "reason": "budget_exceeded"}

    finally:
        # Always log cost — successful, declined, or failed
        end_run(run_id)


def run_workflow_2_prd_only(idea: str, brief_path: str, run_id: str) -> dict:
    """Recovery path (ADR-0001 Q15): re-run the PRD step using a saved brief.

    Use when product_crew.kickoff() crashed after sync_research() already
    wrote the brief to Obsidian. Loads brief from disk, skips the expensive
    research dept call, runs only product_dept_crew.
    """
    start_run(run_id, max_tokens=MAX_TOKENS_PER_RUN)
    try:
        research_brief = load_brief_from_disk(brief_path)   # helper in obsidian_sync
        product_crew = build_product_dept_crew()
        prd = product_crew.kickoff(inputs={
            "idea": idea,
            "research_brief": research_brief,
        })
        sync_prd(idea, prd)
        return {"status": "completed", "prd": prd}
    except BudgetExceeded as e:
        logger.error(f"PRD-only run {run_id} exceeded budget: {e}")
        return {"status": "failed", "reason": "budget_exceeded"}
    finally:
        end_run(run_id)
```

### File 2 — `backend/crews/dept_crews.py` (the two CrewAI crews)

```python
# backend/crews/dept_crews.py
# Builds the two sub-crews. Each one is its own Crew(process=Process.hierarchical)
# with its own manager_agent and its own ChromaDB collection.

from crewai import Crew, Process
from config.loader import load_agents_for, load_tasks_for

def build_research_dept_crew() -> Crew:
    agents = load_agents_for("research_dept")       # agents.yaml → research_dept section
    tasks  = load_tasks_for("research_dept")        # tasks.yaml  → research_* tasks
    return Crew(
        agents=agents,
        tasks=tasks,
        process=Process.hierarchical,
        manager_agent=agents["research_director"],
        verbose=True,
    )

def build_product_dept_crew() -> Crew:
    agents = load_agents_for("product_dept")
    tasks  = load_tasks_for("product_dept")         # tasks.yaml → product_* tasks
    return Crew(
        agents=agents,
        tasks=tasks,
        process=Process.hierarchical,
        manager_agent=agents["product_director"],
        verbose=True,
    )
```

### File 3 — `backend/orchestrator/human_gate.py` (the pause/resume handshake)

This file is the only place that knows about HTTP. It blocks the CEO orchestrator until the user replies via the dashboard, then returns. See **Question 3 (next)** for the full design of this file.

### FastAPI route

```python
# backend/main.py
from fastapi import FastAPI
from crews.jarvis_ceo import run_workflow_2

app = FastAPI()

@app.post("/workflow/research")
def start_research(payload: dict):
    run_id = new_run_id()
    bg_run(run_workflow_2, payload["idea"], run_id)   # runs in background
    return {"status": "running", "run_id": run_id}

@app.get("/workflow/status/{run_id}")
def get_status(run_id: str):
    return read_run_state(run_id)                     # returns running | waiting_input | done

@app.post("/workflow/reply/{run_id}")
def user_reply(run_id: str, payload: dict):
    return store_human_reply(run_id, payload["reply"])    # human_gate.py polls this
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
| `scoring_rubric_tool.py` | hardcoded rubric table from ADR-0000 Q1 (opportunity scoring) | None — pure data, no API |
| `vision_tool.py` | Claude Vision (Workflow 1, Phase 6) | ANTHROPIC_API_KEY |

> **Source:** Tool list per ADR-0001 Q10 (grilling session 2, 2026-06-01). `scoring_rubric_tool.py` was previously implicit; it is now an explicit deliverable so the LLM cannot hallucinate the rubric table. `vision_tool.py` lives in Phase 6 because Workflow 1 (UI validation) is built there.

---

## Cost Estimate Per Run

| Model | Calls per run | Est. tokens | Est. cost |
|-------|--------------|-------------|-----------|
| DeepSeek | ~16 agent calls (1 interpretation + 6 specialists + 1 consolidation + 2 product + ~6 internal) | ~85,000 tokens | ~₹9–16 |
| MiniMax M3 | 0 (not used here) | — | — |
| Claude Vision | 0 (not used here) | — | — |

**Estimated cost per Workflow 2 run: ₹9–16**  
At 30 runs/month: ~₹300–500/month for this workflow alone.

> **+1 interpretation call** (resolved 2026-06-01, see ADR Q5): a single DeepSeek call producing the structured JSON interpretation brief. ~5 seconds, ~₹0.50 per run. Pays for itself in reproducibility — two runs of the same idea now produce comparable PRDs.

---

## Testing Checklist

Before marking Phase 1 complete:

- [ ] Run with idea: `"A habit tracker for Indian college students"`
- [ ] `research_interpretation_task` runs first and produces a valid JSON brief (app_category, target_user, core_problem, search_keywords, subreddits_to_monitor, app_store_categories, ambiguity_flag)
- [ ] All 6 parallel agents receive the interpretation as `context` (check logs for the dependency resolution)
- [ ] All 6 parallel agents return outputs (check logs)
- [ ] **Reproducibility test (resolved 2026-06-01, ADR Q5):** run the same idea twice, confirm the interpretation JSON is identical (same keywords, same subreddits, same categories) and the downstream specialist outputs use the same scope
- [ ] **Ambiguity flag test:** run with idea `"a productivity app"`, confirm `ambiguity_flag` is set to a non-null `AMBIGUOUS: ...` value and the CEO orchestrator surfaces it via `human_gate.ask_user()`
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
