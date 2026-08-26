"""Verify the conversation API end to end, including that streaming is *real*.

    cd backend && AWS_REGION=us-east-1 uv run python ../scripts/verify_conversation_api.py
Checks, in order of what they protect:

  A. **Streaming is real** — frame arrivals spread across the generation window rather than
     clustering at the end, *and* that spread is close to what the runtime itself produces. A
     silently buffered relay returns a complete, correct answer and logs no error anywhere, so a
     timing assertion is the only thing that catches it. A response arriving is not evidence, and
     nor is an early first byte: that can be a header flush.

     The absolute spread and the comparison against a direct call are both checked, because each
     alone can mislead. An absolute threshold passes a relay that buffers when the upstream happens
     to be slow; a comparison alone passes when *both* are buffered. Four layers can each swallow
     the stream independently — the API Gateway integration mode, the adapter's invoke mode, a
     blocking read on the event loop, and a fixed-size read — and all four look the same.

     **Checked at two response sizes**, because a fixed-size read buffers only *short* answers: a
     long one eventually fills the buffer and streams, so a single long prompt passes while every
     brief reply arrives in one burst. That is exactly the bug this build shipped and then found.
     Both sizes are compared against the same turn measured at the runtime rather than against a
     fixed duration — an absolute threshold measures the model's speed, not the relay's fidelity,
     and this agent emits a short answer as one burst upstream too. When the runtime itself shows
     no spread, the run says the prompt could not discriminate instead of scoring it either way.
  B. **The browser never holds a token** — the session cookie is `HttpOnly`, `Secure`,
     `SameSite=Strict`, and its value is an opaque id rather than a JWT.
  C. **Fail closed** — no session, a forged session id, and a conversation id too short for the
     runtime are each refused, and each *before* a runtime invoke.
  D. **CSRF** — a cross-origin POST with a valid session is refused, which is the case that matters
     because a cookie is sent automatically.
  E. **The closed action registry** — a click outside it is refused by the API, not merely
     unrendered by the UI. Paired with an accepted click, or the check could not tell "closed" from
     "broken shut".
  F. **A citation presigns and re-authorises** — and another tenant's document is refused even with
     a genuine session.
  G. **The tenant changes the answer, through the browser's own path** — the same question, asked by
     two travellers at two companies, returns different caps and different currencies. Checked here
     rather than only at the tool layer because this is the path a reader will actually try, and
     every hop between the cookie and the tool has to preserve identity for it to hold.
  H2. **A confirmation is never claimed without the tool.** Asserted on the `booking_confirmed` card
     rather than on the prose, because a run of this suite caught the agent inventing a reference
     (`BKG-535399F53C`) for a booking that never happened. A card cannot be fabricated — it only
     exists if the tool returned one.
  H. **A booking completes by clicking**, and a handoff tenant's summary carries no confirm button
  at
     all — the capability difference expressed as UI rather than as prose. Also the check that
     catches
     cards never reaching the client, and a missing conversation history.

**Every refusal check is paired with an acceptance check.** A deny-only assertion passes just as
happily when the thing under test refuses everything, which is a failure mode this repo has already
paid for once.

The session is established by driving the OAuth flow the way a browser would: hosted-UI login with
the demo user's password, following the redirect to the API's callback, and keeping the cookie. That
exercises the same code path the SPA will, rather than a shortcut that inserts a session row.
"""

from __future__ import annotations

import argparse
import html
import http.client
import http.cookiejar
import importlib.util
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import boto3
from deployed_refs import refs

# The BFF's own sealing module, loaded rather than reimplemented, so the control below cannot drift
# from the encryption context the tokens were actually sealed under. `read()` needs no environment:
# the KMS key id travels inside the ciphertext, and only *sealing* needs the key variable.
#
# **Loaded by path, not by `sys.path` insertion.** `conversation-api/app/` has no `__init__.py`
# while `backend/app/` does, and Python prefers a regular package found later on the path over an
# earlier namespace portion — so `from app import crypto` picked up the *backend's* package
# whenever this ran with `backend/` importable, which is how this suite is normally invoked. An
# ImportError is the lucky outcome; the same clash on a module existing in both resolves silently.
_crypto_spec = importlib.util.spec_from_file_location(
    "bff_crypto", Path(__file__).resolve().parents[1] / "conversation-api" / "app" / "crypto.py"
)
crypto = importlib.util.module_from_spec(_crypto_spec)
_crypto_spec.loader.exec_module(crypto)

REGION = refs.region

# Resolved from SSM rather than hardcoded: the API URL moves whenever the REST API is replaced, and
# a stale constant here would fail in a way that looks like a broken deploy.
API_URL_PARAM = "/multi-tenant-travel/conversation-api/url"

COOKIE_NAME = "travel_session"

# A question that takes several tool calls and a paragraph of prose to answer. Deliberately not a
# one-word reply: streaming can only be observed across a response long enough to have a middle.
STREAMING_PROMPT = (
    "What is my hotel nightly cap, and what does my company's policy say about conferences "
    "where every property is over budget? Explain it properly."
)

# Phrased to survive an agent that remembers. A bare "find me a hotel in London" invites a
# clarifying
# question once memory holds an earlier London booking, which is the assistant behaving well and the
# test failing anyway.
SEARCH_PROMPT = "Search for hotels in Amsterdam for 5 to 8 December and show me the options"

# A one-tool, one-paragraph answer — around 1 KB. Measured separately because a fixed-size read
# buffers *only* short responses, so a long prompt alone would report success on a broken relay.
SHORT_PROMPT = "What is my hotel nightly cap?"

# Enough frames that a single flush of the whole body would be visible as such.
MIN_FRAMES = 3

# Below this, "spread" is indistinguishable from a couple of frames landing in one TCP segment.
# Well under the several seconds a real generation takes, so it fails loudly on a buffered relay
# without being sensitive to how fast the model happened to be.
MIN_SPREAD_SECONDS = 1.0

# The control measurement calls this directly, bypassing every hop the relay adds.
# Resolved from `/multi-tenant-travel/agent/runtime-arn` rather than hardcoded — see
# `deployed_refs.py`.
#
# **A function rather than a module constant, so importing this file touches no network.** It was
# `RUNTIME_ARN = refs.runtime_arn`, resolving Parameter Store at import time — and this module is
# imported by `evaluation/runner/agent_client.py`, which the *offline* evaluation tests import. So
# `./test.sh` reached AWS and passed only on a machine with credentials. It passed here every time,
# which is why it went unnoticed: the README promises "everything that needs no AWS account at all
# runs in seconds", and two of those tests needed an account.
#
# `refs` is itself lazy per attribute, so the cost of this is one function call at the point of use.


def runtime_arn() -> str:
    return refs.runtime_arn


SESSION_TABLE = "multi-tenant-travel-sessions"

_results: list[bool] = []


def report(name: str, passed: bool, detail: str = "") -> bool:
    _results.append(passed)
    print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    for line in str(detail).splitlines():
        if line:
            print(f"        {line}")
    return passed


def parameters() -> dict[str, str]:
    ssm = boto3.client("ssm", region_name=REGION)
    found = ssm.get_parameters(Names=[API_URL_PARAM])
    values = {p["Name"]: p["Value"] for p in found["Parameters"]}
    missing = {API_URL_PARAM} - set(values)
    if missing:
        raise SystemExit(f"missing SSM parameters: {sorted(missing)} — deploy the stack first")
    return values


def bearer_for(session_id: str | None) -> str | None:
    """The session's access token, read from the session table and unsealed.

    **Only for the control measurement**, which has to call the runtime the way the BFF does.
    Reading a token out of the store is exactly what no client may do — which is the point of the
    design, and why this needs AWS credentials the browser will never have. It stays in the
    verification script and nowhere near the request path.

    **The unseal is not optional.** The stored value is KMS ciphertext (`crypto.seal` on write), so
    returning the attribute as-is handed the runtime a `kms1:`-prefixed blob and earned a 403,
    `OAuth authorization failed: Failed to parse token`. The control had been silently empty ever
    since sealing was introduced, and the comparison it feeds passed anyway.
    """
    if not session_id:
        return None
    table = boto3.resource("dynamodb", region_name=REGION).Table(SESSION_TABLE)
    item = (table.get_item(Key={"session_id": session_id}) or {}).get("Item") or {}
    try:
        return crypto.open_(item.get("access_token"), session_id=session_id)
    except crypto.TokenDecryptionError as error:
        # Returned as absent, which the caller now reports as a failure rather than skipping.
        print(f"     (could not unseal the session token: {error})")
        return None


class Browser:
    """Just enough of a browser: a cookie jar, redirect following, and no JavaScript.

    Deliberately built on `urllib` with an explicit `CookieJar` rather than `requests`, so the test
    depends on nothing the repo does not already use — and so the cookie handling is visible rather
    than implicit, which matters when the cookie *is* the thing under test.
    """

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.raw_set_cookie: list[str] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        body: dict | None = None,
        headers: dict | None = None,
        follow: bool = True,
    ) -> tuple[int, dict[str, str], str]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        for name, value in (headers or {}).items():
            request.add_header(name, value)

        opener = (
            self.opener
            if follow
            else urllib.request.build_opener(
                _NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar)
            )
        )
        try:
            with opener.open(request, timeout=90) as response:
                self.raw_set_cookie += response.headers.get_all("set-cookie") or []
                return response.status, dict(response.headers), response.read().decode()
        except urllib.error.HTTPError as error:
            self.raw_set_cookie += error.headers.get_all("set-cookie") or []
            return error.code, dict(error.headers), error.read().decode()

    def session_cookie(self) -> http.cookiejar.Cookie | None:
        for cookie in self.jar:
            if cookie.name == COOKIE_NAME:
                return cookie
        return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Stops at the redirect, so a `Location` and its `Set-Cookie` can both be inspected."""

    def redirect_request(self, *_args, **_kwargs):
        return None


def establish_session(
    browser: Browser, api_url: str, username: str, password: str, *, quiet: bool = False
) -> str | None:
    """Drive the real login the way a browser would, returning the session id.

    **Posts the hosted UI's own sign-in form.** The alternative — minting a token with
    `USER_PASSWORD_AUTH` — cannot work here and the reason is instructive: the web client
    deliberately has no password flow, and a token from that flow would carry different scopes than
    the authorization-code flow issues. Scripting the form is what exercises the path the SPA will
    actually take, PKCE exchange included.

    The form's field names are not a published contract, so this can break on a hosted-UI change.
    Accepted: the alternative is leaving streaming unproven, which is the one thing here that cannot
    be checked any other way.
    """

    # `GET /auth/login` must hand back a Cognito URL carrying a PKCE challenge. Stopping at the
    # redirect is the point: a challenge in the URL is what proves the verifier stayed server-side.
    def note(name: str, passed: bool, detail: str = "") -> None:
        # Silent when the login is a means to an end rather than the thing being tested — otherwise
        # signing in as a second traveller would double every login assertion in the tally.
        if not quiet:
            report(name, passed, detail)

    status, headers, _ = browser.request("GET", f"{api_url}auth/login", follow=False)
    location = headers.get("location") or headers.get("Location") or ""
    note(
        "GET /auth/login redirects to Cognito with a PKCE challenge",
        status == 302
        and "code_challenge=" in location
        and "code_challenge_method=S256" in location,
        "the verifier never leaves the API, so an intercepted code is useless",
    )
    if "code_challenge=" not in location:
        return None

    # A fabricated code against a real `state` must be refused — the check that makes the callback
    # safe against a forged or replayed redirect. Runs before the genuine login so it cannot consume
    # the real pending row.
    state = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(location).query)).get("state", "")
    status, forged_headers, _ = browser.request(
        "GET", f"{api_url}auth/callback?code=fabricated&state=unknown-{state[:8]}", follow=False
    )
    forged_location = forged_headers.get("location") or forged_headers.get("Location") or ""
    note(
        "a callback with an unknown state grants no session (bounced to a fresh login)",
        status == 302
        and "oauth2/authorize" in forged_location
        and COOKIE_NAME not in " ".join(browser.raw_set_cookie),
        f"status {status}: {forged_location[:70]}",
    )

    page_status, _, page = browser.request("GET", location)
    action = re.search(r'<form[^>]*action="([^"]+)"', page)
    csrf = re.search(r'name="_csrf"\s+value="([^"]+)"', page)
    if page_status != 200 or not action or not csrf:
        note("the hosted UI sign-in form loaded", False, f"status {page_status}")
        return None

    origin = f"https://{urllib.parse.urlparse(location).netloc}"
    form = urllib.parse.urlencode(
        {
            "_csrf": html.unescape(csrf.group(1)),
            "username": username,
            "password": password,
            "signInSubmitButton": "submit",
        }
    ).encode()
    request = urllib.request.Request(
        origin + html.unescape(action.group(1)),
        data=form,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": location,
            "Origin": origin,
        },
    )
    opener = urllib.request.build_opener(
        _NoRedirect(), urllib.request.HTTPCookieProcessor(browser.jar)
    )
    try:
        with opener.open(request, timeout=60) as response:
            callback = response.headers.get("location", "")
    except urllib.error.HTTPError as error:
        callback = error.headers.get("location", "")

    if "auth/callback" not in callback or "code=" not in callback:
        note("sign-in produced an authorization code", False, f"redirected to {callback[:90]}")
        return None

    status, headers, _ = browser.request("GET", callback, follow=False)
    set_cookie = " ".join(headers.get_all("set-cookie") if hasattr(headers, "get_all") else [])
    browser.raw_set_cookie += [set_cookie] if set_cookie else []
    found = browser.session_cookie()
    note(
        "the callback exchanges the code server-side and sets the session cookie",
        status == 302 and found is not None,
        f"status {status} -> {headers.get('location', '')}",
    )
    return found.value if found else None


def _frame_arrivals(response) -> tuple[list[float], bytes, float]:
    """Frame arrival times, reading a byte at a time so the timing survives.

    A single `.read()` would collapse exactly the information this measures.

    A truncated stream is reported and its partial body kept, rather than raised: a chunked response
    ending without its terminating chunk used to abort the entire suite from inside whichever check
    happened to be reading, taking every later check down with it.
    """
    started = time.monotonic()
    arrivals: list[float] = []
    payload = b""
    try:
        while chunk := response.read(1):
            payload += chunk
            if chunk == b"\n" and payload.endswith(b"\n\n"):
                arrivals.append(time.monotonic() - started)
    except http.client.IncompleteRead as error:
        payload += error.partial
        print(
            f"     (stream truncated after {len(payload)} bytes and {len(arrivals)} frames: "
            "the connection closed without a terminating chunk)"
        )
    return arrivals, payload, started


def _upstream_arrivals(prompt: str, bearer: str) -> tuple[list[float], int, int]:
    """The same turn measured straight at the runtime — no API Gateway, no adapter, no BFF.

    The control for the relay measurement. Without it, a burst of frames arriving together is
    ambiguous: it could be the transport buffering (this code's fault, and fixable) or the runtime
    delivering its body in one piece (upstream, and not). Raw `http.client` rather than boto3
    because boto3's event-stream iterator is itself a layer that could be reordering arrivals.

    **Returns the HTTP status so the caller can tell a measurement from a refusal.** A rejected
    bearer produces an error body with no SSE frames in it, which is not a control at all; without
    the status the caller sees only an empty list and cannot say why.
    """
    path = f"/runtimes/{urllib.parse.quote(runtime_arn(), safe='')}/invocations?qualifier=DEFAULT"
    host = f"bedrock-agentcore.{REGION}.amazonaws.com"
    connection = http.client.HTTPSConnection(host, timeout=180)
    connection.request(
        "POST",
        path,
        body=json.dumps({"prompt": prompt}),
        headers={
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": str(uuid.uuid4()) + "aaa",
        },
    )
    response = connection.getresponse()
    arrivals, payload, _ = _frame_arrivals(response)
    return arrivals, len(payload), response.status


def check_streaming(api_url: str, cookie: str | None, bearer: str | None) -> None:
    """Assert real streaming: an absolute spread, and one close to the runtime's own.

    Reported as a failure rather than skipped when there is no session: unproven streaming is the
    exact condition this check exists to catch, and a refusal arriving in one chunk would otherwise
    look indistinguishable from a working stream.
    """
    print("\nA. Streaming is real (the check a buffered relay passes silently)")
    if not cookie:
        report(
            "frames arrive spread across the generation window",
            False,
            "no session — run with --password so the login flow can complete",
        )
        return

    def relay(prompt: str) -> tuple[list[float], bytes] | None:
        conversation_id = str(uuid.uuid4()) + "aaa"  # >= 33 chars, the runtime's contract
        request = urllib.request.Request(
            f"{api_url}conversation/{conversation_id}/messages",
            data=json.dumps({"prompt": prompt}).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "Cookie": f"{COOKIE_NAME}={cookie}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                frames, body, _ = _frame_arrivals(response)
                return frames, body
        except urllib.error.HTTPError as error:
            report("the streaming route answers", False, f"HTTP {error.code}: {error.read()[:200]}")
            return None

    measured = relay(STREAMING_PROMPT)
    if measured is None:
        return
    arrivals, payload = measured

    report(
        f"at least {MIN_FRAMES} SSE frames arrived through the relay",
        len(arrivals) >= MIN_FRAMES,
        f"{len(arrivals)} frames, last at {arrivals[-1]:.2f}s" if arrivals else "no frames",
    )
    if not arrivals:
        return

    relay_spread = arrivals[-1] - arrivals[0]

    # **The absolute assertion.** A relay that accumulates the body and flushes it at the end still
    # delivers every frame, correctly, with nothing in any log — so the only evidence available is
    # that the frames were spread out in time.
    report(
        f"frame arrivals spread over more than {MIN_SPREAD_SECONDS}s",
        relay_spread > MIN_SPREAD_SECONDS,
        f"spread {relay_spread:.2f}s — first at {arrivals[0]:.2f}s, last at {arrivals[-1]:.2f}s\n"
        "A spread near zero means something buffered: the answer is correct, and the streaming\n"
        "configuration is doing nothing. Four layers can each cause it independently — the API\n"
        "Gateway transfer mode, the adapter's invoke mode, a blocking read on the event loop, and\n"
        "a fixed-size read that waits to fill its buffer.",
    )

    # **And the comparison**, because the absolute check alone would pass a buffered relay whenever
    # the upstream is slow enough. This measures the same turn with no API Gateway, no adapter and
    # none of the BFF in the path, so a relay that is losing the stream shows up as a spread much
    # narrower than the runtime's.
    if bearer:
        upstream, upstream_bytes, upstream_status = _upstream_arrivals(STREAMING_PROMPT, bearer)
        control = (
            f"runtime HTTP {upstream_status}, {len(upstream)} frames, {upstream_bytes} bytes "
            "(measured with no API Gateway, adapter or BFF in the path)"
        )
        if len(upstream) < 2:
            # **An empty control fails rather than passes.** This read `upstream_spread <= 0.0 or
            # relay_spread >= ...`, so a control that measured nothing satisfied the comparison by
            # short-circuit — it printed "runtime 0.00s across 0 frames" and reported PASS. The
            # escape hatch was there for a runtime that legitimately answers in one frame, but that
            # case is equally unusable as a reference point, so both now say so instead.
            report(
                "the relay's spread is comparable to the runtime's own",
                False,
                f"{control}\nToo few frames to compare against, so nothing here was measured. A "
                "non-200 status means the bearer was refused; a 200 with one frame means the "
                "runtime did not stream, which the relay cannot then be judged against.",
            )
        else:
            upstream_spread = upstream[-1] - upstream[0]
            # Generous, and deliberately so: model generation time varies run to run, so this is
            # looking for the order-of-magnitude collapse a buffered relay produces (0.3s against
            # 8s), not a tight numerical match.
            report(
                "the relay's spread is comparable to the runtime's own",
                relay_spread >= upstream_spread * 0.5,
                f"relay {relay_spread:.2f}s across {len(arrivals)} frames · "
                f"runtime {upstream_spread:.2f}s · {control}",
            )
    else:
        report(
            "the relay's spread is comparable to the runtime's own",
            False,
            "no bearer token available for the control measurement",
        )

    # **A short answer too, because a fixed-size read buffers only short ones.** Such a read holds
    # bytes until it fills, so a long answer streams while a brief reply is kept to the end — which
    # means a single long prompt reports success on a relay that is broken for most real turns.
    # Exactly the bug this build shipped, and then found.
    #
    # **Compared against the runtime, not against a fixed duration.** An absolute `spread > 1s`
    # threshold measured the model rather than the relay: this agent emits a short answer as one
    # burst at the end of generation *upstream too* (measured: 6 frames, first at 5.85s, last at
    # 5.93s), so the assertion failed on a healthy system about half the time. It is also why the
    # threshold cannot simply be lowered — when the upstream itself delivers in one burst there is
    # no spread for the relay to preserve or destroy, and the honest report is that this prompt
    # cannot tell the two apart.
    brief = relay(SHORT_PROMPT)
    if brief and bearer:
        short_arrivals, _ = brief
        short_spread = (short_arrivals[-1] - short_arrivals[0]) if len(short_arrivals) > 1 else 0.0
        short_up, _, short_status = _upstream_arrivals(SHORT_PROMPT, bearer)
        short_up_spread = (short_up[-1] - short_up[0]) if len(short_up) > 1 else 0.0
        measured = (
            f"relay {short_spread:.2f}s across {len(short_arrivals)} frames · "
            f"runtime {short_up_spread:.2f}s across {len(short_up)} frames (HTTP {short_status})"
        )
        if short_up_spread > MIN_SPREAD_SECONDS:
            report(
                "a short answer streams too, not just a long one",
                short_spread >= short_up_spread * 0.5,
                f"{measured}\nA collapse here while the long prompt passes is a fixed-size read: "
                "the buffer only fills on a long answer.",
            )
        else:
            print(
                "     (skipped: the runtime delivers this answer in one burst as well, so there is "
                f"no spread the relay could be destroying — {measured})"
            )

    # The envelope the SPA renders. Checked here because a stream of the wrong *shape* is a stream
    # the
    # frontend cannot use, and that would not surface as a transport failure.
    text = payload.decode(errors="replace")
    report(
        "the stream carries the typed envelope, not bare text",
        '"type":' in text.replace(" ", ""),
        text[:110].replace("\n", " "),
    )


def check_cookie(browser: Browser) -> None:
    print("\nB. The browser never holds a token")
    raw = " ".join(browser.raw_set_cookie)
    if not raw:
        report("a session cookie was issued", False, "no Set-Cookie seen in the flow")
        return
    for attribute, why in (
        ("HttpOnly", "unreachable from JavaScript — the whole point of the design"),
        ("Secure", "never sent over a plaintext connection"),
        ("SameSite=Strict", "the CSRF defence, since a cookie is sent automatically"),
    ):
        report(f"the session cookie sets {attribute}", attribute.lower() in raw.lower(), why)

    value = re.search(rf"{COOKIE_NAME}=([^;]*)", raw)
    opaque = bool(value) and value.group(1).count(".") != 2
    report(
        "the cookie value is an opaque id, not a JWT",
        opaque,
        "a JWT would show three dot-separated segments",
    )


def check_fail_closed(api_url: str, cookie: str | None) -> None:
    print("\nC. Fail closed before spending a runtime invoke")
    long_id = str(uuid.uuid4()) + "aaa"

    status, _, body = _post(f"{api_url}conversation/{long_id}/messages", {"prompt": "hello"})
    report("no session is refused", status == 401, f"status {status}: {body[:60]}")

    status, _, body = _post(
        f"{api_url}conversation/{long_id}/messages",
        {"prompt": "hello"},
        cookie="forged-session-id-that-does-not-exist",
    )
    report("a forged session id is refused", status == 401, f"status {status}: {body[:60]}")

    # Needs a session to reach: the length check sits after the session gate, so without one this
    # is indistinguishable from the check above.
    if cookie:
        status, _, body = _post(f"{api_url}conversation/short/messages", {"prompt": "hi"}, cookie)
        report(
            "a conversation id under 33 characters is refused",
            status == 400,
            f"status {status}: {body[:100]}",
        )
        status, _, body = _post(f"{api_url}conversation/{long_id}/messages", {"prompt": ""}, cookie)
        report("an empty message is refused", status == 400, f"status {status}")

    # The paired acceptance: the unauthenticated routes that are *meant* to answer still do, so a
    # blanket refusal cannot pass this section.
    status, _, body = _get(f"{api_url}")
    report(
        "the readiness route still answers 200",
        status == 200,
        "without this, every check above would pass on a totally broken API",
    )
    status, _, body = _get(f"{api_url}auth/session")
    report(
        "GET /auth/session reports unauthenticated without leaking a token",
        status == 401 and "token" not in body.lower(),
        body[:80],
    )


def check_csrf(api_url: str, cookie: str | None) -> None:
    print("\nD. CSRF — the case a cookie's automatic sending creates")
    if not cookie:
        report("a cross-origin POST with a valid session is refused", False, "no session")
        return
    long_id = str(uuid.uuid4()) + "aaa"
    status, _, _ = _post(
        f"{api_url}conversation/{long_id}/messages",
        {"prompt": "hello"},
        cookie,
        headers={"Origin": "https://evil.example"},
    )
    report("a cross-origin POST is refused", status == 403, f"status {status}")


def check_actions(api_url: str, cookie: str | None) -> None:
    print("\nE. The closed action registry, refused at the API and not only in the UI")
    long_id = str(uuid.uuid4()) + "aaa"
    status, _, body = _post(
        f"{api_url}conversation/{long_id}/actions",
        {"action_id": "transfer_funds", "payload": {}},
        cookie,
    )
    # 401 without a session, 400 with one. Either proves the click did not reach the runtime; only
    # the 400 proves the *registry* refused it, which is why the session matters here.
    report(
        "an action outside the registry is refused",
        status in (400, 401),
        f"status {status}: {body[:80]}",
    )
    if cookie:
        report(
            "the refusal came from the registry rather than the session gate",
            status == 400,
            f"status {status}",
        )


def check_documents(api_url: str, cookie: str | None, tenant: str) -> None:
    print("\nF. Citation links presign on click, after re-authorising")
    other = "pol_initech_2026" if tenant == "globex" else "pol_globex_2026"
    own = "pol_globex_2026" if tenant == "globex" else "pol_initech_2026"

    status, _, body = _get(f"{api_url}documents/{own}")
    report("without a session no link is issued", status == 401, f"status {status}")

    if not cookie:
        return
    status, _, body = _get(f"{api_url}documents/{other}", cookie)
    report(
        f"a {tenant} session cannot presign {other}",
        status == 404,
        "404 rather than 403 on purpose — a 403 confirms the document exists",
    )
    status, _, body = _get(f"{api_url}documents/{own}", cookie)
    payload = json.loads(body) if body.startswith("{") else {}
    report(
        f"a {tenant} session presigns its own document",
        status == 200 and "X-Amz-Signature" in payload.get("url", ""),
        f"status {status}, expires in {payload.get('expires_in')}s",
    )


def _answer(api_url: str, cookie: str, prompt: str) -> str:
    """One turn's prose, collected from the stream. For assertions about *content*."""
    request = urllib.request.Request(
        f"{api_url}conversation/{uuid.uuid4()}aaa/messages",
        data=json.dumps({"prompt": prompt}).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Cookie": f"{COOKIE_NAME}={cookie}"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        try:
            raw = response.read().decode(errors="replace")
        except http.client.IncompleteRead as error:
            # Keep what arrived and say so. The content assertion downstream then fails on its own
            # terms if the truncation cost it the text it was looking for, which is more use than a
            # traceback that also cancels every check after this one.
            print(f"     (stream truncated after {len(error.partial)} bytes)")
            raw = error.partial.decode(errors="replace")
    text = []
    for line in raw.splitlines():
        if line.startswith("data:"):
            try:
                event = json.loads(line[5:])
            except json.JSONDecodeError:
                continue
            if event.get("type") == "text":
                text.append(event.get("text", ""))
    return "".join(text)


def check_tenant_contrast(api_url: str, password: str | None, username: str) -> None:
    """The same question, two tenants, different answers — through the browser's own path.

    **The sample's central claim, measured where a reader meets it.** The tool layer already proves
    this, but the claim that matters is end to end: cookie → session → bearer → runtime → gateway →
    interceptor → tool. Any hop that lost or defaulted the identity would produce one tenant's
    answer
    for both, and every check above this one would still pass.
    """
    print("\nG. The tenant changes the answer, through the browser's own path")
    if not password:
        report("two tenants get different caps", False, "needs --password to sign in as both")
        return

    # priya at globex, sam at initech. Both are demo users seeded from the traveller fixtures.
    other = "sam" if username != "sam" else "priya"
    answers: dict[str, str] = {}
    for who in (username, other):
        browser = Browser()
        cookie = establish_session(browser, api_url, who, password, quiet=True)
        if not cookie:
            report(f"signed in as {who}", False, "login failed")
            return
        answers[who] = _answer(api_url, cookie, "What is my hotel nightly cap?")

    for who, answer in answers.items():
        print(f"        {who}: {answer[:150].replace(chr(10), ' ')}")

    # Asserted on *both* sides. "They differ" alone would pass if one had simply failed to answer.
    globex = answers.get("priya", "")
    initech = answers.get("sam", "")
    report(
        "globex sees a USD cap and initech a EUR one",
        ("250" in globex and ("$" in globex or "USD" in globex))
        and ("150" in initech and ("€" in initech or "EUR" in initech)),
        "same question, same tool, different answer — the identity chain held across every hop",
    )
    report(
        "neither answer mentions the other tenant",
        "initech" not in globex.lower() and "globex" not in initech.lower(),
        "a leak here would be the one failure the whole sample exists to prevent",
    )


def _events(api_url: str, cookie: str, conversation_id: str, body: dict, leaf: str) -> dict:
    """One turn, decoded into the parts a UI consumes: prose, tool names, cards."""
    request = urllib.request.Request(
        f"{api_url}conversation/{conversation_id}/{leaf}",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Cookie": f"{COOKIE_NAME}={cookie}"},
    )
    with urllib.request.urlopen(request, timeout=250) as response:
        raw = response.read().decode(errors="replace")
    text: list[str] = []
    tools: list[str] = []
    cards: list[dict] = []
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            event = json.loads(line[5:])
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "text":
            text.append(event.get("text", ""))
        elif kind == "tool_start":
            tools.append(event.get("tool"))
        elif kind == "cards":
            cards.extend(event.get("cards") or [])
    return {"text": "".join(text), "tools": tools, "cards": cards}


def check_booking(api_url: str, password: str | None) -> None:
    """A complete booking by clicking, and the per-tenant capability difference.

    **The write path end to end, exercised through the API rather than by hand in a browser.** Every
    button the SPA renders comes from a card, and every click posts an `action_id` back — so driving
    the cards and the clicks *is* driving the UI, minus the pixels.

    Also the check that would catch two failures this build had: cards never reaching the client at
    all (the tool response terminates at the model), and no conversation history (so "the first one"
    means nothing on the next turn).
    """
    print("\nH. A booking completed by clicking, and the tenant's capability difference")
    if not password:
        report("a booking completes through card clicks", False, "needs --password")
        return

    summaries: dict[str, dict] = {}
    for who in ("priya", "sam"):
        browser = Browser()
        cookie = establish_session(browser, api_url, who, password, quiet=True)
        if not cookie:
            report(f"signed in as {who}", False, "login failed")
            return
        conversation_id = str(uuid.uuid4()) + "aaa"

        search = _events(
            api_url,
            cookie,
            conversation_id,
            # **Explicit, and deliberately not London.** Once long-term memory exists the agent's
            # behaviour depends on the traveller's *history*: after a few test runs it recalls a
            # London
            # booking and sensibly asks "search again, or change the existing one?" rather than
            # searching — correct behaviour that made this check flaky. So the prompt names a
            # destination with no history and asks for options outright, leaving the agent no
            # reasonable reading other than "search".
            {"prompt": SEARCH_PROMPT},
            "messages",
        )
        if who == "priya":
            report(
                "a search returns rendered cards, not just prose",
                any(card["card_type"] == "hotel_option" for card in search["cards"]),
                f"{len(search['cards'])} cards, tools {search['tools']}\n"
                "Cards travel in the tool response, which terminates at the model — so they have\n"
                "to be forwarded onto the stream or the UI has nothing to draw.",
            )
        if not search["cards"]:
            report("a booking completes through card clicks", False, "no cards to click")
            return

        # The click the SPA would post: an action id and its payload, straight off the card.
        select = next(
            (a for a in search["cards"][0].get("actions", []) if a["id"] == "select_hotel"), None
        )
        if not select:
            report("the option card offers a select action", False, "no select_hotel action")
            return
        prepared = _events(
            api_url,
            cookie,
            conversation_id,
            {"action_id": select["id"], "payload": select["payload"]},
            "actions",
        )
        summary = next((c for c in prepared["cards"] if c["card_type"] == "booking_summary"), None)
        if not summary:
            report(
                "clicking select prepares a booking",
                False,
                f"no booking_summary card; tools {prepared['tools']}",
            )
            return
        summaries[who] = summary

        if who == "priya":
            report(
                "a click resolves against the previous turn's search",
                prepared["tools"] == ["prepare_booking"],
                "which only works with conversation history — without it the agent asks the\n"
                "traveller to start again, because the write path is three turns by design",
            )
            confirm = next(
                (a for a in summary.get("actions", []) if a["id"] == "confirm_booking"), None
            )
            if not confirm:
                report("globex is offered a confirm button", False, "no confirm_booking action")
                return
            confirmed = _events(
                api_url,
                cookie,
                conversation_id,
                {"action_id": "confirm_booking", "payload": confirm["payload"]},
                "actions",
            )
            booked = next(
                (c for c in confirmed["cards"] if c["card_type"] == "booking_confirmed"), None
            )
            # **A confirmation claimed without the tool is worse than a failure**, so the assertion
            # is
            # on the *card*, not on the prose. A run of this suite caught the agent replying "Your
            # booking is confirmed. The reference is BKG-535399F53C." having called no tool at all —
            # a reference that exists nowhere, for a booking that never happened. Real ones are
            # `bkg_…`/`TRV…` from the tool result.
            #
            # Checking the text would have passed that answer. Checking for `booking_confirmed`
            # cannot:
            # the card only exists if `confirm_booking` returned one.
            report(
                "clicking confirm completes the booking",
                booked is not None,
                f"confirmation {booked['data'].get('confirmation_number')}"
                if booked
                else f"no booking_confirmed card; tools {confirmed['tools']}",
            )

    # **The capability difference, and the point is that it is UI rather than prose.** A handoff
    # tenant's summary carries no confirm action at all, so there is no button to press and no
    # ambiguity about whether the agent may transact. The renderer does not branch on tenant — it
    # draws what the card says.
    globex = summaries.get("priya", {})
    initech = summaries.get("sam", {})
    globex_actions = [a["id"] for a in globex.get("actions", [])]
    initech_actions = [a["id"] for a in initech.get("actions", [])]
    report(
        "globex can confirm in chat; initech cannot, and gets a checkout link",
        "confirm_booking" in globex_actions
        and not initech_actions
        and bool(initech.get("data", {}).get("checkout_url")),
        f"globex mode={globex.get('data', {}).get('mode')} actions={globex_actions}\n"
        f"initech mode={initech.get('data', {}).get('mode')} actions={initech_actions or 'none'} "
        f"checkout_url={'yes' if initech.get('data', {}).get('checkout_url') else 'no'}",
    )


def _get(url: str, cookie: str | None = None) -> tuple[int, dict, str]:
    headers = {"Cookie": f"{COOKIE_NAME}={cookie}"} if cookie else {}
    return _send(urllib.request.Request(url, method="GET", headers=headers))


def _post(
    url: str, body: dict, cookie: str | None = None, headers: dict | None = None
) -> tuple[int, dict, str]:
    all_headers = {"Content-Type": "application/json", **(headers or {})}
    if cookie:
        all_headers["Cookie"] = f"{COOKIE_NAME}={cookie}"
    return _send(
        urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST", headers=all_headers
        )
    )


def _send(request: urllib.request.Request) -> tuple[int, dict, str]:
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, dict(response.headers), response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read().decode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--password", help="shared demo password, for the login flow")
    parser.add_argument("--username", default="priya")
    parser.add_argument("--tenant", default="globex")
    parser.add_argument(
        "--session-cookie",
        help="an existing session id, to run the authenticated checks without a login",
    )
    args = parser.parse_args()

    values = parameters()
    api_url = values[API_URL_PARAM]
    print(f"Conversation API: {api_url}\n")

    # Read rather than required, so the password does not have to travel through shell history — and
    # so a stale one cannot be passed after a re-seed and read as a broken deployment. An explicit
    # `--session-cookie` still skips the login entirely, which is how the authenticated checks run
    # against a pool seeded by hand.
    password = args.password or (None if args.session_cookie else refs.demo_password)

    browser = Browser()
    cookie = args.session_cookie
    if not cookie and password:
        print("Login flow — PKCE, exchanged server-side")
        cookie = establish_session(browser, api_url, args.username, password)

    check_streaming(api_url, cookie, bearer_for(cookie))
    check_cookie(browser)
    check_fail_closed(api_url, cookie)
    check_csrf(api_url, cookie)
    check_actions(api_url, cookie)
    check_documents(api_url, cookie, args.tenant)
    check_tenant_contrast(api_url, password, args.username)
    check_booking(api_url, password)

    passed = sum(_results)
    print(f"\n{passed}/{len(_results)} checks passed")
    if not cookie:
        print(
            "\nNo browser session was established, so the authenticated checks could not run.\n"
            "The hosted-UI flow needs a real browser (the web client has no password flow, by\n"
            "design). Complete a login in a browser, copy the session cookie, and re-run with\n"
            "--session-cookie to prove the streaming and per-tenant checks."
        )
    return 0 if passed == len(_results) else 1


if __name__ == "__main__":
    sys.exit(main())
