"""Long-term and short-term memory sinks for Jarvis.

This package holds the two complementary memory layers:

  - ChromaDB (in `chromadb/`) — managed by CrewAI as the
    short-term, agent-visible memory. CrewAI writes to and
    reads from it; we do not touch it directly.

  - `obsidian_sync.py` — the human-facing long-term memory
    sink. Writes per-run status changes to
    `obsidian-vault/runs/{run_id}.md` for the developer to
    review in Obsidian. Wired into the CEO orchestrator at
    every workflow status boundary (P1.12).

Why two layers:
    ChromaDB is for the LLM (RAG, tool recall, agent context).
    The Obsidian vault is for the human (audit trail, post-mortem
    review, "what did the run do?"). Same data, different audience.
    A failure in one must not cascade into the other — both
    modules are defensive about their own I/O.

Public API (re-exported for clean imports):
    >>> from backend.memory import write_run_status, RunStatus
"""

from backend.memory.obsidian_sync import RunStatus, write_run_status

__all__ = ["RunStatus", "write_run_status"]
