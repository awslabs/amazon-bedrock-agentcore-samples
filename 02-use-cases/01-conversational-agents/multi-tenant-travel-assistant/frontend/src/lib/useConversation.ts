/**
 * Conversation state, driven entirely by the event stream.
 *
 * **The stream is the state machine.** `text` appends to the answer in progress, `tool_start` and
 * `tool_end` open and close a status pill, `guardrail` explains why an answer stopped, `done` carries
 * usage. Nothing here polls, and nothing derives state from a completed response — which is what
 * makes the UI update as the agent works rather than after it finishes.
 *
 * Cards are available as soon as the tool returns, before the model has narrated what they mean.
 * They are held on the active turn until `done`, so the reply reads as prose followed by its
 * actionable evidence instead of tiles appearing in an otherwise blank answer.
 */
import { useCallback, useRef, useState } from 'react';
import type { Card, CardAction } from '../../../shared/generated/cards';
import { newConversationId, sendTurn, StreamTransportError, type StreamEvent } from './api';
import { StreamedTextStore } from './streamedText';

export interface Turn {
  role: 'traveller' | 'assistant';
  text: string;
  /** Tool cards collected while the model is still composing; never rendered directly. */
  pendingCards?: Card[];
  cards: Card[];
  /** Categories a content guardrail blocked on, if it intervened. */
  guardrail?: string[];
  /** A transport failure after any useful prose; rendered as a note, never by recolouring the reply. */
  failure?: string;
  /** Present once the turn is complete. */
  usage?: Record<string, number>;
}

/** A tool currently running, as the UI shows it. */
export interface Pill {
  id: string;
  label: string;
}

export function useConversation() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [pills, setPills] = useState<Pill[]>([]);
  const [busy, setBusy] = useState(false);
  // A stable external store means text chunks repaint the active prose, not every completed turn.
  const streamedText = useRef(new StreamedTextStore()).current;
  // Stable for the life of the tab: the runtime keys conversation memory on it, so regenerating per
  // turn would silently start a new conversation on every message.
  const conversationId = useRef(newConversationId());
  /**
   * Card actions already used, as `"<cardId>:<actionId>"`.
   *
   * **Keyed per card, not per action**, because one conversation holds several cards offering the
   * same action — every hotel option has `select_hotel`, so keying on the action alone would grey
   * out all five after one click.
   */
  const [spentActions, setSpentActions] = useState<ReadonlySet<string>>(() => new Set());

  const run = useCallback(
    async (
      display: string | null,
      body: { prompt: string } | { action_id: string; payload?: Record<string, unknown> },
    ): Promise<boolean> => {
      streamedText.reset();
      setBusy(true);
      setPills([]);
      // **`display: null` appends no traveller bubble, which is how a click stops pretending to be a
      // message.** Nobody typed "Selected that hotel" — it was a UI state change wearing a message's
      // clothes, and the card's own state is where that belongs. A typed turn still passes its text.
      setTurns((previous) => [
        ...previous,
        ...(display === null ? [] : [{ role: 'traveller' as const, text: display, cards: [] }]),
        { role: 'assistant' as const, text: '', cards: [] },
      ]);

      // Patches metadata and the final answer onto the tail. Streaming prose deliberately stays in
      // `streamedText` until the turn completes, so this does not re-render the transcript per chunk.
      const patch = (change: (turn: Turn) => Turn) =>
        setTurns((previous) => {
          const next = [...previous];
          next[next.length - 1] = change(next[next.length - 1]);
          return next;
        });

      // Tracks whether a tool ran since the last text chunk. The model narrates, calls a tool, then
      // resumes with a fresh sentence — and the two text runs arrive glued ("information.Your")
      // because the second carries no leading space. A separator is inserted *only* at that
      // boundary; mid-word stream splits have no tool between them, so they are never touched.
      const flow = { resumedAfterTool: false };
      let receivedDone = false;
      let finalUsage: Record<string, number> | undefined;

      try {
        for await (const event of sendTurn(conversationId.current, body)) {
          if (event.type === 'done') {
            receivedDone = true;
            finalUsage = event.usage;
            continue;
          }
          apply(event, patch, setPills, flow, streamedText);
        }

        if (receivedDone) {
          // Do not let `done` turn a coalesced final event into an on-screen dump. Once the prose has
          // visibly drained, the cards are promoted below it in one atomic completed-turn update.
          const text = await settleStreamedText(streamedText);
          patch((turn) => ({
            ...turn,
            text,
            cards: [...turn.cards, ...(turn.pendingCards ?? [])],
            pendingCards: undefined,
            usage: finalUsage,
          }));
        }
      } catch (error) {
        // A dropped connection mid-stream. Reported on the turn rather than thrown, because the
        // partial answer above it is still real and should stay visible. Other exceptions are not
        // mislabelled as network failures: they need their actual diagnostic in development.
        const isTransportFailure = error instanceof StreamTransportError;
        if (!isTransportFailure) {
          console.error('Could not process a conversation stream event.', error);
        }
        patch((turn) => ({
          ...turn,
          text: streamedText.flush(),
          failure: isTransportFailure
            ? 'The response connection closed before the reply finished.'
            : 'Part of this reply could not be displayed. Please try again.',
        }));
      } finally {
        // A terminal error can arrive after a successful search. Those cards are still valid facts,
        // so never make their visibility depend on a `done` event that the failed stream cannot send.
        if (!receivedDone) {
          patch((turn) => ({
            ...turn,
            text: streamedText.flush(),
            cards: [...turn.cards, ...(turn.pendingCards ?? [])],
            pendingCards: undefined,
          }));
        }
        setBusy(false);
        setPills([]);
      }
      // **Whether the turn completed, so a caller can tell success from failure.** `act` needs it: a
      // card button that marks itself used on a turn that errored is the interface asserting
      // something untrue.
      return receivedDone;
    },
    [streamedText],
  );

  const send = useCallback((prompt: string) => run(prompt, { prompt }), [run]);

  /**
   * A card button.
   *
   * **A click is a UI state change, not a message.** It adds no traveller turn — the transcript shows
   * what the *agent* did, and the card shows what the traveller did. The phrase the agent receives is
   * built server-side from the closed registry: the client sends an id and a payload, never text.
   */
  const act = useCallback(
    async (action: CardAction, cardId?: string) => {
      const completed = await run(null, { action_id: action.id, payload: action.payload });
      // **Marked on success, not on click.** Marking optimistically claimed the selection had
      // happened while the agent had returned an error and knew nothing about it. A button is a
      // record of what the system did, so it may only change once the system did it. The cost is
      // accepted: for the seconds a turn is in flight the button stays un-ticked, and `busy` already
      // disables every button for exactly that window, so a double press is still impossible.
      if (completed && cardId) {
        setSpentActions((previous) => new Set(previous).add(`${cardId}:${action.id}`));
      }
      return completed;
    },
    [run],
  );

  /** Start a fresh conversation. */
  const startNew = useCallback(() => {
    streamedText.reset();
    conversationId.current = newConversationId();
    setTurns([]);
    setPills([]);
    setSpentActions(new Set());
  }, [streamedText]);

  return { turns, pills, busy, send, act, startNew, streamedText, spentActions };
}

/**
 * Vite Fast Refresh preserves hook refs. During local development it can therefore retain a store
 * instance created by the previous module version, before `settle()` existed. A production load
 * always has the method, but falling back to `flush()` keeps an in-flight local turn readable rather
 * than labelling a hot-reload transition as a failed reply.
 */
function settleStreamedText(store: StreamedTextStore): Promise<string> {
  const compatibleStore = store as StreamedTextStore & { settle?: () => Promise<string> };
  return compatibleStore.settle ? compatibleStore.settle() : Promise.resolve(store.flush());
}

function apply(
  event: StreamEvent,
  patch: (change: (turn: Turn) => Turn) => void,
  setPills: React.Dispatch<React.SetStateAction<Pill[]>>,
  flow: { resumedAfterTool: boolean },
  streamedText: StreamedTextStore,
) {
  switch (event.type) {
    case 'text': {
      const incoming = event.text;
      const resumed = flow.resumedAfterTool;
      flow.resumedAfterTool = false;
      const current = streamedText.current();
      // Only bridge the gap left by a tool call, and only when neither side already has
      // whitespace — so a genuine word-split ("inform" + "ation") is never broken.
      const gap = resumed && current && !/\s$/.test(current) && !/^\s/.test(incoming);
      streamedText.append((gap ? '\n\n' : '') + incoming);
      return;
    }
    case 'tool_start':
      // Keyed on the tool's own id so two tools running in one step resolve independently rather
      // than the second clearing the first's pill.
      setPills((previous) => [
        ...previous,
        { id: event.id ?? event.tool, label: event.label ?? event.tool },
      ]);
      return;
    case 'tool_end':
      // The next text chunk is a resumed run; mark the boundary so it is separated from the
      // narration that preceded the tool.
      flow.resumedAfterTool = true;
      setPills((previous) => previous.filter((pill) => pill.id !== (event.id ?? event.tool)));
      return;
    case 'cards':
      // The tool result is ready before the model's explanation. Retaining it on the turn rather
      // than rendering it immediately preserves the real event order while giving the reply a
      // natural reading order once the stream completes.
      patch((turn) => ({
        ...turn,
        pendingCards: [...(turn.pendingCards ?? []), ...event.cards],
      }));
      return;
    case 'guardrail':
      patch((turn) => ({ ...turn, guardrail: event.categories }));
      return;
    case 'error':
      if (!streamedText.current()) streamedText.append(event.message);
      patch((turn) => ({ ...turn, text: streamedText.flush(), failure: event.message }));
      return;
    default:
      // An event type this build does not know. Ignored on purpose: the agent must be able to add one
      // without breaking a deployed client.
      return;
  }
}
