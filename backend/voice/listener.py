# backend/voice/listener.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 5 — Voice Layer (local MLX stack).
#
# Goal: ambient voice interface for Jarvis, fully on-device.
#   1. A background thread opens the microphone and runs Silero-VAD
#      (a tiny torch model) to gate out background noise.
#   2. When speech is detected, the buffered audio is fed to mlx-whisper
#      for local transcription.
#   3. The transcript is handed off to the intent parser / workflow
#      trigger (implemented in later phases). If `auto_execute` is
#      True the matched crew runs immediately; otherwise the parsed
#      command is staged on the dashboard for human confirmation.
#   4. The crew's summary is spoken back via mlx-audio (Kokoro-82M-bf16)
#      if `tts_enabled` is True; otherwise the response stays on screen.
#
# Architectural pivot (2026-06-03): the old Porcupine + faster-whisper +
# kokoro-onnx stack was replaced with a 100% local MLX stack. The only
# external dependency at runtime is Hugging Face (one-time model download
# on first use); no API keys, no cloud calls.
#
# Three hardware-aware toggles are exposed via FastAPI at
# /api/voice/settings and mirrored on the Next.js dashboard:
#     mic_enabled   — start/stop the background VAD + STT loop
#     tts_enabled   — speak responses aloud (True) or stay silent (False)
#     auto_execute  — run matched workflows immediately (True) or stage
#                     them on the dashboard for manual safety
#                     confirmation (False)
#
# All heavy MLX / torch imports happen LAZILY inside the methods, not
# at module load, so this file is importable in test suites and on
# headless CI machines that have the packages installed but no
# microphone attached.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

# Stdlib only at module scope — keeps the file importable in any
# environment. All third-party audio / ML imports live inside the
# methods that actually need them.
import os
import shutil
import subprocess
import tempfile
import threading
from typing import Optional

import numpy as np

from backend.utils.logger import get_logger

# Module-level logger. `__name__` resolves to `backend.voice.listener`
# in every log line — easy to grep for when debugging voice flows.
logger = get_logger(__name__)


class JarvisVoiceCore:
    """Single owner of the audio I/O lifecycle for Phase 5.

    Responsibilities:
        - Hold the 3 hardware-state toggles in a thread-safe way.
        - Spawn / stop a background microphone listener that runs
          Silero-VAD gating + mlx-whisper transcription.
        - Expose `run_stt(audio)` and `run_tts(text)` helpers used by
          the rest of the voice pipeline.
        - Honour `tts_enabled` before shelling out to `afplay`.

    Threading model:
        - Public state setters (set_mic_enabled, set_tts_enabled,
          set_auto_execute) are guarded by `_state_lock` so the
          FastAPI thread and the background listener thread see a
          consistent snapshot.
        - The listener thread is the ONLY thread that opens the
          sounddevice stream. The FastAPI thread only flips the
          `stop_listening_event` and joins the worker.

    The class is intentionally a thin coordinator — the heavy lifting
    (Silero-VAD weights, mlx-whisper weights, mlx-audio weights) is
    deferred to inside the methods, so this file stays small and the
    imports only happen when voice is actually used.
    """

    # Audio capture parameters — fixed for the VAD + STT pipeline.
    # 16 kHz / mono / int16 PCM is the format Silero-VAD and
    # mlx-whisper (base.en) both expect.
    SAMPLE_RATE: int = 16000
    CHANNELS: int = 1
    BLOCKSIZE: int = 512  # ~32 ms at 16 kHz — small enough for responsive VAD
    DTYPE: str = "int16"

    def __init__(self) -> None:
        """Boot the voice core and log the lifecycle hook.

        We do NOT open the microphone here on purpose — `__init__`
        must be cheap and side-effect-free so that simply importing
        `JarvisVoiceCore` (e.g. from a test or the dashboard) does
        not start capturing audio. The VAD loop is started explicitly
        via `start_listening()` from the FastAPI voice router.
        """
        logger.info("Initialising Jarvis Voice Layer Core (local MLX stack) ...")

        # 3 hardware-aware toggles (per Step 4 of the Phase 5 brief).
        # Defaults: mic off, TTS on, auto-execute OFF (safety).
        self.mic_enabled: bool = False
        self.tts_enabled: bool = True
        self.auto_execute: bool = False

        # threading.Event is the cleanest cross-thread signal in
        # stdlib — `set()` from one thread, `is_set()` / `wait()`
        # from another. Using an Event (not a bool) means the
        # listener loop can also `wait()` with a timeout if we ever
        # need a periodic poll.
        self.stop_listening_event = threading.Event()
        self.stop_listening_event.set()  # starts in "stopped" state

        # The worker thread handle. None when the loop is not running.
        self._listen_thread: Optional[threading.Thread] = None

        # Guard for the 3 toggles + the thread handle. The FastAPI
        # thread and the listener thread can both touch them.
        self._state_lock = threading.Lock()

    # ------------------------------------------------------------------
    # State management (thread-safe)
    # ------------------------------------------------------------------

    def get_settings(self) -> dict:
        """Return a JSON-serialisable snapshot of the 3 toggles + listening flag.

        Used by `GET /api/voice/settings` to feed the Next.js
        VoiceControls panel. The snapshot is taken under the state
        lock so it can never be half-updated mid-read.
        """
        with self._state_lock:
            is_listening = (
                self._listen_thread is not None
                and self._listen_thread.is_alive()
            )
            return {
                "mic_enabled": self.mic_enabled,
                "tts_enabled": self.tts_enabled,
                "auto_execute": self.auto_execute,
                "is_listening": is_listening,
            }

    def update_settings(self, *, mic_enabled: Optional[bool] = None,
                        tts_enabled: Optional[bool] = None,
                        auto_execute: Optional[bool] = None) -> dict:
        """Apply a partial update to the 3 toggles, starting/stopping the listener as needed.

        The caller (FastAPI) passes only the fields it wants to
        change; untouched fields keep their current value. After
        applying the diff, we react to a `mic_enabled` flip by
        starting or stopping the background listener thread.

        Returns the new full settings dict (same shape as `get_settings`).
        """
        with self._state_lock:
            if mic_enabled is not None:
                self.mic_enabled = bool(mic_enabled)
            if tts_enabled is not None:
                self.tts_enabled = bool(tts_enabled)
            if auto_execute is not None:
                self.auto_execute = bool(auto_execute)

        # React to mic toggle outside the lock — start/stop_listening
        # may join the worker thread, which would deadlock if we
        # held the lock.
        if mic_enabled is not None:
            if mic_enabled:
                self.start_listening()
            else:
                self.stop_listening()

        logger.info(
            "Voice settings updated: mic=%s tts=%s auto_execute=%s",
            self.mic_enabled, self.tts_enabled, self.auto_execute,
        )
        return self.get_settings()

    # ------------------------------------------------------------------
    # Threading control
    # ------------------------------------------------------------------

    def start_listening(self) -> None:
        """Launch the background VAD + STT loop (idempotent).

        A no-op if the loop is already running. The worker thread is
        a daemon so it dies automatically when the FastAPI process
        exits — the `stop_listening_event` is set first so the loop
        breaks out of any blocking `sd.InputStream.read()`.
        """
        with self._state_lock:
            if self._listen_thread is not None and self._listen_thread.is_alive():
                logger.debug("start_listening: worker already alive — no-op")
                return
            # Clear the stop signal BEFORE spawning so the new worker
            # sees `is_set() == False` on its first iteration.
            self.stop_listening_event.clear()
            self.mic_enabled = True
            self._listen_thread = threading.Thread(
                target=self.continuous_listen_loop,
                name="jarvis-voice-listener",
                daemon=True,
            )

        self._listen_thread.start()
        logger.info("Voice listener thread started (id=%s).", self._listen_thread.ident)

    def stop_listening(self) -> None:
        """Signal the background loop to exit and wait for it to join.

        Safe to call from any thread. If the worker is not running
        this is a cheap no-op. The `stop_listening_event` is set
        first (so the loop sees the signal even if it is blocked in
        `stream.read()`) and we join with a short timeout so a stuck
        audio device cannot wedge the FastAPI shutdown path.
        """
        with self._state_lock:
            self.stop_listening_event.set()
            self.mic_enabled = False
            thread = self._listen_thread

        if thread is None or not thread.is_alive():
            logger.debug("stop_listening: no live worker — no-op")
            return

        # Bounded join — the loop's `finally:` always closes the
        # stream, but if the OS hangs on to the audio device we
        # don't want to block the API forever.
        thread.join(timeout=3.0)
        if thread.is_alive():
            logger.warning(
                "Voice listener thread did not exit within 3s — "
                "leaking. Next start_listening() will spawn a fresh thread."
            )
        else:
            logger.info("Voice listener thread stopped cleanly.")

    # ------------------------------------------------------------------
    # Background loop (runs on its own thread)
    # ------------------------------------------------------------------

    def continuous_listen_loop(self) -> None:
        """The background worker: open mic → VAD gate → STT on speech.

        Exits when `stop_listening_event` is set. The audio stream
        and VAD model are torn down in `finally:` so the OS audio
        device is always released, even on exception.

        Lazy imports: sounddevice + torch are heavy and may not be
        installed on every dev box. Importing them inside the method
        means `from backend.voice.listener import JarvisVoiceCore`
        still works in CI / headless pytest runs.
        """
        import sounddevice as sd  # lazy — PortAudio-backed
        import torch  # lazy — used to load Silero-VAD

        # Per-thread rolling buffer of the most recent ~2 s of audio
        # so we can hand a complete utterance to STT once VAD reports
        # silence (end-of-speech). int16 mono at 16 kHz → 2 bytes/sample.
        prefill_samples = int(self.SAMPLE_RATE * 2)
        audio_buffer = np.zeros(prefill_samples, dtype=np.int16)

        vad_model = None
        vad_iterator = None
        stream = None
        try:
            logger.info("Loading Silero-VAD model (torch.hub, snakers4/silero-vad) ...")
            vad_model, _utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
            )
            # utils tuple is (get_speech_timestamps, save_audio,
            # read_audio, VADIterator, collect_chunks). We only need
            # the VADIterator for this gating loop — discard the
            # other 4 with bare `_` so Pyright doesn't warn.
            _, _, _, VADIterator, _ = _utils
            vad_iterator = VADIterator(vad_model, threshold=0.5)

            logger.info(
                "Opening mic stream: rate=%d Hz, channels=%d, blocksize=%d",
                self.SAMPLE_RATE, self.CHANNELS, self.BLOCKSIZE,
            )
            stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                blocksize=self.BLOCKSIZE,
            )
            stream.start()

            # The VADIterator returns start/end events directly
            # (see the `event` handling below), so we do not need a
            # separate `speech_active` flag — the iterator owns
            # utterance state internally.
            while not self.stop_listening_event.is_set():
                # `stream.read(blocksize)` blocks until exactly that
                # many frames are available. Returns (bytes, overflow).
                # We rely on overflow being non-fatal — Silero-VAD is
                # robust to a dropped sample here and there — but log
                # it at debug level so a CPU-starved host is visible.
                pcm_bytes, overflow = stream.read(self.BLOCKSIZE)
                if overflow:
                    logger.debug("Audio buffer overflow — some samples dropped.")
                chunk = np.frombuffer(pcm_bytes, dtype=np.int16)

                # Roll the buffer: drop the oldest BLOCKSIZE samples,
                # append the new chunk. Keeps the last 2 s ready for
                # STT when end-of-speech is detected.
                audio_buffer = np.roll(audio_buffer, -len(chunk))
                audio_buffer[-len(chunk):] = chunk

                # Silero-VAD expects float32 in [-1, 1] at 16 kHz.
                # int16 → float32 normalisation is a single division.
                vad_input = chunk.astype(np.float32) / 32768.0
                # `vad_iterator(chunk, sr)` returns a dict like
                # {"start": ts, "end": ts} on transitions, or {}.
                event = vad_iterator(vad_input, self.SAMPLE_RATE)
                if event and "start" in event:
                    logger.debug("VAD: speech START")
                elif event and "end" in event:
                    logger.info("VAD: speech END — handing buffer to STT")
                    self._handle_utterance(audio_buffer.copy())
                    # Reset the buffer so the next utterance starts clean.
                    audio_buffer[:] = 0

        except Exception as e:
            logger.error("continuous_listen_loop crashed: %s", e, exc_info=True)
        finally:
            # Release hardware in reverse-open order: stream first
            # (holds the mic), then the VAD iterator is GC'd. Each
            # cleanup is wrapped so a partial-init failure cannot
            # wedge the audio device.
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception as cleanup_err:
                    logger.warning("Failed to close audio stream: %s", cleanup_err)
            if vad_iterator is not None:
                try:
                    vad_iterator.reset_states()
                except Exception as cleanup_err:
                    logger.warning("Failed to reset VAD iterator: %s", cleanup_err)
            # Mark the worker as fully stopped so the next
            # `start_listening()` call sees a clean slate.
            self.stop_listening_event.set()
            logger.info("continuous_listen_loop exiting.")

    # ------------------------------------------------------------------
    # Per-utterance handler (called from the background loop)
    # ------------------------------------------------------------------

    def _handle_utterance(self, audio_buffer: np.ndarray) -> None:
        """Transcribe the buffered audio, parse intent, and route.

        Phase 5.2 updates:
            1. STT the utterance via mlx-whisper.
            2. Run the transcript through `parse_voice_intent`.
            3. On "unknown": TTS an apology and exit.
            4. On a matched workflow:
               - auto_execute=False → stage to pending_voice.json,
                 TTS a confirmation message.
               - auto_execute=True  → TTS execution notice and log
                 the routing destination (NO live crew launch yet).
        """
        try:
            text = self.run_stt(audio_buffer)
        except Exception as e:
            logger.error("STT failed: %s", e, exc_info=True)
            return
        if not text:
            logger.debug("STT returned empty text — ignoring")
            return
        logger.info("Voice transcript: %r", text)

        # Phase 5.2: intent parsing
        try:
            from backend.voice.intent import parse_voice_intent
        except Exception as e:
            logger.error("Failed to import intent parser: %s", e, exc_info=True)
            if self.tts_enabled:
                self.run_tts("I had trouble understanding. Please try again.")
            return

        intent = parse_voice_intent(text)
        workflow_id = intent.get("workflow_id", "unknown")
        payload = intent.get("payload", "")
        workflow_label = f"workflow {workflow_id.replace('workflow_', '')}"

        if workflow_id == "unknown":
            if self.tts_enabled:
                self.run_tts("I didn't quite catch which workflow you want to run.")
            return

        if not self.auto_execute:
            # Stage the intent on disk for the Next.js dashboard to poll.
            pending_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "state", "pending_voice.json",
            )
            try:
                os.makedirs(os.path.dirname(pending_path), exist_ok=True)
                import json as _json
                with open(pending_path, "w") as f:
                    _json.dump({
                        "workflow_id": workflow_id,
                        "payload": payload,
                        "source_transcript": text,
                    }, f)
                logger.info("Pending voice intent staged at %s", pending_path)
            except Exception as e:
                logger.error("Failed to write pending_voice.json: %s", e, exc_info=True)

            if self.tts_enabled:
                self.run_tts(f"Staging {workflow_label} on your dashboard for confirmation.")
        else:
            # auto_execute=True: TTS notice only — NO live crew launch.
            logger.info(
                "auto_execute=True: would route %s with payload=%r",
                workflow_id, payload,
            )
            if self.tts_enabled:
                self.run_tts(f"Executing {workflow_label} immediately.")

    # ------------------------------------------------------------------
    # STT hook (mlx-whisper)
    # ------------------------------------------------------------------

    def run_stt(self, audio_data: np.ndarray) -> str:
        """Transcribe an int16 mono 16 kHz numpy buffer via mlx-whisper.

        Returns the joined transcript text, or "" on any failure
        (the caller decides whether empty is a no-op or an error).
        Lazy import: mlx_whisper is heavy and only needed when an
        utterance is actually captured.
        """
        try:
            import mlx_whisper  # lazy — Apple-Silicon-only import
        except ImportError as e:
            logger.error("mlx_whisper not installed: %s", e)
            return ""

        # mlx_whisper.transcribe accepts a numpy float32 array at
        # 16 kHz mono. int16 → float32 normalisation.
        audio_float = audio_data.astype(np.float32) / 32768.0
        try:
            result = mlx_whisper.transcribe(
                audio_float,
                path_or_hf_repo="mlx-community/whisper-base.en-mlx",
            )
        except Exception as e:
            logger.error("mlx_whisper.transcribe failed: %s", e, exc_info=True)
            return ""

        # `result` is a dict-like with a "text" key holding the
        # joined transcript. Strip whitespace; return "" if blank.
        text = (result.get("text") or "").strip()
        return text

    # ------------------------------------------------------------------
    # TTS hook (mlx-audio / Kokoro-82M-bf16) + afplay
    # ------------------------------------------------------------------

    # def run_tts(self, text: str) -> bool:
    #     """Synthesise `text` with Kokoro and play it via `afplay` (macOS).
    #
    #     Honours `self.tts_enabled` — if the user has muted spoken
    #     responses, this method is a no-op and returns False. Audio
    #     is generated to a temp WAV file, played once, then cleaned
    #     up. Returns True on successful playback, False on any skip /
    #     failure (the caller should not crash on a TTS error).
    #     """
    #     if not self.tts_enabled:
    #         logger.debug("run_tts: tts_enabled=False — skipping playback")
    #         return False
    #     if not text or not text.strip():
    #         logger.debug("run_tts: empty text — skipping")
    #         return False
    #
    #     try:
    #         from mlx_audio.tts.generate import generate_audio
    #     except ImportError as e:
    #         logger.error("mlx_audio not installed: %s", e)
    #         return False
    #
    #     # mlx_audio generates a wav file at the given output path.
    #     # We use a NamedTemporaryFile so the file is auto-cleaned if
    #     # something goes wrong mid-generation.
    #     tmp = tempfile.NamedTemporaryFile(
    #         prefix="jarvis_tts_", suffix=".wav", delete=False
    #     )
    #     tmp_path = tmp.name
    #     tmp.close()
    #     try:
    #         generate_audio(
    #             text=text,
    #             model_path="mlx-community/Kokoro-82M-bf16",
    #             output_path=tmp_path,
    #         )
    #     except Exception as e:
    #         logger.error("mlx_audio generate_audio failed: %s", e, exc_info=True)
    #         return False
    #
    #     # macOS-only playback. `afplay` ships with the OS so we
    #     # don't need to bundle anything. `which` check is cheap and
    #     # surfaces a clearer error on non-mac dev boxes.
    #     if shutil.which("afplay") is None:
    #         logger.warning("afplay not found on PATH — generated WAV at %s", tmp_path)
    #         return False
    #
    #     try:
    #         subprocess.run(
    #             ["afplay", tmp_path],
    #             check=True,
    #             timeout=60,
    #             capture_output=True,
    #         )
    #     except subprocess.TimeoutExpired:
    #         logger.error("afplay timed out after 60s on %s", tmp_path)
    #         return False
    #     except subprocess.CalledProcessError as e:
    #         logger.error("afplay failed (rc=%d): %s", e.returncode, e.stderr)
    #         return False
    #     finally:
    #         # Best-effort cleanup. If the file is locked (afplay
    #         # hasn't released it), we just log and move on — the
    #         # temp dir gets reaped at boot.
    #         try:
    #             os.unlink(tmp_path)
    #         except OSError:
    #             pass
    #     return True

    def run_tts(self, text: str) -> bool:
        """Synthesise `text` with Kokoro and play it via `afplay` (macOS).

        Honours `self.tts_enabled` — if the user has muted spoken
        responses, this method is a no-op and returns False. Audio
        is generated to a temp WAV file, played once, then cleaned
        up. Returns True on successful playback, False on any skip /
        failure (the caller should not crash on a TTS error).
        """
        if not self.tts_enabled:
            logger.debug("run_tts: tts_enabled=False — skipping playback")
            return False
        if not text or not text.strip():
            logger.debug("run_tts: empty text — skipping")
            return False

        try:
            from mlx_audio.tts.generate import generate_audio
        except ImportError as e:
            logger.error("mlx_audio not installed: %s", e)
            return False

        # Use a temporary directory to handle whatever filename prefix/suffix variations
        # the specific version of mlx_audio decides to append.
        tmp_dir = tempfile.mkdtemp(prefix="jarvis_tts_")
        prefix_path = os.path.join(tmp_dir, "jarvis_speech")

        try:
            # FIXED PARAMETERS: 'model' instead of 'model_path', and 'file_prefix' instead of 'output_path'
            generate_audio(
                model="mlx-community/Kokoro-82M-bf16",
                text=text,
                voice="af_heart",
                file_prefix=prefix_path
            )

            # Find the actual .wav file generated inside our temporary directory
            generated_files = [f for f in os.listdir(tmp_dir) if f.endswith(".wav")]
            if not generated_files:
                logger.error("TTS failed: No audio file was generated in the temp directory.")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return False

            audio_file_path = os.path.join(tmp_dir, generated_files[0])

        except Exception as e:
            logger.error("mlx_audio generate_audio failed: %s", e, exc_info=True)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False

        # macOS-only playback. `afplay` ships with the OS so we
        # don't need to bundle anything. `which` check is cheap and
        # surfaces a clearer error on non-mac dev boxes.
        if shutil.which("afplay") is None:
            logger.warning("afplay not found on PATH — generated WAV at %s", audio_file_path)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False

        try:
            subprocess.run(
                ["afplay", audio_file_path],
                check=True,
                timeout=60,
                capture_output=True,
            )
        except subprocess.TimeoutExpired:
            logger.error("afplay timed out after 60s on %s", audio_file_path)
            return False
        except subprocess.CalledProcessError as e:
            logger.error("afplay failed (rc=%d): %s", e.returncode, e.stderr)
            return False
        finally:
            # Clean up the entire temporary folder and its contents
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return True