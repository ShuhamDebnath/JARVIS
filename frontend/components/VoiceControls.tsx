"use client";

/**
 * VoiceControls — Phase 5 dashboard panel.
 *
 * Renders 3 hardware-aware toggles that map 1:1 onto the
 * `voice_core.update_settings()` knobs in the FastAPI backend:
 *
 *   1. Wake Word Monitoring → mic_enabled
 *        Starts/stops the background Silero-VAD + mlx-whisper loop.
 *        While ON, the global `voice_core` spawns a daemon thread
 *        that opens the macOS microphone.
 *
 *   2. Spoken Responses → tts_enabled
 *        When ON, mlx-audio (Kokoro-82M-bf16) synthesises the
 *        reply and `afplay` plays it. When OFF, responses stay
 *        on screen only — the mic can still listen.
 *
 *   3. Auto-Execute Actions → auto_execute
 *        When ON, a parsed command (e.g. "research habit tracker")
 *        immediately fires the matched crew. When OFF, the parsed
 *        command is staged on the dashboard for manual human
 *        safety confirmation. Default OFF per safety policy.
 *
 * The component is intentionally dumb: it fetches the snapshot on
 * mount, fires a PATCH on every flip, and renders three <ToggleRow>
 * children. All state lives in the backend; the local React state
 * is just a render cache.
 */

import { useCallback, useEffect, useState } from "react";
import {
  fetchVoiceSettings,
  updateVoiceSettings,
  type VoiceSettings,
  type VoiceSettingsUpdate,
} from "@/lib/api";

type ToggleKey = "mic_enabled" | "tts_enabled" | "auto_execute";

interface ToggleSpec {
  /** Backend key for this toggle (snake_case — matches FastAPI). */
  key: ToggleKey;
  /** Short human-readable label shown next to the switch. */
  label: string;
  /** Longer description shown below the label (1 line). */
  description: string;
}

// The 3 toggles in display order. The order mirrors the safety
// flow: first the user chooses whether the mic is on at all,
// then whether replies are spoken, then whether commands run
// without confirmation.
const TOGGLES: readonly ToggleSpec[] = [
  {
    key: "mic_enabled",
    label: "Wake Word Monitoring",
    description:
      "Triggers the microphone stream + Silero-VAD gatekeeper. The local MLX voice loop runs while this is on.",
  },
  {
    key: "tts_enabled",
    label: "Spoken Responses",
    description:
      "When on, Kokoro (mlx-audio) speaks replies through the speakers. When off, replies stay on screen only.",
  },
  {
    key: "auto_execute",
    label: "Auto-Execute Actions",
    description:
      "When on, matched workflows run immediately. When off, parsed commands are staged for manual confirmation.",
  },
] as const;

const DEFAULT_SETTINGS: VoiceSettings = {
  mic_enabled: false,
  tts_enabled: true,
  auto_execute: false,
  is_listening: false,
};

export default function VoiceControls() {
  // Render cache of the backend's voice-toggle snapshot. The
  // `undefined` "loading" state is rendered as a neutral skeleton
  // so the panel does not flash its defaults before the first
  // fetch resolves.
  const [settings, setSettings] = useState<VoiceSettings | undefined>(
    undefined
  );
  // Per-toggle in-flight flag so we can disable a switch while
  // its PATCH is in flight (prevents double-flip on a fast user).
  const [pending, setPending] = useState<Record<ToggleKey, boolean>>({
    mic_enabled: false,
    tts_enabled: false,
    auto_execute: false,
  });
  // Last error from a fetch or PATCH. Shown above the toggles
  // so the operator can see what went wrong without opening
  // devtools.
  const [error, setError] = useState<string | null>(null);

  // Initial fetch — runs once on mount. We do NOT poll: the
  // backend reflects our own PATCHes synchronously, and the only
  // thing that could change `is_listening` without our action is
  // a hardware fault inside the listener thread, which already
  // logs to jarvis.log.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchVoiceSettings();
        if (!cancelled) setSettings(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          // Render the safety defaults so the panel is still usable
          // while the backend is unreachable.
          setSettings(DEFAULT_SETTINGS);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Fire-and-forget PATCH. We optimistically update the render
  // cache from the patch itself (so the switch flips immediately),
  // then reconcile with the authoritative snapshot the backend
  // returns. If the PATCH fails, we roll back to the previous
  // snapshot and surface the error.
  const onFlip = useCallback(
    async (key: ToggleKey, nextValue: boolean) => {
      const previous = settings;
      if (previous === undefined) return;
      // Optimistic update — instant switch flip.
      setSettings({ ...previous, [key]: nextValue });
      setPending((p) => ({ ...p, [key]: true }));
      setError(null);
      try {
        const patch: VoiceSettingsUpdate = { [key]: nextValue };
        const fresh = await updateVoiceSettings(patch);
        setSettings(fresh);
      } catch (err) {
        // Roll back on failure so the UI never lies about the
        // real backend state.
        if (previous) setSettings(previous);
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setPending((p) => ({ ...p, [key]: false }));
      }
    },
    [settings]
  );

  const isReady = settings !== undefined;

  return (
    <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
      {/* Header row */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-semibold text-white">Voice Layer</h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Phase 5 — local MLX stack (Silero-VAD + mlx-whisper + Kokoro)
          </p>
        </div>
        {/* Live indicator dot — green when the mic thread is alive. */}
        <span
          className={`w-3 h-3 rounded-full shrink-0 ${
            settings?.is_listening
              ? "bg-green-500 animate-pulse"
              : "bg-gray-600"
          }`}
          title={settings?.is_listening ? "Listening" : "Idle"}
          aria-label={
            settings?.is_listening
              ? "Voice listener is active"
              : "Voice listener is idle"
          }
        />
      </div>

      {/* Error banner — only renders when a fetch/PATCH failed. */}
      {error && (
        <div className="mb-3 p-2 rounded border border-red-700 bg-red-950 text-xs text-red-200">
          {error}
        </div>
      )}

      {/* Toggle rows. Skeleton during initial fetch. */}
      {TOGGLES.map((t) => (
        <ToggleRow
          key={t.key}
          spec={t}
          value={isReady ? Boolean(settings?.[t.key]) : false}
          disabled={!isReady || pending[t.key]}
          onChange={(next) => onFlip(t.key, next)}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ToggleRow — single switch + label + description.
// ---------------------------------------------------------------------------

interface ToggleRowProps {
  spec: ToggleSpec;
  value: boolean;
  disabled: boolean;
  onChange: (next: boolean) => void;
}

function ToggleRow({ spec, value, disabled, onChange }: ToggleRowProps) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-t border-gray-800 first:border-t-0 first:pt-0">
      <div className="flex-1 min-w-0">
        <label
          htmlFor={`toggle-${spec.key}`}
          className="text-sm font-medium text-gray-200"
        >
          {spec.label}
        </label>
        <p className="text-xs text-gray-500 mt-0.5">{spec.description}</p>
      </div>
      <button
        id={`toggle-${spec.key}`}
        type="button"
        role="switch"
        aria-checked={value}
        aria-label={spec.label}
        disabled={disabled}
        onClick={() => onChange(!value)}
        className={`
          relative inline-flex h-6 w-11 shrink-0 items-center rounded-full
          transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500
          focus:ring-offset-2 focus:ring-offset-gray-900
          ${value ? "bg-blue-600" : "bg-gray-700"}
          ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
        `}
      >
        <span
          className={`
            inline-block h-4 w-4 transform rounded-full bg-white transition-transform
            ${value ? "translate-x-6" : "translate-x-1"}
          `}
        />
      </button>
    </div>
  );
}
