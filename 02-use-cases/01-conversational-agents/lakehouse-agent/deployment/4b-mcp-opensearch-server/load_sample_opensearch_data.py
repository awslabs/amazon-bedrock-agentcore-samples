#!/usr/bin/env python3
"""
Load Sample Claim-Note Documents into OpenSearch Serverless

This script:
1. Reads the AOSS collection endpoint from SSM.
2. Idempotent-creates the `claim-notes` index with the spec mapping
   (owner_user_sub keyword, note_text text, claim_id/note_type keyword,
   created_at date).
3. Discovers test-user subs from SSM (okta-user-*-sub keys provisioned by
   notebook 07) and bulk-loads DISJOINT free-text claim-note documents
   per user.

Data distinctness (per design §4):
- Notes are FREE-TEXT (adjuster narratives, damage descriptions, call
  summaries), qualitatively different from the structured claims records
  served by the Claims_MCP_Server (which carry claim_id, claim_status,
  claim_amount, etc.). The agent's tool choice should be obvious from the
  question shape: note-search => opensearch/* (this server); structured
  claims/amounts/status => claims/* (Claims_MCP_Server).
- note_type ∈ {adjuster_note, call_summary, damage_assessment}.
- Per-user content is disjoint: each user gets a unique 3-document slice
  from a pool of templates indexed by the user's position in the sorted
  sub list. User A's claim_ids cannot appear under user B's owner_user_sub
  filter, so the notebook 07 isolation invariant is testable by simple
  set-difference.

Usage:
    python load_sample_opensearch_data.py
"""

import boto3
import json
import sys
from datetime import datetime, timezone
from typing import List, Dict

from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from aws_requests_auth.aws_auth import AWSRequestsAuth


CLAIM_NOTES_INDEX = "claim-notes"
SSM_PREFIX = "/app/lakehouse-agent/"


# Index mapping. Field types chosen to support the
# query shape in opensearch_tools.search_claim_notes:
#   - owner_user_sub: keyword (exact-match term filter for RLS)
#   - note_text:      text    (full-text match query)
#   - claim_id:       keyword (exact-match identifier; not searched as text)
#   - note_type:      keyword (exact-match facet)
#   - created_at:     date    (range queries / sorting)
INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "claim_id": {"type": "keyword"},
            "owner_user_sub": {"type": "keyword"},
            "note_text": {"type": "text"},
            "note_type": {"type": "keyword"},
            "created_at": {"type": "date"},
        }
    }
}


# Pool of disjoint free-text note templates. Each template is a 3-tuple of
# (note_type, claim_id_suffix, note_text). The N-th user (sorted by sub)
# claims templates [3N : 3N+3] — guarantees per-user disjoint claim_ids and
# disjoint narrative content.
#
# All notes describe insurance-claim *narratives* with no structured amount/
# status fields in the payload; the agent should pick this tool when the
# user asks about damage descriptions, adjuster commentary, call history,
# etc., and pick the claims/* tools when the user asks about totals,
# pending counts, or specific claim_id lookups.
NOTE_TEMPLATES = [
    # User 0 slice
    (
        "adjuster_note",
        "AN-001",
        "Field adjuster visited the property on the morning after the storm. "
        "Observed water damage to the kitchen ceiling and ongoing seepage from a "
        "displaced roof shingle. Recommended emergency tarp and follow-up "
        "structural inspection. Homeowner cooperative; documentation thorough.",
    ),
    (
        "call_summary",
        "CS-001",
        "Inbound call from policyholder reporting that contractor had not yet "
        "scheduled the roof repair. Confirmed claim is in adjuster review and "
        "noted that the policyholder should expect a callback within two "
        "business days. Tone: anxious but constructive.",
    ),
    (
        "damage_assessment",
        "DA-001",
        "Initial damage assessment: kitchen ceiling drywall saturated across "
        "approximately twelve square feet, cabinetry warping along the upper "
        "left run, hardwood flooring shows cupping under the affected zone. "
        "Mold mitigation flagged as elevated risk; air-quality test recommended.",
    ),
    # User 1 slice
    (
        "adjuster_note",
        "AN-002",
        "Inspected vehicle at the body-shop after the rear-end collision. "
        "Bumper cover cracked, tailgate misaligned by a noticeable margin, "
        "rear quarter panel showing crease damage. Frame appeared straight on "
        "visual check; pre-repair scan recommended before any disassembly.",
    ),
    (
        "call_summary",
        "CS-002",
        "Policyholder called requesting status on the rental-vehicle "
        "extension. Confirmed coverage is in place through the end of the "
        "month and walked them through the body-shop pickup process. They "
        "asked about pursuing the at-fault party's carrier; explained "
        "subrogation timing.",
    ),
    (
        "damage_assessment",
        "DA-002",
        "Photographic survey shows clearly observable damage concentrated at "
        "the rear of the vehicle. Tail lamp housings intact but cracked. No "
        "evidence of airbag deployment. Mileage logged and matches the "
        "policyholder's stated odometer reading at the time of loss.",
    ),
    # User 2 slice (extra capacity if a third test user is provisioned)
    (
        "adjuster_note",
        "AN-003",
        "Walked the property line with the homeowner to identify the source "
        "of basement intrusion. Drainage from the neighboring lot appears to "
        "feed through a low spot near the egress window. Recommend grading "
        "review and a moisture log over the next two weeks before final "
        "settlement discussion.",
    ),
    (
        "call_summary",
        "CS-003",
        "Policyholder followed up regarding their personal-property inventory "
        "spreadsheet. Confirmed receipt and noted three items still need "
        "supporting receipts. Discussed the depreciation schedule and what "
        "categories are subject to actual-cash-value versus replacement-cost "
        "treatment.",
    ),
    (
        "damage_assessment",
        "DA-003",
        "Basement assessment shows water staining along the north wall up to "
        "approximately eight inches above slab grade. Carpet padding is "
        "saturated and not salvageable. HVAC return duct in the affected room "
        "shows rust at the base; recommend professional duct cleaning prior "
        "to drywall close-up.",
    ),
    # User 3 slice (additional headroom)
    (
        "adjuster_note",
        "AN-004",
        "Reviewed the auto loss photos remotely and requested additional "
        "shots of the underside of the front bumper and the radiator support. "
        "Initial impression suggests the impact was lower than the photos "
        "first showed; underlying components likely affected.",
    ),
    (
        "call_summary",
        "CS-004",
        "Policyholder asked whether the deductible would be waived given the "
        "other driver's admission of fault on the police report. Walked "
        "through the carrier's recovery process and explained that the "
        "deductible is reimbursed on successful subrogation, not waived "
        "up-front.",
    ),
    (
        "damage_assessment",
        "DA-004",
        "Front-end damage shows hood crumple, headlight assembly compromised "
        "on the driver side, and visible coolant residue under the front "
        "cross-member. Recommend full tear-down inspection at an authorized "
        "facility before parts ordering.",
    ),
]


def get_aoss_client(region: str, collection_endpoint: str) -> OpenSearch:
    """Build a SigV4-signed OpenSearch client against the AOSS collection."""
    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError("No AWS credentials available for OpenSearch SigV4 signing")

    endpoint_host = collection_endpoint.replace("https://", "").replace("http://", "")

    auth = AWSRequestsAuth(
        aws_access_key=credentials.access_key,
        aws_secret_access_key=credentials.secret_key,
        aws_token=credentials.token,
        aws_host=endpoint_host,
        aws_region=region,
        aws_service="aoss",
    )

    return OpenSearch(
        hosts=[{"host": endpoint_host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )


def ensure_index(client: OpenSearch) -> None:
    """Idempotent: check-exists then create."""
    print(f"\n📚 Ensuring index '{CLAIM_NOTES_INDEX}' exists...")
    try:
        if client.indices.exists(index=CLAIM_NOTES_INDEX):
            print("   ⏭️  Index already exists; skipping create")
            # Note: We do not validate the existing mapping shape here. R8.5
            # / design §12 #3 ("idempotent IaC pattern") suggests fail-loud
            # on drift, but the original demo's data-load scripts do not
            # mapping-diff either. Tutorial-reader cleanup path: run
            # cleanup_runtime.py + re-deploy the AOSS collection (D.2 task
            # 9.6) to drop and recreate the index.
            return
    except Exception as e:
        print(f"   ⚠️  exists() probe failed: {e}; attempting create anyway")

    try:
        client.indices.create(index=CLAIM_NOTES_INDEX, body=INDEX_MAPPING)
        print(f"   ✅ Index created with mapping: {json.dumps(INDEX_MAPPING['mappings']['properties'])}")
    except Exception as e:
        print(f"   ❌ Failed to create index: {e}")
        raise


def discover_user_subs(ssm) -> List[Dict[str, str]]:
    """
    Discover test-user sub identifiers from SSM.

    Reads parameters under /app/lakehouse-agent/okta-user-*-sub. Returns
    a sorted list of {label, sub} dicts where label is the SSM key suffix
    (e.g., 'policyholder001') extracted from `okta-user-<label>-sub`. Sort
    order is alphabetical by label so the per-user template slicing is
    deterministic across runs.
    """
    print(f"\n🔎 Discovering test-user subs in SSM under '{SSM_PREFIX}okta-user-*-sub'...")

    paginator = ssm.get_paginator("get_parameters_by_path")
    found = []
    for page in paginator.paginate(Path=SSM_PREFIX, Recursive=False):
        for p in page.get("Parameters", []):
            name = p["Name"]
            # Match /app/lakehouse-agent/okta-user-<label>-sub
            if not name.startswith(f"{SSM_PREFIX}okta-user-"):
                continue
            if not name.endswith("-sub"):
                continue
            label = name[len(f"{SSM_PREFIX}okta-user-") : -len("-sub")]
            found.append({"label": label, "sub": p["Value"]})

    found.sort(key=lambda x: x["label"])

    if not found:
        print("   ❌ No okta-user-*-sub parameters found in SSM")
        print("      Notebook 07 provisions test users and writes their subs to SSM. Run that cell first.")
        return []

    print(f"   ✅ Discovered {len(found)} test user(s):")
    for u in found:
        print(f"      - okta-user-{u['label']}-sub = {u['sub']}")
    return found


def build_documents_for_user(user_index: int, user_sub: str, user_label: str) -> List[Dict]:
    """
    Build the 3 disjoint note documents for the N-th user (sorted by label).

    Slice the NOTE_TEMPLATES pool at [3*user_index : 3*user_index + 3]. Each
    document carries a per-user-disambiguated claim_id (suffix prefixed with
    the user label) so even claim_id is disjoint across users.
    """
    slice_start = 3 * user_index
    slice_end = slice_start + 3
    if slice_end > len(NOTE_TEMPLATES):
        raise RuntimeError(
            f"NOTE_TEMPLATES pool exhausted: user_index={user_index} requires "
            f"slice [{slice_start}:{slice_end}] but pool has "
            f"{len(NOTE_TEMPLATES)} templates. Add more templates."
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    docs = []
    for note_type, claim_id_suffix, note_text in NOTE_TEMPLATES[slice_start:slice_end]:
        docs.append(
            {
                "claim_id": f"CLM-{user_label}-{claim_id_suffix}",
                "owner_user_sub": user_sub,
                "note_text": note_text,
                "note_type": note_type,
                "created_at": now_iso,
            }
        )
    return docs


def bulk_load(client: OpenSearch, docs: List[Dict]) -> None:
    """Bulk-index documents into the claim-notes index."""
    if not docs:
        print("   ⏭️  No documents to load")
        return

    print(f"\n📥 Bulk-loading {len(docs)} document(s)...")

    # Deterministic _id = claim_id (globally unique: CLM-<user_label>-<suffix>)
    # turns the bulk "index" op into an idempotent UPSERT. Re-running the
    # seeder overwrites the same documents in place instead of appending
    # duplicates under fresh auto-generated ids — so notebook 07's exact
    # per-user note counts stay stable across re-seeds. Custom document _id is
    # supported on SEARCH-type AOSS collections (PUT <index>/_doc/<id> falls
    # under the aoss:WriteDocument grant the loader principal already has), so
    # this needs no additional data-access permission.
    actions = [
        {
            "_op_type": "index",
            "_index": CLAIM_NOTES_INDEX,
            "_id": doc["claim_id"],
            "_source": doc,
        }
        for doc in docs
    ]

    # AOSS does not support refresh on bulk; let it propagate naturally.
    try:
        success, errors = helpers.bulk(client, actions, raise_on_error=False, raise_on_exception=False)
        print(f"   ✅ Indexed {success} document(s)")
        if errors:
            print(f"   ⚠️  {len(errors)} error(s) reported by bulk helper:")
            for err in errors[:5]:
                print(f"      {err}")
    except Exception as e:
        print(f"   ❌ Bulk load failed: {e}")
        raise


def main():
    print("=" * 70)
    print("Load Sample Claim-Note Documents into OpenSearch Serverless")
    print("=" * 70)

    session = boto3.Session()
    region = session.region_name
    if not region:
        print("❌ Could not detect AWS region from boto3 session")
        sys.exit(1)

    ssm = boto3.client("ssm", region_name=region)

    print(f"\n📋 Region: {region}")

    # Read the AOSS collection endpoint from SSM
    print("\n🔍 Loading AOSS collection endpoint from SSM...")
    try:
        endpoint = ssm.get_parameter(Name=f"{SSM_PREFIX}opensearch-collection-endpoint")["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        print(f"❌ SSM parameter {SSM_PREFIX}opensearch-collection-endpoint not found")
        print("   Run deployment/5b-obo-gateway-setup/01_deploy_opensearch_collection.py first")
        sys.exit(1)

    print(f"   ✅ Collection endpoint: {endpoint}")

    # Build AOSS client
    client = get_aoss_client(region, endpoint)

    # Idempotent index create
    ensure_index(client)

    # Discover test-user subs
    users = discover_user_subs(ssm)
    if not users:
        sys.exit(1)

    # Build per-user disjoint document slices
    all_docs = []
    for i, user in enumerate(users):
        try:
            docs = build_documents_for_user(i, user["sub"], user["label"])
        except RuntimeError as e:
            print(f"\n❌ {e}")
            sys.exit(1)
        print(f"\n📄 User {i} ({user['label']}, sub={user['sub']}): {len(docs)} document(s)")
        for d in docs:
            print(f"   - claim_id={d['claim_id']}, note_type={d['note_type']}")
        all_docs.extend(docs)

    # Bulk load
    bulk_load(client, all_docs)

    print("\n" + "=" * 70)
    print("Sample-data load complete!")
    print("=" * 70)
    print(f"\n✅ Loaded {len(all_docs)} document(s) across {len(users)} user(s)")
    print(f"   Index: {CLAIM_NOTES_INDEX}")
    print("\n📋 Next Steps:")
    print("   1. Verify per-user RLS via search_claim_notes (notebook 07)")
    print("   2. Confirm disjointness: user A's claim_ids never appear under user B's filter")


if __name__ == "__main__":
    main()
