# Workflow 3 — Social Trend → Viral Brief → Auto-Post

> Version: 1.1 (split into Phase 3a / 3b per ADR-0003)
> Status: Ready to Build — Phase 3a (briefs), then Phase 3b (Skyvern auto-post)
> Priority: Third — builds after Workflow 2 (Research → PRD)
> Last Updated: June 2026

---

## What This Workflow Does

You trigger Jarvis. It scans trends across Reddit, Google Trends, Twitter, Instagram, and YouTube — then generates platform-specific viral content briefs.

This workflow is **split across two phases** per [ADR-0003](../adr/0003-split-phase-3-skyvern-fallback.md). The split exists because Skyvern (the auto-poster) is the single biggest install risk in the project:

- **Phase 3a — Briefs only (this phase, builds first).** You trigger Jarvis, get the briefs, then create content yourself and post it by hand. No Skyvern install needed. Ships the creative value of the workflow.
- **Phase 3b — Skyvern auto-post (later, gated on Phase 0c).** You drop a finished file into `backend/upload/`, Skyvern posts it. Prerequisite: Phase 0c (Skyvern install batch) has succeeded. If Skyvern install fails, Phase 3a still ships — the developer copy-pastes briefs manually until install is fixed.

**Input:** Manual trigger (schedule added in Phase 7)
**Output:** Platform-specific content briefs (3a) + automated posting (3b, optional)
**Time:** ~10 minutes to generate briefs in 3a
**Human gates (3a):** One — brief review before manual posting
**Human gates (3b):** Two — brief review (inherited from 3a) + upload approval before Skyvern posts

---

## Agent Hierarchy for This Workflow

> Per ADR-0001 Q11 (grilling session 2, 2026-06-01) — Workflow 3 mirrors Workflow 2's per-department-crew structure. Two sub-crews (`content_dept_crew` Phase 3a, `automation_dept_crew` Phase 3b). The CEO-mediated handoff between them is what enforces the "specialists never cross departments" rule from `docs/architecture.md`.

```
Jarvis CEO  (Python orchestrator — backend/crews/jarvis_ceo.py)
│
├── content_dept_crew  (Phase 3a — active)
│   │   manager_agent: content_director  (LLM: MiniMax M3)
│   ├── Trend Scanner          (monitors all platforms for trending topics)
│   ├── Trend Analyser         (ranks trends by relevance and velocity)
│   ├── Viral Idea Generator   (creates platform-specific content briefs)
│   └── Community Angle Agent  (adds cross-post targets and timing)
│
└── automation_dept_crew  (Phase 3b — DEFERRED; see below)
    │   manager_agent: automation_director  (LLM: DeepSeek)
    └── Social Poster      (Skyvern — handles actual upload and posting)
```

> **Phase 3a only invokes `content_dept_crew`.** The `automation_dept_crew` branch is in this spec for reference and for the `social_poster` agent entry that exists in `agents.yaml` from Phase 3a onward (per ADR-0003 Option B — defense in depth). The stub `tools/skyvern_tool.py` will raise `NotImplementedError` if reached, but it should never be reached in Phase 3a. Phase 3b makes the branch live.

---

## Full Pipeline — Phase 3a: Briefs only

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

Brief saved to: backend/output/Brief_{topic}_{YYYY-MM-DD}.md

Which do you want to create today? (type platform names or "all")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

User picks which content to create. Jarvis confirms the brief is saved and ready.

> **Capability note (ADR-0003):** A single trigger may produce 1, 2, 3, or 4 platform briefs depending on the user's reply. The system is *capable* of producing all 4 — that is the Phase 3a Definition of Done, tested as a 4-run matrix (one trigger per platform).

### Step 6 — User Creates Content + Posts Manually

User uses the brief to create content in their own tool:
- YouTube: record video using the brief structure
- Instagram: record Reel or create carousel using the hook + arc
- Twitter: write thread using the opening tweet + supporting points
- Reddit: write post using the title + angle guidance

User then posts manually on the platform. The brief's caption, hashtags, and best-time field are copy-pasted from the brief file. **This step is not automated in Phase 3a.** The brief cuts creation time from 2 hours to 20 minutes; the manual post is the known Phase-3a trade-off documented in ADR-0003.

---

## Full Pipeline — Phase 3b: Skyvern auto-post (deferred)

> **Phase 3b is gated on Phase 0c (Skyvern install) succeeding.** Steps 7–9 below are the post-flight half — they read the brief Phase 3a produced and push the content live. The brief file's `brief_path` and the upload's `upload_path` are the handoff boundary between the two halves. ADR-0003 pins this handoff as `content_dept_crew → CEO threads brief into → automation_dept_crew` (per Q11's CEO-mediated handoff rule).

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

> Phase 3a adds every entry below to `agents.yaml`. The `social_poster` entry is in Phase 3a for defense in depth (ADR-0003 Option B): if any future refactor accidentally wires `automation_dept_crew` into the Phase 3a flow, the `SkyvernTool` stub fires its `NotImplementedError` and the system fails loud rather than silent. `social_poster` is unreachable in Phase 3a — Phase 3b wires it into `automation_dept_crew`.

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
  dept: content
  llm: minimax/minimax-m3
  allow_delegation: true
  memory: false

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
  dept: content
  llm: minimax/minimax-m3
  tools: [RedditTool, PytrendsTool, SerperDevTool, FirecrawlTool]
  allow_delegation: false
  memory: false

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
  dept: content
  llm: minimax/minimax-m3
  allow_delegation: false
  memory: false

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
  dept: content
  llm: minimax/minimax-m3
  allow_delegation: false
  memory: false

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
  dept: content
  llm: minimax/minimax-m3
  allow_delegation: false
  memory: false

social_poster:                                # Phase 3a: present in agents.yaml, never invoked
  role: Social Media Posting Automation Agent  # Phase 3b: wired into automation_dept_crew
  goal: >
    Upload finished content to the specified platform using Skyvern.
    Use caption, hashtags, and timing from the content brief.
    Return post URL or confirmation of successful upload.
  backstory: >
    You are the execution layer. You take finished content and get it live
    on the right platform at the right time with the right metadata.
    You never post without explicit user confirmation.
  dept: content
  llm: deepseek/deepseek-chat
  tools: [SkyvernTool]                        # Stub in Phase 3a; real impl in Phase 3b
  allow_delegation: false
  memory: false
```

---

## tasks.yaml additions for Workflow 3

> All task names are prefixed with their department (`content_` or `automation_`) so they cannot collide when both dept_crews load from the same `tasks.yaml`. (Convention per ADR-0000 Q2.) Tasks do NOT have a `dept:` field — the loader uses the prefix to filter, the same way it filters agents by the `dept:` field.

```yaml
content_trend_scanning_task:
  description: >
    Scan all platforms for trending topics relevant to mobile dev and Flutter/iOS.
    Platforms: Reddit (r/androiddev, r/FlutterDev, r/iOSProgramming, r/mobiledev,
    r/india), Google Trends, Twitter India, Instagram developer hashtags, YouTube India tech.
    Return all trends with: platform, topic, velocity estimate, reach estimate.
  expected_output: >
    List of all detected trends with platform, topic, velocity, and reach.
  agent: trend_scanner

content_trend_analysis_task:
  description: >
    Rank all detected trends using this weighting:
    velocity 40%, niche relevance 30%, India reach 20%, competition density 10%.
    Select top 3 per platform.
    Return ranked list with score per factor and total score.
  expected_output: >
    Ranked list of top 3 trends per platform with factor scores and reasoning.
  agent: trend_analyser
  context: [content_trend_scanning_task]

content_viral_brief_task:
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
  context: [content_trend_analysis_task]

content_community_angle_task:
  description: >
    Add distribution strategy to each brief:
    - Cross-post communities (Discord, Slack, subreddits)
    - CTA angle that drives app downloads without being spammy
    - Best posting time in IST for each platform
    - India-specific cultural note if a festival or local event is relevant
  expected_output: >
    Each brief enhanced with distribution strategy and timing.
  agent: community_angle_agent
  context: [content_viral_brief_task]
  human_input: true

# Phase 3b adds this task. Listed here for visibility; do not enable in Phase 3a.
automation_social_posting_task:
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

### Phase 3a (created this phase)
```
backend/crews/dept_crews.py                  # build_content_dept_crew() factory (lives with other dept factories)
backend/tools/__init__.py                    # package marker (mirrors contracts/)
backend/tools/skyvern_tool.py                # BaseTool stub per ADR-0003
backend/tools/trend_tool.py                  # wraps pytrends
backend/output/Brief_{topic}_{YYYY-MM-DD}.md # workflow output
```

### Phase 3b (created or modified later)
```
backend/tools/skyvern_tool.py                # replaced — real Skyvern-backed impl
backend/crews/dept_crews.py                  # extended — build_automation_dept_crew() factory added
```

---

## Crew Assembly

Per the per-department-crew pattern (ADR-0000 Q2, ADR-0001 Q11), this workflow is **two sub-crews** chained by the Python CEO:

### Phase 3a — `build_content_dept_crew()`

```python
# backend/crews/dept_crews.py — content dept section
from crewai import Crew, Process
from config.loader import load_agents_for, load_tasks_for

def build_content_dept_crew() -> Crew:
    """Build the content_dept_crew for Workflow 3a (briefs only)."""
    agents = load_agents_for("content_dept")
    tasks  = load_tasks_for("content_dept")       # filters by content_ prefix
    return Crew(
        agents=agents,
        tasks=tasks,
        process=Process.hierarchical,
        manager_agent=agents["content_director"],
        # NOTE: no `memory` argument — defaults to False per ADR-0002 Q4
        verbose=True,
    )
```

### Phase 3b — `build_automation_dept_crew()` (added later)

```python
# backend/crews/dept_crews.py — automation dept section
def build_automation_dept_crew() -> Crew:
    """Build the automation_dept_crew for Workflow 3b (Skyvern auto-post)."""
    agents = load_agents_for("automation_dept")
    tasks  = load_tasks_for("automation_dept")    # filters by automation_ prefix
    return Crew(
        agents=agents,
        tasks=tasks,
        process=Process.hierarchical,
        manager_agent=agents["automation_director"],
        # NOTE: no `memory` argument — defaults to False per ADR-0002 Q4
        verbose=True,
    )
```

### CEO-mediated handoff (content → automation)

The two sub-crews never call each other — they are isolated `Crew` instances. The CEO orchestrator threads the brief file path from Phase 3a's `content_dept_crew` output into Phase 3b's `automation_dept_crew` input. This is the same cross-department rule that already separates `research_dept_crew` from `product_dept_crew` in Workflow 2. The handoff boundary is the brief file on disk (`Brief_{topic}_{YYYY-MM-DD}.md`).

```python
# backend/crews/jarvis_ceo.py — Workflow 3 entry points
def run_workflow_3_briefs(topic: str, run_id: str) -> dict:
    """Phase 3a. Returns a brief file path; user posts manually."""
    content_crew = build_content_dept_crew()
    brief = content_crew.kickoff(inputs={"topic": topic})
    return {"status": "completed", "brief_path": brief["file_path"]}

def run_workflow_3_post(upload_path: str, brief_path: str, platform: str, run_id: str) -> dict:
    """Phase 3b. Skyvern posts the uploaded file using the brief's caption/hashtags/timing."""
    automation_crew = build_automation_dept_crew()
    result = automation_crew.kickoff(inputs={
        "upload_path": upload_path,
        "brief_path": brief_path,
        "platform": platform,
    })
    return {"status": "completed", "post_url": result["post_url"]}
```

---

## Cost Estimate Per Run (Phase 3a)

| Model | Calls per run | Est. tokens | Est. cost |
|-------|--------------|-------------|-----------|
| MiniMax M3 | ~2 calls per platform × platforms picked | ~10,000 tokens per platform | ~₹1.50 per platform |
| DeepSeek | 0 calls in Phase 3a (CEO only) | — | — |

**Estimated cost per Workflow 3a run: ₹1.50–11** depending on how many platforms the user selects at Human Gate 1. (All 4 platforms = ~₹6. One platform = ~₹1.50.) The earlier "₹6–11" flat estimate is retired — it implied all-4-platforms-per-run, which the capability DoD contradicts.

**Phase 3b adds:** DeepSeek ~2 calls for the social_poster (~₹1) when Skyvern actually runs.

---

## Testing Checklist

### Phase 3a — Briefs only

Capability matrix test: each platform must be runnable independently and produce a valid brief. Run 4 times, one trigger per platform.

- [ ] Manual trigger runs without errors
- [ ] Trend Scanner returns results from at least 3 platforms
- [ ] Trend Analyser produces a ranked list with scores
- [ ] **Capability — YouTube brief:** trigger with mock topic → assert `Brief_{topic}_{YYYY-MM-DD}.md` contains a populated "YouTube Brief Format" section
- [ ] **Capability — Instagram brief:** trigger with mock topic → assert file contains a populated "Instagram Reels Brief Format" section
- [ ] **Capability — Twitter brief:** trigger with mock topic → assert file contains a populated "Twitter / X Thread Brief Format" section
- [ ] **Capability — Reddit brief:** trigger with mock topic → assert file contains a populated "Reddit Post Brief Format" section
- [ ] **Combined run:** trigger once, user replies "all" at Human Gate 1 → assert all 4 sections present in one file
- [ ] Brief saved to `backend/output/Brief_{topic}_{YYYY-MM-DD}.md`
- [ ] Human gate 1 pauses — user can pick platforms (verified: "all", 1-of-4, 2-of-4, 3-of-4)
- [ ] ntfy.sh "Your brief is ready" notification fires
- [ ] **Defense in depth:** attempt to instantiate `social_poster` agent in Phase 3a (test harness) → assert it builds cleanly (stub `SkyvernTool` imports OK) but invoking the tool raises `NotImplementedError` with the "post manually" message

### Phase 3b — Skyvern auto-post

- [ ] Phase 0c (Skyvern install) has succeeded
- [ ] `tools/skyvern_tool.py` replaced with real implementation
- [ ] Drop a test image into `backend/upload/` → upload watcher detects it
- [ ] Human gate 2 asks for posting confirmation
- [ ] Skyvern successfully posts to at least one platform (Instagram or Twitter)
- [ ] Post URL returned and logged

---

*End of Workflow 3 Spec v1.1 (Phase 3a / 3b split per ADR-0003)*
