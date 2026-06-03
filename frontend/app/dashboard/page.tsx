/**
 * Dashboard page — main grid container for all workflow modules.
 * Phase 4 — Frontend Dashboard
 */

import WorkflowCard from "@/components/WorkflowCard";
import AgentStatus from "@/components/AgentStatus";
import OutputViewer from "@/components/OutputViewer";
import ComingSoon from "@/components/ComingSoon";
import VoiceControls from "@/components/VoiceControls";

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <h1 className="text-2xl font-bold text-white">Jarvis OS</h1>
        <p className="text-sm text-gray-400">AI Operating System — Bengaluru, India</p>
      </header>

      <main className="p-6 space-y-8">
        {/* Agent Status Panel */}
        <section>
          <h2 className="text-lg font-semibold mb-3 text-gray-300">Agent Status</h2>
          <AgentStatus />
        </section>

        {/* Voice Layer Controls (Phase 5) */}
        <section>
          <h2 className="text-lg font-semibold mb-3 text-gray-300">Voice Layer</h2>
          <VoiceControls />
        </section>

        {/* Workflow Grid */}
        <section>
          <h2 className="text-lg font-semibold mb-3 text-gray-300">Workflows</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Workflow 1 — UI Design Loop — not yet built */}
            <ComingSoon title="Workflow 1 — UI Design" />

            {/* Workflow 2 — Research → PRD (Phase 1, built) */}
            <WorkflowCard
              id="workflow-2"
              title="Research → PRD"
              description="Market research, competitor analysis, scored PRD output"
              endpoint="/workflows/research/prd"
              phase="1"
            />

            {/* Workflow 3 — Social Content (Phase 3, built) */}
            <WorkflowCard
              id="workflow-3"
              title="Social Content"
              description="Content briefs and auto-posting to social platforms"
              endpoint="/workflows/social/briefs"
              phase="3"
            />

            {/* Workflow 4 — App Store Intelligence (Phase 2, built) */}
            <WorkflowCard
              id="workflow-4"
              title="App Store Intelligence"
              description="Competitor analysis, ranked lists, top complaints"
              endpoint="/workflows/app-store"
              phase="2"
            />

            {/* Workflows 5–10 — not yet built */}
            <ComingSoon title="Workflow 5 — Competitor Teardown" />
            <ComingSoon title="Workflow 6 — Content Pipeline" />
            <ComingSoon title="Workflow 7 — Morning Briefing" />
            <ComingSoon title="Workflow 8 — Mac Automation" />
            <ComingSoon title="Workflow 9 — ASO Optimiser" />
            <ComingSoon title="Workflow 10 — Reddit Monitor" />
          </div>
        </section>

        {/* Output Viewer */}
        <section>
          <h2 className="text-lg font-semibold mb-3 text-gray-300">Output Viewer</h2>
          <OutputViewer />
        </section>
      </main>
    </div>
  );
}