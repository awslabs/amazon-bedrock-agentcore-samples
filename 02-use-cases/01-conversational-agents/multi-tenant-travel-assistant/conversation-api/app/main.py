"""The conversation API — a BFF that terminates our contract and relays the agent's stream.

**Deliberately thin.** No business logic, no policy, no claim resolution. It does four things:
terminate a browser session, verify before spending, translate our contract into a runtime
invocation, and relay the stream. Anything more belongs in a tool.

**The session is the whole security argument.** The browser holds an opaque id in an httpOnly
cookie; the Cognito tokens live in DynamoDB. An XSS bug in the SPA finds no token to steal. The cost
is a table, CSRF protection and server-side refresh — all real, all cheaper than the failure mode.

**The runtime still gets the traveller's own bearer token, not a SigV4 signature from this Lambda.**
That is the load-bearing decision: the *agent* needs that token to reach the Gateway, where the
interceptor verifies it and injects tenant context. Swapping to SigV4 here would make this Lambda's
role the caller, and end-user identity would have to travel as payload the model's context can reach
— breaking the rule that the model never chooses tenancy. If the runtime ever moves to IAM-only
inbound, the swap happens in `_agentcore_client` and nowhere else. That is the point of the seam.

**Raw ASGI on uvicorn, no FastAPI.** pydantic-core ships native wheels, and a zip built on macOS
will not import them on Lambda. uvicorn and h11 are pure Python. Ironic for a repo whose backend is
FastAPI, and correct for a service with this few routes.

**Streaming needs two switches and fails silently with one.** `responseTransferMode: STREAM` on the
API Gateway integration, and `AWS_LWA_INVOKE_MODE=response_stream` on the function. With only one,
the response still arrives — as a single flush, with no error anywhere. So the test asserts
chunk-arrival *spread*, because that is the only thing that distinguishes the two.

**And two more in this file rather than in infrastructure, both in `_stream_turn`:** boto3 is
synchronous, so every read has to leave the event loop, and the read must be unbounded rather than a
fixed size. Either mistake produces the same impostor of a misconfigured integration — headers
immediately, a long pause, then everything at once — so both are worth knowing about before
re-diagnosing the two switches above.

Verified end to end against a control that calls the runtime directly, with no API Gateway and no
adapter in the path: frame arrivals spread across the generation window at every response size,
matching the runtime's own timing to within a second or two.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import urllib.error
import urllib.parse
from contextvars import ContextVar

import actions
import agent_refs
import boto3
import documents
import oauth
import sessions

REGION = os.environ.get("AWS_REGION", "us-east-1")
FRONTEND_ORIGIN_VAR = "FRONTEND_ORIGIN"

COOKIE_NAME = "travel_session"

# The runtime rejects a session id under 33 characters with a 400 that never reaches the agent —
# which looks exactly like an agent returning nothing. Checked here so the failure is legible, and
# before spending a runtime invoke.
MIN_SESSION_ID = 33

# How much of the upstream stream to take per read. Small enough that a read returns as soon as a
# frame or two has arrived rather than waiting to fill a buffer, large enough that a long answer is
# not thousands of thread hops. Frames are a few hundred bytes each.
STREAM_READ_BYTES = 512


# --- plumbing ---------------------------------------------------------------------------------


# The calling origin for the request being handled, so every response can echo the *matched* origin
# without threading it through a dozen helper signatures.
#
# A `ContextVar` rather than a module global: `asyncio` sets one per task, so two concurrent
# requests
# cannot read each other's value. A plain global would be a cross-request leak in a warm container —
# the same class of bug as caching a client that holds one traveller's token.
_request_origin: ContextVar[str] = ContextVar("request_origin", default="")


def _allowed_origins() -> list[str]:
    """Origins the SPA may be served from — the deployed one, and the dev server.

    **Concrete origins rather than `*`**, because a credentialed request forbids a wildcard, and
    ours
    are credentialed: the cookie is attached automatically. Being forced to name them is a feature —
    it is what makes the CSRF check possible at all.

    Comma-separated so the deployed distribution and `localhost:5173` can both work without a second
    deployment of this function. Everything else is refused, and the list is short on purpose: each
    entry is a site that may make authenticated requests as the traveller.
    """
    configured = os.environ.get(FRONTEND_ORIGIN_VAR, "http://localhost:5173")
    return [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]


def _matched_origin() -> str:
    """The caller's origin if it is allowed, otherwise the first configured one.

    Reflecting the *matched* origin rather than a fixed one is what lets one deployment serve both
    the
    CloudFront distribution and the dev server: `Access-Control-Allow-Origin` takes exactly one
    value,
    so it has to be chosen per request. Only ever a value from the allowlist — echoing an arbitrary
    `Origin` header back is the standard way this check gets accidentally disabled.
    """
    allowed = _allowed_origins()
    caller = _request_origin.get()
    return caller if caller in allowed else allowed[0]


def _cors() -> list[tuple[bytes, bytes]]:
    return [
        (b"access-control-allow-origin", _matched_origin().encode()),
        (b"access-control-allow-headers", b"content-type"),
        (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
        # Without this the browser will neither store nor send the session cookie.
        (b"access-control-allow-credentials", b"true"),
        # The allowed origin varies per caller, so a shared cache must key on it. Without this a
        # proxy could serve the dev server's CORS headers to the deployed site.
        (b"vary", b"Origin"),
    ]


def _agentcore_client(bearer: str):
    """A data-plane client that puts the traveller's JWT on the wire.

    boto3 has no bearer parameter for `InvokeAgentRuntime`, so the header goes on with a
    `before-send` hook. Built per call rather than cached: a shared client would carry whichever
    traveller's token warmed the container, which is the worst bug this layer could have.
    """
    client = boto3.client("bedrock-agentcore", region_name=REGION)

    def _inject(request, **_):
        request.headers["Authorization"] = f"Bearer {bearer}"

    client.meta.events.register("before-send.bedrock-agentcore.InvokeAgentRuntime", _inject)
    return client


# **A ceiling on what one request may send.** Two costs sit behind an unbounded body: this process
# accumulates it in memory, and whatever survives validation becomes model input, billed per token.
# 64 KB is far above any real turn — the longest eval prompt is a few hundred bytes — and far below
# anything that pressures a Lambda. `MAX_PROMPT_CHARS` is the tighter and more important of the two,
# because it bounds *spend* rather than memory.
MAX_BODY_BYTES = 64 * 1024
MAX_PROMPT_CHARS = 8_000


class BodyTooLarge(Exception):
    """Raised mid-read, so an oversized body is refused without being fully buffered first."""


async def _read_body(receive) -> bytes:
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        # Checked inside the loop on purpose: waiting until the body is complete would mean holding
        # the whole thing in memory to decide it was too big to hold.
        if len(body) > MAX_BODY_BYTES:
            raise BodyTooLarge(f"request body exceeds {MAX_BODY_BYTES} bytes")
        if not message.get("more_body"):
            return body


async def _send_json(send, status: int, obj: dict, extra_headers=()) -> None:
    payload = json.dumps(obj).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), *_cors(), *extra_headers],
        }
    )
    await send({"type": "http.response.body", "body": payload})


async def _redirect(send, location: str, extra_headers=()) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 302,
            "headers": [(b"location", location.encode()), *_cors(), *extra_headers],
        }
    )
    await send({"type": "http.response.body", "body": b""})


def _sse(obj: dict) -> bytes:
    return f"data: {json.dumps(obj)}\n\n".encode()


def _log(decision: str, **fields) -> None:
    """One structured line per decision.

    `print` rather than Powertools: this Lambda's dependencies are pinned to pure-Python wheels, and
    a logging library is not worth a native-wheel risk on the path a user waits on. CloudWatch reads
    JSON on stdout the same either way.

    **Ids only, never a token and never a name** — the same rule the rest of the sample follows.
    """
    print(json.dumps({"decision": decision, **fields}))


# --- session cookie ---------------------------------------------------------------------------


def _cookie_header(session_id: str) -> tuple[bytes, bytes]:
    """The session cookie, with the three attributes that matter.

    `HttpOnly` keeps it out of JavaScript — the entire point of this design. `Secure` keeps it off
    plaintext connections. **`SameSite=Strict` is the CSRF defence**: a cookie is sent
    automatically, so without it any site could make the browser issue an authenticated POST here.
    """
    return (
        b"set-cookie",
        (
            f"{COOKIE_NAME}={session_id}; HttpOnly; Secure; SameSite=Strict; Path=/; "
            f"Max-Age={sessions.SESSION_SECONDS}"
        ).encode(),
    )


def _clear_cookie() -> tuple[bytes, bytes]:
    return (
        b"set-cookie",
        f"{COOKIE_NAME}=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0".encode(),
    )


def _cookies(headers: dict[str, str]) -> dict[str, str]:
    jar: dict[str, str] = {}
    for part in headers.get("cookie", "").split(";"):
        name, _, value = part.strip().partition("=")
        if name:
            jar[name] = value
    return jar


def _session_from(headers: dict[str, str]) -> dict | None:
    return sessions.get(_cookies(headers).get(COOKIE_NAME, ""))


def _bearer_for(session: dict) -> str | None:
    """The session's access token, renewed first if it is close to expiry.

    Renewed *before* the stream starts, never during: a streamed response cannot go back and
    re-authenticate, so a token that died mid-generation would truncate an answer with no
    explanation the user could act on.
    """
    if not sessions.needs_refresh(session):
        return session.get("access_token")
    token = session.get("refresh_token")
    if not token:
        return None
    try:
        renewed = oauth.refresh(token)
    except (urllib.error.HTTPError, urllib.error.URLError, KeyError):
        return None
    access = renewed.get("access_token")
    if not access:
        return None
    sessions.update_access_token(
        session["session_id"], access, int(renewed.get("expires_in", 3600))
    )
    return access


def _verified_bearer(session: dict) -> str | None:
    """A token this request may actually use, or `None`.

    **Fails closed before spending a microVM.** Cognito validates signature, expiry and revocation
    server-side, so a rejected token costs one HTTPS call instead of a runtime cold start. It also
    catches a token revoked since the session was created, which a local expiry check cannot see.
    A rejected session is destroyed rather than left to be retried.

    **Validated with `/oauth2/userInfo`, not `cognito-idp:GetUser`.** GetUser is the obvious call
    and
    it does not work here: it requires the `aws.cognito.signin.user.admin` scope, which a token from
    the *authorization-code* flow does not carry — ours arrives with `openid email travel/read
    travel/book`, so GetUser answers `NotAuthorizedException: Access Token does not have required
    scopes`. Since this function destroys the session on any failure, using GetUser logs every
    traveller out on their first message: a fail-closed check that fails closed on valid
    credentials. `userInfo` verifies the same token, needs only `openid`, and returns 401 for an
    expired or revoked one.
    """
    bearer = _bearer_for(session)
    if not bearer:
        return None
    try:
        oauth.user_info(bearer)
    except Exception:  # noqa: BLE001 - any failure here means "do not proceed"
        sessions.destroy(session["session_id"])
        return None
    return bearer


# --- routes -----------------------------------------------------------------------------------


async def _auth_callback(scope, send) -> None:
    """Finish a login: exchange the code, store the tokens, set the cookie."""
    query = dict(urllib.parse.parse_qsl(scope.get("query_string", b"").decode()))
    code, state = query.get("code"), query.get("state")
    if not code or not state:
        await _send_json(send, 400, {"error": "missing code or state"})
        return
    try:
        tokens, return_to = oauth.exchange(code, state)
    except PermissionError as error:
        # No pending row for this state: either a legitimate login whose pending authorization
        # elapsed (or was already consumed by a sibling request), or a genuinely forged/replayed
        # callback. The two are indistinguishable here, so rather than dead-ending the common benign
        # case with an error page, restart the login — a fresh `state` and pending row, bouncing the
        # browser back through Cognito. This does not weaken the replay defence: a forged callback
        # gains no session, it is simply sent to a login it cannot complete without real
        # credentials,
        # and single-use consumption still stands. Logged as a decision either way.
        _log("login restarted after unusable callback", reason=str(error))
        await _redirect(send, oauth.start())
        return
    except (urllib.error.HTTPError, urllib.error.URLError) as error:
        _log("token exchange failed", error=str(error)[:200])
        await _send_json(send, 502, {"error": "identity provider unavailable"})
        return

    access = tokens.get("access_token")
    if not access:
        await _send_json(send, 502, {"error": "no access token returned"})
        return

    parsed = oauth.claims(access)
    session_id = sessions.create(
        access_token=access,
        refresh_token=tokens.get("refresh_token"),
        expires_in=int(tokens.get("expires_in", 3600)),
        tenant_id=parsed.get("custom:tenant_id"),
        traveler_id=parsed.get("custom:traveler_id"),
    )
    _log(
        "session established",
        tenant_id=parsed.get("custom:tenant_id"),
        traveler_id=parsed.get("custom:traveler_id"),
    )
    # Back to the SPA the login began on — CloudFront or the dev server — recorded against the state
    # at `start` and re-checked against the allowlist here. Re-validated rather than trusted because
    # it is read back from storage: only ever an allowed origin is used as a redirect target, so
    # this
    # cannot become an open redirect even if the stored value were somehow tampered with.
    destination = return_to if return_to in _allowed_origins() else _allowed_origins()[0]
    await _redirect(send, destination, extra_headers=[_cookie_header(session_id)])


def _runtime_session_id(session: dict, conversation_id: str) -> str:
    """The runtime session id: this conversation, bound to this traveller.

    **The conversation id the browser sends is never used directly, and that is an isolation
    boundary rather than tidiness.** The runtime keys conversation history on this value, so a
    client
    that presented someone else's conversation id would be handed their transcript. The id is
    client-generated, so nothing stops it being copied or replayed.

    Hashing it together with the traveller's own id makes that impossible: the same conversation id
    presented by two travellers resolves to two different runtime sessions, and neither can name the
    other's. The traveller id comes from the verified token, not from the request.

    `sha256` hex is 64 characters, comfortably over the runtime's 33-character minimum, and opaque —
    so the runtime's own logs carry no traveller identifier.

    **The tenant is in the hash too, and it is defence in depth rather than a fix for a live bug.**
    Traveller ids are opaque and globally unique (`trv_<hex>`), so two tenants cannot collide today.
    But that is a property of the id *generator*, and this is an isolation boundary — it should not
    depend on one. A deployment that ever issued tenant-local traveller ids would otherwise have two
    tenants' travellers share a runtime session, which is a transcript leak. Adding the tenant costs
    one field and removes the dependency.
    """
    traveler = session.get("traveler_id") or session["session_id"]
    tenant = session.get("tenant_id") or ""
    return hashlib.sha256(f"{tenant}:{traveler}:{conversation_id}".encode()).hexdigest()


async def _stream_turn(
    send, session: dict, conversation_id: str, prompt: str, force_tool: str | None = None
) -> None:
    """Invoke the runtime and relay its SSE stream.

    The one place in this file that knows AgentCore exists.

    **`force_tool` names a tool the agent must call on this turn, and only clicks set it.** A typed
    message never does: the model choosing which tool answers a sentence is the whole job. A *click*
    has
    already made that choice — the traveller pressed "select this hotel" — so leaving it to
    persuasion is
    what produced an intermittent stall. See `actions.FORCED_TOOLS`.
    """
    bearer = _verified_bearer(session)
    if not bearer:
        await _send_json(send, 401, {"error": "session expired"}, extra_headers=[_clear_cookie()])
        return

    # **Resolved before the response headers, because after them no status code is available.** The
    # `http.response.start` below commits a 200; anything that fails after it can only close the
    # stream mid-flight. An unconfigured runtime is a deployment problem the operator should see as
    # a
    # 503 with a sentence naming the fix, not as a truncated stream.
    try:
        runtime = agent_refs.runtime_arn()
    except agent_refs.AgentNotDeployed as error:
        _log("refusing a turn: no runtime configured", error=str(error))
        await _send_json(send, 503, {"error": "the assistant is not deployed yet"})
        return

    _log(
        "relaying a turn",
        tenant_id=session.get("tenant_id"),
        traveler_id=session.get("traveler_id"),
        session_id=conversation_id,
        prompt_chars=len(prompt),
    )

    # Headers must be written before the first chunk — they cannot be added once streaming has
    # started, which is also why CORS goes here rather than being appended afterwards.
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"text/event-stream"),
                (b"cache-control", b"no-cache"),
                # Defeats any intermediary that would otherwise buffer the stream.
                (b"x-accel-buffering", b"no"),
                *_cors(),
            ],
        }
    )
    try:
        # **Both the invoke and every read run in a worker thread, and this is what makes the relay
        # actually stream.** boto3 is synchronous: iterating `response["response"]` blocks the
        # thread
        # it runs on. Called directly from this coroutine it blocks the *event loop*, so the `send`
        # calls below cannot flush and the server accumulates the whole body before writing
        # anything.
        #
        # The symptom is a perfect impostor of a misconfigured streaming integration: headers arrive
        # in under a second, then nothing for twenty seconds, then the entire answer at once. Two
        # measurements found it, and both were necessary: plain uvicorn on a laptop reproduced it
        # with
        # no API Gateway and no adapter in the path, which ruled out the transport; and calling the
        # runtime directly showed frames genuinely spread over ~8s, which ruled out the upstream.
        # Neither alone would have been conclusive.
        response = await asyncio.to_thread(
            lambda: _agentcore_client(bearer).invoke_agent_runtime(
                agentRuntimeArn=runtime,
                qualifier="DEFAULT",
                runtimeSessionId=_runtime_session_id(session, conversation_id),
                # `force_tool` is omitted rather than sent as null when absent, so a typed turn's
                # payload is byte-identical to what it was before forcing existed.
                payload=json.dumps(
                    {"prompt": prompt, **({"force_tool": force_tool} if force_tool else {})}
                ),
                accept="text/event-stream",
            )
        )
        # The agent already emits the typed envelope as SSE frames, so chunks pass through
        # untouched.
        # Re-framing here would mean two places that know the event vocabulary.
        #
        # **Read whatever has arrived, never a fixed size.** `StreamingBody.read(n)` blocks until it
        # has `n` bytes or the stream ends — so a 512-byte read holds finished frames hostage
        # waiting
        # for the next one, and the flush boundaries land on exact multiples of the read size. That
        # was
        # measured: `read(512)` produced a 0.02s spread where iterating the underlying stream
        # produced
        # 4.08s on the same prompt.
        #
        # `_raw_stream` is urllib3's response, reached through botocore's wrapper because
        # `StreamingBody` exposes no unbounded incremental read. A private attribute is a real cost;
        # the alternative is a relay that only appears to stream on long answers.
        stream = response["response"]._raw_stream
        while True:
            data = await asyncio.to_thread(stream.read1, STREAM_READ_BYTES)
            if not data:
                break
            await send({"type": "http.response.body", "body": data, "more_body": True})
    except Exception as error:  # noqa: BLE001
        # The response has already started, so an HTTP status is no longer available. An `error`
        # frame in the stream's own vocabulary is what the client can handle — the alternative is a
        # truncated stream that looks like a network fault.
        # The message as well as the type: `ClientError` alone cannot distinguish a permission
        # problem from a bad session id from a runtime that is not READY, and this is the one
        # failure here whose cause is not inferable from the response the user sees.
        _log("upstream failed", error=type(error).__name__, detail=str(error)[:300])
        await send(
            {
                "type": "http.response.body",
                "body": _sse({"type": "error", "message": "the assistant is unavailable"}),
                "more_body": True,
            }
        )
    await send({"type": "http.response.body", "body": b""})


async def _document_link(send, session: dict, doc_id: str) -> None:
    """Presign a policy document, after re-checking the session's tenant owns it."""
    try:
        url = documents.presigned_url(doc_id, session.get("tenant_id"))
    except documents.DocumentRefused:
        _log("document refused", tenant_id=session.get("tenant_id"), doc_id=doc_id)
        # 404 rather than 403: a 403 would confirm the document exists.
        await _send_json(send, 404, {"error": "document not available"})
        return
    except RuntimeError as error:
        _log("document link unavailable", error=str(error))
        await _send_json(send, 500, {"error": "document links are not configured"})
        return
    _log("presigned a document", tenant_id=session.get("tenant_id"), doc_id=doc_id)
    await _send_json(send, 200, {"url": url, "expires_in": documents.LINK_SECONDS})


# --- the app ----------------------------------------------------------------------------------


async def app(scope, receive, send):  # noqa: C901 - a routing table; splitting it hides the routes
    if scope["type"] != "http":
        return

    method, path = scope["method"], scope["path"]
    headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
    parts = [segment for segment in path.split("/") if segment]

    # Recorded once, for this request only, so every response below echoes the origin that was
    # matched rather than a fixed one. See `_request_origin` for why it is a ContextVar.
    _request_origin.set((headers.get("origin") or "").rstrip("/"))

    # LWA pings this before routing traffic. Answer 200 or the function times out at init.
    if method == "GET" and path == "/":
        await _send_json(send, 200, {"ok": True})
        return

    if method == "OPTIONS":
        await send({"type": "http.response.start", "status": 204, "headers": _cors()})
        await send({"type": "http.response.body", "body": b""})
        return

    if method == "GET" and path == "/auth/login":
        # The SPA passes the origin it is served from. Honoured only if it is allowlisted, so the
        # login (and the callback it comes back to) can be either the deployed site or the dev
        # server — an unlisted value is ignored and the default is used, never reflected.
        query = dict(urllib.parse.parse_qsl(scope.get("query_string", b"").decode()))
        requested = (query.get("return") or "").rstrip("/")
        return_to = requested if requested in _allowed_origins() else None
        await _redirect(send, oauth.start(return_to))
        return

    if method == "GET" and path == "/auth/callback":
        await _auth_callback(scope, send)
        return

    if method == "POST" and path == "/auth/logout":
        sessions.destroy(_cookies(headers).get(COOKIE_NAME, ""))
        # **Destroying the row here is only half of signing out.** The other half is Cognito's own
        # hosted-UI session, set on Cognito's domain and invisible to this app — so without this,
        # clicking sign in again silently re-authenticated as the same traveller with no login form
        # at all, which blocks the one demo this sample leads with: sign in as the other tenant and
        # repeat the question. `logout_url` is the same redirect this app already issues for
        # `/auth/login`, aimed at Cognito's `/logout` instead of `/oauth2/authorize` — the client's
        # `logoutUrLs` already allowlists this origin (`addLogoutUrl` in `infra/lib/identity.ts`).
        #
        # Returned in the body rather than as a 302: this is an XHR `fetch`, not a browser
        # navigation, so a redirect here would be followed by `fetch` itself and never move the
        # address bar. The SPA navigates `window.location` to the URL this returns.
        url = oauth.logout_url(_matched_origin())
        await _send_json(
            send, 200, {"ok": True, "logout_url": url}, extra_headers=[_clear_cookie()]
        )
        return

    # ---- everything below needs a session ----------------------------------------------------
    session = _session_from(headers)

    if method == "GET" and path == "/auth/session":
        if not session:
            await _send_json(send, 401, {"authenticated": False})
            return
        # What the SPA needs to *show* who it is helping — never the token, never how to prove it.
        # `username` and `role` are read from the stored access token's claims (a login handle and a
        # role, not the token itself and not profile PII like a passport), so the chip can say
        # "priya,
        # traveler" instead of an opaque id. Decoded, not verified: it is the traveller's own token,
        # already verified at login, and nothing authorises on the result.
        claims = oauth.claims(session.get("access_token", ""))
        await _send_json(
            send,
            200,
            {
                "authenticated": True,
                "tenant_id": session.get("tenant_id"),
                "traveler_id": session.get("traveler_id"),
                "username": claims.get("username") or claims.get("cognito:username"),
                "role": claims.get("custom:role"),
            },
        )
        return

    if not session:
        await _send_json(send, 401, {"error": "no session"})
        return

    # **CSRF, belt to `SameSite`'s braces.** `SameSite=Strict` already stops a cross-site POST in
    # any current browser; an Origin check costs nothing and does not depend on browser behaviour.
    if method == "POST":
        origin = _request_origin.get()
        if origin and origin not in _allowed_origins():
            _log("rejected cross-origin POST", origin=origin)
            await _send_json(send, 403, {"error": "cross-origin request refused"})
            return

    if method == "GET" and len(parts) == 2 and parts[0] == "documents":
        await _document_link(send, session, parts[1])
        return

    # ---- the conversation routes --------------------------------------------------------------
    if method == "POST" and len(parts) == 3 and parts[0] == "conversation":
        conversation_id, leaf = parts[1], parts[2]
        if leaf not in ("messages", "actions"):
            await _send_json(send, 404, {"error": "not found"})
            return

        if len(conversation_id) < MIN_SESSION_ID:
            await _send_json(
                send,
                400,
                {"error": f"conversation id must be at least {MIN_SESSION_ID} characters"},
            )
            return

        try:
            body = json.loads(await _read_body(receive) or b"{}")
        except BodyTooLarge:
            await _send_json(send, 413, {"error": "request body too large"})
            return
        except json.JSONDecodeError:
            await _send_json(send, 400, {"error": "invalid JSON body"})
            return

        # **A body that is not a JSON object is refused here.** `json.loads` happily returns a list,
        # a string or a number, and every `body.get(...)` below would then raise `AttributeError` —
        # a 500 for what is plainly a client error.
        if not isinstance(body, dict):
            await _send_json(send, 400, {"error": "body must be a JSON object"})
            return

        if leaf == "messages":
            supplied = body.get("prompt") or body.get("text") or ""
            # **The prompt must be a string, not merely truthy.** A structured value here reaches
            # `stream_async` and then Bedrock, which refuses it — *"User messages cannot contain
            # tool uses"* for a `toolUse` block — surfacing as a streamed `EventLoopException`
            # inside an HTTP 200. Measured, not hypothesised. No tool ever executes, so this is not
            # the reasoning bypass it resembles; it is a client error reported as a server one, and
            # the fix belongs at the edge where the type is still known.
            if not isinstance(supplied, str):
                await _send_json(send, 400, {"error": "prompt must be a string"})
                return
            prompt = supplied.strip()
            if not prompt:
                await _send_json(send, 400, {"error": "empty message"})
                return
            if len(prompt) > MAX_PROMPT_CHARS:
                await _send_json(
                    send, 400, {"error": f"message exceeds {MAX_PROMPT_CHARS} characters"}
                )
                return
            await _stream_turn(send, session, conversation_id, prompt)
            return

        # A click. Refused here if the action is not in the closed registry — the frontend also
        # refuses to render one, and neither check is redundant: this one is the boundary a
        # hand-written request hits.
        try:
            prompt = actions.phrase_for(body.get("action_id"), body.get("payload"))
        except actions.UnknownAction as error:
            _log("action refused", tenant_id=session.get("tenant_id"), reason=str(error))
            await _send_json(send, 400, {"error": "unknown action"})
            return
        # The tool this click must run, when the click leaves no room for judgement. `None` for
        # reads
        # and refusals — see `actions.forced_tool_for`.
        force_tool = actions.forced_tool_for(body.get("action_id", ""))
        _log(
            "relaying an action",
            action_id=body.get("action_id"),
            session_id=conversation_id,
            force_tool=force_tool,
        )
        await _stream_turn(send, session, conversation_id, prompt, force_tool=force_tool)
        return

    await _send_json(send, 404, {"error": "not found"})
