#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Jarvis — project setup script (Phase 0a)
# Purpose: Install all locked Python dependencies from backend/requirements.txt
#          into the active virtual environment using `uv`.
#
# Usage:   bash scripts/setup.sh
# Prereq:  uv installed (https://docs.astral.sh/uv/) AND venv activated
#          (`source .venv/bin/activate`).
#
# Per ADR-0002 Q6, the crewai and pydantic versions in requirements.txt are
# pinned for a reason — do NOT bump them without re-running the
# tests/test_workflow_2_parallelism.py check.
# ─────────────────────────────────────────────────────────────────────────────

# Exit immediately on any error so the script fails loudly instead of
# silently installing a partial set of packages.
set -euo pipefail

# 1. Confirm `uv` is on PATH. If not, tell the user what to do.
if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: 'uv' is not installed or not on PATH."
  echo "Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "Then re-run this script."
  exit 1
fi

# 2. Confirm we are running inside an activated virtual environment.
#    `python -c "import sys; sys.exit(0 if sys.prefix != sys.base_prefix else 1)"`
#    exits 0 only if the current Python is inside a venv.
if ! python -c "import sys; sys.exit(0 if sys.prefix != sys.base_prefix else 1)" >/dev/null 2>&1; then
  echo "ERROR: No active virtual environment detected."
  echo "Activate the project's venv first:  source .venv/bin/activate"
  echo "Then re-run this script."
  exit 1
fi

# 3. Install the locked dependencies from backend/requirements.txt.
#    `uv pip install` is a drop-in replacement for `pip install` that resolves
#    and installs from the pinned versions file. The venv is already active,
#    so packages land inside it (no `--prefix` needed).
echo "Installing locked dependencies from backend/requirements.txt ..."
uv pip install -r backend/requirements.txt

# 4. Quick post-install sanity check — fail loud if a critical package is missing.
echo "Verifying key packages are importable ..."
python - <<'PY'
import importlib, importlib.util, sys  # util must be imported explicitly
missing = [p for p in ("crewai", "crewai_tools", "pydantic", "openai", "dotenv") if not importlib.util.find_spec(p)]
if missing:
    print(f"ERROR: The following packages did not install correctly: {missing}")
    sys.exit(1)
print("OK — crewai, crewai_tools, pydantic, openai, dotenv are all importable.")
PY

echo "Setup complete. Next: copy .env.example to .env and fill in your API keys."
