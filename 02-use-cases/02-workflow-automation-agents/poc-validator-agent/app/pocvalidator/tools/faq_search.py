"""Shared FAQ search — AgentCore Knowledge Base (FMKB), optional Phase.

Recurring review findings (HIPAA/VPC, RDS storage class, Multi-AZ, WAF,
CloudTrail, Cognito MFA, retention, IMDSv2 — see the source docs under
`agentcore/faq/`) don't fit AgentCore Memory's per-actor namespace model:
Memory namespaces are always `pocvalidator/{actorId}/...`, scoped to one
reviewer's own history, and there is no cross-actor namespace to accumulate
a shared answer set into. A Knowledge Base is the right primitive for
"everyone should see the same answer to a recurring question" — it's a
single, deliberately-curated store, not a per-user memory. See
docs/decisions/0011.

Uses plain vector search (`bedrock-agent-runtime:Retrieve`), not
`RetrieveAndGenerate`. Retrieve only embeds the query and searches — no
generation call — so this path does not depend on this account's standing
Bedrock Marketplace model-access restriction, unlike SOW grading, diagram
vision, evaluators and the what-if pricing tool's code-authoring step.
Formatting the results into a readable answer stays deterministic Python,
matching this project's core principle: a model decides what to look up,
never what the answer says.
"""

from __future__ import annotations

import boto3
from config import FAQ_KNOWLEDGE_BASE_ID, REGION

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agent-runtime", region_name=REGION)
    return _client


def search_faq(query: str, top_k: int = 3) -> dict:
    """Vector-search the FAQ knowledge base. Always returns a dict with a
    `status` key (`ok` or `unavailable`) — never raises.
    """
    if not FAQ_KNOWLEDGE_BASE_ID:
        return {
            "status": "unavailable",
            "query": query,
            "reason": "FAQ_KNOWLEDGE_BASE_ID not configured.",
        }

    try:
        response = _get_client().retrieve(
            knowledgeBaseId=FAQ_KNOWLEDGE_BASE_ID,
            retrievalQuery={"text": query},
            # AgentCore-managed knowledge bases (created via `agentcore add
            # knowledge-base`) use a fully-managed vector store and reject
            # vectorSearchConfiguration — confirmed directly against the
            # deployed KB, which raised ValidationException on that key and
            # named managedSearchConfiguration as the required one instead.
            retrievalConfiguration={
                "managedSearchConfiguration": {"numberOfResults": top_k}
            },
        )
    except Exception as exc:  # noqa: BLE001 — KB may be unavailable/unauthorized in this account
        return {
            "status": "unavailable",
            "query": query,
            "reason": f"Retrieve call failed: {exc}",
        }

    results = []
    for item in response.get("retrievalResults", []):
        content = item.get("content", {}) or {}
        location = item.get("location", {}) or {}
        s3_uri = (location.get("s3Location") or {}).get("uri", "")
        results.append(
            {
                "text": content.get("text", ""),
                "score": item.get("score"),
                "source": s3_uri,
            }
        )

    return {"status": "ok", "query": query, "results": results}
