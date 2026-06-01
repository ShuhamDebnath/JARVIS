# Workflow 4 — App Store Intelligence Report

> Version: 1.0  
> Status: Ready to Build — Phase 2  
> Priority: Fourth — builds immediately after Workflow 2, reuses its tools  
> Last Updated: June 2026

---

## What This Workflow Does

You name an app category or keyword. Jarvis scrapes the App Store and Play Store, reads the top reviews, and delivers a ranked competitor report with complaints, gaps, and opportunity signals — all in under 10 minutes.

**Input:** App category or keyword — example: `"habit tracker"` or `"language learning India"`  
**Output:** Formatted intelligence report saved as markdown  
**Time:** ~10 minutes  
**Human gates:** None — report delivered automatically

---

## Why This Builds Before Workflow 3

Workflow 4 reuses `store_scraper.py`, `reddit_tool.py`, and `firecrawl_tool.py` built in Phase 1. Zero new tool installs. Fastest possible Phase 2 — most of the work is YAML config additions.

---

## Agent Hierarchy for This Workflow

```
Jarvis CEO  (Python orchestrator — backend/crews/jarvis_ceo.py)
│
└── intelligence_dept_crew  (CrewAI Crew, process=Process.hierarchical)
        manager_agent: intelligence_director  (LLM: DeepSeek)
    ├── App Store Analyst      (scrapes rankings + reviews)
    ├── Reddit Monitor         (finds community complaints)
    └── Morning Briefing Agent (not used in this workflow — deferred to Workflow 7)
```

**CEO call for this workflow:**
```python
def run_workflow_4(category: str, run_id: str) -> dict:
    intel_crew = build_intelligence_dept_crew()
    report = intel_crew.kickoff(inputs={"category": category})
    save_output(report, f"AppStore_{category}_{today()}.md")
    obsidian_sync.write_intelligence_note(category, report)
    return {"status": "completed", "report": report}
```

---

## Full Pipeline — Step by Step

### Step 1 — CEO Receives Input
- User types a category or keyword via frontend or terminal
- CEO logs: `"Workflow 4 triggered: {category}"`
- CEO activates intelligence_dept_crew with category as context
- No human gate needed — this is a read-only intelligence report

### Step 2 — App Store Analyst

**Tools used:** app-store-scraper, google-play-scraper, SerperDev

The analyst runs 4 sub-tasks in sequence:

**Sub-task A — Rankings scrape**
- Searches App Store and Play Store for the category keyword
- Returns top 20 apps sorted by: rating, number of ratings, estimated downloads
- Flags: last update date (stale apps = opportunity), paid vs free, IAP presence

**Sub-task B — Review mining**
- For each of the top 10 apps: fetches the 50 most recent reviews
- Separates 1-star and 2-star reviews (complaints) from 4-star and 5-star (strengths)
- Extracts recurring themes — groups similar complaints together
- Returns: complaint frequency map per app

**Sub-task C — Competitor profiling**
- For each top 10 app: visits the App Store listing via Firecrawl
- Extracts: screenshots count, description keywords, update cadence, developer name
- Flags: apps not updated in 6+ months (possible abandonment)

**Sub-task D — Gap identification**
- Compares complaint themes across all 10 apps
- Finds complaints that appear across 3+ apps (systemic gap vs one-off bug)
- Ranks gaps by: frequency, severity language used, recency

### Step 3 — Reddit Monitor

**Tools used:** PRAW, SerperDev

- Searches top 5 relevant subreddits for the category keyword
- Finds: complaint threads, feature request posts, "I switched from X to Y" posts
- Cross-references with App Store gaps — validates or adds new gaps
- Returns: top Reddit complaints + any apps recommended by the community (often hidden gems)

### Step 4 — Intelligence Director Consolidates

Produces the final report in this exact structure:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JARVIS APP STORE INTELLIGENCE REPORT
Category: {category}
Generated: {date} {time} IST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOP 10 APPS — RANKED

| Rank | App | Rating | # Ratings | Last Update | Price | Trend |
|------|-----|--------|-----------|-------------|-------|-------|
| 1    | ... | ...    | ...       | ...         | ...   | ↑/↓/→ |

TOP COMPLAINTS ACROSS ALL APPS

1. [complaint] — found in [n] apps — severity: HIGH/MED/LOW
   Evidence: "[quote from review]"

2. [complaint] — found in [n] apps ...

BIGGEST OPPORTUNITY GAP

[The single gap with highest frequency + severity + no existing solution]
Evidence count: [n reviews] + [n Reddit posts]

STALE APPS (not updated 6+ months — possible market opening)

- [App name] — last update: [date] — [n] ratings — rating: [x]

REDDIT COMMUNITY SIGNAL

- Most recommended app: [app] — reason: [why community likes it]
- Biggest community complaint: [complaint]
- Hidden gem found: [app if any]

OPPORTUNITY SCORE (quick, not full Workflow 2)

Worth researching further? [YES / BORDERLINE / NO]
Reason: [2 sentences]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 5 — Output Saved

- Report saved to: `backend/output/AppStore_{category}_{date}.md`
- Obsidian note written: `obsidian-vault/intelligence/{category}_{date}.md`
- Each competitor gets a note updated: `obsidian-vault/competitors/{appname}.md`
- Run cost logged to `jarvis.log`

---

## agents.yaml additions for Workflow 4

```yaml
# ─────────────────────────────────────────
# DEPARTMENT: intelligence_dept
# All agents: memory: false (ADR-0002)
# ─────────────────────────────────────────
intelligence_director:
  dept: intelligence_dept
  role: Intelligence Department Director
  goal: >
    Coordinate App Store and Reddit intelligence gathering for {category}.
    Activate App Store Analyst and Reddit Monitor.
    Consolidate findings into a ranked intelligence report in the standard format.
  backstory: >
    You are a market intelligence director who has tracked thousands of app categories.
    You find what others miss — the gaps, the stale players, the hidden community favourites.
    You deliver reports that are specific and actionable, not vague summaries.
  llm: deepseek/deepseek-chat
  allow_delegation: true
  memory: false

app_store_analyst:
  dept: intelligence_dept
  role: App Store Intelligence Analyst
  goal: >
    For the category {category}: scrape App Store and Play Store top apps,
    mine their reviews for complaints and strengths, profile each competitor,
    and identify systemic gaps that appear across 3+ apps.
  backstory: >
    You read thousands of app reviews so the developer does not have to.
    You find the patterns — the complaints that keep appearing, the features
    everyone is asking for that no app provides. You cite evidence, not opinions.
  llm: deepseek/deepseek-chat
  tools: [AppStoreScraperTool, PlayStoreScraperTool, FirecrawlTool, SerperDevTool]
  allow_delegation: false
  memory: false

reddit_monitor:
  dept: intelligence_dept
  role: Reddit Community Intelligence Specialist
  goal: >
    Search Reddit for community discussion about the category {category}.
    Find complaint threads, feature requests, app switches, and hidden gems.
    Cross-reference with App Store gaps to validate or surface new ones.
  backstory: >
    Reddit communities are the most honest source of product feedback on the internet.
    You find what users say when they think no one from the company is watching.
    You distinguish one-off complaints from systemic patterns.
  llm: deepseek/deepseek-chat
  tools: [RedditTool, SerperDevTool]
  allow_delegation: false
  memory: false

morning_briefing_agent:
  dept: intelligence_dept
  role: Morning Briefing Specialist
  goal: >
    Compile a daily morning briefing of what matters today in mobile development.
    Sources: App Store trending, Reddit top posts, Google Trends spikes.
    Deliver in under 5 minutes of reading. Voice-friendly format.
  backstory: >
    You are a daily briefing specialist. You surface only what changed today —
    not background knowledge the developer already has. Every briefing is
    fresh, specific, and takes under 5 minutes to consume.
  llm: deepseek/deepseek-chat
  tools: [AppStoreScraperTool, RedditTool, PytrendsTool, SerperDevTool]
  allow_delegation: false
  memory: false
```

---

## tasks.yaml additions for Workflow 4

```yaml
# ─── Workflow 4 — App Store Intelligence ───
intel_store_analysis_task:
  description: >
    Analyse the App Store and Play Store for category: {category}
    Step 1: Search and return top 20 apps sorted by rating and review count.
    Step 2: Fetch 50 recent reviews per top 10 app. Separate complaints (1–2 star)
    from strengths (4–5 star). Extract recurring themes.
    Step 3: Visit each app's listing via Firecrawl — extract screenshots count,
    description keywords, update date, developer name.
    Step 4: Find complaints that appear in 3+ apps. Rank by frequency and severity.
    Flag apps not updated in 6+ months.
  expected_output: >
    Ranked app table (top 20), complaint frequency map per app,
    systemic gaps list with evidence count, stale apps list.
  agent: app_store_analyst

intel_reddit_analysis_task:
  description: >
    Search Reddit for community discussion about: {category}
    Search r/androiddev, r/FlutterDev, r/iOSProgramming, r/apps, r/india,
    and any category-specific subreddits.
    Find: complaint threads, feature requests, app switch posts, hidden gem recommendations.
    Cross-reference with App Store gaps — which gaps does Reddit also confirm?
    Are there any gaps Reddit mentions that the App Store reviews missed?
  expected_output: >
    Top Reddit complaints with post links, hidden gem apps if found,
    community-confirmed gaps, most recommended app and why.
  agent: reddit_monitor

intel_consolidation_task:
  description: >
    Consolidate the App Store analysis and Reddit intelligence for: {category}
    Produce the full intelligence report in the standard Jarvis format:
    - Top 10 ranked apps table
    - Top complaints ranked by frequency and severity (with evidence quotes)
    - Biggest opportunity gap with total evidence count (store + Reddit)
    - Stale apps list
    - Reddit community signal section
    - Quick opportunity score: YES / BORDERLINE / NO with 2-sentence reason
  expected_output: >
    Complete formatted intelligence report in the standard Jarvis format.
    Minimum 600 words. Every gap has at least 3 pieces of evidence.
  agent: intelligence_director
  context: [intel_store_analysis_task, intel_reddit_analysis_task]
```

---

## Files Involved

```
backend/crews/dept_crews.py         # add build_intelligence_dept_crew() factory
backend/crews/jarvis_ceo.py         # add run_workflow_4(category, run_id)
backend/main.py                     # add POST /workflow/intelligence
backend/output/AppStore_{cat}_{date}.md
obsidian-vault/intelligence/{cat}_{date}.md
obsidian-vault/competitors/{appname}.md
```

**No new tool files needed** — all tools built in Phase 1 are reused.

---

## Cost Estimate Per Run

| Model | Calls | Est. tokens | Est. cost |
|-------|-------|-------------|-----------|
| DeepSeek | ~6 agent calls | ~30,000 tokens | ~₹3–6 |

**Estimated cost per Workflow 4 run: ₹3–6** — cheapest workflow in the system.

---

## Testing Checklist

- [ ] Run with category: `"habit tracker"`
- [ ] Top 20 apps returned with all columns populated
- [ ] Review mining returns complaints for at least 8 of 10 apps
- [ ] At least 3 systemic gaps identified with evidence count
- [ ] Reddit section returns at least 2 community signals
- [ ] Report saved to `backend/output/AppStore_habittracker_{date}.md`
- [ ] Obsidian competitor notes created (one per app found)
- [ ] Cost logged — should be under ₹10
- [ ] Run completes in under 10 minutes

---

*End of Workflow 4 Spec v1.0*
