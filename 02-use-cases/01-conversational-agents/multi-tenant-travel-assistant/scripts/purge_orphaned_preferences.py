"""Delete preference records left behind by a replaced memory strategy.

    cd backend && uv run python ../scripts/purge_orphaned_preferences.py [--dry-run]

**Why this exists, and the assumption it corrects.** `constrain_memory_extraction.py` replaces the
built-in `USER_PREFERENCE` strategy with a `CUSTOM` one, because an extraction override can only be
set
at creation. The obvious expectation is that deleting a strategy takes its records with it. It does
not. Measured immediately after the swap:

    strategy TravelPreferences-lDNw1q4RPr : deleted, absent from GetMemory
    its 10 records                        : still present, still stamped with that strategy id

And they are not merely listed — they are still **retrieved**. Asked "what is my hotel nightly cap"
against the namespace, the orphaned policy-as-preference record came back as the top hit at 0.759,
against a `relevance_score` floor of 0.3 and a `top_k` of 5. So the swap fixes what gets *written*
from
here on and changes nothing about what the next turn *reads*. Both halves are needed.

**The rule applied: delete records whose strategy no longer exists.** Not a keyword match on the
text,
which would be guesswork about which of them a reader would call "policy" — and a poor guess,
because
the leak was wider than it first looked. One record was pure policy ("Has a hotel nightly cap of
$250.00 USD, can book hotels up to 4 stars..."), but two more embedded "$250/night (the maximum
allowed
under their corporate travel policy)" inside otherwise perfectly good preferences about hotel
chains.
Orphanhood is the property that is actually decidable: no live strategy will ever consolidate or
update
these again, so they can only go stale.

Nothing depends on them. The travellers' tool-owned preferences live in DynamoDB, seeded by
`backend/seed/travelers.py`; no verification suite asserts a long-term record exists; and genuine
preferences re-extract from ongoing conversations under the constrained strategy.

**Actors are discovered, not listed here.** `ListMemoryRecords` takes an exact namespace — a parent
path matches nothing, verified — so purging needs the set of actor ids. `ListActors` reports the
ones
that actually have memory, which is strictly better than deriving them from the seed: it also covers
travellers created by hand or by an eval run.

Idempotent: a second run finds no orphans and exits clean, so `deploy.sh` can run it every time.
"""

from __future__ import annotations

import argparse
import sys

import boto3
from deployed_refs import refs

# Must match `PREFERENCES_NAMESPACE` in `agent/.../memory.py` and the strategy's namespace template.
NAMESPACE_TEMPLATE = "/travel/preferences/{actorId}/"


def live_strategy_ids(control, memory_id: str) -> set[str]:
    memory = control.get_memory(memoryId=memory_id)["memory"]
    return {s["strategyId"] for s in memory.get("strategies") or []}


def actor_ids(data, memory_id: str) -> list[str]:
    actors, token = [], None
    while True:
        kwargs = {"memoryId": memory_id, "maxResults": 100}
        if token:
            kwargs["nextToken"] = token
        page = data.list_actors(**kwargs)
        actors.extend(a["actorId"] for a in page.get("actorSummaries") or [])
        token = page.get("nextToken")
        if not token:
            return actors


def records_in(data, memory_id: str, namespace: str) -> list[dict]:
    found, token = [], None
    while True:
        kwargs = {"memoryId": memory_id, "namespace": namespace, "maxResults": 100}
        if token:
            kwargs["nextToken"] = token
        page = data.list_memory_records(**kwargs)
        found.extend(page.get("memoryRecordSummaries") or [])
        token = page.get("nextToken")
        if not token:
            return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would be deleted, delete nothing"
    )
    args = parser.parse_args()

    control = boto3.client("bedrock-agentcore-control", region_name=refs.region)
    data = boto3.client("bedrock-agentcore", region_name=refs.region)
    memory_id = refs.memory_id

    live = live_strategy_ids(control, memory_id)
    actors = actor_ids(data, memory_id)
    if not actors:
        print("  no actors have memory yet — nothing to purge")
        return 0

    orphans: list[tuple[str, dict]] = []
    for actor in actors:
        namespace = NAMESPACE_TEMPLATE.replace("{actorId}", actor)
        for record in records_in(data, memory_id, namespace):
            if record.get("memoryStrategyId") not in live:
                orphans.append((namespace, record))

    if not orphans:
        print(f"  no orphaned preference records across {len(actors)} actors")
        return 0

    verb = "would delete" if args.dry_run else "deleting"
    print(f"  {verb} {len(orphans)} orphaned record(s) across {len(actors)} actors")

    deleted, already_gone = [], 0
    for namespace, record in orphans:
        record_id = record["memoryRecordId"]
        print(f"    {record_id}  strategy={record.get('memoryStrategyId')}  ns={namespace}")
        if args.dry_run:
            continue
        try:
            data.delete_memory_record(memoryId=memory_id, memoryRecordId=record_id)
            deleted.append(record_id)
        except data.exceptions.ResourceNotFoundException:
            # **Expected, not an error.** `ListMemoryRecords` serves a lagging index, so a re-run
            # enumerates records that are already gone. Crashing here made the second run look like
            # a
            # failed purge when it was a successful no-op.
            already_gone += 1

    if args.dry_run:
        print("  --dry-run: nothing deleted")
        return 0

    # **Verified by point read, because list and search both lag.** Immediately after a successful
    # delete, `ListMemoryRecords` still returned all ten records and `RetrieveMemoryRecords` still
    # ranked the policy record top — while `GetMemoryRecord` on the same id already reported
    # `ResourceNotFoundException`. Re-listing to confirm would report failure on a purge that
    # worked.
    still_there = []
    for record_id in deleted:
        try:
            data.get_memory_record(memoryId=memory_id, memoryRecordId=record_id)
            still_there.append(record_id)
        except data.exceptions.ResourceNotFoundException:
            pass

    if still_there:
        print(
            f"  {len(still_there)} record(s) still readable after deletion: {still_there}",
            file=sys.stderr,
        )
        return 1

    print(f"  removed {len(deleted)} record(s); {already_gone} already gone")
    print("  NOTE: list and semantic search lag behind deletion — they may still report these")
    return 0


if __name__ == "__main__":
    sys.exit(main())
