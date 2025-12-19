#!/usr/bin/env python3
"""
Agent Trajectory Tests - Generic & Extensible

Tests any agent against expected tool call trajectories.
Supports CSV input/output for easy test case management.

Usage:
    cd tests
    python test_agent_trajectories.py
    python test_agent_trajectories.py --session session_001
    python test_agent_trajectories.py --verbose

Input CSV columns:
    session_id, user_id, description, turn, question, expected_agent,
    expected_tools, expected_tools_input, expected_nested_tools, expected_answer,
    test_description

Output CSV columns:
    All input columns + passed, duration_s, actual_tools, actual_tools_input,
    actual_tools_output, actual_nested_tools, nested_tools_match, actual_answer, errors
"""

import sys
import json
import time
import argparse
import csv
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field

import requests
from colorama import Fore, Style, init

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    print_msg, print_section, get_agent_config,
    generate_session_id, REGION
)

init(autoreset=True)

# Default paths
DEFAULT_INPUT_CSV = Path(__file__).parent / "agent_test_dataset.csv"
DEFAULT_OUTPUT_CSV = Path(__file__).parent / "agent_test_results.csv"


@dataclass
class NestedToolCall:
    """Represents a nested tool call from a subagent."""
    tool_name: str
    input_args: Dict[str, Any] = field(default_factory=dict)
    output: Any = None


@dataclass
class ToolCall:
    """Represents a captured tool call from agent response."""
    tool_name: str
    input_args: Dict[str, Any]
    output: Any = None
    tool_use_id: str = ""
    timestamp: float = 0.0
    nested_tools: List[NestedToolCall] = field(default_factory=list)  # Full nested tool details


@dataclass 
class TurnResult:
    """Result of a single conversation turn."""
    turn: int
    question: str
    expected_agent: str
    test_description: str = ""
    actual_tool_calls: List[ToolCall] = field(default_factory=list)
    expected_tool_calls: List[Dict] = field(default_factory=list)
    expected_nested_tools: List[str] = field(default_factory=list)
    actual_nested_tools: List[str] = field(default_factory=list)
    agent_response: str = ""
    passed: bool = False
    errors: List[str] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class SessionResult:
    """Result of a complete test session."""
    session_id: str
    user_id: str
    description: str
    turns: List[TurnResult] = field(default_factory=list)
    passed: bool = True


class AgentTrajectoryTester:
    """Generic agent trajectory tester - works with any agent."""
    
    def __init__(self, config: Dict, verbose: bool = False, subagent_names: List[str] = None):
        self.config = config
        self.verbose = verbose
        # Configurable subagent names to exclude from nested tools
        self.subagent_names = subagent_names or []
        self.results: List[SessionResult] = []

    def load_dataset_csv(self, path: Path) -> List[Dict]:
        """
        Load test dataset from CSV file.
        
        CSV columns: session_id, user_id, description, turn, question, 
                     expected_agent, expected_tools, expected_tools_input,
                     expected_nested_tools, expected_answer, test_description
        """
        sessions = {}
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row['session_id']
                if sid not in sessions:
                    sessions[sid] = {
                        'session_id': sid,
                        'user_id': row.get('user_id', sid),
                        'description': row.get('description', ''),
                        'turns': []
                    }
                
                # Parse expected tools from CSV
                exp_tools = []
                if row.get('expected_tools'):
                    tool_names = [t.strip() for t in row['expected_tools'].split(',')]
                    try:
                        tool_inputs = json.loads(row.get('expected_tools_input', '[]'))
                    except (json.JSONDecodeError, ValueError, TypeError):
                        tool_inputs = [{}] * len(tool_names)
                    
                    for i, name in enumerate(tool_names):
                        inp = tool_inputs[i].get('input', {}) if i < len(tool_inputs) else {}
                        exp_tools.append({'tool': name, 'input': inp})
                
                # Parse nested tools
                nested = []
                if row.get('expected_nested_tools'):
                    nested = [t.strip() for t in row['expected_nested_tools'].split(',')]
                
                sessions[sid]['turns'].append({
                    'turn': int(row.get('turn', len(sessions[sid]['turns']) + 1)),
                    'question': row['question'],
                    'expected_trajectory': {
                        'agent': row.get('expected_agent', 'unknown'),
                        'tool_sequence': exp_tools,
                        'nested_tools': nested
                    },
                    'expected_answer': row.get('expected_answer', ''),
                    'test_description': row.get('test_description', '')
                })
        
        return list(sessions.values())

    def invoke_agent(self, prompt: str, user_id: str, session_id: str) -> Tuple[str, List[ToolCall]]:
        """Invoke the remote agent and capture tool calls from streaming response."""
        runtime_arn = self.config["runtime_arn"]
        access_token = self.config["access_token"]
        
        encoded_arn = requests.utils.quote(runtime_arn, safe="")
        url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id
        }
        
        payload = {"prompt": prompt, "user_id": user_id, "session_id": session_id}
        response = requests.post(url, headers=headers, json=payload, stream=True, timeout=180)
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text[:500]}")
        
        return self._parse_streaming_response(response)
    
    def _parse_streaming_response(self, response) -> Tuple[str, List[ToolCall]]:
        """Parse streaming response to extract text and tool calls."""
        tool_calls = []
        tool_calls_by_id = {}
        text_content = ""
        current_tool_name = None
        current_tool_input = {}
        seen_tools = set()
        streaming_started = False
        
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            
            raw_line = line[6:] if line.startswith("data: ") else line
            
            if self.verbose and "tool" in raw_line.lower():
                print(f"       [DEBUG] {raw_line[:200]}")
            
            try:
                data = json.loads(raw_line)
                if not isinstance(data, dict):
                    continue
                
                # Extract text content
                if "data" in data and isinstance(data["data"], str):
                    chunk = data["data"]
                    text_content += chunk
                    if self.verbose:
                        if not streaming_started:
                            print(f"\n     {Fore.CYAN}─── Agent Response ───{Style.RESET_ALL}")
                            streaming_started = True
                        print(chunk, end='', flush=True)

                # Capture tool use from current_tool_use (just track the tool name, input comes later)
                if "current_tool_use" in data:
                    tool_info = data["current_tool_use"]
                    if tool_info and isinstance(tool_info, dict):
                        tool_name = tool_info.get("name", "")
                        # Only add tool if not seen - don't capture partial input from streaming
                        if tool_name and tool_name not in seen_tools:
                            seen_tools.add(tool_name)
                            tool_calls.append(ToolCall(
                                tool_name=tool_name,
                                input_args={},  # Will be filled from message event
                                timestamp=time.time()
                            ))
                
                # Capture nested tools from tool_stream events
                if data.get("type") == "tool_stream":
                    tool_stream_event = data.get("tool_stream_event", {})
                    if not isinstance(tool_stream_event, dict):
                        continue
                    inner_data = tool_stream_event.get("data", {})
                    
                    if isinstance(inner_data, dict) and "current_tool_use" in inner_data:
                        nested_info = inner_data["current_tool_use"]
                        if nested_info and isinstance(nested_info, dict):
                            nested_name = nested_info.get("name", "")
                            nested_input = nested_info.get("input", {})
                            # Skip subagent names (configurable)
                            if nested_name and nested_name not in self.subagent_names:
                                # Normalize gateway names: gateway_xxx___tool -> tool
                                if "___" in nested_name:
                                    nested_name = nested_name.split("___")[-1]
                                if tool_calls:
                                    # Check if we already have this nested tool
                                    existing = None
                                    for nt in tool_calls[-1].nested_tools:
                                        if nt.tool_name == nested_name:
                                            existing = nt
                                            break
                                    if existing:
                                        # Update input if we have more complete data
                                        if nested_input and isinstance(nested_input, dict) and len(str(nested_input)) > len(str(existing.input_args)):
                                            existing.input_args = nested_input
                                    else:
                                        # Add new nested tool
                                        tool_calls[-1].nested_tools.append(NestedToolCall(
                                            tool_name=nested_name,
                                            input_args=nested_input if isinstance(nested_input, dict) else {}
                                        ))
                                        if self.verbose:
                                            print(f"\n     {Fore.YELLOW}[NESTED] {nested_name}{Style.RESET_ALL}")
                    
                    # Capture nested tool result from tool_stream
                    if isinstance(inner_data, dict) and "result" in inner_data:
                        result_text = str(inner_data.get("result", ""))
                        # Assign to most recent nested tool without output
                        if tool_calls and tool_calls[-1].nested_tools:
                            for nt in reversed(tool_calls[-1].nested_tools):
                                if not nt.output:
                                    nt.output = result_text[:2000]
                                    break

                # Capture from message content (toolUse/toolResult)
                message = data.get("message", {})
                if isinstance(message, dict) and message.get("content"):
                    content = message.get("content", [])
                    if not isinstance(content, list):
                        content = []
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        
                        if "toolUse" in block:
                            tu = block["toolUse"]
                            name = tu.get("name", "")
                            inp = tu.get("input", {})
                            tid = tu.get("toolUseId", "")
                            if name and inp:  # Only process if we have complete input
                                if tid and tid in tool_calls_by_id:
                                    tool_calls_by_id[tid].input_args = inp
                                elif name not in seen_tools:
                                    seen_tools.add(name)
                                    tc = ToolCall(tool_name=name, input_args=inp, tool_use_id=tid, timestamp=time.time())
                                    tool_calls.append(tc)
                                    if tid:
                                        tool_calls_by_id[tid] = tc
                                else:
                                    # Update existing tool call with complete input
                                    for tc in tool_calls:
                                        if tc.tool_name == name:
                                            tc.input_args = inp
                                            tc.tool_use_id = tid
                                            if tid:
                                                tool_calls_by_id[tid] = tc
                                            break
                        
                        if "toolResult" in block:
                            tr = block["toolResult"]
                            tid = tr.get("toolUseId", "")
                            result_content = tr.get("content", [])
                            result_text = ""
                            if isinstance(result_content, list):
                                for rc in result_content:
                                    if isinstance(rc, dict) and "text" in rc:
                                        result_text += rc["text"]
                            
                            if tid and tid in tool_calls_by_id:
                                tool_calls_by_id[tid].output = result_text[:2000]
                            elif result_text and tool_calls:
                                tool_calls[-1].output = result_text[:2000]

                # Bedrock event format
                event = data.get("event", {})
                if isinstance(event, dict):
                    tu = event.get("contentBlockStart", {}).get("start", {}).get("toolUse", {})
                    if tu and tu.get("name"):
                        current_tool_name = tu.get("name")
                        current_tool_input = {}
                    
                    delta = event.get("contentBlockDelta", {}).get("delta", {})
                    if delta.get("toolUse", {}).get("input"):
                        try:
                            inp = delta["toolUse"]["input"]
                            current_tool_input = json.loads(inp) if isinstance(inp, str) else inp
                        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                            pass
                    
                    if event.get("contentBlockStop") and current_tool_name:
                        if current_tool_name not in seen_tools:
                            seen_tools.add(current_tool_name)
                            tool_calls.append(ToolCall(
                                tool_name=current_tool_name,
                                input_args=current_tool_input,
                                timestamp=time.time()
                            ))
                        current_tool_name = None
                        current_tool_input = {}
                    
                    delta_text = delta.get("text", "")
                    if delta_text:
                        text_content += delta_text
                        if self.verbose:
                            if not streaming_started:
                                print(f"\n     {Fore.CYAN}─── Agent Response ───{Style.RESET_ALL}")
                                streaming_started = True
                            print(delta_text, end='', flush=True)
                            
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        
        if self.verbose and streaming_started:
            print(f"\n     {Fore.CYAN}─── End ───{Style.RESET_ALL}")
        
        # Deduplicate
        unique = {}
        for tc in tool_calls:
            if tc.tool_name not in unique or (tc.input_args and not unique[tc.tool_name].input_args):
                unique[tc.tool_name] = tc
        
        return text_content, list(unique.values())

    def validate_tool_calls(self, actual: List[ToolCall], expected: List[Dict]) -> Tuple[bool, List[str]]:
        """Validate actual tool calls against expected trajectory."""
        errors = []
        
        def normalize(name: str) -> str:
            if "___" in name:
                name = name.split("___")[-1]
            return name
        
        expected_tools = [normalize(t['tool']) for t in expected]
        actual_tools = [normalize(t.tool_name) for t in actual]
        
        for exp in expected_tools:
            if exp not in actual_tools:
                errors.append(f"Expected tool '{exp}' was not called")
        
        return len(errors) == 0, errors

    def run_turn(self, turn_data: Dict, user_id: str, session_id: str) -> TurnResult:
        """Run a single conversation turn."""
        turn_num = turn_data['turn']
        question = turn_data['question']
        expected = turn_data['expected_trajectory']
        test_desc = turn_data.get('test_description', '')
        
        result = TurnResult(
            turn=turn_num,
            question=question,
            expected_agent=expected.get('agent', 'unknown'),
            test_description=test_desc,
            expected_tool_calls=expected.get('tool_sequence', []),
            expected_nested_tools=expected.get('nested_tools', [])
        )
        
        print(f"\n  Turn {turn_num}: {question[:60]}...")
        if test_desc:
            print(f"     {Fore.CYAN}Testing: {test_desc}{Style.RESET_ALL}")
        
        start = time.time()
        try:
            response_text, tool_calls = self.invoke_agent(question, user_id, session_id)
            result.duration = time.time() - start
            result.agent_response = response_text
            result.actual_tool_calls = tool_calls
            
            # Collect nested tool names for comparison
            all_nested_names = []
            for tc in tool_calls:
                for nt in tc.nested_tools:
                    if nt.tool_name not in all_nested_names:
                        all_nested_names.append(nt.tool_name)
            result.actual_nested_tools = all_nested_names
            
            passed, errors = self.validate_tool_calls(tool_calls, result.expected_tool_calls)
            result.passed = passed
            result.errors = errors
            
            self._print_comparison(turn_data, result)
                    
        except Exception as e:
            result.duration = time.time() - start
            result.passed = False
            result.errors = [str(e)]
            print(f"     {Fore.RED}✗ ERROR: {e}{Style.RESET_ALL}")
        
        return result

    def _print_comparison(self, turn_data: Dict, result: TurnResult):
        """Print comparison of expected vs actual."""
        expected = turn_data['expected_trajectory']
        
        if result.passed:
            print(f"     {Fore.GREEN}✓ PASSED ({result.duration:.2f}s){Style.RESET_ALL}")
        else:
            print(f"     {Fore.RED}✗ FAILED ({result.duration:.2f}s){Style.RESET_ALL}")
            for err in result.errors:
                print(f"       - {err}")
        
        expected_tools = [t['tool'] for t in expected.get('tool_sequence', [])]
        actual_tools = [t.tool_name for t in result.actual_tool_calls]
        
        print(f"\n     {Fore.CYAN}─── Tools ───{Style.RESET_ALL}")
        print(f"     Expected: {expected_tools}")
        print(f"     Actual:   {actual_tools}")
        
        exp_nested = expected.get('nested_tools', [])
        if exp_nested or result.actual_nested_tools:
            print(f"\n     {Fore.CYAN}─── Nested Tools ───{Style.RESET_ALL}")
            print(f"     Expected: {exp_nested}")
            print(f"     Actual:   {result.actual_nested_tools}")

    def run_session(self, session_data: Dict) -> SessionResult:
        """Run a complete test session."""
        session_id = generate_session_id()
        user_id = session_data['user_id']
        
        result = SessionResult(
            session_id=session_data['session_id'],
            user_id=user_id,
            description=session_data['description']
        )
        
        print(f"\n{'─' * 60}")
        print(f"📋 {session_data['session_id']}: {session_data['description']}")
        print(f"   User: {user_id} | Session: {session_id[:8]}...")
        
        for turn_data in session_data['turns']:
            turn_result = self.run_turn(turn_data, user_id, session_id)
            result.turns.append(turn_result)
            if not turn_result.passed:
                result.passed = False
        
        return result

    def run_all(self, sessions: List[Dict], filter_session: Optional[str] = None) -> List[SessionResult]:
        """Run all test sessions."""
        if filter_session:
            sessions = [s for s in sessions if s['session_id'] == filter_session]
            if not sessions:
                print_msg(f"Session '{filter_session}' not found", "error")
                return []
        
        print_section(f"Agent Trajectory Tests ({len(sessions)} sessions)")
        
        for session_data in sessions:
            result = self.run_session(session_data)
            self.results.append(result)
        
        return self.results

    def print_summary(self):
        """Print test results summary."""
        print_section("Results Summary", width=70)
        
        total_turns = sum(len(r.turns) for r in self.results)
        passed_turns = sum(sum(1 for t in r.turns if t.passed) for r in self.results)
        
        for result in self.results:
            icon = f"{Fore.GREEN}✓{Style.RESET_ALL}" if result.passed else f"{Fore.RED}✗{Style.RESET_ALL}"
            turns_passed = sum(1 for t in result.turns if t.passed)
            print(f"  {icon} {result.session_id}: {turns_passed}/{len(result.turns)}")
        
        print(f"\n{'=' * 70}")
        pct = (passed_turns / total_turns * 100) if total_turns > 0 else 0
        print(f"Total: {passed_turns}/{total_turns} turns passed ({pct:.0f}%)")

    def save_results_csv(self, output_path: Path, input_sessions: List[Dict]):
        """Save results to CSV with all details."""
        # Build lookup for expected data
        expected_lookup = {}
        for session in input_sessions:
            for turn in session['turns']:
                key = (session['session_id'], turn['turn'])
                expected_lookup[key] = {
                    'expected_answer': turn.get('expected_answer', ''),
                    'expected_tools': turn['expected_trajectory'].get('tool_sequence', []),
                    'expected_agent': turn['expected_trajectory'].get('agent', ''),
                    'nested_tools': turn['expected_trajectory'].get('nested_tools', []),
                    'test_description': turn.get('test_description', '')
                }
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'session_id', 'user_id', 'turn', 'test_description', 'question', 
                'passed', 'duration_s', 'expected_agent', 'expected_tools', 
                'expected_tools_input', 'actual_tools', 'actual_tools_input', 
                'actual_tools_output', 'expected_nested_tools', 'actual_nested_tools', 
                'nested_tools_match', 'all_tool_details', 'expected_answer', 
                'actual_answer', 'errors'
            ])
            
            for session in self.results:
                for turn in session.turns:
                    key = (session.session_id, turn.turn)
                    expected = expected_lookup.get(key, {})
                    
                    exp_tools = expected.get('expected_tools', [])
                    exp_tools_names = ','.join([t['tool'] for t in exp_tools])
                    exp_tools_input = json.dumps([{'tool': t['tool'], 'input': t.get('input', {})} for t in exp_tools])
                    
                    act_tools = turn.actual_tool_calls
                    act_tools_names = ','.join([t.tool_name for t in act_tools])
                    act_tools_input = json.dumps([{'tool': t.tool_name, 'input': t.input_args} for t in act_tools])
                    act_tools_output = json.dumps([{'tool': t.tool_name, 'output': (t.output or '')[:500]} for t in act_tools])
                    
                    # Build comprehensive details with nested tool info
                    all_details = json.dumps([{
                        'tool': t.tool_name, 
                        'input': t.input_args,
                        'output': (t.output or '')[:1000], 
                        'nested_tools': [{
                            'tool': nt.tool_name,
                            'input': nt.input_args,
                            'output': (nt.output or '')[:500]
                        } for nt in t.nested_tools]
                    } for t in act_tools])
                    
                    exp_nested = expected.get('nested_tools', [])
                    nested_match = 'N/A'
                    if exp_nested:
                        missing = [t for t in exp_nested if t not in turn.actual_nested_tools]
                        nested_match = 'MATCH' if not missing else f'MISSING: {",".join(missing)}'
                    
                    writer.writerow([
                        session.session_id, session.user_id, turn.turn, 
                        turn.test_description, turn.question,
                        'PASS' if turn.passed else 'FAIL', f"{turn.duration:.2f}",
                        turn.expected_agent, exp_tools_names, exp_tools_input,
                        act_tools_names, act_tools_input, act_tools_output,
                        ','.join(exp_nested), ','.join(turn.actual_nested_tools), nested_match,
                        all_details, expected.get('expected_answer', '')[:500],
                        turn.agent_response[:500].replace('\n', ' '),
                        '; '.join(turn.errors) if turn.errors else ''
                    ])
        
        print_msg(f"Results saved to {output_path}", "success")


def main():
    parser = argparse.ArgumentParser(description="Test agent tool call trajectories")
    parser.add_argument("--input", "-i", type=str, help="Input CSV file")
    parser.add_argument("--output", "-o", type=str, help="Output CSV file")
    parser.add_argument("--session", "-s", type=str, help="Run specific session only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--subagents", type=str, help="Comma-separated subagent names to exclude from nested tools")
    args = parser.parse_args()
    
    print_section("Agent Trajectory Testing", width=70)
    
    # Load config
    print_msg("Loading agent configuration...", "info")
    try:
        config = get_agent_config()
        print(f"Runtime: {config['runtime_arn'][:50]}...")
        print_msg("Configuration loaded", "success")
    except Exception as e:
        print_msg(f"Setup failed: {e}", "error")
        sys.exit(1)
    
    # Parse subagent names
    subagent_names = []
    if args.subagents:
        subagent_names = [s.strip() for s in args.subagents.split(',')]
    else:
        # Default for shopping agent (can be overridden)
        subagent_names = ["shopping_assistant", "cart_manager"]
    
    # Determine input file
    input_path = Path(args.input) if args.input else DEFAULT_INPUT_CSV
    if not input_path.exists():
        print_msg(f"Input file not found: {input_path}", "error")
        sys.exit(1)
    
    # Load dataset
    tester = AgentTrajectoryTester(config, verbose=args.verbose, subagent_names=subagent_names)
    sessions = tester.load_dataset_csv(input_path)
    
    print_msg(f"Loaded {len(sessions)} sessions from {input_path}", "info")
    
    # Run tests
    tester.run_all(sessions, filter_session=args.session)
    tester.print_summary()
    
    # Save results
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_CSV
    tester.save_results_csv(output_path, sessions)
    
    # Exit code
    all_passed = all(r.passed for r in tester.results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
