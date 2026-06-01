# Workflow 1 — UI Design → Validation → Iteration Loop

> Version: 1.0  
> Status: Ready to Build — Phase 6  
> Priority: Second highest — builds after Workflow 2 is stable  
> Last Updated: June 2026

---

## What This Workflow Does

You upload a screen design document or image. Jarvis analyses it using Claude Vision, returns structured feedback, and loops until you approve the design.

**Input:** Screen design file dropped into `/backend/upload/` — image (PNG/JPG) or markdown screen spec  
**Output:** Structured design feedback report + iteration suggestions saved as markdown  
**Time:** ~20 minutes per screen  
**Human gates:** One per iteration — you review feedback and decide to iterate or approve

---

## Agent Hierarchy for This Workflow

```
Jarvis CEO
└── Design Director
    ├── UI Validator          (Claude Vision — analyses the screen)
    ├── Design Feedback Agent (structures the findings into actionable feedback)
    └── Iteration Suggester   (proposes specific concrete improvements)
```

**Flow:**
1. Upload watcher detects new file in `/backend/upload/`
2. CEO activates Design Director
3. UI Validator analyses the screen with Claude Vision
4. Design Feedback Agent structures findings
5. Iteration Suggester proposes concrete changes
6. Human gate — user reviews and decides: iterate or approve
7. If iterate → user makes changes → re-uploads → loop restarts
8. If approve → final report saved, CEO asks if Workflow 2 PRD screen list should be updated

---

## Full Pipeline — Step by Step

### Step 1 — Upload Detection
- User drops a file into `backend/upload/`
- Upload watcher detects the new file
- CEO logs: `"Workflow 1 triggered: {filename}"`
- CEO validates file type — accepts PNG, JPG, JPEG, PDF, MD
- CEO activates Design Director with file path as context

### Step 2 — UI Validator Analyses the Screen

**LLM used:** Claude (`claude-sonnet-4-5`) — vision capability required

The UI Validator analyses the screen across 6 dimensions:

| Dimension | What it checks |
|-----------|---------------|
| Visual hierarchy | Is the most important element the most prominent? |
| Consistency | Do fonts, colours, spacing follow a system? |
| Usability | Can a new user understand what to do in 5 seconds? |
| Mobile conventions | Does it follow iOS/Android platform guidelines? |
| India context | Is it appropriate for Indian users — language, density, data-light? |
| App Store readiness | Would this screenshot perform well on the App Store listing? |

### Step 3 — Design Feedback Agent Structures Findings

Takes raw UI Validator output and formats it into an actionable report:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JARVIS DESIGN FEEDBACK — {screen_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall: NEEDS ITERATION (or APPROVED)

CRITICAL (fix before proceeding):
1. [issue] — [why it matters] — [what to do]

IMPORTANT (fix in this iteration):
2. [issue] — [why it matters] — [what to do]

MINOR (fix when convenient):
3. [issue] — [why it matters] — [what to do]

STRENGTHS (keep these):
- [what is working well]

Iterate or approve? (iterate / approve)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 4 — Iteration Suggester

For every CRITICAL and IMPORTANT issue, Iteration Suggester adds:
- Specific implementation suggestion (not vague — exact change to make)
- Reference to a known pattern or convention it is based on
- Estimated effort: quick fix / 30 min / half day

### Step 5 — Human Gate

User reads the report and responds:
- `iterate` → user makes changes in their design tool, re-uploads, loop restarts from Step 2
- `approve` → proceed to Step 6

### Step 6 — Output Saved

- Feedback report saved to: `backend/output/Design_{screenname}_{date}_v{n}.md`
- Final approved screen noted in Obsidian: `obsidian-vault/designs/{appname}/{screenname}.md`
- CEO asks: `"Screen approved. Update PRD screen list? (yes / no)"`
- Upload watcher clears the processed file from `/backend/upload/`

---

## agents.yaml additions for Workflow 1

```yaml
design_director:
  role: Design Department Director
  goal: >
    Coordinate UI validation for {filename}.
    Activate UI Validator, Design Feedback Agent, and Iteration Suggester.
    Deliver structured, actionable feedback the developer can act on immediately.
  backstory: >
    You are a design director who has shipped 50+ mobile apps.
    You give honest, specific feedback — never vague.
    You understand Indian users and App Store conversion.
  llm: deepseek/deepseek-chat
  allow_delegation: true
  memory: true

ui_validator:
  role: UI Design Validator
  goal: >
    Analyse the uploaded screen design {filename} across 6 dimensions:
    visual hierarchy, consistency, usability, mobile conventions,
    India context, and App Store readiness.
    Return specific findings per dimension — not general impressions.
  backstory: >
    You are a UI/UX expert trained on thousands of successful mobile apps.
    You use Claude Vision to analyse screens pixel by pixel.
    You understand the difference between what looks good and what converts.
  llm: claude/claude-sonnet-4-5
  tools: [VisionTool]
  allow_delegation: false
  memory: true

design_feedback_agent:
  role: Design Feedback Specialist
  goal: >
    Take the raw UI analysis of {filename} and structure it into
    a prioritised, actionable feedback report.
    Sort issues into: Critical / Important / Minor.
    Always include strengths to preserve.
  backstory: >
    You translate raw design observations into clear developer instructions.
    You prioritise ruthlessly — a developer should always know what to fix first.
    You are constructive, not harsh. You always note what is working.
  llm: deepseek/deepseek-chat
  allow_delegation: false
  memory: true

iteration_suggester:
  role: Design Iteration Specialist
  goal: >
    For every Critical and Important issue in the feedback report for {filename},
    provide a specific, implementable suggestion.
    Reference known patterns where applicable.
    Estimate effort for each change.
  backstory: >
    You bridge the gap between "what is wrong" and "exactly what to do."
    Your suggestions are concrete — a developer should be able to implement
    each one without further clarification.
  llm: deepseek/deepseek-chat
  allow_delegation: false
  memory: true
```

---

## tasks.yaml additions for Workflow 1

```yaml
ui_validation_task:
  description: >
    Analyse this uploaded screen: {filename}
    Examine it across all 6 dimensions:
    visual hierarchy, consistency, usability, mobile conventions,
    India context, App Store readiness.
    Return specific findings per dimension.
    Do not give general impressions — cite specific elements.
  expected_output: >
    6 dimension reports, each with specific findings and element references.
  agent: ui_validator

design_feedback_task:
  description: >
    Take the UI validation findings for {filename} and structure them
    into a prioritised feedback report.
    Sort into Critical / Important / Minor.
    Include a Strengths section.
    Use the standard Jarvis design feedback format.
  expected_output: >
    Formatted feedback report with prioritised issues and strengths.
  agent: design_feedback_agent
  context: [ui_validation_task]

iteration_suggestion_task:
  description: >
    For every Critical and Important issue in the feedback for {filename},
    add a specific implementation suggestion.
    Include: exact change to make, pattern reference if applicable,
    effort estimate (quick fix / 30 min / half day).
  expected_output: >
    Feedback report enhanced with specific suggestions and effort estimates.
  agent: iteration_suggester
  context: [design_feedback_task]
  human_input: true
```

---

## Files Involved

```
backend/crews/design_crew.py
backend/tools/vision_tool.py        # wraps Claude Vision API
backend/output/Design_{name}_{date}_v{n}.md
obsidian-vault/designs/{appname}/{screenname}.md
```

---

## Testing Checklist

- [ ] Drop a PNG screenshot into `backend/upload/`
- [ ] Upload watcher detects file within 5 seconds
- [ ] UI Validator returns findings across all 6 dimensions
- [ ] Feedback report uses correct priority format
- [ ] Human gate pauses — type `iterate` → loop restarts
- [ ] Re-upload triggers fresh analysis (not cached)
- [ ] Type `approve` → report saved to `backend/output/`
- [ ] Obsidian note created for the approved screen
- [ ] Version number increments correctly per iteration (v1, v2, v3)

---

*End of Workflow 1 Spec v1.0*
