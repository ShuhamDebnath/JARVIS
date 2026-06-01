"""Jarvis backend — FastAPI app, crews, tools, utilities.

This file marks `backend/` as a Python package so the app can be started
from the project root with the conventional uvicorn command:

    cd /path/to/jarvis
    source .venv/bin/activate
    uvicorn backend.main:app --reload

Without this `__init__.py`, `backend` would be a namespace package and
absolute imports of the form `from backend.utils import ...` would still
work, but tooling (mypy, IDE, packaging) gets confused. Treating it as a
real package keeps everything consistent with `backend/contracts/` and
`backend/tools/` (both of which are real packages already).
"""
