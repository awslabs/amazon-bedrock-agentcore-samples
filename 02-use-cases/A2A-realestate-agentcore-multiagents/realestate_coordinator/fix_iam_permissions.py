"""
Fix IAM permissions for coordinator to invoke sub-agents
Based on AWS documentation: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html
"""

import boto3
import json

# Get the sub-agent ARNs
property_search_arn = "arn:aws:bedrock-agentcore:us-east-1:506053230750:runtime/property_search_agent-hcIU3UFyU1"
property_booking_arn = "arn:aws:bedrock-agentcore:us-east-1:506053230750:runtime/property_booking_agent-0jtIDe6Ho0"

print(f"✓ Property Search Agent ARN: {property_search_arn}")
print(f"✓ Property Booking Agent ARN: {property_booking_arn}")

# Both coordinator roles
coordinator_roles = [
    "AmazonBedrockAgentCoreSDKRuntime-us-east-1-0fdfe2154b",
    "AmazonBedrockAgentCoreSDKRuntime-us-east-1-5285090eaa"
]

print(f"\nCoordinator Roles: {coordinator_roles}")
print("\nAdding IAM permissions for agent-to-agent communication...")

# Create IAM client
iam = boto3.client('iam')

# Create inline policy to allow invoking sub-agents
# Based on AWS AgentCore Runtime permissions documentation
policy_document = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "InvokeSubAgents",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:InvokeAgentRuntime"
            ],
            "Resource": [
                property_search_arn,
                property_booking_arn,
                f"{property_search_arn}/*",
                f"{property_booking_arn}/*"
            ]
        }
    ]
}

policy_name = "CoordinatorSubAgentInvokePolicy"

for role in coordinator_roles:
    try:
        # Put the inline policy
        iam.put_role_policy(
            RoleName=role,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        print(f"\n✓ Successfully added policy '{policy_name}' to role '{role}'")
        
    except Exception as e:
        print(f"\n✗ Error adding policy to role '{role}': {e}")

print("\n" + "="*70)
print("Permissions Summary")
print("="*70)
print(f"\nAction: bedrock-agentcore:InvokeAgentRuntime")
print(f"\nFor resources:")
print(f"  - {property_search_arn}")
print(f"  - {property_booking_arn}")
print(f"  - {property_search_arn}/*")
print(f"  - {property_booking_arn}/*")
print("\n✓ Coordinator can now invoke sub-agents!")
print("\nNote: IAM policy changes may take a few minutes to propagate.")
print("If you still see 403 errors, wait 1-2 minutes and try again.")
