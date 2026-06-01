# Workflow 10 — Reddit Community Monitor

> Phase 6 | Department: Intelligence | ~5 min | Human gate: None

## What This Workflow Does

You trigger Jarvis (manually now, scheduled in Phase 7). It scans configured subreddits for posts matching your tracked keywords — app names, categories, pain points you care about. It surfaces posts you should read, reply to, or act on.

**Input:** Manual trigger (keywords + subreddits configured once in `.env`)  
**Output:** Reddit monitor report — posts flagged by relevance and opportunity type  
**Time:** ~5 minutes  
**Human gates:** None — report delivered automatically

## Agent Hierarchy

```
Jarvis CEO
└── intelligence_dept_crew
        manager_agent: intelligence_director
    └── Reddit Monitor  (already defined in Workflow 4)
```

## What It Monitors

Configured once in `.env`:
```
REDDIT_TRACKED_SUBREDDITS=androiddev,FlutterDev,iOSProgramming,mobiledev,india,startups
REDDIT_TRACKED_KEYWORDS=habit tracker,productivity app,offline app,flutter,swift
REDDIT_YOUR_APP_NAME=YourAppName
```

## What It Flags

Each post is classified into one of 4 opportunity types:

| Type | Description | Example |
|------|-------------|---------|
| REPLY OPPORTUNITY | User asking a question you can answer | "Best habit tracker for Android?" |
| PAIN POINT | User expressing frustration your app solves | "Why don't any habit apps work offline?" |
| COMPETITOR MENTION | Someone recommending or criticising a competitor | "I switched from Habitica to X because..." |
| YOUR APP MENTION | Someone mentioning your app — positive or negative | "Has anyone tried [YourApp]?" |

## Output Format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JARVIS REDDIT MONITOR
{date} | Scanned {n} subreddits | {n} posts flagged
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REPLY OPPORTUNITIES (answer these — builds visibility)

1. r/{subreddit} | {post title}
   Posted: {time ago} | Upvotes: {n} | Comments: {n}
   URL: {link}
   Why reply: {one sentence — what angle to take}

PAIN POINTS (your app might solve these)

1. r/{subreddit} | {post title}
   Pain expressed: {quote from post}
   URL: {link}

COMPETITOR MENTIONS

1. r/{subreddit} | {competitor} mentioned — {positive/negative}
   Quote: {key line}
   URL: {link}

YOUR APP MENTIONS

1. r/{subreddit} | {post title}
   Sentiment: POSITIVE / NEGATIVE / NEUTRAL
   URL: {link}
   Action needed: {reply suggested / none}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## tasks.yaml additions

```yaml
reddit_monitor_task:
  description: >
    Scan these subreddits: {tracked_subreddits}
    Look for posts matching these keywords: {tracked_keywords}
    Also scan for any mention of: {your_app_name}
    Classify each matching post into one of 4 types:
    REPLY OPPORTUNITY, PAIN POINT, COMPETITOR MENTION, YOUR APP MENTION.
    For REPLY OPPORTUNITYs: suggest a one-line angle for the reply.
    For YOUR APP MENTIONs: classify sentiment (positive/negative/neutral).
    Filter out posts older than 48 hours — only surface fresh opportunities.
    Deliver in the standard Jarvis Reddit Monitor format.
  expected_output: >
    Reddit monitor report in standard format. Only posts from last 48 hours.
    Each post classified with URL and action suggestion.
  agent: reddit_monitor
```

## Files Involved
```
backend/crews/jarvis_ceo.py    # add run_workflow_10(run_id)
backend/main.py                # add POST /workflow/reddit-monitor
backend/output/Reddit_{date}.md
```

## Cost Estimate
~₹2–4 per run — single agent, short context. Cheapest workflow alongside Workflow 7.

---

## Summary — All 10 Workflows

| # | Name | Dept | Phase | New agents | New tools | Est. cost/run |
|---|------|------|-------|------------|-----------|---------------|
| 1 | UI Design Loop | Design | 6 | design_director, ui_validator, design_feedback_agent, iteration_suggester | vision_tool | ₹5–10 |
| 2 | Research → PRD | Research + Product | 1 | All research + product agents | store_scraper, firecrawl, reddit, pytrends, serper | ₹8–15 |
| 3 | Social Engine | Content + Automation | 3 | content agents, social_poster | trend_tool, skyvern | ₹6–11 |
| 4 | App Store Intel | Intelligence | 2 | intelligence agents | none (reuses Phase 1 tools) | ₹3–6 |
| 5 | Competitor Teardown | Research | 6 | none (reuses Phase 1 agents) | none | ₹4–8 |
| 6 | Content Pipeline | Content | 6 | copywriter | none | ₹4–8 |
| 7 | Morning Briefing | Intelligence | 6 | none (reuses Workflow 4 agent) | none | ₹2–4 |
| 8 | Mac Automation | Automation | 6 | mac_automation_agent, automation_director | open_interpreter_tool | ₹1–3 |
| 9 | ASO Optimiser | Product | 6 | none (app_store_optimiser already in YAML) | none | ₹6–12 |
| 10 | Reddit Monitor | Intelligence | 6 | none (reuses reddit_monitor from W4) | none | ₹2–4 |

**Total monthly cost estimate at 30 runs of each workflow:** ~₹1,200–2,500  
**Primary cost driver:** Workflow 2 (PRD) — run it for serious ideas only, not every idea.

---