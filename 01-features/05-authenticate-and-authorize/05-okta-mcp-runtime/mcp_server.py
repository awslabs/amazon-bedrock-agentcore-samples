"""
FastMCP server that wraps an Amazon Bedrock Knowledge Base.

Exposes a single read-only tool (`query_knowledge_base`) that accepts a
natural-language question, runs semantic search via Bedrock's
RetrieveAndGenerate API, and returns the answer with source citations.

Environment variables (set by the AgentCore Runtime):
    KNOWLEDGE_BASE_ID   - Bedrock Knowledge Base ID
    KB_REGION           - Region where the Knowledge Base lives (defaults to AWS_REGION)
    BEDROCK_MODEL_ARN   - Model ARN or inference-profile ARN for generation
"""

import os
from functools import lru_cache
from typing import Annotated

import boto3
from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP(
    "Knowledge Base MCP",
    host="0.0.0.0",
    stateless_http=True,
    json_response=True,
)


def _bedrock_config() -> tuple[str, str, str]:
    """Return (knowledge_base_id, region, model_arn) from environment."""
    kb_id = os.environ.get("KNOWLEDGE_BASE_ID")
    if not kb_id:
        raise RuntimeError("KNOWLEDGE_BASE_ID environment variable is not set.")
    region = os.environ.get("KB_REGION") or os.environ.get("AWS_REGION", "us-east-1")
    model_arn = os.environ.get("BEDROCK_MODEL_ARN")
    if not model_arn:
        raise RuntimeError("BEDROCK_MODEL_ARN environment variable is not set.")
    return kb_id, region, model_arn


@lru_cache(maxsize=1)
def _bedrock_client_and_config() -> tuple[object, str, str]:
    """Resolve config and build the boto3 client once per process."""
    kb_id, region, model_arn = _bedrock_config()
    client = boto3.client("bedrock-agent-runtime", region_name=region)
    return client, kb_id, model_arn


def _citation_source(location: dict) -> str:
    """Best-effort URL/URI for a retrieved reference."""
    return (
        location.get("s3Location", {}).get("uri")
        or location.get("confluenceLocation", {}).get("url")
        or location.get("webLocation", {}).get("url")
        or location.get("salesforceLocation", {}).get("url")
        or location.get("sharePointLocation", {}).get("url")
        or f"{location.get('type', 'unknown')}:<no-url>"
    )


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def query_knowledge_base(
    query: Annotated[
        str,
        Field(description="Natural-language question to ask the knowledge base"),
    ],
) -> dict:
    """Query a Bedrock Knowledge Base using semantic search.

    Sends the question to an Amazon Bedrock Knowledge Base and returns a
    generated answer along with source citations.
    """
    client, kb_id, model_arn = _bedrock_client_and_config()

    response = client.retrieve_and_generate(
        input={"text": query},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn": model_arn,
            },
        },
    )

    answer = response.get("output", {}).get("text", "")

    citations = []
    for citation in response.get("citations", []):
        for ref in citation.get("retrievedReferences", []):
            content = ref.get("content", {}).get("text", "")
            citations.append(
                {
                    "text": content,
                    "source": _citation_source(ref.get("location", {})),
                }
            )

    return {"answer": answer, "citations": citations}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
