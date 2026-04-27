# Security Review: Token Handling Vulnerabilities

**Date:** 2026-04-27
**Scope:** `06-secure-ide-gateway-tool` — OAuth proxy for VS Code + Amazon Bedrock AgentCore Gateway
**Focus:** Token handling, storage, validation, and transport

---

## Architecture Summary

This is a serverless OAuth proxy that sits between VS Code (MCP client) and AgentCore Gateway. It implements:
- **Inbound auth:** VS Code → Cognito (username/password + PKCE)
- **Outbound auth:** AgentCore → Confluence via 3-legged OAuth (3LO)
- **Components:** MCP Proxy Lambda, Callback Lambda, Cookie Authorizer, CDK infrastructure

---

## Findings

### 1. Tokens Stored in Browser localStorage — HIGH

**Files:** `lambda/mcp_proxy_lambda.py` (lines ~799-806), `lambda/callback_lambda.py` (lines ~171-172, ~300)

```javascript
localStorage.setItem('access_token', data.access_token);
localStorage.setItem('id_token', data.id_token);
localStorage.setItem('refresh_token', data.refresh_token);
```

**Risk:** localStorage is readable by any JavaScript on the page, including XSS payloads and malicious browser extensions. Tokens persist indefinitely with no automatic expiration.

**Recommendation:** Move tokens to `HttpOnly; Secure; SameSite=Strict` cookies. Add Content Security Policy headers to mitigate XSS.

---

### 2. JWT Bearer Token Passed in URL Query Parameter — HIGH

**File:** `lambda/mcp_proxy_lambda.py` (lines ~544-563)

```python
params = urllib.parse.urlencode(
    {"redirect_url": original_url, "state": user_token}
)
elicitation["url"] = f"{callback_url}/elicitation-redirect?{params}"
```

The user's Cognito JWT is embedded in the `state` query parameter of the elicitation redirect URL.

**Risk:** URLs are logged in browser history, HTTP server logs, proxy logs, CDN logs, and leaked via `Referer` headers. This is equivalent to putting a password in a URL.

**Recommendation:** Use a short-lived, opaque session identifier that maps to the token server-side (e.g., in DynamoDB with a short TTL). Never transport JWTs in URLs.

---

### 3. JWT Decoded Without Signature Verification — MEDIUM-HIGH

**File:** `lambda/callback_lambda.py` (lines ~18-25, ~96-103)

```python
def _decode_jwt_payload(token):
    """Decode the payload of a JWT without verifying the signature."""
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.b64decode(payload_b64).decode())
```

This function is used to check token expiry and extract `sub`/`iss` claims — but without verifying the signature, any attacker can craft a JWT with arbitrary claims.

**Note:** The `cookie_authorizer/index.js` *does* verify signatures correctly via `CognitoJwtVerifier`. The inconsistency between the two validation paths is itself a risk.

**Recommendation:** Use verified JWT decoding everywhere. Use `python-jose` or `PyJWT` with Cognito's JWKS endpoint.

---

### 4. OAuth `state` Parameter Misused as Bearer Credential — MEDIUM

**File:** `lambda/callback_lambda.py` (lines ~96-103, ~300-301)

The OAuth `state` parameter is designed to prevent CSRF — it should be a random, opaque value. Here it carries the actual Cognito access token, conflating two security mechanisms.

**Risk:** If `state` leaks (which is likely given finding #2), the attacker has a valid bearer token.

**Recommendation:** Use `state` only for CSRF prevention. Pass identity via HttpOnly cookies or server-side session lookup.

---

### 5. Missing `HttpOnly` Flag on Login Cookies — MEDIUM

**File:** `lambda/mcp_proxy_lambda.py` (lines ~273-276)

```python
"cookies": [
    f"access_token={access_token}; Path=/; Secure; SameSite=Lax; Max-Age={expires_in}",
    f"refresh_token={refresh_token}; Path=/; Secure; SameSite=Lax;",
],
```

The `HttpOnly` flag is missing, making these cookies readable by JavaScript. The callback lambda *does* set `HttpOnly` on its cookies (lines ~131-133), creating an inconsistency.

**Recommendation:** Add `HttpOnly` to all token cookies across all code paths.

---

### 6. No Token Expiry Validation in MCP Proxy — MEDIUM

**File:** `lambda/mcp_proxy_lambda.py` (lines ~442-541)

```python
auth = headers.get("authorization")
if auth:
    req.add_header("Authorization", auth)  # No expiry check
```

The proxy forwards authorization headers to AgentCore Gateway without checking whether the token has expired.

**Recommendation:** Decode and verify the token's `exp` claim before forwarding. Return 401 with a clear message if expired.

---

### 7. IAM Permissions Too Broad — MEDIUM

**File:** `cdk/lib/cdk-stack.ts` (lines ~181-190)

```typescript
actions: [
    "bedrock-agentcore:CompleteResourceTokenAuth",
    "secretsmanager:GetSecretValue",
    "kms:Decrypt",
],
resources: ["*"],
```

The callback Lambda can read ANY secret in the account and decrypt with ANY KMS key.

**Recommendation:** Scope `resources` to the specific Secret ARN and KMS key ARN used by this stack. Use `cdk.Stack.of(this).formatArn(...)` to construct specific ARNs.

---

### 8. Debug Mode Exposes Tokens in Browser — MEDIUM

**File:** `lambda/callback_lambda.py` (lines ~271-343)

```javascript
document.getElementById('debug-jwt').value = jwt;
document.getElementById('debug-payload').value = JSON.stringify(tokenPayload, null, 2);
```

When debug mode is enabled (via environment variable), raw JWTs and decoded payloads are rendered in HTML textarea elements — accessible to XSS, screenshots, and screen recordings.

**Recommendation:** Remove debug mode entirely, or restrict it to a separate deployment stage. Never render raw tokens in a browser UI.

---

### 9. No Redirect URI Validation — MEDIUM

**File:** `lambda/mcp_proxy_lambda.py` (lines ~307-328, ~544-563)

Neither the authorization code exchange nor the elicitation redirect validates `redirect_uri` against a whitelist. An attacker who controls `redirect_url` could redirect the user (and their token) to a malicious site.

**Recommendation:** Maintain a strict allowlist of valid redirect URIs. Validate the `redirect_uri` parameter in both the `/authorize` and `/token` endpoints against the stored value from the initial request.

---

### 10. PKCE Allows `plain` Method — LOW-MEDIUM

**File:** `lambda/mcp_proxy_lambda.py` (lines ~340-364)

```python
elif code_challenge_method == "plain":
    if code_verifier != code_challenge:
        return json_response(...)
```

The `plain` PKCE method provides no protection against authorization code interception. PKCE is also not enforced as mandatory.

**Recommendation:** Accept only `S256`. Make PKCE mandatory for all public clients.

---

### 11. No Rate Limiting on Auth Endpoints — LOW-MEDIUM

**File:** `lambda/mcp_proxy_lambda.py` — `/login`, `/token`, `/authorize` endpoints

No rate limiting is implemented on password login or token exchange endpoints.

**Recommendation:** Enable API Gateway throttling. Add WAF rules for OAuth endpoints. Consider account lockout after repeated failures.

---

### 12. Authorization Code Exchange Missing Client Validation — LOW-MEDIUM

**File:** `lambda/mcp_proxy_lambda.py` (lines ~307-328)

The `/token` endpoint does not require or validate a `client_id` when exchanging an authorization code. Any party with the code can exchange it.

**Recommendation:** Require `client_id` on the token endpoint and validate it matches the original authorization request.

---

## Priority Matrix

| Priority | Findings | Action |
|----------|----------|--------|
| **Immediate** | #1 (localStorage), #2 (token in URL), #3 (JWT no verify) | Fix before any production use |
| **Short-term** | #4 (state misuse), #5 (HttpOnly), #6 (expiry), #7 (IAM), #8 (debug) | Fix within next sprint |
| **Medium-term** | #9 (redirect), #10 (PKCE), #11 (rate limit), #12 (client validation) | Plan and schedule |

---

## Files Reviewed

| File | Purpose |
|------|---------|
| `lambda/mcp_proxy_lambda.py` | Main OAuth proxy — login, token, authorize, MCP proxy |
| `lambda/callback_lambda.py` | OAuth callback handler for 3LO flows |
| `lambda/cookie_authorizer/index.js` | API Gateway Lambda authorizer (JWT verification) |
| `cdk/lib/cdk-stack.ts` | Infrastructure-as-code (CDK) |
| `utils.py` | Deployment utilities |
| `README.md` | Documentation |
