/**
 * The composer: a floating, rounded chatbox rather than a full-width bar welded to the window edge.
 *
 * The textarea grows with its content up to a cap, Enter sends and Shift+Enter makes a newline — the
 * interaction people now expect from a chat surface. Sending is a round icon button that only lights
 * up when there is something to send and the previous turn has finished.
 */
import { useLayoutEffect, useRef, useState } from 'react';
import { SendIcon } from './icons';

export interface ComposerProps {
  busy: boolean;
  onSend: (text: string) => void;
}

const MAX_HEIGHT = 200;

export function Composer({ busy, onSend }: ComposerProps) {
  const [draft, setDraft] = useState('');
  const textarea = useRef<HTMLTextAreaElement>(null);

  // Grow to fit content, then scroll. Measured against a reset height so it also shrinks when text is
  // deleted, which a one-way `scrollHeight` grow does not.
  useLayoutEffect(() => {
    const el = textarea.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [draft]);

  const submit = () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft('');
    onSend(text);
  };

  const canSend = draft.trim().length > 0 && !busy;

  return (
    <div className="composer-wrap">
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <textarea
          ref={textarea}
          className="composer-input"
          value={draft}
          rows={1}
          placeholder="Ask about your trips, policy, or book something…"
          disabled={busy}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <button
          type="submit"
          className="composer-send"
          disabled={!canSend}
          aria-label="Send message"
        >
          <SendIcon size={18} />
        </button>
      </form>
      <p className="composer-hint">
        This assistant acts as the traveller you are signed in as. Verify important details before
        you travel.
      </p>
    </div>
  );
}
