"""Firecrawl API wrapper — Phase 1 tool for research specialists.

Per ADR-0000 + the workflow-2 spec, the Revenue Estimator, Gap
Finder, and Audience Sizer use Firecrawl to fetch web pages and
extract markdown. This tool wraps the Firecrawl Python SDK.

Per CLAUDE.md "How to Add a New Tool":
  1. Create this file (✅ Phase 1 P1.7)
  2. Wrap the tool as a CrewAI `BaseTool` subclass (✅ below)
  3. Add the tool name to the relevant agent's `tools:` list
     in agents.yaml (✅ — see FirecrawlTool references on
     revenue_estimator, gap_finder, audience_sizer)
  4. Test the tool independently before adding to a crew
     (smoke test in Phase 0b did not exercise Firecrawl — needs
     FIRECRAWL_API_KEY. Phase 1 e2e P1.15 will smoke it for real.)
  5. Document what the tool does and what API key it needs
     (✅ — this docstring + .env.example)
"""

import os
from typing import Any

from crewai.tools import BaseTool
from pydantic import Field

from backend.utils.logger import get_logger

log = get_logger(__name__)


class FirecrawlTool(BaseTool):
    """Scrape a web page to markdown via the Firecrawl API.

    Returns the page content as markdown text, suitable for an LLM
    to summarise. Used by Revenue Estimator, Gap Finder, and
    Audience Sizer to fetch pricing pages, app landing pages, and
    market-size articles.

    Requires:
        FIRECRAWL_API_KEY in .env (loaded by python-dotenv at
        backend startup). If the key is missing, the tool returns
        a clear error string instead of crashing — per CLAUDE.md
        "Error Handling" rule: "do not crash the crew".
    """

    name: str = "FirecrawlTool"
    description: str = (
        "Fetch a web page and return its content as clean markdown. "
        "Use for pricing pages, app landing pages, and market-size "
        "articles. Pass a single URL as the `url` argument."
    )

    api_key: str = Field(default_factory=lambda: os.getenv("FIRECRAWL_API_KEY", ""))

    def _run(self, url: str, **kwargs: Any) -> str:
        """Scrape `url` to markdown.

        Args:
            url: Absolute HTTP(S) URL of the page to scrape.
            **kwargs: Ignored — kept for BaseTool contract.

        Returns:
            The page content as markdown text, or a clear error
            string if Firecrawl fails / API key is missing.

        Notes:
            Per CLAUDE.md "Error Handling": on any failure, log
            at ERROR level and return a graceful fallback string.
            The crew does not crash — the specialist agent sees
            the error message and can decide to use a different
            source.
        """
        if not self.api_key:
            msg = (
                "Firecrawl unavailable. Set FIRECRAWL_API_KEY in "
                ".env and restart the backend, then try again."
            )
            log.error("FirecrawlTool: %s (url=%s)", msg, url)
            return msg

        try:
            # Imported lazily so a missing key does not block the
            # import chain (test envs without FIRECRAWL_API_KEY
            # can still import this module).
            from firecrawl import FirecrawlApp

            app = FirecrawlApp(api_key=self.api_key)
            result = app.scrape(url=url, formats=["markdown"])
            # Newer firecrawl-py returns an object with a `.markdown`
            # attr; older versions return a dict with a "markdown"
            # key. Handle both.
            if hasattr(result, "markdown"):
                md = result.markdown or ""
            elif isinstance(result, dict):
                md = (
                    result.get("markdown")
                    or result.get("data", {}).get("markdown", "")
                )
            else:
                md = str(result)
            log.info("FirecrawlTool: scraped %d chars from %s", len(md), url)
            return md
        except Exception as e:
            msg = f"Firecrawl failed for {url}: {e}"
            log.error(msg, exc_info=True)
            return (
                f"Firecrawl unavailable. Check FIRECRAWL_API_KEY in "
                f".env or try again. (Underlying error: {type(e).__name__}: {e})"
            )
