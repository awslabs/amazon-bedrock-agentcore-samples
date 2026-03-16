# Hosting Java Agents on AgentCore Runtime

## Overview

These tutorials demonstrate how to host **Java-based AI agents** on Amazon Bedrock AgentCore Runtime — the first Java examples in the official tutorials.

All existing tutorials in this repository use Python. These Java tutorials show equivalent patterns using Spring AI and the Embabel Agent Framework.

## Tutorial Examples

| Example                                                                    | Framework              | Features                          | Complexity   |
| -------------------------------------------------------------------------- | ---------------------- | --------------------------------- | ------------ |
| **[01-springai-with-bedrock-model](01-springai-with-bedrock-model)**       | Spring AI              | Conversational agent, ChatClient  | Easy         |
| **[02-embabel-with-bedrock-model](02-embabel-with-bedrock-model)**         | Embabel + Spring AI    | GOAP planning, AgentCore Browser  | Intermediate |

## Key Differences from Python Tutorials

| Concept              | Python                          | Java                                              |
|----------------------|---------------------------------|---------------------------------------------------|
| Entry point          | `@app.entrypoint`               | `@AgentCoreInvocation`                            |
| Agent framework      | Strands / LangGraph / CrewAI    | Spring AI ChatClient / Embabel GOAP               |
| Runtime starter      | `bedrock-agentcore-sdk`         | `spring-ai-agentcore-runtime-starter`              |
| Browser integration  | Direct SDK call                 | `spring-ai-agentcore-browser` + `ChatClient`       |
| Container base       | Python slim                     | Amazon Corretto 21 ARM64                           |
| Build tool           | pip / poetry                    | Maven                                              |

## Prerequisites

* Java 21 (Amazon Corretto recommended)
* Maven 3.9+
* Docker
* Node.js 18+ and npm (for CDK)
* AWS CLI configured with appropriate credentials
* AWS CDK CLI (`npm install -g aws-cdk`)
