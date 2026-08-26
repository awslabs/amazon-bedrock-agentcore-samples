/**
 * One component per `card_type`, dispatched through an exhaustive switch.
 *
 * **The `never` in the default branch is load-bearing.** `CardType` is generated from
 * `shared/cards.py`, so adding a card type in Python and not handling it here is a *compile error* —
 * not a tile that silently renders as nothing, which is how a missing card type would otherwise
 * surface: no error, no log, just an answer that looks incomplete.
 *
 * **The model never authors markup.** A card is data; these components decide how it looks. That is
 * an XSS boundary as much as a design one — everything below renders through JSX text nodes, so a
 * hostile string in a tool response becomes visible text rather than markup.
 */
import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import type { Card, CardAction } from '../../../shared/generated/cards';
import { ALLOWED_ACTIONS } from '../../../shared/generated/cards';
import {
  day,
  distance,
  minutes,
  money,
  placeName,
  starRating,
  stops,
  timestamp,
} from '../lib/format';
import { buildBookingIcs, icsFilename } from '../lib/ics';
import { documentUrl } from '../lib/api';
import {
  AlertIcon,
  CheckCircleIcon,
  DocumentIcon,
  HeadsetIcon,
  HotelIcon,
  PassportIcon,
  PinIcon,
  PlaneIcon,
  PolicyIcon,
  RouteIcon,
  TicketIcon,
  TripIcon,
  UserIcon,
} from '../components/icons';

export interface CardViewProps {
  card: Card;
  /**
   * Invoked when a button is pressed.
   *
   * The card id travels with the action so the parent can record *which* card was acted on — see
   * `spent` for why the action id alone is not enough.
   */
  onAction: (action: CardAction, cardId?: string) => void;
  /** True while a turn is in flight, so buttons cannot be pressed twice. */
  busy: boolean;
  /**
   * Actions already used, as `"<cardId>:<actionId>"`.
   *
   * **The card id is part of the key** because a conversation holds several cards offering the same
   * action — every hotel option has `select_hotel` — so keying on the action alone would grey out
   * every card's button after one click.
   */
  spent?: ReadonlySet<string>;
}

/**
 * Actions already used, shared through context rather than threaded as a prop.
 *
 * **Context because the alternative is twelve signatures.** Every card component would have to accept
 * and forward `spent` purely to hand it to `Actions` at the bottom. Only `Actions` reads it, so only
 * `Actions` knows about it.
 */
const SpentActions = createContext<ReadonlySet<string>>(new Set());

/** Stable identity, so an absent `spent` does not remount every card on each render. */
const EMPTY: ReadonlySet<string> = new Set();

export function CardView({ card, onAction, busy, spent }: CardViewProps) {
  return (
    <SpentActions.Provider value={spent ?? EMPTY}>
      <CardBody card={card} onAction={onAction} busy={busy} />
    </SpentActions.Provider>
  );
}

function CardBody({ card, onAction, busy }: Omit<CardViewProps, 'spent'>) {
  const data = card.data as Record<string, never>;
  switch (card.card_type) {
    case 'flight_option':
      return <FlightOption card={card} data={data} onAction={onAction} busy={busy} />;
    case 'hotel_option':
      return <HotelOption card={card} data={data} onAction={onAction} busy={busy} />;
    case 'trip':
      return <Trip card={card} data={data} onAction={onAction} busy={busy} />;
    case 'profile':
      return <Profile data={data} />;
    case 'policy_verdict':
      return <PolicyVerdict card={card} data={data} onAction={onAction} busy={busy} />;
    case 'booking_summary':
      return <BookingSummary card={card} data={data} onAction={onAction} busy={busy} />;
    case 'booking_confirmed':
      return <BookingConfirmed card={card} data={data} onAction={onAction} busy={busy} />;
    case 'cancellation':
      return <Cancellation card={card} data={data} onAction={onAction} busy={busy} />;
    case 'entry_requirements':
      return <EntryRequirements data={data} />;
    case 'place':
      return <Place card={card} data={data} onAction={onAction} busy={busy} />;
    case 'route':
      return <Route data={data} />;
    case 'escalation':
      return <Escalation data={data} />;
    case 'citation':
      return <Citation data={data} />;
    default: {
      // Unreachable while the switch is exhaustive. If a new `CardType` is generated and not handled
      // above, `card.card_type` is no longer `never` and this line fails to compile — which is the
      // entire purpose of writing it this way.
      const unhandled: never = card.card_type;
      return <UnknownCard type={unhandled} />;
    }
  }
}

/**
 * The buttons on a card, filtered against the closed registry.
 *
 * **Filtered even though the API also refuses unregistered actions**, and neither check is
 * redundant: this one stops a button from ever being drawn, and the API's stops a hand-written
 * request. A card offering an action outside its type's allowlist means either a stale registry or a
 * tool inventing UI — both worth refusing to render rather than passing along.
 */
function Actions({
  card,
  onAction,
  busy,
}: {
  card: Card;
  onAction: (action: CardAction, cardId?: string) => void;
  busy: boolean;
}) {
  const allowed = ALLOWED_ACTIONS[card.card_type];
  const actions = (card.actions ?? []).filter((action) => allowed.includes(action.id));
  const spent = useContext(SpentActions);
  if (actions.length === 0) return null;
  return (
    <div className="card-actions">
      {actions.map((action) => {
        // **A used action stays visible but becomes inert, and says what happened.** Scrolling back to
        // a booking already confirmed and pressing *Confirm booking* again re-fired the whole turn —
        // the backend refuses it, so nothing broke, but offering a button that can only fail is the
        // interface lying about what is possible. Removing the button would be worse: the card is the
        // record of what happened, and one that vanishes leaves no trace that the thing was done.
        const used = spent.has(`${card.id}:${action.id}`);
        return (
          <button
            key={action.id}
            type="button"
            className={used ? 'btn done' : primary(action.id) ? 'btn primary' : 'btn'}
            disabled={busy || used}
            aria-disabled={used || undefined}
            onClick={() => onAction(action, card.id)}
          >
            {used ? doneLabel(action) : action.label}
          </button>
        );
      })}
    </div>
  );
}

/**
 * What a button says once it has been used.
 *
 * Past tense and specific, because the label is now a *record* rather than an invitation —
 * "Confirmed" tells a traveller scrolling back what they did, where a greyed-out "Confirm booking"
 * only says they cannot.
 */
function doneLabel(action: CardAction): string {
  switch (action.id) {
    case 'confirm_booking':
      return '\u2713 Confirmed';
    case 'confirm_cancel':
      return '\u2713 Cancelled';
    case 'decline_booking':
    case 'keep_booking':
      return '\u2713 Declined';
    default:
      return `\u2713 ${action.label}`;
  }
}

/** The actions that transact or advance, styled to stand out from the ones that merely inform. */
function primary(id: CardAction['id']): boolean {
  return (
    id === 'confirm_booking' ||
    id === 'confirm_cancel' ||
    id === 'select_flight' ||
    id === 'select_hotel'
  );
}

/** Shared frame, so every tile has the same shape and the components below stay about content. */
function Tile({
  icon,
  title,
  subtitle,
  badge,
  children,
}: {
  icon?: ReactNode;
  title: string;
  subtitle?: string;
  badge?: { text: string; tone: 'ok' | 'warn' };
  children?: ReactNode;
}) {
  return (
    <article className="card">
      <header>
        {icon && (
          <span className="card-icon" aria-hidden="true">
            {icon}
          </span>
        )}
        <div className="card-heading">
          <h3>{title}</h3>
          {subtitle && <p className="subtitle">{subtitle}</p>}
        </div>
        {badge && <span className={`badge ${badge.tone}`}>{badge.text}</span>}
      </header>
      {children}
    </article>
  );
}

/**
 * A snake_case enum as something a traveller reads.
 *
 * Statuses arrive as the tool's own vocabulary — `in_progress`, `confirm_in_chat` — and a badge
 * showing `in_progress` is the data model surfacing through the interface. The chips and reason codes
 * elsewhere already strip the underscores; the badges did not.
 */
function label(value: unknown): string {
  const text = String(value ?? '')
    .replace(/_/g, ' ')
    .trim();
  return text ? text[0].toUpperCase() + text.slice(1) : '—';
}

function policyBadge(inPolicy: unknown): { text: string; tone: 'ok' | 'warn' } {
  return inPolicy ? { text: 'In policy', tone: 'ok' } : { text: 'Out of policy', tone: 'warn' };
}

/**
 * A star rating with its scale visible. The arithmetic — and the absent case — is in `format.ts`,
 * where it is tested; this decides only how it looks.
 */
function Stars({ rating }: { rating: unknown }) {
  const scale = starRating(rating);
  if (!scale) return <>—</>;
  return (
    <span className="stars" aria-label={`${scale.filled} of 5 stars`}>
      {'★'.repeat(scale.filled)}
      <span className="empty">{'★'.repeat(scale.empty)}</span>
    </span>
  );
}

// --- the twelve card types ---------------------------------------------------------------------

type Props = CardViewProps & { data: Record<string, never> };

function FlightOption({ card, data, onAction, busy }: Props) {
  return (
    <Tile
      icon={<PlaneIcon size={18} />}
      title={`${data.carrier} ${data.flight_number}`}
      subtitle={`${data.depart_airport} ${data.depart_time} → ${data.arrive_airport} ${data.arrive_time}`}
      badge={policyBadge(data.in_policy)}
    >
      <dl className="facts">
        <Fact label="Duration" value={minutes(data.duration_min)} />
        {/* A stop count the tool did not send must not read as "Direct" — see `finiteNumber`. */}
        <Fact label="Stops" value={stops(data.stops)} />
        <Fact label="Cabin" value={String(data.cabin ?? '—')} />
        <Fact label="Price" value={money(data.price)} />
      </dl>
      {/* Shown only when present, which the tools do only for out-of-policy options: a note on every
          tile trains people to stop reading the ones that matter. */}
      {data.policy_note && <p className="note">{String(data.policy_note)}</p>}
      <Actions card={card} onAction={onAction} busy={busy} />
    </Tile>
  );
}

function HotelOption({ card, data, onAction, busy }: Props) {
  const amenities = Array.isArray(data.amenities) ? (data.amenities as string[]) : [];
  return (
    <Tile
      icon={<HotelIcon size={18} />}
      title={String(data.name)}
      subtitle={String(data.address)}
      badge={policyBadge(data.in_policy)}
    >
      <dl className="facts">
        <Fact label="Rating" value={<Stars rating={data.star_rating} />} />
        <Fact label="Per night" value={money(data.nightly_rate)} />
        <Fact label="Total" value={money(data.total)} />
        {data.preferred ? <Fact label="Chain" value="Preferred" /> : null}
      </dl>
      {amenities.length > 0 && (
        <ul className="chips">
          {amenities.map((amenity) => (
            <li key={amenity}>{amenity.replace(/_/g, ' ')}</li>
          ))}
        </ul>
      )}
      {data.policy_note && <p className="note">{String(data.policy_note)}</p>}
      <Actions card={card} onAction={onAction} busy={busy} />
    </Tile>
  );
}

function Trip({ card, data, onAction, busy }: Props) {
  const segments = Array.isArray(data.segments) ? (data.segments as Record<string, unknown>[]) : [];
  // The trip's own label ("London client kickoff") when the tool sent one, then the destination.
  // `destination` is an object, so `String()` on it renders `[object Object]` — see `placeName`.
  const where = placeName(data.destination);
  const dates = [day(data.start_date), day(data.end_date)].filter(Boolean).join(' – ');
  return (
    <Tile
      icon={<TripIcon size={18} />}
      title={(typeof data.label === 'string' && data.label) || where || 'Trip'}
      subtitle={dates || undefined}
      badge={{ text: label(data.status), tone: data.status === 'cancelled' ? 'warn' : 'ok' }}
    >
      <ul className="segments">
        {segments.map((segment, index) => (
          <li key={index}>
            {String(segment.label ?? segment.description ?? segment.type ?? 'Segment')}
          </li>
        ))}
      </ul>
      <Actions card={card} onAction={onAction} busy={busy} />
    </Tile>
  );
}

function Profile({ data }: { data: Record<string, never> }) {
  const loyalty = Array.isArray(data.loyalty) ? (data.loyalty as Record<string, unknown>[]) : [];
  return (
    <Tile
      icon={<UserIcon size={18} />}
      title={String(data.traveler_name)}
      subtitle={`Home airport ${data.home_airport}`}
    >
      <dl className="facts">
        <Fact label="Passport" value={String(data.passport_country ?? '—')} />
      </dl>
      {loyalty.length > 0 && (
        <ul className="chips">
          {loyalty.map((programme, index) => (
            <li key={index}>{String(programme.programme ?? programme.name ?? '')}</li>
          ))}
        </ul>
      )}
      {/* No passport *number* and no card digits — the tool layer never sends them, and this is the
          card that would show them if it did. */}
    </Tile>
  );
}

function PolicyVerdict({ card, data, onAction, busy }: Props) {
  return (
    <Tile
      icon={<PolicyIcon size={18} />}
      title={String(data.request_label)}
      badge={
        data.eligible ? { text: 'Allowed', tone: 'ok' } : { text: 'Not allowed', tone: 'warn' }
      }
    >
      {/* The quoted rule, verbatim. A verdict without its rule is an assertion the traveller cannot
          check, and the reason code is what makes two tenants' refusals visibly different. */}
      <blockquote>{String(data.rule_quote)}</blockquote>
      <p className="reason">{String(data.reason_code).replace(/_/g, ' ')}</p>
      <Actions card={card} onAction={onAction} busy={busy} />
    </Tile>
  );
}

function BookingSummary({ card, data, onAction, busy }: Props) {
  const items = Array.isArray(data.items) ? (data.items as Record<string, unknown>[]) : [];
  return (
    <Tile
      icon={<TicketIcon size={18} />}
      title="Ready to book"
      subtitle={String(data.payment_label ?? '')}
      badge={policyBadge(data.policy_status === 'in_policy')}
    >
      <ul className="segments">
        {items.map((item, index) => (
          <li key={index}>
            {String(item.label ?? item.type ?? 'Item')} · {money(item.price)}
          </li>
        ))}
      </ul>
      <dl className="facts">
        <Fact label="Total" value={money(data.total)} />
      </dl>
      {/* **The per-tenant difference, rendered rather than described.** A `confirm_in_chat` tenant's
          card carries confirm/decline actions; a `handoff` tenant's carries none and a checkout link
          instead. This component does not branch on tenant — it renders what the card says, which is
          why the capability difference is visible without the UI knowing about tenants at all. */}
      {data.checkout_url && (
        <a
          className="btn primary"
          href={String(data.checkout_url)}
          target="_blank"
          rel="noreferrer"
        >
          Continue to checkout
        </a>
      )}
      <Actions card={card} onAction={onAction} busy={busy} />
    </Tile>
  );
}

function BookingConfirmed({ card, data, onAction, busy }: Props) {
  const items = Array.isArray(data.items) ? (data.items as Record<string, unknown>[]) : [];
  return (
    <Tile
      icon={<CheckCircleIcon size={18} />}
      title={`Confirmed · ${data.confirmation_number}`}
      subtitle={timestamp(data.issued_at) ?? ''}
      badge={{ text: 'Booked', tone: 'ok' }}
    >
      <ul className="segments">
        {items.map((item, index) => (
          <li key={index}>{String(item.label ?? item.type ?? 'Item')}</li>
        ))}
      </ul>
      <dl className="facts">
        <Fact label="Total" value={money(data.total)} />
      </dl>
      {/* **Calendar download, done here rather than asked of the agent.** There is no calendar *tool*,
          so routing this through the model made it improvise. An `.ics` file is browser work: no turn,
          no tool, no round trip, and nothing that can expire between the booking and the click. */}
      <AddToCalendar data={data} />
      <Actions card={card} onAction={onAction} busy={busy} />
    </Tile>
  );
}

/**
 * Download the confirmed booking as a calendar file.
 *
 * Built entirely from the card's own fields, which is what lets it be local: the confirmation number,
 * the segment label and the travel date are all already on screen. Nothing is asked of the server, so
 * there is no handle to go stale and no turn to wait for.
 *
 * **Rendered only when the card carries a date.** An event with no `DTSTART` is not valid iCalendar
 * unless the object declares a `METHOD`, and calendar clients disagree about what to do with one — so
 * a button producing a file that may silently fail to import would be the same bug in a new costume.
 * Better to offer nothing than to offer something that might not work.
 */
function AddToCalendar({ data }: { data: Record<string, never> }) {
  const [added, setAdded] = useState(false);
  const items = Array.isArray(data.items) ? (data.items as Record<string, unknown>[]) : [];
  const summary = String(items[0]?.label ?? 'Trip');
  const reference = String(data.confirmation_number ?? '');

  // `null` when the card carries no usable travel date, in which case no button is drawn at all — see
  // `buildBookingIcs` for why a dateless event is not an acceptable fallback.
  const ics = buildBookingIcs({ startsOn: data.starts_on, summary, reference });
  if (!ics) return null;

  const download = () => {
    const url = URL.createObjectURL(new Blob([ics], { type: 'text/calendar' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = icsFilename(reference);
    link.click();
    URL.revokeObjectURL(url);
    setAdded(true);
  };

  return (
    <div className="card-actions">
      {/* Past tense once used, because the label becomes a *record* rather than an invitation — and it
          is the only feedback there is, since nothing enters the transcript. */}
      <button
        type="button"
        className={added ? 'btn done' : 'btn'}
        disabled={added}
        onClick={download}
      >
        {added ? '\u2713 Downloaded' : 'Download .ics'}
      </button>
    </div>
  );
}

function Cancellation({ card, data, onAction, busy }: Props) {
  const terms = Array.isArray(data.terms) ? (data.terms as unknown[]) : [];
  const cancelled = data.stage === 'cancelled';
  return (
    <Tile
      icon={<AlertIcon size={18} />}
      title={String(data.booking_label)}
      badge={cancelled ? { text: 'Cancelled', tone: 'warn' } : { text: 'Review terms', tone: 'ok' }}
    >
      {/* **Terms before the button, always.** The two-stage cancellation exists so nobody confirms a
          penalty they have not seen; rendering the buttons above the terms would defeat it. */}
      <ul className="segments">
        {terms.map((term, index) => (
          <li key={index}>
            {typeof term === 'string'
              ? term
              : String((term as Record<string, unknown>).label ?? '')}
          </li>
        ))}
      </ul>
      {data.refund_estimate && (
        <dl className="facts">
          <Fact label="Estimated refund" value={money(data.refund_estimate)} />
        </dl>
      )}
      <Actions card={card} onAction={onAction} busy={busy} />
    </Tile>
  );
}

function EntryRequirements({ data }: { data: Record<string, never> }) {
  return (
    <Tile
      icon={<PassportIcon size={18} />}
      title={`Entry into ${data.destination_country}`}
      subtitle={`${data.passport_country} passport`}
    >
      <p>{String(data.requirement)}</p>
      {/* Always shown. Entry rules are the one answer where being confidently wrong strands someone
          at a border, so the disclaimer is part of the card contract rather than optional styling. */}
      <p className="note">{String(data.disclaimer)}</p>
    </Tile>
  );
}

function Place({ card, data, onAction, busy }: Props) {
  const categories = Array.isArray(data.categories) ? (data.categories as string[]) : [];
  // An absent distance yields `null`, not a `0 m` badge — "next door" is a strong claim to make about
  // a place the tool sent no distance for.
  const away = distance(data.distance_m);
  return (
    <Tile
      title={String(data.name)}
      subtitle={String(data.address)}
      icon={<PinIcon size={18} />}
      badge={away ? { text: away, tone: 'ok' } : undefined}
    >
      {categories.length > 0 && (
        <ul className="chips">
          {categories.map((category) => (
            <li key={category}>{category.replace(/_/g, ' ')}</li>
          ))}
        </ul>
      )}
      <Actions card={card} onAction={onAction} busy={busy} />
    </Tile>
  );
}

function Route({ data }: { data: Record<string, never> }) {
  return (
    <Tile
      icon={<RouteIcon size={18} />}
      title={`${data.origin} → ${data.destination}`}
      subtitle={label(data.mode)}
    >
      <dl className="facts">
        <Fact label="Duration" value={minutes(data.duration_min)} />
        <Fact label="Distance" value={`${data.distance_km} km`} />
      </dl>
    </Tile>
  );
}

function Escalation({ data }: { data: Record<string, never> }) {
  /**
   * **The title says what happened, not what would happen with a transport wired in.**
   *
   * This read "Handed to a travel consultant" with a success badge, while `tools/escalation` only
   * assembles the package and logs it — delivery is a documented extension point. So the screen
   * asserted a completed transfer the code does not perform. A sample that overstates on its own
   * surface is the version a reader copies, and the docstring explaining the gap is not what the
   * traveller reads.
   *
   * `warn` rather than `ok` because nothing has completed: the package is ready and waiting for a
   * transport. The tone vocabulary is only `ok | warn`, and of the two this is the honest one.
   * Wiring a real handoff means changing `status` at the delivery site and this title together.
   */
  const delivered = data.status === 'delivered' || data.status === 'queued';
  return (
    <Tile
      icon={<HeadsetIcon size={18} />}
      title={delivered ? 'Handed to a travel consultant' : 'Handoff package prepared'}
      subtitle={String(data.reason_label)}
      badge={{ text: label(data.status), tone: delivered ? 'ok' : 'warn' }}
    >
      {/* The one-line summary the consultant receives, shown to the traveller too — so nobody has to
          wonder what was passed on about them. */}
      <p>{String(data.context_summary_line)}</p>
      {!delivered && (
        <p className="note">
          This demo prepares the handoff and records it; it does not transfer the conversation. See{' '}
          <code>tools/escalation/handler.py</code> for the one call that would.
        </p>
      )}
    </Tile>
  );
}

function Citation({ data }: { data: Record<string, never> }) {
  /**
   * **Opens the document itself, not a question about it.** Every other action on a card posts back
   * to the agent as a phrase — see `Actions` below — because most actions *are* something to ask
   * the assistant to do. Reading a policy document is not: the citation already names exactly which
   * document and passage grounded the answer, so routing "open this" through a model call would add
   * a turn, a cost, and a chance of a different tool being picked, to do something a plain fetch
   * already does. Same reasoning as `AddToCalendar` on `booking_confirmed` — the browser already has
   * everything it needs.
   *
   * **Fetched on click, not rendered as a link on load.** `documentUrl` calls `GET
   * /documents/{doc_id}`, which presigns *and re-authorises* against the session making the call —
   * see `conversation-api/app/documents.py`. A link built from a citation the moment it arrived would
   * still be safe today, but it would also be the pattern a reader copies for a card that arrives on
   * a page loaded hours ago, at which point the presign would be signing against a session that may
   * no longer be this traveller's. Signing at click time is the one version of this that stays
   * correct regardless of when the click happens.
   */
  const [state, setState] = useState<'idle' | 'loading' | 'error'>('idle');
  const docId = String(data.doc_id ?? '');

  const open = async () => {
    setState('loading');
    const url = await documentUrl(docId);
    if (!url) {
      // The same refusal a wrong tenant or a stale link produces server-side — see `_document_link`
      // in `main.py`: a 404 either way, so nothing here can tell "not yours" from "gone".
      setState('error');
      return;
    }
    window.open(url, '_blank', 'noopener,noreferrer');
    setState('idle');
  };

  return (
    <Tile icon={<DocumentIcon size={18} />} title={String(data.label)}>
      <div className="card-actions">
        <button type="button" className="btn" disabled={state === 'loading'} onClick={open}>
          {state === 'loading' ? 'Opening…' : 'Open source'}
        </button>
      </div>
      {state === 'error' && (
        <p className="note">
          This link is no longer available — it may have expired, or belong to a different session.
        </p>
      )}
    </Tile>
  );
}

function UnknownCard({ type }: { type: string }) {
  return (
    <article className="card">
      <p className="note">This version of the app cannot display a “{type}” card.</p>
    </article>
  );
}

function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}
