# Development Guide

## Overview

This guide provides detailed information for developers who want to customize, extend, or learn from the Simple Dual Observability Tutorial code.

## Code Structure

### Project Organization

```
simple-dual-observability/
│
├── agent/
│   ├── weather_time_agent.py          # Core agent implementation
│   ├── strands_agent_config.json      # Agent deployment configuration
│   └── __init__.py
│
├── tools/
│   ├── weather_tool.py                # Weather tool implementation
│   ├── time_tool.py                   # Time tool implementation
│   ├── calculator_tool.py             # Calculator tool implementation
│   └── __init__.py
│
├── simple_observability.py            # Main demo script
│
├── scripts/
│   ├── deploy_agent.sh                # Deploy agent to Runtime
│   ├── setup_cloudwatch.sh            # Configure CloudWatch
│   ├── setup_braintrust.sh            # Configure Braintrust
│   ├── setup_all.sh                   # Complete setup
│   └── cleanup.sh                     # Resource cleanup
│
├── dashboards/
│   ├── cloudwatch-dashboard.json      # CloudWatch dashboard config
│   └── braintrust-dashboard-export.json
│
└── docs/
    ├── design.md                      # Architecture documentation
    ├── braintrust-setup.md            # Braintrust guide
    ├── development.md                 # This file
    ├── troubleshooting.md             # Troubleshooting guide
    ├── observability-options.md       # Observability approaches and CloudWatch logs
    └── generated-files.md             # Generated files guide
```

## Local Testing

### Testing the Agent Locally

Before deploying to AgentCore Runtime, test the agent locally:

```bash
# Activate virtual environment
source .venv/bin/activate

# Test with single query
python -m agent.weather_time_agent "What's the weather in Seattle?"

# Test different scenarios
python -m agent.weather_time_agent "What time is it in Tokyo?"
python -m agent.weather_time_agent "Calculate 25 + 17"
python -m agent.weather_time_agent "Calculate factorial of 5"
```

**Note**: Local testing does not generate OTEL traces. Traces are only generated when running in AgentCore Runtime.

### Testing Individual Tools

Test tools in isolation:

```python
# In Python REPL or script
from tools import get_weather, get_time, calculator

# Test weather tool
result = get_weather(city="Seattle")
print(result)

# Test time tool
result = get_time(timezone="America/Los_Angeles")
print(result)

# Test calculator
result = calculator(operation="add", a=10, b=5)
print(result)

# Test error handling
result = calculator(operation="factorial", a=-5)
print(result)  # Should return error
```

### Testing with Mock Bedrock

For testing without Bedrock API calls:

```python
from unittest.mock import Mock, patch
from agent.weather_time_agent import WeatherTimeAgent

# Mock Bedrock client
with patch('boto3.client') as mock_client:
    mock_bedrock = Mock()
    mock_client.return_value = mock_bedrock

    # Configure mock response
    mock_bedrock.converse.return_value = {
        'output': {
            'message': {
                'content': [{'text': 'The weather in Seattle is sunny.'}]
            }
        },
        'stopReason': 'end_turn'
    }

    # Test agent
    agent = WeatherTimeAgent()
    response = agent.run("What's the weather in Seattle?")
    print(response)
```

## Adding New Tools

### Step 1: Create Tool Implementation

Create new file in `tools/` directory:

```python
# tools/stock_price_tool.py

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def get_stock_price(symbol: str) -> Dict[str, Any]:
    """
    Get current stock price for given symbol.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Dictionary with stock price data

    Example:
        >>> result = get_stock_price('AAPL')
        >>> print(result['price'])
        150.25
    """
    logger.info(f"Getting stock price for: {symbol}")

    # For demo: return simulated data
    # In production: call real stock price API
    result = {
        "symbol": symbol.upper(),
        "price": 150.25,
        "currency": "USD",
        "timestamp": "2024-01-15T10:30:00Z",
        "change_percent": "+2.5%"
    }

    logger.info(f"Stock price result: {result}")
    return result
```

### Step 2: Register Tool in Agent

Update `agent/weather_time_agent.py`:

```python
# Add to TOOL_SCHEMAS
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    # ... existing tools ...
    {
        "name": "get_stock_price",
        "description": "Get current stock price for a given ticker symbol",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., 'AAPL', 'GOOGL')"
                }
            },
            "required": ["symbol"]
        }
    }
]

# Add to _execute_tool method
def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    # Import new tool
    from tools import get_weather, get_time, calculator, get_stock_price

    # ... existing tool handling ...

    elif tool_name == "get_stock_price":
        result = get_stock_price(symbol=tool_input["symbol"])

    else:
        raise ValueError(f"Unknown tool: {tool_name}")

    return result
```

### Step 3: Test New Tool

```bash
# Test locally
python -m agent.weather_time_agent "What's the stock price of AAPL?"

# Test after deployment
python simple_observability.py \
  --agent-id $AGENTCORE_AGENT_ID \
  --scenario success
```

### Step 4: Update Tool Exports

Update `tools/__init__.py`:

```python
from .weather_tool import get_weather
from .time_tool import get_time
from .calculator_tool import calculator
from .stock_price_tool import get_stock_price

__all__ = [
    'get_weather',
    'get_time',
    'calculator',
    'get_stock_price'
]
```

## Customizing the Demo Script

### Adding Custom Scenarios

Extend `simple_observability.py` with new scenarios:

```python
def scenario_parallel_tools(
    client: boto3.client,
    agent_id: str,
    region: str
) -> None:
    """
    Scenario 4: Parallel tool execution.

    Demonstrates agent using multiple tools simultaneously.
    Expected to show parallel spans in trace.
    """
    logger.info("Starting Scenario 4: Parallel Tool Execution")

    session_id = _generate_session_id()
    query = "Get the weather and time for New York, London, and Tokyo"

    result = _invoke_agent(
        client=client,
        agent_id=agent_id,
        query=query,
        session_id=session_id
    )

    _print_result(result, "Scenario 4: Parallel Tool Execution")
    _print_observability_links(region, result["trace_id"])

    print("✓ Expected in traces:")
    print("   - Multiple tool executions")
    print("   - Some tools may execute in parallel")
    print("   - Trace shows concurrent spans")

# Add to main() function
if args.scenario in ["parallel", "all"]:
    scenario_parallel_tools(client, args.agent_id, args.region)
```

### Customizing Output Format

Modify `_print_result()` for different output:

```python
def _print_result_json(
    result: Dict[str, Any],
    scenario_name: str
) -> None:
    """Print result as JSON for programmatic use."""
    import json

    output = {
        "scenario": scenario_name,
        "output": result["output"],
        "trace_id": result["trace_id"],
        "session_id": result["session_id"],
        "elapsed_time": result["elapsed_time"]
    }

    print(json.dumps(output, indent=2))
```

### Adding Metrics Collection

Track custom metrics during execution:

```python
import time
from collections import defaultdict

class MetricsCollector:
    """Collect demo execution metrics."""

    def __init__(self):
        self.metrics = defaultdict(list)

    def record_latency(self, scenario: str, latency: float):
        self.metrics[f"{scenario}_latency"].append(latency)

    def record_tokens(self, scenario: str, tokens: int):
        self.metrics[f"{scenario}_tokens"].append(tokens)

    def print_summary(self):
        print("\n" + "=" * 80)
        print("METRICS SUMMARY")
        print("=" * 80)

        for metric_name, values in self.metrics.items():
            avg = sum(values) / len(values)
            print(f"{metric_name}: avg={avg:.2f}, count={len(values)}")

        print("=" * 80)

# Use in main()
metrics = MetricsCollector()

for scenario in scenarios:
    start = time.time()
    run_scenario(scenario)
    latency = time.time() - start
    metrics.record_latency(scenario, latency)

metrics.print_summary()
```

## Modifying Agent Behavior

### Adjusting Model Parameters

Change model behavior in `agent/weather_time_agent.py`:

```python
# In run() method, modify inferenceConfig:
response = self.bedrock.converse(
    modelId=self.model_id,
    messages=messages,
    system=self.system_prompt,
    toolConfig={"tools": [{"toolSpec": tool_spec} for tool_spec in TOOL_SCHEMAS]},
    inferenceConfig={
        "maxTokens": 1024,        # Reduce for shorter responses
        "temperature": 0.5,        # Lower for more deterministic
        "topP": 0.9,              # Nucleus sampling
        "stopSequences": ["\n\n"]  # Custom stop sequences
    }
)
```

### Customizing System Prompt

Modify agent personality and behavior:

```python
# In __init__ method:
self.system_prompt = [
    {
        "text": (
            "You are an expert assistant specializing in real-time data. "
            "Use available tools to provide accurate, up-to-date information. "
            "Always cite which tool you used for each piece of information. "
            "Be concise but thorough. "
            "If a tool returns an error, explain it clearly to the user."
        )
    }
]
```

### Adding Conversation Memory

Implement multi-turn conversations with memory:

```python
class WeatherTimeAgent:
    def __init__(self, ...):
        self.conversation_history = []  # Add conversation history

    def run(self, query: str, session_id: Optional[str] = None):
        # Initialize messages from history
        messages = self.conversation_history.copy()

        # Add new user message
        messages.append({
            "role": "user",
            "content": [{"text": query}]
        })

        # ... execute agentic loop ...

        # Save to history
        self.conversation_history = messages

        return final_text

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
```

## Extending OTEL Configuration

### Adding Custom Spans

Add custom instrumentation for specific operations:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]):
    # Create custom span
    with tracer.start_as_current_span(
        f"custom.tool.{tool_name}",
        attributes={
            "tool.name": tool_name,
            "tool.input": str(tool_input),
            "custom.attribute": "value"
        }
    ) as span:
        # Execute tool
        result = self._execute_tool_impl(tool_name, tool_input)

        # Add result to span
        span.set_attribute("tool.result_size", len(str(result)))

        return result
```

### Adding Custom Metrics

Export custom metrics via OTEL:

```python
from opentelemetry import metrics

meter = metrics.get_meter(__name__)

# Create counter
tool_calls_counter = meter.create_counter(
    "agent.tool_calls",
    description="Number of tool calls",
    unit="1"
)

# Increment in code
def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]):
    tool_calls_counter.add(1, {"tool.name": tool_name})
    # ... execute tool ...
```

### Configuring Additional Exporters

The Strands telemetry library supports configuring additional exporters via environment variables. To add more export destinations, set the appropriate OTEL environment variables:

```bash
# Configure OTEL to use multiple OTLP exporters
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# Braintrust (already configured by default if BRAINTRUST_API_KEY is set)
export BRAINTRUST_API_KEY=sk-xxxxx

# Add Datadog exporter
export OTEL_EXPORTER_OTLP_ENDPOINT=https://api.datadoghq.com/v1/traces
export DD_API_KEY=${DATADOG_API_KEY}

# Add Honeycomb exporter
export OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces
export HONEYCOMB_API_KEY=${HONEYCOMB_API_KEY}
```

For advanced configuration, consult the [OpenTelemetry Environment Variable Specification](https://opentelemetry.io/docs/specs/otel/protocol/exporter/).

## Testing Strategies

### Unit Testing

Create unit tests for tools:

```python
# tests/test_tools.py

import pytest
from tools import get_weather, get_time, calculator


class TestWeatherTool:
    def test_get_weather_returns_data(self):
        result = get_weather("Seattle")
        assert "city" in result
        assert result["city"] == "Seattle"
        assert "temperature" in result

    def test_get_weather_handles_empty_city(self):
        result = get_weather("")
        assert "error" in result


class TestCalculatorTool:
    def test_add_operation(self):
        result = calculator("add", 10, 5)
        assert result["result"] == 15

    def test_factorial_negative_number(self):
        result = calculator("factorial", -5)
        assert "error" in result

    @pytest.mark.parametrize("a,b,expected", [
        (10, 5, 15),
        (0, 0, 0),
        (-5, 5, 0),
    ])
    def test_add_various_inputs(self, a, b, expected):
        result = calculator("add", a, b)
        assert result["result"] == expected
```

### Integration Testing

Test agent end-to-end:

```python
# tests/test_agent.py

import pytest
from unittest.mock import Mock, patch
from agent.weather_time_agent import WeatherTimeAgent


class TestWeatherTimeAgent:
    @patch('boto3.client')
    def test_agent_handles_weather_query(self, mock_client):
        # Setup mock
        mock_bedrock = Mock()
        mock_client.return_value = mock_bedrock

        mock_bedrock.converse.return_value = {
            'output': {'message': {'content': [{'text': 'Sunny, 72F'}]}},
            'stopReason': 'end_turn'
        }

        # Test
        agent = WeatherTimeAgent()
        response = agent.run("What's the weather?")

        # Verify
        assert "Sunny" in response
        mock_bedrock.converse.assert_called_once()

    @patch('boto3.client')
    def test_agent_handles_tool_calling(self, mock_client):
        # Setup mock with tool calling
        mock_bedrock = Mock()
        mock_client.return_value = mock_bedrock

        # First response: tool use
        # Second response: final answer
        mock_bedrock.converse.side_effect = [
            {
                'output': {
                    'message': {
                        'content': [{
                            'toolUse': {
                                'toolUseId': 'tool-1',
                                'name': 'get_weather',
                                'input': {'city': 'Seattle'}
                            }
                        }]
                    }
                },
                'stopReason': 'tool_use'
            },
            {
                'output': {'message': {'content': [{'text': 'Weather is sunny'}]}},
                'stopReason': 'end_turn'
            }
        ]

        # Test
        agent = WeatherTimeAgent()
        response = agent.run("What's the weather in Seattle?")

        # Verify
        assert response is not None
        assert mock_bedrock.converse.call_count == 2
```

### Load Testing

Test performance under load:

```python
# tests/load_test.py

import time
import concurrent.futures
from simple_observability import _invoke_agent, _create_bedrock_client


def invoke_agent_once(agent_id, region, query_num):
    """Single agent invocation."""
    client = _create_bedrock_client(region)
    session_id = f"load_test_{query_num}"

    start = time.time()
    result = _invoke_agent(
        client=client,
        agent_id=agent_id,
        query="What's the weather in Seattle?",
        session_id=session_id
    )
    latency = time.time() - start

    return {
        "query_num": query_num,
        "latency": latency,
        "trace_id": result["trace_id"]
    }


def run_load_test(agent_id, region, num_requests=10, concurrency=3):
    """Run load test with concurrent requests."""
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(invoke_agent_once, agent_id, region, i)
            for i in range(num_requests)
        ]

        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # Calculate statistics
    latencies = [r["latency"] for r in results]
    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

    print(f"Load Test Results:")
    print(f"  Total requests: {num_requests}")
    print(f"  Concurrency: {concurrency}")
    print(f"  Average latency: {avg_latency:.2f}s")
    print(f"  P95 latency: {p95_latency:.2f}s")

    return results


if __name__ == "__main__":
    import sys
    agent_id = sys.argv[1] if len(sys.argv) > 1 else "abc123"
    run_load_test(agent_id, "us-east-1", num_requests=20, concurrency=5)
```

## Code Quality

### Linting and Formatting

Use ruff for linting and formatting:

```bash
# Install ruff
uv add --dev ruff

# Run linting
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Type Checking

Use mypy for type checking:

```bash
# Install mypy
uv add --dev mypy

# Run type checking
uv run mypy agent/ tools/ simple_observability.py
```

### Security Scanning

Use bandit for security checks:

```bash
# Install bandit
uv add --dev bandit

# Run security scan
uv run bandit -r agent/ tools/ simple_observability.py
```

## Debugging

### Enable Debug Logging

```bash
# In simple_observability.py
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all --debug

# Or set environment variable
export LOGLEVEL=DEBUG
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all
```

### Using Python Debugger

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use debugpy for remote debugging
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
```

### Inspecting OTEL Data

```bash
# View OTEL collector debug output
docker logs otel-collector --follow

# Check OTEL collector metrics
curl http://localhost:8888/metrics

# View trace details
curl http://localhost:55679/debug/tracez
```

## Contributing

When contributing improvements:

1. Follow existing code structure and naming conventions
2. Add tests for new features
3. Update documentation
4. Run linting and type checking
5. Test locally before submitting
6. Follow CLAUDE.md coding standards

## Next Steps

After understanding development:

1. Review [System Design](design.md) for architecture
2. Review [Troubleshooting](troubleshooting.md) for debugging
3. Experiment with custom tools and scenarios
4. Contribute improvements back to the repository
