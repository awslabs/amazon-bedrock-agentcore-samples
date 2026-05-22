"""Customer-managed KMS encryption on a memory resource.

What you learn:
    - Pass encryptionKeyArn to CreateMemory
    - The IAM permissions the memory execution role needs on the key
    - Verify the key is in use via GetMemory

By default, AgentCore Memory data is encrypted with AWS-owned keys. To use
your own key (for compliance, key rotation control, audit, or cross-account
access reviews), pass a customer-managed KMS key ARN to CreateMemory.

Three surfaces:
    python kms-encryption.py boto3
    python kms-encryption.py sdk    # documents the SDK gap
    python kms-encryption.py cli

SDK note: MemoryClient.create_memory_and_wait does not expose
encryptionKeyArn or memoryExecutionRoleArn. Use the wrapped boto3 client
(`client.gmcp_client`) or boto3 directly.

Prerequisites:
    pip install boto3 bedrock-agentcore
    export AWS_REGION=us-east-1
    export KMS_KEY_ARN=arn:aws:kms:us-east-1:111122223333:key/abcd-...
    export MEMORY_EXECUTION_ROLE_ARN=arn:aws:iam::111122223333:role/AgentCoreMemoryRole

The memory execution role's trust policy must allow bedrock-agentcore.amazonaws.com,
and its permissions policy must include kms:GenerateDataKey and kms:Decrypt
on the key. The key policy must in turn allow that role.
"""

import os
import sys
import time
import uuid

REGION = os.getenv("AWS_REGION", "us-east-1")


# === boto3 ============================================================
def run_with_boto3() -> None:
    import boto3

    kms_key_arn = os.environ.get("KMS_KEY_ARN")
    role_arn = os.environ.get("MEMORY_EXECUTION_ROLE_ARN")
    if not kms_key_arn or not role_arn:
        print("[boto3] Set KMS_KEY_ARN and MEMORY_EXECUTION_ROLE_ARN before running.")
        return

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)

    memory_id = control.create_memory(
        name=f"KMSEncrypted_{int(time.time())}",
        description="Memory encrypted with a customer-managed KMS key (boto3)",
        eventExpiryDuration=30,
        encryptionKeyArn=kms_key_arn,
        memoryExecutionRoleArn=role_arn,
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id} with CMK")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    detail = control.get_memory(memoryId=memory_id)["memory"]
    print(f"  status           = {detail['status']}")
    print(f"  encryptionKeyArn = {detail.get('encryptionKeyArn')}")

    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    print(f"[boto3] Deleted memory {memory_id}")


# === AgentCore SDK ====================================================
def run_with_sdk() -> None:
    print(
        "[sdk] CMK encryption is not exposed by MemoryClient.\n"
        "      - encryptionKeyArn: not on create_memory_and_wait\n"
        "      - memoryExecutionRoleArn: not on create_memory_and_wait\n"
        "      Use boto3 (see run_with_boto3) or the wrapped client:\n"
        "        client.gmcp_client.create_memory(\n"
        "            ..., encryptionKeyArn=...,\n"
        "            memoryExecutionRoleArn=...)"
    )


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# Prereqs:
#   - A KMS CMK in the same region as the memory.
#   - A memory execution role whose trust policy allows
#     bedrock-agentcore.amazonaws.com to assume it, and whose permissions
#     include kms:GenerateDataKey and kms:Decrypt on the key.
#   - The key policy must allow that role to use the key.
export KMS_KEY_ARN=arn:aws:kms:$AWS_REGION:<acct>:key/<key-id>
export MEMORY_EXECUTION_ROLE_ARN=arn:aws:iam::<acct>:role/AgentCoreMemoryRole

# 1. Create memory with CMK encryption
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "KMSCli-$(date +%s)" \\
  --event-expiry-duration 30 --client-token "$(uuidgen)" \\
  --encryption-key-arn "$KMS_KEY_ARN" \\
  --memory-execution-role-arn "$MEMORY_EXECUTION_ROLE_ARN"
export MEMORY_ID=<id>

# 2. Verify the key is recorded on the resource
aws bedrock-agentcore-control get-memory \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --query 'memory.{status:status,key:encryptionKeyArn}'

# 3. Teardown
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
