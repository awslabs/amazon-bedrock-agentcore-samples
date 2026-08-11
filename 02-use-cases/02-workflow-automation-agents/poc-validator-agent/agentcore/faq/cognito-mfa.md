# Should Cognito user pools require MFA?

For any user pool that authenticates access to real user data — not a
machine-to-machine (M2M) client-credentials pool used purely for
service-to-service auth — MFA should be required, not optional.

**Why it matters:** password-only authentication is the single most common
initial-access vector in account compromise, regardless of password
strength policy. Cognito supports both SMS and TOTP (authenticator app) MFA
natively; enabling `MfaConfiguration: "ON"` (mandatory) rather than
`"OPTIONAL"` closes the gap where MFA is available but simply never turned
on by end users, which in practice means it protects almost no one.

**A distinction worth making explicitly:** an M2M OAuth client-credentials
flow (a backend service authenticating to another backend service, with no
human in the loop) does not use MFA at all — it authenticates with a client
ID and secret. Flagging "no MFA" on a client-credentials-only user pool is a
false positive; the finding applies specifically to pools with a human sign-in
flow (hosted UI, SDK-based sign-in, or a mobile/web app login).

**What to check for:** `MfaConfiguration: "OFF"` or `"OPTIONAL"` on a user
pool serving an end-user-facing application. `"OPTIONAL"` in particular
looks compliant at a glance but is not equivalent to `"ON"` in practice.
