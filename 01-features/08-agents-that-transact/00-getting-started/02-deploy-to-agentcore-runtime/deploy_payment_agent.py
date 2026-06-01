"""
Deploy Payment Agent to AgentCore Runtime

Deploys the payment-enabled Strands agent to AgentCore Runtime using the
agentcore CLI. After deployment, the agent can be invoked over HTTPS with
SigV4 auth from any AWS-authenticated client.

Architecture:
    App Backend                          AgentCore Runtime
      │                                   ┌──────────────────────────┐
      │ create_session(budget=$0.50)      │  Payment Agent            │
      │                                   │  (execution role)         │
      │── invoke(session, instrument) ──►│  Plugin: ProcessPayment   │
      │                                   │  Cannot: CreateSession    │
      │◄── weather data + cost ─────────│  Cannot: Override budget   │
      │                                   └──────────────────────────┘
      │ get_session(check spend)

Usage:
    python deploy_payment_agent.py

Prerequisites:
    - Tutorial 00 and 01 completed
    - Wallet funded with testnet USDC
    - Node.js 20+ and agentcore CLI installed: npm install -g @aws/agentcore
    - AWS CDK installed: npm install -g aws-cdk
    - pip install -r requirements.txt
"""

import json
import os
import re
import shutil
import subprocess
import sys

import boto3
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_tutorial_env, print_summary, update_env_file

ENV_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
)
load_dotenv(ENV_FILE, override=True)

HERE = os.path.dirname(os.path.abspath(__file__))

# ── Verify AWS credentials ────────────────────────────────────────────────────
session = boto3.Session()
identity = session.client("sts").get_caller_identity()
account_id = identity["Account"]
REGION = session.region_name or os.environ.get("AWS_REGION", "us-west-2")
print(f"Authenticated as: {identity['Arn']}")
print(f"Account: {account_id}")
print(f"Region: {REGION}")

# ── Step 4: Load Payment Config ───────────────────────────────────────────────
config = load_tutorial_env()
PAYMENT_MANAGER_ARN = config["payment_manager_arn"]
USER_ID = config["user_id"]

if config.get("multi_provider"):
    PROVIDER = list(config["instruments"].keys())[0]
    INSTRUMENT_ID = config["instruments"][PROVIDER]["instrument_id"]
else:
    INSTRUMENT_ID = config["instrument_id"]
    PROVIDER = config.get("provider_type", "unknown")

print_summary(
    "Payment Config",
    payment_manager_arn=PAYMENT_MANAGER_ARN,
    region=REGION,
    user_id=USER_ID,
    instrument_id=INSTRUMENT_ID,
    provider=PROVIDER,
)

# ── Step 5: Test Locally ──────────────────────────────────────────────────────
print("""
── Step 5: Test Locally (optional) ──
To test locally before deploying:
  1. Run in a separate terminal:
       python payment_agent.py
  2. Health check:
       curl -s http://localhost:8080/ping
  3. Test invocation:
       curl -X POST http://localhost:8080/invocations \\
            -H 'Content-Type: application/json' \\
            -d '{"prompt": "Hello, what can you do?"}'
  4. Stop the agent (Ctrl+C), then continue with deployment.
""")

# ── Step 6: Scaffold the AgentCore Project ────────────────────────────────────
print("── Step 6: Scaffold AgentCore Project ──")
project_dir = os.path.join(HERE, "PaymentAgent")

if not os.path.exists(project_dir):
    subprocess.run(
        [
            "agentcore",
            "create",
            "--name",
            "PaymentAgent",
            "--framework",
            "Strands",
            "--protocol",
            "HTTP",
            "--model-provider",
            "Bedrock",
            "--memory",
            "none",
        ],
        cwd=HERE,
        check=True,
    )
    print("AgentCore project scaffolded: PaymentAgent/")
else:
    print("PaymentAgent/ already exists — skipping create")

# Copy agent code into the project
agent_dest = os.path.join(project_dir, "app", "PaymentAgent", "main.py")
shutil.copy(os.path.join(HERE, "payment_agent.py"), agent_dest)
print(f"Agent code copied to {agent_dest}")

# Update pyproject.toml
pyproject_content = """[project]
name = "payment-agent"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "bedrock-agentcore[strands-agents]>=1.9.0",
    "boto3>=1.43.5",
    "strands-agents>=1.0.0",
    "strands-agents-tools>=0.2.0",
    "python-dotenv>=1.0.0",
]
"""
pyproject_path = os.path.join(project_dir, "app", "PaymentAgent", "pyproject.toml")
with open(pyproject_path, "w") as f:
    f.write(pyproject_content)

# Remove stale lock file if it exists
lock_file = os.path.join(project_dir, "app", "PaymentAgent", "uv.lock")
if os.path.exists(lock_file):
    os.remove(lock_file)

print("pyproject.toml updated")

# ── Step 7: Deploy to AgentCore Runtime ───────────────────────────────────────
print("\n── Step 7: Deploy to AgentCore Runtime ──")
print("This creates billable AWS resources (Lambda, CloudWatch, API Gateway).")
print("First deploy takes ~2-3 minutes...\n")

subprocess.run(["agentcore", "deploy", "-y"], cwd=project_dir, check=True)

# Verify deployment
result = subprocess.run(
    ["agentcore", "status"], cwd=project_dir, capture_output=True, text=True
)
print(result.stdout)

# Add payment permissions to the auto-created execution role
print("Adding payment permissions to execution role...")
iam = boto3.client("iam")
roles = iam.list_roles(MaxItems=200)["Roles"]
runtime_roles = [
    r["RoleName"]
    for r in roles
    if "PaymentAgent" in r["RoleName"] and "Execution" in r["RoleName"]
]
if not runtime_roles:
    runtime_roles = [r["RoleName"] for r in roles if "PaymentAgent" in r["RoleName"]]

if runtime_roles:
    RUNTIME_ROLE_NAME = runtime_roles[0]
    payment_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:ProcessPayment",
                    "bedrock-agentcore:GetPaymentInstrument",
                    "bedrock-agentcore:ListPaymentInstruments",
                    "bedrock-agentcore:GetPaymentInstrumentBalance",
                    "bedrock-agentcore:GetPaymentSession",
                    "bedrock-agentcore:GetResourcePaymentToken",
                ],
                "Resource": f"arn:aws:bedrock-agentcore:{REGION}:{account_id}:payment-manager/*",
            }
        ],
    }
    iam.put_role_policy(
        RoleName=RUNTIME_ROLE_NAME,
        PolicyName="PaymentDataPlaneAccess",
        PolicyDocument=json.dumps(payment_policy),
    )
    print(f"Added payment permissions to: {RUNTIME_ROLE_NAME}")
else:
    print(
        "WARNING: Could not find PaymentAgent execution role — add payment permissions manually"
    )

# Extract Runtime ARN and save to .env
status_output = result.stdout + result.stderr
match = re.search(r"arn:aws:bedrock-agentcore:[^\s\"]+", status_output)
if match:
    AGENT_RUNTIME_ARN = match.group(0)
    update_env_file(ENV_FILE, {"AGENT_RUNTIME_ARN": AGENT_RUNTIME_ARN})
    print(f"Runtime ARN: {AGENT_RUNTIME_ARN}")
    print("Saved to .env")
else:
    print(
        "NOTE: Could not extract Runtime ARN from status output — check agentcore status manually"
    )

# ── Step 8: Invoke the Deployed Agent ────────────────────────────────────────
print("\n── Step 8: Invoke Deployed Agent ──")
from bedrock_agentcore.payments import PaymentManager  # noqa: E402

manager = PaymentManager(payment_manager_arn=PAYMENT_MANAGER_ARN, region_name=REGION)

fresh_session = manager.create_payment_session(
    user_id=USER_ID,
    limits={"maxSpendAmount": {"value": "0.50", "currency": "USD"}},
    expiry_time_in_minutes=60,
)
fresh_session_id = fresh_session["paymentSessionId"]
print(f"Session: {fresh_session_id} (budget: $0.50, expiry: 60 min)")

invoke_payload = json.dumps(
    {
        "prompt": (
            "Access this paid weather API and tell me what data you get back: "
            "https://x402-test.genesisblock.ai/api/weather "
            "Report the weather data and how much it cost."
        ),
        "payment_manager_arn": PAYMENT_MANAGER_ARN,
        "user_id": USER_ID,
        "payment_session_id": fresh_session_id,
        "payment_instrument_id": INSTRUMENT_ID,
    }
)

print("Invoking deployed agent...")
subprocess.run(
    ["agentcore", "invoke", invoke_payload],
    cwd=project_dir,
    check=True,
)

# ── Step 9: Verify Session Spend ─────────────────────────────────────────────
print("\n── Step 9: Verify Session Spend ──")
session_info = manager.get_payment_session(
    user_id=USER_ID,
    payment_session_id=fresh_session_id,
)
available = session_info.get("availableLimits", {}).get("availableSpendAmount", {})
budget = session_info.get("limits", {}).get("maxSpendAmount", {})
print_summary(
    "Post-Invocation Session",
    session_id=fresh_session_id,
    budget_limit=f"${budget.get('value', 'N/A')} {budget.get('currency', '')}",
    remaining=f"${available.get('value', 'N/A')} {available.get('currency', '')}",
)

# ── Observability ─────────────────────────────────────────────────────────────
print("\n── Observability ──")
print(
    f"GenAI Dashboard: https://{REGION}.console.aws.amazon.com/cloudwatch/home?"
    f"region={REGION}#gen-ai-observability/agent-core"
)
print("Stream logs:     cd PaymentAgent && agentcore logs")
print("\nDone. To clean up: cd PaymentAgent && agentcore remove all -y")
print("Next: python ../03-user-onboarding-wallet-funding/user_onboarding.py")
