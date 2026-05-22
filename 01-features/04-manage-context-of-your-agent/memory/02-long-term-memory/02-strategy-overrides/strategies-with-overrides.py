"""Built-in strategies with prompt + model overrides.

What you learn:
    - Override the extraction prompt and model on a built-in semantic strategy
    - Use `customMemoryStrategy` with `semanticOverride` (or summaryOverride,
      userPreferenceOverride, episodicOverride) inside `memoryStrategies`
    - Required: `memoryExecutionRoleArn` (Bedrock invocations bill against
      your account)

The output schema for built-in strategies is fixed — only the prompt
text appended to the system prompt and the Bedrock model id are
override-able.

Three surfaces:
    python strategies-with-overrides.py boto3
    python strategies-with-overrides.py sdk
    python strategies-with-overrides.py cli

Prerequisites:
    pip install boto3 bedrock-agentcore
    export AWS_REGION=us-east-1
    export MEMORY_EXECUTION_ROLE_ARN=arn:aws:iam::<acct>:role/<role>
"""

import os
import sys
import time
import uuid
from datetime import datetime, timezone

REGION = os.getenv("AWS_REGION", "us-east-1")
MEMORY_ROLE_ARN = os.environ.get("MEMORY_EXECUTION_ROLE_ARN", "")
MODEL_ID = os.getenv("OVERRIDE_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
ACTOR_ID = "user-alex"
SESSION_ID = f"sess-{int(time.time())}"
EXTRACTION_WAIT_SECONDS = 75
NAMESPACE_TEMPLATE = "/users/{actorId}/medical-facts/"

EXTRACTION_ADDENDUM = (
    "Focus exclusively on health-related facts: diagnoses, allergies, "
    "medications, family medical history. Ignore non-medical content."
)
CONSOLIDATION_ADDENDUM = (
    "When two records cover the same medication or condition, prefer the "
    "more recent record and mark the older one as superseded in metadata."
)
TURNS = [
    ("USER", "I'm allergic to penicillin and I take metformin twice daily for type 2 diabetes."),
    ("ASSISTANT", "Got it."),
    ("USER", "Also, my favourite movie is The Godfather."),  # ignored by override
    ("ASSISTANT", "Noted."),
    ("USER", "My mother had breast cancer at 52."),
    ("ASSISTANT", "Thank you for sharing."),
]


def _override_strategy() -> dict:
    return {
        "customMemoryStrategy": {
            "name": "MedicalFacts",
            "description": "Health-only semantic extraction",
            "namespaces": [NAMESPACE_TEMPLATE],
            "configuration": {
                "semanticOverride": {
                    "extraction": {
                        "appendToPrompt": EXTRACTION_ADDENDUM,
                        "modelId": MODEL_ID,
                    },
                    "consolidation": {
                        "appendToPrompt": CONSOLIDATION_ADDENDUM,
                        "modelId": MODEL_ID,
                    },
                }
            },
        }
    }


# === boto3 ============================================================
def run_with_boto3() -> None:
    import boto3

    if not MEMORY_ROLE_ARN:
        raise RuntimeError("Set MEMORY_EXECUTION_ROLE_ARN before running this surface.")

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"OverrideSemantic_{int(time.time())}",
        description="Semantic with extraction + consolidation overrides (boto3)",
        eventExpiryDuration=30,
        memoryExecutionRoleArn=MEMORY_ROLE_ARN,
        memoryStrategies=[_override_strategy()],
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    for role, text in TURNS:
        data.create_event(
            memoryId=memory_id, actorId=ACTOR_ID, sessionId=SESSION_ID,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": role, "content": {"text": text}}}],
        )
    print(f"[boto3] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    hits = data.retrieve_memory_records(
        memoryId=memory_id, namespace=namespace,
        searchCriteria={"searchQuery": "user's medical history", "topK": 10},
    )["memoryRecordSummaries"]
    print(f"\n[boto3] Medical facts ({len(hits)}):")
    for h in hits:
        print(f"  - {h['content']['text']}")
    print("\n[boto3] The Godfather mention should NOT appear — override suppresses it.")

    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    print(f"\n[boto3] Deleted memory {memory_id}")


# === AgentCore SDK ====================================================
def run_with_sdk() -> None:
    from bedrock_agentcore.memory import MemoryClient

    if not MEMORY_ROLE_ARN:
        raise RuntimeError("Set MEMORY_EXECUTION_ROLE_ARN before running this surface.")

    client = MemoryClient(region_name=REGION)
    # MemoryClient.create_memory_and_wait does not expose memoryExecutionRoleArn,
    # so drop down to the wrapped boto3 client (gmcp_client) for CreateMemory.
    cp = client.gmcp_client
    memory_id = cp.create_memory(
        name=f"OverrideSemanticSdk_{int(time.time())}",
        description="Semantic overrides (SDK + gmcp_client)",
        eventExpiryDuration=30,
        memoryExecutionRoleArn=MEMORY_ROLE_ARN,
        memoryStrategies=[_override_strategy()],
    )["memory"]["id"]
    print(f"[sdk] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if cp.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    client.create_event(
        memory_id=memory_id, actor_id=ACTOR_ID, session_id=SESSION_ID,
        messages=[(text, role) for role, text in TURNS],
    )
    print(f"[sdk] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    hits = client.retrieve_memories(
        memory_id=memory_id, namespace=namespace,
        query="user's medical history", top_k=10,
    )
    print(f"\n[sdk] Medical facts ({len(hits)}):")
    for h in hits:
        print(f"  - {h['content']['text']}")

    client.delete_memory_and_wait(memory_id=memory_id)
    print(f"\n[sdk] Deleted memory {memory_id}")


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# 1. Create memory with a customMemoryStrategy that wraps a semantic override.
#    The execution role lets AgentCore invoke Bedrock on your behalf.
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "OverrideCli-$(date +%s)" \\
  --event-expiry-duration 30 --client-token "$(uuidgen)" \\
  --memory-execution-role-arn "$MEMORY_EXECUTION_ROLE_ARN" \\
  --memory-strategies '[{
    "customMemoryStrategy": {
      "name": "MedicalFacts",
      "description": "Health-only semantic extraction",
      "namespaces": ["/users/{actorId}/medical-facts/"],
      "configuration": {
        "semanticOverride": {
          "extraction": {
            "appendToPrompt": "Focus only on health-related facts.",
            "modelId": "anthropic.claude-3-5-sonnet-20241022-v2:0"
          },
          "consolidation": {
            "appendToPrompt": "Prefer the more recent record on conflict.",
            "modelId": "anthropic.claude-3-5-sonnet-20241022-v2:0"
          }
        }
      }
    }
  }]'
export MEMORY_ID=<id>

# 2. Drive the conversation and wait
aws bedrock-agentcore create-event \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --actor-id user-alex --session-id sess-cli \\
  --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \\
  --payload '[{"conversational":{"role":"USER","content":{"text":"I take metformin daily."}}}]'
sleep 75

# 3. Retrieve
aws bedrock-agentcore retrieve-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --namespace "/users/user-alex/medical-facts/" \\
  --search-criteria '{"searchQuery":"medical history","topK":10}'

# 4. Teardown
aws bedrock-agentcore-control delete-memory \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --client-token "$(uuidgen)"
"""


def main() -> None:
    surface = sys.argv[1] if len(sys.argv) > 1 else "boto3"
    if surface == "boto3":
        run_with_boto3()
    elif surface == "sdk":
        run_with_sdk()
    elif surface == "cli":
        print(CLI_WALKTHROUGH)
    else:
        print(f"Unknown surface {surface!r}. Use boto3 | sdk | cli.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
