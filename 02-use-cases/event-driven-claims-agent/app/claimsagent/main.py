"""
Event-Driven Insurance Claims Agent — Dual-Agent Architecture

Agent 1 (Claims Processor): Evaluates claim, verifies policy, makes ACCEPT/REJECT decision
Agent 2 (Validation Agent): Reviews decision, assigns confidence score, routes accordingly
"""

import os
import re

import base64
import urllib.parse
import urllib.request
import json
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model

app = BedrockAgentCoreApp()
log = app.logger

GATEWAY_URL = os.environ.get("AGENTCORE_GATEWAY_URL", os.environ.get("AGENTCORE_GATEWAY_CLAIMS_GATEWAY_URL", ""))

# Gateway OAuth config (injected by CDK WorkloadIdentity)
GATEWAY_TOKEN_ENDPOINT = os.environ.get("AGENTCORE_GATEWAY_TOKEN_ENDPOINT", "")
GATEWAY_OAUTH_SCOPES = os.environ.get("AGENTCORE_GATEWAY_OAUTH_SCOPES", "")
GATEWAY_CLIENT_ID = os.environ.get("AGENTCORE_GATEWAY_CLIENT_ID", "")
GATEWAY_CLIENT_SECRET = os.environ.get("AGENTCORE_GATEWAY_CLIENT_SECRET", "")

PROCESSOR_PROMPT = """You are a Claims Processor for SecureGuard Insurance.

Your job:
1. Extract claim details from the submission (policy number, description, amount, category)
2. Look up the policy using lookup_policy to verify coverage and status
3. Evaluate the claim against policy terms
4. Make a decision: ACCEPT or REJECT with detailed reasoning

Output your decision in this EXACT format:
DECISION: [ACCEPT or REJECT]
AMOUNT: [dollar amount as integer]
POLICY: [policy_number]
CATEGORY: [claim category]
DESCRIPTION: [brief description]
REASONING: [detailed explanation of why you accepted or rejected]
COVERAGE_CHECK: [whether amount is within limits, policy active, deductible noted]

Rules:
- Use lookup_policy tool to verify the policy exists and is active
- Do NOT call create_claim — that happens later based on validation
- REJECT if policy is inactive, amount exceeds coverage limit, or claim type not covered
- ACCEPT if policy is active, amount within limits, and claim type is covered
- Always note the deductible amount in your reasoning
"""

VALIDATOR_PROMPT = """You are a Claims Validation Agent for SecureGuard Insurance.

You receive a claim decision from the Claims Processor and must validate it independently.

Your job:
1. Review the original claim and the processor's decision
2. Check for errors, inconsistencies, or red flags
3. Assign a CONFIDENCE score from 0-100
4. Decide the routing

Scoring guide:
- 90-100: Clear-cut case, decision is obviously correct, proceed immediately
- 80-89: Decision looks sound, minor questions but acceptable to auto-approve
- 60-79: Some concerns, needs human review before finalizing
- 0-59: Significant issues, must go to human review

Output your validation in this EXACT format:
CONFIDENCE: [0-100]
ROUTING: [AUTO_APPROVE or HUMAN_REVIEW]
VALIDATION_NOTES: [your assessment of the processor's decision]
CONCERNS: [any red flags or issues, or "None" if clean]

Rules:
- If CONFIDENCE >= 80: set ROUTING to AUTO_APPROVE
- If CONFIDENCE < 80: set ROUTING to HUMAN_REVIEW
- Be skeptical of high-value claims (>$25k) — lower confidence unless clearly justified
- Flag if the description is vague or lacks detail
- Flag if the category seems mismatched with the description
"""

_processor = None
_validator = None
_mcp_client = None


def _get_gateway_token():
    """Get OAuth token for gateway access using client_credentials flow."""
    if not GATEWAY_TOKEN_ENDPOINT or not GATEWAY_CLIENT_ID or not GATEWAY_CLIENT_SECRET:
        log.warning("Gateway OAuth credentials not configured, trying without auth")
        return None

    try:
        # Client credentials grant flow to gateway's Cognito M2M pool
        creds = base64.b64encode(f"{GATEWAY_CLIENT_ID}:{GATEWAY_CLIENT_SECRET}".encode()).decode()
        data = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "scope": GATEWAY_OAUTH_SCOPES.replace(",", " "),
            }
        ).encode()

        req = urllib.request.Request(
            GATEWAY_TOKEN_ENDPOINT,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {creds}",
            },
        )

        if not GATEWAY_TOKEN_ENDPOINT.startswith("https://"):
            raise ValueError(f"Only HTTPS URLs are permitted: {GATEWAY_TOKEN_ENDPOINT}")
        with urllib.request.urlopen(req) as resp:  # nosec B310
            token_data = json.loads(resp.read())

        log.info("Successfully obtained gateway access token")
        return token_data["access_token"]
    except Exception as e:
        log.error(f"Failed to get gateway token: {e}")
        return None


def get_mcp_client():
    global _mcp_client
    if _mcp_client is None:

        def _transport():
            token = _get_gateway_token()
            headers = {"Authorization": f"Bearer {token}"} if token else None
            return streamablehttp_client(GATEWAY_URL, headers=headers)

        _mcp_client = MCPClient(_transport)
    return _mcp_client


def get_processor():
    global _processor
    if _processor is None:
        _processor = Agent(
            model=load_model(),
            system_prompt=PROCESSOR_PROMPT,
            tools=[get_mcp_client()],
        )
    return _processor


def get_validator():
    global _validator
    if _validator is None:
        _validator = Agent(
            model=load_model(),
            system_prompt=VALIDATOR_PROMPT,
            tools=[get_mcp_client()],
        )
    return _validator


def parse_confidence(text):
    """Extract confidence score from validator output."""
    match = re.search(r"CONFIDENCE:\s*(\d+)", text)
    if match:
        return int(match.group(1))
    return 50


def parse_decision(text):
    """Extract ACCEPT/REJECT from processor output."""
    # Try multiple patterns (streamed text may have markdown formatting)
    match = re.search(r"DECISION[:\s*\*]*\s*(ACCEPT|REJECT)", text, re.IGNORECASE)
    if not match:
        # Handle markdown bold: **DECISION: ACCEPT** or DECISION: **ACCEPT**
        match = re.search(r"DECISION.*?(ACCEPT|REJECT)", text[:500], re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).upper()
    # Default: if "ACCEPT" appears in first 500 chars, assume accepted
    if "ACCEPT" in text[:500].upper():
        return "ACCEPT"
    return "REJECT"


@app.entrypoint
async def invoke(payload, context):
    """Dual-agent claim processing with confidence-based routing."""
    log.info("Processing claim with dual-agent architecture...")

    prompt = payload.get("prompt", "")
    source = payload.get("source")
    claimant_email = payload.get("claimant_email")

    if source or claimant_email:
        metadata_parts = []
        if source:
            metadata_parts.append(f"Source: {source}")
        if claimant_email:
            metadata_parts.append(f"Claimant email: {claimant_email}")
        prompt = f"[{' | '.join(metadata_parts)}]\n\n{prompt}"

    # --- Phase 1: Claims Processor ---
    yield "## Phase 1: Claims Processing\n\n"

    processor = get_processor()
    processor_response = ""
    stream = processor.stream_async(prompt)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            processor_response += event["data"]
            yield event["data"]

    # --- Phase 2: Validation Agent ---
    yield "\n\n---\n## Phase 2: Validation & Routing\n\n"

    validator_input = f"""Original claim submission:
{prompt}

Claims Processor decision:
{processor_response}

Please validate this decision and assign a confidence score."""

    validator = get_validator()
    validator_response = ""
    stream = validator.stream_async(validator_input)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            validator_response += event["data"]
            yield event["data"]

    # --- Phase 3: Routing ---
    yield "\n\n---\n## Phase 3: Execution\n\n"

    confidence = parse_confidence(validator_response)

    # Route based on validator's explicit ROUTING directive
    if "HUMAN_REVIEW" in validator_response:
        routing = "HUMAN_REVIEW"
    elif "AUTO_APPROVE" in validator_response:
        routing = "AUTO_APPROVE"
    elif confidence >= 80:
        routing = "AUTO_APPROVE"
    else:
        routing = "HUMAN_REVIEW"

    decision = parse_decision(processor_response)

    if decision == "REJECT":
        yield f"**Claim rejected** (confidence: {confidence}/100)\n\n"
        executor = get_processor()
        exec_prompt = f"""The claim has been rejected.
1. Call send_notification to inform the claimant of the rejection with the reasoning.
Claimant email: {claimant_email or "unknown"}
Rejection reasoning from processor:
{processor_response}"""

    elif routing == "AUTO_APPROVE":
        yield f"**Auto-approved** (confidence: {confidence}/100)\n\n"
        executor = get_processor()
        exec_prompt = f"""The claim has been validated and approved. Now execute:
1. Call create_claim with the details from this decision:
{processor_response}
2. Call send_notification to inform the claimant of approval.
Claimant email: {claimant_email or "unknown"}"""

    else:
        yield f"**Routed to human review** (confidence: {confidence}/100)\n\n"
        executor = get_processor()
        exec_prompt = f"""The claim decision needs human review (confidence: {confidence}/100).
1. Call create_claim with the extracted details from:
{processor_response}
2. Call request_human_review explaining why review is needed based on these concerns:
{validator_response}
3. Call send_notification to inform the claimant their claim is under review.
Claimant email: {claimant_email or "unknown"}"""

    stream = executor.stream_async(exec_prompt)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
