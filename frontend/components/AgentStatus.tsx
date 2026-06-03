"use client";

/**
 * AgentStatus — persistent polling panel tracking background crew execution.
 * Polls GET /status every 10 seconds and shows active agents + last run summary.
 */
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface AgentInfo {
  name: string;
  status: "idle" | "busy" | "done" | "error";
  last_run?: string;
}

interface RunSummary {
  workflow: string;
  started_at: string;
  duration_s?: number;
  output_file?: string;
}

export default function AgentStatus() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [lastRun, setLastRun] = useState<RunSummary | null>(null);
  const [polling, setPolling] = useState(true);

  useEffect(() => {
    if (!polling) return;

    async function fetchStatus() {
      try {
        const data = await api.get<{
          agents: AgentInfo[];
          last_run?: RunSummary;
        }>("/status");

        setAgents(data.agents ?? []);
        if (data.last_run) setLastRun(data.last_run);
      } catch {
        // Silently ignore polling errors — dashboard should stay up
      }
    }

    fetchStatus();
    const interval = setInterval(fetchStatus, 10_000);
    return () => clearInterval(interval);
  }, [polling]);

  return (
    <div className="border border-gray-700 rounded-lg p-4 bg-gray-900 space-y-3">
      {/* Polling toggle */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-300">Live Agent Monitor</span>
        <button
          onClick={() => setPolling((p) => !p)}
          className={`text-xs px-2 py-1 rounded border ${
            polling ? "border-green-600 text-green-400" : "border-gray-600 text-gray-500"
          }`}
        >
          {polling ? "Polling" : "Paused"}
        </button>
      </div>

      {/* Agent list */}
      {agents.length === 0 ? (
        <p className="text-sm text-gray-500 italic">No active agents — system idle</p>
      ) : (
        <div className="space-y-2">
          {agents.map((agent) => (
            <div key={agent.name} className="flex items-center gap-3 text-sm">
              <span
                className={`w-2 h-2 rounded-full ${
                  agent.status === "busy"
                    ? "bg-yellow-400 animate-pulse"
                    : agent.status === "done"
                    ? "bg-green-400"
                    : agent.status === "error"
                    ? "bg-red-400"
                    : "bg-gray-500"
                }`}
              />
              <span className="text-gray-200 font-mono text-xs">{agent.name}</span>
              <span className="text-gray-500 text-xs ml-auto">{agent.status}</span>
            </div>
          ))}
        </div>
      )}

      {/* Last run summary */}
      {lastRun && (
        <div className="border-t border-gray-800 pt-3 mt-2">
          <p className="text-xs text-gray-400">
            Last run: <span className="text-white">{lastRun.workflow}</span> at{" "}
            {new Date(lastRun.started_at).toLocaleTimeString()}
            {lastRun.duration_s != null && ` · ${lastRun.duration_s}s`}
            {lastRun.output_file && (
              <>
                <br />
                Output: <span className="text-gray-300">{lastRun.output_file}</span>
              </>
            )}
          </p>
        </div>
      )}
    </div>
  );
}