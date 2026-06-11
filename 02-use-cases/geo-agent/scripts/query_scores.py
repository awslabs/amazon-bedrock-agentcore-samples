#!/usr/bin/env python3
"""Query and analyze GEO score tracking data from Amazon DynamoDB.

Usage:
  python scripts/query_scores.py --stats              # Show statistics
  python scripts/query_scores.py --top 10             # Top 10 improvements
  python scripts/query_scores.py --url /path          # Query specific URL
  python scripts/query_scores.py --export scores.json # Export all score data
"""

import argparse
import json
import sys
import boto3
from decimal import Decimal
from typing import List, Dict, Any

REGION = "us-east-1"
TABLE_NAME = "geo-content"


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def get_all_items_with_scores(region: str = None, table_name: str = None) -> List[Dict[str, Any]]:
    """Scan Amazon DynamoDB and return all items that contain score data."""
    region = region or REGION
    table_name = table_name or TABLE_NAME

    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    items = []
    scan_kwargs = {
        "ProjectionExpression": "url_path, original_score, geo_score, score_improvement, created_at, generation_duration_ms"
    }

    try:
        response = table.scan(**scan_kwargs)
        items.extend([
            item for item in response.get("Items", [])
            if "score_improvement" in item
        ])

        while "LastEvaluatedKey" in response:
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            response = table.scan(**scan_kwargs)
            items.extend([
                item for item in response.get("Items", [])
                if "score_improvement" in item
            ])
    except Exception as e:
        print(f"Error: Failed to scan DynamoDB table: {e}", file=sys.stderr)
        sys.exit(1)

    return items


def show_statistics(items: List[Dict[str, Any]]):
    """Display score tracking statistics."""
    if not items:
        print("No items with score data found.")
        return

    improvements = [float(item["score_improvement"]) for item in items]
    original_scores = [
        float(item["original_score"]["overall_score"])
        for item in items
        if "original_score" in item and "overall_score" in item["original_score"]
    ]
    geo_scores = [
        float(item["geo_score"]["overall_score"])
        for item in items
        if "geo_score" in item and "overall_score" in item["geo_score"]
    ]

    print("=" * 60)
    print("GEO Score Tracking Statistics")
    print("=" * 60)
    print(f"Total items: {len(items)}")
    print()

    if improvements:
        print("Score improvement:")
        print(f"  Average: +{sum(improvements) / len(improvements):.1f}")
        print(f"  Max:     +{max(improvements):.1f}")
        print(f"  Min:     +{min(improvements):.1f}")
        print()

    if original_scores:
        print("Original scores:")
        print(f"  Average: {sum(original_scores) / len(original_scores):.1f}")
        print(f"  Range:   {min(original_scores):.0f} - {max(original_scores):.0f}")
        print()

    if geo_scores:
        print("GEO-optimized scores:")
        print(f"  Average: {sum(geo_scores) / len(geo_scores):.1f}")
        print(f"  Range:   {min(geo_scores):.0f} - {max(geo_scores):.0f}")
        print()

    dimensions = ["cited_sources", "statistical_addition", "authoritative"]
    print("Per-dimension average improvement:")
    for dim in dimensions:
        original_dim = []
        geo_dim = []
        for item in items:
            if ("original_score" in item and "dimensions" in item["original_score"] and
                dim in item["original_score"]["dimensions"]):
                original_dim.append(float(item["original_score"]["dimensions"][dim]["score"]))
            if ("geo_score" in item and "dimensions" in item["geo_score"] and
                dim in item["geo_score"]["dimensions"]):
                geo_dim.append(float(item["geo_score"]["dimensions"][dim]["score"]))

        if original_dim and geo_dim:
            avg_original = sum(original_dim) / len(original_dim)
            avg_geo = sum(geo_dim) / len(geo_dim)
            improvement = avg_geo - avg_original
            print(f"  {dim:25s}: {avg_original:5.1f} -> {avg_geo:5.1f} (+{improvement:5.1f})")


def show_top_improvements(items: List[Dict[str, Any]], limit: int = 10):
    """Display items with the largest score improvements."""
    if not items:
        print("No items with score data found.")
        return

    sorted_items = sorted(
        items,
        key=lambda x: float(x.get("score_improvement", 0)),
        reverse=True
    )

    print("=" * 120)
    print(f"Top {limit} improvements")
    print("=" * 120)
    print(f"{'Original':<10} {'GEO':<10} {'Improvement':<12} URL Path")
    print("-" * 120)

    for item in sorted_items[:limit]:
        url_path = item["url_path"]
        original = float(item.get("original_score", {}).get("overall_score", 0))
        geo = float(item.get("geo_score", {}).get("overall_score", 0))
        improvement = float(item.get("score_improvement", 0))

        print(f"{original:<10.1f} {geo:<10.1f} +{improvement:<11.1f} {url_path}")


def show_url_details(items: List[Dict[str, Any]], url_path: str):
    """Display detailed score information for a specific URL."""
    matching = [item for item in items if url_path in item["url_path"]]

    if not matching:
        print(f"No items found matching '{url_path}'.")
        return

    for item in matching:
        print("=" * 60)
        print(f"URL: {item['url_path']}")
        print("=" * 60)

        if "created_at" in item:
            print(f"Created: {item['created_at']}")

        if "generation_duration_ms" in item:
            print(f"Generation time: {float(item['generation_duration_ms'])}ms")

        print()

        if "original_score" in item:
            orig = item["original_score"]
            print(f"Original score: {orig.get('overall_score', 'N/A')}")
            if "dimensions" in orig:
                for dim, data in orig["dimensions"].items():
                    print(f"  - {dim}: {data.get('score', 'N/A')}")

        print()

        if "geo_score" in item:
            geo = item["geo_score"]
            print(f"GEO score: {geo.get('overall_score', 'N/A')}")
            if "dimensions" in geo:
                for dim, data in geo["dimensions"].items():
                    print(f"  - {dim}: {data.get('score', 'N/A')}")

        print()

        if "score_improvement" in item:
            print(f"Improvement: +{float(item['score_improvement']):.1f}")

        print()


def export_scores(items: List[Dict[str, Any]], output_file: str):
    """Export all score data to a JSON file."""
    if not items:
        print("No items with score data found.")
        return

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2, cls=DecimalEncoder)
        print(f"Exported {len(items)} items to {output_file}")
    except Exception as e:
        print(f"Error: Failed to write file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Query and analyze GEO score tracking data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --stats                    # Show statistics
  %(prog)s --top 10                   # Top 10 improvements
  %(prog)s --url /world/3149600       # Query specific URL
  %(prog)s --export scores.json       # Export all data
        """
    )

    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--top", type=int, metavar="N", help="Show top N improvements")
    parser.add_argument("--url", type=str, metavar="PATH", help="Query a specific URL")
    parser.add_argument("--export", type=str, metavar="FILE", help="Export score data to JSON file")
    parser.add_argument("--region", type=str, default=REGION, help=f"AWS region (default: {REGION})")
    parser.add_argument("--table", type=str, default=TABLE_NAME, help=f"DynamoDB table name (default: {TABLE_NAME})")

    args = parser.parse_args()

    if not any([args.stats, args.top, args.url, args.export]):
        args.stats = True

    print("Reading data from DynamoDB...", flush=True)
    items = get_all_items_with_scores(args.region, args.table)
    print(f"Found {len(items)} items with score data\n", flush=True)

    if args.stats:
        show_statistics(items)

    if args.top:
        show_top_improvements(items, args.top)

    if args.url:
        show_url_details(items, args.url)

    if args.export:
        export_scores(items, args.export)


if __name__ == "__main__":
    main()
