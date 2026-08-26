/**
 * The "assistant is working" indicator — three bouncing dots.
 *
 * Shown whenever a turn is in flight and no tool pill is currently up: it fills the quiet gaps the
 * user would otherwise read as a stall — before the first token, and after a tool finishes while the
 * model composes its reply. When a tool is actually running, the named pill ("checking policy…") is
 * shown instead, because that says more than a generic dot.
 */
export function Typing() {
  return (
    <div className="typing" role="status" aria-label="Assistant is typing">
      <span />
      <span />
      <span />
    </div>
  );
}
