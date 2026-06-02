"""Tests for `backend/memory/obsidian_sync.py` — the long-term memory
sink that mirrors every workflow status change to
`obsidian-vault/runs/{run_id}.md` for human review in Obsidian.

What this file covers (P1.12):

  1. First call creates the runs/ directory and a per-run Markdown file.
  2. Subsequent calls APPEND to the same file (one file per run_id, full
     timeline preserved).
  3. File content is human-readable Markdown with the run_id, a
     timestamp, the status, and any caller-supplied note/meta.
  4. `RunStatus` is a string enum so the values render naturally in
     the markdown (no quoting needed).
  5. Disk failures (OSError) are caught, logged, and swallowed —
     the sync helper must never crash a workflow run.

The test pattern mirrors `test_human_gate.py` — `tmp_path` +
`monkeypatch` to redirect the runs dir into the test sandbox so the
real `obsidian-vault/runs/` is never touched. The
`tmp_state_dir` fixture in conftest is for `human_gate.STATE_FILE`;
this fixture is the analogous redirect for `obsidian_sync._RUNS_DIR`.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Shared fixture: redirect the runs dir to a tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_runs_dir(tmp_path, monkeypatch):
    """Override `obsidian_sync._RUNS_DIR` to a tmp path.

    The module uses a module-level constant for the runs dir, just
    like `human_gate.STATE_DIR`. Redirecting it in the test keeps
    the real `obsidian-vault/runs/` clean and lets multiple tests
    run independently without `runs/` cross-contamination.

    Returns:
        The `pathlib.Path` of the temp runs dir.
    """
    from backend.memory import obsidian_sync
    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(obsidian_sync, "_RUNS_DIR", runs_dir)
    return runs_dir


# ---------------------------------------------------------------------------
# 1. First call creates the runs/ directory and the per-run file
# ---------------------------------------------------------------------------


def test_write_run_status_creates_file_on_first_call(tmp_runs_dir) -> None:
    """Calling `write_run_status` for a new run_id creates the
    `runs/` directory (if missing) and writes `{run_id}.md` in it.
    """
    from backend.memory import obsidian_sync

    run_id = "test-run-001"
    path = obsidian_sync.write_run_status(
        run_id, obsidian_sync.RunStatus.STARTED, note="test run"
    )

    assert path.exists(), f"status file should exist at {path}"
    assert path.name == f"{run_id}.md", (
        f"file should be named {run_id}.md, got {path.name}"
    )
    assert path.parent == tmp_runs_dir, (
        f"file should live in {tmp_runs_dir}, got {path.parent}"
    )


# ---------------------------------------------------------------------------
# 2. File content is readable Markdown with run_id, timestamp, status, note
# ---------------------------------------------------------------------------


def test_write_run_status_writes_markdown_with_required_fields(tmp_runs_dir) -> None:
    """The first status entry renders as Markdown that includes the
    run_id (in a heading), a timestamp, the status value, and the
    caller's note. This is the contract the Obsidian reviewer relies on.
    """
    import re
    from backend.memory import obsidian_sync

    run_id = "test-run-content"
    path = obsidian_sync.write_run_status(
        run_id,
        obsidian_sync.RunStatus.STARTED,
        note="first run for content test",
    )

    text = path.read_text(encoding="utf-8")

    # Heading references the run_id so the file is identifiable in
    # the Obsidian file list.
    assert run_id in text, f"run_id should appear in file content; got:\n{text}"

    # Timestamp — a YYYY-MM-DD pattern. We don't pin the exact
    # format beyond that (the helper may use ISO with time, but
    # the date must be present and machine-readable).
    assert re.search(r"\d{4}-\d{2}-\d{2}", text), (
        f"file should contain a YYYY-MM-DD timestamp; got:\n{text}"
    )

    # Status value rendered as the bare string, not the enum repr.
    assert "started" in text, f"status value 'started' should appear; got:\n{text}"
    # The enum repr `RunStatus.STARTED` should NOT leak into the
    # markdown — the file is for humans, not Python.
    assert "RunStatus." not in text, (
        f"enum repr should not leak into markdown; got:\n{text}"
    )

    # Caller's note appears verbatim.
    assert "first run for content test" in text, (
        f"note should appear in file; got:\n{text}"
    )


# ---------------------------------------------------------------------------
# 3. Subsequent calls append to the same file (one file per run_id)
# ---------------------------------------------------------------------------


def test_write_run_status_appends_to_same_file(tmp_runs_dir) -> None:
    """A second call for the same run_id APPENDS a new section to
    the existing file. The run-level `# Run ...` heading is written
    exactly once. Both status values appear in the final file.
    """
    from backend.memory import obsidian_sync

    run_id = "test-run-append"
    path1 = obsidian_sync.write_run_status(
        run_id, obsidian_sync.RunStatus.STARTED, note="first"
    )
    path2 = obsidian_sync.write_run_status(
        run_id, obsidian_sync.RunStatus.RESEARCH_COMPLETE, note="second"
    )

    # Same path both times — the function does not create a new file
    # per call. (Important for grep-ability in Obsidian.)
    assert path1 == path2, f"both calls must return same path; got {path1} vs {path2}"

    text = path1.read_text(encoding="utf-8")

    # Run-level heading is written exactly once.
    assert text.count(f"# Run {run_id}") == 1, (
        f"run-level heading should appear exactly once; got:\n{text}"
    )

    # Both status values appear — second call did not overwrite first.
    assert "started" in text, f"'started' should still be in file; got:\n{text}"
    assert "research_complete" in text, (
        f"'research_complete' should be appended; got:\n{text}"
    )

    # Both notes are preserved.
    assert "first" in text, f"first note should still be in file; got:\n{text}"
    assert "second" in text, f"second note should be appended; got:\n{text}"


# ---------------------------------------------------------------------------
# 4. meta dict is rendered into the file as key: value bullets
# ---------------------------------------------------------------------------


def test_write_run_status_includes_meta_dict(tmp_runs_dir) -> None:
    """The optional `meta` dict is rendered into the section as
    `key: value` bullets. This is how the dashboard reads structured
    data (score, durations, etc.) out of the Markdown.
    """
    from backend.memory import obsidian_sync

    run_id = "test-run-meta"
    path = obsidian_sync.write_run_status(
        run_id,
        obsidian_sync.RunStatus.SCORING_COMPLETE,
        note="scored 42/50",
        meta={"score": 42, "research_brief_chars": 4521, "phase": "scoring"},
    )

    text = path.read_text(encoding="utf-8")

    # All meta keys appear.
    for key in ("score", "research_brief_chars", "phase"):
        assert key in text, f"meta key {key!r} should appear; got:\n{text}"

    # All meta values appear (as string form — no special type handling).
    for value in ("42", "4521", "scoring"):
        assert value in text, f"meta value {value!r} should appear; got:\n{text}"


# ---------------------------------------------------------------------------
# 5. OSError on disk failure is caught, logged, and swallowed
# ---------------------------------------------------------------------------


def test_write_run_status_swallows_oserror(tmp_runs_dir, caplog) -> None:
    """If writing to disk raises OSError (read-only FS, disk full,
    permission denied), the function logs the error and returns
    gracefully — it MUST NOT raise. The whole point of the sync
    helper is to be diagnostic, not load-bearing. Crashing the
    workflow run because Obsidian can't be written to would be
    a worse failure mode than silently dropping the entry.
    """
    import logging
    from unittest.mock import patch
    from backend.memory import obsidian_sync

    # Force the inner open() to raise OSError. This simulates any
    # filesystem-level failure: read-only mount, ENOSPC, EACCES, etc.
    def _boom(*args, **kwargs):
        raise OSError("simulated disk failure")

    with caplog.at_level(logging.ERROR, logger="backend.memory.obsidian_sync"):
        with patch("builtins.open", side_effect=_boom):
            # Must not raise.
            result = obsidian_sync.write_run_status(
                "test-run-oserror",
                obsidian_sync.RunStatus.STARTED,
                note="this should not crash",
            )

    # Return value is still the intended path (the caller gets a
    # valid Path object even though no bytes were written). This
    # keeps the API uniform — callers don't need to branch on
    # success/failure.
    assert result == tmp_runs_dir / "test-run-oserror.md", (
        f"function should return the intended path even on failure; got {result}"
    )

    # The error was logged at ERROR level so the developer can find
    # it in jarvis.log after the fact.
    assert any(
        "simulated disk failure" in record.message
        for record in caplog.records
    ), f"OSError should be logged at ERROR; records: {[r.message for r in caplog.records]}"
