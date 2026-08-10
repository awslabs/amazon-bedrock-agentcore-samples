#!/usr/bin/env python3
"""Run a full review from the command line — no AWS account, no model, no network.

    python scripts/local_review.py --example fsi_loan --sow data/samples/sample-sow-weak.md

This is the fastest way to confirm the sample works before deploying anything,
and it is the path the test suite exercises.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("POC_VALIDATOR_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from pocvalidator.core import catalog, engine, sow
from pocvalidator.core.models import Severity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", default="fsi_loan", help="example id from data/examples.yaml")
    parser.add_argument("--sow", type=Path, help="path to a Scope of Work to score")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--list", action="store_true", help="list available examples")
    args = parser.parse_args()

    examples = catalog.examples()
    if args.list:
        for example in examples:
            print(f"  {example['id']:18} {example['name']}")
        return 0

    example = next((e for e in examples if e["id"] == args.example), None)
    if example is None:
        print(f"Unknown example: {args.example}. Use --list to see the options.")
        return 1

    score = sow.score_heuristic(args.sow.read_text(encoding="utf-8")) if args.sow else None
    graph = engine.graph_from_selection(
        example["segment"], example["industry"], example["region"],
        example["description"].strip(), example["services"],
        [tuple(edge) for edge in example["edges"]], example.get("config") or {},
    )
    report = engine.validate(graph, score)
    verdict, reasoning = report.verdict

    if args.json:
        print(json.dumps({
            "verdict": verdict,
            "reasoning": reasoning,
            "findings": [{"id": f.rule_id, "severity": f.severity.value, "title": f.title}
                         for f in report.sorted_findings],
            "cost": {"baseline": report.cost.baseline,
                     "compliance_premium": report.cost.premium,
                     "total": report.cost.total},
            "sow": {"score": score.total, "rating": score.rating} if score else None,
            "recommendations": [{"title": r.title, "url": r.url, "why": w}
                                for r, w in report.recommendations],
        }, indent=2))
        return 0

    bar = "─" * 74
    print(f"\n{bar}\n  {example['name']}\n{bar}")
    print(f"\n  VERDICT   {verdict}")
    print(f"            {reasoning}\n")
    print("  " + "  ".join(f"{s.value}: {report.count(s)}" for s in Severity))

    print(f"\n{bar}\n  FINDINGS\n{bar}")
    for finding in report.sorted_findings:
        print(f"  [{finding.severity.value:8}] {finding.rule_id:22} {finding.title[:60]}")
        print(f"             {finding.source_label}")

    if report.conflicts:
        print(f"\n{bar}\n  SEGMENT / INDUSTRY TENSION\n{bar}")
        for conflict in report.conflicts:
            print(f"  {conflict.attribute} on {conflict.node_name}")
            print(f"    {conflict.industry_position}")

    print(f"\n{bar}\n  COST  ({report.cost.region}, snapshot {report.cost.as_of})\n{bar}")
    print(f"  Baseline            ${report.cost.baseline:>12,.2f}")
    print(f"  Compliance premium  ${report.cost.premium:>12,.2f}")
    print(f"  Total per month     ${report.cost.total:>12,.2f}")

    if score:
        print(f"\n{bar}\n  SCOPE OF WORK\n{bar}")
        assisted = "model-assisted" if score.model_assisted else "heuristic floor only"
        print(f"  Score {score.total:.1f}/100 — {score.rating}  ({assisted})")
        print(f"  {score.summary}")
        for gap in score.gaps[:4]:
            print(f"    · {gap.name} ({gap.weight}%) — {gap.band_label}")

    print(f"\n{bar}\n  FURTHER READING  (AWS and Amazon sources only)\n{bar}")
    for resource, why in report.recommendations:
        print(f"  [{resource.kind_label:20}] {resource.title[:48]}")
        print(f"      {resource.url}")
        print(f"      because: {why[:64]}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
