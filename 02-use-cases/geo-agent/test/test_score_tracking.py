"""Test script to verify GEO score tracking in Amazon DynamoDB."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import boto3
from datetime import datetime, timezone
from decimal import Decimal

# Test configuration
TABLE_NAME = "geo-content"
REGION = "us-east-1"
TEST_URL_PATH = "/test/score-tracking"

# Mock score data
original_score = {
    "overall_score": 45,
    "dimensions": {
        "cited_sources": {"score": 40},
        "statistical_addition": {"score": 35},
        "authoritative": {"score": 60}
    }
}

geo_score = {
    "overall_score": 78,
    "dimensions": {
        "cited_sources": {"score": 80},
        "statistical_addition": {"score": 75},
        "authoritative": {"score": 80}
    }
}

print("Testing GEO score tracking in DDB...", flush=True)

# Write test item with scores
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

item = {
    "url_path": TEST_URL_PATH,
    "status": "ready",
    "geo_content": "<html><body><h1>Test GEO Content</h1></body></html>",
    "content_type": "text/html; charset=utf-8",
    "original_url": f"https://example.com{TEST_URL_PATH}",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "original_score": original_score,
    "geo_score": geo_score,
    "score_improvement": Decimal(str(geo_score["overall_score"] - original_score["overall_score"])),
    "generation_duration_ms": Decimal("5432")
}

print(f"Writing test item to DDB: {TEST_URL_PATH}", flush=True)
table.put_item(Item=item)

# Read back and verify
print("Reading back from DDB...", flush=True)
response = table.get_item(Key={"url_path": TEST_URL_PATH})
stored_item = response.get("Item")

if stored_item:
    print("\n✓ Item stored successfully!", flush=True)
    print(f"  Original score: {stored_item.get('original_score', {}).get('overall_score')}", flush=True)
    print(f"  GEO score: {stored_item.get('geo_score', {}).get('overall_score')}", flush=True)
    print(f"  Improvement: +{stored_item.get('score_improvement')}", flush=True)
    print(f"  Generation time: {stored_item.get('generation_duration_ms')}ms", flush=True)
    
    # Verify all score fields exist
    assert "original_score" in stored_item, "Missing original_score"
    assert "geo_score" in stored_item, "Missing geo_score"
    assert "score_improvement" in stored_item, "Missing score_improvement"
    
    print("\n✓ All score fields verified!", flush=True)
else:
    print("\n✗ ERROR: Item not found in DDB", flush=True)
    sys.exit(1)

# Cleanup
print("\nCleaning up test item...", flush=True)
table.delete_item(Key={"url_path": TEST_URL_PATH})
print("✓ Test completed successfully!", flush=True)
