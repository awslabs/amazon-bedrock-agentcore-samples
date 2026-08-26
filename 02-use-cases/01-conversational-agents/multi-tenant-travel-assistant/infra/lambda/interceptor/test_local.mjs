/**
 * Interceptor unit tests — run with `node test_local.mjs`.
 *
 * Security-critical code, so the attacks are tested as first-class cases rather than
 * left to a deploy loop: an unsigned token, a wrong-key signature, `alg: none`, an
 * expired token, and a client-supplied tenant header trying to preset identity.
 *
 * A self-signed RSA keypair stands in for Cognito, with `fetch` stubbed to serve its
 * JWKS. That exercises the real verification path — `createPublicKey` from a JWK and an
 * RSA-SHA256 verify — rather than a mock of it.
 */

import { generateKeyPairSync, createSign } from 'node:crypto';
import assert from 'node:assert';

const USER_POOL_ID = 'us-east-1_TESTPOOL';
const REGION = 'us-east-1';
const CLIENT_ID = 'test-client-id';
const ISSUER = `https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}`;

process.env.USER_POOL_ID = USER_POOL_ID;
process.env.COGNITO_REGION = REGION;
process.env.ALLOWED_CLIENT_IDS = CLIENT_ID;

const { publicKey, privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
const { privateKey: otherPrivate } = generateKeyPairSync('rsa', { modulusLength: 2048 });

const KID = 'test-key-1';

// `createPublicKey()` derives a public key from a *private* one and throws on a public
// KeyObject, so export the JWK straight off the public key. Because the JWKS stub runs
// lazily inside the handler, getting this wrong surfaced as "verification failed" — the
// refusal tests then passed for entirely the wrong reason.
function jwk(pub, kid) {
  return { ...pub.export({ format: 'jwk' }), kid, alg: 'RS256', use: 'sig' };
}

// Serve our own JWKS in place of Cognito's.
globalThis.fetch = async () => ({
  ok: true,
  json: async () => ({ keys: [jwk(publicKey, KID)] }),
});

const b64 = (obj) => Buffer.from(JSON.stringify(obj)).toString('base64url');

function mint(claims = {}, { key = privateKey, kid = KID, alg = 'RS256' } = {}) {
  const header = b64({ alg, kid, typ: 'JWT' });
  const payload = b64({
    iss: ISSUER,
    client_id: CLIENT_ID,
    token_use: 'access',
    exp: Math.floor(Date.now() / 1000) + 3600,
    'custom:tenant_id': 'globex',
    'custom:traveler_id': 'trv_31d81fa59772',
    'custom:role': 'traveler',
    scope: 'travel/read travel/book',
    ...claims,
  });
  if (alg === 'none') return `${header}.${payload}.`;
  const signer = createSign('RSA-SHA256');
  signer.update(`${header}.${payload}`);
  return `${header}.${payload}.${signer.sign(key).toString('base64url')}`;
}

const { handler } = await import('./index.mjs');

function event(token, { method = 'tools/call', headers = {}, id = 1 } = {}) {
  return {
    interceptorInputVersion: '1.0',
    mcp: {
      gatewayRequest: {
        path: '/mcp',
        httpMethod: 'POST',
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...headers },
        body: { jsonrpc: '2.0', id, method, params: { name: 'get_travel_policy' } },
      },
    },
  };
}

const injected = (out) => out.mcp?.transformedGatewayRequest?.headers ?? {};
const denied = (out) => Boolean(out.mcp?.transformedGatewayResponse?.body?.result?.isError);

let pass = 0;
const failures = [];
async function check(label, fn) {
  try {
    await fn();
    console.log(`  ok   ${label}`);
    pass++;
  } catch (error) {
    console.log(`  FAIL ${label}: ${error.message}`);
    failures.push(label);
  }
}

console.log('Valid tokens inject verified context');
await check('tenant and traveler injected from claims', async () => {
  const out = await handler(event(mint()));
  const h = injected(out);
  assert.equal(h['X-Tenant-Id'], 'globex');
  assert.equal(h['X-Traveler-Id'], 'trv_31d81fa59772');
  assert.equal(h['X-Traveler-Role'], 'traveler');
});
await check('initech token yields initech, not globex', async () => {
  const out = await handler(
    event(mint({ 'custom:tenant_id': 'initech', 'custom:traveler_id': 'trv_bbc2e338c41a' })),
  );
  assert.equal(injected(out)['X-Tenant-Id'], 'initech');
});
await check('role defaults to traveler when the claim is absent', async () => {
  const out = await handler(event(mint({ 'custom:role': undefined })));
  assert.equal(injected(out)['X-Traveler-Role'], 'traveler');
});

console.log('Forged and malformed tokens are refused');
await check('signature from a different key is refused', async () => {
  assert.ok(denied(await handler(event(mint({}, { key: otherPrivate })))));
});
await check('tampered payload is refused', async () => {
  const token = mint();
  const [h, p, s] = token.split('.');
  const evil = b64({ ...JSON.parse(Buffer.from(p, 'base64url')), 'custom:tenant_id': 'initech' });
  assert.ok(denied(await handler(event(`${h}.${evil}.${s}`))));
});
await check('alg:none is refused', async () => {
  assert.ok(denied(await handler(event(mint({}, { alg: 'none' })))));
});
await check('unknown kid is refused', async () => {
  assert.ok(denied(await handler(event(mint({}, { kid: 'not-our-key' })))));
});
await check('garbage is refused', async () => {
  assert.ok(denied(await handler(event('not-a-token'))));
});
await check('missing bearer is refused', async () => {
  assert.ok(denied(await handler(event(null))));
});

console.log('Claim validation');
await check('expired token is refused', async () => {
  assert.ok(denied(await handler(event(mint({ exp: Math.floor(Date.now() / 1000) - 60 })))));
});
await check('wrong issuer is refused', async () => {
  assert.ok(denied(await handler(event(mint({ iss: 'https://evil.example.com' })))));
});
await check('unknown client is refused', async () => {
  assert.ok(denied(await handler(event(mint({ client_id: 'someone-elses-app' })))));
});
await check('id token presented as a bearer is refused', async () => {
  assert.ok(denied(await handler(event(mint({ token_use: 'id' })))));
});
await check('verified token without tenant claims is refused, not passed through', async () => {
  const out = await handler(event(mint({ 'custom:tenant_id': undefined })));
  assert.ok(denied(out));
  assert.ok(!injected(out)['X-Tenant-Id']);
});

console.log('A caller cannot preset identity');
await check('client-supplied X-Tenant-Id is overwritten', async () => {
  const out = await handler(event(mint(), { headers: { 'X-Tenant-Id': 'initech' } }));
  assert.equal(injected(out)['X-Tenant-Id'], 'globex');
});
await check('lowercase x-tenant-id is also stripped', async () => {
  const out = await handler(event(mint(), { headers: { 'x-tenant-id': 'initech' } }));
  const values = Object.entries(injected(out))
    .filter(([k]) => k.toLowerCase() === 'x-tenant-id')
    .map(([, v]) => v);
  assert.deepEqual(values, ['globex']);
});
await check('spoofed traveler id is overwritten', async () => {
  const out = await handler(event(mint(), { headers: { 'X-Traveler-Id': 'trv_bbc2e338c41a' } }));
  assert.equal(injected(out)['X-Traveler-Id'], 'trv_31d81fa59772');
});

console.log('Discovery traffic passes through untouched');
for (const method of ['initialize', 'tools/list', 'ping']) {
  await check(`${method} needs no token`, async () => {
    const out = await handler(event(null, { method }));
    assert.ok(out.mcp?.transformedGatewayRequest, `${method} must pass through`);
    assert.ok(!denied(out));
  });
}
await check('tools/list does not gain tenant headers', async () => {
  const out = await handler(event(null, { method: 'tools/list' }));
  assert.ok(!injected(out)['X-Tenant-Id']);
});

console.log('Denials are usable by the model');
await check('denial keeps the request id and is a JSON-RPC result', async () => {
  const out = await handler(event('garbage', { id: 42 }));
  const body = out.mcp.transformedGatewayResponse.body;
  assert.equal(body.id, 42);
  assert.equal(body.jsonrpc, '2.0');
  assert.ok(body.result.content[0].text.length > 0);
});
await check('denial does not disclose why verification failed', async () => {
  const text = (
    await handler(event(mint({ exp: 1 })))
  ).mcp.transformedGatewayResponse.body.result.content[0].text.toLowerCase();
  for (const leak of ['expired', 'signature', 'issuer', 'jwks', 'kid']) {
    assert.ok(!text.includes(leak), `leaked "${leak}"`);
  }
});

console.log(`\n${pass} passed, ${failures.length} failed`);
if (failures.length) process.exit(1);
