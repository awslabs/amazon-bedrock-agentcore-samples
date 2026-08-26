"""Verify that a booking cannot happen twice — against DynamoDB, not a dict.

    cd backend && uv run python ../scripts/verify_booking_integrity.py

**Why this needs a deployment when 203 unit tests do not.** Every test in this repo runs against
`InMemoryRepository`, which models the *contract* — consuming an offer that is not held is an
error —
but cannot model how it is enforced. The real guarantee is a `TransactWriteItems` with a
`ConditionExpression` on the offer's status and `attribute_not_exists` on the reservation, and the
only way to know DynamoDB honours it is to make DynamoDB refuse. So the fast suite proves the rule
and
this proves the mechanism, once.

That split is deliberate rather than a shortcut: DynamoDB Local would add a container to a suite
whose
value is running in 2 seconds with no AWS account, to test one write path.

**What was actually broken.** `confirm` reads the offer, checks it is held, re-prices, then writes.
The write used to be two unconditional `put_item` calls. Two requests arriving together — a
double-click, or an HTTP retry after a timeout — both read `held`, both passed the check, and both
wrote: two reservations against one hold, which in a system with a real payment provider is two
charges.

Signed with SigV4 because the API is `AWS_IAM`-authorized. Developer credentials are the right
signer:
the question is whether a *legitimate* caller can double-book, not whether an anonymous one is
refused, which layer 8 of `verify_isolation.py` covers.
"""

from __future__ import annotations

import concurrent.futures
import json
import sys
import urllib.error
import urllib.request

import boto3
from deployed_refs import refs

TENANT = "globex"
TRAVELER = "trv_31d81fa59772"

DESTINATION = "Amsterdam"
CHECK_IN = "2026-12-05"
CHECK_OUT = "2026-12-08"


def _call(path: str, body: dict | None = None) -> tuple[int, dict]:
    """One signed request to the mock TMC, returning status and parsed body."""
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    # **The stage prefix appears twice, which is a documented trap in this repo.** The base URL
    # already ends in the stage (`/v1/`) and the routers carry their own `/v1`, so a booking route
    # is `/v1/v1/booking/...`. `verify_network.py` records the same thing: get it wrong and the
    # answer is 404, which is not a refusal and proves nothing.
    url = f"{refs.backend_api_url.rstrip('/')}/v1{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "X-Tenant-Id": TENANT,
        "X-Traveler-Id": TRAVELER,
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"

    session = boto3.Session()
    signable = AWSRequest(
        method="POST" if data is not None else "GET", url=url, data=data, headers=headers
    )
    SigV4Auth(session.get_credentials(), "execute-api", refs.region).add_auth(signable)

    request = urllib.request.Request(
        url,
        data=data,
        method="POST" if data is not None else "GET",
        headers=dict(signable.headers),
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        raw = error.read().decode(errors="replace")
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, {"raw": raw[:200]}


def hold_an_offer() -> str:
    """Search, then hold the first option, and return the handle."""
    status, found = _call(
        "/booking/search/hotels",
        {"destination": DESTINATION, "check_in": CHECK_IN, "check_out": CHECK_OUT},
    )
    if status != 200 or not (found or {}).get("options"):
        raise SystemExit(f"could not search hotels: HTTP {status} {found}")
    option = found["options"][0]

    status, held = _call(
        "/booking/hold",
        {
            "kind": "hotel",
            "option_id": option["option_id"],
            "destination": DESTINATION,
            "check_in": CHECK_IN,
            "check_out": CHECK_OUT,
        },
    )
    if status != 200:
        raise SystemExit(f"could not hold an offer: HTTP {status} {held}")
    return held["offer_id"]


def report(headline: str, passed: bool, detail: str) -> bool:
    print(f"  {'PASS' if passed else 'FAIL'}  {headline}")
    for line in detail.splitlines():
        print(f"        {line}")
    return passed


def main() -> int:
    print(f"Booking integrity against {refs.backend_api_url}\n")
    results: list[bool] = []

    offer_id = hold_an_offer()
    print(f"held {offer_id}\n")

    print("1. Two confirmations arriving together produce one booking")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_call, "/booking/confirm", {"offer_id": offer_id}) for _ in range(2)]
        outcomes = [f.result() for f in futures]
    statuses = sorted(status for status, _ in outcomes)

    # **The reference is read back, not predicted.** This script used to recompute the service's
    # `bkg_<suffix>` derivation itself, which made it assert an implementation detail and put a
    # fourth copy of that expression in the repo — the exact duplication `_booking_ref`'s docstring
    # warns about. Both callers returning the *same* ref is the stronger property anyway, and it
    # holds whatever the derivation is.
    issued = {
        (body or {}).get("booking_ref")
        for status, body in outcomes
        if status == 200 and isinstance(body, dict)
    }
    booking_ref = next(iter(issued)) if len(issued) == 1 else None

    results.append(
        report(
            "both callers were answered, with one reservation reference between them",
            statuses == [200, 200] and booking_ref is not None,
            f"statuses {statuses}, references issued {issued or '{}'} — the loser reads the "
            "winner's reservation back and returns it, so both get the same booking.\n"
            "This asserted [200, 409]. Booking once was always the requirement; refusing the loser "
            "was not, because the booking it asked for exists. Whether one reservation was created "
            "is checked below, on stored rows, which is where that invariant belongs.",
        )
    )

    print("\n2. The store holds exactly one reservation for that hold")
    status, reservations = _call("/booking/reservations")
    matching = [r for r in reservations or [] if r.get("booking_ref") == booking_ref]
    results.append(
        report(
            "exactly one reservation exists for the consumed offer",
            len(matching) == 1,
            f"HTTP {status}, {len(matching)} reservation(s) with ref {booking_ref}.\n"
            "**This is the check that carries the guarantee**, on stored rows rather than on "
            "responses — two 200s that left two reservations would satisfy every status assertion "
            "while being exactly the bug.",
        )
    )

    print("\n3. A later confirmation replays the same booking rather than making a second one")
    status, again = _call("/booking/confirm", {"offer_id": offer_id})
    replayed = (again or {}).get("booking_ref") if isinstance(again, dict) else None
    results.append(
        report(
            "a third confirmation returns the same reservation",
            status == 200 and replayed == booking_ref,
            f"HTTP {status}, booking_ref {replayed!r} against {booking_ref!r} — the winning "
            "transition landed and is what a retry now reads.\n"
            "This asserted a 409. A lost response is indistinguishable from a client-side failure, "
            "so a retry is correct behaviour — and 'nothing has been charged' was false in the one "
            "case where being wrong about it matters.",
        )
    )

    print("\n4. And still exactly one reservation after the replay")
    status, reservations = _call("/booking/reservations")
    matching = [r for r in reservations or [] if r.get("booking_ref") == booking_ref]
    results.append(
        report(
            "the replay created nothing",
            len(matching) == 1,
            f"{len(matching)} reservation(s) with ref {booking_ref} after three confirmations.",
        )
    )

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
