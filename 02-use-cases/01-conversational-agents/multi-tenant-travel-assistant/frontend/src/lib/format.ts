/**
 * Turning the tools' machine values into what a person reads on a card.
 *
 * **Its own module so it can be tested without a browser.** These helpers carry the coercion rules
 * that decide whether an absent field reads as an honest dash or as a confident wrong fact — and that
 * distinction is invisible in a screenshot of fixture data, where the fields are always present. A
 * `.tsx` would need a JSX transform before `node --test` could import it; a `.ts` does not, because
 * Node strips types natively.
 *
 * Nothing here renders markup. `CardView` owns presentation; this owns the arithmetic and the
 * absences.
 */

/**
 * A number the tool actually sent, or `null`.
 *
 * **`Number()` alone is not enough, and the gap produces wrong facts rather than blanks.** It maps
 * `null`, `undefined` and `''` to **zero**, all of which are finite — so a `Number.isFinite` guard
 * waves them straight through. Three fields on these cards were affected and each failed differently:
 * an absent duration rendered `0m`, an absent stop count rendered **"Direct"**, and an absent distance
 * rendered a `0 m` badge. A dash is an honest absence; a zero is a claim.
 */
export function finiteNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * `{amount, currency}` as the traveller's own currency, which is a per-tenant fact.
 *
 * **Rendered to the cent, deliberately.** Rounding to whole units put `€111` on the card beside the
 * model's own "110.54 EUR per night" in the prose directly above it — the same fact stated two ways in
 * one screenshot, which reads as a system that cannot keep its numbers straight. A price is the one
 * figure a traveller checks against an expense claim, so the card shows what will be charged.
 */
export function money(value: unknown): string {
  if (!value || typeof value !== 'object') return '—';
  const { amount, currency } = value as { amount?: number; currency?: string };
  if (amount === undefined) return '—';
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: currency ?? 'USD',
    }).format(amount);
  } catch {
    // An unrecognised currency code must not blank out a price.
    return `${amount} ${currency ?? ''}`.trim();
  }
}

/**
 * A duration in minutes as `5h 32m`.
 *
 * Hours are omitted below sixty rather than shown as `0h`, since no one says "zero hours forty".
 */
export function minutes(value: unknown): string {
  const total = finiteNumber(value);
  if (total === null) return '—';
  const hours = Math.floor(total / 60);
  return hours > 0 ? `${hours}h ${total % 60}m` : `${total}m`;
}

/** A stop count, where zero is the useful word rather than the useful digit. */
export function stops(value: unknown): string {
  const count = finiteNumber(value);
  if (count === null) return '—';
  return count === 0 ? 'Direct' : String(count);
}

/**
 * A star rating split into filled and unfilled, clamped to the five-point scale.
 *
 * **Returns counts rather than a string so the scale can be rendered.** `★★★` alone cannot be read as
 * "3 of 5" — the denominator is missing, and a two-star hotel beside a three-star one just looks like
 * less of something unquantified.
 *
 * `null` for an absent rating, which must not become five empty stars: that would assert a zero-star
 * hotel where the tool simply sent nothing.
 */
export function starRating(value: unknown): { filled: number; empty: number } | null {
  const rating = finiteNumber(value);
  if (rating === null) return null;
  const filled = Math.max(0, Math.min(5, Math.round(rating)));
  return { filled, empty: 5 - filled };
}

/** A distance badge: metres below a kilometre, then one decimal place. */
export function distance(value: unknown): string | null {
  const metres = finiteNumber(value);
  if (metres === null) return null;
  return metres < 1000 ? `${metres} m` : `${(metres / 1000).toFixed(1)} km`;
}

/**
 * A place as a single readable line.
 *
 * **A destination is an object, not a string**, and rendering it with `String()` put
 * `[object Object]` on every trip tile while thirty API checks passed — the payload was correct all
 * along. The tools send `{name, city, address?, country?}` (see `_place` in `tools/trips/handler.py`),
 * so the city is what a traveller recognises and the name is the fallback when a place has no city.
 *
 * Returns `null` rather than a placeholder, so a caller can choose what an unnameable place looks
 * like instead of inheriting a dash from here.
 */
export function placeName(value: unknown): string | null {
  if (typeof value === 'string') return value.trim() || null;
  if (!value || typeof value !== 'object') return null;
  const place = value as { name?: unknown; city?: unknown };
  for (const candidate of [place.city, place.name]) {
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim();
  }
  return null;
}

/**
 * An ISO date as `10 Feb 2026`.
 *
 * Tools send dates as `YYYY-MM-DD`, which is unambiguous and unpleasant to read in a heading.
 * Parsed as UTC deliberately: a bare date has no timezone, and letting the browser apply a local one
 * shifts it a day backwards for anyone west of Greenwich — a trip that started on the 10th showing
 * as the 9th is the kind of wrong nobody reports and everybody notices.
 */
export function day(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value.trim());
  if (!match) return null;
  const [, year, month, date] = match;
  const parsed = new Date(Date.UTC(Number(year), Number(month) - 1, Number(date)));
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/**
 * An ISO timestamp as `21 Aug 2026, 19:06 UTC`.
 *
 * Separate from `day()` because `day()` matches only the leading date and would silently drop the
 * time — which is wrong for a booking: the confirmed card showed a raw
 * `2026-08-21T19:06:56.646301`, and formatting it as a bare date would have replaced one wrong answer
 * with a less obviously wrong one.
 *
 * **A naive timestamp is read as UTC, and labelled as UTC.** The tools send no offset (see
 * `issued_at` from `tools/booking/handler.py`), and JavaScript reads an offset-less string as *local*
 * time — so a booking made at 19:06 UTC would render as 19:06 in whatever zone the reader happens to
 * be in, which is the same class of quiet error as `day()`'s day-shift. An explicit offset in the
 * value is respected; only the absent case is assumed.
 */
export function timestamp(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const text = value.trim();
  if (!/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(text)) return null;
  const hasOffset = /(?:Z|[+-]\d{2}:?\d{2})$/.test(text);
  const parsed = new Date(hasOffset ? text : `${text.replace(' ', 'T')}Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  const date = parsed.toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
  const time = parsed.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  });
  return `${date}, ${time} UTC`;
}
