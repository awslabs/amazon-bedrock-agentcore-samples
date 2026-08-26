"""Activate the cost allocation tags. Run once, then again after ~24h if keys are still pending.

    AWS_REGION=us-east-1 uv run python scripts/activate_cost_tags.py

**Tagging resources does nothing for cost reporting on its own.** A tag becomes a billing dimension
only once its key is *activated* under Billing → Cost allocation tags — and until then Cost Explorer
cannot group or filter by it at all.

Two properties make this worth a script rather than a note in a runbook:

1. **Activation is not retroactive.** Spend before a key is active is permanently unattributable.
   There is no backfill, so the cost of forgetting grows every day.
2. **A key cannot be activated until AWS has seen it in billing data**, which lags a deploy by up to
   24 hours. `UpdateCostAllocationTagsStatus` answers `Tag keys not found` before then — measured,
   not
   assumed. So the first run after adding a tag usually leaves keys pending and has to be repeated.

Idempotent: already-active keys are reported and skipped, so running it on a schedule is safe.
"""

from __future__ import annotations

import os
import sys

import boto3

# The vocabulary from `infra/bin/infra.ts` and `agentcore.json`. `component` is the one that carries
# the weight — it is the only key whose value *varies*, so it is what turns "the sample costs $X"
# into
# "retrieval is 60% of the bill".
#
# `tenant` is deliberately absent: every resource here is pooled, so a tenant tag would be false on
# most of them. Per-tenant cost comes from the application ledger, not from a resource tag.
KEYS = ["project", "component", "environment", "sample"]

REGION = os.environ.get("AWS_REGION", "us-east-1")


def main() -> int:
    # Cost Explorer is a global service with a us-east-1 endpoint; the region is passed for
    # consistency with the rest of the scripts rather than because it varies.
    client = boto3.client("ce", region_name=REGION)

    known = {
        tag["TagKey"]: tag["Status"]
        for tag in client.list_cost_allocation_tags()["CostAllocationTags"]
    }

    # A key AWS has never seen in billing data cannot be activated, and asking anyway fails the
    # whole
    # call rather than the individual key — so unknown keys are filtered out first.
    pending = [key for key in KEYS if key not in known]
    active = [key for key in KEYS if known.get(key) == "Active"]
    to_activate = [key for key in KEYS if key in known and known[key] != "Active"]

    for key in active:
        print(f"  already active   {key}")

    if to_activate:
        client.update_cost_allocation_tags_status(
            CostAllocationTagsStatus=[{"TagKey": key, "Status": "Active"} for key in to_activate]
        )
        for key in to_activate:
            print(f"  ACTIVATED        {key}")

    for key in pending:
        print(f"  not yet visible  {key} — AWS has not seen it in billing data")

    if pending:
        print(
            "\nRe-run in ~24 hours for the pending keys. Until each is active, spend carrying that "
            "tag is unattributable and cannot be backfilled."
        )
    return 1 if pending else 0


if __name__ == "__main__":
    sys.exit(main())
