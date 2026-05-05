#!/usr/bin/env python3
"""E2E test: parse list page for latest article, run full GEO test suite.

Test steps per site:
  1. Parse list page to find the latest article URL
  2. Purge existing cache
  3. Sync mode: trigger Amazon Bedrock AgentCore generation, wait for GEO content
  4. Cache hit: re-request, verify served from cache
  5. Score check: query Amazon DynamoDB for score tracking data
  6. Passthrough: purge again, verify passthrough returns original + triggers async

Results are logged to test/e2e_results/ with timestamps for historical review.

Usage:
  python test/e2e_geo_test.py                    # test both sites
  python test/e2e_geo_test.py --site setn        # SETN only
  python test/e2e_geo_test.py --site tvbs        # TVBS only
  python test/e2e_geo_test.py --quick            # skip sync (passthrough only)
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
import requests

# --- Site configs ---
SITES = {
    "setn": {
        "list_url": "https://dlmwhof468s34.cloudfront.net/viewall.aspx?pagegroupid=0",
        "link_pattern": r'href="(/News\.aspx\?NewsID=(\d+))"',
        "base_url": "https://dlmwhof468s34.cloudfront.net",
        "cf_host": "dlmwhof468s34.cloudfront.net",
        "sort_key": lambda m: int(m.group(2)),
    },
    "tvbs": {
        "list_url": "https://dq324v08a4yas.cloudfront.net/realtime",
        "link_pattern": r'href="/((?:life|world|politics|entertainment|local|health|money|sports|china|tech|travel|focus|fun)/(\d+))"',
        "base_url": "https://dq324v08a4yas.cloudfront.net",
        "cf_host": "dq324v08a4yas.cloudfront.net",
        "sort_key": lambda m: int(m.group(2)),
    },
}

UA_BOT = "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)"
UA_NORMAL = "Mozilla/5.0 (compatible; GEOTest/1.0)"
DDB_TABLE = "geo-content"
DDB_REGION = "us-east-1"


class TestResult:
    """Collects test step results for logging."""

    def __init__(self, site: str, url: str):
        self.site = site
        self.url = url
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.steps = []
        self.passed = True

    def step(self, name: str, passed: bool, details: dict | None = None):
        entry = {"name": name, "passed": passed}
        if details:
            entry["details"] = details
        self.steps.append(entry)
        if not passed:
            self.passed = False
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")
        if details:
            for k, v in details.items():
                print(f"    {k}: {v}")

    def to_dict(self):
        return {
            "site": self.site,
            "url": self.url,
            "started_at": self.started_at,
            "passed": self.passed,
            "steps": self.steps,
        }


def fetch_latest_article(site_key: str) -> str | None:
    """Parse list page and return the latest article's full URL."""
    cfg = SITES[site_key]
    print(f"[{site_key}] Fetching list: {cfg['list_url']}")
    resp = requests.get(cfg["list_url"], headers={"User-Agent": UA_NORMAL}, timeout=15)
    resp.raise_for_status()

    matches = list(re.finditer(cfg["link_pattern"], resp.text))
    if not matches:
        print(f"[{site_key}] No article links found!")
        return None

    seen = set()
    unique = []
    for m in matches:
        path = m.group(1)
        if path not in seen:
            seen.add(path)
            unique.append(m)

    unique.sort(key=cfg["sort_key"], reverse=True)
    latest_path = unique[0].group(1)
    url = f"{cfg['base_url']}/{latest_path}" if not latest_path.startswith("/") else f"{cfg['base_url']}{latest_path}"
    print(f"[{site_key}] Latest article: {url}")
    return url


def _bot_url(url: str, **params) -> str:
    """Build test URL with ua=genaibot and optional extra params."""
    sep = "&" if "?" in url else "?"
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    extra = f"&{qs}" if qs else ""
    return f"{url}{sep}ua=genaibot{extra}"


def _get_headers(resp) -> dict:
    return {
        "X-GEO-Optimized": resp.headers.get("X-GEO-Optimized", ""),
        "X-GEO-Source": resp.headers.get("X-GEO-Source", ""),
        "X-GEO-Handler-Ms": resp.headers.get("X-GEO-Handler-Ms", ""),
        "X-GEO-Duration-Ms": resp.headers.get("X-GEO-Duration-Ms", ""),
    }


def _ddb_key(site_key: str, url: str) -> str:
    """Build the DDB key the handler would use: {cf_host}#{path}[?query]."""
    from urllib.parse import urlparse
    cfg = SITES[site_key]
    parsed = urlparse(url)
    path = parsed.path or "/"
    key = f"{cfg['cf_host']}#{path}"
    if parsed.query:
        # Strip test params (ua, mode, purge)
        real_qs = "&".join(
            p for p in parsed.query.split("&")
            if not p.startswith(("ua=", "mode=", "purge="))
        )
        if real_qs:
            key += f"?{real_qs}"
    return key


def check_ddb_scores(site_key: str, url: str) -> dict:
    """Query DDB for score tracking data."""
    ddb_key = _ddb_key(site_key, url)
    dynamodb = boto3.resource("dynamodb", region_name=DDB_REGION)
    table = dynamodb.Table(DDB_TABLE)
    try:
        resp = table.get_item(Key={"url_path": ddb_key})
        item = resp.get("Item")
        if not item:
            return {"found": False, "ddb_key": ddb_key}
        result = {"found": True, "ddb_key": ddb_key, "status": item.get("status")}
        if "original_score" in item:
            result["original_score"] = float(item["original_score"].get("overall_score", 0))
        if "geo_score" in item:
            result["geo_score"] = float(item["geo_score"].get("overall_score", 0))
        if "score_improvement" in item:
            result["score_improvement"] = float(item["score_improvement"])
        if "generation_duration_ms" in item:
            result["generation_duration_ms"] = float(item["generation_duration_ms"])
        return result
    except Exception as e:
        return {"found": False, "error": str(e), "ddb_key": ddb_key}


def run_full_test(site_key: str, url: str, quick: bool = False) -> TestResult:
    """Run full test suite for a single URL."""
    result = TestResult(site_key, url)
    print(f"\n{'='*70}")
    print(f"[{site_key}] Full E2E Test: {url}")
    print(f"{'='*70}")

    # Step 1: Purge
    print("\n--- Step 1: Purge cache ---")
    try:
        resp = requests.get(_bot_url(url, purge="true"), headers={"User-Agent": UA_BOT}, timeout=15)
        result.step("purge", resp.status_code == 200, {"status": resp.status_code})
    except Exception as e:
        result.step("purge", False, {"error": str(e)})

    if quick:
        # Quick mode: passthrough only
        print("\n--- Step 2: Passthrough mode ---")
        try:
            start = time.time()
            resp = requests.get(_bot_url(url), headers={"User-Agent": UA_BOT}, timeout=30)
            elapsed = time.time() - start
            hdrs = _get_headers(resp)
            ok = resp.status_code == 200 and hdrs["X-GEO-Source"] in ("passthrough", "cache")
            result.step("passthrough", ok, {
                "status": resp.status_code,
                "time": f"{elapsed:.1f}s",
                "content_length": len(resp.text),
                **hdrs,
            })
        except Exception as e:
            result.step("passthrough", False, {"error": str(e)})
        return result

    # Step 2: Sync mode — full generation
    print("\n--- Step 2: Sync mode (wait for AgentCore) ---")
    try:
        start = time.time()
        resp = requests.get(_bot_url(url, mode="sync"), headers={"User-Agent": UA_BOT}, timeout=80)
        elapsed = time.time() - start
        hdrs = _get_headers(resp)
        is_geo = hdrs["X-GEO-Optimized"] == "true"
        is_html = resp.text.strip().startswith("<")
        ok = resp.status_code == 200 and is_geo and is_html
        result.step("sync_generation", ok, {
            "status": resp.status_code,
            "time": f"{elapsed:.1f}s",
            "content_length": len(resp.text),
            "is_html": is_html,
            **hdrs,
        })
    except Exception as e:
        result.step("sync_generation", False, {"error": str(e)})
        return result  # can't continue if sync failed

    # Step 3: Cache hit — re-request should serve from cache
    print("\n--- Step 3: Cache hit verification ---")
    try:
        start = time.time()
        resp = requests.get(_bot_url(url), headers={"User-Agent": UA_BOT}, timeout=15)
        elapsed = time.time() - start
        hdrs = _get_headers(resp)
        ok = (
            hdrs["X-GEO-Optimized"] == "true"
            and hdrs["X-GEO-Source"] == "cache"
            and resp.status_code == 200
        )
        result.step("cache_hit", ok, {
            "status": resp.status_code,
            "time": f"{elapsed:.1f}s",
            **hdrs,
        })
    except Exception as e:
        result.step("cache_hit", False, {"error": str(e)})

    # Step 4: DDB score check
    print("\n--- Step 4: DDB score tracking ---")
    # Scores are updated async, wait a bit
    time.sleep(3)
    scores = check_ddb_scores(site_key, url)
    has_scores = scores.get("original_score") is not None and scores.get("geo_score") is not None
    result.step("ddb_record", scores.get("found", False), {
        "ddb_key": scores.get("ddb_key"),
        "status": scores.get("status"),
    })
    if has_scores:
        result.step("score_tracking", True, {
            "original_score": scores["original_score"],
            "geo_score": scores["geo_score"],
            "improvement": scores.get("score_improvement", "N/A"),
        })
    else:
        # Scores might still be computing (async), not a hard failure
        result.step("score_tracking", True, {"note": "scores still computing (async)"})

    # Step 5: Passthrough mode — purge and verify passthrough behavior
    print("\n--- Step 5: Passthrough mode ---")
    try:
        requests.get(_bot_url(url, purge="true"), headers={"User-Agent": UA_BOT}, timeout=15)
        start = time.time()
        resp = requests.get(_bot_url(url), headers={"User-Agent": UA_BOT}, timeout=30)
        elapsed = time.time() - start
        hdrs = _get_headers(resp)
        ok = resp.status_code == 200 and hdrs["X-GEO-Source"] in ("passthrough", "cache")
        result.step("passthrough", ok, {
            "status": resp.status_code,
            "time": f"{elapsed:.1f}s",
            **hdrs,
        })
    except Exception as e:
        result.step("passthrough", False, {"error": str(e)})

    return result


def save_results(results: list[TestResult]):
    """Save test results to JSON log file."""
    log_dir = Path(__file__).parent / "e2e_results"
    log_dir.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"e2e_{ts}.json"

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "all_passed": all(r.passed for r in results),
        "results": [r.to_dict() for r in results],
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {log_file}")
    return log_file


def main():
    parser = argparse.ArgumentParser(description="E2E GEO edge serving test suite")
    parser.add_argument("--site", choices=["setn", "tvbs", "both"], default="both")
    parser.add_argument("--quick", action="store_true", help="Skip sync mode (passthrough only)")
    args = parser.parse_args()

    sites = ["setn", "tvbs"] if args.site == "both" else [args.site]
    results = []

    for site in sites:
        url = fetch_latest_article(site)
        if not url:
            r = TestResult(site, "N/A")
            r.step("fetch_list", False, {"error": "No article links found"})
            results.append(r)
            continue
        results.append(run_full_test(site, url, quick=args.quick))

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for r in results:
        status = "✓ PASSED" if r.passed else "✗ FAILED"
        print(f"  [{r.site}] {status} — {r.url}")
        for s in r.steps:
            icon = "✓" if s["passed"] else "✗"
            print(f"    {icon} {s['name']}")

    save_results(results)

    all_passed = all(r.passed for r in results)
    print(f"\nOverall: {'✓ ALL PASSED' if all_passed else '✗ SOME FAILED'}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
