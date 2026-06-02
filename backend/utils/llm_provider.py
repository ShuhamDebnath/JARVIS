"""MiniMax custom LLM provider for LiteLLM.

P1.15 (commit b882eb8) re-pointed all 12 agents in
`backend/config/agents.yaml` from the OpenRouter path
(`deepseek/deepseek-chat`) to the direct MiniMax API using the
string `minimax/MiniMax-M3`. The prefix `minimax/` is NOT a
LiteLLM-recognised provider, so every LLM call fails with
`litellm.BadRequestError: LLM Provider NOT provided. Pass in the
LLM provider you are trying to call. You passed
model=minimax/MiniMax-M3` (raised at
`litellm/litellm_core_utils/get_llm_provider_logic.py:398`).

MiniMax exposes an OpenAI-compatible endpoint at
`https://api.minimax.chat/v1` (per user confirmation 2026-06-02,
during P1.15 Action 2). The fix is to translate `minimax/X` →
`openai/X` with the right `api_base` + `api_key` BEFORE LiteLLM's
`get_llm_provider` runs its provider-list check. We do that by
monkey-patching `get_llm_provider` in every module that holds a
local binding to it (the `from X import Y` form creates a local
name that does NOT see later rebindings of `X.Y`).

Why not a full `Router` rewrite?
- `Router` requires a config.yaml + a different call site
  (`router.completion(...)` instead of `litellm.completion(...)`).
  CrewAI is hard-coded to call `litellm.completion` via its
  internal `LLM` class, so swapping call sites is invasive.
- A thin shim is the smallest possible change to the
  `agents.yaml` model string. If we ever migrate CrewAI or
  switch the prefix, the shim is the only file to revisit.

Calling convention:
- Import this module as a side-effect from anywhere that may
  build a CrewAI agent: `from backend.utils import llm_provider`.
  The `register_minimax_provider()` call runs at import time.
- `MINIMAX_API_KEY` must be in env (already required by
  `env_validator.REQUIRED_KEYS`).
- `MINIMAX_BASE_URL` is optional (defaults to
  `https://api.minimax.chat/v1`).
"""
from __future__ import annotations

import importlib
import os
from typing import Any, Optional, Tuple

# Importing the submodule below also imports `litellm` itself
# (Python runs the parent package's `__init__.py` for any
# submodule import). That `__init__.py` is what wires up the
# `get_llm_provider` re-export we patch later in this file, so
# no separate `import litellm` is needed.
import litellm.litellm_core_utils.get_llm_provider_logic as _gpl  # noqa: E402

# The prefix agents.yaml uses. Kept as a constant so a future
# migration to e.g. `minimax_v2/` only changes one line.
_MINIMAX_PREFIX = "minimax/"

# Default base URL for the direct MiniMax API. Overridable via
# the `MINIMAX_BASE_URL` env var (e.g. for a self-hosted MiniMax
# proxy or a regional endpoint in Phase 7+).
_DEFAULT_MINIMAX_BASE_URL = "https://api.minimax.chat/v1"

# Modules inside `litellm` that hold a local binding to the
# original `get_llm_provider` via `from ... import get_llm_provider`.
# Each entry is a fully-qualified module name. We patch each one
# so the shim intercepts the call regardless of which module the
# caller goes through. The set is small and stable across recent
# litellm versions (verified against the version pinned in
# `backend/requirements.txt`); if a future litellm adds a new
# internal consumer, add it here.
_LITELLM_CONSUMER_MODULES = (
    "litellm",
    "litellm.main",
    "litellm.vector_stores.main",
    "litellm.passthrough.main",
    "litellm.videos.main",
    "litellm.files.main",
    "litellm.llms.openai.chat.o_series_transformation",
)


def _resolve_minimax_credentials() -> Tuple[str, str]:
    """Read `MINIMAX_API_KEY` + `MINIMAX_BASE_URL` from env.

    Raises a clear error if `MINIMAX_API_KEY` is missing — better
    than letting the shim silently inject `None` and surfacing as
    a confusing 401 from the MiniMax API. `MINIMAX_BASE_URL` is
    optional and falls back to the public endpoint.
    """
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key or not api_key.strip():
        raise RuntimeError(
            "MINIMAX_API_KEY is not set. Add it to .env (see .env.example "
            "line 22) or export it in your shell. The `minimax/` LLM "
            "prefix cannot route to the MiniMax API without it."
        )
    base_url = os.getenv("MINIMAX_BASE_URL", _DEFAULT_MINIMAX_BASE_URL).strip()
    if not base_url:
        base_url = _DEFAULT_MINIMAX_BASE_URL
    return api_key, base_url


def _patched_get_llm_provider(
    model: str,
    custom_llm_provider: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    litellm_params: Optional[Any] = None,
) -> Tuple[str, str, Optional[str], Optional[str]]:
    """Thin wrapper around `litellm.get_llm_provider`.

    Detects the `minimax/` prefix and translates it to the
    OpenAI-compatible provider with the MiniMax base URL + key.
    Everything else passes through to the upstream function
    untouched, so any other provider in `agents.yaml` continues
    to work (the `deepseek/...` / `claude-...` strings used in
    earlier phases, for example, are unaffected).
    """
    # Fast path — only intercept our own prefix. The string-startswith
    # check is cheaper than re-running the full provider-list check
    # inside `_original_get_llm_provider`.
    if isinstance(model, str) and model.startswith(_MINIMAX_PREFIX):
        resolved_key, resolved_base = _resolve_minimax_credentials()
        # Strip the `minimax/` prefix so the rest of LiteLLM sees a
        # normal `openai/MiniMax-M3` style model string. The OpenAI
        # code path will then send it to `api_base` with `api_key`.
        bare_model = model[len(_MINIMAX_PREFIX):]
        # Caller-supplied api_key / api_base WIN over the env defaults —
        # this matches LiteLLM's own precedence (caller > env) and
        # makes the shim composable with tests that want to override.
        return (
            bare_model,
            "openai",
            api_key or resolved_key,
            api_base or resolved_base,
        )
    return _original_get_llm_provider(
        model=model,
        custom_llm_provider=custom_llm_provider,
        api_base=api_base,
        api_key=api_key,
        litellm_params=litellm_params,
    )


# Save the un-patched function so the wrapper can delegate.
# Done at import time so the patch is in place before any LLM call.
_original_get_llm_provider = _gpl.get_llm_provider


def register_minimax_provider() -> None:
    """Install the `minimax/` → openai-compatible shim.

    Idempotent — calling this twice is a no-op the second time, so
    importing `backend.utils.llm_provider` from multiple entry
    points (main.py, dept_crews.py, run_live_e2e.py) is safe.

    Patches in two places:
      1. `_gpl.get_llm_provider` — the source module attribute, in
         case any caller goes through it directly.
      2. Each known consumer module's local binding (set up via
         `from ... import get_llm_provider`). These local bindings
         do NOT see later rebindings of the source module's
         attribute, so step 1 alone is insufficient.
    """
    if getattr(_patched_get_llm_provider, "_jarvis_minimax_patched", False):
        return

    # Mark the wrapper first so a re-entrant import (e.g. a test
    # that imports llm_provider twice in the same process) is safe.
    _patched_get_llm_provider._jarvis_minimax_patched = True  # type: ignore[attr-defined]

    # 1. Patch the source module.
    _gpl.get_llm_provider = _patched_get_llm_provider

    # 2. Patch every known consumer's local binding. Each
    # `importlib.import_module` resolves the module if it hasn't
    # been imported yet (cheap after the first call) and then we
    # rebind the local name. If a consumer's `get_llm_provider`
    # doesn't point to the original function (e.g. a future
    # litellm moves it), we leave it alone.
    for mod_name in _LITELLM_CONSUMER_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            # Some consumers are optional sub-features (vector
            # stores, passthrough, videos, files) that may not be
            # importable in a slimmed install. Skip silently.
            continue
        if getattr(mod, "get_llm_provider", None) is _original_get_llm_provider:
            # Pyright can't see the runtime attribute set by
            # `from ... import get_llm_provider` in litellm's
            # internal modules, so silence the type warning here.
            mod.get_llm_provider = _patched_get_llm_provider  # type: ignore[attr-defined]


# Eagerly register on import. Every entry point in the project that
# may build an LLM agent imports this module; the import side effect
# guarantees the patch is live before any `Agent(llm=...)` call.
register_minimax_provider()
