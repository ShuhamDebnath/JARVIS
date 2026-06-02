"""Regression tests for the P1.15 `minimax/` LiteLLM custom-provider shim.

Background (see backend/utils/llm_provider.py for the long version):
- commit b882eb8 swapped all 12 agents in agents.yaml to the
  `minimax/MiniMax-M3` model string for the direct MiniMax API.
- LiteLLM's `get_llm_provider` does NOT recognise `minimax/` as a
  known provider prefix and raises `BadRequestError: LLM Provider
  NOT provided`.
- The shim translates `minimax/X` → `(X, "openai", api_key, api_base)`
  and patches the function in every module that holds a local
  binding (so `from ... import get_llm_provider` callers see it too).

These tests pin the shim's contract so a future litellm upgrade or
an accidental reordering of the side-effect import doesn't silently
re-introduce the E2E crash.
"""
from __future__ import annotations

import importlib

import pytest


# Import the shim once at module level. This is the same import the
# production code (main.py, dept_crews.py, run_live_e2e.py) uses, so
# the test exercises the actual side-effect install path.
from backend.utils import llm_provider  # noqa: F401


def test_minimax_prefix_is_translated_to_openai_provider():
    """`minimax/MiniMax-M3` must come back as `(MiniMax-M3, "openai", key, base)`.

    This is the core contract: the model name is stripped of its
    custom prefix, the provider is set to `openai` (LiteLLM's
    OpenAI-compatible code path), and the api_key/api_base are
    populated from the env. If any of these change, every LLM call
    for the 12 Phase 1 agents breaks.
    """
    import litellm.litellm_core_utils.get_llm_provider_logic as gpl

    model, provider, api_key, api_base = gpl.get_llm_provider(
        model="minimax/MiniMax-M3"
    )

    assert model == "MiniMax-M3", (
        f"expected the model name to be stripped of the `minimax/` "
        f"prefix; got {model!r}"
    )
    assert provider == "openai", (
        f"expected the provider to be `openai` (LiteLLM's "
        f"OpenAI-compatible code path); got {provider!r}"
    )
    assert api_base and "minimax.chat" in api_base, (
        f"expected the api_base to point at the MiniMax API; "
        f"got {api_base!r}"
    )
    assert api_key, (
        "expected the api_key to be populated from MINIMAX_API_KEY"
    )


def test_minimax_prefix_works_via_litellm_main_consumer():
    """The patch must reach `litellm.main.get_llm_provider` too.

    `litellm/main.py` does `from ... import get_llm_provider`,
    creating a LOCAL binding that does NOT see later rebindings of
    the source module's attribute. The shim patches this binding
    explicitly — if a future refactor drops it, the next LLM call
    will hit the un-patched original and crash.
    """
    import litellm.main

    model, provider, api_key, api_base = litellm.main.get_llm_provider(
        model="minimax/MiniMax-M2.7"
    )

    assert model == "MiniMax-M2.7"
    assert provider == "openai"
    assert api_key, "api_key must flow through the consumer-module patch"


def test_caller_supplied_api_key_wins_over_env(monkeypatch):
    """A caller passing `api_key=` to `get_llm_provider` must take priority.

    This matches LiteLLM's own precedence (caller > env) and lets
    tests / Phase 7 self-hosted proxies override the default key
    without monkey-patching the env.
    """
    import litellm.litellm_core_utils.get_llm_provider_logic as gpl

    _, _, api_key, _ = gpl.get_llm_provider(
        model="minimax/MiniMax-M3", api_key="caller-override-key"
    )
    assert api_key == "caller-override-key", (
        f"expected caller-supplied api_key to win; got {api_key!r}"
    )


def test_non_minimax_prefix_delegates_to_original():
    """A non-`minimax/` model string must NOT be intercepted by the shim.

    If the shim's `model.startswith(_MINIMAX_PREFIX)` guard ever
    regresses, it could swallow `deepseek/...` or `claude-...`
    strings and break the fallback providers. The string `*` is
    recognised by the original `get_llm_provider` and resolves to
    the `openai` provider, so it's a safe delegate-only check.
    """
    import litellm.litellm_core_utils.get_llm_provider_logic as gpl

    # We don't need the call to succeed; we only need to assert that
    # the shim didn't rewrite the model. `*` is a known original
    # provider that maps to openai in litellm.
    model, provider, _, _ = gpl.get_llm_provider(model="*")
    assert model == "*", (
        f"non-minimax model should pass through untouched; got {model!r}"
    )
    assert provider == "openai", (
        f"original function should still resolve `*` to openai; "
        f"got {provider!r}"
    )


def test_register_minimax_provider_is_idempotent():
    """Calling `register_minimax_provider()` twice must not stack patches.

    Each call should re-patch the same function reference (which is
    a no-op semantically) rather than wrap a wrap — otherwise
    repeated imports would create a chain of delegates and the
    shim's overhead would grow unbounded.
    """
    # Import fresh to count the active patchers. We just need the
    # function references to be identical, not the wrapper.
    gpl_module = importlib.import_module(
        "litellm.litellm_core_utils.get_llm_provider_logic"
    )
    llm_provider.register_minimax_provider()
    llm_provider.register_minimax_provider()
    # The patched function should still be the SAME object — no
    # double-wrap, no re-import dance.
    assert gpl_module.get_llm_provider is llm_provider._patched_get_llm_provider


def test_shim_raises_clear_error_when_api_key_missing(monkeypatch):
    """Missing MINIMAX_API_KEY should produce a helpful error, not a 401.

    Without the explicit check, a missing env var would silently
    inject `None` as the api_key and the MiniMax API would
    eventually return a confusing 401. The shim raises
    RuntimeError with a message that points the user at the
    .env / .env.example line.
    """
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    import litellm.litellm_core_utils.get_llm_provider_logic as gpl

    with pytest.raises(RuntimeError) as exc_info:
        gpl.get_llm_provider(model="minimax/MiniMax-M3")
    assert "MINIMAX_API_KEY" in str(exc_info.value)
    assert ".env" in str(exc_info.value), (
        "error message should tell the user where to set the key"
    )
