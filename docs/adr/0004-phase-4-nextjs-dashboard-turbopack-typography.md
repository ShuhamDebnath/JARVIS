# ADR-0004 — Phase 4: Next.js Dashboard & Turbopack Typography Fix

> **Status:** Accepted
> **Date:** 2026-06-03
> **Phase:** 4 (Frontend Dashboard)

---

## Context

Phase 4 introduced a Next.js (App Router) frontend to the project, which previously had only a FastAPI backend. Several new architectural decisions arose during implementation.

---

## Decision 1 — Frontend Architecture

**Next.js App Router** is the frontend framework (not pages router). It runs on port 3000 and communicates with the FastAPI backend on port 8000 via a typed fetch client in `frontend/lib/api.ts`.

### Communication pattern

```
Next.js (port 3000) → FastAPI (port 8000)
```

- Backend endpoints are called exclusively through `frontend/lib/api.ts` — no direct `fetch()` calls inside components.
- The API client uses `process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'` as the base URL.
- All HTTP errors are caught and re-thrown as typed `Error` objects with the response body as the message.

### Components built in Phase 4

| Component | File | Purpose |
|-----------|------|---------|
| Dashboard page | `frontend/app/dashboard/page.tsx` | Main grid container |
| Workflow card | `frontend/components/WorkflowCard.tsx` | Trigger + status for each workflow |
| Agent status | `frontend/components/AgentStatus.tsx` | 5-second polling panel for runs |
| Output viewer | `frontend/components/OutputViewer.tsx` | Markdown file viewer with react-markdown |
| Coming soon | `frontend/components/ComingSoon.tsx` | Locked placeholder for unbuilt workflows |
| API client | `frontend/lib/api.ts` | Typed fetch wrapper + `fetchWorkflowStatuses()` + `fetchOutput()` |

---

## Decision 2 — Turbopack Typography Plugin Fix

**Problem:** `@tailwindcss/typography` is a CommonJS package that ships a Tailwind v3 plugin (`src/index.js` using `require('tailwindcss/plugin')`). It does **not** export a v4-compatible CSS `@import` target. When added as a PostCSS plugin via `postcss.config.mjs` in Tailwind v4 (Next.js 16 / Turbopack), it causes:

```
Error: [object Object] is not a PostCSS plugin
```

And when imported as `@import "@tailwindcss/typography" plugin` in `globals.css`, Turbopack resolves it and fails with:

```
CssSyntaxError: tailwindcss: Can't resolve '@tailwindcss/typography'
```

**Solution:** Removed all plugin approaches. The typography styles are replaced with hand-crafted `ReactMarkdown components={}` overrides in `OutputViewer.tsx` that produce identical dark-theme output:

- `h1/h2/h3` → `text-xl/text-lg/text-base`, gray-100
- `p` → `text-gray-300`, `leading-relaxed`
- `strong` → `text-white font-semibold`
- `code` (block) → `bg-gray-900 text-cyan-300 text-xs`, overflow-x-auto
- `ul/ol` → `text-gray-300`, `list-disc`/`list-decimal`
- `blockquote` → `border-l-4 border-gray-600`, italic
- `a` → `text-blue-400 hover:text-blue-300 underline`
- `hr` → `border-gray-700`

**ADR resolution:** Do not add `@tailwindcss/typography` via postcss or CSS `@import` in Tailwind v4 projects. Use component-level overrides via `ReactMarkdown components={}` until `@tailwindcss/typography` ships an ESM/v4-compatible export.

---

## Decision 3 — Backend File Serving

**`GET /output/{filename}`** (`backend/main.py`): Serves markdown files from `backend/output/`.

- Security: filename is resolved via `Path.resolve()` and validated with `is_relative_to(output_dir)` — prevents path traversal attacks (`../` injection).
- Errors: raises `HTTPException(400)` for invalid/traversal filenames, `404` for missing files, `500` for unreadable files.

**`GET /workflows/runs`** (`backend/main.py`): Reads `backend/state/runs.json` for the AgentStatus polling panel. Returns `{}` if the file does not yet exist (empty state on first run).

---

## Consequences

- All Phase 4 files are committed and pushed. The dashboard is functional.
- `frontend/lib/api.ts` is the single integration point — future backend routes are added here only.
- `OutputViewer` component overrides are permanent until `@tailwindcss/typography` ships v4 support.
- Phase 5 (Voice Layer) preparation note: Apple Silicon Macs require `brew install portaudio` before Python audio libraries (faster-whisper, Kokoro, pyaudio) can be installed.

---

*End of ADR-0004*