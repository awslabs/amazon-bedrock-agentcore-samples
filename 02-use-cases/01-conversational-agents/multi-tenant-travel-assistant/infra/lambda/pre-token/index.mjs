/**
 * Pre token generation trigger (event version V2_0) — mirror identity onto the
 * access token.
 *
 * **This is not the trigger the design rejected, and the difference is the whole
 * point.** An earlier draft used a pre-token Lambda to compute `can_book_for`:
 * *authorization* data, owned by the travel platform, which would have gone stale
 * for the token's lifetime and could not express a derived relationship
 * ("arranger for cost centre 4400"). That is still rejected — arranger
 * relationships are resolved live, in `backend/app/service/arrangers.py`.
 *
 * This trigger copies three *identity* claims that Cognito already holds about
 * the person. It invents nothing and duplicates nothing: the user pool is the
 * system of record for "which tenant does this person belong to", and the claims
 * are read straight off the verified user attributes.
 *
 * **Why it is needed at all.** Cognito puts custom attributes in the **ID token**
 * only. The bearer that reaches Runtime and the Gateway is an **access token**,
 * because that is the token type built for authorization — and it arrives with no
 * `custom:tenant_id`. Without this trigger the interceptor has nothing to inject,
 * and the alternative (pass the ID token as a bearer) means using an
 * authentication artifact for authorization, which is the anti-pattern the two
 * token types exist to separate.
 *
 * Second job: **scopes.** Cognito only issues custom scopes through the OAuth
 * endpoints. Tokens obtained by the user pools API (`USER_PASSWORD_AUTH`, which
 * the terminal demo and integration tests use) carry only
 * `aws.cognito.signin.user.admin`. Adding the entitled scopes here means one code
 * path is exercised by both flows, rather than the tests proving something the
 * real front door does differently.
 */

/** Cognito addresses custom attributes with this prefix. */
const CUSTOM = 'custom:';

const TENANT_CLAIM = `${CUSTOM}tenant_id`;
const TRAVELER_CLAIM = `${CUSTOM}traveler_id`;
const ROLE_CLAIM = `${CUSTOM}role`;

/**
 * Must match `SCOPE_READ` / `SCOPE_BOOK` in `infra/lib/identity.ts`.
 *
 * **`<resource-server>/<scope>`, with a slash.** That is the string Cognito emits
 * for a resource-server scope obtained through the OAuth endpoints, and the
 * strings added here must be identical or the two auth flows would produce
 * different scope claims — leaving the Gateway's `--allowed-scopes` matching one
 * flow and silently rejecting the other. An OAuth-conventions habit writes
 * `travel:read` here; it is wrong, and it fails closed with no useful error.
 */
const SCOPE_READ = 'travel/read';
const SCOPE_BOOK = 'travel/book';

/**
 * Scopes a role is entitled to.
 *
 * Both roles get both scopes: a traveller books their own travel, an arranger
 * books for others, and neither distinction is a *scope* distinction — that is
 * Cedar's job, because "may Adaeze book for Priya" depends on facts a static
 * scope cannot see. The map exists so a read-only integration remains expressible
 * without touching policy, which is the only thing scopes are load-bearing for.
 */
const SCOPES_BY_ROLE = {
  traveler: [SCOPE_READ, SCOPE_BOOK],
  arranger: [SCOPE_READ, SCOPE_BOOK],
};

/**
 * **There is no read-only fallback, because nothing enforces a read-only scope.**
 *
 * This was `[SCOPE_READ]`, commented "least privilege for an unrecognised role: read, never book".
 * That was false. The Gateway's `allowedScopes` admits either scope, and `booking.cedar` permits the
 * three write tools on a verified tenant tag alone — it never reads a scope. So a token carrying
 * only `travel/read` could invoke `confirm_booking` exactly like any other, and the "fallback" bought
 * nothing while reading as a control.
 *
 * An unrecognised role is a provisioning fault, so it now fails the sign-in the same way a missing
 * tenant does — at the point of the mistake, rather than by issuing a credential with imaginary
 * limits. Adding a role means adding it to `SCOPES_BY_ROLE`.
 *
 * If a genuinely read-only integration is ever needed, the scope has to become load-bearing: either
 * a Cedar condition on the booking permit that reads the verified scope claim, or separate read and
 * write Gateways. Both are real work; neither is what a silent fallback was doing.
 */

export const handler = async (event) => {
  const attributes = event.request?.userAttributes ?? {};

  const tenantId = attributes[TENANT_CLAIM];
  const travelerId = attributes[TRAVELER_CLAIM];
  const role = attributes[ROLE_CLAIM];

  // A user without a tenant is a provisioning failure, and it must not become a
  // token. Returning the event unchanged would issue a credential that
  // authenticates cleanly and then fails deep inside a tool, where the cause is
  // invisible. Throwing fails the sign-in instead, at the point of the mistake.
  if (!tenantId || !travelerId) {
    console.error(
      JSON.stringify({
        decision: 'refused to issue a token',
        reason: 'user is missing required identity claims',
        // The username, not the missing values — this line is diagnostic, and
        // logging attribute contents would put identity data in CloudWatch.
        username: event.userName,
        has_tenant: Boolean(tenantId),
        has_traveler: Boolean(travelerId),
      }),
    );
    throw new Error('user is not provisioned with tenant_id and traveler_id');
  }

  // Same shape as the identity check above, and for the same reason: an unrecognised role is a
  // provisioning fault, and a token minted for one would carry scopes nothing enforces.
  const scopes = SCOPES_BY_ROLE[role];
  if (!scopes) {
    console.error(
      JSON.stringify({
        decision: 'refused to issue a token',
        reason: 'role is not one this deployment issues scopes for',
        username: event.userName,
        // The role value is a fixed vocabulary, not identity data, so naming it is diagnostic.
        role: role ?? null,
        known_roles: Object.keys(SCOPES_BY_ROLE),
      }),
    );
    throw new Error(`user has an unrecognised role: ${role ?? '(absent)'}`);
  }

  // Identity claims only. If `can_book_for` (or any other authorization fact)
  // ever appears in this object, the design has drifted back to the thing we
  // deliberately removed.
  const claims = {
    [TENANT_CLAIM]: tenantId,
    [TRAVELER_CLAIM]: travelerId,
    [ROLE_CLAIM]: role ?? 'traveler',
  };

  console.log(
    JSON.stringify({
      decision: 'issued token with tenant context',
      tenant_id: tenantId,
      traveler_id: travelerId,
      role: role ?? 'traveler',
      scopes,
      trigger_source: event.triggerSource,
    }),
  );

  event.response = {
    claimsAndScopeOverrideDetails: {
      // The ID token already carries these; restating them keeps the two token
      // types consistent so nothing downstream has to care which it received.
      idTokenGeneration: { claimsToAddOrOverride: claims },
      accessTokenGeneration: {
        claimsToAddOrOverride: claims,
        scopesToAdd: scopes,
      },
    },
  };

  return event;
};
