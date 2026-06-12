# Demo Guide: Running Observability Demonstrations

This guide provides step-by-step instructions for running demonstrations of the dual observability setup with Amazon Bedrock AgentCore, CloudWatch, and Braintrust. Use this to showcase the system in action and understand how observability data flows.

## Overview

Three demonstration scenarios show different aspects of the observability system:

- **Scenario 1**: Successful multi-tool query with complex reasoning - shows normal operation
- **Scenario 2**: Error handling and recovery - shows error visibility in both platforms
- **Scenario 3**: Dashboard review - walks through CloudWatch and Braintrust dashboards

### Quick Start - Run All Scenarios

```bash
# Run all three scenarios in sequence (recommended for demos)
uv run python simple_observability.py --scenario all

# Run individual scenarios
uv run python simple_observability.py --scenario success    # Scenario 1
uv run python simple_observability.py --scenario error      # Scenario 2
uv run python simple_observability.py --scenario dashboard  # Scenario 3

# With explicit agent ID
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all
```

## Scenario 1: Successful Multi-Tool Query

### Purpose
Demonstrate successful agent execution with multiple tool calls, showcasing traces in CloudWatch (automatic) and optionally in Braintrust (if configured).

### Query
```
What's the weather in Seattle and calculate the square root of 144?
```

### How to Run

```bash
# Run the successful query scenario
uv run python simple_observability.py --scenario success

# Or with explicit agent ID
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario success
```

### Expected Behavior

#### Agent Execution Flow
1. **Input Processing** (0-2 seconds)
   - Agent receives user query
   - Initializes conversation with Claude
   - Braintrust creates parent span for entire conversation
   - CloudWatch records initial request metric

2. **Tool Selection** (2-5 seconds)
   - Agent analyzes query and identifies two tasks
   - Decides to call both tools
   - Creates child spans in Braintrust for each tool call
   - CloudWatch records tool usage metrics

3. **Weather Tool Execution** (5-8 seconds)
   - get_weather tool called with location="Seattle"
   - Returns: "72 degrees and sunny"
   - Braintrust records:
     - Tool name: get_weather
     - Input: {"location": "Seattle"}
     - Output: "72 degrees and sunny"
     - Duration: ~0.5 seconds
   - CloudWatch records:
     - ToolName dimension: get_weather
     - ToolCallDuration metric
     - ToolCallSuccess metric

4. **Calculator Tool Execution** (8-11 seconds)
   - calculate tool called with operation="sqrt", x=144
   - Returns: 12.0
   - Braintrust records:
     - Tool name: calculate
     - Input: {"operation": "sqrt", "x": 144}
     - Output: 12.0
     - Duration: ~0.5 seconds
   - CloudWatch records similar metrics

5. **Response Generation** (11-15 seconds)
   - Agent synthesizes final response
   - Combines both tool results
   - Returns natural language answer
   - Both systems record completion

#### Expected Console Output
```
2025-10-25 12:00:00,p12345,{simple_observability.py:150},INFO,Starting dual observability demo...
2025-10-25 12:00:00,p12345,{simple_observability.py:155},INFO,Braintrust experiment initialized: dual-observability-demo
2025-10-25 12:00:00,p12345,{simple_observability.py:160},INFO,CloudWatch namespace: AgentCore/Observability
2025-10-25 12:00:01,p12345,{simple_observability.py:200},INFO,
Query: What's the weather in Seattle and calculate the square root of 144?
2025-10-25 12:00:01,p12345,{simple_observability.py:210},INFO,Processing query with agent...
2025-10-25 12:00:05,p12345,{simple_observability.py:250},INFO,Tool call: get_weather
2025-10-25 12:00:05,p12345,{simple_observability.py:255},INFO,Tool input: {"location": "Seattle"}
2025-10-25 12:00:06,p12345,{simple_observability.py:260},INFO,Tool output: 72 degrees and sunny
2025-10-25 12:00:08,p12345,{simple_observability.py:250},INFO,Tool call: calculate
2025-10-25 12:00:08,p12345,{simple_observability.py:255},INFO,Tool input: {"operation": "sqrt", "x": 144}
2025-10-25 12:00:09,p12345,{simple_observability.py:260},INFO,Tool output: 12.0
2025-10-25 12:00:12,p12345,{simple_observability.py:300},INFO,
Response: The weather in Seattle is currently 72 degrees and sunny. The square root of 144 is 12.
2025-10-25 12:00:12,p12345,{simple_observability.py:305},INFO,Query completed in 11.2 seconds
2025-10-25 12:00:12,p12345,{simple_observability.py:310},INFO,Metrics sent to CloudWatch
2025-10-25 12:00:12,p12345,{simple_observability.py:315},INFO,Trace logged to Braintrust
```

#### Expected CloudWatch Metrics

CloudWatch receives traces and metrics from the AgentCore Runtime automatically via OpenTelemetry. Key observations:

**In CloudWatch GenAI Observability/APM Console:**
- Agent invocation count increments
- Latency recorded: ~11-15 seconds (including all tool calls and LLM processing)
- Tool execution times visible: weather tool ~500ms, calculator tool ~500ms
- Span details showing successful execution of both tools
- No errors recorded

**Note on Metrics:**
The namespace is `AWS/Bedrock-AgentCore` (configured in OTEL settings). AgentCore Runtime automatically emits:
- Invocation counts
- Latency measurements
- Success/error status
- Tool execution details
- Span hierarchy and relationships

These metrics appear in CloudWatch GenAI Observability dashboard or APM console, not as custom metrics namespace.

#### Expected Braintrust Trace
```
Span Hierarchy:
└─ conversation_12345 [15.2s]
   ├─ model_call_1 [3.5s]
   │  └─ Input: "What's the weather in Seattle and calculate the square root of 144?"
   │  └─ Output: [tool_use blocks for get_weather and calculate]
   ├─ tool_get_weather [0.5s]
   │  └─ Input: {"location": "Seattle"}
   │  └─ Output: "72 degrees and sunny"
   ├─ tool_calculate [0.5s]
   │  └─ Input: {"operation": "sqrt", "x": 144}
   │  └─ Output: 12.0
   └─ model_call_2 [2.1s]
      └─ Input: [tool results]
      └─ Output: "The weather in Seattle is currently 72 degrees and sunny..."

Metadata:
  - Total Duration: 15.2s
  - Tool Calls: 2
  - Model: claude-3-5-sonnet-20241022
  - Success: true
```

### Viewing CloudWatch Logs

Use the `check_logs.sh` script to view agent execution logs:

```bash
# View logs from the last 30 minutes
scripts/check_logs.sh --time 30m

# Follow logs in real-time while running the demo
scripts/check_logs.sh --follow

# View logs from the last hour
scripts/check_logs.sh --time 1h
```

**What you'll see in the logs:**
- Agent initialization and startup messages
- Tool call invocations with input parameters
- Tool execution results and output
- Timing information for each operation
- OTEL trace export confirmations to CloudWatch and Braintrust
- Structured logging with log levels (INFO, DEBUG, etc.)

### Key Points to Highlight
- ✓ Both tools executed successfully
- ✓ Traces show complete execution flow
- ✓ CloudWatch metrics align with Braintrust spans
- ✓ Token usage tracked accurately
- ✓ Latency broken down by component
- ✓ Detailed logs available via check_logs.sh for debugging

### Timing Estimate
Total demonstration time: 3-5 minutes
- Execution: ~15 seconds
- CloudWatch dashboard review: 1-2 minutes
- Braintrust trace review: 2-3 minutes

## Scenario 2: Error Handling

### Purpose
Demonstrate how the observability system captures and tracks errors, including partial failures and recovery.

### Query
```
Calculate the factorial of -5
```

### How to Run

```bash
# Run the error handling scenario
uv run python simple_observability.py --scenario error

# Or with explicit agent ID
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario error
```

### Expected Behavior

#### Agent Execution Flow
1. **Input Processing** (0-2 seconds)
   - Agent receives query
   - Identifies calculator tool needed
   - Creates parent span in Braintrust

2. **Tool Call Attempt** (2-5 seconds)
   - calculate tool called with operation="factorial", x=-5
   - Tool validation detects invalid input (negative number)
   - Raises ValueError
   - Error captured in both systems

3. **Error Recording** (5-6 seconds)
   - Braintrust logs:
     - Span marked as error
     - Error type: ValueError
     - Error message: "Factorial is not defined for negative numbers"
     - Stack trace captured
   - CloudWatch logs:
     - ErrorCount: 1
     - ErrorType dimension: ValueError
     - ToolCallFailure: 1

4. **Agent Recovery** (6-10 seconds)
   - Agent may attempt to explain why operation failed
   - Returns user-friendly error message
   - Total trace still logged for analysis

#### Expected Console Output
```
2025-10-25 12:05:00,p12345,{simple_observability.py:200},INFO,
Query: Calculate the factorial of -5
2025-10-25 12:05:00,p12345,{simple_observability.py:210},INFO,Processing query with agent...
2025-10-25 12:05:03,p12345,{simple_observability.py:250},INFO,Tool call: calculate
2025-10-25 12:05:03,p12345,{simple_observability.py:255},INFO,Tool input: {"operation": "factorial", "x": -5}
2025-10-25 12:05:03,p12345,{simple_observability.py:270},ERROR,Tool execution failed: Factorial is not defined for negative numbers
2025-10-25 12:05:05,p12345,{simple_observability.py:300},INFO,
Response: I apologize, but I cannot calculate the factorial of -5. The factorial function is only defined for non-negative integers.
2025-10-25 12:05:05,p12345,{simple_observability.py:305},INFO,Query completed in 5.3 seconds
2025-10-25 12:05:05,p12345,{simple_observability.py:320},INFO,Error metrics sent to CloudWatch
2025-10-25 12:05:05,p12345,{simple_observability.py:325},INFO,Error trace logged to Braintrust
```

#### Expected CloudWatch Metrics

CloudWatch receives traces showing the error scenario:

**In CloudWatch GenAI Observability/APM Console:**
- Agent invocation count increments
- Latency recorded: ~5-8 seconds (shorter due to error)
- Tool execution attempted: calculator tool
- Error status visible in trace
- Tool failed with validation error

**Error Tracking:**
The namespace is `AWS/Bedrock-AgentCore`. AgentCore Runtime records:
- Request that resulted in error
- Latency of the failed request
- Tool that failed and error details
- Status marked as failure/error
- Error details preserved in trace attributes

Error details are captured in the trace span attributes for debugging.

#### Expected Braintrust Trace
```
Span Hierarchy:
└─ conversation_12346 [5.3s] [ERROR]
   ├─ model_call_1 [2.5s]
   │  └─ Input: "Calculate the factorial of -5"
   │  └─ Output: [tool_use block for calculate]
   ├─ tool_calculate [0.2s] [ERROR]
   │  └─ Input: {"operation": "factorial", "x": -5}
   │  └─ Error: ValueError - Factorial is not defined for negative numbers
   │  └─ Stack trace: [full trace]
   └─ model_call_2 [1.5s]
      └─ Input: [error result]
      └─ Output: "I apologize, but I cannot calculate the factorial of -5..."

Metadata:
  - Total Duration: 5.3s
  - Tool Calls: 1
  - Tool Failures: 1
  - Error Type: ValueError
  - Success: false
```

### Viewing Error Logs

Use the `check_logs.sh` script to view error messages:

```bash
# View only ERROR messages from the last 15 minutes
scripts/check_logs.sh --errors

# View only ERROR messages from the last hour
scripts/check_logs.sh --time 1h --errors

# View all logs from the last 30 minutes (includes errors with context)
scripts/check_logs.sh --time 30m
```

**What you'll see in the error logs:**
- ERROR severity level in the log output
- Exact error message from the tool
- Error type (ValueError, etc.)
- Stack trace with file and line number information
- Context around the failure (what was attempted)
- How the agent recovered and responded to the user

### Key Points to Highlight
- ✓ Errors captured in both systems
- ✓ Error details preserved (type, message, stack trace)
- ✓ Metrics differentiate success vs failure
- ✓ Agent handles error gracefully
- ✓ Full context available for debugging via check_logs.sh
- ✓ Easy filtering to see only errors when troubleshooting

### Timing Estimate
Total demonstration time: 3-4 minutes
- Execution: ~6 seconds
- Error metric review: 1-2 minutes
- Trace analysis: 2 minutes

## Scenario 3: Dashboard Review

### Purpose
Walk through CloudWatch and Braintrust dashboards to show observability coverage. CloudWatch shows automatic infrastructure-level traces; Braintrust shows agent-level OTEL traces (if configured).

### How to Run

For Scenario 3, you don't execute queries - you navigate and review the dashboards. However, you should have run Scenarios 1 and 2 first to generate data:

```bash
# First, run Scenario 1 to generate successful query traces
uv run python simple_observability.py --scenario success

# Then run Scenario 2 to generate error traces
uv run python simple_observability.py --scenario error

# Scenario 3 uses the data from the above runs
uv run python simple_observability.py --scenario dashboard

# Or run all three scenarios in sequence
uv run python simple_observability.py --scenario all
```

**After running the queries**, you're ready to review the dashboards as outlined below.

### CloudWatch Dashboard Review

#### Request Metrics Widget
**What to Show:**
- Total request count over time period
- Request rate per minute
- Comparison with previous period

**Key Points:**
- "This shows our request volume - useful for capacity planning"
- "Notice the correlation between request spikes and latency"

#### Latency Distribution Widget
**What to Show:**
- P50, P90, P99 latencies
- Comparison between successful and failed requests
- Tool-specific latency breakdown

**Key Points:**
- "P99 latency is critical for user experience"
- "Tool calls add measurable latency - see the breakdown"
- "Failed requests typically complete faster (fail-fast pattern)"

#### Error Rate Widget
**What to Show:**
- Error percentage over time
- Error breakdown by type
- Correlation with specific tool calls

**Key Points:**
- "We can quickly identify error spikes"
- "Error types help diagnose root causes"
- "This triggers our alerting system at 5% threshold"

#### Token Usage Widget
**What to Show:**
- Input vs output tokens
- Token consumption rate
- Cost implications

**Key Points:**
- "Direct visibility into API costs"
- "Input tokens include conversation history"
- "Helps optimize prompt engineering"

#### Success Rate Widget
**What to Show:**
- Overall success percentage
- Success rate by tool
- Trend over time

**Key Points:**
- "Target: 95%+ success rate"
- "Drops indicate system or integration issues"
- "Tool-specific success helps identify problematic integrations"

#### Recent Traces Widget
**What to Show:**
- Latest request traces
- Quick access to failed requests
- Link to detailed logs

**Key Points:**
- "Quick access to recent activity"
- "Failed requests highlighted for immediate attention"
- "Click through to full CloudWatch Logs Insights"

### Braintrust Dashboard Review

#### Experiment Overview
**What to Show:**
- Experiment list
- Run history
- Performance trends

**Key Points:**
- "Each run captured with full context"
- "Compare performance across code changes"
- "Track improvements over time"

#### Trace Explorer
**What to Show:**
- Filter by success/failure
- Search by input/output content
- Sort by duration or token count

**Key Points:**
- "Powerful filtering for debugging"
- "Search actual conversation content"
- "Find slow or expensive queries"

#### Span Timeline View
**What to Show:**
- Waterfall view of execution
- Parallel vs sequential operations
- Bottleneck identification

**Key Points:**
- "Visual representation of execution flow"
- "Identify optimization opportunities"
- "See exact timing of each component"

#### Cost Analysis
**What to Show:**
- Token usage per request
- Cost per conversation
- Trend analysis

**Key Points:**
- "Direct cost visibility"
- "Identify expensive query patterns"
- "Optimize for cost efficiency"

### Comparison: CloudWatch vs Braintrust

#### CloudWatch Strengths
- ✓ Real-time metrics and alerting
- ✓ AWS-native integration
- ✓ Aggregated statistics
- ✓ Operational dashboards
- ✓ Log correlation

#### Braintrust Strengths
- ✓ Detailed trace visualization
- ✓ Conversation-level analysis
- ✓ Development workflow integration
- ✓ A/B testing support
- ✓ Rich filtering and search

#### Use Together For
- ✓ Complete observability coverage
- ✓ Operations (CloudWatch) + Development (Braintrust)
- ✓ Metrics (CloudWatch) + Traces (Braintrust)
- ✓ Alerting (CloudWatch) + Debugging (Braintrust)

### Timing Estimate
Total demonstration time: 8-12 minutes
- CloudWatch dashboard: 4-6 minutes
- Braintrust dashboard: 4-6 minutes
- Comparison discussion: 2-3 minutes

## Additional Scenarios (Optional)

### Scenario 4: Performance Optimization
**Query:** "What's the weather in Tokyo, London, Paris, and New York?"
**Purpose:** Show multiple tool calls and optimization opportunities

### Scenario 5: Complex Reasoning Chain
**Query:** "Calculate 15 factorial, then find the square root of the result"
**Purpose:** Demonstrate multi-step reasoning with dependent tool calls

### Scenario 6: Rate Limiting
**Query:** Run 100 queries rapidly
**Purpose:** Show throttling metrics and queue behavior

## Troubleshooting Common Demo Issues

### Issue: Metrics Not Appearing in CloudWatch
**Cause:** Metric buffer not flushed or IAM permissions
**Solution:**
1. Check IAM role has `cloudwatch:PutMetricData` permission
2. Verify namespace spelling exactly matches
3. Wait 1-2 minutes for metrics to propagate
4. Check CloudWatch Logs for error messages

### Issue: Braintrust Traces Missing
**Cause:** API key not set or network issues
**Solution:**
1. Verify `BRAINTRUST_API_KEY` environment variable
2. Check internet connectivity
3. Look for error messages in console output
4. Verify project name exists in Braintrust

### Issue: Tool Calls Failing
**Cause:** Tool implementation bugs or input validation
**Solution:**
1. Check tool input format matches schema
2. Review error messages in logs
3. Verify tool registration with agent
4. Test tool independently

### Issue: Slow Response Times
**Cause:** Network latency or model selection
**Solution:**
1. Check AWS region matches Amazon Bedrock model availability
2. Verify network connectivity to Amazon Bedrock
3. Consider using faster model variant
4. Review CloudWatch latency breakdown

## Demo Best Practices

### Preparation
1. Run demo script once before presentation to warm up
2. Pre-create CloudWatch dashboard
3. Clear Braintrust experiment or create new one
4. Have AWS Console and Braintrust open in separate tabs
5. Prepare backup queries in case of issues

### During Demo
1. Explain what you're about to do before running each query
2. Highlight key output as it appears
3. Use both dashboards to tell complete story
4. Point out specific metrics and their business value
5. Leave time for questions between scenarios

### After Demo
1. Share links to dashboards
2. Provide sample queries for attendees to try
3. Reference documentation for setup
4. Collect feedback on observability needs

## Expected Metrics Summary

### Per Successful Query
- Request latency: 10-20 seconds
- Tool calls: 1-3
- Input tokens: 100-300
- Output tokens: 50-150
- Success rate: 100%

### Per Failed Query
- Request latency: 3-8 seconds
- Tool calls: 1-2
- Error count: 1
- Success rate: 0%

### Dashboard Update Frequency
- CloudWatch: 1-minute intervals
- Braintrust: Real-time (async upload)
- Log entries: Immediate

## Presentation Preparation

### Pre-Demo Checklist

#### Environment Setup (30 minutes before demo)

- [ ] Verify AWS credentials are configured
  ```bash
  aws sts get-caller-identity
  ```

- [ ] Confirm Amazon Bedrock model access
  ```bash
  aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?modelId==`us.anthropic.claude-haiku-4-5-20251001-v1:0`]'
  ```

- [ ] Check environment variables
  ```bash
  cat .env
  # Verify: AWS_REGION, BRAINTRUST_API_KEY, BRAINTRUST_PROJECT_ID
  ```

- [ ] Test script execution
  ```bash
  uv run python simple_observability.py --scenario success
  # Run one test query to warm up
  ```

- [ ] Open CloudWatch console
  - Navigate to CloudWatch > GenAI Observability > Bedrock AgentCore
  - View metrics under "Agents"
  - View traces under "Sessions" then "Traces"

- [ ] Open Braintrust console
  - Navigate to https://www.braintrust.dev/app
  - Open "agentcore-observability-demo" project
  - Ensure you can see traces

- [ ] Prepare browser tabs
  - Tab 1: Terminal with demo directory
  - Tab 2: CloudWatch dashboard
  - Tab 3: Braintrust project view
  - Tab 4: This demo guide (for reference)

#### Content Preparation

- [ ] Review all three scenarios in this guide
- [ ] Prepare backup queries (see below)
- [ ] Test network connectivity to all services
- [ ] Clear previous demo data if needed (optional)

### Backup Queries

If primary demo queries fail, use these alternatives:

#### Successful Query Backups
1. "What's the weather in Tokyo?"
2. "Calculate 12 squared"
3. "What's 25 plus 17?"

#### Error Query Backups
1. "Calculate the square root of -1"
2. "What's the weather in zzz123?" (invalid location)
3. "Calculate 10 divided by 0"

#### Multi-Tool Backups
1. "What's the weather in London and calculate 144 divided by 12"
2. "Calculate the square root of 256 and tell me the weather in Paris"

### Presentation Tips

#### Pacing
- Allow time for systems to respond (10-15 seconds per query)
- Don't rush through dashboard explanations
- Pause for questions between scenarios
- Keep total demo under 45 minutes

#### Narration
1. Explain what you're about to do before running each query
2. Highlight key output as it appears
3. Use both dashboards to tell complete story
4. Point out specific metrics and their business value
5. Leave time for questions between scenarios

#### Visual Focus
- Zoom browser if presenting to large audience
- Use browser zoom: Cmd/Ctrl + "+"
- Highlight important sections with cursor
- Scroll slowly when showing long lists

#### Engagement
- Ask rhetorical questions: "Why do we care about P99 latency?"
- Relate to audience's pain points
- Encourage questions throughout
- Connect features to use cases

#### Recovery
- If something fails, stay calm and use backup query
- Turn failures into teaching moments
- Reference error handling capabilities
- Move to next scenario if issue persists

### Demo Success Checklist

- [ ] Successfully executed multi-tool query
- [ ] Showed CloudWatch traces (automatic) and Braintrust traces (if configured)
- [ ] Demonstrated error handling
- [ ] Explained key metrics and their business value
- [ ] Connected operational and development workflows
- [ ] Answered audience questions
- [ ] Provided next steps and resources
- [ ] Collected feedback

### After Demo
1. Share links to dashboards
2. Provide sample queries for attendees to try
3. Reference documentation for setup
4. Collect feedback on observability needs
