"""Obsidian vault sync helper — writes per-run status changes to
`obsidian-vault/runs/{run_id}.md` for human review in Obsidian.

The CEO orchestrator (`backend/crews/jarvis_ceo.py`) calls
`write_run_status()` at every workflow status boundary. Each
call appends a new section to the same file so the full run
timeline is preserved in one Markdown file per run_id.

Why Markdown, not JSON:
    The vault is opened in Obsidian. A timeline of headings is
    readable there in seconds; a JSON blob is not.

Why one file per run_id, not one file per status:
    The developer reviewing the vault wants the full story of one
    run in one place — not 9 files scattered across a flat dir.

This file is in `backend/memory/` next to `chromadb/` (which
CrewAI manages). It is the JARVIS-side long-term-memory sink for
humans; ChromaDB is the LLM-side short-term-memory sink.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from backend.utils.logger import get_logger

log = get_logger(__name__)

# Obsidian vault location. The vault lives at the project root
# (one level above backend/), so this file is at parents[2].
# Tests override `_RUNS_DIR` to a tmp path via monkeypatch.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_VAULT_DIR = _PROJECT_ROOT / "obsidian-vault"
_RUNS_DIR = _VAULT_DIR / "runs"


class RunStatus(str, Enum):
    """The set of status values a workflow run can be in.

    String-valued enum so the values render naturally in the
    Markdown (no `RunStatus.STARTED` quoting) and so the
    downstream JSON state file is human-readable.

    Ordered roughly by lifecycle: started → research →
    scoring → human gate → terminal states.
    """
    STARTED = "started"
    RESEARCH_COMPLETE = "research_complete"
    INTELLIGENCE_COMPLETE = "intelligence_complete"
    SCORING_COMPLETE = "scoring_complete"
    AWAITING_HUMAN = "awaiting_human"
    HUMAN_APPROVED = "human_approved"
    HUMAN_DECLINED = "human_declined"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


def write_run_status(
    run_id: str,
    status: RunStatus,
    *,
    note: str = "",
    meta: Optional[dict] = None,
) -> Path:
    """Append a timestamped status entry to `runs/{run_id}.md`.

    Creates the runs/ directory if missing. The file is one
    Markdown file per run_id — each call appends a new section
    so the full run timeline is preserved in one place.

    Args:
        run_id: The workflow run id (UUID from human_gate).
        status: One of `RunStatus`.
        note: Optional one-line human note.
        meta: Optional dict of structured key/values to include
            in the section.

    Returns:
        The `Path` of the file written.
    """
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = _RUNS_DIR / f"{run_id}.md"
    # First call for this run_id — emit the run-level heading.
    is_first = not path.exists() or path.stat().st_size == 0
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # The whole write is wrapped in try/except OSError so a
    # read-only FS, ENOSPC, or EACCES cannot crash the workflow
    # run. The sync helper is diagnostic, not load-bearing —
    # the cost-guard pattern in backend/utils/cost_guard.py
    # uses the same defensive approach for its post-mortem.
    try:
        with open(path, "a", encoding="utf-8") as f:
            if is_first:
                f.write(f"# Run {run_id}\n\n")
            f.write(f"## {ts} — {status.value}\n\n")
            f.write(f"- **status:** `{status.value}`\n")
            if note:
                f.write(f"- **note:** {note}\n")
            if meta:
                f.write("- **meta:**\n")
                for k, v in meta.items():
                    f.write(f"  - {k}: {v}\n")
            f.write("\n---\n\n")
    except OSError as e:
        log.error(
            "obsidian_sync: failed to write status for run %s (%s): %s. "
            "The workflow run continues; the status is dropped.",
            run_id, status.value, e,
        )
    return path
