
# Workflow 9 — App Store Listing Optimiser

> Phase 6 | Department: Product | ~15 min | Human gate: review new copy before replacing

## What This Workflow Does

You name one of your published apps. Jarvis analyses your current App Store listing, benchmarks it against the top 10 competitors' listings, and rewrites your title, subtitle, description, and keyword field to maximise discoverability and conversion.

**Input:** App name (must be your published app)  
**Output:** Optimised ASO copy — title, subtitle, description, keyword field — ready to paste into App Store Connect  
**Time:** ~15 minutes  
**Human gate:** Always — you review the new copy before applying it

## Agent Hierarchy

```
Jarvis CEO
└── product_dept_crew
        manager_agent: product_director
    └── App Store Optimiser  (single specialist — ASO focused)
```

## Pipeline

1. User names their app
2. App Store Optimiser fetches the current listing via app-store-scraper
3. Fetches top 10 competitor listings in the same category
4. Analyses keyword density, title patterns, description structure across all 11 apps
5. Identifies keyword gaps — high-volume keywords used by competitors but missing from your listing
6. Rewrites all 4 ASO fields using the gap analysis
7. Human gate — presents current vs new copy side by side, asks for approval
8. On approval — outputs the new copy as a ready-to-paste text file

## ASO Fields Optimised

| Field | Limit | Strategy |
|-------|-------|----------|
| Title | 30 chars | Primary keyword + brand name |
| Subtitle | 30 chars | Secondary keyword + value prop |
| Description | 4000 chars | Keyword-rich, benefit-led, 3-section structure |
| Keyword field | 100 chars | Non-redundant keywords not already in title/subtitle |

## Output Format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JARVIS ASO OPTIMISER
App: {your_app}  |  Generated: {date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KEYWORD GAP ANALYSIS
Keywords top competitors use that your listing misses:
  - [keyword]: [monthly search volume estimate] — missing from your listing
  - [keyword]: [volume] — in your description but not title/keywords

CURRENT vs OPTIMISED

TITLE
Current:   {current title}
Optimised: {new title}
Reason:    [why this change — which keyword added/moved]

SUBTITLE
Current:   {current subtitle}
Optimised: {new subtitle}
Reason:    [why]

DESCRIPTION (first 160 chars — visible without expanding)
Current:   {current opening}
Optimised: {new opening}

FULL DESCRIPTION (optimised):
{full 4000 char description}

KEYWORD FIELD (100 chars max)
Current:   {current keywords}
Optimised: {new keywords}
Reason:    [what changed and why]

APPLY THESE CHANGES? (approve / reject)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## agents.yaml — app_store_optimiser already defined in architecture

```yaml
app_store_optimiser:
  dept: product_dept
  role: App Store Optimisation Specialist
  goal: >
    Optimise the App Store listing for: {your_app}
    Analyse the current listing and top 10 competitor listings.
    Identify keyword gaps — high-volume keywords competitors use that are missing.
    Rewrite title, subtitle, description, and keyword field using the gap analysis.
    Present current vs optimised side by side.
  backstory: >
    You are an ASO specialist who has optimised hundreds of App Store listings.
    You know that the title carries 5x the keyword weight of the description.
    You write descriptions that rank AND convert — not just keyword-stuffed text.
    You always cite which competitors use which keywords as evidence for your choices.
  llm: deepseek/deepseek-chat
  tools: [AppStoreScraperTool, SerperDevTool]
  allow_delegation: false
  memory: false
```

## tasks.yaml additions

```yaml
aso_analysis_task:
  description: >
    Analyse the App Store listing for: {your_app}
    Step 1: Fetch the current listing — title, subtitle, description, keywords (if visible).
    Step 2: Fetch the top 10 competitor listings in the same category.
    Step 3: Map keyword density across all 11 listings.
    Step 4: Identify gaps — high-frequency keywords competitors use that {your_app} misses.
    Step 5: Note which competitors appear in top 10 search results for gap keywords.
  expected_output: >
    Current listing copy, competitor keyword map, gap analysis list with
    estimated search volume per gap keyword.
  agent: app_store_optimiser

aso_rewrite_task:
  description: >
    Rewrite the App Store listing for: {your_app} using the gap analysis.
    Constraints:
    - Title: max 30 chars — must include primary gap keyword + brand
    - Subtitle: max 30 chars — secondary keyword + clear value prop
    - Description: max 4000 chars — benefit-led opening 160 chars, 3-section structure
    - Keyword field: max 100 chars — no redundancy with title/subtitle
    Present in the standard Jarvis ASO format with current vs optimised side by side.
    Explain every change with a one-line reason citing competitor evidence.
  expected_output: >
    Full ASO optimisation report in standard format.
    All 4 fields present with current, optimised, and reason.
  agent: app_store_optimiser
  context: [aso_analysis_task]
  human_input: true
```

## Files Involved
```
backend/crews/jarvis_ceo.py    # add run_workflow_9(your_app, run_id)
backend/main.py                # add POST /workflow/aso
backend/output/ASO_{appname}_{date}.md
obsidian-vault/aso/{appname}_{date}.md
```

## Cost Estimate
~₹6–12 per run (longer context — full competitor descriptions analysed).

---