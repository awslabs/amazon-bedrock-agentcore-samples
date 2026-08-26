/**
 * The calendar file the confirmed-booking card downloads.
 *
 * **Worth testing because every failure here is silent.** An invalid `.ics` does not throw in the
 * browser — the file downloads, the button says "Added to calendar", and the traveller finds out when
 * their calendar client refuses it or puts the trip on the wrong day. That is indistinguishable from
 * the bug this replaced (a button that resolved without working), which is why the rules below are
 * asserted rather than trusted.
 *
 *     npm test --prefix frontend
 *
 * `TZ=America/Los_Angeles` is set by that script on purpose: the date handling below is correct at UTC
 * whichever way it is written, so a run there cannot fail and the timezone test would be theatre.
 */
import { strict as assert } from 'node:assert';
import { test } from 'node:test';

import { buildBookingIcs, icsFilename } from '../src/lib/ics.ts';

const booking = { startsOn: '2026-09-15', summary: 'DL154 ATL → LHR', reference: 'TRV6656' };

test('the event is dated on the travel date, not the day it was booked', () => {
  // `issued_at` is the booking moment. Using it — the only date the card carried before `starts_on`
  // existed — would put every trip on today.
  const ics = buildBookingIcs(booking);
  assert.match(ics, /DTSTART;VALUE=DATE:20260915/);
});

test('every event carries a DTSTART, since one without it is not valid iCalendar', () => {
  // Without a `METHOD` property, RFC 5545 makes `DTSTART` required in a `VEVENT`. The version this
  // was ported from omitted it entirely.
  const ics = buildBookingIcs(booking);
  assert.ok(ics.includes('BEGIN:VEVENT'));
  assert.ok(ics.includes('DTSTART'), 'a VEVENT with no DTSTART may not import at all');
});

test('an all-day event ends on the following day, because DTEND is exclusive', () => {
  assert.match(buildBookingIcs(booking), /DTEND;VALUE=DATE:20260916/);
});

test('the end date rolls over months and years', () => {
  // Built from date parts, so `Date` normalises the overflow rather than us doing modular arithmetic.
  assert.match(
    buildBookingIcs({ ...booking, startsOn: '2026-09-30' }),
    /DTEND;VALUE=DATE:20261001/,
  );
  assert.match(
    buildBookingIcs({ ...booking, startsOn: '2026-12-31' }),
    /DTEND;VALUE=DATE:20270101/,
  );
  // A leap year, which is where hand-rolled date maths usually breaks.
  assert.match(
    buildBookingIcs({ ...booking, startsOn: '2028-02-28' }),
    /DTEND;VALUE=DATE:20280229/,
  );
});

test('the date is not shifted by the viewer’s timezone', () => {
  // `new Date('2026-09-15')` is midnight **UTC**, which is still the 14th in Los Angeles — so parsing
  // the string instead of building from its parts moves the entry a day earlier for most of the
  // Americas. This test only fails west of Greenwich, which is why `TZ` is pinned.
  assert.match(buildBookingIcs(booking), /DTSTART;VALUE=DATE:20260915/);
  assert.ok(!buildBookingIcs(booking).includes('20260914'), 'the date slipped a day');
});

test('lines are CRLF-terminated, as the spec requires', () => {
  const ics = buildBookingIcs(booking);
  assert.ok(ics.includes('\r\n'));
  assert.ok(!/[^\r]\n/.test(ics), 'a bare LF appeared somewhere');
});

test('a comma or semicolon in a name cannot corrupt the file', () => {
  // Unescaped, these terminate the property — so a hotel called "Hilton Frankfurt, City Centre" would
  // truncate the summary and push the rest of the line into the parser as something else.
  const ics = buildBookingIcs({
    ...booking,
    summary: 'Hilton Frankfurt, City Centre; Room 4',
  });
  assert.match(ics, /SUMMARY:Hilton Frankfurt\\, City Centre\\; Room 4/);
});

test('a newline in a name becomes the literal escape an iCalendar reader expects', () => {
  const ics = buildBookingIcs({ ...booking, summary: 'Hotel\nSecond line' });
  assert.match(ics, /SUMMARY:Hotel\\nSecond line/);
  // The escaped newline must not have introduced a real line break into the body.
  assert.ok(!/SUMMARY:Hotel\r\n/.test(ics));
});

test('no file is produced when the card carries no usable date', () => {
  // The button is not drawn in this case. Offering a download that might silently fail to import
  // would be the same defect as the agent-routed button it replaced.
  for (const absent of [
    undefined,
    null,
    '',
    'sometime tuesday',
    '15-09-2026',
    '2026-9-15',
    42,
    {},
  ]) {
    assert.equal(
      buildBookingIcs({ ...booking, startsOn: absent }),
      null,
      `startsOn=${JSON.stringify(absent)} should produce no file`,
    );
  }
});

test('the calendar object is well-formed and closed', () => {
  const ics = buildBookingIcs(booking);
  const lines = ics.split('\r\n');
  assert.equal(lines[0], 'BEGIN:VCALENDAR');
  assert.equal(lines.at(-1), 'END:VCALENDAR');
  assert.ok(ics.includes('VERSION:2.0'));
  // A UID is what stops a second download creating a duplicate entry.
  assert.match(ics, /UID:TRV6656@multi-tenant-travel/);
});

test('the filename is the confirmation number a traveller would search for', () => {
  assert.equal(icsFilename('TRV6656'), 'TRV6656.ics');
  assert.equal(icsFilename(''), 'trip.ics', 'never produce a file called ".ics"');
});
