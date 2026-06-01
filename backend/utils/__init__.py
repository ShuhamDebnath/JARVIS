"""Utility helpers for Jarvis backend.

Modules in this package:
- `logger.py`     — shared logging setup (file + stdout). Use this; never `print()`.
- `env_validator` — fails-loud check for required API keys on FastAPI startup.
- `cost_guard`    — token-usage and cost reporting per crew run (Phase 1+).
"""
