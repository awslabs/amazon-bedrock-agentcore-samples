/**
 * One exchange in the transcript.
 *
 * The traveller's line is a compact bubble on the right; the assistant's is full width with the
 * the assistant mark beside it, the way a person reads a reply rather than a chat bubble. Cards render
 * below the prose. Text is rendered as text (never markup) with whitespace preserved — the model
 * authors words, never HTML.
 */
import type { CardAction } from '../../../shared/generated/cards';
import type { StreamedTextStore } from '../lib/streamedText';
import type { Pill, Turn as TurnData } from '../lib/useConversation';
import { CardView } from '../cards/CardView';
import { Logomark } from './Brand';
import { Markdown } from './Markdown';
import { StreamingMarkdown } from './StreamingMarkdown';
import { ToolPills } from './ToolPills';
import { Typing } from './Typing';

export interface TurnProps {
  turn: TurnData;
  onAction: (action: CardAction, cardId?: string) => void;
  busy: boolean;
  /** Card actions already used, so a spent button renders as a record rather than an invitation. */
  spentActions?: ReadonlySet<string>;
  /** True for the last turn while a reply is in flight, so it shows the working indicator. */
  active?: boolean;
  /** Tools currently running, shown as named pills on the active turn. */
  pills?: Pill[];
  /** The independently-rendered prose for the active streamed response. */
  streamedText?: StreamedTextStore;
}

export function Turn({
  turn,
  onAction,
  busy,
  spentActions,
  active = false,
  pills = [],
  streamedText,
}: TurnProps) {
  if (turn.role === 'traveller') {
    return (
      <div className="turn traveller">
        <div className="bubble">{turn.text}</div>
      </div>
    );
  }

  return (
    <div className="turn assistant">
      <span className="turn-avatar" aria-hidden="true">
        <Logomark size={26} />
      </span>
      <div className="turn-body">
        {active && streamedText ? (
          <StreamingMarkdown store={streamedText} />
        ) : turn.text ? (
          <Markdown className="prose" text={turn.text} />
        ) : null}

        {turn.failure && <p className="note">{turn.failure}</p>}

        {turn.guardrail && (
          <p className="note">
            I stopped that answer because of a content check ({turn.guardrail.join(', ')}).
          </p>
        )}

        {turn.cards.length > 0 && (
          <div className="cards">
            {turn.cards.map((card) => (
              <CardView
                key={card.id}
                card={card}
                onAction={onAction}
                busy={busy}
                spent={spentActions}
              />
            ))}
          </div>
        )}

        {/* One activity cue at a time: a named pill while a tool runs, otherwise the typing dots
            for the quiet stretches (before the first token, and after a tool while composing). */}
        {active && (pills.length > 0 ? <ToolPills pills={pills} /> : <Typing />)}
      </div>
    </div>
  );
}
