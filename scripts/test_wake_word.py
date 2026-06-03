# scripts/test_wake_word.py
# ─────────────────────────────────────────────────────────────────────────────
# Standalone test sandbox for the Phase 5.1 wake-word pipeline.
#
# This script bypasses the FastAPI server and the crew orchestrator
# entirely — it just instantiates `JarvisVoiceCore` and calls
# `listen_for_wake_word()` so the developer can confirm:
#
#   1. The Picovoice / Porcupine access key in .env is valid.
#   2. macOS microphone permissions are granted for the terminal.
#   3. The "jarvis" built-in keyword model is being heard.
#
# Usage (from the project root, with the venv active):
#
#     .venv/bin/python scripts/test_wake_word.py
#
# Expected behaviour:
#   - First run on macOS will pop a "Python wants to access the
#     Microphone" system dialog. Click "Allow".
#   - The script prints "Listening for 'Jarvis'..." and then either
#     "✅ Wake word detected successfully!" (success) or
#     "❌ Wake word NOT detected" (Ctrl-C, or PORCUPINE_ACCESS_KEY
#     missing/placeholder).
#   - Exit code 0 on detection, 1 on no detection, 130 on Ctrl-C.
#
# This file is intentionally print()-based (it's a CLI tool, not
# production code) — AI-RULES.md "never print() in production code"
# applies to the backend, not to scripts/.
# ─────────────────────────────────────────────────────────────────────────────

import sys
from pathlib import Path

# Make the project root importable when this script is run directly
# (e.g. `.venv/bin/python scripts/test_wake_word.py` from the repo
# root). Without this, the `from backend.voice.listener` import
# below would fail with ModuleNotFoundError.
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Importing the voice module is the moment pvporcupine + sounddevice
# are pulled in. If the venv is missing a wheel, the import error
# will surface here with a clear message — much friendlier than a
# half-built class.
#
# `type: ignore[reportMissingImports]` — Pyright can't statically
# see the sys.path manipulation above, so it flags the import as
# unresolvable. At runtime, the injected sys.path entry makes the
# import succeed.
from backend.voice.listener import JarvisVoiceCore  # type: ignore[reportMissingImports]


def main() -> int:
    """Run the wake-word sandbox and return a process exit code.

    Exit codes (per `man sysexits.h` convention where it makes sense):
        0 — wake word was detected before the user interrupted.
        1 — wake word NOT detected (loop exited without a hit).
        130 — user pressed Ctrl-C (128 + SIGINT=2).
    """
    print("=" * 60)
    print("🎤 Jarvis — Wake Word Test Sandbox (Phase 5.1)")
    print("=" * 60)
    print()
    print("Listening for 'Jarvis'... Say the wake word!")
    print("(Press Ctrl-C to quit.)")
    print()

    # Instantiate the voice core. The constructor is intentionally
    # side-effect-free — it only logs an INFO line and sets
    # `is_listening = False`. The microphone is opened later, inside
    # `listen_for_wake_word()`.
    core = JarvisVoiceCore()

    # Block until the wake word fires (or an error/interrupt). The
    # method handles its own cleanup, so the audio device is
    # released the moment we get back here.
    detected = core.listen_for_wake_word()

    print()
    if detected:
        print("✅ Wake word detected successfully!")
        return 0

    print("❌ Wake word NOT detected (exited without hearing the keyword).")
    print("   Common causes:")
    print("   - PORCUPINE_ACCESS_KEY missing or still a .env placeholder")
    print("   - macOS microphone permission denied (System Settings →")
    print("     Privacy & Security → Microphone → enable your terminal)")
    print("   - Wrong input device selected in macOS sound settings")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Ctrl-C exits cleanly with the conventional 128+SIGINT code
        # so shell scripts can tell a "user aborted" exit apart from
        # a "no detection" exit.
        print("\n[interrupted by user]")
        sys.exit(130)
