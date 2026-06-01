# backend/utils/logger.py
# ─────────────────────────────────────────────────────────────────────────────
# Shared logging for Jarvis backend.
#
# Per CLAUDE.md "Logging" section: use this module, never `print()`, in
# production code. The configured logger writes to BOTH:
#   1. stdout — for live `uvicorn` / `tail -f` visibility
#   2. backend/logs/jarvis.log — persistent record (auto-created on import)
#
# Usage in any backend module:
#
#     from utils.logger import get_logger
#     logger = get_logger(__name__)
#     logger.info("Crew started")
#     logger.error("Firecrawl failed", exc_info=True)
#
# Why a helper instead of `logging.getLogger(__name__)` directly?
# - Ensures every caller picks up the same handler set (file + stdout)
#   without each module re-calling `basicConfig` (which is a no-op after
#   the first call, so subsequent modules would lose the file handler).
# - Makes intent explicit: "I want a Jarvis logger," not "any logger."
# ─────────────────────────────────────────────────────────────────────────────

import logging
import sys
from pathlib import Path

# backend/utils/logger.py → backend/logs/ (one level up, then into logs/)
_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_FILE = _LOG_DIR / "jarvis.log"

# Format: timestamp | level (padded) | logger name | message
# Example: 2026-06-02 01:25:14 | INFO    | backend.main | Jarvis backend starting up ...
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _configure_root_logger() -> None:
    """Wire the root logger exactly once per process.

    `force=True` lets us override any earlier `basicConfig` call (e.g. from
    pytest, uvicorn, or crewai) so the file handler is always attached.
    Idempotent — re-calling this function is safe.
    """
    # Make sure the logs directory exists before opening the file handler,
    # otherwise the first import in a fresh checkout crashes on FileNotFound.
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
        handlers=[
            # Append-mode file: we keep history across restarts.
            logging.FileHandler(_LOG_FILE, mode="a", encoding="utf-8"),
            # stdout: live tail in the dev terminal.
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


# Run configuration at import time so every `get_logger` call gets a ready
# logger. This is cheap (one FileHandler open) and matches Python convention
# for library-style log setup.
_configure_root_logger()


def get_logger(name: str) -> logging.Logger:
    """Return a named logger wired to the Jarvis log file + stdout.

    Args:
        name: Usually `__name__` from the calling module. This becomes the
            `%(name)s` segment in the log format and is what you'll grep
            for when debugging one component.

    Returns:
        A `logging.Logger` ready to call `.info()`, `.warning()`, `.error()`,
        `.critical()`, `.exception()` on. The exception methods auto-capture
        the traceback — prefer them over `.error(..., exc_info=True)`.
    """
    return logging.getLogger(name)
