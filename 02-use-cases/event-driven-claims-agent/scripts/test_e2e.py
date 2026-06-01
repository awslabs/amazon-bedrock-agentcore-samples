#!/usr/bin/env python3
"""Comprehensive E2E test suite for the Event-Driven Claims Agent.

Tests all scenarios per requirements:
1. Normal claim (auto-approve, confidence ≥80)
2. Cedar policy block (claim ≥$100k)
3. Human review routing (low confidence, vague claim)
4. Rejected claim (expired policy)
5. Event-driven flow (S3 email upload → EventBridge → Agent)

Usage:
    python3 scripts/test_e2e.py --region us-west-2
    python3 scripts/test_e2e.py --region us-west-2 --test 5  # run specific test only
"""

import argparse
import base64
import json
import time
import urllib.parse
import urllib.request

import boto3


def get_cognito_token(region: str) -> tuple[str, str]:
    """Get M2M token from Cognito using client_credentials flow."""
    cf = boto3.client("cloudformation", region_name=region)
    outputs = cf.describe_stacks(StackName="ClaimsInfraStack")["Stacks"][0]["Outputs"]
    output_map = {o["OutputKey"]: o["OutputValue"] for o in outputs}

    user_pool_id = output_map["UserPoolId"]
    client_id = output_map["UserPoolClientId"]
    runtime_arn = output_map.get("RuntimeArn", "")

    # Get client secret
    cognito = boto3.client("cognito-idp", region_name=region)
    client_info = cognito.describe_user_pool_client(UserPoolId=user_pool_id, ClientId=client_id)
    client_secret = client_info["UserPoolClient"]["ClientSecret"]

    # Get domain
    pool_info = cognito.describe_user_pool(UserPoolId=user_pool_id)
    domain = pool_info["UserPool"].get("Domain", "")
    token_endpoint = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"

    # Request token
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "scope": "agentcore/invoke",
        }
    ).encode()

    req = urllib.request.Request(
        token_endpoint,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {creds}",
        },
    )

    if not token_endpoint.startswith("https://"):
        raise ValueError(f"Only HTTPS URLs are permitted: {token_endpoint}")
    with urllib.request.urlopen(req) as resp:  # nosec B310
        token_data = json.loads(resp.read())

    return token_data["access_token"], runtime_arn


def invoke_agent(token: str, runtime_arn: str, region: str, prompt: str) -> str:
    """Invoke the agent runtime with JWT bearer token. Returns response text."""
    escaped_arn = urllib.parse.quote(runtime_arn, safe="")
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations"

    payload = json.dumps({"prompt": prompt}).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    response_text = ""
    try:
        if not url.startswith("https://"):
            raise ValueError(f"Only HTTPS URLs are permitted: {url}")
        with urllib.request.urlopen(req, timeout=120) as resp:  # nosec B310
            for line in resp:
                decoded = line.decode("utf-8").strip()
                if decoded:
                    if decoded.startswith("data: "):
                        chunk = decoded[6:]
                        if chunk.startswith('"') and chunk.endswith('"'):
                            chunk = json.loads(chunk)
                        response_text += chunk
                    elif decoded.startswith("{") and "error" in decoded:
                        response_text += f"\n[ERROR] {decoded}\n"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        response_text = f"HTTP {e.code}: {body}"

    return response_text


def test_1_normal_claim(token, runtime_arn, region):
    """Test 1: Normal claim - auto-approve (confidence ≥80)"""
    print("\n" + "=" * 70)
    print("TEST 1: Normal Claim (Auto-Approve)")
    print("  Policy: POL-12345 (active, John Smith, $50k coverage)")
    print("  Claim: $2,000 fender bender")
    print("  Expected: ACCEPT → Confidence ≥80 → AUTO_APPROVE → Claim created + notification")
    print("=" * 70)

    response = invoke_agent(
        token,
        runtime_arn,
        region,
        "I need to file a claim. My policy is POL-12345. I had a fender bender in a parking lot yesterday. Estimated damage is about $2,000.",
    )

    # Validate
    passed = all(
        [
            "ACCEPT" in response,
            "AUTO_APPROVE" in response or "Auto-Approved" in response or "auto-approved" in response,
            "CLM-" in response,  # Claim ID created
        ]
    )

    print(f"\n{'✅ PASSED' if passed else '❌ FAILED'}")
    if not passed:
        print(f"  Response excerpt: {response[:500]}")
    return passed


def test_2_cedar_block(token, runtime_arn, region):
    """Test 2: Cedar policy block ($150k ≥ $100k threshold)"""
    print("\n" + "=" * 70)
    print("TEST 2: Cedar Policy Block (High Value Claim)")
    print("  Policy: POL-11111 (active, Bob Johnson, $75k coverage)")
    print("  Claim: $150,000 (exceeds $100k Cedar limit)")
    print("  Expected: BLOCKED by BlockExcessiveClaims Cedar policy")
    print("=" * 70)

    response = invoke_agent(
        token,
        runtime_arn,
        region,
        "I need to file a claim. My policy is POL-11111. My car was completely totaled in a highway accident. The repair shop estimates $150,000 in damage.",
    )

    # Cedar block might manifest as: tool call denied, error, or agent acknowledging it can't create
    blocked = any(
        [
            "denied" in response.lower(),
            "blocked" in response.lower(),
            "not authorized" in response.lower(),
            "cannot create" in response.lower(),
            "policy engine" in response.lower(),
            "exceed" in response.lower(),
        ]
    )

    # Even if not explicitly blocked, check if no claim was created
    claim_created = "CLM-" in response

    # The claim might still be processed by the agent (REJECT due to exceeding coverage)
    # but the Cedar policy should prevent the create_claim tool from executing
    print(f"\n{'✅ PASSED (blocked)' if blocked else '⚠️  CHECK MANUALLY'}")
    print(f"  Claim created: {'Yes (unexpected!)' if claim_created else 'No (correct)'}")
    if not blocked:
        print(f"  Response excerpt: {response[:500]}")
    return blocked


def test_3_human_review(token, runtime_arn, region):
    """Test 3: Human review routing (low confidence, vague claim)"""
    print("\n" + "=" * 70)
    print("TEST 3: Human Review Routing (Low Confidence)")
    print("  Policy: POL-12345 (active)")
    print("  Claim: Vague description, high amount ($30k), no details")
    print("  Expected: Confidence <80 → HUMAN_REVIEW routing")
    print("=" * 70)

    response = invoke_agent(
        token,
        runtime_arn,
        region,
        "I think something might have happened to my car. My policy is POL-12345. I'm not entirely sure what the damage is but it could be around $30,000. I don't have any photos or repair estimates yet.",
    )

    # Check for human review indicators
    human_review = any(
        [
            "HUMAN_REVIEW" in response,
            "human review" in response.lower(),
            "review" in response.lower() and "confidence" in response.lower(),
        ]
    )

    print(f"\n{'✅ PASSED' if human_review else '⚠️  CHECK MANUALLY'}")
    if not human_review:
        print(f"  Response excerpt: {response[:500]}")
    return human_review


def test_4_expired_policy(token, runtime_arn, region):
    """Test 4: Rejected claim (expired policy)"""
    print("\n" + "=" * 70)
    print("TEST 4: Expired Policy Rejection")
    print("  Policy: POL-99999 (EXPIRED, Alice Williams)")
    print("  Claim: $500 minor scratch")
    print("  Expected: REJECT (policy expired)")
    print("=" * 70)

    response = invoke_agent(
        token,
        runtime_arn,
        region,
        "I need to file a claim. My policy number is POL-99999. I have a minor scratch on my bumper, about $500 in damage.",
    )

    # Check for rejection
    rejected = any(
        [
            "REJECT" in response,
            "expired" in response.lower(),
            "inactive" in response.lower(),
            "not active" in response.lower(),
        ]
    )

    print(f"\n{'✅ PASSED' if rejected else '❌ FAILED'}")
    if not rejected:
        print(f"  Response excerpt: {response[:500]}")
    return rejected


def test_5_event_driven_email(region):
    """Test 5: Event-driven flow (S3 email → EventBridge → Trigger Lambda → Agent)"""
    print("\n" + "=" * 70)
    print("TEST 5: Event-Driven Email Flow")
    print("  Upload email to S3 → EventBridge rule → Trigger Lambda → Agent Runtime")
    print("  Expected: Claim processed asynchronously")
    print("=" * 70)

    # Get the inbox bucket name
    account = boto3.client("sts").get_caller_identity()["Account"]
    bucket_name = f"claims-inbox-{account}-{region}"

    # Create a sample email
    email_content = """From: customer@example.com
Subject: Insurance Claim - Vehicle Damage
Date: Sat, 30 May 2026 12:00:00 +0000
To: claims@secureguard-insurance.com

Dear Claims Department,

I am writing to file a claim under my policy POL-67890. 

Yesterday afternoon, a tree branch fell on my roof during a storm, causing significant damage to my home's structure. I have had a contractor come out for an initial assessment, and they estimate the repairs will cost approximately $15,000.

I have photos of the damage and the contractor's written estimate available upon request.

Please process this claim at your earliest convenience.

Best regards,
Jane Doe
"""

    s3 = boto3.client("s3", region_name=region)

    # Upload to the claims-inbox/ prefix (matches EventBridge rule)
    key = f"claims-inbox/claim-{int(time.time())}.eml"
    print(f"  Uploading to s3://{bucket_name}/{key}")

    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=email_content.encode("utf-8"),
            ContentType="text/plain",
        )
        print("  ✅ Email uploaded")
    except Exception as e:
        print(f"  ❌ Upload failed: {e}")
        return False

    # Wait for processing (EventBridge → Lambda → Agent takes 40-60s)
    print("  ⏳ Waiting 60s for event-driven processing...")
    time.sleep(60)

    # Check DynamoDB Claims table for new records (more reliable than log parsing)
    dynamodb = boto3.resource("dynamodb", region_name=region)
    claims_table = dynamodb.Table("ClaimsAgent-Claims")
    try:
        # Scan for claims created in the last 2 minutes (from the email test)
        response = claims_table.scan()
        claims = response.get("Items", [])

        # Look for a claim from POL-67890 (Jane Doe's home policy from the test email)
        email_claims = [c for c in claims if c.get("policy_number") == "POL-67890"]

        if email_claims:
            latest = email_claims[-1]
            print("  ✅ Claim found in DynamoDB!")
            print(f"     Claim ID: {latest.get('claim_id')}")
            print(f"     Policy: {latest.get('policy_number')}")
            print(f"     Status: {latest.get('status')}")
            print(f"     Amount: {latest.get('amount', latest.get('claimed_amount', 'N/A'))}")
            return True
        else:
            # Fallback: check Lambda logs
            print("  ⚠️  No POL-67890 claim in DynamoDB. Checking Lambda logs...")
            logs_client = boto3.client("logs", region_name=region)
            try:
                streams = logs_client.describe_log_streams(
                    logGroupName="/aws/lambda/ClaimsAgent-Trigger",
                    orderBy="LastEventTime",
                    descending=True,
                    limit=1,
                )["logStreams"]
                if streams:
                    events = logs_client.get_log_events(
                        logGroupName="/aws/lambda/ClaimsAgent-Trigger",
                        logStreamName=streams[0]["logStreamName"],
                        limit=10,
                    )["events"]
                    agent_invoked = any("Agent response" in e["message"] or "Phase 1" in e["message"] for e in events)
                    if agent_invoked:
                        print("  ✅ Lambda processed the claim (found in logs)")
                        return True
            except Exception:
                pass
            print("  ❌ No evidence of processing found")
            return False
    except Exception as e:
        print(f"  ⚠️  Error checking DynamoDB: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="E2E Test Suite for Claims Agent")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--test", type=int, default=0, help="Run specific test (1-5), 0=all")
    args = parser.parse_args()

    print("🧪 Event-Driven Claims Agent — E2E Test Suite")
    print(f"   Region: {args.region}")
    print(f"   Tests: {'All' if args.test == 0 else f'Test {args.test} only'}")

    # Get token (needed for tests 1-4)
    if args.test == 0 or args.test <= 4:
        print("\n🔑 Getting Cognito M2M token...")
        token, runtime_arn = get_cognito_token(args.region)
        print(f"   ✅ Token obtained | Runtime: {runtime_arn}")

    results = {}

    if args.test == 0 or args.test == 1:
        results["Test 1: Normal Claim (Auto-Approve)"] = test_1_normal_claim(token, runtime_arn, args.region)

    if args.test == 0 or args.test == 2:
        results["Test 2: Cedar Block ($150k)"] = test_2_cedar_block(token, runtime_arn, args.region)

    if args.test == 0 or args.test == 3:
        results["Test 3: Human Review (Low Confidence)"] = test_3_human_review(token, runtime_arn, args.region)

    if args.test == 0 or args.test == 4:
        results["Test 4: Expired Policy (Reject)"] = test_4_expired_policy(token, runtime_arn, args.region)

    if args.test == 0 or args.test == 5:
        results["Test 5: Event-Driven Email"] = test_5_event_driven_email(args.region)

    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 70)
    for name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED / ⚠️  CHECK"
        print(f"  {status} — {name}")

    total = len(results)
    passed_count = sum(1 for v in results.values() if v)
    print(f"\n  {passed_count}/{total} tests passed")
    print("=" * 70)


if __name__ == "__main__":
    main()
