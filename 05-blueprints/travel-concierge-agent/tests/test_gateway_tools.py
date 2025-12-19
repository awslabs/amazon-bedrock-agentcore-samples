#!/usr/bin/env python3
"""
Gateway Tools Test - CSV-based systematic testing

Tests MCP tools directly via gateway with expected input/output validation.
Uses CSV for test cases and results.

Usage:
    cd tests
    python test_gateway_tools.py
    python test_gateway_tools.py --category cart
    python test_gateway_tools.py --test GT001

Input CSV columns:
    test_id, category, tool_name, test_description, input_json,
    expected_output_contains, expected_output_type, validation_rule

Output CSV columns:
    All input columns + passed, duration_s, actual_output, error
"""

import sys
import json
import time
import argparse
import csv
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

import requests
from colorama import Fore, Style, init

sys.path.insert(0, str(Path(__file__).parent))
from utils import print_msg, print_section, get_agent_config

init(autoreset=True)

DEFAULT_INPUT_CSV = Path(__file__).parent / "gateway_tool_test_dataset.csv"
DEFAULT_OUTPUT_CSV = Path(__file__).parent / "gateway_tool_test_results.csv"


@dataclass
class TestCase:
    test_id: str
    category: str
    tool_name: str
    test_description: str
    action_description: str
    input_args: Dict[str, Any]
    expected_output_contains: str
    expected_output_type: str
    validation_rule: str


@dataclass
class TestResult:
    test_case: TestCase
    passed: bool
    duration: float
    actual_output: Any
    error: str = ""


class GatewayToolTester:
    """Tests gateway tools directly with CSV-based test cases."""

    def __init__(self, gateway_url: str, access_token: str, verbose: bool = False):
        self.gateway_url = gateway_url
        self.access_token = access_token
        self.verbose = verbose
        self.tool_map: Dict[str, str] = {}  # short_name -> full_name
        self.results: List[TestResult] = []

    def discover_tools(self) -> bool:
        """Discover available tools from gateway."""
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

        try:
            resp = requests.post(
                self.gateway_url, headers=headers, json=payload, timeout=30
            )
            result = resp.json()
            tools = result.get("result", {}).get("tools", [])

            # Map short names to full names
            for t in tools:
                full_name = t["name"]
                short_name = full_name.split("___")[-1]
                self.tool_map[short_name] = full_name

            return len(self.tool_map) > 0
        except Exception as e:
            print_msg(f"Tool discovery failed: {e}", "error")
            return False

    def call_tool(self, tool_name: str, args: Dict) -> Tuple[bool, Any, str]:
        """
        Call a tool via gateway.
        Returns: (success, result, error_message)
        """
        if tool_name not in self.tool_map:
            return False, None, f"Tool '{tool_name}' not found in gateway"

        full_name = self.tool_map[tool_name]
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": full_name, "arguments": args},
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

        try:
            resp = requests.post(
                self.gateway_url, headers=headers, json=payload, timeout=60
            )
            result = resp.json()

            if "error" in result:
                return False, None, str(result["error"])

            tool_result = result.get("result", {})

            # Check for tool-level error
            if tool_result.get("isError"):
                error_text = tool_result.get("content", [{}])[0].get(
                    "text", "Unknown error"
                )
                return False, None, f"Tool error: {error_text}"

            # Extract content
            content = tool_result.get("content", [])
            if content:
                text = content[0].get("text", "")
                try:
                    return True, json.loads(text), ""
                except json.JSONDecodeError:
                    return True, text, ""

            return True, None, ""
        except Exception as e:
            return False, None, str(e)

    def validate_output(self, result: Any, test_case: TestCase) -> Tuple[bool, str]:
        """
        Validate output against test case rules.
        Returns: (passed, error_message)
        """
        rule = test_case.validation_rule
        expected_type = test_case.expected_output_type
        expected_contains = test_case.expected_output_contains

        # Type validation
        if expected_type == "dict" and not isinstance(result, dict):
            return False, f"Expected dict, got {type(result).__name__}"
        if expected_type == "list" and not isinstance(result, list):
            return False, f"Expected list, got {type(result).__name__}"

        # Rule-based validation
        if rule == "no_error":
            return True, ""

        if rule == "not_empty":
            if result is None or result == "" or result == [] or result == {}:
                return False, "Result is empty"
            return True, ""

        if rule == "is_list":
            if isinstance(result, list):
                return True, ""
            return False, f"Expected list, got {type(result).__name__}"

        if rule.startswith("has_key:"):
            key = rule.split(":")[1]
            if isinstance(result, dict) and key in result:
                return True, ""
            return False, f"Missing key '{key}' in result"

        if rule.startswith("min_length:"):
            min_len = int(rule.split(":")[1])
            if isinstance(result, (list, str)) and len(result) >= min_len:
                return True, ""
            return False, f"Length {len(result) if result else 0} < {min_len}"

        if rule.startswith("contains:"):
            text = rule.split(":")[1]
            if text.lower() in str(result).lower():
                return True, ""
            return False, f"Result doesn't contain '{text}'"

        # Check expected_output_contains
        if expected_contains:
            if expected_contains.lower() in str(result).lower():
                return True, ""
            return False, f"Result doesn't contain '{expected_contains}'"

        return True, ""

    def load_test_cases(self, csv_path: Path) -> List[TestCase]:
        """Load test cases from CSV."""
        test_cases = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    input_args = json.loads(row["input_json"])
                except json.JSONDecodeError:
                    input_args = {}

                test_cases.append(
                    TestCase(
                        test_id=row["test_id"],
                        category=row["category"],
                        tool_name=row["tool_name"],
                        test_description=row["test_description"],
                        action_description=row.get("action_description", ""),
                        input_args=input_args,
                        expected_output_contains=row.get(
                            "expected_output_contains", ""
                        ),
                        expected_output_type=row.get("expected_output_type", "any"),
                        validation_rule=row.get("validation_rule", "no_error"),
                    )
                )
        return test_cases

    def run_test(self, test_case: TestCase) -> TestResult:
        """Run a single test case."""
        print(f"\n  {test_case.test_id}: {test_case.test_description}")
        print(f"     Tool: {test_case.tool_name}")
        if test_case.action_description:
            print(f"     Action: {test_case.action_description}")

        if self.verbose:
            print(f"     Input: {json.dumps(test_case.input_args)[:100]}...")

        start = time.time()
        success, result, error = self.call_tool(
            test_case.tool_name, test_case.input_args
        )
        duration = time.time() - start

        if not success:
            print(
                f"     {Fore.RED}✗ FAILED ({duration:.2f}s): {error}{Style.RESET_ALL}"
            )
            return TestResult(test_case, False, duration, None, error)

        # Validate output
        valid, validation_error = self.validate_output(result, test_case)

        if not valid:
            print(
                f"     {Fore.RED}✗ FAILED ({duration:.2f}s): {validation_error}{Style.RESET_ALL}"
            )
            return TestResult(test_case, False, duration, result, validation_error)

        print(f"     {Fore.GREEN}✓ PASSED ({duration:.2f}s){Style.RESET_ALL}")
        if self.verbose:
            preview = (
                str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
            )
            print(f"     Output: {preview}")

        return TestResult(test_case, True, duration, result, "")

    def run_all(
        self,
        test_cases: List[TestCase],
        filter_category: str = None,
        filter_test_id: str = None,
    ) -> List[TestResult]:
        """Run all test cases with optional filtering."""
        filtered = test_cases

        if filter_category:
            filtered = [t for t in filtered if t.category == filter_category]
        if filter_test_id:
            filtered = [t for t in filtered if t.test_id == filter_test_id]

        if not filtered:
            print_msg("No matching test cases found", "error")
            return []

        print_section(f"Gateway Tool Tests ({len(filtered)} tests)")

        for test_case in filtered:
            result = self.run_test(test_case)
            self.results.append(result)

        return self.results

    def print_summary(self):
        """Print test results summary."""
        print_section("Results Summary", width=70)

        # Group by category
        by_category: Dict[str, List[TestResult]] = {}
        for r in self.results:
            cat = r.test_case.category
            by_category.setdefault(cat, []).append(r)

        total_passed = 0
        total_tests = 0

        for category, results in sorted(by_category.items()):
            passed = sum(1 for r in results if r.passed)
            total = len(results)
            total_passed += passed
            total_tests += total

            pct = (passed / total * 100) if total > 0 else 0
            color = (
                Fore.GREEN
                if passed == total
                else Fore.YELLOW if passed > 0 else Fore.RED
            )
            print(
                f"\n{color}{category.upper()}: {passed}/{total} ({pct:.0f}%){Style.RESET_ALL}"
            )

            for r in results:
                icon = (
                    f"{Fore.GREEN}✓{Style.RESET_ALL}"
                    if r.passed
                    else f"{Fore.RED}✗{Style.RESET_ALL}"
                )
                print(f"  {icon} {r.test_case.test_id}: {r.test_case.test_description}")

        print(f"\n{'=' * 70}")
        pct = (total_passed / total_tests * 100) if total_tests > 0 else 0
        print(f"Total: {total_passed}/{total_tests} tests passed ({pct:.0f}%)")

    def save_results_csv(self, output_path: Path):
        """Save results to CSV."""
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "test_id",
                    "category",
                    "tool_name",
                    "test_description",
                    "action_description",
                    "input_json",
                    "expected_output_contains",
                    "expected_output_type",
                    "validation_rule",
                    "passed",
                    "duration_s",
                    "actual_output",
                    "error",
                ]
            )

            for r in self.results:
                tc = r.test_case
                output_str = (
                    json.dumps(r.actual_output)[:1000] if r.actual_output else ""
                )

                writer.writerow(
                    [
                        tc.test_id,
                        tc.category,
                        tc.tool_name,
                        tc.test_description,
                        tc.action_description,
                        json.dumps(tc.input_args),
                        tc.expected_output_contains,
                        tc.expected_output_type,
                        tc.validation_rule,
                        "PASS" if r.passed else "FAIL",
                        f"{r.duration:.2f}",
                        output_str,
                        r.error,
                    ]
                )

        print_msg(f"Results saved to {output_path}", "success")


def main():
    parser = argparse.ArgumentParser(
        description="Test gateway tools with CSV-based test cases"
    )
    parser.add_argument("--input", "-i", type=str, help="Input CSV file")
    parser.add_argument("--output", "-o", type=str, help="Output CSV file")
    parser.add_argument(
        "--category",
        "-c",
        type=str,
        help="Filter by category (cart, travel, itinerary)",
    )
    parser.add_argument("--test", "-t", type=str, help="Run specific test by ID")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print_section("Gateway Tool Testing", width=70)

    # Load config
    print_msg("Loading gateway configuration...", "info")
    try:
        config = get_agent_config()
        gateway_url = config["gateway_url"]
        access_token = config["access_token"]
        print(f"Gateway URL: {gateway_url}")
        print_msg("Configuration loaded", "success")
    except Exception as e:
        print_msg(f"Setup failed: {e}", "error")
        sys.exit(1)

    # Create tester
    tester = GatewayToolTester(gateway_url, access_token, verbose=args.verbose)

    # Discover tools
    print_msg("Discovering tools...", "info")
    if not tester.discover_tools():
        print_msg("No tools found in gateway", "error")
        sys.exit(1)
    print_msg(f"Found {len(tester.tool_map)} tools", "success")

    # Load test cases
    input_path = Path(args.input) if args.input else DEFAULT_INPUT_CSV
    if not input_path.exists():
        print_msg(f"Input file not found: {input_path}", "error")
        sys.exit(1)

    test_cases = tester.load_test_cases(input_path)
    print_msg(f"Loaded {len(test_cases)} test cases from {input_path}", "info")

    # Run tests
    tester.run_all(test_cases, filter_category=args.category, filter_test_id=args.test)
    tester.print_summary()

    # Save results
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_CSV
    tester.save_results_csv(output_path)

    # Exit code
    all_passed = all(r.passed for r in tester.results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
