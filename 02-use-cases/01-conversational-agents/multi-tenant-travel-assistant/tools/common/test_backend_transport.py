"""What a tool puts on the wire to the backend: trace context, and a signature.

**Tested because the failure is silent and the symptom is misleading.** With no `X-Amzn-Trace-Id` on
the request, the mock TMC's API Gateway — which has active tracing — does not lose a parent span, it
starts an entirely new trace. Every tool call becomes its own root, so a slow turn looks like a fast
agent next to a pile of unrelated one-hop traces, and the question a waterfall exists to answer
cannot be asked. Nothing errors, and the traces that appear look healthy.
"""

from __future__ import annotations

from tools.common.backend import _trace_header

SAMPLED = "Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=1"


class TestTraceHeader:
    def test_forwards_the_lambda_trace_context(self, monkeypatch):
        monkeypatch.setenv("_X_AMZN_TRACE_ID", SAMPLED)
        assert _trace_header() == {"X-Amzn-Trace-Id": SAMPLED}

    def test_absent_when_the_invocation_is_not_traced(self, monkeypatch):
        """No header at all, rather than an empty one.

        An `X-Amzn-Trace-Id: ` with no value is not a trace context; sending one invites the
        downstream to parse it and makes an untraced request look like a broken traced one.
        """
        monkeypatch.delenv("_X_AMZN_TRACE_ID", raising=False)
        assert _trace_header() == {}

    def test_it_is_the_aws_header_and_not_the_w3c_one(self, monkeypatch):
        """The next hop is API Gateway and X-Ray, which read this header and ignore `traceparent`.

        Asserted because `traceparent` is the more standards-shaped choice and was what this file
        originally proposed — it would have joined nothing here.
        """
        monkeypatch.setenv("_X_AMZN_TRACE_ID", SAMPLED)
        assert "traceparent" not in _trace_header()


class TestHeadersCarryIt:
    def test_the_backend_request_includes_the_trace(self, monkeypatch):
        """The header has to reach `_headers`, not merely exist as a helper."""
        monkeypatch.setenv("_X_AMZN_TRACE_ID", SAMPLED)
        from tools.common.backend import _headers
        from tools.common.context import RequestContext

        headers = _headers(
            RequestContext(
                tenant_id="globex", traveler_id="trv_1", session_id="s1", role="traveler"
            )
        )
        assert headers["X-Amzn-Trace-Id"] == SAMPLED
        # Identity headers still present: the trace rides alongside them, replacing none.
        assert headers["X-Tenant-Id"] == "globex"


class TestSigning:
    """SigV4 on the backend call, and the ordering property that makes it correct.

    **Why the backend needs it.** The API trusts `X-Tenant-Id`, because the gateway interceptor
    establishes tenant identity by overwriting that header from a verified token. That trust only
    holds if nobody else can send the header — and before `AWS_IAM` the API was public, so
    `curl -H "X-Tenant-Id: globex"` returned full profile PII. Signing makes the *caller*
    trustworthy, not the header.
    """

    @staticmethod
    def _request(monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)

        import urllib.request

        from tools.common.backend import _headers, _sign
        from tools.common.context import RequestContext

        request = urllib.request.Request(
            "https://example.execute-api.us-east-1.amazonaws.com/v1/policy/hotel",
            method="GET",
            headers=_headers(
                RequestContext(
                    tenant_id="globex", traveler_id="trv_1", session_id="s1", role="traveler"
                )
            ),
        )
        _sign(request)
        return request

    def test_the_request_carries_a_sigv4_authorization_header(self, monkeypatch):
        request = self._request(monkeypatch)
        auth = request.get_header("Authorization")
        assert auth and auth.startswith("AWS4-HMAC-SHA256 "), auth
        assert "execute-api" in auth

    def test_the_identity_headers_are_covered_by_the_signature(self, monkeypatch):
        """The ordering trap, asserted.

        SigV4 signs the headers present when it runs. If `X-Tenant-Id` were added *after* signing,
        the signature would not match what is sent and the backend would answer 403 with nothing to
        say about which header was wrong. So the tenant header must appear in `SignedHeaders`.
        """
        request = self._request(monkeypatch)
        auth = request.get_header("Authorization")
        signed = auth.split("SignedHeaders=")[1].split(",")[0]
        assert "x-tenant-id" in signed, signed
        # And it is still actually on the request, not merely signed for.
        assert request.get_header("X-tenant-id") == "globex"

    def test_missing_credentials_are_a_backend_error_not_a_traceback(self, monkeypatch):
        """A tool with no credentials should refuse in the vocabulary the model already handles."""
        import urllib.request

        import boto3
        from tools.common.backend import _sign
        from tools.common.errors import BackendError

        monkeypatch.setattr(boto3.Session, "get_credentials", lambda self: None)
        request = urllib.request.Request("https://example.com/v1/health", method="GET")
        try:
            _sign(request)
        except BackendError as error:
            assert "credentials" in str(error)
        else:
            raise AssertionError("expected a BackendError")

    def test_a_space_in_a_query_value_is_percent_encoded_not_plus_encoded(self, monkeypatch):
        """A space must reach the wire as `%20`, because SigV4 and API Gateway disagree about `+`.

        **This is a regression test for a 403 that reads like a credentials problem.** `urlencode`
        defaults to `quote_plus`, so `{"name": "Sam Whitfield"}` became `name=Sam+Whitfield`. SigV4
        canonicalises the query per RFC 3986, where `+` is a literal plus; API Gateway decodes it
        as a space. The two forms differ and the request is rejected with *"The request signature we
        calculated does not match the signature you provided"*.

        The only caller passing a human-typed value is `resolve_target_traveler`, so the failure was
        invisible for `?name=Sam` and certain for `?name=Sam Whitfield` — an arranger booking for a
        colleague by full name. Asserted on the URL rather than on a signature, because the wire
        encoding is the property that matters and it holds without credentials.
        """
        import urllib.request

        from tools.common import backend
        from tools.common.context import RequestContext

        captured: dict[str, str] = {}

        def fake_send(request: urllib.request.Request, path: str, timeout: int) -> dict[str, str]:
            captured["url"] = request.full_url
            return {}

        monkeypatch.setattr(backend, "_send", fake_send)
        backend.get(
            "https://example.com",
            "/v1/arrangers/trv_1/resolve",
            RequestContext(tenant_id="globex", traveler_id="trv_1", role="arranger"),
            params={"name": "Sam Whitfield"},
        )

        assert "name=Sam%20Whitfield" in captured["url"], captured["url"]
        assert "+" not in captured["url"].split("?", 1)[1], captured["url"]
