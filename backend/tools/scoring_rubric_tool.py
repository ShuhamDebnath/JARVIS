"""Scoring rubric lookup for opportunity scoring (per ADR-0000 Q1).

Per ADR-0000 Q1 (hybrid rubric, 4 hard sub-scores + 1 subjective):
  - Market size          (rubric)
  - Competition density  (rubric, inverted)
  - Revenue potential    (rubric)
  - Trend momentum       (rubric)
  - Build effort/reward  (subjective — LLM judgement)

The 4 hard dimensions are looked up in a fixed rubric table so the
LLM cannot hallucinate the score. The opportunity_scorer agent calls
this tool with a dimension name and a data point; the tool returns
the matching bracket and the score.

The rubric table mirrors `docs/workflows/workflow-2-research-prd.md`
lines 582-621. This file is the single source of truth at runtime —
the spec is documentation; this Python data structure is what the
LLM actually queries.

Why a hardcoded table and not a file:
  - The rubric is small (~30 rows total) — overkill to load from disk.
  - A file would invite the LLM (or a future refactor) to mutate it.
  - Putting the data in Python makes it import-time-checked by
    Python's parser and trivial to unit-test.
  - Update BOTH the spec and this file in lockstep if the rubric
    is re-calibrated after 10+ real runs of Workflow 2.
"""

import json
from typing import Any

from crewai.tools import BaseTool
from pydantic import Field

from backend.utils.logger import get_logger

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# The rubric table — copy of `docs/workflows/workflow-2-research-prd.md`
# lines 582-621. Update BOTH in lockstep if the rubric is re-calibrated
# after 10+ real runs of Workflow 2.
# ─────────────────────────────────────────────────────────────────────────────
RUBRIC: dict[str, dict[str, Any]] = {
    "market_size": {
        "description": "Total addressable subreddit + keyword volume (sum of audience_sizer's numbers).",
        "rubric": {
            1: "Total addressable subreddit + keyword volume < 10,000",
            3: "10,000 – 100,000",
            5: "100,000 – 500,000",
            7: "500,000 – 2,000,000",
            10: "> 2,000,000",
        },
    },
    "competition_density": {
        "description": "Number of apps with rating >= 4.0 in the category (from competitor_mapper). Inverted: fewer = better score.",
        "invert": True,   # fewer apps = higher score
        "rubric": {
            10: "0–2 apps with rating >= 4.0 in category",
            7:  "3–5 apps with rating >= 4.0",
            4:  "6–10 apps with rating >= 4.0",
            1:  "10+ apps with rating >= 4.0",
        },
    },
    "revenue_potential": {
        "description": "Top-app MRR and monetisation model clarity (from revenue_estimator).",
        "rubric": {
            1: "No monetisation model exists in the category",
            3: "Ads only — eCPM < $1",
            5: "Freemium present — top app MRR < $5k",
            7: "Top app MRR $5k–$50k, subscription model proven",
            10: "Top app MRR > $50k, multiple proven monetisation models",
        },
    },
    "trend_momentum": {
        "description": "pytrends slope + Reddit growth (from trend_validator).",
        "rubric": {
            1:  "pytrends 12-month slope negative, Reddit activity flat",
            4:  "pytrends flat, Reddit activity growing",
            7:  "pytrends positive slope, Reddit growth > 20% YoY",
            10: "pytrends steep positive slope, Reddit growth > 50% YoY",
        },
    },
    "build_effort_vs_reward": {
        "description": "LLM judgement on the feature list (from gap_finder). SUBJECTIVE — no rubric.",
        "subjective": True,
        "rubric": {
            1:  "MVP requires ML, real-time infra, payments, > 6 months solo",
            4:  "MVP requires 1–2 hard integrations (auth, payments), 3–4 months",
            7:  "MVP is mostly CRUD + polish, 1–2 months",
            10: "MVP is a weekend build, near-zero risk",
        },
    },
}

# Default go/no-go threshold (per workflow-2 spec, 35/50).
# Logged at the top of every scoring report per the spec.
DEFAULT_THRESHOLD = 35


class ScoringRubricTool(BaseTool):
    """Look up a score in the fixed opportunity-scoring rubric.

    Used by the `opportunity_scorer` agent. Pass a `dimension` and
    optionally a `data_point`; the tool returns the rubric row(s)
    for that dimension so the LLM can pick the right bracket.

    This tool is read-only — it never makes network calls or
    reads files. Pure data lookup.
    """

    name: str = "ScoringRubricTool"
    description: str = (
        "Look up the scoring rubric for one of the 5 opportunity-score "
        "dimensions (market_size, competition_density, revenue_potential, "
        "trend_momentum, build_effort_vs_reward). Pass `dimension` to "
        "get the full rubric rows for that dimension, or pass both "
        "`dimension` and `data_point` to get the closest matching bracket."
    )

    rubric: dict[str, Any] = Field(default_factory=lambda: RUBRIC)
    default_threshold: int = DEFAULT_THRESHOLD

    def _run(
        self,
        dimension: str,
        data_point: str = "",
        **kwargs: Any,
    ) -> str:
        """Return the rubric row(s) for `dimension`.

        Args:
            dimension: One of: market_size, competition_density,
                revenue_potential, trend_momentum, build_effort_vs_reward.
            data_point: Optional human-readable description of the
                measured value (e.g. "subreddit size = 47,000").
                If provided, the tool echoes it in the response so
                the LLM can pick the matching bracket. The LLM does
                the final scoring — this tool just provides the data.
            **kwargs: Ignored — kept for BaseTool contract.

        Returns:
            A JSON string with: `dimension`, `description`, `rubric`
            (dict of score → text), and `default_threshold` (35).
            For inverted / subjective dimensions, also includes
            `invert: true` or `subjective: true` flags so the LLM
            knows.

        Notes:
            - The competition_density dimension is inverted: fewer
              strong competitors = higher score. The tool flags this
              with `invert: true` in the response.
            - build_effort_vs_reward is `subjective: true` — the LLM
              makes the call; the rubric is for reference only.
        """
        if dimension not in self.rubric:
            return json.dumps({
                "error": f"Unknown dimension {dimension!r}. "
                         f"Valid: {sorted(self.rubric.keys())}",
            })

        entry = self.rubric[dimension]
        result: dict[str, Any] = {
            "dimension": dimension,
            "description": entry["description"],
            "rubric": {str(k): v for k, v in entry["rubric"].items()},
            "default_threshold": self.default_threshold,
        }
        if entry.get("invert"):
            result["invert"] = True
            result["note"] = "INVERTED: fewer apps = higher score"
        if entry.get("subjective"):
            result["subjective"] = True
            result["note"] = "SUBJECTIVE: LLM judgement, not a hard rubric"
        if data_point:
            result["data_point"] = data_point
            result["hint"] = (
                "Compare your data_point to the rubric rows above and "
                "pick the matching score. For inverted dimensions, "
                "fewer apps = higher score."
            )

        log.info(
            "ScoringRubricTool: dimension=%r data_point=%r → %d rows",
            dimension, data_point, len(entry["rubric"]),
        )
        return json.dumps(result, ensure_ascii=False)
