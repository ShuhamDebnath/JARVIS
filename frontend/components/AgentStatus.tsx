"use client";

/**
 * AgentStatus — polling panel for Phase 4 Next.js dashboard.
 * Polls GET /workflows/runs every 5 seconds and displays active/completed runs.
 * Reads backend/state/runs.json via the FastAPI /workflows/runs endpoint.
 */
import { useEffect, useState } from "react";
import { fetchWorkflowStatuses, type RunEntry } from "@/lib/api";

export default function AgentStatus() {
  // runs maps run_id (key in runs.json) → RunEntry
  const [runs, setRuns] = useState<Record<string, RunEntry>>({});
  const [polling, setPolling] = useState(true);

  useEffect(() => {
    if (!polling) return;

    async function poll() {
      const data = await fetchWorkflowStatuses();
      setRuns(data);
    }

    poll();
    const interval = setInterval(poll, 5_000);
    return () => clearInterval(interval);
  }, [polling]);

  // Flat list of runs sorted newest-first
  const runEntries = Object.entries(runs).sort(
    ([, a], [, b]) =>
      new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
  );

  return (
    <div className="border border-gray-700 rounded-lg p-4 bg-gray-900 space-y-3">
      {/* Polling toggle */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-300">Workflow Runs</span>
        <button
          onClick={() => setPolling((p) => !p)}
          className={`text-xs px-2 py-1 rounded border ${
            polling
              ? "border-green-600 text-green-400"
              : "border-gray-600 text-gray-500"
          }`}
        >
          {polling ? "Polling" : "Paused"}
        </button>
      </div>

      {/* Run list */}
      {runEntries.length === 0 ? (
        <p className="text-sm text-gray-500 italic">No active workflows</p>
      ) : (
        <div className="space-y-2">
          {runEntries.map(([runId, run]) => {
            const statusColors: Record<string, string> = {
              queued: "bg-blue-400",
              running: "bg-yellow-400 animate-pulse",
              done: "bg-green-400",
              error: "bg-red-400",
            };
            return (
              <div
                key={runId}
                className="flex items-center gap-3 text-sm border-b border-gray-800 pb-2"
              >
                {/* Status dot */}
                <span
                  className={`w-2.5 h-2.5 rounded-full shrink-0 ${statusColors[run.status] ?? "bg-gray-500"}`}
                />
                {/* Run info */}
                <div className="flex-1 min-w-0">
                  <p className="text-gray-200 text-xs font-mono truncate">
                    {run.app_idea ?? run.topic ?? runId}
                  </p>
                  <p className="text-gray-500 text-xs">
                    {run.status} · {new Date(run.started_at).toLocaleTimeString()}
                  </p>
                </div>
                {/* Output file */}
                {run.output_file && (
                  <span className="text-xs text-gray-400 truncate max-w-[120px]">
                    {run.output_file}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}