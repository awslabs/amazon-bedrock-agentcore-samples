"""HTTP client for the mock TMC.

Tools call the backend **over HTTP and never import its code**. That boundary is the
sample's central claim: `backend/` is the folder a reader deletes and replaces with
their real travel platform, and an import would quietly make that impossible.

`urllib` rather than `requests` or `httpx`: this runs in a zip-packaged Lambda, the
request is one GET with a header, and every dependency added here is a cold-start
cost paid on the conversational path plus a native-wheel risk at package time.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .context import RequestContext
from .errors import BackendError

# Long enough for a cold backend Lambda, short enough that a hung call surfaces as
# a refusal inside a conversation rather than a Gateway timeout.
DEFAULT_TIMEOUT_SECONDS = 10

# Fallback only. Lambda always sets `AWS_REGION`; this keeps a local run from failing with a
# signing error that reads like a credentials problem.
_REGION = os.environ.get("AWS_REGION", "us-east-1")


def _send(request: urllib.request.Request, path: str, timeout: int) -> Any:
    """Perform the call and translate failures into `BackendError`.

    Shared by `get` and `post` so the error handling cannot diverge between them — a POST that
    reported failures differently from a GET would make the write path's refusals inconsistent
    with the read path's, and the model would treat them differently.

    Signing happens here, once, for the same reason the error handling does: it is the single point
    both verbs pass through, and a signature applied in two places is a signature that can diverge
    in one of them.
    """
    _sign(request)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        # The body often carries a useful `detail`, but it is the *backend's* text and may name
        # internals, so callers decide what reaches the model.
        body = error.read().decode(errors="replace")[:500]
        raise BackendError(
            f"backend returned {error.code} for {path}: {body}", status=error.code
        ) from None
    except urllib.error.URLError as error:
        raise BackendError(f"backend unreachable for {path}: {error.reason}") from None
    except json.JSONDecodeError:
        raise BackendError(f"backend returned a non-JSON body for {path}") from None


def post(
    base_url: str,
    path: str,
    context: RequestContext,
    *,
    body: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """POST a tenant-scoped resource.

    Used for the requests whose inputs are an object rather than a couple of path segments
    (searches, eligibility questions) and for the ones that genuinely write (hold, confirm,
    cancel). Identity headers come from the verified context exactly as in `get` — the method
    changes, the trust boundary does not.
    """
    request = urllib.request.Request(
        f"{base_url}{path}",
        method="POST",
        data=json.dumps(body or {}).encode(),
        headers={**_headers(context), "Content-Type": "application/json"},
    )
    return _send(request, path, timeout)


def get(
    base_url: str,
    path: str,
    context: RequestContext,
    *,
    params: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """GET a tenant-scoped resource.

    The tenant header is applied **here**, from the verified context — not passed in
    by callers. A caller that could choose the header is a caller that could choose
    the tenant, which is the whole thing the design prevents.
    """
    url = f"{base_url}{path}"
    if params:
        # **`quote_via=quote`, because the default breaks SigV4 on any value containing a space.**
        # `urlencode` defaults to `quote_plus`, which encodes a space as `+` — the
        # `application/x-www-form-urlencoded` convention. SigV4's canonical query string is RFC
        # 3986, where a space is `%20` and a literal `+` means `%2B`. So a `+` on the wire is signed
        # as a plus by botocore and decoded as a space by API Gateway, so the two canonical forms
        # differ and the request is rejected:
        #
        #     403 The request signature we calculated does not match the signature you provided.
        #
        # **The symptom points at credentials, and the cause is a space in a name.** The only
        # caller passing a value a human typed is `resolve_target_traveler`, so this failed for
        # `?name=Sam Whitfield` and succeeded for `?name=Sam` — an arranger booking for a colleague
        # by full name, which is the normal case. The tool reports it as `BackendError`, which the
        # agent narrates as "I couldn't reach the travel system", so nothing says "signing".
        url = f"{url}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"

    request = urllib.request.Request(url, method="GET", headers=_headers(context))
    return _send(request, path, timeout)


def _trace_header() -> dict[str, str]:
    """The caller's trace context, so the backend call joins the trace instead of starting one.

    **The hole this closes.** Auto-instrumentation patches `requests`/`urllib3`/`httpx`; this module
    uses stdlib `urllib.request` on purpose, so the tool Lambdas carry no HTTP dependency on the
    conversational path — and nothing propagates the span. The mock TMC's API Gateway has active
    tracing, so a request with no trace context does not merely lose its parent: it *starts a new
    trace*. Every tool call therefore appeared as an unrelated root, and the one question a
    waterfall exists to answer — which backend call made this turn slow — could not be asked.

    **`X-Amzn-Trace-Id` rather than `traceparent`**, which is a correction to what this file used to
    claim. W3C is the right header when something downstream speaks OTel; here the next hop is API
    Gateway and X-Ray, which read the AWS header and ignore the W3C one. Emitting `traceparent`
    would have looked more standards-shaped and joined nothing.

    Read from the environment rather than from a tracing SDK, so this stays a header and not a
    dependency. Lambda populates `_X_AMZN_TRACE_ID` when the invocation is sampled; absent means
    this request is not being traced, and then there is nothing to propagate.
    """
    trace_id = os.environ.get("_X_AMZN_TRACE_ID")
    return {"X-Amzn-Trace-Id": trace_id} if trace_id else {}


def _sign(request: urllib.request.Request) -> None:
    """Add SigV4 to a request in place, so the `AWS_IAM` backend will accept it.

    **Why the backend requires this at all.** The API trusts `X-Tenant-Id`, because the gateway
    interceptor is what establishes tenant identity by overwriting it from a verified token. That
    trust is only sound if nobody else can send the header — and before `AWS_IAM` the API was
    public, so `curl -H "X-Tenant-Id: globex"` returned full profile PII. Signing does not make the
    header trustworthy; it makes the *caller* trustworthy, turning the header into an internal
    contract.
    The interceptor decides which tenant; IAM decides who may assert one.

    **botocore rather than a signing dependency**, and rather than switching to `requests` so an SDK
    could sign for us. botocore is already in a Lambda's runtime, so this costs an import on a cold
    start and nothing on the request path — the same trade `_trace_header` makes, and the reason
    `urllib` was chosen for this module in the first place.

    **Order matters, and this is the bug waiting to happen.** SigV4 covers the headers present when
    it signs, so adding `X-Tenant-Id` afterwards yields a signature that does not match what is
    sent — and the backend answers 403 with nothing to say about which header was wrong. So this is
    called last, from `_send`, with the request fully built.
    """
    import boto3
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials is None:
        raise BackendError("no AWS credentials available to sign the backend request")

    signable = AWSRequest(
        method=request.get_method(),
        url=request.full_url,
        data=request.data,
        headers=dict(request.headers),
    )
    SigV4Auth(credentials, "execute-api", session.region_name or _REGION).add_auth(signable)
    for name, value in signable.headers.items():
        request.add_unredirected_header(name, value)


def _headers(context: RequestContext) -> dict[str, str]:
    """Tenant always; traveller when acting for someone; session for the audit trail."""
    from .context import SESSION_HEADER, TENANT_HEADER, TRAVELER_HEADER

    headers = {TENANT_HEADER: context.tenant_id, "Accept": "application/json", **_trace_header()}
    if context.traveler_id:
        headers[TRAVELER_HEADER] = context.traveler_id
    if context.session_id:
        # Carried so the backend can put it on the STS session tag, which is what makes a
        # CloudTrail data event traceable back to one conversation. Never an authorization
        # input — see `SESSION_HEADER`.
        headers[SESSION_HEADER] = context.session_id
    return headers
