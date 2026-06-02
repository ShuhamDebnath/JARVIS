"""Crew assembly for Jarvis workflows.

This package holds the Python files that *assemble* a CrewAI crew from
the YAML agent + task definitions in `backend/config/`. Per CLAUDE.md
(CrewAI Specific rules), YAML is the source of truth for *behaviour* —
the Python files in this directory are thin glue: load YAML, resolve
dotted-path references (e.g., `output_pydantic:
backend.contracts.research.ResearchInterpretation`), build the
crewai.Agent / Task / Crew, return the crew.

One file per workflow (mirrors the `WorkflowCard` granularity in the
frontend). Today:
    - hello_crew.py    — single-agent test crew, Phase 0a
    - (Phase 1+) research_crew.py, prd_crew.py, content_crew.py, ...

If a workflow has an output_pydantic contract, the contract lives in
`backend/contracts/<workflow>.py` per ADR-0002 — never inline in a
crew file. This keeps the YAML + crew + contract split stable.
"""
