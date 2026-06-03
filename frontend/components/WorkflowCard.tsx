"use client";

/**
 * WorkflowCard — atomic component to trigger and track backend workflow runs.
 * Props:
 *   id          — unique workflow identifier (e.g. "workflow-2")
 *   title       — display name
 *   description — one-liner explaining what the workflow does
 *   endpoint    — FastAPI route path to call
 *   phase       — Jarvis phase number this workflow belongs to
 */
import { useState } from "react";
import { api } from "@/lib/api";

interface WorkflowCardProps {
  id: string;
  title: string;
  description: string;
  endpoint: string;
  phase: string;
}

type RunStatus = "idle" | "running" | "success" | "error";

export default function WorkflowCard({
  id,
  title,
  description,
  endpoint,
  phase,
}: WorkflowCardProps) {
  const [status, setStatus] = useState<RunStatus>("idle");
  const [lastResult, setLastResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleTrigger() {
    setLoading(true);
    setStatus("running");
    setLastResult(null);

    try {
      const data = await api.post(endpoint, {});
      setLastResult(JSON.stringify(data, null, 2));
      setStatus("success");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setLastResult(message);
      setStatus("error");
    } finally {
      setLoading(false);
    }
  }

  const statusColors: Record<RunStatus, string> = {
    idle: "bg-gray-700",
    running: "bg-yellow-600 animate-pulse",
    success: "bg-green-600",
    error: "bg-red-600",
  };

  return (
    <div className="border border-gray-700 rounded-lg p-4 bg-gray-900 hover:border-gray-600 transition-colors">
      {/* Header row */}
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="font-semibold text-white">{title}</h3>
          <p className="text-xs text-gray-400 mt-0.5">Phase {phase}</p>
        </div>
        {/* Status dot */}
        <span
          className={`w-3 h-3 rounded-full mt-1 shrink-0 ${statusColors[status]}`}
          title={status}
        />
      </div>

      <p className="text-sm text-gray-400 mb-4">{description}</p>

      {/* Trigger button */}
      <button
        onClick={handleTrigger}
        disabled={loading || status === "running"}
        className="w-full py-2 px-4 rounded bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-sm font-medium text-white transition-colors"
      >
        {loading || status === "running" ? "Running..." : "Run Workflow"}
      </button>

      {/* Last result (collapsed by default) */}
      {lastResult && (
        <details className="mt-3">
          <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-400">
            Last result
          </summary>
          <pre className="mt-2 p-2 bg-gray-950 rounded text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
            {lastResult.length > 500 ? lastResult.slice(0, 500) + "..." : lastResult}
          </pre>
        </details>
      )}
    </div>
  );
}