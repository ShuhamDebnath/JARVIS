# Workflow 7 — Daily Morning Briefing

> Phase 6 | Department: Intelligence | ~5 min | Human gate: None | Voice-friendly

## What This Workflow Does

You trigger Jarvis (manually now, scheduled in Phase 7). Jarvis scans what changed overnight — App Store trending shifts, Reddit hot posts, Google Trends spikes — and delivers a concise morning briefing. Under 5 minutes to consume. Voice-readable.

**Input:** Manual trigger (scheduled daily 7:00 AM IST in Phase 7)  
**Output:** Morning briefing delivered as dashboard text + spoken via Kokoro TTS (Phase 5+)  
**Time:** ~5 minutes end to end

## Agent Hierarchy

```
Jarvis CEO
└── intelligence_dept_crew
        manager_agent: intelligence_director
    └── Morning Briefing Agent  (single agent — fast, focused)
```

## What the Briefing Covers

The briefing agent checks 5 sources in parallel and delivers one tight summary:

| Source | What it checks | Signal it surfaces |
|--------|---------------|-------------------|
| App Store | Today's top charts vs yesterday | Any new app entered top 100 in your categories |
| Reddit | Hot posts in r/androiddev, r/FlutterDev, r/iOSProgramming | Developer news, viral threads |
| Google Trends | Any spike in keywords you track | Emerging search interest in your app space |
| Hacker News | Top 5 posts flagged as relevant | Tech news affecting mobile dev |
| Twitter/X India | India trending dev topics | Local market signals |

## Briefing Output Format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JARVIS MORNING BRIEFING
{date} | {time} IST | Read time: ~3 min
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHAT CHANGED OVERNIGHT

App Store:
- [signal] — [why it matters to you]

Reddit:
- [hot post title] — [subreddit] — [key takeaway]

Google Trends:
- [keyword] spiked [X]% — [context]

Hacker News:
- [relevant post] — [why relevant]

India Signal:
- [trending topic] — [relevance]

NOTHING TO MISS TODAY
[1–2 sentences max — the single most important thing from above]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## agents.yaml — morning_briefing_agent already defined in Workflow 4

No new agent config needed.

## tasks.yaml additions

```yaml
morning_briefing_task:
  description: >
    Generate today's morning briefing for a mobile app developer in Bengaluru, India.
    Check these 5 sources in parallel:
    1. App Store today's charts vs yesterday — any movement in: {tracked_categories}
    2. Reddit hot posts: r/androiddev, r/FlutterDev, r/iOSProgramming, r/india
    3. Google Trends spikes for: {tracked_keywords}
    4. Hacker News top 5 — filter for mobile dev relevance
    5. Twitter India trending — filter for developer relevance
    Deliver in the standard Jarvis morning briefing format.
    End with "NOTHING TO MISS TODAY" — the single most important signal.
    Keep the entire briefing under 400 words — it must be readable in 3 minutes.
  expected_output: >
    Morning briefing in standard format. Under 400 words total.
    Voice-readable — no markdown tables, bullet points only.
  agent: morning_briefing_agent
```

## Tracked Categories and Keywords

These are configured in `.env` or a simple JSON config:
```
TRACKED_CATEGORIES=productivity,health,education,utilities
TRACKED_KEYWORDS=flutter,swift,react native,mobile app india
```

## Files Involved
```
backend/crews/jarvis_ceo.py    # add run_workflow_7(run_id)
backend/main.py                # add POST /workflow/briefing
backend/output/Briefing_{date}.md
```

## Cost Estimate
~₹2–4 per run — cheapest intelligence workflow.

---