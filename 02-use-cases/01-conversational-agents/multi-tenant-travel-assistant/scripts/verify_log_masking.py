"""Verify PII masking at log ingestion — including the permission boundary.

    cd backend && AWS_REGION=us-east-1 uv run python ../scripts/verify_log_masking.py

Turns on `TRAVEL_DEMO_LOG_PII` on the deployed backend, calls `GET /v1/travelers/{id}` so it logs
the full profile on the **real** path, reads the stored log line back two ways, and turns the switch
off again in a `finally`.

**The switch is an environment variable rather than a query parameter, which is why this script
has to set it.** As `?debug_log_pii=true` it was flippable by anyone who could reach the URL,
defended only by a docstring — so the demonstration cost the sample a PII-logging switch on a
public contract. Moving it to the deployment means a caller cannot enable it and a fork does not
inherit it. The cost lands here: two `UpdateFunctionConfiguration` calls and a wait.

Checks:
  A. Value-shaped PII (name, email) is masked in the stored line.
  A2. **Keyword-sensitive identifiers do not mask nested values** — asserted as a known limit, so
     a future service change breaks the check instead of silently invalidating the docs.
  B. Read with `logs:Unmask`, the real value **is** visible — proving masking is an access
     boundary rather than destructive redaction, and that the data is still there for an incident
     responder who is granted that permission deliberately.
  C. Opaque ids (`trv_…`, `globex`) are **not** masked, so debuggability survives. This is the
     payoff of choosing opaque identifiers: masking can be aggressive without making logs
     useless.

**Polls, because masking happens at ingestion.** An immediate read races the mask and would
report a false pass — the value would still be in flight, not yet stored masked.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from deployed_refs import refs

# Not a literal: a reader deploying to another region would otherwise get a script that
# addresses us-east-1 while their stack is elsewhere. Same default and same reason as
# `deploy.sh` — `TRAVEL_REGION` wins over an ambient `AWS_REGION` set for other work.
REGION = refs.region
BACKEND_LOG_GROUP = "/aws/lambda/multi-tenant-travel-mock-tmc"
BACKEND_FUNCTION = "multi-tenant-travel-mock-tmc"
# Must match `backend/app/routers/profile.py::PII_LOG_DEMO_VAR`. Stated in both places because they
# cross a process boundary; a mismatch shows up as a missing log line rather than as an error.
PII_DEMO_VAR = "TRAVEL_DEMO_LOG_PII"
# The API id is generated per deployment, so this comes from the parameter the infra stack
# publishes for it rather than from a pasted URL — see `deployed_refs.py`.
BACKEND_URL = refs.parameter("/multi-tenant-travel/backend/api-url")

TENANT = "globex"
TRAVELER_ID = "trv_31d81fa59772"
# Fixture data only — nothing here is a real document or a real person.
FIXTURE_PASSPORT = "X44719025"
FIXTURE_FULL_NAME = "Priya Raghunathan"
FIXTURE_EMAIL = "priya.raghunathan@globex.example"

DEMO_MARKER = "DEMO ONLY: logging an unredacted profile"


def report(name: str, passed: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    for line in detail.splitlines():
        if line:
            print(f"        {line}")
    return passed


def set_pii_demo(enabled: bool) -> None:
    """Flip `TRAVEL_DEMO_LOG_PII` on the deployed backend and wait for it to take effect.

    **Updating a function's environment replaces the execution environment**, so the next invoke
    is a cold start reading the new value — which is what makes this work, and also why it needs a
    wait rather than an immediate call. The handler reads it per-request, so no import-time capture
    can go stale between these two calls.
    """
    client = boto3.client("lambda", region_name=REGION)
    current = client.get_function_configuration(FunctionName=BACKEND_FUNCTION)
    env = dict(current.get("Environment", {}).get("Variables", {}))
    if enabled:
        env[PII_DEMO_VAR] = "true"
    else:
        env.pop(PII_DEMO_VAR, None)
    client.update_function_configuration(
        FunctionName=BACKEND_FUNCTION, Environment={"Variables": env}
    )
    waiter = client.get_waiter("function_updated_v2")
    waiter.wait(FunctionName=BACKEND_FUNCTION)


def call_backend() -> int:
    """Hit the profile endpoint, signed. Returns the HTTP status.

    **The signing is not optional, and this script was broken without it.** The mock TMC became
    `AWS_IAM`-authorized, so an unsigned call is refused before the handler runs — the whole suite
    stopped at "backend returned 403: Missing Authentication Token", which reads like a broken
    endpoint rather than a stale caller. Nothing re-ran it after that change, so it sat failing.

    Developer credentials can sign here because they carry `execute-api:Invoke`; the tool Lambdas
    reach the same API the same way (`tools/common/backend.py::_sign`), and the ordering constraint
    is the same: sign **last**, with every header already attached, or the signature covers a
    different request than the one sent and the 403 says nothing about which header was wrong.
    """
    url = f"{BACKEND_URL}/v1/travelers/{TRAVELER_ID}"
    request = urllib.request.Request(
        url, headers={"X-Tenant-Id": TENANT, "Accept": "application/json"}
    )
    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials is None:
        print("        no AWS credentials available to sign the request")
        return 0
    signable = AWSRequest(
        method=request.get_method(),
        url=request.full_url,
        data=request.data,
        headers=dict(request.headers),
    )
    SigV4Auth(credentials, "execute-api", session.region_name or REGION).add_auth(signable)
    for name, value in signable.headers.items():
        request.add_unredirected_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status
    except urllib.error.HTTPError as error:
        print(f"        backend returned {error.code}: {error.read().decode()[:200]}")
        return error.code


def find_line(*, unmask: bool, since_ms: int, attempts: int = 12) -> str | None:
    """The demo log line as stored, masked or unmasked.

    **`since_ms` is not optional in spirit.** A window that reaches back before the call under
    test will happily return an *earlier* run's line — which is how a stale event from before a
    fixture change produced a confusing failure here. Scoping to "after we made the request" is
    what makes the assertion about this run.

    `unmask=True` sets `logs:Unmask` on the read. If the caller's credentials lack that
    permission the call raises `AccessDeniedException`, which is itself the boundary working —
    handled by the caller rather than swallowed here.
    """
    logs = boto3.client("logs", region_name=REGION)
    start = since_ms
    for _ in range(attempts):
        kwargs = {
            "logGroupName": BACKEND_LOG_GROUP,
            "startTime": start,
            # Quoted: an unquoted multi-word CloudWatch filter pattern is parsed as several
            # independent terms and silently matches nothing.
            "filterPattern": f'"{DEMO_MARKER}"',
        }
        if unmask:
            kwargs["unmask"] = True
        response = logs.filter_log_events(**kwargs)
        events = response.get("events", [])
        if events:
            return events[-1]["message"]
        time.sleep(10)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    results: list[bool] = []

    # **`finally`, because leaving the switch on is worse than the test failing.** Every exit path
    # from here — a failed assertion, a missing log line, Ctrl-C — must clear it, or a flag that
    # logs unredacted PII survives the run that set it.
    try:
        print(f"\nEnabling {PII_DEMO_VAR} on {BACKEND_FUNCTION} (demo only, cleared at the end)")
        set_pii_demo(True)
        print("Calling GET /v1/travelers/{id} — the backend will log the unredacted record")
        # Recorded before the call so the log search cannot pick up an earlier run's line.
        called_at_ms = int(time.time() * 1000) - 5_000
        status = call_backend()
        results.append(report("backend returned the profile", status == 200, f"HTTP {status}"))
        if status != 200:
            print("\nstopping: no log line to inspect")
            return 1

        print("\nWaiting for ingestion (masking happens on the way in, so an immediate read races)")
        masked = find_line(unmask=False, since_ms=called_at_ms)
        if masked is None:
            report("demo log line found", False, "no matching line within ~2 minutes")
            return 1

        print("\nA. Value-shaped PII is masked at ingestion")
        results.append(
            report(
                "the traveller's name is masked",
                FIXTURE_FULL_NAME not in masked and "*****" in masked,
                "`Name` matches on the value's own shape, so nesting does not defeat it",
            )
        )
        results.append(
            report(
                "the email address is masked",
                FIXTURE_EMAIL not in masked,
                "same — `EmailAddress` is shape-based, not keyword-based",
            )
        )

        print("\nA2. Keyword-sensitive identifiers do NOT mask nested values (measured limit)")
        results.append(
            report(
                "passport under a generic JSON key is NOT masked — documented, not aspirational",
                FIXTURE_PASSPORT in masked,
                "`PassportNumber-US` needs the token `passport` beside the value. The real shape\n"
                f'  {{"passports":[{{"country":"US","number":"{FIXTURE_PASSPORT}"}}]}}\n'
                "does not match. This asserts the limit deliberately: if a future AWS change\n"
                "starts masking it, this check fails and the docs get corrected — better than a\n"
                "comment nobody re-tests. The primary control remains tool-layer curation, which\n"
                "never emits a passport number at all.",
            )
        )

        print("\nB. logs:Unmask reveals it — masking is an access boundary, not deletion")
        try:
            unmasked = find_line(unmask=True, since_ms=called_at_ms, attempts=1)
            visible = bool(unmasked and FIXTURE_FULL_NAME in unmasked)
            results.append(
                report(
                    "with logs:Unmask the real value is visible",
                    visible,
                    "So the data survives for an incident responder granted that permission, while "
                    "an operator with ordinary log-read access cannot see it."
                    if visible
                    else "unmask returned a line without the value — unexpected",
                )
            )
        except Exception as error:  # noqa: BLE001 - AccessDenied here is a meaningful outcome
            results.append(
                report(
                    "logs:Unmask is a separate permission",
                    "AccessDenied" in str(error),
                    f"{str(error)[:160]}\nThe caller lacks logs:Unmask — which is the boundary "
                    "working, not a test failure.",
                )
            )

        print("\nC. Opaque ids stay readable, so logs remain debuggable")
        results.append(
            report(
                "traveller id and tenant are NOT masked",
                TRAVELER_ID in masked and TENANT in masked,
                f"{TRAVELER_ID} and {TENANT} both present — the payoff of opaque ids: masking is "
                "aggressive without destroying debuggability",
            )
        )

        print(f"\n{sum(results)}/{len(results)} checks passed")
        return 0 if all(results) else 1
    finally:
        print(f"\nClearing {PII_DEMO_VAR} on {BACKEND_FUNCTION}")
        set_pii_demo(False)


if __name__ == "__main__":
    sys.exit(main())
