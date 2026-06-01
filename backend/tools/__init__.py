"""Tool wrappers for Jarvis crews.

Each module in this package exposes one or more CrewAI `BaseTool` subclasses.
Tools are referenced by class-name string from `backend/config/agents.yaml`
(e.g. `tools: [SkyvernTool]`); the crew loader resolves the string against
the importable classes in this package.

Phase 0a — only `skyvern_tool.py` is present, and only as the ADR-0003 stub
for Phase 3a defense in depth. Real tool implementations (firecrawl_tool,
reddit_tool, pytrends_tool, store_scraper, vision_tool, etc.) land in the
phases specified in `docs/roadmap.md`.
"""
