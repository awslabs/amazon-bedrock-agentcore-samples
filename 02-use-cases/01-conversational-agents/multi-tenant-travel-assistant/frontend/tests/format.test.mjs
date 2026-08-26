/**
 * The card formatters — and specifically the absent-value rules, which are the ones that ship wrong.
 *
 * **Every case here was a real defect or guards one.** Fixture data always populates these fields, so
 * a browser pass cannot see any of it: the bugs only appear when a tool omits something, which is
 * exactly the situation no screenshot covers.
 *
 *     npm test --prefix frontend
 *
 * No test framework and no build step. Node strips types natively on 22.18+/24, which is why these
 * helpers live in `lib/format.ts` rather than inside `CardView.tsx` — a `.tsx` would need a JSX
 * transform before it could be imported here.
 *
 * **The runner needs a glob, not a directory.** `node --test tests/` tries to load the directory as a
 * module and dies with `MODULE_NOT_FOUND`, which reads like a broken import in the tests themselves;
 * `node --test "tests/*.test.mjs"` is the form that works.
 */
import { strict as assert } from 'node:assert';
import { test } from 'node:test';

import {
  day,
  distance,
  finiteNumber,
  minutes,
  money,
  placeName,
  starRating,
  stops,
  timestamp,
} from '../src/lib/format.ts';

test('a price renders to the cent, matching what the model says in the prose', () => {
  // **The bug:** `maximumFractionDigits: 0` put `€111` on a card directly beneath the model's own
  // "110.54 EUR per night". One screen, one fact, two numbers.
  assert.match(money({ amount: 110.54, currency: 'EUR' }), /110\.54/);
  assert.match(money({ amount: 250, currency: 'USD' }), /250\.00/);
  assert.match(money({ amount: 1234.5, currency: 'USD' }), /1,234\.50/);
});

test('an unrecognised currency code does not blank out the price', () => {
  // Falling back to a bare number beats rendering a dash: the amount is the part that matters, and a
  // dash would read as "no price" for a booking that certainly has one.
  const rendered = money({ amount: 99.5, currency: 'XYZ' });
  assert.match(rendered, /99\.5/);
});

test('a missing price is a dash rather than a zero or the word undefined', () => {
  for (const absent of [undefined, null, '', {}, 'free', 42]) {
    assert.equal(money(absent), '—', `money(${JSON.stringify(absent)})`);
  }
});

test('an absent number is null, because Number() maps three absences to a finite zero', () => {
  // The whole reason this helper exists. `Number(null)` is `0` and `Number.isFinite(0)` is true, so a
  // finiteness guard alone admits every one of these as a real measurement.
  for (const absent of [null, undefined, '']) {
    assert.equal(finiteNumber(absent), null, `finiteNumber(${JSON.stringify(absent)})`);
  }
  assert.equal(finiteNumber('not a number'), null);
  assert.equal(finiteNumber({}), null);
  // Real zeros must survive — a direct flight genuinely has zero stops.
  assert.equal(finiteNumber(0), 0);
  assert.equal(finiteNumber('0'), 0);
  assert.equal(finiteNumber(332), 332);
});

test('an absent stop count does not claim the flight is direct', () => {
  // **The worst of the three coercion bugs**: not a blank, a confident wrong fact about a flight.
  assert.equal(stops(null), '—');
  assert.equal(stops(undefined), '—');
  assert.equal(stops(''), '—');
  // And a real zero still reads as the word a traveller wants.
  assert.equal(stops(0), 'Direct');
  assert.equal(stops(1), '1');
  assert.equal(stops(2), '2');
});

test('an absent duration does not render as 0m', () => {
  assert.equal(minutes(null), '—');
  assert.equal(minutes(undefined), '—');
  assert.equal(minutes(''), '—');
});

test('durations read the way people say them', () => {
  assert.equal(minutes(332), '5h 32m');
  assert.equal(minutes(45), '45m');
  assert.equal(minutes(120), '2h 0m');
  assert.equal(minutes(0), '0m');
});

test('a star rating carries its denominator', () => {
  // `★★★` alone cannot be read as "3 of 5". The unfilled remainder is what supplies the scale.
  assert.deepEqual(starRating(3), { filled: 3, empty: 2 });
  assert.deepEqual(starRating(5), { filled: 5, empty: 0 });
  assert.deepEqual(starRating(0), { filled: 0, empty: 5 });
  // Filled and unfilled must always total the scale, whatever the input.
  for (const value of [1, 2.4, 3.5, 4, 5, 7, -2]) {
    const scale = starRating(value);
    assert.equal(scale.filled + scale.empty, 5, `rating ${value} did not total 5`);
  }
});

test('an absent rating is null, not a zero-star hotel', () => {
  // Five empty stars is an assertion about the hotel. A dash is an assertion about our data.
  for (const absent of [null, undefined, '', 'unrated', {}]) {
    assert.equal(starRating(absent), null, `starRating(${JSON.stringify(absent)})`);
  }
});

test('a rating outside the scale is clamped rather than overflowing the row', () => {
  assert.deepEqual(starRating(9), { filled: 5, empty: 0 });
  assert.deepEqual(starRating(-3), { filled: 0, empty: 5 });
});

test('an absent distance shows no badge instead of claiming 0 m', () => {
  // A `0 m` badge says the hotel is where the traveller is standing.
  for (const absent of [null, undefined, '', {}]) {
    assert.equal(distance(absent), null, `distance(${JSON.stringify(absent)})`);
  }
  assert.equal(distance(400), '400 m');
  assert.equal(distance(1500), '1.5 km');
  assert.equal(distance(0), '0 m', 'a genuine zero is still a real measurement');
});

test('no formatter can emit [object Object] or the word undefined', () => {
  // A guard on the whole class rather than the fields that were reported. `[object Object]` on a card
  // is the single most obviously broken thing a UI can show, and a trip card shipped with one.
  for (const fn of [money, minutes, stops]) {
    for (const value of [{}, { a: 1 }, [], [1, 2], { name: {} }]) {
      const rendered = fn(value);
      assert.ok(
        !rendered.includes('[object'),
        `${fn.name}(${JSON.stringify(value)}) → ${rendered}`,
      );
      assert.ok(
        !rendered.includes('undefined'),
        `${fn.name}(${JSON.stringify(value)}) → ${rendered}`,
      );
      assert.ok(!rendered.includes('NaN'), `${fn.name}(${JSON.stringify(value)}) → ${rendered}`);
    }
  }
});

// The three helpers below shipped during a browser pass, which is the weakest place to add a
// formatter from: a screenshot shows one value in one timezone, and every rule worth having here is
// about a value the fixtures always populate or a zone the author does not live in.

test('a bare date is not shifted a day backwards by the local timezone', () => {
  // **This is what `TZ=America/Los_Angeles` in the npm script is for.** `new Date('2026-11-10')` is
  // UTC midnight, which is the 9th at 16:00 in Los Angeles — so a locally-formatted trip that starts
  // on the 10th renders as the 9th. Nobody reports it and everybody notices.
  assert.match(day('2026-11-10'), /10/);
  assert.match(day('2026-11-10'), /Nov/);
  assert.match(day('2026-01-01'), /1 Jan 2026|Jan 1, 2026/);
});

test('a date-only value keeps its day at both ends of the year', () => {
  // The turn of the year is where an off-by-one hour becomes an off-by-one *year*.
  assert.match(day('2026-12-31'), /31.*Dec.*2026|Dec 31, 2026/);
  assert.match(day('2027-01-01'), /1.*Jan.*2027|Jan 1, 2027/);
});

test('an unparseable date is null rather than Invalid Date on a card', () => {
  for (const absent of [null, undefined, '', 'soon', 'next Tuesday', 42, {}, '2026-13-45']) {
    const rendered = day(absent);
    assert.ok(
      rendered === null || !/Invalid|NaN/.test(rendered),
      `day(${JSON.stringify(absent)}) → ${rendered}`,
    );
  }
});

test('a timestamp keeps its time and states the zone it is in', () => {
  // `day()` matches only the leading date, so reusing it here would have silently dropped the clock
  // time from a booking confirmation — a quieter wrong answer than the raw ISO string it replaced.
  const rendered = timestamp('2026-08-21T19:06:56.646301');
  assert.match(rendered, /19:06/, 'the time survives');
  assert.match(rendered, /UTC/, 'and is labelled, so 19:06 is not read as local');
  assert.match(rendered, /21|Aug/);
});

test('an offset-less timestamp is read as UTC, not as local time', () => {
  // The tools send `issued_at` with no offset. JavaScript reads that as *local*, so under the pinned
  // TZ an unfixed implementation renders 19:06 as 02:06 the next day — seven hours and one date out.
  const naive = timestamp('2026-08-21T19:06:56.646301');
  const explicit = timestamp('2026-08-21T19:06:56Z');
  assert.equal(naive, explicit, 'a naive timestamp must mean the same instant as an explicit Z');
});

test('an explicit offset is respected rather than assumed away', () => {
  // Only the *absent* case is assumed. A value that states its offset is converted, so this must not
  // read as 19:06.
  const rendered = timestamp('2026-08-21T19:06:56+05:30');
  assert.match(rendered, /13:36/, '+05:30 is 13:36 UTC');
  assert.doesNotMatch(rendered, /19:06/);
});

test('a value that is not a timestamp is null, including a bare date', () => {
  // A bare date returns null rather than midnight: `00:00 UTC` on a card asserts a precision the
  // value does not carry. `day()` is the right formatter for those.
  for (const absent of [null, undefined, '', '2026-08-21', 'yesterday', 42, {}, []]) {
    assert.equal(timestamp(absent), null, `timestamp(${JSON.stringify(absent)})`);
  }
});

test('a place renders its city rather than [object Object]', () => {
  // The defect this guards put `[object Object]` on every trip tile while thirty API checks passed.
  assert.equal(placeName({ name: 'Heathrow', city: 'London' }), 'London');
  assert.equal(placeName({ name: 'Heathrow' }), 'Heathrow', 'name is the fallback with no city');
  assert.equal(placeName('London'), 'London');
  for (const absent of [null, undefined, '', '   ', {}, { city: '' }, 42]) {
    assert.equal(placeName(absent), null, `placeName(${JSON.stringify(absent)})`);
  }
});
