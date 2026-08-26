/**
 * A confirmed booking as an iCalendar file, built in the browser.
 *
 * **Why this is not a tool.** `add_to_calendar` used to be an action on the booking card, which asked
 * the *agent* to do something no tool implements. Handed "Add booking off_x to my calendar" with no
 * calendar tool, the model improvised with the booking tools and announced the hold had expired —
 * about a flight it had just successfully booked. Worse than a missing feature, because it reads as a
 * failed booking.
 *
 * A calendar entry needs no agent, no tool and no turn: everything it requires is already on the card.
 * So it is browser work, and nothing here can expire between the booking and the click.
 *
 * Separate from `CardView` so `node --test` can import it — the RFC 5545 rules below are the kind that
 * fail silently in a calendar client rather than visibly on screen.
 */

export interface BookingForCalendar {
  /** Travel date as `YYYY-MM-DD`. Not the booking date — see `Reservation.starts_on`. */
  startsOn: unknown;
  /** What the event is called, normally the first segment's label. */
  summary: string;
  /** The confirmation number, used for the UID and the filename. */
  reference: string;
}

/**
 * Escape a value for an iCalendar property, per RFC 5545 §3.3.11.
 *
 * A comma or semicolon in a hotel name would otherwise terminate the property and corrupt the rest of
 * the file — "Hilton Frankfurt, City Centre" is enough to do it.
 */
function escapeText(value: string): string {
  return value.replace(/([\\;,])/g, '\\$1').replace(/\r?\n/g, '\\n');
}

/**
 * The `.ics` body, or `null` when the card carries no usable travel date.
 *
 * **`null` rather than a dateless event, deliberately.** A `VEVENT` without `DTSTART` is invalid unless
 * the calendar object declares a `METHOD`, and clients disagree about what to do with one — so a button
 * offering a file that might silently fail to import would be the same bug in a new costume. Better to
 * offer no button than one that may not work.
 */
export function buildBookingIcs({
  startsOn,
  summary,
  reference,
}: BookingForCalendar): string | null {
  const parts = typeof startsOn === 'string' ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(startsOn) : null;
  if (!parts) return null;

  // **An all-day event.** The card carries the travel date but no departure *time*, and a whole-day
  // placeholder a traveller can adjust beats a specific hour we invented. All-day form is `VALUE=DATE`
  // with `DTEND` on the following day, because `DTEND` is exclusive.
  //
  // Built from the numbers rather than parsed: `new Date('2026-08-22')` is midnight *UTC*, which is
  // still the 21st anywhere west of Greenwich, so parsing would move the entry a day earlier for most
  // of the Americas. Constructing from parts sidesteps that, and `Date` normalises the overflow when
  // the following day crosses a month or year boundary.
  const [, year, month, day] = parts;
  const start = `${year}${month}${day}`;
  const next = new Date(Number(year), Number(month) - 1, Number(day) + 1);
  const pad = (value: number) => String(value).padStart(2, '0');
  const end = `${next.getFullYear()}${pad(next.getMonth() + 1)}${pad(next.getDate())}`;
  const stamp = `${new Date().toISOString().replace(/[-:]/g, '').split('.')[0]}Z`;

  // CRLF line endings are required by the spec, not a Windows habit.
  return [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//MultiTenantTravel//Travel//EN',
    'BEGIN:VEVENT',
    `UID:${reference || stamp}@multi-tenant-travel`,
    `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${start}`,
    `DTEND;VALUE=DATE:${end}`,
    `SUMMARY:${escapeText(summary)}`,
    `DESCRIPTION:${escapeText(`Booking reference ${reference}`)}`,
    'END:VEVENT',
    'END:VCALENDAR',
  ].join('\r\n');
}

/** Filename for the download — the confirmation number is what a traveller would search for. */
export function icsFilename(reference: string): string {
  return `${reference || 'trip'}.ics`;
}
