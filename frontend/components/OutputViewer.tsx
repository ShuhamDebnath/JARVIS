"use client";

/**
 * OutputViewer — scrollable markdown viewer for rendered reports and briefs.
 * Loads content from /output/{filename} endpoint and renders markdown.
 */
import { useState } from "react";
import { api } from "@/lib/api";

export default function OutputViewer() {
  const [filename, setFilename] = useState("");
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLoad() {
    if (!filename.trim()) return;
    setLoading(true);
    setError(null);
    setContent(null);

    try {
      const data = await api.get<{ content: string }>(
        `/output/${encodeURIComponent(filename.trim())}`
      );
      setContent(data.content ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load file");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
      {/* File selector row */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="filename.md (e.g. PRD_habittracker_2026-06-03.md)"
          value={filename}
          onChange={(e) => setFilename(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLoad()}
          className="flex-1 bg-gray-950 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500"
        />
        <button
          onClick={handleLoad}
          disabled={loading || !filename.trim()}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-sm text-white rounded transition-colors"
        >
          {loading ? "Loading..." : "Load"}
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-800 rounded text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Content */}
      {content !== null && (
        <div className="prose prose-invert prose-sm max-w-none">
          {/* Simple markdown rendering — block paragraphs */}
          {content.split("\n\n").map((para, i) => (
            <p key={i} className="text-gray-300 mb-3 leading-relaxed">
              {para}
            </p>
          ))}
        </div>
      )}

      {!content && !error && (
        <p className="text-sm text-gray-500 italic">
          Enter a filename above and click Load to preview output.
        </p>
      )}
    </div>
  );
}