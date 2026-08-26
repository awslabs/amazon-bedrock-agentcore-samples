import * as logs from 'aws-cdk-lib/aws-logs';

/**
 * PII masking at log **ingestion** — the backstop, not the primary control.
 *
 * **The primary control is the tool layer**, which never emits a passport number, loyalty number
 * or card digit to begin with (`tools/profile/handler.py`, including digits smuggled inside a
 * card *label*, which a field-level allowlist misses). "Never present" beats "present then
 * masked", so this exists for what that layer cannot reach: our own diagnostic lines, output
 * from third-party libraries, and stack traces that quote a request body.
 *
 * **A control rather than a convention**, which is the reason it is worth having at all. It does
 * not depend on every future developer remembering a helper — it applies at ingestion to
 * everything written to the group, including code nobody on the team wrote.
 *
 * **Masking is an access boundary, not redaction.** The value is stored, and `logs:Unmask` is a
 * *separate* permission — so an operator with full log-read access still cannot see a passport
 * number, while an incident responder who genuinely needs it can be granted that permission
 * deliberately and audibly. That is the more interesting half of the control, and it is why
 * masking beats dropping the field.
 *
 * **What is deliberately NOT masked, and why it matters more than what is:**
 *
 * - **Opaque ids** — `trv_31d81fa59772`, `globex`, `off_…`. They identify a record, not a person,
 *   and masking them would destroy the debuggability that made them opaque in the first place.
 *   Choosing opaque ids early is what makes aggressive masking affordable here.
 * - **`NAME` is masked, but the tools still work**, because names never reach a *tool* response —
 *   the profile tool returns a curated record. If a future feature needs names in logs, the fix
 *   is to stop logging names, not to weaken this list.
 */

/**
 * **The limit that matters most, measured rather than assumed: managed identifiers are
 * keyword-sensitive, so they do NOT reliably mask values nested under a generic JSON key.**
 *
 * Probed directly against a live log group with `PassportNumber-US`:
 *
 * ```
 * {"passport":"X44719025"}                                 -> MASKED
 * passport number X44719025                                -> MASKED
 * {"passport_number":"X44719025"}                          -> unmasked
 * {"passports":[{"country":"US","number":"X44719025"}]}     -> unmasked   <-- our real shape
 * ```
 *
 * The detector wants the literal token `passport` beside the value; `"number"` nested inside a
 * `"passports"` array does not satisfy it. It is also length-sensitive — a 9-character value
 * (9 digits, or a letter plus 8 digits) matches, an 8-character one does not.
 *
 * `Name` and `EmailAddress` have no such problem, because they match on the value's own shape:
 * both are masked in the same log line where the passport is not.
 *
 * **Why this does not change the design, but does change the claim.** This was always the
 * backstop; the primary control is `tools/profile/handler.py`, which never emits a passport
 * number at all. What it does mean is that ingestion masking must not be *relied* on for
 * structured payloads — so the honest statement is "PII is curated at the tool boundary, and log
 * masking catches loose prose and third-party output", not "PII cannot reach our logs".
 *
 * A custom data identifier (a regex over our own field names) would close the gap for our exact
 * schema. Deliberately not added: it would be a second place to encode what PII looks like, it
 * would drift from the model, and it would make the backstop look like a guarantee.
 */

/** Managed identifiers relevant to a corporate travel assistant. */
const IDENTIFIERS = [
  // Travel documents. Multiple countries because a corporate traveller population is not
  // single-nationality, and an unmasked GB passport is no better than an unmasked US one.
  logs.DataIdentifier.PASSPORTNUMBER_US,
  logs.DataIdentifier.PASSPORTNUMBER_GB,
  logs.DataIdentifier.PASSPORTNUMBER_CA,
  logs.DataIdentifier.PASSPORTNUMBER_DE,
  logs.DataIdentifier.PASSPORTNUMBER_FR,
  logs.DataIdentifier.PASSPORTNUMBER_ES,
  logs.DataIdentifier.PASSPORTNUMBER_IT,
  logs.DataIdentifier.DRIVERSLICENSE_US,

  // Payment. The tool layer already strips card digits including those hidden in a label; this
  // catches a backend response body that reached a log line by accident.
  logs.DataIdentifier.CREDITCARDNUMBER,

  // Contact details. Present in the system-of-record profile, never in a curated tool response.
  logs.DataIdentifier.NAME,
  logs.DataIdentifier.EMAILADDRESS,
  logs.DataIdentifier.PHONENUMBER_US,
  logs.DataIdentifier.ADDRESS,
];

/**
 * A fresh policy per log group.
 *
 * Not a shared singleton: `DataProtectionPolicy` is bound to the group it is attached to, and
 * reusing one instance across groups produces a construct-tree conflict rather than the intended
 * sharing. The *identifier list* is shared, which is the part that must not drift.
 */
export function piiMaskingPolicy(): logs.DataProtectionPolicy {
  return new logs.DataProtectionPolicy({
    name: 'multi-tenant-travel-pii-masking',
    description:
      'Masks travel-document, payment and contact PII at ingestion. Backstop only — the tool ' +
      'layer curates PII before it reaches the model. logs:Unmask is required to read values.',
    identifiers: IDENTIFIERS,
    // No `logGroupAuditDestination`: findings would be *copied* to a second log group, and a
    // destination holding unmasked audit findings would reintroduce exactly the exposure this
    // removes. Detections are still visible in the group's own metrics.
  });
}
