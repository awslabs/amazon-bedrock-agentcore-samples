/**
 * The only module that talks to the network.
 *
 * **No token handling anywhere in this file, and that is the whole point.** The session lives in an
 * httpOnly cookie the browser attaches automatically, so there is nothing here to store, refresh or
 * accidentally log. `credentials: 'include'` is the only auth code in the SPA.
 *
 * That is why every request goes through here rather than components calling `fetch` directly: one
 * place decides what a session is, so a new component cannot invent a second answer.
 */
import type { Card } from '../../../shared/generated/cards';

/**
 * Base URL of the conversation API.
 *
 * Injected at build time from SSM by the deploy script rather than hardcoded — the stage URL moves
 * whenever the REST API is replaced. The dev-server default lets `npm run dev` work against a proxy.
 */
const API_BASE = (import.meta.env.VITE_API_BASE ?? '/api').replace(/\/$/, '');

/**
 * One event from the agent's stream.
 *
 * Mirrors the envelope the agent emits (`agent/.../stream.py`). **Unknown types are ignored rather
 * than being an error**, so the agent can add an event type without breaking a deployed client —
 * which is what makes the two sides independently deployable.
 */
export type StreamEvent =
  | { type: 'text'; text: string }
  | { type: 'tool_start'; tool: string; label: string; id?: string }
  | { type: 'tool_end'; tool: string; id?: string; ok?: boolean }
  | { type: 'guardrail'; categories: string[] }
  | { type: 'error'; message: string }
  | { type: 'done'; usage?: Record<string, number> }
  | { type: 'cards'; cards: Card[] };

/**
 * The network boundary for a turn failed after (or before) its HTTP response began.
 *
 * Kept distinct from malformed event handling in the conversation hook: calling every UI exception
 * a dropped connection makes the only diagnostic shown to the traveller actively misleading.
 */
export class StreamTransportError extends Error {
  readonly cause?: unknown;

  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = 'StreamTransportError';
    this.cause = cause;
  }
}

export interface Session {
  authenticated: boolean;
  tenant_id?: string;
  traveler_id?: string;
  /** Cognito login handle, e.g. `priya` — for display, not proof. */
  username?: string;
  /** `traveler` | `arranger` — the traveller's role, for display. */
  role?: string;
}

export async function currentSession(): Promise<Session> {
  const response = await fetch(`${API_BASE}/auth/session`, { credentials: 'include' });
  if (!response.ok) return { authenticated: false };
  return response.json();
}

export function loginUrl(): string {
  // Tell the API which origin the login began on, so it sends the browser back here — the deployed
  // site or the dev server. The API honours it only if it is on its allowlist, so this cannot be
  // used to redirect anywhere else.
  const params = new URLSearchParams({ return: window.location.origin });
  return `${API_BASE}/auth/login?${params.toString()}`;
}

export async function logout(): Promise<void> {
  // **Destroying the local session is not signing out — Cognito's hosted-UI session outlives it.**
  // This used to stop here, so clicking "Sign in" afterwards silently re-authenticated as the same
  // traveller with no login form at all: the local cookie was gone, but Cognito's own session
  // cookie, set on Cognito's domain, was not. Found in a browser — the whole demo this sample leads
  // with is signing in as the other tenant and repeating a question, and that path was blocked.
  //
  // The API returns where to send the browser rather than this file building a Cognito URL itself:
  // the client id and domain are server-side configuration, and duplicating them here is a second
  // place to keep in step with `infra/lib/identity.ts`'s `addLogoutUrl`.
  const response = await fetch(`${API_BASE}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  });
  const body = response.ok ? await response.json().catch(() => null) : null;
  if (body?.logout_url) {
    window.location.assign(body.logout_url);
  }
}

/** A short-lived link to a policy document, presigned server-side after a tenant re-check. */
export async function documentUrl(docId: string): Promise<string | null> {
  const response = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}`, {
    credentials: 'include',
  });
  if (!response.ok) return null;
  return (await response.json()).url ?? null;
}

/**
 * Send a turn and yield events as they arrive.
 *
 * **Reads the body as a stream rather than awaiting `response.json()`** — the reason the whole
 * streaming configuration exists. `EventSource` would be the conventional choice for SSE and cannot
 * be used: it only issues GETs, and a turn is a POST with a body.
 *
 * Frames are split on the blank line SSE uses as a terminator, and a partial frame is held over to
 * the next chunk. Without that, a frame split across a TCP boundary is silently dropped — which
 * looks like a model omitting a word.
 */
export async function* sendTurn(
  conversationId: string,
  body: { prompt: string } | { action_id: string; payload?: Record<string, unknown> },
): AsyncGenerator<StreamEvent> {
  const path = 'prompt' in body ? 'messages' : 'actions';
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/conversation/${conversationId}/${path}`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (error) {
    throw new StreamTransportError('Could not start the response stream.', error);
  }

  if (!response.ok || !response.body) {
    // A refusal arrives as JSON with a status, never as a stream — so it is translated into the
    // stream's own vocabulary here. The UI then has exactly one shape to render.
    const detail = await response.text().catch(() => '');
    yield {
      type: 'error',
      message: response.status === 401 ? 'Your session has expired.' : errorText(detail),
    };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  // A gateway may hand the browser several SSE frames in one network read, or split a frame across
  // reads. Keep the boundary handling in one place so the ordinary loop and the final EOF drain have
  // exactly the same semantics.
  const takeCompleteFrames = (): StreamEvent[] => {
    const events: StreamEvent[] = [];
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseFrame(frame);
      if (event) events.push(event);
      boundary = buffer.indexOf('\n\n');
    }
    return events;
  };

  while (true) {
    let done: boolean;
    let value: Uint8Array<ArrayBufferLike> | undefined;
    try {
      ({ done, value } = await reader.read());
    } catch (error) {
      throw new StreamTransportError('The response stream was interrupted.', error);
    }
    if (done) break;
    if (value) buffer += decoder.decode(value, { stream: true });
    for (const event of takeCompleteFrames()) yield event;
  }

  // `TextDecoder` can still be holding the end of a multi-byte character. More importantly, some
  // streaming intermediaries close immediately after their final `data:` line and omit the optional
  // blank-line delimiter. Parse that last complete frame too; otherwise the terminal `done` is
  // silently discarded and the UI treats an otherwise successful reply as interrupted.
  buffer += decoder.decode();
  for (const event of takeCompleteFrames()) yield event;
  if (buffer.trim()) {
    const event = parseFrame(buffer);
    if (event) yield event;
  }
}

function parseFrame(frame: string): StreamEvent | null {
  const line = frame.split('\n').find((candidate) => candidate.startsWith('data:'));
  if (!line) return null;
  try {
    const parsed = JSON.parse(line.slice(5).trim());
    // A frame with no `type` cannot be dispatched on, so it is dropped rather than rendered as
    // `undefined` somewhere in the transcript.
    return typeof parsed?.type === 'string' ? (parsed as StreamEvent) : null;
  } catch {
    return null;
  }
}

function errorText(detail: string): string {
  try {
    return JSON.parse(detail).error ?? 'Something went wrong.';
  } catch {
    return 'Something went wrong.';
  }
}

/**
 * A conversation id the runtime will accept.
 *
 * **At least 33 characters**, which a UUID satisfies. The API checks it too; doing it here as well
 * means a new conversation cannot be created in a state that the first message would reject.
 */
export function newConversationId(): string {
  return crypto.randomUUID() + 'aaa';
}
