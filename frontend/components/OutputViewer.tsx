"use client";

/**
 * OutputViewer — scrollable markdown viewer for Phase 4 Next.js dashboard.
 * Loads .md files from backend/output/ via GET /output/{filename}
 * and renders them using react-markdown with styled output.
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

      {/* Markdown content — scrollable container with dark-theme styling */}
      {markdownContent !== null && (
        <div
          className="max-h-[600px] overflow-y-auto rounded border border-gray-800 bg-gray-950 p-4 text-sm"
          style={{ fontFamily: "Arial, Helvetica, sans-serif" }}
        >
          <ReactMarkdown
            components={{
              // Headings
              h1: ({ children }) => (
                <h1 className="text-xl font-bold text-gray-100 mt-0 mb-3">{children}</h1>
              ),
              h2: ({ children }) => (
                <h2 className="text-lg font-semibold text-gray-100 mt-0 mb-2">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-base font-medium text-gray-200 mt-0 mb-2">{children}</h3>
              ),
              // Paragraphs and text
              p: ({ children }) => (
                <p className="text-gray-300 mb-3 leading-relaxed">{children}</p>
              ),
              // Strong and emphasis
              strong: ({ children }) => (
                <strong className="text-white font-semibold">{children}</strong>
              ),
              em: ({ children }) => (
                <em className="text-gray-200 italic">{children}</em>
              ),
              // Code blocks and inline code
              code: ({ children, className }) => {
                const isBlock = className?.includes("language-");
                return isBlock ? (
                  <code className="block bg-gray-900 text-cyan-300 text-xs rounded p-3 overflow-x-auto my-3 font-mono">
                    {children}
                  </code>
                ) : (
                  <code className="text-cyan-300 text-xs bg-gray-900 px-1 rounded">
                    {children}
                  </code>
                );
              },
              pre: ({ children }) => (
                <pre className="bg-gray-900 text-cyan-300 text-xs rounded p-3 overflow-x-auto my-3 font-mono">
                  {children}
                </pre>
              ),
              // Lists
              ul: ({ children }) => (
                <ul className="text-gray-300 mb-3 pl-5 list-disc space-y-1">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="text-gray-300 mb-3 pl-5 list-decimal space-y-1">{children}</ol>
              ),
              li: ({ children }) => (
                <li className="text-gray-300">{children}</li>
              ),
              // Blockquotes
              blockquote: ({ children }) => (
                <blockquote className="border-l-4 border-gray-600 pl-4 text-gray-400 italic my-3">
                  {children}
                </blockquote>
              ),
              // Horizontal rule
              hr: () => <hr className="border-gray-700 my-4" />,
              // Links
              a: ({ href, children }) => (
                <a href={href} className="text-blue-400 hover:text-blue-300 underline" target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
            }}
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