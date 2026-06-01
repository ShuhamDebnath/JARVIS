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

# ─────────────────────────────────────────────────────────────────────────────
# Silence upstream DeprecationWarnings that fire on `import crewai` (or any
# transitive dep). See backend/output/followups_2026-06-02.md "Flag 3" for
# the full investigation; the short version:
#
#   - Flag 3a: opentelemetry (via chromadb → crewai) uses the deprecated
#     `.values()` dict-style access on `SelectableGroups`. Python 3.11.15's
#     stdlib `importlib.metadata` flags it. Upstream will fix in a future
#     opentelemetry release.
#   - Flag 3b: crewai 0.86.0 still uses the Pydantic v1 `@validator`
#     decorator in `crewai/tools/base_tool.py:30`. Pydantic 2.x flags it
#     as `PydanticDeprecatedSince20`. crewai 0.95+ migrates to
#     `@field_validator`; bump is blocked on Phase 1 test re-validation
#     per ADR-0002 Q6.
#
# Both are upstream issues, not ours. We silence the noise so the real
# warnings (e.g. dotenv parse errors, missing API keys) stay visible in
# logs. The filters are intentionally narrow (message regex) so we don't
# accidentally silence unrelated deprecations.
# ─────────────────────────────────────────────────────────────────────────────

import warnings

# Flag 3a — opentelemetry's deprecated SelectableGroups.values() access.
# Message is uniquely attributable to opentelemetry's
# `_importlib_metadata.py` shim; no other package emits it.
warnings.filterwarnings(
    "ignore",
    message=r"SelectableGroups dict interface is deprecated.*",
)

# Flag 3b — crewai's Pydantic v1 @validator usage.
# Anchored to the start of the message so we don't catch unrelated
# Pydantic deprecations (e.g. v1-style config classes) that may show up
# from other deps in the future.
warnings.filterwarnings(
    "ignore",
    message=r"^Pydantic V1 style `@validator`.*",
)
