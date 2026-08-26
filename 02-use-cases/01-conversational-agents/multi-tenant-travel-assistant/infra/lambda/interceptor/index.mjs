/**
 * Gateway request interceptor — **this is the verifier**.
 *
 * The Gateway forwards the raw bearer token and delegates the trust decision here, so
 * this function fetches Cognito's JWKS, validates the signature itself, and injects the
 * verified tenant context as headers. Confirmed against the `lakehouse-agent` sample,
 * which solves the same problem (row-level security from OAuth claims).
 *
 * ```
 * event.mcp.gatewayRequest.headers   // includes Authorization
 * event.mcp.gatewayRequest.body      // the MCP JSON-RPC envelope
 * ```
 *
 * **Delegation, not impersonation.** The traveller's token stops here. Downstream the
 * tool sees only `X-Tenant-Id` / `X-Traveler-Id` / `X-Traveler-Role`, and trusts them
 * because the tool Lambda's resource policy admits only the Gateway role — so a request
 * that arrives came from the Gateway, which forwards only what this function produced.
 * No KMS signing: that would defend against a compromised Gateway, outside the threat
 * model, at the cost of a KMS call per request.
 *
 * **Headers only, never `body.params.arguments`.** Tool arguments are model-adjacent —
 * the one part of a request a prompt-injected model can shape. The lakehouse sample puts
 * credentials in arguments; that part is deliberately not copied.
 *
 * No dependencies. JWT verification is a signature check over two base64url segments,
 * and `node:crypto` does RSA-SHA256 natively. Pulling in `jose` or
 * `aws-jwt-verify` would add cold-start latency on the conversational path for code
 * that fits on one screen.
 */

import { createPublicKey, createVerify } from 'node:crypto';

const TENANT_CLAIM = 'custom:tenant_id';
const TRAVELER_CLAIM = 'custom:traveler_id';
const ROLE_CLAIM = 'custom:role';

// Must match `tools/common/context.py`. They cross a language boundary, so a test
// asserts the two sides agree.
//
// **These three must ALSO appear in each target's `metadataConfiguration.
// allowedRequestHeaders`.** Injecting a header here is not sufficient: except for
// `Authorization`, interceptor-provided headers are dropped unless allowlisted on the
// target. The failure is silent — the tool simply sees no tenant and refuses, which
// reads like a broken interceptor rather than a missing allowlist entry.
//
// Interceptor values take precedence over client-provided ones for the same name, which
// is the security property we depend on: a caller cannot preset the tenant.
const TENANT_HEADER = 'X-Tenant-Id';
const TRAVELER_HEADER = 'X-Traveler-Id';
const ROLE_HEADER = 'X-Traveler-Role';

// **An audit label, not an identity header — and handled differently on purpose.**
//
// The agent sets this to its runtime session id, so a DynamoDB row read can be traced back to
// one conversation: the backend puts it on an STS session tag, and CloudTrail records the tag.
// Three deliberate differences from the three headers above:
//
//   1. It is **passed through**, not derived from a claim — there is no claim for "which
//      conversation is this", and inventing one would be worse than forwarding it.
//   2. It is therefore **not stripped** from the inbound request; a caller may set it.
//   3. That is acceptable *only* because nothing authorises on it. The worst a forged value can
//      do is mislabel the forger's own audit trail. If any policy ever keys off this, it must
//      move into the strip list and be derived from a verified source instead.
//
// Matches `SESSION_HEADER` in `tools/common/context.py`, and like the others it must be
// allowlisted on each target or it silently never arrives.
const SESSION_HEADER = 'X-Session-Id';

const USER_POOL_ID = process.env.USER_POOL_ID;
const AWS_REGION = process.env.COGNITO_REGION ?? process.env.AWS_REGION;
const EXPECTED_CLIENT_IDS = (process.env.ALLOWED_CLIENT_IDS ?? '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);

const ISSUER = `https://cognito-idp.${AWS_REGION}.amazonaws.com/${USER_POOL_ID}`;
const JWKS_URL = `${ISSUER}/.well-known/jwks.json`;

/**
 * MCP methods that carry no tool call and must pass through untouched.
 *
 * Enforcing on `initialize` or `tools/list` breaks discovery: the agent lists tools
 * before it has any reason to have a tenant, and a rejection there looks like a broken
 * Gateway rather than an auth failure. (Learned the hard way on Tripp.)
 */
const UNAUTHENTICATED_METHODS = new Set([
  'initialize',
  'notifications/initialized',
  'tools/list',
  'prompts/list',
  'resources/list',
  'resources/templates/list',
  'ping',
]);

/**
 * JWKS cached across invocations.
 *
 * Cognito rotates signing keys rarely, and a fetch per tool call would add a network
 * round trip to every request. Keyed by `kid` so a rotation is a cache miss on the new
 * key rather than a hard failure.
 */
let jwksCache = null;
let jwksFetchedAt = 0;
const JWKS_TTL_MS = 60 * 60 * 1000;

async function getJwks(forceRefresh = false) {
  const fresh = jwksCache && Date.now() - jwksFetchedAt < JWKS_TTL_MS;
  if (fresh && !forceRefresh) return jwksCache;

  const response = await fetch(JWKS_URL);
  if (!response.ok) {
    throw new Error(`JWKS fetch failed: ${response.status}`);
  }
  const { keys } = await response.json();
  jwksCache = new Map(keys.map((key) => [key.kid, key]));
  jwksFetchedAt = Date.now();
  return jwksCache;
}

function base64UrlDecode(segment) {
  return Buffer.from(segment.replace(/-/g, '+').replace(/_/g, '/'), 'base64');
}

/**
 * Verify signature, then claims — in that order.
 *
 * Nothing in the payload may be trusted before the signature checks out, which is why
 * the issuer and expiry are validated *after* rather than as a cheap early exit on
 * decoded-but-unverified content.
 */
async function verifyToken(token) {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('malformed token');

  const [headerSegment, payloadSegment, signatureSegment] = parts;
  const header = JSON.parse(base64UrlDecode(headerSegment).toString());

  if (header.alg !== 'RS256') {
    // Refuse rather than accommodate: `alg: none` and HMAC confusion are the classic
    // JWT attacks, and Cognito only ever issues RS256.
    throw new Error(`unexpected algorithm: ${header.alg}`);
  }

  let jwks = await getJwks();
  let jwk = jwks.get(header.kid);
  if (!jwk) {
    // Unknown `kid` is the shape of a key rotation, so refetch once before failing.
    jwks = await getJwks(true);
    jwk = jwks.get(header.kid);
  }
  if (!jwk) throw new Error('signing key not found');

  const publicKey = createPublicKey({ key: jwk, format: 'jwk' });
  const verifier = createVerify('RSA-SHA256');
  verifier.update(`${headerSegment}.${payloadSegment}`);

  if (!verifier.verify(publicKey, base64UrlDecode(signatureSegment))) {
    throw new Error('signature verification failed');
  }

  const claims = JSON.parse(base64UrlDecode(payloadSegment).toString());

  if (claims.iss !== ISSUER) throw new Error('unexpected issuer');
  if (typeof claims.exp !== 'number' || claims.exp * 1000 <= Date.now()) {
    throw new Error('token expired');
  }
  // Access tokens carry `client_id`; ID tokens carry `aud`. Checking both means an ID
  // token presented as a bearer still has to come from a client we recognise.
  const clientId = claims.client_id ?? claims.aud;
  if (EXPECTED_CLIENT_IDS.length && !EXPECTED_CLIENT_IDS.includes(clientId)) {
    throw new Error('unexpected client');
  }
  if (claims.token_use && claims.token_use !== 'access') {
    // The access token is the one built for authorization. Accepting an ID token here
    // would blur the distinction the two token types exist to keep.
    throw new Error(`unexpected token_use: ${claims.token_use}`);
  }

  return claims;
}

/**
 * A denial the model can understand.
 *
 * A valid JSON-RPC result with `isError: true`, carrying the original request id — not
 * a transport failure. The model can relay "I'm not able to do that"; it cannot relay a
 * 500.
 *
 * **`transformedGatewayResponse` short-circuits the call**: when a request interceptor
 * returns one, the gateway responds with it immediately and never reaches the target,
 * even if `transformedGatewayRequest` is also present. That is exactly the deny
 * semantics we want, and it is why the key name matters — `gatewayResponse` (the *input*
 * field name) would be ignored and the request would proceed unauthenticated.
 */
function denial(requestId, message) {
  return {
    interceptorOutputVersion: '1.0',
    mcp: {
      transformedGatewayResponse: {
        statusCode: 200,
        body: {
          jsonrpc: '2.0',
          id: requestId ?? null,
          result: {
            isError: true,
            content: [{ type: 'text', text: message }],
          },
        },
      },
    },
  };
}

function passThrough(headers, body) {
  return {
    interceptorOutputVersion: '1.0',
    mcp: { transformedGatewayRequest: { headers, body } },
  };
}

export const handler = async (event) => {
  const request = event?.mcp?.gatewayRequest ?? {};
  const headers = { ...(request.headers ?? {}) };
  const body = request.body ?? {};
  const method = body?.method;
  const requestId = body?.id;

  // Discovery and lifecycle traffic passes untouched, or tool listing breaks.
  if (UNAUTHENTICATED_METHODS.has(method)) {
    console.log(JSON.stringify({ decision: 'passed through unauthenticated method', method }));
    return passThrough(headers, body);
  }

  // Header names are case-insensitive and the casing that arrives has varied, so match
  // case-insensitively rather than on an exact string.
  const authKey = Object.keys(headers).find((k) => k.toLowerCase() === 'authorization');
  const authorization = authKey ? headers[authKey] : undefined;

  if (!authorization?.toLowerCase().startsWith('bearer ')) {
    console.warn(JSON.stringify({ refusal: 'no bearer token on a tool call', method }));
    return denial(requestId, 'I could not verify who this request is for.');
  }

  let claims;
  try {
    claims = await verifyToken(authorization.slice(7).trim());
  } catch (error) {
    // The reason is logged but never returned: telling a caller *why* verification
    // failed is a probing oracle.
    console.warn(
      JSON.stringify({ refusal: 'token verification failed', reason: error.message, method }),
    );
    return denial(requestId, 'I could not verify who this request is for.');
  }

  const tenantId = claims[TENANT_CLAIM];
  const travelerId = claims[TRAVELER_CLAIM];

  if (!tenantId || !travelerId) {
    // A validly signed token without tenant context is a provisioning failure. It must
    // not become an unscoped request, which is what passing it through would mean.
    console.error(
      JSON.stringify({
        refusal: 'verified token carries no tenant context',
        method,
        has_tenant: Boolean(tenantId),
        has_traveler: Boolean(travelerId),
      }),
    );
    return denial(requestId, 'Your account is missing travel profile information.');
  }

  // Strip any inbound copies before injecting: a caller must not be able to preset the
  // header the tools trust. Rejecting outright would be defensible, but silently
  // overwriting is the behaviour with no bypass to find.
  for (const key of Object.keys(headers)) {
    const lower = key.toLowerCase();
    if (
      lower === TENANT_HEADER.toLowerCase() ||
      lower === TRAVELER_HEADER.toLowerCase() ||
      lower === ROLE_HEADER.toLowerCase()
    ) {
      delete headers[key];
    }
  }

  headers[TENANT_HEADER] = tenantId;
  headers[TRAVELER_HEADER] = travelerId;
  headers[ROLE_HEADER] = claims[ROLE_CLAIM] ?? 'traveler';

  // The conversation id, forwarded untouched. Read case-insensitively because header casing
  // has varied by caller, and matching one exact spelling is a bug waiting for a client change.
  const sessionId = Object.keys(headers).find(
    (k) => k.toLowerCase() === SESSION_HEADER.toLowerCase(),
  );

  // Ids and scopes only — never the token, never a name. The tool name comes from the
  // MCP body so a trajectory can be reconstructed from interceptor logs alone.
  console.log(
    JSON.stringify({
      decision: 'injected verified tenant context',
      method,
      tool: body?.params?.name,
      tenant_id: tenantId,
      traveler_id: travelerId,
      role: headers[ROLE_HEADER],
      scopes: claims.scope,
      session_id: sessionId ? headers[sessionId] : null,
    }),
  );

  // A tool call with no conversation id is not an error — the row read still succeeds and is
  // still tenant-scoped — but it *is* a hole in the audit trail, and holes that are never
  // reported become permanent. Warned rather than refused: the alternative trades a working
  // request for a tidier log.
  if (method === 'tools/call' && !sessionId) {
    console.warn(
      JSON.stringify({
        warning:
          'tools/call arrived with no X-Session-Id — CloudTrail cannot attribute this ' +
          'data access to a conversation',
        tool: body?.params?.name,
        tenant_id: tenantId,
      }),
    );
  }

  return passThrough(headers, body);
};
