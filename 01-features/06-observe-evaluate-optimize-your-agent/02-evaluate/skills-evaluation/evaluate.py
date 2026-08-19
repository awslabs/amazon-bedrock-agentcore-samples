"""Evaluate skill selection and instruction following for the HR Assistant.

This follows the on-demand flow from the AgentCore documentation: invoke the agent,
collect its OpenTelemetry session records, and send those records to the Evaluate API.
AgentCore detects each native Strands ``skills`` tool call and returns one result per
skill invocation.

Prerequisite:
    python ../utils/deploy.py --skills-dir skills --config-output agent_config.json

Usage:
    python evaluate.py [--region REGION] [--config PATH] [--wait SECONDS]
    python evaluate.py --prompt "..." --expected-skill SKILL_NAME
"""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from boto3.session import Session

_SCRIPT_DIR = Path(__file__).parent
_DEFAULT_CONFIG = _SCRIPT_DIR / "agent_config.json"
_RESULTS_DIR = _SCRIPT_DIR / "results"
_SPANS_LOG_GROUP = "aws/spans"
_EVALUATOR_IDS = (
    "Builtin.SkillSelectionAccuracy",
    "Builtin.SkillInstructionFollowing",
)
# The positive prompts name the expected skill, matching the reference implementation
# and keeping this introductory evaluator sample deterministic.
_SCENARIOS = (
    {
        "name": "pto-planning",
        "prompt": (
            "I am employee EMP-001. How many PTO days do I have, and can I take September 14 through "
            "September 16, 2026 off for a family event? Please submit the request, explain the applicable "
            "rules, and use the pto-planning skill."
        ),
        "expected_skill": "pto-planning",
    },
    {
        "name": "benefits-advisor",
        "prompt": (
            "What does Acme's health insurance cover, who is eligible, and what does the employee pay? "
            "Use the benefits-advisor skill."
        ),
        "expected_skill": "benefits-advisor",
    },
    {
        "name": "no-skill-control",
        "prompt": "Show the January 2026 pay stub for employee EMP-001.",
        "expected_skill": None,
    },
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the built-in AgentCore skill evaluators")
    parser.add_argument("--region", default=None, help="AWS region (defaults to the deployment config)")
    parser.add_argument("--config", default=str(_DEFAULT_CONFIG), help="Path to the skill-enabled agent config")
    parser.add_argument("--wait", type=int, default=150, help="Seconds to wait for telemetry (default: 150)")
    parser.add_argument("--prompt", default=None, help="Run one custom prompt instead of the built-in scenarios")
    parser.add_argument(
        "--expected-skill",
        choices=("pto-planning", "benefits-advisor", "none"),
        default=None,
        help="Expected skill for --prompt; use 'none' when no skill should load",
    )
    args = parser.parse_args()
    if bool(args.prompt) != bool(args.expected_skill):
        parser.error("--prompt and --expected-skill must be provided together")
    return args


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Agent config not found at {path}. Deploy the skill-enabled agent first.")
    config = json.loads(path.read_text())
    if not config.get("skills_enabled"):
        raise ValueError(f"{path} is not a skill-enabled deployment. Deploy with --skills-dir skills.")
    return config


def _invoke_agent(client: Any, agent_arn: str, session_id: str, prompt: str) -> str:
    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        qualifier="DEFAULT",
        runtimeSessionId=session_id,
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
    )
    raw = response["response"].read().decode("utf-8")
    parts: list[str] = []
    for line in raw.splitlines():
        if not line.startswith("data: "):
            continue
        chunk: Any = line[len("data: ") :]
        try:
            chunk = json.loads(chunk)
        except json.JSONDecodeError:
            pass
        parts.append(str(chunk))
    return "".join(parts) if parts else raw


def _query_log_group(
    logs_client: Any,
    log_group: str,
    session_id: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    query = f"""fields @message
| filter @message like "{session_id}"
| sort @timestamp asc
| limit 1000"""
    response = logs_client.start_query(
        logGroupName=log_group,
        startTime=int(start.timestamp()),
        endTime=int(end.timestamp()),
        queryString=query,
    )
    query_id = response["queryId"]

    for _ in range(30):
        result = logs_client.get_query_results(queryId=query_id)
        if result["status"] == "Complete":
            records = []
            for row in result.get("results", []):
                message = next((field["value"] for field in row if field["field"] == "@message"), None)
                if not message:
                    continue
                try:
                    document = json.loads(message)
                except json.JSONDecodeError:
                    continue
                if isinstance(document, dict):
                    records.append(document)
            return records
        if result["status"] in {"Failed", "Cancelled", "Timeout"}:
            raise RuntimeError(f"CloudWatch query for {log_group} ended with status {result['status']}")
        time.sleep(2)

    logs_client.stop_query(queryId=query_id)
    raise TimeoutError(f"CloudWatch query for {log_group} timed out")


def _fetch_session_records(
    logs_client: Any,
    runtime_log_group: str,
    session_id: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    records = []
    for log_group in (runtime_log_group, _SPANS_LOG_GROUP):
        records.extend(_query_log_group(logs_client, log_group, session_id, start, end))
    if not records:
        raise RuntimeError(
            f"No telemetry found for session {session_id}. Confirm CloudWatch Transaction Search is enabled."
        )
    return records


def _skill_span_ids(records: list[dict[str, Any]]) -> list[str]:
    return [
        str(record["spanId"])
        for record in records
        if record.get("spanId")
        and isinstance(record.get("attributes"), dict)
        and record["attributes"].get("gen_ai.tool.name") == "skills"
    ]


def _evaluate(client: Any, evaluator_id: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    response = client.evaluate(
        evaluatorId=evaluator_id,
        evaluationInput={"sessionSpans": records},
    )
    return response.get("evaluationResults", [])


def _print_results(scenario_name: str, evaluator_id: str, results: list[dict[str, Any]]) -> None:
    if not results:
        print(f"  {scenario_name:<20} {evaluator_id:<38} SKIPPED (0 results)")
        return
    for result in results:
        value = result.get("value", "N/A")
        label = result.get("label", "N/A")
        print(f"  {scenario_name:<20} {evaluator_id:<38} {value!s:<5} {label}")
        explanation = result.get("explanation") or result.get("errorMessage")
        if explanation:
            print(f"    {str(explanation)[:180]}")


def main() -> int:
    args = _parse_args()
    try:
        config = _load_config(Path(args.config).expanduser().resolve())
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    config_region = config.get("region")
    if args.region and config_region and args.region != config_region:
        print(
            f"ERROR: --region {args.region} does not match the deployed runtime region {config_region}. "
            f"Omit --region or pass --region {config_region}.",
            file=sys.stderr,
        )
        return 1

    region = args.region or config_region or Session().region_name or "us-east-1"
    agentcore_client = boto3.client("bedrock-agentcore", region_name=region)
    logs_client = boto3.client("logs", region_name=region)
    _RESULTS_DIR.mkdir(exist_ok=True)

    scenarios = _SCENARIOS
    if args.prompt:
        expected_skill = None if args.expected_skill == "none" else args.expected_skill
        scenarios = (
            {
                "name": "custom-prompt",
                "prompt": args.prompt,
                "expected_skill": expected_skill,
            },
        )

    print("=" * 88)
    print("HR Assistant — Agent Skills Evaluation")
    print("=" * 88)
    print(f"Region: {region}")
    print(f"Runtime: {config['agent_id']}")
    print(f"Skills: {', '.join(config.get('skills', []))}")

    sessions = []
    for scenario in scenarios:
        session_id = f"skill-eval-{uuid.uuid4()}"
        print(f"\n[Invoke] {scenario['name']} (session={session_id})")
        start = datetime.now(timezone.utc)
        response = _invoke_agent(agentcore_client, config["agent_arn"], session_id, scenario["prompt"])
        print(f"  Response: {response[:180]}")
        sessions.append({**scenario, "session_id": session_id, "start": start, "response": response})

    print(f"\nWaiting {args.wait}s for AgentCore telemetry ingestion ...")
    time.sleep(args.wait)

    output: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "region": region,
        "agent_id": config["agent_id"],
        "evaluators": list(_EVALUATOR_IDS),
        "scenarios": [],
    }
    failures = []

    for session in sessions:
        records = _fetch_session_records(
            logs_client,
            config["cw_log_group"],
            session["session_id"],
            session["start"],
            datetime.now(timezone.utc),
        )
        skill_span_ids = _skill_span_ids(records)
        print(f"\n[Evaluate] {session['name']}: {len(records)} records, {len(skill_span_ids)} skill invocation(s)")

        scenario_output = {
            "name": session["name"],
            "session_id": session["session_id"],
            "prompt": session["prompt"],
            "expected_skill": session["expected_skill"],
            "response": session["response"],
            "skill_span_ids": skill_span_ids,
            "evaluations": {},
        }

        if session["expected_skill"] and not skill_span_ids:
            failures.append(f"{session['name']}: expected a skills tool-call span")
        if not session["expected_skill"] and skill_span_ids:
            failures.append(f"{session['name']}: expected no skill invocation")

        for evaluator_id in _EVALUATOR_IDS:
            results = _evaluate(agentcore_client, evaluator_id, records)
            scenario_output["evaluations"][evaluator_id] = results
            _print_results(session["name"], evaluator_id, results)

            expected_count = len(skill_span_ids)
            if len(results) != expected_count:
                failures.append(
                    f"{session['name']} / {evaluator_id}: expected {expected_count} result(s), got {len(results)}"
                )
            for result in results:
                if result.get("errorCode"):
                    failures.append(
                        f"{session['name']} / {evaluator_id}: {result['errorCode']} - {result.get('errorMessage', '')}"
                    )

        output["scenarios"].append(scenario_output)

    output["validation_failures"] = failures
    results_path = _RESULTS_DIR / "skill_evaluation_results.json"
    results_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nResults saved to {results_path}")

    if failures:
        print("\nValidation failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\nValidation passed: one result per skill invocation, and no results for the control.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
