"""`search_policy_knowledge` — grounded policy answers, filtered to one tenant.

The third tier of policy. The structured record holds what code computes on (caps, cabin
rules); this holds the prose no schema captures — city exceptions, approval chains, the
reasoning behind a rule. Without the contrast the sample would not need both.

**Isolation is one line, and it is the whole control:**

    filter = {"equals": {"key": "tenant_id", "value": context.tenant_id}}

`context.tenant_id` comes from the interceptor's verified JWT, on a channel the model cannot
reach. Verified against the live index: unfiltered, the same query returns *both* tenants'
documents, and a filter naming the other tenant returns theirs. So the filter is not a
convenience — it is the only thing standing between one tenant and another's policy, and it
must never be derived from a tool argument.

**Retrieve, not RetrieveAndGenerate.** The tool returns passages and citations; the agent's
model does the phrasing. Generating here would mean a second model call the ledger has to
account for, a second place a prompt could be injected, and prose that bypasses the system
prompt's refusal rules.
"""

from __future__ import annotations

import os
from typing import Any

import boto3
from botocore.exceptions import ClientError
from shared.cards import CardType, card
from tools.common import (
    RequestContext,
    ToolError,
    dispatch,
    log_decision,
    log_refusal,
    tool_response,
)

from .schemas import SEARCH_POLICY_KNOWLEDGE

KNOWLEDGE_BASE_ID_VAR = "KNOWLEDGE_BASE_ID"

# Enough passages to cover a rule and its exception, few enough to keep the model's context
# small. Filtered queries routinely return fewer — one tenant's document yielded 1 chunk where
# another gave 3 — so callers must handle short results rather than assume this many.
MAX_RESULTS = 5

# A floor against genuine garbage, and **deliberately not a relevance judge** — because for
# short policy docs it cannot be one. Measured against the live index: a genuinely relevant
# chunk scores ~0.57-0.71, but so does "policy on submarine travel" (0.70, on "policy"+"travel"
# alone) and even "do androids dream of electric sheep?" (0.51). The bands overlap, so no
# threshold separates relevant from irrelevant here.
#
# The lesson, worth stating: **a similarity score is not a relevance gate.** The layer that can
# actually tell whether a passage answers the question is the model, which sees the text — and
# the system prompt already forbids answering from passages that do not. So this floor only
# discards the near-random tail (there is no lexical fallback; HYBRID is unsupported on a direct
# S3 Vectors index), and judgement stays with the model.
MIN_SCORE = 0.35

_client = None


def _runtime():
    """Lazily built so import works without AWS, and reused across invocations."""
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agent-runtime")
    return _client


def _knowledge_base_id() -> str:
    kb_id = os.environ.get(KNOWLEDGE_BASE_ID_VAR)
    if not kb_id:
        raise RuntimeError(f"{KNOWLEDGE_BASE_ID_VAR} is not set — the tool has no index to query")
    return kb_id


def _citation(result: dict[str, Any]) -> dict[str, Any]:
    """A reference the UI can turn into a link, carrying no document content.

    `doc_id` rather than an S3 URI: the frontend resolves it through an app route that
    presigns *and re-authorises on click*, because a copied link outlives the conversation it
    came from. Handing out a presigned URL here would be a bearer token for a policy document
    with no ownership re-check.
    """
    metadata = result.get("metadata") or {}
    return {
        "label": metadata.get("title") or "Travel policy",
        "doc_id": metadata.get("doc_id"),
        "version": metadata.get("version"),
    }


def search_policy_knowledge(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Retrieve policy passages for this tenant only."""
    question = (arguments.get("question") or "").strip()
    if not question:
        raise ToolError("I need a question to search the policy documents for.")

    try:
        response = _runtime().retrieve(
            knowledgeBaseId=_knowledge_base_id(),
            retrievalQuery={"text": question},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": MAX_RESULTS,
                    # The isolation boundary. Built here, from verified context — never from
                    # `arguments`.
                    "filter": {"equals": {"key": "tenant_id", "value": context.tenant_id}},
                }
            },
        )
    except ClientError as error:
        # A retrieval failure must not become an invented answer.
        log_refusal("knowledge base retrieval failed", code=error.response["Error"]["Code"])
        return tool_response(
            message="I couldn't search the policy documents just now, so I'd rather not guess.",
            provenance={"source": "policy_knowledge", "tenant_id": context.tenant_id},
        )

    results = response.get("retrievalResults") or []

    # Defence in depth: the filter already scoped this, but a passage whose metadata does not
    # match the caller's tenant is dropped rather than trusted. Cheap, and the failure it
    # guards against is the worst one available here.
    scoped = [r for r in results if (r.get("metadata") or {}).get("tenant_id") == context.tenant_id]
    if len(scoped) != len(results):
        log_refusal(
            "dropped retrieved passages whose tenant metadata did not match the caller",
            returned=len(results),
            kept=len(scoped),
        )

    relevant = [r for r in scoped if (r.get("score") or 0) >= MIN_SCORE]

    log_decision(
        "searched policy knowledge",
        returned=len(results),
        kept_after_tenant_check=len(scoped),
        kept_after_score_filter=len(relevant),
        top_score=round(max((r.get("score") or 0) for r in scoped), 3) if scoped else None,
        doc_ids=sorted(
            {(r.get("metadata") or {}).get("doc_id") for r in relevant if r.get("metadata")}
        ),
    )

    if not relevant:
        # Distinct from an error: the documents were searched and had nothing to say.
        return tool_response(
            message=(
                "I couldn't find anything in your company's travel policy documents about "
                "that. It may not be covered in writing — your travel team would know."
            ),
            provenance={"source": "policy_knowledge", "tenant_id": context.tenant_id},
        )

    passages = [
        {"text": (r.get("content") or {}).get("text", ""), "citation": _citation(r)}
        for r in relevant
    ]

    return tool_response(
        # **A card per document, not per passage.** Several passages routinely come from one
        # document — a rule and its exception both live in the same policy file — and a tile per
        # passage would repeat the same "open the source" link that many times. Deduplicated by
        # `doc_id`, in the order the passages arrived, so the first (most relevant) mention decides
        # the position. A passage whose metadata carried no `doc_id` gets no card: the citation
        # exists for narration either way through `facts.passages`, but a card with nothing to
        # presign would be a button that 404s on click.
        cards=[
            card(CardType.CITATION, f"citation-{p['citation']['doc_id']}", p["citation"])
            for p in _deduplicated_citations(passages)
        ],
        facts={"passages": passages},
        provenance={
            "source": "policy_knowledge",
            "tenant_id": context.tenant_id,
            "passages_returned": len(passages),
            # Stated so the model does not read a short result as a complete answer.
            "note": "quoted from your company's policy documents; not an exhaustive search",
        },
    )


def _deduplicated_citations(passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One passage per cited document, first occurrence wins, `doc_id`-less passages dropped."""
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    for passage in passages:
        doc_id = passage["citation"].get("doc_id")
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        kept.append(passage)
    return kept


TOOLS = {SEARCH_POLICY_KNOWLEDGE: search_policy_knowledge}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Gateway target entry point. All the shared work lives in `dispatch`."""
    return dispatch(event, context, TOOLS)
