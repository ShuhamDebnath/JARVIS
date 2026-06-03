# backend/voice/listener.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 5 — Voice Layer (listener shell).
#
# Goal: ambient voice interface for Jarvis.
#   1. Wait for the Porcupine "Hey Jarvis" wake word
#   2. Capture the next N seconds of microphone audio
#   3. Transcribe the audio with faster-whisper (local STT)
#   4. Hand the transcript to the intent parser → workflow trigger
#   5. Speak the workflow's summary back with Kokoro (local TTS)
#
# This file currently ships a CLEAN STRUCTURAL SHELL only — the four
# public methods (`listen_for_wake_word`, `record_ambient_speech`,
# `transcribe_audio_to_text`, `synthesize_speech_output`) are stubbed
# with safe defaults so the class is importable and instantiable before
# the live audio integration is wired up.
#
# Why stubs first (not full impls in one commit)?
# - Lets the rest of Jarvis import JarvisVoiceCore without crashing
#   on dev machines that do not yet have a working microphone setup
#   (e.g. CI, headless tests, the Phase 4 dashboard pod).
# - Keeps this commit small and reviewable — a 50-line shell, not a
#   500-line audio engine.
#
# Native prerequisite (already satisfied on this machine):
#   brew install portaudio
# See AI-RULES.md Rule 5c for the M1 install story.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

# Deferred audio-lib imports live inside each method so this module
# remains importable in environments without a working mic (CI,
# Next.js dashboard, headless pytest). When the live integration
# lands, we promote the relevant imports to module scope.

from backend.utils.logger import get_logger

# Module-level logger. `__name__` resolves to `backend.voice.listener`
# in every log line — easy to grep for when debugging voice flows.
logger = get_logger(__name__)


class JarvisVoiceCore:
    """Single owner of the audio I/O lifecycle for Phase 5.

    Responsibilities (one method each):
        - detect the wake word
        - capture ambient speech
        - transcribe that speech
        - synthesise a spoken reply

    The class is intentionally a thin coordinator — the heavy lifting
    (Porcupine keyword models, Whisper weights, Kokoro ONNX graphs) is
    deferred to inside the methods, so this file stays small and the
    imports only happen when voice is actually used.
    """

    def __init__(self) -> None:
        """Boot the voice core and log the lifecycle hook.

        We do NOT open the microphone here on purpose — `__init__`
        must be cheap and side-effect-free so that simply importing
        `JarvisVoiceCore` (e.g. from a test or the dashboard) does
        not start capturing audio. The wake-word loop is started
        explicitly via `listen_for_wake_word()` from a dedicated
        Phase 5 entrypoint (the FastAPI voice router, when it
        lands in Phase 5.1).
        """
        logger.info("Initialising Jarvis Voice Layer Core ...")
        # `is_listening` is the single source of truth for whether the
        # wake-word loop is currently running. Set to True in
        # `listen_for_wake_word()` and back to False on shutdown.
        self.is_listening: bool = False

    # ------------------------------------------------------------------
    # Wake-word detection (pvporcupine — "Hey Jarvis")
    # ------------------------------------------------------------------

    def listen_for_wake_word(self) -> bool:
        """Listen for the Porcupine "Hey Jarvis" wake word.

        Stub behaviour (Phase 5.0): returns False immediately so the
        orchestration loop can be wired and tested without an actual
        microphone stream. The real implementation will:
            1. Load the Picovoice access key from .env
               (`PICOVOICE_ACCESS_KEY`).
            2. Construct a `pvporcupine.create(keywords=["jarvis"])`.
            3. Open a sounddevice InputStream at the porcupine frame
               length (typically 512 samples at 16 kHz).
            4. Spin until the keyword is detected, then return True.
            5. Tear down the stream in a `finally:` so a Ctrl-C does
               not leave the mic held open.

        Returns:
            True  → the wake word was heard (caller should now call
                    `record_ambient_speech` then `transcribe_audio_to_text`).
            False → the loop was asked to stop before the wake word fired.
        """
        logger.debug("listen_for_wake_word: stub — returning False")
        return False

    # ------------------------------------------------------------------
    # Ambient microphone capture (sounddevice / pyaudio)
    # ------------------------------------------------------------------

    def record_ambient_speech(self, duration_s: int = 5) -> bytes:
        """Capture `duration_s` seconds of microphone audio as raw PCM.

        Stub behaviour (Phase 5.0): returns an empty `bytes` object
        so the rest of the pipeline can be exercised without a real
        recording. The real implementation will:
            1. Open a `sounddevice.RawInputStream` at 16 kHz,
               mono, int16 — the format faster-whisper expects.
            2. Read `duration_s * 16000 * 2` bytes (2 bytes per
               int16 sample at 16 kHz).
            3. Return the concatenated buffer.

        Args:
            duration_s: How long to listen, in seconds. Default 5s
                        is long enough for a single voice command
                        ("Hey Jarvis, research habit tracker apps")
                        and short enough that a false wake-word
                        trigger does not tie up the mic for long.

        Returns:
            Raw little-endian int16 PCM bytes, ready to be passed
            straight into faster-whisper's `audio` argument.
        """
        logger.debug("record_ambient_speech: stub — returning empty bytes (duration_s=%d)", duration_s)
        return b""

    # ------------------------------------------------------------------
    # Speech-to-text (faster-whisper — local Whisper)
    # ------------------------------------------------------------------

    def transcribe_audio_to_text(self, audio_data: bytes) -> str:
        """Transcribe raw PCM audio to a UTF-8 text string.

        Stub behaviour (Phase 5.0): returns an empty string. The real
        implementation will:
            1. Construct a `WhisperModel` (size = "small.en" or
               "base.en" on Apple Silicon, "large-v3" on machines
               with enough RAM — see Phase 5 implementation notes).
            2. Call `model.transcribe(audio_bytes)` where
               `audio_bytes` is the PCM returned by
               `record_ambient_speech`.
            3. Concatenate segment.text values and strip whitespace.

        Args:
            audio_data: Raw little-endian int16 PCM bytes (as
                        produced by `record_ambient_speech`).

        Returns:
            The transcribed text. Empty string if the buffer is
            silent or the model produces no segments.
        """
        logger.debug("transcribe_audio_to_text: stub — returning empty string (audio_len=%d)", len(audio_data))
        return ""

    # ------------------------------------------------------------------
    # Text-to-speech (kokoro-onnx — local Kokoro)
    # ------------------------------------------------------------------

    def synthesize_speech_output(self, text: str) -> bool:
        """Speak `text` aloud through the default output device.

        Stub behaviour (Phase 5.0): returns False. The real
        implementation will:
            1. Load the Kokoro ONNX model + voices from the local
               model directory (downloaded on first use).
            2. Call `Kokoro.create()` and run
               `kokoro.create(text, voice="af_sarah", speed=1.0)`.
            3. Stream the resulting PCM out through
               `sounddevice.RawOutputStream`.

        Args:
            text: The string to speak. Phase 5 will keep this short
                  (a workflow summary sentence, not a PRD) so the
                  TTS latency stays under ~2 seconds.

        Returns:
            True  → audio was queued to the output device.
            False → TTS was skipped (empty text, model missing, or
                    stub-mode in Phase 5.0).
        """
        logger.debug("synthesize_speech_output: stub — returning False (text_len=%d)", len(text))
        return False
