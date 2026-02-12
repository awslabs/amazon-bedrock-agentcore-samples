# Cost Optimization Agent - Architecture

Copyright (c) 2024 Amazon Web Services, Inc.
Licensed under the Apache License 2.0 - see [LICENSE](../../LICENSE) file for details

## Overview

The Cost Optimization Agent is a **single-agent LLM-powered assistant** that helps users monitor, analyze, and optimize their AWS costs through natural language conversations. It uses one intelligent agent with multiple tool functions, not a multi-agent system.

---

## High-Level Architecture (Single-Agent Design)

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│  (CLI, API, Web App, Slack, etc.)                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Natural Language Query
                             │ "Are my costs higher than usual?"
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│              Amazon Bedrock AgentCore Runtime                      │
│  • HTTP Server (/invocations endpoint)                          │
│  • Request/Response handling                                    │
│  • Streaming support                                            │
│  • Auto-scaling                                                 │
│  • Health checks                                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│              BedrockAgentCoreApp (Python SDK)                   │
│  • Wraps agent code                                             │
│  • Manages streaming                                            │
│  • Handles payload format                                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│            SINGLE STRANDS AGENT (Cost Optimization)             │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Agent(                                                   │ │
│  │    model=BedrockModel("claude-3-5-sonnet"),              │ │
│  │    tools=[...5 tool functions...],                       │ │
│  │    system_prompt="You are an AWS Cost Expert..."         │ │
│  │  )                                                        │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Capabilities:                                                  │
│  • LLM orchestration                                            │
│  • Intelligent tool selection                                   │
│  • Multi-tool coordination                                      │
│  • Reasoning and analysis                                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│              Claude 3.5 Sonnet (via Bedrock)                    │
│  • Natural language understanding                               │
│  • Intent recognition                                           │
│  • Tool selection logic                                         │
│  • Response generation                                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│              5 Tool Functions (NOT separate agents)             │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ @tool                                                     │ │
│  │ def analyze_cost_anomalies(days: int = 7) -> str:        │ │
│  │     """Detect unusual cost spikes or anomalies"""        │ │
│  │     return detect_cost_anomalies(days)                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  1. analyze_cost_anomalies() - Detect cost spikes              │
│  2. get_budget_information() - Retrieve budget status          │
│  3. forecast_future_costs() - Predict future costs             │
│  4. get_service_cost_breakdown() - Service-level costs         │
│  5. get_current_month_costs() - Current month details          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      AWS APIs                                   │
│  • Cost Explorer API                                            │
│  • Budgets API                                                  │
│  • Compute Optimizer API                                        │
│  • CloudWatch API                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Amazon Bedrock AgentCore Runtime

**Purpose:** Production-grade hosting platform for the agent

**Features:**
- HTTP server with `/invocations` endpoint
- Auto-scaling based on load
- Health monitoring (`/ping` endpoint)
- CloudWatch Logs integration
- X-Ray tracing
- VPC support

**Deployment:**
- Containerized (Docker)
- Stored in Amazon ECR
- Managed by AgentCore service

---

### 2. BedrockAgentCoreApp

**Purpose:** Python SDK wrapper that connects your code to AgentCore Runtime

**Code:**
```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
async def process_request(payload):
    # Your agent logic here
    ...
```

**Responsibilities:**
- Payload parsing
- Streaming response handling
- Error management
- Integration with AgentCore Runtime

---

### 3. Strands Agent

**Purpose:** Agentic framework for LLM orchestration

**Code:**
```python
from strands import Agent, tool
from strands.models import BedrockModel

agent = Agent(
    model=BedrockModel("us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
    tools=[analyze_cost_anomalies, get_budget_information, ...],
    system_prompt="You are an AWS Cost Optimization Expert..."
)
```

**Capabilities:**
- Intelligent tool selection
- Multi-tool orchestration
- Reasoning and analysis
- Conversational responses
- Context management

---

### 4. Claude 3.5 Sonnet (via Amazon Bedrock)

**Purpose:** Large Language Model for understanding and reasoning

**Responsibilities:**
- Parse natural language queries
- Understand user intent
- Select appropriate tools
- Analyze tool results
- Generate helpful responses

**Example Flow:**
```
User: "Are my costs higher than usual?"
    ↓
Claude: "User wants anomaly detection"
    ↓
Claude: "I'll call analyze_cost_anomalies(7)"
    ↓
Claude: "I'll also call get_current_month_costs() for context"
    ↓
Claude: "Analyzing results..."
    ↓
Claude: "Your costs are stable at $28.10/month. No anomalies detected."
```

---

### 5. Tool Functions

**Purpose:** Decorated Python functions that the LLM can call

**Pattern:**
```python
@tool
def analyze_cost_anomalies(days: int = 7) -> str:
    """
    Detect unusual cost spikes or anomalies in AWS spending.
    
    Args:
        days: Number of days to analyze (default: 7)
    
    Returns:
        str: Detailed anomaly detection results
    """
    return detect_cost_anomalies(days)
```

**Available Tools:**
1. `analyze_cost_anomalies(days)` - Detect cost anomalies
2. `get_budget_information()` - Retrieve budget status
3. `forecast_future_costs(days_ahead)` - Predict future costs
4. `get_service_cost_breakdown(service_name, time_period)` - Service costs
5. `get_current_month_costs()` - Current month breakdown

---

## Request Flow Example

### Query: "Show me my budget and forecast"

```
1. User sends query
   ↓
2. AgentCore Runtime receives HTTP request
   ↓
3. BedrockAgentCoreApp parses payload
   ↓
4. Strands Agent receives prompt
   ↓
5. Claude analyzes: "User wants TWO things: budget + forecast"
   ↓
6. Claude calls: get_budget_information()
   ├─→ AWS Budgets API
   └─→ Returns: "No budgets configured"
   ↓
7. Claude calls: forecast_future_costs(30)
   ├─→ AWS Cost Explorer API
   └─→ Returns: "Forecast data..."
   ↓
8. Claude synthesizes response:
   "Here's your budget status... And here's your 30-day forecast..."
   ↓
9. Strands Agent streams response
   ↓
10. BedrockAgentCoreApp formats chunks
   ↓
11. AgentCore Runtime streams to user
```

---

## Data Flow

```
┌──────────────┐
│ User Query   │
│ (Text)       │
└──────┬───────┘
       │
       ↓
┌──────────────────────────────────────┐
│ LLM Processing                       │
│ • Intent: "budget + forecast"        │
│ • Tools: [get_budget, forecast]      │
└──────┬───────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────┐
│ Tool Execution (Parallel)            │
│ ┌────────────┐  ┌────────────┐      │
│ │ Budget API │  │ Forecast   │      │
│ │ Call       │  │ API Call   │      │
│ └────────────┘  └────────────┘      │
└──────┬───────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────┐
│ LLM Analysis                         │
│ • Combine results                    │
│ • Add context                        │
│ • Generate response                  │
└──────┬───────────────────────────────┘
       │
       ↓
┌──────────────┐
│ Streaming    │
│ Response     │
└──────────────┘
```

---

## Key Design Decisions

### 1. LLM-Powered Tool Selection

**Why:** Enables natural language understanding and flexible query handling

**Benefits:**
- Users can ask questions naturally
- Agent handles query variations automatically
- Can orchestrate multiple tools
- Provides reasoning and analysis

**Alternative (Rejected):** Keyword-based routing
- Limited to exact keyword matches
- Can't handle complex queries
- No reasoning capability

---

### 2. Strands Framework

**Why:** Provides robust LLM orchestration with minimal code

**Benefits:**
- Built-in tool management
- Streaming support
- Error handling
- Context management

**Alternative (Rejected):** Custom LLM integration
- More code to maintain
- Need to handle edge cases
- Reinventing the wheel

---

### 3. AgentCore Runtime Hosting

**Why:** Production-ready hosting with AWS integration

**Benefits:**
- Auto-scaling
- Monitoring and logging
- Security and compliance
- Easy deployment

**Alternative (Rejected):** Lambda or ECS
- More infrastructure to manage
- Need custom scaling logic
- Less integrated with Bedrock

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Developer Machine                        │
│  • cost_optimization_agent_llm.py                           │
│  • tools/*.py                                               │
│  • deploy.py                                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ python deploy.py
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    AWS CodeBuild                            │
│  • Builds Docker container                                  │
│  • Installs dependencies                                    │
│  • Packages agent code                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Push image
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Amazon ECR                               │
│  • Stores container image                                   │
│  • Version management                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Deploy
                         ↓
┌─────────────────────────────────────────────────────────────┐
│              Amazon Bedrock AgentCore Runtime                  │
│  • Pulls image from ECR                                     │
│  • Runs container                                           │
│  • Exposes /invocations endpoint                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    IAM Role                                 │
│  CostOptimizationAgentRole                                  │
│  • Cost Explorer permissions                                │
│  • Budgets permissions                                      │
│  • Bedrock model access                                     │
│  • CloudWatch Logs                                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Assumed by
                         ↓
┌─────────────────────────────────────────────────────────────┐
│              AgentCore Runtime                              │
│  • Uses role for AWS API calls                              │
│  • No hardcoded credentials                                 │
│  • Least privilege access                                   │
└─────────────────────────────────────────────────────────────┘
```

### Data Encryption and Key Management

#### Encryption at Rest
- **AgentCore Memory**: Uses AWS-managed encryption at rest with AWS KMS keys
- **CloudWatch Logs**: Configured with KMS encryption for log data protection
- **ECR Images**: Container images are encrypted at rest using AWS-managed keys
- **SSM Parameters**: Configuration parameters are encrypted using AWS KMS

#### Key Management Strategy
- **AWS-Managed Keys**: Primary encryption uses AWS-managed KMS keys for simplicity and security
- **Key Rotation**: Automatic key rotation is enabled for all AWS-managed keys
- **Key Access Controls**: IAM policies restrict key access to authorized services and roles only
- **Audit Trail**: All key usage is logged in AWS CloudTrail for compliance monitoring

#### Encryption in Transit
- **HTTPS/TLS**: All API communications use HTTPS with TLS 1.2 or higher
- **Internal Communications**: AgentCore components communicate over encrypted channels
- **AWS API Calls**: All AWS service interactions use encrypted HTTPS connections

---

## Observability

### CloudWatch Logs
- Runtime logs: `/aws/bedrock-agentcore/runtimes/{agent-id}-DEFAULT`
- Application logs from Python code
- Error tracking

### X-Ray Tracing
- Request tracing
- Performance monitoring
- Dependency mapping

### CloudWatch Metrics
- Invocation count
- Error rate
- Latency
- Token usage

### GenAI Dashboard
- Centralized monitoring
- Cost tracking
- Usage analytics

---

## Cost Structure

### Per Query Costs:
```
AWS API Calls:        ~$0.01
LLM Inference:        ~$0.003 (Claude 3.5 Sonnet via Amazon Bedrock)
AgentCore Runtime:    Pay per invocation
─────────────────────────────────
Total:                ~$0.013 per query
```

### Monthly Estimates:
| Queries/Month | Total Cost |
|---------------|------------|
| 100           | $1.30      |
| 1,000         | $13.00     |
| 10,000        | $130.00    |

---

## Scalability

- **Horizontal:** AgentCore Runtime auto-scales based on load
- **Vertical:** Container resources can be adjusted
- **Concurrent:** Handles multiple requests simultaneously
- **Global:** Can be deployed in multiple regions

---

## Future Enhancements

1. **Memory Integration**
   - Remember user preferences
   - Track cost baselines
   - Learn from interactions

2. **Additional Tools**
   - Reserved Instance recommendations
   - Savings Plans analysis
   - Resource tagging suggestions

3. **Multi-Account Support**
   - Consolidated billing analysis
   - Cross-account cost comparison
   - Organization-wide insights

4. **Proactive Alerts**
   - Scheduled cost reports
   - Anomaly notifications
   - Budget threshold alerts

---

## Bias and Fairness Considerations

The Cost Optimization Agent is designed with the following bias and fairness considerations:

### Balanced Service Recommendations
- **Equal Analysis**: The agent analyzes all AWS services with equal weight and does not favor specific services or vendors
- **Data-Driven Decisions**: Recommendations are based solely on usage patterns, costs, and performance metrics rather than subjective preferences
- **Service Agnostic**: The agent does not have built-in preferences for particular AWS services or third-party solutions

### Performance Impact Safeguards
- **Conservative Approach**: The agent includes safeguards against over-aggressive cost cutting that could negatively impact system performance
- **Risk Assessment**: Each recommendation includes an assessment of potential performance implications
- **Gradual Changes**: The agent recommends incremental changes rather than dramatic cost reductions that could cause service disruptions

### Multi-Account and Multi-Team Fairness
- **Equitable Analysis**: In multi-account scenarios, the agent provides fair analysis across all accounts regardless of usage volume
- **Team Neutrality**: Cost allocation and recommendations are based on actual usage patterns, not team size or organizational hierarchy
- **Proportional Recommendations**: Optimization suggestions are proportional to actual usage and spending patterns

### Transparency and Explainability
- **Clear Methodology**: All recommendations include explanations of the analysis methodology and data sources used
- **Confidence Levels**: The agent provides confidence levels for recommendations when possible
- **Limitation Acknowledgment**: The agent explicitly acknowledges limitations in its analysis and recommends human review for significant changes

### Human Oversight Requirements
- **Critical Decision Points**: Recommendations that could significantly impact production systems require explicit human approval
- **Threshold-Based Escalation**: Changes exceeding predefined cost or performance thresholds are flagged for human review
- **Audit Trail**: All recommendations and their outcomes are tracked for continuous improvement and bias detection

---

## Summary

The Cost Optimization Agent uses a modern, LLM-powered architecture that combines:
- **Amazon Bedrock AgentCore** for production hosting
- **Strands** for intelligent orchestration
- **Amazon Bedrock's Claude 3.5 Sonnet** for natural language understanding
- **Decorated Python tools** for AWS API integration

This architecture enables natural language interactions, intelligent tool selection, and conversational responses while maintaining production-grade reliability and scalability.
