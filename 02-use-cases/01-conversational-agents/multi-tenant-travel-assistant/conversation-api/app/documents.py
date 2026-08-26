"""Policy-document links: presigned on click, after re-authorising.

**Retrieval returns a `doc_id`, never a URL.** `search_policy_knowledge` cites documents by id
precisely so that signing can happen here, at click time, with the caller's own session in hand.

**Why that ordering is the whole point.** A presigned URL handed out at retrieval time is a bearer
token for a policy document: it works for anyone holding the link, for as long as the signature
lasts, with no further check. It outlives the conversation it came from, survives being pasted into
a ticket, and carries no trace of who used it. Signing on click means the ownership check happens
*at the moment of access* — the version of the question that actually matters.

**The re-check is not the retrieval filter again.** Retrieval was filtered by the tenant the
*interceptor* verified for that tool call. This is a different request, possibly hours later, from a
browser session. So the tenant is re-read from the session and the document's own tenant is
re-derived from the registry — a valid session for another tenant is refused even though the
`doc_id` is real and the session is genuine. That is the case the test asserts.
"""

from __future__ import annotations

import os

import boto3
from botocore.config import Config

BUCKET_VAR = "POLICY_DOCS_BUCKET"

# Long enough to open a document, short enough that a copied link is stale before it can be shared.
# The link is a credential; its lifetime is the blast radius.
LINK_SECONDS = 300

# doc_id -> (tenant, S3 key). The **authoritative** owner of each document, and deliberately not
# taken from the request: a caller-supplied key would let a valid session name any object in the
# bucket, which is the whole vulnerability this route exists to avoid.
#
# A table would be the production shape. Here the documents are seeded fixtures and the registry
# would be a table with two rows — so it mirrors `backend/seed/documents/` instead. The tenant
# prefix in the key matches the bucket layout, which makes the isolation model visible in the
# console as well as in code.
DOCUMENTS: dict[str, tuple[str, str]] = {
    "pol_globex_2026": ("globex", "policy/globex/globex-travel-policy-2026.md"),
    "pol_initech_2026": ("initech", "policy/initech/initech-travel-policy-2026.md"),
}

_s3 = None


def _client():
    """Lazily built so import works without AWS, and reused across invocations.

    SigV4 explicitly: the default signature version for presigning varies by region, and a v2
    signature is rejected outright by buckets in newer regions — a failure that reads as a broken
    permission rather than a signing-version mismatch.
    """
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
    return _s3


class DocumentRefused(PermissionError):
    """The caller may not have this document. Never distinguishes 'wrong tenant' from 'no such id'.

    Deliberately one error for both: telling a caller that `pol_initech_2026` exists but is not
    theirs confirms another tenant's document id, which is a small leak in a system whose whole
    claim is that tenants are invisible to each other.
    """


def presigned_url(doc_id: str, tenant_id: str | None) -> str:
    """A short-lived link to `doc_id`, if `tenant_id` owns it.

    Raises `DocumentRefused` otherwise — including for an unknown id, so the two are
    indistinguishable from outside.
    """
    entry = DOCUMENTS.get(doc_id)
    if entry is None or not tenant_id or entry[0] != tenant_id:
        raise DocumentRefused(f"document {doc_id} is not available to this session")

    bucket = os.environ.get(BUCKET_VAR)
    if not bucket:
        raise RuntimeError(f"{BUCKET_VAR} is not set — no bucket to sign against")

    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": entry[1]},
        ExpiresIn=LINK_SECONDS,
    )
