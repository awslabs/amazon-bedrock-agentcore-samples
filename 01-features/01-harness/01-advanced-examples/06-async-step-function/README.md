# Async Step Functions with AgentCore Harness

| Information         | Details                                                         |
|:--------------------|:----------------------------------------------------------------|
| Tutorial type       | Advanced Example                                                |
| Agent type          | Weather search assistant with async orchestration               |
| Agentic Framework   | AWS Step Functions + AgentCore Harness                          |
| LLM model           | Anthropic Claude Haiku 4.5                                      |
| Tutorial components | Step Functions, DynamoDB, Harness with MCP tools, CloudFormation|
| Example complexity  | Advanced                                                        |

## Overview

Build serverless, event-driven AI workflows using AWS Step Functions to orchestrate AgentCore harness invocations.

This example demonstrates:
- **Step Functions** orchestration (no Lambda needed for JSON parsing)
- **AgentCore Harness** with MCP tools for real-time web search
- **JSON extraction** from agent markdown responses
- **DynamoDB** storage with city-based queries

## Architecture

```
Trigger → Step Functions → Invoke Harness → Exa MCP Search
                ↓              ↓
         Extract JSON    Parse JSON
                ↓              ↓
            DynamoDB      Store Results
```

**Workflow:**
1. Receive input: `{city, date}`
2. Invoke harness: "Get weather for {city} on {date}"
3. Harness uses Exa MCP (https://mcp.exa.ai/mcp) to search web
4. Extract JSON from markdown using `States.StringSplit()` + `States.Format()`
5. Parse with `States.StringToJson()`
6. Store in DynamoDB with GSI for city queries

## Quick Start

### 1. Deploy
```bash
./deploy.sh
```

Creates:
- DynamoDB table `weather-data` (PK: id, SK: timestamp, GSI: city-index)
- AgentCore harness with Exa MCP tool
- Step Functions state machine `WeatherWorkflow`
- IAM roles

### 2. Test

**Interactive mode** (prompts for city/date):
```bash
./test_workflow.sh
```

**Use sample data**:
```bash
./test_workflow.sh --use-samples
```

**Manual execution**:
```bash
aws stepfunctions start-execution \
  --state-machine-arn $(jq -r '.stateMachineArn' deployment_info.json) \
  --input '{"city":"Tokyo","date":"2024-12-25"}'
```

### 3. Query Results

```bash
# All results
aws dynamodb scan --table-name weather-data

# Specific city
aws dynamodb query --table-name weather-data \
  --index-name city-index \
  --key-condition-expression "city = :city" \
  --expression-attribute-values '{":city":{"S":"Tokyo"}}'
```

### 4. Clean Up
```bash
./cleanup.sh
```

## Key Features

✅ **No Lambda required** - JSON parsing with Step Functions intrinsic functions  
✅ **MCP integration** - Exa search for real-time data  
✅ **Error handling** - 3x retry with exponential backoff  
✅ **Structured storage** - DynamoDB with city GSI  
✅ **Cost effective** - ~$0.27 per 1000 executions  

## How JSON Extraction Works

Step Functions extracts JSON from agent's markdown response without Lambda:

```javascript
// Agent returns: "Here's the weather:\n```json\n{\"city\":\"Tokyo\",...}\n```"

// Step 1: Split by '{' and '}'
parts = text.split('{')  // ["Here's...", "\"city\":\"Tokyo\",...}\n```"]
body = parts[1].split('}')[0]  // "\"city\":\"Tokyo\",..."

// Step 2: Reconstruct JSON
jsonString = '{' + body + '}'  // "{\"city\":\"Tokyo\",...}"

// Step 3: Parse
data = JSON.parse(jsonString)
```

Implemented as:
```json
{
  "Type": "Pass",
  "Parameters": {
    "reconstructed.$": "States.Format('{...}', 
      States.ArrayGetItem(States.StringSplit(...), 0))"
  }
}
```

## DynamoDB Schema

```
Table: weather-data
├─ id (String, PK) - UUID
├─ timestamp (String, SK) - Unix timestamp
├─ city (String) - City name
├─ date (String) - Query date
├─ temperature_c (Number)
├─ temperature_f (Number)
├─ conditions (String)
├─ input_city (String) - Original input
└─ input_date (String) - Original input

GSI: city-index
├─ city (String, PK)
└─ timestamp (String, SK)
```

## Use Cases

- **Scheduled updates** - EventBridge cron triggers
- **Multi-city monitoring** - Parallel execution with Map state
- **Historical analysis** - Query trends by city/date
- **Alert system** - SNS notifications on conditions
- **Data pipeline** - Feed to QuickSight/S3
