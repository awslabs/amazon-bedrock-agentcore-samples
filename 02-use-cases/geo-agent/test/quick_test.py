import sys
import os
from datetime import datetime, timezone

import boto3
import requests
import trafilatura

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tools.sanitize import sanitize_web_content  # noqa: E402

print("All imports successful", flush=True)

URL = "https://alb.kgg23.com/world/3149599"
URL_PATH = "/world/3149599"
TABLE_NAME = "geo-content"
REGION = "us-east-1"

print("Fetching page...", flush=True)
resp = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
text = trafilatura.extract(resp.text)
clean = sanitize_web_content(text)
print(f"Fetched: {len(clean)} chars", flush=True)

geo_content = f"<html><body><h1>GEO Optimized</h1><article>{clean}</article></body></html>"

print("Writing to DDB...", flush=True)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)
table.put_item(Item={
    "url_path": URL_PATH,
    "geo_content": geo_content,
    "content_type": "text/html",
    "original_url": URL,
    "updated_at": datetime.now(timezone.utc).isoformat(),
})
print("Done writing to DDB", flush=True)

print("Reading back...", flush=True)
item = table.get_item(Key={"url_path": URL_PATH}).get("Item")
if item:
    print(f"OK: {len(item['geo_content'])} chars", flush=True)
else:
    print("ERROR: not found", flush=True)
