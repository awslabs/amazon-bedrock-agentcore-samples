/**
 * The scrolling conversation column.
 *
 * Owns the coarse auto-scroll for a new turn and tool-state changes. The streaming prose component
 * follows its own text so completing a reply cannot jump the viewport down into a tall card grid.
 * When there are no turns it shows the welcome hero instead.
 */
import { useEffect, useRef } from 'react';
import type { CardAction } from '../../../shared/generated/cards';
import type { StreamedTextStore } from '../lib/streamedText';
import type { Pill, Turn as TurnData } from '../lib/useConversation';
import { Turn } from './Turn';
import { Welcome } from './Welcome';

export interface TranscriptProps {
  turns: TurnData[];
  pills: Pill[];
  busy: boolean;
  onAction: (action: CardAction, cardId?: string) => void;
  onPick: (prompt: string) => void;
  streamedText: StreamedTextStore;
  /** Card actions already used, passed down to every card's buttons. */
  spentActions?: ReadonlySet<string>;
}

export function Transcript({
  turns,
  pills,
  busy,
  onAction,
  onPick,
  streamedText,
  spentActions,
}: TranscriptProps) {
  const tail = useRef<HTMLDivElement>(null);
  useEffect(() => {
    tail.current?.scrollIntoView({ block: 'end' });
  }, [turns.length, pills.length]);

  if (turns.length === 0) {
    return (
      <section className="transcript">
        <div className="column">
          <Welcome onPick={onPick} />
        </div>
      </section>
    );
  }

  return (
    <section className="transcript">
      <div className="column">
        {turns.map((turn, index) => {
          const isLast = index === turns.length - 1;
          const active = isLast && busy && turn.role === 'assistant';
          return (
            <Turn
              key={index}
              turn={turn}
              onAction={onAction}
              busy={busy}
              spentActions={spentActions}
              active={active}
              pills={active ? pills : []}
              streamedText={active ? streamedText : undefined}
            />
          );
        })}
        <div ref={tail} />
      </div>
    </section>
  );
}
