import { useState } from "react";
import type { Step } from "../types";

/** The agent's progress: live while it works, then collapsed to a one-line summary. */
export function Steps({ steps, running, durationMs }: { steps: Step[]; running: boolean; durationMs?: number }) {
  const [open, setOpen] = useState(false);
  const expanded = running || open;

  return (
    <div className="steps">
      {!running && (
        <button className="steps-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <span className={`chevron ${open ? "open" : ""}`}>›</span>
          {steps.length} steps{durationMs ? ` · ${(durationMs / 1000).toFixed(1)}s` : ""}
          {routeOf(steps) && <span className="route">{routeOf(steps)}</span>}
        </button>
      )}
      {expanded && (
        <ol>
          {steps.map((step, i) => (
            <li key={i}>
              <span className="tick">✓</span>
              <span>{step.label}</span>
            </li>
          ))}
          {running && (
            <li className="pending">
              <span className="spinner" aria-hidden />
              <span>{nextActivity(steps[steps.length - 1])}</span>
            </li>
          )}
        </ol>
      )}
    </div>
  );
}

function routeOf(steps: Step[]): string | undefined {
  return steps.find((s) => s.node === "router")?.route;
}

/** We only hear about a step once it has finished, so guess what the agent is doing now. */
function nextActivity(last: Step | undefined): string {
  if (!last) return "Understanding the question…";
  switch (last.node) {
    case "router":
      return last.route === "retrieve" ? "Searching the documents…" : "Writing a reply…";
    case "retrieve":
      return "Checking which passages are relevant…";
    case "grade":
      return last.label.startsWith("No relevant") ? "Rephrasing the search…" : "Writing the answer…";
    case "rewrite":
      return "Searching again…";
    case "generate":
    case "respond":
      return last.tool_calls ? `Running ${last.tool_calls.map((c) => c.name).join(", ")}…` : "Finishing…";
    case "tools":
      return "Writing the answer…";
    default:
      return "Working…";
  }
}
