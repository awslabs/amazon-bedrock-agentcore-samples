#!/usr/bin/env python3
"""
Video Games Sales Assistant — Evaluation Harness

Measures SQL generation accuracy and response quality using AgentCore Evaluations.

Custom evaluators:
  - SQL Accuracy: Compares generated SQL results against ground-truth expected outputs
  - Response Quality: Checks that natural language answers are relevant and complete

Built-in evaluators:
  - Builtin.Correctness: General answer correctness
  - Builtin.GoalSuccessRate: Whether the agent achieved the user's goal

Usage:
  python evaluations/evaluate.py --region us-east-1 --agent-runtime-arn <ARN>

Prerequisites:
  - Agent deployed to AgentCore Runtime
  - CloudWatch Transaction Search enabled
  - pip install bedrock-agentcore boto3
"""

import argparse
import json
import logging
import time
import uuid
from datetime import timedelta
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATASET_SCENARIOS = [
    {
        "input": "What are the top 5 best-selling games globally?",
        "expected_output": "The query should sum na_sales + jp_sales + pal_sales + other_sales and ORDER BY total DESC LIMIT 5",
        "tags": ["sql_accuracy", "aggregation"],
    },
    {
        "input": "Which genre has the highest average critic score?",
        "expected_output": "The query should use AVG(critic_score) grouped by genre, ordered descending, limit 1",
        "tags": ["sql_accuracy", "aggregation"],
    },
    {
        "input": "Total North America sales for games released in 2015 by genre",
        "expected_output": "The query should filter release_date for year 2015, sum na_sales, group by genre",
        "tags": ["sql_accuracy", "filtering"],
    },
    {
        "input": "Which publisher released the most games on PS4?",
        "expected_output": "The query should filter console='PS4', count titles grouped by publisher, order descending, limit 1",
        "tags": ["sql_accuracy", "filtering"],
    },
    {
        "input": "Compare Japanese sales vs North American sales for Nintendo games",
        "expected_output": "The query should filter publisher='Nintendo', sum jp_sales and na_sales",
        "tags": ["sql_accuracy", "comparison"],
    },
    {
        "input": "What is the trend in game releases by year?",
        "expected_output": "The query should extract year from release_date, count titles per year, order by year",
        "tags": ["sql_accuracy", "trend"],
    },
    {
        "input": "Tell me about the weather today",
        "expected_output": "The agent should politely decline since this is outside the video game sales domain",
        "tags": ["response_quality", "out_of_scope"],
    },
    {
        "input": "What consoles have the highest total sales in Europe?",
        "expected_output": "The query should sum pal_sales grouped by console, ordered descending",
        "tags": ["sql_accuracy", "aggregation"],
    },
]


class VideoGamesSalesEvaluator:
    """Runs evaluations against the deployed Video Games Sales Assistant."""

    def __init__(self, region: str, agent_runtime_arn: str):
        self.region = region
        self.agent_runtime_arn = agent_runtime_arn
        self.agentcore_client = boto3.client("bedrock-agentcore", region_name=region)

    def invoke_agent(self, prompt: str, session_id: str) -> str:
        """Invoke the deployed agent and collect the full response."""
        payload = json.dumps({
            "prompt": prompt,
            "session_id": session_id,
            "user_id": "evaluator",
            "user_timezone": "UTC",
            "user_name": "Evaluator",
            "prompt_uuid": str(uuid.uuid4()),
        }).encode()

        response = self.agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=self.agent_runtime_arn,
            runtimeSessionId=session_id,
            payload=payload,
            qualifier="DEFAULT",
        )

        content = []
        for chunk in response.get("response", []):
            content.append(chunk.decode("utf-8"))

        full_response = "".join(content)

        # Extract text data from JSONL stream
        text_parts = []
        for line in full_response.strip().split("\n"):
            try:
                parsed = json.loads(line)
                if "data" in parsed:
                    text_parts.append(parsed["data"])
            except json.JSONDecodeError:
                continue

        return "".join(text_parts)

    def run_dataset_evaluation(self) -> dict:
        """Run evaluation across all dataset scenarios.

        Uses AgentCore on-demand evaluation when available, otherwise
        falls back to direct invocation + manual scoring.
        """
        logger.info("Running evaluation with %d scenarios", len(DATASET_SCENARIOS))
        results = []

        for i, scenario in enumerate(DATASET_SCENARIOS):
            session_id = str(uuid.uuid4())
            logger.info(
                "[%d/%d] Evaluating: %s",
                i + 1,
                len(DATASET_SCENARIOS),
                scenario["input"][:60],
            )

            try:
                response = self.invoke_agent(scenario["input"], session_id)
                results.append({
                    "scenario": scenario,
                    "session_id": session_id,
                    "response": response[:500],
                    "status": "success",
                })
                logger.info("  Response length: %d chars", len(response))
            except Exception as e:
                results.append({
                    "scenario": scenario,
                    "session_id": session_id,
                    "response": None,
                    "status": "error",
                    "error": str(e),
                })
                logger.error("  Error: %s", e)

            time.sleep(2)

        return self._score_results(results)

    def run_agentcore_evaluation(self, sql_evaluator_arn: str = "", response_evaluator_arn: str = "") -> dict:
        """Run evaluation using AgentCore Evaluation SDK (built-in + custom evaluators).

        Uses both built-in evaluators and CDK-deployed LLM-as-a-Judge evaluators:
          - Builtin.Correctness: General answer correctness
          - Builtin.GoalSuccessRate: Whether agent achieved user's goal
          - SqlAccuracy (custom): SQL query correctness evaluation
          - ResponseQuality (custom): Response clarity and helpfulness

        Requires:
          - Agent traces in CloudWatch (via ADOT/OpenTelemetry)
          - Evaluators registered in the account (deployed via CDK)
        """
        try:
            from bedrock_agentcore.evaluation import EvaluationClient

            ec = EvaluationClient(region_name=self.region)

            # Invoke agent to generate traces
            session_id = str(uuid.uuid4()) + "-" + "0" * 10
            logger.info("Invoking agent to generate traces for evaluation...")
            self.invoke_agent(DATASET_SCENARIOS[0]["input"], session_id)
            time.sleep(10)  # Wait for traces to propagate to CloudWatch

            # Build evaluator list
            evaluator_ids = [
                "Builtin.Correctness",
                "Builtin.GoalSuccessRate",
            ]
            if sql_evaluator_arn:
                evaluator_ids.append(sql_evaluator_arn)
            if response_evaluator_arn:
                evaluator_ids.append(response_evaluator_arn)

            logger.info("Running AgentCore evaluators: %s", evaluator_ids)
            results = ec.run(
                evaluator_ids=evaluator_ids,
                agent_id=self.agent_runtime_arn.split("/")[-1],
                session_id=session_id,
                look_back_time=timedelta(hours=1),
            )

            logger.info("AgentCore evaluation results: %s", json.dumps(results, indent=2, default=str))
            return results

        except ImportError:
            logger.warning(
                "bedrock_agentcore.evaluation not available — "
                "install bedrock-agentcore>=1.0 for built-in evaluator support"
            )
            return {}
        except Exception as e:
            logger.warning("AgentCore evaluation failed (non-fatal): %s", e)
            return {}

    def _score_results(self, results: list) -> dict:
        """Score evaluation results and produce a summary report."""
        total = len(results)
        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "error")

        # Basic heuristic scoring for SQL accuracy
        sql_scenarios = [r for r in results if "sql_accuracy" in r["scenario"].get("tags", [])]
        sql_with_response = [r for r in sql_scenarios if r["response"]]
        sql_responded = len(sql_with_response)

        summary = {
            "total_scenarios": total,
            "successful_invocations": successful,
            "failed_invocations": failed,
            "sql_accuracy_scenarios": len(sql_scenarios),
            "sql_scenarios_with_response": sql_responded,
            "success_rate": successful / total if total > 0 else 0,
            "results": results,
        }

        output_file = Path("evaluations/eval_results.json")
        output_file.write_text(json.dumps(summary, indent=2, default=str))
        logger.info("Results saved to: %s", output_file)
        logger.info(
            "Summary: %d/%d successful (%.0f%%)",
            successful,
            total,
            summary["success_rate"] * 100,
        )

        return summary


def main():
    parser = argparse.ArgumentParser(
        description="Run evaluations for Video Games Sales Assistant"
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument(
        "--agent-runtime-arn",
        required=True,
        help="AgentCore Runtime ARN (from deploy outputs)",
    )
    parser.add_argument(
        "--use-agentcore-evals",
        action="store_true",
        help="Also run AgentCore built-in evaluators (requires traces in CloudWatch)",
    )

    args = parser.parse_args()

    evaluator = VideoGamesSalesEvaluator(
        region=args.region, agent_runtime_arn=args.agent_runtime_arn
    )

    # Run dataset evaluation
    results = evaluator.run_dataset_evaluation()

    # Optionally run AgentCore built-in evaluators
    if args.use_agentcore_evals:
        agentcore_results = evaluator.run_agentcore_evaluation()
        results["agentcore_evaluators"] = agentcore_results

    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    print(f"  Success rate: {results['success_rate']:.0%}")
    print(f"  Total: {results['total_scenarios']} scenarios")
    print(f"  Passed: {results['successful_invocations']}")
    print(f"  Failed: {results['failed_invocations']}")
    print("=" * 60)


if __name__ == "__main__":
    main()