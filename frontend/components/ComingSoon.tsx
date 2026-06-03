/**
 * ComingSoon — generic fallback block for unbuilt workflows.
 * Rendered in disabled state with a lock icon.
 */
interface ComingSoonProps {
  title: string;
}

export default function ComingSoon({ title }: ComingSoonProps) {
  return (
    <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/50 opacity-60">
      <div className="flex items-center gap-2 mb-2">
        {/* Lock icon (SVG inline) */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="w-4 h-4 text-gray-500"
        >
          <path
            fillRule="evenodd"
            d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z"
            clipRule="evenodd"
          />
        </svg>
        <span className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
          Coming Soon
        </span>
      </div>
      <h3 className="font-medium text-gray-400">{title}</h3>
      <p className="text-xs text-gray-600 mt-1">Not yet built — see roadmap</p>
    </div>
  );
}