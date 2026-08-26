/**
 * Live tool-status pills — "checking policy…", "searching flights…".
 *
 * The wording is server-authored (from the tool schema), never the raw `snake_case` tool name and
 * never the model narrating its own routing. Each pill carries a pulsing dot so an in-flight step
 * reads as activity rather than a static label.
 */
export interface Pill {
  id: string;
  label: string;
}

export function ToolPills({ pills }: { pills: Pill[] }) {
  if (pills.length === 0) return null;
  return (
    <div className="pills" aria-live="polite">
      {pills.map((pill) => (
        <span key={pill.id} className="pill">
          <span className="pill-dot" aria-hidden="true" />
          {pill.label}…
        </span>
      ))}
    </div>
  );
}
