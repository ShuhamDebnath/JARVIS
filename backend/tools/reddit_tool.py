"""PRAW (Python Reddit API Wrapper) tool for research specialists.

Per the workflow-2 spec:
  - Pain Point Hunter uses PRAW to find complaint threads
  - Audience Sizer uses PRAW to size subreddits
  - Trend Validator uses PRAW to check subreddit growth
  - Gap Finder uses PRAW to find feature-request threads

This tool exposes one method: search a subreddit for posts matching
a query, returning the top N results with their text + metadata.

Per ADR-0000 Q5 + the workflow-2 spec, the research_interpreter
LLM may include the `r/` prefix in subreddit names ("r/getdisciplined").
The `_run` method sanitises that — strips `r/` from the start of
the subreddit name before passing to PRAW.

Requires (in .env):
  - REDDIT_CLIENT_ID       (from reddit.com/prefs/apps — "script" app)
  - REDDIT_CLIENT_SECRET   (same)
  - REDDIT_USER_AGENT      (any string, e.g. "jarvis/1.0")
"""

import json
import os
from typing import Any

from crewai.tools import BaseTool
from pydantic import Field

from backend.utils.logger import get_logger

log = get_logger(__name__)


class RedditTool(BaseTool):
    """Search a subreddit for posts matching a query, via PRAW.

    Returns the top N posts (default 10) with title, body, score,
    URL, and the comment count. Used by 4 of the 6 research
    specialists — see workflow-2 spec for details.

    Requires:
        REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
        in .env. Without them, the tool returns a clear error
        JSON (per CLAUDE.md "Error Handling").
    """

    name: str = "RedditTool"
    description: str = (
        "Search a subreddit for posts matching a query. Pass "
        "`subreddit` (name, may include r/ prefix) and `query` "
        "(search string). Returns top posts with title, body, "
        "score, URL, and comment count."
    )

    # Env-loaded at instance construction time. default_factory is
    # used (not a class-level literal) so the env var is read fresh
    # each time a tool is built — important because dept_crews.py
    # builds a fresh tool per crew per run.
    client_id: str = Field(default_factory=lambda: os.getenv("REDDIT_CLIENT_ID", ""))
    client_secret: str = Field(default_factory=lambda: os.getenv("REDDIT_CLIENT_SECRET", ""))
    user_agent: str = Field(default_factory=lambda: os.getenv("REDDIT_USER_AGENT", "jarvis/1.0"))

    def _run(
        self,
        subreddit: str,
        query: str,
        limit: int = 10,
        **kwargs: Any,
    ) -> str:
        """Search a subreddit and return top posts as a JSON string.

        Args:
            subreddit: Subreddit name, with or without `r/` prefix.
                Sanitised: leading `r/` and `/r/` are stripped before
                the PRAW call (per workflow-2 spec — research_interpreter
                LLM may include the prefix).
            query: Search string.
            limit: Max posts to return. Default 10 per workflow-2 spec.
            **kwargs: Ignored — kept for BaseTool contract.

        Returns:
            A JSON string (a JSON array of post dicts) — string
            rather than list because CrewAI serialises tool outputs
            to the LLM as text. Each post dict has:
              - title: str
              - body: str (selftext, may be empty for link posts)
              - score: int (upvotes minus downvotes)
              - url: str
              - num_comments: int
              - created_utc: float (Unix epoch)
            On any failure, returns a JSON error object so the LLM
            can see the error and decide what to do.
        """
        import praw

        # Sanitise r/ prefix (workflow-2 spec line 117 — research_interpreter
        # LLM may include it; PRAW wants the bare name).
        sub_name = subreddit.strip()
        if sub_name.startswith("/r/"):
            sub_name = sub_name[3:]
        elif sub_name.startswith("r/"):
            sub_name = sub_name[2:]

        if not self.client_id or not self.client_secret:
            msg = (
                "RedditTool unavailable. Set REDDIT_CLIENT_ID and "
                "REDDIT_CLIENT_SECRET in .env (free at reddit.com/prefs/apps) "
                "and restart the backend."
            )
            log.error("RedditTool: %s", msg)
            return json.dumps([{"error": msg}], ensure_ascii=False)

        try:
            reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
            sub = reddit.subreddit(sub_name)
            posts = []
            for post in sub.search(query, limit=limit, sort="relevance"):
                posts.append({
                    "title": post.title,
                    "body": post.selftext or "",
                    "score": post.score,
                    "url": post.url,
                    "num_comments": post.num_comments,
                    "created_utc": post.created_utc,
                })
            log.info(
                "RedditTool: r/%s q=%r → %d posts", sub_name, query, len(posts)
            )
            return json.dumps(posts, ensure_ascii=False)
        except Exception as e:
            msg = f"Reddit search failed for r/{sub_name} q={query!r}: {e}"
            log.error(msg, exc_info=True)
            return json.dumps(
                [{
                    "error": msg,
                    "hint": "Check REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET in .env.",
                }],
                ensure_ascii=False,
            )
