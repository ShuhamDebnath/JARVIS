# Workflow 6 — Content Pipeline: Topic → Post

> Phase 6 | Department: Content | ~8 min | Human gate: review before post

## What This Workflow Does

You give Jarvis a topic or talking point. It generates ready-to-publish content for all 4 platforms — not just a brief (that is Workflow 3) but the actual finished post copy, caption, and thread — ready for you to review and post.

**Input:** Topic or talking point — example: `"I just shipped offline mode in my Flutter app"`  
**Output:** Finished post copy for YouTube description, Instagram caption, Twitter thread, Reddit post  
**Difference from Workflow 3:** Workflow 3 finds trends and gives you briefs. Workflow 6 takes a topic you already have and writes the full content.

## Agent Hierarchy

```
Jarvis CEO
└── content_dept_crew
        manager_agent: content_director
    ├── Copywriter          (writes the actual content per platform)
    └── Community Angle Agent (adds posting strategy + hashtags)
```

## Pipeline

1. User gives topic via frontend or terminal
2. Content Director receives topic — decides tone and angle per platform
3. Copywriter writes finished content for all 4 platforms simultaneously
4. Community Angle Agent adds hashtags, posting time, cross-post targets
5. Human gate — user reviews all 4 platform outputs
6. User approves → drops media file in `/backend/upload/` if needed → Skyvern posts (Phase 3b)

## Platform Output Formats

**YouTube (description + title):**
```
TITLE: {SEO-optimised title}
DESCRIPTION:
{Hook paragraph — 2 sentences}
{Main content summary — 3–5 bullet points}
{CTA — subscribe / app link}
TAGS: {10 tags}
```

**Instagram (caption):**
```
{Hook line — stops the scroll}
{Story — 3–5 short paragraphs}
{CTA}
.
{30 hashtags — mix of niche and broad}
```

**Twitter thread:**
```
Tweet 1 (hook): {max 240 chars}
Tweet 2–7: {each a standalone point}
Tweet 8 (CTA): {app link or follow}
```

**Reddit post:**
```
SUBREDDIT: {best fit}
TITLE: {community-native title}
BODY: {conversational, adds value, no hard sell}
```

## agents.yaml additions

```yaml
copywriter:
  dept: content_dept
  role: Platform Content Copywriter
  goal: >
    Write finished, publish-ready content for all 4 platforms for topic: {topic}
    YouTube: title + description. Instagram: caption. Twitter: full thread.
    Reddit: title + body.
    Content must be written in the developer's voice — technical but accessible,
    first-person, India-aware. Never generic. Always specific to the topic.
  backstory: >
    You write content that developers actually want to read.
    You know the difference between Instagram voice and Reddit voice.
    You write in first-person as if you are the developer — authentic, not corporate.
  llm: minimax/minimax-m3
  allow_delegation: false
  memory: false
```

## tasks.yaml additions

```yaml
content_writing_task:
  description: >
    Write finished post content for all 4 platforms for this topic: {topic}
    Platform requirements:
    YouTube: SEO title + hook paragraph + 5-bullet summary + CTA + 10 tags
    Instagram: scroll-stopping hook + 3-5 short paragraphs + CTA + 30 hashtags
    Twitter: 8-tweet thread (hook + 6 points + CTA) — each tweet max 240 chars
    Reddit: community-native title + body that adds real value
    Write in first-person as the developer. Specific, not generic.
  expected_output: >
    4 complete platform posts in correct format, clearly labelled by platform.
  agent: copywriter

content_strategy_task:
  description: >
    For the content written for topic: {topic}, add posting strategy:
    - Best posting time per platform in IST
    - Top 3 cross-post communities (Discord, Slack, subreddits)
    - Any India-specific angle to add or cultural note
    - CTA recommendation: what action should this content drive?
  expected_output: >
    Posting strategy added to each platform section — time, communities, CTA.
  agent: community_angle_agent
  context: [content_writing_task]
  human_input: true
```

## Files Involved
```
backend/crews/jarvis_ceo.py    # add run_workflow_6(topic, run_id)
backend/main.py                # add POST /workflow/content
backend/output/Content_{topic}_{date}.md
```

## Cost Estimate
~₹4–8 per run (MiniMax M3 for writing, DeepSeek for strategy).
