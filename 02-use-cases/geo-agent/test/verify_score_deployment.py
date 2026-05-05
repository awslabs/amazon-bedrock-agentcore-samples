#!/usr/bin/env python3
"""Verify that GEO score tracking is correctly deployed.

Checks:
1. Amazon DynamoDB table exists and is accessible
2. AWS Lambda functions are deployed
3. Storage Lambda supports score fields
4. Amazon DynamoDB items contain all required score fields
"""

import sys
import os
import json
import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
TABLE_NAME = os.environ.get("GEO_TABLE_NAME", "geo-content")
STORAGE_FUNCTION = "geo-content-storage"
GENERATOR_FUNCTION = "geo-content-generator"


def check_dynamodb_table():
    """Check that the Amazon DynamoDB table exists and is accessible."""
    print("1. Checking DynamoDB table...", flush=True)
    try:
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(TABLE_NAME)
        status = table.table_status
        print(f"   ✓ Table '{TABLE_NAME}' exists, status: {status}", flush=True)
        return True
    except Exception as e:
        print(f"   ✗ Error: {e}", flush=True)
        return False


def check_lambda_functions():
    """Check that the required AWS Lambda functions are deployed."""
    print("\n2. Checking Lambda functions...", flush=True)
    lambda_client = boto3.client("lambda", region_name=REGION)

    functions = [STORAGE_FUNCTION, GENERATOR_FUNCTION]
    all_exist = True

    for func_name in functions:
        try:
            response = lambda_client.get_function(FunctionName=func_name)
            runtime = response["Configuration"]["Runtime"]
            print(f"   ✓ {func_name} deployed (runtime: {runtime})", flush=True)
        except lambda_client.exceptions.ResourceNotFoundException:
            print(f"   ✗ {func_name} not found", flush=True)
            all_exist = False
        except Exception as e:
            print(f"   ✗ Error checking {func_name}: {e}", flush=True)
            all_exist = False

    return all_exist


def test_storage_lambda():
    """Test that the Storage Lambda supports score fields in its payload."""
    print("\n3. Testing Storage Lambda score support...", flush=True)

    lambda_client = boto3.client("lambda", region_name=REGION)

    test_payload = {
        "url_path": "/test/verify-deployment",
        "geo_content": "<html><body><h1>Test Content</h1></body></html>",
        "original_url": "https://example.com/test/verify-deployment",
        "content_type": "text/html; charset=utf-8",
        "generation_duration_ms": 1234,
        "host": "example.com",
        "original_score": {
            "overall_score": 50,
            "dimensions": {
                "cited_sources": {"score": 45},
                "statistical_addition": {"score": 40},
                "authoritative": {"score": 65}
            }
        },
        "geo_score": {
            "overall_score": 82,
            "dimensions": {
                "cited_sources": {"score": 85},
                "statistical_addition": {"score": 80},
                "authoritative": {"score": 81}
            }
        }
    }

    try:
        response = lambda_client.invoke(
            FunctionName=STORAGE_FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps(test_payload)
        )

        result = json.loads(response["Payload"].read())

        if result.get("statusCode") == 200:
            print("   ✓ Storage Lambda processed score payload successfully", flush=True)
            return True
        else:
            print(f"   ✗ Storage Lambda returned error: {result}", flush=True)
            return False

    except Exception as e:
        print(f"   ✗ Failed to invoke Storage Lambda: {e}", flush=True)
        return False


def verify_ddb_item():
    """Verify that the Amazon DynamoDB item contains all required score fields."""
    print("\n4. Verifying DynamoDB item...", flush=True)

    try:
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(TABLE_NAME)

        response = table.get_item(
            Key={"url_path": "example.com#/test/verify-deployment"}
        )

        item = response.get("Item")

        if not item:
            print("   ✗ Test item not found", flush=True)
            return False

        required_fields = [
            "geo_content",
            "original_score",
            "geo_score",
            "score_improvement"
        ]

        missing_fields = [f for f in required_fields if f not in item]

        if missing_fields:
            print(f"   ✗ Missing fields: {', '.join(missing_fields)}", flush=True)
            return False

        original = float(item["original_score"]["overall_score"])
        geo = float(item["geo_score"]["overall_score"])
        improvement = float(item["score_improvement"])
        expected_improvement = geo - original

        print("   ✓ All required fields present", flush=True)
        print(f"   ✓ Original score: {original}", flush=True)
        print(f"   ✓ GEO score: {geo}", flush=True)
        print(f"   ✓ Improvement: +{improvement}", flush=True)

        if abs(improvement - expected_improvement) < 0.01:
            print("   ✓ Score calculation correct", flush=True)
        else:
            print(f"   Warning: Score mismatch: expected {expected_improvement}, got {improvement}", flush=True)

        return True

    except Exception as e:
        print(f"   ✗ Verification failed: {e}", flush=True)
        return False


def cleanup():
    """Clean up test data from Amazon DynamoDB."""
    print("\n5. Cleaning up test data...", flush=True)

    try:
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(TABLE_NAME)

        table.delete_item(Key={"url_path": "example.com#/test/verify-deployment"})
        print("   ✓ Test data cleaned up", flush=True)
        return True

    except Exception as e:
        print(f"   Warning: Cleanup failed (can be ignored): {e}", flush=True)
        return False


def main():
    """Run all deployment verification checks."""
    print("=" * 60)
    print("GEO Score Tracking Deployment Verification")
    print("=" * 60)

    results = []

    results.append(("DynamoDB Table", check_dynamodb_table()))
    results.append(("Lambda Functions", check_lambda_functions()))
    results.append(("Storage Lambda", test_storage_lambda()))
    results.append(("DynamoDB Item", verify_ddb_item()))

    cleanup()

    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{name:20s} {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\nAll checks passed. Score tracking is correctly deployed.")
        return 0
    else:
        print("\nSome checks failed. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
