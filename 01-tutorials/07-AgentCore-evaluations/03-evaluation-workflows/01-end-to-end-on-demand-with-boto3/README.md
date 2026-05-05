# AgentCore Evaluation Utility

Python utility for extracting CloudWatch trace data and evaluating agent sessions using the AgentCore Evaluation DataPlane API.

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Configure AWS credentials with access to CloudWatch Logs and AgentCore Evaluation API:

```bash
aws configure
```

Or set environment variables:

```bash
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-east-1"
```

## Usage

```python
from utils import EvaluationClient

# Initialize client
client = EvaluationClient(region="us-east-1")

# Evaluate a session (session scope)
results = client.evaluate_session(
    session_id="your-session-id",
    evaluator_ids=["Builtin.Helpfulness"],
    agent_id="your-agent-id",
    region="us-east-1",
    scope="session"
)

# Print results
for result in results.results:
    print(f"{result.evaluator_name}: {result.value} - {result.label}")
    print(f"Explanation: {result.explanation}")
```

## Evaluation Scopes

The `scope` parameter is required and determines what level of data is evaluated:

- **`session`**: Evaluates the entire session. Works with most evaluators including `Builtin.GoalSuccessRate` and all response quality evaluators.
- **`trace`**: Evaluates a specific trace. Requires `trace_id` parameter.
- **`span`**: Evaluates individual tool execution spans. Required for `Builtin.ToolSelectionAccuracy` and `Builtin.ToolParameterAccuracy`.

## Multi-Evaluator Support

Evaluate with multiple evaluators across different scopes (matching the notebook pattern):

```python
# Response quality evaluators (session scope)
results = client.evaluate_session(
    session_id="session-id",
    evaluator_ids=[
        "Builtin.Correctness",
        "Builtin.Faithfulness",
        "Builtin.Helpfulness",
        "Builtin.ResponseRelevance",
        "Builtin.Conciseness",
        "Builtin.Coherence",
        "Builtin.InstructionFollowing",
        "Builtin.Refusal",
        "Builtin.Harmfulness",
        "Builtin.Stereotyping",
    ],
    agent_id="agent-id",
    region="us-east-1",
    scope="session"
)

# Goal success (session scope)
results = client.evaluate_session(
    session_id="session-id",
    evaluator_ids=["Builtin.GoalSuccessRate"],
    agent_id="agent-id",
    region="us-east-1",
    scope="session"
)

# Tool evaluators (span scope)
results = client.evaluate_session(
    session_id="session-id",
    evaluator_ids=["Builtin.ToolSelectionAccuracy", "Builtin.ToolParameterAccuracy"],
    agent_id="agent-id",
    region="us-east-1",
    scope="span"
)
```

## Auto-Save and Metadata

Save input/output files and track experiments:

```python
results = client.evaluate_session(
    session_id="session-id",
    evaluator_ids=["Builtin.Helpfulness"],
    agent_id="agent-id",
    region="us-east-1",
    scope="session",
    auto_save_input=True,   # Saves to evaluation_input/
    auto_save_output=True,  # Saves to evaluation_output/
    auto_create_dashboard=True,  # generates data for HTML dashboard available locally
    metadata={
        "experiment": "baseline",
        "description": "Initial evaluation run"
    }
)
```

Input files contain only the spans sent to the API for exact replay. Output files contain complete results with metadata.

## Implementation Details

The utility queries CloudWatch Logs for OpenTelemetry spans and runtime logs, filters relevant data (gen_ai attributes and conversation logs), and submits to the evaluation API. Default lookback window is 7 days with a maximum of 1000 items per evaluation.
