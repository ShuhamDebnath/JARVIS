# Workflow 5 — Competitor Deep Teardown

> Version: 1.0  
> Status: Ready to Build — Phase 6  
> Priority: Phase 6 workflow — builds after frontend is live  
> Last Updated: June 2026

---

## What This Workflow Does

You name one specific competitor app. Jarvis does a deep teardown — downloads their screenshots, reads every review, maps their feature set, tracks their update history, and delivers a complete intelligence dossier on that single app.

This is deeper than Workflow 4 (which scans a whole category broadly). Workflow 5 goes deep on one target.

**Input:** App name — example: `"Habitica"` or `"Duolingo"`  
**Output:** Full competitor dossier saved as markdown  
**Time:** ~12 minutes  
**Human gates:** None — report delivered automatically

---

## When to Use This vs Workflow 4

| | Workflow 4 | Workflow 5 |
|---|---|---|
| Scope | Whole category — 10+ apps broad | One app — deep |
| Use case | "What exists in this space?" | "How does this specific app work?" |
| Depth | Complaint themes, gap map | Feature map, update history, revenue model, UX patterns |
| Triggers before | Deciding to research a space | Deciding to compete directly with one app |

---

## Agent Hierarchy for This Workflow

```
Jarvis CEO  (Python orchestrator — backend/crews/jarvis_ceo.py)
│
└── research_dept_crew  (CrewAI Crew, process=Process.hierarchical)
        manager_agent: research_director  (LLM: DeepSeek)
    ├── Competitor Mapper   (extended — goes deeper on one target)
    ├── Gap Finder          (reads ALL reviews for this one app)
    └── Revenue Estimator   (deep revenue model analysis for this one app)
```

Workflow 5 reuses the `research_dept_crew` — only 3 specialists activate, with deeper task configs passed as context. No new crew file needed.

---

## Full Pipeline — Step by Step

### Step 1 — CEO Receives Input
- User types competitor app name
- CEO searches App Store + Play Store to confirm the app exists and get its exact ID
- CEO logs: `"Workflow 5 triggered: {app_name}"`
- CEO activates research_dept_crew with `{"competitor": app_name, "mode": "deep_teardown"}`

### Step 2 — Competitor Mapper (Deep Mode)

**Tools:** app-store-scraper, google-play-scraper, Firecrawl, SerperDev

Builds a complete profile of the single target app:

**App identity:**
- Full app name, developer, company, founding year
- App Store + Play Store links, bundle ID
- Category, subcategory, keywords visible in listing
- Countries available, language support

**Ratings and traction:**
- Current rating (App Store + Play Store separately)
- Total number of ratings — both stores
- Rating over time — is it improving or declining?
- Estimated downloads (from chart position history + review velocity)
- Estimated MRR (from pricing + download estimate)

**Update history:**
- Last 10 version updates — what changed each time
- Update frequency — weekly / monthly / sporadic
- Are they actively maintained or drifting?

**Screenshots and listing analysis:**
- How many screenshots? What do they show?
- What problem does the listing headline promise?
- What social proof is shown (awards, press mentions)?

### Step 3 — Gap Finder (Full Review Mining)

**Tools:** app-store-scraper, google-play-scraper

Reads ALL available reviews for this one app (up to 500 per platform):

- Separates by star rating — full distribution analysis
- Groups complaints into themes — minimum 3 occurrences to count
- Tracks which version each complaint started appearing in
- Identifies "the one thing everyone asks for that doesn't exist"
- Finds praise patterns — what do loyal users love most?
- Identifies churn signals — "I'm switching to X because..."

### Step 4 — Revenue Estimator (Deep Mode)

**Tools:** Firecrawl, SerperDev

Deep revenue model analysis:
- Free vs paid vs freemium — exact model
- Subscription tiers — prices, features at each tier
- India pricing vs global pricing (often very different)
- IAP items if any — what they are, what they cost
- Revenue estimate range — low / mid / high based on download estimate
- AppFollow, Sensor Tower, or similar estimate if publicly available

### Step 5 — Research Director Consolidates

Produces the full competitor dossier:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JARVIS COMPETITOR TEARDOWN
Target: {app_name}
Generated: {date} IST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

APP IDENTITY
Developer: | Category: | Launch year: | Countries: | Languages:

TRACTION
App Store rating: X.X (N reviews) | Play Store rating: X.X (N reviews)
Estimated downloads: LOW / MID / HIGH range
Estimated MRR: ₹X–X range
Rating trend: IMPROVING / STABLE / DECLINING

MAINTENANCE HEALTH
Last update: | Update frequency: | Active? YES/NO
Last 3 updates summary:
  vX.X — [what changed]
  vX.X — [what changed]
  vX.X — [what changed]

FEATURE MAP (what this app does)
Core features:
  - [feature]: [one line description]
Premium features (paid only):
  - [feature]: [one line description]
Notably absent (users ask for these):
  - [missing feature] — [evidence count] requests

REVENUE MODEL
Model: [freemium / subscription / one-time / free]
Tiers:
  Free: [what you get]
  [Tier name] — [price/month]: [what you get]
India pricing: [price] vs Global: [price]
Estimated MRR: ₹[range]

USER SENTIMENT
What loyal users love (from 5-star reviews):
  1. [theme]
  2. [theme]
Top complaints (from 1–2 star reviews):
  1. [complaint] — [N] occurrences — since v[version]
  2. [complaint] — [N] occurrences
  3. [complaint] — [N] occurrences
Churn destination (users switch to):
  - [app name] — reason: [why]

THE SINGLE BIGGEST OPPORTUNITY
If you were to compete with {app_name}, the one thing to do differently:
[2–3 sentences of specific, evidence-based recommendation]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 6 — Output Saved

- Dossier saved to: `backend/output/Competitor_{appname}_{date}.md`
- Obsidian note updated: `obsidian-vault/competitors/{appname}.md`
- Cross-linked to any PRD that mentions this competitor
- Run cost logged

---

## agents.yaml additions for Workflow 5

No new agents needed. Workflow 5 uses existing research_dept specialists with deeper task configs passed at runtime. The `mode: deep_teardown` input in the CEO's `kickoff(inputs={...})` call signals to the task descriptions that they should go deeper on one app rather than broad across many.

Only task additions needed in `tasks.yaml`.

---

## tasks.yaml additions for Workflow 5

```yaml
# ─── Workflow 5 — Competitor Deep Teardown ───
competitor_profile_task:
  description: >
    Build a complete profile of this competitor app: {competitor}
    Find it on both App Store and Play Store. Extract:
    - Full identity: developer, company, launch year, countries, languages
    - Traction: ratings (both stores), total review count, estimated downloads
    - Update history: last 10 versions with what changed in each
    - Listing analysis: screenshots, headline promise, social proof shown
    - Rating trend: is overall rating improving, stable, or declining over time?
  expected_output: >
    Structured app profile with all identity, traction, maintenance, and listing fields.
  agent: competitor_mapper

competitor_review_mining_task:
  description: >
    Read ALL available reviews for {competitor} — up to 500 per platform.
    Group complaints into themes (minimum 3 occurrences to include).
    Track which app version each complaint first appeared in.
    Find the single most-requested missing feature.
    Identify praise patterns from 5-star reviews — what do loyal users love?
    Find churn signals: users mentioning switching to another app and why.
  expected_output: >
    Full review analysis: complaint themes with occurrence count and version,
    top missing feature with evidence count, praise themes, churn destinations.
  agent: gap_finder

competitor_revenue_task:
  description: >
    Analyse the revenue model of {competitor} in detail.
    Find: free vs paid structure, all subscription tiers with exact prices,
    India pricing vs global pricing, any IAP items and their prices.
    Estimate MRR based on download estimate and conversion rate assumptions.
    Check AppFollow, Sensor Tower, or any publicly available revenue estimates.
  expected_output: >
    Full revenue model breakdown with all tiers, India vs global pricing,
    MRR estimate range (low/mid/high).
  agent: revenue_estimator

competitor_dossier_task:
  description: >
    Consolidate all findings into a complete competitor dossier for {competitor}.
    Use the standard Jarvis Competitor Teardown format.
    The final section "THE SINGLE BIGGEST OPPORTUNITY" must be specific —
    a developer should be able to use it to decide exactly what to build differently.
  expected_output: >
    Complete formatted competitor dossier in the standard Jarvis format.
    Minimum 800 words. "The Single Biggest Opportunity" section must be
    specific and evidence-based — not generic advice.
  agent: research_director
  context: [competitor_profile_task, competitor_review_mining_task, competitor_revenue_task]
```

---

## Files Involved

```
backend/crews/jarvis_ceo.py         # add run_workflow_5(competitor, run_id)
backend/main.py                     # add POST /workflow/competitor
backend/output/Competitor_{name}_{date}.md
obsidian-vault/competitors/{appname}.md
```

**No new tool files, no new crew files, no new agent definitions.** Only `tasks.yaml` additions and one new CEO function.

---

## Cost Estimate Per Run

| Model | Calls | Est. tokens | Est. cost |
|-------|-------|-------------|-----------|
| DeepSeek | ~5 calls | ~40,000 tokens | ~₹4–8 |

**Estimated cost per Workflow 5 run: ₹4–8**

---

## Testing Checklist

- [ ] Run with competitor: `"Habitica"`
- [ ] App found on both App Store and Play Store
- [ ] Update history returns at least 5 versions
- [ ] Review mining processes at least 100 reviews
- [ ] At least 3 complaint themes with occurrence counts
- [ ] Revenue model section has pricing for all tiers
- [ ] "Single Biggest Opportunity" section is specific (not generic)
- [ ] Dossier saved to `backend/output/Competitor_Habitica_{date}.md`
- [ ] Obsidian competitor note created/updated
- [ ] Completes in under 12 minutes

---

*End of Workflow 5 Spec v1.0*
