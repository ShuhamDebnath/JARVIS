# backend/voice/intent.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 5.2 — Keyword-based voice intent parser and workflow router.
#
# Maps a spoken transcript (lowercased, stripped) to one of three CrewAI
# workflows.  If no keyword matches, returns "unknown" so the caller can
# fall back to a graceful TTS apology message.
#
# Extracted subject / category / topic is returned as a plain string so the
# caller can interpolate it into the pending-voice state file or pass it to
# the crew launch shim.
#
# CRITICAL: This module MUST NOT trigger any live LLM runs. It is purely
# parsing + routing logic. Crew execution is deferred to a separate phase.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ── Workflow ID constants ────────────────────────────────────────────────────

WORKFLOW_1 = "workflow_1"   # Research → PRD
WORKFLOW_2 = "workflow_2"   # App Store Intelligence
WORKFLOW_3 = "workflow_3"   # Social Content Engine
WORKFLOW_UNKNOWN = "unknown"


# ── Routing rules ──────────────────────────────────────────────────────────

# Each entry: (set of trigger substrings, workflow_id, field_name_for_extraction)
_WORKFLOW_RULES = [
    (
        {"research", "prd", "market"},
        WORKFLOW_1,
        "subject",
    ),
    (
        {"store", "competitor", "intelligence"},
        WORKFLOW_2,
        "category",
    ),
    (
        {"social", "content", "brief"},
        WORKFLOW_3,
        "topic",
    ),
]


def _strip_and_lower(text: str) -> str:
    """Return a lowercase, whitespace-collapsed copy of `text`."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _extract_payload(text: str, keyword: str) -> str:
    """Pull the meaningful noun phrase after the trigger keyword.

    Example inputs/outputs:
        "research a habit tracker"  → "habit tracker"
        "competitor analysis for twitter" → "twitter"
        "social brief about AI apps" → "AI apps"

    Returns "" if nothing recoverable is found.
    """
    # Split on the keyword then strip common filler words.
    parts = text.split(keyword, 1)
    if len(parts) < 2 or not parts[1].strip():
        return ""
    remainder = parts[1].strip()
    # Drop common leading filler: "a", "an", "the", "for", "about", "on"
    filler = {"a", "an", "the", "for", "about", "on", "to", "into", "in"}
    words = remainder.split()
    if words and words[0].lower() in filler:
        words = words[1:]
    return " ".join(words).strip()


def parse_voice_intent(text: str) -> dict:
    """Parse a voice transcript and return routing instructions.

    Args:
        text: Raw transcribed text from the STT pipeline. Will be
              lowercased and whitespace-normalised before matching.

    Returns:
        A dict with two keys:
            workflow_id  — "workflow_1", "workflow_2", "workflow_3",
                           or "unknown"
            payload      — extracted subject/category/topic string,
                           or "" when unknown

    Example:
        >>> parse_voice_intent("research a habit tracker")
        {"workflow_id": "workflow_1", "payload": "habit tracker"}

        >>> parse_voice_intent("Competitor analysis for Twitter")
        {"workflow_id": "workflow_2", "payload": "Twitter"}

        >>> parse_voice_intent("What time is it")
        {"workflow_id": "unknown", "payload": ""}
    """
    if not text or not isinstance(text, str):
        logger.warning("parse_voice_intent called with empty or non-string input")
        return {"workflow_id": WORKFLOW_UNKNOWN, "payload": ""}

    normalised = _strip_and_lower(text)
    logger.debug("parse_voice_intent input normalised: %r", normalised)

    for keywords, workflow_id, field in _WORKFLOW_RULES:
        for keyword in keywords:
            if keyword in normalised:
                payload = _extract_payload(normalised, keyword)
                logger.info(
                    "Intent matched workflow=%s (%s) keyword=%r payload=%r",
                    workflow_id, field, keyword, payload,
                )
                return {"workflow_id": workflow_id, "payload": payload}

    logger.info("No workflow keyword matched for: %r", normalised)
    return {"workflow_id": WORKFLOW_UNKNOWN, "payload": ""}