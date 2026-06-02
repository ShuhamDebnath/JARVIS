"""Test package for Jarvis.

Per the Phase 0a plan, tests live under `tests/` at the project root
(not inside `backend/`). This makes the test suite independent of
the backend package layout — the backend can be refactored freely
without breaking test imports.

Files in this package:
    conftest.py              — shared fixtures + MockLLM
    test_hello_crew.py       — Step 7 hello-world crew
    test_human_gate.py       — Step 9 human_gate handshake
    test_phase0a_e2e.py      — Step 10 FastAPI end-to-end
"""
