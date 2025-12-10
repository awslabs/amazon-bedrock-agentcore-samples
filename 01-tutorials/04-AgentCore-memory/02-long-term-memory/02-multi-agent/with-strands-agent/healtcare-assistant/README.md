# Multi-Agent Healthcare System with Episodic Memory

> **Amazon Enhances AgentCore Memory with Episodic Memory, Enabling AI Agents to Learn From Experience**
>
> *New episodic memory capability helps developers capture and leverage prior experiences of AI agents, improving decision-making in complex tasks.*

A comprehensive example demonstrating **multi-agent coordination with episodic memory** using Amazon Bedrock AgentCore Memory. This tutorial shows how AI agents can learn from past interactions and improve decision-making over time.

## Overview

This tutorial showcases a healthcare assistant system with:
- **Supervisor Agent**: Routes patient questions to specialized agents
- **Claims Agent**: Handles insurance claims and billing queries
- **Demographics Agent**: Manages patient demographic information
- **Medication Agent**: Handles medication and prescription queries

Each agent maintains isolated short-term memory through **memory branching**, while sharing long-term insights through **episodic memory with custom strategies**.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Supervisor Agent                         │
│              (Routes to specialized agents)                 │
└────────────┬────────────┬────────────┬─────────────────────┘
             │            │            │
    ┌────────▼───┐  ┌────▼─────┐  ┌──▼──────────┐
    │   Claims   │  │Demographics│  │ Medication  │
    │   Agent    │  │   Agent    │  │   Agent     │
    └────────────┘  └────────────┘  └─────────────┘
         │               │                 │
         └───────────────┴─────────────────┘
                         │
              ┌──────────▼──────────┐
              │  AgentCore Memory   │
              │  with Branching     │
              └─────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
    ┌────▼─────────────┐    ┌───────────▼──────┐
    │ Short-Term       │    │ Long-Term         │
    │ (Events)         │    │ (Episodes +       │
    │ Per Branch       │    │  Reflections)     │
    └──────────────────┘    └───────────────────┘
```

## Memory Strategy

### Episodic Override with Custom Prompts

The system uses a custom episodic memory strategy with:

**Extraction**: Converts conversation events into structured episodes
- Prompt: "Extract patient interactions with healthcare agents"
- Namespace: `healthcare/{actorId}/{sessionId}`

**Consolidation**: Merges related episodes
- Prompt: "Consolidate healthcare conversations"

**Reflection**: Generates cross-session insights
- Prompt: "Generate insights from patient care patterns"
- Namespace: `healthcare/{actorId}` (shared across all sessions)

### Memory Branching

Each agent operates on its own memory branch:
- `main`: Supervisor agent routing decisions
- `claims_agent`: Insurance and billing conversations
- `demographics_agent`: Patient information updates
- `medication_agent`: Prescription discussions

**Benefits:**
- Agents don't see each other's conversations
- Clean separation of concerns
- All agents contribute to shared long-term memory
- Patient-level insights span all interactions

## Prerequisites

### AWS Services
- **Amazon Bedrock**: Access to Claude Sonnet 4 model
- **Amazon Bedrock AgentCore Memory**: For episodic memory with custom strategies
  - Requires gamma endpoints access for episodic override features
  - IAM role for memory execution
- **Amazon HealthLake** (optional): FHIR datastore with patient data
  - Can create new datastore with Synthea data during setup
  - Or use existing datastore

### IAM Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "healthlake:DescribeFHIRDatastore",
        "healthlake:CreateFHIRDatastore",
        "healthlake:ReadResource",
        "healthlake:SearchWithGet"
      ],
      "Resource": "*"
    }
  ]
}
```

### Python Environment
- Python 3.9+
- Jupyter Notebook or JupyterLab

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure AWS credentials:
```bash
aws configure
```

## Usage

### Quick Start

1. Open the notebook:
```bash
jupyter notebook multi-agent-healthcare-memory.ipynb
```

2. Run cells sequentially:
   - **Step 1**: Install dependencies
   - **Step 2**: Create IAM role for memory execution
   - **Step 3**: Configure memory strategy (enter memory name and patient ID)
   - **Step 3b**: Create or find memory
   - **Step 4**: Initialize data plane client with branching
   - **Step 5**: Configure HealthLake (create new or use existing)
   - **Step 6**: Create agents with dynamic HealthLake tools
   - **Step 7**: Test with interactive chat
   - **Step 8**: Verify short-term memory (events)
   - **Step 9**: Check long-term memory (episodes and reflections)

### Interactive Inputs

The notebook prompts for:
- **Memory name**: Custom name or auto-generated unique name
- **Patient ID**: Your patient ID or demo default
- **HealthLake datastore ID**: Existing datastore or create new with Synthea data
- **HealthLake region**: AWS region for HealthLake

### Testing the System

The interactive chat (Step 7) allows you to:
- Ask about insurance claims
- Request demographic information
- Query medications and prescriptions
- See supervisor routing in action
- Observe memory branching

Example questions:
```
You: What's the status of my insurance claim?
You: Can you tell me about my medications?
You: What's my current address on file?
```

Type `quit`, `exit`, or `q` to end the chat session.

## Memory Browser Integration

After running the notebook, you can visualize the memory using the memory browser:

1. Note the Memory ID from the configuration summary
2. Open memory browser at `http://localhost:8000`
3. Enter the Memory ID to explore:
   - **Short-term memory**: Events by branch
   - **Episodes**: Session-level consolidated memories
   - **Reflections**: Patient-level insights

## Key Concepts Demonstrated

### 1. Multi-Agent Coordination
- Supervisor pattern for routing
- Specialized agents with domain expertise
- Dynamic tool usage for real-time data

### 2. Memory Branching
- Isolated conversations per agent
- Branch-specific event storage
- Shared session context

### 3. Episodic Memory
- Custom extraction, consolidation, and reflection prompts
- Session-level episodes
- Patient-level reflections

### 4. HealthLake Integration
- Dynamic FHIR queries
- Real-time patient data access
- Synthea synthetic data support

## Customization

### Adding New Agents

```python
@tool
def get_patient_allergies(patient_id: str = PATIENT_ID) -> dict:
    """Get patient allergies from HealthLake"""
    return query_healthlake('AllergyIntolerance', {'patient': patient_id})

allergy_agent = Agent(
    model="global.anthropic.claude-sonnet-4-20250514-v1:0",
    system_prompt="You handle patient allergies. Use get_patient_allergies tool.",
    tools=[get_patient_allergies]
)
```

### Modifying Memory Strategy

Edit the `override_strategy` in Step 3 to customize:
- Extraction prompts
- Consolidation logic
- Reflection generation
- Namespace patterns

### Using Different Models

Change the `model` parameter in agent creation:
```python
Agent(
    model="anthropic.claude-3-5-sonnet-20241022-v2:0",  # Different model
    system_prompt="...",
    tools=[...]
)
```

## Troubleshooting

### Model Not Available
If you see "serviceUnavailableException", ensure:
- Using global inference profile: `global.anthropic.claude-sonnet-4-20250514-v1:0`
- Or region-specific profile for your region

### HealthLake Access Denied
Verify IAM permissions include:
- `healthlake:DescribeFHIRDatastore`
- `healthlake:ReadResource`
- `healthlake:SearchWithGet`

### Memory Creation Failed
Check that:
- IAM role has Bedrock invoke permissions
- Trust policy includes gamma endpoints for preprod
- Memory execution role ARN is correct

## Cleanup

After completing the tutorial, you can clean up resources to avoid ongoing charges:

1. Run the **Cleanup** cell at the end of the notebook
2. You'll be prompted to delete:
   - **Memory**: AgentCore Memory instance
   - **IAM Role**: Memory execution role
   - **HealthLake Datastore**: FHIR datastore (optional)

Each resource can be deleted independently based on your needs.

### Manual Cleanup

If needed, you can also delete resources manually:

```bash
# Delete memory
aws bedrock-agentcore-cp delete-memory --memory-id <MEMORY_ID> --region us-east-1

# Delete IAM role
aws iam delete-role-policy --role-name AgentCoreMemoryExecutionRole --policy-name BedrockModelAccess
aws iam delete-role --role-name AgentCoreMemoryExecutionRole

# Delete HealthLake datastore
aws healthlake delete-fhir-datastore --datastore-id <DATASTORE_ID> --region <REGION>
```

## Learn More

- [AgentCore Memory Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-memory.html)
- [Strands Agents Guide](https://strandsagents.com)
- [HealthLake FHIR API](https://docs.aws.amazon.com/healthlake/latest/devguide/working-with-FHIR-healthlake.html)
- [Memory Branching Patterns](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-memory-branching.html)

## License

This sample code is made available under the MIT-0 license. See the LICENSE file.
