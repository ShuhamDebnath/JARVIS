/**
 * lib/api.ts — Fetch API networking client for FastAPI backend.
 * All HTTP calls to Jarvis backend go through here.
 * Error handling: throws a typed Error with the response body as the message.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${BASE_URL}${path}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    // Try to parse error envelope from FastAPI
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.error) message = body.error;
      if (body?.hint) message += ` | Hint: ${body.hint}`;
    } catch {
      // Not JSON — use status text
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const api = {
  /**
   * GET — fetch data from a backend route.
   * @example await api.get<{phase: string}>("/health")
   */
  get<T>(path: string): Promise<T> {
    return request<T>(path, { method: "GET" });
  },

  /**
   * POST — trigger a workflow or send data.
   * @example await api.post<HelloOutput>("/crews/hello", { name: "Jarvis" })
   */
  post<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
};

// ---------------------------------------------------------------------------
// Phase 4 — Status Polling (Next.js dashboard → FastAPI)
// ---------------------------------------------------------------------------

/**
 * fetchWorkflowStatuses — polls GET /workflows/runs for active run state.
 * Reads backend/state/runs.json and returns the JSON payload.
 * Logs errors to console instead of crashing the app.
 */
export async function fetchWorkflowStatuses(): Promise<Record<string, RunEntry>> {
  try {
    const data = await request<Record<string, RunEntry>>("/workflows/runs");
    return data;
  } catch (err) {
    // Graceful degradation — log and return empty object so dashboard stays up
    console.error("[AgentStatus] Failed to fetch workflow statuses:", err);
    return {};
  }
}

/** Shape of a single run entry inside runs.json */
export interface RunEntry {
  status: "queued" | "running" | "done" | "error";
  app_idea?: string;
  topic?: string;
  started_at: string;
  completed_at?: string;
  output_file?: string;
  error_message?: string;
}

// ---------------------------------------------------------------------------
// Phase 4 — Output Viewer (Next.js dashboard → FastAPI)
// ---------------------------------------------------------------------------

/**
 * fetchOutput — retrieves a markdown file from backend/output/ via the
 * FastAPI GET /output/{filename} endpoint.
 * @param filename  The name of the file (e.g. "PRD_habittracker_2026-06-03.md")
 * @returns The file content string
 * @throws Error if the file is not found or the request fails
 */
export async function fetchOutput(filename: string): Promise<string> {
  const data = await request<{ filename: string; content: string }>(
    `/output/${encodeURIComponent(filename)}`
  );
  return data.content;
}