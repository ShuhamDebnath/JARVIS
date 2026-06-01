"""Skyvern tool — BaseTool stub per ADR-0003.

This file exists in Phase 3a for **defense in depth**:
`social_poster` is registered in `agents.yaml` with `tools: [SkyvernTool]`,
but the agent is never invoked in Phase 3a. If a future refactor accidentally
wires `automation_dept_crew` into the Phase 3a flow, the tool raises
`NotImplementedError` with an explanatory message — the developer sees the
error immediately rather than Skyvern silently failing because it never got
installed.

Phase 3b replaces this stub with the real Skyvern-backed implementation
(gated on Phase 0c — the Skyvern install batch — succeeding). See
`docs/roadmap.md` Phase 3b step list and `docs/adr/0003-split-phase-3-skyvern-fallback.md`.

Why a `BaseTool` subclass and not a plain function:
CrewAI agents load tools by class-name string from `agents.yaml` (see the
`tools: [SkyvernTool]` line on `social_poster`). The crew loader imports the
class and instantiates it at agent-build time, then exposes `_run` to the
agent as a tool callable. A plain function would not satisfy the loader
contract, and we want the import to succeed cleanly in Phase 3a even though
nothing actually calls `_run`.
"""

from crewai.tools import BaseTool


class SkyvernTool(BaseTool):
    """Browser automation for social posting (Skyvern-backed).

    In Phase 3a this is a stub — `_run` always raises `NotImplementedError`.
    In Phase 3b this is replaced with the real Skyvern client call. The
    signature (`brief_path: str`) is stable across both phases so the
    `social_posting_task` contract does not change.
    """

    name: str = "SkyvernTool"
    description: str = (
        "Browser automation for social posting (Skyvern-backed). "
        "Phase 3a: raises NotImplementedError. "
        "Phase 3b: opens the target platform, uploads the file, pastes "
        "caption and hashtags from the brief, returns the post URL."
    )

    def _run(self, brief_path: str, **kwargs) -> str:
        """Stub for Phase 3a. Real implementation lands in Phase 3b.

        Args:
            brief_path: Absolute path to the brief Markdown file produced
                by `content_dept_crew` in Phase 3a. The brief contains
                the caption, hashtags, and best-posting-time for each
                platform — Skyvern reads it to populate the post form.

        Returns:
            A post URL or upload confirmation string in Phase 3b.
            In Phase 3a this method never returns — it raises.

        Raises:
            NotImplementedError: Always in Phase 3a, by design (ADR-0003).
        """
        raise NotImplementedError(
            f"Skyvern not installed (Phase 3b prerequisite). "
            f"Open the brief at {brief_path} and post manually."
        )
