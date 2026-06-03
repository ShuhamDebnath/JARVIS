"""Voice layer for Jarvis (Phase 5).

This package implements the ambient voice interface described in
`docs/roadmap.md` Phase 5:

    Wake word ("Hey Jarvis")
        → pvporcupine                  (backend/voice/listener.py)
    Ambient speech capture
        → sounddevice / pyaudio        (backend/voice/listener.py)
    Speech-to-text
        → faster-whisper (local)       (backend/voice/listener.py)
    Intent parsing → workflow trigger  (added in Phase 5.1)
    Text-to-speech
        → kokoro-onnx (local)          (backend/voice/listener.py)

The first landed module is `listener.py`, which exposes
`JarvisVoiceCore` — a single class that owns the audio I/O lifecycle
(wake-word loop, ambient recording, STT, TTS) and is the only object
the rest of Jarvis should talk to when the voice layer is active.

Why a class (not a set of free functions)?
- The wake-word loop owns long-lived audio stream handles; bundling
  them into one class makes resource lifecycle obvious.
- Phase 5.1 will add an IntentParser that needs shared state with
  the STT pipeline — a class keeps that refactor local.

Phase 5 is staggered: the present commit ships the structural shell
and method stubs only. The wake-word / STT / TTS bodies are filled
in after the surrounding workflow-trigger integration is agreed.
"""
