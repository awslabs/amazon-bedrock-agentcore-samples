"""Load the fixtures into a deployed environment.

Run once after `cdk deploy`. Idempotent — every write is a `put_item` keyed on
tenant and id, so re-running overwrites rather than duplicating.

    uv run python -m seed.load --table-prefix multi-tenant-travel \\
        --bucket "$(aws cloudformation describe-stacks --stack-name multi-tenant-travel \\
            --query "Stacks[0].Outputs[?contains(OutputKey,'PolicyDocsBucketName')].OutputValue" \\
            --output text)"

The bucket name carries the account id, so it is read from the stack that made it rather than
written down. `./deploy.sh --seed` does this for you.

Deliberately a script rather than a CloudFormation custom resource: seeding is a
data operation, and coupling it to stack lifecycle means a failed seed rolls back
infrastructure that was otherwise fine.
"""

import argparse
import sys

import boto3

from app.dynamo_repository import DynamoRepository

from . import seed
from .documents import DOCUMENTS


def upload_policy_documents(bucket: str) -> int:
    """Upload each policy doc **and its `.metadata.json` sidecar**.

    The sidecar is what carries `tenant_id` into the vector index, and it is the only
    mechanism Bedrock reads: S3 *object* metadata is silently ignored during ingestion. A
    knowledge base built without sidecars indexes documents with no `tenant_id`, so every
    filtered query returns nothing — which looks like a broken filter rather than absent
    metadata, and is a slow thing to diagnose.

    Object metadata is still set, purely so the values are visible in the console next to
    the object. Retrieval does not use it.
    """
    s3 = boto3.client("s3")
    for doc in DOCUMENTS:
        s3.put_object(
            Bucket=bucket,
            Key=doc.s3_key(),
            Body=doc.read().encode(),
            ContentType="text/markdown",
            Metadata=doc.kb_metadata(),
        )
        s3.put_object(
            Bucket=bucket,
            Key=doc.metadata_key(),
            Body=doc.metadata_sidecar().encode(),
            ContentType="application/json",
        )
        print(f"  uploaded s3://{bucket}/{doc.s3_key()} (+ sidecar)")
    return len(DOCUMENTS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table-prefix", required=True, help="e.g. multi-tenant-travel-Data")
    parser.add_argument("--bucket", help="Policy-docs bucket; skipped if omitted")
    args = parser.parse_args()

    repo = DynamoRepository(table_prefix=args.table_prefix)

    print(f"Seeding tables with prefix {args.table_prefix!r}...")
    seed(repo)

    # Read back rather than trusting the writes — a silent partial seed would
    # surface later as a confusing empty result from the API.
    tenants = ["globex", "initech"]
    for tenant_id in tenants:
        config = repo.tenant_config(tenant_id)
        travelers = repo.travelers(tenant_id)
        trips = repo.trips(tenant_id)
        policies = repo.policies(tenant_id)
        print(
            f"  {config.display_name}: {len(travelers)} travelers, "
            f"{len(trips)} trips, {len(policies)} policies"
        )

    if args.bucket:
        print(f"Uploading policy documents to {args.bucket}...")
        upload_policy_documents(args.bucket)

    print("Seed complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
