"use client";

/**
 * OutputViewer — scrollable markdown viewer for Phase 4 Next.js dashboard.
 * Loads .md files from backend/output/ via GET /output/{filename}
 * and renders them using react-markdown with Tailwind typography.
 */
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { fetchOutput } from "@/lib/api";

export default function OutputViewer() {
  const [filenameInput, setFilenameInput] = useState("");
  const [markdownContent, setMarkdownContent] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleLoad() {
    const trimmed = filenameInput.trim();
    if (!trimmed) return;

    setIsLoading(true);
    setErrorMessage(null);
    setMarkdownContent(null);

    try {
      const content = await fetchOutput(trimmed);
      setMarkdownContent(content);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to load file");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="border border-gray-700 rounded-lg p-4 bg-gray-900 space-y-4">
      {/* File selector row */}
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="filename.md (e.g. PRD_habittracker_2026-06-03.md)"
          value={filenameInput}
          onChange={(e) => setFilenameInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLoad()}
          className="flex-1 bg-gray-950 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500"
        />
        <button
          onClick={handleLoad}
          disabled={isLoading || !filenameInput.trim()}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-sm text-white rounded transition-colors"
        >
          {isLoading ? "Loading..." : "Load"}
        </button>
      </div>

      {/* Error state */}
      {errorMessage && (
        <div className="p-3 bg-red-900/30 border border-red-800 rounded text-sm text-red-300">
          {errorMessage}
        </div>
      )}

      {/* Markdown content — scrollable container */}
      {markdownContent !== null && (
        <div className="max-h-[600px] overflow-y-auto rounded border border-gray-800 bg-gray-950 p-4">
          <ReactMarkdown
            className="prose prose-invert prose-sm max-w-none
                       prose-headings:text-gray-100
                       prose-p:text-gray-300
                       prose-strong:text-white
                       prose-code:text-cyan-300
                       prose-link:text-blue-400
                       prose-ul:text-gray-300
                       prose-li:text-gray-300
                       prose-hr:border-gray-700"
          >
            {markdownContent}
          </ReactMarkdown>
        </div>
      )}

      {/* Empty state */}
      {!markdownContent && !errorMessage && (
        <p className="text-sm text-gray-500 italic">
          Enter a filename above and click Load to preview output.
        </p>
      )}
    </div>
  );
}