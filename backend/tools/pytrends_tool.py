"""pytrends (Google Trends) wrapper for research specialists.

Per the workflow-2 spec, Trend Validator uses Google Trends to:
  - Plot 5-year search volume trajectory for the search_keywords
  - Detect growing/stable/declining markets
  - Find related queries and rising topics

Per the Phase 0b smoke test results (see
`backend/output/phase_0b_smoke_test_2026-06-02.md`), the 'today 7-d'
timeframe is fragile. We default to 'today 3-m' which is more
stable. Callers can override via the `timeframe` arg.

pytrends has a known rate limit (HTTP 429 after a burst of calls).
We add a configurable sleep before the call as a courtesy. Tests
can set `rate_limit_sleep_s=0.0` to skip the sleep.
"""

import json
import time
from typing import Any

from crewai.tools import BaseTool
from pydantic import Field

from backend.utils.logger import get_logger

log = get_logger(__name__)

# Default 3-month window — long enough to smooth weekly noise,
# short enough to be relevant. Per Phase 0b smoke test note:
# 'today 7-d' is fragile; longer timeframes are more stable.
DEFAULT_TIMEFRAME = "today 3-m"


class PytrendsTool(BaseTool):
    """Query Google Trends for a keyword via pytrends.

    Returns interest-over-time average, related queries (top),
    and rising topics. The Trend Validator reads this to decide
    if a market is growing/stable/declining.

    No API key needed (pytrends scrapes public Google Trends).
    Has a known 429 rate limit; we add a small sleep before
    the call (configurable; tests can set it to 0).
    """

    name: str = "PytrendsTool"
    description: str = (
        "Query Google Trends for a keyword. Returns a JSON object "
        "with: `interest_avg` (mean of interest-over-time), "
        "`related_queries_top` (top related search queries), and "
        "`rising_topics` (queries with biggest search increase). "
        "Pass the keyword as the `keyword` argument."
    )

    # Sleep before the HTTP call to avoid 429s. Field is configurable
    # for tests (set to 0 to skip).
    rate_limit_sleep_s: float = Field(default=2.0)

    def _run(
        self,
        keyword: str,
        timeframe: str = DEFAULT_TIMEFRAME,
        **kwargs: Any,
    ) -> str:
        """Fetch Google Trends data for `keyword`.

        Args:
            keyword: Search term. Google Trends treats this as a
                literal string, not a regex. Multi-word queries
                should be a single string ("habit tracker India").
            timeframe: pytrends timeframe string. Defaults to
                'today 3-m' (3-month window). Other valid values:
                'today 1-m', 'today 12-m', 'today 5-y', etc.
                Per Phase 0b smoke test: avoid 'today 7-d'.
            **kwargs: Ignored — kept for BaseTool contract.

        Returns:
            A JSON string with: `interest_avg` (int, mean of
            interest-over-time series), `related_queries_top`
            (list of {query, value}), `rising_topics` (list of
            {query, value}). On failure, returns a JSON object
            with `error` and `hint` keys (the LLM sees the error).
        """
        try:
            from pytrends.request import TrendReq

            # Be polite to Google. Configurable sleep; 0 in tests.
            if self.rate_limit_sleep_s > 0:
                time.sleep(self.rate_limit_sleep_s)

            # India locale + IST (+5:30) — primary market per the
            # project profile (CLAUDE.md "Owner Profile").
            pt = TrendReq(hl="en-IN", tz=330)
            pt.build_payload([keyword], timeframe=timeframe)

            # Interest over time — averaged across the window.
            iot = pt.interest_over_time()
            if not iot.empty and keyword in iot.columns:
                interest_avg = int(iot[keyword].mean())
            else:
                interest_avg = 0

            # Related queries — top + rising frames.
            rq = pt.related_queries()
            payload = rq.get(keyword, {}) if rq else {}
            top_df = payload.get("top")
            rising_df = payload.get("rising")
            top_list = top_df.head(10).to_dict("records") if top_df is not None else []
            rising_list = (
                rising_df.head(10).to_dict("records") if rising_df is not None else []
            )

            log.info(
                "PytrendsTool: keyword=%r timeframe=%s interest_avg=%d "
                "top=%d rising=%d",
                keyword, timeframe, interest_avg, len(top_list), len(rising_list),
            )
            return json.dumps(
                {
                    "keyword": keyword,
                    "timeframe": timeframe,
                    "interest_avg": interest_avg,
                    "related_queries_top": top_list,
                    "rising_topics": rising_list,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            msg = f"pytrends failed for keyword={keyword!r}: {e}"
            log.error(msg, exc_info=True)
            return json.dumps(
                {
                    "keyword": keyword,
                    "error": msg,
                    "hint": "Google Trends may be rate-limiting (HTTP 429). Wait 60s and retry.",
                },
                ensure_ascii=False,
            )
