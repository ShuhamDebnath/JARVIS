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

        Live implementation (Phase 5.1). On success, the audio stream
        and Porcupine handle are torn down before returning, so a
        follow-up call to `record_ambient_speech()` opens a fresh
        stream with no contention.

        Flow:
            1. Read PORCUPINE_ACCESS_KEY from the environment. If it
               is missing or still holds a `.env.example` placeholder,
               log an ERROR and return False — the voice layer is
               degraded, but Phases 0-4 keep working.
            2. Initialise `pvporcupine.create(access_key=key,
               keywords=["jarvis"])`. The built-in `jarvis` keyword
               ships with the pvporcupine wheel; no custom .ppn file
               is needed for v1.
            3. Open a `sounddevice.RawInputStream` whose `samplerate`,
               `channels`, and `blocksize` EXACTLY match the Porcupine
               instance. A mismatch will make `porcupine.process()`
               raise at the first call.
            4. Loop: read one frame, call `porcupine.process(pcm)`. If
               the returned keyword index is >= 0, the wake word fired.
            5. Cleanup: in `finally:`, close the stream and call
               `porcupine.delete()` to release native handles — even
               on Ctrl-C or an unexpected exception.

        Returns:
            True  → wake word heard; stream and Porcupine are cleaned
                    up before returning so the caller can open a new
                    stream for the actual command.
            False → no key, interruption, or runtime error. The
                    wake-word loop is NOT running after the call
                    either way (`is_listening` is reset in `finally`).
        """
        # Lazy imports — keeps this module importable in headless /
        # CI environments where pvporcupine + sounddevice are present
        # but no audio device is reachable.
        import os
        import pvporcupine
        import sounddevice as sd

        # Step 1 — read the access key. We use PORCUPINE_ACCESS_KEY
        # to match the rest of the project (`.env.example`,
        # `env_validator.py`). Picovoice is the company; Porcupine
        # is the product — they share the same key.
        raw_key = os.environ.get("PORCUPINE_ACCESS_KEY", "")
        # Strip whitespace and reject anything that still looks like
        # the `.env.example` placeholder (covers `your_*` and
        # `replace_me_with_*` patterns without hard-coding either).
        access_key = raw_key.strip()
        is_placeholder = (
            not access_key
            or access_key.startswith("your_")
            or "replace_me" in access_key
        )
        if is_placeholder:
            logger.error(
                "listen_for_wake_word: PORCUPINE_ACCESS_KEY is missing or still a "
                ".env.example placeholder. Get a free key at "
                "https://console.picovoice.ai/ and add it to .env. "
                "Voice Layer (Phase 5) is disabled until then — wake word "
                "detection will return False."
            )
            return False

        # Step 2/3 — open the Porcupine handle and a matching audio
        # stream. The variables are declared above the `try` so the
        # `finally` cleanup can see them and skip when None.
        porcupine = None
        stream = None
        try:
            # Built-in "jarvis" keyword — no custom .ppn file needed
            # for v1. Phase 5.2 can swap to a custom "Hey Jarvis"
            # phrase via `keyword_paths=[...]` without changing
            # anything else in this method.
            porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=["jarvis"],
            )

            # The Porcupine constructor returns a handle whose
            # `sample_rate` and `frame_length` are the EXACT values
            # the audio stream must use. Mismatches surface as a
            # `ValueError` from `porcupine.process()` on the first
            # frame.
            #
            # Channels is hardcoded to 1 because Porcupine is
            # mono-only — pvporcupine 4.x does not expose a channel
            # count attribute. Verified at runtime via
            # `dir(pvporcupine.Porcupine)` (only `frame_length`
            # and `sample_rate` are present).
            stream = sd.RawInputStream(
                samplerate=porcupine.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=porcupine.frame_length,
            )
            stream.start()

            self.is_listening = True
            logger.info(
                "Wake-word loop started — rate=%d Hz, channels=1, frame=%d. "
                "Say 'jarvis' to trigger.",
                porcupine.sample_rate, porcupine.frame_length,
            )

            # Step 4 — read one frame at a time and feed Porcupine.
            # `stream.read(frame_length)` blocks until exactly that
            # many frames are available (because blocksize==frame_length).
            while True:
                pcm_bytes, overflow = stream.read(porcupine.frame_length)
                if overflow:
                    # Non-fatal — sounddevice drops a few samples
                    # under load. Log so the operator can spot a
                    # CPU-starved host.
                    logger.warning("Audio buffer overflow — some samples dropped.")

                # `bytes(...)` copies the buffer out of sounddevice's
                # internal memory so Porcupine can read it after the
                # next read() call. Without the copy, the second
                # read() would clobber the first.
                keyword_index = porcupine.process(bytes(pcm_bytes))

                if keyword_index >= 0:
                    # Step 5 — wake word fired. We log, then return
                    # True. The `finally` block tears down the stream
                    # and Porcupine handle so the next phase of the
                    # voice flow (record_ambient_speech) can open its
                    # own stream on a free device.
                    logger.info("Wake word detected! (keyword_index=%d)", keyword_index)
                    return True

        except KeyboardInterrupt:
            # User pressed Ctrl-C. Fall through to cleanup. Returning
            # False lets the caller treat this the same as a normal
            # "no detection" exit and decide whether to retry.
            logger.info("Wake-word loop interrupted by user (Ctrl-C).")
            return False
        except Exception as e:
            # Any other failure (no microphone permission, invalid
            # access key, device busy) lands here. Log the full
            # traceback for debugging and return False so the
            # caller can degrade gracefully.
            logger.error("listen_for_wake_word: unexpected error — %s", e, exc_info=True)
            return False
        finally:
            # Always release native handles, even on exception or
            # Ctrl-C. Order: stream first (it holds the mic), then
            # Porcupine (it talks to the stream). Each cleanup is
            # wrapped because a partial-init failure can leave
            # either of them `None`.
            self.is_listening = False
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception as cleanup_err:
                    logger.warning("Failed to close audio stream cleanly: %s", cleanup_err)
            if porcupine is not None:
                try:
                    porcupine.delete()
                except Exception as cleanup_err:
                    logger.warning("Failed to delete porcupine handle cleanly: %s", cleanup_err)

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
