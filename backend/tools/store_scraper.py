"""App Store + Google Play Store scraper wrappers for research specialists.

Per ADR-0000 + the workflow-2 spec, the following specialists use these:
  - Competitor Mapper: Play Store + App Store top 10 for category
  - Revenue Estimator: App Store top 3 chart positions
  - Gap Finder: Play Store + App Store 1/2-star reviews

We wrap the two npm packages:
  - google-play-scraper (npm) — uses ESM-style CJS with .default indirection
  - app-store-scraper (npm)    — plain CJS, no indirection

Why a subprocess to Node instead of in-process:
    Per ADR-0000 Q10 (grilling session 2): tools reference npm
    libraries via subprocess.run. A single long-lived Node process
    is a Phase 7 optimisation (today we spawn per call — slow but
    isolated, and crash-safe).

The Node bridge script lives at `backend/tools/store_scraper.js`
(shipped alongside this file). It exports a `search()` function
that takes a JSON spec from argv[2] and writes the result JSON to
stdout. The Python wrapper parses the last non-empty stdout line.

⚠️ The google-play-scraper .default quirk (per Phase 0b smoke test):
    ❌ const g = require('google-play-scraper'); g.search({...})
    ✅ const { search } = require('google-play-scraper').default;
    If you edit the bridge, do NOT remove the .default. The
    call will crash with "g.search is not a function".
"""

import json
import subprocess
from pathlib import Path
from typing import Any

from crewai.tools import BaseTool

from backend.utils.logger import get_logger

log = get_logger(__name__)

# Path to the node bridge script. This file ships alongside this
# Python module — Phase 1 single-call mode (Phase 7 swaps to a
# long-lived node process for performance).
_BRIDGE_JS = Path(__file__).resolve().parent / "store_scraper.js"

# Per-call timeout. App Store and Play Store searches should be
# fast (1-3s typical); 30s catches network issues without hanging.
_SUBPROCESS_TIMEOUT_S = 30


def _call_node_bridge(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Spawn Node, run the bridge script with `payload`, parse JSON.

    Args:
        payload: Dict passed as JSON via argv[2]. The bridge
            script's `search()` reads it and dispatches to the
            right npm library.

    Returns:
        The list of app dicts from the bridge script's stdout
            (parsed from the final JSON line).

    Raises:
        RuntimeError: If the bridge script exits non-zero, or if
            its stdout is not parseable JSON, or if it times out.
        FileNotFoundError: If `node` is not on PATH.
    """
    try:
        proc = subprocess.run(
            ["node", str(_BRIDGE_JS), json.dumps(payload)],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_S,
            check=False,   # check returncode manually for a clear error
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "Node.js not found on PATH. Install Node 18+ and ensure "
            "'node' is runnable. On macOS: `brew install node`."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"Node bridge timed out after {_SUBPROCESS_TIMEOUT_S}s "
            f"for payload={payload}. The App/Play store may be slow "
            f"or rate-limiting."
        ) from e

    if proc.returncode != 0:
        raise RuntimeError(
            f"Node bridge failed (exit={proc.returncode}): "
            f"stderr={proc.stderr.strip()}"
        )

    # The bridge script's final line is the JSON result. Earlier
    # lines (if any) are noise from the npm libraries' deprecation
    # warnings — we take the last non-empty line.
    out_lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if not out_lines:
        raise RuntimeError(
            f"Node bridge produced no output. stderr={proc.stderr.strip()}"
        )
    try:
        result = json.loads(out_lines[-1])
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Node bridge output is not valid JSON: {out_lines[-1]!r}. "
            f"stderr={proc.stderr.strip()}"
        ) from e
    return result


class AppStoreScraperTool(BaseTool):
    """Search Apple's App Store via the app-store-scraper npm package.

    Returns top N apps for a search query, with title, app_id,
    score (rating), price, and developer name. Used by Competitor
    Mapper, Revenue Estimator, and Gap Finder.

    No API key needed (app-store-scraper scrapes the public iTunes
    search API).
    """

    name: str = "AppStoreScraperTool"
    description: str = (
        "Search the Apple App Store for apps matching a query. "
        "Pass `query` (search string) and optionally `limit` "
        "(default 10). Returns top apps with title, app_id, "
        "score, price, and developer."
    )

    def _run(self, query: str, limit: int = 10, **kwargs: Any) -> str:
        """Search the App Store for `query`.

        Args:
            query: Search string (e.g. "habit tracker").
            limit: Max apps to return. Default 10.
            **kwargs: Ignored — kept for BaseTool contract.

        Returns:
            A JSON string (array of app dicts) on success; a JSON
            string with `error` and `hint` keys on failure.
        """
        try:
            apps = _call_node_bridge({"store": "apple", "query": query, "limit": limit})
            log.info("AppStoreScraperTool: query=%r limit=%d → %d apps", query, limit, len(apps))
            return json.dumps(apps, ensure_ascii=False)
        except Exception as e:
            msg = f"AppStoreScraperTool failed for query={query!r}: {e}"
            log.error(msg, exc_info=True)
            return json.dumps([{
                "error": msg,
                "hint": "Check that `node` is on PATH and `npm install` was run.",
            }], ensure_ascii=False)


class PlayStoreScraperTool(BaseTool):
    """Search Google Play Store via the google-play-scraper npm package.

    Returns top N apps for a search query, with title, app_id,
    score (rating), installs, developer, and price. Used by
    Competitor Mapper, Revenue Estimator, and Gap Finder.

    No API key needed (scrapes the public Play Store).

    ⚠️ The google-play-scraper v10.x package is ESM-style CJS —
    the bridge script must destructure from `.default` (NOT the
    top level). This is the #1 thing that will trip up anyone
    editing the JS bridge. See `store_scraper.js` for the pattern.
    """

    name: str = "PlayStoreScraperTool"
    description: str = (
        "Search the Google Play Store for apps matching a query. "
        "Pass `query` (search string) and optionally `limit` "
        "(default 10). Returns top apps with title, app_id, "
        "score, installs, developer, and price."
    )

    def _run(self, query: str, limit: int = 10, **kwargs: Any) -> str:
        """Search the Play Store for `query`.

        Args:
            query: Search string (e.g. "habit tracker").
            limit: Max apps to return. Default 10.
            **kwargs: Ignored — kept for BaseTool contract.

        Returns:
            A JSON string (array of app dicts) on success; a JSON
            string with `error` and `hint` keys on failure.
        """
        try:
            apps = _call_node_bridge({"store": "play", "query": query, "limit": limit})
            log.info("PlayStoreScraperTool: query=%r limit=%d → %d apps", query, limit, len(apps))
            return json.dumps(apps, ensure_ascii=False)
        except Exception as e:
            msg = f"PlayStoreScraperTool failed for query={query!r}: {e}"
            log.error(msg, exc_info=True)
            return json.dumps([{
                "error": msg,
                "hint": "Check that `node` is on PATH and `npm install` was run.",
            }], ensure_ascii=False)
