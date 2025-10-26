# Demo Scenarios for Dual Observability Tutorial

This document provides detailed scenarios for demonstrating the dual observability setup with Amazon Bedrock AgentCore, CloudWatch, and Braintrust.

## Overview

Each scenario demonstrates different aspects of the observability system:
- **Scenario 1**: Successful multi-tool query with complex reasoning
- **Scenario 2**: Error handling and recovery patterns
- **Scenario 3**: Dashboard review and metrics analysis

## Scenario 1: Successful Multi-Tool Query

### Purpose
Demonstrate successful agent execution with multiple tool calls, showcasing how traces flow through both CloudWatch and Braintrust.

### Query
```
What's the weather in Seattle and calculate the square root of 144?
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
```
Namespace: AgentCore/Observability
Metrics:
  - RequestCount: 1
  - RequestLatency: 11200 ms (P50: 11200, P90: 11200, P99: 11200)
  - ToolCallCount: 2
  - ToolCallDuration (get_weather): 500 ms
  - ToolCallDuration (calculate): 500 ms
  - ToolCallSuccess: 2
  - TokensUsed (Input): ~150
  - TokensUsed (Output): ~50
  - SuccessRate: 100%
```

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

### Key Points to Highlight
- ✓ Both tools executed successfully
- ✓ Traces show complete execution flow
- ✓ CloudWatch metrics align with Braintrust spans
- ✓ Token usage tracked accurately
- ✓ Latency broken down by component

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
```
Namespace: AgentCore/Observability
Metrics:
  - RequestCount: 1
  - RequestLatency: 5300 ms
  - ToolCallCount: 1
  - ToolCallFailure: 1
  - ErrorCount: 1
  - ErrorRate: 100%
  - SuccessRate: 0%

Dimensions:
  - ErrorType: ValueError
  - ToolName: calculate
```

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

### Key Points to Highlight
- ✓ Errors captured in both systems
- ✓ Error details preserved (type, message, stack trace)
- ✓ Metrics differentiate success vs failure
- ✓ Agent handles error gracefully
- ✓ Full context available for debugging

### Timing Estimate
Total demonstration time: 3-4 minutes
- Execution: ~6 seconds
- Error metric review: 1-2 minutes
- Trace analysis: 2 minutes

## Scenario 3: Dashboard Review

### Purpose
Walk through both CloudWatch and Braintrust dashboards to show comprehensive observability coverage.

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
