# Demo Presentation Guide: Dual Observability with AgentCore

This guide provides a step-by-step walkthrough for presenting the dual observability tutorial, combining Amazon Bedrock AgentCore with CloudWatch and Braintrust.

## Pre-Demo Checklist

### Environment Setup (30 minutes before demo)

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
  cd /home/ubuntu/repos/amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/07-simple-dual-observability
  cat .env
  # Verify: AWS_REGION, BRAINTRUST_API_KEY, BRAINTRUST_PROJECT_NAME
  ```

- [ ] Test script execution
  ```bash
  uv run python simple_observability.py
  # Run one test query to warm up
  ```

- [ ] Open CloudWatch console
  - Navigate to CloudWatch > Dashboards
  - Have "AgentCore Observability" dashboard ready
  - Or use metrics explorer with namespace: AgentCore/Observability

- [ ] Open Braintrust console
  - Navigate to https://www.braintrust.dev/app
  - Open "dual-observability-demo" project
  - Ensure you can see experiments and traces

- [ ] Prepare browser tabs
  - Tab 1: Terminal with demo directory
  - Tab 2: CloudWatch dashboard
  - Tab 3: Braintrust experiment view
  - Tab 4: This demo guide (for reference)

### Content Preparation

- [ ] Review scenarios in `scenarios/demo_scenarios.md`
- [ ] Prepare backup queries in case of issues
- [ ] Test network connectivity to all services
- [ ] Clear previous demo data if needed (optional)

## Demo Flow (30-45 minutes)

### Introduction (5 minutes)

#### Opening Statement
"Today I'll demonstrate comprehensive observability for Amazon Bedrock AgentCore applications using a dual approach: CloudWatch for operational metrics and Braintrust for detailed trace analysis."

#### What We'll Cover
1. Why dual observability matters
2. Live agent execution with real-time monitoring
3. CloudWatch metrics and dashboards
4. Braintrust trace analysis
5. How to use both together

#### Architecture Overview
```
User Query
    |
    v
AgentCore Agent
    |
    +-- Amazon Bedrock (Claude 3.5 Sonnet)
    |
    +-- Tools (Weather, Calculator)
    |
    v
Dual Observability
    |
    +-- CloudWatch: Metrics, Logs, Dashboards
    |
    +-- Braintrust: Traces, Spans, Experiments
```

**Key Point:** "We use both systems because they complement each other - CloudWatch for operations and alerting, Braintrust for development and debugging."

### Part 1: Successful Query Demo (10 minutes)

#### Step 1: Explain the Query
"I'll ask the agent to perform two tasks simultaneously: check the weather and do a calculation."

**Query:** "What's the weather in Seattle and calculate the square root of 144?"

**What to emphasize:**
- This tests multi-tool coordination
- Requires the agent to reason about two different tasks
- Shows parallel tool execution

#### Step 2: Execute the Query
```bash
uv run python simple_observability.py
```

**As it runs, narrate:**
- "The agent is initializing..."
- "Now it's calling Amazon Bedrock..."
- "Watch for the tool calls..."
- "Here's the weather tool being called..."
- "And now the calculator tool..."
- "Final response being generated..."

**Point out in console output:**
- Structured logging format
- Tool call details (name, input, output)
- Duration tracking
- Braintrust and CloudWatch confirmation messages

#### Step 3: Review CloudWatch Metrics
Switch to CloudWatch dashboard tab.

**Request Rate Widget:**
- "See the spike in requests - that's our query"
- "In production, we'd see patterns over time"
- "Useful for capacity planning"

**Latency Widget:**
- "P50 shows typical response time"
- "P99 is what we use for SLA tracking"
- "Notice the latency breakdown by component"
- Point out: "Our P99 target is 30 seconds"

**Token Usage Widget:**
- "Input tokens include the query and tool results"
- "Output tokens are the agent's response"
- "This directly maps to API costs"

**Tool Performance Widget:**
- "Each tool's performance tracked separately"
- "Both tools completed in under 1 second"
- "We can identify slow tools quickly"

**Key Point:** "CloudWatch gives us the operational view - perfect for monitoring production systems and triggering alerts."

#### Step 4: Review Braintrust Trace
Switch to Braintrust tab.

**Experiment View:**
- "Each run is captured as an experiment"
- "Click on the most recent trace"
- Show: input, output, duration, tokens

**Span Timeline:**
- Open the waterfall view
- "This visualizes the execution flow"
- Point out:
  - Initial model call
  - Two tool call spans
  - Final response generation
- "See how some operations are sequential, others could be parallel"

**Trace Details:**
- Click into a tool call span
- "Here's the exact input sent to the tool"
- "And the exact output received"
- "Plus timing information and metadata"

**Key Point:** "Braintrust gives us the development view - perfect for debugging and optimization."

### Part 2: Error Handling Demo (8 minutes)

#### Step 1: Explain the Error Scenario
"Now let's see what happens when something goes wrong. I'll ask the agent to perform an invalid calculation."

**Query:** "Calculate the factorial of -5"

**What to emphasize:**
- This will trigger a validation error
- The tool will reject the input
- Both systems will capture the error

#### Step 2: Execute the Query
```bash
uv run python simple_observability.py
```

**As it runs, narrate:**
- "Agent receives the query..."
- "Calls the calculator tool..."
- "Tool validates input and raises an error"
- "Watch for the error message in logs..."
- "Agent handles the error gracefully..."

**Point out in console output:**
- ERROR log level
- Error message: "Factorial is not defined for negative numbers"
- Agent's recovery and user-friendly response
- Error metrics sent to both systems

#### Step 3: Review CloudWatch Error Metrics
Switch to CloudWatch dashboard.

**Error Rate Widget:**
- "Error count increased by 1"
- "Error rate calculated as percentage"
- "Alert would trigger at 5% error rate"

**Success Rate Widget:**
- "Success rate dipped with this failed request"
- "Returns to normal with subsequent successful queries"

**Recent Traces Widget:**
- Scroll to find the error entry
- "Errors are highlighted for quick attention"
- "Click through to full log details"

**Key Point:** "In production, this error spike would trigger a CloudWatch alarm, alerting the ops team."

#### Step 4: Review Braintrust Error Trace
Switch to Braintrust tab.

**Filter for Errors:**
- Apply filter: `has_error = true`
- "All failed traces isolated"
- Click on the error trace

**Error Details:**
- "Error type: ValueError"
- "Full error message preserved"
- "Stack trace available for debugging"
- Show span marked with error indicator

**Input Analysis:**
- "We can see exactly what the user asked"
- "And exactly what was sent to the tool"
- "Makes reproducing the issue trivial"

**Key Point:** "Braintrust makes debugging fast - we see exactly what happened, why it failed, and can reproduce it instantly."

### Part 3: Dashboard Deep Dive (12 minutes)

#### CloudWatch Dashboard Walkthrough

**Widget 1: Request Rate**
- Shows requests per minute
- Useful for:
  - Capacity planning
  - Traffic pattern analysis
  - Anomaly detection
- "We can set alarms for unusual traffic spikes"

**Widget 2: Latency Percentiles**
- P50, P90, P99, Average
- Explains: "P99 means 99% of requests complete faster than this time"
- Target: P99 < 30 seconds
- "We alert if P99 exceeds our SLA"

**Widget 3: Error Rate**
- Total errors and percentage
- Alert threshold: 5%
- "Helps identify systemic issues quickly"

**Widget 4: Token Usage**
- Split by input/output
- Stacked view shows total
- Cost calculation: Input @ $3/M, Output @ $15/M tokens
- "Direct visibility into API costs"

**Widget 5: Success Rate**
- Target: 95%+
- Calculated as (successes / total requests) * 100
- "Key SLA metric for uptime reporting"

**Widget 6: Tool Performance**
- Average and P99 by tool
- "Identifies which tools are slow"
- "Helps prioritize optimization work"

**Widget 7: Tool Success/Failure**
- Count of successes and failures per tool
- "Helps identify problematic integrations"

**Widget 8: Recent Traces**
- Log query showing recent activity
- Errors highlighted
- "Quick access for troubleshooting"

#### Braintrust Dashboard Walkthrough

**Experiments View**
- List of all runs
- Sortable by date, duration, success rate
- "Compare performance across code changes"
- "Track improvements over time"

**Trace Explorer**
- Powerful search capabilities
- Filter by:
  - Success/failure
  - Duration
  - Token count
  - Input/output content
- "Find specific conversations instantly"

**Span Waterfall**
- Visual execution timeline
- Shows:
  - Sequential dependencies
  - Parallel opportunities
  - Bottlenecks
- "Identify optimization opportunities"

**Performance Metrics**
- Time series charts
- Latency trends
- Token usage trends
- "Development-time performance tracking"

**Cost Analysis**
- Token usage breakdown
- Per-conversation cost
- Cumulative cost tracking
- "Optimize for cost efficiency"

### Part 4: Integration and Workflow (5 minutes)

#### How to Use Both Together

**Operational Workflow:**
1. "CloudWatch monitors production continuously"
2. "Alert fires on error spike or latency increase"
3. "Ops team checks CloudWatch for scope of issue"
4. "Switch to Braintrust to examine specific failures"
5. "Find failing traces, review inputs and errors"
6. "Identify root cause and implement fix"
7. "Deploy and verify with CloudWatch metrics"

**Development Workflow:**
1. "Make code changes to agent or tools"
2. "Test with sample queries"
3. "Review traces in Braintrust"
4. "Optimize based on span timings"
5. "Check token usage for cost efficiency"
6. "Deploy and monitor with CloudWatch"

**Key Integration Points:**
- Request IDs link CloudWatch logs to Braintrust traces
- Timestamps enable time-based correlation
- Both systems track same metrics (latency, errors, success rate)
- Complementary strengths: operations vs development

#### When to Use Which System

**Use CloudWatch when:**
- ✓ Monitoring production systems
- ✓ Setting up alerts and alarms
- ✓ Analyzing aggregate metrics
- ✓ Investigating incidents in real-time
- ✓ Reporting on SLAs
- ✓ Capacity planning

**Use Braintrust when:**
- ✓ Debugging specific failures
- ✓ Optimizing prompt engineering
- ✓ Analyzing conversation quality
- ✓ A/B testing model changes
- ✓ Understanding user intent
- ✓ Development and testing

**Key Point:** "You need both. CloudWatch tells you something is wrong. Braintrust tells you why and how to fix it."

### Conclusion (3 minutes)

#### Summary
"We've seen how dual observability provides comprehensive insights into AgentCore applications:"

1. **CloudWatch provides:**
   - Real-time operational metrics
   - Alerting and monitoring
   - Aggregate statistics
   - Production readiness

2. **Braintrust provides:**
   - Detailed trace analysis
   - Conversation-level context
   - Development insights
   - Optimization guidance

3. **Together they enable:**
   - Fast incident response
   - Efficient debugging
   - Continuous optimization
   - Cost management

#### Next Steps
"To implement this in your own applications:"

1. Copy the sample code from the repository
2. Configure your AWS credentials and Braintrust API key
3. Customize the CloudWatch dashboard for your metrics
4. Set up alerts based on your SLAs
5. Integrate Braintrust into your development workflow

**Resources:**
- Repository: `01-tutorials/06-AgentCore-observability/07-simple-dual-observability/`
- README with setup instructions
- Dashboard templates
- Scenario documentation

#### Q&A
"I'm happy to answer any questions about:"
- Implementation details
- Integration with existing systems
- Custom metrics and dimensions
- Alerting strategies
- Cost optimization
- Scaling considerations

## Troubleshooting During Demo

### Script Won't Run

**Symptoms:** Python errors, import failures

**Quick Fixes:**
```bash
# Reinstall dependencies
uv sync

# Verify Python version
python --version  # Should be 3.11+

# Check environment variables
env | grep -E 'AWS|BRAINTRUST'
```

### Metrics Not in CloudWatch

**Symptoms:** Empty dashboard widgets

**Quick Fixes:**
- Wait 1-2 minutes for metrics to propagate
- Check IAM permissions: `cloudwatch:PutMetricData`
- Verify namespace spelling: "AgentCore/Observability"
- Switch to CloudWatch Metrics Explorer and search manually

### Traces Not in Braintrust

**Symptoms:** Empty experiment list

**Quick Fixes:**
- Verify API key: `echo $BRAINTRUST_API_KEY`
- Check network connectivity
- Look for error messages in console output
- Wait 30 seconds for async upload to complete
- Refresh Braintrust UI

### Agent Errors

**Symptoms:** Tool calls fail, Amazon Bedrock errors

**Quick Fixes:**
- Check Amazon Bedrock model access in region
- Verify AWS credentials are valid
- Review error message for specific issue
- Switch to backup query if one is problematic

### Slow Responses

**Symptoms:** Queries take longer than expected

**Quick Fixes:**
- Check network connectivity to Amazon Bedrock
- Verify region matches model availability
- Note: First query after idle period may be slower
- Use this as teaching moment about cold starts

## Backup Queries

If primary demo queries fail, use these alternatives:

### Successful Query Backups
1. "What's the weather in Tokyo?"
2. "Calculate 12 squared"
3. "What's 25 plus 17?"

### Error Query Backups
1. "Calculate the square root of -1"
2. "What's the weather in zzz123?"  (invalid location)
3. "Calculate 10 divided by 0"

### Multi-Tool Backups
1. "What's the weather in London and calculate 144 divided by 12"
2. "Calculate the square root of 256 and tell me the weather in Paris"

## Presentation Tips

### Pacing
- Allow time for systems to respond (10-15 seconds per query)
- Don't rush through dashboard explanations
- Pause for questions between sections
- Keep total demo under 45 minutes

### Narration
- Explain what you're about to do before doing it
- Point out interesting details as they appear
- Connect back to business value frequently
- Use specific numbers and metrics

### Visual Focus
- Zoom browser if presenting to large audience
- Use browser zoom: Cmd/Ctrl + "+"
- Highlight important sections with cursor
- Scroll slowly when showing long lists

### Engagement
- Ask rhetorical questions: "Why do we care about P99 latency?"
- Relate to audience's pain points
- Encourage questions throughout
- Connect features to use cases

### Recovery
- If something fails, stay calm and use backup
- Turn failures into teaching moments
- Reference error handling capabilities
- Move to next section if issue persists

## Advanced Topics (if time permits)

### Custom Metrics
Show how to add custom metrics:
```python
cloudwatch.put_metric_data(
    Namespace='AgentCore/Observability',
    MetricData=[{
        'MetricName': 'CustomMetric',
        'Value': 123,
        'Unit': 'Count'
    }]
)
```

### Braintrust Metadata
Explain custom metadata tagging:
```python
braintrust.log(
    metadata={
        'environment': 'production',
        'user_tier': 'premium',
        'custom_field': 'value'
    }
)
```

### Alert Configuration
Walk through creating CloudWatch alarm:
- Go to CloudWatch > Alarms > Create Alarm
- Select metric: ErrorRate
- Set threshold: > 5% for 2 periods
- Configure SNS notification
- Demo how alert would trigger

### Cost Optimization
Show cost calculation:
- Input tokens: 150 @ $3/M = $0.00045
- Output tokens: 50 @ $15/M = $0.00075
- Total per query: $0.0012
- Multiply by daily query volume for monthly cost

### Scaling Considerations
Discuss production deployment:
- Metric aggregation strategies
- Sampling for high-volume systems
- Retention policies
- Multi-region considerations
- Data privacy and compliance

## Post-Demo Follow-Up

### Sharing Resources
- Provide link to GitHub repository
- Share CloudWatch dashboard JSON
- Distribute setup documentation
- Send Braintrust project invitation

### Feedback Collection
- What was most useful?
- What needs more explanation?
- What features are you excited to use?
- What's blocking implementation?

### Next Actions
- Schedule follow-up for implementation help
- Offer code review of integration
- Provide access to additional examples
- Connect with support channels

## Demo Success Checklist

- [ ] Successfully executed multi-tool query
- [ ] Showed both CloudWatch and Braintrust traces
- [ ] Demonstrated error handling
- [ ] Explained key metrics and their business value
- [ ] Connected operational and development workflows
- [ ] Answered audience questions
- [ ] Provided next steps and resources
- [ ] Collected feedback

## Additional Resources

### Documentation
- AgentCore Documentation: AWS Bedrock AgentCore docs
- CloudWatch Metrics: AWS CloudWatch User Guide
- Braintrust: https://www.braintrust.dev/docs

### Support
- GitHub Issues: For tutorial-specific questions
- AWS Support: For Amazon Bedrock and CloudWatch
- Braintrust Support: For Braintrust-specific issues

### Related Tutorials
- 01-AgentCore-basics: Introduction to AgentCore
- 02-AgentCore-tools: Building custom tools
- 05-AgentCore-streaming: Streaming responses
- Other observability tutorials in this directory

### Community
- AWS re:Post for Amazon Bedrock
- Braintrust Community Slack
- GitHub Discussions for this repository
