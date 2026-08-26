"""Verify the audit trail: can CloudTrail alone attribute a data access?

    cd backend && AWS_REGION=us-east-1 uv run python ../scripts/verify_audit.py
Runs one real conversation turn, then asks **CloudTrail** — not our own logs — who it was for.
That distinction is the whole point: an application that is wrong about what it did will be wrong
in its logs too, in the same direction. CloudTrail is written by AWS.

Checks:
  A. The `AssumeRole` for the tenant data role carries all three session tags.
  B. `tenant` is transitive and the audit tags are not — a later, unrelated role chain must not
     inherit a stale conversation id, while nothing downstream may re-tag itself into another
     tenant.
  C. `user` is a **hash**, not a traveller id. CloudTrail is retained for years and shipped to
     SIEMs; a per-person identifier accumulating there becomes a person-tracking dataset by
     accident.
  D. The application log line for the same request carries the *same* `session_id` and hashed
     `user`, so audit and cost/debug records join on one dimension set with no mapping table.

**Known limit, asserted rather than hidden (check E):** DynamoDB *item-level* events cannot be
selected on a trail in this region — both basic and advanced selectors are rejected by the
service. So the trail proves *which tenant, which conversation, on whose behalf obtained
credentials*, not which individual row was then read. The row-level guarantee rests on the IAM
`LeadingKeys` boundary making a cross-tenant read impossible, which `verify_isolation` covers.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import boto3
from deployed_refs import refs

# Not a literal: a reader deploying to another region would otherwise get a script that
# addresses us-east-1 while their stack is elsewhere. Same default and same reason as
# `deploy.sh` — `TRAVEL_REGION` wins over an ambient `AWS_REGION` set for other work.
REGION = os.environ.get("TRAVEL_REGION") or os.environ.get("AWS_REGION") or "us-east-1"
DATA_ROLE_NAME = "multi-tenant-travel-tenant-data"
BACKEND_LOG_GROUP = "/aws/lambda/multi-tenant-travel-mock-tmc"
# Stated rather than derived from another name. This used to be `DATA_ROLE_NAME.split("-")[0]`,
# which worked only while the stack name was a single word — renaming the project turned it into
# `multi`, and the failure would have surfaced as a missing trail rather than as a wrong constant.
AUDIT_TRAIL_NAME = "multi-tenant-travel-audit"
# Priya's traveller id, so the hash can be recomputed independently rather than trusted.
PRIYA_TRAVELER_ID = "trv_31d81fa59772"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def report(name: str, passed: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    for line in detail.splitlines():
        if line:
            print(f"        {line}")
    return passed


class SearchStatus(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True)
class AssumeRoleSearch:
    status: SearchStatus
    pages: int
    event: dict[str, Any] | None = None


def assume_role_event(
    session: str,
    minutes: int = 20,
    max_pages: int = 40,
    *,
    cloudtrail: Any | None = None,
) -> AssumeRoleSearch:
    """The `AssumeRole` for our data role carrying this conversation's tag.

    **Pages, because a single `MaxResults=50` page is nowhere near enough and the shortfall reads as
    a
    broken chain.** `AssumeRole` is one of the noisiest events in the account — a busy 30 minutes
    here
    produced ~3,300 of them, of which 54 carried session tags. Reading only the newest 50 found the
    tagged assumption **only when the account happened to be quiet**, so this check failed while the
    attribution chain was completely intact: the tags were present, just thousands of events deep.

    `ResourceName` would be the natural server-side filter, but CloudTrail permits exactly one
    lookup
    attribute per call and `EventName` is the one that keeps the scan bounded. So the filter stays
    client-side and the *pagination* is what makes it correct.

    `max_pages` bounds the walk at ~2,000 events rather than leaving it unbounded — and a bound that
    is
    hit is reported by the caller rather than silently returning `None`, because "not found" and
    "gave
    up looking" are different answers.
    """
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")

    ct = cloudtrail or boto3.client("cloudtrail", region_name=REGION)
    end = datetime.datetime.now(datetime.UTC)
    start = end - datetime.timedelta(minutes=minutes)
    token, pages = None, 0
    while pages < max_pages:
        kwargs = {
            "LookupAttributes": [{"AttributeKey": "EventName", "AttributeValue": "AssumeRole"}],
            "StartTime": start,
            "EndTime": end,
            "MaxResults": 50,
        }
        if token:
            kwargs["NextToken"] = token
        response = ct.lookup_events(**kwargs)
        pages += 1
        for event in response.get("Events", []):
            raw = event["CloudTrailEvent"]
            if DATA_ROLE_NAME not in raw or session not in raw:
                continue
            return AssumeRoleSearch(SearchStatus.FOUND, pages, json.loads(raw))
        token = response.get("NextToken")
        if not token:
            return AssumeRoleSearch(SearchStatus.NOT_FOUND, pages)
    return AssumeRoleSearch(SearchStatus.EXHAUSTED, pages)


def backend_log_line(session: str, minutes: int = 20, attempts: int = 6) -> dict | None:
    """Our own log line for the same role assumption, to prove the dimensions match.

    **Polls, because the line is only written on a cache miss.** Credentials are cached per
    (tenant, session, traveller) per container, so the `AssumeRole` — and therefore the log line —
    happens once per conversation per warm container, not once per request. A single immediate
    read can miss it either because ingestion lags or because the line was written by a container
    that served an earlier turn. Both look identical to a broken chain, which is why this retries
    rather than concluding on one look.
    """
    logs = boto3.client("logs", region_name=REGION)
    start = int((time.time() - minutes * 60) * 1000)
    for _ in range(attempts):
        try:
            response = logs.filter_log_events(
                logGroupName=BACKEND_LOG_GROUP,
                startTime=start,
                # **Quoted deliberately.** An unquoted multi-word CloudWatch filter pattern is
                # parsed as several independent terms and matches nothing — it returns zero events
                # rather than an error, so it reads as "the chain is broken" instead of "the query
                # is wrong". Cost a false failure here before it was spotted.
                filterPattern='"assumed tenant-scoped data role"',
            )
        except logs.exceptions.ResourceNotFoundException:
            return None
        for event in response.get("events", []):
            if session not in event["message"]:
                continue
            try:
                return json.loads(event["message"])
            except json.JSONDecodeError:
                continue
        time.sleep(10)
    return None


def main() -> int:
    # The live verification helpers resolve deployed SSM references at import time. Keep that work
    # on
    # the executable path so pagination tests can import this module with no AWS account or
    # deployment.
    from scripts.verify_guardrails import invoke_agent, text_of, token_for
    from scripts.verify_guardrails import session_id as make_session_id

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--password",
        help="shared demo password; read from Parameter Store when omitted",
    )
    parser.add_argument("--user", default="priya")
    args = parser.parse_args()

    # Read rather than required, so a credential need not travel through shell history.
    token = token_for(args.user, args.password or refs.demo_password)
    # **Unique per run, and that is what makes this check work at all.** `make_session_id("audit")`
    # returns the *same* padded string every time, and the backend caches tenant credentials for an
    # hour keyed on `(tenant, session, traveller)` — so the first run of the hour assumed the role
    # and
    # every run after it reused the cached credential, calling no `AssumeRole` and writing no log
    # line.
    # The failure is indistinguishable from a broken attribution chain: the turn answers correctly,
    # CloudTrail simply has nothing new to find. Suffixing the id forces a cache miss, which is
    # exactly
    # what a check on the *act* of assuming a role needs.
    session = f"{make_session_id('audit')[:40]}-{int(time.time())}"[:64]
    results: list[bool] = []

    print(f"\nRunning one turn with session {session}")
    events = invoke_agent(token, "What is my hotel nightly cap?", session)
    answer = text_of(events)
    results.append(
        report("the turn produced a real answer", "250" in answer, f"answer: {answer[:140]!r}")
    )

    # CloudTrail delivery is not instant; a trail typically lands events within a few minutes.
    print("\nWaiting for CloudTrail delivery...")
    search = AssumeRoleSearch(SearchStatus.NOT_FOUND, 0)
    for _ in range(10):
        search = assume_role_event(session)
        if search.status is SearchStatus.FOUND:
            break
        if search.status is SearchStatus.EXHAUSTED:
            report(
                "AssumeRole visible in CloudTrail",
                False,
                f"search limit reached after {search.pages} pages "
                f"(~{search.pages * 50:,} events) while more pages remained",
            )
            print("\nAudit check inconclusive: CloudTrail search exhausted before a match")
            return 1
        time.sleep(20)

    if search.status is not SearchStatus.FOUND or not search.event:
        report("AssumeRole visible in CloudTrail", False, "no matching event within ~3 minutes")
        print("\n0 checks passed (CloudTrail delivery lag or a broken chain)")
        return 1

    event = search.event
    params = event.get("requestParameters") or {}
    tags = {t["key"]: t["value"] for t in (params.get("tags") or [])}

    print("\nA. CloudTrail alone attributes the credential grant")
    results.append(
        report(
            "all three session tags present",
            {"tenant", "session_id", "user"} <= set(tags),
            f"tenant={tags.get('tenant')}\nsession_id={tags.get('session_id')}\n"
            f"user={tags.get('user')}",
        )
    )
    results.append(
        report(
            "the conversation id matches the turn we ran",
            tags.get("session_id") == session,
            f"expected {session}",
        )
    )

    print("\nB. Transitivity is asymmetric on purpose")
    transitive = params.get("transitiveTagKeys") or []
    results.append(
        report(
            "only `tenant` is transitive",
            transitive == ["tenant"],
            f"transitiveTagKeys={transitive} — a transitive conversation id would be inherited "
            "by a later, unrelated chain and the trail would start lying",
        )
    )

    print("\nC. The person is hashed, not identified")
    expected = hashlib.sha256(PRIYA_TRAVELER_ID.encode()).hexdigest()[:16]
    results.append(
        report(
            "`user` is a hash of the traveller id, and no raw id appears",
            tags.get("user") == expected and PRIYA_TRAVELER_ID not in json.dumps(tags),
            f"user={tags.get('user')} recomputed={expected}",
        )
    )

    print("\nD. Audit and application records join on one dimension set")
    line = backend_log_line(session)
    facts = (line or {}).get("facts") or {}
    results.append(
        report(
            "the backend's own log line carries the same session_id and hashed user",
            facts.get("session_id") == tags.get("session_id")
            and facts.get("user") == tags.get("user"),
            f"log: session_id={facts.get('session_id')} user={facts.get('user')}",
        )
    )

    print("\nE. Known limit, asserted so it cannot be forgotten")
    ct = boto3.client("cloudtrail", region_name=REGION)
    selectors = ct.get_event_selectors(TrailName=AUDIT_TRAIL_NAME)
    data_resources = [
        r for s in (selectors.get("EventSelectors") or []) for r in (s.get("DataResources") or [])
    ]
    results.append(
        report(
            "no DynamoDB data-event selector (the service rejects it on a trail)",
            not data_resources,
            "So item-level row reads are NOT in the trail. Attribution stops at the credential "
            "grant; the row-level guarantee is IAM LeadingKeys, not after-the-fact detection.",
        )
    )

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
