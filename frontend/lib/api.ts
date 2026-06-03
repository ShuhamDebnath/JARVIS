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