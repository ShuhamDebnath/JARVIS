# Workflow 3 — Social Trend → Viral Brief → Auto-Post

> Version: 1.0  
> Status: Ready to Build — Phase 3  
> Priority: Third — builds after Workflow 4 (App Store Intelligence)  
> Last Updated: June 2026

---

## What This Workflow Does

You trigger Jarvis manually. It scans trends across Reddit, Google Trends, Twitter, Instagram, and YouTube — then generates platform-specific viral content briefs. You create the content using the brief. You drop it in the upload folder. Skyvern posts it automatically.

**Input:** Manual trigger (schedule added in Phase 7)  
**Output:** Platform-specific content briefs + automated posting after your approval  
**Time:** ~10 minutes to generate briefs  
**Human gates:** Two — brief review before content creation, upload approval before posting

---

## Agent Hierarchy for This Workflow

```
Jarvis CEO
└── Content Director
    ├── Trend Scanner          (monitors all platforms for trending topics)
    ├── Trend Analyser         (ranks trends by relevance and velocity)
    ├── Viral Idea Generator   (creates platform-specific content briefs)
    └── Community Angle Agent  (adds cross-post targets and timing)
└── Automation Director
    └── Social Poster          (Skyvern — handles actual upload and posting)
```

**Flow:**
1. User triggers workflow manually
2. CEO activates Content Director
3. Trend Scanner checks all platforms simultaneously
4. Trend Analyser ranks and selects top 3 per platform
5. Viral Idea Generator creates briefs for all 4 platforms
6. Community Angle Agent adds posting strategy
7. Human gate 1 — user reviews briefs, picks what to create
8. User creates content (20 min instead of 2 hours)
9. User drops finished file into `backend/upload/`
10. Human gate 2 — Jarvis asks posting confirmation
11. Automation Director → Social Poster uploads via Skyvern

---

## Full Pipeline — Step by Step

### Step 1 — Trend Scanner

Scans all platforms simultaneously. Each source has a specific focus:

| Platform | What it scans | Tool |
|----------|--------------|------|
| Reddit | r/androiddev, r/FlutterDev, r/iOSProgramming, r/mobiledev, r/programming, r/india | PRAW |
| Google Trends | Developer keywords set by user (configured once) | pytrends |
| Twitter/X | India-region trending + #mobiledev #flutter #ios #appdev | SerperDev |
| Instagram | Top hashtags: #mobiledev #appdev #flutter #ios #indiatech | SerperDev |
| YouTube | Technology trending in India | SerperDev + Firecrawl |

### Step 2 — Trend Analyser

Ranks every detected trend by 4 factors:

| Factor | What it measures | Weight |
|--------|-----------------|--------|
| Velocity | How fast is it growing right now? | 40% |
| Niche relevance | Is it relevant to mobile dev / Flutter / iOS? | 30% |
| India reach | Does it have India-specific momentum? | 20% |
| Competition density | How saturated is the content on this topic? | 10% |

Selects top 3 trends per platform. Total: up to 12 trend opportunities presented.

### Step 3 — Viral Idea Generator

Creates a platform-specific brief for each selected trend:

#### YouTube Brief Format
```
TREND: {trend_name}
TITLE: {hook title — optimised for search + click}
HOOK (first 30 seconds):
  - Open with: {opening line}
  - Pain point to address: {pain}
  - Promise to viewer: {what they will learn}
TALKING POINTS:
  1. {point}
  2. {point}
  3. {point}
  4. {point}
  5. {point}
THUMBNAIL TEXT: {3–5 words max}
TAGS: {10 relevant tags}
BEST UPLOAD TIME: {IST — based on India audience data}
```

#### Instagram Reels Brief Format
```
TREND: {trend_name}
HOOK LINE (first 3 seconds): {exact line to say or show}
STORY ARC (3 points):
  1. {setup}
  2. {conflict or insight}
  3. {payoff or CTA}
TRENDING AUDIO SUGGESTION: {audio name if applicable}
CAPTION: {150 words max — conversational}
HASHTAGS: {20 relevant hashtags — mix of niche and broad}
BEST POST TIME: {IST}
```

#### Twitter / X Thread Brief Format
```
TREND: {trend_name}
OPENING TWEET: {hook — max 240 chars — must stop the scroll}
SUPPORTING TWEETS:
  Tweet 2: {point}
  Tweet 3: {point}
  Tweet 4: {point}
  Tweet 5: {point}
  Tweet 6: {point}
  Tweet 7: {point}
CLOSING TWEET / CTA: {drive to app or follow}
BEST POST TIME: {IST}
```

#### Reddit Post Brief Format
```
TREND: {trend_name}
BEST SUBREDDIT: {subreddit name + why}
SECONDARY SUBREDDITS: {2 alternatives}
TITLE: {Reddit-native title — not clickbait, adds value}
POST ANGLE: {how to frame for this community — what they care about}
VALUE ADD: {what insight or tool or story to lead with}
CTA: {subtle — Reddit hates hard sells}
```

### Step 4 — Community Angle Agent

Adds posting strategy to each brief:
- Which Discord / Slack / Reddit communities to cross-post
- How to angle the CTA to drive app downloads without being spammy
- Best posting time in IST for each platform
- India-specific cultural note if relevant (festivals, local events, trending topics)

### Step 5 — Human Gate 1 — Brief Review

Jarvis presents all briefs and asks:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JARVIS CONTENT BRIEF READY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Top trends found across platforms:

1. [YouTube] Flutter 3.x performance tips — velocity: HIGH
2. [Instagram] "Built my first app" story arc — velocity: HIGH
3. [Twitter] Indian dev salary comparison thread — velocity: MEDIUM
4. [Reddit] r/FlutterDev — offline-first app tutorial — velocity: HIGH

All 4 briefs saved to: backend/output/ContentBrief_{date}.md

Which do you want to create today? (type platform names or "all")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

User picks which content to create. Jarvis confirms the brief is saved and ready.

### Step 6 — User Creates Content

User uses the brief to create content in their own tool:
- YouTube: record video using the brief structure
- Instagram: record Reel or create carousel using the hook + arc
- Twitter: write thread using the opening tweet + supporting points
- Reddit: write post using the title + angle guidance

**This step is not automated.** The brief cuts creation time from 2 hours to 20 minutes.

### Step 7 — Upload Gate

User drops finished file into `backend/upload/`:
- Video file → Jarvis detects → assumes YouTube or Instagram Reel
- Image(s) → Jarvis detects → assumes Instagram carousel or Twitter image
- Text file → Jarvis detects → assumes Twitter thread or Reddit post

Jarvis asks for confirmation:

```
File detected: reel_flutter_tips.mp4
Post to: Instagram (6pm IST today)?
Caption and hashtags from brief will be used.
Confirm? (yes / no)
```

### Step 8 — Social Poster (Skyvern)

Automation Director activates Social Poster:
- Opens the target platform in Skyvern browser agent
- Uploads the file
- Pastes caption / thread / title from the brief
- Adds hashtags
- Schedules or posts immediately based on user confirmation
- Returns: post URL or confirmation

### Step 9 — Performance Tracking (Phase 7 addition)

48 hours after posting:
- Checks views, likes, comments, shares via platform APIs or scraping
- Feeds engagement data back to Trend Analyser
- Jarvis learns what content performs best for this specific audience over time

---

## agents.yaml additions for Workflow 3

```yaml
content_director:
  role: Content Department Director
  goal: >
    Coordinate trend scanning and content brief generation.
    Activate Trend Scanner, Trend Analyser, Viral Idea Generator,
    and Community Angle Agent.
    Deliver ready-to-use platform briefs the developer can create content from in 20 minutes.
  backstory: >
    You are a content strategist who has grown developer audiences across YouTube,
    Instagram, Twitter, and Reddit. You understand Indian developer culture and
    know what content resonates with this audience.
  llm: minimax/minimax-m3
  allow_delegation: true
  memory: true

trend_scanner:
  role: Social Media Trend Scanner
  goal: >
    Scan Reddit, Google Trends, Twitter, Instagram, and YouTube for
    trending topics relevant to mobile development and Flutter/iOS.
    Focus on India-region signals.
    Return all detected trends with source, velocity estimate, and reach.
  backstory: >
    You monitor the pulse of the developer internet in real time.
    You find trends before they peak — not after.
    You always include India-specific data because that is the primary audience.
  llm: minimax/minimax-m3
  tools: [RedditTool, PytrendsTool, SerperDevTool, FirecrawlTool]
  allow_delegation: false
  memory: true

trend_analyser:
  role: Trend Analysis and Ranking Specialist
  goal: >
    Rank all detected trends by: velocity (40%), niche relevance (30%),
    India reach (20%), competition density (10%).
    Select the top 3 trends per platform.
    Return a ranked list with scores and reasoning.
  backstory: >
    You separate signal from noise. Most trending topics are irrelevant to
    this developer's audience. You filter ruthlessly and rank with evidence.
  llm: minimax/minimax-m3
  allow_delegation: false
  memory: true

viral_idea_generator:
  role: Viral Content Brief Specialist
  goal: >
    Create platform-specific content briefs for the top ranked trends.
    Generate briefs for: YouTube, Instagram Reels, Twitter thread, Reddit post.
    Each brief must be specific enough that the developer can create the content
    in 20 minutes without additional research.
  backstory: >
    You have studied what makes content go viral for developer audiences.
    Your briefs are specific — not generic templates.
    You tailor every brief to the specific trend and the India developer audience.
  llm: minimax/minimax-m3
  allow_delegation: false
  memory: true

community_angle_agent:
  role: Community Distribution Specialist
  goal: >
    Add distribution strategy to each content brief:
    cross-post communities, CTA angles for app downloads,
    best posting times in IST, India-specific cultural notes.
  backstory: >
    You know where developers gather online and what makes them engage.
    You know the unwritten rules of each community — what gets upvoted,
    what gets removed, what drives follows vs unfollows.
  llm: minimax/minimax-m3
  allow_delegation: false
  memory: true

social_poster:
  role: Social Media Posting Automation Agent
  goal: >
    Upload finished content to the specified platform using Skyvern.
    Use caption, hashtags, and timing from the content brief.
    Return post URL or confirmation of successful upload.
  backstory: >
    You are the execution layer. You take finished content and get it live
    on the right platform at the right time with the right metadata.
    You never post without explicit user confirmation.
  llm: deepseek/deepseek-chat
  tools: [SkyvernTool]
  allow_delegation: false
```

---

## tasks.yaml additions for Workflow 3

```yaml
trend_scanning_task:
  description: >
    Scan all platforms for trending topics relevant to mobile dev and Flutter/iOS.
    Platforms: Reddit (r/androiddev, r/FlutterDev, r/iOSProgramming, r/mobiledev,
    r/india), Google Trends, Twitter India, Instagram developer hashtags, YouTube India tech.
    Return all trends with: platform, topic, velocity estimate, reach estimate.
  expected_output: >
    List of all detected trends with platform, topic, velocity, and reach.
  agent: trend_scanner

trend_analysis_task:
  description: >
    Rank all detected trends using this weighting:
    velocity 40%, niche relevance 30%, India reach 20%, competition density 10%.
    Select top 3 per platform.
    Return ranked list with score per factor and total score.
  expected_output: >
    Ranked list of top 3 trends per platform with factor scores and reasoning.
  agent: trend_analyser
  context: [trend_scanning_task]

viral_brief_task:
  description: >
    Create platform-specific content briefs for the top ranked trends.
    For YouTube: title, hook script, 5 talking points, thumbnail text, tags, best time.
    For Instagram: hook line, 3-point story arc, audio suggestion, caption, hashtags, best time.
    For Twitter: opening tweet, 6 supporting tweets, closing CTA, best time.
    For Reddit: best subreddit, title, post angle, value add, subtle CTA.
    All briefs must be specific and actionable — not generic templates.
  expected_output: >
    4 complete platform briefs, each in the standard Jarvis brief format.
  agent: viral_idea_generator
  context: [trend_analysis_task]

community_angle_task:
  description: >
    Add distribution strategy to each brief:
    - Cross-post communities (Discord, Slack, subreddits)
    - CTA angle that drives app downloads without being spammy
    - Best posting time in IST for each platform
    - India-specific cultural note if a festival or local event is relevant
  expected_output: >
    Each brief enhanced with distribution strategy and timing.
  agent: community_angle_agent
  context: [viral_brief_task]
  human_input: true

social_posting_task:
  description: >
    Upload the file from {upload_path} to {platform}.
    Use the caption, hashtags, and timing from the content brief at {brief_path}.
    Only proceed after explicit user confirmation.
    Return: post URL or upload confirmation.
  expected_output: >
    Post URL or confirmation message with platform and timestamp.
  agent: social_poster
  human_input: true
```

---

## Files Involved

```
backend/crews/social_crew.py
backend/tools/trend_tool.py          # wraps pytrends
backend/tools/skyvern_tool.py        # wraps Skyvern for posting
backend/output/ContentBrief_{date}.md
```

---

## Cost Estimate Per Run

| Model | Calls per run | Est. tokens | Est. cost |
|-------|--------------|-------------|-----------|
| MiniMax M3 | ~8 agent calls | ~40,000 tokens | ~₹5–10 |
| DeepSeek | ~2 calls (CEO + poster) | ~5,000 tokens | ~₹1 |

**Estimated cost per Workflow 3 run: ₹6–11**

---

## Testing Checklist

- [ ] Manual trigger runs without errors
- [ ] Trend Scanner returns results from at least 3 platforms
- [ ] Trend Analyser produces a ranked list with scores
- [ ] All 4 platform briefs generated in correct format
- [ ] Brief saved to `backend/output/ContentBrief_{date}.md`
- [ ] Human gate 1 pauses — user can pick platforms
- [ ] Drop a test image into `backend/upload/` → upload watcher detects it
- [ ] Human gate 2 asks for posting confirmation
- [ ] Skyvern successfully posts to at least one platform (Instagram or Twitter)
- [ ] Post URL returned and logged

---

*End of Workflow 3 Spec v1.0*
