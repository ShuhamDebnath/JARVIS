"""Inter-agent contracts for Jarvis crews.

This package holds Pydantic models that define the *shape* of data passed
between agents and between crews. These are not internal state — they
are the public interface between agents. Treat them as immutable: any
change here is a breaking change for every agent that consumes the
output.

Why a separate package?
- Inter-agent contracts are *contracts*, not *schemas*. The directory
  name signals that to anyone reading `import` statements.
- Keeps the strict-typing discipline out of `backend/crews/`, which
  is otherwise YAML-driven and should stay light on Python types.
- Each workflow that crosses an agent boundary gets its own file
  (e.g., `research.py` for research_dept outputs, `prd.py` for
  product_dept outputs). One model per file, one file per contract.
"""
