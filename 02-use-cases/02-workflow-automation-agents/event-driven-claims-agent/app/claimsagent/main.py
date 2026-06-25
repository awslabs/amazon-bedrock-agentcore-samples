"""
Event-Driven Insurance Claims Agent — Dual-Agent Architecture

Agent 1 (Claims Processor): Evaluates claim, verifies policy, makes ACCEPT/REJECT decision
Agent 2 (Validation Agent): Reviews decision, assigns confidence score, routes accordingly
"""

import base64
import json
import urllib.parse
import urllib.request
import uuid

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from config import (
    GATEWAY_CLIENT_ID,
    GATEWAY_CLIENT_SECRET,
    GATEWAY_OAUTH_SCOPES,
    GATEWAY_TOKEN_ENDPOINT,
    GATEWAY_URL,
)
from mcp.client.streamable_http import streamablehttp_client
from memory.session import get_memory_session_manager
from model.load import load_model
from parsing import parse_confidence, parse_decision
from strands import Agent
from strands.tools.mcp import MCPClient
from tools.structured_output import (
    get_last_decision,
    get_last_validation,
    reset_state,
    submit_decision,
    submit_validation,
)

app = BedrockAgentCoreApp()
log = app.logger

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
- After making your decision, you MUST call the submit_decision tool with all fields filled in.
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
- After completing your validation, you MUST call the submit_validation tool with all fields.
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


def get_processor(session_manager=None):
    """Create or return the Claims Processor agent.

    When a session_manager is provided, a fresh agent is created for that session
    (memory is per-invocation). Without memory, the cached singleton is reused.
    """
    global _processor
    if session_manager is not None:
        # Per-invocation agent with memory — enables cross-session recall
        return Agent(
            model=load_model(),
            system_prompt=PROCESSOR_PROMPT,
            tools=[get_mcp_client(), submit_decision],
            session_manager=session_manager,
        )
    if _processor is None:
        _processor = Agent(
            model=load_model(),
            system_prompt=PROCESSOR_PROMPT,
            tools=[get_mcp_client(), submit_decision],
        )
    return _processor


def get_validator():
    global _validator
    if _validator is None:
        _validator = Agent(
            model=load_model(),
            system_prompt=VALIDATOR_PROMPT,
            tools=[get_mcp_client(), submit_validation],
        )
    return _validator


@app.entrypoint
async def invoke(payload, context):
    """Dual-agent claim processing with confidence-based routing."""
    log.info("Processing claim with dual-agent architecture...")

    # --- PAYLOAD PARSING (handles agentcore dev wrapping) ---
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {"prompt": payload}

    # Unwrap nested JSON from agentcore dev's {"prompt": "<json>"} wrapper
    if "prompt" in payload and "policy_number" not in payload:
        prompt_value = payload["prompt"]
        if isinstance(prompt_value, str):
            try:
                parsed = json.loads(prompt_value)
                if isinstance(parsed, dict):
                    payload = parsed
            except (json.JSONDecodeError, TypeError):
                pass  # Natural language prompt, keep as-is

    prompt = payload.get("prompt", "")
    source = payload.get("source")
    claimant_email = payload.get("claimant_email")

    # Reset structured output state between invocations
    reset_state()

    # Extract actor/session identifiers for memory
    # Use claimant_email as actor_id for cross-session recall of repeat claimants
    actor_id = claimant_email or payload.get("user_id", "anonymous")
    session_id = f"claim-{actor_id}-{uuid.uuid4().hex}"

    if source or claimant_email:
        metadata_parts = []
        if source:
            metadata_parts.append(f"Source: {source}")
        if claimant_email:
            metadata_parts.append(f"Claimant email: {claimant_email}")
        prompt = f"[{' | '.join(metadata_parts)}]\n\n{prompt}"

    # --- Memory: graceful degradation ---
    session_manager = None
    try:
        session_manager = get_memory_session_manager(session_id, actor_id)
    except Exception as exc:
        log.warning("Memory unavailable (running without memory): %s", exc)

    # --- Phase 1: Claims Processor ---
    yield "## Phase 1: Claims Processing\n\n"

    processor = get_processor(session_manager=session_manager)
    processor_response = ""
    stream = processor.stream_async(prompt)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            processor_response += event["data"]
            yield event["data"]

    # Prefer structured output from tool call; fall back to regex parsing
    structured_decision = get_last_decision()

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

    # Prefer structured output from tool call; fall back to regex parsing
    structured_validation = get_last_validation()

    # --- Phase 3: Routing ---
    yield "\n\n---\n## Phase 3: Execution\n\n"

    if structured_validation:
        confidence = structured_validation["confidence"]
        routing = structured_validation["routing"]
    else:
        confidence = parse_confidence(validator_response)
        if "HUMAN_REVIEW" in validator_response:
            routing = "HUMAN_REVIEW"
        elif "AUTO_APPROVE" in validator_response:
            routing = "AUTO_APPROVE"
        elif confidence >= 80:
            routing = "AUTO_APPROVE"
        else:
            routing = "HUMAN_REVIEW"

    if structured_decision:
        decision = structured_decision["decision"]
    else:
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
