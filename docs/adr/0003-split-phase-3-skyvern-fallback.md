# ADR-0003 — Split Phase 3 into 3a (briefs) and 3b (Skyvern auto-post)

> Date: 2026-06-01 (grilling session 2)
> Resolves: Question 12 from `docs/adr/0001-grilling-session-followups.md`
> Status: Accepted
> Applied: 2026-06-01 — spec edits landed (roadmap.md Phase 0c + Phase 3 split, workflow-3-social-media-engine.md restructured, tools/skyvern_tool.py stub created, tools/__init__.py package marker). See "Punch list — spec edits to apply next session" in `0001-grilling-session-followups.md` for item-level status.

---

## Context

Phase 3 of the build roadmap groups two qualitatively different deliverables under one go/no-go boundary:

1. **Brief generation.** `content_dept_crew` produces platform-specific captions, scripts, and posting plans. Pure LLM work. Zero external install dependency.
2. **Auto-posting.** `automation_dept_crew` uses Skyvern to push briefs to Instagram, Twitter, Reddit, and YouTube. Requires Skyvern; Skyvern on macOS requires Docker; the Python dependency tree is heavy; the package has been historically fragile on Apple Silicon.

If the Skyvern install fails, the obvious workaround (Selenium/Puppeteer) is explicitly forbidden by AI-RULES.md Rule 8. Today the entire Phase 3 is blocked if Skyvern doesn't install.

Roadmap principle 1 is *"working beats complete"*. Phase 3's brief-generation half is the creative work — what to post, when, hashtags, hook angles — and delivers real daily value on its own. The auto-posting half is mechanical: copy text into a posting form, attach a media file. A human can perform that mechanical step in seconds while the LLM half still saves hours of ideation.

Coupling the two deliverables behind one Skyvern install risks one of two failure modes:

- **Mode A:** Skyvern install succeeds, Phase 3 closes cleanly. (Best case.)
- **Mode B:** Skyvern install fails. Phase 3 stalls indefinitely. The brief-generation work — already 90% functional — never ships because it's gated behind an install boundary.

Mode B is the asymmetry this ADR addresses.

---

## Decision

Split Phase 3 into two sub-phases with independent go/no-go boundaries:

### Phase 3a — Briefs working, posting manual

- Goal: trigger once → get platform-specific viral content briefs for Instagram, Twitter, Reddit, YouTube. Developer copy-pastes captions and uploads media by hand.
- Crews involved: `content_dept_crew` only.
- Output: `backend/output/Brief_{topic}_{date}.md` + ntfy.sh notification ("Your brief is ready").
- No Skyvern install required. No Phase 0c install batch needed before this.
- Definition of done: brief generated for all 4 platforms.

### Phase 3b — Skyvern auto-post

- Goal: drop finished file → Skyvern posts it. Upload watcher detects new files in `backend/upload/`, triggers `automation_dept_crew`, posts to Instagram + Twitter at minimum.
- Crews involved: `automation_dept_crew`.
- Prerequisite: Skyvern installs and authenticates on this Mac.
- Phase 0c install batch (Skyvern, pyautogui, instagrapi) moves from "before Phase 3" to "before Phase 3b".
- Definition of done: Skyvern successfully posts to at least one platform unattended.

### Implementation detail — `skyvern_tool.py` during Phase 3a

The tool file exists during Phase 3a as a `BaseTool` stub:

```python
class SkyvernTool(BaseTool):
    name = "SkyvernTool"
    description = "Browser automation for social posting (Skyvern-backed)."

    def _run(self, brief_path: str, **kwargs) -> str:
        raise NotImplementedError(
            f"Skyvern not installed (Phase 3b prerequisite). "
            f"Open the brief at {brief_path} and post manually."
        )
```

`content_dept_crew` never references this tool. `automation_dept_crew` references it and will fail loudly with the explanatory message if invoked in Phase 3a — exactly the signal we want. The Phase 3a CEO flow simply does not invoke `automation_dept_crew`.

---

## Consequences

### Positive

- Workflow 3's creative half ships even if the Skyvern install never succeeds.
- AI-RULES.md Rule 8 stays intact — Skyvern is still the tool of record for auto-posting; we just haven't reached the auto-post phase.
- Clearer go/no-go boundary per sub-phase. Phase 3a closes on "briefs generated"; Phase 3b closes on "automated post lands".
- Removes Skyvern from the critical path for unlocking daily content value.

### Negative

- Two more sub-phases to track in the roadmap (3a, 3b).
- Some readers may conflate "Phase 3 done" with "auto-posting works" — needs explicit communication in roadmap.md and the Workflow 3 spec.
- A separate manual step (copy-paste posting) is added to the daily routine until Phase 3b lands. This is a known trade-off — the creative work is the expensive bottleneck, not the posting.

### Cost

Neutral. No additional LLM spend. Defers Skyvern install effort to a later sub-phase where it can be tackled in isolation.

---

## Cross-references

- `docs/roadmap.md` Phase 3 section — split into 3a and 3b with separate step lists and definitions of done.
- `docs/roadmap.md` Phase 0c (Skyvern install batch) — change trigger from "Before Phase 3 starts" to "Before Phase 3b starts".
- `docs/workflows/workflow-3-social-media-engine.md` — testing checklist needs Phase 3a vs 3b annotations on each item. Brief-generation tests are 3a; "Skyvern posts to at least one platform" is 3b.

---

*End of ADR-0003.*
